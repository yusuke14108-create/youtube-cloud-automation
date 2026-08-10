import json
import sys
from pathlib import Path

import requests

from crawler.sites import nba_news
from crawler.state import diff_new, load_state, save_state

ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / "data" / "state.json"
OUTPUT_DIR = ROOT / "data" / "new_items"

SITES = [nba_news]


def main():
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; regulation-news-bot/1.0)"})

    state = load_state(STATE_PATH)
    all_new_items = []

    for site in SITES:
        try:
            items = site.fetch_items(session)
        except Exception as exc:
            print(f"[warn] {site.SOURCE}: fetch failed: {exc}", file=sys.stderr)
            continue
        new_items = diff_new(site.SOURCE, items, state)
        print(f"[info] {site.SOURCE}: {len(items)} items, {len(new_items)} new")
        all_new_items.extend(new_items)

    save_state(STATE_PATH, state)

    if all_new_items:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        from datetime import datetime, timezone

        stamp = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d_%H%M%S")
        out_path = OUTPUT_DIR / f"{stamp}.json"
        out_path.write_text(json.dumps(all_new_items, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[info] wrote {len(all_new_items)} new items to {out_path}")
        return out_path
    else:
        print("[info] no new items")
        return None


if __name__ == "__main__":
    main()
