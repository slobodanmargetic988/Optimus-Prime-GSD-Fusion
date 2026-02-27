import importlib.util
import json
import sys
import tempfile
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
        monkeypatch.setattr(MODULE, "_dispatch_next_task", lambda req, plan, state, build: {"ok": True, "status": "noop"})

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

