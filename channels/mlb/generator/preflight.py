"""Safe readiness checks. Never prints API keys, tokens, or client secrets."""
import argparse
import os
import shutil
import subprocess
import sys

import requests
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError, TransportError
from google.oauth2.credentials import Credentials

from generator.synthesize import ENGINE_URL
from generator.youtube_auth import CLIENT_SECRET_PATH, SCOPES, TOKEN_PATH


def _result(name, ok, detail, required=True):
    status = "OK" if ok else ("ERROR" if required else "WARN")
    print(f"[{status}] {name}: {detail}")
    return ok or not required


def check_ai():
    provider = os.getenv("LLM_PROVIDER", "claude_cli")
    if provider == "anthropic":
        key_ok = bool(os.getenv("ANTHROPIC_API_KEY"))
        model_ok = bool(os.getenv("ANTHROPIC_MODEL"))
        return all([
            _result("AI API key", key_ok, "configured" if key_ok else "ANTHROPIC_API_KEY is missing"),
            _result("AI model", model_ok, os.getenv("ANTHROPIC_MODEL", "ANTHROPIC_MODEL is missing")),
        ])
    if provider == "gemini":
        key_ok = bool(os.getenv("GEMINI_API_KEY"))
        model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        return all([
            _result("AI API key", key_ok, "configured" if key_ok else "GEMINI_API_KEY is missing"),
            _result("AI model", bool(model), model),
        ])
    if provider == "claude_cli":
        path = shutil.which("claude") or ("/opt/homebrew/bin/claude" if os.path.exists("/opt/homebrew/bin/claude") else None)
        return _result("AI CLI", bool(path), "claude command found" if path else "claude command not found")
    return _result("AI provider", False, f"unsupported LLM_PROVIDER={provider}")


def check_youtube(online=True):
    if not CLIENT_SECRET_PATH.exists():
        return _result("YouTube client", False, "credentials/client_secret.json is missing")
    if not TOKEN_PATH.exists():
        return _result("YouTube OAuth", False, "credentials/token.json is missing; reauthorize")
    try:
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    except Exception:
        return _result("YouTube OAuth", False, "token file is invalid; reauthorize")
    if not creds.refresh_token:
        return _result("YouTube OAuth", False, "refresh token is missing; reauthorize")
    if not online:
        return _result("YouTube OAuth", True, "token structure present; online refresh skipped", required=False)
    try:
        creds.refresh(Request())
    except RefreshError:
        return _result("YouTube OAuth", False, "token expired or revoked; run the reauthorization command")
    except TransportError:
        return _result("YouTube OAuth", False, "refresh could not reach Google; check network and retry")
    except Exception as exc:
        return _result("YouTube OAuth", False, f"refresh failed ({type(exc).__name__})")
    return _result("YouTube OAuth", bool(creds.valid), "refresh succeeded" if creds.valid else "credentials remain invalid")


def check_voicevox(required=True):
    try:
        response = requests.get(f"{ENGINE_URL}/version", timeout=3)
        response.raise_for_status()
        return _result("VOICEVOX", True, f"reachable at {ENGINE_URL}", required)
    except requests.RequestException:
        return _result("VOICEVOX", False, f"unreachable at {ENGINE_URL}", required)


def check_ffmpeg():
    configured = os.getenv("FFMPEG_BIN")
    full = "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"
    path = configured if configured and os.path.isfile(configured) else (full if os.path.isfile(full) else shutil.which("ffmpeg"))
    if not path:
        return _result("FFmpeg", False, "ffmpeg executable not found")
    try:
        filters = subprocess.run([path, "-hide_banner", "-filters"], capture_output=True, text=True, timeout=10, check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return _result("FFmpeg", False, "ffmpeg could not list filters")
    if " subtitles " not in filters:
        return _result("FFmpeg", False, "subtitles/libass filter is missing; install a full FFmpeg build")
    return _result("FFmpeg", True, "ffmpeg with subtitles/libass found")


def ready(online=True, voicevox_required=True):
    return all([check_ai(), check_youtube(online=online), check_voicevox(required=voicevox_required), check_ffmpeg()])


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check MLB channel runtime readiness without exposing secrets")
    parser.add_argument("--offline", action="store_true", help="validate OAuth structure without refreshing it")
    parser.add_argument("--no-voicevox", action="store_true", help="make VOICEVOX optional for data/script-only stages")
    args = parser.parse_args(argv)
    ok = ready(online=not args.offline, voicevox_required=not args.no_voicevox)
    print(f"[{'OK' if ok else 'ERROR'}] preflight: {'ready' if ok else 'not ready'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
