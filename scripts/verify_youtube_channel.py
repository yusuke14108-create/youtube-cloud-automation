#!/usr/bin/env python3
"""Fail closed unless OAuth belongs to the configured YouTube channel."""
import argparse
import json
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--credentials-dir", type=Path, required=True)
    parser.add_argument("--expected-id", required=True)
    parser.add_argument("--expected-title", required=True)
    args = parser.parse_args()

    token = args.credentials_dir / "token.json"
    client = args.credentials_dir / "client_secret.json"
    for path in (token, client):
        if not path.is_file():
            raise SystemExit(f"[FAIL] missing credential file: {path.name}")
        json.loads(path.read_text(encoding="utf-8"))

    creds = Credentials.from_authorized_user_file(str(token), SCOPES)
    items = build("youtube", "v3", credentials=creds, cache_discovery=False).channels().list(
        part="snippet", mine=True
    ).execute().get("items", [])
    if len(items) != 1:
        raise SystemExit(f"[FAIL] expected exactly one OAuth channel, got {len(items)}")
    actual_id = items[0]["id"]
    actual_title = items[0]["snippet"]["title"]
    if actual_id != args.expected_id:
        raise SystemExit(
            f"[FAIL] refusing upload: expected {args.expected_title} ({args.expected_id}), "
            f"got {actual_title} ({actual_id})"
        )
    print(f"[OK] YouTube destination: {actual_title} ({actual_id})")


if __name__ == "__main__":
    main()
