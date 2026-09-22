---
name: claude-skill
description: Delegate a task to the Claude Code CLI, typically a headless `claude -p` run. Use when the user wants the work executed through Claude Code rather than answered inline.
---

# Claude Code Headless Mode

Build and run `claude` commands for work that should be executed through Claude Code itself.

| Reference | Read it when |
|-----------|--------------|
| [references/flags-and-permissions.md](references/flags-and-permissions.md) | The command needs more than `-p` — permission modes, tool scoping, output formats, flag inventory, installation |
| [references/examples.md](references/examples.md) | You want a worked command for a specific shape of task (read-only analysis, safe edit run, JSON report, resume, MCP, sandboxed unattended run) |

Requires the `claude` CLI installed and authenticated on the target machine.

## Core rules

- **`claude --help` on the target machine is the compatibility floor.** CLI flags and permission-rule syntax move faster than docs and copied examples, and they differ between builds. Verify any uncommon flag there before emitting it.
- **Do not add `--model`** unless the user asked for an override or the workflow must pin a model for reproducibility. The user's configured model is the right default.
- **Prefer `--append-system-prompt` over `--system-prompt`** unless replacing Claude Code's default behavior is the point.
- **Choose the least-permissive mode that still fits the task.** `acceptEdits` is the usual starting point for coding automation. For a truly unattended run, reach for explicit permission rules or `dontAsk` first; `bypassPermissions` is only for an already-isolated environment.

## Verify before advising

```bash
claude --version
claude auth status --text
claude --help          # and `claude doctor` if the install looks off
```

## Basic shape

```bash
claude -p "summarize the repository architecture"
claude -p "review the auth layer for risks" --output-format json
```

Everything else is a matter of scoping tools and permissions around that — see the references.

## When to pause

Only when one of these is materially unclear: the user needs a specific model or provider behavior that requires pinning; they asked for a fully unattended run in an environment that is not clearly sandboxed; or the workflow depends on a feature not visible in `claude --help`. Otherwise give the best current command.

## What to return

The exact command or sequence, a one-line note that the user's configured model is used by default, any permission or isolation caveat, and the resume command if the workflow is meant to continue later.
