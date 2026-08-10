import tempfile
import unittest
import wave
from pathlib import Path

from generator.artifacts import valid_text, valid_wav


class ArtifactTests(unittest.TestCase):
    def test_valid_wav_rejects_broken_and_accepts_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.wav"
            path.write_bytes(b"broken")
            self.assertFalse(valid_wav(path))
            with wave.open(str(path), "wb") as out:
                out.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
                out.writeframes(b"\0\0" * 800)
            self.assertTrue(valid_wav(path))

    def test_valid_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.srt"
            path.write_text("", encoding="utf-8")
            self.assertFalse(valid_text(path))
            path.write_text("caption", encoding="utf-8")
            self.assertTrue(valid_text(path))


if __name__ == "__main__":
    unittest.main()
