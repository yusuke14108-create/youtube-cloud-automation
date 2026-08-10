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


def _save_credentials_atomically(creds: Credentials, token_path: Path = None) -> None:
    """Write beside token.json, then atomically replace it with mode 0600."""
    path = token_path or TOKEN_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        temp_path = Path(temp_name)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(creds.to_json())
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_path, 0o600)
        os.replace(temp_path, path)
        os.chmod(path, 0o600)
        temp_path = None
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def get_credentials(reauthorize: bool = False) -> Credentials:
    creds = None
    if not reauthorize and TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_PATH), SCOPES)
        creds = flow.run_local_server(
            port=0,
            prompt="consent select_account",
            access_type="offline",
        )

    _save_credentials_atomically(creds)
    return creds


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Authorize the medical-news YouTube channel")
    parser.add_argument(
        "--reauthorize", action="store_true",
        help="ignore an existing token and replace it only after a successful new consent flow",
    )
    args = parser.parse_args()
    get_credentials(reauthorize=args.reauthorize)
    print(f"[info] credentials saved to {TOKEN_PATH}")
