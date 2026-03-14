import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest


OP_SIMPLE_BUILD_PATH = Path(__file__).resolve().parents[1] / "op_simple_build.py"
BOSS_PROMPT_PATH = Path(__file__).resolve().parents[2] / "op_simple" / "prompts" / "managers" / "boss.md"
WRAPUP_PROMPT_PATH = Path(__file__).resolve().parents[2] / "op_simple" / "prompts" / "managers" / "wrapup-manager.md"
REVIEWER_PROMPT_PATH = (
    Path(__file__).resolve().parents[2] / "op_simple" / "prompts" / "workers" / "optimus-reviewer" / "README.md"
)
SPEC = importlib.util.spec_from_file_location("op_simple_build", OP_SIMPLE_BUILD_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


@pytest.fixture(autouse=True)
def _force_codex_binary_present(monkeypatch):
    monkeypatch.setattr(MODULE.shutil, "which", lambda _binary: "/usr/bin/codex")


def git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True)
    return (proc.stdout or "").strip()


def build_repo(root: Path) -> None:
    git(root, "init", "-b", "main")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "Test User")
    (root / "README.md").write_text("seed\n", encoding="utf-8")
    git(root, "add", "README.md")
    git(root, "commit", "-m", "seed")


def make_req(root: Path, **overrides: object) -> SimpleNamespace:
    payload = {
        "repo_root": str(root),
        "sleep_minutes": 0,
        "max_build_cycles": 1,
        "max_parallel_workers": 8,
        "dry_run": True,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def test_build_config_defaults_boss_model_and_reasoning(tmp_path: Path) -> None:
    cfg = MODULE._build_config(make_req(tmp_path))
    assert cfg.boss_model == "gpt-5.3-codex"
    assert cfg.boss_reasoning_effort == "xhigh"
    assert cfg.codex_profile is None
    assert cfg.worktrees_parent == MODULE.DEFAULT_WORKTREES_PARENT


def test_build_config_accepts_boss_model_and_reasoning_override(tmp_path: Path) -> None:
    cfg = MODULE._build_config(
        make_req(
            tmp_path,
            boss_model="gpt-5.4-codex-experimental",
            boss_reasoning_effort="medium",
        )
    )
    assert cfg.boss_model == "gpt-5.4-codex-experimental"
    assert cfg.boss_reasoning_effort == "medium"


def test_build_config_accepts_run_base_source_branch_override(tmp_path: Path) -> None:
    cfg = MODULE._build_config(
        make_req(
            tmp_path,
            run_base_source_branch="op-simple-canary-prev",
        )
    )
    assert cfg.run_base_source_branch == "op-simple-canary-prev"


def test_build_config_defaults_executor_settings(tmp_path: Path) -> None:
    cfg = MODULE._build_config(make_req(tmp_path))
    assert cfg.codex_profile is None
    assert cfg.executor_provider == "codex"
    assert cfg.executor_model is None
    assert cfg.blackbox_lane == "free"
    assert cfg.allow_worker_executor_override is False


def test_build_config_defaults_ground_sync_settings(tmp_path: Path) -> None:
    cfg = MODULE._build_config(make_req(tmp_path))
    assert cfg.ground_sync_enabled is True
    assert cfg.ground_sync_every_n_cycles == MODULE.GROUND_SYNC_DEFAULT_EVERY_N_CYCLES
    assert cfg.ground_sync_timeout_seconds == MODULE.GROUND_SYNC_DEFAULT_TIMEOUT_SECONDS


def test_build_config_defaults_cycle_release_settings(tmp_path: Path) -> None:
    cfg = MODULE._build_config(make_req(tmp_path))
    assert cfg.cycle_release_mode == MODULE.DEFAULT_CYCLE_RELEASE_MODE
    assert cfg.cycle_release_timeout_seconds == MODULE.DEFAULT_CYCLE_RELEASE_TIMEOUT_SECONDS
    assert cfg.cycle_release_poll_seconds == MODULE.DEFAULT_CYCLE_RELEASE_POLL_SECONDS


def test_build_config_accepts_ground_sync_overrides(tmp_path: Path) -> None:
    cfg = MODULE._build_config(
        make_req(
            tmp_path,
            ground_sync_enabled="false",
            ground_sync_every_n_cycles="3",
            ground_sync_timeout_seconds="45",
        )
    )
    assert cfg.ground_sync_enabled is False
    assert cfg.ground_sync_every_n_cycles == 3
    assert cfg.ground_sync_timeout_seconds == 45


def test_build_config_accepts_cycle_release_overrides(tmp_path: Path) -> None:
    cfg = MODULE._build_config(
        make_req(
            tmp_path,
            cycle_release_mode="max_work",
            cycle_release_timeout_seconds="90",
            cycle_release_poll_seconds="2",
        )
    )
    assert cfg.cycle_release_mode == "max_work"
    assert cfg.cycle_release_timeout_seconds == 90
    assert cfg.cycle_release_poll_seconds == 2


def test_build_config_accepts_executor_overrides(tmp_path: Path) -> None:
    cfg = MODULE._build_config(
        make_req(
            tmp_path,
            profile="openrouter_free",
            executor_provider="blackbox",
            executor_model="blackboxai/minimax/minimax-m2.5",
            blackbox_lane="api_key",
            allow_worker_executor_override=True,
        )
    )
    assert cfg.codex_profile == "openrouter_free"
    assert cfg.executor_provider == "blackbox"
    assert cfg.executor_model == "blackboxai/minimax/minimax-m2.5"
    assert cfg.blackbox_lane == "api_key"
    assert cfg.allow_worker_executor_override is True


def test_build_config_accepts_worktrees_parent_override(tmp_path: Path) -> None:
    custom_parent = tmp_path / "forest"
    cfg = MODULE._build_config(make_req(tmp_path, worktrees_parent=str(custom_parent)))
    assert cfg.worktrees_parent == custom_parent.resolve()


def test_build_config_accepts_selected_aliases_csv(tmp_path: Path) -> None:
    cfg = MODULE._build_config(make_req(tmp_path, selected_aliases="six, seven, eight, nine, ten"))
    assert cfg.selected_aliases == ["six", "seven", "eight", "nine", "ten"]


def test_build_config_accepts_selected_aliases_list_and_dedupes(tmp_path: Path) -> None:
    cfg = MODULE._build_config(make_req(tmp_path, selected_aliases=["Six", "seven", "six", " eight "]))
    assert cfg.selected_aliases == ["six", "seven", "eight"]


def test_build_config_defaults_selected_aliases_to_discovered_profiles(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    for name in (".codex", ".codex-second"):
        profile = tmp_path / name
        profile.mkdir(parents=True, exist_ok=True)
        (profile / "auth.json").write_text("{}", encoding="utf-8")

    cfg = MODULE._build_config(make_req(tmp_path))

    assert cfg.selected_aliases == ["codex-second"]


def write_boss_artifacts(root: Path, cycle_number: int, *, overrides: dict[str, dict[str, object]] | None = None) -> None:
    override_map = overrides or {}
    base_payloads: dict[str, dict[str, object]] = {
        "production_line_register": {
            "schema_version": "1.0",
            "updated_at": "2026-01-01T00:00:00Z",
            "cycle_number": cycle_number,
            "assignments": [],
        },
        "worker_packets": {
            "schema_version": "1.0",
            "updated_at": "2026-01-01T00:00:00Z",
            "cycle_number": cycle_number,
            "packets": [],
        },
        "plan_packets": {
            "schema_version": "1.0",
            "updated_at": "2026-01-01T00:00:00Z",
            "cycle_number": cycle_number,
            "phase": "multi-phase",
            "phases": [],
            "requirements": [],
            "tasks": [],
            "lane_base_branches": {},
        },
        "task_execution_state": {
            "schema_version": "1.0",
            "updated_at": "2026-01-01T00:00:00Z",
            "cycle_number": cycle_number,
            "tasks": [],
            "blockers": [],
            "attempts": {stage: 0 for stage in MODULE.TASK_ATTEMPT_STAGES},
            "last_handoff_outcome": {"status": "unknown", "reason_codes": [], "timestamp": None},
        },
        "worker_registry": {
            "schema_version": "1.0",
            "updated_at": "2026-01-01T00:00:00Z",
            "cycle_number": cycle_number,
            "workers": [],
        },
        "cycle_summary": {
            "schema_version": "1.0",
            "cycle_number": cycle_number,
            "manager_statuses": {},
            "task_counts": {"pending": 0, "in_progress": 0, "done": 0, "blocked": 0},
            "dispatch_counts": {"attempted": 0, "launched": 0, "launch_failed": 0, "unknown": 0},
            "project_done": False,
            "insurmountable_blocker": False,
            "termination": {},
            "stop_reason": "",
            "notes": "",
        },
    }
    for artifact_key, payload in base_payloads.items():
        if artifact_key in override_map and override_map[artifact_key] is None:
            continue
        merged = dict(payload)
        if artifact_key in override_map:
            merged.update(override_map[artifact_key])
        MODULE._atomic_write_json(root / MODULE.ARTIFACT_FILES[artifact_key], merged)


def test_stop_priority_terminate_file_wins(tmp_path: Path) -> None:
    build_repo(tmp_path)
    (tmp_path / "terminate_run.json").write_text("{}\n", encoding="utf-8")

    out = MODULE.run_op_simple_build(make_req(tmp_path, max_build_cycles=5))

    assert out["ok"] is True
    assert out["data"]["stop_reason"] == "operator_terminate_file"


def test_boss_timeout_respects_max_cycles(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)

    def fake_invoke_manager(*_args, **kwargs):
        manager = kwargs["manager_name"]
        return MODULE.ManagerResult(
            manager=manager,
            status="timeout",
            timeout=True,
            returncode=None,
            started_at="2026-01-01T00:00:00Z",
            finished_at="2026-01-01T00:00:05Z",
            duration_seconds=5.0,
            message="timed out",
        )

    monkeypatch.setattr(MODULE, "_invoke_manager", fake_invoke_manager)
    monkeypatch.setattr(MODULE.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        MODULE,
        "_ensure_workstation_prep",
        lambda _cfg, initialize_state=None, force_refresh=False: {
            "schema_version": "1.0",
            "worktrees_parent": str((tmp_path / "forest").resolve()),
            "workstations": [],
        },
    )

    out = MODULE.run_op_simple_build(
        make_req(
            tmp_path,
            dry_run=False,
            max_build_cycles=1,
            sleep_minutes=0,
            worktrees_parent=str(tmp_path / "forest"),
        )
    )

    assert out["ok"] is True
    assert "after BOSS timeout" in out["summary"]
    decision_payload = json.loads((tmp_path / MODULE.ARTIFACT_FILES["cycle_manager_decision"]).read_text(encoding="utf-8"))
    assert decision_payload["cycle_number"] == 1
    assert decision_payload["decision"] == "skip_cycle"
    assert decision_payload["reason_code"] == "boss_timeout_fail_closed"

    summary_payload = json.loads((tmp_path / MODULE.ARTIFACT_FILES["cycle_summary"]).read_text(encoding="utf-8"))
    assert summary_payload["cycle_number"] == 1
    assert summary_payload["manager_statuses"]["BOSS"]["status"] == "timeout"
    assert summary_payload["timeout_state"]["consecutive_boss_timeouts"] == 1

    capsule_payload = json.loads((tmp_path / MODULE.ARTIFACT_FILES["terminal_capsule"]).read_text(encoding="utf-8"))
    assert capsule_payload["cycle_number"] == 1
    assert capsule_payload["reason_code"] == "boss_timeout_fail_closed"
    assert capsule_payload["manager_status"] == "timeout"

    cycle_dir = tmp_path / MODULE.HISTORY_DIR / "cycle-000001"
    assert (cycle_dir / "cycle_summary.json").exists()
    assert (cycle_dir / "cycle_manager_decision.json").exists()
    assert (cycle_dir / "terminal_capsule.json").exists()


def test_summary_preserves_termination_markers(tmp_path: Path) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=True,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["cycle_summary"],
        {
            "schema_version": "1.0",
            "cycle_number": 4,
            "task_counts": {"pending": 0, "in_progress": 0, "done": 10, "blocked": 0},
            "project_done": True,
            "insurmountable_blocker": True,
            "termination": {"reason_code": "project_done"},
            "stop_reason": "project_done",
            "notes": "complete",
        },
    )

    summary = MODULE._render_cycle_summary(cfg, 4, {}, {"attempted": 0, "launched": 0, "launch_failed": 0, "unknown": 0})

    assert summary["project_done"] is True
    assert summary["insurmountable_blocker"] is True
    assert MODULE._termination_from_summary(summary) == "project_done"


def test_termination_from_summary_treats_skip_cycle_as_non_terminal() -> None:
    summary = {
        "project_done": False,
        "insurmountable_blocker": False,
        "termination": {"reason_code": "active_workers_in_progress_no_safe_new_dispatch"},
        "stop_reason": "skip_cycle",
    }

    assert MODULE._termination_from_summary(summary) is None


def test_termination_from_summary_ignores_unrecognized_stop_reason_text() -> None:
    summary = {
        "project_done": False,
        "insurmountable_blocker": False,
        "termination": {"reason_code": "proceed_with_partial_reconciliation_and_single_safe_dispatch"},
        "stop_reason": "proceed_with_partial_reconciliation_and_single_safe_dispatch",
    }

    assert MODULE._termination_from_summary(summary) is None


def test_boss_failure_skips_cycle_and_writes_conservative_summary(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)

    def fake_invoke_manager(*_args, **kwargs):
        return MODULE.ManagerResult(
            manager="BOSS",
            status="failed",
            timeout=False,
            returncode=1,
            started_at="2026-01-01T00:00:00Z",
            finished_at="2026-01-01T00:00:01Z",
            duration_seconds=1.0,
            message="codex exec returned non-zero",
            reason_code="manager_non_zero_exit",
        )

    def fail_rate_gate(*_args, **_kwargs):
        raise AssertionError("rate-gate should not run when BOSS fails")

    def fail_dispatch(*_args, **_kwargs):
        raise AssertionError("dispatch should not run when BOSS fails")

    monkeypatch.setattr(MODULE, "_invoke_manager", fake_invoke_manager)
    monkeypatch.setattr(MODULE, "_run_rate_gate_wait", fail_rate_gate)
    monkeypatch.setattr(MODULE, "_dispatch_packets", fail_dispatch)

    out = MODULE.run_op_simple_build(make_req(tmp_path, dry_run=True, max_build_cycles=1, sleep_minutes=0))

    assert out["ok"] is True
    decision = json.loads((tmp_path / MODULE.ARTIFACT_FILES["cycle_manager_decision"]).read_text(encoding="utf-8"))
    assert decision["decision"] == "skip_cycle"
    assert decision["reason_code"] == "manager_non_zero_exit"
    assert decision["worker_registry_ready"] is True

    summary = json.loads((tmp_path / MODULE.ARTIFACT_FILES["cycle_summary"]).read_text(encoding="utf-8"))
    assert summary["dispatch_counts"] == {"attempted": 0, "launched": 0, "launch_failed": 0, "unknown": 0}
    assert "cycle skipped by runtime safety rules" in summary["notes"]
    assert summary["manager_statuses"]["work-dispatcher"]["status"] == "skipped"
    assert summary["manager_statuses"]["summary"]["status"] == "ok"
    assert (tmp_path / MODULE.ARTIFACT_FILES["watchdog_state"]).exists()
    capsule = json.loads((tmp_path / MODULE.ARTIFACT_FILES["terminal_capsule"]).read_text(encoding="utf-8"))
    assert capsule["reason_code"] == "manager_non_zero_exit"
    assert capsule["stop_reason"] == ""
    assert capsule["manager_status"] == "failed"


def test_worker_state_signature_and_counts_helpers(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=True,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["worker_registry"],
        {
            "schema_version": "1.0",
            "updated_at": "2026-01-01T00:00:00Z",
            "cycle_number": 1,
            "workers": [
                {
                    "worker_id": "worker-1",
                    "status": "in_progress",
                    "pid": 111,
                    "thread_id": "thread-1",
                    "current_task_id": "TASK-1",
                    "current_task_provider": "blackbox",
                    "current_task_model": "blackboxai/minimax/minimax-free",
                },
                {
                    "worker_id": "worker-2",
                    "status": "pending",
                    "pid": None,
                    "thread_id": "",
                    "current_task_id": "",
                    "current_task_provider": "codex",
                    "current_task_model": "",
                },
            ],
        },
    )
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["task_execution_state"],
        {
            "schema_version": "1.0",
            "updated_at": "2026-01-01T00:00:00Z",
            "cycle_number": 1,
            "tasks": [
                {"task_id": "TASK-1", "status": "in_progress", "assigned_worker": "worker-1", "assigned_provider": "blackbox"},
                {"task_id": "TASK-2", "status": "pending", "assigned_worker": "", "assigned_provider": ""},
                {"task_id": "TASK-3", "status": "blocked", "assigned_worker": "", "assigned_provider": ""},
            ],
        },
    )

    monkeypatch.setattr(MODULE, "_is_pid_alive", lambda pid: pid == 111)

    signature_before, in_progress = MODULE._worker_task_state_signature(cfg)
    assert isinstance(signature_before, str) and len(signature_before) == 64
    assert in_progress == 1
    assert MODULE._live_pid_in_progress_worker_count(cfg) == 1
    assert MODULE._task_counts_from_execution_state(cfg) == {"pending": 1, "in_progress": 1, "done": 0, "blocked": 1}

    payload = MODULE._read_json(tmp_path / MODULE.ARTIFACT_FILES["worker_registry"], default={})
    payload["workers"][0]["current_task_model"] = "blackboxai/minimax/minimax-m2.5"
    MODULE._atomic_write_json(tmp_path / MODULE.ARTIFACT_FILES["worker_registry"], payload)
    signature_after, _ = MODULE._worker_task_state_signature(cfg)
    assert signature_after != signature_before


def test_worker_liveness_ignores_stale_thread_markers(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=True,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    stale_at = (datetime.now(timezone.utc) - timedelta(seconds=MODULE.THREAD_LIVENESS_MAX_AGE_SECONDS + 60)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    fresh_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["worker_registry"],
        {
            "schema_version": "1.0",
            "updated_at": fresh_at,
            "cycle_number": 1,
            "workers": [
                {
                    "worker_id": "worker-stale",
                    "status": "in_progress",
                    "pid": None,
                    "thread_id": "thread-old",
                    "last_update": stale_at,
                },
                {
                    "worker_id": "worker-fresh",
                    "status": "in_progress",
                    "pid": None,
                    "thread_id": "thread-new",
                    "last_update": fresh_at,
                },
            ],
        },
    )
    monkeypatch.setattr(MODULE, "_is_pid_alive", lambda _pid: False)

    assert MODULE._active_worker_count(cfg) == 1
    assert MODULE._live_pid_in_progress_worker_count(cfg) == 1


def test_build_mergeability_report_clears_lane_merge_gate_pending_when_lane_ready(tmp_path: Path) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=True,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._ensure_default_artifacts(cfg)
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["task_execution_state"],
        {
            "schema_version": "1.0",
            "updated_at": "2026-01-01T00:00:00Z",
            "cycle_number": 5,
            "tasks": [
                {
                    "task_id": "TASK-1",
                    "lane_id": "phase-1/lane-a",
                    "status": "done",
                    "lane_merge_gate_pending": True,
                }
            ],
            "blockers": [],
            "attempts": {stage: 0 for stage in MODULE.TASK_ATTEMPT_STAGES},
            "last_handoff_outcome": {"status": "unknown", "reason_codes": [], "timestamp": None},
        },
    )
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["worker_registry"],
        {
            "schema_version": "1.0",
            "updated_at": "2026-01-01T00:00:00Z",
            "cycle_number": 5,
            "workers": [
                {
                    "worker_id": "worker-1",
                    "status": "done",
                    "current_task_id": "TASK-1",
                    "branch": "main",
                }
            ],
        },
    )

    report = MODULE._build_mergeability_report(cfg, cycle_number=5, cycle_mode="merge_recovery")

    lane_report = report["lane_status"]["phase-1/lane-a"]
    assert lane_report["tester_gate_status"] == "pass"
    assert lane_report["lane_to_run_merge_status"] == "ready"
    assert report["lane_merge_gate_pending_cleared_count"] == 1

    task_state = json.loads((tmp_path / MODULE.ARTIFACT_FILES["task_execution_state"]).read_text(encoding="utf-8"))
    task_row = task_state["tasks"][0]
    assert task_row["lane_merge_gate_pending"] is False
    assert isinstance(task_row.get("lane_merge_gate_cleared_at"), str)


def test_build_mergeability_report_marks_pending_lane_as_blocked_for_merge(tmp_path: Path) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=True,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._ensure_default_artifacts(cfg)
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["task_execution_state"],
        {
            "schema_version": "1.0",
            "updated_at": "2026-01-01T00:00:00Z",
            "cycle_number": 6,
            "tasks": [
                {
                    "task_id": "TASK-2",
                    "lane_id": "phase-2/lane-b",
                    "status": "in_progress",
                },
                {
                    "task_id": "TASK-3",
                    "lane_id": "phase-2/lane-b",
                    "status": "pending",
                },
            ],
            "blockers": [],
            "attempts": {stage: 0 for stage in MODULE.TASK_ATTEMPT_STAGES},
            "last_handoff_outcome": {"status": "unknown", "reason_codes": [], "timestamp": None},
        },
    )

    report = MODULE._build_mergeability_report(cfg, cycle_number=6, cycle_mode="normal")

    lane_report = report["lane_status"]["phase-2/lane-b"]
    assert lane_report["tester_gate_status"] == "pending_lane_completion"
    assert lane_report["lane_to_run_merge_status"] == "waiting_for_lane_completion"
    assert report["gate_owner"] == "BOSS"
    assert any(item.get("reason_code") == "lane_pending_tasks" for item in report["merge_blockers"])


