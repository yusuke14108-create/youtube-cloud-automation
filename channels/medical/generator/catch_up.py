from datetime import datetime

from generator.auto_publish import main as auto_publish
from generator.run_daily import main as run_daily


def main():
    now = datetime.now()
    if now.hour < 5:
        print("[medical] before 05:00, catch-up not needed")
        return

    # run_daily is idempotent: it skips generation when today's upload exists.
    run_daily()

    # If the Mac starts after the review deadline, publish immediately. Between
    # 05:00 and 06:00 the normal 06:00 launch agent keeps the review window.
    if now.hour >= 6:
        auto_publish()


if __name__ == "__main__":
    main()
