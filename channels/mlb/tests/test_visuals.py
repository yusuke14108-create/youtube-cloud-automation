import unittest

from generator.slides import _TOKEN_RE, _should_draw_diagram


class VisualPriorityTests(unittest.TestCase):
    def test_title_tokenizer_keeps_inflected_japanese_word(self):
        self.assertIn("新しい", _TOKEN_RE.findall("新しい記録が生まれた"))

    def test_licensed_photo_suppresses_connected_circle_diagram(self):
        visual = {"kind": "diagram", "labels": ["A", "B", "C"]}
        self.assertFalse(_should_draw_diagram(True, visual))

    def test_diagram_remains_as_no_photo_fallback(self):
        visual = {"kind": "diagram", "labels": ["A", "B", "C"]}
        self.assertTrue(_should_draw_diagram(False, visual))


if __name__ == "__main__":
    unittest.main()
