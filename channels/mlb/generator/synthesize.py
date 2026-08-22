import json
import os
import wave
from io import BytesIO
from pathlib import Path

import requests

from generator.captions import MAX_CHUNK_LEN, chunks_to_captions, text_to_caption_chunks, write_srt
from generator.pronunciation import for_speech

ENGINE_URL = os.getenv("VOICEVOX_URL", "http://localhost:50021")
SPEAKER_ID = int(os.getenv("VOICEVOX_SPEAKER_ID", "3"))

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "data" / "scripts"
AUDIO_DIR = ROOT / "data" / "audio"


SENTENCE_END_CHARS = "。！？"


def _synthesize_segment(session: requests.Session, text: str, is_first=True, is_last=True) -> bytes:
    query = session.post(f"{ENGINE_URL}/audio_query", params={"text": for_speech(text), "speaker": SPEAKER_ID}, timeout=30)
    query.raise_for_status()
    payload = query.json()

    # VOICEVOX pads 0.1s of silence before and after every synthesis call. Since captions are
    # synthesized one chunk at a time, leaving that on would insert a pause at every chunk
    # boundary and make continuous sentences sound chopped up. Keep padding only where a real
    # pause belongs: the start/end of a section, and after sentence-final punctuation.
    payload["prePhonemeLength"] = 0.1 if is_first else 0.0
    if is_last:
        payload["postPhonemeLength"] = 0.1
    else:
        payload["postPhonemeLength"] = 0.25 if text.rstrip().endswith(tuple(SENTENCE_END_CHARS)) else 0.0

    synth = session.post(
        f"{ENGINE_URL}/synthesis",
        params={"speaker": SPEAKER_ID},
        json=payload,
        timeout=60,
    )
    synth.raise_for_status()
    return synth.content


def _synthesize_chunks(session: requests.Session, text: str, max_len: int = MAX_CHUNK_LEN) -> tuple:
    """Synthesize each caption chunk separately, so subtitle timing is each
    chunk's own measured audio duration instead of a character-count estimate."""
    chunks = text_to_caption_chunks(text.replace("\n", ""), max_len=max_len)
    last = len(chunks) - 1
    wav_bytes_list = [
        _synthesize_segment(session, chunk, is_first=(i == 0), is_last=(i == last))
        for i, chunk in enumerate(chunks)
    ]
    durations = [_wav_duration(w) for w in wav_bytes_list]
    return chunks, wav_bytes_list, durations


def _wav_duration(wav_bytes: bytes) -> float:
    with wave.open(BytesIO(wav_bytes), "rb") as w:
        return w.getnframes() / w.getframerate()


def _concat_wavs(wav_bytes_list: list, out_path: Path) -> None:
    with wave.open(BytesIO(wav_bytes_list[0]), "rb") as first:
        params = first.getparams()

    with wave.open(str(out_path), "wb") as out:
        out.setparams(params)
        for wav_bytes in wav_bytes_list:
            with wave.open(BytesIO(wav_bytes), "rb") as w:
                out.writeframes(w.readframes(w.getnframes()))


def synthesize_text(session: requests.Session, text: str, out_wav_path: Path, out_srt_path: Path, caption_max_len: int = 22) -> None:
    chunks, wav_bytes_list, durations = _synthesize_chunks(session, text, max_len=caption_max_len)

    out_wav_path.parent.mkdir(parents=True, exist_ok=True)
    _concat_wavs(wav_bytes_list, out_wav_path)

    captions = chunks_to_captions(chunks, durations)
    write_srt(captions, out_srt_path)
    sync_path = out_srt_path.with_suffix(".sync.json")
    sync_path.write_text(json.dumps([
        {"display": chunk, "speech": for_speech(chunk), "duration": duration}
        for chunk, duration in zip(chunks, durations)
    ], ensure_ascii=False, indent=2), encoding="utf-8")


def synthesize_sections(
    session: requests.Session,
    sections: list,
    out_wav_path: Path,
    out_srt_path: Path,
    out_sections_path: Path,
) -> None:
    all_wav_bytes = []
    all_captions = []
    section_durations = []
    offset = 0.0

    for section in sections:
        chunks, wav_bytes_list, durations = _synthesize_chunks(session, section["narration"])
        all_wav_bytes.extend(wav_bytes_list)
        all_captions.extend(chunks_to_captions(chunks, durations, offset=offset))
        section_duration = sum(durations)
        section_durations.append(section_duration)
        offset += section_duration

    out_wav_path.parent.mkdir(parents=True, exist_ok=True)
    _concat_wavs(all_wav_bytes, out_wav_path)
    write_srt(all_captions, out_srt_path)

    sections_out = [{"bullet": s["bullet"], "duration": d} for s, d in zip(sections, section_durations)]
    out_sections_path.write_text(json.dumps(sections_out, ensure_ascii=False, indent=2), encoding="utf-8")


def latest_script_file():
    files = sorted(SCRIPTS_DIR.glob("*.json"))
    return files[-1] if files else None


def main(script_path=None):
    path = script_path or latest_script_file()
    if path is None:
        print("[info] no script file found")
        return None

    data = json.loads(path.read_text(encoding="utf-8"))
    session = requests.Session()
    out_dir = AUDIO_DIR / path.stem

    for i, video in enumerate(data["long_videos"], start=1):
        synthesize_sections(
            session, video["sections"], out_dir / f"long_{i}.wav",
            out_dir / f"long_{i}.srt", out_dir / f"long_{i}_sections.json",
        )
        print(f"[info] wrote {out_dir / f'long_{i}.wav'}")

    for i, short in enumerate(data["short_videos"], start=1):
        wav_path = out_dir / f"short_{i}.wav"
        srt_path = out_dir / f"short_{i}.srt"
        # Larger mobile-first captions need shorter phrase units.  The caption
        # splitter still protects player names, statistics and Japanese word
        # boundaries, so this does not introduce mid-word line breaks.
        synthesize_text(session, short["script"], wav_path, srt_path, caption_max_len=12)
        print(f"[info] wrote {wav_path}")

    return out_dir


if __name__ == "__main__":
    main()
