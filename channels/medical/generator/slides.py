from pathlib import Path
import os
import re

from PIL import Image, ImageDraw, ImageFont, ImageOps

FONT_BOLD = os.getenv("FONT_BOLD", "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc")
FONT_REGULAR = os.getenv("FONT_REGULAR", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
if not Path(FONT_BOLD).exists():
    FONT_BOLD = "/System/Library/Fonts/ヒラギノ角ゴシック W7.ttc"
if not Path(FONT_REGULAR).exists():
    FONT_REGULAR = "/System/Library/Fonts/ヒラギノ角ゴシック W4.ttc"

BG_TOP = (231, 243, 249)
BG_BOTTOM = (250, 251, 246)
ACCENT_COLOR = (33, 113, 163)
ACCENT_LIGHT = (191, 219, 236)
TITLE_COLOR = (36, 44, 50)
SUMMARY_COLOR = (94, 106, 116)
BADGE_TEXT_COLOR = (255, 255, 255)
CARD_BG = (255, 255, 255)

THUMB_BG_TOP = (24, 96, 140)
THUMB_BG_BOTTOM = (16, 68, 100)
THUMB_TEXT_COLOR = (255, 224, 79)

SOURCE_LABELS = {
    "pmda": "PMDA",
    "mhlw": "厚生労働省",
    "niid": "感染研(JIHS)",
    "pubmed": "PubMed",
    "medical": "医療ニュース",
}


_TOKEN_RE = re.compile(
    r"[A-Za-z0-9]+(?:[._/+:-][A-Za-z0-9]+)*|"
    r"[ァ-ヶー・]+|[一-龯々]+[ぁ-ん]{0,4}|[ぁ-ん]+|."
)
_BREAK_AFTER = set(" 、。！？：；）】」』〉》〕はがをにへでともやのねよかしばなら")
_NO_LINE_START = set("、。！？：；）】」』〉》〕ぁぃぅぇぉゃゅょっァィゥェォャュョッー")


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list:
    """Wrap at Japanese phrase boundaries while keeping Latin/numeric words intact."""
    tokens = _TOKEN_RE.findall(text)
    lines = []
    while tokens:
        width_end = 0
        for i in range(1, len(tokens) + 1):
            if draw.textlength("".join(tokens[:i]), font=font) <= max_width:
                width_end = i
            else:
                break
        if width_end == 0:
            width_end = 1
        if width_end == len(tokens):
            lines.append("".join(tokens).strip())
            break
        cut = width_end
        for i in range(width_end, max(1, width_end - 9), -1):
            if tokens[i - 1][-1] in _BREAK_AFTER and tokens[i][0] not in _NO_LINE_START:
                cut = i
                break
        while cut < len(tokens) and tokens[cut][0] in _NO_LINE_START:
            cut += 1
        lines.append("".join(tokens[:cut]).strip())
        tokens = tokens[cut:]
    return lines


def _fit_font(text: str, font_path: str, max_size: int, min_size: int, max_width: float) -> ImageFont.FreeTypeFont:
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    for size in range(max_size, min_size - 1, -1):
        font = ImageFont.truetype(font_path, size=size)
        if probe.textlength(text, font=font) <= max_width:
            return font
    return ImageFont.truetype(font_path, size=min_size)


def _draw_centered_fit(draw, text, box, font_path, max_size, min_size, fill):
    x, y, w, h = box
    font = _fit_font(text, font_path, max_size, min_size, w - 36)
    tw = draw.textlength(text, font=font)
    draw.text((x + (w - tw) / 2, y + (h - font.size) / 2 - 4), text, font=font, fill=fill)


def _ellipsize(draw, text, font, max_width):
    if draw.textlength(text, font=font) <= max_width:
        return text
    suffix = "…"
    shortened = text
    while shortened and draw.textlength(shortened + suffix, font=font) > max_width:
        shortened = shortened[:-1]
    return shortened + suffix


def _gradient_background(width: int, height: int, top: tuple, bottom: tuple) -> Image.Image:
    img = Image.new("RGB", (width, height), top)
    draw = ImageDraw.Draw(img)
    for y in range(height):
        t = y / max(height - 1, 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        draw.line([(0, y), (width, y)], fill=color)
    return img


CARD_ALPHA = 242


def section_panel_box(width: int, height: int) -> tuple:
    """The new long-form format uses imagery across the whole frame."""
    return 0, 0, width, height


def make_background(width: int, height: int, out_path: Path) -> None:
    img = _gradient_background(width, height, BG_TOP, BG_BOTTOM)
    draw = ImageDraw.Draw(img)
    _draw_decorative_circles(draw, width, height)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out_path)


def make_abstract_panel_bg(width: int, height: int, out_path: Path, variant: int = 0) -> None:
    """Textured brand-color background for the no-asset motion fallback — a flat
    gradient shows almost no visible pan/zoom, so this gives zoompan real edges."""
    img = _gradient_background(width, height, BG_TOP, BG_BOTTOM)
    draw = ImageDraw.Draw(img)
    blobs = [
        (0.15, 0.20, 0.55, ACCENT_LIGHT),
        (0.85, 0.75, 0.50, ACCENT_LIGHT),
        (0.75, 0.15, 0.32, ACCENT_COLOR),
        (0.25, 0.85, 0.30, ACCENT_COLOR),
    ]
    offset = variant % len(blobs)
    for cx, cy, r, color in blobs:
        cx = (cx + offset * 0.13) % 1.0
        cy = (cy + offset * 0.09) % 1.0
        rad = r * min(width, height)
        draw.ellipse([width * cx - rad, height * cy - rad, width * cx + rad, height * cy + rad], fill=color)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)


