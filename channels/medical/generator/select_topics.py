import json
from pathlib import Path

from generator.llm import run
from generator.performance import load_digest

ROOT = Path(__file__).resolve().parent.parent
NEW_ITEMS_DIR = ROOT / "data" / "new_items"
SELECTED_DIR = ROOT / "data" / "selected"

SELECT_SCHEMA = {
    "type": "object",
    "properties": {
        "selected_ids": {
            "type": "array",
            "items": {"type": "string"},
        },
        "reason": {"type": "string"},
    },
    "required": ["selected_ids", "reason"],
}

SELECT_PROMPT_TEMPLATE = """以下は本日、PMDA・厚生労働省(感染症情報)・国立健康危機管理研究機構(JIHS/NIID)・PubMedから新たに検知された発表・論文一覧です。

このチャンネルは医療従事者・医学生向けに、臨床・実務上意味のある医薬品・医療機器・感染症の動向を解説するYouTubeチャンネルです。今日取り上げる価値のある項目を3〜5件選んでください。

選定基準:
- 新薬・新医療機器の承認、効能追加、用法用量変更など臨床実務に影響する情報
- 副作用・安全性情報（添付文書改訂、使用上の注意改訂など）
- 感染症の発生動向における重要な変化（急増、新規株、警報レベル変更など）
- PubMed論文は、臨床試験・診療ガイドライン・メタ解析・系統的レビューのうち、診療や学習への示唆が明確でニュース価値の高いものを優先する
- 可能なら規制・安全性情報と新着論文をバランス良く選び、同種の話題だけに偏らせない
- 単なる人事異動、採用情報、一般向けイベント告知、定型的な統計更新（RSS的な定期更新で内容に変化がないもの）は除外する
- 該当する項目が3件未満の場合は、無理に選ばず該当するものだけを選んでよい（0件も可）

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
        {"id": it["id"], "source": it["source"], "date": it["date"], "title": it["title"]} for it in items
    ]
    prompt = SELECT_PROMPT_TEMPLATE.format(
        items_json=json.dumps(items_for_prompt, ensure_ascii=False, indent=2),
        performance_digest=load_digest(),
    )

    result = run(prompt, SELECT_SCHEMA)
    selected_ids = result["selected_ids"]

    if not selected_ids:
        print(f"[info] no items selected: {result['reason']}")
        return None

    by_id = {it["id"]: it for it in items}
    selected_items = []
    for sid in selected_ids:
        item = by_id.get(sid)
        if item is None:
            raise RuntimeError(f"selected id {sid!r} not found in items")
        selected_items.append(item)

    SELECTED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = SELECTED_DIR / f"{path.stem}.json"
    out_path.write_text(
        json.dumps({"items": selected_items, "reason": result["reason"]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[info] selected {len(selected_items)} items -> {out_path}")
    return out_path


if __name__ == "__main__":
    main()
