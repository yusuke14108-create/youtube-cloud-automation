from datetime import datetime

from generator.run_daily import main as run_daily


def main():
    now = datetime.now()
    if now.hour < 3:
        print("[medical] before 03:00, catch-up not needed")
        return

    # run_daily is idempotent: it skips generation when today's upload exists.
    run_daily()

    # The upload itself carries the 06:00 publish reservation. A bulk publish
    # here could undo a user's manual cancellation.


if __name__ == "__main__":
    main()
