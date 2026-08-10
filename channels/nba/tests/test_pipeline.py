import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from generator.run_daily import allocate_short_counts
from generator.visual_media import _license_ok
from generator import upload_youtube


class PipelineTests(unittest.TestCase):
    def test_short_allocation(self):
        self.assertEqual(allocate_short_counts(2, 3), [1, 2])
        self.assertEqual(allocate_short_counts(1, 2), [2])
        self.assertEqual(allocate_short_counts(2, 0), [0, 0])

    def test_asset_license_allowlist(self):
        allowed = {"LicenseShortName": {"value": "CC BY-SA 4.0"}}
        rejected = {"LicenseShortName": {"value": "CC BY-NC 4.0"}}
        self.assertTrue(_license_ok(allowed))
        self.assertFalse(_license_ok(rejected))

    def test_upload_resume_reuses_completed_long_video(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            script_path = root / "20260810_test.json"
            video_dir = root / "video" / script_path.stem
            video_dir.mkdir(parents=True)
            (video_dir / "long.mp4").write_bytes(b"long")
            (video_dir / "short_1.mp4").write_bytes(b"short")
            script_path.write_text(json.dumps({
                "title": "test", "thumbnail_text": "test", "thumbnail_image_query": "", "summary": "test",
                "source_item": {"source": "nba_news", "title": "source", "url": "https://example.invalid"},
                "short_scripts": [{"hook": "hook", "script": "script", "image_query": ""}],
            }), encoding="utf-8")
            progress = root / "progress"
            uploads = root / "uploads"

            def fake_thumbnail(*args, **kwargs):
                args[3].write_bytes(b"png")

            with patch.object(upload_youtube, "VIDEO_DIR", root / "video"), \
                 patch.object(upload_youtube, "UPLOAD_PROGRESS_DIR", progress), \
                 patch.object(upload_youtube, "UPLOADS_DIR", uploads), \
                 patch.object(upload_youtube, "_youtube_client", return_value=object()), \
                 patch.object(upload_youtube, "make_thumbnail", side_effect=fake_thumbnail), \
                 patch.object(upload_youtube, "upload_video", side_effect=["long-id", RuntimeError("short failed")]):
                with self.assertRaises(RuntimeError):
                    upload_youtube.main(script_path)

            saved = json.loads((progress / f"{script_path.stem}.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["long"], "long-id")

            with patch.object(upload_youtube, "VIDEO_DIR", root / "video"), \
                 patch.object(upload_youtube, "UPLOAD_PROGRESS_DIR", progress), \
                 patch.object(upload_youtube, "UPLOADS_DIR", uploads), \
                 patch.object(upload_youtube, "_youtube_client", return_value=object()), \
                 patch.object(upload_youtube, "make_thumbnail", side_effect=fake_thumbnail), \
                 patch.object(upload_youtube, "upload_video", return_value="short-id") as uploader:
                result = upload_youtube.main(script_path)
            self.assertEqual(result, {"long": "long-id", "shorts": ["short-id"]})
            self.assertEqual(uploader.call_count, 1)


if __name__ == "__main__":
    unittest.main()
