import importlib.util
import json
import os
import tempfile
from pathlib import Path
import sys
import unittest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "tester_targeted_pytest_runner.py"
SPEC = importlib.util.spec_from_file_location("tester_targeted_pytest_runner", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def make_env(root: Path) -> Path:
    env_path = root / ".env"
    env_path.write_text("FOO=bar\n", encoding="utf-8")
    return env_path


def make_fake_python(root: Path) -> Path:
    path = root / "fake_python.py"
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "args = sys.argv[1:]\n"
        "text = ' '.join(args)\n"
        "if '-m' in args and 'pytest' in args:\n"
        "    if 'users_auth' in text:\n"
        "        print('1 passed in 0.01s')\n"
        "        raise SystemExit(0)\n"
        "    if 'users_ordering' in text:\n"
        "        print('1 failed in 0.01s')\n"
        "        print('AssertionError: ordering mismatch')\n"
        "        raise SystemExit(1)\n"
        "    if 'users_blocked' in text:\n"
        "        print('OperationalError: could not connect to server: Connection refused')\n"
        "        raise SystemExit(1)\n"
        "print('0 passed in 0.00s')\n"
        "raise SystemExit(0)\n",
        encoding="utf-8",
    )
    os.chmod(path, 0o755)
    return path


def build_cfg(root: Path, **overrides):
    return MODULE.RunnerInput(
        worktree_root=root,
        task_identifier=overrides.get("task_identifier", "MYO-167"),
        env_source=overrides.get("env_source", make_env(root)),
        python_bin=overrides.get("python_bin", make_fake_python(root)),
        runs=overrides.get(
            "runs",
            [
                MODULE.RunSpec(name="users_auth", cmd="pytest users_auth -q", required=True),
                MODULE.RunSpec(name="users_ordering", cmd="pytest users_ordering -q", required=True),
            ],
        ),
        db_precheck=overrides.get("db_precheck", MODULE.DbPrecheck(enabled=False, host="127.0.0.1", port=5432)),
        stop_on_blocked=overrides.get("stop_on_blocked", False),
        dry_run=overrides.get("dry_run", False),
        timeout_sec=overrides.get("timeout_sec", None),
    )


class TesterTargetedPytestRunnerTests(unittest.TestCase):
    def test_unit_classification_and_decision(self):
        blocked, sig, cls = MODULE.classify_failure("connection refused")
        self.assertEqual((blocked, sig, cls), ("blocked", "db_unreachable", "db_unreachable"))

        fail, sig2, cls2 = MODULE.classify_failure("AssertionError: boom")
        self.assertEqual((fail, sig2, cls2), ("fail", "test_failure", "test_failure"))

        runs = [
            MODULE.RunResult("a", True, "pass", 0, 1, "", "", None, None, "cmd", None),
            MODULE.RunResult("b", True, "fail", 1, 1, "", "", "test_failure", None, "cmd", None),
        ]
        decision, blocker = MODULE.derive_decision(runs, None)
        self.assertEqual(decision, "needs_dev_fix")
        self.assertEqual(blocker, "test_failure")

    def test_integration_two_run_mixed_outcomes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = build_cfg(root)
            out = MODULE.execute(cfg)
            self.assertTrue(out["ok"])
            self.assertEqual(out["decision_hint"], "needs_dev_fix")
            self.assertEqual([item["result"] for item in out["runs"]], ["pass", "fail"])
            self.assertEqual(out["blocker_class"], "test_failure")

    def test_failure_missing_env_file_and_missing_python_bin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing_env = root / "missing.env"
            cfg = build_cfg(root, env_source=missing_env)
            out = MODULE.execute(cfg)
            self.assertFalse(out["ok"])
            self.assertEqual(out["decision_hint"], "blocked")
            self.assertEqual(out["blocker_class"], "missing_env")

            env_path = make_env(root)
            cfg2 = build_cfg(root, env_source=env_path, python_bin=root / "no_python")
            out2 = MODULE.execute(cfg2)
            self.assertFalse(out2["ok"])
            self.assertEqual(out2["blocker_class"], "missing_env")

    def test_failure_db_unavailable_classification_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = build_cfg(
                root,
                runs=[MODULE.RunSpec(name="users_auth", cmd="pytest users_auth -q", required=True)],
                db_precheck=MODULE.DbPrecheck(enabled=True, host="127.0.0.1", port=65530),
                stop_on_blocked=True,
            )
            out = MODULE.execute(cfg)
            self.assertFalse(out["ok"])
            self.assertEqual(out["decision_hint"], "blocked")
            self.assertEqual(out["blocker_class"], "db_unreachable")
            self.assertEqual(out["runs"], [])

    def test_timeout_run_classifies_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env_path = make_env(root)
            pybin = Path(sys.executable)
            cfg = build_cfg(
                root,
                env_source=env_path,
                python_bin=pybin,
                runs=[
                    MODULE.RunSpec(
                        name="timeout_case",
                        cmd="python -c \"import time; time.sleep(0.2)\"",
                        required=True,
                        timeout_sec=0.01,
                    )
                ],
                timeout_sec=0.05,
            )
            out = MODULE.execute(cfg)
            self.assertFalse(out["ok"])
            self.assertEqual(out["decision_hint"], "blocked")
            self.assertEqual(out["runs"][0]["result"], "blocked")
            self.assertEqual(out["runs"][0]["signature"], "timeout")

    def test_contract_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = build_cfg(root, dry_run=True)
            out = MODULE.execute(cfg)
            required = {
                "ok",
                "tool",
                "task_identifier",
                "decision_hint",
                "runs",
                "blocker_class",
                "host_rerun_commands",
                "warnings",
                "errors",
            }
            self.assertTrue(required.issubset(set(out.keys())))
            run_required = {"name", "result", "exit_code", "duration_ms", "summary", "snippet", "signature", "timeout_sec"}
            self.assertTrue(run_required.issubset(set(out["runs"][0].keys())))


if __name__ == "__main__":
    unittest.main()
