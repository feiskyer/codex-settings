#!/usr/bin/env python3
"""Generate or edit images with Gemini image models via Nanobanana."""

import argparse
import json
import os
import sys
import uuid
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image

ASPECT_RATIO_MAP = {
    "1024x1024": "1:1",
    "832x1248": "2:3",
    "1248x832": "3:2",
    "864x1184": "3:4",
    "1184x864": "4:3",
    "896x1152": "4:5",
    "1152x896": "5:4",
    "768x1344": "9:16",
    "1344x768": "16:9",
    "1536x672": "21:9",
}

SUPPORTED_ASPECT_RATIOS = [
    "1:1",
    "1:4",
    "1:8",
    "2:3",
    "3:2",
    "3:4",
    "4:1",
    "4:3",
    "4:5",
    "5:4",
    "8:1",
    "9:16",
    "16:9",
    "21:9",
]

SUPPORTED_MODELS = [
    "gemini-3.1-flash-image-preview",
    "gemini-3-pro-image-preview",
    "gemini-2.5-flash-image",
]

SUPPORTED_RESOLUTIONS = ["512px", "1K", "2K", "4K"]


def get_client():
    """Initialize the Gemini client after CLI arguments have been parsed."""
    load_dotenv(Path.home() / ".nanobanana.env")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is required. Set it in ~/.nanobanana.env or export it."
        )
    return genai.Client(api_key=api_key)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate or edit images using Google Gemini API"
    )
    parser.add_argument(
        "--prompt",
        type=str,
        required=True,
        help="Prompt for image generation or editing",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=f"nanobanana-{uuid.uuid4()}.png",
        help="Output image filename (default: nanobanana-<UUID>.png)",
    )
    parser.add_argument(
        "--input",
        dest="input_files",
        type=str,
        nargs="*",
        help="Input image files for editing or multi-reference composition",
    )
    parser.add_argument(
        "--aspect-ratio",
        type=str,
        choices=SUPPORTED_ASPECT_RATIOS,
        default=None,
        help="Aspect ratio of the generated image. If omitted, Gemini chooses automatically.",
    )
    parser.add_argument(
        "--size",
        type=str,
        choices=list(ASPECT_RATIO_MAP.keys()),
        default=None,
        help="Deprecated alias for aspect ratio using legacy size presets.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gemini-3.1-flash-image-preview",
        choices=SUPPORTED_MODELS,
        help="Model to use for image generation (default: gemini-3.1-flash-image-preview)",
    )
    parser.add_argument(
        "--resolution",
        type=str,
        default="1K",
        choices=SUPPORTED_RESOLUTIONS,
        help="Resolution of the generated image (default: 1K)",
    )
    parser.add_argument(
        "--disable-google-search",
        action="store_true",
        help="Disable Google Search grounding (enabled by default).",
    )
    parser.add_argument(
        "--disable-thinking",
        action="store_true",
        help="Reduce or disable thinking where the model family supports it.",
    )
    parser.add_argument(
        "--thinking-level",
        type=str,
        default="high",
        choices=["minimal", "low", "medium", "high"],
        help="Thinking level for Gemini 3 image models (default: high).",
    )
    parser.add_argument(
        "--exclude-thoughts",
        action="store_true",
        help="Do not include thought summaries in stdout or saved text output.",
    )
    parser.add_argument(
        "--text-output",
        type=str,
        default=None,
        help="Optional path to save response text and thought summaries.",
    )
    parser.add_argument(
        "--metadata-output",
        type=str,
        default=None,
        help="Optional path to save structured metadata about the run.",
    )
    return parser.parse_args(argv)


def resolve_aspect_ratio(args):
    if args.aspect_ratio:
        return args.aspect_ratio
    if args.size:
        return ASPECT_RATIO_MAP[args.size]
    return None


def build_thinking_config(args):
    if args.disable_thinking:
        if args.model.startswith("gemini-2.5"):
            return types.ThinkingConfig(
                include_thoughts=False,
                thinking_budget=0,
            )
        return types.ThinkingConfig(
            include_thoughts=False,
            thinking_level="minimal",
        )

    kwargs = {"include_thoughts": not args.exclude_thoughts}
    if args.model.startswith("gemini-2.5"):
        return types.ThinkingConfig(**kwargs)

    kwargs["thinking_level"] = args.thinking_level
    return types.ThinkingConfig(**kwargs)


def ensure_parent_dir(path_str):
    if not path_str:
        return
    Path(path_str).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


