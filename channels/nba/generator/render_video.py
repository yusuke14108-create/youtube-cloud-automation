import json
import re
import subprocess
import wave
from pathlib import Path

import requests
from generator.config import FFMPEG_BIN

from generator.slides import make_abstract_panel_bg, make_background, make_section_foreground, make_slide, section_panel_box
from generator.visual_media import fetch_visual_asset, load_recent_source_pages

ROOT = Path(__file__).resolve().parent.parent
AUDIO_DIR = ROOT / "data" / "audio"
SCRIPTS_DIR = ROOT / "data" / "scripts"
VIDEO_DIR = ROOT / "data" / "video"
ASSET_DIR = ROOT / "data" / "assets"

LONG_SIZE = (1920, 1080)
SHORT_SIZE = (1080, 1920)
FPS = 25

_SRT_BLOCK_RE = re.compile(
    r"\d+\s*\n(\d{2}):(\d{2}):(\d{2}),(\d{3})\s+-->\s+"
    r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*\n(.*?)(?=\n\s*\n|\Z)",
    re.DOTALL,
)


def _ass_time(parts) -> str:
    hours, minutes, seconds, millis = map(int, parts)
    return f"{hours}:{minutes:02d}:{seconds:02d}.{millis // 10:02d}"


def _write_ass(srt_path: Path, kind: str) -> Path:
    """Write explicit-resolution captions so cloud runners cannot resize or
    push them outside the visible frame.  Shorts use the same mobile-first
    sizing proven in the MLB test; long video uses a proportional 16:9 style."""
    if kind == "short":
        play_res = (1080, 1920)
        style = "Style: Caption,Noto Sans CJK JP,72,&H00FFFFFF,&H00FFFFFF,&H00101010,&H00000000,-1,0,0,0,88,100,0,0,1,3.2,0,2,120,120,300,1"
    elif kind == "long":
        play_res = (1920, 1080)
        style = "Style: Caption,Noto Sans CJK JP,52,&H00FFFFFF,&H00FFFFFF,&H00101010,&H00000000,-1,0,0,0,96,100,0,0,1,2.6,0,2,150,150,78,1"
    else:
        raise ValueError(f"unknown subtitle kind: {kind}")

    events = []
    for match in _SRT_BLOCK_RE.finditer(srt_path.read_text(encoding="utf-8")):
        groups = match.groups()
        text = groups[8].strip().replace("\n", r"\N").replace(",", "，")
        text = text.replace('<font color="#FFD54A">', r"{\c&H4AD5FF&}")
        text = text.replace("</font>", r"{\c&HFFFFFF&}")
        events.append(
            f"Dialogue: 0,{_ass_time(groups[:4])},{_ass_time(groups[4:8])},Caption,,0,0,0,,{text}"
        )
    if not events:
        raise RuntimeError(f"no subtitle events parsed from {srt_path}")

    ass_path = srt_path.with_name(f"{srt_path.stem}_{kind}.ass")
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {play_res[0]}
PlayResY: {play_res[1]}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{style}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ass_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    return ass_path


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


def render_visual_sequence(query, out_dir, stem, session, out_path, box, width, height, duration, variant=0, used_source_pages=None):
    """Change licensed imagery roughly every 10 seconds instead of holding one image per section."""
    count = max(2, min(4, round(duration / 10)))
    part_duration = duration / count
    clips, assets = [], []
    used_source_pages = used_source_pages if used_source_pages is not None else set()
    for index in range(count):
        asset = fetch_visual_asset(
            query, out_dir, f"{stem}_{index + 1}", session,
            result_index=variant + index, exclude_source_pages=used_source_pages,
        )
        if asset:
            assets.append(asset)
            used_source_pages.add(asset["source_page"])
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


def concat_clips_with_audio_and_subtitles(clip_paths, wav_path, srt_path, out_path, subtitle_kind) -> None:
    concat_path = out_path.parent / f"{out_path.stem}_concat.txt"
    lines = [f"file '{p}'" for p in clip_paths]
    concat_path.write_text("\n".join(lines), encoding="utf-8")

    ass_path = _write_ass(srt_path, subtitle_kind)
    subtitles_arg = f"ass=filename='{_escape_for_filter(ass_path)}'"
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
    used_source_pages = load_recent_source_pages(run_id)

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
            used_source_pages=used_source_pages,
        )
        asset_manifest.extend({k: asset.get(k) for k in ("usage", "query", "credit", "source_page")} for asset in assets)

        clip_path = video_dir / f"long_section_{i + 1}_clip.mp4"
        compose_full_frame_motion(long_bg, motion_path, fg_path, clip_path, long_box, long_w, long_h, duration)
        clip_paths.append(clip_path)

    concat_clips_with_audio_and_subtitles(
        clip_paths, audio_dir / "long.wav", audio_dir / "long.srt", video_dir / "long.mp4", "long",
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
            used_source_pages=used_source_pages,
        )
        asset_manifest.extend({k: asset.get(k) for k in ("usage", "query", "credit", "source_page")} for asset in assets)

        clip_path = video_dir / f"short_{i}_clip.mp4"
        compose_full_frame_bg_only(motion_path, fg_path, clip_path, short_w, short_h, duration)

        concat_clips_with_audio_and_subtitles(
            [clip_path], short_wav, audio_dir / f"short_{i}.srt", video_dir / f"short_{i}.mp4", "short",
        )
        print(f"[info] wrote {video_dir / f'short_{i}.mp4'}")

    asset_dir.mkdir(parents=True, exist_ok=True)
    (asset_dir / "licenses.json").write_text(json.dumps(asset_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return video_dir


if __name__ == "__main__":
    main()
