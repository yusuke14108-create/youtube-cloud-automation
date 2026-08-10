import re
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parent.parent
ASSET_DIR = ROOT / "data" / "assets"
API = "https://commons.wikimedia.org/w/api.php"
ALLOWED = ("cc0", "public domain", "cc by ", "cc-by-", "cc by-sa", "cc-by-sa")
REJECTED = ("-nc", "noncommercial", "-nd", "no derivatives")
USER_AGENT = "JapanesePlayersBasketballNews/1.0 (licensed still-image retrieval)"


def _plain(value):
    return re.sub(r"<[^>]+>", "", (value or {}).get("value", "")).strip()


def _license_ok(meta):
    text = " ".join(_plain(meta.get(k)).lower() for k in ("LicenseShortName", "UsageTerms", "License"))
    return any(x in text for x in ALLOWED) and not any(x in text for x in REJECTED)


def _search_commons(query: str, filetype: str, session: requests.Session):
    params = {
        "action": "query", "generator": "search", "gsrsearch": f"filetype:{filetype} {query}",
        "gsrnamespace": 6, "gsrlimit": 10, "prop": "imageinfo", "iiprop": "url|extmetadata|mime",
        "iiurlwidth": 1400, "format": "json", "origin": "*",
    }
    response = session.get(API, params=params, timeout=25)
    response.raise_for_status()
    for page in response.json().get("query", {}).get("pages", {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        mime = info.get("mime", "")
        # For video, thumburl is a static poster-frame JPEG, not the clip itself — use the real file.
        # For photos, thumburl is a smaller resize of the same image, worth preferring.
        is_video = mime.startswith("video/")
        if filetype == "video" and not is_video:
            continue
        url = info.get("url") if is_video else (info.get("thumburl") or info.get("url"))
        if _license_ok(meta) and url:
            return {
                "title": page.get("title", ""), "url": url,
                "source_page": info.get("descriptionurl", ""), "author": _plain(meta.get("Artist")) or "不明",
                "license": _plain(meta.get("LicenseShortName")) or _plain(meta.get("UsageTerms")),
            }
    return None


def find_commons_photo(query: str, session=None):
    session = session or requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    return _search_commons(query, "bitmap", session)


def find_commons_video(query: str, session=None):
    session = session or requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    return _search_commons(query, "video", session)


MAX_DOWNLOAD_BYTES = 60 * 1024 * 1024


def _download(item: dict, out_path: Path, session: requests.Session, max_bytes: int = None) -> None:
    response = session.get(item["url"], timeout=60, stream=bool(max_bytes))
    response.raise_for_status()
    if not max_bytes:
        out_path.write_bytes(response.content)
        return
    total = 0
    with open(out_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=1024 * 256):
            total += len(chunk)
            if total > max_bytes:
                response.close()
                out_path.unlink(missing_ok=True)
                raise requests.RequestException(f"asset exceeds {max_bytes} bytes, aborted")
            f.write(chunk)


def fetch_visual_asset(query: str, out_dir: Path, stem: str, session=None):
    """Fetch a license-checked still image. Gameplay/broadcast video retrieval
    is intentionally disabled, even when a search result appears reusable."""
    if not query:
        return None
    session = session or requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        photo = find_commons_photo(query, session)
    except requests.RequestException:
        photo = None
    if photo:
        suffix = Path(urlparse(photo["url"]).path).suffix.lower()
        if suffix not in (".jpg", ".jpeg", ".png", ".webp"):
            suffix = ".jpg"
        path = out_dir / f"{stem}{suffix}"
        try:
            _download(photo, path, session)
            return {
                "kind": "photo", "local_path": str(path),
                "credit": f"{photo['author']} / {photo['license']}", "source_page": photo["source_page"],
                "query": query, "usage": stem,
            }
        except requests.RequestException:
            pass

    return None
