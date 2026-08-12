import re

MAX_CHUNK_LEN = 22
BREAK_CHARS = set("はがをにへでともやのねよかしば、。！？")
NO_CHUNK_START = set("、。！？：；）】」』〉》〕ぁぃぅぇぉゃゅょっァィゥェォャュョッー")
PREFERRED_SUFFIXES = ("しています", "して", "ています", "ました", "ません", "ため", "一方", "ただし")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？])")
CLAUSE_SPLIT_RE = re.compile(r"(?<=[、])")


def _find_break_point(text: str, max_len: int) -> int:
    window_start = max(2, max_len - 8)
    for i in range(min(max_len, len(text) - 1), window_start - 1, -1):
        if text[i - 1] in BREAK_CHARS:
            return i
    for i in range(max_len + 1, min(len(text), max_len + 10)):
        if text[i - 1] in BREAK_CHARS:
            return i
    cut = min(len(text), max_len + 8)
    while cut < len(text) and text[cut] in NO_CHUNK_START:
        cut += 1
    return cut


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


IMPORTANT_RE = re.compile(r"(大谷翔平|山本由伸|佐々木朗希|鈴木誠也|今永昇太|千賀滉大|ダルビッシュ有|菊池雄星|吉田正尚|本塁打|ホームラン|奪三振|勝利|敗戦|記録|\d+(?:\.\d+)?(?:本|安打|打点|盗塁|勝|敗|奪三振|回)?)")


def _highlight(text: str) -> str:
    return IMPORTANT_RE.sub(r'<font color="#FFCF40">\1</font>', text)
