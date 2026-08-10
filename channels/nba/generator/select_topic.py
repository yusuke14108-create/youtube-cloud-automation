import json
from pathlib import Path

from generator.claude_cli import run
from generator.performance import load_digest
from generator.config import DAILY_LONG_VIDEOS

ROOT = Path(__file__).resolve().parent.parent
NEW_ITEMS_DIR = ROOT / "data" / "new_items"
SELECTED_DIR = ROOT / "data" / "selected"

SELECT_SCHEMA = {
    "type": "object",
    "properties": {
        "selected_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 2},
        "reason": {"type": "string"},
    },
    "required": ["selected_ids", "reason"],
}

SELECT_PROMPT_TEMPLATE = """以下は日本人バスケットボール選手に関する本日のニュース候補です。

日本人選手を中心にNBAを解説するYouTubeチャンネルの長尺動画として、重複しないテーマを最大{max_topics}件選んでください。

選定基準:
- 試合結果、出場状況、移籍・契約、負傷、監督や本人の公式コメントなど検証可能な話題
- 同じ出来事を伝える転載記事は1テーマにまとめる
- 噂だけの記事、釣り見出し、情報源を確認できない話題は除外する
- 試合映像がなくても、独自図解・数字・戦術説明で成立すること

該当項目がなければ selected_ids を空配列にしてください。

## 過去動画の視聴傾向（参考情報）
{performance_digest}

## 一覧
{items_json}
"""


def latest_new_items_file():
    files = sorted(NEW_ITEMS_DIR.glob("*.json"))
    return files[-1] if files else None


def main(new_items_path=None):
    path = new_items_path or latest_new_items_file()
    if path is None:
        print("[info] no new_items file found")
        return None

    items = json.loads(path.read_text(encoding="utf-8"))
    if not items:
        print("[info] new_items file is empty")
        return None

    items_for_prompt = [
        {"id": it["id"], "player": it.get("player"), "date": it["date"], "title": it["title"], "url": it["url"]} for it in items
    ]
    prompt = SELECT_PROMPT_TEMPLATE.format(
        items_json=json.dumps(items_for_prompt, ensure_ascii=False, indent=2),
        performance_digest=load_digest(), max_topics=DAILY_LONG_VIDEOS,
    )

    result = run(prompt, SELECT_SCHEMA)
    selected_ids = result["selected_ids"][:DAILY_LONG_VIDEOS]
    if not selected_ids:
        print(f"[info] no item selected: {result['reason']}")
        return None

    SELECTED_DIR.mkdir(parents=True, exist_ok=True)
    out_paths = []
    for index, selected_id in enumerate(selected_ids, 1):
        selected_item = next((it for it in items if it["id"] == selected_id), None)
        if selected_item is None:
            continue
        out_path = SELECTED_DIR / f"{path.stem}_{index}.json"
        out_path.write_text(json.dumps({**selected_item, "reason": result["reason"]}, ensure_ascii=False, indent=2), encoding="utf-8")
        out_paths.append(out_path)
    return out_paths or None


if __name__ == "__main__":
    main()
