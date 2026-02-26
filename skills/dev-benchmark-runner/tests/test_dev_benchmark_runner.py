import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "dev_benchmark_runner.py"
SPEC = importlib.util.spec_from_file_location("dev_benchmark_runner", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FakeRunner(MODULE.CommandRunner):
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def run(self, cmd, cwd):
        self.calls.append((cmd, cwd))
        if self.responses:
            return self.responses.pop(0)
        return MODULE.CmdResult(1, "", "unexpected call")


class DevBenchmarkRunnerTests(unittest.TestCase):
    def cfg(self, root: Path, script: Path, artifact: Path, **overrides):
        return MODULE.RunnerInput(
            script=script,
            dataset_size=overrides.get("dataset_size", 150),
            iterations=overrides.get("iterations", 12),
            warmup=overrides.get("warmup", 3),
            max_retries=overrides.get("max_retries", 2),
            artifact_path=artifact,
            dry_run=overrides.get("dry_run", False),
            repo_root=root,
        )

    def test_retry_policy_and_output_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "bench.py"
            script.write_text("print('noop')\n", encoding="utf-8")
            artifact = root / "out" / "bench.json"

            transient_fail = MODULE.CmdResult(1, "", "connection reset timeout")
            success = MODULE.CmdResult(
                0,
                json.dumps(
                    {
                        "metrics": {"p50_ms": 10.0, "p95_ms": 20.0, "mean_ms": 12.0},
                        "comparison": {"minimal_vs_tasks_percent_improvement": 15.5},
                    }
                ),
                "",
            )
            runner = FakeRunner([transient_fail, success])

            out = MODULE.execute(self.cfg(root, script, artifact, max_retries=2), runner=runner)
            self.assertTrue(out["ok"])
            self.assertEqual(out["attempts"], 2)
            self.assertEqual(out["tool"], "dev-benchmark-runner")
            self.assertIn("metrics", out)
            self.assertIn("comparison", out)
            self.assertTrue(any(w["code"] == "retry_transient_failure" for w in out["warnings"]))

    def test_integration_sample_script_and_artifact_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "bench_sample.py"
            script.write_text(
                """
import argparse, json
p=argparse.ArgumentParser()
p.add_argument('--dataset-size', type=int)
p.add_argument('--iterations', type=int)
p.add_argument('--warmup', type=int)
p.add_argument('--json', action='store_true')
a=p.parse_args()
print(json.dumps({
  "metrics": {"p50_ms": 5.5, "p95_ms": 9.1, "mean_ms": 6.8},
  "comparison": {"minimal_vs_tasks_percent_improvement": 11.0},
  "inputs": {"dataset_size": a.dataset_size, "iterations": a.iterations, "warmup": a.warmup}
}))
""".strip()
                + "\n",
                encoding="utf-8",
            )
            artifact = root / "reports" / "evidence" / "bench.json"

            out = MODULE.execute(self.cfg(root, script, artifact), runner=MODULE.CommandRunner())
            self.assertTrue(out["ok"])
            self.assertTrue(artifact.exists())

            art = json.loads(artifact.read_text(encoding="utf-8"))
            self.assertEqual(art["schema_version"], "1.0")
            self.assertEqual(art["tool"], "dev-benchmark-runner")
            self.assertIn("metrics", art)
            self.assertIn("comparison", art)
            self.assertIn("input", art)

    def test_failure_missing_script_dependency(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = type(
                "Args",
                (),
                {
                    "input_json": None,
                    "script": str(root / "missing.py"),
                    "dataset_size": 10,
                    "iterations": 2,
                    "warmup": 0,
                    "max_retries": 1,
                    "artifact_path": str(root / "a.json"),
                    "repo_root": str(root),
                    "dry_run": False,
                },
            )
            with self.assertRaises(MODULE.ToolError) as ctx:
                MODULE.parse_input(args)
            self.assertEqual(ctx.exception.code, "env")

    def test_failure_path_script_error_class(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "bench.py"
            script.write_text("print('noop')\n", encoding="utf-8")
            artifact = root / "x" / "a.json"

            failure = MODULE.CmdResult(1, "", "ValueError: unsupported benchmark mode")
            runner = FakeRunner([failure])
            out = MODULE.execute(self.cfg(root, script, artifact, max_retries=0), runner=runner)
            self.assertFalse(out["ok"])
            self.assertEqual(out["errors"][0]["code"], "script")

    def test_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "bench.py"
            script.write_text("print('noop')\n", encoding="utf-8")
            artifact = root / "a.json"
            out = MODULE.execute(self.cfg(root, script, artifact, dry_run=True), runner=FakeRunner([]))
            self.assertTrue(out["ok"])
            self.assertEqual(out["attempts"], 0)
            self.assertTrue(any(w["code"] == "dry_run" for w in out["warnings"]))


if __name__ == "__main__":
    unittest.main()
