import json
from datetime import datetime
from pathlib import Path

from generator.llm import run
from generator.performance import load_digest
from generator.config import LLM_PROVIDER
from generator.source_fetch import build_source_context

ROOT = Path(__file__).resolve().parent.parent
SELECTED_DIR = ROOT / "data" / "selected"
SCRIPTS_DIR = ROOT / "data" / "scripts"

GENERATE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "thumbnail_text": {"type": "string"},
        "thumbnail_image_query": {"type": "string"},
        "summary": {"type": "string"},
        "long_sections": {
            "type": "array",
            "minItems": 3,
            "maxItems": 8,
            "items": {
                "type": "object",
                "properties": {
                    "item_id": {"type": "string"},
                    "source": {"type": "string"},
                    "bullet": {"type": "string"},
                    "narration": {"type": "string", "minLength": 320},
                    "image_query": {"type": "string"},
                    "visual": {
                        "type": "object",
                        "properties": {
                            "kind": {"type": "string", "enum": ["comparison", "timeline", "none"]},
                            "before_label": {"type": "string"},
                            "before_value": {"type": "string"},
                            "after_label": {"type": "string"},
                            "after_value": {"type": "string"},
                            "date_label": {"type": "string"},
                            "date_value": {"type": "string"},
                        },
                        "required": ["kind"],
                    },
                },
                "required": ["item_id", "source", "bullet", "narration", "image_query", "visual"],
            },
        },
        "short_scripts": {
            "type": "array",
            "minItems": 3,
            "maxItems": 5,
            "items": {
                "type": "object",
                "properties": {
                    "item_id": {"type": "string"},
                    "source": {"type": "string"},
                    "hook": {"type": "string"},
                    "script": {"type": "string"},
                    "image_query": {"type": "string"},
                },
                "required": ["item_id", "source", "hook", "script", "image_query"],
            },
        },
    },
    "required": ["title", "thumbnail_text", "thumbnail_image_query", "summary", "long_sections", "short_scripts"],
}

GENERATE_PROMPT_TEMPLATE = """次の複数の医療系トピックについて、YouTube動画用の台本一式を作成してください。医療従事者・医学生向けのチャンネルです。

本日選定されたトピック（{count}件）:
{items_json}

まず各URLの内容をWebFetchツールで取得し、正確な内容を把握してください。推測で書かないこと。用量・適応・日付などの事実関係は原文に忠実にすること。専門用語は医療従事者・学生向けなので過度に噛み砕く必要はないが、不正確な単純化はしないこと。

作成するもの:
- title: 長尺動画（今日のまとめ回）のタイトル。先頭を必ず「【YYYY年M月D日】」とし、その後に主要トピック2〜3件と「医療ニュース」または「医学論文」を入れる。単なる項目の羅列ではなく、視聴者が内容を判断できる具体的なタイトルにする
- thumbnail_text: サムネイルに載せる短い文字（10字前後、インパクト重視）
- thumbnail_image_query: サムネイル背景に使う写真を検索するための短い英語キーワード（2〜4語、例:"medical vials", "pill capsules", "hospital corridor"。Wikimedia Commonsで実在しそうな一般的な物・情景を指すこと。特定の患者・製品名は避け、抽象的な医療イメージにする）
- summary: 今日のまとめの要約（200字程度）
- long_sections: 長尺動画の構成。以下の順で構成すること:
  1. 導入セクション1つ（item_id="intro", source="medical", bullet="今日のまとめ"のような導入見出し、今日扱う{count}件の概要を手短に紹介するnarration、visual.kind="none"）
  2. 選定された{count}件それぞれについて1セクションずつ（順番はそのまま、item_idは各項目のid、sourceは各項目のsource値を使う。bulletは画面表示用なので22文字以内の短い要点見出しにする。narrationはその話題の詳細解説。visualは用量や数値の変化がある場合はkind="comparison"、承認日・施行日など特定の日付を強調したい場合はkind="timeline"、それ以外はkind="none"）
  3. まとめセクション1つ（item_id="summary", source="medical", 全体の総括、visual.kind="none"）
  各セクションにimage_queryを必ず含めること。背景に動きのある写真・映像を表示するための短い英語キーワード（2〜4語、例:"medical vials", "hospital corridor", "laboratory microscope"）。Wikimedia Commonsで実在しそうな一般的な物・情景を指し、特定の患者・製品名は避ける。
  各narrationは320〜500字を目安にする。一文40字程度までを目安に短く区切ること。visualフィールドは全セクションに必ず含めること（省略禁止、不要ならkindに"none"を明示）。
- short_scripts: 合計{short_count}本のショート台本（それぞれ150〜300字、一文を短く区切ること）。まず全トピックを最低1本ずつ扱う。トピックが3件未満の場合は、重要度が高い話題を「臨床上の注意」「薬理・病態の学習ポイント」など異なる角度で展開し、重複した台本にしない。item_idは対応する項目のid、sourceはその項目のsource値。hookは短いフック文、scriptはその話題を30〜60秒で解説する内容で、最後に「詳しくは概要欄の長尺動画で」等、長尺動画への誘導で終えること。各ショートにもimage_query（背景用の英語キーワード、上記と同じ形式）を必ず含めること。

医療情報は不正確な要約が実害につながりやすいため、原文に無い数値・用量・適応・因果関係は絶対に創作しないこと。個別患者への診断・治療指示はしないこと。「速報時点の情報であり、診療判断は添付文書・公式通知・所属施設の手順を確認してください」という趣旨をまとめに含めること。

narrationにアルファベットの略称（WHO、CDC、FDAなど）を書かないこと。VOICEVOXがローマ字をそのまま1文字ずつ読み上げてしまい不自然になるため。言及が必要な場合は日本語の説明で言い換えるか、省いて内容だけを話す。薬剤の一般的な略称（略号ではなくカタカナ化された一般名）はそのまま使ってよい。略称は画面表示用のsummaryやbulletでは使ってよい。

## 過去動画の視聴傾向（参考情報）
{performance_digest}
上記の傾向を参考にしつつ、トピックの組み合わせ方・構成は毎回同じパターンを繰り返さず変化をつけること。データがまだ少ない場合は無理に傾向に合わせず、多様な構成を試すこと。
"""


