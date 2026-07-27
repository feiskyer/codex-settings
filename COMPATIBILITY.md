# 兼容性策略

## 支持模式

当前稳定发布线为 `v1.1.0`，目标是当前稳定版 Codex CLI。模型提供商 API、模型标识符、实验性功能开关和浏览器集成都可能独立变化，因此每个 Pull Request 都应使用当时安装的稳定版 Codex CLI 验证其修改范围。

默认安装文档不固定 Git ref，直接跟随仓库默认分支获取最新版本；发布检查点仍使用不可变的语义化版本标签。Git 标签使用 `v<version>`，并与 `.codex-plugin/plugin.json` 中不带 `v` 的版本保持一致，例如 Git `v1.1.0` 对应 Plugin `1.1.0`。

## 兼容性要求

- `config.toml` 和根目录下的 `*.config.toml` Profiles 应通过变更所使用稳定版 Codex CLI 的严格配置校验。
- Skills 应遵循当前的 `SKILL.md` 和 `agents/openai.yaml` 结构，并能在支持 Skills 的 Codex 产品形态中使用。
- Codex Plugin 应直接复用根 `skills/`，manifest 和 marketplace 通过结构校验，并在相关变更时使用当前稳定版 Codex CLI 完成隔离安装测试。
- 发布的 Plugin 内容发生变化时必须更新 manifest 版本；相同版本不保证绕过本地 Plugin 缓存。
- Python、Shell 和 JavaScript 脚本应在对应 Skill 中说明非标准前置依赖，并提供无需凭据即可执行的 `--help` 或语法检查方式。
- 外部模型名称、MCP 服务、浏览器 DOM 选择器和模型提供商认证流程属于兼容性边界，不视为永久稳定接口。
- 从 Custom Prompts 迁移的工作流应以 Skills 形式维护，不再保留重复的 `prompts/` 副本。

## `v1.1.0` 迁移说明

- `prompts/github-issue-fixer.md` 已迁移为 `skills/github-fix-issue/`。
- `prompts/github-pr-reviewer.md` 已迁移为 `skills/github-review-pr/`。
- 两个 GitHub Skills 默认只执行用户已授权的本地分析或修改；创建分支、提交、push、创建 PR、发布 review 或批准 PR 需要明确授权。

## 破坏性变更

以下情况属于需要明确说明的兼容性变更：

- 删除或重命名 Profile 或 Skill
- 改变所需凭据或认证方式
- 扩大默认权限或网络访问范围
- 改变输出文件格式
- 删除已经文档化的命令行参数

此类变更应在 Commit 或 Pull Request 中明确标注，并提供迁移说明。
