#!/usr/bin/env python3
"""Generate or edit images using the OpenAI GPT Image API."""

import argparse
import base64
from contextlib import ExitStack
import os
from pathlib import Path
import sys
import uuid

from dotenv import load_dotenv
import httpx
from openai import OpenAI


DOWNLOAD_TIMEOUT_SECONDS = 60.0
MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024
FORMAT_SUFFIXES = {
    "png": {".png"},
    "jpeg": {".jpg", ".jpeg"},
    "webp": {".webp"},
}
PREFERRED_SUFFIXES = {
    "png": ".png",
    "jpeg": ".jpg",
    "webp": ".webp",
}

def get_client():
    """Initialize the OpenAI client with an optional custom base URL."""
    load_dotenv(Path.home() / ".gpt-image.env")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is required. Set it in ~/.gpt-image.env or export it."
        )

    kwargs = {"api_key": api_key}
    base_url = os.getenv("OPENAI_API_BASE")
    if base_url:
        kwargs["base_url"] = base_url

    return OpenAI(**kwargs)


def positive_int(value):
    """Parse a positive integer for argparse."""
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def add_common_args(parser):
    parser.add_argument(
        "--prompt",
        required=True,
        help="Text prompt for generation or editing",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output filename (default: auto-generated PNG)",
    )
    parser.add_argument(
        "--model",
        default="gpt-image-2",
        help="Model to use (default: gpt-image-2)",
    )
    parser.add_argument(
        "--size",
        default="1024x1024",
        choices=["1024x1024", "1024x1536", "1536x1024", "auto"],
        help="Image size (default: 1024x1024)",
    )
    parser.add_argument(
        "--quality",
        default="auto",
        choices=["auto", "high", "medium", "low"],
        help="Image quality (default: auto)",
    )
    parser.add_argument(
        "--n",
        type=positive_int,
        default=1,
        help="Number of images to generate (default: 1)",
    )
    parser.add_argument(
        "--format",
        choices=["png", "jpeg", "webp"],
        default=None,
        help="Output format (default: inferred from --output, otherwise png)",
    )
    parser.add_argument(
        "--background",
        choices=["auto", "transparent", "opaque"],
        default=None,
        help="Background type (default: auto)",
    )


