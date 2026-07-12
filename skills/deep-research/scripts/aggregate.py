#!/usr/bin/env python3
"""Aggregate manifest-ordered Codex child reports into an internal raw draft."""

import argparse
import json
from pathlib import Path
import re
import sys


TASK_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Aggregate deep-research child outputs in manifest order"
    )
    parser.add_argument("--run-dir", required=True)
    parser.add_argument(
        "--manifest",
        default=None,
        help="Manifest path (default: <run-dir>/manifest.json)",
    )
    parser.add_argument(
        "--output",
        default="aggregated_raw.md",
        help="Output path relative to run directory (default: aggregated_raw.md)",
    )
    return parser.parse_args(argv)


def resolve_within(base_dir, relative_path, label):
    candidate = (base_dir / relative_path).resolve()
    try:
        candidate.relative_to(base_dir)
    except ValueError as exc:
        raise ValueError(f"{label} must stay inside the run directory") from exc
    return candidate


def load_tasks(manifest_path):
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw_tasks = payload.get("tasks") if isinstance(payload, dict) else payload
    if not isinstance(raw_tasks, list) or not raw_tasks:
        raise ValueError("manifest must contain a non-empty tasks list")

    tasks = []
    for raw_task in raw_tasks:
        task_id = str(raw_task.get("id") or "")
        if not TASK_ID_RE.fullmatch(task_id):
            raise ValueError(f"invalid task id: {task_id!r}")
        tasks.append(
            {
                "id": task_id,
                "title": str(raw_task.get("title") or task_id),
            }
        )
    return tasks


def aggregate(run_dir, manifest_path, output_path):
    tasks = load_tasks(manifest_path)
    sections = ["# Aggregated Research Materials", ""]
    missing = []

    for task in tasks:
        child_path = resolve_within(
            run_dir,
            Path("child_outputs") / f"{task['id']}.md",
            "child output",
        )
        if not child_path.is_file():
            missing.append(task["id"])
            continue
        content = child_path.read_text(encoding="utf-8").strip()
        if not content:
            missing.append(task["id"])
            continue
        sections.extend([f"## {task['title']}", "", content, ""])

    if missing:
        raise RuntimeError("missing or empty child outputs: " + ", ".join(missing))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(sections).rstrip() + "\n", encoding="utf-8")
    return output_path


def run(args):
    run_dir = Path(args.run_dir).expanduser().resolve()
    if not run_dir.is_dir():
        raise FileNotFoundError(f"run directory not found: {run_dir}")
    manifest_path = (
        Path(args.manifest).expanduser().resolve()
        if args.manifest
        else run_dir / "manifest.json"
    )
    output_path = resolve_within(run_dir, Path(args.output), "output")
    return aggregate(run_dir, manifest_path, output_path)


def main(argv=None):
    try:
        output_path = run(parse_args(argv))
        print(output_path)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
