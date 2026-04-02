import importlib.util
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.quality import lane_b_quality_gate as QUALITY_GATE


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
    snapshot_script = root / "skills" / "minimal-rate-snapshot" / "scripts" / "minimal_rate_snapshot.py"
    snapshot_script.parent.mkdir(parents=True, exist_ok=True)
    snapshot_script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import json",
                "payload = [",
                "  {'alias': 'codex', 'codex_home': '/tmp/.codex', 'gated': False, 'primary_window': {'used_percent': 20, 'reset_at': 1773529474}, 'secondary_window': {'used_percent': 20, 'reset_at': 1774002467}},",
                "  {'alias': 'codex-second', 'codex_home': '/tmp/.codex-second', 'gated': False, 'primary_window': {'used_percent': 20, 'reset_at': 1773529474}, 'secondary_window': {'used_percent': 20, 'reset_at': 1774002467}},",
                "]",
                "print(json.dumps(payload, indent=2))",
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
                "    return {",
                "        'artifact_path': path,",
                "        'content_type': content_type,",
                "        'content': content,",
                "        'checksum_sha256': checksum(content_type, content),",
                "    }",
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
                "    {'task_id': 'TASK-001', 'title': 'Implement core workflow', 'phase_id': 'phase-1', 'lane_id': 'phase-1/lane-a', 'task_kind': 'implementation', 'status': 'pending', 'verification_contract': {'mode': 'tdd_red', 'expected_failure_reason_codes': ['tdd_expected_failure_observed'], 'infra_failure_reason_codes': ['verification_environment_error', 'verification_command_target_missing']}, 'requirement_ids': ['REQ-001'], 'depends_on': [], 'must_haves': ['core path'], 'verify_commands': ['python3 -m pytest'], 'gaps_that_need_patching': []},",
                "    {'task_id': 'TASK-002', 'title': 'Implement quality gates', 'phase_id': 'phase-1', 'lane_id': 'phase-1/lane-b', 'task_kind': 'implementation', 'status': 'pending', 'verification_contract': {'mode': 'tdd_red', 'expected_failure_reason_codes': ['tdd_expected_failure_observed'], 'infra_failure_reason_codes': ['verification_environment_error', 'verification_command_target_missing']}, 'requirement_ids': ['REQ-002'], 'depends_on': ['TASK-001'], 'must_haves': ['quality path'], 'verify_commands': ['python3 -m pytest'], 'gaps_that_need_patching': []},",
                "    {'task_id': 'TASK-003', 'title': 'Implement rollout ops', 'phase_id': 'phase-1', 'lane_id': 'phase-1/lane-c', 'task_kind': 'implementation', 'status': 'pending', 'verification_contract': {'mode': 'tdd_red', 'expected_failure_reason_codes': ['tdd_expected_failure_observed'], 'infra_failure_reason_codes': ['verification_environment_error', 'verification_command_target_missing']}, 'requirement_ids': ['REQ-003'], 'depends_on': ['TASK-002'], 'must_haves': ['ops path'], 'verify_commands': ['python3 -m pytest'], 'gaps_that_need_patching': []},",
                "]",
                "plan_packets = {",
                "    'schema_version': '1.0',",
                "    'generated_at': '2026-01-01T00:00:00Z',",
                "    'plan_id': plan_id,",
                "    'phase': 'multi-phase',",
                "    'phases': [{'phase_id': 'phase-1', 'task_ids': ['TASK-001', 'TASK-002', 'TASK-003'], 'depends_on_phase_ids': [], 'entry_criteria': ['phase_dependencies_done'], 'exit_criteria': ['all_tasks_review_done', 'verify_commands_passed', 'uat_matrix_passed', 'zero_open_gaps']}],",
                "    'requirements': requirements,",
                "    'lane_base_branches': {'phase-1/lane-a': 'lane-phase-1-a', 'phase-1/lane-b': 'lane-phase-1-b', 'phase-1/lane-c': 'lane-phase-1-c'},",
                "    'tasks': tasks,",
                "    'depends_on': [],",
                "    'must_haves': ['core path', 'quality path', 'ops path'],",
                "    'verify_commands': ['python3 -m pytest'],",
                "}",
                "plan_check = {'schema_version': '1.0', 'passed': True, 'checks': [{'id': 'requirement_coverage', 'passed': True}], 'coverage': {'requirements_total': 3, 'requirements_covered': 3, 'missing_requirement_ids': []}, 'dependency_graph': {'nodes': ['TASK-001', 'TASK-002', 'TASK-003'], 'edges': [{'from': 'TASK-001', 'to': 'TASK-002'}, {'from': 'TASK-002', 'to': 'TASK-003'}], 'cycle_detected': False, 'valid': True}, 'verify_contract_completeness': True, 'phase_traceability': True, 'blocking_errors': []}",
                "task_state = {'schema_version': '1.0', 'plan_id': plan_id, 'updated_at': '2026-01-01T00:00:00Z', 'tasks': []}",
                "for task in tasks:",
                "    task_id = task['task_id']",
                "    evidence_ref = f'reports/optimus-prime/planning/evidence/{task_id}/TASK_EVIDENCE.json'",
                "    task_state['tasks'].append({'task_id': task_id, 'phase_id': task['phase_id'], 'lane_id': task['lane_id'], 'task_kind': task['task_kind'], 'requirement_ids': task['requirement_ids'], 'verification_contract': task['verification_contract'], 'status': 'pending', 'owner_slot': None, 'dispatch_thread_id': None, 'last_progress_at': None, 'attempts': {'dev': 0, 'test': 0, 'review': 0}, 'evidence': {'task_evidence_ref': evidence_ref, 'dev_ready_evidence_ref': evidence_ref, 'verify_results': [], 'uat_results': []}, 'gaps_that_need_patching': [], 'blockers': [], 'last_handoff_outcome': {'status': None, 'reason_codes': [], 'timestamp': None}, 'blocking_source': 'none', 'gapfix_state': {'active_batch_id': None, 'active': False, 'target_gap_stage': None, 'consumed_gap_ids': [], 'batch_started_cycle': None, 'batch_last_updated_at': None}, 'progress_watchdog': {'started': False, 'first_dispatched_cycle': None, 'task_started_cycle': None, 'last_forward_progress_cycle': None, 'consecutive_no_forward_progress_cycles': 0, 'threshold_cycles': 25, 'triggered': False, 'triggered_at': None}})",
                "",
                "state_json = {'schema_version': '1.0', 'initialized_at': '2026-01-01T00:00:00Z', 'updated_at': '2026-01-01T00:00:00Z', 'mission': 'inline:Build MyBoard', 'scope': 'inline:Board workflow', 'mission_source': {'mode': 'inline', 'value': 'Build MyBoard', 'path': None, 'display': 'Build MyBoard'}, 'scope_source': {'mode': 'inline', 'value': 'Board workflow', 'path': None, 'display': 'Board workflow'}, 'constraints': [], 'requirements': requirements, 'map_fingerprint': 'map-test', 'repo_fingerprint': 'repo-test', 'baseline_ready': True, 'plan_ready': True, 'plan_id': plan_id, 'build_ready': True}",
                "state_md = '# STATE\\\\n\\\\n- baseline_ready: true\\\\n- plan_ready: true\\\\n- build_ready: true\\\\n'",
                "gaps = {'schema_version': '1.0', 'plan_id': plan_id, 'updated_at': '2026-01-01T00:00:00Z', 'gaps': []}",
                "closure = {'schema_version': '1.0', 'plan_id': plan_id, 'generated_at': '2026-01-01T00:00:00Z', 'tasks': []}",
                "test_contract = '# TEST CONTRACT\\\\n'",
                "uat_matrix = '# PLAYWRIGHT UAT MATRIX\\\\n'",
                "verification = '# VERIFICATION\\\\n'",
                "uat = '# UAT\\\\n'",
                "",
                "rows = [",
                "    row('PLAN_PACKETS.json', 'json', plan_packets),",
                "    row('PLAN_CHECK.json', 'json', plan_check),",
                "    row('TASK_EXECUTION_STATE.json', 'json', task_state),",
                "    row('GAPS.json', 'json', gaps),",
                "    row('GAP_CLOSURE_PLAN_PACKETS.json', 'json', closure),",
                "    row('TEST_CONTRACT.md', 'text', test_contract),",
                "    row('PLAYWRIGHT_UAT_MATRIX.md', 'text', uat_matrix),",
                "    row('VERIFICATION.md', 'text', verification),",
                "    row('UAT.md', 'text', uat),",
                "    row('STATE.json', 'json', state_json),",
                "    row('STATE.md', 'text', state_md),",
                "]",
                "for task in tasks:",
                "    task_id = task['task_id']",
                "    ev = {'schema_version': '1.0', 'plan_id': plan_id, 'phase_id': task['phase_id'], 'task_id': task_id, 'task_kind': task['task_kind'], 'requirement_ids': task['requirement_ids'], 'updated_at': '2026-01-01T00:00:00Z', 'dev': {'status': 'queued', 'checks': [], 'verify_results': [], 'dev_ready': False, 'blockers': [], 'artifacts': []}, 'test': {'status': 'queued', 'checks': [], 'verify_results': [], 'uat_results': [], 'blockers': [], 'artifacts': []}, 'review': {'status': 'queued', 'decision': None, 'blockers': [], 'artifacts': []}, 'summary': {'result': 'blocked', 'expectation': 'expect_fail', 'expectation_met': False, 'failure_class': 'none', 'reason_codes': ['not_started']}}",
                "    rows.append(row(f'evidence/{task_id}/TASK_EVIDENCE.json', 'json', ev))",
                "",
                "bundle_path.write_text('\\n'.join(json.dumps(item) for item in rows) + '\\n', encoding='utf-8')",
                "if validator_match:",
                "    subprocess.run(validator_match.group(1), shell=True, check=False)",
                "if last_message is not None:",
                "    last_message.parent.mkdir(parents=True, exist_ok=True)",
                "    last_message.write_text('planner complete\\\\n', encoding='utf-8')",
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


def write_strategy_manifest(root: Path) -> Path:
    manifest_path = root / "strategy" / "STRATEGY_MANIFEST.md"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        "\n".join(
            [
                "# Project Context",
                "Build strategy for this repo.",
                "",
                "# Scan Files",
                "- README.md",
                "",
                "# Scan Directories",
                "- docs",
                "",
                "# Related Projects",
                "- ../shared-lib",
                "",
                "# Questions And Priorities",
                "- What should planner optimize first?",
                "",
                "# Ignore",
                "- strategy/current",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest_path


def test_emit_build_progress_prints_only_on_tty(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        req = MODULE.parse_request({"command": "/op-build", "repo_root": str(root)})
        monkeypatch.setattr(MODULE.sys.stdout, "isatty", lambda: True)
        MODULE._emit_build_progress(req, "hello")
        out = capsys.readouterr().out
        assert "[op-build " in out
        assert "hello" in out

        monkeypatch.setattr(MODULE.sys.stdout, "isatty", lambda: False)
        MODULE._emit_build_progress(req, "hidden")
        out = capsys.readouterr().out
        assert out == ""


def test_summarize_watchdog_findings_includes_reasons_and_warning_codes():
    summary = MODULE._summarize_watchdog_findings(
        progress_delta=False,
        progress_reason_codes=["no_task_state_delta"],
        watchdog_state={
            "consecutive_no_progress_cycles": 3,
            "threshold_cycles": 25,
        },
        cycle_warnings=[
            {"code": "no_progress_watchdog_warning"},
            {"code": "dispatch_plan_no_assignments"},
        ],
    )
    assert "progress=stalled" in summary
    assert "no_progress=3/25" in summary
    assert "reasons=no_task_state_delta" in summary
    assert "warnings=no_progress_watchdog_warning" in summary


def test_task_progress_watchdog_skips_dormant_tasks_until_first_dispatch():
    task_state = {
        "tasks": [
            {
                "task_id": "TASK-001",
                "phase_id": "phase-1",
                "status": "pending",
                "owner_slot": None,
                "blocking_source": "none",
                "evidence": {"task_evidence_ref": "reports/optimus-prime/planning/evidence/TASK-001/TASK_EVIDENCE.json"},
                "gaps_that_need_patching": [],
                "progress_watchdog": {
                    "started": False,
                    "first_dispatched_cycle": 0,
                    "task_started_cycle": 0,
                    "last_forward_progress_cycle": 0,
                    "consecutive_no_forward_progress_cycles": 17,
                    "threshold_cycles": 25,
                    "triggered": False,
                    "triggered_at": None,
                },
            }
        ]
    }
    build_state = {"last_cycle": 18}
    warnings = MODULE._apply_task_progress_watchdog(task_state, build_state, plan_id="plan-test")
    assert warnings == []
    watchdog = task_state["tasks"][0]["progress_watchdog"]
    assert watchdog["started"] is False
    assert watchdog["consecutive_no_forward_progress_cycles"] == 17
    assert task_state["tasks"][0]["status"] == "pending"


def test_mark_task_watchdog_started_on_first_dispatch():
    task = {
        "task_id": "TASK-001",
        "status": "pending",
        "progress_watchdog": {
            "started": False,
            "first_dispatched_cycle": 0,
            "task_started_cycle": 0,
            "last_forward_progress_cycle": 0,
            "consecutive_no_forward_progress_cycles": 5,
            "threshold_cycles": 25,
            "triggered": True,
            "triggered_at": "2026-03-03T00:00:00Z",
        },
    }
    build_state = {"last_cycle": 9}
    MODULE._mark_task_watchdog_started(task, build_state)
    watchdog = task["progress_watchdog"]
    assert watchdog["started"] is True
    assert watchdog["first_dispatched_cycle"] == 9
    assert watchdog["task_started_cycle"] == 9
    assert watchdog["consecutive_no_forward_progress_cycles"] == 0
    assert watchdog["triggered"] is False
    assert watchdog["triggered_at"] is None


def planner_checksum(content_type: str, content: object) -> str:
    if content_type == "json":
        payload = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    else:
        payload = str(content).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def planner_row(path: str, content_type: str, content: object) -> dict[str, object]:
    return {
        "artifact_path": path,
        "content_type": content_type,
        "content": content,
        "checksum_sha256": planner_checksum(content_type, content),
    }


def write_planner_bundle(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(item) for item in rows) + "\n", encoding="utf-8")


def write_profile_selection(
    root: Path,
    *,
    profiles: list[dict[str, str]] | None = None,
    selected_aliases: list[str] | None = None,
) -> Path:
    planning = root / "reports" / "optimus-prime" / "planning"
    planning.mkdir(parents=True, exist_ok=True)
    if profiles is None:
        codex_home = Path(os.environ.get("CODEX_HOME", str(root.parent / ".codex"))).expanduser().resolve()
        auth_path = codex_home / "auth.json"
        profiles = [
            {
                "alias": "codex",
                "codex_home": str(codex_home),
                "auth_path": str(auth_path),
            }
        ]
    if selected_aliases is None:
        selected_aliases = [item["alias"] for item in profiles]
    payload = {
        "schema_version": "1.0",
        "detected_at": "2026-01-01T00:00:00Z",
        "detection_root": str(Path(profiles[0]["codex_home"]).parent if profiles else root.parent),
        "profiles": profiles,
        "selected_aliases": selected_aliases,
        "selection_policy": "initialize_autodetect",
        "notes": [],
    }
    path = planning / "PROFILE_SELECTION.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


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
            "op-simple-build": "op-simple-build",
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



def test_op_plan_requires_override_when_planning_artifacts_exist():
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
        with pytest.raises(MODULE.OpError) as exc_info:
            run_payload({"command": "/op-plan", "repo_root": str(root)})
        assert exc_info.value.code == "override_required"

        out = run_payload(
            {
                "command": "/op-plan",
                "repo_root": str(root),
                "override_old_plan": True,
            }
        )
        assert out["ok"] is True
        assert out["status"] == "completed"



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


def test_command_strategy_fails_when_manifest_missing():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)

        out = run_payload(
            {
                "command": "/op-strategy",
                "repo_root": str(root),
            }
        )

        assert out["ok"] is False
        assert out["status"] == "blocked_preflight"
        assert any(item.get("code") == "strategy_manifest_missing" for item in out.get("errors", []))


def test_command_strategy_generates_manifest_driven_artifacts(
    monkeypatch: pytest.MonkeyPatch,
):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        write_strategy_manifest(root)

        def fake_run_strategy(
            *,
            repo_root: Path,
            manifest: str | None = None,
            manifest_file: str | None = None,
            emit=None,
            codex_home=None,
        ):
            del codex_home
            assert manifest is None
            if emit:
                emit("fake strategy generation complete")
            packet_path = repo_root / "strategy" / "current" / "strategy_packet.md"
            summary_path = repo_root / "strategy" / "current" / "STRATEGY_SUMMARY.md"
            packet_path.parent.mkdir(parents=True, exist_ok=True)
            packet_path.write_text("# Strategic Summary\n\nGenerated.\n", encoding="utf-8")
            summary_path.write_text("# Summary\n\nGenerated.\n", encoding="utf-8")
            manifest_path = MODULE.strategy_runner.resolve_strategy_manifest_path(repo_root, manifest_file)
            return MODULE.strategy_runner.StrategyRunResult(
                manifest_ref=str(manifest_path),
                packet_path=packet_path.resolve(),
                summary_path=summary_path.resolve(),
                artifacts=[str(manifest_path), str(packet_path.resolve()), str(summary_path.resolve())],
            )

        monkeypatch.setattr(MODULE.strategy_runner, "run_strategy", fake_run_strategy)

        out = run_payload(
            {
                "command": "/op-strategy",
                "repo_root": str(root),
            }
        )

        assert out["ok"] is True
        assert out["status"] == "completed"
        assert out["data"]["strategy"]["status"] == "completed"
        assert (root / "strategy" / "current" / "strategy_packet.md").exists()
        assert (root / "strategy" / "current" / "STRATEGY_SUMMARY.md").exists()


def test_initialize_skips_strategy_when_manifest_missing(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        monkeypatch.setattr(
            MODULE.strategy_runner,
            "run_strategy",
            lambda **_kwargs: (_ for _ in ()).throw(AssertionError("strategy runner should not be called")),
        )

        out = run_payload(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )

        assert out["ok"] is True
        assert out["data"]["strategy"]["status"] == "skipped"
        assert out["data"]["strategy"]["reason"] == "manifest_missing"


def test_initialize_warns_when_existing_strategy_artifacts_will_be_reused(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        strategy_current = root / "strategy" / "current"
        strategy_current.mkdir(parents=True, exist_ok=True)
        (strategy_current / "strategy_packet.md").write_text("# Packet\n", encoding="utf-8")
        (strategy_current / "STRATEGY_SUMMARY.md").write_text("# Summary\n", encoding="utf-8")
        messages: list[str] = []

        monkeypatch.setattr(
            MODULE.strategy_runner,
            "run_strategy",
            lambda **_kwargs: (_ for _ in ()).throw(AssertionError("strategy runner should not be called")),
        )
        monkeypatch.setattr(MODULE, "_emit_build_progress", lambda _req, message: messages.append(message))

        out = run_payload(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )

        assert out["ok"] is True
        assert any(item.get("code") == "strategy_artifacts_present_without_regeneration" for item in out.get("warnings", []))
        assert any("existing strategy artifacts will still be considered by planner" in message for message in messages)


def test_initialize_auto_runs_strategy_when_manifest_exists(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        write_strategy_manifest(root)
        seen: dict[str, object] = {}

        def fake_run_strategy(
            *,
            repo_root: Path,
            manifest: str | None = None,
            manifest_file: str | None = None,
            emit=None,
            codex_home=None,
        ):
            del codex_home
            seen["called"] = True
            seen["manifest"] = manifest
            seen["manifest_file"] = manifest_file
            if emit:
                emit("strategy generated for initialize")
            packet_path = repo_root / "strategy" / "current" / "strategy_packet.md"
            summary_path = repo_root / "strategy" / "current" / "STRATEGY_SUMMARY.md"
            packet_path.parent.mkdir(parents=True, exist_ok=True)
            packet_path.write_text("# Strategic Summary\n\nInit packet.\n", encoding="utf-8")
            summary_path.write_text("# Summary\n\nInit summary.\n", encoding="utf-8")
            manifest_path = MODULE.strategy_runner.resolve_strategy_manifest_path(repo_root, manifest_file)
            return MODULE.strategy_runner.StrategyRunResult(
                manifest_ref=str(manifest_path),
                packet_path=packet_path.resolve(),
                summary_path=summary_path.resolve(),
                artifacts=[str(manifest_path), str(packet_path.resolve()), str(summary_path.resolve())],
            )

        monkeypatch.setattr(MODULE.strategy_runner, "run_strategy", fake_run_strategy)

        out = run_payload(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )

        assert out["ok"] is True
        assert seen["called"] is True
        assert seen["manifest"] is None
        assert seen["manifest_file"] is None
        assert out["data"]["strategy"]["status"] == "completed"
        assert (root / "strategy" / "current" / "strategy_packet.md").exists()
        assert (root / "strategy" / "current" / "STRATEGY_SUMMARY.md").exists()


def test_initialize_auto_runs_strategy_when_inline_manifest_is_provided(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        seen: dict[str, object] = {}

        def fake_run_strategy(
            *,
            repo_root: Path,
            manifest: str | None = None,
            manifest_file: str | None = None,
            emit=None,
            codex_home=None,
        ):
            del codex_home
            seen["called"] = True
            seen["manifest"] = manifest
            seen["manifest_file"] = manifest_file
            if emit:
                emit("strategy generated from inline manifest")
            packet_path = repo_root / "strategy" / "current" / "strategy_packet.md"
            summary_path = repo_root / "strategy" / "current" / "STRATEGY_SUMMARY.md"
            packet_path.parent.mkdir(parents=True, exist_ok=True)
            packet_path.write_text("# Strategic Summary\n\nInline packet.\n", encoding="utf-8")
            summary_path.write_text("# Summary\n\nInline summary.\n", encoding="utf-8")
            return MODULE.strategy_runner.StrategyRunResult(
                manifest_ref=MODULE.strategy_runner.INLINE_STRATEGY_MANIFEST_LABEL,
                packet_path=packet_path.resolve(),
                summary_path=summary_path.resolve(),
                artifacts=[str(packet_path.resolve()), str(summary_path.resolve())],
            )

        monkeypatch.setattr(MODULE.strategy_runner, "run_strategy", fake_run_strategy)

        out = run_payload(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
                "strategy_manifest": "# Inline Manifest\n\nRead README first.\n",
            }
        )

        assert out["ok"] is True
        assert seen["called"] is True
        assert seen["manifest"] == "# Inline Manifest\n\nRead README first."
        assert seen["manifest_file"] is None
        assert out["data"]["strategy"]["manifest_path"] == MODULE.strategy_runner.INLINE_STRATEGY_MANIFEST_LABEL


def test_initialize_fails_when_explicit_strategy_manifest_is_missing():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)

        out = run_payload(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
                "strategy_manifest_file": "strategy/MISSING.md",
            }
        )

        assert out["ok"] is False
        assert out["status"] == "blocked_preflight"
        assert any(item.get("code") == "strategy_manifest_missing" for item in out.get("errors", []))


def test_initialize_skip_strategy_bypasses_strategy_runner(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        write_strategy_manifest(root)
        monkeypatch.setattr(
            MODULE.strategy_runner,
            "run_strategy",
            lambda **_kwargs: (_ for _ in ()).throw(AssertionError("strategy runner should not be called")),
        )

        out = run_payload(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
                "skip_strategy": True,
            }
        )

        assert out["ok"] is True
        assert out["data"]["strategy"]["status"] == "skipped"
        assert out["data"]["strategy"]["reason"] == "skip_strategy_requested"


def test_profile_detection_accepts_valid_codex_dirs_only():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        profile_root = Path(os.environ["CODEX_HOME"]).expanduser().resolve().parent
        (profile_root / ".codex-second").mkdir(parents=True, exist_ok=True)
        (profile_root / ".codex-second" / "auth.json").write_text("{}\n", encoding="utf-8")
        (profile_root / ".codex-invalid").mkdir(parents=True, exist_ok=True)
        (profile_root / ".codexinvalid-noauth").mkdir(parents=True, exist_ok=True)

        payload = MODULE._detect_profile_selection_payload()
        aliases = payload["selected_aliases"]
        assert "codex" in aliases
        assert "codex-second" in aliases
        assert "codex-invalid" not in aliases
        assert "codexinvalid-noauth" not in aliases


def test_profile_detection_allows_alternate_profiles_without_default():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        profile_root = root.parent / "profiles"
        profile_root.mkdir(parents=True, exist_ok=True)
        alt_one = profile_root / ".codex-second"
        alt_two = profile_root / ".codexslobodan"
        alt_one.mkdir(parents=True, exist_ok=True)
        alt_two.mkdir(parents=True, exist_ok=True)
        (alt_one / "auth.json").write_text("{}\n", encoding="utf-8")
        (alt_two / "auth.json").write_text("{}\n", encoding="utf-8")
        os.environ["CODEX_HOME"] = str(profile_root / ".codex-missing")

        payload = MODULE._detect_profile_selection_payload()
        assert payload["selected_aliases"] == ["codex-second", "codexslobodan"]
        assert any("default .codex profile not found" in str(item) for item in payload.get("notes", []))


def test_initialize_writes_profile_selection_and_state_refs():
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
        selection_path = root / "reports" / "optimus-prime" / "planning" / "PROFILE_SELECTION.json"
        assert selection_path.exists()
        selection = json.loads(selection_path.read_text(encoding="utf-8"))
        assert selection["selection_policy"] == "initialize_autodetect"
        assert isinstance(selection.get("selected_aliases"), list) and selection["selected_aliases"]

        state_path = root / "reports" / "optimus-prime" / "planning" / "STATE.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        assert state["profile_aliases"] == selection["selected_aliases"]
        assert state["profile_selection_ref"] == str(selection_path.resolve())


def test_initialize_blocks_when_no_profiles_detected():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        codex_home = Path(os.environ["CODEX_HOME"]).expanduser().resolve()
        auth_file = codex_home / "auth.json"
        if auth_file.exists():
            auth_file.unlink()
        empty_root = root.parent / "empty-profiles"
        empty_root.mkdir(parents=True, exist_ok=True)
        os.environ["CODEX_HOME"] = str(empty_root / ".codex")

        with pytest.raises(MODULE.OpError) as exc_info:
            run_payload(
                {
                    "command": "/op-initialize",
                    "repo_root": str(root),
                    "mission": "Build MyBoard",
                    "scope": "Board workflow",
                }
            )
        assert exc_info.value.code == "profile_detection_none_found"


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
            profile_selection: dict | None = None,
        ):
            calls.append(repo_root)
            assert stage == "initialize"
            assert force_refresh is False
            assert emit_success_warning is True
            assert isinstance(profile_selection, dict)
            assert profile_selection.get("selected_aliases")
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


def test_initialize_seeds_rate_registry_before_plan(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        call_order: list[str] = []

        def fake_seed(
            repo_root: Path,
            *,
            stage: str = "build_loop",
            force_refresh: bool = False,
            emit_success_warning: bool = True,
            profile_selection: dict | None = None,
        ):
            assert repo_root.resolve() == root.resolve()
            assert stage == "initialize"
            call_order.append("seed")
            return []

        def fake_plan(_req):
            call_order.append("plan")
            return {
                "ok": True,
                "status": "completed",
                "warnings": [],
                "artifacts": [],
                "data": {"plan_ready": True},
            }

        monkeypatch.setattr(MODULE, "_seed_rate_registry_if_missing", fake_seed)
        monkeypatch.setattr(MODULE, "command_plan", fake_plan)
        out = run_payload(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )

        assert out["ok"] is True
        assert call_order == ["seed", "plan"]


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


def test_select_planner_profile_from_rate_registry_uses_highest_weekly_not_5h_gated():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        planning_root = root / "reports" / "optimus-prime" / "planning"
        planning_root.mkdir(parents=True, exist_ok=True)

        selection_path = planning_root / "PROFILE_SELECTION.json"
        selection_payload = {
            "schema_version": "1.0",
            "profiles": [
                {"alias": "codex", "codex_home": "/tmp/codex", "auth_path": "/tmp/codex/auth.json"},
                {"alias": "codex-second", "codex_home": "/tmp/codex-second", "auth_path": "/tmp/codex-second/auth.json"},
                {"alias": "codex-third", "codex_home": "/tmp/codex-third", "auth_path": "/tmp/codex-third/auth.json"},
            ],
            "selected_aliases": ["codex", "codex-second", "codex-third"],
            "selection_policy": "initialize_autodetect",
        }
        selection_path.write_text(json.dumps(selection_payload, indent=2) + "\n", encoding="utf-8")

        rate_path = root / "reports" / "optimus-prime" / "PROFILE_RATE_REGISTRY.json"
        rate_path.parent.mkdir(parents=True, exist_ok=True)
        rate_payload = {
            "profiles": {
                "codex": {
                    "recommended_action": "continue",
                    "five_hour": {"remaining_percent": 95},
                    "weekly": {"remaining_percent": 99},
                },
                "codex-second": {
                    "recommended_action": "continue",
                    "five_hour": {"remaining_percent": 90},
                    "weekly": {"remaining_percent": 70},
                },
                "codex-third": {
                    "recommended_action": "continue",
                    "five_hour": {"remaining_percent": 0.5},
                    "weekly": {"remaining_percent": 95},
                },
            }
        }
        rate_path.write_text(json.dumps(rate_payload, indent=2) + "\n", encoding="utf-8")

        alias, home = MODULE._select_planner_profile_from_rate_registry(root, stage="plan")

        assert alias == "codex-second"
        assert home == "/tmp/codex-second"


def test_select_planner_profile_from_rate_registry_falls_back_on_invalid_data():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        planning_root = root / "reports" / "optimus-prime" / "planning"
        planning_root.mkdir(parents=True, exist_ok=True)

        selection_path = planning_root / "PROFILE_SELECTION.json"
        selection_payload = {
            "schema_version": "1.0",
            "profiles": [
                {"alias": "codex-second", "codex_home": "/tmp/codex-second", "auth_path": "/tmp/codex-second/auth.json"},
            ],
            "selected_aliases": ["codex-second"],
            "selection_policy": "initialize_autodetect",
        }
        selection_path.write_text(json.dumps(selection_payload, indent=2) + "\n", encoding="utf-8")

        rate_path = root / "reports" / "optimus-prime" / "PROFILE_RATE_REGISTRY.json"
        rate_path.parent.mkdir(parents=True, exist_ok=True)
        rate_path.write_text(json.dumps({"profiles": "bad"}, indent=2) + "\n", encoding="utf-8")

        alias, home = MODULE._select_planner_profile_from_rate_registry(root, stage="plan")
        assert alias is None
        assert home is None


def test_planner_generation_passes_selected_profile_home_to_codex_exec(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        req = MODULE.parse_request(
            {
                "command": "/op-plan",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        mission_source, scope_source = MODULE._resolve_mission_scope_sources(req, stage="plan", required=False)
        monkeypatch.setattr(
            MODULE,
            "_select_planner_profile_from_rate_registry",
            lambda *_args, **_kwargs: ("codex-second", "/tmp/codex-second"),
        )
        captured: dict[str, object] = {}

        def fake_run_codex_exec(**kwargs: object) -> int:
            captured["codex_home"] = kwargs.get("codex_home")
            raise OSError("simulated launch failure")

        monkeypatch.setattr(MODULE, "run_codex_exec", fake_run_codex_exec)

        with pytest.raises(MODULE.OpError) as exc_info:
            MODULE._run_llm_plan_generation(
                req,
                mission_source=mission_source,
                scope_source=scope_source,
            )

        assert exc_info.value.code == "planner_execution_failed"
        assert captured.get("codex_home") == "/tmp/codex-second"


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
                "override_old_plan": True,
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
                "override_old_plan": True,
            }
        )
        assert len(calls) == 1

        run_payload(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
                "override_old_plan": True,
            }
        )
        # /op-initialize invokes helper directly and once again via /op-new-project.
        assert len(calls) == 3


def test_op_build_defaults_use_watcher_driven_cycle_release():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        req = MODULE.parse_request({"command": "/op-build", "repo_root": str(root)})
        assert req.sleep_minutes == 0.0
        assert req.start_policy == "auto"
        assert req.enable_artifact_fan_in is False


def test_op_build_request_accepts_enable_artifact_fan_in_override():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        req = MODULE.parse_request(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "enable_artifact_fan_in": True,
            }
        )
        assert req.enable_artifact_fan_in is True


def test_parse_request_accepts_strategy_manifest_and_skip_strategy():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        req = MODULE.parse_request(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
                "strategy_manifest_file": "strategy/custom.md",
                "skip_strategy": True,
            }
        )
        assert req.strategy_manifest is None
        assert req.strategy_manifest_file == "strategy/custom.md"
        assert req.skip_strategy is True


