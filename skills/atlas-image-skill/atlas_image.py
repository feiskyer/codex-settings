#!/usr/bin/env python3
"""Generate images from text with the Atlas Cloud API."""

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

DEFAULT_API_BASE = "https://api.atlascloud.ai"
DEFAULT_MODEL = "google/nano-banana-2-lite/text-to-image-developer"
USER_AGENT = "codex-settings-atlas-image-skill/1.0"
SUPPORTED_ASPECT_RATIOS = (
    "auto",
    "1:1",
    "3:2",
    "2:3",
    "3:4",
    "4:3",
    "4:5",
    "5:4",
    "9:16",
    "16:9",
    "21:9",
    "4:1",
    "1:4",
    "8:1",
    "1:8",
)
SUPPORTED_THINKING_LEVELS = ("default", "high", "minimal")
PENDING_STATUSES = {"created", "starting", "processing"}
REQUEST_TIMEOUT_SECONDS = 60
DEFAULT_POLL_INTERVAL_SECONDS = 2.0
DEFAULT_POLL_TIMEOUT_SECONDS = 300.0
MAX_JSON_BYTES = 1024 * 1024
MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024
GET_MAX_RETRIES = 3


def positive_float(value):
    """Parse a positive floating-point number for argparse."""
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def normalize_api_base(value):
    """Validate and normalize an HTTPS API base URL."""
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("--api-base must be an HTTPS URL")
    if parsed.params or parsed.query or parsed.fragment:
        raise ValueError("--api-base must not contain parameters, a query, or a fragment")
    return value.rstrip("/")


