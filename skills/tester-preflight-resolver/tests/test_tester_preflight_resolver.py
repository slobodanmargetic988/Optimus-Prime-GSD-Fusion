import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "tester_preflight_resolver.py"
SPEC = importlib.util.spec_from_file_location("tester_preflight_resolver", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=True)


def init_repo(root: Path) -> None:
    run(["git", "init"], root)
    run(["git", "config", "user.name", "Test User"], root)
    run(["git", "config", "user.email", "test@example.com"], root)


def commit_file(root: Path, name: str, content: str, message: str) -> str:
    (root / name).write_text(content, encoding="utf-8")
    run(["git", "add", name], root)
    run(["git", "commit", "-m", message], root)
    return run(["git", "rev-parse", "HEAD"], root).stdout.strip()


def current_branch(root: Path) -> str:
    return run(["git", "branch", "--show-current"], root).stdout.strip()


class TesterPreflightResolverTests(unittest.TestCase):
    def test_fallback_branch_naming_unit(self):
        self.assertEqual(MODULE.fallback_branch_name("codex/dev-2/myo-166", "-test"), "codex/dev-2/myo-166-test")
        self.assertEqual(MODULE.fallback_branch_name("codex/dev-2/myo-166-test", "-test"), "codex/dev-2/myo-166-test")

    def test_lineage_validation_pass_fail_unit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_repo(root)
            base = commit_file(root, "a.txt", "one\n", "base")
            second = commit_file(root, "a.txt", "two\n", "second")

            cfg = MODULE.PreflightInput(
                worktree_root=root,
                task_identifier="MYO-166",
                branch_name=current_branch(root),
                start_from_branch=current_branch(root),
                start_from_commit=base,
                target_head_commit=None,
                fallback_suffix="-test",
                allow_fallback=True,
                dry_run=False,
            )
            self.assertTrue(MODULE.lineage_ok(cfg, MODULE.CommandRunner(), second))

            unrelated = "0" * 40
            self.assertFalse(MODULE.lineage_ok(cfg, MODULE.CommandRunner(), unrelated))

    def test_integration_branch_available_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_repo(root)
            base = commit_file(root, "app.txt", "base\n", "base")
            default_branch = current_branch(root)
            run(["git", "checkout", "-b", "codex/dev-2/myo-166"], root)
            feature_head = commit_file(root, "app.txt", "feature\n", "feature")
            run(["git", "checkout", default_branch], root)

            cfg = MODULE.PreflightInput(
                worktree_root=root,
                task_identifier="MYO-166",
                branch_name="codex/dev-2/myo-166",
                start_from_branch=default_branch,
                start_from_commit=base,
                target_head_commit=feature_head,
                fallback_suffix="-test",
                allow_fallback=True,
                dry_run=False,
            )
            out = MODULE.execute(cfg)
            self.assertTrue(out["ok"])
            self.assertEqual(out["intended_branch"], "codex/dev-2/myo-166")
            self.assertEqual(out["resolved_branch"], "codex/dev-2/myo-166")
            self.assertFalse(out["fallback_used"])
            self.assertTrue(out["branch_exists"])
            self.assertFalse(out["fallback_created"])
            self.assertEqual(out["next_step"], "run_tests")

    def test_integration_branch_locked_fallback_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock_root = Path(tmp) / "lock-worktree"
            init_repo(root)
            base = commit_file(root, "app.txt", "base\n", "base")
            default_branch = current_branch(root)
            run(["git", "checkout", "-b", "codex/dev-2/myo-166"], root)
            commit_file(root, "app.txt", "feature\n", "feature")
            run(["git", "checkout", default_branch], root)

            run(["git", "worktree", "add", str(lock_root), "codex/dev-2/myo-166"], root)

            cfg = MODULE.PreflightInput(
                worktree_root=root,
                task_identifier="MYO-166",
                branch_name="codex/dev-2/myo-166",
                start_from_branch=default_branch,
                start_from_commit=base,
                target_head_commit=None,
                fallback_suffix="-test",
                allow_fallback=True,
                dry_run=False,
            )
            out = MODULE.execute(cfg)
            self.assertTrue(out["ok"])
            self.assertEqual(out["intended_branch"], "codex/dev-2/myo-166")
            self.assertEqual(out["resolved_branch"], "codex/dev-2/myo-166-test")
            self.assertTrue(out["fallback_used"])
            self.assertTrue(out["branch_exists"])
            self.assertTrue(out["fallback_created"])
            self.assertEqual(out["next_step"], "run_tests")
            warning_codes = {w["code"] for w in out["warnings"]}
            self.assertIn("fallback_used", warning_codes)

    def test_failure_invalid_start_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_repo(root)
            commit_file(root, "a.txt", "base\n", "base")

            cfg = MODULE.PreflightInput(
                worktree_root=root,
                task_identifier="MYO-166",
                branch_name=current_branch(root),
                start_from_branch=current_branch(root),
                start_from_commit="badbadbad",
                target_head_commit=None,
                fallback_suffix="-test",
                allow_fallback=True,
                dry_run=False,
            )
            out = MODULE.execute(cfg)
            self.assertFalse(out["ok"])
            self.assertEqual(out["next_step"], "blocked")
            codes = {e["code"] for e in out["errors"]}
            self.assertIn("invalid_start_commit", codes)


if __name__ == "__main__":
    unittest.main()
