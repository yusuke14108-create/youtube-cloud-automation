from datetime import datetime
import json

from generator.upload_youtube import UPLOADS_DIR, _youtube_client


def main():
    files = sorted(UPLOADS_DIR.glob("*.json"))
    if not files:
        print("[info] no uploads file found")
        return

    path = files[-1]
    today = datetime.now().strftime("%Y%m%d")
    if not path.name.startswith(today):
        print(f"[info] latest uploads file ({path.name}) is not from today, nothing to publish")
        return

    data = json.loads(path.read_text(encoding="utf-8"))
    video_ids = [*data.get("longs", ([data["long"]] if data.get("long") else [])), *data["shorts"]]
    youtube = _youtube_client()
    response = youtube.videos().list(part="status", id=",".join(video_ids)).execute()
    statuses = {item["id"]: item["status"]["privacyStatus"] for item in response.get("items", [])}

    for video_id in video_ids:
        status = statuses.get(video_id)
        if status != "private":
            print(f"[info] {video_id}: already {status or 'missing'}, skipped")
            continue
        youtube.videos().update(
            part="status",
            body={"id": video_id, "status": {"privacyStatus": "public"}},
        ).execute()
        print(f"[info] {video_id}: published (was left private)")


if __name__ == "__main__":
    main()
