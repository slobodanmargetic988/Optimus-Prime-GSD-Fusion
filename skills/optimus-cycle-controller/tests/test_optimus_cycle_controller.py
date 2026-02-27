import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "optimus_cycle_controller.py"


@pytest.fixture
def controller_module():
    spec = importlib.util.spec_from_file_location("optimus_cycle_controller", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_jsonl(path: Path):
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(json.loads(line))
    return out


def make_config(controller_module, tmp_path: Path, **overrides):
    payload = {
        "repo_root": str(tmp_path),
        "sleep_minutes": 0,
        "profile_aliases": ["codex"],
        "dry_run": True,
        "emit_stdout": False,
    }
    payload.update(overrides)
    return controller_module.normalize_config(payload)


def test_loop_continues_when_no_terminal_evidence(controller_module, tmp_path):
    config = make_config(controller_module, tmp_path, max_cycles=1)
    result = controller_module.run_controller(config)

    assert result["ok"] is False
    assert result["reason"] == "max_cycles_reached_without_terminal"
    assert result["terminal_reason"] is None



def test_stops_on_valid_project_done_file(controller_module, tmp_path):
    done_path = tmp_path / "reports" / "optimus-prime" / "control" / "PROJECT_DONE.json"
    write_json(done_path, {"status": "done", "evidence": "all scoped tasks done"})

    config = make_config(controller_module, tmp_path, max_cycles=3)
    result = controller_module.run_controller(config)

    assert result["ok"] is True
    assert result["terminal_reason"] == "project_done"

    final_state = json.loads(config.final_state_path.read_text(encoding="utf-8"))
    assert final_state["terminal_reason"] == "project_done"



def test_stops_on_valid_insurmountable_blocker_file(controller_module, tmp_path):
    blocker_path = (
        tmp_path / "reports" / "optimus-prime" / "control" / "INSURMOUNTABLE_BLOCKER.json"
    )
    write_json(blocker_path, {"status": "blocked", "reason": "manual dependency deadlock"})

    config = make_config(controller_module, tmp_path, max_cycles=3)
    result = controller_module.run_controller(config)

    assert result["ok"] is True
    assert result["terminal_reason"] == "insurmountable_blocker"



def test_stops_on_all_rate_gates_blocking_and_writes_evidence(controller_module, tmp_path):
    rate_path = tmp_path / "reports" / "optimus-prime" / "PROFILE_RATE_REGISTRY.json"
    write_json(
        rate_path,
        {
            "profiles": {
                "codex": {
                    "five_hour": {"remaining_percent": 5},
                    "weekly": {"remaining_percent": 8},
                    "recommended_action": "wind_down",
                }
            }
        },
    )

    config = make_config(controller_module, tmp_path, max_cycles=3)
    result = controller_module.run_controller(config)

    assert result["ok"] is True
    assert result["terminal_reason"] == "all_rate_gates_blocking"

    all_rate_path = tmp_path / "reports" / "optimus-prime" / "control" / "ALL_RATE_GATES_BLOCKING.json"
    assert all_rate_path.exists()
    payload = json.loads(all_rate_path.read_text(encoding="utf-8"))
    assert payload["status"] == "all_rate_gates_blocking"



def test_rejects_malformed_evidence_files(controller_module, tmp_path):
    bad_done = tmp_path / "reports" / "optimus-prime" / "control" / "PROJECT_DONE.json"
    bad_done.parent.mkdir(parents=True, exist_ok=True)
    bad_done.write_text("{not-json", encoding="utf-8")

    config = make_config(controller_module, tmp_path, max_cycles=1)
    result = controller_module.run_controller(config)

    assert result["ok"] is False
    heartbeat = json.loads(config.heartbeat_path.read_text(encoding="utf-8"))
    assert any("project_done_file_malformed" in w for w in heartbeat["warnings"])



def test_lock_file_prevents_concurrent_controller_runs(controller_module, tmp_path):
    sleeper = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        lock_path = tmp_path / "reports" / "optimus-prime" / "controller" / "lock.pid"
        write_json(lock_path, {"pid": sleeper.pid, "status": "running"})

        config = make_config(controller_module, tmp_path, max_cycles=1)
        result = controller_module.run_controller(config)

        assert result["ok"] is False
        assert result["error"] == "lock_conflict"
        assert result["active_pid"] == sleeper.pid
    finally:
        sleeper.terminate()
        sleeper.wait(timeout=5)



def test_emits_heartbeat_each_cycle(controller_module, tmp_path):
    config = make_config(controller_module, tmp_path, max_cycles=2)
    result = controller_module.run_controller(config)

    assert result["ok"] is False
    heartbeat = json.loads(config.heartbeat_path.read_text(encoding="utf-8"))
    assert heartbeat["cycle_number"] == 2
    assert heartbeat["status"] == "running"



def test_emits_directives_for_optimus_action(controller_module, tmp_path):
    config = make_config(controller_module, tmp_path, max_cycles=1)
    controller_module.run_controller(config)

    events = read_jsonl(config.events_path)
    directive_events = [e for e in events if e.get("event_type") == "directive"]

    assert directive_events, "expected at least one directive event"
    assert any(e.get("requires_optimus_action") is True for e in directive_events)



def test_emits_linear_sync_directive_when_handoff_indicates_phase(controller_module, tmp_path):
    handoff_path = tmp_path / "reports" / "optimus-prime" / "HANDOFF_LOG.jsonl"
    handoff_path.parent.mkdir(parents=True, exist_ok=True)
    handoff_path.write_text(
        json.dumps(
            {
                "task_identifier": "MYO-777",
                "target_phase": "agent_review_done",
                "status": "review_done",
                "branch": "codex/dev-1/MYO-777",
                "head_commit": "abc1234",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    config = make_config(controller_module, tmp_path, max_cycles=1)
    controller_module.run_controller(config)

    events = read_jsonl(config.events_path)
    sync_directives = [
        e
        for e in events
        if e.get("event_type") == "directive" and e.get("action_code") == "sync_linear_phase"
    ]
    assert sync_directives
    payload = sync_directives[0]["payload"]
    assert payload["recommended_tool"] == "linear-handoff-sync"
    assert payload["recommended_args"]["issue_identifier"] == "MYO-777"
    assert payload["recommended_args"]["target_phase"] == "agent_review_done"


def test_emits_runtime_resolve_directive_for_tester_without_runtime_strategy(controller_module, tmp_path):
    worker_registry_path = tmp_path / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
    write_json(
        worker_registry_path,
        {
            "workers": [
                {
                    "slot": "test-1",
                    "role": "tester",
                    "state": "running",
                    "active_task": "MYO-901",
                }
            ]
        },
    )

    config = make_config(controller_module, tmp_path, max_cycles=1)
    controller_module.run_controller(config)

    events = read_jsonl(config.events_path)
    runtime_directives = [
        e
        for e in events
        if e.get("event_type") == "directive"
        and e.get("action_code") == "runtime_strategy_resolve"
    ]
    assert runtime_directives
    payload = runtime_directives[0]["payload"]
    assert payload["recommended_tool"] == "runtime-coordinator"
    assert payload["recommended_args"]["task_identifier"] == "MYO-901"


def test_emits_blocker_refresh_directive_when_handoff_is_blocked(controller_module, tmp_path):
    handoff_path = tmp_path / "reports" / "optimus-prime" / "HANDOFF_LOG.jsonl"
    handoff_path.parent.mkdir(parents=True, exist_ok=True)
    handoff_path.write_text(
        json.dumps(
            {
                "task_identifier": "MYO-902",
                "status": "blocked",
                "blocker_summary": "runtime start failed",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    config = make_config(controller_module, tmp_path, max_cycles=1)
    controller_module.run_controller(config)

    events = read_jsonl(config.events_path)
    blocker_directives = [
        e
        for e in events
        if e.get("event_type") == "directive"
        and e.get("action_code") == "refresh_blocker_index"
    ]
    assert blocker_directives
    payload = blocker_directives[0]["payload"]
    assert payload["recommended_tool"] == "runtime-coordinator"


def test_emits_test_train_wave_directives(controller_module, tmp_path):
    state_path = tmp_path / "reports" / "optimus-prime" / "TEST_TRAIN_STATE.json"
    write_json(
        state_path,
        {
            "test_train_mode": "final-stage",
            "test_branch": "test",
            "test_next_branch": "test-next",
            "shared_test_base_url": "https://test.example.internal",
            "active_wave": {
                "wave_id": "wave-0012",
                "state": "PROMOTION_EVAL",
                "planned_flow_pass_completed": True,
            },
            "promotion_eligibility": {"eligible": True, "reasons": ["eligible"]},
        },
    )

    config = make_config(controller_module, tmp_path, max_cycles=1)
    controller_module.run_controller(config)

    events = read_jsonl(config.events_path)
    action_codes = {
        e.get("action_code")
        for e in events
        if e.get("event_type") == "directive"
    }
    assert "evaluate_promotion_gate" in action_codes
    assert "promote_test_next_to_test" in action_codes
    assert "deploy_test_branch" in action_codes
    assert "start_new_test_wave" in action_codes


def test_optimus_cannot_end_without_valid_final_state_terminal_payload(controller_module, tmp_path):
    final_state_path = tmp_path / "reports" / "optimus-prime" / "controller" / "FINAL_STATE.json"

    assert controller_module.can_optimus_stop_from_final_state(final_state_path) is False

    write_json(final_state_path, {"terminal_reason": "not_allowed", "evidence_file": "x"})
    assert controller_module.can_optimus_stop_from_final_state(final_state_path) is False

    write_json(
        final_state_path,
        {
            "terminal_reason": "project_done",
            "evidence_file": "/tmp/proof-missing.json",
            "generated_at": "2026-02-26T00:00:00Z",
        },
    )
    assert controller_module.can_optimus_stop_from_final_state(final_state_path) is False

    evidence_path = tmp_path / "reports" / "optimus-prime" / "control" / "PROJECT_DONE.json"
    write_json(evidence_path, {"status": "done", "evidence": "tests and gates passed"})

    write_json(
        final_state_path,
        {
            "terminal_reason": "project_done",
            "evidence_file": str(evidence_path),
            "generated_at": "2026-02-26T00:00:00Z",
        },
    )
    assert controller_module.can_optimus_stop_from_final_state(final_state_path) is True



def test_verify_final_state_cli_mode(controller_module, tmp_path):
    evidence_path = tmp_path / "reports" / "optimus-prime" / "control" / "PROJECT_DONE.json"
    write_json(evidence_path, {"status": "done", "evidence": "complete"})

    final_state_path = tmp_path / "reports" / "optimus-prime" / "controller" / "FINAL_STATE.json"
    write_json(
        final_state_path,
        {
            "terminal_reason": "project_done",
            "evidence_file": str(evidence_path),
            "generated_at": "2026-02-26T00:00:00Z",
        },
    )

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--verify-final-state",
            str(final_state_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["mode"] == "verify_final_state"
