import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from generator import youtube_auth


class YouTubeAuthTests(unittest.TestCase):
    def test_reauthorize_failure_preserves_existing_token(self):
        with tempfile.TemporaryDirectory() as temp:
            token_path = Path(temp) / "token.json"
            token_path.write_text("old-token", encoding="utf-8")
            flow = Mock()
            flow.run_local_server.side_effect = RuntimeError("consent cancelled")
            with patch.object(youtube_auth, "TOKEN_PATH", token_path), \
                 patch.object(youtube_auth.Credentials, "from_authorized_user_file") as loader, \
                 patch.object(youtube_auth.InstalledAppFlow, "from_client_secrets_file", return_value=flow):
                with self.assertRaises(RuntimeError):
                    youtube_auth.get_credentials(force_interactive=True)
            loader.assert_not_called()
            self.assertEqual(token_path.read_text(encoding="utf-8"), "old-token")

    def test_reauthorize_success_replaces_token(self):
        with tempfile.TemporaryDirectory() as temp:
            token_path = Path(temp) / "token.json"
            token_path.write_text("old-token", encoding="utf-8")
            credentials = Mock()
            credentials.valid = True
            credentials.to_json.return_value = "new-token"
            flow = Mock()
            flow.run_local_server.return_value = credentials
            with patch.object(youtube_auth, "TOKEN_PATH", token_path), \
                 patch.object(youtube_auth.Credentials, "from_authorized_user_file") as loader, \
                 patch.object(youtube_auth.InstalledAppFlow, "from_client_secrets_file", return_value=flow):
                youtube_auth.get_credentials(force_interactive=True)
            loader.assert_not_called()
            self.assertEqual(token_path.read_text(encoding="utf-8"), "new-token")
            self.assertEqual(token_path.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
