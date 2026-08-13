import base64
import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = SKILL_DIR / "minimax_image.py"
SPEC = importlib.util.spec_from_file_location("minimax_image", MODULE_PATH)
minimax_image = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(minimax_image)


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, size=-1):
        return self.body[:size] if size >= 0 else self.body


class RecordingOpener:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, request, timeout):
        self.calls.append((request, timeout))
        return FakeResponse(self.responses.pop(0))


class MiniMaxImageTests(unittest.TestCase):
    def test_global_request_uses_configured_contract(self):
        opener = RecordingOpener(
            [
                json.dumps(
                    {
                        "data": {"image_urls": ["aW1hZ2U="]},
                        "metadata": {"success_count": "1", "failed_count": "0"},
                        "base_resp": {"status_code": 0},
                    }
                ).encode()
            ]
        )
        args = minimax_image.parse_args(
            [
                "--prompt",
                "A quiet observatory",
                "--model",
                "image-01-live",
                "--aspect-ratio",
                "16:9",
                "--response-format",
                "base64",
            ]
        )

        values = minimax_image.request_generation(args, "test-key", opener=opener)

        request = opener.calls[0][0]
        payload = json.loads(request.data)
        self.assertEqual(request.full_url, "https://api.minimax.io/v1/image_generation")
        self.assertEqual(request.headers["Authorization"], "Bearer test-key")
        self.assertEqual(payload["model"], "image-01-live")
        self.assertEqual(payload["prompt"], "A quiet observatory")
        self.assertEqual(payload["aspect_ratio"], "16:9")
        self.assertEqual(payload["response_format"], "base64")
        self.assertEqual(values, ["aW1hZ2U="])

    def test_dimensions_seed_and_optimizer_are_forwarded(self):
        opener = RecordingOpener(
            [
                json.dumps(
                    {
                        "data": {"image_urls": ["aW1hZ2U="]},
                        "metadata": {"success_count": 1, "failed_count": 0},
                        "base_resp": {"status_code": 0},
                    }
                ).encode()
            ]
        )
        args = minimax_image.parse_args(
            [
                "--prompt",
                "A geometric garden",
                "--width",
                "1024",
                "--height",
                "768",
                "--seed",
                "42",
                "--disable-prompt-optimizer",
                "--response-format",
                "base64",
            ]
        )

        minimax_image.request_generation(args, "test-key", opener=opener)

        payload = json.loads(opener.calls[0][0].data)
        self.assertEqual(payload["width"], 1024)
        self.assertEqual(payload["height"], 768)
        self.assertEqual(payload["seed"], 42)
        self.assertFalse(payload["prompt_optimizer"])

    def test_invalid_paid_request_inputs_are_rejected_locally(self):
        invalid_arguments = [
            ["--prompt", "x" * 1501],
            ["--prompt", "test", "--n", "10"],
            ["--prompt", "test", "--width", "513", "--height", "512"],
        ]
        for arguments in invalid_arguments:
            with (
                self.subTest(arguments=arguments),
                redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit),
            ):
                minimax_image.parse_args(arguments)

    def test_china_request_and_base64_response_are_saved(self):
        api_opener = RecordingOpener(
            [
                json.dumps(
                    {
                        "data": {
                            "image_urls": [
                                base64.b64encode(b"first-image").decode(),
                                base64.b64encode(b"second-image").decode(),
                            ]
                        },
                        "metadata": {"success_count": 2, "failed_count": 0},
                        "base_resp": {"status_code": 0},
                    }
                ).encode()
            ]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "nested" / "result.png"
            args = minimax_image.parse_args(
                [
                    "--region",
                    "china",
                    "--prompt",
                    "A paper-cut landscape",
                    "--response-format",
                    "base64",
                    "--n",
                    "2",
                    "--output",
                    str(output),
                ]
            )

            saved = minimax_image.run(
                args,
                api_key="test-key",
                api_opener=api_opener,
            )

            self.assertEqual(
                api_opener.calls[0][0].full_url,
                "https://api.minimaxi.com/v1/image_generation",
            )
            self.assertEqual(Path(saved[0]).read_bytes(), b"first-image")
            self.assertEqual(Path(saved[1]).read_bytes(), b"second-image")

    def test_url_response_is_downloaded(self):
        downloader = RecordingOpener([b"downloaded-image"])
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "result.png"

            saved = minimax_image.save_images(
                ["https://cdn.example/result.png"],
                output,
                "url",
                opener=downloader,
            )

            self.assertEqual(saved, [str(output)])
            self.assertEqual(output.read_bytes(), b"downloaded-image")

    def test_api_error_is_reported(self):
        opener = RecordingOpener(
            [
                json.dumps(
                    {"base_resp": {"status_code": 1001, "status_msg": "invalid request"}}
                ).encode()
            ]
        )
        args = minimax_image.parse_args(["--prompt", "A lighthouse"])

        with self.assertRaisesRegex(RuntimeError, "invalid request"):
            minimax_image.request_generation(args, "test-key", opener=opener)

    def test_response_metadata_must_match_returned_images(self):
        opener = RecordingOpener(
            [
                json.dumps(
                    {
                        "data": {"image_urls": ["aW1hZ2U="]},
                        "metadata": {"success_count": 0, "failed_count": 1},
                        "base_resp": {"status_code": 0},
                    }
                ).encode()
            ]
        )
        args = minimax_image.parse_args(
            ["--prompt", "A lighthouse", "--response-format", "base64"]
        )

        with self.assertRaisesRegex(RuntimeError, "did not match metadata"):
            minimax_image.request_generation(args, "test-key", opener=opener)


if __name__ == "__main__":
    unittest.main()
