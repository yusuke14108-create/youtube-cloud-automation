import json
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import generator.youtube_auth as auth


class YouTubeReauthorizeTests(unittest.TestCase):
    def test_reauthorize_ignores_old_token_and_atomically_replaces_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            token = Path(tmp) / "token.json"
            secret = Path(tmp) / "client_secret.json"
            token.write_text("old-token", encoding="utf-8")
            secret.write_text("{}", encoding="utf-8")
            creds = Mock(valid=True, expired=False, refresh_token="refresh")
            creds.to_json.return_value = json.dumps({"token": "new-token"})
            flow = Mock()
            flow.run_local_server.return_value = creds

            with patch.object(auth, "TOKEN_PATH", token), patch.object(auth, "CLIENT_SECRET_PATH", secret), \
                    patch.object(auth.Credentials, "from_authorized_user_file") as load_old, \
                    patch.object(auth.InstalledAppFlow, "from_client_secrets_file", return_value=flow):
                result = auth.get_credentials(reauthorize=True)

            self.assertIs(result, creds)
            load_old.assert_not_called()
            self.assertEqual(json.loads(token.read_text(encoding="utf-8"))["token"], "new-token")
            self.assertEqual(stat.S_IMODE(token.stat().st_mode), 0o600)
            self.assertEqual(list(token.parent.glob(".token.json.*.tmp")), [])

    def test_failed_reauthorization_preserves_old_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            token = Path(tmp) / "token.json"
            secret = Path(tmp) / "client_secret.json"
            token.write_text("old-token", encoding="utf-8")
            secret.write_text("{}", encoding="utf-8")
            flow = Mock()
            flow.run_local_server.side_effect = RuntimeError("consent cancelled")

            with patch.object(auth, "TOKEN_PATH", token), patch.object(auth, "CLIENT_SECRET_PATH", secret), \
                    patch.object(auth.Credentials, "from_authorized_user_file") as load_old, \
                    patch.object(auth.InstalledAppFlow, "from_client_secrets_file", return_value=flow):
                with self.assertRaisesRegex(RuntimeError, "consent cancelled"):
                    auth.get_credentials(reauthorize=True)

            load_old.assert_not_called()
            self.assertEqual(token.read_text(encoding="utf-8"), "old-token")


if __name__ == "__main__":
    unittest.main()