def test_merge_progression_engine_releases_done_workers_for_ready_lane(tmp_path: Path) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=True,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._ensure_default_artifacts(cfg)
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["task_execution_state"],
        {
            "schema_version": "1.0",
            "updated_at": "2026-01-01T00:00:00Z",
            "cycle_number": 7,
            "tasks": [{"task_id": "TASK-1", "lane_id": "phase-1/lane-a", "status": "done"}],
            "blockers": [],
            "attempts": {stage: 0 for stage in MODULE.TASK_ATTEMPT_STAGES},
            "last_handoff_outcome": {"status": "unknown", "reason_codes": [], "timestamp": None},
        },
    )
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["worker_registry"],
        {
            "schema_version": "1.0",
            "updated_at": "2026-01-01T00:00:00Z",
            "cycle_number": 7,
            "workers": [
                {
                    "worker_id": "worker-1",
                    "status": "done",
                    "current_task_id": "TASK-1",
                    "current_packet_id": "packet-1",
                    "branch": "main",
                }
            ],
        },
    )
    mergeability = MODULE._build_mergeability_report(cfg, cycle_number=7, cycle_mode="merge_recovery")

    progression = MODULE._run_merge_progression_engine(
        cfg,
        cycle_number=7,
        cycle_mode="merge_recovery",
        mergeability_report=mergeability,
    )

    assert progression["state_changed"] is True
    assert progression["workers_released_count"] == 1
    assert progression["lane_merge_completed_count"] == 1
    worker_state = json.loads((tmp_path / MODULE.ARTIFACT_FILES["worker_registry"]).read_text(encoding="utf-8"))
    worker_row = worker_state["workers"][0]
    assert worker_row["status"] == "idle"
    assert worker_row["current_task_id"] is None
    task_state = json.loads((tmp_path / MODULE.ARTIFACT_FILES["task_execution_state"]).read_text(encoding="utf-8"))
    task_row = task_state["tasks"][0]
    assert isinstance(task_row.get("lane_fan_in_accepted_at"), str)
    assert isinstance(task_row.get("lane_to_run_merged_at"), str)
    report_after = MODULE._build_mergeability_report(cfg, cycle_number=8, cycle_mode="merge_recovery")
    assert report_after["unmerged_commit_count"] == 0
    assert "unscoped" not in report_after["lane_shas"]


def test_merge_progression_engine_opens_blocker_when_lane_ready_but_commit_not_in_run_base(tmp_path: Path) -> None:
    build_repo(tmp_path)
    subprocess.run(["git", "checkout", "-b", "feature-merge-test"], cwd=tmp_path, check=True)
    feature_file = tmp_path / "feature.txt"
    feature_file.write_text("feature branch content\n", encoding="utf-8")
    subprocess.run(["git", "add", "feature.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "feature commit"], cwd=tmp_path, check=True)
    subprocess.run(["git", "checkout", "main"], cwd=tmp_path, check=True)

    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=True,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._ensure_default_artifacts(cfg)
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["task_execution_state"],
        {
            "schema_version": "1.0",
            "updated_at": "2026-01-01T00:00:00Z",
            "cycle_number": 8,
            "tasks": [{"task_id": "TASK-2", "lane_id": "phase-2/lane-b", "status": "done"}],
            "blockers": [],
            "attempts": {stage: 0 for stage in MODULE.TASK_ATTEMPT_STAGES},
            "last_handoff_outcome": {"status": "unknown", "reason_codes": [], "timestamp": None},
        },
    )
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["worker_registry"],
        {
            "schema_version": "1.0",
            "updated_at": "2026-01-01T00:00:00Z",
            "cycle_number": 8,
            "workers": [
                {
                    "worker_id": "worker-2",
                    "status": "done",
                    "current_task_id": "TASK-2",
                    "branch": "feature-merge-test",
                }
            ],
        },
    )
    mergeability = MODULE._build_mergeability_report(cfg, cycle_number=8, cycle_mode="merge_recovery")

    progression = MODULE._run_merge_progression_engine(
        cfg,
        cycle_number=8,
        cycle_mode="merge_recovery",
        mergeability_report=mergeability,
    )

    assert progression["state_changed"] is True
    assert progression["lane_merge_blocked_count"] == 1
    task_state = json.loads((tmp_path / MODULE.ARTIFACT_FILES["task_execution_state"]).read_text(encoding="utf-8"))
    blockers = task_state.get("blockers") if isinstance(task_state, dict) else []
    assert isinstance(blockers, list)
    blocker_row = next((row for row in blockers if isinstance(row, dict) and row.get("lane_id") == "phase-2/lane-b"), None)
    assert isinstance(blocker_row, dict)
    assert blocker_row.get("reason_code") == "lane_run_merge_pending_commit_not_in_run_base"
    assert blocker_row.get("status") == "open"


def test_build_mergeability_report_skips_already_merged_ancestor_commits(tmp_path: Path) -> None:
    build_repo(tmp_path)
    subprocess.run(["git", "checkout", "-b", "feature-ancestor-merged"], cwd=tmp_path, check=True)
    feature_file = tmp_path / "feature_ancestor.txt"
    feature_file.write_text("ancestor merge content\n", encoding="utf-8")
    subprocess.run(["git", "add", "feature_ancestor.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "feature ancestor commit"], cwd=tmp_path, check=True)
    subprocess.run(["git", "checkout", "main"], cwd=tmp_path, check=True)
    subprocess.run(["git", "merge", "--no-ff", "feature-ancestor-merged", "-m", "merge feature ancestor"], cwd=tmp_path, check=True)

    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=True,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._ensure_default_artifacts(cfg)
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["task_execution_state"],
        {
            "schema_version": "1.0",
            "updated_at": "2026-01-01T00:00:00Z",
            "cycle_number": 9,
            "tasks": [{"task_id": "TASK-9", "lane_id": "phase-9/lane-a", "status": "done"}],
            "blockers": [],
            "attempts": {stage: 0 for stage in MODULE.TASK_ATTEMPT_STAGES},
            "last_handoff_outcome": {"status": "unknown", "reason_codes": [], "timestamp": None},
        },
    )
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["worker_registry"],
        {
            "schema_version": "1.0",
            "updated_at": "2026-01-01T00:00:00Z",
            "cycle_number": 9,
            "workers": [
                {
                    "worker_id": "worker-9",
                    "status": "done",
                    "current_task_id": "TASK-9",
                    "branch": "feature-ancestor-merged",
                }
            ],
        },
    )

    report = MODULE._build_mergeability_report(cfg, cycle_number=9, cycle_mode="merge_recovery")
    lane_row = report["lane_status"]["phase-9/lane-a"]
    assert report["unmerged_commit_count"] == 0
    assert lane_row["lane_unmerged_commit_count"] == 0
    assert report["lane_shas"] == {}


def test_apply_restart_determinism_hooks_supports_watchdog_resume_idempotency(tmp_path: Path) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=True,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._ensure_default_artifacts(cfg)
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["watchdog_exit_signal"],
        {
            "schema_version": "1.0",
            "cycle_number": 3,
            "reason_code": "stale_base_branch_commit",
            "message": "stale",
        },
    )

    first = MODULE._apply_restart_determinism_hooks(cfg, cycle_number=3, resume_mode=True)
    second = MODULE._apply_restart_determinism_hooks(cfg, cycle_number=3, resume_mode=True)

    assert first["scenario"] == "watchdog_resume"
    assert first["idempotent_continuation"] is False
    assert second["scenario"] == "watchdog_resume"
    assert second["idempotent_continuation"] is True


def test_apply_restart_determinism_hooks_supports_process_kill_resume_with_prior_lock(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=True,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._ensure_default_artifacts(cfg)
    monkeypatch.setattr(MODULE, "_is_pid_running", lambda _pid: False)

    out = MODULE._apply_restart_determinism_hooks(
        cfg,
        cycle_number=3,
        resume_mode=True,
        prior_run_lock={"pid": 424242, "started_at": "2026-03-13T00:00:00Z"},
    )

    assert out["scenario"] == "process_kill_resume"
    log_row = out["continuation_log"][-1]
    assert log_row["prior_run_lock_pid"] == 424242
    assert log_row["prior_run_lock_present"] is True


def test_run_resume_detects_process_kill_resume_from_preexisting_lock(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    stale_pid = 424242
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._atomic_write_json(
        tmp_path / MODULE.RUN_LOCK_FILE,
        {
            "schema_version": "1.0",
            "lock_id": "stale-lock",
            "pid": stale_pid,
            "started_at": "2026-03-13T00:00:00Z",
            "command": "op-simple-build",
        },
    )
    monkeypatch.setattr(MODULE, "_is_pid_running", lambda _pid: False)
    monkeypatch.setattr(
        MODULE,
        "_load_resume_run_base_meta",
        lambda _cfg: {
            "run_base_branch": "main",
            "run_base_from_branch": "main",
            "run_base_from_commit": git(tmp_path, "rev-parse", "HEAD"),
            "created_new": False,
        },
    )
    monkeypatch.setattr(
        MODULE,
        "_ensure_workstation_prep",
        lambda _cfg, initialize_state=None, force_refresh=False: {
            "schema_version": "1.0",
            "worktrees_parent": str((tmp_path / "forest").resolve()),
            "workstations": [],
        },
    )
    monkeypatch.setattr(MODULE, "_watchdog_tick", lambda _cfg, _cycle, *, force_reset_target=False: (False, {"message": ""}))
    monkeypatch.setattr(MODULE, "_run_rate_gate_wait", lambda _cfg, _cycle, _warnings: None)
    monkeypatch.setattr(
        MODULE,
        "_dispatch_packets",
        lambda _cfg, _cycle, *, reserved_slots=0: {"attempted": 0, "launched": 0, "launch_failed": 0, "unknown": 0},
    )

    out = MODULE.run_op_simple_build(
        make_req(
            tmp_path,
            command="op-resume",
            dry_run=True,
            max_build_cycles=1,
            sleep_minutes=0,
            ground_sync_enabled=False,
            worktrees_parent=str(tmp_path / "forest"),
        )
    )

    assert out["ok"] is True
    restart_state = MODULE._read_json(tmp_path / MODULE.ARTIFACT_FILES["restart_determinism_state"], default={})
    assert restart_state.get("scenario") == "process_kill_resume"


def test_packet4_gate_closure_scaffold_writer_builds_expected_artifacts(tmp_path: Path, monkeypatch) -> None:
    json_path = tmp_path / "packet4_gate_evidence_bundle_2026-03-13.json"
    md_path = tmp_path / "packet4_gate_evidence_bundle_2026-03-13.md"
    monkeypatch.setattr(
        MODULE,
        "_packet4_gate_closure_paths",
        lambda *, date_text: {"json": json_path, "md": md_path},
    )

    out = MODULE._write_packet4_gate_closure_scaffold(
        date_text="2026-03-13",
        generated_at_utc="2026-03-13T12:00:00Z",
        repo="earth-root",
    )

    assert out["json"] == str(json_path)
    assert out["md"] == str(md_path)
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["packet"] == "Packet 4"
    assert payload["status"] == "warn"
    md_text = md_path.read_text(encoding="utf-8")
    assert "Packet 4 Gate Evidence Bundle (Scaffold)" in md_text
    assert "Decision: `hold`" in md_text


def test_packet4_kpi_trend_scaffold_writer_builds_expected_artifacts(tmp_path: Path, monkeypatch) -> None:
    json_path = tmp_path / "packet4_kpi_trend_summary_2026-03-13.json"
    md_path = tmp_path / "packet4_kpi_trend_summary_2026-03-13.md"
    monkeypatch.setattr(
        MODULE,
        "_packet4_kpi_trend_paths",
        lambda *, date_text: {"json": json_path, "md": md_path},
    )

    out = MODULE._write_packet4_kpi_trend_scaffold(
        date_text="2026-03-13",
        generated_at_utc="2026-03-13T12:00:00Z",
        repo="earth-root",
    )

    assert out["json"] == str(json_path)
    assert out["md"] == str(md_path)
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["packet"] == "Packet 4"
    assert payload["status"] == "warn"
    md_text = md_path.read_text(encoding="utf-8")
    assert "Packet 4 KPI Trend Summary (Scaffold)" in md_text
    assert "non_actionable_cycle_ratio" in md_text


def test_packet4_gate_recommendation_scaffold_writer_builds_expected_artifact(tmp_path: Path, monkeypatch) -> None:
    md_path = tmp_path / "packet4_gate_recommendation_2026-03-13.md"
    monkeypatch.setattr(MODULE, "_packet4_gate_recommendation_path", lambda *, date_text: md_path)

    out = MODULE._write_packet4_gate_recommendation_scaffold(
        date_text="2026-03-13",
        generated_at_utc="2026-03-13T12:00:00Z",
        repo="earth-root",
    )

    assert out == str(md_path)
    md_text = md_path.read_text(encoding="utf-8")
    assert "Packet 4 Gate Recommendation (Scaffold)" in md_text
    assert "Decision: `hold`" in md_text


def test_cycle_release_watchset_from_dispatch_cycle_tracks_launched_rows_with_pid_only(tmp_path: Path) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=5,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=True,
        cycle_release_mode="token_conservative",
    )
    rows = [
        {
            "cycle_number": 7,
            "worker_id": "worker-1",
            "status": "launched",
            "pid": 1111,
            "timestamp": "2026-03-14T00:00:01Z",
        },
        {
            "cycle_number": 7,
            "worker_id": "worker-2",
            "status": "unknown",
            "pid": 2222,
            "timestamp": "2026-03-14T00:00:02Z",
        },
        {
            "cycle_number": 7,
            "worker_id": "worker-3",
            "status": "launched",
            "pid": None,
            "timestamp": "2026-03-14T00:00:03Z",
        },
        {
            "cycle_number": 6,
            "worker_id": "worker-4",
            "status": "launched",
            "pid": 4444,
            "timestamp": "2026-03-14T00:00:04Z",
        },
        {
            "cycle_number": 7,
            "worker_id": "worker-5",
            "status": "launched",
            "pid": "not-an-int",
            "timestamp": "2026-03-14T00:00:05Z",
        },
    ]
    text = "\n".join(json.dumps(row) for row in rows) + "\n"
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    (tmp_path / MODULE.DISPATCH_LAUNCH_LOG_FILE).write_text(text, encoding="utf-8")

    out = MODULE._cycle_release_watchset_from_dispatch_cycle(cfg, 7)
    assert out == [1111]


def test_cycle_release_watchset_from_live_workers_uses_pid_liveness_only(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=5,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=True,
        cycle_release_mode="max_work",
    )
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["worker_registry"],
        {
            "schema_version": "1.0",
            "updated_at": now_iso,
            "cycle_number": 12,
            "workers": [
                {
                    "worker_id": "worker-thread-only",
                    "status": "in_progress",
                    "pid": None,
                    "thread_id": "thread-fresh",
                    "last_update": now_iso,
                },
                {
                    "worker_id": "worker-dead-pid",
                    "status": "in_progress",
                    "pid": 1111,
                    "thread_id": "thread-fresh",
                    "last_update": now_iso,
                },
                {
                    "worker_id": "worker-live-pid",
                    "status": "in_progress",
                    "pid": 2222,
                    "thread_id": "thread-stale",
                    "last_update": "2020-01-01T00:00:00Z",
                },
            ],
        },
    )
    monkeypatch.setattr(MODULE, "_is_pid_alive", lambda pid: int(pid) == 2222)
    out = MODULE._cycle_release_watchset_from_live_workers(cfg)
    assert out == [2222]


def test_await_cycle_release_signal_token_conservative_waits_for_all_dead_with_guard(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=5,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=True,
        cycle_release_mode="token_conservative",
        cycle_release_timeout_seconds=40,
        cycle_release_poll_seconds=1,
    )
    alive_sequence = iter(
        [
            [101, 102],
            [101, 102],
            [101],
            [],
            [],
        ]
    )

    def fake_alive_pids(_tracked_pids):
        try:
            return next(alive_sequence)
        except StopIteration:
            return []

    ticks = {"t": 0.0}

    def fake_monotonic():
        return float(ticks["t"])

    def fake_sleep(seconds):
        ticks["t"] += float(seconds)

    monkeypatch.setattr(MODULE, "_cycle_release_watchset_from_dispatch_cycle", lambda _cfg, _cycle: [101, 102])
    monkeypatch.setattr(MODULE, "_cycle_release_alive_pids", fake_alive_pids)
    monkeypatch.setattr(MODULE.time, "sleep", fake_sleep)
    monkeypatch.setattr(MODULE.time, "monotonic", fake_monotonic)

    out = MODULE._await_cycle_release_signal(
        cfg,
        cycle_number=11,
    )

    assert out["mode"] == "token_conservative"
    assert out["timed_out"] is False
    assert out["decision"] == "all_tracked_pids_dead_guarded"
    assert out["tracked_pids"] == [101, 102]
    assert out["alive_pids"] == []


def test_await_cycle_release_signal_max_work_releases_on_first_dead_with_guard(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=5,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=True,
        cycle_release_mode="max_work",
        cycle_release_timeout_seconds=20,
        cycle_release_poll_seconds=1,
    )
    alive_sequence = iter(
        [
            [201, 202],
            [201, 202],
            [201],
            [201],
        ]
    )

    def fake_alive_pids(_tracked_pids):
        try:
            return next(alive_sequence)
        except StopIteration:
            return [201]

    ticks = {"t": 0.0}

    def fake_monotonic():
        return float(ticks["t"])

    def fake_sleep(seconds):
        ticks["t"] += float(seconds)

    monkeypatch.setattr(MODULE, "_cycle_release_watchset_from_live_workers", lambda _cfg: [201, 202])
    monkeypatch.setattr(MODULE, "_cycle_release_alive_pids", fake_alive_pids)
    monkeypatch.setattr(MODULE.time, "sleep", fake_sleep)
    monkeypatch.setattr(MODULE.time, "monotonic", fake_monotonic)

    out = MODULE._await_cycle_release_signal(
        cfg,
        cycle_number=12,
    )

    assert out["mode"] == "max_work"
    assert out["timed_out"] is False
    assert out["decision"] == "first_tracked_pid_dead_guarded"
    assert out["tracked_pids"] == [201, 202]
    assert out["alive_pids"] == [201]


def test_await_cycle_release_signal_returns_timeout_release(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=5,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=True,
        cycle_release_mode="token_conservative",
        cycle_release_timeout_seconds=3,
        cycle_release_poll_seconds=1,
    )
    monkeypatch.setattr(MODULE, "_cycle_release_watchset_from_dispatch_cycle", lambda _cfg, _cycle: [301])
    monkeypatch.setattr(MODULE, "_cycle_release_alive_pids", lambda _tracked: [301])

    ticks = {"t": 0.0}

    def fake_monotonic():
        return float(ticks["t"])

    def fake_sleep(seconds):
        ticks["t"] += float(seconds)

    monkeypatch.setattr(MODULE.time, "sleep", fake_sleep)
    monkeypatch.setattr(MODULE.time, "monotonic", fake_monotonic)

    out = MODULE._await_cycle_release_signal(
        cfg,
        cycle_number=13,
    )

    assert out["timed_out"] is True
    assert out["decision"] == "timeout_release"


def test_await_cycle_release_signal_returns_immediate_when_no_tracked_pids(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=5,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=True,
        cycle_release_mode="token_conservative",
        cycle_release_timeout_seconds=10,
        cycle_release_poll_seconds=1,
    )
    monkeypatch.setattr(MODULE, "_cycle_release_watchset_from_dispatch_cycle", lambda _cfg, _cycle: [])
    out = MODULE._await_cycle_release_signal(cfg, cycle_number=14)
    assert out["timed_out"] is False
    assert out["decision"] == "no_wait_no_tracked_pids"
    assert out["tracked_pid_count"] == 0


