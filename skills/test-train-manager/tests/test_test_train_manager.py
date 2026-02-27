import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "test_train_manager.py"
SPEC = importlib.util.spec_from_file_location("test_train_manager", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def git(cwd: Path, *args: str, check: bool = True):
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=check,
        capture_output=True,
        text=True,
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def build_repo(root: Path) -> None:
    git(root, "init", "-b", "main")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "Test User")

    write_text(root / "README.md", "seed\n")
    git(root, "add", "README.md")
    git(root, "commit", "-m", "seed")
    git(root, "branch", "test")
    git(root, "branch", "test-next", "test")


def run_action(repo_root: Path, **overrides):
    payload = {
        "repo_root": str(repo_root),
        "action": overrides.get("action", "sync_state"),
        "test_branch": overrides.get("test_branch", "test"),
        "test_next_branch": overrides.get("test_next_branch", "test-next"),
        "test_train_mode": overrides.get("test_train_mode", "final-stage"),
        "shared_test_base_url": overrides.get("shared_test_base_url"),
        "deploy_test_branch_cmd": overrides.get("deploy_test_branch_cmd"),
        "dry_run": overrides.get("dry_run", False),
        "planned_flow_pass_completed": overrides.get("planned_flow_pass_completed"),
        "task_identifier": overrides.get("task_identifier"),
        "task_outcome": overrides.get("task_outcome"),
        "force": overrides.get("force", False),
    }
    inp = MODULE.build_input(payload)
    return MODULE.run(inp)


class TestTrainManagerTests(unittest.TestCase):
    def test_bootstrap_creates_state_and_wave(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_repo(root)
            out = run_action(root, action="bootstrap")
            self.assertTrue(out["ok"])
            self.assertEqual(out["active_wave"]["state"], "WAVE_BOOTSTRAP")

            state_path = root / "reports" / "optimus-prime" / "TEST_TRAIN_STATE.json"
            self.assertTrue(state_path.exists())
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["test_branch"], "test")
            self.assertEqual(state["test_next_branch"], "test-next")

    def test_gate_eligible_after_wave_close_without_critical_blocker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_repo(root)
            run_action(root, action="bootstrap")
            run_action(root, action="start_new_test_wave")
            run_action(root, action="close_test_wave", planned_flow_pass_completed=True)
            out = run_action(root, action="evaluate_promotion_gate")
            self.assertTrue(out["ok"])
            self.assertTrue(out["promotion_eligibility"]["eligible"])

    def test_gate_blocked_by_critical_blocker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_repo(root)
            run_action(root, action="bootstrap")
            run_action(root, action="start_new_test_wave")
            run_action(root, action="close_test_wave", planned_flow_pass_completed=True)

            append_jsonl(
                root / "reports" / "optimus-prime" / "BLOCKERS.jsonl",
                {
                    "timestamp": MODULE.utc_now_iso(),
                    "category": "runtime",
                    "status": "active",
                    "summary": "runtime down",
                },
            )
            out = run_action(root, action="evaluate_promotion_gate")
            self.assertTrue(out["ok"])
            self.assertFalse(out["promotion_eligibility"]["eligible"])
            self.assertIn("critical_environment_blocker_active", out["promotion_eligibility"]["reasons"])

    def test_promote_merges_test_next_into_test(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_repo(root)
            run_action(root, action="bootstrap")
            run_action(root, action="start_new_test_wave")
            run_action(root, action="close_test_wave", planned_flow_pass_completed=True)

            git(root, "checkout", "test-next")
            write_text(root / "feature.txt", "hello\n")
            git(root, "add", "feature.txt")
            git(root, "commit", "-m", "add feature")
            git(root, "checkout", "main")

            out = run_action(root, action="promote_test_next_to_test")
            self.assertTrue(out["ok"])

            file_text = git(root, "show", "test:feature.txt").stdout
            self.assertEqual(file_text.strip(), "hello")

    def test_record_outcome_escalates_after_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_repo(root)
            run_action(root, action="bootstrap")
            run_action(root, action="start_new_test_wave")

            run_action(root, action="record_test_outcome", task_identifier="MYO-1", task_outcome="failed")
            run_action(root, action="record_test_outcome", task_identifier="MYO-1", task_outcome="failed")
            out = run_action(root, action="record_test_outcome", task_identifier="MYO-1", task_outcome="failed")
            self.assertTrue(out["ok"])
            self.assertTrue(out["task_state"]["needs_orchestrator_review"])
            self.assertEqual(out["task_state"]["escalation_reason"], "failed_attempts>=3")

    def test_repeated_blockers_force_shared_env_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_repo(root)
            run_action(root, action="bootstrap", test_train_mode="final-stage")

            blockers = root / "reports" / "optimus-prime" / "BLOCKERS.jsonl"
            for _ in range(3):
                append_jsonl(
                    blockers,
                    {
                        "timestamp": MODULE.utc_now_iso(),
                        "category": "env",
                        "worker_role": "tester",
                        "fingerprint": "runtime|env_missing|seed",
                        "summary": "missing env",
                    },
                )

            out = run_action(root, action="sync_state", test_train_mode="final-stage")
            self.assertTrue(out["ok"])
            self.assertEqual(out["test_train_mode"], "forced-shared-env")


if __name__ == "__main__":
    unittest.main()
