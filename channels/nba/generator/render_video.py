import json
import subprocess
import wave
from pathlib import Path

import requests
from generator.config import FFMPEG_BIN

from generator.slides import make_abstract_panel_bg, make_background, make_section_foreground, make_slide, section_panel_box
from generator.visual_media import fetch_visual_asset

ROOT = Path(__file__).resolve().parent.parent
AUDIO_DIR = ROOT / "data" / "audio"
SCRIPTS_DIR = ROOT / "data" / "scripts"
VIDEO_DIR = ROOT / "data" / "video"
ASSET_DIR = ROOT / "data" / "assets"

LONG_SIZE = (1920, 1080)
SHORT_SIZE = (1080, 1920)
FPS = 25

SUBTITLE_STYLE = (
    "FontName=Noto Sans CJK JP,FontSize=20,Bold=1,PrimaryColour=&H00FFFFFF,"
    "OutlineColour=&H00101010,BorderStyle=1,Outline=1.4,Shadow=0,"
    "Alignment=2,MarginL=64,MarginR=64,MarginV=84,WrapStyle=2"
)
LONG_SUBTITLE_STYLE = (
    "FontName=Noto Sans CJK JP,FontSize=29,Bold=1,PrimaryColour=&H00FFFFFF,"
    "OutlineColour=&H00101010,BorderStyle=1,Outline=1.5,Shadow=0,"
    "Alignment=2,MarginL=42,MarginR=42,MarginV=46,WrapStyle=2"
)


def _escape_for_filter(path: Path) -> str:
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _even(n) -> int:
    """libx264 requires even frame dimensions; panel geometry is fractional so
    a computed width like 633 would otherwise fail the encode outright."""
    return int(n) // 2 * 2


def _run_ffmpeg(cmd: list, timeout: int = 180) -> None:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"ffmpeg timed out after {timeout}s: {' '.join(cmd)}") from exc
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {' '.join(cmd)}\n{proc.stderr[-4000:]}")


def render_motion_photo(image_path, out_path, width, height, duration, zoom_out=False) -> None:
    """Ken Burns pan/zoom on a still photo, cropped/scaled to exactly width x height."""
    width, height = _even(width), _even(height)
    frames = max(1, round(duration * FPS))
    z_from, z_to = (1.12, 1.0) if zoom_out else (1.0, 1.12)
    zoom_expr = f"{z_from}+({z_to}-{z_from})*on/{frames}"
    pre_w, pre_h = int(width * 1.5), int(height * 1.5)
    vf = (
        f"scale={pre_w}:{pre_h}:force_original_aspect_ratio=increase,"
        f"crop={pre_w}:{pre_h},"
        f"zoompan=z='{zoom_expr}':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height}:fps={FPS}"
    )
    cmd = [
        FFMPEG_BIN, "-y", "-loop", "1", "-i", str(image_path),
        "-t", str(duration), "-vf", vf,
        "-pix_fmt", "yuv420p", "-c:v", "libx264", "-r", str(FPS),
        str(out_path),
    ]
    _run_ffmpeg(cmd)


def render_motion_video_clip(video_path, out_path, width, height, duration) -> None:
    """Loop/trim a real video clip to exactly `duration` seconds, cropped to width x height."""
    width, height = _even(width), _even(height)
    vf = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},fps={FPS}"
    cmd = [
        FFMPEG_BIN, "-y", "-stream_loop", "-1", "-i", str(video_path),
        "-t", str(duration), "-vf", vf, "-an",
        "-pix_fmt", "yuv420p", "-c:v", "libx264", "-r", str(FPS),
        str(out_path),
    ]
    _run_ffmpeg(cmd)


def render_motion_fallback(out_path, width, height, duration, variant=0, zoom_out=False) -> None:
    """Fallback when no Commons asset is found: zoom/pan on a procedurally
    generated textured background (a flat gradient shows almost no visible
    motion under zoompan), so every section still has real, visible movement."""
    width, height = _even(width), _even(height)
    tmp_bg = out_path.parent / f"{out_path.stem}_abstract.png"
    make_abstract_panel_bg(width, height, tmp_bg, variant=variant)
    render_motion_photo(tmp_bg, out_path, width, height, duration, zoom_out=zoom_out)