def test_quiet_cycle_gate_skips_boss_when_state_unchanged(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    boss_calls: list[int] = []
    rate_gate_calls: list[int] = []
    dispatch_calls: list[int] = []
    live_worker_pid = 424242

    def fake_invoke_manager(*_args, **kwargs):
        manager = kwargs["manager_name"]
        cycle_number = int(kwargs["cycle_number"])
        if manager != "BOSS":
            raise AssertionError(f"unexpected manager call: {manager}")
        boss_calls.append(cycle_number)
        write_boss_artifacts(
            tmp_path,
            cycle_number,
            overrides={
                "worker_registry": {
                    "workers": [
                        {
                            "worker_id": "worker-1",
                            "status": "in_progress",
                            "pid": live_worker_pid,
                            "thread_id": "thread-1",
                            "current_task_id": "TASK-001",
                            "current_packet_id": "packet-1",
                            "current_task_profile": "codex",
                        }
                    ]
                },
                "task_execution_state": {
                    "tasks": [
                        {
                            "task_id": "TASK-001",
                            "status": "in_progress",
                            "assigned_worker": "worker-1",
                            "assigned_profile": "codex",
                        }
                    ]
                },
                "cycle_summary": {
                    "task_counts": {"pending": 0, "in_progress": 1, "done": 0, "blocked": 0},
                },
            },
        )
        return MODULE.ManagerResult(
            manager="BOSS",
            status="ok",
            timeout=False,
            returncode=0,
            started_at="2026-01-01T00:00:00Z",
            finished_at="2026-01-01T00:00:01Z",
            duration_seconds=1.0,
            message="ok",
        )

    def fake_rate_gate(_cfg, cycle_number: int, _warnings):
        rate_gate_calls.append(int(cycle_number))

    def fake_dispatch(_cfg, cycle_number: int):
        dispatch_calls.append(int(cycle_number))
        return {"attempted": 0, "launched": 0, "launch_failed": 0, "unknown": 0}

    monkeypatch.setattr(MODULE, "_invoke_manager", fake_invoke_manager)
    monkeypatch.setattr(MODULE, "_run_rate_gate_wait", fake_rate_gate)
    monkeypatch.setattr(MODULE, "_dispatch_packets", fake_dispatch)
    monkeypatch.setattr(
        MODULE,
        "_is_pid_alive",
        lambda pid: int(pid) == live_worker_pid,
    )
    monkeypatch.setattr(MODULE.time, "sleep", lambda _seconds: None)

    out = MODULE.run_op_simple_build(make_req(tmp_path, max_build_cycles=2, dry_run=True, sleep_minutes=0))

    assert out["ok"] is True
    assert boss_calls == [1]
    assert rate_gate_calls == [1]
    assert dispatch_calls == [1]

    summary = json.loads((tmp_path / MODULE.ARTIFACT_FILES["cycle_summary"]).read_text(encoding="utf-8"))
    assert summary["cycle_number"] == 2
    assert summary["manager_statuses"]["BOSS"]["status"] == "skipped"
    assert summary["termination"]["reason_code"] == "active_workers_in_progress_no_safe_new_dispatch"
    assert summary["stop_reason"] == "skip_cycle"

    decision = json.loads((tmp_path / MODULE.ARTIFACT_FILES["cycle_manager_decision"]).read_text(encoding="utf-8"))
    assert decision["cycle_number"] == 2
    assert decision["decision"] == "skip_cycle"
    assert decision["reason_code"] == "active_workers_in_progress_no_safe_new_dispatch"


def test_quiet_cycle_gate_does_not_skip_when_task_state_has_no_in_progress(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    boss_calls: list[int] = []
    rate_gate_calls: list[int] = []
    dispatch_calls: list[int] = []

    def fake_invoke_manager(*_args, **kwargs):
        manager = kwargs["manager_name"]
        cycle_number = int(kwargs["cycle_number"])
        if manager != "BOSS":
            raise AssertionError(f"unexpected manager call: {manager}")
        boss_calls.append(cycle_number)
        write_boss_artifacts(
            tmp_path,
            cycle_number,
            overrides={
                "worker_registry": {
                    "workers": [
                        {
                            "worker_id": "worker-1",
                            "status": "in_progress",
                            "pid": None,
                            "thread_id": "thread-stale",
                            "current_task_id": "TASK-001",
                            "current_packet_id": "packet-1",
                            "current_task_profile": "codex",
                        }
                    ]
                },
                "task_execution_state": {
                    "tasks": [
                        {
                            "task_id": "TASK-001",
                            "status": "pending",
                            "assigned_worker": None,
                            "assigned_profile": None,
                        }
                    ]
                },
                "cycle_summary": {
                    "task_counts": {"pending": 1, "in_progress": 0, "done": 0, "blocked": 0},
                },
            },
        )
        return MODULE.ManagerResult(
            manager="BOSS",
            status="ok",
            timeout=False,
            returncode=0,
            started_at="2026-01-01T00:00:00Z",
            finished_at="2026-01-01T00:00:01Z",
            duration_seconds=1.0,
            message="ok",
        )

    def fake_rate_gate(_cfg, cycle_number: int, _warnings):
        rate_gate_calls.append(int(cycle_number))

    def fake_dispatch(_cfg, cycle_number: int):
        dispatch_calls.append(int(cycle_number))
        return {"attempted": 0, "launched": 0, "launch_failed": 0, "unknown": 0}

    monkeypatch.setattr(MODULE, "_invoke_manager", fake_invoke_manager)
    monkeypatch.setattr(MODULE, "_run_rate_gate_wait", fake_rate_gate)
    monkeypatch.setattr(MODULE, "_dispatch_packets", fake_dispatch)
    monkeypatch.setattr(MODULE.time, "sleep", lambda _seconds: None)

    out = MODULE.run_op_simple_build(make_req(tmp_path, max_build_cycles=2, dry_run=True, sleep_minutes=0))

    assert out["ok"] is True
    assert boss_calls == [1, 2]
    assert rate_gate_calls == [1, 2]
    assert dispatch_calls == [1, 2]

    summary = json.loads((tmp_path / MODULE.ARTIFACT_FILES["cycle_summary"]).read_text(encoding="utf-8"))
    assert summary["cycle_number"] == 2
    assert summary["manager_statuses"]["BOSS"]["status"] == "ok"


def test_quiet_cycle_gate_forces_periodic_full_boss_cycle(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    boss_calls: list[int] = []
    rate_gate_calls: list[int] = []
    dispatch_calls: list[int] = []
    live_worker_pid = 434343

    def fake_invoke_manager(*_args, **kwargs):
        manager = kwargs["manager_name"]
        cycle_number = int(kwargs["cycle_number"])
        if manager != "BOSS":
            raise AssertionError(f"unexpected manager call: {manager}")
        boss_calls.append(cycle_number)
        write_boss_artifacts(
            tmp_path,
            cycle_number,
            overrides={
                "worker_registry": {
                    "workers": [
                        {
                            "worker_id": "worker-1",
                            "status": "in_progress",
                            "pid": live_worker_pid,
                            "thread_id": "thread-1",
                            "current_task_id": "TASK-001",
                            "current_packet_id": "packet-1",
                            "current_task_profile": "codex",
                        }
                    ]
                },
                "task_execution_state": {
                    "tasks": [
                        {
                            "task_id": "TASK-001",
                            "status": "in_progress",
                            "assigned_worker": "worker-1",
                            "assigned_profile": "codex",
                        }
                    ]
                },
                "cycle_summary": {
                    "task_counts": {"pending": 0, "in_progress": 1, "done": 0, "blocked": 0},
                },
            },
        )
        return MODULE.ManagerResult(
            manager="BOSS",
            status="ok",
            timeout=False,
            returncode=0,
            started_at="2026-01-01T00:00:00Z",
            finished_at="2026-01-01T00:00:01Z",
            duration_seconds=1.0,
            message="ok",
        )

    def fake_rate_gate(_cfg, cycle_number: int, _warnings):
        rate_gate_calls.append(int(cycle_number))

    def fake_dispatch(_cfg, cycle_number: int):
        dispatch_calls.append(int(cycle_number))
        return {"attempted": 0, "launched": 0, "launch_failed": 0, "unknown": 0}

    monkeypatch.setattr(MODULE, "_invoke_manager", fake_invoke_manager)
    monkeypatch.setattr(MODULE, "_run_rate_gate_wait", fake_rate_gate)
    monkeypatch.setattr(MODULE, "_dispatch_packets", fake_dispatch)
    monkeypatch.setattr(MODULE, "QUIET_CYCLE_FORCE_FULL_EVERY", 2)
    monkeypatch.setattr(
        MODULE,
        "_is_pid_alive",
        lambda pid: int(pid) == live_worker_pid,
    )
    monkeypatch.setattr(MODULE.time, "sleep", lambda _seconds: None)

    out = MODULE.run_op_simple_build(make_req(tmp_path, max_build_cycles=3, dry_run=True, sleep_minutes=0))

    assert out["ok"] is True
    assert boss_calls == [1, 3]
    assert rate_gate_calls == [1, 3]
    assert dispatch_calls == [1, 3]


def test_invoke_manager_boss_fails_when_required_artifact_missing(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    codex_home = tmp_path / ".codex-second"
    codex_home.mkdir(parents=True, exist_ok=True)
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["profile_snapshot"],
        {
            "schema_version": "1.0",
            "profiles": [
                {
                    "alias": "codex-second",
                    "codex_home": str(codex_home.resolve()),
                    "window_5h_remaining_pct": 80.0,
                    "window_week_remaining_pct": 90.0,
                }
            ],
        },
    )

    monkeypatch.setattr(MODULE, "_load_prompt_template", lambda *_args, **_kwargs: "prompt body")

    def fake_codex_exec_prompt(*_args, **_kwargs):
        write_boss_artifacts(
            tmp_path,
            3,
            overrides={"cycle_summary": None},
        )
        return MODULE.ManagerResult(
            manager="BOSS",
            status="ok",
            timeout=False,
            returncode=0,
            started_at="2026-01-01T00:00:00Z",
            finished_at="2026-01-01T00:00:01Z",
            duration_seconds=1.0,
        )

    monkeypatch.setattr(MODULE, "_codex_exec_prompt", fake_codex_exec_prompt)

    out = MODULE._invoke_manager(
        cfg,
        manager_name="BOSS",
        cycle_number=3,
        context={},
        expected_artifacts=list(MODULE.BOSS_REQUIRED_ARTIFACTS),
    )

    assert out.status == "failed"
    assert out.reason_code == "boss_missing_artifact"
    assert out.details == {"artifact_key": "cycle_summary"}


def test_invoke_manager_boss_fails_when_required_artifact_cycle_number_is_stale(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    codex_home = tmp_path / ".codex-second"
    codex_home.mkdir(parents=True, exist_ok=True)
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["profile_snapshot"],
        {
            "schema_version": "1.0",
            "profiles": [
                {
                    "alias": "codex-second",
                    "codex_home": str(codex_home.resolve()),
                    "window_5h_remaining_pct": 80.0,
                    "window_week_remaining_pct": 90.0,
                }
            ],
        },
    )

    monkeypatch.setattr(MODULE, "_load_prompt_template", lambda *_args, **_kwargs: "prompt body")

    def fake_codex_exec_prompt(*_args, **_kwargs):
        write_boss_artifacts(
            tmp_path,
            4,
            overrides={"worker_packets": {"cycle_number": 3}},
        )
        return MODULE.ManagerResult(
            manager="BOSS",
            status="ok",
            timeout=False,
            returncode=0,
            started_at="2026-01-01T00:00:00Z",
            finished_at="2026-01-01T00:00:01Z",
            duration_seconds=1.0,
        )

    monkeypatch.setattr(MODULE, "_codex_exec_prompt", fake_codex_exec_prompt)

    out = MODULE._invoke_manager(
        cfg,
        manager_name="BOSS",
        cycle_number=4,
        context={},
        expected_artifacts=list(MODULE.BOSS_REQUIRED_ARTIFACTS),
    )

    assert out.status == "failed"
    assert out.reason_code == "boss_stale_artifact"
    assert out.details == {"artifact_key": "worker_packets", "cycle_number": 3}


def test_codex_exec_prompt_resume_uses_model_and_reasoning_flags(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
    )
    captured: dict[str, object] = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = list(cmd)
        captured["cwd"] = kwargs.get("cwd")
        captured["env"] = kwargs.get("env")
        captured["input"] = kwargs.get("input")
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout="session id: 123e4567-e89b-12d3-a456-426614174002\n",
            stderr="",
        )

    monkeypatch.setattr(MODULE.subprocess, "run", fake_run)

    out = MODULE._codex_exec_prompt(
        cfg,
        "BOSS",
        7,
        30,
        "prompt body",
        codex_home="/tmp/codex-home",
        resume_session_id="123e4567-e89b-12d3-a456-426614174001",
        model="gpt-5.3-codex",
        reasoning_effort="xhigh",
        codex_profile="openrouter_free",
    )

    assert out.status == "ok"
    assert out.session_id == "123e4567-e89b-12d3-a456-426614174002"
    cmd = captured["cmd"]
    assert isinstance(cmd, list)
    assert cmd[:3] == ["codex", "exec", "resume"]
    assert "--dangerously-bypass-approvals-and-sandbox" in cmd
    assert "-p" in cmd
    profile_idx = cmd.index("-p")
    assert cmd[profile_idx + 1] == "openrouter_free"
    assert "--model" in cmd
    model_idx = cmd.index("--model")
    assert cmd[model_idx + 1] == "gpt-5.3-codex"
    assert "-c" in cmd
    config_idx = cmd.index("-c")
    assert cmd[config_idx + 1] == 'model_reasoning_effort="xhigh"'
    assert "123e4567-e89b-12d3-a456-426614174001" in cmd


def test_codex_exec_prompt_supports_profile_flag(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
    )
    captured: dict[str, object] = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = list(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(MODULE.subprocess, "run", fake_run)

    out = MODULE._codex_exec_prompt(
        cfg,
        "BOSS",
        7,
        30,
        "prompt body",
        codex_profile="openrouter_free",
    )
    assert out.status == "ok"
    cmd = captured["cmd"]
    assert isinstance(cmd, list)
    assert "-p" in cmd
    profile_idx = cmd.index("-p")
    assert cmd[profile_idx + 1] == "openrouter_free"


def test_codex_exec_prompt_timeout_persists_partial_stdout_stderr(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
    )

    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=30, output="partial stdout", stderr="partial stderr")

    monkeypatch.setattr(MODULE.subprocess, "run", fake_run)

    out = MODULE._codex_exec_prompt(
        cfg,
        "BOSS",
        7,
        30,
        "prompt body",
    )
    assert out.status == "timeout"
    assert out.timeout is True

    cycle_dir = tmp_path / MODULE.HISTORY_DIR / "cycle-000007"
    stdout_path = cycle_dir / "manager-boss.stdout.log"
    stderr_path = cycle_dir / "manager-boss.stderr.log"
    assert stdout_path.read_text(encoding="utf-8") == "partial stdout"
    assert stderr_path.read_text(encoding="utf-8") == "partial stderr"


def test_build_blackbox_exec_command_free_lane_unsets_keys(tmp_path: Path, monkeypatch) -> None:
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
        executor_provider="blackbox",
        blackbox_lane="free",
    )
    monkeypatch.setenv("BLACKBOX_API_KEY", "abc")
    monkeypatch.setenv("OPENAI_API_KEY", "def")
    cmd, env, error = MODULE._build_blackbox_exec_command(cfg, "prompt body")
    assert error is None
    assert cmd[:2] == ["blackbox", "-m"]
    assert "blackboxai/minimax/minimax-free" in cmd
    assert "--approval-mode" in cmd
    assert "yolo" in cmd
    assert "--include-directories" in cmd
    include_idx = cmd.index("--include-directories")
    assert cmd[include_idx + 1] == "."
    assert env is not None
    assert "BLACKBOX_API_KEY" not in env
    assert "OPENAI_API_KEY" not in env


def test_build_blackbox_exec_command_api_key_lane_uses_keychain_lookup(tmp_path: Path, monkeypatch) -> None:
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
        executor_provider="blackbox",
        blackbox_lane="api_key",
    )
    monkeypatch.setattr(MODULE, "_resolve_blackbox_api_key", lambda: "secret-key")
    cmd, env, error = MODULE._build_blackbox_exec_command(cfg, "prompt body")
    assert error is None
    assert cmd[:2] == ["blackbox", "-m"]
    assert "blackboxai/minimax/minimax-m2.5" in cmd
    assert "--approval-mode" in cmd
    assert "yolo" in cmd
    assert "--include-directories" in cmd
    include_idx = cmd.index("--include-directories")
    assert cmd[include_idx + 1] == "."
    assert env is not None
    assert env.get("BLACKBOX_API_KEY") == "secret-key"


def test_dispatch_packets_writes_launch_and_registry(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
        worktrees_parent=tmp_path,
        codex_profile="openrouter_free",
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["worker_packets"],
        {
            "schema_version": "1.0",
            "packets": [
                {
                    "worker_id": "worker-1",
                    "packet_id": "packet-1",
                    "profile_alias": "codex",
                    "prompt": "do task",
                }
            ],
        },
    )
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["profile_snapshot"],
        {
            "schema_version": "1.0",
            "profiles": [{"alias": "codex", "codex_home": "/tmp/.codex"}],
        },
    )
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["worker_registry"],
        {
            "schema_version": "1.0",
            "workers": [
                {
                    "worker_id": "worker-1",
                    "worktree": str(tmp_path / "workstation-1"),
                    "branch": "codex/worker-1/task",
                    "status": "idle",
                    "current_task_profile": None,
                    "next_task_profile": "codex",
                    "current_task_id": None,
                    "current_packet_id": None,
                    "pid": None,
                    "thread_id": None,
                    "last_update": "2026-01-01T00:00:00Z",
                }
            ],
        },
    )
    (tmp_path / "workstation-1").mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(MODULE, "_resolve_dispatch_script", lambda _cfg: Path("/tmp/fake-dispatch.py"))
    captured_cmds: list[list[str]] = []

    def fake_run(*_args, **_kwargs):
        if _args:
            first = _args[0]
            if isinstance(first, list):
                captured_cmds.append(first)
        payload = {
            "status": "started",
            "session_id": "thread-123",
            "pid": 4321,
        }
        return subprocess.CompletedProcess(args=[], returncode=0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(MODULE.subprocess, "run", fake_run)

    counters = MODULE._dispatch_packets(cfg, cycle_number=3)

    assert counters == {"attempted": 1, "launched": 1, "launch_failed": 0, "unknown": 0}
    assert captured_cmds, "expected dispatch command invocation"
    assert "--cwd" in captured_cmds[0]
    cwd_idx = captured_cmds[0].index("--cwd")
    assert captured_cmds[0][cwd_idx + 1] == str((tmp_path / "workstation-1").resolve())
    assert "--no-full-auto" in captured_cmds[0]
    assert any("--dangerously-bypass-approvals-and-sandbox" in token for token in captured_cmds[0])
    assert "--extra-arg=-p" in captured_cmds[0]
    assert "--extra-arg=openrouter_free" in captured_cmds[0]

    launch_rows = [json.loads(line) for line in (tmp_path / MODULE.DISPATCH_LAUNCH_LOG_FILE).read_text(encoding="utf-8").splitlines()]
    assert len(launch_rows) == 1
    assert launch_rows[0]["status"] == "launched"
    assert launch_rows[0]["thread_id"] == "thread-123"
    assert launch_rows[0]["pid"] == 4321

    registry = json.loads((tmp_path / MODULE.ARTIFACT_FILES["dispatch_registry"]).read_text(encoding="utf-8"))
    assert len(registry["events"]) == 1
    assert registry["events"][0]["status"] == "launched"

    worker_registry = json.loads((tmp_path / MODULE.ARTIFACT_FILES["worker_registry"]).read_text(encoding="utf-8"))
    assert worker_registry["workers"][0]["status"] == "in_progress"
    assert worker_registry["workers"][0]["current_packet_id"] == "packet-1"
    assert worker_registry["workers"][0]["thread_id"] == "thread-123"
    assert worker_registry["workers"][0]["pid"] == 4321


def test_dispatch_packets_rejects_worktree_outside_configured_parent(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    allowed_parent = tmp_path / "forest"
    allowed_parent.mkdir(parents=True, exist_ok=True)
    outside_worktree = tmp_path / "outside-worktree"
    outside_worktree.mkdir(parents=True, exist_ok=True)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
        worktrees_parent=allowed_parent,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["worker_packets"],
        {
            "schema_version": "1.0",
            "packets": [{"worker_id": "worker-1", "packet_id": "packet-1", "profile_alias": "codex", "prompt": "do task"}],
        },
    )
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["worker_registry"],
        {
            "schema_version": "1.0",
            "workers": [{"worker_id": "worker-1", "worktree": str(outside_worktree), "status": "idle"}],
        },
    )
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["profile_snapshot"],
        {
            "schema_version": "1.0",
            "profiles": [{"alias": "codex", "codex_home": "/tmp/.codex"}],
        },
    )
    monkeypatch.setattr(MODULE, "_resolve_dispatch_script", lambda _cfg: Path("/tmp/fake-dispatch.py"))
    monkeypatch.setattr(
        MODULE.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("dispatch command should not execute")),
    )

    counters = MODULE._dispatch_packets(cfg, cycle_number=3)

    assert counters == {"attempted": 1, "launched": 0, "launch_failed": 1, "unknown": 0}
    launch_row = json.loads((tmp_path / MODULE.DISPATCH_LAUNCH_LOG_FILE).read_text(encoding="utf-8").splitlines()[0])
    assert launch_row["status"] == "launch_failed"
    assert "outside configured worktrees_parent" in str(launch_row["message"] or "")


def test_dispatch_packets_override_flag_off_ignores_worker_executor_override(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
        worktrees_parent=tmp_path,
        executor_provider="codex",
        allow_worker_executor_override=False,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["worker_packets"],
        {
            "schema_version": "1.0",
            "packets": [{"worker_id": "worker-1", "packet_id": "packet-1", "profile_alias": "codex", "prompt": "do task"}],
        },
    )
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["worker_registry"],
        {
            "schema_version": "1.0",
            "workers": [
                {
                    "worker_id": "worker-1",
                    "worktree": str(tmp_path / "workstation-1"),
                    "status": "idle",
                    "next_task_provider": "blackbox",
                    "next_task_model": "blackboxai/minimax/minimax-m2.5",
                }
            ],
        },
    )
    (tmp_path / "workstation-1").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(MODULE, "_resolve_dispatch_script", lambda _cfg: Path("/tmp/fake-dispatch.py"))
    captured_cmds: list[list[str]] = []

    def fake_run(cmd, **_kwargs):
        captured_cmds.append(list(cmd))
        payload = {"status": "started", "session_id": "thread-123", "pid": 4321}
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(MODULE.subprocess, "run", fake_run)
    counters = MODULE._dispatch_packets(cfg, cycle_number=1)
    assert counters["launched"] == 1
    assert captured_cmds
    assert captured_cmds[0][0] == "python3"
    launch_row = json.loads((tmp_path / MODULE.DISPATCH_LAUNCH_LOG_FILE).read_text(encoding="utf-8").splitlines()[0])
    assert launch_row["executor_provider"] == "codex"


