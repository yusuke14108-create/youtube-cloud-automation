import json
import os
import shutil
import subprocess
from pathlib import Path

import requests
from generator.slides import make_section_slide, make_short_slide
from generator.visual_media import fetch_visual_asset, fetch_verified_fallback_photo

_FFMPEG_FULL = "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"
FFMPEG_BIN = os.getenv("FFMPEG_BIN") or (_FFMPEG_FULL if Path(_FFMPEG_FULL).exists() else None) or shutil.which("ffmpeg") or "ffmpeg"

ROOT = Path(__file__).resolve().parent.parent
AUDIO_DIR = ROOT / "data" / "audio"
SCRIPTS_DIR = ROOT / "data" / "scripts"
VIDEO_DIR = ROOT / "data" / "video"
ASSET_DIR = ROOT / "data" / "assets"
MLB_PHOTO_FALLBACKS = ("baseball stadium", "baseball pitching mound", "baseball glove")


def _fetch_mlb_photo(query, out_dir, stem, session, result_index):
    """Prefer the requested player/topic, then a clearly baseball-specific photo."""
    candidates = [query] + [item for item in MLB_PHOTO_FALLBACKS if item != query]
    for offset, candidate in enumerate(candidates):
        asset = fetch_visual_asset(
            candidate, out_dir, stem, session,
            result_index=result_index + offset, kind_preference="photo",
        )
        if asset:
            asset["query"] = candidate
            return asset
    # Commons search can be rate-limited from shared GitHub runner IPs. Keep a
    # small, attribution-complete catalog so a transient search failure never
    # sends MLB back to abstract circle diagrams (or aborts the whole batch).
    asset = fetch_verified_fallback_photo(out_dir, stem, session, result_index)
    if asset:
        asset["query"] = "verified baseball stadium fallback"
    return asset

LONG_SIZE = (1920, 1080)
SHORT_SIZE = (1080, 1920)

SUBTITLE_FONT = os.getenv("SUBTITLE_FONT", "Noto Sans CJK JP")
LONG_SUBTITLE_STYLE = (
    f"FontName={SUBTITLE_FONT},FontSize=19,Bold=1,PrimaryColour=&H00FFFFFF,"
    "OutlineColour=&H00101010,BorderStyle=1,Outline=0.9,Shadow=0,"
    "Alignment=2,MarginL=38,MarginR=38,MarginV=42,Spacing=0.2"
)

