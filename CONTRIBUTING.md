# 贡献指南

感谢你参与改进这个 Codex 配置与 Skills 仓库。

## 开始之前

1. 阅读 `AGENTS.md`，了解当前仓库结构、开发约定和验证命令。
2. 每次变更只聚焦一个模型提供商、Skill、工作流或文档问题。
3. 如果提案会改变默认权限、认证方式、模型提供商行为，或同时影响多个 Skill 的公开接口，请先创建 Issue 讨论。

## 开发要求

- 不要把真实凭据或用户本地运行状态提交到仓库。
- 对重复、脆弱或需要确定性执行的逻辑，应在 Skill 的 `scripts/` 目录中提供脚本，不要要求 Agent 每次临时生成。
- 为脚本、解析器、参数处理、文件行为和常见失败路径，在 `skills/<name>/tests/` 下添加离线测试。
- `SKILL.md` 只保留 Skill 触发后 Agent 真正需要的核心流程；较长的参考资料应放在 `references/` 中。
- 当 Skill 的用途、显示名称或默认调用方式发生变化时，同步更新 `agents/openai.yaml`。

## 验证

按改动选择检查，不需要为文案修改运行无关的模型服务或 API：

1. 解析所有修改过的 TOML 文件。
2. 对每个修改过的 Skill 运行 `quick_validate.py`。
3. 对修改过的脚本运行语法检查和离线测试。
4. 确认命令行脚本无需凭据也能显示 `--help`。
5. 提交前运行 `git diff --check`。

不要仅为了满足 Pull Request 检查而调用真实付费 API。如果确实需要集成测试，应使用权限最小的凭据、清理日志中的敏感信息，并记录可复现的人工步骤，但不要公开任何密钥。

### 配置、Skills 与 Plugin 结构

```bash
# TOML syntax (config changes)
python3 -c 'import pathlib, tomllib; [tomllib.loads(p.read_text()) for p in pathlib.Path(".").glob("**/*.toml")]'

# Plugin package and marketplace
python3 -m json.tool .codex-plugin/plugin.json >/dev/null
python3 -m json.tool .agents/plugins/marketplace.json >/dev/null
python3 ~/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .

# Skill structure (use only changed directories for a local edit)
for skill in skills/*; do
  test ! -f "$skill/SKILL.md" || \
    python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py "$skill"
done

git diff --check
```

Skills、manifest、marketplace 或 Plugin 安装脚本变化时，用已安装的稳定版 Codex CLI 运行 `bash scripts/test-plugin-install.sh`。它在工作树 `.tmp/` 下创建临时目录和隔离的 `CODEX_HOME`，验证安装、内容一致性和卸载，再清理夹具；不会更新用户已安装的 Plugin。

### 可执行脚本与离线测试

以下是全部命令；局部修改只运行对应脚本和测试目录。测试不需要网络、凭据或生产系统访问，允许在当前任务内修复本次改动导致的失败并重跑。

```bash
python3 -m compileall -q skills
ruff check skills
for test_dir in skills/*/tests; do
  test ! -d "$test_dir" || python3 -m unittest discover -s "$test_dir" -v
done

bash -n skills/brainstorming/scripts/start-server.sh \
  skills/brainstorming/scripts/stop-server.sh \
  scripts/test-plugin-install.sh \
  scripts/update-codex-plugins.sh \
  scripts/test-update-codex-plugins.sh
bash scripts/test-update-codex-plugins.sh
node --check skills/brainstorming/scripts/server.cjs
node --check skills/brainstorming/scripts/helper.js
```

结构检查不能证明提示词效果。修改触发条件、授权边界或完成条件时，用代表性请求检查是否选对 Skill、是否保留用户范围、是否在必要验证前过早停止；区分人工走查和真实模型运行。没有模型对照测试时，不声称行为效果已被实测证明。

### 仅在对应 Provider 配置变化时运行

- 严格配置：相关 Provider 可用时运行 `CODEX_HOME="$PWD" codex --strict-config exec --ephemeral --sandbox read-only --skip-git-repo-check -c mcp_servers.chrome.enabled=false -c web_search="disabled" "Reply exactly OK"`。
- 默认网关：确认 `copilot-gateway` 可用后运行 `codex` 或 `codex doctor --summary`。
- LiteLLM：相关服务可用后运行 `codex --profile github-copilot`。
- ChatGPT：已认证时运行 `codex --profile chatgpt`。

缺少 CLI、依赖、认证或运行中的服务时，报告具体缺口；只有当前任务已授权相应环境变更时才安装、登录或调整服务。

## Pull Request 要求

Pull Request 应包含：

- 问题与解决方案的简要说明
- 受影响的配置或 Skills
- 已执行的自动化和人工验证
- 有意跳过的集成测试及原因
- 对安全、权限或兼容性的影响

不要混入无关格式化、个人配置或其他工作区修改。

## 兼容性与发布

`main` 是滚动更新分支，目标是当前稳定版 Codex CLI。完整支持策略见 `COMPATIBILITY.md`。如果变更会主动放弃兼容性或改变公开工作流，应在 Pull Request 和发布说明中明确指出。