def test_dispatch_packets_override_flag_on_applies_worker_executor_override(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
        worktrees_parent=tmp_path,
        executor_provider="codex",
        allow_worker_executor_override=True,
        blackbox_lane="free",
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["worker_packets"],
        {
            "schema_version": "1.0",
            "packets": [{"worker_id": "worker-1", "packet_id": "packet-1", "profile_alias": "codex", "prompt": "do task"}],
        },
    )
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["worker_registry"],
        {
            "schema_version": "1.0",
            "workers": [
                {
                    "worker_id": "worker-1",
                    "worktree": str(tmp_path / "workstation-1"),
                    "status": "idle",
                    "next_task_provider": "blackbox",
                    "next_task_model": "blackboxai/minimax/minimax-free",
                }
            ],
        },
    )
    (tmp_path / "workstation-1").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(MODULE, "_resolve_dispatch_script", lambda _cfg: None)
    monkeypatch.setattr(
        MODULE,
        "_build_blackbox_exec_command",
        lambda _cfg, _prompt, model=None: (["blackbox", "-m", str(model or "x"), "-p", "do task"], {}, None),
    )
    monkeypatch.setattr(MODULE, "_append_new_executor_event", lambda *_args, **_kwargs: None)

    class FakeProc:
        def __init__(self, pid: int) -> None:
            self.pid = pid

    monkeypatch.setattr(MODULE.subprocess, "Popen", lambda *args, **kwargs: FakeProc(9876))

    counters = MODULE._dispatch_packets(cfg, cycle_number=2)

    assert counters["launched"] == 1
    launch_row = json.loads((tmp_path / MODULE.DISPATCH_LAUNCH_LOG_FILE).read_text(encoding="utf-8").splitlines()[0])
    assert launch_row["executor_provider"] == "blackbox"
    assert launch_row["executor_model"] == "blackboxai/minimax/minimax-free"
    assert launch_row["pid"] == 9876
    worker_registry = json.loads((tmp_path / MODULE.ARTIFACT_FILES["worker_registry"]).read_text(encoding="utf-8"))
    worker = worker_registry["workers"][0]
    assert worker["current_task_provider"] == "blackbox"
    assert worker["current_task_model"] == "blackboxai/minimax/minimax-free"


def test_watchdog_emits_exit_signal_after_idle_threshold(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._ensure_initialize_state(cfg)
    MODULE._ensure_default_artifacts(cfg)

    stale_epoch = int((datetime.now(timezone.utc) - timedelta(minutes=MODULE.WATCHDOG_STALE_COMMIT_MINUTES + 5)).timestamp())
    monkeypatch.setattr(MODULE, "_git_commit_epoch_seconds", lambda _repo_root, _ref: stale_epoch)
    current_sha = git(tmp_path, "rev-parse", "main")
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["watchdog_state"],
        {
            "schema_version": "1.0",
            "cycle_number": 0,
            "monitored_branch": "main",
            "last_commit_sha": current_sha,
            "commit_ref": "main",
            "last_commit_at_utc": "",
            "last_commit_age_minutes": None,
            "watchdog_age_offset_minutes": 0.0,
            "watchdog_age_minutes": None,
            "watchdog_target_reset_at_utc": "2026-01-01T00:00:00Z",
            "stale_after_minutes": MODULE.WATCHDOG_STALE_COMMIT_MINUTES,
            "stale": False,
        },
    )

    MODULE._atomic_write_json(
        tmp_path / MODULE.RUN_LOCK_FILE,
        {
            "schema_version": "1.0",
            "lock_id": "op-simple-build-test-lock",
            "pid": 12345,
            "started_at": MODULE.utc_now_iso(),
            "command": "op-simple-build",
        },
    )

    stop, signal = MODULE._watchdog_tick(cfg, cycle_number=1)
    assert stop is False
    assert signal["reason_code"] == "stale_base_branch_commit"
    assert float(signal["watchdog_age_minutes"] or 0.0) <= 0.001
    assert float(signal["commit_age_minutes"]) > float(MODULE.WATCHDOG_STALE_COMMIT_MINUTES)

    state = json.loads((tmp_path / MODULE.ARTIFACT_FILES["watchdog_state"]).read_text(encoding="utf-8"))
    assert state["stale"] is False
    assert float(state["watchdog_age_minutes"] or 0.0) <= 0.001
    assert state["stale_after_minutes"] == MODULE.WATCHDOG_STALE_COMMIT_MINUTES
    assert not (tmp_path / MODULE.ARTIFACT_FILES["watchdog_exit_signal"]).exists()
    nudge_path = tmp_path / MODULE.RECOVERY_INSTRUCTIONS_FILE
    assert not nudge_path.exists()


def test_write_watchdog_recovery_nudge_appends_loaded_narrative(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
    )
    template_path = tmp_path / "watchdog_nudge_body_template.md"
    template_text = (
        "This is a custom narrative body.\n\n"
        "## Custom checklist\n"
        "1. Confirm profile posture.\n"
    )
    template_path.write_text(template_text, encoding="utf-8")
    monkeypatch.setattr(MODULE, "WATCHDOG_RECOVERY_NUDGE_BODY_TEMPLATE_FILE", template_path)

    MODULE._write_watchdog_recovery_nudge(
        cfg,
        cycle_number=17,
        monitored_branch="op-simple-canary-test",
        commit_ref="op-simple-canary-test",
        last_commit_sha="abc123",
        last_commit_at_utc="2026-03-14T00:00:00Z",
        watchdog_age_minutes=31.23456,
        stale_after_minutes=150,
    )

    nudge_text = (tmp_path / MODULE.RECOVERY_INSTRUCTIONS_FILE).read_text(encoding="utf-8")
    assert "Cycle: 17" in nudge_text
    assert "Reason: Watchdog observed no repository movement for 31.235 minutes." in nudge_text
    assert "Watchdog stop threshold: 150 minutes" in nudge_text
    assert "This is a custom narrative body." in nudge_text
    assert "## Custom checklist" in nudge_text
    assert nudge_text.index("Watchdog stop threshold: 150 minutes") < nudge_text.index("This is a custom narrative body.")


def test_write_watchdog_recovery_nudge_uses_fallback_when_template_missing(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
    )
    monkeypatch.setattr(
        MODULE,
        "WATCHDOG_RECOVERY_NUDGE_BODY_TEMPLATE_FILE",
        tmp_path / "missing-watchdog-recovery-nudge-body-template.md",
    )

    MODULE._write_watchdog_recovery_nudge(
        cfg,
        cycle_number=5,
        monitored_branch="main",
        commit_ref="main",
        last_commit_sha="abc123",
        last_commit_at_utc="2026-03-14T00:00:00Z",
        watchdog_age_minutes=42.0,
        stale_after_minutes=150,
    )

    nudge_text = (tmp_path / MODULE.RECOVERY_INSTRUCTIONS_FILE).read_text(encoding="utf-8")
    assert "Broad diagnostics checklist" in nudge_text
    assert "rename this file to `recovery_instructions_CONSUMED.md`" in nudge_text


def test_watchdog_emits_recovery_nudge_after_30_minutes_without_stale_stop(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._ensure_initialize_state(cfg)
    MODULE._ensure_default_artifacts(cfg)

    stale_epoch = int((datetime.now(timezone.utc) - timedelta(minutes=MODULE.WATCHDOG_RECOVERY_NUDGE_MINUTES + 5)).timestamp())
    monkeypatch.setattr(MODULE, "_git_commit_epoch_seconds", lambda _repo_root, _ref: stale_epoch)
    current_sha = git(tmp_path, "rev-parse", "main")
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["watchdog_state"],
        {
            "schema_version": "1.0",
            "cycle_number": 0,
            "monitored_branch": "main",
            "last_commit_sha": current_sha,
            "commit_ref": "main",
            "last_commit_at_utc": "",
            "last_commit_age_minutes": None,
            "watchdog_age_offset_minutes": 0.0,
            "watchdog_age_minutes": None,
            "watchdog_target_reset_at_utc": "2026-01-01T00:00:00Z",
            "stale_after_minutes": MODULE.WATCHDOG_STALE_COMMIT_MINUTES,
            "stale": False,
        },
    )

    stop, signal = MODULE._watchdog_tick(cfg, cycle_number=9)

    assert stop is False
    assert signal["reason_code"] == "stale_base_branch_commit"
    assert float(signal["watchdog_age_minutes"]) >= float(MODULE.WATCHDOG_RECOVERY_NUDGE_MINUTES)
    assert not (tmp_path / MODULE.ARTIFACT_FILES["watchdog_exit_signal"]).exists()
    nudge_path = tmp_path / MODULE.RECOVERY_INSTRUCTIONS_FILE
    assert nudge_path.exists()
    nudge_text = nudge_path.read_text(encoding="utf-8")
    assert "Generated at:" in nudge_text
    assert "no repository movement" in nudge_text
    assert "Broad diagnostics checklist" in nudge_text


def test_watchdog_force_reset_target_avoids_immediate_stale_stop(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
        resume_mode=True,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._ensure_initialize_state(cfg)
    MODULE._ensure_default_artifacts(cfg)

    stale_epoch = int((datetime.now(timezone.utc) - timedelta(minutes=MODULE.WATCHDOG_STALE_COMMIT_MINUTES + 5)).timestamp())
    monkeypatch.setattr(MODULE, "_git_commit_epoch_seconds", lambda _repo_root, _ref: stale_epoch)
    current_sha = git(tmp_path, "rev-parse", "main")
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["watchdog_state"],
        {
            "schema_version": "1.0",
            "cycle_number": 12,
            "monitored_branch": "main",
            "last_commit_sha": current_sha,
            "commit_ref": "main",
            "last_commit_at_utc": "",
            "last_commit_age_minutes": None,
            "watchdog_age_offset_minutes": 0.0,
            "watchdog_age_minutes": None,
            "watchdog_target_reset_at_utc": "2026-01-01T00:00:00Z",
            "stale_after_minutes": MODULE.WATCHDOG_STALE_COMMIT_MINUTES,
            "stale": True,
        },
    )

    stop, _signal = MODULE._watchdog_tick(cfg, cycle_number=13, force_reset_target=True)

    assert stop is False
    state = json.loads((tmp_path / MODULE.ARTIFACT_FILES["watchdog_state"]).read_text(encoding="utf-8"))
    assert state["stale"] is False
    assert float(state["watchdog_age_minutes"] or 0.0) <= 0.001
    assert float(state["watchdog_age_offset_minutes"]) > float(MODULE.WATCHDOG_STALE_COMMIT_MINUTES)


def test_watchdog_resets_target_when_mergeability_progress_changes(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._ensure_initialize_state(cfg)
    MODULE._ensure_default_artifacts(cfg)

    stale_epoch = int((datetime.now(timezone.utc) - timedelta(minutes=MODULE.WATCHDOG_STALE_COMMIT_MINUTES + 5)).timestamp())
    monkeypatch.setattr(MODULE, "_git_commit_epoch_seconds", lambda _repo_root, _ref: stale_epoch)
    current_sha = git(tmp_path, "rev-parse", "main")
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["watchdog_state"],
        {
            "schema_version": "1.0",
            "cycle_number": 4,
            "monitored_branch": "main",
            "last_commit_sha": current_sha,
            "commit_ref": "main",
            "last_commit_at_utc": "",
            "last_commit_age_minutes": None,
            "watchdog_age_offset_minutes": 0.0,
            "watchdog_age_minutes": 155.0,
            "watchdog_target_reset_at_utc": "2026-01-01T00:00:00Z",
            "stale_after_minutes": MODULE.WATCHDOG_STALE_COMMIT_MINUTES,
            "stale": True,
            "progress_signal": "previous-progress-signal",
            "progress_changed": False,
        },
    )
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["mergeability_report"],
        {
            "schema_version": "1.0",
            "updated_at": "2026-01-01T00:00:00Z",
            "cycle_number": 5,
            "progress_fingerprint": "new-progress-signal",
            "unmerged_commit_count": 1,
            "merge_blockers": [{"reason_code": "lane_pending_tasks"}],
        },
    )

    stop, signal = MODULE._watchdog_tick(cfg, cycle_number=5)

    assert stop is False
    assert signal["reason_code"] == "stale_base_branch_commit"
    assert signal["progress_changed"] is True
    state = json.loads((tmp_path / MODULE.ARTIFACT_FILES["watchdog_state"]).read_text(encoding="utf-8"))
    assert state["progress_changed"] is True
    assert float(state["watchdog_age_minutes"] or 0.0) <= 0.001


def test_watchdog_hard_limit_stops_even_when_lane_branch_is_active(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._ensure_initialize_state(cfg)
    MODULE._ensure_default_artifacts(cfg)
    git(tmp_path, "checkout", "-b", "lane-phase-1-a")
    git(tmp_path, "checkout", "main")
    MODULE._write_lane_base_watchdog_registry(
        cfg,
        cycle_number=0,
        lane_base_branches={"phase-1/lane-a": "lane-phase-1-a"},
        plan_cycle_number=1,
    )
    main_sha = git(tmp_path, "rev-parse", "main")
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["watchdog_state"],
        {
            "schema_version": "1.0",
            "cycle_number": 6,
            "monitored_branch": "main",
            "last_commit_sha": main_sha,
            "watchdog_age_offset_minutes": 0.0,
            "watchdog_target_reset_at_utc": "2026-01-01T00:00:00Z",
            "run_base_hard_age_offset_minutes": 0.0,
            "run_base_hard_target_reset_at_utc": "2026-01-01T00:00:00Z",
            "progress_signal": "stable-progress-signal",
        },
    )
    monkeypatch.setattr(
        MODULE,
        "_watchdog_progress_signal",
        lambda _cfg: {"signal": "stable-progress-signal", "components": {}},
    )
    now_epoch = int(datetime.now(timezone.utc).timestamp())

    def fake_commit_epoch(_repo_root: Path, ref: str) -> int:
        if ref == "main":
            return now_epoch - int((MODULE.WATCHDOG_STALE_COMMIT_MINUTES * 2 + 1) * 60)
        if ref == "lane-phase-1-a":
            return now_epoch - int(2 * 60)
        return now_epoch

    monkeypatch.setattr(MODULE, "_git_commit_epoch_seconds", fake_commit_epoch)

    stop, signal = MODULE._watchdog_tick(cfg, cycle_number=7)

    assert stop is True
    assert signal["reason_code"] == "stale_run_base_hard_limit"
    assert float(signal["run_base_hard_age_minutes"] or 0.0) > float(MODULE.WATCHDOG_STALE_COMMIT_MINUTES * 2)
    assert float(signal["lane_aggregate_watchdog_age_minutes"] or 0.0) < float(MODULE.WATCHDOG_STALE_COMMIT_MINUTES)


def test_watchdog_all_branches_idle_rule_prevents_stop_when_lane_is_active(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._ensure_initialize_state(cfg)
    MODULE._ensure_default_artifacts(cfg)
    git(tmp_path, "checkout", "-b", "lane-phase-2-b")
    git(tmp_path, "checkout", "main")
    MODULE._write_lane_base_watchdog_registry(
        cfg,
        cycle_number=0,
        lane_base_branches={"phase-2/lane-b": "lane-phase-2-b"},
        plan_cycle_number=1,
    )
    main_sha = git(tmp_path, "rev-parse", "main")
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["watchdog_state"],
        {
            "schema_version": "1.0",
            "cycle_number": 10,
            "monitored_branch": "main",
            "last_commit_sha": main_sha,
            "watchdog_age_offset_minutes": 0.0,
            "watchdog_target_reset_at_utc": "2026-01-01T00:00:00Z",
            "run_base_hard_age_offset_minutes": 0.0,
            "run_base_hard_target_reset_at_utc": "2026-01-01T00:00:00Z",
            "progress_signal": "stable-progress-signal",
        },
    )
    monkeypatch.setattr(
        MODULE,
        "_watchdog_progress_signal",
        lambda _cfg: {"signal": "stable-progress-signal", "components": {}},
    )
    now_epoch = int(datetime.now(timezone.utc).timestamp())

    def fake_commit_epoch(_repo_root: Path, ref: str) -> int:
        if ref == "main":
            return now_epoch - int((MODULE.WATCHDOG_STALE_COMMIT_MINUTES + 5) * 60)
        if ref == "lane-phase-2-b":
            return now_epoch - int(1 * 60)
        return now_epoch

    monkeypatch.setattr(MODULE, "_git_commit_epoch_seconds", fake_commit_epoch)

    stop, signal = MODULE._watchdog_tick(cfg, cycle_number=11)

    assert stop is False
    assert signal["reason_code"] == "stale_base_branch_commit"
    assert signal["all_monitored_branches_idle_stale"] is False
    assert float(signal["watchdog_age_minutes"] or 0.0) > float(MODULE.WATCHDOG_STALE_COMMIT_MINUTES)
    assert float(signal["lane_aggregate_watchdog_age_minutes"] or 0.0) < float(MODULE.WATCHDOG_STALE_COMMIT_MINUTES)


def test_watchdog_terminal_warning_nudge_has_cycle_cooldown(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._ensure_initialize_state(cfg)
    MODULE._ensure_default_artifacts(cfg)
    git(tmp_path, "checkout", "-b", "lane-phase-3-c")
    git(tmp_path, "checkout", "main")
    MODULE._write_lane_base_watchdog_registry(
        cfg,
        cycle_number=0,
        lane_base_branches={"phase-3/lane-c": "lane-phase-3-c"},
        plan_cycle_number=1,
    )
    main_sha = git(tmp_path, "rev-parse", "main")
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["watchdog_state"],
        {
            "schema_version": "1.0",
            "cycle_number": 9,
            "monitored_branch": "main",
            "last_commit_sha": main_sha,
            "watchdog_age_offset_minutes": 0.0,
            "watchdog_target_reset_at_utc": "2026-01-01T00:00:00Z",
            "run_base_hard_age_offset_minutes": 0.0,
            "run_base_hard_target_reset_at_utc": "2026-01-01T00:00:00Z",
            "progress_signal": "stable-progress-signal",
            "terminal_warning_last_emitted_cycle": None,
        },
    )
    monkeypatch.setattr(
        MODULE,
        "_watchdog_progress_signal",
        lambda _cfg: {"signal": "stable-progress-signal", "components": {}},
    )
    now_epoch = int(datetime.now(timezone.utc).timestamp())
    hard_warning_age = int((MODULE.WATCHDOG_STALE_COMMIT_MINUTES * 2) - MODULE.WATCHDOG_TERMINAL_WARNING_LEAD_MINUTES + 1)

    def fake_commit_epoch(_repo_root: Path, ref: str) -> int:
        if ref == "main":
            return now_epoch - int(hard_warning_age * 60)
        if ref == "lane-phase-3-c":
            return now_epoch - int(1 * 60)
        return now_epoch

    monkeypatch.setattr(MODULE, "_git_commit_epoch_seconds", fake_commit_epoch)

    stop_first, _signal_first = MODULE._watchdog_tick(cfg, cycle_number=10)

    assert stop_first is False
    warning_path = tmp_path / MODULE.TERMINAL_WARNING_INSTRUCTIONS_FILE
    assert warning_path.exists()
    warning_path.unlink()

    stop_second, _signal_second = MODULE._watchdog_tick(cfg, cycle_number=12)

    assert stop_second is False
    assert not warning_path.exists()
    state = json.loads((tmp_path / MODULE.ARTIFACT_FILES["watchdog_state"]).read_text(encoding="utf-8"))
    assert state["terminal_warning_last_emitted_cycle"] == 10
    assert state["terminal_warning_emitted_this_cycle"] is False


def test_lane_watchdog_registry_refresh_prefers_plan_lane_map(tmp_path: Path) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._ensure_initialize_state(cfg)
    MODULE._ensure_default_artifacts(cfg)
    git(tmp_path, "checkout", "-b", "lane-phase-legacy-a")
    git(tmp_path, "checkout", "main")
    git(tmp_path, "checkout", "-b", "lane-phase-fresh-b")
    git(tmp_path, "checkout", "main")

    MODULE._write_lane_base_watchdog_registry(
        cfg,
        cycle_number=2,
        lane_base_branches={"phase-legacy/lane-a": "lane-phase-legacy-a"},
        plan_cycle_number=3,
    )
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["plan_packets"],
        {
            "schema_version": "1.0",
            "updated_at": "2026-01-01T00:00:00Z",
            "cycle_number": 9,
            "lane_base_branches": {"phase-fresh/lane-b": "lane-phase-fresh-b"},
            "tasks": [],
        },
    )

    MODULE._refresh_lane_base_watchdog_registry(
        cfg,
        cycle_number=4,
        now_utc=datetime.now(timezone.utc),
        force_reset_target=False,
    )

    registry = json.loads((tmp_path / MODULE.ARTIFACT_FILES["lane_base_watchdog_registry"]).read_text(encoding="utf-8"))
    assert registry["lane_base_branches"] == {"phase-fresh/lane-b": "lane-phase-fresh-b"}
    assert int(registry["plan_cycle_number"] or 0) == 9
    lane_ids = sorted(str(row.get("lane_id") or "") for row in registry.get("lanes", []) if isinstance(row, dict))
    assert lane_ids == ["phase-fresh/lane-b"]


