import importlib.util
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

SKILL_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = SKILL_DIR / "atlas_image.py"
SPEC = importlib.util.spec_from_file_location("atlas_image", MODULE_PATH)
atlas_image = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(atlas_image)


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
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return FakeResponse(response)


def api_response(data, code=200, message=""):
    return json.dumps({"code": code, "message": message, "data": data}).encode()


class AtlasImageTests(unittest.TestCase):
    def test_submit_uses_live_contract_and_exactly_one_post(self):
        opener = RecordingOpener(
            [api_response({"id": "prediction-1", "status": "created"})]
        )
        args = atlas_image.parse_args(
            [
                "--prompt",
                "A geometric garden",
                "--aspect-ratio",
                "16:9",
                "--thinking-level",
                "high",
            ]
        )

        data = atlas_image.submit_generation(args, "test-key", opener=opener)

        self.assertEqual(data["id"], "prediction-1")
        self.assertEqual(len(opener.calls), 1)
        request = opener.calls[0][0]
        payload = json.loads(request.data)
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(
            request.full_url,
            "https://api.atlascloud.ai/api/v1/model/generateImage",
        )
        self.assertEqual(request.headers["Authorization"], "Bearer test-key")
        self.assertEqual(
            request.get_header("User-agent"),
            "codex-settings-atlas-image-skill/1.0",
        )
        self.assertEqual(
            payload["model"],
            "google/nano-banana-2-lite/text-to-image-developer",
        )
        self.assertEqual(payload["aspect_ratio"], "16:9")
        self.assertEqual(payload["thinking_level"], "high")
        self.assertFalse(payload["enable_sync_mode"])

    def test_run_polls_with_get_and_saves_first_output(self):
        api_opener = RecordingOpener(
            [
                api_response({"id": "prediction-2", "status": "created"}),
                api_response({"id": "prediction-2", "status": "processing"}),
                api_response(
                    {
                        "id": "prediction-2",
                        "status": "completed",
                        "outputs": ["https://cdn.example/result.png"],
                    }
                ),
            ]
        )
        downloader = RecordingOpener([b"generated-image"])
        clock = iter([0.0, 0.0, 0.1, 0.1])
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "nested" / "result.png"
            args = atlas_image.parse_args(
                ["--prompt", "A quiet observatory", "--output", str(output)]
            )

            saved = atlas_image.run(
                args,
                api_key="test-key",
                api_opener=api_opener,
                download_opener=downloader,
                sleep_fn=lambda _seconds: None,
                monotonic_fn=lambda: next(clock),
            )

            self.assertEqual(saved, str(output))
            self.assertEqual(output.read_bytes(), b"generated-image")
        methods = [call[0].get_method() for call in api_opener.calls]
        self.assertEqual(methods, ["POST", "GET", "GET"])

    def test_completed_submit_does_not_poll(self):
        api_opener = RecordingOpener(
            [
                api_response(
                    {
                        "id": "prediction-3",
                        "status": "completed",
                        "outputs": ["https://cdn.example/result.png"],
                    }
                )
            ]
        )
        downloader = RecordingOpener([b"generated-image"])
        with tempfile.TemporaryDirectory() as temp_dir:
            args = atlas_image.parse_args(
                [
                    "--prompt",
                    "A lighthouse",
                    "--output",
                    str(Path(temp_dir) / "result.png"),
                ]
            )
            atlas_image.run(
                args,
                api_key="test-key",
                api_opener=api_opener,
                download_opener=downloader,
            )
        self.assertEqual(len(api_opener.calls), 1)
        self.assertEqual(api_opener.calls[0][0].get_method(), "POST")

    def test_transient_get_is_retried_but_post_is_not(self):
        error = HTTPError("https://example", 503, "Unavailable", {}, None)
        opener = RecordingOpener(
            [
                error,
                api_response(
                    {
                        "id": "prediction-4",
                        "status": "completed",
                        "outputs": ["https://cdn.example/result.png"],
                    }
                ),
            ]
        )
        sleeps = []

        data = atlas_image.request_prediction(
            "https://api.atlascloud.ai",
            "prediction-4",
            "test-key",
            opener=opener,
            sleep_fn=sleeps.append,
        )

        self.assertEqual(data["status"], "completed")
        self.assertEqual(len(opener.calls), 2)
        self.assertEqual(sleeps, [1])
        self.assertEqual(
            opener.calls[0][0].get_header("User-agent"),
            "codex-settings-atlas-image-skill/1.0",
        )

    def test_invalid_paid_inputs_are_rejected_locally(self):
        invalid_arguments = [
            ["--prompt", "   "],
            ["--prompt", "test", "--api-base", "http://api.example"],
            ["--prompt", "test", "--timeout", "0"],
        ]
        for arguments in invalid_arguments:
            with (
                self.subTest(arguments=arguments),
                redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit),
            ):
                atlas_image.parse_args(arguments)

    def test_failed_prediction_reports_api_error(self):
        args = atlas_image.parse_args(["--prompt", "A lighthouse"])
        with self.assertRaisesRegex(RuntimeError, "content policy"):
            atlas_image.wait_for_outputs(
                {
                    "id": "prediction-5",
                    "status": "failed",
                    "error": "content policy",
                },
                args,
                "test-key",
            )

    def test_polling_timeout_is_bounded(self):
        args = atlas_image.parse_args(
            ["--prompt", "A lighthouse", "--timeout", "1"]
        )
        clock = iter([0.0, 1.0])
        with self.assertRaisesRegex(RuntimeError, "timed out"):
            atlas_image.wait_for_outputs(
                {"id": "prediction-6", "status": "created"},
                args,
                "test-key",
                monotonic_fn=lambda: next(clock),
            )

    def test_compatibility_api_key_is_used(self):
        api_opener = RecordingOpener(
            [
                api_response(
                    {
                        "id": "prediction-7",
                        "status": "completed",
                        "outputs": ["https://cdn.example/result.png"],
                    }
                )
            ]
        )
        downloader = RecordingOpener([b"generated-image"])
        with tempfile.TemporaryDirectory() as temp_dir:
            args = atlas_image.parse_args(
                [
                    "--prompt",
                    "A lighthouse",
                    "--output",
                    str(Path(temp_dir) / "result.png"),
                ]
            )
            with patch.dict(
                os.environ,
                {"ATLAS_CLOUD_API_KEY": "compat-key"},
                clear=True,
            ):
                atlas_image.run(
                    args,
                    api_opener=api_opener,
                    download_opener=downloader,
                )
        self.assertEqual(
            api_opener.calls[0][0].headers["Authorization"],
            "Bearer compat-key",
        )


if __name__ == "__main__":
    unittest.main()
