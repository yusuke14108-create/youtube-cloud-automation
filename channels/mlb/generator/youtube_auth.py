import argparse
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


def get_credentials(force_reauthorize=False) -> Credentials:
    creds = None
    if TOKEN_PATH.exists() and not force_reauthorize:
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

    TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    return creds


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Authorize YouTube for private uploads and analytics")
    parser.add_argument("--reauthorize", action="store_true", help="ignore the current token and request fresh consent")
    args = parser.parse_args()
    get_credentials(force_reauthorize=args.reauthorize)
    print(f"[info] credentials saved to {TOKEN_PATH}")
