#!/usr/bin/env python3
"""Generate images from text with the MiniMax Image API."""

import argparse
import base64
import binascii
import json
import os
import sys
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

API_ENDPOINTS = {
    "global": "https://api.minimax.io/v1/image_generation",
    "china": "https://api.minimaxi.com/v1/image_generation",
}
SUPPORTED_MODELS = ("image-01", "image-01-live")
SUPPORTED_ASPECT_RATIOS = ("1:1", "16:9", "4:3", "3:2", "2:3", "3:4", "9:16", "21:9")
DOWNLOAD_TIMEOUT_SECONDS = 60
MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024


def positive_int(value):
    """Parse a positive integer for argparse."""
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def image_count(value):
    """Parse the API's supported image count range."""
    parsed = positive_int(value)
    if parsed > 9:
        raise argparse.ArgumentTypeError("must be between 1 and 9")
    return parsed


def image_dimension(value):
    """Parse an image dimension accepted by the API."""
    parsed = positive_int(value)
    if parsed < 512 or parsed > 2048 or parsed % 8:
        raise argparse.ArgumentTypeError(
            "must be between 512 and 2048 and divisible by 8"
        )
    return parsed


def build_parser():
    parser = argparse.ArgumentParser(
        description="Generate images from text with the MiniMax Image API"
    )
    parser.add_argument("--prompt", required=True, help="Text prompt for image generation")
    parser.add_argument(
        "--output",
        default=None,
        help="Output filename (default: minimax-image-<UUID>.png)",
    )
    parser.add_argument(
        "--model",
        choices=SUPPORTED_MODELS,
        default="image-01",
        help="Image model (default: image-01)",
    )
    parser.add_argument(
        "--region",
        choices=tuple(API_ENDPOINTS),
        default="global",
        help="API region (default: global)",
    )
    parser.add_argument(
        "--aspect-ratio",
        choices=SUPPORTED_ASPECT_RATIOS,
        default=None,
        help="Requested aspect ratio",
    )
    parser.add_argument("--width", type=image_dimension, default=None, help="Requested width")
    parser.add_argument("--height", type=image_dimension, default=None, help="Requested height")
    parser.add_argument("--seed", type=int, default=None, help="Generation seed")
    parser.add_argument("--n", type=image_count, default=1, help="Number of images")
    parser.add_argument(
        "--response-format",
        choices=("url", "base64"),
        default="url",
        help="API response format (default: url)",
    )
    parser.add_argument(
        "--disable-prompt-optimizer",
        action="store_true",
        help="Disable prompt optimization",
    )
    return parser


def parse_args(argv=None):
    args = build_parser().parse_args(argv)
    args.prompt = args.prompt.strip()
    if not args.prompt:
        build_parser().error("--prompt must not be empty")
    if len(args.prompt) > 1500:
        build_parser().error("--prompt must not exceed 1500 characters")
    if (args.width is None) != (args.height is None):
        build_parser().error("--width and --height must be provided together")
    args.output = args.output or f"minimax-image-{uuid.uuid4()}.png"
    output_path = Path(args.output).expanduser()
    if output_path.name in {"", ".", ".."}:
        build_parser().error("--output must name a file")
    if output_path.is_dir():
        build_parser().error("--output must not be a directory")
    args.output = output_path
    return args


def build_payload(args):
    payload = {
        "model": args.model,
        "prompt": args.prompt,
        "response_format": args.response_format,
        "n": args.n,
        "prompt_optimizer": not args.disable_prompt_optimizer,
    }
    for field in ("aspect_ratio", "width", "height", "seed"):
        value = getattr(args, field)
        if value is not None:
            payload[field] = value
    return payload


def read_response(response):
    data = response.read(MAX_DOWNLOAD_BYTES + 1)
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise RuntimeError("API response exceeds the maximum allowed size")
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("MiniMax returned an invalid JSON response") from exc


def response_count(metadata, field):
    """Parse a non-negative image count from response metadata."""
    value = metadata.get(field)
    if isinstance(value, bool):
        raise TypeError(f"MiniMax response contained an invalid {field}")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"MiniMax response contained an invalid {field}") from exc
    if parsed < 0:
        raise RuntimeError(f"MiniMax response contained an invalid {field}")
    return parsed


def request_generation(args, api_key, opener=urlopen):
    request = Request(
        API_ENDPOINTS[args.region],
        data=json.dumps(build_payload(args)).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with opener(request, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
            payload = read_response(response)
    except HTTPError as exc:
        raise RuntimeError(f"MiniMax request failed with HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"MiniMax request failed: {exc.reason}") from exc

    base_response = payload.get("base_resp")
    if isinstance(base_response, dict):
        status_code = base_response.get("status_code")
        if status_code not in (None, 0):
            message = base_response.get("status_msg") or "unknown API error"
            raise RuntimeError(f"MiniMax request failed: {message}")

    data = payload.get("data")
    image_values = data.get("image_urls") if isinstance(data, dict) else None
    if not isinstance(image_values, list) or not image_values:
        raise RuntimeError("MiniMax response did not contain any images")
    if not all(isinstance(value, str) and value for value in image_values):
        raise RuntimeError("MiniMax response contained an invalid image value")

    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        raise TypeError("MiniMax response did not contain image metadata")
    success_count = response_count(metadata, "success_count")
    response_count(metadata, "failed_count")
    if success_count != len(image_values):
        raise RuntimeError("MiniMax response image count did not match metadata")
    return image_values


def output_path_for_result(output_path, index, multiple):
    if multiple:
        return output_path.with_name(
            f"{output_path.stem}_{index + 1}{output_path.suffix}"
        )
    return output_path


def read_limited(response):
    data = response.read(MAX_DOWNLOAD_BYTES + 1)
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise RuntimeError("Downloaded image exceeds the maximum allowed size")
    if not data:
        raise RuntimeError("Downloaded image is empty")
    return data


def download_image(url, opener=urlopen):
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError("MiniMax returned an invalid image URL")
    request = Request(url, headers={"Accept": "image/*"})
    try:
        with opener(request, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
            return read_limited(response)
    except HTTPError as exc:
        raise RuntimeError(f"Image download failed with HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"Image download failed: {exc.reason}") from exc


def decode_image(value):
    encoded = value.split(",", 1)[1] if value.startswith("data:") and "," in value else value
    try:
        data = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise RuntimeError("MiniMax returned invalid base64 image data") from exc
    if not data:
        raise RuntimeError("MiniMax returned empty base64 image data")
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise RuntimeError("Decoded image exceeds the maximum allowed size")
    return data


def save_images(image_values, output_path, response_format, opener=urlopen):
    output_path = Path(output_path)
    saved_paths = []
    multiple = len(image_values) > 1
    for index, value in enumerate(image_values):
        target = output_path_for_result(output_path, index, multiple)
        image_data = (
            download_image(value, opener=opener)
            if response_format == "url"
            else decode_image(value)
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(image_data)
        saved_paths.append(str(target))
    return saved_paths


def run(args, api_key=None, api_opener=urlopen, download_opener=urlopen):
    active_api_key = api_key or os.getenv("MINIMAX_API_KEY")
    if not active_api_key:
        raise RuntimeError("MINIMAX_API_KEY is required")
    image_values = request_generation(args, active_api_key, opener=api_opener)
    saved_paths = save_images(
        image_values,
        args.output,
        args.response_format,
        opener=download_opener,
    )
    for saved_path in saved_paths:
        print(f"Image saved to: {saved_path}")
    return saved_paths


def main(argv=None):
    try:
        return 0 if run(parse_args(argv)) else 1
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
