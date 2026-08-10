import time
from generator.catch_up import main
from generator.config import now_local


INTERVAL_SECONDS = 900


if __name__ == "__main__":
    while True:
        started = now_local()
        try:
            print(f"[scheduler] starting {started.isoformat()}", flush=True)
            main()
        except Exception as exc:
            print(f"[scheduler] run failed: {exc}", flush=True)
        elapsed = (now_local() - started).total_seconds()
        time.sleep(max(5, INTERVAL_SECONDS - elapsed))
