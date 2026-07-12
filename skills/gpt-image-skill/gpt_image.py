#!/usr/bin/env python3
"""Generate or edit images using OpenAI GPT Image API."""

import argparse
import base64
import os
import sys
import uuid

from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image
from io import BytesIO

# Load environment variables from ~/.gpt-image.env
load_dotenv(os.path.expanduser("~") + "/.gpt-image.env")


def get_client():
    """Initialize OpenAI client with optional custom base URL."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY is required. Set it in ~/.gpt-image.env or export it.", file=sys.stderr)
        sys.exit(1)

    kwargs = {"api_key": api_key}
    base_url = os.getenv("OPENAI_API_BASE")
    if base_url:
        kwargs["base_url"] = base_url

    return OpenAI(**kwargs)


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
    }

    if args.format:
        params["output_format"] = args.format
    if args.background:
        params["background"] = args.background

    response = client.images.generate(**params)

    save_results(response, args)


def edit_image(client, args):
    """Edit image(s) using a prompt and reference images."""
    if not args.input:
        print("Error: --input is required for image editing.", file=sys.stderr)
        sys.exit(1)

    print(f"Editing images with prompt: {args.prompt}")
    print(f"Input images: {args.input}")

    # Open image files
    image_files = []
    for path in args.input:
        if not os.path.exists(path):
            print(f"Error: Input file not found: {path}", file=sys.stderr)
            sys.exit(1)
        image_files.append(open(path, "rb"))

    params = {
        "model": args.model,
        "image": image_files if len(image_files) > 1 else image_files[0],
        "prompt": args.prompt,
        "n": args.n,
        "size": args.size,
        "quality": args.quality,
    }

    try:
        response = client.images.edit(**params)
        save_results(response, args)
    finally:
        for f in image_files:
            f.close()


def save_results(response, args):
    """Save generated/edited images to disk."""
    if not response.data:
        print("Error: No image data received from the API.", file=sys.stderr)
        sys.exit(1)

    for i, image_data in enumerate(response.data):
        # Determine output filename
        if args.n > 1:
            base, ext = os.path.splitext(args.output)
            output_path = f"{base}_{i + 1}{ext}"
        else:
            output_path = args.output

        # Handle base64 response
        if image_data.b64_json:
            img_bytes = base64.b64decode(image_data.b64_json)
            image = Image.open(BytesIO(img_bytes))
            image.save(output_path)
            print(f"Image saved to: {output_path}")
        elif image_data.url:
            # Download from URL
            import httpx
            resp = httpx.get(image_data.url)
            with open(output_path, "wb") as f:
                f.write(resp.content)
            print(f"Image saved to: {output_path}")
        else:
            print(f"Warning: No image content for result {i + 1}", file=sys.stderr)

    if response.data[0].revised_prompt:
        print(f"\nRevised prompt: {response.data[0].revised_prompt}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate or edit images using OpenAI GPT Image API"
    )
    subparsers = parser.add_subparsers(dest="command")

    # Common arguments
    def add_common_args(p):
        p.add_argument(
            "--prompt", type=str, required=True,
            help="Text prompt for generation or editing"
        )
        p.add_argument(
            "--output", type=str, default=None,
            help="Output filename (default: auto-generated)"
        )
        p.add_argument(
            "--model", type=str, default="gpt-image-2",
            help="Model to use (default: gpt-image-2)"
        )
        p.add_argument(
            "--size", type=str, default="1024x1024",
            choices=["1024x1024", "1024x1536", "1536x1024", "auto"],
            help="Image size (default: 1024x1024)"
        )
        p.add_argument(
            "--quality", type=str, default="auto",
            choices=["auto", "high", "medium", "low"],
            help="Image quality (default: auto)"
        )
        p.add_argument(
            "--n", type=int, default=1,
            help="Number of images to generate (default: 1)"
        )
        p.add_argument(
            "--format", type=str, default=None,
            choices=["png", "jpeg", "webp"],
            help="Output format (default: png)"
        )
        p.add_argument(
            "--background", type=str, default=None,
            choices=["auto", "transparent", "opaque"],
            help="Background type (default: auto)"
        )

    # Generate (default command)
    add_common_args(parser)

    # Edit subcommand
    edit_parser = subparsers.add_parser("edit", help="Edit existing images")
    add_common_args(edit_parser)
    edit_parser.add_argument(
        "--input", type=str, nargs="+", required=True,
        help="Input image file(s) for editing"
    )

    args = parser.parse_args()

    # Default output filename
    if args.output is None:
        ext = args.format or "png"
        args.output = f"gpt-image-{uuid.uuid4()}.{ext}"

    client = get_client()

    if args.command == "edit":
        edit_image(client, args)
    else:
        generate_image(client, args)


if __name__ == "__main__":
    main()