def render_motion_clip(asset, out_path, box, width, height, duration, variant=0, zoom_out=False) -> None:
    _, _, w, h = box
    try:
        if asset and asset["kind"] == "video":
            render_motion_video_clip(asset["local_path"], out_path, int(w), int(h), duration)
            return
        if asset and asset["kind"] == "photo":
            render_motion_photo(asset["local_path"], out_path, int(w), int(h), duration, zoom_out=zoom_out)
            return
    except RuntimeError as exc:
        print(f"[warn] motion clip from fetched asset failed, falling back: {exc}")
    render_motion_fallback(out_path, int(w), int(h), duration, variant=variant, zoom_out=zoom_out)


def render_visual_sequence(query, out_dir, stem, session, out_path, box, width, height, duration, variant=0):
    """Change licensed imagery roughly every 10 seconds instead of holding one image per section."""
    count = max(2, min(4, round(duration / 10)))
    part_duration = duration / count
    clips, assets = [], []
    for index in range(count):
        asset = fetch_visual_asset(query, out_dir, f"{stem}_{index + 1}", session, result_index=index)
        if asset:
            assets.append(asset)
        clip = out_path.parent / f"{out_path.stem}_part_{index + 1}.mp4"
        render_motion_clip(asset, clip, box, width, height, part_duration, variant + index, zoom_out=(index % 2 == 1))
        clips.append(clip)
    concat_file = out_path.parent / f"{out_path.stem}_parts.txt"
    concat_file.write_text("\n".join(f"file '{clip.resolve()}'" for clip in clips), encoding="utf-8")
    _run_ffmpeg([FFMPEG_BIN, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", str(out_path)])
    return assets


def compose_full_frame_motion(background_path, motion_clip_path, foreground_path, out_path, box, width, height, duration) -> None:
    """background (static, full frame) + motion clip (positioned at box) + foreground overlay (static, full frame, alpha)."""
    x, y, _, _ = box
    filter_complex = (
        f"[0:v]scale={width}:{height},setsar=1[bg];"
        f"[2:v]format=rgba[fg];"
        f"[bg][1:v]overlay={int(x)}:{int(y)}:shortest=0[bg2];"
        f"[bg2][fg]overlay=0:0:shortest=0[outv]"
    )
    cmd = [
        FFMPEG_BIN, "-y",
        "-loop", "1", "-i", str(background_path),
        "-i", str(motion_clip_path),
        "-loop", "1", "-i", str(foreground_path),
        "-t", str(duration),
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-r", str(FPS), "-pix_fmt", "yuv420p", "-c:v", "libx264",
        str(out_path),
    ]
    _run_ffmpeg(cmd)


def compose_full_frame_bg_only(motion_clip_path, foreground_path, out_path, width, height, duration) -> None:
    """Shorts: the motion clip fills the whole frame; foreground overlay (badge/title/scrim) sits on top."""
    filter_complex = (
        f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}[bg];"
        f"[1:v]format=rgba[fg];"
        f"[bg][fg]overlay=0:0:shortest=0[outv]"
    )
    cmd = [
        FFMPEG_BIN, "-y",
        "-i", str(motion_clip_path),
        "-loop", "1", "-i", str(foreground_path),
        "-t", str(duration),
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-r", str(FPS), "-pix_fmt", "yuv420p", "-c:v", "libx264",
        str(out_path),
    ]
    _run_ffmpeg(cmd)


def concat_clips_with_audio_and_subtitles(clip_paths, wav_path, srt_path, out_path, style) -> None:
    concat_path = out_path.parent / f"{out_path.stem}_concat.txt"
    lines = [f"file '{p}'" for p in clip_paths]
    concat_path.write_text("\n".join(lines), encoding="utf-8")

    subtitles_arg = f"subtitles=filename='{_escape_for_filter(srt_path)}':force_style='{style}'"
    cmd = [
        FFMPEG_BIN, "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_path),
        "-i", str(wav_path),
        "-vf", subtitles_arg,
        "-r", str(FPS), "-fps_mode", "cfr",
        "-c:v", "libx264", "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p", "-shortest",
        str(out_path),
    ]
    _run_ffmpeg(cmd)


def main(script_path=None):
    if script_path is None:
        script_files = sorted(SCRIPTS_DIR.glob("*.json"))
        if not script_files:
            print("[info] no script file found")
            return None
        script_path = script_files[-1]
    data = json.loads(script_path.read_text(encoding="utf-8"))
    source = data["source_item"]["source"]

    run_id = script_path.stem
    audio_dir = AUDIO_DIR / run_id
    video_dir = VIDEO_DIR / run_id
    asset_dir = ASSET_DIR / run_id
    video_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    asset_manifest = []

    long_bg = video_dir / "long_bg.png"
    make_background(*LONG_SIZE, long_bg)
    long_w, long_h = LONG_SIZE
    long_box = section_panel_box(long_w, long_h)

    durations_data = json.loads((audio_dir / "long_sections.json").read_text(encoding="utf-8"))
    bullets = [s["bullet"] for s in data["long_sections"]]

    clip_paths = []
    for i, section in enumerate(data["long_sections"]):
        duration = durations_data[i]["duration"]
        fg_path = video_dir / f"long_section_{i + 1}_fg.png"
        make_section_foreground(
            long_w, long_h, source, data["title"], bullets, i, fg_path, visual=section.get("visual"),
        )

        motion_path = video_dir / f"long_section_{i + 1}_motion.mp4"
        assets = render_visual_sequence(
            section.get("image_query", ""), asset_dir, f"long_section_{i + 1}", session,
            motion_path, long_box, long_w, long_h, duration, variant=i * 4,
        )
        asset_manifest.extend({k: asset.get(k) for k in ("usage", "query", "credit", "source_page")} for asset in assets)

        clip_path = video_dir / f"long_section_{i + 1}_clip.mp4"
        compose_full_frame_motion(long_bg, motion_path, fg_path, clip_path, long_box, long_w, long_h, duration)
        clip_paths.append(clip_path)

    concat_clips_with_audio_and_subtitles(
        clip_paths, audio_dir / "long.wav", audio_dir / "long.srt", video_dir / "long.mp4", LONG_SUBTITLE_STYLE,
    )
    print(f"[info] wrote {video_dir / 'long.mp4'}")

    short_w, short_h = SHORT_SIZE
    short_bg = video_dir / "short_bg.png"
    make_background(short_w, short_h, short_bg)

    for i, short in enumerate(data["short_scripts"], start=1):
        fg_path = video_dir / f"short_{i}_fg.png"
        make_slide(
            short_w, short_h, source, short["hook"], data["title"], fg_path,
            anchor_y_ratio=0.25, max_summary_lines=2,
        )

        motion_path = video_dir / f"short_{i}_motion.mp4"
        short_wav = audio_dir / f"short_{i}.wav"
        with wave.open(str(short_wav), "rb") as w:
            duration = w.getnframes() / w.getframerate()
        assets = render_visual_sequence(
            short.get("image_query", ""), asset_dir, f"short_{i}", session,
            motion_path, (0, 0, short_w, short_h), short_w, short_h, duration, variant=i * 4,
        )
        asset_manifest.extend({k: asset.get(k) for k in ("usage", "query", "credit", "source_page")} for asset in assets)

        clip_path = video_dir / f"short_{i}_clip.mp4"
        compose_full_frame_bg_only(motion_path, fg_path, clip_path, short_w, short_h, duration)

        concat_clips_with_audio_and_subtitles(
            [clip_path], short_wav, audio_dir / f"short_{i}.srt", video_dir / f"short_{i}.mp4", SUBTITLE_STYLE,
        )
        print(f"[info] wrote {video_dir / f'short_{i}.mp4'}")

    asset_dir.mkdir(parents=True, exist_ok=True)
    (asset_dir / "licenses.json").write_text(json.dumps(asset_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return video_dir


if __name__ == "__main__":
    main()
