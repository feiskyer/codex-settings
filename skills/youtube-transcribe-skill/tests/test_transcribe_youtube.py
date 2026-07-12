import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock


SKILL_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = SKILL_DIR / "scripts" / "transcribe_youtube.py"
SPEC = importlib.util.spec_from_file_location("transcribe_youtube", MODULE_PATH)
transcribe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(transcribe)


SAMPLE_VTT = """WEBVTT

00:00:01.000 --> 00:00:03.000
<c>Hello</c> world

00:00:04.500 --> 00:00:06.000 align:start position:0%
Second &amp; final line
"""


class UrlTests(unittest.TestCase):
    def test_supported_youtube_url_shapes(self):
        urls = [
            "https://www.youtube.com/watch?v=abc123XYZ_-",
            "https://youtu.be/abc123XYZ_-",
            "https://youtube.com/shorts/abc123XYZ_-",
            "https://youtube.com/live/abc123XYZ_-",
            "https://www.youtube-nocookie.com/embed/abc123XYZ_-",
        ]

        for url in urls:
            with self.subTest(url=url):
                self.assertTrue(transcribe.is_youtube_url(url))

        self.assertFalse(transcribe.is_youtube_url("https://example.com/video"))


class ParserTests(unittest.TestCase):
    def test_vtt_is_normalized_to_timestamped_text(self):
        self.assertEqual(
            transcribe.parse_vtt(SAMPLE_VTT),
            ["00:01 Hello world", "00:04 Second & final line"],
        )

    def test_command_uses_cookies_only_when_explicit(self):
        args = transcribe.parse_args(["https://youtu.be/abc123XYZ_-"])
        command = transcribe.build_yt_dlp_command(args, "yt-dlp", "/tmp/work")
        self.assertNotIn("--cookies-from-browser", command)

        args.cookies_from_browser = "chrome"
        command = transcribe.build_yt_dlp_command(args, "yt-dlp", "/tmp/work")
        cookie_index = command.index("--cookies-from-browser")
        self.assertEqual(command[cookie_index + 1], "chrome")


class RunTests(unittest.TestCase):
    def test_run_converts_downloaded_vtt_to_txt(self):
        def fake_run(command, **_kwargs):
            template = Path(command[command.index("--output") + 1])
            work_dir = template.parent
            (work_dir / "abc123XYZ_-.info.json").write_text(
                json.dumps({"id": "abc123XYZ_-", "title": "Sample / Video"}),
                encoding="utf-8",
            )
            (work_dir / "abc123XYZ_-.en.vtt").write_text(
                SAMPLE_VTT,
                encoding="utf-8",
            )
            return SimpleNamespace(returncode=0, stdout="")

        with tempfile.TemporaryDirectory() as temp_dir:
            args = transcribe.parse_args(
                [
                    "https://youtu.be/abc123XYZ_-",
                    "--languages",
                    "en.*",
                    "--output-dir",
                    temp_dir,
                ]
            )
            with mock.patch.object(
                transcribe,
                "resolve_executable",
                return_value="/usr/local/bin/yt-dlp",
            ):
                with mock.patch.object(
                    transcribe.subprocess,
                    "run",
                    side_effect=fake_run,
                ):
                    result = transcribe.run(args)

            output_path = Path(result["path"])
            self.assertEqual(output_path.name, "Sample _ Video.txt")
            self.assertEqual(result["language"], "en")
            self.assertEqual(result["lines"], 2)
            self.assertFalse(result["cookies_used"])
            self.assertEqual(
                output_path.read_text(encoding="utf-8"),
                "00:01 Hello world\n00:04 Second & final line\n",
            )

    def test_missing_subtitles_is_an_error(self):
        def fake_run(command, **_kwargs):
            template = Path(command[command.index("--output") + 1])
            (template.parent / "abc123XYZ_-.info.json").write_text(
                json.dumps({"id": "abc123XYZ_-", "title": "Sample"}),
                encoding="utf-8",
            )
            return SimpleNamespace(returncode=0, stdout="")

        args = transcribe.parse_args(["https://youtu.be/abc123XYZ_-"])
        with mock.patch.object(
            transcribe,
            "resolve_executable",
            return_value="yt-dlp",
        ):
            with mock.patch.object(
                transcribe.subprocess,
                "run",
                side_effect=fake_run,
            ):
                with self.assertRaisesRegex(RuntimeError, "No matching subtitles"):
                    transcribe.run(args)


if __name__ == "__main__":
    unittest.main()
