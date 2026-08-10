#!/usr/bin/env python3
"""Write GitHub Secrets to private runtime files without logging values."""
import argparse
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    client = os.environ.get("YT_CLIENT_SECRET_JSON")
    token = os.environ.get("YT_TOKEN_JSON")
    if not client or not token:
        raise SystemExit("missing YT_CLIENT_SECRET_JSON or YT_TOKEN_JSON")
    json.loads(client)
    json.loads(token)
    args.destination.mkdir(parents=True, exist_ok=True)
    for name, value in (("client_secret.json", client), ("token.json", token)):
        path = args.destination / name
        path.write_text(value, encoding="utf-8")
        path.chmod(0o600)
    print("[OK] runtime YouTube credentials created")


if __name__ == "__main__":
    main()
