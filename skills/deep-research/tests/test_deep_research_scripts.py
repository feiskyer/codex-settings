import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock


SKILL_DIR = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load_module("run_children", SKILL_DIR / "scripts" / "run_children.py")
aggregate = load_module("aggregate", SKILL_DIR / "scripts" / "aggregate.py")


def create_run_dir(root, tasks):
    run_dir = Path(root) / "run"
    (run_dir / "prompts").mkdir(parents=True)
    manifest_tasks = []
    for task_id, title in tasks:
        prompt_path = run_dir / "prompts" / f"{task_id}.md"
        prompt_path.write_text(f"Research {title}", encoding="utf-8")
        manifest_tasks.append(
            {
                "id": task_id,
                "title": title,
                "prompt_file": f"prompts/{task_id}.md",
            }
        )
    (run_dir / "manifest.json").write_text(
        json.dumps({"tasks": manifest_tasks}),
        encoding="utf-8",
    )
    return run_dir


class ManifestTests(unittest.TestCase):
    def test_prompt_path_cannot_escape_run_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "run"
            run_dir.mkdir()
            outside = Path(temp_dir) / "outside.md"
            outside.write_text("secret", encoding="utf-8")
            manifest = run_dir / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "id": "escape",
                                "prompt_file": "../outside.md",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "inside the run directory"):
                runner.load_manifest(manifest, run_dir.resolve())


class RunnerTests(unittest.TestCase):
    def test_dry_run_builds_scoped_command_without_model_override(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = create_run_dir(temp_dir, [("one", "One")])
            args = runner.parse_args(
                [
                    "--run-dir",
                    str(run_dir),
                    "--workspace",
                    temp_dir,
                    "--codex-bin",
                    "codex-test",
                    "--network",
                    "--dry-run",
                ]
            )
            results = runner.run(args)
            command = results[0]["command"]

            self.assertIn("workspace-write", command)
            self.assertIn("sandbox_workspace_write.network_access=true", command)
            self.assertNotIn("--model", command)

    def test_runner_records_success_and_writes_results(self):
        def fake_run(command, **_kwargs):
            output_path = Path(command[command.index("--output-last-message") + 1])
            output_path.write_text("# Child result\n", encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="child log")

        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = create_run_dir(temp_dir, [("one", "One")])
            args = runner.parse_args(
                [
                    "--run-dir",
                    str(run_dir),
                    "--workspace",
                    temp_dir,
                    "--parallel",
                    "1",
                ]
            )
            with mock.patch.object(runner, "resolve_codex", return_value="codex"):
                with mock.patch.object(
                    runner.subprocess,
                    "run",
                    side_effect=fake_run,
                ):
                    results = runner.run(args)

            self.assertEqual(results[0]["status"], "success")
            self.assertTrue((run_dir / "results.json").is_file())
            self.assertIn("child log", (run_dir / "logs" / "one.log").read_text())


class AggregateTests(unittest.TestCase):
    def test_aggregate_preserves_manifest_order(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = create_run_dir(
                temp_dir,
                [("first", "First title"), ("second", "Second title")],
            )
            output_dir = run_dir / "child_outputs"
            output_dir.mkdir()
            (output_dir / "first.md").write_text("First body", encoding="utf-8")
            (output_dir / "second.md").write_text("Second body", encoding="utf-8")

            args = aggregate.parse_args(["--run-dir", str(run_dir)])
            output_path = aggregate.run(args)
            content = output_path.read_text(encoding="utf-8")

            self.assertLess(content.index("First title"), content.index("Second title"))

    def test_aggregate_rejects_missing_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = create_run_dir(temp_dir, [("missing", "Missing")])
            args = aggregate.parse_args(["--run-dir", str(run_dir)])

            with self.assertRaisesRegex(RuntimeError, "missing or empty"):
                aggregate.run(args)


if __name__ == "__main__":
    unittest.main()
