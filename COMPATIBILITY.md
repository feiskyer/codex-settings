# 兼容性策略

## 支持模式

`main` 分支采用滚动更新模式，目标是当前稳定版 Codex CLI。模型提供商 API、模型标识符、实验性功能开关和浏览器集成都可能独立变化，因此每个 Pull Request 都应使用当时安装的稳定版 Codex CLI 验证其修改范围。

在项目发布第一个正式版本之前，`main` 是唯一受支持的版本线。未来发布版本时，应使用语义化版本标签，并在发布说明中记录已验证的 Codex CLI 版本和模型提供商相关假设。

## 兼容性要求

- `config.toml` 和根目录下的 `*.config.toml` Profiles 应通过变更所使用稳定版 Codex CLI 的严格配置校验。
- Skills 应遵循当前的 `SKILL.md` 和 `agents/openai.yaml` 结构，并能在支持 Skills 的 Codex 产品形态中使用。
- Python、Shell 和 JavaScript 脚本应在对应 Skill 中说明非标准前置依赖，并提供无需凭据即可执行的 `--help` 或语法检查方式。
- 外部模型名称、MCP 服务、浏览器 DOM 选择器和模型提供商认证流程属于兼容性边界，不视为永久稳定接口。
- `prompts/` 下的历史文件仅作为迁移参考，不属于当前主动支持的 Skill 接口。

## 破坏性变更

以下情况属于需要明确说明的兼容性变更：

- 删除或重命名 Profile 或 Skill
- 改变所需凭据或认证方式
- 扩大默认权限或网络访问范围
- 改变输出文件格式
- 删除已经文档化的命令行参数

此类变更应在 Commit 或 Pull Request 中明确标注，并提供迁移说明。
