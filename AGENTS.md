# Repository Guidelines

## Repository Structure

- `config.toml` is the shared Codex CLI configuration and points to the local `copilot-gateway` provider at `localhost:4141`.
- Root-level `*.config.toml` files are optional Codex Profiles (`chatgpt`, `azure`, `github-copilot`, and `openrouter`). Keep the `<name>.config.toml` naming required by `codex --profile <name>`.
- `skills/<name>/SKILL.md` contains reusable workflows. Put deterministic helpers in `scripts/`, detailed references in `references/`, UI metadata in `agents/openai.yaml`, and offline regression tests in `tests/`.
- `.codex-plugin/plugin.json` packages the existing root `skills/` tree as the `codex-settings` Plugin without duplicating it.
- `.agents/plugins/marketplace.json` exposes the repository root as the Plugin source.
- `skills/github-fix-issue/` and `skills/github-review-pr/` replace the former GitHub Custom Prompts. Do not recreate duplicate workflows under `prompts/`.
- `litellm_config.yaml` is only for the optional GitHub Copilot through LiteLLM profile. It is not the backend used by the default `config.toml`.

## Definition of Done

A change in this repository is finished when all of these hold. Work through them without stopping for approval between steps:

1. The change itself is complete, including every file it implies — a renamed or materially changed Skill also updates its `agents/openai.yaml`, and a new or removed Skill also updates the Skills table in `README.md`.
2. The validation commands matching the changed files have been run and pass. Fix failures caused by the change and rerun affected checks; report unrelated failures separately.
3. `.codex-plugin/plugin.json` `version` is bumped if released Plugin content changed.
4. The final report states which validation commands ran, which integration checks were skipped and why, and any assumption the change rests on.

Stop early only for a genuine blocker: a missing credential, an ambiguous requirement where the readings lead to materially different work, or an action outside the scope described above.

## Validation Commands

Use [CONTRIBUTING.md](CONTRIBUTING.md#验证) for the commands matching the changed files: TOML parsing for configs, structure and isolated Plugin installation for Skills/manifests, and syntax plus offline tests for executable helpers. Prose-only edits do not require unrelated provider or API runs.

The offline tests use disposable local fixtures, have no network or production access, and need no credentials. Run them, fix failures caused by the requested change, and rerun affected checks without asking for approval at each step. The Plugin install test uses an isolated temporary `CODEX_HOME`, not the user's installed plugins.

Provider integration checks apply only to changed provider files. External API Skills use mocked/offline tests unless the user explicitly requests a live integration run. If a check requires changing the user's environment, authentication, or running services beyond the task's authorization, report the missing prerequisite instead.

## Style and Skill Conventions

- TOML uses two-space indentation where indentation applies, aligned `=` signs within related blocks, double-quoted strings, and grouped tables.
- Name Profiles, Skills, prompts, and scripts with lowercase kebab-case unless the platform requires another filename.
- Skill frontmatter contains only `name` and `description`. Put requirements and compatibility notes in the body.
- Keep each `description` as short as it can be while still making clear when the Skill applies. Describe the triggering situation, not a list of keywords, and do not treat the presence of an API key or a broad topic as a trigger. When several Skills cover the same territory, exactly one is the default and the others say they apply only when the user names that provider or tool.
- Write Skill instructions in imperative form. Keep the core workflow concise and move repeatable or fragile behavior into bundled scripts.
- Keep `SKILL.md` small enough to load cheaply. Move workflow detail, command references, and long examples into `references/` and have `SKILL.md` point at them per step, so a run only reads what that step needs. Do not restate a script's `--help` output; point at it.
- Assume the reading model has judgment. Write down what it cannot infer — this repository's paths, invariants, and failure modes — and leave out step-by-step recipes for decisions it can make from the request. These Skills are installed by others and run on models this repository does not control, so over-specified procedure constrains more than it helps.
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