def test_parse_request_accepts_inline_strategy_manifest():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        req = MODULE.parse_request(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
                "strategy_manifest": "# Inline Manifest\n\nRead README first.\n",
            }
        )
        assert req.strategy_manifest == "# Inline Manifest\n\nRead README first."
        assert req.strategy_manifest_file is None


def test_parse_request_accepts_private_publish_flags_for_initialize():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        req = MODULE.parse_request(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
                "publish_private_repo": True,
                "github_owner": "slobodanmargetic988",
                "github_repo_name": "myboard-private",
            }
        )
        assert req.publish_private_repo is True
        assert req.github_owner == "slobodanmargetic988"
        assert req.github_repo_name == "myboard-private"


def test_parse_request_rejects_github_publish_details_without_publish_flag():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        with pytest.raises(MODULE.OpError, match="require publish_private_repo=true"):
            MODULE.parse_request(
                {
                    "command": "/op-initialize",
                    "repo_root": str(root),
                    "mission": "Build MyBoard",
                    "scope": "Board workflow",
                    "github_owner": "slobodanmargetic988",
                }
            )


def test_parse_request_rejects_inline_and_file_strategy_manifest_together():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        with pytest.raises(MODULE.OpError, match="provide strategy_manifest or strategy_manifest_file, not both"):
            MODULE.parse_request(
                {
                    "command": "/op-initialize",
                    "repo_root": str(root),
                    "mission": "Build MyBoard",
                    "scope": "Board workflow",
                    "strategy_manifest": "# Inline Manifest\n",
                    "strategy_manifest_file": "strategy/custom.md",
                }
            )


def test_op_simple_build_defaults_parallel_workers_and_boss_settings():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        req = MODULE.parse_request({"command": "/op-simple-build", "repo_root": str(root)})
        assert req.sleep_minutes == 0.0
        assert req.max_parallel_workers == 8
        assert req.boss_model == "gpt-5.3-codex"
        assert req.boss_reasoning_effort == "xhigh"


def test_op_simple_build_accepts_boss_model_and_reasoning_override():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        req = MODULE.parse_request(
            {
                "command": "/op-simple-build",
                "repo_root": str(root),
                "boss_model": "gpt-5.4-codex-experimental",
                "boss_reasoning_effort": "medium",
            }
        )
        assert req.boss_model == "gpt-5.4-codex-experimental"
        assert req.boss_reasoning_effort == "medium"


def test_op_simple_build_invalid_boss_model_and_reasoning_fall_back_to_defaults():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        req = MODULE.parse_request(
            {
                "command": "/op-simple-build",
                "repo_root": str(root),
                "boss_model": "not-a-real-model",
                "boss_reasoning_effort": "ultra",
            }
        )
        assert req.boss_model == "gpt-5.3-codex"
        assert req.boss_reasoning_effort == "xhigh"


def test_op_simple_build_accepts_run_base_source_branch_override():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        req = MODULE.parse_request(
            {
                "command": "/op-simple-build",
                "repo_root": str(root),
                "run_base_source_branch": "op-simple-canary-prev",
            }
        )
        assert req.run_base_source_branch == "op-simple-canary-prev"


def test_op_build_accepts_start_policy_override():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        req = MODULE.parse_request(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "start_policy": "resume",
            }
        )
        assert req.start_policy == "resume"


def test_parse_request_rejects_start_policy_on_non_build_command():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        with pytest.raises(MODULE.OpError, match="start_policy is only supported for /op-build"):
            MODULE.parse_request(
                {
                    "command": "/op-resume",
                    "repo_root": str(root),
                    "start_policy": "resume",
                }
            )


def test_parse_request_rejects_invalid_start_policy():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        with pytest.raises(MODULE.OpError, match="start_policy must be one of"):
            MODULE.parse_request(
                {
                    "command": "/op-build",
                    "repo_root": str(root),
                    "start_policy": "sideways",
                }
            )


def test_parse_request_rejects_resume_start_policy_with_fresh_run_flags():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        with pytest.raises(MODULE.OpError, match="conflicts with fresh-run flags"):
            MODULE.parse_request(
                {
                    "command": "/op-build",
                    "repo_root": str(root),
                    "start_policy": "resume",
                    "mission": "Build a better thing",
                    "scope": "Fresh scope",
                }
            )


def test_op_simple_build_executor_defaults():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        req = MODULE.parse_request({"command": "/op-simple-build", "repo_root": str(root)})
        assert req.executor_provider == "codex"
        assert req.executor_model is None
        assert req.blackbox_lane == "free"
        assert req.allow_worker_executor_override is False


def test_op_simple_build_accepts_executor_overrides_and_profile_alias():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        req = MODULE.parse_request(
            {
                "command": "/op-simple-build",
                "repo_root": str(root),
                "profile": "openrouter_free",
                "executor_provider": "blackbox",
                "executor_model": "blackboxai/minimax/minimax-m2.5",
                "blackbox_lane": "api_key",
                "allow_worker_executor_override": True,
            }
        )
        assert req.profile == "openrouter_free"
        assert req.codex_profile == "openrouter_free"
        assert req.executor_provider == "blackbox"
        assert req.executor_model == "blackboxai/minimax/minimax-m2.5"
        assert req.blackbox_lane == "api_key"
        assert req.allow_worker_executor_override is True


def test_op_simple_build_accepts_selected_aliases_csv():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        req = MODULE.parse_request(
            {
                "command": "/op-simple-build",
                "repo_root": str(root),
                "selected_aliases": "six, seven, Eight, six",
            }
        )
        assert req.selected_aliases == ["six", "seven", "eight"]


def test_op_build_accepts_selected_aliases_list():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        req = MODULE.parse_request(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "selected_aliases": ["six", " seven ", "SIX", "ten"],
            }
        )
        assert req.selected_aliases == ["six", "seven", "ten"]


def test_command_build_passes_selected_aliases_to_op_simple_build(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        req = MODULE.parse_request(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "selected_aliases": "six, seven, eight",
            }
        )
        captured: dict[str, object] = {}

        fake_module = types.ModuleType("op_simple_build")
        fake_module.SimpleBuildError = RuntimeError

        def fake_run_op_simple_build(simple_req):
            captured["selected_aliases"] = list(simple_req.selected_aliases or [])
            captured["command"] = simple_req.command
            return {
                "ok": True,
                "status": "completed",
                "summary": "ok",
                "warnings": [],
                "errors": [],
                "artifacts": [],
                "next_action": None,
                "state_ref": None,
                "data": {},
            }

        fake_module.inspect_resume_run_base_meta = lambda *_args, **_kwargs: {
            "run_base_branch": "main",
        }
        fake_module.run_op_simple_build = fake_run_op_simple_build
        monkeypatch.setitem(sys.modules, "op_simple_build", fake_module)
        monkeypatch.setattr(
            MODULE,
            "command_initialize",
            lambda _req: {
                "ok": True,
                "status": "completed",
                "summary": "init ok",
                "warnings": [],
                "errors": [],
                "artifacts": [],
                "next_action": None,
                "state_ref": None,
                "data": {},
            },
        )

        out = MODULE.command_build(req)

        assert out["ok"] is True
        assert captured["command"] == "op-simple-build"
        assert captured["selected_aliases"] == ["six", "seven", "eight"]


def test_command_build_passes_strategy_flags_to_initialize(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        req = MODULE.parse_request(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "mission": "Fresh mission",
                "scope": "Board workflow",
                "strategy_manifest_file": "strategy/custom.md",
                "skip_strategy": True,
            }
        )
        captured: dict[str, object] = {}

        fake_module = types.ModuleType("op_simple_build")
        fake_module.SimpleBuildError = RuntimeError
        fake_module.inspect_resume_run_base_meta = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not inspect resume state"))
        fake_module.run_op_simple_build = lambda simple_req: {
            "ok": True,
            "status": "completed",
            "summary": "ok",
            "warnings": [],
            "errors": [],
            "artifacts": [],
            "next_action": None,
            "state_ref": None,
            "data": {"simple_command": simple_req.command},
        }
        monkeypatch.setitem(sys.modules, "op_simple_build", fake_module)

        def fake_initialize(init_req):
            captured["command"] = init_req.command
            captured["strategy_manifest"] = init_req.strategy_manifest
            captured["strategy_manifest_file"] = init_req.strategy_manifest_file
            captured["skip_strategy"] = init_req.skip_strategy
            return {
                "ok": True,
                "status": "completed",
                "summary": "init ok",
                "warnings": [],
                "errors": [],
                "artifacts": [],
                "next_action": None,
                "state_ref": None,
                "data": {},
            }

        monkeypatch.setattr(MODULE, "command_initialize", fake_initialize)

        out = MODULE.command_build(req)

        assert out["ok"] is True
        assert captured["command"] == "op-initialize"
        assert captured["strategy_manifest"] is None
        assert captured["strategy_manifest_file"] == "strategy/custom.md"
        assert captured["skip_strategy"] is True


