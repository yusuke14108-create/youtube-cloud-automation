"""Safe launchd entry point: preflight, then generate and upload privately."""
import sys

from generator.pipeline import run
from generator.preflight import ready


def main():
    if not ready(online=True, voicevox_required=True):
        print("[error] scheduled private upload cancelled by preflight")
        return 1
    run("collect", "upload-private", dry_run=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
