import json
import argparse
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from generator.slides import SOURCE_LABELS, make_thumbnail
from generator.thumbnail_image import fetch_thumbnail_background
from generator.youtube_auth import get_credentials
from generator.artifacts import valid_video
from generator.config import UPLOAD_PRIVACY

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "data" / "scripts"
VIDEO_DIR = ROOT / "data" / "video"
UPLOADS_DIR = ROOT / "data" / "uploads"

CATEGORY_ID = "27"  # Education


def _scheduled_publish_at():
    raw = os.getenv("YOUTUBE_SCHEDULE_PUBLIC_HOUR", "").strip()
    if not raw:
        return None
    local_now = datetime.now(ZoneInfo(os.getenv("TZ", "Asia/Tokyo")))
    target = local_now.replace(hour=int(raw), minute=0, second=0, microsecond=0)
    if target <= local_now:
        target += timedelta(days=1)
    return target.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _youtube_client():
    creds = get_credentials()
    return build("youtube", "v3", credentials=creds)


def upload_video(youtube, video_path: Path, title: str, description: str, tags: list, thumbnail_path: Path = None) -> str:
    status_body = {"privacyStatus": UPLOAD_PRIVACY, "selfDeclaredMadeForKids": False}
    publish_at = _scheduled_publish_at() if UPLOAD_PRIVACY == "private" else None
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


def validate_upload_inputs(script_path=None):
    if script_path is None:
        script_files = sorted(SCRIPTS_DIR.glob("*.json"))
        if not script_files:
            raise RuntimeError("no script file found")
        script_path = script_files[-1]
    data = json.loads(Path(script_path).read_text(encoding="utf-8"))
    video_dir = VIDEO_DIR / Path(script_path).stem
    paths = [video_dir / "long.mp4"] + [video_dir / f"short_{i}.mp4" for i in range(1, len(data["short_scripts"]) + 1)]
    invalid = [str(path) for path in paths if not valid_video(path)]
    if invalid:
        raise RuntimeError(f"missing or invalid rendered videos: {invalid}")
    print(f"[validate] {len(paths)} videos are readable; no network calls or uploads were made")
    return True


def main(script_path=None, validate_only=False):
    if validate_only:
        return validate_upload_inputs(script_path)
    if script_path is None:
        script_files = sorted(SCRIPTS_DIR.glob("*.json"))
        if not script_files:
            print("[info] no script file found")
            return None
        script_path = script_files[-1]
    data = json.loads(script_path.read_text(encoding="utf-8"))

    run_id = script_path.stem
    video_dir = VIDEO_DIR / run_id
    source_items = data["source_items"]
    checkpoint_path = UPLOADS_DIR / f"{run_id}.partial.json"
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8")) if checkpoint_path.exists() else {"long": None, "shorts": {}}

    required_videos = [video_dir / "long.mp4"] + [video_dir / f"short_{i}.mp4" for i in range(1, len(data["short_scripts"]) + 1)]
    invalid = [str(path) for path in required_videos if not valid_video(path)]
    if invalid:
        raise RuntimeError(f"refusing upload; missing or invalid rendered videos: {invalid}")

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
        "medical",
        data["thumbnail_text"],
        data["title"],
        thumb_path,
        background_image_path=background["local_path"] if background else None,
    )

    sources_text = "\n".join(f"・{s['title']} ({SOURCE_LABELS.get(s['source'], s['source'])}): {s['url']}" for s in source_items)
    disclaimer = (
        "※本動画は医療従事者・医学生向けの情報整理を目的としています。"
        "個別の診断・治療を指示するものではありません。"
        "診療判断では最新の添付文書・公式通知・所属施設の手順をご確認ください。"
    )
    ncbi_notice = "\n\nPubMed/NCBI利用条件: https://www.ncbi.nlm.nih.gov/home/about/policies/" if any(s["source"] == "pubmed" for s in source_items) else ""
    thumb_credit = f"\n\nサムネイル画像: {background['credit']} ({background['source_page']})" if background else ""
    description = f"{data['summary']}\n\n{disclaimer}\n\n出典:\n{sources_text}{ncbi_notice}{thumb_credit}\n\nVOICEVOX:ずんだもん"
    long_id = checkpoint.get("long")
    if long_id:
        print(f"[checkpoint] reusing uploaded long video: {long_id}")
    else:
        long_id = upload_video(
            youtube, video_dir / "long.mp4", data["title"], description,
            tags=["医療ニュース", "医療従事者", "医学生"], thumbnail_path=thumb_path,
        )
        checkpoint["long"] = long_id
        checkpoint_path.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[info] uploaded long video: https://youtu.be/{long_id} ({UPLOAD_PRIVACY})")

    short_ids = []
    for i, short in enumerate(data["short_scripts"], start=1):
        short_title = f"{short['hook']} #Shorts"
        matching = next((s for s in source_items if s["id"] == short.get("item_id")), None)
        source_line = f"\n出典: {matching['url']}" if matching else ""
        short_description = (
            f"{short['script']}\n\n詳しくはこちら: https://youtu.be/{long_id}"
            f"{source_line}\n\nVOICEVOX:ずんだもん"
        )
        short_id = checkpoint.get("shorts", {}).get(str(i))
        if short_id:
            print(f"[checkpoint] reusing uploaded short {i}: {short_id}")
        else:
            short_id = upload_video(
                youtube, video_dir / f"short_{i}.mp4", short_title, short_description,
                tags=["医療ニュース", "Shorts"],
            )
            checkpoint.setdefault("shorts", {})[str(i)] = short_id
            checkpoint_path.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[info] uploaded short {i}: https://youtu.be/{short_id} ({UPLOAD_PRIVACY})")
        short_ids.append(short_id)

    result = {"long": long_id, "shorts": short_ids}

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    (UPLOADS_DIR / f"{run_id}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("script", nargs="?", help="path to script JSON")
    parser.add_argument("--validate-only", action="store_true", help="validate local files without OAuth or upload")
    args = parser.parse_args()
    main(Path(args.script) if args.script else None, validate_only=args.validate_only)