def save_text_output(path_str, text_parts, thought_parts):
    if not path_str:
        return

    ensure_parent_dir(path_str)
    lines = []
    if text_parts:
        lines.append("# Response Text")
        lines.append("")
        lines.extend(text_parts)
        lines.append("")
    if thought_parts:
        lines.append("# Thought Summaries")
        lines.append("")
        lines.extend(thought_parts)
        lines.append("")

    Path(path_str).write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def save_metadata_output(path_str, payload):
    if not path_str:
        return

    ensure_parent_dir(path_str)
    Path(path_str).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def save_image_parts(parts, output_path):
    output_path = Path(output_path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    saved_paths = []
    image_index = 0
    for part in parts:
        if part.inline_data is None or part.inline_data.data is None:
            continue

        image_index += 1
        target_path = output_path
        if image_index > 1:
            target_path = output_path.with_name(
                f"{output_path.stem}-{image_index}{output_path.suffix}"
            )

        with Image.open(BytesIO(part.inline_data.data)) as image:
            image.save(target_path)
        saved_paths.append(str(target_path))

    return saved_paths


def load_input_images(input_files):
    """Validate and load input images without leaving file handles open."""
    loaded_images = []
    try:
        for img_path in input_files or []:
            path = Path(img_path).expanduser()
            if not path.is_file():
                raise FileNotFoundError(f"Input image not found: {path}")
            with Image.open(path) as image:
                loaded_images.append(image.copy())
    except Exception:
        for image in loaded_images:
            image.close()
        raise
    return loaded_images


def run(args, client=None):
    """Execute one generation or editing request and return saved image paths."""
    aspect_ratio = resolve_aspect_ratio(args)

    if args.input_files and len(args.input_files) > 14:
        raise ValueError("Nanobanana supports at most 14 input reference images.")

    contents = []
    input_images = load_input_images(args.input_files)

    if input_images:
        print(f"Editing images with prompt: {args.prompt}")
        print(f"Input images: {args.input_files}")
        contents.append(args.prompt)
        contents.extend(input_images)
    else:
        print(f"Generating image with prompt: {args.prompt}")
        contents.append(args.prompt)

    print(f"Model: {args.model}")
    print(f"Resolution: {args.resolution}")
    print(
        "Google Search grounding: "
        + ("disabled" if args.disable_google_search else "enabled")
    )
    if aspect_ratio:
        print(f"Aspect ratio: {aspect_ratio}")
    else:
        print("Aspect ratio: auto")

    config_kwargs = {
        "response_modalities": ["TEXT", "IMAGE"],
        "thinking_config": build_thinking_config(args),
    }
    if aspect_ratio or args.resolution:
        image_config_kwargs = {"image_size": args.resolution}
        if aspect_ratio:
            image_config_kwargs["aspect_ratio"] = aspect_ratio
        config_kwargs["image_config"] = types.ImageConfig(**image_config_kwargs)
    if not args.disable_google_search:
        config_kwargs["tools"] = [types.Tool(google_search=types.GoogleSearch())]

    try:
        active_client = client or get_client()
        response = active_client.models.generate_content(
            model=args.model,
            contents=contents,
            config=types.GenerateContentConfig(**config_kwargs),
        )
    finally:
        for image in input_images:
            image.close()

    if (
        response.candidates is None
        or len(response.candidates) == 0
        or response.candidates[0].content is None
        or response.candidates[0].content.parts is None
    ):
        raise ValueError("No data received from the API.")

    parts = response.candidates[0].content.parts
    text_parts = []
    thought_parts = []
    for part in parts:
        if part.text is not None:
            if getattr(part, "thought", False):
                thought_parts.append(part.text)
            else:
                text_parts.append(part.text)

    for block_title, block_parts in (
        ("Response Text", text_parts),
        ("Thought Summaries", thought_parts),
    ):
        if not block_parts:
            continue
        print(f"\n{block_title}:")
        for text in block_parts:
            print(text)

    saved_paths = save_image_parts(parts, args.output)
    save_text_output(args.text_output, text_parts, thought_parts)

    metadata = {
        "model": args.model,
        "prompt": args.prompt,
        "input_files": args.input_files or [],
        "aspect_ratio": aspect_ratio,
        "resolution": args.resolution,
        "google_search_enabled": not args.disable_google_search,
        "thinking_disabled": args.disable_thinking,
        "thinking_level": None if args.disable_thinking else args.thinking_level,
        "include_thought_summaries": not args.exclude_thoughts and not args.disable_thinking,
        "response_text": text_parts,
        "thought_summaries": thought_parts,
        "saved_images": saved_paths,
    }
    save_metadata_output(args.metadata_output, metadata)

    if not saved_paths:
        raise RuntimeError(
            "No image data found in the API response. "
            "Try again with a more explicit image-generation prompt."
        )

    for saved_path in saved_paths:
        print(f"\nImage saved to: {saved_path}")

    if args.text_output:
        print(f"Text output saved to: {Path(args.text_output).expanduser().resolve()}")
    if args.metadata_output:
        print(
            f"Metadata output saved to: {Path(args.metadata_output).expanduser().resolve()}"
        )
    return saved_paths


def main(argv=None, client=None):
    try:
        args = parse_args(argv)
        run(args, client=client)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