def build_parser():
    parser = argparse.ArgumentParser(
        description="Generate images from text with the Atlas Cloud API"
    )
    parser.add_argument("--prompt", required=True, help="Text prompt for image generation")
    parser.add_argument(
        "--output",
        default=None,
        help="Output filename (default: atlas-image-<UUID>.png)",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Atlas image model (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--aspect-ratio",
        choices=SUPPORTED_ASPECT_RATIOS,
        default="auto",
        help="Requested aspect ratio (default: auto)",
    )
    parser.add_argument(
        "--thinking-level",
        choices=SUPPORTED_THINKING_LEVELS,
        default="default",
        help="Model thinking level (default: default)",
    )
    parser.add_argument(
        "--poll-interval",
        type=positive_float,
        default=DEFAULT_POLL_INTERVAL_SECONDS,
        help="Seconds between prediction checks (default: 2)",
    )
    parser.add_argument(
        "--timeout",
        type=positive_float,
        default=DEFAULT_POLL_TIMEOUT_SECONDS,
        help="Maximum prediction wait in seconds (default: 300)",
    )
    parser.add_argument(
        "--api-base",
        default=None,
        help="Atlas Cloud API base URL (default: ATLASCLOUD_API_BASE or api.atlascloud.ai)",
    )
    return parser


def parse_args(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.prompt = args.prompt.strip()
    if not args.prompt:
        parser.error("--prompt must not be empty")
    if len(args.prompt) > 10000:
        parser.error("--prompt must not exceed 10000 characters")
    args.model = args.model.strip()
    if not args.model:
        parser.error("--model must not be empty")
    args.output = Path(args.output or f"atlas-image-{uuid.uuid4()}.png").expanduser()
    if args.output.name in {"", ".", ".."} or args.output.is_dir():
        parser.error("--output must name a file")
    configured_base = (
        args.api_base
        or os.getenv("ATLASCLOUD_API_BASE")
        or os.getenv("ATLAS_CLOUD_API_BASE")
        or DEFAULT_API_BASE
    )
    try:
        args.api_base = normalize_api_base(configured_base)
    except ValueError as exc:
        parser.error(str(exc))
    return args


def build_payload(args):
    return {
        "model": args.model,
        "prompt": args.prompt,
        "aspect_ratio": args.aspect_ratio,
        "thinking_level": args.thinking_level,
        "resolution": "1k",
        "enable_sync_mode": False,
        "enable_base64_output": False,
    }


def read_json(response):
    body = response.read(MAX_JSON_BYTES + 1)
    if len(body) > MAX_JSON_BYTES:
        raise RuntimeError("Atlas Cloud response exceeds the maximum allowed size")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Atlas Cloud returned an invalid JSON response") from exc
    if not isinstance(payload, dict):
        raise TypeError("Atlas Cloud returned an invalid response object")
    return payload


def response_data(payload):
    code = payload.get("code")
    if code not in (None, 0, 200):
        message = payload.get("message") or "unknown API error"
        raise RuntimeError(f"Atlas Cloud request failed: {message}")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise TypeError("Atlas Cloud response did not contain prediction data")
    return data


def api_request(request, opener=urlopen):
    try:
        with opener(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return response_data(read_json(response))
    except HTTPError as exc:
        raise RuntimeError(f"Atlas Cloud request failed with HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"Atlas Cloud request failed: {exc.reason}") from exc


def submit_generation(args, api_key, opener=urlopen):
    """Submit exactly one generation POST and return its prediction data."""
    request = Request(
        f"{args.api_base}/api/v1/model/generateImage",
        data=json.dumps(build_payload(args)).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    data = api_request(request, opener=opener)
    prediction_id = data.get("id")
    if not isinstance(prediction_id, str) or not prediction_id:
        raise RuntimeError("Atlas Cloud response did not contain a prediction ID")
    return data


def request_prediction(
    api_base,
    prediction_id,
    api_key,
    opener=urlopen,
    sleep_fn=time.sleep,
):
    """Fetch a prediction, retrying only transient GET failures."""
    request = Request(
        f"{api_base}/api/v1/model/prediction/{quote(prediction_id, safe='')}",
        headers={
            "Authorization": f"Bearer {api_key}",
            "User-Agent": USER_AGENT,
        },
        method="GET",
    )
    for attempt in range(GET_MAX_RETRIES + 1):
        try:
            with opener(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                return response_data(read_json(response))
        except HTTPError as exc:
            transient = exc.code == 429 or 500 <= exc.code < 600
            if not transient or attempt == GET_MAX_RETRIES:
                raise RuntimeError(
                    f"Atlas Cloud prediction request failed with HTTP {exc.code}"
                ) from exc
        except URLError as exc:
            if attempt == GET_MAX_RETRIES:
                raise RuntimeError(
                    f"Atlas Cloud prediction request failed: {exc.reason}"
                ) from exc
        sleep_fn(2**attempt)
    raise RuntimeError("Atlas Cloud prediction request exhausted retries")


def completed_outputs(data):
    status = data.get("status")
    if status == "completed":
        outputs = data.get("outputs")
        if not isinstance(outputs, list) or not outputs:
            raise RuntimeError("Completed Atlas Cloud prediction contained no outputs")
        if not all(isinstance(value, str) and value for value in outputs):
            raise RuntimeError("Atlas Cloud prediction contained an invalid output")
        return outputs
    if status in {"failed", "timeout"}:
        detail = data.get("error") or f"prediction {status}"
        raise RuntimeError(f"Atlas Cloud generation failed: {detail}")
    if status not in PENDING_STATUSES:
        raise RuntimeError(f"Atlas Cloud returned an unknown prediction status: {status}")
    return None


def wait_for_outputs(
    initial_data,
    args,
    api_key,
    opener=urlopen,
    sleep_fn=time.sleep,
    monotonic_fn=time.monotonic,
):
    outputs = completed_outputs(initial_data)
    if outputs:
        return outputs
    deadline = monotonic_fn() + args.timeout
    prediction_id = initial_data["id"]
    while monotonic_fn() < deadline:
        data = request_prediction(
            args.api_base,
            prediction_id,
            api_key,
            opener=opener,
            sleep_fn=sleep_fn,
        )
        outputs = completed_outputs(data)
        if outputs:
            return outputs
        remaining = deadline - monotonic_fn()
        if remaining > 0:
            sleep_fn(min(args.poll_interval, remaining))
    raise RuntimeError("Atlas Cloud generation timed out while polling")


def download_image(url, opener=urlopen):
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError("Atlas Cloud returned an invalid image URL")
    request = Request(
        url,
        headers={"Accept": "image/*", "User-Agent": USER_AGENT},
    )
    try:
        with opener(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            data = response.read(MAX_DOWNLOAD_BYTES + 1)
    except HTTPError as exc:
        raise RuntimeError(f"Image download failed with HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"Image download failed: {exc.reason}") from exc
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise RuntimeError("Downloaded image exceeds the maximum allowed size")
    if not data:
        raise RuntimeError("Downloaded image is empty")
    return data


def save_first_output(outputs, output_path, opener=urlopen):
    image_data = download_image(outputs[0], opener=opener)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(image_data)
    return str(output_path)


def run(
    args,
    api_key=None,
    api_opener=urlopen,
    download_opener=urlopen,
    sleep_fn=time.sleep,
    monotonic_fn=time.monotonic,
):
    active_api_key = (
        api_key
        or os.getenv("ATLASCLOUD_API_KEY")
        or os.getenv("ATLAS_CLOUD_API_KEY")
    )
    if not active_api_key:
        raise RuntimeError("ATLASCLOUD_API_KEY is required")
    initial_data = submit_generation(args, active_api_key, opener=api_opener)
    outputs = wait_for_outputs(
        initial_data,
        args,
        active_api_key,
        opener=api_opener,
        sleep_fn=sleep_fn,
        monotonic_fn=monotonic_fn,
    )
    saved_path = save_first_output(outputs, args.output, opener=download_opener)
    print(f"Image saved to: {saved_path}")
    return saved_path


def main(argv=None):
    try:
        return 0 if run(parse_args(argv)) else 1
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
