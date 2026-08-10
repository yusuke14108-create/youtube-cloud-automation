"""Read-only YouTube OAuth diagnostic. Never opens a browser or rewrites tokens."""
import json
import sys

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from generator.youtube_auth import SCOPES, TOKEN_PATH


def main() -> int:
    if not TOKEN_PATH.exists():
        print(f"[error] token missing: {TOKEN_PATH}; run: python -m generator.youtube_auth")
        return 2
    try:
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
        if creds.expired:
            if not creds.refresh_token:
                print("[error] token expired and has no refresh token; re-authentication is required")
                return 3
            creds.refresh(Request())
        channel = build("youtube", "v3", credentials=creds).channels().list(part="snippet", mine=True).execute()
        items = channel.get("items", [])
        if not items:
            print("[error] OAuth works but no YouTube channel is available for this account")
            return 4
        print(json.dumps({"ok": True, "channel": items[0]["snippet"]["title"], "token_file": str(TOKEN_PATH)}, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(f"[error] YouTube OAuth validation failed: {type(exc).__name__}: {exc}")
        print("[action] run python -m generator.youtube_auth --reauthorize; the old token is kept unless consent succeeds")
        return 1


if __name__ == "__main__":
    sys.exit(main())
