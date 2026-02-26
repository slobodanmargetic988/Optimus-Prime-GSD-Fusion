import importlib.util
import sys
import tempfile
from pathlib import Path
import unittest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "dev_check_bundle.py"
SPEC = importlib.util.spec_from_file_location("dev_check_bundle", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def cfg(root: Path, **overrides):
    checks = overrides.get(
        "checks",
        [
            {"name": "compileall", "cmd": f"{sys.executable} -c \"print('ok')\""},
        ],
    )
    return MODULE.BundleInput(
        task_identifier=overrides.get("task_identifier", "MYO-163"),
        checks=[
            MODULE.CheckSpec(
                name=item["name"],
                cmd=item["cmd"],
                timeout_sec=item.get("timeout_sec"),
            )
            for item in checks
        ],
        stop_on_fail=overrides.get("stop_on_fail", False),
        max_parallel=overrides.get("max_parallel", 1),
        dry_run=overrides.get("dry_run", False),
        repo_root=root,
        timeout_sec=overrides.get("timeout_sec"),
    )


class DevCheckBundleTests(unittest.TestCase):
    def test_overall_verdict_derivation_unit(self):
        pass_only = [MODULE.CheckResult("a", "pass", 0, 1, "")]
        with_fail = [MODULE.CheckResult("a", "pass", 0, 1, ""), MODULE.CheckResult("b", "fail", 1, 1, "")]
        with_blocked = [MODULE.CheckResult("a", "pass", 0, 1, ""), MODULE.CheckResult("b", "blocked", None, 1, "")]

        self.assertEqual(MODULE.derive_overall(pass_only), "pass")
        self.assertEqual(MODULE.derive_overall(with_fail), "fail")
        self.assertEqual(MODULE.derive_overall(with_blocked), "blocked")

    def test_integration_mixed_pass_fail_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checks = [
                {"name": "compileall", "cmd": f"{sys.executable} -c \"print('compile-ok')\""},
                {"name": "pytest", "cmd": f"{sys.executable} -c \"import sys; print('pytest-fail'); sys.exit(3)\""},
                {"name": "benchmark", "cmd": f"{sys.executable} -c \"print('benchmark-ok')\""},
            ]
            out = MODULE.run_checks(cfg(root, checks=checks), runner=MODULE.CommandRunner())

            self.assertFalse(out["ok"])
            self.assertEqual(out["overall"], "fail")
            self.assertEqual([c["result"] for c in out["checks"]], ["pass", "fail", "pass"])
            self.assertEqual(out["checks"][1]["exit_code"], 3)

    def test_stop_on_fail_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checks = [
                {"name": "pytest", "cmd": f"{sys.executable} -c \"import sys; sys.exit(2)\""},
                {"name": "benchmark", "cmd": f"{sys.executable} -c \"print('should-not-run')\""},
            ]
            out = MODULE.run_checks(cfg(root, checks=checks, stop_on_fail=True), runner=MODULE.CommandRunner())

            self.assertEqual(len(out["checks"]), 1)
            self.assertEqual(out["checks"][0]["name"], "pytest")
            warning_codes = {w["code"] for w in out["warnings"]}
            self.assertIn("stop_on_fail_triggered", warning_codes)

    def test_timeout_and_blocked_handling(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checks = [
                {
                    "name": "slow",
                    "cmd": f"{sys.executable} -c \"import time; time.sleep(0.5)\"",
                    "timeout_sec": 0.05,
                }
            ]
            out = MODULE.run_checks(cfg(root, checks=checks), runner=MODULE.CommandRunner())

            self.assertFalse(out["ok"])
            self.assertEqual(out["overall"], "blocked")
            self.assertEqual(out["checks"][0]["result"], "blocked")
            self.assertEqual(len(out["blockers"]), 1)

    def test_missing_command_marks_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checks = [{"name": "missing", "cmd": "cmd_that_should_not_exist_12345"}]
            out = MODULE.run_checks(cfg(root, checks=checks), runner=MODULE.CommandRunner())

            self.assertFalse(out["ok"])
            self.assertEqual(out["overall"], "blocked")
            self.assertEqual(out["checks"][0]["result"], "blocked")
            self.assertIn("Command not found", out["checks"][0]["snippet"])

    def test_output_contract_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = MODULE.run_checks(cfg(root, dry_run=True), runner=MODULE.CommandRunner())
            required = {
                "ok",
                "schema_version",
                "tool",
                "tool_version",
                "task_identifier",
                "overall",
                "checks",
                "blockers",
                "warnings",
                "errors",
            }
            self.assertTrue(required.issubset(set(out.keys())))
            check_required = {"name", "result", "exit_code", "duration_ms", "snippet"}
            self.assertTrue(check_required.issubset(set(out["checks"][0].keys())))


if __name__ == "__main__":
    unittest.main()
