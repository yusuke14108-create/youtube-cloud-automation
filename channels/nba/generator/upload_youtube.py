import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from generator.slides import make_thumbnail
from generator.thumbnail_image import fetch_thumbnail_background
from generator.youtube_auth import get_credentials

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "data" / "scripts"
VIDEO_DIR = ROOT / "data" / "video"
UPLOADS_DIR = ROOT / "data" / "uploads"
UPLOAD_PROGRESS_DIR = ROOT / "data" / "upload_progress"

CATEGORY_ID = "17"  # Sports


def _scheduled_publish_at():
    raw = os.getenv("YOUTUBE_SCHEDULE_PUBLIC_HOUR", "").strip()
    if not raw:
        return None
    local_now = datetime.now(ZoneInfo(os.getenv("TZ", "Asia/Tokyo")))
    target = local_now.replace(hour=int(raw), minute=0, second=0, microsecond=0)
    if target <= local_now:
        target += timedelta(days=1)
    return target.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _save_json_atomic(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _youtube_client():
    creds = get_credentials()
    return build("youtube", "v3", credentials=creds)


def upload_video(youtube, video_path: Path, title: str, description: str, tags: list, thumbnail_path: Path = None) -> str:
    status_body = {"privacyStatus": "private", "selfDeclaredMadeForKids": False}
    publish_at = _scheduled_publish_at()
    if publish_at:
        status_body["publishAt"] = publish_at
    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags,
            "categoryId": CATEGORY_ID,
        },
        "status": status_body,
    }
    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"[info] upload progress: {int(status.progress() * 100)}%")

    video_id = response["id"]

    if thumbnail_path is not None:
        try:
            youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(thumbnail_path))).execute()
        except HttpError as exc:
            print(f"[warn] custom thumbnail rejected (video still uploaded): {exc}")

    return video_id


def main(script_path=None):
    if script_path is None:
        script_files = sorted(SCRIPTS_DIR.glob("*.json"))
        if not script_files:
            print("[info] no script file found")
            return None
        script_path = script_files[-1]
    data = json.loads(script_path.read_text(encoding="utf-8"))

    run_id = script_path.stem
    video_dir = VIDEO_DIR / run_id
    source_item = data["source_item"]

    progress_path = UPLOAD_PROGRESS_DIR / f"{run_id}.json"
    progress = json.loads(progress_path.read_text(encoding="utf-8")) if progress_path.exists() else {"long": None, "shorts": {}}
    youtube = _youtube_client()

    background = None
    query = data.get("thumbnail_image_query")
    if query:
        try:
            background = fetch_thumbnail_background(query, run_id)
        except Exception as exc:
            print(f"[warn] thumbnail background fetch failed, falling back to gradient: {exc}")

    thumb_path = video_dir / "thumbnail.png"
    make_thumbnail(
        source_item["source"],
        data["thumbnail_text"],
        data["title"],
        thumb_path,
        background_image_path=background["local_path"] if background else None,
    )
    if background:
        print(f"[info] thumbnail background credit: {background['credit']} ({background['source_page']})")

    description = f"{data['summary']}\n\n出典: {source_item['title']}\n{source_item['url']}"
    licenses_path = ROOT / "data" / "assets" / run_id / "licenses.json"
    if licenses_path.exists():
        licenses = json.loads(licenses_path.read_text(encoding="utf-8"))
        if licenses:
            description += "\n\n使用素材（ライセンス確認済み）:"
            for item in licenses:
                description += f"\n- {item['credit']}: {item['source_page']}"
    if background:
        description += f"\n\nサムネイル画像: {background['credit']} ({background['source_page']})"
    long_id = progress.get("long")
    if not long_id:
        long_id = upload_video(
            youtube,
            video_dir / "long.mp4",
            data["title"],
            description,
            tags=["NBA", "日本人選手", "バスケットボール"],
            thumbnail_path=thumb_path,
        )
        progress["long"] = long_id
        _save_json_atomic(progress_path, progress)
        print(f"[info] uploaded long video: https://youtu.be/{long_id} (private)")
    else:
        print(f"[resume] reusing uploaded long video: {long_id}")

    short_ids = []
    for i, short in enumerate(data["short_scripts"], start=1):
        short_title = f"{short['hook']} #Shorts"
        short_description = f"{short['script']}\n\n詳しくはこちら: https://youtu.be/{long_id}"
        short_id = progress.get("shorts", {}).get(str(i))
        if not short_id:
            short_id = upload_video(
                youtube,
                video_dir / f"short_{i}.mp4",
                short_title,
                short_description,
                tags=["NBA", "日本人選手", "Shorts"],
            )
            progress.setdefault("shorts", {})[str(i)] = short_id
            _save_json_atomic(progress_path, progress)
            print(f"[info] uploaded short {i}: https://youtu.be/{short_id} (private)")
        else:
            print(f"[resume] reusing uploaded short {i}: {short_id}")
        short_ids.append(short_id)

    result = {"long": long_id, "shorts": short_ids}

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    _save_json_atomic(UPLOADS_DIR / f"{run_id}.json", result)

    return result


if __name__ == "__main__":
    main()