def _draw_decorative_circles(draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
    draw.ellipse(
        [width * 0.72, -height * 0.12, width * 1.15, height * 0.35],
        fill=ACCENT_LIGHT,
    )
    draw.ellipse(
        [-width * 0.2, height * 0.75, width * 0.25, height * 1.25],
        fill=ACCENT_LIGHT,
    )


def _draw_badge(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, font: ImageFont.FreeTypeFont) -> int:
    pad_x, pad_y = 22, 12
    w = draw.textlength(text, font=font) + pad_x * 2
    h = font.size + pad_y * 2
    draw.rounded_rectangle([x, y, x + w, y + h], radius=h / 2, fill=ACCENT_COLOR)
    draw.text((x + pad_x, y + pad_y), text, font=font, fill=BADGE_TEXT_COLOR)
    return h


def _draw_comparison_panel(draw: ImageDraw.ImageDraw, x: float, y: float, w: float, h: float, visual: dict) -> None:
    arrow_font = ImageFont.truetype(FONT_BOLD, size=int(h * 0.14))

    box_h = h * 0.34
    gap = h * 0.1

    before_y = y
    after_y = y + box_h + gap

    for box_y, label, value, is_after in (
        (before_y, visual.get("before_label", ""), visual.get("before_value", ""), False),
        (after_y, visual.get("after_label", ""), visual.get("after_value", ""), True),
    ):
        fill = (*ACCENT_COLOR, CARD_ALPHA) if is_after else (*CARD_BG, CARD_ALPHA)
        text_color = (255, 255, 255) if is_after else TITLE_COLOR
        label_color = (230, 245, 236) if is_after else SUMMARY_COLOR

        draw.rounded_rectangle([x, box_y, x + w, box_y + box_h], radius=box_h * 0.18, fill=fill)

        _draw_centered_fit(draw, label, (x, box_y + box_h * 0.06, w, box_h * 0.38), FONT_REGULAR, int(h * 0.085), 20, label_color)
        _draw_centered_fit(draw, value, (x, box_y + box_h * 0.38, w, box_h * 0.52), FONT_BOLD, int(h * 0.13), 24, text_color)

    arrow_y = before_y + box_h + gap / 2
    aw = draw.textlength("↓", font=arrow_font)
    draw.text((x + (w - aw) / 2, arrow_y - arrow_font.size / 2), "↓", font=arrow_font, fill=ACCENT_COLOR)


def _draw_timeline_panel(draw: ImageDraw.ImageDraw, x: float, y: float, w: float, h: float, visual: dict) -> None:
    card_h = h * 0.42
    card_y = y + (h - card_h) / 2

    draw.rounded_rectangle([x, card_y, x + w, card_y + card_h], radius=card_h * 0.18, fill=(*CARD_BG, CARD_ALPHA))

    label = visual.get("date_label", "")
    _draw_centered_fit(draw, label, (x, card_y + card_h * 0.08, w, card_h * 0.38), FONT_REGULAR, int(h * 0.08), 20, SUMMARY_COLOR)

    date_value = visual.get("date_value", "")
    _draw_centered_fit(draw, date_value, (x, card_y + card_h * 0.42, w, card_h * 0.48), FONT_BOLD, int(h * 0.13), 24, ACCENT_COLOR)


def _draw_visual_panel(draw: ImageDraw.ImageDraw, x: float, y: float, w: float, h: float, visual: dict) -> None:
    kind = visual.get("kind", "none")
    if kind == "comparison":
        _draw_comparison_panel(draw, x, y, w, h, visual)
    elif kind == "timeline":
        _draw_timeline_panel(draw, x, y, w, h, visual)


def make_slide(
    width: int,
    height: int,
    source: str,
    title: str,
    summary: str,
    out_path: Path,
    anchor_y_ratio: float = 0.5,
    max_summary_lines: int = 4,
) -> None:
    img = _gradient_background(width, height, BG_TOP, BG_BOTTOM)
    draw = ImageDraw.Draw(img)
    _draw_decorative_circles(draw, width, height)

    margin = int(width * 0.08)
    max_w = width - margin * 2

    badge_font = ImageFont.truetype(FONT_BOLD, size=int(height * 0.032))
    title_font = ImageFont.truetype(FONT_BOLD, size=int(height * 0.055))
    summary_font = ImageFont.truetype(FONT_REGULAR, size=int(height * 0.026))

    _draw_badge(draw, margin, margin, SOURCE_LABELS.get(source, source), badge_font)

    title_lines = _wrap_text(draw, title, title_font, max_w)
    summary_lines = _wrap_text(draw, summary, summary_font, max_w)[:max_summary_lines]

    line_gap = 1.35
    title_block_h = len(title_lines) * title_font.size * line_gap
    summary_block_h = len(summary_lines) * summary_font.size * line_gap
    block_gap = height * 0.05
    total_h = title_block_h + block_gap + summary_block_h
    y = height * anchor_y_ratio - total_h / 2

    for line in title_lines:
        w = draw.textlength(line, font=title_font)
        draw.text(((width - w) / 2, y), line, font=title_font, fill=TITLE_COLOR)
        y += title_font.size * line_gap

    y += block_gap
    for line in summary_lines:
        w = draw.textlength(line, font=summary_font)
        draw.text(((width - w) / 2, y), line, font=summary_font, fill=SUMMARY_COLOR)
        y += summary_font.size * line_gap

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out_path)


