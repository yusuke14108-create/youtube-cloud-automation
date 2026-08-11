import json
import os
import subprocess
import time
from datetime import datetime

import requests

from generator.generate_scripts import SCRIPTS_DIR, main as generate_scripts
from generator.render_video import main as render_video
from generator.select_topics import SELECTED_DIR, main as select_topics
from generator.synthesize import ENGINE_URL, main as synthesize
from generator.upload_youtube import UPLOADS_DIR, main as upload_youtube
from generator.visual_assets import collect

VIDEO_DIR = UPLOADS_DIR.parent / "video"

LOCK_PATH = UPLOADS_DIR.parent / ".run_daily.lock"
STALE_LOCK_SECONDS = 1800


def _find_resume_point(today: str):
    """Resume today's furthest-progressed fact packet or script."""
    scripts = sorted(SCRIPTS_DIR.glob(f"{today}_*.json"))
    for script in reversed(scripts):
        try:
            is_mlb = "long_videos" in json.loads(script.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            is_mlb = False
        if is_mlb and not (UPLOADS_DIR / f"{script.stem}.json").exists():
            return "script", script
    selected = sorted(SELECTED_DIR.glob(f"{today}_*.json"))
    for sel in reversed(selected):
        if not (SCRIPTS_DIR / f"{sel.stem}.json").exists():
            return "selected", sel
    return None, None


def _acquire_lock():
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    if LOCK_PATH.exists():
        if time.time() - LOCK_PATH.stat().st_mtime < STALE_LOCK_SECONDS:
            return False
        LOCK_PATH.unlink()
    try:
        os.close(os.open(str(LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        return True
    except FileExistsError:
        return False


def _release_lock():
    LOCK_PATH.unlink(missing_ok=True)


def ensure_voicevox(timeout_seconds=90):
    try:
        requests.get(f"{ENGINE_URL}/version", timeout=2).raise_for_status()
        return
    except requests.RequestException:
        if os.getenv("VOICEVOX_AUTO_START", "1") != "1":
            raise RuntimeError(f"VOICEVOX is unavailable at {ENGINE_URL}")
        if subprocess.run(["which", "open"], capture_output=True).returncode != 0:
            raise RuntimeError(f"VOICEVOX is unavailable at {ENGINE_URL}; start the engine service")
        subprocess.run(["open", "-a", "VOICEVOX"], check=True)
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            requests.get(f"{ENGINE_URL}/version", timeout=2).raise_for_status()
            return
        except requests.RequestException:
            time.sleep(2)
    raise RuntimeError("VOICEVOX did not start")


def main(upload=True):
    today = datetime.now().strftime("%Y%m%d")
    existing = sorted(UPLOADS_DIR.glob(f"{today}_*.json"))
    if upload and existing:
        latest = json.loads(existing[-1].read_text(encoding="utf-8"))
        if "longs" in latest:
            return latest
    if not _acquire_lock():
        print("[mlb] another run is already in progress, skipping")
        return None
    try:
        stage, path = _find_resume_point(today)
        if stage == "script":
            print(f"[mlb] resuming from existing script: {path}")
            script = path
            collect(script)
        elif stage == "selected":
            print(f"[mlb] resuming from existing fact packet: {path}")
            script = generate_scripts(path)
            collect(script)
        else:
            selected = select_topics()
            script = generate_scripts(selected)
            collect(script)
        script_data = json.loads(script.read_text(encoding="utf-8"))
        video_dir = VIDEO_DIR / script.stem
        expected = [
            *(video_dir / f"long_{i}.mp4" for i in range(1, len(script_data["long_videos"]) + 1)),
            *(video_dir / f"short_{i}.mp4" for i in range(1, len(script_data["short_videos"]) + 1)),
        ]
        if not expected or not all(path.exists() and path.stat().st_size > 0 for path in expected):
            ensure_voicevox()
            synthesize(script)
            render_video(script)
        else:
            print(f"[mlb] rendered videos already exist for {script.stem}; skipping render")
        if not upload:
            print("[mlb] preview ready; upload skipped")
            return {"script": str(script)}
        return upload_youtube(script)
    finally:
        _release_lock()


if __name__ == "__main__":
    main()
