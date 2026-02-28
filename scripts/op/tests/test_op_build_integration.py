import importlib.util
import json
import os
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
TEST_CONTROL_RUN_ID = "test-control-run-id"


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
    snapshot_script = root / "skills" / "codex-rate-snapshot" / "scripts" / "read_codex_rate_snapshots.py"
    snapshot_script.parent.mkdir(parents=True, exist_ok=True)
    snapshot_script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import argparse",
                "import json",
                "",
                "parser = argparse.ArgumentParser()",
                "parser.add_argument('--profile', action='append', default=[])",
                "parser.add_argument('--json-pretty', action='store_true')",
                "args = parser.parse_args()",
                "profiles = {}",
                "for item in args.profile:",
                "    alias = item.split('=', 1)[0].strip()",
                "    if not alias:",
                "        continue",
                "    profiles[alias] = {",
                "        'recommended_action': 'continue',",
                "        'five_hour': {'remaining_percent': 80},",
                "        'weekly': {'remaining_percent': 80},",
                "    }",
                "if not profiles:",
                "    profiles = {'codex': {'recommended_action': 'continue', 'five_hour': {'remaining_percent': 80}, 'weekly': {'remaining_percent': 80}}}",
                "payload = {'profiles': profiles}",
                "if args.json_pretty:",
                "    print(json.dumps(payload, indent=2))",
                "else:",
                "    print(json.dumps(payload))",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    fake_bin = root / "bin"
    fake_bin.mkdir(parents=True, exist_ok=True)
    fake_codex = fake_bin / "codex"
    fake_codex.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import hashlib",
                "import json",
                "import re",
                "import subprocess",
                "import sys",
                "from pathlib import Path",
                "",
                "def checksum(content_type, content):",
                "    if content_type == 'json':",
                "        payload = json.dumps(content, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')",
                "    else:",
                "        payload = str(content).encode('utf-8')",
                "    return hashlib.sha256(payload).hexdigest()",
                "",
                "def row(path, content_type, content):",
                "    return {'artifact_path': path, 'content_type': content_type, 'content': content, 'checksum_sha256': checksum(content_type, content)}",
                "",
                "args = sys.argv[1:]",
                "prompt = sys.stdin.read()",
                "bundle_match = re.search(r'Output artifacts by writing a JSONL file at:\\s*(\\S+)', prompt)",
                "if not bundle_match:",
                "    print('missing bundle path', file=sys.stderr)",
                "    raise SystemExit(1)",
                "bundle_path = Path(bundle_match.group(1)).expanduser().resolve()",
                "bundle_path.parent.mkdir(parents=True, exist_ok=True)",
                "validator_match = re.search(r'After writing the bundle, run this validator command:\\s*(.+)', prompt)",
                "last_message = None",
                "if '--output-last-message' in args:",
                "    idx = args.index('--output-last-message')",
                "    if idx + 1 < len(args):",
                "        last_message = Path(args[idx + 1]).expanduser().resolve()",
                "",
                "plan_id = 'plan-test'",
                "requirements = [",
                "    {'id': 'REQ-001', 'title': 'Core workflow', 'acceptance_criteria': ['core path'], 'verify_commands': ['python3 -m pytest']},",
                "    {'id': 'REQ-002', 'title': 'Quality gates', 'acceptance_criteria': ['quality path'], 'verify_commands': ['python3 -m pytest']},",
                "    {'id': 'REQ-003', 'title': 'Rollout ops', 'acceptance_criteria': ['ops path'], 'verify_commands': ['python3 -m pytest']},",
                "]",
                "tasks = [",
                "    {'task_id': 'TASK-001', 'title': 'Implement core workflow', 'phase_id': 'phase-1', 'requirement_ids': ['REQ-001'], 'depends_on': [], 'must_haves': ['core path'], 'verify_commands': ['python3 -m pytest']},",
                "    {'task_id': 'TASK-002', 'title': 'Implement quality gates', 'phase_id': 'phase-1', 'requirement_ids': ['REQ-002'], 'depends_on': ['TASK-001'], 'must_haves': ['quality path'], 'verify_commands': ['python3 -m pytest']},",
                "    {'task_id': 'TASK-003', 'title': 'Implement rollout ops', 'phase_id': 'phase-1', 'requirement_ids': ['REQ-003'], 'depends_on': ['TASK-002'], 'must_haves': ['ops path'], 'verify_commands': ['python3 -m pytest']},",
                "]",
                "plan_packets = {'schema_version': '1.0', 'generated_at': '2026-01-01T00:00:00Z', 'plan_id': plan_id, 'phase': 'multi-phase', 'phases': [{'phase_id': 'phase-1', 'task_ids': ['TASK-001', 'TASK-002', 'TASK-003'], 'depends_on_phase_ids': [], 'entry_criteria': ['phase_dependencies_done'], 'exit_criteria': ['all_tasks_review_done', 'verify_commands_passed', 'uat_matrix_passed', 'zero_open_gaps']}], 'requirements': requirements, 'tasks': tasks, 'depends_on': [], 'must_haves': ['core path', 'quality path', 'ops path'], 'verify_commands': ['python3 -m pytest']}",
                "plan_check = {'schema_version': '1.0', 'passed': True, 'checks': [{'id': 'requirement_coverage', 'passed': True}], 'coverage': {'requirements_total': 3, 'requirements_covered': 3, 'missing_requirement_ids': []}, 'dependency_graph': {'nodes': ['TASK-001', 'TASK-002', 'TASK-003'], 'edges': [{'from': 'TASK-001', 'to': 'TASK-002'}, {'from': 'TASK-002', 'to': 'TASK-003'}], 'cycle_detected': False, 'valid': True}, 'verify_contract_completeness': True, 'phase_traceability': True, 'blocking_errors': []}",
                "task_state = {'schema_version': '1.0', 'plan_id': plan_id, 'updated_at': '2026-01-01T00:00:00Z', 'tasks': []}",
                "for task in tasks:",
                "    task_id = task['task_id']",
                "    evidence_ref = f'reports/optimus-prime/planning/evidence/{task_id}/TASK_EVIDENCE.json'",
                "    task_state['tasks'].append({'task_id': task_id, 'phase_id': task['phase_id'], 'requirement_ids': task['requirement_ids'], 'status': 'queued', 'owner_slot': None, 'attempts': {'dev': 0, 'test': 0, 'review': 0}, 'evidence': {'task_evidence_ref': evidence_ref, 'dev_ready_evidence_ref': evidence_ref, 'verify_results': [], 'uat_results': []}, 'blockers': []})",
                "state_json = {'schema_version': '1.0', 'initialized_at': '2026-01-01T00:00:00Z', 'updated_at': '2026-01-01T00:00:00Z', 'mission': 'inline:Build MyBoard', 'scope': 'inline:Board workflow', 'mission_source': {'mode': 'inline', 'value': 'Build MyBoard', 'path': None, 'display': 'Build MyBoard'}, 'scope_source': {'mode': 'inline', 'value': 'Board workflow', 'path': None, 'display': 'Board workflow'}, 'constraints': [], 'requirements': requirements, 'map_fingerprint': 'map-test', 'repo_fingerprint': 'repo-test', 'baseline_ready': True, 'plan_ready': True, 'plan_id': plan_id, 'build_ready': True}",
                "state_md = '# STATE\\n\\n- baseline_ready: true\\n- plan_ready: true\\n- build_ready: true\\n'",
                "gaps = {'schema_version': '1.0', 'plan_id': plan_id, 'updated_at': '2026-01-01T00:00:00Z', 'gaps': []}",
                "closure = {'schema_version': '1.0', 'plan_id': plan_id, 'generated_at': '2026-01-01T00:00:00Z', 'tasks': []}",
                "rows = [",
                "    row('PLAN_PACKETS.json', 'json', plan_packets),",
                "    row('PLAN_CHECK.json', 'json', plan_check),",
                "    row('TASK_EXECUTION_STATE.json', 'json', task_state),",
                "    row('GAPS.json', 'json', gaps),",
                "    row('GAP_CLOSURE_PLAN_PACKETS.json', 'json', closure),",
                "    row('TEST_CONTRACT.md', 'text', '# TEST CONTRACT\\n'),",
                "    row('PLAYWRIGHT_UAT_MATRIX.md', 'text', '# PLAYWRIGHT UAT MATRIX\\n'),",
                "    row('VERIFICATION.md', 'text', '# VERIFICATION\\n'),",
                "    row('UAT.md', 'text', '# UAT\\n'),",
                "    row('STATE.json', 'json', state_json),",
                "    row('STATE.md', 'text', state_md),",
                "]",
                "for task in tasks:",
                "    task_id = task['task_id']",
                "    ev = {'schema_version': '1.0', 'plan_id': plan_id, 'phase_id': task['phase_id'], 'task_id': task_id, 'requirement_ids': task['requirement_ids'], 'updated_at': '2026-01-01T00:00:00Z', 'dev': {'status': 'queued', 'checks': [], 'verify_results': [], 'dev_ready': False, 'blockers': [], 'artifacts': []}, 'test': {'status': 'queued', 'checks': [], 'verify_results': [], 'uat_results': [], 'blockers': [], 'artifacts': []}, 'review': {'status': 'queued', 'decision': None, 'blockers': [], 'artifacts': []}, 'gate': {'ready_for_test': False, 'ready_for_review': False, 'ready_for_phase_exit': False}, 'summary': {'result': 'pass', 'reason_codes': []}}",
                "    rows.append(row(f'evidence/{task_id}/TASK_EVIDENCE.json', 'json', ev))",
                "bundle_path.write_text('\\n'.join(json.dumps(item) for item in rows) + '\\n', encoding='utf-8')",
                "if validator_match:",
                "    subprocess.run(validator_match.group(1), shell=True, check=False)",
                "if last_message is not None:",
                "    last_message.parent.mkdir(parents=True, exist_ok=True)",
                "    last_message.write_text('planner complete\\n', encoding='utf-8')",
                "print(json.dumps({'ok': True, 'bundle_path': str(bundle_path)}))",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    fake_codex.chmod(0o755)
    profile_dir = root.parent / ".codex"
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "auth.json").write_text("{}\n", encoding="utf-8")
    os.environ["CODEX_HOME"] = str(profile_dir)
    os.environ["PATH"] = f"{fake_bin}:{os.environ.get('PATH', '')}"
    git(root, "add", ".")
    git(root, "commit", "-m", "seed")


