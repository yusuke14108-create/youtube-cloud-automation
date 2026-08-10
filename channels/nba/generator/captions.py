import re

MAX_CHUNK_LEN = 20
BREAK_CHARS = set("はがをにでともやのねよかしば")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？])")
CLAUSE_SPLIT_RE = re.compile(r"(?<=[、])")


def _find_break_point(text: str, max_len: int) -> int:
    window_start = max(1, max_len - 6)
    for i in range(max_len, window_start - 1, -1):
        if i < len(text) and text[i - 1] in BREAK_CHARS:
            return i
    return max_len


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


def _merge_short_tails(chunks: list, min_len: int = 3) -> list:
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


def write_srt(captions: list, out_path) -> None:
    lines = []
    for i, cue in enumerate(captions, start=1):
        lines.append(str(i))
        lines.append(f"{_format_timestamp(cue['start'])} --> {_format_timestamp(cue['end'])}")
        lines.append(cue["text"])
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")
