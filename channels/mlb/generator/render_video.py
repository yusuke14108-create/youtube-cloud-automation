import json
import os
import shutil
import subprocess
from pathlib import Path

from generator.slides import make_section_slide, make_short_slide

_FFMPEG_FULL = "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"
FFMPEG_BIN = os.getenv("FFMPEG_BIN") or (_FFMPEG_FULL if Path(_FFMPEG_FULL).exists() else None) or shutil.which("ffmpeg") or "ffmpeg"

ROOT = Path(__file__).resolve().parent.parent
AUDIO_DIR = ROOT / "data" / "audio"
SCRIPTS_DIR = ROOT / "data" / "scripts"
VIDEO_DIR = ROOT / "data" / "video"

LONG_SIZE = (1920, 1080)
SHORT_SIZE = (1080, 1920)

SUBTITLE_FONT = os.getenv("SUBTITLE_FONT", "Noto Sans CJK JP")
LONG_SUBTITLE_STYLE = (
    f"FontName={SUBTITLE_FONT},FontSize=14,Bold=1,PrimaryColour=&H00FFFFFF,"
    "OutlineColour=&H00000000,BorderStyle=1,Outline=1.5,Shadow=1,"
    "Alignment=2,MarginL=32,MarginR=32,MarginV=36,Spacing=0.2"
)

SHORT_SUBTITLE_STYLE = (
    f"FontName={SUBTITLE_FONT},FontSize=10,Bold=1,PrimaryColour=&H00FFFFFF,"
    "OutlineColour=&H00000000,BorderStyle=1,Outline=1.2,Shadow=0,"
    "Alignment=2,MarginL=22,MarginR=22,MarginV=70,Spacing=0.1"
)


def _escape_for_filter(path: Path) -> str:
    return str(path).replace("\\", "\\\\").replace(":", "\\:")


def render(wav_path: Path, srt_path: Path, slide_path: Path, out_path: Path) -> None:
    subtitles_arg = f"subtitles={_escape_for_filter(srt_path)}:force_style='{SHORT_SUBTITLE_STYLE}'"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        FFMPEG_BIN,
        "-y",
        "-loop", "1",
        "-i", str(slide_path),
        "-i", str(wav_path),
        "-vf", subtitles_arg,
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        str(out_path),
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)


def render_deck(image_paths: list, durations: list, wav_path: Path, srt_path: Path, out_path: Path) -> None:
    concat_path = out_path.parent / f"{out_path.stem}_concat.txt"
    lines = []
    for image_path, duration in zip(image_paths, durations):
        lines.append(f"file '{image_path}'")
        lines.append(f"duration {duration}")
    lines.append(f"file '{image_paths[-1]}'")
    concat_path.parent.mkdir(parents=True, exist_ok=True)
    concat_path.write_text("\n".join(lines), encoding="utf-8")

    subtitles_arg = f"subtitles={_escape_for_filter(srt_path)}:force_style='{LONG_SUBTITLE_STYLE}'"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        FFMPEG_BIN,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_path),
        "-i", str(wav_path),
        "-vf", subtitles_arg,
        "-r", "25",
        "-fps_mode", "cfr",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        str(out_path),
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)


def main(script_path=None):
    if script_path is None:
        script_files = sorted(SCRIPTS_DIR.glob("*.json"))
        if not script_files:
            print("[info] no script file found")
            return None
        script_path = script_files[-1]
    data = json.loads(script_path.read_text(encoding="utf-8"))

    run_id = script_path.stem
    audio_dir = AUDIO_DIR / run_id
    video_dir = VIDEO_DIR / run_id

    for video_index, video in enumerate(data["long_videos"], start=1):
        durations_data = json.loads((audio_dir / f"long_{video_index}_sections.json").read_text(encoding="utf-8"))
        bullets = [s["bullet"] for s in video["sections"]]
        image_paths, durations = [], []
        for section_index, section in enumerate(video["sections"]):
            slide_path = video_dir / f"long_{video_index}_section_{section_index + 1}.png"
            make_section_slide(
                *LONG_SIZE, section.get("category", "MLB"), video["title"], bullets,
                section_index, slide_path, visual=section.get("visual"),
                key_points=section.get("key_points", []),
            )
            image_paths.append(slide_path)
            durations.append(durations_data[section_index]["duration"])
        render_deck(
            image_paths, durations, audio_dir / f"long_{video_index}.wav",
            audio_dir / f"long_{video_index}.srt", video_dir / f"long_{video_index}.mp4"
        )
        print(f"[info] wrote {video_dir / f'long_{video_index}.mp4'}")

    for i, short in enumerate(data["short_videos"], start=1):
        slide_path = video_dir / f"short_{i}_bg.png"
        make_short_slide(
            *SHORT_SIZE,
            short.get("category", "MLB"),
            short["hook"],
            slide_path,
            visual=short.get("visual"),
        )
        render(
            audio_dir / f"short_{i}.wav",
            audio_dir / f"short_{i}.srt",
            slide_path,
            video_dir / f"short_{i}.mp4",
        )
        print(f"[info] wrote {video_dir / f'short_{i}.mp4'}")

    return video_dir


if __name__ == "__main__":
    main()
