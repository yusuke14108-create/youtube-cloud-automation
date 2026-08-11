import os
import subprocess
import sys
import time
import json
from pathlib import Path

import requests

from crawler import main as crawler_main
from generator import generate_scripts, render_video, select_topic, synthesize, upload_youtube
from generator import pipeline_state
from generator.config import DAILY_LONG_VIDEOS, DAILY_SHORTS, VOICEVOX_URL, now_local

VOICEVOX_VERSION_URL = f"{VOICEVOX_URL}/version"
VOICEVOX_APP = "VOICEVOX"
VOICEVOX_WAIT_TIMEOUT_SEC = 60

LOCK_PATH = upload_youtube.UPLOADS_DIR.parent / ".run_daily.lock"
STALE_LOCK_SECONDS = 1800


def allocate_short_counts(topic_count: int, total_shorts: int) -> list[int]:
    if topic_count <= 0:
        return []
    base, extra = divmod(max(0, total_shorts), topic_count)
    return [base + (1 if i >= topic_count - extra else 0) for i in range(topic_count)]


def _acquire_lock():
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    if LOCK_PATH.exists():
        try:
            lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
            pid = int(lock["pid"])
            os.kill(pid, 0)
            if time.time() - LOCK_PATH.stat().st_mtime < STALE_LOCK_SECONDS:
                return False
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            pass
        LOCK_PATH.unlink()
    try:
        fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, json.dumps({"pid": os.getpid(), "started": now_local().isoformat()}).encode())
        os.close(fd)
        return True
    except FileExistsError:
        return False


def _release_lock():
    LOCK_PATH.unlink(missing_ok=True)


def _find_resume_point(today: str):
    """If an earlier run today crashed mid-pipeline (e.g. generate_scripts timed
    out), return the furthest-progressed artifact so we can finish it instead of
    re-crawling. The crawl marks items 'seen' in state.json as a side effect, so
    a fresh crawl would find 0 new items and the orphaned selection would never
    be picked up otherwise."""
    scripts = sorted(generate_scripts.SCRIPTS_DIR.glob(f"{today}_*.json"))
    for script in reversed(scripts):
        if not (upload_youtube.UPLOADS_DIR / f"{script.stem}.json").exists():
            return "script", script
    selected = sorted(generate_scripts.SELECTED_DIR.glob(f"{today}_*.json"))
    for sel in reversed(selected):
        if not (generate_scripts.SCRIPTS_DIR / f"{sel.stem}.json").exists():
            return "selected", sel
    return None, None


def _voicevox_ready() -> bool:
    try:
        return requests.get(VOICEVOX_VERSION_URL, timeout=2).ok
    except requests.RequestException:
        return False


def ensure_voicevox_running() -> bool:
    if _voicevox_ready():
        return True

    print("[daily] VOICEVOX not responding, launching app")
    if sys.platform == "darwin":
        subprocess.run(["open", "-a", VOICEVOX_APP], check=False)

    deadline = time.time() + VOICEVOX_WAIT_TIMEOUT_SEC
    while time.time() < deadline:
        if _voicevox_ready():
            return True
        time.sleep(3)

    return False


def _audio_ready(script_path):
    data = json.loads(script_path.read_text(encoding="utf-8"))
    directory = synthesize.AUDIO_DIR / script_path.stem
    required = [directory / "long.wav", directory / "long.srt", directory / "long_sections.json"]
    required += [directory / f"short_{i}.{ext}" for i in range(1, len(data["short_scripts"]) + 1) for ext in ("wav", "srt")]
    return all(pipeline_state.artifact_ready(path) for path in required)


def _video_ready(script_path):
    data = json.loads(script_path.read_text(encoding="utf-8"))
    directory = render_video.VIDEO_DIR / script_path.stem
    required = [directory / "long.mp4"] + [directory / f"short_{i}.mp4" for i in range(1, len(data["short_scripts"]) + 1)]
    return all(pipeline_state.artifact_ready(path, minimum_bytes=1024) for path in required)


def main(allow_upload=True):
    today = now_local().strftime("%Y%m%d")
    existing = sorted(upload_youtube.UPLOADS_DIR.glob(f"{today}_*.json"))
    if len(existing) >= DAILY_LONG_VIDEOS:
        return [json.loads(path.read_text(encoding="utf-8")) for path in existing]

    if not _acquire_lock():
        print("[daily] another run is already in progress, skipping")
        return None
    try:
        state = pipeline_state.load(today)
        if not state["topics"]:
            new_items_path = Path(state["new_items_path"]) if state.get("new_items_path") else crawler_main.main()
            if new_items_path is None:
                return None
            state["new_items_path"] = str(new_items_path)
            pipeline_state.save(state)
            selected_paths = select_topic.main(new_items_path)
            if not selected_paths:
                return None
            selected_paths = selected_paths[:max(0, DAILY_LONG_VIDEOS - len(existing))]
            existing_short_count = sum(len(json.loads(path.read_text(encoding="utf-8")).get("shorts", [])) for path in existing)
            counts = allocate_short_counts(len(selected_paths), max(0, DAILY_SHORTS - existing_short_count))
            state["topics"] = [{"selected_path": str(path), "short_count": count} for path, count in zip(selected_paths, counts)]
            pipeline_state.save(state)

        results = []
        for topic in state["topics"]:
            selected_path = Path(topic["selected_path"])
            script_path = Path(topic["script_path"]) if topic.get("script_path") else generate_scripts.main(selected_path, short_count=topic["short_count"])
            if not script_path:
                continue
            topic["script_path"] = str(script_path)
            topic["stage"] = "script"
            pipeline_state.save(state)

            if not _audio_ready(script_path):
                if not ensure_voicevox_running():
                    print("[daily] VOICEVOX did not become ready in time, stopping", file=sys.stderr)
                    return results or None
                if synthesize.main(script_path) is None:
                    continue
            topic["stage"] = "audio"
            pipeline_state.save(state)

            if not _video_ready(script_path) and render_video.main(script_path) is None:
                continue
            topic["stage"] = "video"
            pipeline_state.save(state)

            if allow_upload:
                result = upload_youtube.main(script_path)
                if result:
                    results.append(result)
                    topic["stage"] = "uploaded_private"
                    topic["upload_result"] = result
                    pipeline_state.save(state)
            else:
                print(f"[dry-run] upload skipped; reusable video: {render_video.VIDEO_DIR / script_path.stem}")
        return results or None
    finally:
        _release_lock()


if __name__ == "__main__":
    main()
