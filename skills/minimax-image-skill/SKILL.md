---
name: minimax-image-skill
description: Generate images when the user names MiniMax or image-01/image-01-live. Use the default image skill when no provider is named.
---

# MiniMax Image Skill

Generate images from a text prompt through the bundled MiniMax Image API helper.

## Resolve the skill directory

Resolve the absolute directory containing this `SKILL.md` before running a command and refer to it as `<skill-dir>`. Keep output paths relative to the user's working directory unless the user requests another location.

## Requirements

- Export `MINIMAX_API_KEY` before running the helper.
- Use Python 3.9 or newer. The helper uses only the Python standard library.

## Generate an image

Every option has a working default, so pass only what the request actually constrains:

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

Use `--model image-01-live` when requested. Consult `python3 "<skill-dir>/minimax_image.py" --help` for optional fields and accepted values.

The helper downloads URL responses immediately because generated URLs expire. It also decodes base64 responses and creates output parent directories automatically. For multiple results, it adds a numeric suffix to the output filename.

## Safety and failures

- Never print or persist the API key.
- Do not call the API until the prompt and local output path pass validation.
- If the API rejects a field combination, correct an assistant-chosen option when the user's requested result is unchanged; ask when resolving it would change a user constraint. Check for generated output before a bounded retry.
- Do not claim success unless at least one image was saved locally.