def test_command_build_enforces_managed_gitignore_before_runtime(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        req = MODULE.parse_request(
            {
                "command": "/op-build",
                "repo_root": str(root),
            }
        )
        calls: list[Path] = []
        captured: dict[str, object] = {}

        fake_module = types.ModuleType("op_simple_build")
        fake_module.SimpleBuildError = RuntimeError

        def fake_run_op_simple_build(simple_req):
            captured["command"] = simple_req.command
            return {
                "ok": True,
                "status": "completed",
                "summary": "ok",
                "warnings": [],
                "errors": [],
                "artifacts": [],
                "next_action": None,
                "state_ref": None,
                "data": {},
            }

        def record_gitignore(repo_root: Path) -> None:
            calls.append(repo_root)

        fake_module.inspect_resume_run_base_meta = lambda *_args, **_kwargs: {
            "run_base_branch": "main",
        }
        fake_module.run_op_simple_build = fake_run_op_simple_build
        monkeypatch.setitem(sys.modules, "op_simple_build", fake_module)
        monkeypatch.setattr(MODULE, "_ensure_managed_gitignore_block", record_gitignore)
        monkeypatch.setattr(MODULE, "MANDATORY_BUILD_BASELINE", [])

        out = MODULE.command_build(req)

        assert out["ok"] is True
        assert captured["command"] == "op-simple-build"
        assert len(calls) == 1
        assert calls[0].resolve() == root.resolve()


def test_command_build_auto_selects_new_on_fresh_run_intent(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        req = MODULE.parse_request(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "mission": "Fresh mission",
            }
        )
        captured: dict[str, object] = {}

        fake_module = types.ModuleType("op_simple_build")
        fake_module.SimpleBuildError = RuntimeError
        fake_module.inspect_resume_run_base_meta = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not inspect resume state"))

        def fake_run_op_simple_build(simple_req):
            captured["command"] = simple_req.command
            return {
                "ok": True,
                "status": "completed",
                "summary": "ok",
                "warnings": [],
                "errors": [],
                "artifacts": [],
                "next_action": None,
                "state_ref": None,
                "data": {},
            }

        fake_module.run_op_simple_build = fake_run_op_simple_build
        monkeypatch.setitem(sys.modules, "op_simple_build", fake_module)
        monkeypatch.setattr(
            MODULE,
            "command_initialize",
            lambda _req: {
                "ok": True,
                "status": "completed",
                "summary": "init ok",
                "warnings": [],
                "errors": [],
                "artifacts": [],
                "next_action": None,
                "state_ref": None,
                "data": {},
            },
        )

        out = MODULE.command_build(req)

        assert out["ok"] is True
        assert captured["command"] == "op-simple-build"
        assert out["data"]["requested_start_policy"] == "auto"
        assert out["data"]["resolved_start_mode"] == "new"
        assert out["data"]["start_policy_reason_code"] == "fresh_run_intent"


def test_command_build_auto_selects_new_when_runtime_marker_missing(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        req = MODULE.parse_request({"command": "/op-build", "repo_root": str(root)})
        captured: dict[str, object] = {}

        fake_module = types.ModuleType("op_simple_build")
        fake_module.SimpleBuildError = RuntimeError
        fake_module.inspect_resume_run_base_meta = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not inspect without marker"))

        def fake_run_op_simple_build(simple_req):
            captured["command"] = simple_req.command
            return {
                "ok": True,
                "status": "completed",
                "summary": "ok",
                "warnings": [],
                "errors": [],
                "artifacts": [],
                "next_action": None,
                "state_ref": None,
                "data": {},
            }

        fake_module.run_op_simple_build = fake_run_op_simple_build
        monkeypatch.setitem(sys.modules, "op_simple_build", fake_module)
        monkeypatch.setattr(MODULE, "MANDATORY_BUILD_BASELINE", [])

        out = MODULE.command_build(req)

        assert out["ok"] is True
        assert captured["command"] == "op-simple-build"
        assert out["data"]["resolved_start_mode"] == "new"
        assert out["data"]["start_policy_reason_code"] == "no_existing_op_simple_state"


def test_command_build_auto_selects_resume_when_runtime_state_is_valid(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        marker = root / ".op-simple" / "current" / "initialize_state.json"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("{}\n", encoding="utf-8")
        req = MODULE.parse_request({"command": "/op-build", "repo_root": str(root)})
        captured: dict[str, object] = {}

        fake_module = types.ModuleType("op_simple_build")
        fake_module.SimpleBuildError = RuntimeError
        fake_module.inspect_resume_run_base_meta = lambda *_args, **_kwargs: {
            "run_base_branch": "op-simple-canary-123",
        }

        def fake_run_op_simple_build(simple_req):
            captured["command"] = simple_req.command
            return {
                "ok": True,
                "status": "completed",
                "summary": "ok",
                "warnings": [],
                "errors": [],
                "artifacts": [],
                "next_action": None,
                "state_ref": None,
                "data": {},
            }

        fake_module.run_op_simple_build = fake_run_op_simple_build
        monkeypatch.setitem(sys.modules, "op_simple_build", fake_module)

        out = MODULE.command_build(req)

        assert out["ok"] is True
        assert captured["command"] == "op-resume"
        assert out["data"]["resolved_start_mode"] == "resume"
        assert out["data"]["start_policy_reason_code"] == "resume_state_valid"


def test_command_build_auto_blocks_when_existing_runtime_state_is_invalid(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        marker = root / ".op-simple" / "current" / "initialize_state.json"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("{}\n", encoding="utf-8")
        req = MODULE.parse_request({"command": "/op-build", "repo_root": str(root)})

        fake_module = types.ModuleType("op_simple_build")

        class FakeSimpleBuildError(Exception):
            def __init__(self, code, message):
                super().__init__(message)
                self.code = code
                self.message = message

        fake_module.SimpleBuildError = FakeSimpleBuildError
        fake_module.inspect_resume_run_base_meta = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            FakeSimpleBuildError("op_simple_resume_missing_branch", "branch missing")
        )
        fake_module.run_op_simple_build = lambda _req: (_ for _ in ()).throw(AssertionError("runtime should not launch"))
        monkeypatch.setitem(sys.modules, "op_simple_build", fake_module)

        out = MODULE.command_build(req)

        assert out["ok"] is False
        assert out["status"] == "blocked_preflight"
        assert out["data"]["requested_start_policy"] == "auto"
        assert out["data"]["resolved_start_mode"] is None
        assert out["data"]["start_policy_reason_code"] == "resume_state_invalid_existing_state_present"


def test_command_build_explicit_resume_uses_resume_runtime(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        req = MODULE.parse_request(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "start_policy": "resume",
            }
        )
        captured: dict[str, object] = {}

        fake_module = types.ModuleType("op_simple_build")
        fake_module.SimpleBuildError = RuntimeError
        fake_module.inspect_resume_run_base_meta = lambda *_args, **_kwargs: {
            "run_base_branch": "op-simple-canary-123",
        }

        def fake_run_op_simple_build(simple_req):
            captured["command"] = simple_req.command
            return {
                "ok": True,
                "status": "completed",
                "summary": "ok",
                "warnings": [],
                "errors": [],
                "artifacts": [],
                "next_action": None,
                "state_ref": None,
                "data": {},
            }

        fake_module.run_op_simple_build = fake_run_op_simple_build
        monkeypatch.setitem(sys.modules, "op_simple_build", fake_module)

        out = MODULE.command_build(req)

        assert out["ok"] is True
        assert captured["command"] == "op-resume"
        assert out["data"]["start_policy_reason_code"] == "explicit_resume_requested"


def test_command_build_explicit_resume_blocks_when_runtime_state_invalid(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        req = MODULE.parse_request(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "start_policy": "resume",
            }
        )

        fake_module = types.ModuleType("op_simple_build")

        class FakeSimpleBuildError(Exception):
            def __init__(self, code, message):
                super().__init__(message)
                self.code = code
                self.message = message

        fake_module.SimpleBuildError = FakeSimpleBuildError
        fake_module.inspect_resume_run_base_meta = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            FakeSimpleBuildError("op_simple_resume_unavailable", "missing initialize state")
        )
        fake_module.run_op_simple_build = lambda _req: (_ for _ in ()).throw(AssertionError("runtime should not launch"))
        monkeypatch.setitem(sys.modules, "op_simple_build", fake_module)

        out = MODULE.command_build(req)

        assert out["ok"] is False
        assert out["status"] == "blocked_preflight"
        assert out["data"]["requested_start_policy"] == "resume"
        assert out["data"]["start_policy_reason_code"] == "resume_state_invalid_existing_state_present"


def test_command_build_explicit_new_ignores_existing_resume_state(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        marker = root / ".op-simple" / "current" / "initialize_state.json"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("{}\n", encoding="utf-8")
        req = MODULE.parse_request(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "start_policy": "new",
            }
        )
        captured: dict[str, object] = {}

        fake_module = types.ModuleType("op_simple_build")
        fake_module.SimpleBuildError = RuntimeError
        fake_module.inspect_resume_run_base_meta = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("explicit new should not inspect"))

        def fake_run_op_simple_build(simple_req):
            captured["command"] = simple_req.command
            return {
                "ok": True,
                "status": "completed",
                "summary": "ok",
                "warnings": [],
                "errors": [],
                "artifacts": [],
                "next_action": None,
                "state_ref": None,
                "data": {},
            }

        fake_module.run_op_simple_build = fake_run_op_simple_build
        monkeypatch.setitem(sys.modules, "op_simple_build", fake_module)
        monkeypatch.setattr(MODULE, "MANDATORY_BUILD_BASELINE", [])

        out = MODULE.command_build(req)

        assert out["ok"] is True
        assert captured["command"] == "op-simple-build"
        assert out["data"]["start_policy_reason_code"] == "explicit_new_requested"


def test_parse_request_rejects_invalid_executor_provider():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        try:
            MODULE.parse_request(
                {
                    "command": "/op-simple-build",
                    "repo_root": str(root),
                    "executor_provider": "invalid-provider",
                }
            )
        except MODULE.OpError as exc:
            assert exc.code == "input_error"
            assert "executor_provider" in exc.message
        else:  # pragma: no cover - defensive
            raise AssertionError("expected parse_request to reject invalid executor_provider")


def test_op_simple_build_dry_run_runs_without_codex():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        out = run_payload(
            {
                "command": "/op-simple-build",
                "repo_root": str(root),
                "dry_run": True,
                "max_build_cycles": 1,
            }
        )
        assert out["ok"] is True
        assert out["status"] == "completed"
        assert (root / ".op-simple" / "current" / "cycle_summary.json").exists()


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
        build_state["profile_aliases"] = ["codex"]

        for task in task_state["tasks"]:
            task["status"] = "review_done"
            task["owner_slot"] = None
        task_state["tasks"][0]["status"] = "review_done"
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
        assert task["status"] == "pending"
        assert task["owner_slot"] is None


def test_lane_b_quality_gate_blocks_when_canary_root_unset(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        manifest = root / "scripts" / "quality" / "lane_b_required_tests.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "required_risk_tests": [],
                    "full_matrix_targets": [],
                    "coverage_targets": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        monkeypatch.delenv("OP_CANARY_PROJECT_ROOT", raising=False)
        monkeypatch.setattr(sys, "argv", ["lane_b_quality_gate", "--repo-root", str(root)])
        rc = QUALITY_GATE.main()
        assert rc == 1
        artifact = json.loads((root / "reports" / "optimus-prime" / "planning" / "LANE_B_QUALITY_GATE.json").read_text(encoding="utf-8"))
        assert artifact["status"] == "blocked"
        assert artifact["runtime_canary"]["error_code"] == "canary_project_root_missing"


def test_lane_b_quality_gate_uses_env_canary_root_when_set(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        manifest = root / "scripts" / "quality" / "lane_b_required_tests.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "required_risk_tests": [],
                    "full_matrix_targets": [],
                    "coverage_targets": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        capture: dict[str, str] = {}
        monkeypatch.setenv("OP_CANARY_PROJECT_ROOT", "/tmp/canary-root")
        monkeypatch.setattr(QUALITY_GATE, "run_required_risk_tests", lambda *_args, **_kwargs: (True, []))
        monkeypatch.setattr(QUALITY_GATE, "run_full_matrix", lambda *_args, **_kwargs: True)
        monkeypatch.setattr(QUALITY_GATE, "run_coverage_snapshot", lambda *_args, **_kwargs: (True, {"scripts/op/op_core.py": 80.0}))

        def fake_run_canary(_repo_root: Path, canary_project_root: str):
            capture["project_root"] = canary_project_root
            return True, {"status": "passed", "artifacts": {"canary_gate": "/tmp/canary.json"}}

        monkeypatch.setattr(QUALITY_GATE, "run_runtime_canary_gate", fake_run_canary)
        monkeypatch.setattr(sys, "argv", ["lane_b_quality_gate", "--repo-root", str(root)])
        rc = QUALITY_GATE.main()
        assert rc == 0
        assert capture["project_root"] == "/tmp/canary-root"
        artifact = json.loads((root / "reports" / "optimus-prime" / "planning" / "LANE_B_QUALITY_GATE.json").read_text(encoding="utf-8"))
        assert artifact["status"] == "passed"
        assert artifact["runtime_canary"]["project_root"] == "/tmp/canary-root"


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


def test_seed_rate_registry_warns_when_snapshot_script_unavailable(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        write_profile_selection(root)
        rate_path = root / "reports" / "optimus-prime" / "PROFILE_RATE_REGISTRY.json"
        rate_path.unlink(missing_ok=True)

        monkeypatch.setattr(MODULE, "_resolve_rate_snapshot_script", lambda _repo_root: None)
        warnings = MODULE._seed_rate_registry_if_missing(root)

        assert any(item.get("code") == "rate_registry_seed_unavailable" for item in warnings)
        assert not rate_path.exists()


def test_seed_rate_registry_uses_selected_aliases(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        second = root.parent / ".codex-second"
        second.mkdir(parents=True, exist_ok=True)
        (second / "auth.json").write_text("{}\n", encoding="utf-8")
        selection = {
            "schema_version": "1.0",
            "detected_at": "2026-01-01T00:00:00Z",
            "detection_root": str(root.parent),
            "profiles": [
                {
                    "alias": "codex",
                    "codex_home": str((root.parent / ".codex").resolve()),
                    "auth_path": str((root.parent / ".codex" / "auth.json").resolve()),
                },
                {
                    "alias": "codex-second",
                    "codex_home": str(second.resolve()),
                    "auth_path": str((second / "auth.json").resolve()),
                },
            ],
            "selected_aliases": ["codex", "codex-second"],
            "selection_policy": "initialize_autodetect",
            "notes": [],
        }
        captured: dict[str, object] = {}

        script_path = root / "fake_snapshot.py"
        script_path.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
        monkeypatch.setattr(MODULE, "_resolve_rate_snapshot_script", lambda _repo_root: script_path)

        def fake_run(cmd, *, cwd, stdin_text=None):
            captured["cmd"] = cmd
            payload = [
                {
                    "alias": "codex",
                    "codex_home": str((root.parent / ".codex").resolve()),
                    "gated": False,
                    "primary_window": {"used_percent": 20.0, "reset_at": 1773529474},
                    "secondary_window": {"used_percent": 20.0, "reset_at": 1774002467},
                },
                {
                    "alias": "codex-second",
                    "codex_home": str(second.resolve()),
                    "gated": False,
                    "primary_window": {"used_percent": 20.0, "reset_at": 1773529474},
                    "secondary_window": {"used_percent": 20.0, "reset_at": 1774002467},
                },
            ]
            return 0, json.dumps(payload), ""

        monkeypatch.setattr(MODULE, "_run", fake_run)
        warnings = MODULE._seed_rate_registry_if_missing(
            root,
            force_refresh=True,
            emit_success_warning=False,
            profile_selection=selection,
        )
        assert warnings == []
        cmd = captured["cmd"]
        assert isinstance(cmd, list)
        assert "--profile" not in cmd
        assert cmd[:2] == [sys.executable, str(script_path)]
        assert "--json-pretty" in cmd


def test_select_profile_alias_prefers_unassigned_when_extra_profiles():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        build_state = {
            "profile_aliases": ["codex", "codex-second", "codex-third"],
            "slot_profile_assignments": {
                "dev-1": "codex",
                "test-1": "codex-second",
            },
        }
        result = MODULE._select_profile_alias_for_slot(
            root,
            build_state,
            slot="review-1",
            slot_count=2,
        )
        assert result["ok"] is True
        assert result["alias"] == "codex-third"


def test_select_profile_alias_uses_least_gated_when_slots_exhausted():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        rate_path = root / "reports" / "optimus-prime" / "PROFILE_RATE_REGISTRY.json"
        rate_path.parent.mkdir(parents=True, exist_ok=True)
        rate_path.write_text(
            json.dumps(
                {
                    "profiles": {
                        "codex": {"five_hour": {"remaining_percent": 10}, "weekly": {"remaining_percent": 10}},
                        "codex-second": {"five_hour": {"remaining_percent": 80}, "weekly": {"remaining_percent": 80}},
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        build_state = {
            "profile_aliases": ["codex", "codex-second"],
            "slot_profile_assignments": {"dev-1": "codex"},
        }
        result = MODULE._select_profile_alias_for_slot(
            root,
            build_state,
            slot="test-1",
            slot_count=2,
        )
        assert result["ok"] is True
        assert result["alias"] == "codex-second"


def test_select_profile_alias_returns_all_hard_gated_reason():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
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
        build_state = {
            "profile_aliases": ["codex", "codex-second"],
            "slot_profile_assignments": {},
        }
        result = MODULE._select_profile_alias_for_slot(
            root,
            build_state,
            slot="dev-1",
            slot_count=3,
        )
        assert result["ok"] is False
        assert result["reason"] == "profile_assignment_all_hard_gated"


def test_select_profile_alias_excludes_profiles_with_auth_errors():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        rate_path = root / "reports" / "optimus-prime" / "PROFILE_RATE_REGISTRY.json"
        rate_path.parent.mkdir(parents=True, exist_ok=True)
        rate_path.write_text(
            json.dumps(
                {
                    "profiles": {
                        "codex": {
                            "five_hour": {"remaining_percent": 90},
                            "weekly": {"remaining_percent": 90},
                            "recommended_action": "continue",
                            "errors": ["refresh_token_reused"],
                        },
                        "codex-second": {
                            "five_hour": {"remaining_percent": 80},
                            "weekly": {"remaining_percent": 80},
                            "recommended_action": "continue",
                            "errors": [],
                        },
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        build_state = {
            "profile_aliases": ["codex", "codex-second"],
            "slot_profile_assignments": {},
        }
        result = MODULE._select_profile_alias_for_slot(
            root,
            build_state,
            slot="dev-1",
            slot_count=3,
        )
        assert result["ok"] is True
        assert result["alias"] == "codex-second"


def test_select_profile_alias_excludes_permanently_blocked_profiles():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        rate_path = root / "reports" / "optimus-prime" / "PROFILE_RATE_REGISTRY.json"
        rate_path.parent.mkdir(parents=True, exist_ok=True)
        rate_path.write_text(
            json.dumps(
                {
                    "profiles": {
                        "codex": {
                            "recommended_action": "continue",
                            "permanently_blocked": True,
                            "permanent_block_reason": "refresh_token_reused",
                        },
                        "codex-second": {
                            "recommended_action": "continue",
                        },
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        build_state = {
            "profile_aliases": ["codex", "codex-second"],
            "slot_profile_assignments": {},
        }
        result = MODULE._select_profile_alias_for_slot(
            root,
            build_state,
            slot="dev-1",
            slot_count=3,
        )
        assert result["ok"] is True
        assert result["alias"] == "codex-second"


def test_select_profile_alias_keeps_profiles_with_non_auth_snapshot_errors():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        rate_path = root / "reports" / "optimus-prime" / "PROFILE_RATE_REGISTRY.json"
        rate_path.parent.mkdir(parents=True, exist_ok=True)
        rate_path.write_text(
            json.dumps(
                {
                    "profiles": {
                        "codex": {
                            "five_hour": {"remaining_percent": 90},
                            "weekly": {"remaining_percent": 90},
                            "recommended_action": "continue",
                            "errors": ["token_count_event_not_found"],
                        },
                        "codex-second": {
                            "five_hour": {"remaining_percent": 80},
                            "weekly": {"remaining_percent": 80},
                            "recommended_action": "continue",
                            "errors": [],
                        },
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        build_state = {
            "profile_aliases": ["codex", "codex-second"],
            "slot_profile_assignments": {},
        }
        result = MODULE._select_profile_alias_for_slot(
            root,
            build_state,
            slot="dev-1",
            slot_count=3,
        )
        assert result["ok"] is True
        assert result["alias"] == "codex"


def test_seed_rate_registry_refresh_preserves_permanently_blocked_profile(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        write_profile_selection(root)
        rate_path = root / "reports" / "optimus-prime" / "PROFILE_RATE_REGISTRY.json"
        rate_path.parent.mkdir(parents=True, exist_ok=True)
        rate_path.write_text(
            json.dumps(
                {
                    "profiles": {
                        "codex": {
                            "recommended_action": "wind_down",
                            "permanently_blocked": True,
                            "permanent_block_reason": "refresh_token_reused",
                        }
                    },
                    "gated_profiles": ["codex"],
                    "eligible_profiles": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        script_path = root / "fake_snapshot.py"
        script_path.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
        script_path.chmod(0o755)
        monkeypatch.setattr(MODULE, "_resolve_rate_snapshot_script", lambda _repo_root: script_path)
        monkeypatch.setattr(
            MODULE,
            "_run",
            lambda *_args, **_kwargs: (
                0,
                json.dumps(
                    {
                        "profiles": {
                            "codex": {"recommended_action": "continue"},
                            "codex-second": {"recommended_action": "continue"},
                        },
                        "eligible_profiles": ["codex", "codex-second"],
                        "gated_profiles": [],
                    }
                ),
                "",
            ),
        )

        warnings = MODULE._seed_rate_registry_if_missing(root, force_refresh=True, emit_success_warning=False)
        assert warnings == []
        refreshed = json.loads(rate_path.read_text(encoding="utf-8"))
        codex_row = refreshed.get("profiles", {}).get("codex", {})
        assert codex_row.get("permanently_blocked") is True
        assert codex_row.get("recommended_action") == "wind_down"
        assert "codex" in (refreshed.get("gated_profiles") or [])


def test_refresh_token_reused_unauthorized_detector_requires_auth_marker():
    assert MODULE._is_refresh_token_reused_unauthorized("401 Unauthorized code: refresh_token_reused") is True
    assert MODULE._is_refresh_token_reused_unauthorized("refresh_token_reused") is False
    assert MODULE._is_refresh_token_reused_unauthorized("401 Unauthorized") is False


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
        done_registry_path = root / "reports" / "optimus-prime" / "planning" / "DONE_TASKS_REGISTRY.json"
        done_registry_path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "plan_id": "plan-test",
                    "updated_at": "2026-01-01T00:00:00Z",
                    "done_task_ids": sorted(
                        [MODULE._as_str(item.get("task_id")) for item in task_state["tasks"] if MODULE._as_str(item.get("task_id"))]
                    ),
                    "merged_tasks": [
                        {
                            "task_id": MODULE._as_str(item.get("task_id")),
                            "merged_commit": "abc123",
                            "merged_at": "2026-01-01T00:00:00Z",
                            "branch": "RAB-BASE",
                            "verification_passed": True,
                            "verification_ref": "reports/optimus-prime/branch-manager/attempt-1/MERGE_VALIDATION.json",
                        }
                        for item in task_state["tasks"]
                        if MODULE._as_str(item.get("task_id"))
                    ],
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
        assert out["ok"] is True
        assert out["status"] == "completed"



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


def test_op_status_ignores_malformed_legacy_gaps_artifact():
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
        assert out["ok"] is True
        assert out["status"] == "completed"
        assert not any(item.get("code") == "status_snapshot_degraded" for item in out.get("warnings", []))


def test_op_status_reports_active_build_lock_as_running_wait_action():
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
        lock_payload = {
            "schema_version": "1.0",
            "lock_id": "test-lock-id",
            "pid": os.getpid(),
            "acquired_at": "2026-03-02T00:00:00Z",
        }
        lock_path.write_text(json.dumps(lock_payload, indent=2) + "\n", encoding="utf-8")

        out = run_payload({"command": "/op-status", "repo_root": str(root)})
        assert out["ok"] is True
        assert out["status"] == "completed"
        assert out.get("data", {}).get("build") == "running"
        assert out.get("data", {}).get("next_action") == "wait (build active)"
        assert "Build is active" in (out.get("next_action") or "")
        assert any(item.get("code") == "status_build_running" for item in out.get("warnings", []))


def test_status_ignores_legacy_gap_closure_schema_invalid_tasks_field():
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
        assert out["ok"] is True
        assert out["status"] == "completed"


def test_status_ignores_legacy_gap_closure_schema_invalid_plan_id():
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
        assert out["ok"] is True
        assert out["status"] == "completed"


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


def test_op_report_marks_health_degraded_on_no_progress_watchdog(monkeypatch: pytest.MonkeyPatch):
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
        build_state = {
            "schema_version": "1.0",
            "updated_at": "2026-01-01T00:00:00Z",
            "last_cycle": 8,
            "current_strategy": "self_heal",
            "current_phase_id": "phase-1",
            "no_progress_watchdog": {
                "consecutive_no_progress_cycles": 4,
                "threshold_cycles": 25,
                "last_progress_at": "2026-01-01T00:00:00Z",
                "triggered": False,
                "triggered_at": None,
            },
        }
        build_state_path.write_text(json.dumps(build_state, indent=2) + "\n", encoding="utf-8")
        lock_path = root / "reports" / "optimus-prime" / "planning" / "BUILD_LOOP.lock"
        lock_path.write_text(
            json.dumps({"schema_version": "1.0", "lock_id": "test-lock", "pid": 42424, "acquired_at": "2026-01-01T00:00:00Z"}, indent=2)
            + "\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(MODULE, "_pid_is_running", lambda pid: pid == 42424)

        out = run_payload({"command": "/op-report", "repo_root": str(root)})
        assert out["ok"] is True
        assert out["data"]["health"] == "yellow"
        assert MODULE._as_str(out["data"].get("health_reason")).startswith("no_progress_watchdog:")
        warning_codes = {item.get("code") for item in out.get("warnings", []) if isinstance(item, dict)}
        assert "no_progress_watchdog_degraded" in warning_codes


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


def test_op_health_ignores_malformed_legacy_gaps_artifact():
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
        assert health["ok"] is True
        assert health["status"] == "completed"


def test_op_health_ignores_malformed_legacy_gap_closure_artifact():
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
        assert health["ok"] is True
        assert health["status"] == "completed"


def test_health_ignores_legacy_gap_closure_schema_invalid_tasks_field():
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
        assert out["ok"] is True
        assert out["status"] == "completed"


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


def test_gap_closure_generated_tasks_require_requirement_ids():
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
        task_state["tasks"][0]["status"] = "review_done"
        task_state["tasks"][0]["owner_slot"] = None

        _, closure_payload = MODULE._refresh_gap_artifacts(root, plan_packets, task_state, build_state)
        closure_tasks = [task for task in closure_payload.get("tasks", []) if isinstance(task, dict)]
        assert closure_tasks
        assert all(isinstance(task.get("requirement_ids"), list) and task.get("requirement_ids") for task in closure_tasks)


def test_gap_recovery_generated_tasks_require_requirement_ids():
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
        planning = root / "reports" / "optimus-prime" / "planning"
        (planning / "GAPS.json").write_text("{ invalid-json", encoding="utf-8")
        (planning / "GAP_CLOSURE_PLAN_PACKETS.json").write_text("{ invalid-json", encoding="utf-8")

        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        build_state["open_gap_ids"] = ["gap-recovery-reqids-1"]
        build_state["active_gap_closure_phase_id"] = "phase-1"

        _, closure_payload, _ = MODULE._recover_gap_artifacts_for_build(
            root,
            plan_packets,
            task_state,
            build_state,
            MODULE._as_str(plan_packets.get("plan_id")) if isinstance(plan_packets, dict) else "plan-unknown",
            True,
            True,
        )
        closure_tasks = [task for task in closure_payload.get("tasks", []) if isinstance(task, dict)]
        assert closure_tasks
        assert all(isinstance(task.get("requirement_ids"), list) and task.get("requirement_ids") for task in closure_tasks)


def test_dispatch_exhausted_gap_closure_continues_to_next_dispatchable_task(monkeypatch: pytest.MonkeyPatch):
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
        build_state["profile_aliases"] = ["codex"]

        for task in task_state["tasks"]:
            task["status"] = "review_done"
            task["owner_slot"] = None

        _, gap_closure_payload = MODULE._refresh_gap_artifacts(root, plan_packets, task_state, build_state)
        MODULE._ensure_gap_closure_task_state(root, task_state, gap_closure_payload, plan_packets["plan_id"])
        merged_plan = MODULE._merge_plan_with_gap_closure(plan_packets, gap_closure_payload)
        gap_tasks = [task for task in task_state["tasks"] if task.get("is_gap_closure")]
        assert len(gap_tasks) >= 2
        gap_tasks.sort(key=lambda item: item.get("task_id") or "")

        first = gap_tasks[0]
        first["status"] = "blocked"
        first["owner_slot"] = None
        source_gap_id = first.get("source_gap_id")
        assert isinstance(source_gap_id, str) and source_gap_id
        build_state["gap_retry_exhausted_ids"] = [source_gap_id]

        second = gap_tasks[1]
        second["status"] = "queued"
        second["owner_slot"] = None
        merged_task_map = {task.get("task_id"): task for task in merged_plan.get("tasks", []) if isinstance(task, dict)}
        merged_plan["tasks"] = [
            merged_task_map[first.get("task_id")],
            merged_task_map[second.get("task_id")],
        ]

        dispatched: list[str] = []

        def fake_dispatch_task_packet(_req, task, _plan_task, _stage, _plan_id, _alias, **_kwargs):
            dispatched.append(task.get("task_id"))
            return {"ok": True, "status": "dispatch_started"}

        monkeypatch.setattr(MODULE, "_dispatch_task_packet", fake_dispatch_task_packet)

        result = MODULE._dispatch_next_task(req, merged_plan, task_state, build_state, None)
        assert result.get("ok") is True
        assert dispatched
        assert dispatched[0] != first.get("task_id")
        warning_codes = set()
        warning = result.get("warning")
        if isinstance(warning, dict):
            warning_codes.add(warning.get("code"))
        for item in result.get("warnings", []):
            if isinstance(item, dict):
                warning_codes.add(item.get("code"))
        assert "gap_closure_skipped_exhausted_continue_scan" in warning_codes


def test_dispatch_returns_blocked_only_after_full_scan_if_all_exhausted():
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
        build_state["profile_aliases"] = ["codex"]

        for task in task_state["tasks"]:
            task["status"] = "review_done"
            task["owner_slot"] = None
        task_state["tasks"][0]["status"] = "review_done"
        task_state["tasks"][1]["status"] = "blocked"
        _, gap_closure_payload = MODULE._refresh_gap_artifacts(root, plan_packets, task_state, build_state)
        MODULE._ensure_gap_closure_task_state(root, task_state, gap_closure_payload, plan_packets["plan_id"])
        merged_plan = MODULE._merge_plan_with_gap_closure(plan_packets, gap_closure_payload)
        gap_tasks = [task for task in task_state["tasks"] if task.get("is_gap_closure")]
        assert len(gap_tasks) >= 2
        exhausted_ids = []
        merged_task_map = {task.get("task_id"): task for task in merged_plan.get("tasks", []) if isinstance(task, dict)}
        ordered_gap_tasks = sorted(gap_tasks, key=lambda item: item.get("task_id") or "")
        merged_plan["tasks"] = [merged_task_map[item.get("task_id")] for item in ordered_gap_tasks]
        for task in ordered_gap_tasks:
            task["status"] = "blocked"
            task["owner_slot"] = None
            source_gap_id = task.get("source_gap_id")
            assert isinstance(source_gap_id, str) and source_gap_id
            exhausted_ids.append(source_gap_id)
        build_state["gap_retry_exhausted_ids"] = exhausted_ids

        result = MODULE._dispatch_next_task(req, merged_plan, task_state, build_state, None)
        assert result.get("ok") is False
        assert result.get("status") == "blocked"
        assert result.get("reason") in {"gap_closure_retry_suppressed", "gap_retry_exhausted"}


def test_active_workers_count_ignores_dead_running_pid(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        reports = root / "reports" / "optimus-prime"
        reports.mkdir(parents=True, exist_ok=True)
        (reports / "WORKER_REGISTRY.json").write_text(
            json.dumps(
                {
                    "workers": [
                        {"slot": "dev-1", "session_state": "running", "dispatch_pid": 12345},
                        {"slot": "test-1", "session_state": "running", "dispatch_pid": 23456},
                        {"slot": "review-1", "session_state": "not_running", "dispatch_pid": 34567},
                    ]
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(MODULE, "_pid_is_running", lambda pid: pid == 23456)
        assert MODULE._active_workers_count(root) == 1


def test_sync_task_state_invalid_evidence_clears_owner_slot_and_appends_blocker():
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
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        task = task_state["tasks"][0]
        task["status"] = "dev_in_progress"
        task["owner_slot"] = "dev-1"
        evidence_path = root / task["evidence"]["task_evidence_ref"]
        evidence_path.write_text("{ invalid-json", encoding="utf-8")

        warnings = MODULE._sync_task_state_from_evidence(root, plan_packets, task_state)
        assert any(item.get("code") == "task_evidence_invalid" for item in warnings)
        assert task["status"] == "blocked"
        assert task["owner_slot"] is None
        assert isinstance(task.get("blockers"), list) and task["blockers"]


def test_tdd_red_expected_fail_evidence_advances_stage():
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
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        task = task_state["tasks"][0]
        task["status"] = "dev_working"
        task["owner_slot"] = "dev-1"
        evidence_path = root / task["evidence"]["task_evidence_ref"]
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        payload["summary"] = {
            "result": "fail",
            "expectation": "expect_fail",
            "expectation_met": True,
            "failure_class": "expected_red",
            "reason_codes": ["tdd_expected_failure_observed"],
        }
        evidence_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        warnings = MODULE._sync_task_state_from_evidence(root, plan_packets, task_state)
        assert task["status"] == "review_done"
        assert task["owner_slot"] is None
        assert task["blocking_source"] == "none"
        assert any(item.get("code") == "tdd_expectation_met" for item in warnings if isinstance(item, dict))


def test_tdd_red_expected_fail_evidence_advances_stage_when_summary_result_pass():
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
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        task = task_state["tasks"][0]
        task["status"] = "dev_working"
        task["owner_slot"] = "dev-1"
        evidence_path = root / task["evidence"]["task_evidence_ref"]
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        payload["summary"] = {
            "result": "pass",
            "expectation": "expect_fail",
            "expectation_met": True,
            "failure_class": "expected_red",
            "reason_codes": ["tdd_expected_failure_observed"],
        }
        evidence_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        warnings = MODULE._sync_task_state_from_evidence(root, plan_packets, task_state)
        assert task["status"] == "review_done"
        assert task["owner_slot"] is None
        assert task["blocking_source"] == "none"
        assert any(item.get("code") == "tdd_expectation_met" for item in warnings if isinstance(item, dict))


def test_gapfix_test_stage_uses_gap_stage_expectation_and_returns_to_testing():
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
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        task = task_state["tasks"][0]
        task["status"] = "review_done"
        task["owner_slot"] = None
        task["task_kind"] = "implementation"
        task["verification_contract"] = {
            "mode": "hardening",
            "expected_failure_reason_codes": ["tdd_expected_failure_observed"],
            "infra_failure_reason_codes": ["verification_environment_error"],
        }
        task["gapfix_state"] = {
            "active_batch_id": "batch-test-gap",
            "active": True,
            "target_gap_stage": "test",
            "consumed_gap_ids": ["gap-test-1"],
            "batch_started_cycle": 1,
            "batch_last_updated_at": "2026-03-03T00:00:00Z",
        }
        evidence_path = root / task["evidence"]["task_evidence_ref"]
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        payload["summary"] = {
            "result": "pass",
            "expectation": "expect_pass",
            "expectation_met": True,
            "failure_class": "none",
            "reason_codes": ["gapfix_completed"],
        }
        evidence_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        warnings = MODULE._sync_task_state_from_evidence(root, plan_packets, task_state)
        assert task["status"] == "review_done"
        assert task["owner_slot"] is None
        assert task["blocking_source"] == "none"
        assert task["gapfix_state"]["active"] is False
        assert task["gapfix_state"]["active_batch_id"] is None
        assert any(
            item.get("code") == "tdd_expectation_met" and item.get("stage_name") == "test"
            for item in warnings
            if isinstance(item, dict)
        )


def test_gapfix_review_stage_uses_gap_stage_expectation_and_returns_to_review():
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
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        task = task_state["tasks"][0]
        task["status"] = "dev_done"
        task["owner_slot"] = None
        task["task_kind"] = "implementation"
        task["verification_contract"] = {
            "mode": "hardening",
            "expected_failure_reason_codes": ["tdd_expected_failure_observed"],
            "infra_failure_reason_codes": ["verification_environment_error"],
        }
        task["gapfix_state"] = {
            "active_batch_id": "batch-review-gap",
            "active": True,
            "target_gap_stage": "review",
            "consumed_gap_ids": ["gap-review-1"],
            "batch_started_cycle": 1,
            "batch_last_updated_at": "2026-03-03T00:00:00Z",
        }
        evidence_path = root / task["evidence"]["task_evidence_ref"]
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        payload["summary"] = {
            "result": "pass",
            "expectation": "expect_pass",
            "expectation_met": True,
            "failure_class": "none",
            "reason_codes": ["gapfix_completed"],
        }
        evidence_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        warnings = MODULE._sync_task_state_from_evidence(root, plan_packets, task_state)
        assert task["status"] == "review_done"
        assert task["owner_slot"] is None
        assert task["blocking_source"] == "none"
        assert task["gapfix_state"]["active"] is False
        assert task["gapfix_state"]["active_batch_id"] is None
        assert any(
            item.get("code") == "tdd_expectation_met" and item.get("stage_name") == "review"
            for item in warnings
            if isinstance(item, dict)
        )


def test_handoff_blocked_is_non_authoritative_when_evidence_contract_advances():
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
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        task = task_state["tasks"][0]
        task["status"] = "dev_working"
        task["owner_slot"] = "dev-1"
        handoff_path = root / "reports" / "optimus-prime" / "HANDOFF_LOG.jsonl"
        handoff_path.parent.mkdir(parents=True, exist_ok=True)
        handoff_row = {
            "task_identifier": "TASK-001",
            "result": "blocked",
            "reason_codes": ["missing_docs"],
            "task_evidence_ref": task["evidence"]["task_evidence_ref"],
            "timestamp": MODULE.utc_now_iso(),
        }
        handoff_path.write_text(json.dumps(handoff_row) + "\n", encoding="utf-8")
        evidence_path = root / task["evidence"]["task_evidence_ref"]
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        payload["summary"] = {
            "result": "fail",
            "expectation": "expect_fail",
            "expectation_met": True,
            "failure_class": "expected_red",
            "reason_codes": ["tdd_expected_failure_observed"],
        }
        evidence_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        handoff_warnings = MODULE._apply_handoff_updates(root, task_state, build_state)
        sync_warnings = MODULE._sync_task_state_from_evidence(root, plan_packets, task_state)
        assert any(item.get("code") == "handoff_non_authoritative_state_only" for item in handoff_warnings if isinstance(item, dict))
        assert task["status"] == "review_done"
        assert task["owner_slot"] is None
        assert task["last_handoff_outcome"]["status"] == "blocked"
        assert any(item.get("code") == "tdd_expectation_met" for item in sync_warnings if isinstance(item, dict))


def test_review_done_demotes_to_blocked_when_latest_evidence_contract_fails_and_not_merged():
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
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        task = task_state["tasks"][0]
        task["status"] = "review_done"
        task["owner_slot"] = None
        evidence_path = root / task["evidence"]["task_evidence_ref"]
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        payload["summary"] = {
            "result": "pass",
            "expectation": "expect_fail",
            "expectation_met": False,
            "failure_class": "unexpected",
            "reason_codes": ["tdd_expectation_not_met"],
        }
        evidence_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        warnings = MODULE._sync_task_state_from_evidence(root, plan_packets, task_state)
        assert task["status"] == "blocked"
        assert task["blocking_source"] == "evidence"
        assert any(item.get("code") == "tdd_expectation_not_met" for item in warnings if isinstance(item, dict))


def test_sync_task_state_blocks_when_developer_dispatch_commit_link_missing(monkeypatch: pytest.MonkeyPatch):
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
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        task = task_state["tasks"][0]
        task["status"] = "dev_working"
        task["owner_slot"] = "dev-1"
        task["last_dispatch"] = {
            "stage": "dev",
            "role": "developer",
            "branch_name": "codex/dev-1/task-001",
            "start_from_commit": "a" * 40,
            "start_from_branch": "RAB-BASE",
            "dispatched_at": MODULE.utc_now_iso(),
        }
        evidence_path = root / task["evidence"]["task_evidence_ref"]
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        payload["summary"] = {
            "result": "fail",
            "expectation": "expect_fail",
            "expectation_met": True,
            "failure_class": "expected_red",
            "reason_codes": ["tdd_expected_failure_observed"],
        }
        evidence_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        monkeypatch.setattr(
            MODULE,
            "_repo_guard_scan",
            lambda *_args, **_kwargs: {
                "ok": False,
                "mode": "dispatch_commit_link",
                "reason_code": "dispatch_commit_link_missing",
                "head_commit": "a" * 40,
                "changed_paths": [],
                "forbidden_paths": [],
            },
        )

        warnings = MODULE._sync_task_state_from_evidence(root, plan_packets, task_state)
        assert task["status"] == "blocked"
        assert task["blocking_source"] == "evidence"
        assert any(item.get("code") == "dispatch_commit_link_missing" for item in warnings if isinstance(item, dict))


def test_sync_task_state_advances_when_developer_dispatch_commit_link_passes(monkeypatch: pytest.MonkeyPatch):
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
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        task = task_state["tasks"][0]
        task["status"] = "dev_working"
        task["owner_slot"] = "dev-1"
        task["last_dispatch"] = {
            "stage": "dev",
            "role": "developer",
            "branch_name": "codex/dev-1/task-001",
            "start_from_commit": "a" * 40,
            "start_from_branch": "RAB-BASE",
            "dispatched_at": MODULE.utc_now_iso(),
        }
        evidence_path = root / task["evidence"]["task_evidence_ref"]
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        payload["summary"] = {
            "result": "fail",
            "expectation": "expect_fail",
            "expectation_met": True,
            "failure_class": "expected_red",
            "reason_codes": ["tdd_expected_failure_observed"],
        }
        evidence_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        monkeypatch.setattr(
            MODULE,
            "_repo_guard_scan",
            lambda *_args, **_kwargs: {
                "ok": True,
                "mode": "dispatch_commit_link",
                "reason_code": None,
                "head_commit": "b" * 40,
                "changed_paths": ["src/app.py"],
                "forbidden_paths": [],
            },
        )

        warnings = MODULE._sync_task_state_from_evidence(root, plan_packets, task_state)
        assert task["status"] == "review_done"
        assert task["owner_slot"] is None
        assert any(item.get("code") == "tdd_expectation_met" for item in warnings if isinstance(item, dict))


def test_sync_task_state_maps_repo_guard_runtime_error_to_inspection_failed(monkeypatch: pytest.MonkeyPatch):
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
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        task = task_state["tasks"][0]
        task["status"] = "dev_working"
        task["owner_slot"] = "dev-1"
        task["last_dispatch"] = {
            "stage": "dev",
            "role": "developer",
            "branch_name": "codex/dev-1/task-001",
            "start_from_commit": "a" * 40,
            "start_from_branch": "RAB-BASE",
            "dispatched_at": MODULE.utc_now_iso(),
        }
        evidence_path = root / task["evidence"]["task_evidence_ref"]
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        payload["summary"] = {
            "result": "fail",
            "expectation": "expect_fail",
            "expectation_met": True,
            "failure_class": "expected_red",
            "reason_codes": ["tdd_expected_failure_observed"],
        }
        evidence_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        monkeypatch.setattr(
            MODULE,
            "_repo_guard_scan",
            lambda *_args, **_kwargs: {
                "ok": False,
                "error": "runtime_error",
                "message": "tool execution failed",
            },
        )

        warnings = MODULE._sync_task_state_from_evidence(root, plan_packets, task_state)
        assert task["status"] == "blocked"
        assert task["blocking_source"] == "evidence"
        assert any(
            item.get("code") == "dispatch_commit_link_inspection_failed"
            for item in warnings
            if isinstance(item, dict)
        )


def test_validate_task_execution_state_allows_missing_last_dispatch_field():
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
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        for task in task_state.get("tasks", []):
            if isinstance(task, dict):
                task.pop("last_dispatch", None)
        errors = MODULE._validate_task_execution_state(task_state, plan_packets)
        assert not any("last_dispatch" in str(item.get("message")) for item in errors if isinstance(item, dict))


def test_task_evidence_summary_ready_for_test_normalized_to_pass():
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
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        task = task_state["tasks"][0]
        evidence_path = root / task["evidence"]["task_evidence_ref"]
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        payload["summary"]["result"] = "ready_for_test"
        evidence_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        warnings = MODULE._sync_task_state_from_evidence(root, plan_packets, task_state)
        assert any(item.get("code") == "task_evidence_normalized" for item in warnings)
        after = json.loads(evidence_path.read_text(encoding="utf-8"))
        assert after["summary"]["result"] == "pass"


def test_task_evidence_summary_awaiting_execution_stays_not_started_and_not_blocked():
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
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        task = task_state["tasks"][0]
        task["status"] = "pending"
        evidence_path = root / task["evidence"]["task_evidence_ref"]
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        payload["summary"]["result"] = "blocked"
        payload["summary"]["reason_codes"] = ["awaiting_execution"]
        payload["dev"]["checks"] = []
        payload["dev"]["verify_results"] = []
        payload["test"]["checks"] = []
        payload["test"]["verify_results"] = []
        payload["test"]["uat_results"] = []
        payload["review"]["decision"] = "pending"
        payload["review"]["status"] = "pending"
        evidence_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        warnings = MODULE._sync_task_state_from_evidence(root, plan_packets, task_state)
        assert not any(item.get("code") == "task_evidence_invalid" for item in warnings)
        assert task["status"] == "pending"
        normalized_payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        assert "not_started" in normalized_payload["summary"]["reason_codes"]


def test_task_evidence_unknown_summary_result_still_invalid():
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
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        task = task_state["tasks"][0]
        evidence_path = root / task["evidence"]["task_evidence_ref"]
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        payload["summary"]["result"] = "maybe"
        evidence_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        warnings = MODULE._sync_task_state_from_evidence(root, plan_packets, task_state)
        assert any(item.get("code") == "task_evidence_invalid" for item in warnings)
        assert not any(item.get("code") == "task_evidence_normalized" for item in warnings)


def test_gap_rows_have_category_and_reason_codes_after_refresh():
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
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")

        task_state["tasks"][0]["status"] = "review_done"
        task_state["tasks"][0]["owner_slot"] = None
        gaps_payload, _ = MODULE._refresh_gap_artifacts(root, plan_packets, task_state, build_state)
        open_rows = [row for row in gaps_payload.get("gaps", []) if isinstance(row, dict) and row.get("status") == "open"]
        assert open_rows
        assert all(MODULE._as_str(row.get("category")) for row in open_rows)
        assert all(isinstance(row.get("reason_codes"), list) and row.get("reason_codes") for row in open_rows)


def test_gap_rows_backfill_missing_category_reason_codes():
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
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        task_state["tasks"][0]["status"] = "review_done"
        task_state["tasks"][0]["owner_slot"] = None

        gaps_path = planning / "GAPS.json"
        gaps_path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "plan_id": plan_packets["plan_id"],
                    "updated_at": "2026-01-01T00:00:00Z",
                    "gaps": [
                        {
                            "gap_id": "gap-backfill-1",
                            "phase_id": "phase-1",
                            "task_id": "TASK-001",
                            "requirement_id": None,
                            "severity": "high",
                            "result": "blocked",
                            "evidence_ref": "reports/optimus-prime/planning/evidence/TASK-001/TASK_EVIDENCE.json",
                            "opened_at": "2026-01-01T00:00:00Z",
                            "status": "open",
                            "reason": "task state blocked",
                        }
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        gaps_payload, _ = MODULE._refresh_gap_artifacts(root, plan_packets, task_state, build_state)
        row = next(item for item in gaps_payload.get("gaps", []) if item.get("gap_id") == "gap-backfill-1")
        assert row.get("category")
        assert isinstance(row.get("reason_codes"), list) and row.get("reason_codes")


def test_active_workers_count_falls_back_to_snapshot_when_registry_unreadable():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        reports = root / "reports" / "optimus-prime"
        reports.mkdir(parents=True, exist_ok=True)
        (reports / "WORKER_REGISTRY.json").write_text("{ invalid-json", encoding="utf-8")
        (reports / "STATUS_SNAPSHOT.json").write_text(
            json.dumps({"counts": {"active_workers": 2}}, indent=2) + "\n",
            encoding="utf-8",
        )
        assert MODULE._active_workers_count(root) == 2


def test_recover_unreadable_worker_registry_success():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        reports = root / "reports" / "optimus-prime"
        reports.mkdir(parents=True, exist_ok=True)
        registry_path = reports / "WORKER_REGISTRY.json"
        registry_path.write_text("{ invalid-json", encoding="utf-8")

        warnings = MODULE._recover_unreadable_worker_registry(root)
        assert any(item.get("code") == "worker_registry_recovered" for item in warnings)
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
        assert payload == {"workers": []}


def test_recover_unreadable_worker_registry_failure_warns_dispatch_allowed(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        reports = root / "reports" / "optimus-prime"
        reports.mkdir(parents=True, exist_ok=True)
        registry_path = reports / "WORKER_REGISTRY.json"
        registry_path.write_text("{ invalid-json", encoding="utf-8")
        original_atomic = MODULE._atomic_write_json

        def failing_atomic(path: Path, payload: dict):
            if path == registry_path:
                raise OSError("simulated write failure")
            return original_atomic(path, payload)

        monkeypatch.setattr(MODULE, "_atomic_write_json", failing_atomic)
        warnings = MODULE._recover_unreadable_worker_registry(root)
        assert any(item.get("code") == "worker_registry_recovery_failed_dispatch_allowed" for item in warnings)


def test_derive_gap_requirement_ids_missing_fields_uses_fallback():
    req_ids, fallback_used = MODULE._derive_gap_requirement_ids({}, {}, {})
    assert req_ids == ["REQ-GAP-CLOSURE"]
    assert fallback_used is True


def test_repo_guard_scan_uses_installed_op_script_path(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    def fake_run_tool(script: Path, payload: dict[str, object], cwd: Path) -> dict[str, object]:
        captured["script"] = script
        captured["payload"] = payload
        captured["cwd"] = cwd
        return {"ok": True}

    monkeypatch.setattr(MODULE, "_run_tool_json", fake_run_tool)
    repo_root = Path("/tmp/myboard")
    payload = {"mode": "dispatch_commit_link"}
    out = MODULE._repo_guard_scan(repo_root, payload)
    assert out.get("ok") is True
    expected_script = (Path(MODULE.__file__).resolve().parent / "repo_guard_scanner.py").resolve()
    assert captured["script"] == expected_script
    assert captured["cwd"] == repo_root
    assert captured["payload"] == payload


def test_dispatch_task_packet_emits_gap_requirement_fallback_warning(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        req = MODULE.parse_request(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
            }
        )

        task = {
            "task_id": "GAPFIX-TEST",
            "requirement_ids": ["REQ-GAP-CLOSURE"],
            "requirement_fallback_used": True,
            "evidence": {
                "task_evidence_ref": "reports/optimus-prime/planning/evidence/GAPFIX-TEST/TASK_EVIDENCE.json",
            },
            "attempts": {"dev": 0, "test": 0, "review": 0},
            "blockers": [],
        }
        plan_task = {
            "must_haves": ["Resolve gap"],
            "requirement_ids": ["REQ-GAP-CLOSURE"],
            "requirement_fallback_used": True,
        }

        monkeypatch.setattr(MODULE, "_resolve_skill_script", lambda *_args, **_kwargs: Path("/tmp/fake_script.py"))
        monkeypatch.setattr(MODULE, "_run_tool_json", lambda *_args, **_kwargs: {"ok": True, "status": "dispatch_started"})
        monkeypatch.setattr(MODULE, "_git_text", lambda *_args, **_kwargs: "abc1234")

        out = MODULE._dispatch_task_packet(req, task, plan_task, "dev", "plan-1", "codex")
        warning_codes = {item.get("code") for item in out.get("warnings", []) if isinstance(item, dict)}
        assert "gap_closure_requirement_fallback" in warning_codes


def test_dispatch_task_packet_includes_phase_id_in_worker_payload(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        req = MODULE.parse_request(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
            }
        )

        task = {
            "task_id": "TASK-001",
            "phase_id": "phase-2",
            "requirement_ids": ["REQ-001"],
            "evidence": {
                "task_evidence_ref": "reports/optimus-prime/planning/evidence/TASK-001/TASK_EVIDENCE.json",
            },
            "attempts": {"dev": 0, "test": 0, "review": 0},
            "blockers": [],
        }
        plan_task = {
            "phase_id": "phase-9",
            "must_haves": ["Implement feature"],
            "requirement_ids": ["REQ-001"],
        }

        captured: dict[str, object] = {}

        def fake_run(_script: Path, payload: dict[str, object], _cwd: Path) -> dict[str, object]:
            captured.update(payload)
            return {"ok": True, "status": "dispatch_started"}

        monkeypatch.setattr(MODULE, "_resolve_skill_script", lambda *_args, **_kwargs: Path("/tmp/fake_script.py"))
        monkeypatch.setattr(MODULE, "_run_tool_json", fake_run)
        monkeypatch.setattr(MODULE, "_git_text", lambda *_args, **_kwargs: "abc1234")

        MODULE._dispatch_task_packet(req, task, plan_task, "dev", "plan-1", "codex")
        assert captured.get("phase_id") == "phase-2"
        assert captured.get("mcp_mode") == "enable-only"
        assert captured.get("mcp_allowlist") == ["figma"]


@pytest.mark.parametrize(
    ("stage", "expected_status", "expected_slot"),
    [
        ("test", "testing", "test-1"),
        ("review", "reviewing", "review-1"),
    ],
)
def test_dispatch_task_packet_clears_active_gapfix_when_tester_or_reviewer_takes_over(
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
    expected_status: str,
    expected_slot: str,
):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        req = MODULE.parse_request(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
            }
        )

        task = {
            "task_id": "TASK-001",
            "phase_id": "phase-1",
            "requirement_ids": ["REQ-001"],
            "evidence": {
                "task_evidence_ref": "reports/optimus-prime/planning/evidence/TASK-001/TASK_EVIDENCE.json",
            },
            "attempts": {"dev": 1, "test": 0, "review": 0},
            "blockers": [],
            "gapfix_state": {
                "active_batch_id": "batch-123",
                "active": True,
                "target_gap_stage": "test",
                "consumed_gap_ids": ["gap-1"],
                "batch_started_cycle": 3,
                "batch_last_updated_at": "2026-03-03T00:00:00Z",
            },
        }
        plan_task = {
            "phase_id": "phase-1",
            "must_haves": ["Implement feature"],
            "requirement_ids": ["REQ-001"],
        }

        monkeypatch.setattr(MODULE, "_resolve_skill_script", lambda *_args, **_kwargs: Path("/tmp/fake_script.py"))
        monkeypatch.setattr(MODULE, "_run_tool_json", lambda *_args, **_kwargs: {"ok": True, "status": "dispatch_started"})
        monkeypatch.setattr(MODULE, "_git_text", lambda *_args, **_kwargs: "abc1234")

        out = MODULE._dispatch_task_packet(
            req,
            task,
            plan_task,
            stage,
            "plan-1",
            "codex",
            start_from_branch_override="codex/run-1/dev-1/task-001",
        )
        assert out["ok"] is True
        assert task["status"] == expected_status
        assert task["owner_slot"] == expected_slot
        assert task["gapfix_state"]["active"] is False
        assert task["gapfix_state"]["active_batch_id"] is None


def test_append_task_blocker_compacts_duplicates_and_bounds():
    task = {"blockers": []}
    for _ in range(5):
        MODULE._append_task_blocker(
            task,
            summary="task evidence invalid for TASK-001",
            details={"code": "task_evidence_invalid", "evidence_path": "/tmp/evidence.json"},
        )
    blockers = task.get("blockers")
    assert isinstance(blockers, list) and len(blockers) == 1
    assert blockers[0].get("occurrences") == 5

    for idx in range(40):
        MODULE._append_task_blocker(
            task,
            summary=f"unique-{idx}",
            details={"code": f"c-{idx}", "evidence_path": f"/tmp/e-{idx}.json"},
        )
    blockers = task.get("blockers")
    assert isinstance(blockers, list)
    assert len(blockers) <= 25


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))


def test_new_project_accepts_mission_scope_file_sources():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        mission_path = root / "mission.txt"
        scope_path = root / "scope.md"
        mission_path.write_text("Build MyBoard MCP backend\n", encoding="utf-8")
        scope_path.write_text("Implement API, tests, docs.\n", encoding="utf-8")

        out = run_payload(
            {
                "command": "/op-new-project",
                "repo_root": str(root),
                "mission_file": str(mission_path),
                "scope_file": str(scope_path),
            }
        )

        assert out["ok"] is True
        state = json.loads((root / "reports" / "optimus-prime" / "planning" / "STATE.json").read_text(encoding="utf-8"))
        mission_source = state.get("mission_source", {})
        scope_source = state.get("scope_source", {})
        assert mission_source.get("mode") == "file"
        assert mission_source.get("path") == str(mission_path.resolve())
        assert scope_source.get("mode") == "file"
        assert scope_source.get("path") == str(scope_path.resolve())


def test_new_project_rejects_mixed_mission_input_modes():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        mission_path = root / "mission.txt"
        mission_path.write_text("Build MyBoard MCP backend\n", encoding="utf-8")
        with pytest.raises(MODULE.OpError) as exc_info:
            run_payload(
                {
                    "command": "/op-new-project",
                    "repo_root": str(root),
                    "mission": "inline mission",
                    "mission_file": str(mission_path),
                    "scope": "inline scope",
                }
            )
        assert exc_info.value.code == "input_error"
        assert "mutually exclusive" in exc_info.value.message


def test_planner_validator_rejects_missing_required_artifacts():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        req = MODULE.parse_request({"command": "/op-plan", "repo_root": str(root)})
        bundle_path = root / "reports" / "optimus-prime" / "planning" / "llm" / "attempt-1" / "PLAN_BUNDLE.jsonl"
        write_planner_bundle(
            bundle_path,
            [
                planner_row(
                    "PLAN_PACKETS.json",
                    "json",
                    {
                        "schema_version": "1.0",
                        "plan_id": "plan-test",
                        "phases": [],
                        "requirements": [],
                        "tasks": [],
                    },
                )
            ],
        )
        payload, errors = MODULE._planner_validate_bundle(req, bundle_path)
        assert payload is None
        assert any(item.get("code") == "planner_bundle_schema_error" for item in errors)
        assert any("missing required artifacts" in str(item.get("message")) for item in errors)


def test_op_plan_retry_exhausted_after_ten_failed_attempts(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        run_payload(
            {
                "command": "/op-new-project",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )

        def fake_run_codex_exec(**_kwargs: object) -> int:
            return 0

        monkeypatch.setattr(MODULE, "run_codex_exec", fake_run_codex_exec)
        with pytest.raises(MODULE.OpError) as exc_info:
            run_payload(
                {
                    "command": "/op-plan",
                    "repo_root": str(root),
                    "override_old_plan": True,
                }
            )
        assert exc_info.value.code == "planner_retry_exhausted"
        attempts_log = root / "reports" / "optimus-prime" / "planning" / "llm" / "PLAN_GENERATION_ATTEMPTS.jsonl"
        lines = [line for line in attempts_log.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(lines) == 10


def test_op_plan_retries_and_succeeds_after_validation_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        run_payload(
            {
                "command": "/op-new-project",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )

        original_validate = MODULE._planner_validate_bundle
        calls = {"count": 0}

        def fake_validate(req: object, bundle_path: Path):
            calls["count"] += 1
            if calls["count"] == 1:
                return None, [{"code": "planner_bundle_schema_error", "message": "simulated-first-attempt-failure"}]
            return original_validate(req, bundle_path)

        monkeypatch.setattr(MODULE, "_planner_validate_bundle", fake_validate)
        monkeypatch.setattr(MODULE.sys.stdout, "isatty", lambda: True)
        out = run_payload(
            {
                "command": "/op-plan",
                "repo_root": str(root),
                "override_old_plan": True,
            }
        )
        assert out["ok"] is True
        logs = capsys.readouterr().out
        assert "planner generation attempt 1/10" in logs
        assert "planner generation failed on attempt #1; applying necessary fixes and retrying." in logs
        assert "planner generation succeeded on attempt #2" in logs
        assert calls["count"] >= 2
        attempts_log = root / "reports" / "optimus-prime" / "planning" / "llm" / "PLAN_GENERATION_ATTEMPTS.jsonl"
        lines = [line for line in attempts_log.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(lines) >= 2


def test_initialize_fails_when_planner_retry_exhausted(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)

        def fail_planner(*_args: object, **_kwargs: object):
            raise MODULE.OpError("planner_retry_exhausted", "planner loop failed", stage="plan")

        monkeypatch.setattr(MODULE, "_run_llm_plan_generation", fail_planner)
        with pytest.raises(MODULE.OpError) as exc_info:
            run_payload(
                {
                    "command": "/op-initialize",
                    "repo_root": str(root),
                    "mission": "Build MyBoard",
                    "scope": "Board workflow",
                }
            )
        assert exc_info.value.code == "planner_retry_exhausted"


def test_hardening_rule_applies_only_when_requirement_group_has_more_than_two_tasks():
    two_task_group = [
        {"task_id": "TASK-001", "title": "Implement A", "requirement_ids": ["REQ-001"], "depends_on": []},
        {"task_id": "TASK-002", "title": "Implement B", "requirement_ids": ["REQ-001"], "depends_on": ["TASK-001"]},
    ]
    no_error = MODULE._validate_hardening_rule(two_task_group)
    assert no_error == []

    three_task_group = [
        {"task_id": "TASK-001", "title": "Implement A", "requirement_ids": ["REQ-001"], "depends_on": []},
        {"task_id": "TASK-002", "title": "Implement B", "requirement_ids": ["REQ-001"], "depends_on": ["TASK-001"]},
        {"task_id": "TASK-003", "title": "Ship feature", "requirement_ids": ["REQ-001"], "depends_on": ["TASK-002"]},
    ]
    errors = MODULE._validate_hardening_rule(three_task_group)
    assert any(item.get("code") == "planner_bundle_schema_error" for item in errors)


def test_bundle_validator_enforces_terminal_hardening_rule():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        run_payload(
            {
                "command": "/op-new-project",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        run_payload(
            {
                "command": "/op-plan",
                "repo_root": str(root),
                "override_old_plan": True,
            }
        )

        planning_root = (root / "reports" / "optimus-prime" / "planning").resolve()
        bundle_path = planning_root / "llm" / "attempt-1" / "PLAN_BUNDLE.jsonl"
        rows = [json.loads(line) for line in bundle_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        for row in rows:
            path = str(row.get("artifact_path") or "")
            content = row.get("content")
            if path == "PLAN_PACKETS.json" and isinstance(content, dict):
                content["requirements"] = [
                    {
                        "id": "REQ-001",
                        "title": "Core workflow",
                        "acceptance_criteria": ["core path"],
                        "verify_commands": ["python3 -m pytest"],
                    }
                ]
                for task in content.get("tasks", []):
                    if isinstance(task, dict):
                        task["requirement_ids"] = ["REQ-001"]
                row["checksum_sha256"] = planner_checksum("json", content)
            elif path == "TASK_EXECUTION_STATE.json" and isinstance(content, dict):
                for task in content.get("tasks", []):
                    if isinstance(task, dict):
                        task["requirement_ids"] = ["REQ-001"]
                row["checksum_sha256"] = planner_checksum("json", content)
            elif path.startswith("evidence/") and path.endswith("/TASK_EVIDENCE.json") and isinstance(content, dict):
                content["requirement_ids"] = ["REQ-001"]
                row["checksum_sha256"] = planner_checksum("json", content)
        write_planner_bundle(bundle_path, rows)

        _, errors = MODULE.validate_bundle_contract(bundle_path, planning_root)
        assert any(
            "needs at least 2 terminal hardening/review tasks" in str(item.get("message"))
            for item in errors
        )


def test_op_plan_returns_planner_execution_failed_when_codex_exec_unavailable(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        run_payload(
            {
                "command": "/op-new-project",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )

        def fail_run_codex_exec(**_kwargs: object) -> int:
            raise FileNotFoundError("codex")

        monkeypatch.setattr(MODULE, "run_codex_exec", fail_run_codex_exec)
        with pytest.raises(MODULE.OpError) as exc_info:
            run_payload(
                {
                    "command": "/op-plan",
                    "repo_root": str(root),
                    "override_old_plan": True,
                }
            )
        assert exc_info.value.code == "planner_execution_failed"


def test_planner_prompt_includes_bundled_example_path():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        req = MODULE.parse_request(
            {
                "command": "/op-plan",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        mission_source, scope_source = MODULE._resolve_mission_scope_sources(req, stage="plan", required=False)
        bundle_path = root / "reports" / "optimus-prime" / "planning" / "llm" / "attempt-1" / "PLAN_BUNDLE.jsonl"
        prompt = MODULE._planner_prompt_text(
            req=req,
            bundle_path=bundle_path,
            mission_source=mission_source,
            scope_source=scope_source,
            prior_errors=[],
        )
        expected = str((MODULE.SCRIPT_DIR / "llm" / "examples" / "op-plan" / "reports" / "optimus-prime" / "planning").resolve())
        assert expected in prompt
        assert "strategy/current/strategy_packet.md" in prompt
        assert "strategy/current/STRATEGY_SUMMARY.md" in prompt
        assert "STATE.md" in prompt


def test_planner_prompt_prefers_repo_local_template_override():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        repo_template = root / "scripts" / "op" / "planner" / "prompts" / "llm_plan_prompt.md"
        repo_template.parent.mkdir(parents=True, exist_ok=True)
        repo_template.write_text(
            "\n".join(
                [
                    "REPO LOCAL PLANNER TEMPLATE",
                    "bundle={{BUNDLE_PATH}}",
                    "validator={{VALIDATOR_COMMAND}}",
                    "repo={{REPO_ROOT}}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        req = MODULE.parse_request(
            {
                "command": "/op-plan",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        mission_source, scope_source = MODULE._resolve_mission_scope_sources(req, stage="plan", required=False)
        bundle_path = root / "reports" / "optimus-prime" / "planning" / "llm" / "attempt-1" / "PLAN_BUNDLE.jsonl"
        prompt = MODULE._planner_prompt_text(
            req=req,
            bundle_path=bundle_path,
            mission_source=mission_source,
            scope_source=scope_source,
            prior_errors=[],
        )
        assert "REPO LOCAL PLANNER TEMPLATE" in prompt


def test_planner_prompt_template_path_falls_back_to_engine_when_repo_override_missing():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        resolved = MODULE._planner_prompt_template_path(root)
        assert resolved == MODULE.PLANNER_PROMPT_TEMPLATE_PATH.resolve()


def test_planner_prompt_omits_strategy_note_when_skip_strategy_requested():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        req = MODULE.parse_request(
            {
                "command": "/op-plan",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
                "skip_strategy": True,
            }
        )
        mission_source, scope_source = MODULE._resolve_mission_scope_sources(req, stage="plan", required=False)
        bundle_path = root / "reports" / "optimus-prime" / "planning" / "llm" / "attempt-1" / "PLAN_BUNDLE.jsonl"
        prompt = MODULE._planner_prompt_text(
            req=req,
            bundle_path=bundle_path,
            mission_source=mission_source,
            scope_source=scope_source,
            prior_errors=[],
        )
        assert "strategy/current/strategy_packet.md" not in prompt
        assert "strategy/current/STRATEGY_SUMMARY.md" not in prompt


def test_planner_bundled_example_contract_is_schema_current():
    example_root = (MODULE.SCRIPT_DIR / "llm" / "examples" / "op-plan" / "reports" / "optimus-prime" / "planning").resolve()
    assert example_root.exists()
    with tempfile.TemporaryDirectory() as tmp:
        bundle_path = Path(tmp) / "PLAN_BUNDLE.jsonl"
        rows: list[dict[str, object]] = []
        for path in sorted(example_root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(example_root).as_posix()
            if path.suffix.lower() == ".json":
                content_type = "json"
                content = json.loads(path.read_text(encoding="utf-8"))
            else:
                content_type = "text"
                content = path.read_text(encoding="utf-8")
            rows.append(planner_row(rel, content_type, content))
        write_planner_bundle(bundle_path, rows)
        bundle, errors = MODULE.validate_bundle_contract(bundle_path, example_root)
        assert errors == []
        assert isinstance(bundle, dict)
        plan_packets = bundle["PLAN_PACKETS.json"].content
        assert isinstance(plan_packets, dict)
        lane_base_branches = plan_packets.get("lane_base_branches")
        assert isinstance(lane_base_branches, dict)
        tasks = plan_packets.get("tasks")
        assert isinstance(tasks, list) and tasks
        task_lane_ids: set[str] = set()
        for task in tasks:
            assert isinstance(task, dict)
            assert isinstance(task.get("lane_id"), str) and task.get("lane_id")
            task_lane_ids.add(str(task.get("lane_id")))
            assert task.get("status") == "pending"
            assert isinstance(task.get("gaps_that_need_patching"), list)
        assert task_lane_ids.issubset(set(str(item) for item in lane_base_branches.keys()))


def test_git_bootstrap_prompt_references_shared_validator_script():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        req = MODULE.parse_request(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        prompt = MODULE._git_bootstrap_prompt_text(req=req, prior_errors=[])
        validator_script = str((MODULE.SCRIPT_DIR / "planner" / "validate_git_bootstrap.py").resolve())
        assert validator_script in prompt
        assert "same verifier OP will run" in prompt


def test_git_bootstrap_skips_llm_when_repo_already_initialized(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        called = {"value": False}

        def fake_run_codex_exec(**_kwargs: object) -> int:
            called["value"] = True
            return 0

        monkeypatch.setattr(MODULE, "run_codex_exec", fake_run_codex_exec)
        req = MODULE.parse_request(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        warnings, artifacts = MODULE._ensure_git_initialized_for_initialize(req)
        assert any(item.get("code") == "git_origin_missing" for item in warnings)
        assert artifacts == []
        assert called["value"] is False


def test_git_bootstrap_initializes_non_git_repo_with_llm_then_validates(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        req = MODULE.parse_request(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )

        def fake_run_codex_exec(*, repo_root: Path, **_kwargs: object) -> int:
            subprocess.run(["git", "init", "-b", "main"], cwd=str(repo_root), check=True, capture_output=True, text=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(repo_root), check=True, capture_output=True, text=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(repo_root), check=True, capture_output=True, text=True)
            (repo_root / "README.md").write_text("placeholder\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=str(repo_root), check=True, capture_output=True, text=True)
            subprocess.run(["git", "commit", "-m", "bootstrap"], cwd=str(repo_root), check=True, capture_output=True, text=True)
            subprocess.run(["git", "branch", "RAB-BASE"], cwd=str(repo_root), check=True, capture_output=True, text=True)
            return 0

        monkeypatch.setattr(MODULE, "run_codex_exec", fake_run_codex_exec)
        warnings, artifacts = MODULE._ensure_git_initialized_for_initialize(req)
        assert MODULE._is_git_work_tree(root) is True
        assert MODULE._git_text(root, "rev-parse", "HEAD")
        assert MODULE._git_text(root, "show-ref", "--verify", "refs/heads/main")
        assert MODULE._git_text(root, "show-ref", "--verify", "refs/heads/RAB-BASE")
        assert MODULE._git_text(root, "branch", "--show-current") == "RAB-BASE"
        assert isinstance(warnings, list)
        assert artifacts


def test_git_bootstrap_existing_rab_base_repo_gets_main_branch_created_and_checks_out_rab_base():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        git(root, "init", "-b", "RAB-BASE")
        git(root, "config", "user.email", "test@example.com")
        git(root, "config", "user.name", "Test User")
        (root / "README.md").write_text("seed\n", encoding="utf-8")
        git(root, "add", "README.md")
        git(root, "commit", "-m", "seed")

        req = MODULE.parse_request(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )

        warnings, artifacts = MODULE._ensure_git_initialized_for_initialize(req)
        assert any(item.get("code") == "git_origin_missing" for item in warnings)
        assert artifacts == []
        assert MODULE._git_text(root, "show-ref", "--verify", "refs/heads/main")
        assert MODULE._git_text(root, "show-ref", "--verify", "refs/heads/RAB-BASE")
        assert MODULE._git_text(root, "branch", "--show-current") == "RAB-BASE"


def test_validate_git_bootstrap_can_require_primary_branch():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        git(root, "init", "-b", "RAB-BASE")
        git(root, "config", "user.email", "test@example.com")
        git(root, "config", "user.name", "Test User")
        (root / "README.md").write_text("seed\n", encoding="utf-8")
        git(root, "add", "README.md")
        git(root, "commit", "-m", "seed")

        result = MODULE.validate_git_bootstrap(
            repo_root=root,
            required_branch="RAB-BASE",
            require_readme=True,
            required_primary_branch="main",
        )
        assert result["ok"] is False
        assert any(item.get("code") == "git_primary_branch_missing" for item in result["errors"])


def test_private_publish_create_or_reuse_pushes_main_and_rab_base(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        remote_root = root / "remote.git"
        build_repo(root)
        git(root, "branch", "RAB-BASE")
        git(root, "checkout", "RAB-BASE")
        git(root, "init", "--bare", str(remote_root))

        req = MODULE.parse_request(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
                "publish_private_repo": True,
                "github_owner": "slobodanmargetic988",
                "github_repo_name": "b2b-dog-cat",
            }
        )

        original_run = MODULE._run
        commands: list[list[str]] = []
        origin_state = {"url": None}

        def fake_run(cmd: list[str], *, cwd: Path, stdin_text: str | None = None):
            commands.append(list(cmd))
            if cmd[:3] == ["git", "remote", "get-url"]:
                if origin_state["url"] is None:
                    return 2, "", "no such remote"
                return 0, origin_state["url"] + "\n", ""
            if cmd[:4] == ["gh", "repo", "view", "slobodanmargetic988/b2b-dog-cat"] and "--json" in cmd:
                return 1, "", "not found"
            if cmd[:4] == ["gh", "repo", "create", "slobodanmargetic988/b2b-dog-cat"]:
                origin_state["url"] = str(remote_root.resolve())
                original_run(["git", "remote", "add", "origin", origin_state["url"]], cwd=cwd)
                return 0, "", ""
            if cmd[:3] == ["gh", "auth", "status"]:
                return 0, "ok\n", ""
            if cmd[:3] == ["gh", "api", "repos/slobodanmargetic988/b2b-dog-cat"] and "--jq" in cmd:
                payload = {
                    "full_name": "slobodanmargetic988/b2b-dog-cat",
                    "visibility": "private",
                    "private": True,
                    "default_branch": "main",
                    "html_url": "https://github.com/slobodanmargetic988/b2b-dog-cat",
                }
                return 0, json.dumps(payload) + "\n", ""
            if cmd[:4] == ["gh", "repo", "edit", "slobodanmargetic988/b2b-dog-cat"] and "--default-branch" in cmd:
                return 0, "", ""
            return original_run(cmd, cwd=cwd, stdin_text=stdin_text)

        monkeypatch.setattr(MODULE, "_run", fake_run)

        warnings, artifacts = MODULE._ensure_git_initialized_for_initialize(req)

        assert warnings == []
        publish_artifact = root / "reports" / "optimus-prime" / "planning" / "llm" / "git-bootstrap" / "PUBLISH_REPO.json"
        assert str(publish_artifact.resolve()) in artifacts
        payload = json.loads(publish_artifact.read_text(encoding="utf-8"))
        assert payload["repo_slug"] == "slobodanmargetic988/b2b-dog-cat"
        assert payload["visibility"] == "private"
        assert payload["default_branch"] == "main"
        assert payload["pushed_branches"] == ["main", "RAB-BASE"]
        assert ["git", "push", "-u", "origin", "main"] in commands
        assert ["git", "push", "-u", "origin", "RAB-BASE"] in commands


def test_git_bootstrap_raises_when_llm_output_fails_deterministic_validator(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        req = MODULE.parse_request(
            {
                "command": "/op-initialize",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )

        def fake_run_codex_exec(**_kwargs: object) -> int:
            return 0

        monkeypatch.setattr(MODULE, "run_codex_exec", fake_run_codex_exec)
        with pytest.raises(MODULE.OpError) as exc_info:
            MODULE._ensure_git_initialized_for_initialize(req)
        assert exc_info.value.code == "git_bootstrap_failed"


def test_planner_validator_rejects_unexpected_artifact_rows():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        run_payload(
            {
                "command": "/op-new-project",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        run_payload(
            {
                "command": "/op-plan",
                "repo_root": str(root),
                "override_old_plan": True,
            }
        )

        bundle_path = root / "reports" / "optimus-prime" / "planning" / "llm" / "attempt-1" / "PLAN_BUNDLE.jsonl"
        lines = [line for line in bundle_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        rows = [json.loads(line) for line in lines]
        rows.append(planner_row("UNEXPECTED_FILE.json", "json", {"hello": "world"}))
        write_planner_bundle(bundle_path, rows)

        req = MODULE.parse_request({"command": "/op-plan", "repo_root": str(root)})
        payload, errors = MODULE._planner_validate_bundle(req, bundle_path)
        assert payload is None
        assert any(item.get("code") == "planner_bundle_schema_error" for item in errors)
        assert any("unexpected artifacts" in str(item.get("message")) for item in errors)


def test_planner_validator_rejects_non_string_task_fields():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        run_payload(
            {
                "command": "/op-new-project",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        run_payload(
            {
                "command": "/op-plan",
                "repo_root": str(root),
                "override_old_plan": True,
            }
        )

        bundle_path = root / "reports" / "optimus-prime" / "planning" / "llm" / "attempt-1" / "PLAN_BUNDLE.jsonl"
        rows = [json.loads(line) for line in bundle_path.read_text(encoding="utf-8").splitlines() if line.strip()]

        for row in rows:
            if row.get("artifact_path") == "PLAN_PACKETS.json":
                row["content"]["tasks"][0]["task_id"] = 123
                row["checksum_sha256"] = planner_checksum("json", row["content"])
                break
        write_planner_bundle(bundle_path, rows)

        req = MODULE.parse_request({"command": "/op-plan", "repo_root": str(root)})
        payload, errors = MODULE._planner_validate_bundle(req, bundle_path)
        assert payload is None
    assert any(item.get("code") == "planner_bundle_schema_error" for item in errors)
    assert any("task_id must be string" in str(item.get("message")) for item in errors)


def test_planner_validator_rejects_missing_lane_base_branches():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        run_payload(
            {
                "command": "/op-new-project",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        run_payload(
            {
                "command": "/op-plan",
                "repo_root": str(root),
                "override_old_plan": True,
            }
        )

        bundle_path = root / "reports" / "optimus-prime" / "planning" / "llm" / "attempt-1" / "PLAN_BUNDLE.jsonl"
        rows = [json.loads(line) for line in bundle_path.read_text(encoding="utf-8").splitlines() if line.strip()]

        for row in rows:
            if row.get("artifact_path") == "PLAN_PACKETS.json":
                row["content"].pop("lane_base_branches", None)
                row["checksum_sha256"] = planner_checksum("json", row["content"])
                break

        write_planner_bundle(bundle_path, rows)
        req = MODULE.parse_request({"command": "/op-plan", "repo_root": str(root)})
        payload, errors = MODULE._planner_validate_bundle(req, bundle_path)
        assert payload is None
        assert any("lane_base_branches" in str(item.get("message")) for item in errors)


def test_planner_validator_rejects_incomplete_lane_base_branches():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        run_payload(
            {
                "command": "/op-new-project",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        run_payload(
            {
                "command": "/op-plan",
                "repo_root": str(root),
                "override_old_plan": True,
            }
        )

        bundle_path = root / "reports" / "optimus-prime" / "planning" / "llm" / "attempt-1" / "PLAN_BUNDLE.jsonl"
        rows = [json.loads(line) for line in bundle_path.read_text(encoding="utf-8").splitlines() if line.strip()]

        for row in rows:
            if row.get("artifact_path") == "PLAN_PACKETS.json":
                row["content"]["lane_base_branches"] = {}
                row["checksum_sha256"] = planner_checksum("json", row["content"])
                break

        write_planner_bundle(bundle_path, rows)
        req = MODULE.parse_request({"command": "/op-plan", "repo_root": str(root)})
        payload, errors = MODULE._planner_validate_bundle(req, bundle_path)
        assert payload is None
        assert any("must include every tasks[].lane_id" in str(item.get("message")) for item in errors)


def test_planner_validator_rejects_missing_task_verification_contract():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        run_payload(
            {
                "command": "/op-new-project",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        run_payload(
            {
                "command": "/op-plan",
                "repo_root": str(root),
                "override_old_plan": True,
            }
        )

        bundle_path = root / "reports" / "optimus-prime" / "planning" / "llm" / "attempt-1" / "PLAN_BUNDLE.jsonl"
        rows = [json.loads(line) for line in bundle_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        for row in rows:
            if row.get("artifact_path") == "PLAN_PACKETS.json":
                del row["content"]["tasks"][0]["verification_contract"]
                row["checksum_sha256"] = planner_checksum("json", row["content"])
                break
        write_planner_bundle(bundle_path, rows)

        req = MODULE.parse_request({"command": "/op-plan", "repo_root": str(root)})
        payload, errors = MODULE._planner_validate_bundle(req, bundle_path)
        assert payload is None
        assert any("verification_contract" in str(item.get("message")) for item in errors)


def test_planner_validator_rejects_missing_task_kind():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        run_payload(
            {
                "command": "/op-new-project",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        run_payload(
            {
                "command": "/op-plan",
                "repo_root": str(root),
                "override_old_plan": True,
            }
        )

        bundle_path = root / "reports" / "optimus-prime" / "planning" / "llm" / "attempt-1" / "PLAN_BUNDLE.jsonl"
        rows = [json.loads(line) for line in bundle_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        for row in rows:
            if row.get("artifact_path") == "PLAN_PACKETS.json":
                del row["content"]["tasks"][0]["task_kind"]
                row["checksum_sha256"] = planner_checksum("json", row["content"])
                break
        write_planner_bundle(bundle_path, rows)

        req = MODULE.parse_request({"command": "/op-plan", "repo_root": str(root)})
        payload, errors = MODULE._planner_validate_bundle(req, bundle_path)
        assert payload is None
        assert any("task_kind" in str(item.get("message")) for item in errors)


def test_planner_validator_rejects_invalid_task_kind_mode_pair():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        run_payload(
            {
                "command": "/op-new-project",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        run_payload(
            {
                "command": "/op-plan",
                "repo_root": str(root),
                "override_old_plan": True,
            }
        )

        bundle_path = root / "reports" / "optimus-prime" / "planning" / "llm" / "attempt-1" / "PLAN_BUNDLE.jsonl"
        rows = [json.loads(line) for line in bundle_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        for row in rows:
            if row.get("artifact_path") == "PLAN_PACKETS.json":
                row["content"]["tasks"][0]["task_kind"] = "lane_test"
                row["content"]["tasks"][0]["verification_contract"]["mode"] = "hardening"
                row["checksum_sha256"] = planner_checksum("json", row["content"])
                break
        write_planner_bundle(bundle_path, rows)

        req = MODULE.parse_request({"command": "/op-plan", "repo_root": str(root)})
        payload, errors = MODULE._planner_validate_bundle(req, bundle_path)
        assert payload is None
        assert any("mode must be one of lane_test" in str(item.get("message")) for item in errors)


def test_planner_validator_rejects_task_kind_mismatch_between_plan_and_task_state():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        run_payload(
            {
                "command": "/op-new-project",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        run_payload(
            {
                "command": "/op-plan",
                "repo_root": str(root),
                "override_old_plan": True,
            }
        )

        bundle_path = root / "reports" / "optimus-prime" / "planning" / "llm" / "attempt-1" / "PLAN_BUNDLE.jsonl"
        rows = [json.loads(line) for line in bundle_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        for row in rows:
            if row.get("artifact_path") == "TASK_EXECUTION_STATE.json":
                row["content"]["tasks"][0]["task_kind"] = "lane_review"
                row["checksum_sha256"] = planner_checksum("json", row["content"])
                break

        write_planner_bundle(bundle_path, rows)
        req = MODULE.parse_request({"command": "/op-plan", "repo_root": str(root)})
        payload, errors = MODULE._planner_validate_bundle(req, bundle_path)
        assert payload is None
        assert any("must match PLAN_PACKETS task_kind" in str(item.get("message")) for item in errors)


def test_planner_validator_rejects_missing_evidence_expectation_fields():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        run_payload(
            {
                "command": "/op-new-project",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        run_payload(
            {
                "command": "/op-plan",
                "repo_root": str(root),
                "override_old_plan": True,
            }
        )

        bundle_path = root / "reports" / "optimus-prime" / "planning" / "llm" / "attempt-1" / "PLAN_BUNDLE.jsonl"
        rows = [json.loads(line) for line in bundle_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        for row in rows:
            if row.get("artifact_path") == "evidence/TASK-001/TASK_EVIDENCE.json":
                row["content"]["summary"].pop("expectation", None)
                row["content"]["summary"].pop("expectation_met", None)
                row["content"]["summary"].pop("failure_class", None)
                row["checksum_sha256"] = planner_checksum("json", row["content"])
                break
        write_planner_bundle(bundle_path, rows)

        req = MODULE.parse_request({"command": "/op-plan", "repo_root": str(root)})
        payload, errors = MODULE._planner_validate_bundle(req, bundle_path)
        assert payload is None
        assert any("summary.expectation" in str(item.get("message")) for item in errors)


def test_planner_validator_rejects_non_string_owner_slot_and_review_decision():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        run_payload(
            {
                "command": "/op-new-project",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        run_payload(
            {
                "command": "/op-plan",
                "repo_root": str(root),
                "override_old_plan": True,
            }
        )

        bundle_path = root / "reports" / "optimus-prime" / "planning" / "llm" / "attempt-1" / "PLAN_BUNDLE.jsonl"
        rows = [json.loads(line) for line in bundle_path.read_text(encoding="utf-8").splitlines() if line.strip()]

        for row in rows:
            if row.get("artifact_path") == "TASK_EXECUTION_STATE.json":
                row["content"]["tasks"][0]["owner_slot"] = 123
                row["checksum_sha256"] = planner_checksum("json", row["content"])
            if row.get("artifact_path") == "evidence/TASK-001/TASK_EVIDENCE.json":
                row["content"]["review"]["decision"] = 456
                row["checksum_sha256"] = planner_checksum("json", row["content"])
        write_planner_bundle(bundle_path, rows)

        req = MODULE.parse_request({"command": "/op-plan", "repo_root": str(root)})
        payload, errors = MODULE._planner_validate_bundle(req, bundle_path)
        assert payload is None
        assert any("owner_slot must be string|null" in str(item.get("message")) for item in errors)
        assert any("review.decision must be string|null" in str(item.get("message")) for item in errors)


def test_planner_validator_enforces_gap_closure_required_true_and_gap_optional_field_types():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        run_payload(
            {
                "command": "/op-new-project",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        run_payload(
            {
                "command": "/op-plan",
                "repo_root": str(root),
                "override_old_plan": True,
            }
        )

        bundle_path = root / "reports" / "optimus-prime" / "planning" / "llm" / "attempt-1" / "PLAN_BUNDLE.jsonl"
        rows = [json.loads(line) for line in bundle_path.read_text(encoding="utf-8").splitlines() if line.strip()]

        for row in rows:
            if row.get("artifact_path") == "GAPS.json":
                row["content"]["gaps"] = [
                    {
                        "gap_id": "gap-x",
                        "phase_id": "phase-1",
                        "severity": "high",
                        "result": "blocked",
                        "evidence_ref": "reports/optimus-prime/planning/evidence/TASK-001/TASK_EVIDENCE.json",
                        "opened_at": "2026-01-01T00:00:00Z",
                        "status": "open",
                        "category": "task_blocked",
                        "reason_codes": ["task_state_blocked"],
                        "closure_task_id": "GAPFIX-XXXX",
                        "last_seen_open_at": "2026-01-01T00:00:00Z",
                        "closure_required": False,
                        "closure_evidence_ref": 123,
                        "closed_by_task_id": 456,
                        "closed_at": None,
                        "resolution_candidate_at": None,
                    }
                ]
                row["checksum_sha256"] = planner_checksum("json", row["content"])
        write_planner_bundle(bundle_path, rows)

        req = MODULE.parse_request({"command": "/op-plan", "repo_root": str(root)})
        payload, errors = MODULE._planner_validate_bundle(req, bundle_path)
        assert payload is None
        assert any("closure_required must be true" in str(item.get("message")) for item in errors)
        assert any("closure_evidence_ref must be string|null" in str(item.get("message")) for item in errors)
        assert any("closed_by_task_id must be string|null" in str(item.get("message")) for item in errors)


def test_planner_validator_rejects_phase_cycle_and_phase_task_mismatch():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        run_payload(
            {
                "command": "/op-new-project",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        run_payload(
            {
                "command": "/op-plan",
                "repo_root": str(root),
                "override_old_plan": True,
            }
        )

        bundle_path = root / "reports" / "optimus-prime" / "planning" / "llm" / "attempt-1" / "PLAN_BUNDLE.jsonl"
        rows = [json.loads(line) for line in bundle_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        for row in rows:
            if row.get("artifact_path") == "PLAN_PACKETS.json":
                row["content"]["phases"] = [
                    {
                        "phase_id": "phase-1",
                        "task_ids": ["TASK-001"],
                        "depends_on_phase_ids": ["phase-2"],
                        "entry_criteria": ["phase_dependencies_done"],
                        "exit_criteria": ["all_tasks_review_done"],
                    },
                    {
                        "phase_id": "phase-2",
                        "task_ids": ["TASK-002"],
                        "depends_on_phase_ids": ["phase-1"],
                        "entry_criteria": ["phase_dependencies_done"],
                        "exit_criteria": ["all_tasks_review_done"],
                    },
                ]
                row["checksum_sha256"] = planner_checksum("json", row["content"])
                break
        write_planner_bundle(bundle_path, rows)

        req = MODULE.parse_request({"command": "/op-plan", "repo_root": str(root)})
        payload, errors = MODULE._planner_validate_bundle(req, bundle_path)
        assert payload is None
        assert any("phase DAG contains cycle" in str(item.get("message")) for item in errors)
        assert any("tasks missing from phase.task_ids mapping" in str(item.get("message")) for item in errors)


def test_planner_validator_rejects_invalid_state_source_shapes():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_repo(root)
        run_payload(
            {
                "command": "/op-new-project",
                "repo_root": str(root),
                "mission": "Build MyBoard",
                "scope": "Board workflow",
            }
        )
        run_payload(
            {
                "command": "/op-plan",
                "repo_root": str(root),
                "override_old_plan": True,
            }
        )

        bundle_path = root / "reports" / "optimus-prime" / "planning" / "llm" / "attempt-1" / "PLAN_BUNDLE.jsonl"
        rows = [json.loads(line) for line in bundle_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        for row in rows:
            if row.get("artifact_path") == "STATE.json":
                row["content"]["mission_source"] = {"mode": "inline", "display": "x"}
                row["content"]["scope_source"] = "invalid"
                row["checksum_sha256"] = planner_checksum("json", row["content"])
                break
        write_planner_bundle(bundle_path, rows)

        req = MODULE.parse_request({"command": "/op-plan", "repo_root": str(root)})
        payload, errors = MODULE._planner_validate_bundle(req, bundle_path)
        assert payload is None
        assert any("STATE.mission_source missing required keys" in str(item.get("message")) for item in errors)
        assert any("STATE.scope_source must be object" in str(item.get("message")) for item in errors)


def test_load_dispatch_assignments_gapfix_requires_existing_gap_batch_ref():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        planning = root / "reports" / "optimus-prime" / "planning"
        planning.mkdir(parents=True, exist_ok=True)
        (planning / "WORK_DISPATCH_PLAN.json").write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "updated_at": "2026-01-01T00:00:00Z",
                    "active_phase_id": "phase-1",
                    "assignments": [
                        {
                            "task_id": "TASK-001",
                            "lane_id": "phase-1/lane-a",
                            "phase_id": "phase-1",
                            "next_stage": "dev",
                            "next_role": "developer",
                            "slot": "dev-1",
                            "dispatch_policy": "resume_if_same_lane",
                            "is_gapfix": True,
                            "gap_batch_id": "task-001-dev-c1-abc123",
                            "gap_batch_ref": str(
                                root
                                / "reports"
                                / "optimus-prime"
                                / "planning"
                                / "gapfix"
                                / "TASK-001"
                                / "batch-task-001-dev-c1-abc123.json"
                            ),
                            "gap_stage": "dev",
                            "source_gap_ids": ["GAP-TASK-001-001"],
                        }
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        assignments, warnings, readable = MODULE._load_work_dispatch_plan_assignments(root, active_phase_id="phase-1")
        assert readable is True
        assert assignments == []
        warning_codes = [row.get("code") for row in warnings if isinstance(row, dict)]
        assert "dispatch_assignment_invalid" in warning_codes


def test_dispatch_filter_blocks_only_hard_gated_assignment_aliases(monkeypatch: pytest.MonkeyPatch):
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
        req = MODULE.parse_request({"command": "/op-build", "repo_root": str(root), "dry_run": True})
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        build_state["profile_aliases"] = ["codex-first", "codex-second"]
        build_state["slot_profile_assignments"] = {"dev-1": "codex-first", "dev-2": "codex-second"}
        MODULE._ensure_worker_registry_v2(root, build_state)
        registry_path = root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
        registry_payload = json.loads(registry_path.read_text(encoding="utf-8"))
        for row in registry_payload.get("workers", []):
            if row.get("slot") in {"dev-1", "dev-2"}:
                row["worktree_root"] = str(root)
                row["branch"] = f"codex/{row['slot']}/task"
        registry_path.write_text(json.dumps(registry_payload, indent=2) + "\n", encoding="utf-8")
        workstation_registry_path = root / "reports" / "optimus-prime" / "planning" / "WORKSTATION_REGISTRY.json"
        workstation_registry_path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "updated_at": "2026-01-01T00:00:00Z",
                    "slots": {
                        "dev-1": {
                            "slot": "dev-1",
                            "status": "ready",
                            "target_task_id": "TASK-001",
                            "target_lane_id": "phase-1/lane-a",
                            "target_stage": "dev",
                            "target_branch": "codex/dev-1/task",
                            "target_worktree_name": "workstation-dev-1",
                            "target_worktree_root": str(root),
                        },
                        "dev-2": {
                            "slot": "dev-2",
                            "status": "ready",
                            "target_task_id": "TASK-002",
                            "target_lane_id": "phase-1/lane-b",
                            "target_stage": "dev",
                            "target_branch": "codex/dev-2/task",
                            "target_worktree_name": "workstation-dev-2",
                            "target_worktree_root": str(root),
                        },
                    },
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        for row in task_state.get("tasks", []):
            if row.get("task_id") in {"TASK-001", "TASK-002"}:
                row["status"] = "pending"
        assignments = [
            {
                "task_id": "TASK-001",
                "lane_id": "phase-1/lane-a",
                "phase_id": "phase-1",
                "next_stage": "dev",
                "next_role": "developer",
                "slot": "dev-1",
                "dispatch_policy": "resume_if_same_lane",
            },
            {
                "task_id": "TASK-002",
                "lane_id": "phase-1/lane-b",
                "phase_id": "phase-1",
                "next_stage": "dev",
                "next_role": "developer",
                "slot": "dev-2",
                "dispatch_policy": "resume_if_same_lane",
            },
        ]
        dispatched: list[str] = []
        monkeypatch.setattr(
            MODULE,
            "_dispatch_task_packet",
            lambda _req, task_payload, *_args, **_kwargs: (
                dispatched.append(str(task_payload.get("task_id")))
                or {"ok": True, "dispatch": {"dispatch_mode_used": "exec", "dispatch_thread_id": "thread-ok"}}
            ),
        )
        monkeypatch.setattr(
            MODULE,
            "_select_profile_alias_for_slot",
            lambda *_args, **kwargs: {
                "ok": True,
                "alias": "codex-first" if kwargs.get("slot") == "dev-1" else "codex-second",
            },
        )
        monkeypatch.setattr(
            MODULE,
            "_read_profile_rate_states",
            lambda *_args, **_kwargs: {
                "codex-first": {"hard_gated": True, "soft_gated": False},
                "codex-second": {"hard_gated": False, "soft_gated": False},
            },
        )
        monkeypatch.setattr(MODULE, "_active_worker_count_by_alias", lambda *_args, **_kwargs: {})
        out = MODULE._dispatch_next_task_from_assignments(
            req,
            plan_packets,
            task_state,
            build_state,
            assignments,
        )
        observations = out.get("assignment_observations")
        assert isinstance(observations, list)
        assert "TASK-002" in dispatched
        assert "TASK-001" not in dispatched
        assert any(
            isinstance(item, dict) and item.get("reason_code") == "dispatch_skipped_hard_gate_alias"
            for item in observations
        )


def test_dead_pid_without_progress_returns_forced_redispatch_assignment():
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
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        task = next(item for item in task_state["tasks"] if item.get("task_id") == "TASK-001")
        task["status"] = "dev_working"
        task["owner_slot"] = "dev-1"
        task["lane_id"] = "phase-1/lane-a"
        MODULE._ensure_worker_registry_v2(root, build_state)
        registry_path = root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
        registry_payload = json.loads(registry_path.read_text(encoding="utf-8"))
        for row in registry_payload.get("workers", []):
            if row.get("slot") == "dev-1":
                row["session_state"] = "running"
                row["state"] = "running"
                row["dispatch_pid"] = None
                row["active_task_id"] = "TASK-001"
                row["active_task"] = "TASK-001"
        registry_path.write_text(json.dumps(registry_payload, indent=2) + "\n", encoding="utf-8")

        assignments, warnings = MODULE._prepare_dead_pid_redispatch_assignments(
            root,
            task_state,
            plan_packets,
            build_state,
        )
        warning_codes = {item.get("code") for item in warnings if isinstance(item, dict)}
        assert assignments
        assert assignments[0].get("task_id") == "TASK-001"
        assert assignments[0].get("slot") == "dev-1"
        assert "dead_pid_no_evidence_redispatch" in warning_codes
        assert build_state.get("dead_pid_retry_counts", {}).get("TASK-001") == 1


def test_dead_pid_with_running_dispatch_thread_within_grace_defers_redispatch():
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
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        task = next(item for item in task_state["tasks"] if item.get("task_id") == "TASK-001")
        task["status"] = "dev_working"
        task["owner_slot"] = "dev-1"
        task["lane_id"] = "phase-1/lane-a"
        MODULE._ensure_worker_registry_v2(root, build_state)
        registry_path = root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
        registry_payload = json.loads(registry_path.read_text(encoding="utf-8"))
        now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        for row in registry_payload.get("workers", []):
            if row.get("slot") == "dev-1":
                row["session_state"] = "running"
                row["state"] = "running"
                row["dispatch_pid"] = None
                row["dispatch_thread_id"] = "thread-still-running"
                row["dispatch_started_at"] = now_iso
                row["active_task_id"] = "TASK-001"
                row["active_task"] = "TASK-001"
        registry_path.write_text(json.dumps(registry_payload, indent=2) + "\n", encoding="utf-8")

        assignments, warnings = MODULE._prepare_dead_pid_redispatch_assignments(
            root,
            task_state,
            plan_packets,
            build_state,
        )
        warning_codes = {item.get("code") for item in warnings if isinstance(item, dict)}
        assert assignments == []
        assert "dead_pid_awaiting_worker_heartbeat" in warning_codes
        assert task.get("status") == "dev_working"
        assert task.get("owner_slot") == "dev-1"
        assert build_state.get("dead_pid_retry_counts", {}).get("TASK-001") is None


def test_dead_pid_with_running_dispatch_thread_beyond_grace_redispatches():
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
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        build_state["dead_pid_recovery_policy"] = {"grace_sec": 60}
        task = next(item for item in task_state["tasks"] if item.get("task_id") == "TASK-001")
        task["status"] = "dev_working"
        task["owner_slot"] = "dev-1"
        task["lane_id"] = "phase-1/lane-a"
        MODULE._ensure_worker_registry_v2(root, build_state)
        registry_path = root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
        registry_payload = json.loads(registry_path.read_text(encoding="utf-8"))
        stale_iso = (datetime.now(timezone.utc) - timedelta(seconds=180)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        for row in registry_payload.get("workers", []):
            if row.get("slot") == "dev-1":
                row["session_state"] = "running"
                row["state"] = "running"
                row["dispatch_pid"] = None
                row["dispatch_thread_id"] = "thread-stale"
                row["dispatch_started_at"] = stale_iso
                row["active_task_id"] = "TASK-001"
                row["active_task"] = "TASK-001"
        registry_path.write_text(json.dumps(registry_payload, indent=2) + "\n", encoding="utf-8")

        assignments, warnings = MODULE._prepare_dead_pid_redispatch_assignments(
            root,
            task_state,
            plan_packets,
            build_state,
        )
        warning_codes = {item.get("code") for item in warnings if isinstance(item, dict)}
        assert assignments
        assert assignments[0].get("task_id") == "TASK-001"
        assert "dead_pid_no_evidence_redispatch" in warning_codes
        assert "dead_pid_awaiting_worker_heartbeat" not in warning_codes


def test_dead_pid_with_progress_reconciles_without_redispatch():
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
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        task = next(item for item in task_state["tasks"] if item.get("task_id") == "TASK-001")
        task["status"] = "dev_working"
        task["owner_slot"] = "dev-1"
        task["lane_id"] = "phase-1/lane-a"
        evidence_path = root / "reports" / "optimus-prime" / "planning" / "evidence" / "TASK-001" / "TASK_EVIDENCE.json"
        evidence_payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        evidence_payload["summary"] = {
            "result": "fail",
            "expectation": "expect_fail",
            "expectation_met": True,
            "failure_class": "expected_red",
            "reason_codes": ["tdd_expected_failure_observed"],
        }
        evidence_path.write_text(json.dumps(evidence_payload, indent=2) + "\n", encoding="utf-8")
        MODULE._ensure_worker_registry_v2(root, build_state)
        registry_path = root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
        registry_payload = json.loads(registry_path.read_text(encoding="utf-8"))
        for row in registry_payload.get("workers", []):
            if row.get("slot") == "dev-1":
                row["session_state"] = "running"
                row["state"] = "running"
                row["dispatch_pid"] = None
                row["active_task_id"] = "TASK-001"
                row["active_task"] = "TASK-001"
        registry_path.write_text(json.dumps(registry_payload, indent=2) + "\n", encoding="utf-8")

        assignments, warnings = MODULE._prepare_dead_pid_redispatch_assignments(
            root,
            task_state,
            plan_packets,
            build_state,
        )
        warning_codes = {item.get("code") for item in warnings if isinstance(item, dict)}
        assert assignments == []
        assert "dead_pid_evidence_reconciled" in warning_codes
        assert task.get("status") == "review_done"
        assert task.get("owner_slot") is None


def test_dead_pid_lane_test_no_progress_resets_to_pending():
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
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        task = next(item for item in task_state["tasks"] if item.get("task_id") == "TASK-001")
        plan_packets["tasks"][0]["task_kind"] = "lane_test"
        plan_packets["tasks"][0]["verification_contract"]["mode"] = "lane_test"
        task["task_kind"] = "lane_test"
        task["verification_contract"]["mode"] = "lane_test"
        task["status"] = "testing"
        task["owner_slot"] = "test-1"
        MODULE._ensure_worker_registry_v2(root, build_state)
        registry_path = root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
        registry_payload = json.loads(registry_path.read_text(encoding="utf-8"))
        for row in registry_payload.get("workers", []):
            if row.get("slot") == "test-1":
                row["session_state"] = "running"
                row["state"] = "running"
                row["dispatch_pid"] = None
                row["active_task_id"] = "TASK-001"
                row["active_task"] = "TASK-001"
        registry_path.write_text(json.dumps(registry_payload, indent=2) + "\n", encoding="utf-8")

        assignments, _warnings = MODULE._prepare_dead_pid_redispatch_assignments(
            root,
            task_state,
            plan_packets,
            build_state,
        )
        assert assignments
        assert assignments[0].get("task_id") == "TASK-001"
        assert task.get("status") == "pending"


def test_dead_pid_legacy_stage_emits_normalization_warning():
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
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        task = next(item for item in task_state["tasks"] if item.get("task_id") == "TASK-001")
        plan_packets["tasks"][0]["task_kind"] = "lane_review"
        plan_packets["tasks"][0]["verification_contract"]["mode"] = "lane_review"
        task["task_kind"] = "lane_review"
        task["verification_contract"]["mode"] = "lane_review"
        task["status"] = "testing"
        task["owner_slot"] = "test-1"
        MODULE._ensure_worker_registry_v2(root, build_state)
        registry_path = root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
        registry_payload = json.loads(registry_path.read_text(encoding="utf-8"))
        for row in registry_payload.get("workers", []):
            if row.get("slot") == "test-1":
                row["session_state"] = "running"
                row["state"] = "running"
                row["dispatch_pid"] = None
                row["active_task_id"] = "TASK-001"
                row["active_task"] = "TASK-001"
        registry_path.write_text(json.dumps(registry_payload, indent=2) + "\n", encoding="utf-8")

        _assignments, warnings = MODULE._prepare_dead_pid_redispatch_assignments(
            root,
            task_state,
            plan_packets,
            build_state,
        )
        assert any(
            isinstance(item, dict) and item.get("code") == "dead_pid_legacy_stage_normalized"
            for item in warnings
        )


def test_preflight_repairs_task_kind_from_plan_authority():
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
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets_path = planning / "PLAN_PACKETS.json"
        task_state_path = planning / "TASK_EXECUTION_STATE.json"
        plan_packets = json.loads(plan_packets_path.read_text(encoding="utf-8"))
        task_state = json.loads(task_state_path.read_text(encoding="utf-8"))
        plan_packets["tasks"][0]["task_kind"] = "lane_review"
        task_state["tasks"][0]["task_kind"] = "implementation"
        plan_packets_path.write_text(json.dumps(plan_packets, indent=2) + "\n", encoding="utf-8")
        task_state_path.write_text(json.dumps(task_state, indent=2) + "\n", encoding="utf-8")

        req = MODULE.parse_request({"command": "/op-build", "repo_root": str(root)})
        warnings, _missing, _state_payload, _plan_packets, repaired_task_state, _profile_selection = MODULE._preflight_build(req)
        assert repaired_task_state["tasks"][0]["task_kind"] == "lane_review"
        assert any(
            isinstance(item, dict) and item.get("code") == "task_kind_repaired_from_plan"
            for item in warnings
        )


def test_handoff_updates_normalize_legacy_success_aliases_to_completed():
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
        planning = root / "reports" / "optimus-prime" / "planning"
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        handoff_path = root / "reports" / "optimus-prime" / "HANDOFF_LOG.jsonl"
        handoff_path.write_text(
            json.dumps(
                {
                    "task_identifier": "TASK-001",
                    "result": "ready_for_review",
                    "task_evidence_ref": "reports/optimus-prime/planning/evidence/TASK-001/TASK_EVIDENCE.json",
                }
            )
            + "\n",
            encoding="utf-8",
        )

        MODULE._apply_handoff_updates(root, task_state, build_state)
        task = next(item for item in task_state["tasks"] if item.get("task_id") == "TASK-001")
        assert task["last_handoff_outcome"]["status"] == "completed"


def test_dead_pid_missing_completion_artifact_blocks_after_threshold():
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
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        build_state["worker_completion_policy"] = {"missing_threshold": 2}
        build_state["dead_pid_retry_counts"] = {"TASK-001": 1}
        task = next(item for item in task_state["tasks"] if item.get("task_id") == "TASK-001")
        task["status"] = "dev_working"
        task["owner_slot"] = "dev-1"
        task["lane_id"] = "phase-1/lane-a"
        evidence_path = root / "reports" / "optimus-prime" / "planning" / "evidence" / "TASK-001" / "TASK_EVIDENCE.json"
        evidence_path.unlink(missing_ok=True)

        MODULE._ensure_worker_registry_v2(root, build_state)
        registry_path = root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
        dispatch_log_path = root / "reports" / "optimus-prime" / "dispatch-dev-1.log"
        dispatch_log_path.write_text("refresh_token_reused\n", encoding="utf-8")
        registry_payload = json.loads(registry_path.read_text(encoding="utf-8"))
        for row in registry_payload.get("workers", []):
            if row.get("slot") == "dev-1":
                row["session_state"] = "running"
                row["state"] = "running"
                row["dispatch_pid"] = None
                row["active_task_id"] = "TASK-001"
                row["active_task"] = "TASK-001"
                row["dispatch_log"] = str(dispatch_log_path)
        registry_path.write_text(json.dumps(registry_payload, indent=2) + "\n", encoding="utf-8")

        assignments, warnings = MODULE._prepare_dead_pid_redispatch_assignments(
            root,
            task_state,
            plan_packets,
            build_state,
        )
        warning_codes = {item.get("code") for item in warnings if isinstance(item, dict)}
        assert assignments == []
        assert task.get("status") == "blocked"
        assert "worker_completion_artifact_missing" in warning_codes
        assert "worker_dispatch_auth_failed" in warning_codes
        gap_rows = task.get("gaps_that_need_patching")
        assert isinstance(gap_rows, list) and gap_rows
        assert any((row.get("status") == "open" and row.get("stage") == "dev") for row in gap_rows if isinstance(row, dict))
        assert any(
            "worker_dispatch_auth_failed" in (row.get("reason_codes") or [])
            for row in gap_rows
            if isinstance(row, dict)
        )


def test_dead_pid_missing_completion_artifact_ignores_stale_dispatch_log_hint():
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
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        build_state["worker_completion_policy"] = {"missing_threshold": 2}
        build_state["dead_pid_retry_counts"] = {"TASK-001": 1}
        task = next(item for item in task_state["tasks"] if item.get("task_id") == "TASK-001")
        task["status"] = "dev_working"
        task["owner_slot"] = "dev-1"
        task["lane_id"] = "phase-1/lane-a"
        evidence_path = root / "reports" / "optimus-prime" / "planning" / "evidence" / "TASK-001" / "TASK_EVIDENCE.json"
        evidence_path.unlink(missing_ok=True)

        MODULE._ensure_worker_registry_v2(root, build_state)
        registry_path = root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
        dispatch_log_path = root / "reports" / "optimus-prime" / "dispatch-dev-1.log"
        dispatch_log_path.write_text("refresh_token_reused\n", encoding="utf-8")
        stale_ts = (datetime.now(timezone.utc) - timedelta(hours=2)).timestamp()
        os.utime(dispatch_log_path, (stale_ts, stale_ts))
        registry_payload = json.loads(registry_path.read_text(encoding="utf-8"))
        for row in registry_payload.get("workers", []):
            if row.get("slot") == "dev-1":
                row["session_state"] = "running"
                row["state"] = "running"
                row["dispatch_pid"] = None
                row["active_task_id"] = "TASK-001"
                row["active_task"] = "TASK-001"
                row["dispatch_log"] = str(dispatch_log_path)
                row["updated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        registry_path.write_text(json.dumps(registry_payload, indent=2) + "\n", encoding="utf-8")

        assignments, warnings = MODULE._prepare_dead_pid_redispatch_assignments(
            root,
            task_state,
            plan_packets,
            build_state,
        )
        warning_codes = {item.get("code") for item in warnings if isinstance(item, dict)}
        assert assignments == []
        assert task.get("status") == "blocked"
        assert "worker_completion_artifact_missing" in warning_codes
        assert "worker_dispatch_auth_failed" not in warning_codes
        gap_rows = task.get("gaps_that_need_patching")
        assert isinstance(gap_rows, list) and gap_rows
        assert all(
            "worker_dispatch_auth_failed" not in (row.get("reason_codes") or [])
            for row in gap_rows
            if isinstance(row, dict)
        )


def test_fan_in_merges_handoff_rows_without_duplicates():
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
        planning = root / "reports" / "optimus-prime" / "planning"
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        MODULE._ensure_worker_registry_v2(root, build_state)
        registry_path = root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
        worktree_root = root / ".MyBoard-workstations" / "workstation-dev-1"
        worktree_root.mkdir(parents=True, exist_ok=True)
        registry_payload = json.loads(registry_path.read_text(encoding="utf-8"))
        for row in registry_payload.get("workers", []):
            if row.get("slot") == "dev-1":
                row["worktree_root"] = str(worktree_root)
        registry_path.write_text(json.dumps(registry_payload, indent=2) + "\n", encoding="utf-8")

        canonical_handoff_path = root / "reports" / "optimus-prime" / "HANDOFF_LOG.jsonl"
        canonical_handoff_path.parent.mkdir(parents=True, exist_ok=True)
        row_a = {"event": "dispatch_attempt", "task_identifier": "TASK-001", "slot": "dev-1"}
        row_b = {"event": "task_update", "task_identifier": "TASK-001", "slot": "dev-1", "status": "dev_done"}
        canonical_handoff_path.write_text(json.dumps(row_a) + "\n", encoding="utf-8")
        worker_handoff_path = worktree_root / "reports" / "optimus-prime" / "HANDOFF_LOG.jsonl"
        worker_handoff_path.parent.mkdir(parents=True, exist_ok=True)
        worker_handoff_path.write_text(
            json.dumps(row_a) + "\n" + json.dumps(row_b) + "\n",
            encoding="utf-8",
        )

        warnings = MODULE._fan_in_worker_artifacts(root, build_state)
        warning_codes = {item.get("code") for item in warnings if isinstance(item, dict)}
        lines = [line for line in canonical_handoff_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(lines) == 2
        assert "worktree_artifacts_synced" in warning_codes
        assert int((build_state.get("artifact_fan_in") or {}).get("handoff_rows_synced", 0)) == 1


def test_reconcile_verify_gap_closes_on_passed_verify():
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
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        task = next(item for item in task_state["tasks"] if item.get("task_id") == "TASK-001")
        task["status"] = "tests_done"
        phase_id = task.get("phase_id") or "phase-1"
        cmd = "python3 -m pytest"
        gap_id = MODULE._gap_id(plan_packets.get("plan_id") or "plan", phase_id, "TASK-001", f"verify:{cmd}", "fail")
        task["gaps_that_need_patching"] = [
            {
                "gap_id": gap_id,
                "category": "verify_missing",
                "severity": "P1",
                "stage": "test",
                "status": "open",
                "reason_codes": ["verify_command_not_passed"],
                "retry_count": 0,
                "max_retries": 5,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
                "closure_ref": None,
            }
        ]
        evidence_path = MODULE._task_evidence_path(root, task)
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        payload["dev"]["verify_results"] = [{"command": cmd, "passed": True}]
        evidence_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        warnings = MODULE._refresh_task_embedded_gaps(root, plan_packets, task_state)
        row = task["gaps_that_need_patching"][0]
        assert row["status"] == "closed"
        assert "gap_closed_by_evidence" in row.get("reason_codes", [])
        assert any(item.get("code") == "task_gap_closed" for item in warnings)


def test_refresh_task_embedded_gaps_does_not_generate_for_blocked_tasks():
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
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        task = next(item for item in task_state["tasks"] if item.get("task_id") == "TASK-001")
        task["status"] = "blocked"
        task["gaps_that_need_patching"] = []

        MODULE._refresh_task_embedded_gaps(root, plan_packets, task_state)
        open_gaps = [row for row in task.get("gaps_that_need_patching", []) if row.get("status") == "open"]
        assert not open_gaps


def test_refresh_task_embedded_gaps_skips_uat_missing_for_expect_fail_review():
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
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        task = next(item for item in task_state["tasks"] if item.get("task_id") == "TASK-001")
        task["status"] = "review_done"
        task["gaps_that_need_patching"] = []
        evidence_path = MODULE._task_evidence_path(root, task)
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        payload["summary"] = {
            "result": "fail",
            "expectation": "expect_fail",
            "expectation_met": True,
            "failure_class": "expected_red",
            "reason_codes": ["tdd_expected_failure_observed"],
        }
        payload["test"]["uat_results"] = [
            {
                "requirement_id": "REQ-001",
                "requirement_ids": ["REQ-001"],
                "passed": False,
                "notes": "red phase expected",
            }
        ]
        evidence_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        MODULE._refresh_task_embedded_gaps(root, plan_packets, task_state)
        open_gaps = [row for row in task["gaps_that_need_patching"] if row.get("status") == "open"]
        assert all(row.get("category") != "uat_missing" for row in open_gaps)


def test_refresh_task_embedded_gaps_closes_existing_uat_missing_for_expect_fail_review():
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
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        task = next(item for item in task_state["tasks"] if item.get("task_id") == "TASK-001")
        task["status"] = "review_done"
        phase_id = task.get("phase_id") or "phase-1"
        gap_id = MODULE._gap_id(plan_packets.get("plan_id") or "plan", phase_id, "TASK-001", "uat:REQ-001", "blocked")
        task["gaps_that_need_patching"] = [
            {
                "gap_id": gap_id,
                "category": "uat_missing",
                "severity": "P1",
                "stage": "review",
                "status": "open",
                "reason_codes": ["uat_requirement_not_passed"],
                "retry_count": 0,
                "max_retries": 5,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
                "closure_ref": None,
            }
        ]
        evidence_path = MODULE._task_evidence_path(root, task)
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        payload["summary"] = {
            "result": "fail",
            "expectation": "expect_fail",
            "expectation_met": True,
            "failure_class": "expected_red",
            "reason_codes": ["tdd_expected_failure_observed"],
        }
        payload["test"]["uat_results"] = [
            {
                "requirement_id": "REQ-001",
                "requirement_ids": ["REQ-001"],
                "passed": False,
                "notes": "red phase expected",
            }
        ]
        evidence_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        MODULE._refresh_task_embedded_gaps(root, plan_packets, task_state)
        row = task["gaps_that_need_patching"][0]
        assert row["status"] == "closed"
        assert "gap_closed_by_evidence" in row.get("reason_codes", [])


def test_refresh_gap_artifacts_does_not_generate_for_blocked_tasks():
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
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        task = next(item for item in task_state["tasks"] if item.get("task_id") == "TASK-001")
        task["status"] = "blocked"

        gaps_payload, _ = MODULE._refresh_gap_artifacts(root, plan_packets, task_state, build_state)
        rows = [row for row in gaps_payload.get("gaps", []) if isinstance(row, dict) and row.get("task_id") == "TASK-001"]
        open_rows = [row for row in rows if row.get("status") == "open"]
        assert not open_rows


def test_reconcile_merge_blocked_gap_closes_on_done_registry_success():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        planning = root / "reports" / "optimus-prime" / "planning"
        planning.mkdir(parents=True, exist_ok=True)
        task_state = {
            "tasks": [
                {
                    "task_id": "TASK-001",
                    "phase_id": "phase-1",
                    "status": "blocked",
                    "gaps_that_need_patching": [
                        {
                            "gap_id": "gap-merge-1",
                            "category": "merge_blocked",
                            "severity": "P1",
                            "stage": "merge",
                            "status": "open",
                            "reason_codes": ["merge_or_verification_failed"],
                            "retry_count": 1,
                            "max_retries": 10,
                            "created_at": "2026-01-01T00:00:00Z",
                            "updated_at": "2026-01-01T00:00:00Z",
                            "closure_ref": None,
                        }
                    ],
                }
            ]
        }
        (planning / "DONE_TASKS_REGISTRY.json").write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "merged_tasks": [
                        {
                            "task_id": "TASK-001",
                            "merged_commit": "abc1234",
                            "merged_at": "2026-01-01T00:00:00Z",
                            "branch": "RAB-BASE",
                            "verification_passed": True,
                            "verification_ref": "reports/optimus-prime/branch-manager/attempt-task-001-1/MERGE_VALIDATION.json",
                        }
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        warnings = MODULE._reconcile_task_embedded_gap_closures(root, task_state)
        row = task_state["tasks"][0]["gaps_that_need_patching"][0]
        assert row["status"] == "closed"
        assert row["closure_ref"]
        assert any(item.get("code") == "task_gap_closed" for item in warnings)


def test_reconcile_workstation_gap_closes_on_workstation_validation_success():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        ws_attempt = root / "reports" / "optimus-prime" / "workstation-manager" / "attempt-dev-1-1"
        ws_attempt.mkdir(parents=True, exist_ok=True)
        (ws_attempt / "WORKSTATION_VALIDATION.json").write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "slot": "dev-1",
                    "task_id": "TASK-001",
                    "lane_id": "phase-1/lane-a",
                    "attempt": 1,
                    "ok": True,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        task_state = {
            "tasks": [
                {
                    "task_id": "TASK-001",
                    "phase_id": "phase-1",
                    "status": "blocked",
                    "owner_slot": "dev-1",
                    "gaps_that_need_patching": [
                        {
                            "gap_id": "gap-ws-1",
                            "category": "other",
                            "severity": "P1",
                            "stage": "workstation",
                            "status": "open",
                            "reason_codes": ["workstation_prepare_failed"],
                            "retry_count": 1,
                            "max_retries": 10,
                            "created_at": "2026-01-01T00:00:00Z",
                            "updated_at": "2026-01-01T00:00:00Z",
                            "closure_ref": None,
                            "slot": "dev-1",
                        }
                    ],
                }
            ]
        }
        warnings = MODULE._reconcile_task_embedded_gap_closures(root, task_state)
        row = task_state["tasks"][0]["gaps_that_need_patching"][0]
        assert row["status"] == "closed"
        assert row["closure_ref"]
        assert any(item.get("code") == "task_gap_closed" for item in warnings)


def test_reopen_closed_gap_on_regression_increments_retry_count():
    task = {
        "task_id": "TASK-001",
        "gaps_that_need_patching": [
            {
                "gap_id": "gap-1",
                "category": "verify_missing",
                "severity": "P1",
                "stage": "test",
                "status": "closed",
                "reason_codes": ["verify_command_not_passed", "gap_closed_by_evidence"],
                "retry_count": 2,
                "max_retries": 5,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
                "closure_ref": "ref",
            }
        ],
    }
    MODULE._upsert_task_gap(
        task,
        {
            "gap_id": "gap-1",
            "category": "verify_missing",
            "severity": "P1",
            "stage": "test",
            "status": "open",
            "reason_codes": ["verify_command_not_passed"],
            "retry_count": 0,
            "max_retries": 5,
            "closure_ref": None,
        },
    )
    row = task["gaps_that_need_patching"][0]
    assert row["status"] == "open"
    assert row["retry_count"] >= 3


def _write_manager_action_from_prompt(prompt_text: str, payload: dict[str, object]) -> None:
    marker = "Write JSON action file to: "
    path_line = next((line for line in prompt_text.splitlines() if marker in line), "")
    action_path = Path(path_line.split(marker, 1)[1].strip())
    action_path.parent.mkdir(parents=True, exist_ok=True)
    action_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _stub_workstation_async_llm(
    monkeypatch: pytest.MonkeyPatch,
    payload_builder,
):
    def fake_start_codex_exec_background(**kwargs):
        prompt = str(kwargs.get("prompt_text") or "")
        payload = payload_builder(prompt)
        _write_manager_action_from_prompt(prompt, payload)
        return 424242, None

    monkeypatch.setattr(MODULE, "_start_codex_exec_background", fake_start_codex_exec_background)
    monkeypatch.setattr(MODULE, "_poll_background_process", lambda *_args, **_kwargs: (True, 0))


def _write_workstation_registry_slot(
    root: Path,
    *,
    slot: str,
    task_id: str,
    lane_id: str,
    stage: str,
    branch: str,
    worktree_root: Path,
) -> None:
    path = root / "reports" / "optimus-prime" / "planning" / "WORKSTATION_REGISTRY.json"
    payload = {
        "schema_version": "1.0",
        "updated_at": "2026-01-01T00:00:00Z",
        "slots": {
            slot: {
                "slot": slot,
                "status": "ready",
                "request_id": "req-test",
                "pid": None,
                "attempt": 1,
                "retry_count": 0,
                "requested_cycle": 1,
                "started_at": "2026-01-01T00:00:00Z",
                "completed_at": "2026-01-01T00:00:01Z",
                "last_update_at": "2026-01-01T00:00:01Z",
                "target_task_id": task_id,
                "target_lane_id": lane_id,
                "target_stage": stage,
                "target_branch": branch,
                "target_base_ref": "RAB-BASE",
                "target_worktree_name": f"workstation-{slot}",
                "target_worktree_root": str(worktree_root),
                "attempt_dir": None,
                "action_path": None,
                "validation_path": None,
                "stdout_path": None,
                "stderr_path": None,
                "last_message_path": None,
                "llm_exit_code": 0,
                "last_error": None,
            }
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _mark_task_review_done_merge_ready(root: Path, task: dict[str, object]) -> None:
    task["status"] = "review_done"
    task["active_branch"] = "codex/dev-1/task-001"
    evidence = task.get("evidence") if isinstance(task.get("evidence"), dict) else {}
    evidence_ref = evidence.get("task_evidence_ref")
    if not isinstance(evidence_ref, str) or not evidence_ref:
        return
    evidence_path = root / evidence_ref
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload["summary"] = {
        "result": "fail",
        "expectation": "expect_fail",
        "expectation_met": True,
        "failure_class": "expected_red",
        "reason_codes": ["tdd_expected_failure_observed"],
    }
    evidence_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_worker_registry_normalizes_idle_worker_branch_from_rab_base_to_bootstrap():
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
        planning = root / "reports" / "optimus-prime" / "planning"
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        registry_path = root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
        registry_payload = {
            "workers": [
                {
                    "slot": "dev-1",
                    "role": "developer",
                    "session_state": "not_running",
                    "active_task_id": None,
                    "active_task": None,
                    "lane_id": None,
                    "previous_lane_id": "n/a",
                    "branch": "RAB-BASE",
                    "worktree_root": None,
                }
            ]
        }
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text(json.dumps(registry_payload, indent=2) + "\n", encoding="utf-8")
        workstation_registry_path = root / "reports" / "optimus-prime" / "planning" / "WORKSTATION_REGISTRY.json"
        workstation_registry_path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "updated_at": "2026-01-01T00:00:00Z",
                    "slots": {
                        "dev-1": {
                            "slot": "dev-1",
                            "status": "ready",
                            "target_task_id": "TASK-001",
                            "target_lane_id": "phase-1/lane-a",
                            "target_stage": "dev",
                            "target_branch": "codex/dev-1/task",
                            "target_worktree_name": "workstation-dev-1",
                            "target_worktree_root": str(root),
                        },
                        "dev-2": {
                            "slot": "dev-2",
                            "status": "ready",
                            "target_task_id": "TASK-002",
                            "target_lane_id": "phase-1/lane-b",
                            "target_stage": "dev",
                            "target_branch": "codex/dev-2/task",
                            "target_worktree_name": "workstation-dev-2",
                            "target_worktree_root": str(root),
                        },
                        "dev-3": {
                            "slot": "dev-3",
                            "status": "ready",
                            "target_task_id": "TASK-003",
                            "target_lane_id": "phase-1/lane-c",
                            "target_stage": "dev",
                            "target_branch": "codex/dev-3/task",
                            "target_worktree_name": "workstation-dev-3",
                            "target_worktree_root": str(root),
                        },
                    },
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        MODULE._ensure_worker_registry_v2(root, build_state)
        registry_after = json.loads(registry_path.read_text(encoding="utf-8"))
        slot_row = next(item for item in registry_after.get("workers", []) if isinstance(item, dict) and item.get("slot") == "dev-1")
        assert slot_row.get("branch") == "codex/dev-1/bootstrap"


def test_dispatch_assignment_observations_written_with_reason_and_duration(monkeypatch: pytest.MonkeyPatch):
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
        req = MODULE.parse_request({"command": "/op-build", "repo_root": str(root), "dry_run": True})
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        build_state["last_cycle"] = 3
        build_state["profile_aliases"] = ["codex"]
        build_state["slot_profile_assignments"] = {"dev-1": "codex"}
        MODULE._ensure_worker_registry_v2(root, build_state)
        registry_path = root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
        registry_payload = json.loads(registry_path.read_text(encoding="utf-8"))
        for row in registry_payload.get("workers", []):
            if row.get("slot") == "dev-1":
                row["worktree_root"] = str(root)
                row["branch"] = "codex/dev-1/task-001"
        registry_path.write_text(json.dumps(registry_payload, indent=2) + "\n", encoding="utf-8")
        _write_workstation_registry_slot(
            root,
            slot="dev-1",
            task_id="TASK-001",
            lane_id="phase-1/lane-a",
            stage="dev",
            branch="codex/dev-1/task",
            worktree_root=root,
        )
        _write_workstation_registry_slot(
            root,
            slot="dev-1",
            task_id="TASK-001",
            lane_id="phase-1/lane-a",
            stage="dev",
            branch="codex/dev-1/task-001",
            worktree_root=root,
        )

        for row in task_state.get("tasks", []):
            if row.get("task_id") == "TASK-001":
                row["status"] = "pending"
            if row.get("task_id") == "TASK-002":
                row["status"] = "pending"

        monkeypatch.setattr(
            MODULE,
            "_select_profile_alias_for_slot",
            lambda *_args, **_kwargs: {"ok": True, "alias": "codex"},
        )
        monkeypatch.setattr(MODULE, "_active_worker_count_by_alias", lambda *_args, **_kwargs: {})
        monkeypatch.setattr(
            MODULE,
            "_read_profile_rate_states",
            lambda *_args, **_kwargs: {"codex": {"soft_gated": False}},
        )

        def fake_dispatch(*_args, **_kwargs):
            task = _args[1]
            task["dispatch_thread_id"] = "thread-abc"
            return {
                "ok": True,
                "dispatch": {
                    "dispatch_mode_used": "exec",
                    "dispatch_thread_id": "thread-abc",
                    "pid": 45678,
                    "dispatch_log": str(root / ".codex-dispatch" / "dispatch.log"),
                },
            }

        monkeypatch.setattr(MODULE, "_dispatch_task_packet", fake_dispatch)
        assignments = [
            {
                "task_id": "TASK-UNKNOWN",
                "lane_id": "phase-1/lane-a",
                "phase_id": "phase-1",
                "next_stage": "dev",
                "next_role": "developer",
                "slot": "dev-1",
                "dispatch_policy": "resume_if_same_lane",
            },
            {
                "task_id": "TASK-001",
                "lane_id": "phase-1/lane-a",
                "phase_id": "phase-1",
                "next_stage": "test",
                "next_role": "tester",
                "slot": "dev-1",
                "dispatch_policy": "resume_if_same_lane",
            },
            {
                "task_id": "TASK-001",
                "lane_id": "phase-1/lane-a",
                "phase_id": "phase-1",
                "next_stage": "dev",
                "next_role": "developer",
                "slot": "dev-1",
                "dispatch_policy": "resume_if_same_lane",
            },
        ]
        out = MODULE._dispatch_next_task_from_assignments(
            req,
            plan_packets,
            task_state,
            build_state,
            assignments,
        )
        observations = out.get("assignment_observations", [])
        assert observations
        statuses = {row.get("status") for row in observations if isinstance(row, dict)}
        assert "invalid" in statuses
        assert "skipped" in statuses
        assert "dispatched" in statuses
        assert all(isinstance(row.get("duration_ms"), int) and row.get("duration_ms") >= 0 for row in observations if isinstance(row, dict))
        assert all(MODULE._as_str(row.get("reason_code")) for row in observations if isinstance(row, dict))
        obs_path = planning / "DISPATCH_ASSIGNMENT_OBSERVATIONS.jsonl"
        assert obs_path.exists()
        persisted_rows = [
            json.loads(line)
            for line in obs_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(persisted_rows) >= len(observations)
        registry_after = json.loads(registry_path.read_text(encoding="utf-8"))
        dev1 = next(
            row for row in registry_after.get("workers", []) if isinstance(row, dict) and row.get("slot") == "dev-1"
        )
        assert dev1.get("dispatch_pid") == 45678
        assert dev1.get("dispatch_log") == str(root / ".codex-dispatch" / "dispatch.log")


def test_dispatch_next_task_persists_dispatch_pid_and_log(monkeypatch: pytest.MonkeyPatch):
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
        req = MODULE.parse_request({"command": "/op-build", "repo_root": str(root), "dry_run": True})
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        build_state["profile_aliases"] = ["codex"]
        MODULE._ensure_worker_registry_v2(root, build_state)
        monkeypatch.setattr(MODULE, "_select_profile_alias_for_slot", lambda *_args, **_kwargs: {"ok": True, "alias": "codex"})
        monkeypatch.setattr(MODULE, "_active_worker_count_by_alias", lambda *_args, **_kwargs: {})
        monkeypatch.setattr(
            MODULE,
            "_read_profile_rate_states",
            lambda *_args, **_kwargs: {"codex": {"soft_gated": False}},
        )

        def fake_dispatch(_req, task_payload, *_args, **_kwargs):
            task_payload["dispatch_thread_id"] = "thread-main-dispatch"
            return {
                "ok": True,
                "dispatch": {
                    "dispatch_mode_used": "exec",
                    "dispatch_thread_id": "thread-main-dispatch",
                    "pid": 56789,
                    "dispatch_log": str(root / ".codex-dispatch" / "dispatch-main.log"),
                },
            }

        monkeypatch.setattr(MODULE, "_dispatch_task_packet", fake_dispatch)

        out = MODULE._dispatch_next_task(req, plan_packets, task_state, build_state, None)
        assert out.get("ok") is True
        registry_payload = json.loads((root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json").read_text(encoding="utf-8"))
        dev1 = next(
            row for row in registry_payload.get("workers", []) if isinstance(row, dict) and row.get("slot") == "dev-1"
        )
        assert dev1.get("dispatch_pid") == 56789
        assert dev1.get("dispatch_log") == str(root / ".codex-dispatch" / "dispatch-main.log")


def test_dispatch_next_task_routes_lane_test_tasks_to_tester(monkeypatch: pytest.MonkeyPatch):
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
        req = MODULE.parse_request({"command": "/op-build", "repo_root": str(root), "dry_run": True})
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        build_state["profile_aliases"] = ["codex"]
        MODULE._ensure_worker_registry_v2(root, build_state)
        plan_packets["tasks"][0]["task_kind"] = "lane_test"
        plan_packets["tasks"][0]["verification_contract"]["mode"] = "lane_test"
        plan_packets["lane_base_branches"][plan_packets["tasks"][0]["lane_id"]] = "main"
        task_state["tasks"][0]["task_kind"] = "lane_test"
        task_state["tasks"][0]["verification_contract"]["mode"] = "lane_test"
        monkeypatch.setattr(MODULE, "_select_profile_alias_for_slot", lambda *_args, **_kwargs: {"ok": True, "alias": "codex"})
        monkeypatch.setattr(MODULE, "_active_worker_count_by_alias", lambda *_args, **_kwargs: {})
        monkeypatch.setattr(MODULE, "_read_profile_rate_states", lambda *_args, **_kwargs: {"codex": {"soft_gated": False}})
        seen: list[str] = []

        def fake_dispatch(_req, _task_payload, _plan_task, stage_name, *_args, **_kwargs):
            seen.append(stage_name)
            return {"ok": True, "dispatch": {"dispatch_mode_used": "exec", "dispatch_thread_id": "thread-lane-test"}}

        monkeypatch.setattr(MODULE, "_dispatch_task_packet", fake_dispatch)

        out = MODULE._dispatch_next_task(req, plan_packets, task_state, build_state, None)
        assert out.get("ok") is True
        assert seen == ["test"]


def test_dispatch_next_task_routes_lane_review_tasks_to_reviewer(monkeypatch: pytest.MonkeyPatch):
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
        req = MODULE.parse_request({"command": "/op-build", "repo_root": str(root), "dry_run": True})
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        build_state["profile_aliases"] = ["codex"]
        MODULE._ensure_worker_registry_v2(root, build_state)
        plan_packets["tasks"][0]["task_kind"] = "lane_review"
        plan_packets["tasks"][0]["verification_contract"]["mode"] = "lane_review"
        plan_packets["lane_base_branches"][plan_packets["tasks"][0]["lane_id"]] = "main"
        task_state["tasks"][0]["task_kind"] = "lane_review"
        task_state["tasks"][0]["verification_contract"]["mode"] = "lane_review"
        monkeypatch.setattr(MODULE, "_select_profile_alias_for_slot", lambda *_args, **_kwargs: {"ok": True, "alias": "codex"})
        monkeypatch.setattr(MODULE, "_active_worker_count_by_alias", lambda *_args, **_kwargs: {})
        monkeypatch.setattr(MODULE, "_read_profile_rate_states", lambda *_args, **_kwargs: {"codex": {"soft_gated": False}})
        seen: list[str] = []

        def fake_dispatch(_req, _task_payload, _plan_task, stage_name, *_args, **_kwargs):
            seen.append(stage_name)
            return {"ok": True, "dispatch": {"dispatch_mode_used": "exec", "dispatch_thread_id": "thread-lane-review"}}

        monkeypatch.setattr(MODULE, "_dispatch_task_packet", fake_dispatch)

        out = MODULE._dispatch_next_task(req, plan_packets, task_state, build_state, None)
        assert out.get("ok") is True
        assert seen == ["review"]


def test_dispatch_next_task_prefers_plan_task_kind_over_stale_task_state(monkeypatch: pytest.MonkeyPatch):
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
        req = MODULE.parse_request({"command": "/op-build", "repo_root": str(root), "dry_run": True})
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        build_state["profile_aliases"] = ["codex"]
        MODULE._ensure_worker_registry_v2(root, build_state)
        plan_packets["tasks"][0]["task_kind"] = "lane_review"
        plan_packets["tasks"][0]["verification_contract"]["mode"] = "lane_review"
        plan_packets["lane_base_branches"][plan_packets["tasks"][0]["lane_id"]] = "main"
        task_state["tasks"][0]["task_kind"] = "implementation"
        task_state["tasks"][0]["verification_contract"]["mode"] = "implementation_green"
        monkeypatch.setattr(MODULE, "_select_profile_alias_for_slot", lambda *_args, **_kwargs: {"ok": True, "alias": "codex"})
        monkeypatch.setattr(MODULE, "_active_worker_count_by_alias", lambda *_args, **_kwargs: {})
        monkeypatch.setattr(MODULE, "_read_profile_rate_states", lambda *_args, **_kwargs: {"codex": {"soft_gated": False}})
        seen: list[str] = []

        def fake_dispatch(_req, _task_payload, _plan_task, stage_name, *_args, **_kwargs):
            seen.append(stage_name)
            return {"ok": True, "dispatch": {"dispatch_mode_used": "exec", "dispatch_thread_id": "thread-plan-authority"}}

        monkeypatch.setattr(MODULE, "_dispatch_task_packet", fake_dispatch)

        out = MODULE._dispatch_next_task(req, plan_packets, task_state, build_state, None)
        assert out.get("ok") is True
        assert seen == ["review"]
        assert task_state["tasks"][0]["task_kind"] == "lane_review"


def test_dispatch_next_task_marks_profile_permanently_blocked_on_refresh_token_reused_unauthorized(
    monkeypatch: pytest.MonkeyPatch,
):
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
        req = MODULE.parse_request({"command": "/op-build", "repo_root": str(root), "dry_run": True})
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        build_state["profile_aliases"] = ["codex"]
        MODULE._ensure_worker_registry_v2(root, build_state)
        monkeypatch.setattr(MODULE, "_select_profile_alias_for_slot", lambda *_args, **_kwargs: {"ok": True, "alias": "codex"})
        monkeypatch.setattr(MODULE, "_active_worker_count_by_alias", lambda *_args, **_kwargs: {})
        monkeypatch.setattr(MODULE, "_read_profile_rate_states", lambda *_args, **_kwargs: {"codex": {"soft_gated": False}})
        monkeypatch.setattr(
            MODULE,
            "_dispatch_task_packet",
            lambda *_args, **_kwargs: {
                "ok": False,
                "code": "dispatch_failed",
                "message": "401 Unauthorized code: refresh_token_reused",
            },
        )

        out = MODULE._dispatch_next_task(req, plan_packets, task_state, build_state, None)
        assert out.get("ok") is False
        rate_payload = json.loads(
            (root / "reports" / "optimus-prime" / "PROFILE_RATE_REGISTRY.json").read_text(encoding="utf-8")
        )
        codex_row = rate_payload.get("profiles", {}).get("codex", {})
        assert codex_row.get("permanently_blocked") is True
        assert codex_row.get("eligible_for_new_work") is False
        assert codex_row.get("permanent_block_reason") == "refresh_token_reused"


def test_dispatch_next_task_does_not_mark_profile_permanently_blocked_without_unauthorized(
    monkeypatch: pytest.MonkeyPatch,
):
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
        req = MODULE.parse_request({"command": "/op-build", "repo_root": str(root), "dry_run": True})
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        build_state["profile_aliases"] = ["codex"]
        MODULE._ensure_worker_registry_v2(root, build_state)
        monkeypatch.setattr(MODULE, "_select_profile_alias_for_slot", lambda *_args, **_kwargs: {"ok": True, "alias": "codex"})
        monkeypatch.setattr(MODULE, "_active_worker_count_by_alias", lambda *_args, **_kwargs: {})
        monkeypatch.setattr(MODULE, "_read_profile_rate_states", lambda *_args, **_kwargs: {"codex": {"soft_gated": False}})
        monkeypatch.setattr(
            MODULE,
            "_dispatch_task_packet",
            lambda *_args, **_kwargs: {
                "ok": False,
                "code": "dispatch_failed",
                "message": "refresh_token_reused",
            },
        )

        out = MODULE._dispatch_next_task(req, plan_packets, task_state, build_state, None)
        assert out.get("ok") is False
        rate_path = root / "reports" / "optimus-prime" / "PROFILE_RATE_REGISTRY.json"
        if rate_path.exists():
            payload = json.loads(rate_path.read_text(encoding="utf-8"))
            codex_row = payload.get("profiles", {}).get("codex", {})
            assert codex_row.get("permanently_blocked") is not True


def test_dispatch_next_task_from_assignments_respects_cycle_cap(monkeypatch: pytest.MonkeyPatch):
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
        req = MODULE.parse_request({"command": "/op-build", "repo_root": str(root), "dry_run": True})
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        build_state["dispatch_window"] = {"max_running_workers": 6, "soft_cap_active": False, "max_assignments_per_cycle": 2}
        build_state["profile_aliases"] = ["codex"]
        build_state["slot_profile_assignments"] = {"dev-1": "codex", "dev-2": "codex", "dev-3": "codex"}
        MODULE._ensure_worker_registry_v2(root, build_state)
        registry_path = root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
        registry_payload = json.loads(registry_path.read_text(encoding="utf-8"))
        for row in registry_payload.get("workers", []):
            slot = row.get("slot")
            if slot in {"dev-1", "dev-2", "dev-3"}:
                row["worktree_root"] = str(root)
                row["branch"] = f"codex/{slot}/task"
        registry_path.write_text(json.dumps(registry_payload, indent=2) + "\n", encoding="utf-8")
        workstation_registry_path = root / "reports" / "optimus-prime" / "planning" / "WORKSTATION_REGISTRY.json"
        workstation_registry_path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "updated_at": "2026-01-01T00:00:00Z",
                    "slots": {
                        "dev-1": {
                            "slot": "dev-1",
                            "status": "ready",
                            "target_task_id": "TASK-001",
                            "target_lane_id": "phase-1/lane-a",
                            "target_stage": "dev",
                            "target_branch": "codex/dev-1/task",
                            "target_worktree_name": "workstation-dev-1",
                            "target_worktree_root": str(root),
                        },
                        "dev-2": {
                            "slot": "dev-2",
                            "status": "ready",
                            "target_task_id": "TASK-002",
                            "target_lane_id": "phase-1/lane-b",
                            "target_stage": "dev",
                            "target_branch": "codex/dev-2/task",
                            "target_worktree_name": "workstation-dev-2",
                            "target_worktree_root": str(root),
                        },
                        "dev-3": {
                            "slot": "dev-3",
                            "status": "ready",
                            "target_task_id": "TASK-003",
                            "target_lane_id": "phase-1/lane-c",
                            "target_stage": "dev",
                            "target_branch": "codex/dev-3/task",
                            "target_worktree_name": "workstation-dev-3",
                            "target_worktree_root": str(root),
                        },
                    },
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        for row in task_state.get("tasks", []):
            if row.get("task_id") in {"TASK-001", "TASK-002", "TASK-003"}:
                row["status"] = "pending"

        monkeypatch.setattr(MODULE, "_select_profile_alias_for_slot", lambda *_args, **_kwargs: {"ok": True, "alias": "codex"})
        monkeypatch.setattr(MODULE, "_read_profile_rate_states", lambda *_args, **_kwargs: {"codex": {"soft_gated": False}})
        monkeypatch.setattr(MODULE, "_active_worker_count_by_alias", lambda *_args, **_kwargs: {})

        dispatched_tasks: list[str] = []

        def fake_dispatch(_req, task_payload, *_args, **_kwargs):
            task_id = MODULE._as_str(task_payload.get("task_id"))
            dispatched_tasks.append(task_id)
            task_payload["dispatch_thread_id"] = f"thread-{task_id}"
            return {
                "ok": True,
                "dispatch": {"dispatch_mode_used": "exec", "dispatch_thread_id": f"thread-{task_id}"},
            }

        monkeypatch.setattr(MODULE, "_dispatch_task_packet", fake_dispatch)

        assignments = [
            {"task_id": "TASK-001", "lane_id": "phase-1/lane-a", "phase_id": "phase-1", "next_stage": "dev", "next_role": "developer", "slot": "dev-1", "dispatch_policy": "resume_if_same_lane"},
            {"task_id": "TASK-002", "lane_id": "phase-1/lane-b", "phase_id": "phase-1", "next_stage": "dev", "next_role": "developer", "slot": "dev-2", "dispatch_policy": "resume_if_same_lane"},
            {"task_id": "TASK-003", "lane_id": "phase-1/lane-c", "phase_id": "phase-1", "next_stage": "dev", "next_role": "developer", "slot": "dev-3", "dispatch_policy": "resume_if_same_lane"},
        ]
        out = MODULE._dispatch_next_task_from_assignments(req, plan_packets, task_state, build_state, assignments)
        assert out.get("ok") is True
        assert out.get("status") == "completed"
        assert out.get("dispatch_count") == 2
        assert len(dispatched_tasks) == 2
        observations = out.get("assignment_observations") or []
        assert any(isinstance(item, dict) and item.get("reason_code") == "dispatch_cycle_cap_reached" for item in observations)


def test_dispatch_resume_startup_failure_sets_exec_only_slot_policy(monkeypatch: pytest.MonkeyPatch):
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
        req = MODULE.parse_request({"command": "/op-build", "repo_root": str(root), "dry_run": True})
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        build_state["profile_aliases"] = ["codex"]
        build_state["slot_profile_assignments"] = {"dev-1": "codex"}
        MODULE._ensure_worker_registry_v2(root, build_state)
        registry_path = root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
        registry_payload = json.loads(registry_path.read_text(encoding="utf-8"))
        for row in registry_payload.get("workers", []):
            if row.get("slot") == "dev-1":
                row["worktree_root"] = str(root)
                row["branch"] = "codex/dev-1/task"
                row["lane_id"] = "phase-1/lane-a"
                row["previous_lane_id"] = "phase-1/lane-a"
                row["dispatch_thread_id"] = "thread-old"
        registry_path.write_text(json.dumps(registry_payload, indent=2) + "\n", encoding="utf-8")
        _write_workstation_registry_slot(
            root,
            slot="dev-1",
            task_id="TASK-001",
            lane_id="phase-1/lane-a",
            stage="dev",
            branch="codex/dev-1/task",
            worktree_root=root,
        )
        for row in task_state.get("tasks", []):
            if row.get("task_id") == "TASK-001":
                row["status"] = "pending"
                row["lane_id"] = "phase-1/lane-a"
                row["dispatch_thread_id"] = "thread-old"

        monkeypatch.setattr(MODULE, "_select_profile_alias_for_slot", lambda *_args, **_kwargs: {"ok": True, "alias": "codex"})
        monkeypatch.setattr(MODULE, "_read_profile_rate_states", lambda *_args, **_kwargs: {"codex": {"soft_gated": False}})
        monkeypatch.setattr(MODULE, "_active_worker_count_by_alias", lambda *_args, **_kwargs: {})
        monkeypatch.setattr(
            MODULE,
            "_dispatch_task_packet",
            lambda *_args, **_kwargs: {
                "ok": True,
                "dispatch": {
                    "dispatch_mode_used": "exec",
                    "dispatch_thread_id": "thread-fallback",
                    "warnings": [{"code": "dispatch_resume_notty_detected"}],
                },
            },
        )

        assignments = [
            {"task_id": "TASK-001", "lane_id": "phase-1/lane-a", "phase_id": "phase-1", "next_stage": "dev", "next_role": "developer", "slot": "dev-1", "dispatch_policy": "resume_if_same_lane"}
        ]
        out = MODULE._dispatch_next_task_from_assignments(req, plan_packets, task_state, build_state, assignments)
        warning_codes = {
            item.get("code")
            for item in out.get("warnings", [])
            if isinstance(item, dict)
        }
        assert "dispatch_resume_temporarily_disabled_slot" in warning_codes
        assert build_state.get("slot_resume_policy", {}).get("dev-1") == "exec_only"
        assert build_state.get("resume_fail_counts_by_slot", {}).get("dev-1") == 1
