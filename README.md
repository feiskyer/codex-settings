# OpenAI Codex CLI Settings and Custom Prompts

A curated collection of configurations, skills and custom prompts for [OpenAI Codex CLI](https://github.com/openai/codex), designed to enhance your development workflow with various model providers and reusable prompt templates.

> For Claude Code settings, skills, agents and custom commands, please refer [feiskyer/claude-code-settings](https://github.com/feiskyer/claude-code-settings).

## Overview

This repository provides:

- **Flexible Configuration**: Support for multiple model providers (LiteLLM/Copilot proxy, ChatGPT subscription, Azure OpenAI, OpenRouter, ModelScope, Kimi)
- **Custom Prompts**: Reusable prompt templates for common development tasks
- **Skills (Experimental)**: Discoverable instruction bundles for specialized tasks (image generation, YouTube transcription, spec-driven workflows)
- **Best Practices**: Pre-configured settings optimized for development workflows
- **Easy Setup**: Simple installation and configuration process

## Quick Start

### Installation

```bash
# Backup existing Codex configuration (if any)
mv ~/.codex ~/.codex.bak

# Clone this repository to ~/.codex
git clone https://github.com/feiskyer/codex-settings.git ~/.codex

# Or symlink if you prefer to keep it elsewhere
ln -s /path/to/codex-settings ~/.codex
```

### Basic Configuration

The default `config.toml` uses LiteLLM as a gateway. To use it:

1. Install LiteLLM and Codex CLI:

   ```bash
   pip install -U 'litellm[proxy]'
   npm install -g @openai/codex
   ```

1. Create a LiteLLM config file (full example [litellm_config.yaml](litellm_config.yaml)):

   ```yaml
   general_settings:
     master_key: sk-dummy
   litellm_settings:
     drop_params: true
   model_list:
   - model_name: gpt-5
     litellm_params:
       model: github_copilot/gpt-5
       extra_headers:
         editor-version: "vscode/1.104.3"
         editor-plugin-version: "copilot-chat/0.26.7"
         Copilot-Integration-Id: "vscode-chat"
         user-agent: "GitHubCopilotChat/0.26.7"
         x-github-api-version: "2025-04-01"
   ```

1. Start LiteLLM proxy:

   ```bash
   litellm --config ~/.codex/litellm_config.yaml
   # Runs on http://localhost:4000 by default
   ```

1. Run Codex:

   ```bash
   codex
   ```

## Configuration Files

### Main Configuration

- [config.toml](config.toml): Default configuration using LiteLLM gateway
  - Model: `gpt-5` via `model_provider = "github"` (Copilot proxy on `http://localhost:4000`)
  - Approval policy: `on-request`; reasoning summary: `detailed`; reasoning effort: `high`; raw agent reasoning visible
  - MCP servers: `claude` (local), `exa` (hosted), `chrome` (DevTools over `npx`)

### Alternative Configurations

Located in `configs/` directory:

- [OpenAI ChatGPT](configs/chatgpt.toml): Use ChatGPT subscription provider
- [Azure OpenAI](configs/azure.toml): Use Azure OpenAI service provider
- [Github Copilot](configs/github-copilot.toml): Use Github Copilot via LiteLLM proxy
- [OpenRouter](configs/openrouter.toml): Use OpenRouter provider
- [Model Scope](configs/modelscope.toml): Use ModelScope provider
- [Kimi](configs/kimi.toml): Use Moonshot Kimi provider

To use an alternative config:

```bash
# Take ChatGPT for example
cp ~/.codex/configs/chatgpt.toml ~/.codex/config.toml
codex
```

## Custom Prompts

Custom prompts are stored in the `prompts/` directory. Access them via the `/prompts:` slash menu in Codex.

- `/prompts:deep-reflector` - Analyze development sessions to extract learnings, patterns, and improvements for future interactions.
- `/prompts:insight-documenter [breakthrough]` - Capture and document significant technical breakthroughs into reusable knowledge assets.
- `/prompts:instruction-reflector` - Analyze and improve Codex instructions in AGENTS.md based on conversation history.
- `/prompts:github-issue-fixer [issue-number]` - Systematically analyze, plan, and implement fixes for GitHub issues with PR creation.
- `/prompts:github-pr-reviewer [pr-number]` - Perform thorough GitHub pull request code analysis and review.
- `/prompts:ui-engineer [requirements]` - Create production-ready frontend solutions with modern UI/UX standards.
- `/prompts:prompt-creator [requirements]` - Create Codex custom prompts with proper structure and best practices.

### Creating Custom Prompts

1. Create a new `.md` file in `~/.codex/prompts/`
2. Use argument placeholders:
   - `$1` to `$9`: Positional arguments
   - `$ARGUMENTS`: All arguments joined by spaces
   - `$$`: Literal dollar sign
3. Restart Codex to load new prompts

## Skills (Experimental)

Skills are reusable instruction bundles that Codex automatically discovers at startup. Each skill has a name, description, and detailed instructions stored on disk. Codex injects only metadata (name, description, path) into context - the body stays on disk until needed.

### How to Use Skills

Skills are automatically loaded when Codex starts. To use a skill:

1. **List all skills**: Use the `/skills` command to see all available skills

   ```text
   /skills
   ```

2. **Invoke a skill**: Use `$<skill-name> [prompt]` to invoke a skill with an optional prompt

   ```text
   $kiro-skill Create a feature spec for user authentication
   $nanobanana-skill Generate an image of a sunset over mountains
   ```

Skills are stored in `~/.codex/skills/**/SKILL.md`. Only files named exactly `SKILL.md` are recognized.

### Available Skills

<details>
<summary>claude-skill - Handoff task to Claude Code CLI</summary>

#### [claude-skill](skills/claude-skill)

Non-interactive automation mode for hands-off task execution using Claude Code. Use when you want to leverage Claude Code to implement features or review code.

**Key Features:**

- Multiple permission modes (default, acceptEdits, plan, bypassPermissions)
- Autonomous execution without approval prompts
- Streaming progress updates
- Structured final summaries

**Requirements:** Claude Code CLI installed (`npm install -g @anthropic-ai/claude-code`)

</details>

<details>
<summary>autonomous-skill - Long-running task automation</summary>

#### [autonomous-skill](skills/autonomous-skill)

Execute complex, long-running tasks across multiple sessions using a dual-agent pattern (Initializer + Executor) with automatic session continuation.

> Warning: workflows may pause when Codex requests permissions. Treat this as experimental; expect to babysit early runs and keep iterating on approvals/sandbox settings.

**Key Features:**

- Dual-agent pattern (Initializer creates task list, Executor completes tasks)
- Auto-continuation across sessions with progress tracking
- Task isolation with per-task directories (`.autonomous/<task-name>/`)
- Progress persistence via `task_list.md` and `progress.md`
- Non-interactive mode execution

**Usage:**

```bash
# Start a new autonomous task
~/.codex/skills/autonomous-skill/scripts/run-session.sh "Build a REST API for todo app"

# Continue an existing task
~/.codex/skills/autonomous-skill/scripts/run-session.sh --task-name build-rest-api-todo --continue

# List all tasks
~/.codex/skills/autonomous-skill/scripts/run-session.sh --list
```

</details>

<details>
<summary>nanobanana-skill - Image generation with Gemini</summary>

#### [nanobanana-skill](skills/nanobanana-skill)

Generate or edit images using Google Gemini API via nanobanana. Use when creating, generating, or editing images.

**Key Features:**

- Image generation with various aspect ratios (square, portrait, landscape, ultra-wide)
- Image editing capabilities
- Multiple model options (gemini-3-pro-image-preview, gemini-2.5-flash-image)
- Resolution options (1K, 2K, 4K)

**Requirements:**

- `GEMINI_API_KEY` configured in `~/.nanobanana.env`
- Python3 with google-genai, Pillow, python-dotenv

</details>

<details>
<summary>youtube-transcribe-skill - Extract YouTube subtitles</summary>

#### [youtube-transcribe-skill](skills/youtube-transcribe-skill)

Extract subtitles/transcripts from a YouTube video URL and save as a local file.

**Key Features:**

- Dual extraction methods: CLI (`yt-dlp`) and Browser Automation (fallback)
- Automatic subtitle language selection (zh-Hans, zh-Hant, en)
- Cookie handling for age-restricted content
- Saves transcripts to local text files

**Requirements:**

- `yt-dlp` (for CLI method), or
- Browser automation MCP server (for fallback method)

</details>

<details>
<summary>kiro-skill - Interactive feature development</summary>

#### [kiro-skill](skills/kiro-skill)

Interactive feature development workflow from idea to implementation. Creates requirements (EARS format), design documents, and implementation task lists.

**Triggered by:** "kiro" or references to `.kiro/specs/` directory

**Workflow:**

1. **Requirements** → Define what needs to be built (EARS format with user stories)
2. **Design** → Determine how to build it (architecture, components, data models)
3. **Tasks** → Create actionable implementation steps (test-driven, incremental)
4. **Execute** → Implement tasks one at a time

**Storage:** Creates files in `.kiro/specs/{feature-name}/` directory

</details>

<details>
<summary>spec-kit-skill - Constitution-based development</summary>

#### [spec-kit-skill](skills/spec-kit-skill)

GitHub Spec-Kit integration for constitution-based spec-driven development.

**Triggered by:** "spec-kit", "speckit", "constitution", "specify", or references to `.specify/` directory

**Prerequisites:**

```bash
# Install spec-kit CLI
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git

# Initialize project
specify init . --ai codex
```

**7-Phase Workflow:**

1. **Constitution** → Establish governing principles
2. **Specify** → Define functional requirements
3. **Clarify** → Resolve ambiguities (max 5 questions)
4. **Plan** → Create technical strategy
5. **Tasks** → Generate dependency-ordered tasks
6. **Analyze** → Validate consistency (read-only)
7. **Implement** → Execute implementation

</details>

## Configuration Options

### Approval Policies

- `untrusted`: Prompt for untrusted commands (recommended)
- `on-failure`: Only prompt when sandbox commands fail
- `on-request`: Model decides when to ask
- `never`: Auto-approve all commands (use with caution)

### Sandbox Modes

- `read-only`: Can read files, no writes or network
- `workspace-write`: Can write to workspace, network configurable
- `danger-full-access`: Full system access (use in containers only)

### Reasoning Settings

For reasoning-capable models (o3, gpt-5):

- **Effort**: `minimal`, `low`, `medium`, `high`
- **Summary**: `auto`, `concise`, `detailed`, `none`

### Shell Environment

Control which environment variables are passed to subprocesses:

```toml
[shell_environment_policy]
inherit = "all"  # all, core, none
exclude = ["AWS_*", "AZURE_*"]  # Exclude patterns
set = { CI = "1" }  # Force-set values
```

## Advanced Features

### Profiles

Define multiple configuration profiles:

```toml
[profiles.openrouter]
model = "gpt-5"
model_reasoning_effort = "high"
approval_policy = "on-request"
sandbox_mode = "workspace-write"
model_provider = "openrouter"

[profiles.github]
model = "gpt-5"
model_reasoning_effort = "high"
approval_policy = "on-request"
sandbox_mode = "workspace-write"
model_provider = "github"

[model_providers.github]
name     = "OpenAI"
base_url = "http://localhost:4000"
http_headers = { "Authorization"= "Bearer sk-dummy"}
wire_api = "chat"

[model_providers.openrouter]
name     = "OpenRouter"
base_url = "https://openrouter.ai/api/v1"
http_headers = { "Authorization"= "Bearer [YOUR-API-KEY]"}
wire_api = "chat"
```

Use with: `codex --profile openrouter`

### MCP Servers

Extend Codex with Model Context Protocol servers:

```toml
[mcp_servers.context7]
command = "npx"
args = ["-y", "@upstash/context7-mcp@latest"]
```

## Project Documentation

Codex automatically reads `AGENTS.md` files in your project to understand context. Please always create one in your project root with `/init` command on your first codex run.

## References

- [Codex CLI Official Docs](https://developers.openai.com/codex/cli/)
- [Codex GitHub Repository](https://github.com/openai/codex)
- [LiteLLM Documentation](https://docs.litellm.ai/)

## Contributing

Contributions welcome! Feel free to:

- Add new custom prompts
- Share alternative configurations
- Improve documentation
- Report issues and suggest features

## LICENSE

This project is released under MIT License - See [LICENSE](LICENSE) for details.
