import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from generator.config import FFMPEG_BIN, TIMEZONE_NAME, VOICEVOX_URL
from generator.youtube_auth import CLIENT_SECRET_PATH, SCOPES, TOKEN_PATH

ROOT = Path(__file__).resolve().parent.parent


def _result(name, ok, detail, required=True):
    return {"name": name, "ok": bool(ok), "detail": detail, "required": required}


def check_ai():
    if os.getenv("LLM_PROVIDER", "").lower() == "gemini":
        key = os.getenv("GEMINI_API_KEY", "")
        model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        return _result("AI API", bool(key and model), f"Gemini key={'set' if key else 'missing'}, model={model}")
    url = os.getenv("AI_API_URL", "")
    key = os.getenv("AI_API_KEY", "")
    model = os.getenv("AI_MODEL", "")
    if not (url and key and model):
        return _result("AI API", False, f"endpoint={'set' if url else 'missing'}, key={'set' if key else 'missing'}, model={model or 'missing'}")
    models_url = url.replace("/chat/completions", "/models")
    try:
        response = requests.get(models_url, headers={"Authorization": f"Bearer {key}"}, timeout=8)
        return _result("AI API", response.ok, f"credentials endpoint returned HTTP {response.status_code}; model={model}")
    except requests.RequestException:
        return _result("AI API", False, "configured endpoint is not reachable")


def check_youtube():
    if not CLIENT_SECRET_PATH.exists():
        return _result("YouTube OAuth", False, "client_secret.json missing")
    try:
        secret = json.loads(CLIENT_SECRET_PATH.read_text(encoding="utf-8"))
        if not (secret.get("installed") or secret.get("web")):
            return _result("YouTube OAuth", False, "client secret has no installed/web application")
    except (OSError, json.JSONDecodeError):
        return _result("YouTube OAuth", False, "client secret is unreadable or invalid JSON")
    if not TOKEN_PATH.exists():
        return _result("YouTube OAuth", False, "token.json missing; run the auth command")
    try:
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
        refresh_error = None
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
                TOKEN_PATH.chmod(0o600)
            except Exception:
                refresh_error = "refresh rejected; run the auth command"
        secure = all((path.stat().st_mode & 0o077) == 0 for path in (CLIENT_SECRET_PATH, TOKEN_PATH))
        ok = bool(creds.valid) and secure
        detail = "token valid" if creds.valid else refresh_error or "token cannot refresh"
        if not secure:
            detail += "; credential permissions must be 600"
        return _result("YouTube OAuth", ok, detail)
    except Exception:
        return _result("YouTube OAuth", False, "token is unreadable or incompatible with required scopes")


def check_voicevox():
    try:
        response = requests.get(f"{VOICEVOX_URL}/version", timeout=3)
        return _result("VOICEVOX", response.ok, f"reachable at configured URL ({response.status_code})")
    except requests.RequestException:
        return _result("VOICEVOX", False, "not reachable at configured URL")


def check_ffmpeg():
    binary = shutil.which(FFMPEG_BIN) if not Path(FFMPEG_BIN).is_absolute() else FFMPEG_BIN
    if not binary or not Path(binary).exists():
        return _result("FFmpeg", False, "binary not found")
    proc = subprocess.run([binary, "-filters"], capture_output=True, text=True, timeout=5)
    first = proc.stdout.splitlines()[0] if proc.stdout else "version unavailable"
    has_subtitles = " subtitles " in proc.stdout
    detail = f"{first}; subtitles filter={'yes' if has_subtitles else 'missing'}"
    return _result("FFmpeg", proc.returncode == 0 and has_subtitles, detail)


def check_writes():
    failures = []
    for relative in ("data", "data/runs", "data/scripts", "data/audio", "data/video", "data/uploads", "data/upload_progress", "data/assets"):
        path = ROOT / relative
        try:
            path.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=path, prefix=".preflight-", delete=True):
                pass
        except OSError:
            failures.append(relative)
    return _result("Writable storage", not failures, "ok" if not failures else "not writable: " + ", ".join(failures))


def check_legacy_scheduler():
    launchctl = shutil.which("launchctl")
    if not launchctl:
        return _result("Legacy scheduler", True, "launchd not present", required=False)
    label = f"gui/{os.getuid()}/com.yishitoya.fintechnewsch.catchup"
    proc = subprocess.run([launchctl, "print", label], capture_output=True, timeout=5)
    if proc.returncode == 0:
        return _result("Legacy scheduler", False, "old finance launchd job is loaded; unload it before Docker/launchd operation", required=False)
    return _result("Legacy scheduler", True, "old finance launchd job is not loaded", required=False)


def run():
    checks = [check_ai(), check_youtube(), check_voicevox(), check_ffmpeg(), check_writes(), check_legacy_scheduler()]
    print(f"Timezone: {TIMEZONE_NAME}")
    for item in checks:
        print(f"[{'OK' if item['ok'] else 'FAIL'}] {item['name']}: {item['detail']}")
    return all(item["ok"] for item in checks if item["required"])
