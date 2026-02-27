import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


OP_CORE_PATH = Path(__file__).resolve().parents[1] / "op_core.py"
CONTROLLER_SOURCE = Path(__file__).resolve().parents[3] / "skills" / "optimus-cycle-controller" / "scripts" / "optimus_cycle_controller.py"
SPEC = importlib.util.spec_from_file_location("op_core", OP_CORE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def git(cwd: Path, *args: str) -> None:
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



def test_command_normalization_accepts_prefix_variants():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        for value in ["/op-plan", "$op-plan", "op-plan"]:
            req = MODULE.parse_request(
                {
                    "command": value,
                    "repo_root": str(root),
                }
            )
            assert req.command == "op-plan"



def test_map_codebase_fingerprint_stable_when_repo_unchanged():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)

        out1 = run_payload({"command": "/op-map-codebase", "repo_root": str(root)})
        assert out1["ok"] is True
        map1 = json.loads((root / "reports" / "optimus-prime" / "planning" / "MAP_CODEBASE.json").read_text(encoding="utf-8"))

        out2 = run_payload({"command": "op-map-codebase", "repo_root": str(root)})
        assert out2["ok"] is True
        map2 = json.loads((root / "reports" / "optimus-prime" / "planning" / "MAP_CODEBASE.json").read_text(encoding="utf-8"))

        assert map1["map_fingerprint"] == map2["map_fingerprint"]



def test_new_project_auto_maps_when_missing():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)

        out = run_payload(
            {
                "command": "/op-new-project",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        assert out["ok"] is True
        assert (root / "reports" / "optimus-prime" / "planning" / "MAP_CODEBASE.json").exists()
        state = json.loads((root / "reports" / "optimus-prime" / "planning" / "STATE.json").read_text(encoding="utf-8"))
        assert state["baseline_ready"] is True
        assert state["plan_ready"] is False



def test_plan_check_blocks_when_verify_commands_missing():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)

        run_payload(
            {
                "command": "op-new-project",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        state_path = root / "reports" / "optimus-prime" / "planning" / "STATE.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["requirements"][0]["verify_commands"] = []
        state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

        out = run_payload({"command": "/op-plan", "repo_root": str(root)})
        assert out["ok"] is True
        assert out["status"] == "blocked_plan_check"
        state2 = json.loads(state_path.read_text(encoding="utf-8"))
        assert state2["plan_ready"] is False



def test_initialize_chains_map_new_plan():
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
        planning = root / "reports" / "optimus-prime" / "planning"
        assert (planning / "MAP_CODEBASE.json").exists()
        assert (planning / "PROJECT.md").exists()
        assert (planning / "PLAN_CHECK.json").exists()



def test_build_preflight_blocks_without_baseline():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)

        out = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
            }
        )
        assert out["ok"] is False
        assert out["status"] == "blocked_preflight"


def test_op_build_default_sleep_minutes_is_five():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        req = MODULE.parse_request({"command": "/op-build", "repo_root": str(root)})
        assert req.sleep_minutes == 5.0


def test_op_plan_emits_task_execution_state():
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
        task_state_path = root / "reports" / "optimus-prime" / "planning" / "TASK_EXECUTION_STATE.json"
        assert task_state_path.exists()
        task_state = json.loads(task_state_path.read_text(encoding="utf-8"))
        assert isinstance(task_state.get("tasks"), list)
        assert len(task_state["tasks"]) > 0


def test_build_preflight_blocks_when_task_state_missing():
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
        task_state_path = root / "reports" / "optimus-prime" / "planning" / "TASK_EXECUTION_STATE.json"
        task_state_path.unlink()
        out = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
            }
        )
        assert out["ok"] is False
        assert out["status"] == "blocked_preflight"


def test_build_lock_conflict_when_loop_lock_exists():
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
        lock_path = root / "reports" / "optimus-prime" / "planning" / "BUILD_LOOP.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "lock_id": "existing-lock",
                    "pid": os.getpid(),
                    "acquired_at": "2026-01-01T00:00:00Z",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        out = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
            }
        )
        assert out["ok"] is False
        assert out["status"] == "lock_conflict"


def test_build_does_not_escalate_on_unknown_fingerprint():
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
        out = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 6,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert out["ok"] is False
        assert out["status"] == "running_needs_resume"
        assert not any(item.get("code") == "strategy_escalated" for item in out["warnings"])



