#!/usr/bin/env python3
"""Run manifest-defined Codex research tasks concurrently without a shell."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import time


TASK_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def positive_int(value):
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def nonnegative_int(value):
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return parsed


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Run Codex research child tasks from a JSON manifest"
    )
    parser.add_argument("--run-dir", required=True, help="Research run directory")
    parser.add_argument(
        "--manifest",
        default=None,
        help="Manifest path (default: <run-dir>/manifest.json)",
    )
    parser.add_argument(
        "--workspace",
        default=".",
        help="Workspace passed to Codex with -C (default: current directory)",
    )
    parser.add_argument("--parallel", type=positive_int, default=8)
    parser.add_argument("--timeout", type=positive_int, default=600)
    parser.add_argument("--retries", type=nonnegative_int, default=0)
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument(
        "--network",
        action="store_true",
        help="Allow shell network access inside workspace-write sandboxes",
    )
    parser.add_argument(
        "--resume-existing",
        action="store_true",
        help="Skip tasks whose non-empty child output already exists",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print commands without starting Codex",
    )
    return parser.parse_args(argv)


def resolve_within(base_dir, relative_path, label):
    """Resolve a relative path and reject traversal outside the run directory."""
    candidate = (base_dir / relative_path).resolve()
    try:
        candidate.relative_to(base_dir)
    except ValueError as exc:
        raise ValueError(f"{label} must stay inside the run directory") from exc
    return candidate


def load_manifest(manifest_path, run_dir):
    """Load and validate ordered task definitions."""
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw_tasks = payload.get("tasks") if isinstance(payload, dict) else payload
    if not isinstance(raw_tasks, list) or not raw_tasks:
        raise ValueError("manifest must contain a non-empty tasks list")

    tasks = []
    seen_ids = set()
    for index, raw_task in enumerate(raw_tasks):
        if not isinstance(raw_task, dict):
            raise ValueError(f"task {index} must be an object")
        task_id = str(raw_task.get("id") or "")
        if not TASK_ID_RE.fullmatch(task_id):
            raise ValueError(f"invalid task id: {task_id!r}")
        if task_id in seen_ids:
            raise ValueError(f"duplicate task id: {task_id}")
        seen_ids.add(task_id)

        prompt_value = raw_task.get("prompt_file")
        if not isinstance(prompt_value, str) or not prompt_value:
            raise ValueError(f"task {task_id} is missing prompt_file")
        prompt_path = resolve_within(run_dir, Path(prompt_value), "prompt_file")
        if not prompt_path.is_file():
            raise FileNotFoundError(f"prompt file not found: {prompt_path}")

        tasks.append(
            {
                "id": task_id,
                "title": str(raw_task.get("title") or task_id),
                "prompt_path": prompt_path,
                "output_path": resolve_within(
                    run_dir,
                    Path("child_outputs") / f"{task_id}.md",
                    "child output",
                ),
                "log_path": resolve_within(
                    run_dir,
                    Path("logs") / f"{task_id}.log",
                    "task log",
                ),
            }
        )
    return tasks


def resolve_codex(command):
    """Resolve a Codex executable name or explicit path."""
    if Path(command).parent != Path("."):
        path = Path(command).expanduser()
        if path.is_file():
            return str(path.resolve())
        return None
    return shutil.which(command)


def build_command(args, codex_bin, output_path, workspace):
    """Build a least-privilege Codex command for one child task."""
    command = [
        codex_bin,
        "exec",
        "--full-auto",
        "--sandbox",
        "workspace-write",
        "--ephemeral",
        "--color",
        "never",
        "-C",
        str(workspace),
        "--output-last-message",
        str(output_path),
    ]
    if args.network:
        command.extend(["-c", "sandbox_workspace_write.network_access=true"])
    command.append("-")
    return command


def append_log(log_path, text):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(text)
        if not text.endswith("\n"):
            log_file.write("\n")


def run_task(task, args, codex_bin, workspace):
    """Run one task with bounded retries and return a serializable result."""
    output_path = task["output_path"]
    log_path = task["log_path"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    if args.resume_existing and output_path.is_file() and output_path.stat().st_size:
        return {"id": task["id"], "status": "skipped", "attempts": 0}

    command = build_command(args, codex_bin, output_path, workspace)
    prompt = task["prompt_path"].read_text(encoding="utf-8")
    started = time.monotonic()
    last_error = ""

    log_path.write_text(
        f"command: {shlex.join(command)}\n",
        encoding="utf-8",
    )

    for attempt in range(1, args.retries + 2):
        output_path.unlink(missing_ok=True)
        append_log(log_path, f"\n--- attempt {attempt} ---")
        try:
            completed = subprocess.run(
                command,
                cwd=workspace,
                input=prompt,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=args.timeout,
                check=False,
            )
            append_log(log_path, completed.stdout or "")
            if (
                completed.returncode == 0
                and output_path.is_file()
                and output_path.stat().st_size > 0
            ):
                return {
                    "id": task["id"],
                    "status": "success",
                    "attempts": attempt,
                    "duration_seconds": round(time.monotonic() - started, 3),
                    "output": str(output_path),
                    "log": str(log_path),
                }
            last_error = (
                f"Codex exited {completed.returncode} or produced an empty output"
            )
        except subprocess.TimeoutExpired as exc:
            timeout_output = exc.stdout or ""
            if isinstance(timeout_output, bytes):
                timeout_output = timeout_output.decode("utf-8", errors="replace")
            append_log(log_path, timeout_output)
            last_error = f"timed out after {args.timeout} seconds"
        append_log(log_path, f"error: {last_error}")

    return {
        "id": task["id"],
        "status": "failed",
        "attempts": args.retries + 1,
        "duration_seconds": round(time.monotonic() - started, 3),
        "error": last_error,
        "log": str(log_path),
    }


def write_results(run_dir, results):
    """Atomically write ordered task results."""
    destination = run_dir / "results.json"
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps({"results": results}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)
    return destination


def run(args):
    """Validate the run and execute all manifest tasks."""
    run_dir = Path(args.run_dir).expanduser().resolve()
    workspace = Path(args.workspace).expanduser().resolve()
    if not run_dir.is_dir():
        raise FileNotFoundError(f"run directory not found: {run_dir}")
    if not workspace.is_dir():
        raise FileNotFoundError(f"workspace not found: {workspace}")

    manifest_path = (
        Path(args.manifest).expanduser().resolve()
        if args.manifest
        else run_dir / "manifest.json"
    )
    tasks = load_manifest(manifest_path, run_dir)

    codex_bin = args.codex_bin if args.dry_run else resolve_codex(args.codex_bin)
    if not codex_bin:
        raise RuntimeError(f"Codex executable not found: {args.codex_bin}")

    if args.dry_run:
        return [
            {
                "id": task["id"],
                "command": build_command(
                    args,
                    codex_bin,
                    task["output_path"],
                    workspace,
                ),
            }
            for task in tasks
        ]

    results_by_id = {}
    with ThreadPoolExecutor(max_workers=min(args.parallel, len(tasks))) as executor:
        futures = {
            executor.submit(run_task, task, args, codex_bin, workspace): task["id"]
            for task in tasks
        }
        for future in as_completed(futures):
            task_id = futures[future]
            try:
                results_by_id[task_id] = future.result()
            except Exception as exc:
                results_by_id[task_id] = {
                    "id": task_id,
                    "status": "failed",
                    "attempts": 0,
                    "error": str(exc),
                }

    ordered_results = [results_by_id[task["id"]] for task in tasks]
    write_results(run_dir, ordered_results)
    return ordered_results


def main(argv=None):
    try:
        args = parse_args(argv)
        results = run(args)
        print(json.dumps(results, indent=2, ensure_ascii=False))
        if args.dry_run:
            return 0
        return 0 if all(item["status"] in {"success", "skipped"} for item in results) else 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