def run_payload(payload: dict) -> dict:
    req = MODULE.parse_request(payload)
    return MODULE.execute_request(req)


def write_profile_selection(root: Path, aliases: list[str]) -> None:
    profile_root = Path(os.environ["CODEX_HOME"]).expanduser().resolve().parent
    profiles: list[dict[str, str]] = []
    for alias in aliases:
        dirname = f".{alias}"
        if alias == "codex":
            dirname = ".codex"
        home = profile_root / dirname
        home.mkdir(parents=True, exist_ok=True)
        auth = home / "auth.json"
        if not auth.exists():
            auth.write_text("{}\n", encoding="utf-8")
        profiles.append(
            {
                "alias": alias,
                "codex_home": str(home.resolve()),
                "auth_path": str(auth.resolve()),
            }
        )
    path = root / "reports" / "optimus-prime" / "planning" / "PROFILE_SELECTION.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "detected_at": "2026-01-01T00:00:00Z",
                "detection_root": str(profile_root),
                "profiles": profiles,
                "selected_aliases": aliases,
                "selection_policy": "initialize_autodetect",
                "notes": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def pin_build_lock(monkeypatch: pytest.MonkeyPatch, lock_id: str = TEST_CONTROL_RUN_ID) -> None:
    monkeypatch.setattr(MODULE, "_acquire_build_loop_lock", lambda _lock_path: (True, lock_id, None))


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
                "control_number": 1,
                "control_run_id": TEST_CONTROL_RUN_ID,
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
                "control_number": 1,
                "control_run_id": TEST_CONTROL_RUN_ID,
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

        def fake_cycle(_req, **_kwargs):
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
        pin_build_lock(monkeypatch)

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


