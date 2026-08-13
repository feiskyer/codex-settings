---
name: minimax-image-skill
description: 'Generate images with the MiniMax Image API. Use when the user asks for MiniMax image generation, image-01, image-01-live, or an image from a text prompt through MiniMax.'
---

# MiniMax Image Skill

Generate images from a text prompt through the bundled MiniMax Image API helper.

## Resolve the skill directory

Resolve the absolute directory containing this `SKILL.md` before running a command and refer to it as `<skill-dir>`. Keep output paths relative to the user's working directory unless the user requests another location.

## Requirements

- Export `MINIMAX_API_KEY` before running the helper.
- Use Python 3.9 or newer. The helper uses only the Python standard library.

## Generate an image

Ask for the prompt and, when relevant, the model, region, aspect ratio, dimensions, result count, and output filename. Then run:

```bash
python3 "<skill-dir>/minimax_image.py" \
  --prompt "A quiet observatory beneath an aurora" \
  --output "observatory.png"
```

The global endpoint is used by default. Select the China endpoint explicitly when needed:

```bash
python3 "<skill-dir>/minimax_image.py" \
  --region china \
  --prompt "A paper-cut landscape at sunrise" \
  --output "landscape.png"
```

Use `--model image-01-live` for that model. Optional API fields are exposed through `--aspect-ratio`, `--width`, `--height`, `--seed`, `--n`, `--response-format`, and `--disable-prompt-optimizer`.

The helper downloads URL responses immediately because generated URLs expire. It also decodes base64 responses and creates output parent directories automatically. For multiple results, it adds a numeric suffix to the output filename.

## Safety and failures

- Never print or persist the API key.
- Do not call the API until the prompt and local output path pass validation.
- If the API rejects a field combination, report the returned error and ask the user to adjust only that option.
- Do not claim success unless at least one image was saved locally.
