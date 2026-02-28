import json
import tempfile
from pathlib import Path

from scripts.quality import op_runtime_canary_gate as gate


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _seed_minimal_canary_project(root: Path, *, plan_packets_id: str, task_state_id: str, evidence_id: str) -> None:
    planning = root / "reports" / "optimus-prime" / "planning"
    controller = root / "reports" / "optimus-prime" / "controller"
    runtime_root = root / "reports" / "optimus-prime"

    _write(
        planning / "PLAN_PACKETS.json",
        {
            "schema_version": "1.0",
            "plan_id": plan_packets_id,
            "tasks": [
                {
                    "task_id": "TASK-001",
                    "phase_id": "phase-1",
                    "requirement_ids": ["REQ-001"],
                    "verify_commands": ["python3 -m pytest"],
                    "must_haves": [],
                    "depends_on": [],
                }
            ],
            "phases": [{"phase_id": "phase-1", "task_ids": ["TASK-001"], "depends_on_phase_ids": []}],
            "requirements": [{"requirement_id": "REQ-001"}],
        },
    )
    _write(
        planning / "TASK_EXECUTION_STATE.json",
        {
            "schema_version": "1.0",
            "plan_id": task_state_id,
            "tasks": [
                {
                    "task_id": "TASK-001",
                    "phase_id": "phase-1",
                    "status": "queued",
                    "owner_slot": None,
                    "attempts": {"dev": 0, "test": 0, "review": 0},
                    "evidence": {"task_evidence_ref": "reports/optimus-prime/planning/evidence/TASK-001/TASK_EVIDENCE.json"},
                    "requirement_ids": ["REQ-001"],
                    "blockers": [],
                    "last_progress_at": "2026-01-01T00:00:00Z",
                }
            ],
        },
    )
    _write(
        planning / "BUILD_STATE.json",
        {
            "schema_version": "1.0",
            "last_cycle": 5,
            "terminal_state": None,
        },
    )
    _write(
        planning / "NO_PROGRESS_WATCHDOG_STATE.json",
        {
            "schema_version": "1.0",
            "last_cycle": 5,
            "consecutive_no_progress_cycles": 0,
            "threshold_cycles": 25,
            "last_progress_at": "2026-01-01T00:00:00Z",
            "triggered": False,
            "triggered_at": None,
            "trigger_reason": None,
        },
    )
    _write(
        planning / "evidence" / "TASK-001" / "TASK_EVIDENCE.json",
        {
            "schema_version": "1.0",
            "plan_id": evidence_id,
            "phase_id": "phase-1",
            "task_id": "TASK-001",
            "requirement_ids": ["REQ-001"],
            "dev": {"status": "pending", "checks": [], "verify_results": [], "dev_ready": False, "blockers": [], "artifacts": []},
            "test": {"status": "pending", "checks": [], "verify_results": [], "uat_results": [], "blockers": [], "artifacts": []},
            "review": {"status": "pending", "decision": "pending", "blockers": [], "artifacts": []},
            "gate": {"ready_for_test": False, "ready_for_review": False, "ready_for_phase_exit": False},
            "summary": {"result": "blocked", "reason_codes": ["not_started"]},
            "updated_at": "2026-01-01T00:00:00Z",
        },
    )
    _write(runtime_root / "WORKER_REGISTRY.json", {"workers": []})
    controller.mkdir(parents=True, exist_ok=True)
    (controller / "EVENTS.jsonl").write_text("", encoding="utf-8")
    (runtime_root / "HANDOFF_LOG.jsonl").write_text("", encoding="utf-8")


def test_runtime_canary_blocks_on_plan_id_mismatch_and_opens_finding():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _seed_minimal_canary_project(
            root,
            plan_packets_id="plan-a",
            task_state_id="plan-b",
            evidence_id="plan-b",
        )
        out = gate.run_canary(root, "MyBoard", stale_seconds=3600, fix_streak=3)
        assert out["status"] == "blocked"
        assert any(check["id"] == "plan_id_parity" and check["passed"] is False for check in out["checks"])
        findings_path = root / "reports" / "optimus-prime" / "planning" / "RUN_FINDINGS.json"
        findings = json.loads(findings_path.read_text(encoding="utf-8"))
        assert any((item.get("status") in {"open", "regressed"}) for item in findings.get("findings", []))


def test_runtime_canary_marks_finding_fixed_after_three_clean_runs():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _seed_minimal_canary_project(
            root,
            plan_packets_id="plan-a",
            task_state_id="plan-b",
            evidence_id="plan-b",
        )
        first = gate.run_canary(root, "MyBoard", stale_seconds=3600, fix_streak=3)
        assert first["status"] == "blocked"

        _seed_minimal_canary_project(
            root,
            plan_packets_id="plan-c",
            task_state_id="plan-c",
            evidence_id="plan-c",
        )
        second = gate.run_canary(root, "MyBoard", stale_seconds=3600, fix_streak=3)
        third = gate.run_canary(root, "MyBoard", stale_seconds=3600, fix_streak=3)
        fourth = gate.run_canary(root, "MyBoard", stale_seconds=3600, fix_streak=3)
        assert second["status"] == "passed"
        assert third["status"] == "passed"
        assert fourth["status"] == "passed"

        findings_path = root / "reports" / "optimus-prime" / "planning" / "RUN_FINDINGS.json"
        findings = json.loads(findings_path.read_text(encoding="utf-8"))
        statuses = {item.get("status") for item in findings.get("findings", [])}
        assert "fixed" in statuses


def test_runtime_canary_dedup_stable_for_same_handoff_staleness():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _seed_minimal_canary_project(
            root,
            plan_packets_id="plan-a",
            task_state_id="plan-a",
            evidence_id="plan-a",
        )

        task_state_path = root / "reports" / "optimus-prime" / "planning" / "TASK_EXECUTION_STATE.json"
        task_state = json.loads(task_state_path.read_text(encoding="utf-8"))
        task_state["tasks"][0]["status"] = "dev_in_progress"
        task_state["tasks"][0]["owner_slot"] = "dev-1"
        task_state["tasks"][0]["last_progress_at"] = "2026-01-01T00:00:00Z"
        task_state_path.write_text(json.dumps(task_state, indent=2) + "\n", encoding="utf-8")

        first = gate.run_canary(root, "MyBoard", stale_seconds=60, fix_streak=3)
        second = gate.run_canary(root, "MyBoard", stale_seconds=60, fix_streak=3)
        assert first["status"] == "blocked"
        assert second["status"] == "blocked"

        findings_path = root / "reports" / "optimus-prime" / "planning" / "RUN_FINDINGS.json"
        findings = json.loads(findings_path.read_text(encoding="utf-8"))
        open_rows = [
            row
            for row in findings.get("findings", [])
            if row.get("category") == "ingestion" and row.get("status") in {"open", "regressed", "in_progress"}
        ]
        assert len(open_rows) == 1
        assert int(open_rows[0].get("count") or 0) >= 2
