---
name: nanobanana-skill
description: Generate, edit, or composite images with Gemini / Nanobanana models through the bundled CLI wrapper. This is the default image skill — use it for any image generation or editing request that does not name a different provider.
---

# Nanobanana Image Skill

Use the bundled `nanobanana.py` to generate or edit images with Gemini image models. The default path targets **Nano Banana 2** (`gemini-3.1-flash-image-preview`) with **thinking summaries** and **Google Search grounding** on, because those defaults are the main reason to use this skill instead of a generic image prompt.

## Requirements

1. `GEMINI_API_KEY` in `~/.nanobanana.env` (`GEMINI_API_KEY=sk-dummy`) or the shell environment.
2. Python dependencies from `requirements.txt`.
3. The executable is `nanobanana.py` in this same skill directory. Resolve its absolute path once before running it.

The CLI can print `--help` without credentials. It validates local input files before creating an API client and exits non-zero when the API returns no image.

## Defaults

Model `gemini-3.1-flash-image-preview`, search grounding on, thinking summaries on at level `high`, resolution `1K`, and no aspect ratio unless the request implies a shape. Do not make the user choose a model, search mode, or thinking mode unless they asked for that level of control.

Leaving aspect ratio unspecified is usually better for edits, because Gemini can match the input image shape. For text-only generation, set one only when the user implies a format such as poster, square post, banner, phone wallpaper, or ultrawide hero.

Worth overriding: `--model gemini-3-pro-image-preview` for very detail-heavy or typography-sensitive work (slower); `--resolution 512px` for quick ideation (Nanobanana 2 models only), `2K`/`4K` for polished deliverables; `--thinking-level low` when latency beats refinement; search off when the user wants a purely imaginative result. Run `python3 /absolute/path/to/nanobanana.py --help` for the exact accepted values, including the full aspect-ratio and model lists.

## Run it

Generate from text:

```bash
python3 /absolute/path/to/nanobanana.py \
  --prompt "Create a high-end coffee bag package design with tactile paper texture and clear typography" \
  --output /absolute/path/to/output/package.png
```

Edit or composite — pass every reference with `--input`. Nanobanana 2 mixes multiple references well, so do not narrow a blend, lineup, storyboard, or consistency pass down to a single image:

```bash
python3 /absolute/path/to/nanobanana.py \
  --prompt "Turn these product photos into a clean ecommerce hero image with a soft studio shadow and subtle headline area" \
  --input /absolute/path/to/ref1.png /absolute/path/to/ref2.png \
  --aspect-ratio 4:5 \
  --output /absolute/path/to/output/hero.png
```

Grounded generation, saving the model's text and metadata alongside the image:

```bash
python3 /absolute/path/to/nanobanana.py \
  --prompt "Use Google Search to ground an editorial illustration about the most recent lunar mission and create a clean magazine cover concept" \
  --text-output /absolute/path/to/output/cover.txt \
  --metadata-output /absolute/path/to/output/cover.json \
  --output /absolute/path/to/output/cover.png
```

Then report the saved path(s), whether search grounding stayed enabled, where any text or thought summaries landed, and any warning from the run. If the model returns text but no image, say so plainly and suggest a more explicitly image-focused prompt rather than presenting the run as a success.

## Prompting

Good Nanobanana prompts are production briefs, not art wishes: subject, visual style, composition or camera framing, any required text, the output's use case, and constraints such as brand colors, negative space, or realism level.

```text
Create a premium sparkling water can advertisement. Use a cold studio product-photo look, silver highlights, condensation droplets, and a clean dark-teal background. Leave negative space in the upper-right for headline copy.
```

For edits, say what to preserve as well as what to change:

```text
Keep the shoe silhouette and logo placement intact. Replace the background with a bright outdoor basketball court, add dynamic afternoon shadows, and keep the image looking like a real sports campaign photo.
```

## When a run fails

Confirm `GEMINI_API_KEY` is present, each input path exists and is readable, and the output directory is writable. If a feature looks unsupported, retry on `gemini-3.1-flash-image-preview` first.
