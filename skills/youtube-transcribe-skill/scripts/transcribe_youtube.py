#!/usr/bin/env python3
"""Download YouTube subtitles with yt-dlp and normalize them to plain text."""

import argparse
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import parse_qs, urlparse


DEFAULT_LANGUAGES = "zh-Hans,zh-Hant,zh.*,en.*"
TIMING_RE = re.compile(
    r"(?P<start>(?:\d{2}:)?\d{2}:\d{2}[.,]\d{3})\s+-->\s+"
    r"(?P<end>(?:\d{2}:)?\d{2}:\d{2}[.,]\d{3})"
)
TAG_RE = re.compile(r"<[^>]+>")
INLINE_TIMESTAMP_RE = re.compile(r"<\d{2}:\d{2}:\d{2}[.,]\d{3}>")
INVALID_FILENAME_RE = re.compile(r"[\\/:*?\"<>|\x00-\x1f]")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{3,}$")


def is_youtube_url(value):
    """Return whether a URL points to a supported YouTube video shape."""
    try:
        parsed = urlparse(value)
    except ValueError:
        return False

    if parsed.scheme not in {"http", "https"}:
        return False

    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host.startswith("m."):
        host = host[2:]

    path_parts = [part for part in parsed.path.split("/") if part]
    if host == "youtu.be":
        return bool(path_parts and SAFE_ID_RE.fullmatch(path_parts[0]))

    if host not in {"youtube.com", "youtube-nocookie.com"}:
        return False
    if parsed.path == "/watch":
        video_ids = parse_qs(parsed.query).get("v", [])
        return bool(video_ids and SAFE_ID_RE.fullmatch(video_ids[0]))
    return bool(
        len(path_parts) >= 2
        and path_parts[0] in {"shorts", "live", "embed"}
        and SAFE_ID_RE.fullmatch(path_parts[1])
    )


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Download YouTube subtitles and save timestamped plain text"
    )
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory for the transcript (default: current directory)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Explicit .txt output path; overrides --output-dir",
    )
    parser.add_argument(
        "--languages",
        default=DEFAULT_LANGUAGES,
        help=f"yt-dlp subtitle language selector (default: {DEFAULT_LANGUAGES})",
    )
    parser.add_argument(
        "--cookies-from-browser",
        default=None,
        help="Browser name/profile approved by the user for authenticated retry",
    )
    parser.add_argument(
        "--yt-dlp-bin",
        default="yt-dlp",
        help="yt-dlp executable name or path (default: yt-dlp)",
    )
    return parser.parse_args(argv)


def resolve_executable(command):
    """Resolve an executable name or path."""
    if os.sep in command or (os.altsep and os.altsep in command):
        path = Path(command).expanduser()
        if path.is_file() and os.access(path, os.X_OK):
            return str(path.resolve())
        return None
    return shutil.which(command)


def build_yt_dlp_command(args, executable, work_dir):
    """Build the yt-dlp command without enabling cookies implicitly."""
    output_template = str(Path(work_dir) / "%(id)s.%(ext)s")
    command = [
        executable,
        "--quiet",
        "--no-warnings",
        "--skip-download",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs",
        args.languages,
        "--sub-format",
        "vtt",
        "--write-info-json",
        "--output",
        output_template,
    ]
    if args.cookies_from_browser:
        command.extend(["--cookies-from-browser", args.cookies_from_browser])
    command.append(args.url)
    return command


def clean_caption(lines):
    """Normalize a VTT cue body into one plain-text caption."""
    text = " ".join(line.strip() for line in lines if line.strip())
    text = INLINE_TIMESTAMP_RE.sub("", text)
    text = TAG_RE.sub("", text)
    return " ".join(html.unescape(text).split())


def format_timestamp(value):
    """Convert a VTT timestamp to a compact HH:MM:SS or MM:SS value."""
    whole = value.replace(",", ".").split(".", 1)[0]
    parts = whole.split(":")
    if len(parts) == 3 and parts[0] == "00":
        return ":".join(parts[1:])
    return whole


