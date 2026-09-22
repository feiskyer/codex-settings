---
name: gpt-image-skill
description: Generate or edit images through the OpenAI GPT Image API. Use only when the user names OpenAI, GPT Image, or a `gpt-image-*` model for image work; for image requests with no provider named, use the default image skill instead.
---

# GPT Image Skill

Generate or edit images with OpenAI's GPT Image models through the bundled `gpt_image.py`.

## Resolve the skill directory

Before running any command, resolve the absolute directory containing this `SKILL.md` and refer to it as `<skill-dir>`. Never assume the current working directory is the skill directory. Keep user input and output paths relative to the user's working directory unless the user requests another location.

## Requirements

1. **OPENAI_API_KEY** in `~/.gpt-image.env` or the shell environment.
2. **OPENAI_API_BASE** (optional) for compatible endpoints such as Azure OpenAI or a proxy, in the same places.
3. **Python dependencies**: `python3 -m pip install -r "<skill-dir>/requirements.txt"`.
4. **Executable**: `<skill-dir>/gpt_image.py`.

## Run it

Generate:

```bash
python3 "<skill-dir>/gpt_image.py" --prompt "Modern minimalist logo for a tech startup" \
  --quality high --background transparent --output "logo.png"
```

Edit or combine references:

```bash
python3 "<skill-dir>/gpt_image.py" edit --prompt "Add a rainbow in the sky" \
  --input photo.png --output "photo-with-rainbow.png"
```

`edit` accepts several `--input` files to composite multiple references into one image.

Options live on the subcommands, so read them with `generate --help` or `edit --help` — the bare `python3 "<skill-dir>/gpt_image.py" --help` only lists the two modes. That is where the current `--model`, `--size`, `--quality`, `--format`, `--background`, and `--n` values are; every one has a working default, so pass only what the request actually constrains. Parent directories in the output path are created automatically, and an omitted `--format` is inferred from the `.png`, `.jpg`/`.jpeg`, or `.webp` extension, defaulting to PNG.

Report the saved path when the run completes.

## When a run fails

Check that `OPENAI_API_KEY` is set and, for a custom endpoint, that `OPENAI_API_BASE` is correct; confirm input images exist and are readable, the output directory is writable, and the model name is valid. Do not report success unless an image was saved locally.
