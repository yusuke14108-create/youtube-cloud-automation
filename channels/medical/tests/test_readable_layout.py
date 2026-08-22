import unittest

from generator.captions import text_to_caption_chunks
from generator.slides import _TOKEN_RE, section_panel_box


class ReadableLayoutTests(unittest.TestCase):
    def test_title_tokenizer_keeps_inflected_japanese_word(self):
        self.assertIn("新しい", _TOKEN_RE.findall("新しい治療が始まる"))

    def test_caption_does_not_split_new_word(self):
        chunks = text_to_caption_chunks("この新しい治療法について説明します。", max_len=7)
        boundaries = {len("".join(chunks[:i])) for i in range(1, len(chunks))}
        start = "この新しい治療法について説明します。".index("新しい")
        self.assertFalse(any(start < boundary < start + len("新しい") for boundary in boundaries))

    def test_long_form_image_is_full_bleed(self):
        self.assertEqual((0, 0, 1920, 1080), section_panel_box(1920, 1080))


if __name__ == "__main__":
    unittest.main()
