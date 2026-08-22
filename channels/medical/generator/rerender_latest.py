import json
from datetime import datetime

from generator.captions import ensure_short_cta
from generator.generate_scripts import SCRIPTS_DIR
from generator.render_video import main as render_video
from generator.synthesize import main as synthesize
from generator.upload_youtube import UPLOADS_DIR, _youtube_client, main as upload_youtube


def _cancel_previous_schedule(upload_path):
    if not upload_path or not upload_path.exists():
        return
    data = json.loads(upload_path.read_text(encoding="utf-8"))
    video_ids = [data.get("long"), *data.get("shorts", [])]
    youtube = _youtube_client()
    for video_id in filter(None, video_ids):
        response = youtube.videos().list(part="status", id=video_id).execute()
        if not response.get("items"):
            continue
        status = response["items"][0]["status"]
        status.pop("publishAt", None)
        status["privacyStatus"] = "private"
        youtube.videos().update(
            part="status",
            body={"id": video_id, "status": status},
        ).execute()
        print(f"[info] previous version left private with schedule removed: https://youtu.be/{video_id}")


def main():
    scripts = sorted(SCRIPTS_DIR.glob("*.json"))
    if not scripts:
        raise RuntimeError("no saved medical script available to rerender")
    source_path = scripts[-1]
    source_upload = UPLOADS_DIR / f"{source_path.stem}.json"
    data = json.loads(source_path.read_text(encoding="utf-8"))
    for short in data["short_scripts"]:
        short["script"] = ensure_short_cta(short["script"])

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S_redesign")
    output_path = SCRIPTS_DIR / f"{run_id}.json"
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[info] redesign script: {output_path}")

    synthesize(output_path)
    render_video(output_path)
    result = upload_youtube(output_path)
    _cancel_previous_schedule(source_upload)
    print(f"[medical-redesign] done: {result}")
    return result


if __name__ == "__main__":
    main()