def build_parser():
    """Build a parser with explicit generate and edit modes."""
    parser = argparse.ArgumentParser(
        prog="gpt_image.py",
        description="Generate or edit images using the OpenAI GPT Image API"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser(
        "generate",
        help="Generate image(s) from a text prompt",
    )
    add_common_args(generate_parser)

    edit_parser = subparsers.add_parser("edit", help="Edit existing images")
    add_common_args(edit_parser)
    edit_parser.add_argument(
        "--input",
        nargs="+",
        required=True,
        help="Input image file(s) for editing",
    )
    return parser


def infer_output_format(output_path):
    """Infer the API output format from a supported filename suffix."""
    suffix = output_path.suffix.lower()
    for output_format, suffixes in FORMAT_SUFFIXES.items():
        if suffix in suffixes:
            return output_format
    return None


def normalize_output(output, requested_format):
    """Return a normalized output path and matching API output format."""
    output_format = requested_format or "png"
    if output is None:
        suffix = PREFERRED_SUFFIXES[output_format]
        return Path(f"gpt-image-{uuid.uuid4()}{suffix}"), output_format

    output_path = Path(output).expanduser()
    if output_path.name in {"", ".", ".."}:
        raise ValueError("--output must name a file, not a directory")

    inferred_format = infer_output_format(output_path)
    if requested_format:
        if output_path.suffix and output_path.suffix.lower() not in FORMAT_SUFFIXES[requested_format]:
            expected = ", ".join(sorted(FORMAT_SUFFIXES[requested_format]))
            raise ValueError(
                f"--output extension must match --format {requested_format} ({expected})"
            )
        if not output_path.suffix:
            output_path = output_path.with_suffix(PREFERRED_SUFFIXES[requested_format])
        return output_path, requested_format

    if inferred_format:
        return output_path, inferred_format
    if output_path.suffix:
        raise ValueError(
            "unsupported --output extension; use .png, .jpg/.jpeg, or .webp"
        )
    return output_path.with_suffix(".png"), "png"


def parse_args(argv=None):
    """Parse arguments while preserving the legacy generation command shape."""
    raw_args = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()

    # Keep `gpt_image.py --prompt ...` working while exposing explicit modes.
    if raw_args and raw_args[0] not in {"generate", "edit", "-h", "--help"}:
        raw_args.insert(0, "generate")
    elif not raw_args:
        raw_args.append("generate")

    args = parser.parse_args(raw_args)
    try:
        output_path, output_format = normalize_output(args.output, args.format)
    except ValueError as exc:
        parser.error(str(exc))

    if args.background == "transparent" and output_format == "jpeg":
        parser.error("transparent backgrounds require png or webp output")

    args.output = str(output_path)
    args.format = output_format
    return args


def generate_image(client, args):
    """Generate image(s) from a text prompt."""
    print(f"Generating image with prompt: {args.prompt}")
    print(f"Model: {args.model} | Size: {args.size} | Quality: {args.quality}")

    params = {
        "model": args.model,
        "prompt": args.prompt,
        "n": args.n,
        "size": args.size,
        "quality": args.quality,
        "output_format": args.format,
    }
    if args.background:
        params["background"] = args.background

    response = client.images.generate(**params)
    return save_results(response, args)


def edit_image(client, args):
    """Edit image(s) using a prompt and reference images."""
    input_paths = [Path(path).expanduser() for path in args.input]
    missing_paths = [str(path) for path in input_paths if not path.is_file()]
    if missing_paths:
        raise FileNotFoundError(f"Input file not found: {missing_paths[0]}")

    print(f"Editing images with prompt: {args.prompt}")
    print(f"Input images: {[str(path) for path in input_paths]}")

    with ExitStack() as stack:
        image_files = [stack.enter_context(path.open("rb")) for path in input_paths]
        params = {
            "model": args.model,
            "image": image_files if len(image_files) > 1 else image_files[0],
            "prompt": args.prompt,
            "n": args.n,
            "size": args.size,
            "quality": args.quality,
            "output_format": args.format,
        }
        if args.background:
            params["background"] = args.background

        response = client.images.edit(**params)
        return save_results(response, args)


def output_path_for_result(output, index, multiple):
    """Return the output path for one API result."""
    output_path = Path(output)
    if multiple:
        output_path = output_path.with_name(
            f"{output_path.stem}_{index + 1}{output_path.suffix}"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path


def download_image(url, output_path):
    """Download an image response with timeout, status, and size checks."""
    try:
        with httpx.stream(
            "GET",
            url,
            follow_redirects=True,
            timeout=DOWNLOAD_TIMEOUT_SECONDS,
        ) as response:
            response.raise_for_status()
            total_bytes = 0
            with output_path.open("wb") as output_file:
                for chunk in response.iter_bytes():
                    total_bytes += len(chunk)
                    if total_bytes > MAX_DOWNLOAD_BYTES:
                        raise RuntimeError(
                            f"Downloaded image exceeds {MAX_DOWNLOAD_BYTES} bytes"
                        )
                    output_file.write(chunk)
            if total_bytes == 0:
                raise RuntimeError("Downloaded image is empty")
    except Exception:
        output_path.unlink(missing_ok=True)
        raise


def save_results(response, args):
    """Save generated or edited images to disk and return their paths."""
    if not response.data:
        raise RuntimeError("No image data received from the API")

    saved_paths = []
    multiple = len(response.data) > 1
    for index, image_data in enumerate(response.data):
        output_path = output_path_for_result(args.output, index, multiple)
        if getattr(image_data, "b64_json", None):
            image_bytes = base64.b64decode(image_data.b64_json, validate=True)
            if len(image_bytes) > MAX_DOWNLOAD_BYTES:
                raise RuntimeError(
                    f"Decoded image exceeds {MAX_DOWNLOAD_BYTES} bytes"
                )
            output_path.write_bytes(image_bytes)
        elif getattr(image_data, "url", None):
            download_image(image_data.url, output_path)
        else:
            print(
                f"Warning: No image content for result {index + 1}",
                file=sys.stderr,
            )
            continue

        saved_paths.append(str(output_path))
        print(f"Image saved to: {output_path}")

    if not saved_paths:
        raise RuntimeError("No image content was saved")

    revised_prompt = getattr(response.data[0], "revised_prompt", None)
    if revised_prompt:
        print(f"\nRevised prompt: {revised_prompt}")
    return saved_paths


def main(argv=None):
    try:
        args = parse_args(argv)
        client = get_client()
        if args.command == "edit":
            edit_image(client, args)
        else:
            generate_image(client, args)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
