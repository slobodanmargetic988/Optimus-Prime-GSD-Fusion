import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "repo_guard_scanner.py"
SPEC = importlib.util.spec_from_file_location("repo_guard_scanner", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def git(root: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=str(root), capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"git {' '.join(args)} failed")
    return (proc.stdout or "").strip()


def init_repo() -> Path:
    root = Path(tempfile.mkdtemp())
    git(root, "init")
    git(root, "config", "user.email", "scanner@test.local")
    git(root, "config", "user.name", "Scanner Test")
    (root / "README.md").write_text("seed\n", encoding="utf-8")
    git(root, "add", "README.md")
    git(root, "commit", "-m", "seed")
    git(root, "checkout", "-b", "RAB-BASE")
    return root


def test_merge_source_report_artifacts_returns_forbidden_paths():
    root = init_repo()
    git(root, "checkout", "-b", "codex/dev-1/task-001")
    report = root / "reports" / "optimus-prime" / "planning" / "UAT.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("uat\n", encoding="utf-8")
    src = root / "src" / "app.py"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("print('ok')\n", encoding="utf-8")
    git(root, "add", "reports/optimus-prime/planning/UAT.md", "src/app.py")
    git(root, "commit", "-m", "artifact")

    out = MODULE.run(
        {
            "mode": "merge_source_report_artifacts",
            "repo_root": str(root),
            "source_branch": "codex/dev-1/task-001",
        }
    )

    assert out["ok"] is True
    assert "reports/optimus-prime/planning/UAT.md" in out["forbidden_paths"]
    assert out["inspect_error"] is None


def test_merge_source_report_artifacts_handles_invalid_branch():
    root = init_repo()
    out = MODULE.run(
        {
            "mode": "merge_source_report_artifacts",
            "repo_root": str(root),
            "source_branch": "missing/branch",
        }
    )
    assert out["ok"] is True
    assert out["forbidden_paths"] == []
    assert out["inspect_error"] is None


def test_dispatch_commit_link_fails_when_head_equals_start():
    root = init_repo()
    git(root, "checkout", "-b", "codex/dev-1/task-001")
    head = git(root, "rev-parse", "HEAD")

    out = MODULE.run(
        {
            "mode": "dispatch_commit_link",
            "repo_root": str(root),
            "branch_name": "codex/dev-1/task-001",
            "start_from_commit": head,
        }
    )

    assert out["ok"] is False
    assert out["reason_code"] == "dispatch_commit_link_missing"
    assert out["advanced"] is False


def test_dispatch_commit_link_fails_when_report_paths_in_commit_range():
    root = init_repo()
    git(root, "checkout", "-b", "codex/dev-1/task-001")
    start = git(root, "rev-parse", "HEAD")
    report = root / "reports" / "optimus-prime" / "planning" / "STATE.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("state\n", encoding="utf-8")
    git(root, "add", "reports/optimus-prime/planning/STATE.md")
    git(root, "commit", "-m", "report only")

    out = MODULE.run(
        {
            "mode": "dispatch_commit_link",
            "repo_root": str(root),
            "branch_name": "codex/dev-1/task-001",
            "start_from_commit": start,
        }
    )

    assert out["ok"] is False
    assert out["reason_code"] == "forbidden_op_artifact_commit"
    assert "reports/optimus-prime/planning/STATE.md" in out["forbidden_paths"]


def test_dispatch_commit_link_passes_with_non_report_change():
    root = init_repo()
    git(root, "checkout", "-b", "codex/dev-1/task-001")
    start = git(root, "rev-parse", "HEAD")
    src = root / "src" / "app.py"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("print('hello')\n", encoding="utf-8")
    git(root, "add", "src/app.py")
    git(root, "commit", "-m", "code")

    out = MODULE.run(
        {
            "mode": "dispatch_commit_link",
            "repo_root": str(root),
            "branch_name": "codex/dev-1/task-001",
            "start_from_commit": start,
        }
    )

    assert out["ok"] is True
    assert out["reason_code"] is None
    assert out["advanced"] is True
    assert "src/app.py" in out["changed_paths"]


def test_dispatch_commit_link_fails_when_branch_missing():
    root = init_repo()
    out = MODULE.run(
        {
            "mode": "dispatch_commit_link",
            "repo_root": str(root),
            "branch_name": "codex/dev-1/missing",
            "start_from_commit": "deadbeef",
        }
    )
    assert out["ok"] is False
    assert out["reason_code"] == "dispatch_commit_link_inspection_failed"
    assert isinstance(out.get("inspect_error"), str)


def test_cli_contract_stdin_mode_and_exit_code():
    root = init_repo()
    git(root, "checkout", "-b", "codex/dev-1/task-001")
    payload = {
        "mode": "dispatch_commit_link",
        "repo_root": str(root),
        "branch_name": "codex/dev-1/task-001",
        "start_from_commit": git(root, "rev-parse", "HEAD"),
    }
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--input-json", "-"],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 1
    parsed = json.loads(proc.stdout)
    assert parsed["ok"] is False
    assert parsed["mode"] == "dispatch_commit_link"
    assert parsed["reason_code"] == "dispatch_commit_link_missing"
