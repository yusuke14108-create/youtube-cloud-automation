import math
import os
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

_TSUKUSHI = os.getenv("JP_FONT_PATH", "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc")
_TSUKUSHI_FALLBACK = "/System/Library/Fonts/ヒラギノ丸ゴ ProN W4.ttc"
FONT_BOLD = (_TSUKUSHI, 0)
FONT_REGULAR = (os.getenv("JP_FONT_REGULAR_PATH", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"), 0)


def _font(spec, size: int) -> ImageFont.FreeTypeFont:
    path, index = spec
    try:
        return ImageFont.truetype(path, size=size, index=index)
    except OSError:
        for candidate in (_TSUKUSHI_FALLBACK, "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
            try:
                return ImageFont.truetype(candidate, size=size)
            except OSError:
                continue
        return ImageFont.load_default()

BG_TOP = (241, 246, 250)
BG_BOTTOM = (229, 239, 232)
ACCENT_COLOR = (16, 92, 62)
ACCENT_LIGHT = (194, 222, 204)
TITLE_COLOR = (18, 42, 57)
SUMMARY_COLOR = (70, 91, 105)
BADGE_TEXT_COLOR = (255, 255, 255)
CARD_BG = (255, 255, 255)

THUMB_BG_TOP = (22, 91, 132)
THUMB_BG_BOTTOM = (20, 47, 79)
THUMB_TEXT_COLOR = (255, 226, 72)

SOURCE_LABELS = {
    "MLB": "MLB日本人選手ラボ", "打撃": "打撃データ", "投球": "投球データ",
    "試合結果": "試合結果", "選手解説": "選手解説", "記録": "記録解説",
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


def _fit_font(text: str, font_spec, max_size: int, min_size: int, max_width: float) -> ImageFont.FreeTypeFont:
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    for size in range(max_size, min_size - 1, -1):
        font = _font(font_spec, size)
        if probe.textlength(text, font=font) <= max_width:
            return font
    return _font(font_spec, min_size)


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


CONFETTI_COLORS = [(255, 205, 69), (54, 190, 178), (118, 145, 229), (244, 126, 146)]


def _draw_star(draw: ImageDraw.ImageDraw, cx: float, cy: float, r_outer: float, fill, r_inner_ratio: float = 0.45) -> None:
    r_inner = r_outer * r_inner_ratio
    points = []
    for i in range(10):
        angle = math.pi / 2 + i * math.pi / 5
        r = r_outer if i % 2 == 0 else r_inner
        points.append((cx + r * math.cos(angle), cy - r * math.sin(angle)))
    draw.polygon(points, fill=fill)


def _draw_decorative_circles(draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
    draw.ellipse(
        [width * 0.68, -height * 0.16, width * 1.18, height * 0.38],
        fill=ACCENT_LIGHT,
    )
    draw.ellipse(
        [-width * 0.22, height * 0.72, width * 0.28, height * 1.28],
        fill=ACCENT_LIGHT,
    )
    # confetti: kept to corners/blob areas only — the center band (list rows + key-point
    # chips) is real content and stars there would overlap text.
    dots = [
        (0.02, 0.03, 14, 0), (0.94, 0.07, 11, 2), (0.97, 0.50, 13, 3),
        (0.05, 0.92, 12, 1), (0.92, 0.93, 15, 0),
    ]
    for fx, fy, size, ci in dots:
        color = CONFETTI_COLORS[ci % len(CONFETTI_COLORS)]
        _draw_star(draw, width * fx, height * fy, size, color)


def _draw_badge(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, font: ImageFont.FreeTypeFont) -> int:
    pad_x, pad_y = 22, 12
    w = draw.textlength(text, font=font) + pad_x * 2
    h = font.size + pad_y * 2
    draw.rounded_rectangle([x, y, x + w, y + h], radius=h / 2, fill=ACCENT_COLOR)
    draw.text((x + pad_x, y + pad_y), text, font=font, fill=BADGE_TEXT_COLOR)
    return h


def _draw_comparison_panel(draw: ImageDraw.ImageDraw, x: float, y: float, w: float, h: float, visual: dict) -> None:
    arrow_font = _font(FONT_BOLD, int(h * 0.14))

    box_h = h * 0.34
    gap = h * 0.1

    before_y = y
    after_y = y + box_h + gap

    for box_y, label, value, is_after in (
        (before_y, visual.get("before_label", ""), visual.get("before_value", ""), False),
        (after_y, visual.get("after_label", ""), visual.get("after_value", ""), True),
    ):
        fill = ACCENT_COLOR if is_after else CARD_BG
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

    draw.rounded_rectangle([x, card_y, x + w, card_y + card_h], radius=card_h * 0.18, fill=CARD_BG)

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


def _draw_science_visual(img, draw, x, y, w, h, visual):
    """Render a licensed photo or a simple original explanatory diagram."""
    draw.rounded_rectangle([x, y, x + w, y + h], radius=28, fill=(255, 255, 255))
    local = visual.get("local_path")
    if local and Path(local).exists():
        photo = Image.open(local).convert("RGB")
        scale = max(w / photo.width, h / photo.height)
        photo = photo.resize((int(photo.width * scale), int(photo.height * scale)))
        left = max(0, int((photo.width - w) / 2))
        top = max(0, int((photo.height - h) / 2))
        photo = photo.crop((left, top, left + int(w), top + int(h)))
        mask = Image.new("L", (int(w), int(h)), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, w, h], radius=28, fill=255)
        img.paste(photo, (int(x), int(y)), mask)
    else:
        labels = visual.get("labels") or ["ふしぎ", "しくみ"]
        colors = [(255, 205, 69), (54, 190, 178), (118, 145, 229), (244, 126, 146)]
        cy = y + h * 0.46
        spacing = w / (len(labels) + 1)
        font = _font(FONT_BOLD, max(22, int(h * 0.065)))
        for i, label in enumerate(labels):
            cx = x + spacing * (i + 1)
            radius = min(w / (len(labels) * 3.2), h * 0.13)
            draw.ellipse([cx-radius, cy-radius, cx+radius, cy+radius], fill=colors[i % len(colors)])
            fitted = _fit_font(label, FONT_BOLD, font.size, 18, spacing * 0.9)
            tw = draw.textlength(label, font=fitted)
            draw.text((cx - tw/2, cy + radius + 14), label, font=fitted, fill=TITLE_COLOR)
            if i < len(labels) - 1:
                draw.line([cx+radius, cy, cx+spacing-radius, cy], fill=ACCENT_COLOR, width=6)
                draw.polygon([(cx+spacing-radius, cy), (cx+spacing-radius-18, cy-10), (cx+spacing-radius-18, cy+10)], fill=ACCENT_COLOR)
    caption = visual.get("caption", "")
    if caption:
        font = _fit_font(caption, FONT_BOLD, 30, 20, w - 40)
        shown = _ellipsize(draw, caption, font, w - 40)
        draw.rounded_rectangle([x+16, y+h-64, x+w-16, y+h-14], radius=18, fill=(255, 255, 255, 220))
        tw = draw.textlength(shown, font=font)
        draw.text((x+(w-tw)/2, y+h-57), shown, font=font, fill=TITLE_COLOR)


def _should_draw_diagram(has_media: bool, visual: dict = None) -> bool:
    """Photos take priority; diagrams are used only when no licensed image exists."""
    return (not has_media) and bool(visual) and visual.get("kind", "none") != "none"


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

    badge_font = _font(FONT_BOLD, int(height * 0.032))
    title_font = _font(FONT_BOLD, int(height * 0.055))
    summary_font = _font(FONT_REGULAR, int(height * 0.026))

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


def make_short_slide(width: int, height: int, source: str, hook: str, out_path: Path, visual: dict = None, background_image_path=None, background_kind=None) -> None:
    """Portrait layout with fixed safe zones for the hook and burned-in captions."""
    has_media = bool(background_image_path) and Path(background_image_path).exists()
    if has_media:
        photo = ImageOps.fit(Image.open(background_image_path).convert("RGB"), (width, height), method=Image.LANCZOS)
        wash = Image.new("RGB", (width, height), BG_TOP)
        img = Image.blend(photo, wash, 0.12 if background_kind == "illustration" else 0.48)
    else:
        img = _gradient_background(width, height, BG_TOP, BG_BOTTOM)
    draw = ImageDraw.Draw(img)
    if not has_media:
        _draw_decorative_circles(draw, width, height)

    margin = int(width * 0.09)
    badge_font = _font(FONT_BOLD, 38)
    badge_h = _draw_badge(draw, margin, 82, SOURCE_LABELS.get(source, source), badge_font)

    # Keep the hook below the badge and above the subtitle zone. Its font shrinks
    # until the whole block fits, so Japanese line breaks never collide with UI.
    hook_top = 1040 if background_kind == "illustration" else 210
    hook_bottom = 1300 if background_kind == "illustration" else 600
    max_w = width - margin * 2
    chosen_font = None
    chosen_lines = None
    for size in range(76, 47, -2):
        font = _font(FONT_BOLD, size)
        lines = _wrap_text(draw, hook, font, max_w)
        block_h = len(lines) * size * 1.22
        if len(lines) <= 4 and block_h <= hook_bottom - hook_top:
            chosen_font, chosen_lines = font, lines
            break
    if chosen_font is None:
        chosen_font = _font(FONT_BOLD, 46)
        chosen_lines = _wrap_text(draw, hook, chosen_font, max_w)[:4]

    line_h = chosen_font.size * 1.22
    block_h = len(chosen_lines) * line_h
    card_pad = 26
    card_top = hook_top + (hook_bottom - hook_top - block_h) / 2 - card_pad
    card_bottom = card_top + block_h + card_pad * 2
    pop_color = CONFETTI_COLORS[1]
    shadow_off = 10
    draw.rounded_rectangle(
        [margin - 16 + shadow_off, card_top + shadow_off, width - margin + 16 + shadow_off, card_bottom + shadow_off],
        radius=36, fill=ACCENT_LIGHT,
    )
    draw.rounded_rectangle(
        [margin - 16, card_top, width - margin + 16, card_bottom],
        radius=36, fill=(255, 255, 255), outline=pop_color, width=6,
    )
    _draw_star(draw, margin + 6, card_top + 10, 22, CONFETTI_COLORS[0])
    _draw_star(draw, width - margin - 6, card_bottom - 10, 22, CONFETTI_COLORS[3])

    y = hook_top + (hook_bottom - hook_top - block_h) / 2
    for line in chosen_lines:
        tw = draw.textlength(line, font=chosen_font)
        draw.text(((width - tw) / 2, y), line, font=chosen_font, fill=TITLE_COLOR)
        y += line_h

    # A licensed photo is the primary explanation. Do not cover it with the old
    # connected-circle diagram; diagrams are only a last-resort fallback.
    if _should_draw_diagram(has_media, visual):
        _draw_science_visual(img, draw, margin, 660, width - margin * 2, 540, visual)

    divider_y = 1260
    if background_kind != "illustration":
        draw.rounded_rectangle([margin, divider_y, width - margin, divider_y + 5], radius=2, fill=ACCENT_COLOR)
    channel_font = _font(FONT_BOLD, 32)
    channel_text = "メジャー魂｜MLB速報"
    channel_w = draw.textlength(channel_text, font=channel_font)
    channel_y = 150 if background_kind == "illustration" else divider_y + 35
    draw.text(((width - channel_w) / 2, channel_y), channel_text, font=channel_font, fill=(255, 255, 255) if background_kind == "illustration" else SUMMARY_COLOR, stroke_width=3 if background_kind == "illustration" else 0, stroke_fill=(8, 18, 30))

    guide_font = _font(FONT_REGULAR, 27)
    guide_text = "日本人メジャーリーガーを60秒で！"
    guide_w = draw.textlength(guide_text, font=guide_font)
    if background_kind != "illustration":
        draw.text(((width - guide_w) / 2, divider_y + 90), guide_text, font=guide_font, fill=(132, 147, 157))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out_path)


def make_section_slide(
    width: int,
    height: int,
    source: str,
    title: str,
    bullets: list,
    current_index: int,
    out_path: Path,
    visual: dict = None,
    key_points: list = None,
    background_image_path=None,
) -> None:
    img = _gradient_background(width, height, BG_TOP, BG_BOTTOM)
    has_media = bool(background_image_path) and Path(background_image_path).exists()
    if has_media:
        photo = ImageOps.fit(
            Image.open(background_image_path).convert("RGB"),
            (int(width * 0.46), int(height * 0.58)), method=Image.LANCZOS,
        )
        img.paste(photo, (int(width * 0.52), int(height * 0.20)))
    draw = ImageDraw.Draw(img)
    if not has_media:
        _draw_decorative_circles(draw, width, height)

    margin = int(width * 0.08)
    marker_d = int(height * 0.045)
    text_x = margin + marker_d + int(width * 0.018)

    # Prefer a real, licensed image whenever one was retrieved. The previous
    # visual panel was drawn over the photo and made the output look like a row
    # of connected circles even though an image existed underneath.
    has_visual = _should_draw_diagram(has_media, visual)
    list_right = width * 0.48 if has_visual or has_media else width * 0.91
    max_w = list_right - text_x

    badge_font = _font(FONT_BOLD, int(height * 0.028))
    header_font = _font(FONT_REGULAR, int(height * 0.024))
    marker_font = _font(FONT_BOLD, int(height * 0.026))
    item_font_active = _font(FONT_BOLD, int(height * 0.040))
    item_font_inactive = _font(FONT_REGULAR, int(height * 0.026))

    badge_h = _draw_badge(draw, margin, margin, SOURCE_LABELS.get(source, source), badge_font)

    header_lines = _wrap_text(draw, title, header_font, width - margin * 2)[:1]
    hy = margin + badge_h + 14
    for line in header_lines:
        draw.text((margin, hy), line, font=header_font, fill=SUMMARY_COLOR)
        hy += header_font.size * 1.3

    list_top = height * 0.26
    list_bottom = height * 0.68
    n = len(bullets)
    row_h = (list_bottom - list_top) / n

    for i, text in enumerate(bullets):
        row_y = list_top + i * row_h
        cy = row_y + row_h / 2
        cx = margin + marker_d / 2

        if i < current_index:
            marker_fill = ACCENT_LIGHT
            marker_outline = None
            text_color = (132, 147, 157)
            font = item_font_inactive
            marker_label = None
            label_color = ACCENT_COLOR
        elif i == current_index:
            pop_color = CONFETTI_COLORS[i % len(CONFETTI_COLORS)]
            shadow_off = row_h * 0.05
            draw.rounded_rectangle(
                [margin - 14 + shadow_off, row_y + row_h * 0.06 + shadow_off, list_right + 14 + shadow_off, row_y + row_h * 0.94 + shadow_off],
                radius=row_h * 0.32,
                fill=ACCENT_LIGHT,
            )
            draw.rounded_rectangle(
                [margin - 14, row_y + row_h * 0.06, list_right + 14, row_y + row_h * 0.94],
                radius=row_h * 0.32,
                fill=(255, 255, 255),
                outline=pop_color,
                width=5,
            )
            marker_fill = pop_color
            marker_outline = None
            text_color = TITLE_COLOR
            font = item_font_active
            marker_label = str(i + 1)
            label_color = (255, 255, 255)
        else:
            marker_fill = None
            marker_outline = ACCENT_LIGHT
            text_color = (185, 196, 201)
            font = item_font_inactive
            marker_label = str(i + 1)
            label_color = (176, 187, 179)

        if i == current_index:
            _draw_star(draw, cx, cy, marker_d * 0.72, marker_fill)
        elif marker_fill:
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

        fitted = _fit_font(text, FONT_BOLD if i == current_index else FONT_REGULAR, font.size, 22, max_w)
        display_text = _ellipsize(draw, text, fitted, max_w)
        if i == current_index:
            draw.text(
                (text_x, cy - fitted.size / 2 - 2),
                display_text,
                font=fitted,
                fill=text_color,
                stroke_width=2,
                stroke_fill=pop_color,
            )
        else:
            draw.text((text_x, cy - fitted.size / 2 - 2), display_text, font=fitted, fill=text_color)

    if has_visual:
        panel_x = width * 0.53
        panel_w = width * 0.92 - panel_x
        _draw_science_visual(img, draw, panel_x, list_top, panel_w, list_bottom - list_top, visual)

    if key_points:
        chip_y = height * 0.78
        gap = 18
        chip_w = (width - margin * 2 - gap * (len(key_points) - 1)) / len(key_points)
        chip_font = _font(FONT_BOLD, 27)
        for i, point in enumerate(key_points):
            x = margin + i * (chip_w + gap)
            draw.rounded_rectangle([x, chip_y, x + chip_w, chip_y + 72], radius=24, fill=(255, 255, 255), outline=ACCENT_LIGHT, width=3)
            _draw_centered_fit(draw, point, (x, chip_y, chip_w, 72), FONT_BOLD, chip_font.size, 19, TITLE_COLOR)

    credit = (visual or {}).get("credit", "")
    if credit:
        credit_font = _font(FONT_REGULAR, 16)
        draw.text((margin, height - 30), f"画像: {credit}", font=credit_font, fill=SUMMARY_COLOR)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out_path)


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

    badge_font = _font(FONT_BOLD, int(height * 0.05))
    text_font = _font(FONT_BOLD, int(height * 0.19))
    title_font = _font(FONT_BOLD, int(height * 0.045))

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
