import re
from pathlib import Path
from urllib.parse import urlparse

import requests

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


def find_commons_image(query, session=None):
    session = session or requests.Session()
    session.headers["User-Agent"] = "MedicalNewsYouTube/1.0 (thumbnail asset retrieval; contact via YouTube channel)"
    params = {
        "action": "query", "generator": "search", "gsrsearch": f"filetype:bitmap {query}",
        "gsrnamespace": 6, "gsrlimit": 10, "prop": "imageinfo", "iiprop": "url|extmetadata",
        "iiurlwidth": 1400, "format": "json", "origin": "*",
    }
    response = session.get(API, params=params, timeout=25)
    response.raise_for_status()
    for page in response.json().get("query", {}).get("pages", {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        if _license_ok(meta) and (info.get("thumburl") or info.get("url")):
            return {
                "title": page.get("title", ""), "url": info.get("thumburl") or info["url"],
                "source_page": info.get("descriptionurl", ""), "author": _plain(meta.get("Artist")) or "不明",
                "license": _plain(meta.get("LicenseShortName")) or _plain(meta.get("UsageTerms")),
                "license_url": _plain(meta.get("LicenseUrl")),
            }
    return None


def fetch_thumbnail_background(query: str, run_id: str, session=None):
    session = session or requests.Session()
    item = find_commons_image(query, session)
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
