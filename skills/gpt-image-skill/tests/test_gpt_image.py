import base64
from contextlib import redirect_stderr, redirect_stdout
import io
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock


SKILL_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = SKILL_DIR / "gpt_image.py"
SPEC = importlib.util.spec_from_file_location("gpt_image", MODULE_PATH)
gpt_image = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gpt_image)


def image_response(content=b"image-bytes"):
    return SimpleNamespace(
        data=[
            SimpleNamespace(
                b64_json=base64.b64encode(content).decode("ascii"),
                url=None,
                revised_prompt=None,
            )
        ]
    )


class FakeImages:
    def __init__(self, response):
        self.response = response
        self.edit_params = None

    def edit(self, **params):
        self.edit_params = params
        return self.response


class FakeClient:
    def __init__(self, response):
        self.images = FakeImages(response)


class ArgumentTests(unittest.TestCase):
    def test_legacy_generation_syntax_still_works(self):
        args = gpt_image.parse_args(["--prompt", "draw a cat"])

        self.assertEqual(args.command, "generate")
        self.assertEqual(args.prompt, "draw a cat")
        self.assertEqual(args.format, "png")
        self.assertTrue(args.output.endswith(".png"))

    def test_documented_edit_syntax_requires_prompt_only_once(self):
        args = gpt_image.parse_args(
            ["edit", "--prompt", "add a rainbow", "--input", "photo.png"]
        )

        self.assertEqual(args.command, "edit")
        self.assertEqual(args.prompt, "add a rainbow")
        self.assertEqual(args.input, ["photo.png"])

    def test_output_format_is_inferred_from_filename(self):
        args = gpt_image.parse_args(
            ["--prompt", "draw a cat", "--output", "cat.webp"]
        )

        self.assertEqual(args.format, "webp")

    def test_mismatched_output_extension_is_rejected(self):
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                gpt_image.parse_args(
                    [
                        "--prompt",
                        "draw a cat",
                        "--format",
                        "jpeg",
                        "--output",
                        "cat.png",
                    ]
                )


class EditTests(unittest.TestCase):
    def test_edit_passes_format_and_background_and_creates_parent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "input.png"
            input_path.write_bytes(b"input")
            output_path = root / "nested" / "edited.webp"
            args = gpt_image.parse_args(
                [
                    "edit",
                    "--prompt",
                    "replace the background",
                    "--input",
                    str(input_path),
                    "--format",
                    "webp",
                    "--background",
                    "transparent",
                    "--output",
                    str(output_path),
                ]
            )
            client = FakeClient(image_response())

            with redirect_stdout(io.StringIO()):
                saved_paths = gpt_image.edit_image(client, args)

            self.assertEqual(saved_paths, [str(output_path)])
            self.assertEqual(output_path.read_bytes(), b"image-bytes")
            self.assertEqual(client.images.edit_params["output_format"], "webp")
            self.assertEqual(client.images.edit_params["background"], "transparent")

    def test_missing_input_fails_before_api_call(self):
        args = gpt_image.parse_args(
            ["edit", "--prompt", "edit", "--input", "/missing/image.png"]
        )
        client = FakeClient(image_response())

        with self.assertRaises(FileNotFoundError):
            gpt_image.edit_image(client, args)

        self.assertIsNone(client.images.edit_params)


class SaveResultTests(unittest.TestCase):
    def test_no_image_content_is_an_error(self):
        response = SimpleNamespace(
            data=[SimpleNamespace(b64_json=None, url=None, revised_prompt=None)]
        )
        args = SimpleNamespace(output="unused.png")

        with redirect_stderr(io.StringIO()):
            with self.assertRaises(RuntimeError):
                gpt_image.save_results(response, args)


class DownloadTests(unittest.TestCase):
    def test_download_checks_status_and_writes_streamed_content(self):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.iter_bytes.return_value = [b"image-", b"bytes"]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "nested" / "image.png"
            output_path.parent.mkdir(parents=True)
            with mock.patch.object(
                gpt_image.httpx,
                "stream",
                return_value=response,
            ) as stream:
                gpt_image.download_image("https://example.test/image", output_path)

            response.raise_for_status.assert_called_once_with()
            self.assertEqual(output_path.read_bytes(), b"image-bytes")
            stream.assert_called_once_with(
                "GET",
                "https://example.test/image",
                follow_redirects=True,
                timeout=gpt_image.DOWNLOAD_TIMEOUT_SECONDS,
            )

    def test_oversized_download_removes_partial_file(self):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.iter_bytes.return_value = [b"abc", b"def"]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "image.png"
            with mock.patch.object(gpt_image, "MAX_DOWNLOAD_BYTES", 5):
                with mock.patch.object(
                    gpt_image.httpx,
                    "stream",
                    return_value=response,
                ):
                    with self.assertRaises(RuntimeError):
                        gpt_image.download_image(
                            "https://example.test/image",
                            output_path,
                        )

            self.assertFalse(output_path.exists())


if __name__ == "__main__":
    unittest.main()