def test_build_escalates_strategy_after_five_attempts():
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

        runtime_health = root / "reports" / "optimus-prime" / "runtime" / "RUNTIME_HEALTH.json"
        runtime_health.parent.mkdir(parents=True, exist_ok=True)
        runtime_health.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "updated_at": "2026-01-01T00:00:00Z",
                    "test_train_mode": "final-stage",
                    "gate_state": "blocked",
                    "consecutive_passes": 0,
                    "required_passes": 2,
                    "pipeline_checks": [],
                    "profile_checks": [],
                    "both_sources_pass": False,
                    "last_failure_fingerprint": "runtime|health|blocked",
                    "next_heal_allowed_at": None,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        out = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 6,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert out["ok"] is False
        assert out["status"] == "running_needs_resume"
        assert any(item.get("code") == "strategy_escalated" for item in out["warnings"])



def test_build_halts_on_hard_stop_all_rate_gates_blocking():
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

        rate_path = root / "reports" / "optimus-prime" / "PROFILE_RATE_REGISTRY.json"
        rate_path.parent.mkdir(parents=True, exist_ok=True)
        rate_path.write_text(
            json.dumps(
                {
                    "profiles": {
                        "codex": {
                            "five_hour": {"remaining_percent": 1, "gated": True, "reset_at": "2099-01-01T00:00:00Z"},
                            "weekly": {"remaining_percent": 1},
                            "recommended_action": "wind_down",
                        }
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        out = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert out["ok"] is False
        assert out["status"] == "blocked_terminal"
        assert out["data"]["terminal_reason"] == "all_rate_gates_blocking"


def test_build_rate_gate_under_two_hours_sleeps_and_resumes():
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

        soon = (datetime.now(timezone.utc) + timedelta(minutes=30)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        rate_path = root / "reports" / "optimus-prime" / "PROFILE_RATE_REGISTRY.json"
        rate_path.parent.mkdir(parents=True, exist_ok=True)
        rate_path.write_text(
            json.dumps(
                {
                    "profiles": {
                        "codex": {
                            "five_hour": {"remaining_percent": 1, "gated": True, "reset_at": soon},
                            "weekly": {"remaining_percent": 1},
                            "recommended_action": "wind_down",
                        }
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        out = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert out["ok"] is False
        assert out["status"] == "running_needs_resume"



def test_build_completes_when_project_done_evidence_valid():
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

        done_path = root / "reports" / "optimus-prime" / "control" / "PROJECT_DONE.json"
        done_path.parent.mkdir(parents=True, exist_ok=True)
        done_path.write_text(
            json.dumps({"status": "done", "evidence": "all scoped tasks complete"}, indent=2) + "\n",
            encoding="utf-8",
        )

        task_state_path = root / "reports" / "optimus-prime" / "planning" / "TASK_EXECUTION_STATE.json"
        task_state = json.loads(task_state_path.read_text(encoding="utf-8"))
        for task in task_state["tasks"]:
            req_id = task["requirement_ids"][0]
            task["status"] = "review_done"
            task["owner_slot"] = None
            task["evidence"] = {
                "dev_ready_evidence_ref": f"reports/optimus-prime/planning/evidence/{task['task_id']}/DEV_READY.json",
                "verify_results": [{"command": "python3 -m pytest", "passed": True}],
                "uat_results": [{"requirement_id": req_id, "passed": True}],
            }
        task_state_path.write_text(json.dumps(task_state, indent=2) + "\n", encoding="utf-8")

        out = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert out["ok"] is True
        assert out["status"] == "completed"



def test_build_resume_uses_existing_state_without_orphaning_progress():
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

        state_path = root / "reports" / "optimus-prime" / "planning" / "BUILD_STATE.json"
        state1 = json.loads(state_path.read_text(encoding="utf-8"))
        build_id_1 = state1["build_id"]
        last_cycle_1 = state1["last_cycle"]

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

        state2 = json.loads(state_path.read_text(encoding="utf-8"))
        assert state2["build_id"] == build_id_1
        assert state2["last_cycle"] > last_cycle_1
        assert isinstance(state2.get("cycle_gate_decision"), dict)
        assert isinstance(state2.get("remediation_state"), dict)
        assert isinstance(state2.get("offset_recovery"), dict)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