def test_op_build_uses_control_number_for_directive_selection(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        init = run_payload(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        assert init["ok"] is True

        events_path = root / "reports" / "optimus-prime" / "controller" / "EVENTS.jsonl"
        events_path.parent.mkdir(parents=True, exist_ok=True)
        events = [
            {
                "timestamp": "2026-01-01T00:00:00Z",
                "cycle_number": 1,
                "control_number": 1,
                "control_run_id": TEST_CONTROL_RUN_ID,
                "event_type": "directive",
                "action_code": "review_dispatch_queue",
                "payload": {
                    "directive_type": "review_dispatch_queue",
                    "requires_optimus_action": True,
                },
            },
            {
                "timestamp": "2026-01-01T00:00:01Z",
                "cycle_number": 1,
                "control_number": 2,
                "control_run_id": TEST_CONTROL_RUN_ID,
                "event_type": "directive",
                "action_code": "dispatch_filter",
                "payload": {
                    "directive_type": "dispatch_filter",
                    "requires_optimus_action": True,
                    "recommended_args": {"reason": "hard-gate"},
                },
            },
        ]
        events_path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")

        monkeypatch.setattr(
            MODULE,
            "_run_controller_cycle",
            lambda _req, **_kwargs: {
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
        pin_build_lock(monkeypatch)

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
        warning_codes = {item.get("code") for item in out.get("warnings", [])}
        assert "dispatch_skipped_hard_gate" not in warning_codes


def test_op_build_passes_selected_profile_aliases_to_controller(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        init = run_payload(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        assert init["ok"] is True
        write_profile_selection(root, ["codex", "codex-second"])

        events_path = root / "reports" / "optimus-prime" / "controller" / "EVENTS.jsonl"
        events_path.parent.mkdir(parents=True, exist_ok=True)
        events_path.write_text("", encoding="utf-8")

        captured: dict[str, object] = {}

        def fake_cycle(_req, **kwargs):
            captured.update(kwargs)
            return {
                "ok": False,
                "status": "running",
                "terminal_reason": None,
                "last_cycle_number": 1,
                "events_path": str(events_path),
            }

        monkeypatch.setattr(MODULE, "_run_controller_cycle", fake_cycle)
        monkeypatch.setattr(MODULE, "_dispatch_next_task", lambda *_args, **_kwargs: {"ok": True, "status": "noop"})
        pin_build_lock(monkeypatch)

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
        assert captured.get("profile_aliases") == ["codex", "codex-second"]


def test_op_build_dispatch_reassigns_profile_when_current_is_hard_gated(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        init = run_payload(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        assert init["ok"] is True
        write_profile_selection(root, ["codex", "codex-second"])

        rate_path = root / "reports" / "optimus-prime" / "PROFILE_RATE_REGISTRY.json"
        rate_path.parent.mkdir(parents=True, exist_ok=True)
        rate_path.write_text(
            json.dumps(
                {
                    "profiles": {
                        "codex": {"recommended_action": "wind_down"},
                        "codex-second": {"recommended_action": "continue"},
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        events_path = root / "reports" / "optimus-prime" / "controller" / "EVENTS.jsonl"
        events_path.parent.mkdir(parents=True, exist_ok=True)
        events_path.write_text("", encoding="utf-8")

        monkeypatch.setattr(
            MODULE,
            "_run_controller_cycle",
            lambda _req, **_kwargs: {
                "ok": False,
                "status": "running",
                "terminal_reason": None,
                "last_cycle_number": 1,
                "events_path": str(events_path),
            },
        )
        monkeypatch.setattr(MODULE, "_seed_rate_registry_if_missing", lambda *_args, **_kwargs: [])

        dispatch_payloads: list[dict] = []

        def fake_tool(script: Path, payload: dict, cwd: Path) -> dict:
            if script.name == "dispatch_worker_packet.py":
                dispatch_payloads.append(payload)
            return {"ok": True, "status": "dispatch_started"}

        monkeypatch.setattr(MODULE, "_run_tool_json", fake_tool)
        pin_build_lock(monkeypatch)
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
        assert dispatch_payloads
        assert dispatch_payloads[0]["codex_profile_alias"] == "codex-second"
        assert any(item.get("code") == "profile_assignment_reassigned" for item in out.get("warnings", []))


def test_op_build_skips_dispatch_when_all_selected_profiles_hard_gated(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        init = run_payload(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        assert init["ok"] is True
        write_profile_selection(root, ["codex", "codex-second"])

        rate_path = root / "reports" / "optimus-prime" / "PROFILE_RATE_REGISTRY.json"
        rate_path.parent.mkdir(parents=True, exist_ok=True)
        rate_path.write_text(
            json.dumps(
                {
                    "profiles": {
                        "codex": {"recommended_action": "wind_down"},
                        "codex-second": {"recommended_action": "wait_until_reset"},
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        events_path = root / "reports" / "optimus-prime" / "controller" / "EVENTS.jsonl"
        events_path.parent.mkdir(parents=True, exist_ok=True)
        events_path.write_text("", encoding="utf-8")
        monkeypatch.setattr(
            MODULE,
            "_run_controller_cycle",
            lambda _req, **_kwargs: {
                "ok": False,
                "status": "running",
                "terminal_reason": None,
                "last_cycle_number": 1,
                "events_path": str(events_path),
            },
        )
        monkeypatch.setattr(MODULE, "_seed_rate_registry_if_missing", lambda *_args, **_kwargs: [])
        dispatch_calls = {"count": 0}

        def fake_tool(script: Path, payload: dict, cwd: Path) -> dict:
            if script.name == "dispatch_worker_packet.py":
                dispatch_calls["count"] += 1
            return {"ok": True, "status": "dispatch_started"}

        monkeypatch.setattr(MODULE, "_run_tool_json", fake_tool)
        pin_build_lock(monkeypatch)
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
        assert any(item.get("code") == "profile_assignment_all_hard_gated" for item in out.get("warnings", []))


def test_operator_stop_integration_consumes_marker_and_records_stop_state(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        init = run_payload(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        assert init["ok"] is True

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
                            "dispatch_pid": 24680,
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
        marker.write_text(json.dumps({"stop": True, "reason": "integration stop"}, indent=2) + "\n", encoding="utf-8")

        alive = {24680}

        def fake_pid_is_running(pid: int) -> bool:
            return pid in alive

        def fake_kill(pid: int, sig: int) -> None:
            if pid == 24680 and sig == MODULE.signal.SIGTERM:
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
        assert not marker.exists()
        assert list((root / "reports" / "optimus-prime" / "control").glob("OPERATOR_STOP.applied.*.json"))
        stop_state = json.loads((root / "reports" / "optimus-prime" / "control" / "OPERATOR_STOP_STATE.json").read_text(encoding="utf-8"))
        assert stop_state["reconcile_pending"] is True
        assert task_id in stop_state["affected_task_ids"]


def test_operator_stop_failure_integration_returns_blocked_terminal(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        init = run_payload(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        assert init["ok"] is True

        marker = root / "reports" / "optimus-prime" / "control" / "OPERATOR_STOP.json"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps({"stop": True, "reason": "integration-failure"}, indent=2) + "\n", encoding="utf-8")

        def fail_apply(*_args, **_kwargs):
            raise MODULE.OpError("operator_stop_apply_failed", "simulated integration failure", stage="build_loop")

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
        assert out["ok"] is False
        assert out["status"] == "blocked_terminal"
        assert any(item.get("code") == "operator_stop_apply_failed" for item in out.get("errors", []))
        assert marker.exists()
        lock_path = root / "reports" / "optimus-prime" / "planning" / "BUILD_LOOP.lock"
        assert not lock_path.exists()


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
            lambda _req, **_kwargs: {
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
                    "control_number": 1,
                    "control_run_id": TEST_CONTROL_RUN_ID,
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
            lambda _req, **_kwargs: {
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
        pin_build_lock(monkeypatch)
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
                    "control_number": 1,
                    "control_run_id": TEST_CONTROL_RUN_ID,
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
            lambda _req, **_kwargs: {
                "ok": False,
                "status": "running",
                "terminal_reason": None,
                "last_cycle_number": 1,
                "events_path": str(events_path),
            },
        )
        monkeypatch.setattr(MODULE, "_run_tool_json", fake_tool)
        monkeypatch.setattr(MODULE, "_dispatch_next_task", lambda req, plan, state, build, *_: {"ok": True, "status": "noop"})
        pin_build_lock(monkeypatch)
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
                    "control_number": 1,
                    "control_run_id": TEST_CONTROL_RUN_ID,
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
            lambda _req, **_kwargs: {
                "ok": False,
                "status": "running",
                "terminal_reason": None,
                "last_cycle_number": 1,
                "events_path": str(events_path),
            },
        )
        monkeypatch.setattr(MODULE, "_run_tool_json", fake_tool)
        monkeypatch.setattr(MODULE, "_dispatch_next_task", lambda req, plan, state, build, *_: {"ok": True, "status": "noop"})
        pin_build_lock(monkeypatch)
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
            lambda _req, **_kwargs: {
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
                    "control_number": 1,
                    "control_run_id": TEST_CONTROL_RUN_ID,
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
            lambda _req, **_kwargs: {
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
        pin_build_lock(monkeypatch)
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
            lambda _req, **_kwargs: {
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
            lambda _req, **_kwargs: {
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
            lambda _req, **_kwargs: {
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
            lambda _req, **_kwargs: {
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
            lambda _req, **_kwargs: {
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
            lambda _req, **_kwargs: {
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


def test_no_progress_watchdog_triggers_terminal_stop_and_writes_event(monkeypatch: pytest.MonkeyPatch):
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
        events_path.write_text("", encoding="utf-8")
        monkeypatch.setattr(MODULE, "NO_PROGRESS_THRESHOLD_CYCLES", 3)
        monkeypatch.setattr(
            MODULE,
            "_run_controller_cycle",
            lambda _req, **_kwargs: {
                "ok": False,
                "status": "running",
                "terminal_reason": None,
                "last_cycle_number": 1,
                "events_path": str(events_path),
            },
        )
        monkeypatch.setattr(MODULE, "_dispatch_next_task", lambda req, plan, state, build, *_: {"ok": True, "status": "noop"})
        monkeypatch.setattr(MODULE, "_apply_handoff_updates", lambda *_args, **_kwargs: [])
        monkeypatch.setattr(MODULE, "_sync_task_state_from_evidence", lambda *_args, **_kwargs: [])

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
        assert out["status"] == "blocked_terminal"
        assert out.get("data", {}).get("terminal_reason") == "no_progress_watchdog"
        warning_codes = {item.get("code") for item in out.get("warnings", [])}
        assert "no_progress_watchdog_triggered" in warning_codes
        assert "no_progress_watchdog_stopped" in warning_codes

        watchdog_event_path = root / "reports" / "optimus-prime" / "planning" / "NO_PROGRESS_WATCHDOG_EVENT.json"
        assert watchdog_event_path.exists()
        watchdog_event = json.loads(watchdog_event_path.read_text(encoding="utf-8"))
        assert watchdog_event["action_taken"] == "stop_loop_and_workers"
        assert isinstance(watchdog_event.get("affected_task_ids"), list)

        lock_path = root / "reports" / "optimus-prime" / "planning" / "BUILD_LOOP.lock"
        assert not lock_path.exists()


def test_no_progress_watchdog_resets_on_task_state_delta(monkeypatch: pytest.MonkeyPatch):
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
        events_path.write_text("", encoding="utf-8")

        monkeypatch.setattr(MODULE, "NO_PROGRESS_THRESHOLD_CYCLES", 5)
        monkeypatch.setattr(
            MODULE,
            "_run_controller_cycle",
            lambda _req, **_kwargs: {
                "ok": False,
                "status": "running",
                "terminal_reason": None,
                "last_cycle_number": 1,
                "events_path": str(events_path),
            },
        )
        monkeypatch.setattr(MODULE, "_apply_handoff_updates", lambda *_args, **_kwargs: [])
        monkeypatch.setattr(MODULE, "_sync_task_state_from_evidence", lambda *_args, **_kwargs: [])

        dispatch_calls = {"count": 0}

        def fake_dispatch(_req, _plan, task_state, _build_state, *_):
            dispatch_calls["count"] += 1
            if dispatch_calls["count"] == 2:
                task = task_state["tasks"][0]
                task["status"] = "dev_in_progress"
                task["owner_slot"] = "dev-1"
                task["last_progress_at"] = MODULE.utc_now_iso()
            return {"ok": True, "status": "noop"}

        monkeypatch.setattr(MODULE, "_dispatch_next_task", fake_dispatch)

        out = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 4,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert out["status"] == "running_needs_resume"

        watchdog_state_path = root / "reports" / "optimus-prime" / "planning" / "NO_PROGRESS_WATCHDOG_STATE.json"
        watchdog_state = json.loads(watchdog_state_path.read_text(encoding="utf-8"))
        assert watchdog_state["triggered"] is False
        assert watchdog_state["consecutive_no_progress_cycles"] == 2
        assert watchdog_state["last_progress_at"] is not None

        progress_path = root / "reports" / "optimus-prime" / "planning" / "RUN_PROGRESS_LEDGER.jsonl"
        rows = [json.loads(line) for line in progress_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(rows) == 4
        assert any(row.get("progress_reason_codes") == ["task_state_fingerprint_changed"] for row in rows)


def test_watchdog_triggers_even_when_watchdog_state_write_fails(monkeypatch: pytest.MonkeyPatch):
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
        events_path.write_text("", encoding="utf-8")

        monkeypatch.setattr(MODULE, "NO_PROGRESS_THRESHOLD_CYCLES", 3)
        monkeypatch.setattr(
            MODULE,
            "_run_controller_cycle",
            lambda _req, **_kwargs: {
                "ok": False,
                "status": "running",
                "terminal_reason": None,
                "last_cycle_number": 1,
                "events_path": str(events_path),
            },
        )
        monkeypatch.setattr(MODULE, "_dispatch_next_task", lambda req, plan, state, build, *_: {"ok": True, "status": "noop"})
        monkeypatch.setattr(MODULE, "_apply_handoff_updates", lambda *_args, **_kwargs: [])
        monkeypatch.setattr(MODULE, "_sync_task_state_from_evidence", lambda *_args, **_kwargs: [])
        original_atomic = MODULE._atomic_write_json

        def flaky_atomic(path: Path, payload: dict):
            if path.name == "NO_PROGRESS_WATCHDOG_STATE.json":
                raise OSError("simulated watchdog state persist failure")
            return original_atomic(path, payload)

        monkeypatch.setattr(MODULE, "_atomic_write_json", flaky_atomic)

        out = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 6,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert out["status"] == "blocked_terminal"
        assert out.get("data", {}).get("terminal_reason") == "no_progress_watchdog"
        warning_codes = {item.get("code") for item in out.get("warnings", [])}
        assert "no_progress_watchdog_state_persist_failed" in warning_codes
        assert "no_progress_watchdog_triggered" in warning_codes
        assert not (root / "reports" / "optimus-prime" / "planning" / "BUILD_LOOP.lock").exists()


def test_watchdog_marker_write_failure_does_not_crash_and_returns_terminal_watchdog(monkeypatch: pytest.MonkeyPatch):
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
        events_path.write_text("", encoding="utf-8")

        monkeypatch.setattr(MODULE, "NO_PROGRESS_THRESHOLD_CYCLES", 3)
        monkeypatch.setattr(
            MODULE,
            "_run_controller_cycle",
            lambda _req, **_kwargs: {
                "ok": False,
                "status": "running",
                "terminal_reason": None,
                "last_cycle_number": 1,
                "events_path": str(events_path),
            },
        )
        monkeypatch.setattr(MODULE, "_dispatch_next_task", lambda req, plan, state, build, *_: {"ok": True, "status": "noop"})
        monkeypatch.setattr(MODULE, "_apply_handoff_updates", lambda *_args, **_kwargs: [])
        monkeypatch.setattr(MODULE, "_sync_task_state_from_evidence", lambda *_args, **_kwargs: [])
        def fail_marker_write(*_args, **_kwargs):
            raise OSError("simulated marker write failure")

        monkeypatch.setattr(MODULE, "_write_watchdog_stop_marker", fail_marker_write)

        out = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 6,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert out["status"] == "blocked_terminal"
        assert out.get("data", {}).get("terminal_reason") == "no_progress_watchdog"
        warning_codes = {item.get("code") for item in out.get("warnings", [])}
        assert "no_progress_watchdog_marker_write_failed" in warning_codes
        assert "no_progress_watchdog_stopped" in warning_codes
        assert not (root / "reports" / "optimus-prime" / "planning" / "BUILD_LOOP.lock").exists()


def test_watchdog_event_write_failure_does_not_crash_and_returns_terminal_watchdog(monkeypatch: pytest.MonkeyPatch):
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
        events_path.write_text("", encoding="utf-8")

        monkeypatch.setattr(MODULE, "NO_PROGRESS_THRESHOLD_CYCLES", 3)
        monkeypatch.setattr(
            MODULE,
            "_run_controller_cycle",
            lambda _req, **_kwargs: {
                "ok": False,
                "status": "running",
                "terminal_reason": None,
                "last_cycle_number": 1,
                "events_path": str(events_path),
            },
        )
        monkeypatch.setattr(MODULE, "_dispatch_next_task", lambda req, plan, state, build, *_: {"ok": True, "status": "noop"})
        monkeypatch.setattr(MODULE, "_apply_handoff_updates", lambda *_args, **_kwargs: [])
        monkeypatch.setattr(MODULE, "_sync_task_state_from_evidence", lambda *_args, **_kwargs: [])
        original_atomic = MODULE._atomic_write_json

        def flaky_atomic(path: Path, payload: dict):
            if path.name == "NO_PROGRESS_WATCHDOG_EVENT.json":
                raise OSError("simulated watchdog event write failure")
            return original_atomic(path, payload)

        monkeypatch.setattr(MODULE, "_atomic_write_json", flaky_atomic)

        out = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 6,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert out["status"] == "blocked_terminal"
        assert out.get("data", {}).get("terminal_reason") == "no_progress_watchdog"
        warning_codes = {item.get("code") for item in out.get("warnings", [])}
        assert "no_progress_watchdog_event_write_failed" in warning_codes
        assert "no_progress_watchdog_stopped" in warning_codes
        assert not (root / "reports" / "optimus-prime" / "planning" / "BUILD_LOOP.lock").exists()


def test_build_loop_normalizes_dead_running_registry_entry_before_dispatch(monkeypatch: pytest.MonkeyPatch):
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
        events_path.write_text("", encoding="utf-8")
        registry_path = root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text(
            json.dumps(
                {
                    "workers": [
                        {
                            "slot": "dev-1",
                            "session_state": "running",
                            "state": "running",
                            "dispatch_pid": 99887,
                            "active_task": None,
                        }
                    ]
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        monkeypatch.setattr(MODULE, "_pid_is_running", lambda _pid: False)
        monkeypatch.setattr(
            MODULE,
            "_run_controller_cycle",
            lambda _req, **_kwargs: {
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
        assert any(item.get("code") == "worker_registry_dead_pid_normalized" for item in out.get("warnings", []))
        registry_after = json.loads(registry_path.read_text(encoding="utf-8"))
        assert registry_after["workers"][0]["session_state"] == "not_running"


def test_build_allows_dispatch_with_warning_when_registry_recovery_fails(monkeypatch: pytest.MonkeyPatch):
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
        events_path.write_text("", encoding="utf-8")
        monkeypatch.setattr(
            MODULE,
            "_recover_unreadable_worker_registry",
            lambda _repo_root: [
                {
                    "code": "worker_registry_recovery_failed_dispatch_allowed",
                    "message": "simulated registry recovery failure; dispatch remains allowed",
                    "stage": "build_loop",
                }
            ],
        )
        monkeypatch.setattr(
            MODULE,
            "_run_controller_cycle",
            lambda _req, **_kwargs: {
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
        assert any(
            item.get("code") == "worker_registry_recovery_failed_dispatch_allowed"
            for item in out.get("warnings", [])
        )
