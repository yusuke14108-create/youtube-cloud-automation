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

BG_TOP = (244, 246, 250)
BG_BOTTOM = (224, 231, 242)
ACCENT_COLOR = (203, 55, 45)
ACCENT_LIGHT = (238, 196, 191)
TITLE_COLOR = (40, 48, 44)
SUMMARY_COLOR = (95, 107, 99)
BADGE_TEXT_COLOR = (255, 255, 255)
CARD_BG = (255, 255, 255)

THUMB_BG_TOP = (46, 148, 94)
THUMB_BG_BOTTOM = (33, 110, 70)
THUMB_TEXT_COLOR = (255, 224, 79)

SOURCE_LABELS = {
    "nba_news": "日本人選手 NBAニュース",
    "mhlw": "厚生労働省",
    "nta": "国税庁",
    "fsa": "金融庁",
    "soumu": "総務省",
    "kantei": "首相官邸",
}


_TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:[._/+:-][A-Za-z0-9]+)*|.")
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


def _gradient_background(width: int, height: int, top: tuple, bottom: tuple) -> Image.Image:
    img = Image.new("RGB", (width, height), top)
    draw = ImageDraw.Draw(img)
    for y in range(height):
        t = y / max(height - 1, 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        draw.line([(0, y), (width, y)], fill=color)
    return img


def make_abstract_panel_bg(width: int, height: int, out_path: Path, variant: int = 0) -> None:
    """A textured brand-color background for the no-asset motion fallback —
    a flat gradient shows almost no visible pan/zoom, so this gives the
    zoompan filter actual edges to move against."""
    img = _gradient_background(width, height, BG_TOP, BG_BOTTOM)
    draw = ImageDraw.Draw(img)
    blobs = [
        (0.15, 0.20, 0.55, ACCENT_LIGHT),
        (0.85, 0.75, 0.5, ACCENT_LIGHT),
        (0.75, 0.15, 0.32, ACCENT_COLOR),
        (0.25, 0.85, 0.30, ACCENT_COLOR),
    ]
    offset = variant % len(blobs)
    for i, (cx, cy, r, color) in enumerate(blobs):
        cx = (cx + offset * 0.13) % 1.0
        cy = (cy + offset * 0.09) % 1.0
        rad = r * min(width, height)
        draw.ellipse(
            [width * cx - rad, height * cy - rad, width * cx + rad, height * cy + rad],
            fill=color,
        )
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


CARD_ALPHA = 242


def _draw_comparison_panel(draw: ImageDraw.ImageDraw, x: float, y: float, w: float, h: float, visual: dict) -> None:
    label_font = ImageFont.truetype(FONT_REGULAR, size=int(h * 0.11))
    value_font = ImageFont.truetype(FONT_BOLD, size=int(h * 0.16))
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

        lw = draw.textlength(label, font=label_font)
        draw.text((x + (w - lw) / 2, box_y + box_h * 0.14), label, font=label_font, fill=label_color)

        vw = draw.textlength(value, font=value_font)
        draw.text((x + (w - vw) / 2, box_y + box_h * 0.44), value, font=value_font, fill=text_color)

    arrow_y = before_y + box_h + gap / 2
    aw = draw.textlength("↓", font=arrow_font)
    draw.text((x + (w - aw) / 2, arrow_y - arrow_font.size / 2), "↓", font=arrow_font, fill=ACCENT_COLOR)


def _draw_timeline_panel(draw: ImageDraw.ImageDraw, x: float, y: float, w: float, h: float, visual: dict) -> None:
    label_font = ImageFont.truetype(FONT_REGULAR, size=int(h * 0.1))
    date_font = ImageFont.truetype(FONT_BOLD, size=int(h * 0.15))

    card_h = h * 0.42
    card_y = y + (h - card_h) / 2

    draw.rounded_rectangle([x, card_y, x + w, card_y + card_h], radius=card_h * 0.18, fill=(*CARD_BG, CARD_ALPHA))

    label = visual.get("date_label", "")
    lw = draw.textlength(label, font=label_font)
    draw.text((x + (w - lw) / 2, card_y + card_h * 0.16), label, font=label_font, fill=SUMMARY_COLOR)

    date_value = visual.get("date_value", "")
    dw = draw.textlength(date_value, font=date_font)
    draw.text((x + (w - dw) / 2, card_y + card_h * 0.48), date_value, font=date_font, fill=ACCENT_COLOR)


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
    """Badge + title + summary on a transparent canvas with a dark scrim
    behind the text block, so a moving photo/video can show through the rest
    of the frame while the text stays legible over it."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = int(width * 0.08)
    max_w = width - margin * 2

    badge_font = ImageFont.truetype(FONT_BOLD, size=int(height * 0.032))
    # Shorts need a compact header: the old 5.5% title size could collide with
    # the source badge and push the second title outside its scrim.
    title_font = ImageFont.truetype(FONT_BOLD, size=int(height * 0.044))
    summary_font = ImageFont.truetype(FONT_REGULAR, size=int(height * 0.020))

    title_lines = _wrap_text(draw, title, title_font, max_w)
    summary_lines = _wrap_text(draw, summary, summary_font, max_w)[:max_summary_lines]

    line_gap = 1.35
    title_block_h = len(title_lines) * title_font.size * line_gap
    summary_block_h = len(summary_lines) * summary_font.size * line_gap
    block_gap = height * 0.05
    total_h = title_block_h + block_gap + summary_block_h
    badge_bottom = margin + badge_font.size * 1.7
    y = max(height * anchor_y_ratio - total_h / 2, badge_bottom + height * 0.025)

    scrim_pad = height * 0.03
    draw.rounded_rectangle(
        [margin * 0.4, y - scrim_pad, width - margin * 0.4, y + total_h + scrim_pad],
        radius=height * 0.02,
        fill=(20, 24, 22, 165),
    )

    _draw_badge(draw, margin, margin, SOURCE_LABELS.get(source, source), badge_font)

    for line in title_lines:
        w = draw.textlength(line, font=title_font)
        draw.text(((width - w) / 2, y), line, font=title_font, fill=(255, 255, 255, 255))
        y += title_font.size * line_gap

    y += block_gap
    for line in summary_lines:
        w = draw.textlength(line, font=summary_font)
        draw.text(((width - w) / 2, y), line, font=summary_font, fill=(235, 240, 236, 255))
        y += summary_font.size * line_gap

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)


def section_panel_box(width: int, height: int) -> tuple:
    """Geometry of the right-hand visual panel, shared with render_video.py so
    the motion clip composited underneath lines up with this foreground layer."""
    list_top = height * 0.32
    list_bottom = height * 0.72
    panel_x = width * 0.60
    panel_w = width * 0.92 - panel_x
    return panel_x, list_top, panel_w, list_bottom - list_top


def make_background(width: int, height: int, out_path: Path) -> None:
    img = _gradient_background(width, height, BG_TOP, BG_BOTTOM)
    draw = ImageDraw.Draw(img)
    _draw_decorative_circles(draw, width, height)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out_path)


def make_section_foreground(
    width: int,
    height: int,
    source: str,
    title: str,
    bullets: list,
    current_index: int,
    out_path: Path,
    visual: dict = None,
) -> None:
    """Badge/header/checklist and (if present) the semi-transparent comparison
    or timeline card, on a transparent canvas. The right-hand panel area
    (section_panel_box) is left transparent so a motion clip shows through it."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = int(width * 0.08)
    marker_d = int(height * 0.045)
    text_x = margin + marker_d + int(width * 0.025)

    list_w = width * 0.5
    max_w = list_w - (text_x - margin)

    badge_font = ImageFont.truetype(FONT_BOLD, size=int(height * 0.028))
    header_font = ImageFont.truetype(FONT_REGULAR, size=int(height * 0.024))
    marker_font = ImageFont.truetype(FONT_BOLD, size=int(height * 0.024))
    item_font_active = ImageFont.truetype(FONT_BOLD, size=int(height * 0.04))
    item_font_inactive = ImageFont.truetype(FONT_REGULAR, size=int(height * 0.032))

    badge_h = _draw_badge(draw, margin, margin, SOURCE_LABELS.get(source, source), badge_font)

    header_lines = _wrap_text(draw, title, header_font, width - margin * 2)[:1]
    hy = margin + badge_h + 14
    for line in header_lines:
        draw.text((margin, hy), line, font=header_font, fill=SUMMARY_COLOR)
        hy += header_font.size * 1.3

    list_top = height * 0.32
    list_bottom = height * 0.72
    n = len(bullets)
    row_h = (list_bottom - list_top) / n

    for i, text in enumerate(bullets):
        row_y = list_top + i * row_h
        cy = row_y + row_h / 2
        cx = margin + marker_d / 2

        if i < current_index:
            marker_fill = ACCENT_LIGHT
            marker_outline = None
            text_color = SUMMARY_COLOR
            font = item_font_inactive
            marker_label = None
            label_color = ACCENT_COLOR
        elif i == current_index:
            draw.rounded_rectangle(
                [margin - 14, row_y + row_h * 0.06, margin + text_x - margin + max_w + 20, row_y + row_h * 0.94],
                radius=row_h * 0.32,
                fill=(255, 255, 255),
            )
            marker_fill = ACCENT_COLOR
            marker_outline = None
            text_color = TITLE_COLOR
            font = item_font_active
            marker_label = str(i + 1)
            label_color = (255, 255, 255)
        else:
            marker_fill = None
            marker_outline = ACCENT_LIGHT
            text_color = (176, 187, 179)
            font = item_font_inactive
            marker_label = str(i + 1)
            label_color = (176, 187, 179)

        if marker_fill:
            draw.ellipse([cx - marker_d / 2, cy - marker_d / 2, cx + marker_d / 2, cy + marker_d / 2], fill=marker_fill)
        else:
            draw.ellipse(
                [cx - marker_d / 2, cy - marker_d / 2, cx + marker_d / 2, cy + marker_d / 2],
                outline=marker_outline,
                width=3,
            )

        if marker_label is None:
            # draw a checkmark with line segments instead of a "✓" glyph — Hiragino has no glyph for
            # it and silently falls back to a tofu box.
            draw.line(
                [(cx - marker_d * 0.22, cy), (cx - marker_d * 0.05, cy + marker_d * 0.2)],
                fill=label_color,
                width=3,
            )
            draw.line(
                [(cx - marker_d * 0.05, cy + marker_d * 0.2), (cx + marker_d * 0.25, cy - marker_d * 0.22)],
                fill=label_color,
                width=3,
            )
        else:
            lw = draw.textlength(marker_label, font=marker_font)
            draw.text((cx - lw / 2, cy - marker_font.size / 2 - 2), marker_label, font=marker_font, fill=label_color)

        draw.text((text_x, cy - font.size / 2 - 2), text, font=font, fill=text_color)

    if visual and visual.get("kind", "none") != "none":
        panel_x, panel_y, panel_w, panel_h = section_panel_box(width, height)
        _draw_visual_panel(draw, panel_x, panel_y, panel_w, panel_h, visual)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)


def make_thumbnail(
    source: str, thumbnail_text: str, title: str, out_path: Path, background_image_path=None, variant: int = 0
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

    variant %= 3
    # Rotate composition as well as imagery. This prevents every upload from
    # looking like the same centered template with different words.
    text_max_width = width - margin * 2 if variant == 0 else int(width * 0.70)
    text_lines = _wrap_text(draw, thumbnail_text, text_font, text_max_width)[:2]
    line_gap = 1.1
    block_h = len(text_lines) * text_font.size * line_gap
    y = (height - block_h) / 2 if variant != 2 else height * 0.20
    shadow_offset = max(4, int(height * 0.008))
    for line in text_lines:
        w = draw.textlength(line, font=text_font)
        if variant == 0:
            x = (width - w) / 2
        elif variant == 1:
            x = margin
        else:
            x = width - margin - w
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
        title_x = (width - w) / 2 if variant == 0 else (margin if variant == 1 else width - margin - w)
        draw.text(
            (title_x, y2),
            line,
            font=title_font,
            fill=(255, 255, 255),
            stroke_width=4,
            stroke_fill=(0, 0, 0),
        )
        y2 += title_font.size * 1.3

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out_path)
