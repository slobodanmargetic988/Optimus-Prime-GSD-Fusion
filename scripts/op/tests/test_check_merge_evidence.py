import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "planner" / "check_merge_evidence.py"
SPEC = importlib.util.spec_from_file_location("check_merge_evidence", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _build_valid_registry(root: Path) -> Path:
    merged_rows = []
    done_task_ids = list(MODULE.DEFAULT_TASK_IDS)
    for task_id in MODULE.DEFAULT_TASK_IDS:
        validation_rel = f"reports/optimus-prime/branch-manager/attempt-{task_id.lower()}/MERGE_VALIDATION.json"
        _write_json(
            root / validation_rel,
            {
                "schema_version": "1.0",
                "task_id": task_id,
                "ok": True,
                "branch": "RAB-BASE",
                "source_branch": f"codex/dev-1/{task_id.lower()}",
                "merged_commit": f"{task_id.lower()}-commit",
                "merge_proof_passed": True,
                "verification_skipped": True,
                "verification_skip_reason": "review_stage_already_verified",
            },
        )
        merged_rows.append(
            {
                "task_id": task_id,
                "merged_commit": f"{task_id.lower()}-commit",
                "merged_at": "2026-03-26T22:42:55Z",
                "branch": "RAB-BASE",
                "verification_passed": True,
                "verification_ref": validation_rel,
            }
        )

    done_path = root / "reports" / "optimus-prime" / "planning" / "DONE_TASKS_REGISTRY.json"
    _write_json(
        done_path,
        {
            "schema_version": "1.0",
            "updated_at": "2026-03-26T22:42:55Z",
            "done_task_ids": done_task_ids,
            "merged_tasks": merged_rows,
        },
    )
    return done_path


def test_check_merge_evidence_passes_for_default_lane_merge_tasks():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        done_path = _build_valid_registry(root)
        result = MODULE.check_merge_evidence(
            repo_root=root,
            done_registry_path=done_path,
            required_task_ids=list(MODULE.DEFAULT_TASK_IDS),
            expected_branch="RAB-BASE",
        )
        assert result["ok"] is True
        assert result["errors"] == []
        assert [row["task_id"] for row in result["tasks"]] == list(MODULE.DEFAULT_TASK_IDS)
        assert all(row["ok"] is True for row in result["tasks"])


def test_check_merge_evidence_fails_when_required_task_has_no_merge_row():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        done_path = _build_valid_registry(root)
        payload = json.loads(done_path.read_text(encoding="utf-8"))
        payload["merged_tasks"] = [
            row for row in payload["merged_tasks"] if row.get("task_id") != "TASK-006"
        ]
        done_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        result = MODULE.check_merge_evidence(
            repo_root=root,
            done_registry_path=done_path,
            required_task_ids=list(MODULE.DEFAULT_TASK_IDS),
            expected_branch="RAB-BASE",
        )
        assert result["ok"] is False
        failed = next(row for row in result["tasks"] if row["task_id"] == "TASK-006")
        codes = [issue["code"] for issue in failed["issues"]]
        assert "merge_row_missing" in codes


def test_cli_returns_nonzero_on_merge_validation_failure():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        done_path = _build_valid_registry(root)
        broken = root / "reports" / "optimus-prime" / "branch-manager" / "attempt-task-009" / "MERGE_VALIDATION.json"
        payload = json.loads(broken.read_text(encoding="utf-8"))
        payload["ok"] = False
        broken.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--repo-root",
                str(root),
                "--done-registry",
                str(done_path),
                "--log-root",
                str(root / "logs"),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        assert proc.returncode == 1
        assert "FAIL TASK-009" in proc.stdout
        assert "Overall result: FAIL" in proc.stdout