def test_run_resume_passes_watchdog_target_reset_once(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._atomic_write_json(
        tmp_path / MODULE.INITIALIZE_STATE_FILE,
        {
            "schema_version": "1.0",
            "updated_at": "2026-01-01T00:00:00Z",
            "monitored_branch": "main",
            "workflow": {"max_parallel_workers": 8},
            "run_context": {
                "run_base_branch": "main",
                "run_base_from_branch": "main",
                "run_base_from_commit": git(tmp_path, "rev-parse", "main"),
                "run_base_created_at": "2026-01-01T00:00:00Z",
                "created_new": False,
                "dry_run": True,
            },
        },
    )

    force_flags: list[bool] = []

    def fake_watchdog_tick(_cfg, _cycle_number, *, force_reset_target=False):
        force_flags.append(bool(force_reset_target))
        return False, {"message": "watchdog healthy"}

    monkeypatch.setattr(MODULE, "_watchdog_tick", fake_watchdog_tick)

    out = MODULE.run_op_simple_build(
        make_req(
            tmp_path,
            command="op-resume",
            dry_run=True,
            max_build_cycles=1,
            sleep_minutes=0,
        )
    )

    assert out["ok"] is True
    assert force_flags == [True]


def test_rate_gate_wait_logs_heartbeat_and_rescan(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)

    states = iter(["all_hard_gated", "all_hard_gated", "has_ungated"])

    def fake_gate_state(_cfg):
        try:
            return next(states)
        except StopIteration:  # pragma: no cover - defensive fallback
            return "has_ungated"

    refresh_calls = {"count": 0}

    def fake_refresh(*_args, **_kwargs):
        refresh_calls["count"] += 1
        return True, "snapshot refreshed"

    monkeypatch.setattr(MODULE, "_profile_snapshot_gate_state", fake_gate_state)
    monkeypatch.setattr(MODULE, "_refresh_profile_snapshot_via_skill", fake_refresh)
    monkeypatch.setattr(MODULE.time, "sleep", lambda _seconds: None)

    warnings: list[dict[str, object]] = []
    MODULE._run_rate_gate_wait(cfg, cycle_number=7, warnings=warnings)

    assert refresh_calls["count"] >= 2
    rows = [json.loads(line) for line in (tmp_path / MODULE.MANAGER_CALL_LOG_FILE).read_text(encoding="utf-8").splitlines()]
    assert any(row.get("manager") == "rate-gate" and row.get("status") == "heartbeat" for row in rows)


def test_rate_gate_wait_is_skipped_for_blackbox_executor(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
        executor_provider="blackbox",
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    called = {"refresh": 0}

    def fake_refresh(*_args, **_kwargs):
        called["refresh"] += 1
        return True, "should not be called"

    monkeypatch.setattr(MODULE, "_refresh_profile_snapshot_via_skill", fake_refresh)
    warnings: list[dict[str, object]] = []
    MODULE._run_rate_gate_wait(cfg, cycle_number=9, warnings=warnings)
    assert called["refresh"] == 0
    assert warnings == []


def test_rate_gate_wait_conservative_when_snapshot_unknown(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)

    states = iter(["unknown", "unknown", "has_ungated"])

    def fake_gate_state(_cfg):
        try:
            return next(states)
        except StopIteration:  # pragma: no cover - defensive fallback
            return "has_ungated"

    monkeypatch.setattr(MODULE, "_profile_snapshot_gate_state", fake_gate_state)
    monkeypatch.setattr(MODULE, "_refresh_profile_snapshot_via_skill", lambda *_args, **_kwargs: (False, "refresh failed"))
    monkeypatch.setattr(MODULE, "_refresh_rate_gate_snapshot", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(MODULE.time, "sleep", lambda _seconds: None)

    warnings: list[dict[str, object]] = []
    MODULE._run_rate_gate_wait(cfg, cycle_number=8, warnings=warnings)

    assert any(item.get("code") == "rate_gate_snapshot_unknown" for item in warnings)
    rows = [json.loads(line) for line in (tmp_path / MODULE.MANAGER_CALL_LOG_FILE).read_text(encoding="utf-8").splitlines()]
    assert any(row.get("manager") == "rate-gate" and row.get("status") == "heartbeat" for row in rows)


def test_rate_gate_rescan_logs_failure_returncode(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)

    states = iter(["all_hard_gated", "all_hard_gated", "has_ungated"])

    def fake_gate_state(_cfg):
        try:
            return next(states)
        except StopIteration:  # pragma: no cover - defensive fallback
            return "has_ungated"

    calls = {"count": 0}

    def fake_refresh(*_args, **_kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return True, "entry refresh ok"
        return False, "rescan refresh failed"

    monkeypatch.setattr(MODULE, "_profile_snapshot_gate_state", fake_gate_state)
    monkeypatch.setattr(MODULE, "_refresh_profile_snapshot_via_skill", fake_refresh)
    monkeypatch.setattr(MODULE, "_refresh_rate_gate_snapshot", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(MODULE.time, "sleep", lambda _seconds: None)

    warnings: list[dict[str, object]] = []
    MODULE._run_rate_gate_wait(cfg, cycle_number=9, warnings=warnings)

    rows = [json.loads(line) for line in (tmp_path / MODULE.MANAGER_CALL_LOG_FILE).read_text(encoding="utf-8").splitlines()]
    rescan_rows = [row for row in rows if row.get("manager") == "rate-gate" and row.get("status") == "rescan"]
    assert rescan_rows
    assert any(int(row.get("returncode") or 0) == 1 for row in rescan_rows)


def test_dispatch_respects_parallel_worker_cap(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=1,
        dry_run=False,
        worktrees_parent=tmp_path,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["worker_packets"],
        {
            "schema_version": "1.0",
            "packets": [
                {
                    "worker_id": "worker-2",
                    "packet_id": "packet-2",
                    "profile_alias": "codex",
                    "prompt": "next task",
                }
            ],
        },
    )
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["worker_registry"],
        {
            "schema_version": "1.0",
            "workers": [
                {
                    "worker_id": "worker-1",
                    "status": "in_progress",
                    "pid": 9999,
                    "thread_id": "thread-existing",
                }
            ],
        },
    )
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["profile_snapshot"],
        {
            "schema_version": "1.0",
            "profiles": [{"alias": "codex", "codex_home": "/tmp/.codex"}],
        },
    )

    monkeypatch.setattr(MODULE, "_resolve_dispatch_script", lambda _cfg: Path("/tmp/fake-dispatch.py"))
    monkeypatch.setattr(MODULE, "_is_pid_alive", lambda _pid: True)

    def fail_run(*_args, **_kwargs):  # pragma: no cover - should not execute when cap reached
        raise AssertionError("dispatch subprocess should not be called when parallel cap is exhausted")

    monkeypatch.setattr(MODULE.subprocess, "run", fail_run)

    counters = MODULE._dispatch_packets(cfg, cycle_number=3)

    assert counters == {"attempted": 0, "launched": 0, "launch_failed": 0, "unknown": 0}
    assert not (tmp_path / MODULE.DISPATCH_LAUNCH_LOG_FILE).exists()


def test_dispatch_ignores_dead_pid_for_parallel_capacity(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=1,
        dry_run=False,
        worktrees_parent=tmp_path,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["worker_packets"],
        {
            "schema_version": "1.0",
            "packets": [
                {
                    "worker_id": "worker-2",
                    "packet_id": "packet-2",
                    "profile_alias": "codex",
                    "prompt": "next task",
                }
            ],
        },
    )
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["worker_registry"],
        {
            "schema_version": "1.0",
            "workers": [
                {
                    "worker_id": "worker-1",
                    "status": "in_progress",
                    "pid": 9999,
                    "thread_id": "thread-existing",
                },
                {
                    "worker_id": "worker-2",
                    "worktree": str(tmp_path / "workstation-2"),
                    "status": "idle",
                    "pid": None,
                    "thread_id": None,
                },
            ],
        },
    )
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["profile_snapshot"],
        {
            "schema_version": "1.0",
            "profiles": [{"alias": "codex", "codex_home": "/tmp/.codex"}],
        },
    )
    (tmp_path / "workstation-2").mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(MODULE, "_resolve_dispatch_script", lambda _cfg: Path("/tmp/fake-dispatch.py"))
    monkeypatch.setattr(MODULE, "_is_pid_alive", lambda _pid: False)

    def fake_run(*_args, **_kwargs):
        payload = {"status": "started", "session_id": "thread-new", "pid": 4321}
        return subprocess.CompletedProcess(args=[], returncode=0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(MODULE.subprocess, "run", fake_run)

    counters = MODULE._dispatch_packets(cfg, cycle_number=3)

    assert counters == {"attempted": 1, "launched": 1, "launch_failed": 0, "unknown": 0}


def test_normalize_dead_worker_leases_clears_pid_only_and_preserves_assignments(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=2,
        dry_run=False,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["worker_registry"],
        {
            "schema_version": "1.0",
            "cycle_number": 4,
            "workers": [
                {
                    "worker_id": "worker-1",
                    "status": "in_progress",
                    "pid": 1111,
                    "thread_id": "thread-dead",
                    "current_task_id": "TASK-001",
                    "current_packet_id": "packet-1",
                    "current_task_profile": "codex",
                },
                {
                    "worker_id": "worker-2",
                    "status": "in_progress",
                    "pid": 2222,
                    "thread_id": "thread-live",
                    "current_task_id": "TASK-002",
                    "current_packet_id": "packet-2",
                    "current_task_profile": "codex",
                },
            ],
        },
    )
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["task_execution_state"],
        {
            "schema_version": "1.0",
            "cycle_number": 4,
            "tasks": [
                {"task_id": "TASK-001", "status": "in_progress", "assigned_worker": "worker-1", "assigned_profile": "codex"},
                {"task_id": "TASK-002", "status": "in_progress", "assigned_worker": "worker-2", "assigned_profile": "codex"},
            ],
        },
    )

    monkeypatch.setattr(MODULE, "_is_pid_alive", lambda pid: int(pid) == 2222)

    out = MODULE._normalize_dead_worker_leases(cfg, cycle_number=5)

    assert out == {"reclaimed_workers": 1, "requeued_tasks": 0}

    worker_registry = json.loads((tmp_path / MODULE.ARTIFACT_FILES["worker_registry"]).read_text(encoding="utf-8"))
    worker_1 = next(row for row in worker_registry["workers"] if row["worker_id"] == "worker-1")
    worker_2 = next(row for row in worker_registry["workers"] if row["worker_id"] == "worker-2")
    assert worker_1["status"] == "in_progress"
    assert worker_1["pid"] is None
    assert worker_1["thread_id"] == "thread-dead"
    assert worker_1["current_task_id"] == "TASK-001"
    assert worker_1["current_packet_id"] == "packet-1"
    assert worker_2["status"] == "in_progress"
    assert worker_2["pid"] == 2222

    task_state = json.loads((tmp_path / MODULE.ARTIFACT_FILES["task_execution_state"]).read_text(encoding="utf-8"))
    task_1 = next(row for row in task_state["tasks"] if row["task_id"] == "TASK-001")
    task_2 = next(row for row in task_state["tasks"] if row["task_id"] == "TASK-002")
    assert task_1["status"] == "in_progress"
    assert task_1["assigned_worker"] == "worker-1"
    assert task_1["assigned_profile"] == "codex"
    assert task_2["status"] == "in_progress"
    assert task_2["assigned_worker"] == "worker-2"


def test_ensure_workstation_prep_prepares_slots_and_seeds_worker_registry(tmp_path: Path, monkeypatch) -> None:
    worktrees_parent = tmp_path / "forest"
    worktrees_parent.mkdir(parents=True, exist_ok=True)
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=2,
        dry_run=False,
        worktrees_parent=worktrees_parent,
    )
    (tmp_path / ".op-simple" / "current").mkdir(parents=True, exist_ok=True)
    init_state = MODULE._ensure_initialize_state(
        cfg,
        run_meta={
            "run_base_branch": "op-simple-canary-test",
            "run_base_from_branch": "main",
            "run_base_from_commit": git(tmp_path, "rev-parse", "HEAD"),
            "run_base_created_at": "2026-01-01T00:00:00Z",
            "created_new": True,
            "dry_run": False,
        },
    )
    fake_script = tmp_path / "fake_prepare.py"
    fake_script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    monkeypatch.setattr(MODULE, "_resolve_workstation_prepare_script", lambda _cfg: fake_script)

    real_run = MODULE.subprocess.run

    def fake_run(cmd, *args, **kwargs):
        if isinstance(cmd, list) and len(cmd) >= 2 and cmd[0] == "python3" and cmd[1] == str(fake_script):
            assert cmd[cmd.index("--worktrees-parent") + 1] == str(worktrees_parent.resolve())
            worktree_name = cmd[cmd.index("--worktree-name") + 1]
            branch_name = cmd[cmd.index("--branch-name") + 1]
            target_path = worktrees_parent / worktree_name
            target_path.mkdir(parents=True, exist_ok=True)
            payload = {
                "ok": True,
                "target_path": str(target_path),
                "branch_name_resolved": branch_name,
                "message": "prepared",
            }
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=json.dumps(payload), stderr="")
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(MODULE.subprocess, "run", fake_run)

    out = MODULE._ensure_workstation_prep(cfg, initialize_state=init_state, force_refresh=True)

    assert len(out["workstations"]) == 2
    assert out["worktrees_parent"] == str(worktrees_parent.resolve())
    assert out["workstations"][0]["workstation_id"] == MODULE._workstation_id_for_index(cfg, 1)
    assert out["workstations"][0]["branch"].startswith("op-simple-canary-test-w")
    assert Path(out["workstations"][0]["worktree"]).exists()

    registry = json.loads((tmp_path / MODULE.ARTIFACT_FILES["worker_registry"]).read_text(encoding="utf-8"))
    assert len(registry["workers"]) == 2
    assert registry["workers"][0]["worker_id"] == "worker-1"
    assert registry["workers"][0]["status"] == "idle"


def test_ensure_initialize_state_refreshes_run_specific_fields(tmp_path: Path) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=5,
        dry_run=False,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._atomic_write_json(
        tmp_path / MODULE.INITIALIZE_STATE_FILE,
        {
            "schema_version": "1.0",
            "updated_at": "2026-01-01T00:00:00Z",
            "monitored_branch": "old-branch",
            "workflow": {"max_parallel_workers": 2, "preserve_me": True},
            "run_context": {"run_base_branch": "old-branch"},
            "custom": {"note": "keep"},
        },
    )

    out = MODULE._ensure_initialize_state(
        cfg,
        run_meta={
            "run_base_branch": "op-simple-canary-123",
            "run_base_from_branch": "main",
            "run_base_from_commit": "abc123",
            "run_base_created_at": "2026-01-02T00:00:00Z",
            "created_new": True,
            "dry_run": False,
        },
    )

    assert out["monitored_branch"] == "op-simple-canary-123"
    assert out["workflow"]["max_parallel_workers"] == 5
    assert out["workflow"]["preserve_me"] is True
    assert out["custom"] == {"note": "keep"}
    assert out["run_context"]["run_base_branch"] == "op-simple-canary-123"


def test_seed_plan_artifacts_from_planner_when_current_plan_empty(tmp_path: Path) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=2,
        dry_run=False,
    )
    (tmp_path / ".op-simple" / "current").mkdir(parents=True, exist_ok=True)
    (tmp_path / "reports" / "optimus-prime" / "planning").mkdir(parents=True, exist_ok=True)
    planner_payload = {
        "schema_version": "1.0",
        "lane_base_branches": {"phase-1/lane-a": "lane-phase-1-a"},
        "tasks": [
            {
                "task_id": "TASK-001",
                "phase_id": "phase-1",
                "lane_id": "phase-1/lane-a",
                "status": "pending",
            }
        ],
    }
    (tmp_path / "reports" / "optimus-prime" / "planning" / "PLAN_PACKETS.json").write_text(
        json.dumps(planner_payload, indent=2),
        encoding="utf-8",
    )
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["plan_packets"],
        {"schema_version": "1.0", "tasks": []},
    )
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["task_execution_state"],
        {"schema_version": "1.0", "tasks": []},
    )

    seeded = MODULE._seed_plan_artifacts_from_planner(cfg)

    assert seeded is True
    current_plan = json.loads((tmp_path / MODULE.ARTIFACT_FILES["plan_packets"]).read_text(encoding="utf-8"))
    assert len(current_plan["tasks"]) == 1
    assert current_plan["lane_base_branches"] == {"phase-1/lane-a": "lane-phase-1-a"}
    task_state = json.loads((tmp_path / MODULE.ARTIFACT_FILES["task_execution_state"]).read_text(encoding="utf-8"))
    assert len(task_state["tasks"]) == 1
    assert task_state["blockers"] == []
    assert set(task_state["attempts"]) == set(MODULE.TASK_ATTEMPT_STAGES)
    assert task_state["last_handoff_outcome"]["status"] == "unknown"


def test_ensure_default_artifacts_write_task_execution_state_sections(tmp_path: Path) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=2,
        dry_run=False,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)

    MODULE._ensure_default_artifacts(cfg)

    task_state = json.loads((tmp_path / MODULE.ARTIFACT_FILES["task_execution_state"]).read_text(encoding="utf-8"))
    assert task_state["tasks"] == []
    assert task_state["blockers"] == []
    assert set(task_state["attempts"]) == set(MODULE.TASK_ATTEMPT_STAGES)
    assert task_state["last_handoff_outcome"]["status"] == "unknown"


def test_run_blocks_preflight_when_lane_base_branches_contract_missing(tmp_path: Path) -> None:
    build_repo(tmp_path)
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["plan_packets"],
        {
            "schema_version": "1.0",
            "updated_at": "2026-01-01T00:00:00Z",
            "cycle_number": 1,
            "tasks": [
                {
                    "task_id": "TASK-001",
                    "lane_id": "phase-1/lane-a",
                    "status": "pending",
                }
            ],
        },
    )

    out = MODULE.run_op_simple_build(
        make_req(
            tmp_path,
            dry_run=True,
            max_build_cycles=1,
            sleep_minutes=0,
            ground_sync_enabled=False,
        )
    )

    assert out["ok"] is False
    assert out["status"] == "blocked_preflight"
    errors = out["errors"] if isinstance(out.get("errors"), list) else []
    assert errors
    assert str(errors[0].get("code") or "").strip() in {"lane_base_branches_invalid", "lane_base_branches_missing"}


def test_run_resume_blocks_preflight_when_lane_base_branches_missing_lane_mapping(tmp_path: Path) -> None:
    build_repo(tmp_path)
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._atomic_write_json(
        tmp_path / MODULE.INITIALIZE_STATE_FILE,
        {
            "schema_version": "1.0",
            "updated_at": "2026-01-01T00:00:00Z",
            "monitored_branch": "main",
            "workflow": {"max_parallel_workers": 8},
            "run_context": {
                "run_base_branch": "main",
                "run_base_from_branch": "main",
                "run_base_from_commit": git(tmp_path, "rev-parse", "main"),
                "run_base_created_at": "2026-01-01T00:00:00Z",
                "created_new": False,
                "dry_run": True,
            },
        },
    )
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["plan_packets"],
        {
            "schema_version": "1.0",
            "updated_at": "2026-01-01T00:00:00Z",
            "cycle_number": 2,
            "lane_base_branches": {},
            "tasks": [
                {
                    "task_id": "TASK-002",
                    "lane_id": "phase-2/lane-b",
                    "status": "pending",
                }
            ],
        },
    )

    out = MODULE.run_op_simple_build(
        make_req(
            tmp_path,
            command="op-resume",
            dry_run=True,
            max_build_cycles=1,
            sleep_minutes=0,
            ground_sync_enabled=False,
        )
    )

    assert out["ok"] is False
    assert out["status"] == "blocked_preflight"
    errors = out["errors"] if isinstance(out.get("errors"), list) else []
    assert errors
    assert str(errors[0].get("code") or "").strip() == "lane_base_branches_incomplete"


def test_installed_fallback_paths_for_prompts_and_schema(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir(parents=True, exist_ok=True)
    build_repo(project_root)

    installed_scripts = tmp_path / "installed" / "scripts"
    prompt_dir = installed_scripts / "op_simple" / "prompts" / "managers"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    (prompt_dir / "boss.md").write_text("installed prompt\n", encoding="utf-8")

    schema_path = installed_scripts.parent / "docs" / "plans" / "OP_SIMPLE_SCHEMA_CATALOG_V2.md"
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    schema_path.write_text("# schema\n", encoding="utf-8")

    cfg = MODULE.RunConfig(
        repo_root=project_root,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
    )

    monkeypatch.setattr(MODULE, "SCRIPTS_ROOT", installed_scripts)

    resolved_prompt = MODULE._manager_prompt_template_path(cfg, "BOSS")
    assert resolved_prompt == (prompt_dir / "boss.md")
    assert MODULE._load_prompt_template(cfg, "BOSS").strip() == "installed prompt"
    assert MODULE._schema_catalog_path(cfg) == schema_path.resolve()


def test_create_run_base_branch_creates_unique_branch_from_main(tmp_path: Path) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
    )
    before_main = git(tmp_path, "rev-parse", "main")

    run_meta = MODULE._create_run_base_branch(cfg)

    current = git(tmp_path, "branch", "--show-current")
    assert current == run_meta["run_base_branch"]
    assert current.startswith("op-simple-canary-")
    assert run_meta["run_base_from_branch"] == "main"
    assert run_meta["run_base_from_commit"] == before_main
    assert run_meta["created_new"] is True


def test_create_run_base_branch_uses_configured_source_branch(tmp_path: Path) -> None:
    build_repo(tmp_path)
    git(tmp_path, "checkout", "-b", "feature-seed")
    (tmp_path / "feature.txt").write_text("seed\n", encoding="utf-8")
    git(tmp_path, "add", "feature.txt")
    git(tmp_path, "commit", "-m", "feature seed")
    source_commit = git(tmp_path, "rev-parse", "feature-seed")

    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
        run_base_source_branch="feature-seed",
    )

    run_meta = MODULE._create_run_base_branch(cfg)

    current = git(tmp_path, "branch", "--show-current")
    assert current == run_meta["run_base_branch"]
    assert current.startswith("op-simple-canary-")
    assert run_meta["run_base_from_branch"] == "feature-seed"
    assert run_meta["run_base_from_commit"] == source_commit
    assert run_meta["created_new"] is True


def test_create_run_base_branch_dry_run_uses_current_branch(tmp_path: Path) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=True,
    )

    run_meta = MODULE._create_run_base_branch(cfg)

    assert run_meta["created_new"] is False
    assert run_meta["run_base_branch"] == "main"
    assert git(tmp_path, "branch", "--show-current") == "main"


def test_run_prefers_project_done_over_watchdog_stop(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)

    monkeypatch.setattr(
        MODULE,
        "_watchdog_tick",
        lambda _cfg, _cycle, *, force_reset_target=False: (True, {"message": "idle"}),
    )
    monkeypatch.setattr(
        MODULE,
        "_render_cycle_summary",
        lambda *_args, **_kwargs: {
            "schema_version": "1.0",
            "cycle_number": 1,
            "project_done": True,
            "insurmountable_blocker": False,
            "termination": {},
            "stop_reason": "",
            "task_counts": {"pending": 0, "in_progress": 0, "done": 0, "blocked": 0},
            "dispatch_counts": {"attempted": 0, "launched": 0, "launch_failed": 0, "unknown": 0},
            "manager_statuses": {},
            "notes": "",
        },
    )

    out = MODULE.run_op_simple_build(make_req(tmp_path, max_build_cycles=5, dry_run=True))

    assert out["ok"] is True
    assert out["data"]["stop_reason"] == "project_done"


