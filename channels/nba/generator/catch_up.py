from generator.auto_publish import main as auto_publish
from generator.run_daily import main as run_daily
from generator.config import (
    ENABLE_AUTO_PUBLISH, ENABLE_UPLOAD, GENERATE_HOUR, GENERATE_MINUTE,
    PUBLISH_HOUR, PUBLISH_MINUTE, now_local, reached,
)


def main():
    now = now_local()
    if not reached(now, GENERATE_HOUR, GENERATE_MINUTE):
        print(f"[nba] generation window not reached: {now.isoformat()}")
        return None

    run_daily(allow_upload=ENABLE_UPLOAD)

    if ENABLE_AUTO_PUBLISH and reached(now, PUBLISH_HOUR, PUBLISH_MINUTE):
        auto_publish()
    elif reached(now, PUBLISH_HOUR, PUBLISH_MINUTE):
        print("[safe] automatic public publishing is disabled")


if __name__ == "__main__":
    main()
