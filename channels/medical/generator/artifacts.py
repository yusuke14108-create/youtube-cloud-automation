import json
import subprocess
import wave
from pathlib import Path

from generator.config import FFPROBE_BIN


def valid_wav(path: Path) -> bool:
    try:
        with wave.open(str(path), "rb") as audio:
            return audio.getnframes() > 0 and audio.getframerate() > 0
    except (OSError, wave.Error, EOFError):
        return False


def valid_video(path: Path) -> bool:
    if not path.exists() or path.stat().st_size < 1024:
        return False
    try:
        proc = subprocess.run(
            [FFPROBE_BIN, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
            capture_output=True, text=True, timeout=30,
        )
        duration = float(json.loads(proc.stdout)["format"]["duration"])
        return proc.returncode == 0 and duration > 0.1
    except (OSError, KeyError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired):
        return False


def valid_text(path: Path) -> bool:
    return path.exists() and bool(path.read_text(encoding="utf-8").strip())
