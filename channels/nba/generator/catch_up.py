from generator.run_daily import main as run_daily
from generator.config import (
    ENABLE_UPLOAD, GENERATE_HOUR, GENERATE_MINUTE, now_local, reached,
)


def main():
    now = now_local()
    if not reached(now, GENERATE_HOUR, GENERATE_MINUTE):
        print(f"[nba] generation window not reached: {now.isoformat()}")
        return None

    run_daily(allow_upload=ENABLE_UPLOAD)

    # The upload itself carries the 06:00 publish reservation. A bulk publish
    # here could undo a user's manual cancellation.


if __name__ == "__main__":
    main()
