# Codex 子任务运行与恢复

准备执行子任务时读取。`<skill-dir>` 是包含 `SKILL.md` 的绝对目录，不是当前工作目录。

## 运行目录与 manifest

选择不重复的 `.research/<name>/`，保存 `manifest.json`、`prompts/`、`logs/`、`child_outputs/`；只在需要缓存来源时创建 `raw/` 或 `cache/`。

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

`id` 只能包含字母、数字、点、下划线和短横线，且不可重复；Prompt 路径必须位于运行目录内。每份 Prompt 写清子目标、输入、授权范围、输出要求及证据缺口的报告方式。

## 预检与执行

不熟悉的批次、自动生成的 Prompt 或高成本任务先预检；`--dry-run` 校验本地输入并打印命令，不启动 Codex：

```bash
python3 "<skill-dir>/scripts/run_children.py" \
  --run-dir ".research/<name>" --workspace "$PWD" --dry-run
```

下列并发、超时只是示例，按已授权任务和预算调整；不必为了填满并发数拆出无用任务：

```bash
python3 "<skill-dir>/scripts/run_children.py" \
  --run-dir ".research/<name>" --workspace "$PWD" \
  --parallel 2 --timeout 600 --retries 0
```

Runner 保持当前模型配置，运行 `codex exec`，使用 `workspace-write` 沙箱，不绕过审批。`--network` 仅控制子进程的 shell 网络访问，确有需要且已授权时才添加；它不授予访问任意外部系统的权限。

输出包括 `child_outputs/<id>.md`、`logs/<id>.log` 和 `results.json`。退出码、结果状态和文件非空都不能代替对内容及引用的核验。

## 有限重试与恢复

Runner 的 `--retries` 会重试进程失败或空输出，但不会识别权限拒绝与其他失败的区别。默认保持零次自动重试；确认失败可重试且没有重复副作用后，再选择有限次数。

`--resume-existing` 只检查输出是否非空，不检查它是否来自失败进程或内容是否合格。先读旧 `results.json` 和现有输出，备份诊断材料；需要重跑的任务使用只包含这些任务的重试 manifest，通过 `--manifest` 传入，不带 `--resume-existing`。Runner 会覆盖同名任务的输出、日志及 `results.json`，不要把部分重跑的状态误当成整批状态。

保留原始完整 manifest 用于最终核对和聚合：

```bash
python3 "<skill-dir>/scripts/aggregate.py" \
  --run-dir ".research/<name>"
```

聚合器按 manifest 顺序生成 `aggregated_raw.md`，只检查子报告存在且非空，不读取 `results.json`，也不验证引用。主控须先确认所有必需子任务的实际结果；聚合成功不代表研究已完成。
