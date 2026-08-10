"""Backward-compatible entry point: topic selection is now MLB fact collection."""
from generator.collect_mlb import FACTS_DIR as SELECTED_DIR, main


if __name__ == "__main__":
    main()
