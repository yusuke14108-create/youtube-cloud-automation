import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT / "data" / "runs"


def path_for(day: str) -> Path:
    return RUNS_DIR / f"{day}.json"


def load(day: str) -> dict:
    path = path_for(day)
    if not path.exists():
        return {"day": day, "new_items_path": None, "topics": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save(state: dict) -> Path:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    path = path_for(state["day"])
    tmp = path.with_suffix(f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    return path


def artifact_ready(path, minimum_bytes=1) -> bool:
    target = Path(path) if path else None
    return bool(target and target.is_file() and target.stat().st_size >= minimum_bytes)