def make_short_slide(width: int, height: int, source: str, hook: str, out_path: Path) -> None:
    """Portrait foreground layer with fixed safe zones for the hook and burned-in
    captions, drawn on a transparent canvas so a moving photo/video shows through.
    A dark scrim sits behind the hook text to keep it legible over any footage."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = int(width * 0.09)
    logo_x, logo_y, logo_d = margin, 72, 74
    draw.rounded_rectangle([logo_x, logo_y, logo_x + logo_d, logo_y + logo_d], radius=20, fill=ACCENT_COLOR)
    cross_w = 13
    cx, cy = logo_x + logo_d / 2, logo_y + logo_d / 2
    draw.rounded_rectangle([cx - cross_w / 2, logo_y + 14, cx + cross_w / 2, logo_y + logo_d - 14], radius=5, fill="white")
    draw.rounded_rectangle([logo_x + 14, cy - cross_w / 2, logo_x + logo_d - 14, cy + cross_w / 2], radius=5, fill="white")
    channel_font = ImageFont.truetype(FONT_BOLD, size=39)
    draw.text((logo_x + logo_d + 18, logo_y + 11), "医療と医学の", font=channel_font, fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(18, 26, 32, 210))
    draw.text((logo_x + logo_d + 18, logo_y + 53), "最新ニュース", font=channel_font, fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(18, 26, 32, 210))

    # Keep the hook below the badge and above the subtitle zone. Its font shrinks
    # until the whole block fits, so Japanese line breaks never collide with UI.
    hook_top = 245
    hook_bottom = 790
    max_w = width - margin * 2
    chosen_font = None
    chosen_lines = None
    for size in range(76, 47, -2):
        font = ImageFont.truetype(FONT_BOLD, size=size)
        lines = _wrap_text(draw, hook, font, max_w)
        block_h = len(lines) * size * 1.22
        if len(lines) <= 4 and block_h <= hook_bottom - hook_top:
            chosen_font, chosen_lines = font, lines
            break
    if chosen_font is None:
        chosen_font = ImageFont.truetype(FONT_BOLD, size=46)
        chosen_lines = _wrap_text(draw, hook, chosen_font, max_w)[:4]

    line_h = chosen_font.size * 1.22
    block_h = len(chosen_lines) * line_h
    y = hook_top + (hook_bottom - hook_top - block_h) / 2

    scrim_pad = 48
    draw.rounded_rectangle(
        [margin * 0.4, y - scrim_pad, width - margin * 0.4, y + block_h + scrim_pad],
        radius=32,
        fill=(18, 26, 32, 170),
    )

    for line in chosen_lines:
        tw = draw.textlength(line, font=chosen_font)
        draw.text(((width - tw) / 2, y), line, font=chosen_font, fill=(255, 255, 255, 255))
        y += line_h

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)


def make_section_slide(
    width: int,
    height: int,
    source: str,
    title: str,
    bullets: list,
    current_index: int,
    out_path: Path,
    visual: dict = None,
) -> None:
    """Full-bleed editorial format with one readable topic over changing imagery."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = int(width * 0.055)
    draw.rectangle([0, 0, width, int(height * 0.29)], fill=(8, 20, 29, 205))
    draw.rectangle([0, int(height * 0.76), width, height], fill=(8, 20, 29, 185))

    badge_font = ImageFont.truetype(FONT_BOLD, size=34)
    _draw_badge(draw, margin, 42, SOURCE_LABELS.get(source, source), badge_font)
    progress_font = ImageFont.truetype(FONT_BOLD, size=32)
    progress = f"{current_index + 1} / {len(bullets)}"
    pw = draw.textlength(progress, font=progress_font)
    draw.text((width - margin - pw, 55), progress, font=progress_font, fill=(230, 241, 247, 255))

    topic = bullets[current_index]
    topic_font = ImageFont.truetype(FONT_BOLD, size=76)
    topic_lines = _wrap_text(draw, topic, topic_font, width - margin * 2)
    if len(topic_lines) > 2:
        topic_font = ImageFont.truetype(FONT_BOLD, size=64)
        topic_lines = _wrap_text(draw, topic, topic_font, width - margin * 2)[:2]
    y = 145
    for line in topic_lines:
        draw.text((margin, y), line, font=topic_font, fill=(255, 255, 255, 255))
        y += topic_font.size * 1.18

    channel_font = ImageFont.truetype(FONT_BOLD, size=34)
    draw.text((margin, height - 105), "医療と医学の最新ニュース", font=channel_font, fill=(225, 239, 247, 255))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)


