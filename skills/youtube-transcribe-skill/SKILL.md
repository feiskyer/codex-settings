---
name: youtube-transcribe-skill
description: Extract subtitles or transcripts from YouTube URLs and save normalized timestamped text locally. Use when the user asks for YouTube subtitles, captions, transcripts, video-to-text, 视频字幕, 字幕提取, YouTube 转文字, or 提取字幕.
---

# YouTube Transcript Extraction

Use the bundled `scripts/transcribe_youtube.py` wrapper for the primary workflow. It downloads subtitles with `yt-dlp`, selects the preferred language, converts WebVTT cues into timestamped plain text, and reports the output path and line count.

## Requirements

1. Install `yt-dlp` and confirm `yt-dlp --version` succeeds.
2. Resolve the absolute directory containing this `SKILL.md`; refer to it as `<skill-dir>`.
3. Keep the output in the user's current working directory unless they request another location.

The Python wrapper itself uses only the standard library. It can display `--help` without `yt-dlp` being installed.

## Primary workflow

Run without browser cookies first:

```bash
python3 "<skill-dir>/scripts/transcribe_youtube.py" \
  "<youtube-url>" \
  --output-dir "$PWD"
```

The default language preference is Simplified Chinese, Traditional Chinese, other Chinese variants, then English. Override it when the user requests another language:

```bash
python3 "<skill-dir>/scripts/transcribe_youtube.py" \
  "<youtube-url>" \
  --languages "ja.*,en.*" \
  --output-dir "$PWD"
```

The wrapper supports normal watch URLs plus `youtu.be`, Shorts, live, and embed URLs. A successful run writes one `.txt` file whose non-empty lines use this shape:

```text
00:03 Subtitle text
00:08 Next subtitle text
```

## Cookie retry

Do not read browser cookies by default. If the initial command fails specifically because the video requires sign-in, age verification, membership, or another authenticated session:

1. Explain that the retry will let `yt-dlp` read YouTube cookies from a local browser profile.
2. Ask the user which browser profile they approve using.
3. Retry only after approval:

```bash
python3 "<skill-dir>/scripts/transcribe_youtube.py" \
  "<youtube-url>" \
  --cookies-from-browser chrome \
  --output-dir "$PWD"
```

Never print, copy, or persist browser cookies in the transcript or logs.

## Browser fallback

Use browser automation only when `yt-dlp` is unavailable or cannot obtain subtitles and an appropriate browser-control capability is available.

1. Inspect the tools available in the current session; do not assume fixed MCP server or tool names.
2. Open the video, reveal the transcript panel, and extract visible timestamp/text pairs.
3. Save the result as `<sanitized-video-title>.txt` in the requested directory.
4. Close pages or sessions opened solely for this task.

If neither CLI extraction nor browser automation is available, report the missing capability instead of claiming success.

## Completion report

Return:

1. Absolute transcript path
2. Selected subtitle language
3. Number of transcript lines
4. Whether browser cookies or browser automation were used
