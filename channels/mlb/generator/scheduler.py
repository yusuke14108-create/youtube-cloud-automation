"""Small container-native scheduler; avoids depending on a host cron daemon."""
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from generator.pipeline import run as run_pipeline
from generator.preflight import ready


def main():
    generate_hour = int(os.getenv("GENERATE_HOUR", "3"))
    generate_minute = int(os.getenv("GENERATE_MINUTE", "0"))
    timezone = ZoneInfo("Asia/Tokyo")
    last_generate = None
    while True:
        now = datetime.now(timezone)
        day = now.strftime("%Y%m%d")
        try:
            if (now.hour, now.minute) >= (generate_hour, generate_minute) and last_generate != day:
                if ready(online=True, voicevox_required=True):
                    run_pipeline("collect", "upload-private", dry_run=False)
                    last_generate = day
                else:
                    print("[error] scheduled private upload cancelled by preflight", flush=True)
            # The upload itself carries the 06:00 publish reservation. A bulk
            # publish could undo a user's manual cancellation.
        except Exception as exc:
            print(f"[error] scheduled job failed: {exc}", flush=True)
        time.sleep(300)


if __name__ == "__main__":
    main()
