import unittest

from generator.slides import _should_draw_diagram


class VisualPriorityTests(unittest.TestCase):
    def test_licensed_photo_suppresses_connected_circle_diagram(self):
        visual = {"kind": "diagram", "labels": ["A", "B", "C"]}
        self.assertFalse(_should_draw_diagram(True, visual))

    def test_diagram_remains_as_no_photo_fallback(self):
        visual = {"kind": "diagram", "labels": ["A", "B", "C"]}
        self.assertTrue(_should_draw_diagram(False, visual))


if __name__ == "__main__":
    unittest.main()
