import unittest
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from generator.run_daily import allocate_short_counts
from generator.visual_media import _license_ok
from generator.visual_media import _person_title_matches
from generator.visual_media import _basketball_context_matches
from generator.captions import caption_display_text, text_to_caption_chunks
from generator.pronunciation import for_speech
from generator import upload_youtube
from generator.generate_scripts import GENERATE_PROMPT_TEMPLATE, GENERATE_SCHEMA, _normalize_display_names


class PipelineTests(unittest.TestCase):
    def test_audience_improvement_rules_are_part_of_generation_prompt(self):
        self.assertEqual(GENERATE_SCHEMA["properties"]["long_sections"]["minItems"], 4)
        self.assertEqual(GENERATE_SCHEMA["properties"]["long_sections"]["maxItems"], 5)
        self.assertIn("長尺動画（3〜5分）", GENERATE_PROMPT_TEMPLATE)
        self.assertIn("hookは必ず主役の選手名から始め", GENERATE_PROMPT_TEMPLATE)
        self.assertIn("各Shorts内で完結", GENERATE_PROMPT_TEMPLATE)
        self.assertIn("長尺への誘導は必須ではなく", GENERATE_PROMPT_TEMPLATE)

    def test_reading_hints_never_leak_into_visible_text(self):
        fixed = _normalize_display_names({"title": "かわむら ゆうきと、はちむら るい"})
        self.assertEqual(fixed["title"], "河村勇輝と、八村塁")

    def test_short_allocation(self):
        self.assertEqual(allocate_short_counts(2, 3), [1, 2])
        self.assertEqual(allocate_short_counts(1, 2), [2])
        self.assertEqual(allocate_short_counts(2, 0), [0, 0])

    def test_asset_license_allowlist(self):
        allowed = {"LicenseShortName": {"value": "CC BY-SA 4.0"}}
        rejected = {"LicenseShortName": {"value": "CC BY-NC 4.0"}}
        self.assertTrue(_license_ok(allowed))
        self.assertFalse(_license_ok(rejected))

    def test_player_photo_search_rejects_unrelated_people(self):
        self.assertTrue(_person_title_matches("Yuki Kawamura", "File:Yuki_Kawamura.jpg"))
        self.assertFalse(_person_title_matches("Yuki Kawamura", "Australia_vs_Japan_World_Cup.jpg"))
        self.assertFalse(_person_title_matches("Yuki Kawamura", "Takumu_Kawamura_2024.jpg"))

    def test_other_sports_are_rejected_from_nba_visuals(self):
        self.assertFalse(_basketball_context_matches("Yuki Kawamura", "Japan football World Cup.jpg"))
        self.assertTrue(_basketball_context_matches("Yuki Kawamura", "Yuki Kawamura basketball.jpg"))

    def test_caption_breaks_preserve_words_and_particles(self):
        chunks = text_to_caption_chunks("河村勇輝がクリッパーズを選んだ理由とは何なのか。", max_len=14)
        self.assertEqual("".join(chunks), "河村勇輝がクリッパーズを選んだ理由とは何なのか。")
        self.assertFalse(any(chunk.endswith(("理", "私", "選", "見")) for chunk in chunks))
        self.assertFalse(any(chunk.startswith(("由", "は", "んだ", "えて")) for chunk in chunks))
        display = caption_display_text("選んだ理由とは何なのか。", max_line_len=8)
        self.assertNotIn("理\n由", display)
        team = caption_display_text("ロサンゼルス・クリッパーズと契約", max_line_len=14)
        self.assertNotIn("クリッ\nパーズ", team)
        exhibit = caption_display_text("エキシビット１０契約で競争に挑む", max_line_len=8)
        self.assertNotIn("エキシビット\n１０契約", exhibit)
        self.assertNotIn("競\n争", exhibit)

    def test_pronunciation_dictionary_keeps_given_name_boundary(self):
        self.assertIn("かわむら ゆうき", for_speech("河村勇輝の理由"))

    def test_uploads_are_scheduled_for_six_jst(self):
        with patch.dict(os.environ, {"TZ": "Asia/Tokyo", "YOUTUBE_SCHEDULE_PUBLIC_HOUR": "6"}):
            value = upload_youtube._scheduled_publish_at()
        target = datetime.fromisoformat(value.replace("Z", "+00:00"))
        self.assertEqual(target.hour, 21)  # 06:00 JST is 21:00 UTC on the previous day.
        self.assertGreater(target, datetime.now(timezone.utc))

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
