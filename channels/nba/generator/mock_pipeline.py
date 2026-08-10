import json
import math
import wave
from datetime import datetime
from pathlib import Path

from generator import pipeline_state, render_video, synthesize
from generator.config import now_local
from generator.generate_scripts import SCRIPTS_DIR

ROOT = Path(__file__).resolve().parent.parent


def _silent_wav(path: Path, duration: float, rate=24000):
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = int(duration * rate)
    with wave.open(str(path), "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(rate)
        target.writeframes(b"\0\0" * frames)


def _srt(path: Path, duration: float, text: str):
    milliseconds = math.floor(duration * 1000)
    stamp = f"00:00:{milliseconds // 1000:02d},{milliseconds % 1000:03d}"
    path.write_text(f"1\n00:00:00,000 --> {stamp}\n{text}\n", encoding="utf-8")


def run():
    run_id = f"{now_local():%Y%m%d_%H%M%S}_mock"
    new_items_dir = ROOT / "data" / "new_items"
    selected_dir = ROOT / "data" / "selected"
    new_items_dir.mkdir(parents=True, exist_ok=True)
    selected_dir.mkdir(parents=True, exist_ok=True)
    item = {"id": "mock", "source": "nba_news", "player": "テスト選手", "date": now_local().isoformat(), "title": "モックニュース", "url": "https://example.invalid/mock"}
    new_items_path = new_items_dir / f"{run_id}.json"
    selected_path = selected_dir / f"{run_id}_1.json"
    new_items_path.write_text(json.dumps([item], ensure_ascii=False, indent=2), encoding="utf-8")
    selected_path.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")

    sections = [
        {"bullet": label, "narration": "モック音声です。", "image_query": "", "visual": {"kind": "comparison", "before_label": "前半", "before_value": f"{i}点", "after_label": "後半", "after_value": f"{i + 2}点"}}
        for i, label in enumerate(("ニュースの要点", "数字の確認", "役割の変化", "チームへの影響", "今後の注目"), 1)
    ]
    shorts = [
        {"hook": "数字で確認", "script": "モックショートです。", "image_query": ""},
        {"hook": "次戦の注目", "script": "モックショートです。", "image_query": ""},
    ]
    script = {"title": "モック NBAニュース", "thumbnail_text": "動作確認", "thumbnail_image_query": "", "summary": "外部通信と投稿を行わない検証です。", "long_sections": sections, "short_scripts": shorts, "source_item": item}
    script_path = SCRIPTS_DIR / f"{run_id}_1.json"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")

    audio_dir = synthesize.AUDIO_DIR / script_path.stem
    duration = 0.8
    _silent_wav(audio_dir / "long.wav", duration * len(sections))
    _srt(audio_dir / "long.srt", duration * len(sections), "モック字幕")
    (audio_dir / "long_sections.json").write_text(json.dumps([{"bullet": s["bullet"], "duration": duration} for s in sections], ensure_ascii=False), encoding="utf-8")
    for index in range(1, len(shorts) + 1):
        _silent_wav(audio_dir / f"short_{index}.wav", duration)
        _srt(audio_dir / f"short_{index}.srt", duration, "モック字幕")

    original = (render_video.LONG_SIZE, render_video.SHORT_SIZE, render_video.FPS)
    render_video.LONG_SIZE, render_video.SHORT_SIZE, render_video.FPS = (640, 360), (360, 640), 5
    try:
        video_dir = render_video.main(script_path)
    finally:
        render_video.LONG_SIZE, render_video.SHORT_SIZE, render_video.FPS = original
    required = [video_dir / "long.mp4", video_dir / "short_1.mp4", video_dir / "short_2.mp4"]
    if not all(path.exists() and path.stat().st_size > 1024 for path in required):
        raise RuntimeError("mock rendering did not produce every expected video")

    state = {"day": run_id, "new_items_path": str(new_items_path), "topics": [{"selected_path": str(selected_path), "short_count": 2, "script_path": str(script_path), "stage": "video", "upload_skipped": True}]}
    pipeline_state.save(state)
    print(f"[ok] mock pipeline reached video stage without AI, network, VOICEVOX, or YouTube: {video_dir}")
    return video_dir
