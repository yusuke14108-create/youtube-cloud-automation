import json
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from generator.slides import make_thumbnail
from generator.youtube_auth import get_credentials

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "data" / "scripts"
VIDEO_DIR = ROOT / "data" / "video"
UPLOADS_DIR = ROOT / "data" / "uploads"
CATEGORY_ID = "17"  # Sports
MADE_FOR_KIDS = False


def _youtube_client():
    return build("youtube", "v3", credentials=get_credentials())


def upload_video(youtube, video_path, title, description, tags, thumbnail_path=None):
    body = {
        "snippet": {"title": title[:100], "description": description, "tags": tags, "categoryId": CATEGORY_ID},
        "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": MADE_FOR_KIDS},
    }
    request = youtube.videos().insert(
        part="snippet,status", body=body,
        media_body=MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4"),
    )
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"[info] upload progress: {int(status.progress() * 100)}%")
    video_id = response["id"]
    if thumbnail_path:
        try:
            youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(thumbnail_path))).execute()
        except HttpError as exc:
            print(f"[warn] custom thumbnail rejected: {exc}")
    return video_id


def _sources(data, source_ids):
    wanted = {str(x) for x in source_ids}
    facts = data.get("source_packet", {}).get("facts", [])
    lines, seen = [], set()
    for fact in facts:
        if str(fact.get("player_id")) not in wanted or fact.get("source") in seen:
            continue
        seen.add(fact.get("source"))
        lines.append(f"・{fact.get('source_label', 'MLB公式データ')}: {fact['source']}")
    return "\n".join(lines) or "・MLB公式データ（動画内記載）"


def main(script_path=None):
    if script_path is None:
        files = sorted(SCRIPTS_DIR.glob("*.json"))
        if not files:
            return None
        script_path = files[-1]
    script_path = Path(script_path)
    data = json.loads(script_path.read_text(encoding="utf-8"))
    run_id = script_path.stem
    video_dir = VIDEO_DIR / run_id
    youtube = _youtube_client()
    partial_path = UPLOADS_DIR / f"{run_id}.partial.json"
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    progress = json.loads(partial_path.read_text(encoding="utf-8")) if partial_path.exists() else {"longs": [], "shorts": []}
    rendered_manifest_path = ROOT / "data" / "assets" / run_id / "licenses.json"
    rendered_manifest = json.loads(rendered_manifest_path.read_text(encoding="utf-8")) if rendered_manifest_path.exists() else []
    credits = "\n".join(
        f"・{a.get('author')} / {a.get('license')} / {a.get('source_page')}"
        for a in data.get("visual_manifest", [])
    )
    rendered_credits = "\n".join(
        f"・{a.get('credit')} / {a.get('source_page')}" for a in rendered_manifest
    )
    credits = "\n".join(part for part in (credits, rendered_credits) if part) or "・外部映像・画像なし（独自図解を使用）"
    notice = "試合映像・放送映像の無断転載は行っていません。記録は取得時点のMLB公式データに基づきます。"

    long_ids = list(progress.get("longs", []))
    for i, video in enumerate(data["long_videos"], start=1):
        if i <= len(long_ids):
            continue
        thumb = video_dir / f"thumbnail_{i}.png"
        make_thumbnail("MLB", video["thumbnail_text"], video["title"], thumb)
        description = (
            f"{video['summary']}\n\n{notice}\n\n情報源:\n{_sources(data, video['source_ids'])}"
            f"\n\n素材クレジット:\n{credits}\n\nVOICEVOX:ずんだもん"
        )
        long_ids.append(upload_video(
            youtube, video_dir / f"long_{i}.mp4", video["title"], description,
            ["MLB", "メジャーリーグ", "日本人選手", "野球解説"], thumb,
        ))
        partial_path.write_text(json.dumps({"longs": long_ids, "shorts": progress.get("shorts", [])}, indent=2), encoding="utf-8")

    short_ids = list(progress.get("shorts", []))
    for i, short in enumerate(data["short_videos"], start=1):
        if i <= len(short_ids):
            continue
        long_link = f"https://youtu.be/{long_ids[0]}" if long_ids else ""
        description = (
            f"{short['script']}\n\n長尺版: {long_link}\n\n情報源:\n{_sources(data, short['source_ids'])}"
            f"\n\n{notice}\n\nVOICEVOX:ずんだもん"
        )
        short_ids.append(upload_video(
            youtube, video_dir / f"short_{i}.mp4", f"{short['hook']} #Shorts", description,
            ["MLB", "日本人選手", "Shorts"],
        ))
        partial_path.write_text(json.dumps({"longs": long_ids, "shorts": short_ids}, indent=2), encoding="utf-8")
    result = {"longs": long_ids, "shorts": short_ids}
    (UPLOADS_DIR / f"{run_id}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    partial_path.unlink(missing_ok=True)
    return result


if __name__ == "__main__":
    main()
