import argparse
import os
from pathlib import Path


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


def main():
    _load_local_env()
    parser = argparse.ArgumentParser(description="NBA channel operations")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("preflight", help="safely validate runtime dependencies")
    sub.add_parser("youtube-auth", help="perform YouTube OAuth and save token.json")
    run_parser = sub.add_parser("run", help="run or resume today's pipeline")
    run_parser.add_argument("--dry-run", action="store_true", help="generate through video but never upload")
    run_parser.add_argument("--upload-private", action="store_true", help="explicitly allow private YouTube uploads; never publishes")
    sub.add_parser("mock-pipeline", help="render a complete offline mock pipeline without uploading")
    args = parser.parse_args()
    if args.command == "preflight":
        from generator import preflight
        raise SystemExit(0 if preflight.run() else 1)
    if args.command == "run":
        from generator.run_daily import main as run_daily
        if args.dry_run and args.upload_private:
            parser.error("--dry-run and --upload-private cannot be combined")
        run_daily(allow_upload=args.upload_private)
        return
    if args.command == "mock-pipeline":
        from generator import mock_pipeline
        mock_pipeline.run()
        return
    from generator.youtube_auth import get_credentials
    get_credentials(force_interactive=True)
    print("[ok] YouTube OAuth token saved")


if __name__ == "__main__":
    main()
