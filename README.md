# Codex CLI 配置与 Skills

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

这是一个面向 [OpenAI Codex CLI](https://developers.openai.com/codex/cli/) 的个人配置仓库，包含常用配置、Skills、MCP 示例和命令规则。

仓库里的配置主要服务于作者自己的开发环境，但也可以按需选取。使用前请先看清楚模型提供商、权限和外部依赖，不要直接把真实密钥提交到仓库。

## 仓库包含什么

- Codex 主配置和多个模型提供商示例。
- 一组可直接安装的 Skills，覆盖需求梳理、深度调研、图像生成、字幕提取和任务交接等场景。
- LiteLLM、MCP 和命令规则示例。
- 两个历史 Custom Prompts，保留作为迁移到 Skills 的参考。

相关项目：[Claude Code Settings](https://github.com/feiskyer/claude-code-settings)

## 安装

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

如需保留其他模型提供商和 LiteLLM 示例，一并复制：

```bash
mkdir -p ~/.codex/configs
cp -R ~/codex-settings/configs/. ~/.codex/configs/
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

将 Codex 切换到对应配置：

```bash
cp ~/.codex/configs/github-copilot.toml ~/.codex/config.toml
```

在一个终端中启动 LiteLLM：

```bash
litellm --config ~/.codex/litellm_config.yaml
```

确认 LiteLLM 使用的 GitHub Copilot 提供商已经完成认证，然后在另一个终端中启动 Codex：

```bash
codex doctor --summary
codex mcp list
codex
```

这种方式由 LiteLLM 和它所连接的 GitHub Copilot 提供商处理上游认证，不需要运行 `codex login`。

</details>

<details>
<summary><strong>使用 ChatGPT</strong></summary>

将 Codex 切换到 ChatGPT 配置：

```bash
cp ~/.codex/configs/chatgpt.toml ~/.codex/config.toml
```

登录 ChatGPT 账号并启动 Codex：

```bash
codex login
codex doctor --summary
codex mcp list
codex
```

这种方式直接使用 Codex 的 ChatGPT 登录状态，不需要启动本地代理或网关。

</details>

## 目录结构

```text
.
├── config.toml                 # 默认配置：本地 copilot-gateway
├── configs/                    # 其他模型提供商配置
├── litellm_config.yaml         # GitHub Copilot/LiteLLM 示例
├── skills/                     # Codex Skills 及其脚本和参考资料
├── prompts/                    # 历史 Custom Prompts
├── policy/                     # 旧格式的命令规则示例
└── LICENSE                     # MIT License
```

## 配置说明

### 默认配置

根目录的 [config.toml](config.toml) 当前使用：

- 模型：`gpt-5.5`
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
| [configs/chatgpt.toml](configs/chatgpt.toml) | 使用 OpenAI/ChatGPT 账号 | 运行 `codex login`，并确认配置中的模型仍对当前账号开放 |
| [configs/azure.toml](configs/azure.toml) | Azure OpenAI | 填写实例地址和 API Key，确认部署名称与接口兼容性 |
| [configs/github-copilot.toml](configs/github-copilot.toml) | 通过 LiteLLM 使用 GitHub Copilot | 先启动 `litellm_config.yaml`，再检查账号可用模型 |
| [configs/openrouter.toml](configs/openrouter.toml) | OpenRouter | 填写 API Key，并确认目标模型支持当前调用方式 |

模型名称和功能开关会随 Codex 与上游服务更新。遇到无法识别的配置项时，可以运行：

```bash
codex features list
codex doctor --summary
```

### Profiles

当前 Codex 通过独立文件加载 Profile：

```text
~/.codex/<name>.config.toml
```

例如，`codex --profile work` 会在基础配置之上叠加 `~/.codex/work.config.toml`。Profile 不会自动清除基础配置中的模型提供商、权限或 MCP 设置，使用前要检查继承结果。

### LiteLLM

[litellm_config.yaml](litellm_config.yaml) 与 [configs/github-copilot.toml](configs/github-copilot.toml) 配套，默认监听 `http://localhost:4000`。它和根目录配置使用的 `localhost:4141` 不是同一个网关。

```bash
python3 -m pip install -U 'litellm[proxy]'
litellm --config ~/.codex/litellm_config.yaml
```

### MCP

默认配置会通过 `npx` 启动 Chrome DevTools MCP；部分备用配置还引用 Context7 或 Claude Code MCP。启用前请确认相关命令已经安装，并检查它们可以访问哪些文件和网络资源。

团队环境中建议固定 npm 包版本，不要长期依赖 `@latest`。

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

## 历史 Prompts 和规则文件

`prompts/` 中保留了两个旧版 Custom Prompts。Codex 已不再推荐这种方式，新工作流应优先写成 Skill。

`policy/` 中的 `.codexpolicy` 文件也采用旧命名。当前 Codex 从 `~/.codex/rules/*.rules` 或受信任项目中的 `.codex/rules/*.rules` 加载规则。迁移前请逐行检查内容，再把需要的文件复制并改为 `.rules` 后缀。

```bash
mkdir -p ~/.codex/rules
cp ~/.codex/policy/default.codexpolicy ~/.codex/rules/default.rules
```

规则只能控制命令审批，不能替代沙箱或操作系统权限隔离。

## 开发和检查

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
- [Codex Skills](https://developers.openai.com/codex/skills)
- [Codex Rules](https://developers.openai.com/codex/rules)
- [Codex GitHub 仓库](https://github.com/openai/codex)
- [LiteLLM 文档](https://docs.litellm.ai/)

## 许可证

本项目采用 [MIT License](LICENSE)。
