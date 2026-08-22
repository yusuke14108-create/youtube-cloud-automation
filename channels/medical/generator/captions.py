import re

MAX_CHUNK_LEN = 22
SHORT_CTA = "詳しい解説は、チャンネルの長尺動画をご覧ください。"


def ensure_short_cta(script: str) -> str:
    return script if SHORT_CTA in script else script.rstrip() + SHORT_CTA


BREAK_CHARS = set("はがをにへでともやのねよかしば、。！？")
NO_CHUNK_START = set("、。！？：；）】」』〉》〕ぁぃぅぇぉゃゅょっァィゥェォャュョッー")
NO_CHUNK_END = set("、：；（【「『〈《〔")
PARTICLES = set("はがをにへでともやのかば")
PREFERRED_SUFFIXES = ("しています", "して", "ています", "ました", "ません", "ため", "一方", "ただし")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？])")
CLAUSE_SPLIT_RE = re.compile(r"(?<=[、])")
PROTECTED_TERM_RE = re.compile(
    r"[ァ-ヶー・]+(?:[0-9０-９]+)?(?:mg|mL|錠|カプセル|契約)?|"
    r"[一-龯々]+(?:[ぁ-ん]{1,4})?|"
    r"[A-Za-z]+(?:[ -][A-Za-z0-9]+)*|"
    r"[0-9０-９]+(?:\.[0-9０-９]+)?(?:mg|mL|％|%|例|人|倍)"
)


def _inside_protected_term(text: str, index: int) -> bool:
    return any(start < index < end for start, end in (m.span() for m in PROTECTED_TERM_RE.finditer(text)))


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
    if not 1 < index < len(text) or _inside_protected_term(text, index):
        return -10_000
    left, right = text[index - 1], text[index]
    if left in NO_CHUNK_END or right in NO_CHUNK_START or right in PARTICLES:
        return -10_000
    score = -abs(index - target) * 3
    if left in "、。！？":
        score += 100
    if left in PARTICLES:
        score += 65
    left_class, right_class = _char_class(left), _char_class(right)
    if left_class != right_class:
        score += 20
    if left_class == "hiragana" and right_class == "kanji":
        score += 55
    if left_class == "kanji" and right_class == "hiragana":
        score -= 100
    if left_class == right_class and left_class in {"kanji", "katakana", "ascii"}:
        score -= 90
    return score


def _find_break_point(text: str, max_len: int) -> int:
    lower = max(3, max_len - 8)
    upper = min(len(text) - 1, max_len + 8)
    return max(range(lower, upper + 1), key=lambda i: _break_score(text, i, max_len))


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
    return _merge_short_tails(chunks)


def chunks_to_captions(chunks: list, durations: list, offset: float = 0.0) -> list:
    """Each chunk is timed by its own measured audio duration. The earlier
    approach split a paragraph's total duration by character count, which
    accumulated drift against the actual narration within long paragraphs."""
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


def write_srt(captions: list, out_path) -> None:
    lines = []
    for i, cue in enumerate(captions, start=1):
        lines.append(str(i))
        lines.append(f"{_format_timestamp(cue['start'])} --> {_format_timestamp(cue['end'])}")
        lines.append(_highlight(cue["text"]))
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


IMPORTANT_RE = re.compile(r"(死亡|重症|注意|警告|有効|無効|改善|悪化|副作用|リスク|治療|予防|感染|がん|癌|\d+(?:\.\d+)?(?:mg|mL|例|人|％|%|倍)?)")


def _highlight(text: str) -> str:
    return IMPORTANT_RE.sub(r'<font color="#52D6FF">\1</font>', text)
