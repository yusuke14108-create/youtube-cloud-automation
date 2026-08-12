import json
from datetime import datetime
from pathlib import Path

from generator.llm import run
from generator.performance import load_digest

ROOT = Path(__file__).resolve().parent.parent
SELECTED_DIR = ROOT / "data" / "facts"
SCRIPTS_DIR = ROOT / "data" / "scripts"

VISUAL_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["diagram", "comparison", "scorecard", "none"]},
        "caption": {"type": "string"},
        "labels": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
    },
    "required": ["kind", "caption", "labels"],
}

SECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "item_id": {"type": "string"},
        "category": {"type": "string"},
        "bullet": {"type": "string"},
        "narration": {"type": "string", "minLength": 160},
        "image_query": {"type": "string"},
        "key_points": {"type": "array", "minItems": 2, "maxItems": 3, "items": {"type": "string"}},
        "visual": VISUAL_SCHEMA,
    },
    "required": ["item_id", "category", "bullet", "narration", "image_query", "key_points", "visual"],
}

LONG_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"}, "thumbnail_text": {"type": "string"},
        "summary": {"type": "string"},
        "source_ids": {"type": "array", "items": {"type": "string"}},
        "sections": {"type": "array", "minItems": 4, "maxItems": 7, "items": SECTION_SCHEMA},
    },
    "required": ["title", "thumbnail_text", "summary", "source_ids", "sections"],
}

SHORT_SCHEMA = {
    "type": "object",
    "properties": {
        "item_id": {"type": "string"}, "category": {"type": "string"},
        "hook": {"type": "string"}, "script": {"type": "string", "minLength": 100},
        "image_query": {"type": "string"},
        "source_ids": {"type": "array", "items": {"type": "string"}},
        "visual": VISUAL_SCHEMA,
    },
    "required": ["item_id", "category", "hook", "script", "image_query", "source_ids", "visual"],
}

GENERATE_SCHEMA = {
    "type": "object",
    "properties": {
        "long_videos": {"type": "array", "minItems": 1, "maxItems": 2, "items": LONG_SCHEMA},
        "short_videos": {"type": "array", "minItems": 2, "maxItems": 3, "items": SHORT_SCHEMA},
    },
    "required": ["long_videos", "short_videos"],
}

PROMPT = """以下はMLB公式JSONエンドポイントから取得した、日本人選手に関する事実パケットです。
日本のMLBファン向けに、長尺1〜2本とShorts 2〜3本の台本を作成してください。

事実パケット:
{facts}

厳守事項:
- 入力にない移籍、故障、発言、球速、順位、記録、評価を作らない。
- 数字は入力値だけを使う。試合が未終了なら確定結果として語らない。
- source_idsには、根拠にしたfactsのplayer_idを文字列で入れる。
- 長尺は導入、本題2〜5節、まとめの4〜7節。各節は先に要点を述べる。
- Shortsは30〜60秒。冒頭2秒で結論につながる問いを置き、最後は長尺へ案内する。
- 権利のある試合映像・球団ロゴ・選手写真がある前提で書かない。
- 画面は独自図解、数値カード、比較図に加え、権利確認済みの一般的な野球写真を多く使って成立させる。
- 各セクションとShortsにimage_queryを必ず付ける。英語2〜4語で、baseball stadium、baseball glove、pitching moundなど一般素材を指定する。選手名、球団名、ロゴ、試合中継は指定しない。
- visual.labelsは入力にある数値や短い日本語だけにする。
- 選手や球団への中傷、根拠のない将来予測、賭博の推奨をしない。
- VOICEVOX向けに英字略称を読み上げない。MLBは「メジャーリーグ」と言い換える。
- タイトルは「【YYYY年M月D日】」で始める。

過去動画の傾向:
{performance}
"""


def latest_selected_file():
    files = sorted(SELECTED_DIR.glob("*.json"))
    return files[-1] if files else None


def main(selected_path=None):
    path = Path(selected_path) if selected_path else latest_selected_file()
    if path is None:
        return None
    packet = json.loads(path.read_text(encoding="utf-8"))
    result = run(PROMPT.format(facts=json.dumps(packet, ensure_ascii=False, indent=2), performance=load_digest()), GENERATE_SCHEMA)
    prefix = datetime.now().strftime("【%Y年%-m月%-d日】")
    if not 1 <= len(result["long_videos"]) <= 2 or not 2 <= len(result["short_videos"]) <= 3:
        raise ValueError("output must contain 1-2 long videos and 2-3 Shorts")
    for video in result["long_videos"]:
        if not video["title"].startswith("【"):
            video["title"] = prefix + video["title"]
        for section in video["sections"]:
            section["bullet"] = section["bullet"][:22]
            section["key_points"] = [p[:18] for p in section["key_points"][:3]]
    out = SCRIPTS_DIR / f"{path.stem}.json"
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({**result, "source_packet": packet}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[mlb] wrote scripts: {out}")
    return out


if __name__ == "__main__":
    main()
