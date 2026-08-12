import re
from typing import Optional

MAX_CHUNK_LEN = 20
BREAK_CHARS = set("、。！？：；")
NO_CHUNK_START = set("、。！？：；）】」』〉》〕ぁぃぅぇぉゃゅょっァィゥェォャュョッー")
NO_CHUNK_END = set("、：；（【「『〈《〔")
PARTICLES = set("はがをにへでともやのかば")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？])")
CLAUSE_SPLIT_RE = re.compile(r"(?<=[、])")


def _char_class(ch: str) -> str:
    code = ord(ch)
    if 0x4E00 <= code <= 0x9FFF or 0x3400 <= code <= 0x4DBF:
        return "kanji"
    if 0x3040 <= code <= 0x309F:
        return "hiragana"
    if 0x30A0 <= code <= 0x30FF:
        return "katakana"
    if ch.isascii() and ch.isalnum():
        return "ascii"
    return "other"


def _break_score(text: str, index: int, target: int) -> int:
    """Score a cue boundary without cutting a word or stranding a particle."""
    if not 1 < index < len(text):
        return -10_000
    left, right = text[index - 1], text[index]
    if left in NO_CHUNK_END or right in NO_CHUNK_START or right in PARTICLES:
        return -10_000
    score = -abs(index - target) * 3
    if left in BREAK_CHARS:
        score += 100
    if left in PARTICLES:
        score += 65
    left_class, right_class = _char_class(left), _char_class(right)
    if left_class != right_class:
        score += 20
    # Hiragana followed by kanji is commonly a phrase boundary (選んだ|理由).
    if left_class == "hiragana" and right_class == "kanji":
        score += 55
    # Kanji followed by hiragana is commonly one inflected word (選|んだ, 見|える).
    if left_class == "kanji" and right_class == "hiragana":
        score -= 100
    # Never split a kanji compound such as 「理由」 or an alphabetic name.
    if left_class == right_class and left_class in {"kanji", "katakana", "ascii"}:
        score -= 90
    if left_class == right_class == "hiragana":
        score -= 55
    # A one-character particle belongs with the phrase on its left: 「私は」, not 「私」/「は」.
    return score


def _find_break_point(text: str, max_len: int) -> int:
    upper = min(len(text) - 1, max_len + 8)
    lower = max(3, max_len - 8)
    candidates = range(lower, upper + 1)
    return max(candidates, key=lambda i: _break_score(text, i, max_len))


def _hard_wrap(text: str, max_len: int) -> list:
    chunks = []
    remaining = text
    while len(remaining) > max_len:
        cut = _find_break_point(remaining, max_len)
        chunks.append(remaining[:cut])
        remaining = remaining[cut:]
    if remaining:
        chunks.append(remaining)
    return chunks or [text]


def _merge_short_tails(chunks: list, min_len: int = 6) -> list:
    merged = []
    for chunk in chunks:
        if merged and len(chunk) < min_len:
            merged[-1] += chunk
        else:
            merged.append(chunk)
    return merged


def text_to_caption_chunks(text: str, max_len: int = MAX_CHUNK_LEN) -> list:
    chunks = []
    for sentence in SENTENCE_SPLIT_RE.split(text):
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) <= max_len:
            chunks.append(sentence)
            continue
        for clause in CLAUSE_SPLIT_RE.split(sentence):
            clause = clause.strip()
            if not clause:
                continue
            if len(clause) <= max_len:
                chunks.append(clause)
            else:
                chunks.extend(_hard_wrap(clause, max_len))
    return _merge_short_tails(chunks) or [text]


def chunks_to_captions(chunks: list, durations: list, offset: float = 0.0) -> list:
    captions = []
    t = offset
    for chunk, duration in zip(chunks, durations):
        captions.append({"start": t, "end": t + duration, "text": chunk})
        t += duration
    return captions


def _format_timestamp(seconds: float) -> str:
    ms = round(seconds * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1_000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def caption_display_text(text: str, max_line_len: Optional[int] = None) -> str:
    if not max_line_len or len(text) <= max_line_len:
        return text
    return "\n".join(_hard_wrap(text, max_line_len))


def write_srt(captions: list, out_path, max_line_len: Optional[int] = None) -> None:
    lines = []
    for i, cue in enumerate(captions, start=1):
        lines.append(str(i))
        lines.append(f"{_format_timestamp(cue['start'])} --> {_format_timestamp(cue['end'])}")
        lines.append(_highlight(caption_display_text(cue["text"], max_line_len)))
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


IMPORTANT_RE = re.compile(r"(河村勇輝|八村塁|富永啓生|契約|移籍|復帰|得点|勝利|負傷|記録|日本代表|\d+(?:\.\d+)?(?:点|本|勝|敗|％|%|位)?)")


def _highlight(text: str) -> str:
    return IMPORTANT_RE.sub(r'<font color="#FFD54A">\1</font>', text)
