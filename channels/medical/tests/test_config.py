import unittest

from generator.config import UPLOAD_PRIVACY


class ConfigTests(unittest.TestCase):
    def test_upload_never_defaults_public(self):
        self.assertIn(UPLOAD_PRIVACY, {"private", "unlisted"})


if __name__ == "__main__":
    unittest.main()
