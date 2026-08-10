import json
from pathlib import Path


def load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def diff_new(source: str, items: list[dict], state: dict) -> list[dict]:
    seen_ids = set(state.get(source, []))
    new_items = [item for item in items if item["id"] not in seen_ids]
    state[source] = list(seen_ids | {item["id"] for item in items})
    return new_items