def latest_selected_file():
    files = sorted(SELECTED_DIR.glob("*.json"))
    return files[-1] if files else None


def main(selected_path=None):
    path = selected_path or latest_selected_file()
    if path is None:
        print("[info] no selected item found")
        return None

    selected = json.loads(path.read_text(encoding="utf-8"))
    items = selected["items"]
    short_count = max(3, len(items))

    items_for_prompt = [
        {"id": it["id"], "source": it["source"], "date": it["date"], "title": it["title"], "url": it["url"]}
        for it in items
    ]
    prompt = GENERATE_PROMPT_TEMPLATE.format(
        count=len(items), short_count=short_count, items_json=json.dumps(items_for_prompt, ensure_ascii=False, indent=2),
        performance_digest=load_digest(),
    )
    allowed_tools = ["WebFetch"]
    if LLM_PROVIDER != "claude-cli":
        prompt += "\n\n以下は各URLから事前取得した原文です。この内容だけを根拠にしてください。\n\n" + build_source_context(items)
        allowed_tools = None
    result = run(prompt, GENERATE_SCHEMA, allowed_tools=allowed_tools)

    date_prefix = datetime.now().strftime("【%Y年%-m月%-d日】")
    if not result["title"].startswith("【"):
        result["title"] = f"{date_prefix}{result['title']}"

    expected_sections = len(items) + 2
    if len(result.get("long_sections", [])) != expected_sections:
        raise ValueError(f"expected {expected_sections} long sections, got {len(result.get('long_sections', []))}")
    if len(result.get("short_scripts", [])) != short_count:
        raise ValueError(f"expected {short_count} short scripts, got {len(result.get('short_scripts', []))}")

    for section in result["long_sections"]:
        section.setdefault("visual", {"kind": "none"})
        section.setdefault("image_query", section.get("bullet", "medical research"))
    for short in result["short_scripts"]:
        short.setdefault("image_query", short.get("hook", "medical research"))

    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = SCRIPTS_DIR / f"{path.stem}.json"
    out_path.write_text(
        json.dumps({**result, "source_items": items}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[info] wrote script: {out_path}")
    return out_path


if __name__ == "__main__":
    main()