def make_thumbnail(
    source: str, thumbnail_text: str, title: str, out_path: Path, background_image_path=None
) -> None:
    width, height = 1280, 720

    if background_image_path and Path(background_image_path).exists():
        photo = Image.open(background_image_path).convert("RGB")
        photo = ImageOps.fit(photo, (width, height), method=Image.LANCZOS)
        darken = Image.new("RGB", (width, height), (8, 8, 8))
        img = Image.blend(photo, darken, 0.45)
    else:
        img = _gradient_background(width, height, THUMB_BG_TOP, THUMB_BG_BOTTOM)

    draw = ImageDraw.Draw(img)
    margin = int(width * 0.06)

    badge_font = ImageFont.truetype(FONT_BOLD, size=int(height * 0.05))
    text_font = ImageFont.truetype(FONT_BOLD, size=int(height * 0.19))
    title_font = ImageFont.truetype(FONT_BOLD, size=int(height * 0.045))

    badge_text = SOURCE_LABELS.get(source, source)
    badge_pad_x, badge_pad_y = 20, 12
    badge_w = draw.textlength(badge_text, font=badge_font) + badge_pad_x * 2
    badge_h = badge_font.size + badge_pad_y * 2
    draw.rounded_rectangle([margin, margin, margin + badge_w, margin + badge_h], radius=badge_h / 2, fill=(255, 255, 255))
    draw.text((margin + badge_pad_x, margin + badge_pad_y), badge_text, font=badge_font, fill=THUMB_BG_BOTTOM)

    text_lines = _wrap_text(draw, thumbnail_text, text_font, width - margin * 2)[:2]
    line_gap = 1.1
    block_h = len(text_lines) * text_font.size * line_gap
    y = (height - block_h) / 2
    shadow_offset = max(4, int(height * 0.008))
    for line in text_lines:
        w = draw.textlength(line, font=text_font)
        x = (width - w) / 2
        draw.text((x + shadow_offset, y + shadow_offset), line, font=text_font, fill=(0, 0, 0))
        draw.text(
            (x, y),
            line,
            font=text_font,
            fill=THUMB_TEXT_COLOR,
            stroke_width=9,
            stroke_fill=(20, 20, 20),
        )
        y += text_font.size * line_gap

    title_lines = _wrap_text(draw, title, title_font, width - margin * 2)[:2]
    y2 = height - margin - len(title_lines) * title_font.size * 1.3
    for line in title_lines:
        w = draw.textlength(line, font=title_font)
        draw.text(
            ((width - w) / 2, y2),
            line,
            font=title_font,
            fill=(255, 255, 255),
            stroke_width=4,
            stroke_fill=(0, 0, 0),
        )
        y2 += title_font.size * 1.3

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out_path)
