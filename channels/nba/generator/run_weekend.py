import sys
from datetime import datetime
import json

from generator import case_study, render_video, synthesize, upload_youtube
from generator.run_daily import _acquire_lock, _release_lock, ensure_voicevox_running


def main():
    today = datetime.now().strftime("%Y%m%d")
    existing = sorted(upload_youtube.UPLOADS_DIR.glob(f"{today}_*.json"))
    if existing:
        result = json.loads(existing[-1].read_text(encoding="utf-8"))
        print(f"[weekend] today's upload already exists, skipped: {existing[-1]}")
        return result

    if not _acquire_lock():
        print("[weekend] another run is already in progress, skipping")
        return None
    try:
        script_path = case_study.main()
        if script_path is None:
            print("[weekend] no case study topic available, stopping")
            return None

        if not ensure_voicevox_running():
            print("[weekend] VOICEVOX did not become ready in time, stopping", file=sys.stderr)
            return None

        if synthesize.main(script_path) is None:
            print("[weekend] synthesis failed, stopping")
            return None

        if render_video.main(script_path) is None:
            print("[weekend] render failed, stopping")
            return None

        result = upload_youtube.main(script_path)
        if result is None:
            print("[weekend] upload failed, stopping")
            return None

        print(f"[weekend] done: {result}")
        return result
    finally:
        _release_lock()


if __name__ == "__main__":
    main()
