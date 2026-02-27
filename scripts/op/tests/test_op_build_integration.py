import importlib.util
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


OP_CORE_PATH = Path(__file__).resolve().parents[1] / "op_core.py"
CONTROLLER_SOURCE = Path(__file__).resolve().parents[3] / "skills" / "optimus-cycle-controller" / "scripts" / "optimus_cycle_controller.py"
SPEC = importlib.util.spec_from_file_location("op_core_integration", OP_CORE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def git(cwd: Path, *args: str) -> None:
    import subprocess

    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True)


def build_repo(root: Path) -> None:
    git(root, "init", "-b", "main")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "Test User")
    (root / "README.md").write_text("seed\n", encoding="utf-8")
    (root / "docs" / "plans").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "plans" / "LANE_B_FULL_GSD_FUSION_PLAN.md").write_text("seed\n", encoding="utf-8")
    (root / "scripts" / "runtime").mkdir(parents=True, exist_ok=True)
    (root / "scripts" / "runtime" / "start.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    controller_target = root / "skills" / "optimus-cycle-controller" / "scripts" / "optimus_cycle_controller.py"
    controller_target.parent.mkdir(parents=True, exist_ok=True)
    controller_target.write_text(CONTROLLER_SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "seed")


def run_payload(payload: dict) -> dict:
    req = MODULE.parse_request(payload)
    return MODULE.execute_request(req)


def seed_stale_in_progress_task(root: Path, *, status: str = "dev_in_progress", owner_slot: str = "dev-1", minutes_ago: int = 20) -> str:
    task_state_path = root / "reports" / "optimus-prime" / "planning" / "TASK_EXECUTION_STATE.json"
    task_state = json.loads(task_state_path.read_text(encoding="utf-8"))
    task = next(item for item in task_state.get("tasks", []) if isinstance(item, dict))
    task["status"] = status
    task["owner_slot"] = owner_slot
    task["last_progress_at"] = (
        datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    task_state_path.write_text(json.dumps(task_state, indent=2) + "\n", encoding="utf-8")
    return str(task.get("task_id"))


def test_op_build_applies_runtime_and_test_train_directives(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        out = run_payload(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        assert out["ok"] is True

        events_path = root / "reports" / "optimus-prime" / "controller" / "EVENTS.jsonl"
        events_path.parent.mkdir(parents=True, exist_ok=True)
        events = [
            {
                "timestamp": "2026-01-01T00:00:00Z",
                "cycle_number": 1,
                "event_type": "directive",
                "action_code": "runtime_health_check",
                "payload": {
                    "directive_type": "runtime_health_check",
                    "recommended_args": {"action": "health", "test_train_mode": "final-stage"},
                    "requires_optimus_action": True,
                },
            },
            {
                "timestamp": "2026-01-01T00:00:01Z",
                "cycle_number": 1,
                "event_type": "directive",
                "action_code": "evaluate_promotion_gate",
                "payload": {
                    "directive_type": "evaluate_promotion_gate",
                    "recommended_args": {"action": "evaluate_promotion_gate"},
                    "requires_optimus_action": True,
                },
            },
        ]
        events_path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")

        def fake_cycle(_req):
            return {
                "ok": False,
                "status": "running",
                "terminal_reason": None,
                "last_cycle_number": 1,
                "events_path": str(events_path),
            }

        calls: list[dict] = []

        def fake_tool(script: Path, payload: dict, cwd: Path) -> dict:
            calls.append({"script": str(script), "payload": payload, "cwd": str(cwd)})
            return {"ok": True, "status": "completed"}

        monkeypatch.setattr(MODULE, "_run_controller_cycle", fake_cycle)
        monkeypatch.setattr(MODULE, "_run_tool_json", fake_tool)
        monkeypatch.setattr(MODULE, "_dispatch_next_task", lambda req, plan, state, build, *_: {"ok": True, "status": "noop"})

        build_out = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert build_out["ok"] is False
        assert build_out["status"] == "running_needs_resume"
        actions = [c["payload"].get("action") for c in calls]
        assert "health" in actions
        assert "evaluate_promotion_gate" in actions


def test_op_build_stops_for_manual_rerun_when_rate_reset_exceeds_two_hours(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        out = run_payload(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        assert out["ok"] is True

        events_path = root / "reports" / "optimus-prime" / "controller" / "EVENTS.jsonl"
        events_path.parent.mkdir(parents=True, exist_ok=True)
        events_path.write_text("", encoding="utf-8")

        rate_path = root / "reports" / "optimus-prime" / "PROFILE_RATE_REGISTRY.json"
        rate_path.parent.mkdir(parents=True, exist_ok=True)
        rate_path.write_text(
            json.dumps(
                {
                    "profiles": {
                        "codex": {
                            "recommended_action": "wind_down",
                            "five_hour": {
                                "gated": True,
                                "reset_at": "2099-01-01T00:00:00Z",
                            },
                        }
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        dispatch_calls = {"count": 0}

        def fake_dispatch(req, plan, state, build, *_):
            dispatch_calls["count"] += 1
            return {"ok": True, "status": "noop"}

        monkeypatch.setattr(
            MODULE,
            "_run_controller_cycle",
            lambda _req: {
                "ok": True,
                "terminal_reason": "all_rate_gates_blocking",
                "last_cycle_number": 1,
                "events_path": str(events_path),
            },
        )
        monkeypatch.setattr(MODULE, "_dispatch_next_task", fake_dispatch)

        build_out = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert build_out["ok"] is False
        assert build_out["status"] == "blocked_terminal"
        assert build_out["data"]["rate_gate_state"]["manual_rerun_required"] is True
        assert dispatch_calls["count"] == 0


def test_dispatch_filter_blocks_dispatch_for_cycle(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        run_payload(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        events_path = root / "reports" / "optimus-prime" / "controller" / "EVENTS.jsonl"
        events_path.parent.mkdir(parents=True, exist_ok=True)
        events_path.write_text(
            json.dumps(
                {
                    "timestamp": "2026-01-01T00:00:00Z",
                    "cycle_number": 1,
                    "event_type": "directive",
                    "action_code": "dispatch_filter",
                    "payload": {
                        "directive_type": "dispatch_filter",
                        "recommended_args": {"mode": "hard_gate"},
                        "requires_optimus_action": True,
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(
            MODULE,
            "_run_controller_cycle",
            lambda _req: {
                "ok": False,
                "status": "running",
                "terminal_reason": None,
                "last_cycle_number": 1,
                "events_path": str(events_path),
            },
        )
        dispatch_calls = {"count": 0}

        def fake_dispatch(req, plan, state, build, *_):
            dispatch_calls["count"] += 1
            return {"ok": True, "status": "noop"}

        monkeypatch.setattr(MODULE, "_dispatch_next_task", fake_dispatch)
        out = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert out["status"] == "running_needs_resume"
        assert dispatch_calls["count"] == 0
        assert any(item.get("code") == "dispatch_skipped_hard_gate" for item in out["warnings"])


def test_runtime_adapter_uses_state_derived_mode(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        run_payload(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        state_path = root / "reports" / "optimus-prime" / "TEST_TRAIN_STATE.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({"test_train_mode": "off"}, indent=2) + "\n", encoding="utf-8")
        events_path = root / "reports" / "optimus-prime" / "controller" / "EVENTS.jsonl"
        events_path.parent.mkdir(parents=True, exist_ok=True)
        events_path.write_text(
            json.dumps(
                {
                    "timestamp": "2026-01-01T00:00:00Z",
                    "cycle_number": 1,
                    "event_type": "directive",
                    "action_code": "runtime_health_check",
                    "payload": {
                        "directive_type": "runtime_health_check",
                        "recommended_args": {"action": "health"},
                        "requires_optimus_action": True,
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )

        calls: list[dict] = []

        def fake_tool(script: Path, payload: dict, cwd: Path) -> dict:
            calls.append(payload)
            return {"ok": True, "status": "completed"}

        monkeypatch.setattr(
            MODULE,
            "_run_controller_cycle",
            lambda _req: {
                "ok": False,
                "status": "running",
                "terminal_reason": None,
                "last_cycle_number": 1,
                "events_path": str(events_path),
            },
        )
        monkeypatch.setattr(MODULE, "_run_tool_json", fake_tool)
        monkeypatch.setattr(MODULE, "_dispatch_next_task", lambda req, plan, state, build, *_: {"ok": True, "status": "noop"})
        out = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert out["status"] == "running_needs_resume"
        assert any(call.get("test_train_mode") == "off" for call in calls)


def test_runtime_adapter_fallback_mode_when_state_malformed(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        run_payload(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        state_path = root / "reports" / "optimus-prime" / "TEST_TRAIN_STATE.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text("{ invalid-json", encoding="utf-8")
        events_path = root / "reports" / "optimus-prime" / "controller" / "EVENTS.jsonl"
        events_path.parent.mkdir(parents=True, exist_ok=True)
        events_path.write_text(
            json.dumps(
                {
                    "timestamp": "2026-01-01T00:00:00Z",
                    "cycle_number": 1,
                    "event_type": "directive",
                    "action_code": "runtime_health_check",
                    "payload": {
                        "directive_type": "runtime_health_check",
                        "recommended_args": {"action": "health"},
                        "requires_optimus_action": True,
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )

        calls: list[dict] = []

        def fake_tool(script: Path, payload: dict, cwd: Path) -> dict:
            calls.append(payload)
            return {"ok": True, "status": "completed"}

        monkeypatch.setattr(
            MODULE,
            "_run_controller_cycle",
            lambda _req: {
                "ok": False,
                "status": "running",
                "terminal_reason": None,
                "last_cycle_number": 1,
                "events_path": str(events_path),
            },
        )
        monkeypatch.setattr(MODULE, "_run_tool_json", fake_tool)
        monkeypatch.setattr(MODULE, "_dispatch_next_task", lambda req, plan, state, build, *_: {"ok": True, "status": "noop"})
        out = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert out["status"] == "running_needs_resume"
        assert any(call.get("test_train_mode") == "off" for call in calls)


def test_handoff_offset_truncation_recovers_with_warning(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        run_payload(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        build_state_path = root / "reports" / "optimus-prime" / "planning" / "BUILD_STATE.json"
        build_state = json.loads(build_state_path.read_text(encoding="utf-8"))
        build_state["handoff_log_offset"] = 99
        build_state_path.write_text(json.dumps(build_state, indent=2) + "\n", encoding="utf-8")

        handoff_path = root / "reports" / "optimus-prime" / "HANDOFF_LOG.jsonl"
        handoff_path.parent.mkdir(parents=True, exist_ok=True)
        handoff_path.write_text(
            json.dumps({"task_identifier": "TASK-001", "result": "dev_done"}) + "\n",
            encoding="utf-8",
        )

        events_path = root / "reports" / "optimus-prime" / "controller" / "EVENTS.jsonl"
        events_path.parent.mkdir(parents=True, exist_ok=True)
        events_path.write_text("", encoding="utf-8")
        monkeypatch.setattr(
            MODULE,
            "_run_controller_cycle",
            lambda _req: {
                "ok": False,
                "status": "running",
                "terminal_reason": None,
                "last_cycle_number": 1,
                "events_path": str(events_path),
            },
        )
        monkeypatch.setattr(MODULE, "_dispatch_next_task", lambda req, plan, state, build, *_: {"ok": True, "status": "noop"})
        out = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert out["status"] == "running_needs_resume"
        assert any(item.get("code") == "handoff_offset_reset" for item in out["warnings"])
        build_state_after = json.loads(build_state_path.read_text(encoding="utf-8"))
        assert build_state_after["offset_recovery"]["handoff_offset_resets"] >= 1


def test_directive_failure_queues_remediation_and_skips_dispatch(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        run_payload(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        events_path = root / "reports" / "optimus-prime" / "controller" / "EVENTS.jsonl"
        events_path.parent.mkdir(parents=True, exist_ok=True)
        events_path.write_text(
            json.dumps(
                {
                    "timestamp": "2026-01-01T00:00:00Z",
                    "cycle_number": 1,
                    "event_type": "directive",
                    "action_code": "runtime_health_check",
                    "payload": {
                        "directive_type": "runtime_health_check",
                        "recommended_args": {"action": "health"},
                        "requires_optimus_action": True,
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(
            MODULE,
            "_run_controller_cycle",
            lambda _req: {
                "ok": False,
                "status": "running",
                "terminal_reason": None,
                "last_cycle_number": 1,
                "events_path": str(events_path),
            },
        )

        calls: list[dict] = []

        def fake_tool(script: Path, payload: dict, cwd: Path) -> dict:
            calls.append(payload)
            if payload.get("action") == "health":
                return {"ok": False, "status": "failed"}
            if payload.get("action") == "repair":
                return {"ok": True, "status": "queued"}
            return {"ok": True, "status": "completed"}

        dispatch_calls = {"count": 0}

        def fake_dispatch(req, plan, state, build, *_):
            dispatch_calls["count"] += 1
            return {"ok": True, "status": "noop"}

        monkeypatch.setattr(MODULE, "_run_tool_json", fake_tool)
        monkeypatch.setattr(MODULE, "_dispatch_next_task", fake_dispatch)
        out = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert out["status"] == "running_needs_resume"
        assert dispatch_calls["count"] == 0
        assert any(item.get("code") == "directive_tool_failed_remediation_queued" for item in out["warnings"])
        build_state = json.loads((root / "reports" / "optimus-prime" / "planning" / "BUILD_STATE.json").read_text(encoding="utf-8"))
        assert build_state["remediation_state"]["active"] is True
        assert any(call.get("action") == "repair" for call in calls)


def test_dispatch_cap_blocks_when_active_workers_at_limit(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        run_payload(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        build_state_path = root / "reports" / "optimus-prime" / "planning" / "BUILD_STATE.json"
        build_state = json.loads(build_state_path.read_text(encoding="utf-8"))
        build_state["dispatch_window"]["max_running_workers"] = 1
        build_state_path.write_text(json.dumps(build_state, indent=2) + "\n", encoding="utf-8")

        events_path = root / "reports" / "optimus-prime" / "controller" / "EVENTS.jsonl"
        events_path.parent.mkdir(parents=True, exist_ok=True)
        events_path.write_text("", encoding="utf-8")
        monkeypatch.setattr(
            MODULE,
            "_run_controller_cycle",
            lambda _req: {
                "ok": False,
                "status": "running",
                "terminal_reason": None,
                "last_cycle_number": 1,
                "events_path": str(events_path),
            },
        )
        monkeypatch.setattr(MODULE, "_active_workers_count", lambda _root: 1)
        dispatch_calls = {"count": 0}
        monkeypatch.setattr(MODULE, "_dispatch_next_task", lambda req, plan, state, build, *_: dispatch_calls.__setitem__("count", dispatch_calls["count"] + 1) or {"ok": True, "status": "noop"})
        out = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert out["status"] == "running_needs_resume"
        assert dispatch_calls["count"] == 0
        assert any(item.get("code") == "dispatch_skipped_soft_cap" for item in out["warnings"])


def test_dispatch_cap_allows_dispatch_when_capacity_available(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        run_payload(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        build_state_path = root / "reports" / "optimus-prime" / "planning" / "BUILD_STATE.json"
        build_state = json.loads(build_state_path.read_text(encoding="utf-8"))
        build_state["dispatch_window"]["max_running_workers"] = 2
        build_state_path.write_text(json.dumps(build_state, indent=2) + "\n", encoding="utf-8")

        events_path = root / "reports" / "optimus-prime" / "controller" / "EVENTS.jsonl"
        events_path.parent.mkdir(parents=True, exist_ok=True)
        events_path.write_text("", encoding="utf-8")
        monkeypatch.setattr(
            MODULE,
            "_run_controller_cycle",
            lambda _req: {
                "ok": False,
                "status": "running",
                "terminal_reason": None,
                "last_cycle_number": 1,
                "events_path": str(events_path),
            },
        )
        monkeypatch.setattr(MODULE, "_active_workers_count", lambda _root: 1)
        dispatch_calls = {"count": 0}

        def fake_dispatch(req, plan, state, build, *_):
            dispatch_calls["count"] += 1
            return {"ok": True, "status": "noop"}

        monkeypatch.setattr(MODULE, "_dispatch_next_task", fake_dispatch)
        out = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert out["status"] == "running_needs_resume"
        assert dispatch_calls["count"] == 1


def test_build_does_not_silently_stall_on_stale_dev_in_progress(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        run_payload(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        seed_stale_in_progress_task(root, status="dev_in_progress", owner_slot="dev-1", minutes_ago=20)
        events_path = root / "reports" / "optimus-prime" / "controller" / "EVENTS.jsonl"
        events_path.parent.mkdir(parents=True, exist_ok=True)
        events_path.write_text("", encoding="utf-8")
        monkeypatch.setattr(
            MODULE,
            "_run_controller_cycle",
            lambda _req: {
                "ok": False,
                "status": "running",
                "terminal_reason": None,
                "last_cycle_number": 1,
                "events_path": str(events_path),
            },
        )

        dispatch_calls = {"count": 0}

        def fake_dispatch(req, plan, state, build, *_):
            dispatch_calls["count"] += 1
            return {"ok": True, "status": "noop"}

        monkeypatch.setattr(MODULE, "_dispatch_next_task", fake_dispatch)
        out = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert out["status"] == "running_needs_resume"
        assert dispatch_calls["count"] == 1
        assert any(item.get("code") == "stale_in_progress_recovered" for item in out.get("warnings", []))


def test_build_stale_in_progress_recovery_allows_next_dispatch(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        run_payload(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        seed_stale_in_progress_task(root, status="review_in_progress", owner_slot="review-1", minutes_ago=25)
        events_path = root / "reports" / "optimus-prime" / "controller" / "EVENTS.jsonl"
        events_path.parent.mkdir(parents=True, exist_ok=True)
        events_path.write_text("", encoding="utf-8")
        monkeypatch.setattr(
            MODULE,
            "_run_controller_cycle",
            lambda _req: {
                "ok": False,
                "status": "running",
                "terminal_reason": None,
                "last_cycle_number": 1,
                "events_path": str(events_path),
            },
        )
        monkeypatch.setattr(MODULE, "_active_worker_slots", lambda _root: set())
        dispatch_calls = {"count": 0}

        def fake_dispatch(req, plan, state, build, *_):
            dispatch_calls["count"] += 1
            return {"ok": True, "status": "noop"}

        monkeypatch.setattr(MODULE, "_dispatch_next_task", fake_dispatch)
        out = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert out["status"] == "running_needs_resume"
        assert dispatch_calls["count"] == 1
        assert any(item.get("code") == "stale_in_progress_recovered" for item in out.get("warnings", []))


def test_stale_in_progress_blocked_then_recovers_when_slot_clears(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        run_payload(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        task_id = seed_stale_in_progress_task(root, status="dev_in_progress", owner_slot="dev-1", minutes_ago=30)
        events_path = root / "reports" / "optimus-prime" / "controller" / "EVENTS.jsonl"
        events_path.parent.mkdir(parents=True, exist_ok=True)
        events_path.write_text("", encoding="utf-8")
        monkeypatch.setattr(
            MODULE,
            "_run_controller_cycle",
            lambda _req: {
                "ok": False,
                "status": "running",
                "terminal_reason": None,
                "last_cycle_number": 1,
                "events_path": str(events_path),
            },
        )
        dispatch_calls = {"count": 0}

        def fake_dispatch(req, plan, state, build, *_):
            dispatch_calls["count"] += 1
            return {"ok": True, "status": "noop"}

        monkeypatch.setattr(MODULE, "_dispatch_next_task", fake_dispatch)
        monkeypatch.setattr(MODULE, "_active_worker_slots", lambda _root: {"dev-1"})
        first = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert first["status"] == "running_needs_resume"
        assert dispatch_calls["count"] == 1
        assert any(item.get("code") == "stale_in_progress_blocked" for item in first.get("warnings", []))

        monkeypatch.setattr(MODULE, "_active_worker_slots", lambda _root: set())
        second = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert second["status"] == "running_needs_resume"
        assert dispatch_calls["count"] == 2
        assert any(item.get("code") == "stale_in_progress_recovered" for item in second.get("warnings", []))
        task_state = json.loads((root / "reports" / "optimus-prime" / "planning" / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        row = next(item for item in task_state["tasks"] if item.get("task_id") == task_id)
        assert row["status"] == "queued"


def test_stale_recovery_advances_state_and_enables_dispatch(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        run_payload(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        task_id = seed_stale_in_progress_task(root, status="review_in_progress", owner_slot="review-1", minutes_ago=40)
        events_path = root / "reports" / "optimus-prime" / "controller" / "EVENTS.jsonl"
        events_path.parent.mkdir(parents=True, exist_ok=True)
        events_path.write_text("", encoding="utf-8")
        monkeypatch.setattr(
            MODULE,
            "_run_controller_cycle",
            lambda _req: {
                "ok": False,
                "status": "running",
                "terminal_reason": None,
                "last_cycle_number": 1,
                "events_path": str(events_path),
            },
        )
        monkeypatch.setattr(MODULE, "_active_worker_slots", lambda _root: set())
        dispatch_calls = {"count": 0}

        def fake_dispatch(req, plan, state, build, *_):
            dispatch_calls["count"] += 1
            return {"ok": True, "status": "noop"}

        monkeypatch.setattr(MODULE, "_dispatch_next_task", fake_dispatch)
        out = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert out["status"] == "running_needs_resume"
        assert dispatch_calls["count"] == 1
        assert any(item.get("code") == "stale_in_progress_recovered" for item in out.get("warnings", []))
        task_state = json.loads((root / "reports" / "optimus-prime" / "planning" / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        row = next(item for item in task_state["tasks"] if item.get("task_id") == task_id)
        assert row["status"] == "test_done"


def test_gap_closure_does_not_generate_recursive_gapfix_tasks():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        run_payload(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )

        plan_packets = json.loads((root / "reports" / "optimus-prime" / "planning" / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((root / "reports" / "optimus-prime" / "planning" / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(root / "reports" / "optimus-prime" / "planning" / "BUILD_STATE.json")

        task_state["tasks"][0]["status"] = "blocked"
        task_state["tasks"][0]["owner_slot"] = None

        _, closure_one = MODULE._refresh_gap_artifacts(root, plan_packets, task_state, build_state)
        MODULE._ensure_gap_closure_task_state(root, task_state, closure_one, plan_packets["plan_id"])
        merged = MODULE._merge_plan_with_gap_closure(plan_packets, closure_one)

        closure_tasks = [task for task in task_state["tasks"] if task.get("is_gap_closure")]
        assert closure_tasks
        closure_tasks[0]["status"] = "blocked"
        closure_tasks[0]["owner_slot"] = None

        gaps_two, closure_two = MODULE._refresh_gap_artifacts(root, merged, task_state, build_state)
        open_gaps = [row for row in gaps_two.get("gaps", []) if row.get("status") == "open"]
        assert all(not str(row.get("task_id", "")).startswith("GAPFIX-") for row in open_gaps)
        assert all(
            not any(str(dep).startswith("GAPFIX-") for dep in (task.get("depends_on") or []))
            for task in closure_two.get("tasks", [])
        )


def test_sticky_gap_does_not_auto_close_without_explicit_closure_evidence():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        run_payload(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )

        plan_packets = json.loads((root / "reports" / "optimus-prime" / "planning" / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((root / "reports" / "optimus-prime" / "planning" / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(root / "reports" / "optimus-prime" / "planning" / "BUILD_STATE.json")

        for task in task_state["tasks"]:
            task["status"] = "review_done"
            task["owner_slot"] = None

        gaps_path = root / "reports" / "optimus-prime" / "planning" / "GAPS.json"
        gaps_payload = {
            "schema_version": "1.0",
            "plan_id": plan_packets["plan_id"],
            "updated_at": "2026-01-01T00:00:00Z",
            "gaps": [
                {
                    "gap_id": "gap-sticky-open-1",
                    "phase_id": "phase-1",
                    "task_id": "TASK-001",
                    "requirement_id": None,
                    "severity": "high",
                    "result": "fail",
                    "evidence_ref": "reports/optimus-prime/planning/evidence/TASK-001/TASK_EVIDENCE.json",
                    "opened_at": "2026-01-01T00:00:00Z",
                    "status": "open",
                    "reason": "sticky gap",
                    "closure_task_id": "GAPFIX-ABCDEF01",
                    "last_seen_open_at": "2026-01-01T00:00:00Z",
                    "closure_required": True,
                    "closure_evidence_ref": None,
                    "closed_by_task_id": None,
                    "closed_at": None,
                    "resolution_candidate_at": None,
                }
            ],
        }
        gaps_path.write_text(json.dumps(gaps_payload, indent=2) + "\n", encoding="utf-8")

        gaps_after, _ = MODULE._refresh_gap_artifacts(root, plan_packets, task_state, build_state)
        row = next(item for item in gaps_after["gaps"] if item.get("gap_id") == "gap-sticky-open-1")
        assert row["status"] == "open"


def test_sticky_gap_closes_only_after_explicit_closure_evidence():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        run_payload(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )

        plan_packets = json.loads((root / "reports" / "optimus-prime" / "planning" / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((root / "reports" / "optimus-prime" / "planning" / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(root / "reports" / "optimus-prime" / "planning" / "BUILD_STATE.json")

        for task in task_state["tasks"]:
            task["status"] = "review_done"
            task["owner_slot"] = None

        gaps_path = root / "reports" / "optimus-prime" / "planning" / "GAPS.json"
        gap_id = "gap-sticky-close-1"
        gaps_payload = {
            "schema_version": "1.0",
            "plan_id": plan_packets["plan_id"],
            "updated_at": "2026-01-01T00:00:00Z",
            "gaps": [
                {
                    "gap_id": gap_id,
                    "phase_id": "phase-1",
                    "task_id": "TASK-001",
                    "requirement_id": None,
                    "severity": "high",
                    "result": "fail",
                    "evidence_ref": "reports/optimus-prime/planning/evidence/TASK-001/TASK_EVIDENCE.json",
                    "opened_at": "2026-01-01T00:00:00Z",
                    "status": "open",
                    "reason": "sticky gap",
                    "closure_task_id": f"GAPFIX-{MODULE._sha256(gap_id)[:8].upper()}",
                    "last_seen_open_at": "2026-01-01T00:00:00Z",
                    "closure_required": True,
                    "closure_evidence_ref": None,
                    "closed_by_task_id": None,
                    "closed_at": None,
                    "resolution_candidate_at": None,
                }
            ],
        }
        gaps_path.write_text(json.dumps(gaps_payload, indent=2) + "\n", encoding="utf-8")

        _, closure = MODULE._refresh_gap_artifacts(root, plan_packets, task_state, build_state)
        MODULE._ensure_gap_closure_task_state(root, task_state, closure, plan_packets["plan_id"])
        closure_task = next(task for task in task_state["tasks"] if task.get("is_gap_closure") and task.get("source_gap_id") == gap_id)
        closure_task["status"] = "review_done"
        closure_task["owner_slot"] = None
        evidence_path = MODULE._task_evidence_path(root, closure_task)
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        payload["dev"]["status"] = "done"
        payload["dev"]["dev_ready"] = True
        payload["test"]["status"] = "done"
        payload["review"]["status"] = "done"
        payload["review"]["decision"] = "accepted"
        payload["gate"]["ready_for_test"] = True
        payload["gate"]["ready_for_review"] = True
        payload["gate"]["ready_for_phase_exit"] = True
        payload["summary"]["result"] = "pass"
        payload["summary"]["reason_codes"] = ["closed_gap"]
        evidence_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        gaps_after, _ = MODULE._refresh_gap_artifacts(root, plan_packets, task_state, build_state)
        row = next(item for item in gaps_after["gaps"] if item.get("gap_id") == gap_id)
        assert row["status"] == "closed"
        assert row.get("closed_by_task_id") == closure_task["task_id"]
        assert row.get("closure_evidence_ref")


def test_build_keeps_gap_open_until_explicit_closure_even_after_recovery():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        run_payload(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        planning_root = root / "reports" / "optimus-prime" / "planning"
        build_state_path = planning_root / "BUILD_STATE.json"
        build_state = MODULE._fresh_build_state_payload()
        build_state["open_gap_ids"] = ["gap-sticky-after-recovery-1"]
        build_state["active_gap_closure_phase_id"] = "phase-1"
        build_state_path.write_text(json.dumps(build_state, indent=2) + "\n", encoding="utf-8")

        gaps_path = planning_root / "GAPS.json"
        gaps_path.write_text("{ invalid-json", encoding="utf-8")

        out = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert out["status"] == "running_needs_resume"
        gaps_after = json.loads(gaps_path.read_text(encoding="utf-8"))
        row = next(item for item in gaps_after["gaps"] if item.get("gap_id") == "gap-sticky-after-recovery-1")
        assert row["status"] == "open"


def test_project_done_still_blocked_when_preserved_gap_survives_recovery():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        run_payload(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        done_path = root / "reports" / "optimus-prime" / "control" / "PROJECT_DONE.json"
        done_path.parent.mkdir(parents=True, exist_ok=True)
        done_path.write_text(json.dumps({"status": "done", "evidence": "all scoped tasks complete"}, indent=2) + "\n", encoding="utf-8")

        planning_root = root / "reports" / "optimus-prime" / "planning"
        task_state_path = planning_root / "TASK_EXECUTION_STATE.json"
        task_state = json.loads(task_state_path.read_text(encoding="utf-8"))
        for task in task_state["tasks"]:
            req_id = task["requirement_ids"][0]
            evidence_rel = f"reports/optimus-prime/planning/evidence/{task['task_id']}/TASK_EVIDENCE.json"
            evidence_path = root / evidence_rel
            evidence_payload = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence_payload["dev"]["status"] = "done"
            evidence_payload["dev"]["dev_ready"] = True
            evidence_payload["dev"]["verify_results"] = [{"command": "python3 -m pytest", "passed": True}]
            evidence_payload["test"]["status"] = "done"
            evidence_payload["test"]["verify_results"] = [{"command": "python3 -m pytest", "passed": True}]
            evidence_payload["test"]["uat_results"] = [{"requirement_id": req_id, "passed": True}]
            evidence_payload["review"]["status"] = "done"
            evidence_payload["review"]["decision"] = "accepted"
            evidence_payload["gate"]["ready_for_test"] = True
            evidence_payload["gate"]["ready_for_review"] = True
            evidence_payload["gate"]["ready_for_phase_exit"] = True
            evidence_payload["summary"]["result"] = "pass"
            evidence_payload["summary"]["reason_codes"] = ["completed"]
            evidence_path.write_text(json.dumps(evidence_payload, indent=2) + "\n", encoding="utf-8")
            task["status"] = "review_done"
            task["owner_slot"] = None
            task["evidence"] = {
                "task_evidence_ref": evidence_rel,
                "dev_ready_evidence_ref": evidence_rel,
                "verify_results": [{"command": "python3 -m pytest", "passed": True}],
                "uat_results": [{"requirement_id": req_id, "passed": True}],
            }
        task_state_path.write_text(json.dumps(task_state, indent=2) + "\n", encoding="utf-8")

        build_state_path = planning_root / "BUILD_STATE.json"
        build_state = json.loads(build_state_path.read_text(encoding="utf-8"))
        build_state["open_gap_ids"] = ["gap-preserved-done-1"]
        build_state["active_gap_closure_phase_id"] = "phase-1"
        build_state_path.write_text(json.dumps(build_state, indent=2) + "\n", encoding="utf-8")
        (planning_root / "GAPS.json").write_text("{ invalid-json", encoding="utf-8")

        out = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert out["status"] == "running_needs_resume"
        assert any(item.get("code") == "strict_done_incomplete" for item in out.get("warnings", []))
        gaps_after = json.loads((planning_root / "GAPS.json").read_text(encoding="utf-8"))
        open_ids = {
            row.get("gap_id")
            for row in gaps_after.get("gaps", [])
            if isinstance(row, dict) and row.get("status") == "open"
        }
        assert "gap-preserved-done-1" in open_ids
