import json
import copy
import re
import requests
from bs4 import BeautifulSoup
from pathlib import Path

from generator.claude_cli import run
from generator.performance import load_digest

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
            "minItems": 5,
            "maxItems": 7,
            "items": {
                "type": "object",
                "properties": {
                    "bullet": {"type": "string"},
                    "narration": {"type": "string", "minLength": 300},
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
                "required": ["bullet", "narration", "image_query", "visual"],
            },
        },
        "short_scripts": {
            "type": "array",
            "minItems": 3,
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "hook": {"type": "string"},
                    "script": {"type": "string"},
                    "image_query": {"type": "string"},
                },
                "required": ["hook", "script", "image_query"],
            },
        },
    },
    "required": ["title", "thumbnail_text", "thumbnail_image_query", "summary", "long_sections", "short_scripts"],
}

GENERATE_PROMPT_TEMPLATE = """次のニュース候補を起点に、日本人選手を中心としたNBA解説動画の台本一式を作成してください。

出典: {source}
発表日: {date}
タイトル: {title}
URL: {url}

取得できた記事本文（広告・メニューを含む可能性があります）:
{source_excerpt}

URLの本文と、可能なら記事内で示されたチーム・リーグ・選手本人などの一次情報を確認してください。確認できない情報を事実として書かず、報道と分析を明確に区別してください。最新の所属、日付、試合結果、得点などを推測しないでください。

著作権ルール:
- NBA中継や試合映像、放送画面、無断転載SNS動画を使う前提の表現・演出を作らない
- 記事本文を長く引用・翻訳転載せず、事実を自分の言葉で要約する
- 映像がなくても、独自のコート図、数字カード、時系列、役割比較で理解できる構成にする
- image_queryは選手名・NBA・チーム名を避け、都市、一般的なバスケットボール用品、アリーナ外観などの英語一般語にする

作成するもの:
- title: 長尺動画のタイトル（視聴意欲を引く、誇張しすぎない、40字前後）
- thumbnail_text: サムネイルに載せる短い文字（10字前後。煽りすぎない）
- thumbnail_image_query: ライセンス確認済み静止画を探す英語一般語（2〜4語）。選手名・チーム名・NBA・試合映像を避け、basketball hoop、arena exterior、city skyline等にする
- summary: このニュースと分析の要約（200字程度）
- long_sections: 長尺動画（7〜10分）を5〜7個のセクションに分けた配列。各セクションは以下を持つ:
  - bullet: そのセクションの要点を表す短い見出し（画面に大きく表示する、10〜16字程度、体言止めや短いフレーズで）
  - narration: そのセクションのナレーション本文（日本語）。一文は40字程度までを目安に短く区切り、だらだら続く長い説明文にしない。「まず〜」「次に〜」「ポイントは3つあります。1つ目は〜」のように、要点ごとに区切って話す構成にする。
  - image_query: ライセンス確認済み静止画を探す英語一般語（2〜4語）。選手・チーム・リーグの固有名詞を使わない。全セクションに必須。
  - visual: 独自図解用データ。数字や役割の比較はkind="comparison"、移籍・出場経過はkind="timeline"、不要ならkind="none"。
    - kind="none": 上記のような具体的な数値・日付の資料が特にないセクション（導入・まとめなど）。この場合は他のフィールドを省略してよい。
    全セクションに無理にvisualを付けず、実際に数値や日付を提示しているセクションだけkindを"comparison"か"timeline"にすること。visualフィールド自体は全セクションに必ず含めること（省略禁止）。資料が不要なセクションでもkindフィールドに"none"を明示すること。
  全ナレーションを合計2600字以上にし、冒頭でニュースの要点、続いて数字・役割・背景、最後に今後の注目点をまとめる。
- short_scripts: 30〜60秒のショート動画を{short_count}本（各150〜300字）。長尺への誘導で終え、互いに違う切り口にする。

バスケットボール初心者にも、戦術用語を短く説明してください。選手への敬意を保ち、誹謗中傷や国籍による過剰な持ち上げを避けてください。

narrationではNBAなどのアルファベット略称を読み上げ用の日本語へ直すこと（例: NBAは「エヌビーエー」）。略称は画面表示用のsummaryやbulletでは使ってよい。

## 過去動画の視聴傾向（参考情報）
{performance_digest}
上記の傾向を参考にしつつ、セクションの切り口・構成・タイトルの付け方は毎回同じパターンを繰り返さず、変化をつけること。データがまだ少ない場合は無理に傾向に合わせず、多様な構成を試すこと。
"""


def latest_selected_file():
    files = sorted(SELECTED_DIR.glob("*.json"))
    return files[-1] if files else None


def fetch_source_excerpt(url: str) -> str:
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")
        for node in soup(["script", "style", "nav", "footer", "aside"]):
            node.decompose()
        text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
        return text[:16000] or "本文を取得できませんでした。URLを直接確認してください。"
    except requests.RequestException as exc:
        return f"本文取得失敗: {exc}。URLを直接確認し、確認できない数値は使用しないでください。"


def main(selected_path=None, short_count=3):
    path = selected_path or latest_selected_file()
    if path is None:
        print("[info] no selected item found")
        return None

    item = json.loads(path.read_text(encoding="utf-8"))

    prompt = GENERATE_PROMPT_TEMPLATE.format(
        source=item["source"], date=item["date"], title=item["title"], url=item["url"],
        source_excerpt=fetch_source_excerpt(item["url"]),
        performance_digest=load_digest(), short_count=short_count,
    )
    schema = copy.deepcopy(GENERATE_SCHEMA)
    schema["properties"]["short_scripts"]["minItems"] = short_count
    schema["properties"]["short_scripts"]["maxItems"] = short_count
    result = run(prompt, schema, allowed_tools=["WebFetch"])

    # --json-schema doesn't reliably enforce "required" inside array items, so the model
    # sometimes omits "visual" entirely rather than sending {"kind": "none"}. Normalize here
    # instead of trusting the model to always comply.
    for section in result["long_sections"]:
        section.setdefault("visual", {"kind": "none"})
        section.setdefault("image_query", section.get("bullet", item["title"]))
    for short in result["short_scripts"]:
        short.setdefault("image_query", short.get("hook", item["title"]))

    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = SCRIPTS_DIR / f"{path.stem}.json"
    out_path.write_text(
        json.dumps({**result, "source_item": item}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[info] wrote script: {out_path}")
    return out_path


if __name__ == "__main__":
    main()
