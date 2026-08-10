import argparse
import os
import tempfile
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]

ROOT = Path(__file__).resolve().parent.parent
CLIENT_SECRET_PATH = ROOT / "credentials" / "client_secret.json"
TOKEN_PATH = ROOT / "credentials" / "token.json"


def _save_credentials_atomic(creds: Credentials) -> None:
    """Replace token.json only after complete credentials were obtained.

    The temporary file lives beside token.json so os.replace remains atomic.
    Any existing token is left untouched if writing or OAuth fails.
    """
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=TOKEN_PATH.parent,
            prefix=".token.", suffix=".json.tmp", delete=False,
        ) as temp:
            temp_path = Path(temp.name)
            os.chmod(temp_path, 0o600)
            temp.write(creds.to_json())
            temp.flush()
            os.fsync(temp.fileno())
        os.replace(temp_path, TOKEN_PATH)
        TOKEN_PATH.chmod(0o600)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def get_credentials(force_interactive: bool = False) -> Credentials:
    creds = None
    # Reauthorization deliberately does not parse, refresh, rename, or delete
    # the old token. It remains the rollback copy until consent succeeds.
    if not force_interactive and TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    if not creds or not creds.valid:
        if not force_interactive and (not creds or not creds.refresh_token):
            raise RuntimeError("YouTube OAuth is not ready. Run: .venv/bin/python -m generator.cli youtube-auth")
        flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_PATH), SCOPES)
        creds = flow.run_local_server(port=0)

    _save_credentials_atomic(creds)
    return creds


def main():
    parser = argparse.ArgumentParser(description="Authorize the YouTube channel")
    parser.add_argument(
        "--reauthorize", action="store_true",
        help="ignore the existing token and start a fresh OAuth consent flow",
    )
    args = parser.parse_args()
    get_credentials(force_interactive=args.reauthorize)
    print(f"[info] credentials saved to {TOKEN_PATH}")


if __name__ == "__main__":
    main()
