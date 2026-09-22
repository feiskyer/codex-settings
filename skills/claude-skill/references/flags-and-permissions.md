# Flags, Permission Modes, and Tool Scoping

Detail behind the core rules in SKILL.md. Read this when building a command that needs more than `-p`, or when the user asks about permissions, tool scoping, or output formats.

## Permission modes

| Mode | Use |
| --- | --- |
| `default` | Interactive exploration. Prompts on first use of write/bash-style tools. |
| `acceptEdits` | Recommended starting point for coding automation. Auto-accepts edits, but command execution can still prompt. |
| `plan` | Analysis only. No file changes or command execution. |
| `dontAsk` | Auto-denies anything not already approved by permission rules. Good for unattended-but-constrained runs. |
| `bypassPermissions` | Skips prompts entirely. Only for strong sandbox / container / VM isolation. |

- `acceptEdits` is this skill's recommended default, not the CLI default.
- If the user says "no prompts at all," prefer explicit permission rules or `dontAsk` with allow rules — not `bypassPermissions`.
- Only recommend `bypassPermissions` when the environment is already isolated and the user accepts the risk.
- For read-only analysis, prefer `--tools` plus `default` or `plan`.

## Tool availability vs permission approval

These are different mechanisms and are easy to confuse:

- `--tools` restricts which built-in tools are available at all.
- `--allowedTools` pre-approves specific tools or tool rules so Claude does not prompt for them.
- `--disallowedTools` removes tools or rules from context.

To limit Claude to a narrow tool family, use both: `--tools` sets the hard boundary, `--allowedTools` removes prompts inside it.

Permission rules follow `Tool` or `Tool(specifier)` syntax, and **the specifier syntax varies by build** — Anthropic's docs often show `Bash(git diff *)` while some installed builds show `Bash(git:*)`. Mirror whatever the target machine's `claude --help` prints. Either way, use an argument-aware rule:

- Good: `Bash(git diff *)` / `Bash(git:*)`
- Good: `Bash(npm run test *)`
- Risky: `Bash(find)` — matches only the exact literal command `find`, with no arguments

## Output formats

- `text`: default human-readable output
- `json`: one final structured result
- `stream-json`: event stream for long-running automation

Do not promise a fixed JSON schema unless you have validated it on the target version. Prefer wording like "returns a final result object with response text, timing, and session metadata."

## Model selection

Omit `--model` by default — the user's configured model (via `/model`, settings, or `ANTHROPIC_MODEL`) is the right one unless they said otherwise. Use `--model <alias-or-name>` only for an explicit override or when a workflow must pin a model for reproducibility. For persistent defaults and third-party deployments, pin through settings or environment variables rather than bolting `--model` onto every command.

## Flags that are safe starting points

`--append-system-prompt`, `--allowedTools`, `--disallowedTools`, `--tools`, `--permission-mode`, `--output-format`, `--mcp-config`, `--continue` / `--resume`, `--settings` / `--setting-sources`, `--session-id`, `--add-dir`, `--max-budget-usd`, `--fallback-model` (print mode).

Published docs sometimes mention flags absent from the installed binary. Verify less-common flags against `claude --help` on the target machine before emitting them.

## Installation

`npm install -g @anthropic-ai/claude-code` is the standard path in Anthropic's getting-started docs. Newer builds may also support native installer flows and `claude install`. Point the user at the official setup docs and verify the result with `claude doctor` rather than assuming one installer path is universal.