def parse_vtt(content):
    """Parse WebVTT content into timestamped transcript lines."""
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n{2,}", normalized)
    transcript = []
    previous_text = None

    for block in blocks:
        lines = [line for line in block.split("\n") if line.strip()]
        timing_index = next(
            (index for index, line in enumerate(lines) if TIMING_RE.search(line)),
            None,
        )
        if timing_index is None:
            continue
        match = TIMING_RE.search(lines[timing_index])
        caption = clean_caption(lines[timing_index + 1 :])
        if not caption or caption == previous_text:
            continue
        transcript.append(f"{format_timestamp(match.group('start'))} {caption}")
        previous_text = caption

    return transcript


def language_preferences(selector):
    """Turn yt-dlp language patterns into an ordered matching preference."""
    preferences = []
    for item in selector.split(","):
        normalized = item.strip().replace(".*", "")
        if normalized:
            preferences.append(normalized)
    return preferences


def choose_subtitle(paths, video_id, selector):
    """Choose one downloaded subtitle according to the requested language order."""
    candidates = []
    prefix = f"{video_id}."
    for path in paths:
        name = path.name
        language = name[len(prefix) : -4] if name.startswith(prefix) else name[:-4]
        candidates.append((path, language))

    for preference in language_preferences(selector):
        for path, language in candidates:
            if language == preference or language.startswith(f"{preference}-"):
                return path, language
    return candidates[0] if candidates else (None, None)


def sanitize_filename(value, fallback):
    """Return a portable transcript filename stem."""
    cleaned = INVALID_FILENAME_RE.sub("_", value).strip(" .")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return (cleaned or fallback)[:120]


def resolve_output_path(args, title, video_id):
    """Resolve and create the requested output path."""
    if args.output:
        output_path = Path(args.output).expanduser()
        if output_path.suffix.lower() != ".txt":
            raise ValueError("--output must use a .txt extension")
    else:
        output_path = Path(args.output_dir).expanduser() / (
            sanitize_filename(title, video_id) + ".txt"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path.resolve()


def run(args):
    """Download, convert, and save one transcript."""
    if not is_youtube_url(args.url):
        raise ValueError("Unsupported or invalid YouTube URL")

    executable = resolve_executable(args.yt_dlp_bin)
    if not executable:
        raise RuntimeError(f"yt-dlp executable not found: {args.yt_dlp_bin}")

    with tempfile.TemporaryDirectory(prefix="youtube-transcript-") as temp_dir:
        command = build_yt_dlp_command(args, executable, temp_dir)
        completed = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        if completed.returncode != 0:
            detail = completed.stdout.strip()[-2000:]
            cookie_hint = (
                " Retry with --cookies-from-browser only after the user approves it."
                if not args.cookies_from_browser
                else ""
            )
            raise RuntimeError(
                f"yt-dlp failed with exit code {completed.returncode}: {detail}"
                f"{cookie_hint}"
            )

        info_files = sorted(Path(temp_dir).glob("*.info.json"))
        if not info_files:
            raise RuntimeError("yt-dlp did not produce video metadata")
        metadata = json.loads(info_files[0].read_text(encoding="utf-8"))
        video_id = str(metadata.get("id") or info_files[0].name.split(".", 1)[0])
        title = str(metadata.get("title") or video_id)

        subtitle_path, language = choose_subtitle(
            sorted(Path(temp_dir).glob("*.vtt")),
            video_id,
            args.languages,
        )
        if subtitle_path is None:
            raise RuntimeError("No matching subtitles were downloaded for this video")

        transcript_lines = parse_vtt(subtitle_path.read_text(encoding="utf-8-sig"))
        if not transcript_lines:
            raise RuntimeError("The downloaded subtitle file contained no transcript cues")

        output_path = resolve_output_path(args, title, video_id)
        output_path.write_text("\n".join(transcript_lines) + "\n", encoding="utf-8")

    return {
        "path": str(output_path),
        "language": language,
        "lines": len(transcript_lines),
        "cookies_used": bool(args.cookies_from_browser),
    }


def main(argv=None):
    try:
        result = run(parse_args(argv))
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
