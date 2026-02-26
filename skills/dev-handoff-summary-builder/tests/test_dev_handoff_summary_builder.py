import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "dev_handoff_summary_builder.py"
SPEC = importlib.util.spec_from_file_location("dev_handoff_summary_builder", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def run(cmd, cwd):
    subprocess.run(cmd, cwd=str(cwd), check=True, capture_output=True, text=True)


def make_repo(root: Path) -> tuple[str, str]:
    run(["git", "init"], root)
    run(["git", "config", "user.name", "Test User"], root)
    run(["git", "config", "user.email", "test@example.com"], root)

    (root / "file.txt").write_text("v1\n", encoding="utf-8")
    run(["git", "add", "file.txt"], root)
    run(["git", "commit", "-m", "base"], root)
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(root), check=True, capture_output=True, text=True).stdout.strip()

    (root / "file.txt").write_text("v2\n", encoding="utf-8")
    run(["git", "add", "file.txt"], root)
    run(["git", "commit", "-m", "change"], root)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(root), check=True, capture_output=True, text=True).stdout.strip()

    return base, head


class DevHandoffSummaryBuilderTests(unittest.TestCase):
    def test_payload_has_all_mandatory_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = {
                "task_identifier": "MYO-164",
                "branch": "codex/dev-2/myo-164",
                "start_from_branch": "main",
                "start_from_commit": "abc123",
                "checks_json_path": None,
                "decision_hint": "auto",
                "blockers": [],
                "dry_run": True,
                "repo_root": str(root),
            }
            cfg = MODULE.parse_input(type("Args", (), {
                "input_json": None,
                "task_identifier": payload["task_identifier"],
                "branch": payload["branch"],
                "start_from_branch": payload["start_from_branch"],
                "start_from_commit": payload["start_from_commit"],
                "checks_json_path": payload["checks_json_path"],
                "decision_hint": payload["decision_hint"],
                "repo_root": payload["repo_root"],
                "dry_run": payload["dry_run"],
            })())
            out = MODULE.build_summary(cfg)
            required = {
                "task_identifier",
                "branch",
                "start_from_branch",
                "start_from_commit",
                "head_commit",
                "files_changed_count",
                "checks",
                "decision",
                "blockers",
            }
            self.assertTrue(required.issubset(set(out.keys())))

    def test_decision_derivation_and_validation(self):
        checks_pass = {"pytest": "pass"}
        checks_fail = {"pytest": "fail"}

        decision, blockers = MODULE.derive_decision(checks_pass, [], "auto")
        self.assertEqual(decision, "ready_for_test")
        self.assertEqual(blockers, [])

        decision, blockers = MODULE.derive_decision(checks_fail, [], "auto")
        self.assertEqual(decision, "blocked")
        self.assertEqual(blockers, [])

        decision, blockers = MODULE.derive_decision(checks_pass, ["env missing"], "ready_for_test")
        self.assertEqual(decision, "blocked")
        self.assertTrue(any("overridden" in b for b in blockers))

    def test_integration_with_real_git_and_check_bundle_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base, head = make_repo(root)
            checks_path = root / "checks.json"
            checks_path.write_text(
                json.dumps(
                    {
                        "ok": True,
                        "overall": "pass",
                        "checks": [
                            {"name": "compileall", "result": "pass", "exit_code": 0, "duration_ms": 12, "snippet": "ok"},
                            {"name": "pytest", "result": "pass", "exit_code": 0, "duration_ms": 42, "snippet": "ok"},
                        ],
                        "blockers": [],
                    }
                ),
                encoding="utf-8",
            )

            cfg = MODULE.SummaryInput(
                task_identifier="MYO-164",
                branch="codex/dev-2/myo-164",
                start_from_branch="main",
                start_from_commit=base,
                checks_json_path=checks_path,
                decision_hint="auto",
                blockers=[],
                dry_run=False,
                repo_root=root,
            )
            out = MODULE.build_summary(cfg)
            self.assertEqual(out["head_commit"], head)
            self.assertEqual(out["files_changed_count"], 1)
            self.assertEqual(out["checks"]["compileall"], "pass")
            self.assertEqual(out["checks"]["pytest"], "pass")
            self.assertEqual(out["decision"], "ready_for_test")

    def test_contract_shape_and_allowed_decisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = MODULE.SummaryInput(
                task_identifier="MYO-164",
                branch="codex/dev-2/myo-164",
                start_from_branch="main",
                start_from_commit="abc123",
                checks_json_path=None,
                decision_hint="auto",
                blockers=[],
                dry_run=True,
                repo_root=root,
            )
            out = MODULE.build_summary(cfg)
            self.assertIn(out["decision"], {"ready_for_test", "blocked"})
            self.assertIsInstance(out["checks"], dict)
            self.assertIsInstance(out["blockers"], list)


if __name__ == "__main__":
    unittest.main()
