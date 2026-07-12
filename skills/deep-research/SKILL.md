---
name: deep-research
description: '深度调研的多实例（多 Agent）编排工作流：把一个调研目标拆成可并行子目标，用 Codex CLI 子进程采集和分析证据，再聚合、核验并精修为完整报告。用于系统性网页或资料调研、竞品与行业分析、批量链接或数据集分片、长文证据整合，以及用户提及深度调研、Deep Research、Wide Research、多 Agent 并行调研或多进程调研的场景。'
---

# Deep Research

把深度调研作为可重复、可审计的生产流程执行。主控负责目标澄清、样本摸底、子任务设计、结果核验和最终综合；子进程负责边界清晰的采集或局部分析。

## 核心约束

1. 保持用户当前模型和推理配置，不传 `--model`，不覆盖无关配置。
2. 子进程默认使用 `workspace-write`；只有确实需要 shell 网络访问时才启用 runner 的 `--network`。
3. 先检查当前会话可用的 Skills、连接器和 MCP，再按来源适配能力；不要假设固定服务或工具名存在。
4. 不使用 `--dangerously-bypass-approvals-and-sandbox`。
5. 所有运行产物写入独立的 `.research/<name>/` 目录。
6. 在开始批量执行前向用户展示拆分方案；需要明显成本、长时间运行或外部系统访问时，等待明确同意。

## Bundled scripts

先解析当前 Skill 的绝对目录并记为 `<skill-dir>`。

- `scripts/run_children.py`：跨平台并行执行 `codex exec`，负责超时、重试、日志和结果状态。
- `scripts/aggregate.py`：按 manifest 顺序聚合成功的子报告，缺失或空结果时失败。

两个脚本都使用 Python 标准库，不生成临时 shell 脚本。

## Workflow

### 1. 澄清与摸底

明确目标、受众、时间范围、来源边界、评价标准和最终格式。通过当前可用工具获取少量真实样本，记录代表性来源和缺口，避免只凭经验拆分。

### 2. 创建运行目录

使用不重复的语义化名称，例如：

```text
.research/20260712-codex-skills-a3f2/
├── prompts/
├── logs/
├── child_outputs/
├── raw/
├── cache/
└── manifest.json
```

把网页原文、数据和解析结果缓存到 `raw/` 或 `cache/`，避免重复抓取。

### 3. 设计子任务

每个子任务只负责一个明确边界，Prompt 至少包含：

1. 子目标、输入和允许访问的范围
2. 输出结构和证据要求
3. 失败时必须说明原因，不得编造结果
4. 输出自然语言 Markdown，并把来源链接放在对应结论附近

将 Prompt 分别写入 `prompts/`，然后创建 manifest：

```json
{
  "tasks": [
    {
      "id": "market-history",
      "title": "市场历史",
      "prompt_file": "prompts/market-history.md"
    },
    {
      "id": "current-competitors",
      "title": "当前竞品",
      "prompt_file": "prompts/current-competitors.md"
    }
  ]
}
```

`id` 只能包含字母、数字、点、下划线和短横线。Prompt 必须位于本次运行目录内。

### 4. 预检和执行

先预览命令，不启动 Codex 子进程：

```bash
python3 "<skill-dir>/scripts/run_children.py" \
  --run-dir ".research/<name>" \
  --workspace "$PWD" \
  --dry-run
```

检查 manifest 和 Prompt 后执行：

```bash
python3 "<skill-dir>/scripts/run_children.py" \
  --run-dir ".research/<name>" \
  --workspace "$PWD" \
  --parallel 8 \
  --timeout 600 \
  --retries 1
```

只有子任务必须通过 shell 直接联网时才添加 `--network`。根据任务成本调整并发和超时，先用 1–2 个子任务验证链路，再扩大并发。

Runner 固定输出：

- `child_outputs/<id>.md`
- `logs/<id>.log`
- `results.json`

### 5. 核验和失败处理

读取 `results.json`，检查失败、超时、空输出和引用缺失。只重试失败的边界任务；不要因为单个失败重新运行所有成功任务。需要改变模型、权限或来源范围时先说明原因。

### 6. 聚合原始材料

```bash
python3 "<skill-dir>/scripts/aggregate.py" \
  --run-dir ".research/<name>"
```

默认生成 `aggregated_raw.md`。该文件只是按 manifest 顺序整理的内部材料，不是最终报告。

### 7. 综合与精修

通读子报告和关键原始来源，先设计章节大纲和素材映射，再分章节写入 `polished_report.md`。处理重复信息、来源冲突和证据强弱；验证关键数据和引用，不能把子报告简单拼接后直接交付。

### 8. 交付

最终回复提供：

1. 成品报告绝对路径
2. 关键结论和可执行建议摘要
3. 未解决的证据缺口或失败子任务
4. 是否启用了额外网络权限或其他例外

不要把内部 Prompt、调度日志或完整中间稿当作成品发送给用户。