def test_run_persists_watchdog_terminal_stop_reason_to_cycle_summary(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)

    def fake_invoke_manager(cfg, *, manager_name, cycle_number, context, expected_artifacts):
        if manager_name == "BOSS":
            write_boss_artifacts(cfg.repo_root, cycle_number)
            return MODULE.ManagerResult(
                manager="BOSS",
                status="ok",
                timeout=False,
                returncode=0,
                started_at="2026-01-01T00:00:00Z",
                finished_at="2026-01-01T00:00:01Z",
                duration_seconds=1.0,
                message="ok",
            )
        if manager_name == "wrapup-manager":
            MODULE._atomic_write_json(
                cfg.repo_root / MODULE.ARTIFACT_FILES["wrapup_manager_report"],
                {
                    "schema_version": "1.0",
                    "updated_at": "2026-01-01T00:00:00Z",
                    "cycle_number": cycle_number,
                    "status": "ok",
                    "stop_reason": "stale_base_branch_commit",
                    "summary": "watchdog wrapup",
                },
            )
            return MODULE.ManagerResult(
                manager="wrapup-manager",
                status="ok",
                timeout=False,
                returncode=0,
                started_at="2026-01-01T00:00:00Z",
                finished_at="2026-01-01T00:00:01Z",
                duration_seconds=1.0,
            )
        raise AssertionError(f"unexpected manager call: {manager_name}")

    monkeypatch.setattr(MODULE, "_invoke_manager", fake_invoke_manager)
    monkeypatch.setattr(
        MODULE,
        "_watchdog_tick",
        lambda _cfg, _cycle, *, force_reset_target=False: (
            True,
            {
                "reason_code": "stale_base_branch_commit",
                "message": "stale branch",
                "watchdog_age_minutes": 151.0,
            },
        ),
    )
    monkeypatch.setattr(MODULE, "_run_rate_gate_wait", lambda _cfg, _cycle, _warnings: None)
    dispatch_calls = {"count": 0}

    def fake_dispatch(_cfg, _cycle):
        dispatch_calls["count"] += 1
        return {"attempted": 0, "launched": 0, "launch_failed": 0, "unknown": 0}

    monkeypatch.setattr(MODULE, "_dispatch_packets", fake_dispatch)
    monkeypatch.setattr(
        MODULE,
        "_ensure_workstation_prep",
        lambda _cfg, initialize_state=None, force_refresh=False: {
            "schema_version": "1.0",
            "worktrees_parent": str((tmp_path / "forest").resolve()),
            "workstations": [],
        },
    )

    out = MODULE.run_op_simple_build(
        make_req(
            tmp_path,
            dry_run=False,
            max_build_cycles=5,
            sleep_minutes=0,
            ground_sync_enabled=False,
            worktrees_parent=str(tmp_path / "forest"),
        )
    )

    assert out["ok"] is True
    assert out["data"]["stop_reason"] == "stale_base_branch_commit"

    summary_payload = json.loads((tmp_path / MODULE.ARTIFACT_FILES["cycle_summary"]).read_text(encoding="utf-8"))
    assert summary_payload["stop_reason"] == "stale_base_branch_commit"
    assert (summary_payload.get("termination") or {}).get("reason_code") == "stale_base_branch_commit"

    capsule_payload = json.loads((tmp_path / MODULE.ARTIFACT_FILES["terminal_capsule"]).read_text(encoding="utf-8"))
    assert capsule_payload["stop_reason"] == "stale_base_branch_commit"
    assert capsule_payload["reason_code"] == "stale_base_branch_commit"
    assert dispatch_calls["count"] == 0


def test_run_near_stale_enters_merge_recovery_and_reserves_two_dispatch_slots(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)

    def fake_invoke_manager(cfg, *, manager_name, cycle_number, context, expected_artifacts):
        if manager_name == "BOSS":
            write_boss_artifacts(cfg.repo_root, cycle_number)
            return MODULE.ManagerResult(
                manager="BOSS",
                status="ok",
                timeout=False,
                returncode=0,
                started_at="2026-01-01T00:00:00Z",
                finished_at="2026-01-01T00:00:01Z",
                duration_seconds=1.0,
                message="ok",
            )
        raise AssertionError(f"unexpected manager call: {manager_name}")

    monkeypatch.setattr(MODULE, "_invoke_manager", fake_invoke_manager)
    monkeypatch.setattr(
        MODULE,
        "_watchdog_tick",
        lambda _cfg, _cycle, *, force_reset_target=False: (
            False,
            {
                "reason_code": "watchdog_near_stale",
                "message": "near stale",
                "watchdog_age_minutes": 142.0,
                "near_stale": True,
            },
        ),
    )
    monkeypatch.setattr(MODULE, "_run_rate_gate_wait", lambda _cfg, _cycle, _warnings: None)
    monkeypatch.setattr(
        MODULE,
        "_ensure_workstation_prep",
        lambda _cfg, initialize_state=None, force_refresh=False: {
            "schema_version": "1.0",
            "worktrees_parent": str((tmp_path / "forest").resolve()),
            "workstations": [],
        },
    )
    captured = {"reserved_slots": None}

    def fake_dispatch(_cfg, _cycle, *, reserved_slots=0):
        captured["reserved_slots"] = reserved_slots
        return {"attempted": 0, "launched": 0, "launch_failed": 0, "unknown": 0}

    monkeypatch.setattr(MODULE, "_dispatch_packets", fake_dispatch)

    out = MODULE.run_op_simple_build(
        make_req(
            tmp_path,
            dry_run=False,
            max_build_cycles=1,
            sleep_minutes=0,
            ground_sync_enabled=False,
            worktrees_parent=str(tmp_path / "forest"),
        )
    )

    assert out["ok"] is True
    assert captured["reserved_slots"] == MODULE.MERGE_RECOVERY_RESERVED_SLOTS
    summary_payload = json.loads((tmp_path / MODULE.ARTIFACT_FILES["cycle_summary"]).read_text(encoding="utf-8"))
    assert summary_payload["cycle_mode"] == "merge_recovery"


def test_run_ignores_unrecognized_summary_stop_reason(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)

    monkeypatch.setattr(
        MODULE,
        "_watchdog_tick",
        lambda _cfg, _cycle, *, force_reset_target=False: (False, {"message": ""}),
    )
    monkeypatch.setattr(
        MODULE,
        "_render_cycle_summary",
        lambda *_args, **_kwargs: {
            "schema_version": "1.0",
            "cycle_number": 1,
            "project_done": False,
            "insurmountable_blocker": False,
            "termination": {"reason_code": "proceed_with_partial_reconciliation_and_single_safe_dispatch"},
            "stop_reason": "proceed_with_partial_reconciliation_and_single_safe_dispatch",
            "task_counts": {"pending": 1, "in_progress": 1, "done": 0, "blocked": 0},
            "dispatch_counts": {"attempted": 1, "launched": 1, "launch_failed": 0, "unknown": 0},
            "manager_statuses": {},
            "notes": "",
        },
    )

    out = MODULE.run_op_simple_build(make_req(tmp_path, max_build_cycles=1, dry_run=True))

    assert out["ok"] is True
    assert out["data"]["stop_reason"] is None
    assert out["summary"] == "Reached max_build_cycles=1."


