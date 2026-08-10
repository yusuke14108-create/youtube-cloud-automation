import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def _load_local_env():
    path = Path(__file__).resolve().parent.parent / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


_load_local_env()


def int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    value = int(os.getenv(name, str(default)))
    return max(minimum, min(maximum, value))


def bool_env(name: str, default=False) -> bool:
    return os.getenv(name, "true" if default else "false").strip().lower() in {"1", "true", "yes", "on"}


CHANNEL_NAME = os.getenv("CHANNEL_NAME", "日本人選手 NBAニュース")
NBA_PLAYERS = [
    name.strip()
    for name in os.getenv("NBA_PLAYERS", "八村塁,河村勇輝,富永啓生").split(",")
    if name.strip()
]
DAILY_LONG_VIDEOS = int_env("DAILY_LONG_VIDEOS", 2, 1, 2)
DAILY_SHORTS = int_env("DAILY_SHORTS", 3, 2, 3)
VOICEVOX_URL = os.getenv("VOICEVOX_URL", "http://localhost:50021").rstrip("/")
VOICEVOX_SPEAKER_ID = int(os.getenv("VOICEVOX_SPEAKER_ID", "3"))
_MAC_FFMPEG_FULL = "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"
FFMPEG_BIN = os.getenv("FFMPEG_BIN", _MAC_FFMPEG_FULL if Path(_MAC_FFMPEG_FULL).exists() else "ffmpeg")
TIMEZONE_NAME = os.getenv("TZ", "Asia/Tokyo")
TIMEZONE = ZoneInfo(TIMEZONE_NAME)
GENERATE_HOUR = int_env("GENERATE_HOUR", 5, 0, 23)
GENERATE_MINUTE = int_env("GENERATE_MINUTE", 0, 0, 59)
PUBLISH_HOUR = int_env("PUBLISH_HOUR", 7, 0, 23)
PUBLISH_MINUTE = int_env("PUBLISH_MINUTE", 0, 0, 59)
ENABLE_UPLOAD = bool_env("ENABLE_UPLOAD", False)
ENABLE_AUTO_PUBLISH = bool_env("ENABLE_AUTO_PUBLISH", False)


def now_local() -> datetime:
    return datetime.now(TIMEZONE)


def reached(now: datetime, hour: int, minute: int) -> bool:
    return (now.hour, now.minute) >= (hour, minute)
