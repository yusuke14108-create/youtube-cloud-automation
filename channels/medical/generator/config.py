import os
import shutil


def env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


LLM_PROVIDER = os.getenv("MEDICAL_NEWS_LLM_PROVIDER", "claude-cli").lower()
FFMPEG_BIN = os.getenv("FFMPEG_BIN") or shutil.which("ffmpeg") or "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"
FFPROBE_BIN = os.getenv("FFPROBE_BIN") or shutil.which("ffprobe") or "ffprobe"
FFMPEG_TIMEOUT = env_int("FFMPEG_TIMEOUT", 1800)
VOICEVOX_URL = os.getenv("VOICEVOX_URL", "http://localhost:50021").rstrip("/")
UPLOAD_PRIVACY = os.getenv("YOUTUBE_UPLOAD_PRIVACY", "private")

if UPLOAD_PRIVACY not in {"private", "unlisted"}:
    raise ValueError("YOUTUBE_UPLOAD_PRIVACY must be private or unlisted; automatic public uploads are forbidden")
