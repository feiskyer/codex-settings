# Repository Guidelines

## Repository Structure

- `config.toml` is the shared Codex CLI configuration and points to the local `copilot-gateway` provider at `localhost:4141`.
- Root-level `*.config.toml` files are optional Codex Profiles (`chatgpt`, `azure`, `github-copilot`, and `openrouter`). Keep the `<name>.config.toml` naming required by `codex --profile <name>`.
- `skills/<name>/SKILL.md` contains reusable workflows. Put deterministic helpers in `scripts/`, detailed references in `references/`, UI metadata in `agents/openai.yaml`, and offline regression tests in `tests/`.
- `.codex-plugin/plugin.json` packages the existing root `skills/` tree as the `codex-settings` Plugin without duplicating it.
- `.agents/plugins/marketplace.json` exposes the repository root as the Plugin source.
- `skills/github-fix-issue/` and `skills/github-review-pr/` replace the former GitHub Custom Prompts. Do not recreate duplicate workflows under `prompts/`.
- `litellm_config.yaml` is only for the optional GitHub Copilot through LiteLLM profile. It is not the backend used by the default `config.toml`.

## Validation Commands

Run checks that match the files you changed. The standard offline suite is:

```bash
# TOML syntax
python3 -c 'import pathlib, tomllib; [tomllib.loads(p.read_text()) for p in pathlib.Path(".").glob("**/*.toml")]'

# Plugin package and marketplace
python3 -m json.tool .codex-plugin/plugin.json >/dev/null
python3 -m json.tool .agents/plugins/marketplace.json >/dev/null
python3 ~/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .

# Skill structure
for skill in skills/*; do
  test ! -f "$skill/SKILL.md" || \
    python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py "$skill"
done

# Python scripts and offline tests
python3 -m compileall -q skills
ruff check skills
for test_dir in skills/*/tests; do
  test ! -d "$test_dir" || python3 -m unittest discover -s "$test_dir" -v
done

# Bundled shell and JavaScript helpers
bash -n skills/brainstorming/scripts/start-server.sh \
  skills/brainstorming/scripts/stop-server.sh \
  scripts/test-plugin-install.sh \
  scripts/update-codex-plugins.sh \
  scripts/test-update-codex-plugins.sh
bash scripts/test-update-codex-plugins.sh
node --check skills/brainstorming/scripts/server.cjs
node --check skills/brainstorming/scripts/helper.js
```

Run provider integration checks only when the related provider files change:

- Strict Codex config: with the relevant provider available, run `CODEX_HOME="$PWD" codex --strict-config exec --ephemeral --sandbox read-only --skip-git-repo-check -c mcp_servers.chrome.enabled=false -c web_search="disabled" "Reply exactly OK"`.
- Default gateway: start `copilot-gateway`, then run `codex` or `codex doctor --summary`.
- LiteLLM profile: start `litellm --config ~/.codex/litellm_config.yaml`, then run `codex --profile github-copilot`.
- ChatGPT profile: authenticate with `codex login`, then run `codex --profile chatgpt`.
- Codex Plugin: when the marketplace, Plugin manifest, Skills, or Plugin test script changes, run `scripts/test-plugin-install.sh` with the installed stable Codex CLI.
- External API Skills: prefer mocked/offline tests. Use real credentials only for an explicitly requested integration test.

## Style and Skill Conventions

- TOML uses two-space indentation where indentation applies, aligned `=` signs within related blocks, double-quoted strings, and grouped tables.
- Name Profiles, Skills, prompts, and scripts with lowercase kebab-case unless the platform requires another filename.
- Skill frontmatter contains only `name` and `description`. Put requirements and compatibility notes in the body.
- Write Skill instructions in imperative form. Keep the core workflow concise and move repeatable or fragile behavior into bundled scripts.
- Add or refresh `agents/openai.yaml` when a Skill is created or materially renamed. Its `default_prompt` must mention `$skill-name`.
- Bump `.codex-plugin/plugin.json` `version` whenever released Plugin content changes. Use semantic versions for releases and a single `+codex.<cachebuster>` suffix only for local iteration.
- Keep default installation documentation unpinned so it follows the repository default branch. Use matching immutable `v<version>` tags as release checkpoints, not as the default install ref.
- Scripts must expose `--help`, validate local inputs before network/API calls, return non-zero on failure, and create output parent directories when appropriate.
- Tests must not require paid API calls, browser cookies, interactive approval, or live third-party services unless the user explicitly requests an integration run.

## Commit and Pull Request Guidelines

- Use concise title-case imperative commit subjects, consistent with repository history.
- Keep commits scoped; do not include local Codex runtime state, credentials, generated logs, or unrelated working-tree changes.
- In pull requests, list affected configs or Skills, validation commands run, intentionally skipped integration checks, and any compatibility assumptions.
- Use redacted placeholders such as `sk-dummy` in examples.

## Security

- Never commit API keys, access tokens, cookies, real authorization headers, or private logs.
- Review `shell_environment_policy`, sandbox, network, MCP, and browser-cookie behavior when changing integrations.
- Do not silently broaden permissions or enable browser-cookie access. Explain the need and obtain user approval first.
- Follow `SECURITY.md` for vulnerability reporting.
