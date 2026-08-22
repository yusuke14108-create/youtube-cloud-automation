import re
from pathlib import Path
from urllib.parse import urlparse

import requests
from generator.visual_media import _basketball_context_matches, _person_title_matches, load_recent_source_pages

ROOT = Path(__file__).resolve().parent.parent
ASSET_DIR = ROOT / "data" / "assets"
API = "https://commons.wikimedia.org/w/api.php"
ALLOWED = ("cc0", "public domain", "cc by ", "cc-by-", "cc by-sa", "cc-by-sa")
REJECTED = ("-nc", "noncommercial", "-nd", "no derivatives")


def _plain(value):
    return re.sub(r"<[^>]+>", "", (value or {}).get("value", "")).strip()


def _license_ok(meta):
    text = " ".join(_plain(meta.get(k)).lower() for k in ("LicenseShortName", "UsageTerms", "License"))
    return any(x in text for x in ALLOWED) and not any(x in text for x in REJECTED)


def find_commons_image(query, session=None, result_index=0, exclude_source_pages=None):
    session = session or requests.Session()
    session.headers["User-Agent"] = "FinanceNewsYouTube/1.0 (thumbnail asset retrieval; contact via YouTube channel)"
    params = {
        "action": "query", "generator": "search", "gsrsearch": f"filetype:bitmap {query}",
        "gsrnamespace": 6, "gsrlimit": 10, "prop": "imageinfo", "iiprop": "url|extmetadata",
        "iiurlwidth": 1400, "format": "json", "origin": "*",
    }
    response = session.get(API, params=params, timeout=25)
    response.raise_for_status()
    matches = []
    excluded = set(exclude_source_pages or ())
    for page in response.json().get("query", {}).get("pages", {}).values():
        title = page.get("title", "")
        if not _person_title_matches(query, title) or not _basketball_context_matches(query, title):
            continue
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        source_page = info.get("descriptionurl", "")
        if _license_ok(meta) and (info.get("thumburl") or info.get("url")) and source_page not in excluded:
            matches.append({
                "title": page.get("title", ""), "url": info.get("thumburl") or info["url"],
                "source_page": source_page, "author": _plain(meta.get("Artist")) or "不明",
                "license": _plain(meta.get("LicenseShortName")) or _plain(meta.get("UsageTerms")),
                "license_url": _plain(meta.get("LicenseUrl")),
            })
    return matches[result_index % len(matches)] if matches else None


def fetch_thumbnail_background(query: str, run_id: str, session=None):
    session = session or requests.Session()
    excluded = load_recent_source_pages(run_id)
    seed = sum(run_id.encode("utf-8"))
    item = find_commons_image(query, session, result_index=seed, exclude_source_pages=excluded)
    if item is None:
        item = find_commons_image(query, session, result_index=seed)
    if item is None:
        return None

    out_dir = ASSET_DIR / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(urlparse(item["url"]).path).suffix.lower()
    if suffix not in (".jpg", ".jpeg", ".png", ".webp"):
        suffix = ".jpg"
    path = out_dir / f"thumbnail_bg{suffix}"

    response = session.get(item["url"], timeout=40)
    response.raise_for_status()
    path.write_bytes(response.content)

    return {
        "local_path": str(path),
        "credit": f"{item['author']} / {item['license']}",
        "source_page": item["source_page"],
    }
