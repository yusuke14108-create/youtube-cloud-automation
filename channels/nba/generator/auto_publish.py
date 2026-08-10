import json
from datetime import datetime
from pathlib import Path

from googleapiclient.discovery import build

from generator.youtube_auth import get_credentials

ROOT = Path(__file__).resolve().parent.parent
UPLOADS_DIR = ROOT / "data" / "uploads"


def _youtube_client():
    creds = get_credentials()
    return build("youtube", "v3", credentials=creds)


def publish_if_still_private(youtube, video_id: str) -> str:
    resp = youtube.videos().list(part="status", id=video_id).execute()
    items = resp.get("items", [])
    if not items:
        print(f"[warn] {video_id}: not found, skipping")
        return "not_found"

    status = items[0]["status"]
    if status["privacyStatus"] != "private":
        print(f"[info] {video_id}: already {status['privacyStatus']}, leaving as is")
        return status["privacyStatus"]

    status["privacyStatus"] = "public"
    youtube.videos().update(part="status", body={"id": video_id, "status": status}).execute()
    print(f"[info] {video_id}: published (was left private)")
    return "public"


def main(uploads_path=None):
    today = datetime.now().strftime("%Y%m%d")
    paths = [uploads_path] if uploads_path else sorted(UPLOADS_DIR.glob(f"{today}_*.json"))
    if not paths:
        print("[info] no uploads file found")
        return None
    youtube = _youtube_client()
    results = {}
    for path in paths:
        uploads = json.loads(Path(path).read_text(encoding="utf-8"))
        for video_id in [uploads["long"], *uploads["shorts"]]:
            results[video_id] = publish_if_still_private(youtube, video_id)
    return results


if __name__ == "__main__":
    main()
