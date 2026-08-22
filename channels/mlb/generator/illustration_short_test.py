"""Render one source-grounded MLB Short with an original player illustration."""
import json
from datetime import datetime

from generator.generate_scripts import SCRIPTS_DIR
from generator.render_video import main as render_video
from generator.run_daily import ensure_voicevox
from generator.synthesize import main as synthesize
from generator.upload_youtube import main as upload_youtube

SOURCE_URL = "https://www.mlb.com/news/shohei-ohtani-hits-30th-home-run-of-season-vs-rockies"


def main():
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S_illustration_test")
    script_path = SCRIPTS_DIR / f"{run_id}.json"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "long_videos": [],
        "short_videos": [{
            "item_id": "ohtani-30-hr",
            "category": "記録",
            "hook": "大谷翔平 6年連続30本塁打",
            "script": (
                "大谷翔平選手が、6年連続で30本塁打に到達しました。"
                "メジャーリーグ公式によると、8月19日の30号は、推定448フィートの2ラン本塁打です。"
                "この一打で30本塁打到達は6シーズン連続。"
                "打者として結果を残しながら、投手復帰へ向けた調整も続いています。"
                "二刀流の現在地を示す、大きな節目となりました。"
            ),
            "image_query": "Shohei Ohtani baseball",
            "illustration_path": "assets/illustrations/ohtani-two-way-20260823.png",
            "asset_kind": "illustration",
            "source_ids": ["660271"],
            "visual": {"kind": "scorecard", "caption": "6年連続", "labels": ["30本", "448ft"]},
        }],
        "source_packet": {"facts": [{
            "player_id": "660271", "player_name": "大谷翔平", "player_name_en": "Shohei Ohtani",
            "source": SOURCE_URL, "source_label": "MLB公式",
        }]},
        "visual_manifest": [{
            "author": "OpenAI image generation", "license": "Original illustration",
            "source_page": "Generated specifically for this channel",
        }],
    }
    script_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    ensure_voicevox()
    synthesize(script_path)
    render_video(script_path)
    result = upload_youtube(script_path)
    if len(result.get("shorts", [])) != 1 or result.get("longs"):
        raise RuntimeError(f"unexpected illustration test result: {result}")
    print(f"[mlb-illustration-test] private Short: https://youtu.be/{result['shorts'][0]}")
    return result


if __name__ == "__main__":
    main()
