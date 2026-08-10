#!/usr/bin/env python3
"""Conservative media checks before changing private uploads to public."""
import argparse
import json
import subprocess
from pathlib import Path


def probe(path: Path) -> dict:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        check=True, capture_output=True, text=True, timeout=60,
    )
    return json.loads(proc.stdout)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("channel_root", type=Path)
    parser.add_argument("--minimum-bytes", type=int, default=100_000)
    args = parser.parse_args()
    videos = sorted((args.channel_root / "data").rglob("*.mp4"))
    if not videos:
        raise SystemExit("[FAIL] no rendered MP4 files found")
    failures = []
    for video in videos:
        try:
            info = probe(video)
            streams = info.get("streams", [])
            duration = float(info.get("format", {}).get("duration", 0))
            has_video = any(s.get("codec_type") == "video" and s.get("width", 0) >= 720 and s.get("height", 0) >= 720 for s in streams)
            has_audio = any(s.get("codec_type") == "audio" for s in streams)
            ok = video.stat().st_size >= args.minimum_bytes and duration >= 10 and has_video and has_audio
            print(f"[{'OK' if ok else 'FAIL'}] {video.name}: {duration:.1f}s, {video.stat().st_size} bytes, video={has_video}, audio={has_audio}")
            if not ok:
                failures.append(video.name)
        except Exception as exc:
            failures.append(video.name)
            print(f"[FAIL] {video.name}: {type(exc).__name__}")
    if failures:
        raise SystemExit("[FAIL] quality gate rejected: " + ", ".join(failures))


if __name__ == "__main__":
    main()
