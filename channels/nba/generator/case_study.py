import json
import random
from datetime import datetime
from pathlib import Path

from generator.claude_cli import run
from generator.generate_scripts import GENERATE_SCHEMA
from generator.performance import load_digest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "data" / "scripts"
USED_LOG_PATH = ROOT / "data" / "case_study_used.json"

CASE_STUDY_PROMPT_TEMPLATE = """以下は過去に取り上げた制度変更のテーマです。これをベースに「ケーススタディ回」の動画台本一式を作成してください。

過去のテーマ:
タイトル: {title}
要約: {summary}
出典: {source_title} ({source_url})

このケーススタディ動画では、上記の制度変更が「具体的にどんな人に、いくらの影響があるのか」を、年収や家族構成の異なる複数のケースでシミュレーションして見せてください。単なる制度の再解説ではなく、「Aさんの場合」「Bさんの場合」のように具体的な人物像・金額を使い、視聴者が自分に当てはめて考えられるようにすること。

作成するもの:
- title: 長尺動画のタイトル（視聴意欲を引く、誇張しすぎない、40字前後。「ケース別」「シミュレーション」等が伝わるとよい）
- thumbnail_text: サムネイルに載せる短い文字（10字前後、インパクト重視）
- summary: このケーススタディの要約（200字程度）
- long_sections: 長尺動画（7〜10分）を5〜7個のセクションに分けた配列。各セクションは以下を持つ:
  - bullet: そのセクションの要点を表す短い見出し（画面に大きく表示する、10〜16字程度、体言止めや短いフレーズで。「Aさんの場合」のようなケース名も可）
  - narration: そのセクションのナレーション本文（日本語）。一文は40字程度までを目安に短く区切り、だらだら続く長い説明文にしない。
  - image_query: そのセクションの背景に動きのある写真・映像を表示するための短い英語キーワード（2〜4語、例:"family living room", "japanese yen coins"）。全セクションに必須。
  - visual: そのセクションの理解を助ける資料が必要な場合のみ設定する画面表示用データ。
    - kind="comparison": ケースごとの金額比較など、具体的な数値・条件が変わる場合。before_label/before_value、after_label/after_valueを使う（例: before_label="改正前の負担額" after_label="改正後の負担額"）。
    - kind="timeline": 施行日など特定の日付を強調したい場合。date_label/date_valueを入れる。
    - kind="none": 資料が不要なセクション。
    visualフィールド自体は全セクションに必ず含めること（省略禁止）。資料が不要なセクションでもkindフィールドに"none"を明示すること。
  全セクションのnarrationを合計して2600字以上（目安2800〜3200字、ナレーション読み上げは1分あたり約310字が目安）になるようにする。最初のセクションで結論の一部を提示し、最後のセクションはまとめにする。
- short_scripts: 30〜60秒のショート動画3本分の台本（それぞれ150〜300字）。一文を短く区切ること。各ショートは異なるケース・切り口で視聴者の興味を引き、最後に「詳しくは概要欄の長尺動画で」等、長尺動画への誘導で終えること。各ショートにもimage_query（背景用の英語キーワード）を必ず含めること。

このチャンネルは家計に直結する制度変更を一般視聴者向けにわかりやすく解説する内容です。専門用語は噛み砕いて説明してください。金額は過去のテーマの要約に忠実にし、正確な数値が分からない場合は「概算」であることを明示してください。

narrationにアルファベットの略称を書かないこと。VOICEVOXがローマ字をそのまま1文字ずつ読み上げてしまい不自然になるため。言及が必要な場合は日本語の説明で言い換えるか、省いて内容だけを話す。

## 過去動画の視聴傾向（参考情報）
{performance_digest}
上記の傾向を参考にしつつ、毎回同じ構成を繰り返さず変化をつけること。データがまだ少ない場合は多様な構成を試すこと。
"""


def _load_used_ids() -> set:
    if USED_LOG_PATH.exists():
        return set(json.loads(USED_LOG_PATH.read_text(encoding="utf-8")))
    return set()


def _save_used_ids(used: set) -> None:
    USED_LOG_PATH.write_text(json.dumps(sorted(used), ensure_ascii=False, indent=2), encoding="utf-8")


def pick_source_script():
    candidates = sorted(SCRIPTS_DIR.glob("*.json"))
    candidates = [c for c in candidates if not c.stem.endswith("_casestudy")]
    if not candidates:
        return None

    used = _load_used_ids()
    unused = [c for c in candidates if c.stem not in used]
    if not unused:
        used = set()
        unused = candidates

    chosen = random.choice(unused)
    used.add(chosen.stem)
    _save_used_ids(used)
    return chosen


def main():
    source_path = pick_source_script()
    if source_path is None:
        print("[info] no past script available for a case study")
        return None

    source_data = json.loads(source_path.read_text(encoding="utf-8"))
    prompt = CASE_STUDY_PROMPT_TEMPLATE.format(
        title=source_data["title"],
        summary=source_data["summary"],
        source_title=source_data["source_item"]["title"],
        source_url=source_data["source_item"]["url"],
        performance_digest=load_digest(),
    )
    result = run(prompt, GENERATE_SCHEMA)

    for section in result["long_sections"]:
        section.setdefault("visual", {"kind": "none"})
        section.setdefault("image_query", section.get("bullet", source_data["title"]))
    for short in result["short_scripts"]:
        short.setdefault("image_query", short.get("hook", source_data["title"]))

    run_id = f"{datetime.now():%Y%m%d_%H%M%S}_casestudy"
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = SCRIPTS_DIR / f"{run_id}.json"
    out_path.write_text(
        json.dumps({**result, "source_item": source_data["source_item"]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[info] wrote case study script (based on {source_path.name}): {out_path}")
    return out_path


if __name__ == "__main__":
    main()
