"""Deterministic, network-free fixture for full render dry-runs."""
import json
import math
import struct
import wave
from datetime import datetime
from pathlib import Path

from generator.generate_scripts import SCRIPTS_DIR
from generator.render_video import AUDIO_DIR, main as render_video
from generator.visual_assets import collect


def _write_wav(path, seconds=1.2, rate=24000):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as out:
        out.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        frames = [struct.pack("<h", int(900 * math.sin(2 * math.pi * 220 * i / rate))) for i in range(int(rate * seconds))]
        out.writeframes(b"".join(frames))


def _write_srt(path, text, seconds=1.2):
    path.write_text(f"1\n00:00:00,000 --> 00:00:01,200\n{text}\n", encoding="utf-8")


def create_fixture(long_count=2, short_count=3):
    if not 1 <= long_count <= 2 or not 2 <= short_count <= 3:
        raise ValueError("fixture requires 1-2 longs and 2-3 Shorts")
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S_mock")
    sections = [
        {"item_id": "intro", "category": "試合結果", "bullet": "今日の要点", "narration": "モック音声です。", "key_points": ["公式データ", "独自図解"], "visual": {"kind": "scorecard", "caption": "テスト", "labels": ["4打数", "2安打"]}},
        {"item_id": "detail", "category": "打撃", "bullet": "数字を確認", "narration": "モック音声です。", "key_points": ["2安打", "1打点"], "visual": {"kind": "comparison", "caption": "打撃結果", "labels": ["2安打", "1打点"]}},
        {"item_id": "summary", "category": "記録", "bullet": "今日のまとめ", "narration": "モック音声です。", "key_points": ["確認完了", "非公開のみ"], "visual": {"kind": "diagram", "caption": "まとめ", "labels": ["収集", "動画"]}},
        {"item_id": "source", "category": "選手解説", "bullet": "出典を確認", "narration": "モック音声です。", "key_points": ["出典保存", "権利確認"], "visual": {"kind": "diagram", "caption": "情報源", "labels": ["公式", "台帳"]}},
    ]
    data = {
        "long_videos": [{"title": f"【モック】長尺{i}", "thumbnail_text": "動作確認", "summary": "モック", "source_ids": ["660271"], "sections": sections} for i in range(1, long_count + 1)],
        "short_videos": [{"item_id": f"short{i}", "category": "MLB", "hook": f"モックShorts {i}", "script": "モック音声です。続きは長尺で。", "source_ids": ["660271"], "visual": {"kind": "scorecard", "caption": "テスト", "labels": ["2安打", "1打点"]}} for i in range(1, short_count + 1)],
        "source_packet": {"facts": [{"player_id": 660271, "source": "https://statsapi.mlb.com/mock", "source_label": "mock MLB data"}]},
    }
    script = SCRIPTS_DIR / f"{run_id}.json"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    collect(script)
    audio_dir = AUDIO_DIR / run_id
    audio_dir.mkdir(parents=True, exist_ok=True)
    for i in range(1, long_count + 1):
        _write_wav(audio_dir / f"long_{i}.wav")
        _write_srt(audio_dir / f"long_{i}.srt", "長尺モック字幕")
        (audio_dir / f"long_{i}_sections.json").write_text(json.dumps([{"bullet": s["bullet"], "duration": 0.3} for s in sections], ensure_ascii=False), encoding="utf-8")
    for i in range(1, short_count + 1):
        _write_wav(audio_dir / f"short_{i}.wav")
        _write_srt(audio_dir / f"short_{i}.srt", "ショートモック字幕")
    return script


def main(long_count=2, short_count=3):
    script = create_fixture(long_count, short_count)
    video_dir = render_video(script)
    expected = [*(video_dir / f"long_{i}.mp4" for i in range(1, long_count + 1)), *(video_dir / f"short_{i}.mp4" for i in range(1, short_count + 1))]
    if not all(p.exists() and p.stat().st_size for p in expected):
        raise RuntimeError("mock render did not produce every expected video")
    print(f"[mock] complete dry-run: {long_count} long, {short_count} Shorts -> {video_dir}")
    print("[mock] upload simulated only; no YouTube API call was made")
    return video_dir


if __name__ == "__main__":
    main()
