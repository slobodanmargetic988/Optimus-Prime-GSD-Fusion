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


def write_schema_invalid_tasks_artifact(path: Path, *, plan_id: str = "plan-test") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "plan_id": plan_id,
                "generated_at": "2026-01-01T00:00:00Z",
                "tasks": {"invalid": True},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def write_schema_invalid_gap_closure_artifact(
    path: Path,
    *,
    plan_id: str | None = "plan-test",
    tasks: object | None = None,
) -> None:
    payload: dict[str, object] = {
        "schema_version": "1.0",
        "generated_at": "2026-01-01T00:00:00Z",
        "tasks": [] if tasks is None else tasks,
    }
    if plan_id is not None:
        payload["plan_id"] = plan_id
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def assert_build_lock_released(root: Path) -> None:
    lock_path = root / "reports" / "optimus-prime" / "planning" / "BUILD_LOOP.lock"
    assert not lock_path.exists()



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


def test_command_normalization_accepts_new_commands():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        cases = {
            "/op-health": "op-health",
            "$op-status": "op-status",
            "op-report": "op-report",
            "op-resume": "op-resume",
        }
        for raw, expected in cases.items():
            req = MODULE.parse_request({"command": raw, "repo_root": str(root)})
            assert req.command == expected



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



def test_initialize_seeds_rate_registry_once_when_missing(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        calls: list[Path] = []

        def fake_seed(
            repo_root: Path,
            *,
            stage: str = "build_loop",
            force_refresh: bool = False,
            emit_success_warning: bool = True,
        ):
            calls.append(repo_root)
            assert stage == "initialize"
            assert force_refresh is False
            assert emit_success_warning is True
            return [{"code": "rate_registry_seeded", "message": "ok", "stage": stage}]

        monkeypatch.setattr(MODULE, "_seed_rate_registry_if_missing", fake_seed)
        out = run_payload(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )

        assert out["ok"] is True
        assert len(calls) == 1
        assert any(item.get("code") == "rate_registry_seeded" for item in out.get("warnings", []))


def test_seed_rate_registry_skips_when_registry_exists(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        registry_path = root / "reports" / "optimus-prime" / "PROFILE_RATE_REGISTRY.json"
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text(
            json.dumps({"profiles": {"codex": {"recommended_action": "continue"}}}, indent=2) + "\n",
            encoding="utf-8",
        )

        def fail_run(*_args, **_kwargs):
            raise AssertionError("snapshot script should not run when registry already exists")

        monkeypatch.setattr(MODULE, "_run", fail_run)
        warnings = MODULE._seed_rate_registry_if_missing(root, stage="initialize")
        assert warnings == []


def test_new_project_creates_gitignore_when_missing():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        gitignore_path = root / ".gitignore"
        gitignore_path.unlink(missing_ok=True)

        out = run_payload(
            {
                "command": "/op-new-project",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )

        assert out["ok"] is True
        assert gitignore_path.exists()
        content = gitignore_path.read_text(encoding="utf-8")
        assert MODULE.OPTIMUS_GITIGNORE_BEGIN in content
        assert MODULE.OPTIMUS_GITIGNORE_END in content
        for entry in MODULE.OPTIMUS_GITIGNORE_LINES[1:-1]:
            assert entry in content


def test_new_project_appends_managed_gitignore_block_preserving_user_lines():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        gitignore_path = root / ".gitignore"
        original = "*.pyc\n.cache/\n"
        gitignore_path.write_text(original, encoding="utf-8")

        out = run_payload(
            {
                "command": "/op-new-project",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )

        assert out["ok"] is True
        content = gitignore_path.read_text(encoding="utf-8")
        assert content.startswith(original)
        assert content.count(MODULE.OPTIMUS_GITIGNORE_BEGIN) == 1
        assert content.count(MODULE.OPTIMUS_GITIGNORE_END) == 1


def test_new_project_replaces_existing_managed_gitignore_block_without_duplicate():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        gitignore_path = root / ".gitignore"
        gitignore_path.write_text(
            "\n".join(
                [
                    "node_modules/",
                    MODULE.OPTIMUS_GITIGNORE_BEGIN,
                    "/reports/optimus-prime/old/**",
                    MODULE.OPTIMUS_GITIGNORE_END,
                    ".venv/",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        out = run_payload(
            {
                "command": "/op-new-project",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )

        assert out["ok"] is True
        content = gitignore_path.read_text(encoding="utf-8")
        assert content.count(MODULE.OPTIMUS_GITIGNORE_BEGIN) == 1
        assert content.count(MODULE.OPTIMUS_GITIGNORE_END) == 1
        assert "/reports/optimus-prime/old/**" not in content
        assert "node_modules/" in content
        assert ".venv/" in content


def test_new_project_repairs_corrupt_managed_gitignore_block_missing_end():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        gitignore_path = root / ".gitignore"
        gitignore_path.write_text(
            "\n".join(
                [
                    "node_modules/",
                    MODULE.OPTIMUS_GITIGNORE_BEGIN,
                    "/reports/optimus-prime/old/**",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        out = run_payload(
            {
                "command": "/op-new-project",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )

        assert out["ok"] is True
        content = gitignore_path.read_text(encoding="utf-8")
        assert content.count(MODULE.OPTIMUS_GITIGNORE_BEGIN) == 1
        assert content.count(MODULE.OPTIMUS_GITIGNORE_END) == 1
        assert "/reports/optimus-prime/old/**" not in content
        assert "node_modules/" in content


def test_new_project_preserves_existing_user_reports_wildcard_line():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        gitignore_path = root / ".gitignore"
        gitignore_path.write_text("reports/*\n", encoding="utf-8")

        out = run_payload(
            {
                "command": "/op-new-project",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )

        assert out["ok"] is True
        content = gitignore_path.read_text(encoding="utf-8")
        assert "reports/*" in content
        assert content.count(MODULE.OPTIMUS_GITIGNORE_BEGIN) == 1


def test_gitignore_write_failure_is_silently_ignored_in_bootstrap_commands(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        original_write_text = MODULE.Path.write_text

        def flaky_write_text(self: Path, *args: object, **kwargs: object):
            if self.name == ".gitignore":
                raise OSError("simulated gitignore write failure")
            return original_write_text(self, *args, **kwargs)

        monkeypatch.setattr(MODULE.Path, "write_text", flaky_write_text, raising=False)

        new_out = run_payload(
            {
                "command": "/op-new-project",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        init_out = run_payload(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )

        assert new_out["ok"] is True
        assert init_out["ok"] is True


def test_gitignore_helper_only_invoked_by_bootstrap_commands(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        calls: list[Path] = []

        def recorder(repo_root: Path) -> None:
            calls.append(repo_root)

        monkeypatch.setattr(MODULE, "_ensure_managed_gitignore_block", recorder)

        run_payload({"command": "/op-map-codebase", "repo_root": str(root)})
        assert len(calls) == 0

        run_payload(
            {
                "command": "/op-new-project",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        assert len(calls) == 1

        run_payload(
            {
                "command": "/op-plan",
                "repo_root": str(root),
            }
        )
        assert len(calls) == 1

        run_payload(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        # /op-initialize invokes helper directly and once again via /op-new-project.
        assert len(calls) == 3


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


def test_build_preflight_blocks_on_malformed_state_json():
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
        state_path = root / "reports" / "optimus-prime" / "planning" / "STATE.json"
        state_path.write_text("{ invalid-json", encoding="utf-8")
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
        assert any(item.get("code") == "state_payload_invalid" for item in out.get("warnings", []))


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


def test_operator_stop_halts_running_workers_and_records_ledger(monkeypatch: pytest.MonkeyPatch):
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
        task_state = json.loads(task_state_path.read_text(encoding="utf-8"))
        task_id = task_state["tasks"][0]["task_id"]
        task_state["tasks"][0]["status"] = "dev_in_progress"
        task_state["tasks"][0]["owner_slot"] = "dev-1"
        task_state_path.write_text(json.dumps(task_state, indent=2) + "\n", encoding="utf-8")

        registry_path = root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text(
            json.dumps(
                {
                    "workers": [
                        {
                            "slot": "dev-1",
                            "session_state": "running",
                            "active_task": task_id,
                            "dispatch_pid": 12345,
                        }
                    ]
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        stop_marker = root / "reports" / "optimus-prime" / "control" / "OPERATOR_STOP.json"
        stop_marker.parent.mkdir(parents=True, exist_ok=True)
        stop_marker.write_text(json.dumps({"stop": True, "reason": "manual stop"}, indent=2) + "\n", encoding="utf-8")

        alive = {12345}

        def fake_pid_is_running(pid: int) -> bool:
            return pid in alive

        def fake_kill(pid: int, sig: int) -> None:
            if pid == 12345 and sig == MODULE.signal.SIGTERM:
                alive.discard(pid)

        monkeypatch.setattr(MODULE, "_pid_is_running", fake_pid_is_running)
        monkeypatch.setattr(MODULE.os, "kill", fake_kill)

        out = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert out["status"] == "stopped_operator"
        warning_codes = {item.get("code") for item in out.get("warnings", [])}
        assert "operator_stop_applied" in warning_codes
        assert "operator_stop_worker_terminated" in warning_codes
        assert "operator_stop_marker_consumed" in warning_codes

        assert not stop_marker.exists()
        archived = list((root / "reports" / "optimus-prime" / "control").glob("OPERATOR_STOP.applied.*.json"))
        assert archived

        stop_state = json.loads((root / "reports" / "optimus-prime" / "control" / "OPERATOR_STOP_STATE.json").read_text(encoding="utf-8"))
        assert stop_state["reconcile_pending"] is True
        assert task_id in stop_state["affected_task_ids"]

        build_state = json.loads((root / "reports" / "optimus-prime" / "planning" / "BUILD_STATE.json").read_text(encoding="utf-8"))
        assert build_state["operator_stop"]["reconcile_pending"] is True
        assert task_id in build_state["stop_affected_task_ids"]

        registry_after = json.loads(registry_path.read_text(encoding="utf-8"))
        assert registry_after["workers"][0]["session_state"] == "stopped_operator"


def test_operator_stop_force_kill_path_when_term_does_not_exit(monkeypatch: pytest.MonkeyPatch):
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
        task_state = json.loads(task_state_path.read_text(encoding="utf-8"))
        task_id = task_state["tasks"][0]["task_id"]
        task_state["tasks"][0]["status"] = "dev_in_progress"
        task_state["tasks"][0]["owner_slot"] = "dev-1"
        task_state_path.write_text(json.dumps(task_state, indent=2) + "\n", encoding="utf-8")

        registry_path = root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text(
            json.dumps(
                {
                    "workers": [
                        {
                            "slot": "dev-1",
                            "session_state": "running",
                            "active_task": task_id,
                            "dispatch_pid": 23456,
                        }
                    ]
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        stop_marker = root / "reports" / "optimus-prime" / "control" / "OPERATOR_STOP.json"
        stop_marker.parent.mkdir(parents=True, exist_ok=True)
        stop_marker.write_text(
            json.dumps({"stop": True, "term_grace_sec": 1, "kill_grace_sec": 1}, indent=2) + "\n",
            encoding="utf-8",
        )

        alive = {23456}
        wait_calls = {"count": 0}

        def fake_pid_is_running(pid: int) -> bool:
            return pid in alive

        def fake_kill(pid: int, sig: int) -> None:
            if pid == 23456 and sig == MODULE.signal.SIGKILL:
                alive.discard(pid)

        def fake_wait(pid: int, timeout_sec: int) -> bool:
            wait_calls["count"] += 1
            if wait_calls["count"] == 1:
                return False
            return True

        monkeypatch.setattr(MODULE, "_pid_is_running", fake_pid_is_running)
        monkeypatch.setattr(MODULE.os, "kill", fake_kill)
        monkeypatch.setattr(MODULE, "_wait_pid_exit", fake_wait)

        out = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert out["status"] == "stopped_operator"
        assert any(item.get("code") == "operator_stop_worker_force_killed" for item in out.get("warnings", []))


def test_build_operator_stop_io_failure_returns_blocked_not_stopped(monkeypatch: pytest.MonkeyPatch):
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
        marker = root / "reports" / "optimus-prime" / "control" / "OPERATOR_STOP.json"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps({"stop": True, "reason": "io-fail"}, indent=2) + "\n", encoding="utf-8")

        def fail_archive(*_args, **_kwargs):
            raise OSError("simulated archive failure")

        monkeypatch.setattr(MODULE, "_archive_operator_stop_marker", fail_archive)
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
        assert any(item.get("code") == "operator_stop_apply_failed" for item in out.get("errors", []))
        assert any(item.get("code") == "operator_stop_apply_failed" for item in out.get("warnings", []))
        assert marker.exists()
        assert_build_lock_released(root)


def test_operator_stop_targets_live_pid_even_when_state_not_running(monkeypatch: pytest.MonkeyPatch):
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
        task_state = json.loads(task_state_path.read_text(encoding="utf-8"))
        task_id = task_state["tasks"][0]["task_id"]
        task_state["tasks"][0]["status"] = "dev_in_progress"
        task_state["tasks"][0]["owner_slot"] = "dev-1"
        task_state_path.write_text(json.dumps(task_state, indent=2) + "\n", encoding="utf-8")

        registry_path = root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text(
            json.dumps(
                {
                    "workers": [
                        {
                            "slot": "dev-1",
                            "session_state": "idle",
                            "active_task": task_id,
                            "dispatch_pid": 34567,
                        }
                    ]
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        marker = root / "reports" / "optimus-prime" / "control" / "OPERATOR_STOP.json"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps({"stop": True}, indent=2) + "\n", encoding="utf-8")

        alive = {34567}
        kill_calls: list[tuple[int, int]] = []

        def fake_pid_is_running(pid: int) -> bool:
            return pid in alive

        def fake_kill(pid: int, sig: int) -> None:
            kill_calls.append((pid, int(sig)))
            if pid == 34567 and sig == MODULE.signal.SIGTERM:
                alive.discard(pid)

        monkeypatch.setattr(MODULE, "_pid_is_running", fake_pid_is_running)
        monkeypatch.setattr(MODULE.os, "kill", fake_kill)

        out = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert out["status"] == "stopped_operator"
        assert any(pid == 34567 and sig == MODULE.signal.SIGTERM for pid, sig in kill_calls)


def test_operator_stop_apply_failure_does_not_consume_marker(monkeypatch: pytest.MonkeyPatch):
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
        marker = root / "reports" / "optimus-prime" / "control" / "OPERATOR_STOP.json"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps({"stop": True, "reason": "simulated failure"}, indent=2) + "\n", encoding="utf-8")

        def fail_apply(*_args, **_kwargs):
            raise MODULE.OpError("operator_stop_apply_failed", "simulated apply failure", stage="build_loop")

        monkeypatch.setattr(MODULE, "_apply_operator_stop", fail_apply)

        out = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert out["status"] == "blocked_terminal"
        assert any(item.get("code") == "operator_stop_apply_failed" for item in out.get("errors", []))
        assert marker.exists()


def test_build_lock_released_after_operator_stop_failure(monkeypatch: pytest.MonkeyPatch):
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
        marker = root / "reports" / "optimus-prime" / "control" / "OPERATOR_STOP.json"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps({"stop": True}, indent=2) + "\n", encoding="utf-8")

        def fail_apply(*_args, **_kwargs):
            raise MODULE.OpError("operator_stop_apply_failed", "simulated apply failure", stage="build_loop")

        monkeypatch.setattr(MODULE, "_apply_operator_stop", fail_apply)

        out = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert out["status"] == "blocked_terminal"
        assert_build_lock_released(root)


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


def test_build_invalid_runtime_health_json_degrades_with_warning():
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
        runtime_health.write_text("{ invalid-json", encoding="utf-8")

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
        assert any(item.get("code") == "runtime_health_invalid_json" for item in out["warnings"])
        assert not any(item.get("code") == "strategy_escalated" for item in out["warnings"])


def test_build_invalid_blockers_log_bytes_degrades_with_warning():
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
        blockers = root / "reports" / "optimus-prime" / "BLOCKERS.jsonl"
        blockers.parent.mkdir(parents=True, exist_ok=True)
        blockers.write_bytes(b"\xff\xfe\x80")

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
        assert any(item.get("code") == "blockers_log_unreadable" for item in out["warnings"])


def test_build_invalid_gap_retry_policy_does_not_crash():
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
        build_state["gap_retry_policy"] = {"max_attempts": "not-a-number"}
        build_state["gap_retry_attempts"] = {"gap-bad": "bad"}
        build_state_path.write_text(json.dumps(build_state, indent=2) + "\n", encoding="utf-8")

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


def test_gap_closure_retry_exhausts_after_five_attempts(monkeypatch: pytest.MonkeyPatch):
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
        req = MODULE.parse_request(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
            }
        )
        plan_packets = json.loads((root / "reports" / "optimus-prime" / "planning" / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((root / "reports" / "optimus-prime" / "planning" / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(root / "reports" / "optimus-prime" / "planning" / "BUILD_STATE.json")

        for task in task_state["tasks"]:
            task["status"] = "review_done"
            task["owner_slot"] = None
        task_state["tasks"][0]["status"] = "blocked"
        task_state["tasks"][0]["owner_slot"] = None

        _, gap_closure_payload = MODULE._refresh_gap_artifacts(root, plan_packets, task_state, build_state)
        MODULE._ensure_gap_closure_task_state(root, task_state, gap_closure_payload, plan_packets["plan_id"])
        merged_plan = MODULE._merge_plan_with_gap_closure(plan_packets, gap_closure_payload)
        gap_tasks = [task for task in task_state["tasks"] if task.get("is_gap_closure")]
        assert gap_tasks
        closure_task = gap_tasks[0]
        closure_task["status"] = "blocked"
        closure_task["owner_slot"] = None
        active_phase_id = closure_task["phase_id"]
        for other in gap_tasks[1:]:
            other["status"] = "review_done"
            other["owner_slot"] = None
        source_gap_id = closure_task.get("source_gap_id")
        assert source_gap_id

        def fake_dispatch(*_args, **_kwargs):
            closure_task["status"] = "blocked"
            closure_task["owner_slot"] = None
            return {"ok": False, "status": "blocked", "reason": "forced_test_failure"}

        monkeypatch.setattr(MODULE, "_dispatch_task_packet", fake_dispatch)

        for _ in range(4):
            result = MODULE._dispatch_next_task(req, merged_plan, task_state, build_state, active_phase_id)
            assert result.get("reason") != "gap_retry_exhausted"

        fifth = MODULE._dispatch_next_task(req, merged_plan, task_state, build_state, active_phase_id)
        assert fifth.get("reason") == "gap_retry_exhausted"
        assert fifth.get("warning", {}).get("code") == "gap_retry_exhausted"

        sixth = MODULE._dispatch_next_task(req, merged_plan, task_state, build_state, active_phase_id)
        assert sixth.get("reason") == "gap_closure_retry_suppressed"
        assert sixth.get("warning", {}).get("code") == "gap_closure_retry_suppressed"
        assert build_state["gap_retry_attempts"][source_gap_id] == 5
        assert source_gap_id in build_state["gap_retry_exhausted_ids"]


def test_stale_in_progress_blocked_when_slot_active():
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
        task_state = json.loads(
            (root / "reports" / "optimus-prime" / "planning" / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8")
        )
        build_state = MODULE._fresh_build_state_payload()
        task = task_state["tasks"][0]
        task["status"] = "dev_in_progress"
        task["owner_slot"] = "dev-1"
        task["last_progress_at"] = "2000-01-01T00:00:00Z"

        original_slots = MODULE._active_worker_slots
        MODULE._active_worker_slots = lambda _root: {"dev-1"}  # type: ignore[assignment]
        try:
            warnings = MODULE._recover_stale_in_progress_tasks(root, task_state, build_state)
        finally:
            MODULE._active_worker_slots = original_slots  # type: ignore[assignment]
        assert any(item.get("code") == "stale_in_progress_blocked" for item in warnings)
        assert task["status"] == "dev_in_progress"
        assert task["owner_slot"] == "dev-1"


def test_stale_in_progress_missing_last_progress_at_recovers():
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
        task_state = json.loads(
            (root / "reports" / "optimus-prime" / "planning" / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8")
        )
        build_state = MODULE._fresh_build_state_payload()
        task = task_state["tasks"][0]
        task["status"] = "dev_in_progress"
        task["owner_slot"] = "dev-1"
        task["last_progress_at"] = None
        task["updated_at"] = None

        original_slots = MODULE._active_worker_slots
        MODULE._active_worker_slots = lambda _root: set()  # type: ignore[assignment]
        try:
            warnings = MODULE._recover_stale_in_progress_tasks(root, task_state, build_state)
        finally:
            MODULE._active_worker_slots = original_slots  # type: ignore[assignment]
        recovered = [item for item in warnings if item.get("code") == "stale_in_progress_recovered"]
        assert recovered
        assert recovered[0].get("reason") == "missing_last_progress_at"
        assert task["status"] == "queued"
        assert task["owner_slot"] is None


def test_strategy_repair_uses_state_derived_mode(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        runtime_script = root / "skills" / "runtime-coordinator" / "scripts" / "runtime_coordinator.py"
        runtime_script.parent.mkdir(parents=True, exist_ok=True)
        runtime_script.write_text("print('{}')\n", encoding="utf-8")
        state_path = root / "reports" / "optimus-prime" / "TEST_TRAIN_STATE.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({"test_train_mode": "off"}, indent=2) + "\n", encoding="utf-8")
        req = MODULE.parse_request({"command": "/op-build", "repo_root": str(root), "dry_run": True})

        seen: dict[str, str] = {}

        def fake_run(cmd, *, cwd, stdin_text=None):
            seen["test_train_mode"] = json.loads(stdin_text)["test_train_mode"]
            return 0, json.dumps({"ok": True}), ""

        monkeypatch.setattr(MODULE, "_run", fake_run)
        result = MODULE._apply_strategy_action(req, "self_heal")
        assert result["status"] == "applied"
        assert seen["test_train_mode"] == "off"


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



def test_build_halts_on_hard_stop_all_rate_gates_blocking(monkeypatch: pytest.MonkeyPatch):
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

        monkeypatch.setattr(
            MODULE,
            "_seed_rate_registry_if_missing",
            lambda *_args, **_kwargs: [],
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


def test_build_all_rate_gates_blocking_with_invalid_registry_continues_with_warning(monkeypatch: pytest.MonkeyPatch):
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
        rate_path.write_text("{ invalid-json", encoding="utf-8")

        events_path = root / "reports" / "optimus-prime" / "controller" / "EVENTS.jsonl"
        events_path.parent.mkdir(parents=True, exist_ok=True)
        events_path.write_text("", encoding="utf-8")

        dispatch_calls = {"count": 0}

        monkeypatch.setattr(
            MODULE,
            "_seed_rate_registry_if_missing",
            lambda *_args, **_kwargs: [],
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
        assert out["ok"] is False
        assert out["status"] == "running_needs_resume"
        assert dispatch_calls["count"] == 1
        assert any(item.get("code") == "rate_registry_invalid_ignored" for item in out["warnings"])


def test_seed_rate_registry_warns_when_snapshot_script_unavailable(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        rate_path = root / "reports" / "optimus-prime" / "PROFILE_RATE_REGISTRY.json"
        rate_path.unlink(missing_ok=True)

        monkeypatch.setattr(MODULE, "_resolve_rate_snapshot_script", lambda _repo_root: None)
        warnings = MODULE._seed_rate_registry_if_missing(root)

        assert any(item.get("code") == "rate_registry_seed_unavailable" for item in warnings)
        assert not rate_path.exists()


def test_build_seeds_rate_registry_before_controller_cycle(monkeypatch: pytest.MonkeyPatch):
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
        rate_path.unlink(missing_ok=True)
        events_path = root / "reports" / "optimus-prime" / "controller" / "EVENTS.jsonl"
        events_path.parent.mkdir(parents=True, exist_ok=True)
        events_path.write_text("", encoding="utf-8")

        call_order: list[str] = []
        original_run = MODULE._run

        def wrapped_run(cmd, *, cwd, stdin_text=None):
            script_name = Path(cmd[1]).name if len(cmd) > 1 else ""
            if script_name == "read_codex_rate_snapshots.py":
                call_order.append("snapshot")
                payload = {
                    "profiles": {
                        "codex": {
                            "alias": "codex",
                            "five_hour": {"remaining_percent": 80},
                            "weekly": {"remaining_percent": 70},
                            "recommended_action": "continue",
                        }
                    },
                    "profile_running_mode": "single-profile",
                }
                return 0, json.dumps(payload), ""
            return original_run(cmd, cwd=cwd, stdin_text=stdin_text)

        monkeypatch.setattr(MODULE, "_run", wrapped_run)
        monkeypatch.setattr(
            MODULE,
            "_run_controller_cycle",
            lambda _req: (
                call_order.append("controller")
                or {
                    "ok": True,
                    "terminal_reason": None,
                    "last_cycle_number": 1,
                    "events_path": str(events_path),
                }
            ),
        )
        monkeypatch.setattr(MODULE, "_dispatch_next_task", lambda *_args, **_kwargs: {"ok": True, "status": "noop"})

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
        assert rate_path.exists()
        seeded = json.loads(rate_path.read_text(encoding="utf-8"))
        assert isinstance(seeded.get("profiles"), dict)
        assert "codex" in seeded["profiles"]
        assert "snapshot" in call_order
        assert "controller" in call_order
        assert call_order.index("snapshot") < call_order.index("controller")
        assert not any(item.get("code") == "rate_registry_seeded" for item in out.get("warnings", []))


def test_build_refreshes_rate_registry_each_cycle_even_when_registry_exists(monkeypatch: pytest.MonkeyPatch):
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
            json.dumps({"profiles": {"codex": {"recommended_action": "continue", "marker": "stale"}}}, indent=2) + "\n",
            encoding="utf-8",
        )

        events_path = root / "reports" / "optimus-prime" / "controller" / "EVENTS.jsonl"
        events_path.parent.mkdir(parents=True, exist_ok=True)
        events_path.write_text("", encoding="utf-8")

        calls: dict[str, int] = {"snapshot": 0}
        original_run = MODULE._run

        def wrapped_run(cmd, *, cwd, stdin_text=None):
            script_name = Path(cmd[1]).name if len(cmd) > 1 else ""
            if script_name == "read_codex_rate_snapshots.py":
                calls["snapshot"] += 1
                payload = {
                    "profiles": {
                        "codex": {
                            "alias": "codex",
                            "five_hour": {"remaining_percent": 80},
                            "weekly": {"remaining_percent": 70},
                            "recommended_action": "continue",
                            "marker": "fresh",
                        }
                    },
                    "profile_running_mode": "single-profile",
                }
                return 0, json.dumps(payload), ""
            return original_run(cmd, cwd=cwd, stdin_text=stdin_text)

        monkeypatch.setattr(MODULE, "_run", wrapped_run)
        monkeypatch.setattr(
            MODULE,
            "_run_controller_cycle",
            lambda _req: {
                "ok": True,
                "terminal_reason": None,
                "last_cycle_number": 1,
                "events_path": str(events_path),
            },
        )
        monkeypatch.setattr(MODULE, "_dispatch_next_task", lambda *_args, **_kwargs: {"ok": True, "status": "noop"})

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
        assert calls["snapshot"] == 1
        refreshed = json.loads(rate_path.read_text(encoding="utf-8"))
        assert refreshed["profiles"]["codex"]["marker"] == "fresh"


def test_build_recovers_malformed_gap_closure_and_releases_lock():
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
        gap_closure_path = root / "reports" / "optimus-prime" / "planning" / "GAP_CLOSURE_PLAN_PACKETS.json"
        gap_closure_path.write_text("{ invalid-json", encoding="utf-8")
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
        assert any(item.get("code") == "gap_closure_artifact_invalid" for item in out.get("warnings", []))
        assert any(item.get("code") == "gap_closure_artifact_recovered" for item in out.get("warnings", []))
        lock_path = root / "reports" / "optimus-prime" / "planning" / "BUILD_LOOP.lock"
        assert not lock_path.exists()
        out2 = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert out2["status"] != "lock_conflict"


def test_build_recovers_when_both_gap_artifacts_malformed():
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
        (planning_root / "GAPS.json").write_text("{ invalid-json", encoding="utf-8")
        (planning_root / "GAP_CLOSURE_PLAN_PACKETS.json").write_text("{ invalid-json", encoding="utf-8")
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
        codes = {item.get("code") for item in out.get("warnings", [])}
        assert "gaps_artifact_invalid" in codes
        assert "gap_closure_artifact_invalid" in codes
        assert "gaps_artifact_recovered" in codes
        assert "gap_closure_artifact_recovered" in codes
        assert_build_lock_released(root)


def test_build_recovers_malformed_gaps_with_backup_metadata():
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
        gaps_path = root / "reports" / "optimus-prime" / "planning" / "GAPS.json"
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
        assert any(item.get("code") == "gaps_artifact_invalid" for item in out.get("warnings", []))
        assert any(item.get("code") == "gaps_artifact_recovered" for item in out.get("warnings", []))
        build_state = json.loads((root / "reports" / "optimus-prime" / "planning" / "BUILD_STATE.json").read_text(encoding="utf-8"))
        recovery = build_state.get("gap_artifact_recovery", {})
        assert recovery.get("reason") == "malformed_gap_artifacts"
        assert any("GAPS.json" in item for item in recovery.get("recovered_files", []))
        backups = list((root / "reports" / "optimus-prime" / "planning").glob("GAPS.corrupt.*.json"))
        assert backups


def test_build_recovery_failure_on_single_backup_still_releases_lock(monkeypatch: pytest.MonkeyPatch):
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
        (planning_root / "GAPS.json").write_text("{ invalid-json", encoding="utf-8")

        def fail_backup(path: Path):
            raise MODULE.OpError(
                "state_read_error",
                f"unable to backup corrupted artifact {path}: permission denied",
                stage="state",
            )

        monkeypatch.setattr(MODULE, "_backup_corrupt_file", fail_backup)
        out = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert out["status"] == "blocked_preflight"
        assert any(item.get("code") == "gap_artifact_recovery_failed" for item in out.get("errors", []))
        assert_build_lock_released(root)


def test_build_recovery_preserves_sticky_open_gaps_from_prior_state():
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
        build_state["open_gap_ids"] = ["gap-preserve-001"]
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
        assert any(item.get("code") == "gaps_artifact_recovered" for item in out.get("warnings", []))
        recovered = json.loads(gaps_path.read_text(encoding="utf-8"))
        open_ids = {
            row.get("gap_id")
            for row in recovered.get("gaps", [])
            if isinstance(row, dict) and row.get("status") == "open"
        }
        assert "gap-preserve-001" in open_ids


def test_build_recovery_failure_returns_blocked_preflight_and_releases_lock(monkeypatch: pytest.MonkeyPatch):
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
        gaps_path = root / "reports" / "optimus-prime" / "planning" / "GAPS.json"
        gaps_path.write_text("{ invalid-json", encoding="utf-8")

        def fail_recovery(*_args, **_kwargs):
            raise MODULE.OpError(
                "gap_artifact_recovery_failed",
                "simulated recovery failure",
                stage="build_preflight",
            )

        monkeypatch.setattr(MODULE, "_recover_gap_artifacts_for_build", fail_recovery)
        out = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert out["status"] == "blocked_preflight"
        assert any(item.get("code") == "gap_artifact_recovery_failed" for item in out.get("errors", []))
        assert_build_lock_released(root)


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


def test_op_health_and_status_commands():
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
        health = run_payload({"command": "/op-health", "repo_root": str(root)})
        assert health["ok"] is True
        assert health["status"] == "completed"
        status = run_payload({"command": "/op-status", "repo_root": str(root)})
        assert status["ok"] is True
        assert status["status"] == "completed"
        assert "active_phase_id" in status["data"]


def test_op_status_blocks_not_crashes_on_malformed_plan_packets():
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
        plan_packets_path = root / "reports" / "optimus-prime" / "planning" / "PLAN_PACKETS.json"
        plan_packets_path.write_text("{ invalid-json", encoding="utf-8")

        out = run_payload({"command": "/op-status", "repo_root": str(root)})
        assert out["ok"] is False
        assert out["status"] == "blocked"
        assert any(item.get("code") == "status_artifact_invalid" for item in out.get("warnings", []))
        assert any(item.get("code") == "status_snapshot_degraded" for item in out.get("warnings", []))
        assert out.get("data", {}).get("next_action") == out.get("next_action")


def test_op_status_blocks_not_crashes_on_malformed_build_state():
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
        build_state_path = root / "reports" / "optimus-prime" / "planning" / "BUILD_STATE.json"
        build_state_path.write_text("{ invalid-json", encoding="utf-8")

        out = run_payload({"command": "/op-status", "repo_root": str(root)})
        assert out["ok"] is False
        assert out["status"] == "blocked"
        assert any(item.get("code") == "status_artifact_invalid" for item in out.get("warnings", []))
        assert any(item.get("code") == "status_snapshot_degraded" for item in out.get("warnings", []))
        assert out.get("data", {}).get("next_action") == out.get("next_action")


def test_op_status_blocks_not_crashes_on_malformed_gaps():
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
        gaps_path = root / "reports" / "optimus-prime" / "planning" / "GAPS.json"
        gaps_path.write_text("{ invalid-json", encoding="utf-8")

        out = run_payload({"command": "/op-status", "repo_root": str(root)})
        assert out["ok"] is False
        assert out["status"] == "blocked"
        assert any(item.get("code") == "status_artifact_invalid" for item in out.get("warnings", []))
        assert any(item.get("code") == "status_snapshot_degraded" for item in out.get("warnings", []))
        assert out.get("data", {}).get("next_action") == out.get("next_action")


def test_status_blocks_on_gap_closure_schema_invalid_tasks_field():
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
        closure_path = root / "reports" / "optimus-prime" / "planning" / "GAP_CLOSURE_PLAN_PACKETS.json"
        write_schema_invalid_tasks_artifact(closure_path)
        out = run_payload({"command": "/op-status", "repo_root": str(root)})
        assert out["ok"] is False
        assert out["status"] == "blocked"
        assert any(item.get("code") == "status_artifact_invalid" for item in out.get("warnings", []))
        assert any(item.get("code") == "status_snapshot_degraded" for item in out.get("warnings", []))


def test_status_blocks_on_gap_closure_schema_invalid_plan_id():
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
        closure_path = root / "reports" / "optimus-prime" / "planning" / "GAP_CLOSURE_PLAN_PACKETS.json"
        write_schema_invalid_gap_closure_artifact(closure_path, plan_id="")
        out = run_payload({"command": "/op-status", "repo_root": str(root)})
        assert out["ok"] is False
        assert out["status"] == "blocked"
        assert any(item.get("code") == "status_artifact_invalid" for item in out.get("warnings", []))
        assert any(item.get("code") == "status_snapshot_degraded" for item in out.get("warnings", []))


def test_op_report_shows_running_when_lock_pid_alive(monkeypatch: pytest.MonkeyPatch):
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
        build_state_path = root / "reports" / "optimus-prime" / "planning" / "BUILD_STATE.json"
        build_state_path.parent.mkdir(parents=True, exist_ok=True)
        build_state_path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "updated_at": "2026-01-01T00:00:00Z",
                    "last_cycle": 12,
                    "current_strategy": "self_heal",
                    "current_phase_id": "phase-1",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        lock_path = root / "reports" / "optimus-prime" / "planning" / "BUILD_LOOP.lock"
        lock_path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "lock_id": "test-lock",
                    "pid": 42424,
                    "acquired_at": "2026-01-01T00:00:00Z",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(MODULE, "_pid_is_running", lambda pid: pid == 42424)

        out = run_payload({"command": "/op-report", "repo_root": str(root)})
        assert out["ok"] is True
        assert out["status"] == "running"
        assert out["data"]["build"] == "running"
        assert out["data"]["cycle"] == 12
        assert out["data"]["next"] == "wait (build active)"
        assert out["summary"].startswith("build: running")


def test_op_report_shows_needs_resume_after_bounded_build():
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
        out = run_payload({"command": "/op-report", "repo_root": str(root)})
        assert out["ok"] is True
        assert out["status"] == "needs_resume"
        assert out["data"]["build"] == "needs_resume"
        assert out["data"]["next"] == "/op-resume"


def test_op_health_fails_when_plan_not_ready():
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
        state_path = root / "reports" / "optimus-prime" / "planning" / "STATE.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["plan_ready"] = False
        state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

        health = run_payload({"command": "/op-health", "repo_root": str(root)})
        assert health["ok"] is False
        assert health["status"] == "blocked"
        checks = {item["id"]: item for item in health["data"]["checks"]}
        assert checks["build_preflight_ready"]["passed"] is False


def test_op_health_blocks_instead_of_crashing_on_malformed_state_json():
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
        state_path = root / "reports" / "optimus-prime" / "planning" / "STATE.json"
        state_path.write_text("{ invalid-json", encoding="utf-8")

        health = run_payload({"command": "/op-health", "repo_root": str(root)})
        assert health["ok"] is False
        assert health["status"] == "blocked"
        checks = {item["id"]: item for item in health["data"]["checks"]}
        assert checks["build_preflight_ready"]["passed"] is False


def test_op_health_blocks_on_malformed_gaps_artifact():
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
        gaps_path = root / "reports" / "optimus-prime" / "planning" / "GAPS.json"
        gaps_path.write_text("{ invalid-json", encoding="utf-8")
        health = run_payload({"command": "/op-health", "repo_root": str(root)})
        assert health["ok"] is False
        assert health["status"] == "blocked"
        assert any(item.get("code") == "gaps_artifact_invalid" for item in health.get("warnings", []))
        assert any(item.get("code") == "gap_artifact_integrity_blocked" for item in health.get("errors", []))


def test_op_health_blocks_on_malformed_gap_closure_artifact():
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
        gap_closure_path = root / "reports" / "optimus-prime" / "planning" / "GAP_CLOSURE_PLAN_PACKETS.json"
        gap_closure_path.write_text("{ invalid-json", encoding="utf-8")
        health = run_payload({"command": "/op-health", "repo_root": str(root)})
        assert health["ok"] is False
        assert health["status"] == "blocked"
        assert any(item.get("code") == "gap_closure_artifact_invalid" for item in health.get("warnings", []))
        assert any(item.get("code") == "gap_artifact_integrity_blocked" for item in health.get("errors", []))


def test_health_blocks_on_gap_closure_schema_invalid_tasks_field():
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
        closure_path = root / "reports" / "optimus-prime" / "planning" / "GAP_CLOSURE_PLAN_PACKETS.json"
        write_schema_invalid_tasks_artifact(closure_path)
        out = run_payload({"command": "/op-health", "repo_root": str(root)})
        assert out["ok"] is False
        assert out["status"] == "blocked"
        assert any(item.get("code") == "gap_closure_artifact_invalid" for item in out.get("warnings", []))
        assert any(item.get("code") == "gap_artifact_integrity_blocked" for item in out.get("errors", []))


def test_corruption_policy_matrix_malformed_gaps_across_commands():
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
        (root / "reports" / "optimus-prime" / "planning" / "GAPS.json").write_text("{ invalid-json", encoding="utf-8")

        status = run_payload({"command": "/op-status", "repo_root": str(root)})
        health = run_payload({"command": "/op-health", "repo_root": str(root)})
        build = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        resume = run_payload(
            {
                "command": "/op-resume",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )

        assert status["status"] == "blocked"
        assert health["status"] == "blocked"
        assert build["status"] == "running_needs_resume"
        assert resume["status"] == "running_needs_resume"


def test_op_resume_blocks_without_existing_build_state():
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
        out = run_payload({"command": "/op-resume", "repo_root": str(root), "max_build_cycles": 1, "dry_run": True})
        assert out["ok"] is False
        assert out["status"] == "blocked_preflight"


def test_op_resume_uses_existing_build_state():
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
        resumed = run_payload(
            {
                "command": "/op-resume",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert resumed["status"] == "running_needs_resume"


def test_op_resume_malformed_build_state_backup_and_reset():
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

        planning_root = root / "reports" / "optimus-prime" / "planning"
        build_state_path = planning_root / "BUILD_STATE.json"
        build_state_path.write_text("{ invalid-json", encoding="utf-8")

        resumed = run_payload(
            {
                "command": "/op-resume",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert resumed["status"] in {"running_needs_resume", "blocked_preflight"}
        assert any(item.get("code") == "resume_state_corrupt_reset" for item in resumed.get("warnings", []))

        backups = list(planning_root.glob("BUILD_STATE.corrupt.*.json"))
        assert backups
        repaired_state = json.loads(build_state_path.read_text(encoding="utf-8"))
        recovery = repaired_state.get("state_recovery", {})
        assert recovery.get("reason") == "malformed_build_state"
        assert recovery.get("backup_path")


def test_op_resume_non_numeric_last_cycle_backup_and_reset():
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
        planning_root = root / "reports" / "optimus-prime" / "planning"
        build_state_path = planning_root / "BUILD_STATE.json"
        build_state = json.loads(build_state_path.read_text(encoding="utf-8"))
        build_state["last_cycle"] = "oops"
        build_state_path.write_text(json.dumps(build_state, indent=2) + "\n", encoding="utf-8")

        resumed = run_payload(
            {
                "command": "/op-resume",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert resumed["status"] in {"running_needs_resume", "blocked_preflight"}
        assert any(item.get("code") == "resume_state_corrupt_reset" for item in resumed.get("warnings", []))

        backups = list(planning_root.glob("BUILD_STATE.corrupt.*.json"))
        assert backups
        repaired_state = json.loads(build_state_path.read_text(encoding="utf-8"))
        recovery = repaired_state.get("state_recovery", {})
        assert recovery.get("reason") == "malformed_build_state"
        assert recovery.get("backup_path")


def test_op_resume_requeues_all_dead_stop_affected_in_progress_tasks(monkeypatch: pytest.MonkeyPatch):
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

        planning_root = root / "reports" / "optimus-prime" / "planning"
        task_state_path = planning_root / "TASK_EXECUTION_STATE.json"
        task_state = json.loads(task_state_path.read_text(encoding="utf-8"))
        task_id = task_state["tasks"][0]["task_id"]
        task_state["tasks"][0]["status"] = "dev_in_progress"
        task_state["tasks"][0]["owner_slot"] = "dev-1"
        task_state["tasks"][0]["last_progress_at"] = "2000-01-01T00:00:00Z"
        task_state_path.write_text(json.dumps(task_state, indent=2) + "\n", encoding="utf-8")

        build_state_path = planning_root / "BUILD_STATE.json"
        build_state = json.loads(build_state_path.read_text(encoding="utf-8"))
        build_state["operator_stop"] = {
            "last_stop_id": "stop-test-1",
            "last_applied_at": "2026-01-01T00:00:00Z",
            "reconcile_pending": True,
        }
        build_state["stop_affected_task_ids"] = [task_id]
        build_state_path.write_text(json.dumps(build_state, indent=2) + "\n", encoding="utf-8")

        control_root = root / "reports" / "optimus-prime" / "control"
        control_root.mkdir(parents=True, exist_ok=True)
        (control_root / "OPERATOR_STOP_STATE.json").write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "stop_id": "stop-test-1",
                    "requested_at": "2026-01-01T00:00:00Z",
                    "applied_at": "2026-01-01T00:00:10Z",
                    "stop_mode": "graceful_then_force",
                    "resume_policy": "auto",
                    "marker_path": str(control_root / "OPERATOR_STOP.json"),
                    "marker_archived_path": str(control_root / "OPERATOR_STOP.applied.test.json"),
                    "workers": [],
                    "affected_task_ids": [task_id],
                    "reconcile_pending": True,
                    "reconciled_at": None,
                    "reconcile_results": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        registry_path = root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text(
            json.dumps(
                {
                    "workers": [
                        {
                            "slot": "dev-1",
                            "session_state": "running",
                            "active_task": task_id,
                            "dispatch_pid": 34567,
                        }
                    ]
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        events_path = root / "reports" / "optimus-prime" / "controller" / "EVENTS.jsonl"
        events_path.parent.mkdir(parents=True, exist_ok=True)
        events_path.write_text("", encoding="utf-8")
        monkeypatch.setattr(MODULE, "_pid_is_running", lambda _pid: False)
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
                "command": "/op-resume",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert out["status"] == "running_needs_resume"
        warning_codes = {item.get("code") for item in out.get("warnings", [])}
        assert "resume_post_stop_reconciled" in warning_codes
        assert "resume_task_requeued_after_stop" in warning_codes

        task_state_after = json.loads(task_state_path.read_text(encoding="utf-8"))
        task_after = next(item for item in task_state_after.get("tasks", []) if item.get("task_id") == task_id)
        assert task_after["status"] == "queued"
        assert task_after["owner_slot"] is None

        stop_state_after = json.loads((control_root / "OPERATOR_STOP_STATE.json").read_text(encoding="utf-8"))
        assert stop_state_after["reconcile_pending"] is False
        assert stop_state_after["reconciled_at"]

        registry_after = json.loads(registry_path.read_text(encoding="utf-8"))
        assert registry_after["workers"][0]["session_state"] == "not_running"


def test_op_resume_continues_task_when_worker_alive_and_evidence_progressing(monkeypatch: pytest.MonkeyPatch):
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

        planning_root = root / "reports" / "optimus-prime" / "planning"
        task_state_path = planning_root / "TASK_EXECUTION_STATE.json"
        task_state = json.loads(task_state_path.read_text(encoding="utf-8"))
        task_id = task_state["tasks"][0]["task_id"]
        task_state["tasks"][0]["status"] = "dev_in_progress"
        task_state["tasks"][0]["owner_slot"] = "dev-1"
        task_state["tasks"][0]["last_progress_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        task_state_path.write_text(json.dumps(task_state, indent=2) + "\n", encoding="utf-8")

        evidence_path = root / "reports" / "optimus-prime" / "planning" / "evidence" / task_id / "TASK_EVIDENCE.json"
        evidence_payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        evidence_payload["updated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        evidence_path.write_text(json.dumps(evidence_payload, indent=2) + "\n", encoding="utf-8")

        build_state_path = planning_root / "BUILD_STATE.json"
        build_state = json.loads(build_state_path.read_text(encoding="utf-8"))
        build_state["operator_stop"] = {
            "last_stop_id": "stop-test-2",
            "last_applied_at": "2026-01-01T00:00:00Z",
            "reconcile_pending": True,
        }
        build_state["stop_affected_task_ids"] = [task_id]
        build_state_path.write_text(json.dumps(build_state, indent=2) + "\n", encoding="utf-8")

        control_root = root / "reports" / "optimus-prime" / "control"
        control_root.mkdir(parents=True, exist_ok=True)
        (control_root / "OPERATOR_STOP_STATE.json").write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "stop_id": "stop-test-2",
                    "requested_at": "2026-01-01T00:00:00Z",
                    "applied_at": "2026-01-01T00:00:10Z",
                    "stop_mode": "graceful_then_force",
                    "resume_policy": "auto",
                    "marker_path": str(control_root / "OPERATOR_STOP.json"),
                    "marker_archived_path": str(control_root / "OPERATOR_STOP.applied.test.json"),
                    "workers": [],
                    "affected_task_ids": [task_id],
                    "reconcile_pending": True,
                    "reconciled_at": None,
                    "reconcile_results": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        registry_path = root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text(
            json.dumps(
                {
                    "workers": [
                        {
                            "slot": "dev-1",
                            "session_state": "running",
                            "active_task": task_id,
                            "dispatch_pid": 45678,
                        }
                    ]
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        events_path = root / "reports" / "optimus-prime" / "controller" / "EVENTS.jsonl"
        events_path.parent.mkdir(parents=True, exist_ok=True)
        events_path.write_text("", encoding="utf-8")
        monkeypatch.setattr(MODULE, "_pid_is_running", lambda pid: pid == 45678)
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
                "command": "/op-resume",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert out["status"] == "running_needs_resume"
        assert any(item.get("code") == "resume_task_continued_after_stop" for item in out.get("warnings", []))

        task_state_after = json.loads(task_state_path.read_text(encoding="utf-8"))
        task_after = next(item for item in task_state_after.get("tasks", []) if item.get("task_id") == task_id)
        assert task_after["status"] == "dev_in_progress"
        assert task_after["owner_slot"] == "dev-1"


def test_build_strict_done_blocks_when_sticky_open_gap_exists():
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
        done_path.write_text(json.dumps({"status": "done", "evidence": "all scoped tasks complete"}, indent=2) + "\n", encoding="utf-8")

        task_state_path = root / "reports" / "optimus-prime" / "planning" / "TASK_EXECUTION_STATE.json"
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

        gaps_path = root / "reports" / "optimus-prime" / "planning" / "GAPS.json"
        gap_id = "gap-sticky-001"
        gaps_payload = {
            "schema_version": "1.0",
            "plan_id": "plan-sticky",
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
                    "reason": "sticky open gap",
                    "closure_task_id": "GAPFIX-TEST0001",
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
        (root / "reports" / "optimus-prime" / "planning" / "GAP_CLOSURE_PLAN_PACKETS.json").write_text(
            json.dumps({"schema_version": "1.0", "plan_id": "plan-sticky", "generated_at": "2026-01-01T00:00:00Z", "tasks": []}, indent=2)
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
        assert any(item.get("code") == "strict_done_incomplete" for item in out.get("warnings", []))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
