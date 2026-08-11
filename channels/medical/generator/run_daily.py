import os
import time
import subprocess
import sys
from datetime import datetime
import json

import requests

from crawler.main import main as crawl
from generator.generate_scripts import SCRIPTS_DIR, main as generate_scripts
from generator.render_video import main as render_video
from generator.select_topics import SELECTED_DIR, main as select_topics
from generator.synthesize import ENGINE_URL, main as synthesize
from generator.upload_youtube import UPLOADS_DIR, main as upload_youtube
from generator.config import VOICEVOX_URL, env_int

LOCK_PATH = UPLOADS_DIR.parent / ".run_daily.lock"
STALE_LOCK_SECONDS = env_int("PIPELINE_STALE_LOCK_SECONDS", 21600)


def _find_resume_point(today: str):
    """If an earlier run today crashed mid-pipeline (e.g. generate_scripts timed
    out), return the furthest-progressed artifact so we can finish it instead of
    re-crawling. The crawl marks items 'seen' in state.json as a side effect, so
    a fresh crawl would find 0 new items and the orphaned selection would never
    be picked up otherwise."""
    scripts = sorted(SCRIPTS_DIR.glob(f"{today}_*.json"))
    for script in reversed(scripts):
        if not (UPLOADS_DIR / f"{script.stem}.json").exists():
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


def ensure_voicevox(timeout_seconds: int = 90) -> None:
    try:
        requests.get(f"{ENGINE_URL}/version", timeout=2).raise_for_status()
        return
    except requests.RequestException:
        if os.getenv("VOICEVOX_AUTO_START", "1") == "0":
            raise RuntimeError(f"VOICEVOX is unavailable at {ENGINE_URL}; start the engine or container")
        if sys.platform == "darwin":
            subprocess.run(["open", "-a", "VOICEVOX"], check=True)
        else:
            command = os.getenv("VOICEVOX_START_COMMAND")
            if not command:
                raise RuntimeError(
                    f"VOICEVOX is unavailable at {ENGINE_URL}. On Linux use Docker Compose or set VOICEVOX_START_COMMAND"
                )
            subprocess.Popen(command.split())

    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            requests.get(f"{ENGINE_URL}/version", timeout=2).raise_for_status()
            return
        except requests.RequestException:
            time.sleep(2)
    raise RuntimeError("VOICEVOX did not start within the timeout")


def main():
    today = datetime.now().strftime("%Y%m%d")
    existing = sorted(UPLOADS_DIR.glob(f"{today}_*.json"))
    if existing:
        result = json.loads(existing[-1].read_text(encoding="utf-8"))
        print(f"[medical] today's upload already exists, skipped: {existing[-1]}")
        return result

    if not _acquire_lock():
        print("[medical] another run is already in progress, skipping")
        return None
    try:
        stage, path = _find_resume_point(today)
        if stage == "script":
            print(f"[medical] resuming from existing script: {path}")
            script_path = path
        elif stage == "selected":
            print(f"[medical] resuming from orphaned selection: {path}")
            script_path = generate_scripts(path)
        else:
            items_path = crawl()
            if items_path is None:
                print("[medical] no new items today, stopping")
                return None

            selected_path = select_topics(items_path)
            if selected_path is None:
                print("[medical] no suitable topics selected, stopping")
                return None

            script_path = generate_scripts(selected_path)

        ensure_voicevox()
        synthesize(script_path)
        render_video(script_path)
        result = upload_youtube(script_path)
        print(f"[medical] done: {result}")
        return result
    finally:
        _release_lock()


if __name__ == "__main__":
    main()