SHORT_SUBTITLE_STYLE = (
    f"FontName={SUBTITLE_FONT},FontSize=20,Bold=1,PrimaryColour=&H00FFFFFF,"
    "OutlineColour=&H00101010,BorderStyle=1,Outline=1.0,Shadow=0,"
    "Alignment=2,MarginL=96,MarginR=96,MarginV=130,Spacing=0.1,WrapStyle=2"
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


def render_deck(image_paths: list, durations: list, wav_path: Path, srt_path: Path, out_path: Path, subtitle_style: str = LONG_SUBTITLE_STYLE) -> None:
    concat_path = out_path.parent / f"{out_path.stem}_concat.txt"
    lines = []
    for image_path, duration in zip(image_paths, durations):
        lines.append(f"file '{image_path}'")
        lines.append(f"duration {duration}")
    lines.append(f"file '{image_paths[-1]}'")
    concat_path.parent.mkdir(parents=True, exist_ok=True)
    concat_path.write_text("\n".join(lines), encoding="utf-8")

    subtitles_arg = f"subtitles={_escape_for_filter(srt_path)}:force_style='{subtitle_style}'"
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
    asset_dir = ASSET_DIR / run_id
    session = requests.Session()
    asset_manifest = []

    for video_index, video in enumerate(data["long_videos"], start=1):
        durations_data = json.loads((audio_dir / f"long_{video_index}_sections.json").read_text(encoding="utf-8"))
        bullets = [s["bullet"] for s in video["sections"]]
        image_paths, durations = [], []
        for section_index, section in enumerate(video["sections"]):
            section_duration = durations_data[section_index]["duration"]
            assets = [
                _fetch_mlb_photo(
                    section.get("image_query", "baseball stadium"), asset_dir,
                    f"long_{video_index}_section_{section_index + 1}_{asset_index + 1}",
                    session, result_index=asset_index,
                )
                for asset_index in range(max(2, min(4, round(section_duration / 10))))
            ]
            assets = [asset for asset in assets if asset]
            if not assets:
                raise RuntimeError(f"licensed MLB photo not found for section: {section.get('image_query', '')}")
            for asset_index, asset in enumerate(assets):
                slide_path = video_dir / f"long_{video_index}_section_{section_index + 1}_{asset_index + 1}.png"
                make_section_slide(
                    *LONG_SIZE, section.get("category", "MLB"), video["title"], bullets,
                    section_index, slide_path, visual=section.get("visual"),
                    key_points=section.get("key_points", []),
                    background_image_path=asset.get("local_path") if asset else None,
                )
                image_paths.append(slide_path)
                durations.append(section_duration / len(assets))
                if asset:
                    asset_manifest.append({
                        **{k: asset.get(k) for k in ("credit", "source_page", "local_path")},
                        "query": asset.get("query", section.get("image_query", "baseball stadium")),
                        "usage": f"long_{video_index}_section_{section_index + 1}",
                    })
        render_deck(
            image_paths, durations, audio_dir / f"long_{video_index}.wav",
            audio_dir / f"long_{video_index}.srt", video_dir / f"long_{video_index}.mp4"
        )
        print(f"[info] wrote {video_dir / f'long_{video_index}.mp4'}")

    for i, short in enumerate(data["short_videos"], start=1):
        illustration_path = short.get("illustration_path")
        if illustration_path:
            local_path = ROOT / illustration_path
            if not local_path.is_file():
                raise RuntimeError(f"illustration asset not found: {local_path}")
            assets = [{
                "kind": "photo", "local_path": str(local_path),
                "credit": "Original AI illustration / OpenAI image generation",
                "source_page": "Original illustration generated for this channel",
                "query": "original player illustration",
            }]
        else:
            assets = [
                _fetch_mlb_photo(
                    short.get("image_query", "baseball stadium"), asset_dir, f"short_{i}_{asset_index + 1}",
                    session, result_index=asset_index,
                )
                for asset_index in range(3)
            ]
        assets = [asset for asset in assets if asset]
        if not assets:
            raise RuntimeError(f"licensed MLB photo not found for Short: {short.get('image_query', '')}")
        slide_paths = []
        for asset_index, asset in enumerate(assets):
            slide_path = video_dir / f"short_{i}_bg_{asset_index + 1}.png"
            make_short_slide(
                *SHORT_SIZE, short.get("category", "MLB"), short["hook"], slide_path,
                visual=short.get("visual"), background_image_path=asset.get("local_path") if asset else None,
                background_kind=short.get("asset_kind"),
            )
            slide_paths.append(slide_path)
            if asset:
                asset_manifest.append({
                    **{k: asset.get(k) for k in ("credit", "source_page", "local_path")},
                    "query": asset.get("query", short.get("image_query", "baseball stadium")),
                    "usage": f"short_{i}",
                })
        import wave
        with wave.open(str(audio_dir / f"short_{i}.wav"), "rb") as wav:
            short_duration = wav.getnframes() / wav.getframerate()
        render_deck(
            slide_paths, [short_duration / len(slide_paths)] * len(slide_paths),
            audio_dir / f"short_{i}.wav", audio_dir / f"short_{i}.srt",
            video_dir / f"short_{i}.mp4", SHORT_SUBTITLE_STYLE,
        )
        print(f"[info] wrote {video_dir / f'short_{i}.mp4'}")

    asset_dir.mkdir(parents=True, exist_ok=True)
    (asset_dir / "licenses.json").write_text(json.dumps(asset_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return video_dir


if __name__ == "__main__":
    main()