def test_run_invokes_wrapup_manager_once_on_project_done(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    calls: list[str] = []

    def fake_invoke_manager(*_args, **kwargs):
        calls.append(str(kwargs.get("manager_name") or ""))
        manager = str(kwargs.get("manager_name") or "")
        return MODULE.ManagerResult(
            manager=manager,
            status="ok",
            timeout=False,
            returncode=0,
            started_at="2026-01-01T00:00:00Z",
            finished_at="2026-01-01T00:00:01Z",
            duration_seconds=1.0,
        )

    monkeypatch.setattr(MODULE, "_invoke_manager", fake_invoke_manager)
    monkeypatch.setattr(
        MODULE,
        "_render_cycle_summary",
        lambda *_args, **_kwargs: {
            "schema_version": "1.0",
            "cycle_number": 1,
            "project_done": True,
            "insurmountable_blocker": False,
            "termination": {},
            "stop_reason": "",
            "task_counts": {"pending": 0, "in_progress": 0, "done": 0, "blocked": 0},
            "dispatch_counts": {"attempted": 0, "launched": 0, "launch_failed": 0, "unknown": 0},
            "manager_statuses": {},
            "notes": "",
        },
    )

    out = MODULE.run_op_simple_build(make_req(tmp_path, max_build_cycles=1, dry_run=True, sleep_minutes=0))

    assert out["ok"] is True
    assert calls.count("BOSS") == 1
    assert calls.count("wrapup-manager") == 1
    trace_rows = [
        json.loads(line)
        for line in (tmp_path / MODULE.TRACE_EVENT_LOG_FILE).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    event_names = {str(row.get("event_name") or "") for row in trace_rows}
    assert "runtime.manager.cycle_decision" in event_names
    assert "runtime.dispatch.launch_cycle" in event_names
    assert "merge.lifecycle.wrapup_manager" in event_names
    trace_event = next(row for row in trace_rows if row.get("event_name") == "merge.lifecycle.wrapup_manager")
    assert trace_event["schema_version"] == "trace-event-envelope.v1"
    assert trace_event["identity"]["project_id"].startswith("prj.")
    assert trace_event["identity"]["run_id"].startswith("run.")
    assert trace_event["identity"]["event_id"].startswith("event.")
    assert trace_event["source"]["repo"] == tmp_path.name
    for row in trace_rows:
        validation_errors = MODULE._validate_trace_event_envelope_v1(row)
        assert validation_errors == []


def test_run_invokes_wrapup_manager_on_watchdog_terminal_stop(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    calls: list[str] = []

    def fake_invoke_manager(*_args, **kwargs):
        manager = str(kwargs.get("manager_name") or "")
        calls.append(manager)
        return MODULE.ManagerResult(
            manager=manager,
            status="ok",
            timeout=False,
            returncode=0,
            started_at="2026-01-01T00:00:00Z",
            finished_at="2026-01-01T00:00:01Z",
            duration_seconds=1.0,
        )

    monkeypatch.setattr(MODULE, "_invoke_manager", fake_invoke_manager)
    monkeypatch.setattr(
        MODULE,
        "_watchdog_tick",
        lambda _cfg, _cycle, *, force_reset_target=False: (
            True,
            {"reason_code": "stale_base_branch_commit", "message": "watchdog stale"},
        ),
    )
    monkeypatch.setattr(
        MODULE,
        "_render_cycle_summary",
        lambda *_args, **_kwargs: {
            "schema_version": "1.0",
            "cycle_number": 1,
            "project_done": False,
            "insurmountable_blocker": False,
            "termination": {},
            "stop_reason": "",
            "task_counts": {"pending": 0, "in_progress": 0, "done": 0, "blocked": 0},
            "dispatch_counts": {"attempted": 0, "launched": 0, "launch_failed": 0, "unknown": 0},
            "manager_statuses": {},
            "notes": "",
        },
    )

    out = MODULE.run_op_simple_build(
        make_req(
            tmp_path,
            max_build_cycles=1,
            dry_run=True,
            sleep_minutes=0,
            ground_sync_enabled=False,
        )
    )

    assert out["ok"] is True
    assert out["data"]["stop_reason"] == "stale_base_branch_commit"
    assert calls.count("BOSS") == 1
    assert calls.count("wrapup-manager") == 1


def test_emit_trace_event_envelope_rejects_invalid_payload(tmp_path: Path) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=True,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)

    bad_payload = {
        "schema_version": "trace-event-envelope.v1",
        "event_name": "x",
        "timestamp_utc": "bad-time",
        "identity": {
            "project_id": "project.bad",
            "run_id": "run.bad",
            "event_id": "event.bad",
        },
        "actor": {"type": "service", "id": "wrapup-manager"},
        "decision": {"question": "short", "rationale": "short", "reason_codes": []},
        "operation": {"name": "x", "intent": "x"},
        "outcome": {"status": "unknown", "summary": "x"},
        "risk": {"level": "none"},
        "evidence": {"artifacts": []},
        "source": {"repo": "repo"},
    }

    try:
        MODULE._emit_trace_event_envelope(cfg, cycle_number=1, payload=bad_payload)
    except MODULE.SimpleBuildError as exc:
        assert exc.code == "trace_event_envelope_invalid"
    else:  # pragma: no cover - defensive
        raise AssertionError("expected trace_event_envelope_invalid error")


def test_run_emits_cycle_trace_events_for_manager_and_dispatch(tmp_path: Path) -> None:
    build_repo(tmp_path)

    out = MODULE.run_op_simple_build(
        make_req(
            tmp_path,
            max_build_cycles=1,
            dry_run=True,
            sleep_minutes=0,
            ground_sync_enabled=False,
        )
    )

    assert out["ok"] is True
    trace_path = tmp_path / MODULE.TRACE_EVENT_LOG_FILE
    trace_rows = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    event_names = {str(row.get("event_name") or "") for row in trace_rows}
    assert "runtime.manager.cycle_decision" in event_names
    assert "runtime.dispatch.launch_cycle" in event_names
    manager_event = next(row for row in trace_rows if row.get("event_name") == "runtime.manager.cycle_decision")
    dispatch_event = next(row for row in trace_rows if row.get("event_name") == "runtime.dispatch.launch_cycle")
    manager_llm = (((manager_event.get("operation") or {}).get("inputs") or {}).get("llm") or {})
    assert manager_llm.get("role") == "manager"
    assert manager_llm.get("provider") in {"codex", "openrouter", "blackbox"}
    assert manager_llm.get("checker_result") == "not_applicable"
    assert manager_llm.get("hardening_telemetry_state") == "missing"
    assert manager_llm.get("override_applied") is False
    dispatch_inputs = ((dispatch_event.get("operation") or {}).get("inputs") or {})
    dispatch_routing = dispatch_inputs.get("routing") or {}
    assert isinstance(dispatch_routing.get("provider_stats"), dict)
    assert isinstance(dispatch_routing.get("model_stats"), dict)
    assert isinstance(dispatch_routing.get("profile_stats"), dict)
    for row in trace_rows:
        assert MODULE._validate_trace_event_envelope_v1(row) == []


def test_run_wrapup_trace_includes_llm_hardening_from_report(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)

    def fake_write_wrapup_stub(cfg, cycle_number: int):
        MODULE._atomic_write_json(
            cfg.repo_root / MODULE.ARTIFACT_FILES["wrapup_manager_report"],
            {
                "schema_version": "1.0",
                "updated_at": "2026-01-01T00:00:00Z",
                "cycle_number": cycle_number,
                "status": "dry_run",
                "stop_reason": "project_done",
                "run_base_branch": "main",
                "summary": "wrapup complete",
                "llm_hardening": {
                    "mini_jobs": 2,
                    "prompt_complexity_score": 28,
                    "checker_result": "pass",
                    "checker_id": "scripts/check_wrapup.py",
                    "override_applied": False,
                },
            },
        )

    monkeypatch.setattr(MODULE, "_write_wrapup_stub", fake_write_wrapup_stub)
    monkeypatch.setattr(
        MODULE,
        "_render_cycle_summary",
        lambda *_args, **_kwargs: {
            "schema_version": "1.0",
            "cycle_number": 1,
            "project_done": True,
            "insurmountable_blocker": False,
            "termination": {},
            "stop_reason": "",
            "task_counts": {"pending": 0, "in_progress": 0, "done": 0, "blocked": 0},
            "dispatch_counts": {"attempted": 0, "launched": 0, "launch_failed": 0, "unknown": 0},
            "manager_statuses": {},
            "notes": "",
        },
    )

    out = MODULE.run_op_simple_build(make_req(tmp_path, max_build_cycles=1, dry_run=True, sleep_minutes=0))

    assert out["ok"] is True
    trace_rows = [
        json.loads(line)
        for line in (tmp_path / MODULE.TRACE_EVENT_LOG_FILE).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    wrapup_event = next(row for row in trace_rows if row.get("event_name") == "merge.lifecycle.wrapup_manager")
    wrapup_llm = (((wrapup_event.get("operation") or {}).get("inputs") or {}).get("llm") or {})
    assert wrapup_llm.get("checker_result") == "pass"
    assert wrapup_llm.get("override_applied") is False
    assert wrapup_llm.get("mini_jobs") == 2
    assert wrapup_llm.get("prompt_complexity_score") == 28
    assert wrapup_llm.get("hardening_telemetry_state") == "present"
    assert wrapup_llm.get("hardening_telemetry_source") == "wrapup_manager_report"


def test_emit_cycle_trace_events_emits_additional_manager_invocation_for_non_boss(tmp_path: Path) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=True,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._ensure_default_artifacts(cfg)
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["cycle_manager_decision"],
        {
            "schema_version": "1.0",
            "cycle_number": 1,
            "decision": "proceed",
            "reason_code": "registry_ready",
            "message": "cycle proceeds",
            "worker_registry_ready": True,
        },
    )
    MODULE._append_manager_log(
        cfg,
        {
            "schema_version": "1.0",
            "cycle_number": 1,
            "manager": "BOSS",
            "status": "ok",
            "timeout": False,
            "returncode": 0,
            "started_at": "2026-01-01T00:00:00Z",
            "finished_at": "2026-01-01T00:00:01Z",
            "duration_seconds": 1.0,
            "executor_provider": "codex",
            "executor_model": "gpt-5.3-codex",
            "profile_alias": "codex",
            "reasoning_effort": "xhigh",
            "tooling_effort": "medium_tooling",
        },
    )
    MODULE._append_manager_log(
        cfg,
        {
            "schema_version": "1.0",
            "cycle_number": 1,
            "manager": "planner-audit",
            "status": "ok",
            "timeout": False,
            "returncode": 0,
            "started_at": "2026-01-01T00:00:01Z",
            "finished_at": "2026-01-01T00:00:02Z",
            "duration_seconds": 1.0,
            "executor_provider": "codex",
            "executor_model": "gpt-5.3-codex",
            "profile_alias": "codex",
            "reasoning_effort": "high_effort",
            "tooling_effort": "medium_tooling",
            "mini_jobs": 3,
            "prompt_complexity_score": 44,
            "checker_result": "pass",
            "override_applied": False,
        },
    )

    trace_errors = MODULE._emit_cycle_trace_events(
        cfg,
        cycle_number=1,
        dispatch_counts={"attempted": 0, "launched": 0, "launch_failed": 0, "unknown": 0},
    )
    assert trace_errors == []
    rows = [
        json.loads(line)
        for line in (tmp_path / MODULE.TRACE_EVENT_LOG_FILE).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    extra = [
        row
        for row in rows
        if row.get("event_name") == "runtime.manager.invocation"
        and (row.get("actor") or {}).get("id") == "planner-audit"
    ]
    assert extra
    llm = (((extra[0].get("operation") or {}).get("inputs") or {}).get("llm") or {})
    assert llm.get("mini_jobs") == 3
    assert llm.get("prompt_complexity_score") == 44
    assert llm.get("checker_result") == "pass"


def test_run_ground_sync_triggers_cadence_and_terminal(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    sync_calls: list[tuple[int, str]] = []

    def fake_run_ground_sync(_cfg, *, cycle_number: int, trigger: str):
        sync_calls.append((int(cycle_number), str(trigger)))
        return "ok", f"trigger={trigger}"

    monkeypatch.setattr(MODULE, "_run_ground_sync", fake_run_ground_sync)

    out = MODULE.run_op_simple_build(
        make_req(
            tmp_path,
            max_build_cycles=3,
            dry_run=True,
            sleep_minutes=0,
            ground_sync_every_n_cycles=2,
        )
    )

    assert out["ok"] is True
    assert (2, "cadence") in sync_calls
    assert sync_calls[-1] == (3, "terminal")


def test_run_ground_sync_passes_checkpoint_and_lock_timeout(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE._build_config(
        make_req(
            tmp_path,
            dry_run=False,
            ground_sync_timeout_seconds=47,
        )
    )

    trace_path = tmp_path / MODULE.TRACE_EVENT_LOG_FILE
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.write_text("{\"ok\":true}\n", encoding="utf-8")

    earth_root = tmp_path / "Earth"
    script_path = earth_root / "ground-control-hub" / "scripts" / "ground_ingestion_normalize.py"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text("#!/usr/bin/env python3\n", encoding="utf-8")

    snapshot_path = earth_root / "reports" / "ground-ingest-inputs" / "prj.tetris" / "trace_event_envelope.jsonl"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text("{\"ok\":true}\n", encoding="utf-8")

    monkeypatch.setattr(MODULE, "_discover_earth_root", lambda _repo_root: earth_root)
    monkeypatch.setattr(MODULE, "_trace_identity_context", lambda _cfg, _cycle: {"project_id": "prj.tetris"})
    monkeypatch.setattr(
        MODULE,
        "_sync_trace_snapshot_to_ground_inbox",
        lambda _cfg, *, earth_root, project_id: snapshot_path,
    )
    monkeypatch.setattr(MODULE, "_collect_ground_ingest_inputs", lambda _earth_root: [snapshot_path])

    captured: dict[str, object] = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(MODULE.subprocess, "run", fake_run)

    status, message = MODULE._run_ground_sync(cfg, cycle_number=9, trigger="cadence")

    assert status == "ok"
    assert "ground sync completed" in message
    cmd = list(captured["cmd"])
    assert "--checkpoint-state" in cmd
    assert "--lock-timeout-seconds" in cmd

    checkpoint_idx = cmd.index("--checkpoint-state")
    lock_timeout_idx = cmd.index("--lock-timeout-seconds")
    assert cmd[checkpoint_idx + 1].endswith("ground-control-hub/artifacts/ground_ingestion_checkpoint.v1.json")
    assert cmd[lock_timeout_idx + 1] == "47"


def test_run_does_not_invoke_wrapup_manager_for_non_project_done_terminal_reason(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    calls: list[str] = []

    def fake_invoke_manager(*_args, **kwargs):
        calls.append(str(kwargs.get("manager_name") or ""))
        manager = str(kwargs.get("manager_name") or "")
        return MODULE.ManagerResult(
            manager=manager,
            status="ok",
            timeout=False,
            returncode=0,
            started_at="2026-01-01T00:00:00Z",
            finished_at="2026-01-01T00:00:01Z",
            duration_seconds=1.0,
        )

    monkeypatch.setattr(MODULE, "_invoke_manager", fake_invoke_manager)
    monkeypatch.setattr(
        MODULE,
        "_render_cycle_summary",
        lambda *_args, **_kwargs: {
            "schema_version": "1.0",
            "cycle_number": 1,
            "project_done": False,
            "insurmountable_blocker": True,
            "termination": {"reason_code": "insurmountable_blocker"},
            "stop_reason": "insurmountable_blocker",
            "task_counts": {"pending": 0, "in_progress": 0, "done": 0, "blocked": 0},
            "dispatch_counts": {"attempted": 0, "launched": 0, "launch_failed": 0, "unknown": 0},
            "manager_statuses": {},
            "notes": "",
        },
    )

    out = MODULE.run_op_simple_build(make_req(tmp_path, max_build_cycles=1, dry_run=True, sleep_minutes=0))

    assert out["ok"] is True
    assert calls.count("BOSS") == 1
    assert "wrapup-manager" not in calls


def test_run_project_done_soft_gates_wrapup_failure(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)

    def fake_invoke_manager(*_args, **kwargs):
        manager = str(kwargs.get("manager_name") or "")
        if manager == "wrapup-manager":
            return MODULE.ManagerResult(
                manager=manager,
                status="failed",
                timeout=False,
                returncode=1,
                started_at="2026-01-01T00:00:01Z",
                finished_at="2026-01-01T00:00:02Z",
                duration_seconds=1.0,
                message="codex exec returned non-zero",
                reason_code="manager_non_zero_exit",
            )
        return MODULE.ManagerResult(
            manager=manager,
            status="ok",
            timeout=False,
            returncode=0,
            started_at="2026-01-01T00:00:00Z",
            finished_at="2026-01-01T00:00:01Z",
            duration_seconds=1.0,
        )

    monkeypatch.setattr(MODULE, "_invoke_manager", fake_invoke_manager)
    monkeypatch.setattr(
        MODULE,
        "_render_cycle_summary",
        lambda *_args, **_kwargs: {
            "schema_version": "1.0",
            "cycle_number": 1,
            "project_done": True,
            "insurmountable_blocker": False,
            "termination": {},
            "stop_reason": "",
            "task_counts": {"pending": 0, "in_progress": 0, "done": 0, "blocked": 0},
            "dispatch_counts": {"attempted": 0, "launched": 0, "launch_failed": 0, "unknown": 0},
            "manager_statuses": {},
            "notes": "",
        },
    )

    out = MODULE.run_op_simple_build(make_req(tmp_path, max_build_cycles=1, dry_run=True, sleep_minutes=0))

    assert out["ok"] is True
    assert out["data"]["stop_reason"] == "project_done"
    assert any(item.get("code") == "manager_non_zero_exit" for item in out.get("warnings", []))


def test_invoke_manager_wrapup_dry_run_writes_report(tmp_path: Path) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=True,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)

    out = MODULE._invoke_manager(
        cfg,
        manager_name="wrapup-manager",
        cycle_number=3,
        context={},
        expected_artifacts=["wrapup_manager_report"],
    )

    assert out.status == "ok"
    report = MODULE._read_json(tmp_path / MODULE.ARTIFACT_FILES["wrapup_manager_report"], default={})
    assert report.get("cycle_number") == 3
    assert report.get("status") == "dry_run"


def test_invoke_manager_dry_run_logs_executor_metadata(tmp_path: Path) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=True,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)

    out = MODULE._invoke_manager(
        cfg,
        manager_name="BOSS",
        cycle_number=1,
        context={},
        expected_artifacts=[],
    )

    assert out.status == "ok"
    rows = [
        json.loads(line)
        for line in (tmp_path / MODULE.MANAGER_CALL_LOG_FILE).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows
    latest = rows[-1]
    assert latest["executor_provider"] == "codex"
    assert latest["executor_model"] == "gpt-5.3-codex"
    assert latest["reasoning_effort"] == "xhigh"
    assert latest["tooling_effort"] == "medium_tooling"
    assert latest["checker_result"] == "not_applicable"
    assert latest["override_applied"] is False
    assert latest["llm_hardening_state"] == "missing"
    assert latest.get("llm_hardening_source") is None
    llm_meta = MODULE._manager_llm_metadata(cfg, manager_name="BOSS", log_row=latest)
    assert llm_meta.get("hardening_telemetry_state") == "missing"
    assert llm_meta.get("checker_result") == "not_applicable"


def test_invoke_manager_extracts_llm_hardening_from_cycle_manager_decision(tmp_path: Path) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=True,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["cycle_manager_decision"],
        {
            "schema_version": "1.0",
            "cycle_number": 1,
            "decision": "proceed",
            "reason_code": "registry_ready",
            "message": "manager decision with telemetry",
            "worker_registry_ready": True,
            "llm_hardening": {
                "mini_jobs": 4,
                "prompt_complexity_score": 61,
                "checker_result": "fail",
                "checker_id": "scripts/check_cycle.py",
                "override_applied": True,
                "override_reason_code": "checker_false_negative",
                "override_explanation": "checker guardrail did not match current runtime packet shape",
                "override_evidence_refs": ["reports/op/checks/cycle-1.json"],
                "risk_level": "medium",
                "fallback_or_followup_action": "re-run checker on normalized packet next cycle",
            },
        },
    )

    out = MODULE._invoke_manager(
        cfg,
        manager_name="BOSS",
        cycle_number=1,
        context={},
        expected_artifacts=[],
    )

    assert out.status == "ok"
    rows = [
        json.loads(line)
        for line in (tmp_path / MODULE.MANAGER_CALL_LOG_FILE).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    latest = rows[-1]
    assert latest["mini_jobs"] == 4
    assert latest["prompt_complexity_score"] == 61
    assert latest["checker_result"] == "fail"
    assert latest["checker_id"] == "scripts/check_cycle.py"
    assert latest["override_applied"] is True
    assert latest["override_reason_code"] == "checker_false_negative"
    assert latest["risk_level"] == "medium"
    assert latest["llm_hardening_state"] == "present"
    assert latest["llm_hardening_source"] == "cycle_manager_decision"
    llm_meta = MODULE._manager_llm_metadata(cfg, manager_name="BOSS", log_row=latest)
    assert llm_meta["mini_jobs"] == 4
    assert llm_meta["prompt_complexity_score"] == 61
    assert llm_meta["checker_result"] == "fail"
    assert llm_meta["override_applied"] is True
    assert llm_meta["override_reason_code"] == "checker_false_negative"
    assert llm_meta["hardening_telemetry_state"] == "present"
    assert llm_meta["hardening_telemetry_source"] == "cycle_manager_decision"


def test_invoke_manager_distinguishes_missing_vs_explicit_not_applicable_hardening(tmp_path: Path) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=True,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["cycle_manager_decision"],
        {
            "schema_version": "1.0",
            "cycle_number": 1,
            "decision": "proceed",
            "reason_code": "registry_ready",
            "message": "explicit not_applicable telemetry",
            "worker_registry_ready": True,
            "llm_hardening": {
                "checker_result": "not_applicable",
                "override_applied": False,
            },
        },
    )

    out = MODULE._invoke_manager(
        cfg,
        manager_name="BOSS",
        cycle_number=1,
        context={},
        expected_artifacts=[],
    )
    assert out.status == "ok"
    rows = [
        json.loads(line)
        for line in (tmp_path / MODULE.MANAGER_CALL_LOG_FILE).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    latest = rows[-1]
    assert latest["checker_result"] == "not_applicable"
    assert latest["llm_hardening_state"] == "present"
    assert latest["llm_hardening_source"] == "cycle_manager_decision"
    llm_meta = MODULE._manager_llm_metadata(cfg, manager_name="BOSS", log_row=latest)
    assert llm_meta["checker_result"] == "not_applicable"
    assert llm_meta["hardening_telemetry_state"] == "present"


def test_run_persists_summary_manager_status_entry(tmp_path: Path) -> None:
    build_repo(tmp_path)

    out = MODULE.run_op_simple_build(make_req(tmp_path, dry_run=True, max_build_cycles=1, sleep_minutes=0))

    assert out["ok"] is True
    summary = json.loads((tmp_path / MODULE.ARTIFACT_FILES["cycle_summary"]).read_text(encoding="utf-8"))
    assert summary["manager_statuses"]["summary"]["status"] == "ok"


def test_max_build_cycles_applies_to_current_run_not_global_counter(tmp_path: Path) -> None:
    build_repo(tmp_path)
    (tmp_path / ".op-simple" / "current").mkdir(parents=True, exist_ok=True)
    MODULE._atomic_write_json(
        tmp_path / MODULE.CYCLE_COUNTER_FILE,
        {"schema_version": "1.0", "cycle_number": 10, "updated_at": "2026-01-01T00:00:00Z"},
    )

    out = MODULE.run_op_simple_build(make_req(tmp_path, max_build_cycles=1, dry_run=True, sleep_minutes=0))

    assert out["ok"] is True
    assert out["data"]["cycles_this_run"] == 1
    assert out["data"]["cycle_number"] == 11


def test_profile_rows_from_disk_excludes_default_when_multiple_profiles(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    default_profile = tmp_path / ".codex"
    secondary_profile = tmp_path / ".codex-second"
    default_profile.mkdir(parents=True, exist_ok=True)
    secondary_profile.mkdir(parents=True, exist_ok=True)
    (default_profile / "auth.json").write_text("{}", encoding="utf-8")
    (secondary_profile / "auth.json").write_text("{}", encoding="utf-8")

    rows = MODULE._profile_rows_from_disk()
    aliases = {str(row.get("alias")) for row in rows if isinstance(row, dict)}

    assert "codex" not in aliases
    assert "codex-second" in aliases


def test_profile_rows_from_disk_keeps_default_when_single_profile(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    default_profile = tmp_path / ".codex"
    default_profile.mkdir(parents=True, exist_ok=True)
    (default_profile / "auth.json").write_text("{}", encoding="utf-8")

    rows = MODULE._profile_rows_from_disk()
    aliases = [str(row.get("alias")) for row in rows if isinstance(row, dict)]

    assert aliases == ["codex"]


def test_profile_rows_from_disk_filters_to_selected_aliases(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    for name in (".codex-six", ".codex-seven", ".codex-eight"):
        profile = tmp_path / name
        profile.mkdir(parents=True, exist_ok=True)
        (profile / "auth.json").write_text("{}", encoding="utf-8")

    rows = MODULE._profile_rows_from_disk(selected_aliases=["codex-seven", "codex-six"])
    aliases = [str(row.get("alias")) for row in rows if isinstance(row, dict)]

    assert aliases == ["codex-seven", "codex-six"]


def test_rate_snapshot_profile_args_respects_selected_aliases_filter(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    for name in (".codex-six", ".codex-seven", ".codex-eight"):
        profile = tmp_path / name
        profile.mkdir(parents=True, exist_ok=True)
        (profile / "auth.json").write_text("{}", encoding="utf-8")
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=True,
        selected_aliases=["six", "seven", "ten"],
    )

    args, missing = MODULE._rate_snapshot_profile_args(cfg)

    assert args == [f"codex-six={(tmp_path / '.codex-six').resolve()}", f"codex-seven={(tmp_path / '.codex-seven').resolve()}"]
    assert missing == ["ten"]


def test_profile_rows_from_disk_selected_aliases_accepts_full_or_short_alias(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    for name in (".codex-six", ".codex-seven"):
        profile = tmp_path / name
        profile.mkdir(parents=True, exist_ok=True)
        (profile / "auth.json").write_text("{}", encoding="utf-8")

    short_rows = MODULE._profile_rows_from_disk(selected_aliases=["six"])
    full_rows = MODULE._profile_rows_from_disk(selected_aliases=["codex-six"])

    short_aliases = [str(row.get("alias")) for row in short_rows if isinstance(row, dict)]
    full_aliases = [str(row.get("alias")) for row in full_rows if isinstance(row, dict)]

    assert short_aliases == ["codex-six"]
    assert full_aliases == ["codex-six"]


def test_rate_snapshot_profile_args_autodiscovers_when_selected_aliases_not_set(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    default_profile = tmp_path / ".codex"
    secondary_profile = tmp_path / ".codex-second"
    default_profile.mkdir(parents=True, exist_ok=True)
    secondary_profile.mkdir(parents=True, exist_ok=True)
    (default_profile / "auth.json").write_text("{}", encoding="utf-8")
    (secondary_profile / "auth.json").write_text("{}", encoding="utf-8")
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=True,
        selected_aliases=None,
    )

    args, missing = MODULE._rate_snapshot_profile_args(cfg)

    assert args == [f"codex-second={(tmp_path / '.codex-second').resolve()}"]
    assert missing == []


def test_rate_snapshot_profile_args_defaults_to_codex_when_no_profiles_discovered(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=True,
        selected_aliases=None,
    )

    args, missing = MODULE._rate_snapshot_profile_args(cfg)

    assert args == ["codex=default"]
    assert missing == []


def test_bootstrap_profile_snapshot_before_first_boss_seeds_from_discovery(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    for name in (".codex", ".codex-second"):
        profile = tmp_path / name
        profile.mkdir(parents=True, exist_ok=True)
        (profile / "auth.json").write_text("{}", encoding="utf-8")

    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=True,
        selected_aliases=None,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)

    ok, message = MODULE._bootstrap_profile_snapshot_before_first_boss(cfg, cycle_number=0)

    assert ok is True
    assert "filesystem discovery" in message
    payload = json.loads((tmp_path / MODULE.ARTIFACT_FILES["profile_snapshot"]).read_text(encoding="utf-8"))
    aliases = [str(row.get("alias")) for row in payload.get("profiles", []) if isinstance(row, dict)]
    assert aliases == ["codex-second"]


def test_run_bootstraps_profile_snapshot_before_first_boss(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    events: list[str] = []

    def fake_bootstrap(_cfg, *, cycle_number: int):
        events.append(f"bootstrap:{cycle_number}")
        return True, "bootstrap ok"

    def fake_invoke_manager(*_args, **kwargs):
        manager = str(kwargs.get("manager_name") or "")
        if manager == "BOSS":
            events.append("boss")
        return MODULE.ManagerResult(
            manager=manager,
            status="ok",
            timeout=False,
            returncode=0,
            started_at="2026-01-01T00:00:00Z",
            finished_at="2026-01-01T00:00:01Z",
            duration_seconds=1.0,
        )

    monkeypatch.setattr(MODULE, "_bootstrap_profile_snapshot_before_first_boss", fake_bootstrap)
    monkeypatch.setattr(MODULE, "_invoke_manager", fake_invoke_manager)

    out = MODULE.run_op_simple_build(make_req(tmp_path, max_build_cycles=1, dry_run=True, sleep_minutes=0))

    assert out["ok"] is True
    assert events and events[0] == "bootstrap:0"
    assert "boss" in events


def test_select_boss_profile_from_snapshot_prefers_highest_weekly_not_5h_gated(tmp_path: Path) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["profile_snapshot"],
        {
            "schema_version": "1.0",
            "profiles": [
                {
                    "alias": "codex-first",
                    "codex_home": "/tmp/codex-first",
                    "window_5h_remaining_pct": 0.5,
                    "window_week_remaining_pct": 99.0,
                },
                {
                    "alias": "codex-second",
                    "codex_home": "/tmp/codex-second",
                    "window_5h_remaining_pct": 70.0,
                    "window_week_remaining_pct": 65.0,
                },
                {
                    "alias": "codex-third",
                    "codex_home": "/tmp/codex-third",
                    "window_5h_remaining_pct": 60.0,
                    "window_week_remaining_pct": 75.0,
                },
            ],
        },
    )

    alias, home = MODULE._select_boss_profile_from_snapshot(cfg)

    assert alias == "codex-third"
    assert home == "/tmp/codex-third"


def test_select_boss_profile_from_snapshot_keeps_preferred_alias_when_weekly_over_50(tmp_path: Path) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["profile_snapshot"],
        {
            "schema_version": "1.0",
            "profiles": [
                {
                    "alias": "codex-preferred",
                    "codex_home": "/tmp/codex-preferred",
                    "window_5h_remaining_pct": 70.0,
                    "window_week_remaining_pct": 55.0,
                },
                {
                    "alias": "codex-higher",
                    "codex_home": "/tmp/codex-higher",
                    "window_5h_remaining_pct": 80.0,
                    "window_week_remaining_pct": 95.0,
                },
            ],
        },
    )

    alias, home = MODULE._select_boss_profile_from_snapshot(cfg, preferred_alias="codex-preferred")

    assert alias == "codex-preferred"
    assert home == "/tmp/codex-preferred"


def test_select_boss_profile_from_snapshot_switches_when_preferred_weekly_below_50(tmp_path: Path) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["profile_snapshot"],
        {
            "schema_version": "1.0",
            "profiles": [
                {
                    "alias": "codex-preferred",
                    "codex_home": "/tmp/codex-preferred",
                    "window_5h_remaining_pct": 70.0,
                    "window_week_remaining_pct": 49.0,
                },
                {
                    "alias": "codex-higher",
                    "codex_home": "/tmp/codex-higher",
                    "window_5h_remaining_pct": 80.0,
                    "window_week_remaining_pct": 95.0,
                },
            ],
        },
    )

    alias, home = MODULE._select_boss_profile_from_snapshot(cfg, preferred_alias="codex-preferred")

    assert alias == "codex-higher"
    assert home == "/tmp/codex-higher"


def test_select_boss_profile_from_snapshot_includes_default_codex_when_highest_capacity(tmp_path: Path) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["profile_snapshot"],
        {
            "schema_version": "1.0",
            "profiles": [
                {
                    "alias": "codex",
                    "codex_home": "/tmp/codex",
                    "window_5h_remaining_pct": 80.0,
                    "window_week_remaining_pct": 99.0,
                    "hard_gated": False,
                },
                {
                    "alias": "codex-second",
                    "codex_home": "/tmp/codex-second",
                    "window_5h_remaining_pct": 70.0,
                    "window_week_remaining_pct": 60.0,
                    "hard_gated": False,
                },
            ],
        },
    )

    alias, home = MODULE._select_boss_profile_from_snapshot(cfg)

    assert alias == "codex"
    assert home == "/tmp/codex"


def test_select_boss_profile_from_snapshot_skips_hard_gated_profiles(tmp_path: Path) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["profile_snapshot"],
        {
            "schema_version": "1.0",
            "profiles": [
                {
                    "alias": "codex-first",
                    "codex_home": "/tmp/codex-first",
                    "window_5h_remaining_pct": 90.0,
                    "window_week_remaining_pct": 95.0,
                    "hard_gated": True,
                },
                {
                    "alias": "codex-second",
                    "codex_home": "/tmp/codex-second",
                    "window_5h_remaining_pct": 50.0,
                    "window_week_remaining_pct": 60.0,
                    "hard_gated": False,
                },
            ],
        },
    )

    alias, home = MODULE._select_boss_profile_from_snapshot(cfg)

    assert alias == "codex-second"
    assert home == "/tmp/codex-second"


def test_select_boss_profile_from_snapshot_returns_none_when_all_profiles_hard_gated(tmp_path: Path) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["profile_snapshot"],
        {
            "schema_version": "1.0",
            "profiles": [
                {
                    "alias": "codex-first",
                    "codex_home": "/tmp/codex-first",
                    "window_5h_remaining_pct": 90.0,
                    "window_week_remaining_pct": 95.0,
                    "hard_gated": True,
                },
                {
                    "alias": "codex-second",
                    "codex_home": "/tmp/codex-second",
                    "window_5h_remaining_pct": 55.0,
                    "window_week_remaining_pct": 50.0,
                    "hard_gated": True,
                },
            ],
        },
    )

    alias, home = MODULE._select_boss_profile_from_snapshot(cfg)

    assert alias is None
    assert home is None


def test_select_boss_profile_from_snapshot_falls_back_on_missing_or_malformed(tmp_path: Path) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)

    alias, home = MODULE._select_boss_profile_from_snapshot(cfg)
    assert alias is None
    assert home is None

    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["profile_snapshot"],
        {"schema_version": "1.0", "profiles": "bad"},
    )
    alias, home = MODULE._select_boss_profile_from_snapshot(cfg)
    assert alias is None
    assert home is None


def test_record_boss_timeout_state_triggers_adaptation_after_two_timeouts(tmp_path: Path) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._ensure_default_artifacts(cfg)
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["profile_snapshot"],
        {
            "schema_version": "1.0",
            "profiles": [
                {
                    "alias": "codex-old",
                    "codex_home": "/tmp/codex-old",
                    "window_5h_remaining_pct": 80.0,
                    "window_week_remaining_pct": 90.0,
                    "hard_gated": False,
                },
                {
                    "alias": "codex-new",
                    "codex_home": "/tmp/codex-new",
                    "window_5h_remaining_pct": 70.0,
                    "window_week_remaining_pct": 85.0,
                    "hard_gated": False,
                },
            ],
        },
    )
    timeout_result = MODULE.ManagerResult(
        manager="BOSS",
        status="timeout",
        timeout=True,
        returncode=None,
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:00:10Z",
        duration_seconds=10.0,
        message="timed out; manager_profile_alias=codex-old",
        reason_code="manager_timeout",
    )

    first = MODULE._record_boss_timeout_state(
        cfg,
        cycle_number=1,
        result=timeout_result,
        reason_code="manager_timeout",
    )
    second = MODULE._record_boss_timeout_state(
        cfg,
        cycle_number=2,
        result=timeout_result,
        reason_code="manager_timeout",
    )

    assert first["consecutive_boss_timeouts"] == 1
    assert first["adaptation_active"] is False
    assert first["rotation_required"] is False

    assert second["consecutive_boss_timeouts"] == 2
    assert second["adaptation_active"] is True
    assert second["rotation_required"] is True
    assert second["last_timeout_profile_alias"] == "codex-old"


def test_invoke_manager_boss_uses_selected_profile_home(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    codex_second_home = tmp_path / ".codex-second"
    codex_second_home.mkdir(parents=True, exist_ok=True)
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["profile_snapshot"],
        {
            "schema_version": "1.0",
            "profiles": [
                {
                    "alias": "codex-second",
                    "codex_home": str(codex_second_home),
                    "window_5h_remaining_pct": 80.0,
                    "window_week_remaining_pct": 90.0,
                }
            ],
        },
    )

    monkeypatch.setattr(MODULE, "_load_prompt_template", lambda *_args, **_kwargs: "prompt body")
    captured: dict[str, str | None] = {
        "codex_home": None,
        "resume_session_id": None,
        "model": None,
        "reasoning_effort": None,
    }

    def fake_codex_exec_prompt(*_args, **kwargs):
        captured["codex_home"] = kwargs.get("codex_home")
        captured["resume_session_id"] = kwargs.get("resume_session_id")
        captured["model"] = kwargs.get("model")
        captured["reasoning_effort"] = kwargs.get("reasoning_effort")
        return MODULE.ManagerResult(
            manager="BOSS",
            status="ok",
            timeout=False,
            returncode=0,
            started_at="2026-01-01T00:00:00Z",
            finished_at="2026-01-01T00:00:01Z",
            duration_seconds=1.0,
            session_id="123e4567-e89b-12d3-a456-426614174000",
        )

    monkeypatch.setattr(MODULE, "_codex_exec_prompt", fake_codex_exec_prompt)

    out = MODULE._invoke_manager(
        cfg,
        manager_name="BOSS",
        cycle_number=1,
        context={},
        expected_artifacts=[],
    )

    assert out.status == "ok"
    assert captured["codex_home"] == str(codex_second_home)
    assert captured["resume_session_id"] is None
    assert captured["model"] == "gpt-5.3-codex"
    assert captured["reasoning_effort"] == "xhigh"
    assert out.message == "manager_profile_alias=codex-second"
    session_state = MODULE._read_json(tmp_path / MODULE.BOSS_SESSION_STATE_FILE, default={})
    assert session_state["session_id"] == "123e4567-e89b-12d3-a456-426614174000"
    assert session_state["codex_home"] == str(codex_second_home)


def test_invoke_manager_boss_rotates_profile_after_timeout_requirement(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._ensure_default_artifacts(cfg)
    codex_old_home = tmp_path / ".codex-old"
    codex_new_home = tmp_path / ".codex-new"
    codex_old_home.mkdir(parents=True, exist_ok=True)
    codex_new_home.mkdir(parents=True, exist_ok=True)
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["profile_snapshot"],
        {
            "schema_version": "1.0",
            "profiles": [
                {
                    "alias": "codex-old",
                    "codex_home": str(codex_old_home),
                    "window_5h_remaining_pct": 80.0,
                    "window_week_remaining_pct": 90.0,
                    "hard_gated": False,
                },
                {
                    "alias": "codex-new",
                    "codex_home": str(codex_new_home),
                    "window_5h_remaining_pct": 70.0,
                    "window_week_remaining_pct": 85.0,
                    "hard_gated": False,
                },
            ],
        },
    )
    MODULE._atomic_write_json(
        tmp_path / MODULE.BOSS_SESSION_STATE_FILE,
        {
            "schema_version": "1.0",
            "updated_at": "2026-01-01T00:00:00Z",
            "session_id": "123e4567-e89b-12d3-a456-426614174111",
            "codex_home": str(codex_old_home),
            "profile_alias": "codex-old",
            "previous_profile_alias": "codex-old",
        },
    )
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["timeout_adaptation_state"],
        {
            "schema_version": "1.0",
            "updated_at": "2026-01-01T00:00:00Z",
            "consecutive_boss_timeouts": 2,
            "timeout_threshold": 2,
            "adaptation_active": True,
            "rotation_required": True,
            "last_timeout_cycle": 9,
            "last_timeout_profile_alias": "codex-old",
            "last_timeout_reason": "manager_timeout",
        },
    )

    monkeypatch.setattr(MODULE, "_load_prompt_template", lambda *_args, **_kwargs: "prompt body")
    monkeypatch.setattr(MODULE.shutil, "which", lambda _binary: "/usr/bin/codex")
    captured = {"codex_home": None}

    def fake_codex_exec_prompt(*_args, **kwargs):
        captured["codex_home"] = kwargs.get("codex_home")
        return MODULE.ManagerResult(
            manager="BOSS",
            status="ok",
            timeout=False,
            returncode=0,
            started_at="2026-01-01T00:00:00Z",
            finished_at="2026-01-01T00:00:01Z",
            duration_seconds=1.0,
            session_id="123e4567-e89b-12d3-a456-426614174222",
        )

    monkeypatch.setattr(MODULE, "_codex_exec_prompt", fake_codex_exec_prompt)

    out = MODULE._invoke_manager(
        cfg,
        manager_name="BOSS",
        cycle_number=11,
        context={},
        expected_artifacts=[],
    )

    assert out.status == "ok"
    assert captured["codex_home"] == str(codex_new_home)
    assert out.message == "manager_profile_alias=codex-new"

    timeout_state = MODULE._read_json(tmp_path / MODULE.ARTIFACT_FILES["timeout_adaptation_state"], default={})
    decision = timeout_state.get("last_rotation_decision") if isinstance(timeout_state, dict) else {}
    assert decision.get("selected_alias") == "codex-new"
    evidence = decision.get("selection_evidence") if isinstance(decision, dict) else {}
    assert isinstance(evidence, dict)
    assert evidence.get("prior_alias_rejected_reason") == "excluded_for_timeout_rotation"


