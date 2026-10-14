---
name: atlas-image-skill
description: 'Generate images with the Atlas Cloud API. Use when the user asks for Atlas Cloud image generation, an Atlas image model, or an image from a text prompt through Atlas Cloud.'
---

# Atlas Image Skill

Generate an image from a text prompt through the bundled Atlas Cloud helper.

## Resolve the skill directory

Resolve the absolute directory containing this `SKILL.md` before running a command and refer to it as `<skill-dir>`. Keep output paths relative to the user's working directory unless the user requests another location.

## Requirements

- Export `ATLASCLOUD_API_KEY` before running the helper. `ATLAS_CLOUD_API_KEY` is also accepted for compatibility.
- Use Python 3.9 or newer. The helper uses only the Python standard library.

## Generate an image

Confirm the prompt and output filename before submitting a generation request. Then run:

```bash
python3 "<skill-dir>/atlas_image.py" \
  --prompt "A quiet observatory beneath an aurora" \
  --output "observatory.png"
```

The helper defaults to `google/nano-banana-2-lite/text-to-image-developer`. Use `--model` to select another current Atlas text-to-image model. Optional fields include `--aspect-ratio` and `--thinking-level`.

The API is asynchronous. The helper submits exactly one generation request, polls the returned prediction with bounded GET requests, downloads the first HTTPS output, and creates output parent directories automatically.

## Safety and failures

- Never print or persist the API key.
- Validate the prompt, API base, and local output path before calling the API.
- Never retry the generation POST because another request may incur another charge.
- Retry only transient prediction GET failures, with bounded exponential backoff.
- Do not claim success unless the generated image was saved locally.
