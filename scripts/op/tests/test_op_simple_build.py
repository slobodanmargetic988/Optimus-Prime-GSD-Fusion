import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace


OP_SIMPLE_BUILD_PATH = Path(__file__).resolve().parents[1] / "op_simple_build.py"
BOSS_PROMPT_PATH = Path(__file__).resolve().parents[2] / "op_simple" / "prompts" / "managers" / "boss.md"
SPEC = importlib.util.spec_from_file_location("op_simple_build", OP_SIMPLE_BUILD_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


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

    out = MODULE.run_op_simple_build(make_req(tmp_path, dry_run=False, max_build_cycles=1, sleep_minutes=0))

    assert out["ok"] is True
    assert "after BOSS timeout" in out["summary"]


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


def test_dispatch_packets_writes_launch_and_registry(tmp_path: Path, monkeypatch) -> None:
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


def test_watchdog_emits_exit_signal_after_idle_threshold(tmp_path: Path) -> None:
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

    stop = False
    for cycle in range(1, 12):
        stop, _signal = MODULE._watchdog_tick(cfg, cycle)

    assert stop is True
    assert (tmp_path / MODULE.ARTIFACT_FILES["watchdog_exit_signal"]).exists()


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

    def fail_run(*_args, **_kwargs):  # pragma: no cover - should not execute when cap reached
        raise AssertionError("dispatch subprocess should not be called when parallel cap is exhausted")

    monkeypatch.setattr(MODULE.subprocess, "run", fail_run)

    counters = MODULE._dispatch_packets(cfg, cycle_number=3)

    assert counters == {"attempted": 0, "launched": 0, "launch_failed": 0, "unknown": 0}
    assert not (tmp_path / MODULE.DISPATCH_LAUNCH_LOG_FILE).exists()


def test_ensure_workstation_prep_prepares_slots_and_seeds_worker_registry(tmp_path: Path, monkeypatch) -> None:
    build_repo(tmp_path)
    cfg = MODULE.RunConfig(
        repo_root=tmp_path,
        sleep_minutes=0,
        max_build_cycles=1,
        max_parallel_workers=2,
        dry_run=False,
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
            worktree_name = cmd[cmd.index("--worktree-name") + 1]
            branch_name = cmd[cmd.index("--branch-name") + 1]
            target_path = tmp_path / worktree_name
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
    assert out["workstations"][0]["workstation_id"] == "workstation-1"
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

    monkeypatch.setattr(MODULE, "_watchdog_tick", lambda _cfg, _cycle: (True, {"message": "idle"}))
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


def test_select_boss_profile_from_snapshot_excludes_default_codex_when_multiple_profiles_exist(tmp_path: Path) -> None:
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

    assert alias == "codex-second"
    assert home == "/tmp/codex-second"


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
    captured: dict[str, str | None] = {"codex_home": None}

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
    assert captured["codex_home"] == "/tmp/codex-second"
    assert out.message == "manager_profile_alias=codex-second"


def test_boss_prompt_mentions_cycle_number_and_runtime_skip_correction() -> None:
    prompt = BOSS_PROMPT_PATH.read_text(encoding="utf-8")

    assert "cycle_manager_decision.json" in prompt
    assert "current cycle's top-level `cycle_number`" in prompt
    assert "runtime will correct the cycle to a deterministic `skip_cycle` outcome" in prompt
