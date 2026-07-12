from contextlib import redirect_stderr, redirect_stdout
import io
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

from PIL import Image


SKILL_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = SKILL_DIR / "nanobanana.py"
SPEC = importlib.util.spec_from_file_location("nanobanana", MODULE_PATH)
nanobanana = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(nanobanana)


def image_bytes():
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), "red").save(buffer, format="PNG")
    return buffer.getvalue()


def response_with_parts(*parts):
    return SimpleNamespace(
        candidates=[
            SimpleNamespace(
                content=SimpleNamespace(parts=list(parts)),
            )
        ]
    )


class FakeModels:
    def __init__(self, response):
        self.response = response
        self.params = None

    def generate_content(self, **params):
        self.params = params
        return self.response


class FakeClient:
    def __init__(self, response):
        self.models = FakeModels(response)


class ArgumentTests(unittest.TestCase):
    def test_help_does_not_require_api_key(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    nanobanana.parse_args(["--help"])

        self.assertEqual(raised.exception.code, 0)

    def test_missing_api_key_is_reported_when_client_is_needed(self):
        with mock.patch.object(nanobanana, "load_dotenv"):
            with mock.patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(RuntimeError, "GEMINI_API_KEY"):
                    nanobanana.get_client()


class ExecutionTests(unittest.TestCase):
    def test_missing_input_fails_before_api_call(self):
        args = nanobanana.parse_args(
            ["--prompt", "edit", "--input", "/definitely/missing.png"]
        )
        client = FakeClient(response_with_parts())

        with self.assertRaises(FileNotFoundError):
            nanobanana.run(args, client=client)

        self.assertIsNone(client.models.params)

    def test_generation_saves_image_and_creates_parent(self):
        image_part = SimpleNamespace(
            inline_data=SimpleNamespace(data=image_bytes()),
            text=None,
            thought=False,
        )
        client = FakeClient(response_with_parts(image_part))

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "nested" / "image.png"
            args = nanobanana.parse_args(
                ["--prompt", "draw a cat", "--output", str(output_path)]
            )

            with redirect_stdout(io.StringIO()):
                saved_paths = nanobanana.run(args, client=client)

            self.assertEqual(saved_paths, [str(output_path.resolve())])
            self.assertTrue(output_path.is_file())
            self.assertEqual(client.models.params["model"], args.model)

    def test_text_only_response_is_a_failure_after_optional_outputs_are_saved(self):
        text_part = SimpleNamespace(
            inline_data=None,
            text="No image generated",
            thought=False,
        )
        client = FakeClient(response_with_parts(text_part))

        with tempfile.TemporaryDirectory() as temp_dir:
            metadata_path = Path(temp_dir) / "metadata.json"
            args = nanobanana.parse_args(
                [
                    "--prompt",
                    "draw a cat",
                    "--metadata-output",
                    str(metadata_path),
                ]
            )

            with redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(RuntimeError, "No image data"):
                    nanobanana.run(args, client=client)

            self.assertTrue(metadata_path.is_file())

    def test_main_returns_nonzero_for_runtime_errors(self):
        with mock.patch.object(
            nanobanana,
            "get_client",
            side_effect=RuntimeError("missing key"),
        ):
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                exit_code = nanobanana.main(["--prompt", "draw a cat"])

        self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
