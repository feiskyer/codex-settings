# Codex CLI 配置与 Skills

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

一套开箱即用的 [Codex CLI](https://developers.openai.com/codex/cli/) 工作台，集成多模型 Profiles、可复用 Skills 与 [Chrome DevTools MCP](https://github.com/ChromeDevTools/chrome-devtools-mcp)。

仓库采用面向个人开发效率的默认配置；你可以整套使用，也可以按需选取 Profiles 或 Skills。使用前请确认模型提供商、权限和外部依赖，并避免提交真实密钥。

## 为什么用这套配置

如果你想少花时间调配置，多花时间完成真正的开发工作，这个仓库提供了一套可以直接运行、也可以自由组合的 Codex CLI 工作台。

- **灵活切换模型**：预置 [copilot-gateway](https://www.npmjs.com/package/copilot-gateway)、ChatGPT、Azure OpenAI、OpenRouter 和 [LiteLLM](https://docs.litellm.ai/)/GitHub Copilot Profiles。
- **复用成熟工作流**：通过 Skills 完成需求梳理、深度调研、图像生成、字幕提取和任务交接。
- **连接真实开发环境**：通过 Chrome DevTools MCP 调试网页、检查性能并执行浏览器自动化。
- **整套或按需使用**：既可以作为完整的 Codex Home，也可以只复制需要的 Profile 或 Skill。

> 本项目面向 Codex CLI；Claude Code 的配置、Skills 与 Agents 请查看 [Claude Code Settings](https://github.com/feiskyer/claude-code-settings)。

## 快速开始

### 1. 安装 Codex CLI

使用 npm 安装：

```bash
npm install -g @openai/codex
```

也可以参考 [Codex CLI 官方文档](https://developers.openai.com/codex/cli/) 选择其他安装方式。

### 2. 首次安装：直接克隆到 `~/.codex`

如果本机还没有 `~/.codex`，最简单的方式是直接把仓库克隆到 Codex 的用户配置目录：

```bash
git clone https://github.com/feiskyer/codex-settings.git ~/.codex
```

这样根目录的 `config.toml` 会成为默认配置，`skills/` 下的内容也会被 Codex 自动发现。

<details>
<summary><strong>如果 ~/.codex 已经存在：保留原目录并手动合并</strong></summary>

先把仓库克隆到其他目录。下面使用 `~/codex-settings`，你也可以换成其他位置：

```bash
git clone https://github.com/feiskyer/codex-settings.git ~/codex-settings
```

复制配置前，先备份现有文件：

```bash
test ! -f ~/.codex/config.toml || \
  cp ~/.codex/config.toml ~/.codex/config.toml.bak

# 使用仓库默认配置
cp ~/codex-settings/config.toml ~/.codex/config.toml
```

如需保留其他模型提供商的 Profiles 和 LiteLLM 示例，一并复制：

```bash
cp ~/codex-settings/*.config.toml ~/.codex/
cp ~/codex-settings/litellm_config.yaml ~/.codex/litellm_config.yaml
```

然后安装仓库中的 Skills：

```bash
mkdir -p ~/.codex/skills
cp -R ~/codex-settings/skills/. ~/.codex/skills/
```

完成合并后，继续按照下方说明选择一种认证方式。

</details>

### 3. 选择认证方式

下面三种方式任选其一。仓库默认使用 `copilot-gateway`，因为根目录的 `config.toml` 已经按该方式配置。

#### copilot-gateway（默认）

根目录的 [config.toml](config.toml) 已指向：

```text
http://localhost:4141
```

先在一个终端中启动 `copilot-gateway`：

```bash
npx copilot-gateway@latest start --proxy-env
```

保持网关进程运行。确认它已经监听 `localhost:4141` 后，在另一个终端中启动 Codex：

```bash
codex doctor --summary
codex mcp list
codex
```

这种方式由 `copilot-gateway` 负责上游认证，不需要运行 `codex login`。仓库只提供 Codex 配置，不包含 `copilot-gateway` 的安装和启动脚本。

<details>
<summary><strong>使用 LiteLLM</strong></summary>

LiteLLM 使用 [litellm_config.yaml](litellm_config.yaml)，默认监听 `http://localhost:4000`。先安装 LiteLLM：

```bash
python3 -m pip install -U 'litellm[proxy]'
```

在一个终端中启动 LiteLLM：

```bash
litellm --config ~/.codex/litellm_config.yaml
```

确认 LiteLLM 使用的 GitHub Copilot 提供商已经完成认证，然后在另一个终端中启动 Codex：

```bash
codex doctor --summary
codex mcp list
codex --profile github-copilot
```

这种方式由 LiteLLM 和它所连接的 GitHub Copilot 提供商处理上游认证，不需要运行 `codex login`。

</details>

<details>
<summary><strong>使用 ChatGPT</strong></summary>

登录 ChatGPT 账号并启动 Codex：

```bash
codex login
codex doctor --summary
codex mcp list
codex --profile chatgpt
```

这种方式直接使用 Codex 的 ChatGPT 登录状态，不需要启动本地代理或网关。

</details>

## 常见问题

### 1. Codex CLI 应该如何安装？

优先按照 [Codex CLI 官方文档](https://developers.openai.com/codex/cli/) 选择当前平台支持的安装方式；也可以使用 `npm install -g @openai/codex`。本仓库不提供 Codex 或 Windows 安装包。安装后运行 `codex --version` 和 `codex doctor --summary` 检查是否完整，不要把 ChatGPT 应用和 Codex CLI 当成同一个安装包。

### 2. 为什么 Codex 会连接 `localhost:4141`？需要执行 `codex login` 吗？

本仓库默认使用 [copilot-gateway](https://www.npmjs.com/package/copilot-gateway)，请求会发送到 `http://localhost:4141`，因此需要先运行：

```bash
npx copilot-gateway@latest start --proxy-env
```

该模式由网关处理上游认证，不需要执行 `codex login`，也不是 OpenAI 官方的 GitHub Copilot 登录方式。

### 3. ChatGPT 登录、API Key 和第三方 Provider 有什么区别？

`codex login` 使用 ChatGPT 登录，并消耗 ChatGPT 工作区或订阅提供的 Codex 用量；API Key 使用 OpenAI Platform 的独立 API 计费。第三方 Provider 使用自己的端点、凭据和计费规则，不会自动继承 ChatGPT 订阅或 OpenAI API 权限。本仓库默认 `copilot-gateway` 的上游认证由网关负责。

### 4. 如何切换 Profile 或模型？

使用 `--profile` 切换仓库提供的模型配置，使用 `--model` 临时指定模型：

```bash
codex --profile chatgpt
codex --profile azure
codex --profile openrouter
codex --model <MODEL>
```

模型必须被当前 Provider、部署和账号权限支持；可用 `codex debug models` 查看 Codex 当前识别的模型。本仓库填写的默认模型不保证在所有 Provider 中都可用。

### 5. Reconnecting、请求错误或一直思考怎么排查？

先运行：

```bash
codex --version
codex login status
codex doctor --summary
```

默认配置还应确认 `copilot-gateway` 正在监听 `localhost:4141`；LiteLLM Profile 则检查 `localhost:4000`。如果只有 MCP 异常，再运行 `codex mcp list --json`。

### 6. Skills 如何安装和调用？为什么没有显示？

将仓库克隆到 `~/.codex` 时，仓库中的 Skills 会位于 `~/.codex/skills`；也可以按照前面的步骤单独复制。可通过 `/skills` 或 `$skill-name` 显式调用。未识别时，请检查 Skill 目录中是否包含有效的 `SKILL.md`，并确认当前 Codex 版本支持 Skills。

### 7. Chrome DevTools MCP 会自动连接吗？

默认配置会通过 `npx` 启动最新版 Chrome DevTools MCP，并请求自动连接本机 Chrome，但是否成功仍取决于 Chrome 和本机调试环境。可以运行：

```bash
codex mcp list --json
codex mcp get chrome --json
```

所有 Profiles 都会继承基础配置中的 Chrome DevTools MCP。

### 8. 为什么额度很快用完？ChatGPT 和 API Key 共用额度吗？

ChatGPT 登录使用计划包含的 Codex 用量及可能购买的 ChatGPT credits；API Key 使用 OpenAI Platform 的独立 API 计费，两者不共用额度。消耗速度会受模型、推理强度、上下文长度和任务类型影响，本仓库不承诺固定可用时长。第三方 Provider 的额度和重置规则以对应服务为准。

### 9. 可以切换到 Kimi、MiniMax、DeepSeek 或 GLM-5.2 吗？

可以。本仓库在 [litellm_config.yaml](litellm_config.yaml) 末尾提供了默认注释的 Kimi K3、MiniMax-M3、DeepSeek-V4-Pro 和 GLM-5.2 配置示例。设置对应的 `MOONSHOT_API_KEY`、`MINIMAX_API_KEY`、`DEEPSEEK_API_KEY` 或 `ZAI_API_KEY`，取消所需模型段落的注释，启动 LiteLLM 后运行：

```bash
codex --profile github-copilot --model <MODEL>
```

这里继续复用 `github-copilot` Profile 指向的 `localhost:4000` LiteLLM 网关；Profile 名称不会限制实际使用的上游模型。LiteLLM 会把 Codex 的 Responses API 请求桥接到对应 Provider，但不同模型的工具调用、推理和多模态能力可能不同，启用后应先执行最小任务验证。

### 10. 本仓库的默认权限是什么？

默认配置使用 `approval_policy = "never"` 和 `sandbox_mode = "danger-full-access"`，这是本仓库有意采用的效率优先设置：Codex 可以不经命令批准、在无沙箱限制下执行操作。请只在信任的代码仓库和本机环境中使用；安装第三方 Provider、Skill 或 MCP 前，应检查其网络访问、凭据处理和数据政策。如需更严格的权限，可以参考后面的“默认配置”章节调整。

## 目录结构

```text
.
├── config.toml                 # 默认配置：本地 copilot-gateway
├── *.config.toml               # 可叠加到主配置的模型提供商 Profiles
├── litellm_config.yaml         # GitHub Copilot/LiteLLM 示例
├── skills/                     # Codex Skills 及其脚本和参考资料
├── CONTRIBUTING.md             # 贡献流程和验证要求
├── SECURITY.md                 # 安全问题报告策略
├── COMPATIBILITY.md            # 兼容性和版本支持策略
└── LICENSE                     # MIT License
```

## 配置说明

### 默认配置

根目录的 [config.toml](config.toml) 当前使用：

- 模型：`gpt-5.6-sol`
- 模型提供商：`github`
- 本地网关：`http://localhost:4141`
- Web Search：`live`
- MCP：Chrome DevTools MCP
- 审批策略：`never`
- 沙箱模式：`danger-full-access`

如果不需要完全开放的本地权限，建议至少改成：

```toml
approval_policy = "on-request"
sandbox_mode = "workspace-write"

[sandbox_workspace_write]
network_access = false
```

### 其他配置

| 文件 | 适用场景 | 使用前需要做什么 |
| --- | --- | --- |
| [chatgpt.config.toml](chatgpt.config.toml) | 使用 OpenAI/ChatGPT 账号 | 运行 `codex login`，再使用 `codex --profile chatgpt` |
| [azure.config.toml](azure.config.toml) | Azure OpenAI | 填写项目地址，设置 `AZURE_OPENAI_API_KEY`，再使用 `codex --profile azure` |
| [github-copilot.config.toml](github-copilot.config.toml) | 通过 LiteLLM 使用 GitHub Copilot | 先启动 `litellm_config.yaml`，再使用 `codex --profile github-copilot` |
| [openrouter.config.toml](openrouter.config.toml) | OpenRouter | 设置 `OPENROUTER_API_KEY`，再使用 `codex --profile openrouter` |

各 Profile 当前默认使用 `gpt-5.6-sol`，实际可用性取决于模型提供商和账号权限。如遇模型不可用，请替换为对应提供商支持的模型标识符。遇到无法识别的配置项时，可以运行：

```bash
codex features list
codex doctor --summary
```

### Profiles

当前 Codex 通过独立文件加载 Profile：

```text
~/.codex/<name>.config.toml
```

例如，`codex --profile chatgpt` 会在基础配置之上叠加 `~/.codex/chatgpt.config.toml`。本仓库的 Profile 文件只覆盖模型、模型提供商和认证信息；权限、Features、MCP、TUI 等共享设置继续由 `config.toml` 提供。

### LiteLLM

当前 Codex 自定义模型提供商只接受 `wire_api = "responses"`。LiteLLM 可以作为兼容层，将 GitHub Copilot 等第三方模型提供商的 Chat Completions 等接口封装为 Responses API，从而供 Codex 使用。

[litellm_config.yaml](litellm_config.yaml) 与 [github-copilot.config.toml](github-copilot.config.toml) 配套，默认监听 `http://localhost:4000`。它和根目录配置使用的 `localhost:4141` 不是同一个网关。

```bash
python3 -m pip install -U 'litellm[proxy]'
litellm --config ~/.codex/litellm_config.yaml
```

### MCP

默认配置通过 `npx` 启动最新版 Chrome DevTools MCP，并自动连接本机 Chrome。所有 Profiles 共享该 MCP 配置。

## Skills（技能）

| 名称 | 用途 | 依赖或注意事项 |
| --- | --- | --- |
| [brainstorming](skills/brainstorming/) | 实现前梳理需求、比较方案并形成设计文档 | 可视化伴侣需要 Node.js、浏览器和本机端口权限 |
| [claude-skill](skills/claude-skill/) | 把任务交给 Claude Code CLI 执行 | 需要安装并登录 `claude` CLI |
| [deep-research](skills/deep-research/) | 并行执行深度调研并汇总为完整报告 | 需要 Codex CLI；联网和 MCP 权限按任务配置 |
| [gpt-image-skill](skills/gpt-image-skill/) | 使用 OpenAI Image API 生成或编辑图片 | 需要 Python、`OPENAI_API_KEY` 和对应依赖 |
| [grill-me](skills/grill-me/) | 逐项追问方案，并维护术语表和 ADR | 会在项目中写入设计与决策文档 |
| [handoff](skills/handoff/) | 把当前会话整理成下一位 Agent 可直接接手的交接文档 | 交接文件写入系统临时目录 |
| [nanobanana-skill](skills/nanobanana-skill/) | 使用 Gemini 图像模型生成或编辑图片 | 需要 Python、`GEMINI_API_KEY` 和对应依赖 |
| [youtube-transcribe-skill](skills/youtube-transcribe-skill/) | 提取 YouTube 字幕或转录文本 | 需要 `yt-dlp`，或使用 Chrome DevTools MCP 作为备用方案 |

显式调用示例：

```text
$brainstorming 帮我把这个产品想法整理成可执行的设计
$grill-me 逐项挑战一下这份技术方案
$handoff 把当前进度整理成交接文档
$gpt-image-skill 生成一张产品发布海报
```

### 图像技能依赖

建议使用独立虚拟环境安装 Python 依赖：

```bash
python3 -m venv ~/.codex/.venv
source ~/.codex/.venv/bin/activate
python -m pip install -r ~/.codex/skills/gpt-image-skill/requirements.txt
python -m pip install -r ~/.codex/skills/nanobanana-skill/requirements.txt
```

API Key 应保存在本地环境变量或 Skill 指定的私有环境文件中，不要写进仓库。

## 开发和检查

在仓库根目录开发时，可以把当前 clone 目录临时设为 `CODEX_HOME`：

```bash
cd /path/to/codex-settings
export CODEX_HOME="$(pwd)"
```

该设置只对当前终端会话生效。此后根目录的 `config.toml`、`*.config.toml` 和 `skills/` 会作为当前 Codex Home 使用。

修改配置或 Skill 后，建议运行：

```bash
# 检查 TOML 语法
python3 -c 'import pathlib, tomllib; [tomllib.loads(p.read_text()) for p in pathlib.Path(".").glob("**/*.toml")]'

# 检查 Codex 配置、认证、MCP 和网络状态
codex doctor --summary

# 查看当前版本支持的功能开关
codex features list

# 查看 MCP 配置
codex mcp list
```

新增或修改脚本时，还要检查 `--help`、最小可用示例和常见失败路径。测试外部 API 时使用最小权限凭据，并清理日志中的敏感信息。

## 安全提醒

- 不要提交 API Key、访问令牌、Cookie、真实 Authorization Header 或包含隐私信息的日志。
- 不要在不可信项目中直接使用 `danger-full-access`、`approval_policy = "never"` 或过于宽泛的 allow 规则。
- 安装 Skill、MCP 服务或第三方依赖前，先阅读源码并确认网络访问范围。
- 使用第三方模型提供商时，确认代码和提示词的保存、处理和合规政策。
- 如需报告安全问题，优先使用 GitHub 的私密漏洞报告功能；如果仓库没有启用，请先通过维护者的 GitHub 主页联系，不要在公开 Issue 中披露细节或凭据。

## 贡献

欢迎通过 [Issues](https://github.com/feiskyer/codex-settings/issues) 和 [Pull Requests](https://github.com/feiskyer/codex-settings/pulls) 提交改进。

完整流程见 [CONTRIBUTING.md](CONTRIBUTING.md)，安全问题请按 [SECURITY.md](SECURITY.md) 私下报告，版本与兼容性边界见 [COMPATIBILITY.md](COMPATIBILITY.md)。

提交前请确认：

1. 没有包含真实密钥、个人配置或敏感日志。
2. 新配置使用清晰的占位符，并说明前置条件。
3. 新 Skill 使用 kebab-case 目录名，且 `SKILL.md` 包含准确的 `name` 和 `description`。
4. 新脚本说明依赖、输入、输出和失败行为。
5. README、命令示例和实际目录结构保持一致。
6. 已完成与改动相匹配的本地检查，并在 PR 中记录结果。

## 参考资料

- [Codex CLI 官方文档](https://developers.openai.com/codex/cli/)
- [Codex 配置说明](https://developers.openai.com/codex/config-basic)
- [Codex 配置参考](https://developers.openai.com/codex/config-reference)
- [Codex Skills](https://developers.openai.com/codex/skills)
- [Codex GitHub 仓库](https://github.com/openai/codex)
- [LiteLLM 文档](https://docs.litellm.ai/)

## 许可证

本项目采用 [MIT License](LICENSE)。
