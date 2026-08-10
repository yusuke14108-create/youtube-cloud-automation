"""Stage-oriented pipeline for resumable local and Docker operation."""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from generator.collect_mlb import FACTS_DIR, main as collect_facts
from generator.generate_scripts import SCRIPTS_DIR, main as generate_scripts
from generator.mock_pipeline import main as mock_e2e
from generator.render_video import VIDEO_DIR, main as render_video
from generator.run_daily import ensure_voicevox
from generator.synthesize import AUDIO_DIR, main as synthesize
from generator.upload_youtube import UPLOADS_DIR, main as upload_youtube
from generator.visual_assets import collect as collect_assets

STAGES = ("collect", "script", "assets", "audio", "video", "upload-private")


def _latest(directory, today_only=False):
    pattern = f"{datetime.now():%Y%m%d}_*.json" if today_only else "*.json"
    files = sorted(directory.glob(pattern))
    return files[-1] if files else None


def _resolve_run(run_id=None):
    if run_id:
        fact = FACTS_DIR / f"{run_id}.json"
        script = SCRIPTS_DIR / f"{run_id}.json"
    else:
        script = _latest(SCRIPTS_DIR, today_only=True)
        fact = FACTS_DIR / f"{script.stem}.json" if script else _latest(FACTS_DIR, today_only=True)
    return fact if fact and fact.exists() else None, script if script and script.exists() else None


def _videos_complete(script):
    data = json.loads(script.read_text(encoding="utf-8"))
    directory = VIDEO_DIR / script.stem
    paths = [
        *(directory / f"long_{i}.mp4" for i in range(1, len(data["long_videos"]) + 1)),
        *(directory / f"short_{i}.mp4" for i in range(1, len(data["short_videos"]) + 1)),
    ]
    return bool(paths) and all(p.exists() and p.stat().st_size > 0 for p in paths)


def run(from_stage="collect", to_stage="upload-private", run_id=None, dry_run=False):
    start, end = STAGES.index(from_stage), STAGES.index(to_stage)
    if start > end:
        raise ValueError("--from-stage must not come after --to-stage")
    fact, script = _resolve_run(run_id)
    for stage in STAGES[start:end + 1]:
        if stage == "collect":
            if fact is None:
                fact = collect_facts()
            else:
                print(f"[resume] facts exist: {fact}")
        elif stage == "script":
            if script is None:
                if fact is None:
                    raise RuntimeError("fact packet missing; run collect first")
                script = generate_scripts(fact)
            else:
                print(f"[resume] script exists: {script}")
        elif stage == "assets":
            if script is None:
                raise RuntimeError("script missing; run script first")
            collect_assets(script)
        elif stage == "audio":
            if script is None:
                raise RuntimeError("script missing; run script first")
            ensure_voicevox()
            synthesize(script)
        elif stage == "video":
            if script is None:
                raise RuntimeError("script missing; run script first")
            if _videos_complete(script):
                print(f"[resume] videos already complete; render skipped: {VIDEO_DIR / script.stem}")
            else:
                render_video(script)
        elif stage == "upload-private":
            if script is None or not _videos_complete(script):
                raise RuntimeError("complete videos missing; run video first")
            if (UPLOADS_DIR / f"{script.stem}.json").exists():
                print(f"[resume] private upload record exists: {UPLOADS_DIR / f'{script.stem}.json'}")
            elif dry_run:
                data = json.loads(script.read_text(encoding="utf-8"))
                print(f"[dry-run] would privately upload {len(data['long_videos'])} long and {len(data['short_videos'])} Shorts")
            else:
                upload_youtube(script)
    return script


def main(argv=None):
    parser = argparse.ArgumentParser(description="Resumable MLB video pipeline")
    parser.add_argument("--from-stage", choices=STAGES, default="collect")
    parser.add_argument("--to-stage", choices=STAGES, default="upload-private")
    parser.add_argument("--run-id", help="resume a specific data run")
    parser.add_argument("--dry-run", action="store_true", help="never call the YouTube API")
    parser.add_argument("--mock", action="store_true", help="network-free 2-long/3-Short render test")
    args = parser.parse_args(argv)
    if args.mock:
        mock_e2e(2, 3)
        return 0
    run(args.from_stage, args.to_stage, args.run_id, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