def test_invoke_manager_boss_fails_closed_when_runtime_context_invalid(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._ensure_default_artifacts(cfg)
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["profile_snapshot"],
        {
            "schema_version": "1.0",
            "profiles": [
                {
                    "alias": "codex-second",
                    "codex_home": "/tmp/codex-second",
                    "window_5h_remaining_pct": 80.0,
                    "window_week_remaining_pct": 90.0,
                }
            ],
        },
    )
    monkeypatch.setattr(MODULE, "_load_prompt_template", lambda *_args, **_kwargs: "prompt body")
    monkeypatch.setattr(MODULE.shutil, "which", lambda _binary: None)
    monkeypatch.setattr(
        MODULE,
        "_codex_exec_prompt",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not call codex exec when invalid")),
    )

    out = MODULE._invoke_manager(
        cfg,
        manager_name="BOSS",
        cycle_number=4,
        context={},
        expected_artifacts=[],
    )

    assert out.status == "failed"
    assert out.reason_code == "boss_runtime_context_invalid"
    assert "codex_binary_missing" in str(out.message)
    timeout_state = MODULE._read_json(tmp_path / MODULE.ARTIFACT_FILES["timeout_adaptation_state"], default={})
    checks = timeout_state.get("last_boss_runtime_checks") if isinstance(timeout_state, dict) else {}
    assert checks.get("runtime_context_valid") is False
    assert "codex_binary_missing" in (checks.get("invalid_reasons") or [])


def test_invoke_manager_boss_fails_closed_when_no_eligible_profile_in_snapshot(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._ensure_default_artifacts(cfg)
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["profile_snapshot"],
        {
            "schema_version": "1.0",
            "profiles": [
                {
                    "alias": "codex-hg",
                    "codex_home": "/tmp/codex-hg",
                    "window_5h_remaining_pct": 80.0,
                    "window_week_remaining_pct": 90.0,
                    "hard_gated": True,
                }
            ],
        },
    )
    monkeypatch.setattr(MODULE, "_load_prompt_template", lambda *_args, **_kwargs: "prompt body")
    monkeypatch.setattr(MODULE.shutil, "which", lambda _binary: "/usr/bin/codex")
    monkeypatch.setattr(
        MODULE,
        "_codex_exec_prompt",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not call codex exec when no profile is eligible")),
    )

    out = MODULE._invoke_manager(
        cfg,
        manager_name="BOSS",
        cycle_number=5,
        context={},
        expected_artifacts=[],
    )

    assert out.status == "failed"
    assert out.reason_code == "boss_runtime_context_invalid"
    assert "no_eligible_profile_in_snapshot" in str(out.message)
    timeout_state = MODULE._read_json(tmp_path / MODULE.ARTIFACT_FILES["timeout_adaptation_state"], default={})
    checks = timeout_state.get("last_boss_runtime_checks") if isinstance(timeout_state, dict) else {}
    assert checks.get("runtime_context_valid") is False
    assert "no_eligible_profile_in_snapshot" in (checks.get("invalid_reasons") or [])


def test_invoke_manager_boss_fails_closed_when_selected_codex_home_missing_on_disk(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._ensure_default_artifacts(cfg)
    missing_home = tmp_path / ".codex-missing-profile-home"
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["profile_snapshot"],
        {
            "schema_version": "1.0",
            "profiles": [
                {
                    "alias": "codex-missing-profile-home",
                    "codex_home": str(missing_home.resolve()),
                    "window_5h_remaining_pct": 80.0,
                    "window_week_remaining_pct": 90.0,
                    "hard_gated": False,
                }
            ],
        },
    )
    monkeypatch.setattr(MODULE, "_load_prompt_template", lambda *_args, **_kwargs: "prompt body")
    monkeypatch.setattr(MODULE.shutil, "which", lambda _binary: "/usr/bin/codex")
    monkeypatch.setattr(
        MODULE,
        "_codex_exec_prompt",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("should not call codex exec when selected codex home is missing")
        ),
    )

    out = MODULE._invoke_manager(
        cfg,
        manager_name="BOSS",
        cycle_number=5,
        context={},
        expected_artifacts=[],
    )

    assert out.status == "failed"
    assert out.reason_code == "boss_runtime_context_invalid"
    assert "selected_codex_home_missing_on_disk" in str(out.message)
    timeout_state = MODULE._read_json(tmp_path / MODULE.ARTIFACT_FILES["timeout_adaptation_state"], default={})
    checks = timeout_state.get("last_boss_runtime_checks") if isinstance(timeout_state, dict) else {}
    assert checks.get("runtime_context_valid") is False
    assert "selected_codex_home_missing_on_disk" in (checks.get("invalid_reasons") or [])


def test_invoke_manager_wrapup_uses_selected_profile_home_and_boss_model_reasoning(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["profile_snapshot"],
        {
            "schema_version": "1.0",
            "profiles": [
                {
                    "alias": "codex-wrapup",
                    "codex_home": "/tmp/codex-wrapup",
                    "window_5h_remaining_pct": 88.0,
                    "window_week_remaining_pct": 91.0,
                }
            ],
        },
    )

    monkeypatch.setattr(MODULE, "_load_prompt_template", lambda *_args, **_kwargs: "prompt body")
    captured: dict[str, str | None] = {
        "codex_home": None,
        "resume_session_id": None,
        "model": None,
        "reasoning_effort": None,
    }

    def fake_codex_exec_prompt(*_args, **kwargs):
        captured["codex_home"] = kwargs.get("codex_home")
        captured["resume_session_id"] = kwargs.get("resume_session_id")
        captured["model"] = kwargs.get("model")
        captured["reasoning_effort"] = kwargs.get("reasoning_effort")
        MODULE._atomic_write_json(
            tmp_path / MODULE.ARTIFACT_FILES["wrapup_manager_report"],
            {
                "schema_version": "1.0",
                "updated_at": "2026-01-01T00:00:00Z",
                "cycle_number": 1,
                "status": "completed",
                "summary": "ok",
            },
        )
        return MODULE.ManagerResult(
            manager="wrapup-manager",
            status="ok",
            timeout=False,
            returncode=0,
            started_at="2026-01-01T00:00:00Z",
            finished_at="2026-01-01T00:00:01Z",
            duration_seconds=1.0,
        )

    monkeypatch.setattr(MODULE, "_codex_exec_prompt", fake_codex_exec_prompt)

    out = MODULE._invoke_manager(
        cfg,
        manager_name="wrapup-manager",
        cycle_number=1,
        context={},
        expected_artifacts=["wrapup_manager_report"],
    )

    assert out.status == "ok"
    assert captured["codex_home"] == "/tmp/codex-wrapup"
    assert captured["resume_session_id"] is None
    assert captured["model"] == "gpt-5.3-codex"
    assert captured["reasoning_effort"] == "xhigh"
    assert out.message == "manager_profile_alias=codex-wrapup"


def test_invoke_manager_boss_resumes_existing_session(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    codex_third_home = tmp_path / ".codex-third"
    codex_third_home.mkdir(parents=True, exist_ok=True)
    MODULE._atomic_write_json(
        tmp_path / MODULE.BOSS_SESSION_STATE_FILE,
        {
            "schema_version": "1.0",
            "updated_at": "2026-01-01T00:00:00Z",
            "session_id": "123e4567-e89b-12d3-a456-426614174001",
            "codex_home": str(codex_third_home),
            "profile_alias": "codex-third",
            "previous_profile_alias": "codex-third",
        },
    )
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["profile_snapshot"],
        {
            "schema_version": "1.0",
            "profiles": [
                {
                    "alias": "codex-third",
                    "codex_home": str(codex_third_home),
                    "window_5h_remaining_pct": 70.0,
                    "window_week_remaining_pct": 80.0,
                }
            ],
        },
    )

    monkeypatch.setattr(MODULE, "_load_prompt_template", lambda *_args, **_kwargs: "prompt body")
    captured: dict[str, str | None] = {
        "codex_home": None,
        "resume_session_id": None,
        "model": None,
        "reasoning_effort": None,
    }

    def fake_codex_exec_prompt(*_args, **kwargs):
        captured["codex_home"] = kwargs.get("codex_home")
        captured["resume_session_id"] = kwargs.get("resume_session_id")
        captured["model"] = kwargs.get("model")
        captured["reasoning_effort"] = kwargs.get("reasoning_effort")
        return MODULE.ManagerResult(
            manager="BOSS",
            status="ok",
            timeout=False,
            returncode=0,
            started_at="2026-01-01T00:00:00Z",
            finished_at="2026-01-01T00:00:01Z",
            duration_seconds=1.0,
            session_id=None,
        )

    monkeypatch.setattr(MODULE, "_codex_exec_prompt", fake_codex_exec_prompt)

    out = MODULE._invoke_manager(
        cfg,
        manager_name="BOSS",
        cycle_number=2,
        context={},
        expected_artifacts=[],
    )

    assert out.status == "ok"
    assert captured["codex_home"] == str(codex_third_home)
    assert captured["resume_session_id"] == "123e4567-e89b-12d3-a456-426614174001"
    assert captured["model"] == "gpt-5.3-codex"
    assert captured["reasoning_effort"] == "xhigh"
    assert out.message == "manager_profile_alias=codex-third"


def test_invoke_manager_boss_switches_profile_and_starts_new_thread(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    codex_old_home = tmp_path / ".codex-old"
    codex_new_home = tmp_path / ".codex-new"
    codex_old_home.mkdir(parents=True, exist_ok=True)
    codex_new_home.mkdir(parents=True, exist_ok=True)
    MODULE._atomic_write_json(
        tmp_path / MODULE.BOSS_SESSION_STATE_FILE,
        {
            "schema_version": "1.0",
            "updated_at": "2026-01-01T00:00:00Z",
            "session_id": "123e4567-e89b-12d3-a456-426614174010",
            "codex_home": str(codex_old_home),
            "profile_alias": "codex-old",
            "previous_profile_alias": "codex-old",
        },
    )
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["profile_snapshot"],
        {
            "schema_version": "1.0",
            "profiles": [
                {
                    "alias": "codex-old",
                    "codex_home": str(codex_old_home),
                    "window_5h_remaining_pct": 70.0,
                    "window_week_remaining_pct": 49.0,
                },
                {
                    "alias": "codex-new",
                    "codex_home": str(codex_new_home),
                    "window_5h_remaining_pct": 90.0,
                    "window_week_remaining_pct": 95.0,
                },
            ],
        },
    )

    monkeypatch.setattr(MODULE, "_load_prompt_template", lambda *_args, **_kwargs: "prompt body")
    captured: dict[str, str | None] = {"resume_session_id": None, "codex_home": None}

    def fake_codex_exec_prompt(*_args, **kwargs):
        captured["resume_session_id"] = kwargs.get("resume_session_id")
        captured["codex_home"] = kwargs.get("codex_home")
        return MODULE.ManagerResult(
            manager="BOSS",
            status="ok",
            timeout=False,
            returncode=0,
            started_at="2026-01-01T00:00:00Z",
            finished_at="2026-01-01T00:00:01Z",
            duration_seconds=1.0,
            session_id="123e4567-e89b-12d3-a456-426614174011",
        )

    monkeypatch.setattr(MODULE, "_codex_exec_prompt", fake_codex_exec_prompt)

    out = MODULE._invoke_manager(
        cfg,
        manager_name="BOSS",
        cycle_number=2,
        context={},
        expected_artifacts=[],
    )

    assert out.status == "ok"
    assert captured["resume_session_id"] is None
    assert captured["codex_home"] == str(codex_new_home)
    assert out.message == "manager_profile_alias=codex-new"
    session_state = MODULE._read_json(tmp_path / MODULE.BOSS_SESSION_STATE_FILE, default={})
    assert session_state["profile_alias"] == "codex-new"
    assert session_state["previous_profile_alias"] == "codex-old"
    assert session_state["session_id"] == "123e4567-e89b-12d3-a456-426614174011"


def test_invoke_manager_boss_resume_failure_retries_fresh_session_and_persists_new_session(
    tmp_path: Path, monkeypatch
) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=8,
        dry_run=False,
    )
    (tmp_path / MODULE.CURRENT_DIR).mkdir(parents=True, exist_ok=True)
    codex_resume_home = tmp_path / ".codex-resume"
    codex_resume_home.mkdir(parents=True, exist_ok=True)
    MODULE._atomic_write_json(
        tmp_path / MODULE.BOSS_SESSION_STATE_FILE,
        {
            "schema_version": "1.0",
            "updated_at": "2026-01-01T00:00:00Z",
            "session_id": "123e4567-e89b-12d3-a456-426614174020",
            "codex_home": str(codex_resume_home),
            "profile_alias": "codex-resume",
            "previous_profile_alias": "codex-resume",
        },
    )
    MODULE._atomic_write_json(
        tmp_path / MODULE.ARTIFACT_FILES["profile_snapshot"],
        {
            "schema_version": "1.0",
            "profiles": [
                {
                    "alias": "codex-resume",
                    "codex_home": str(codex_resume_home),
                    "window_5h_remaining_pct": 70.0,
                    "window_week_remaining_pct": 80.0,
                }
            ],
        },
    )

    monkeypatch.setattr(MODULE, "_load_prompt_template", lambda *_args, **_kwargs: "prompt body")
    attempts: list[str | None] = []

    def fake_codex_exec_prompt(*_args, **kwargs):
        attempts.append(kwargs.get("resume_session_id"))
        if kwargs.get("resume_session_id"):
            return MODULE.ManagerResult(
                manager="BOSS",
                status="failed",
                timeout=False,
                returncode=1,
                started_at="2026-01-01T00:00:00Z",
                finished_at="2026-01-01T00:00:01Z",
                duration_seconds=1.0,
                message="resume failed",
                reason_code="manager_non_zero_exit",
            )
        return MODULE.ManagerResult(
            manager="BOSS",
            status="ok",
            timeout=False,
            returncode=0,
            started_at="2026-01-01T00:00:01Z",
            finished_at="2026-01-01T00:00:02Z",
            duration_seconds=1.0,
            session_id="123e4567-e89b-12d3-a456-426614174021",
        )

    monkeypatch.setattr(MODULE, "_codex_exec_prompt", fake_codex_exec_prompt)

    out = MODULE._invoke_manager(
        cfg,
        manager_name="BOSS",
        cycle_number=2,
        context={},
        expected_artifacts=[],
    )

    assert out.status == "ok"
    assert attempts == ["123e4567-e89b-12d3-a456-426614174020", None]
    assert out.message == "fresh_session_retry_after_resume_failure; manager_profile_alias=codex-resume"
    session_state = MODULE._read_json(tmp_path / MODULE.BOSS_SESSION_STATE_FILE, default={})
    assert session_state["session_id"] == "123e4567-e89b-12d3-a456-426614174021"


def test_boss_prompt_mentions_cycle_number_and_runtime_skip_correction() -> None:
    prompt = BOSS_PROMPT_PATH.read_text(encoding="utf-8")

    assert "cycle_manager_decision.json" in prompt
    assert "current cycle's top-level `cycle_number`" in prompt
    assert "runtime will correct the cycle to a deterministic `skip_cycle` outcome" in prompt
    assert "recovery_instructions.md" in prompt
    assert "3 Consecutive Missing-Ingestion Cycles" in prompt
    assert "reviewer_decision" in prompt
    assert "pid=null" in prompt


def test_reviewer_prompt_enforces_strict_machine_schema_and_canonical_handoff() -> None:
    prompt = REVIEWER_PROMPT_PATH.read_text(encoding="utf-8")

    assert "Return exactly one machine-readable JSON object" in prompt
    assert "Top-level keys are exactly: `task_identifier`, `decision`, `checks`, `findings`" in prompt
    assert "reviewer_decision" in prompt
    assert "<worktree_root>/reports/handoffs/<task_identifier>.handoff.json" in prompt


def test_wrapup_prompt_mentions_lifecycle_and_wrapup_report() -> None:
    prompt = WRAPUP_PROMPT_PATH.read_text(encoding="utf-8")

    assert "app_lifecycle.json" in prompt
    assert "wrapup_manager_report.json" in prompt
