import importlib.util
import hashlib
import json
import os
import subprocess
import sys
import tempfile
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
                "    {'task_id': 'TASK-001', 'title': 'Implement core workflow', 'phase_id': 'phase-1', 'lane_id': 'phase-1/lane-a', 'status': 'pending', 'requirement_ids': ['REQ-001'], 'depends_on': [], 'must_haves': ['core path'], 'verify_commands': ['python3 -m pytest'], 'gaps_that_need_patching': []},",
                "    {'task_id': 'TASK-002', 'title': 'Implement quality gates', 'phase_id': 'phase-1', 'lane_id': 'phase-1/lane-b', 'status': 'pending', 'requirement_ids': ['REQ-002'], 'depends_on': ['TASK-001'], 'must_haves': ['quality path'], 'verify_commands': ['python3 -m pytest'], 'gaps_that_need_patching': []},",
                "    {'task_id': 'TASK-003', 'title': 'Implement rollout ops', 'phase_id': 'phase-1', 'lane_id': 'phase-1/lane-c', 'status': 'pending', 'requirement_ids': ['REQ-003'], 'depends_on': ['TASK-002'], 'must_haves': ['ops path'], 'verify_commands': ['python3 -m pytest'], 'gaps_that_need_patching': []},",
                "]",
                "plan_packets = {",
                "    'schema_version': '1.0',",
                "    'generated_at': '2026-01-01T00:00:00Z',",
                "    'plan_id': plan_id,",
                "    'phase': 'multi-phase',",
                "    'phases': [{'phase_id': 'phase-1', 'task_ids': ['TASK-001', 'TASK-002', 'TASK-003'], 'depends_on_phase_ids': [], 'entry_criteria': ['phase_dependencies_done'], 'exit_criteria': ['all_tasks_review_done', 'verify_commands_passed', 'uat_matrix_passed', 'zero_open_gaps']}],",
                "    'requirements': requirements,",
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
                "    task_state['tasks'].append({'task_id': task_id, 'phase_id': task['phase_id'], 'lane_id': task['lane_id'], 'requirement_ids': task['requirement_ids'], 'status': 'pending', 'owner_slot': None, 'dispatch_thread_id': None, 'last_progress_at': None, 'attempts': {'dev': 0, 'test': 0, 'review': 0}, 'evidence': {'task_evidence_ref': evidence_ref, 'dev_ready_evidence_ref': evidence_ref, 'verify_results': [], 'uat_results': []}, 'gaps_that_need_patching': [], 'blockers': []})",
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
                "    ev = {'schema_version': '1.0', 'plan_id': plan_id, 'phase_id': task['phase_id'], 'task_id': task_id, 'requirement_ids': task['requirement_ids'], 'updated_at': '2026-01-01T00:00:00Z', 'dev': {'status': 'queued', 'checks': [], 'verify_results': [], 'dev_ready': False, 'blockers': [], 'artifacts': []}, 'test': {'status': 'queued', 'checks': [], 'verify_results': [], 'uat_results': [], 'blockers': [], 'artifacts': []}, 'review': {'status': 'queued', 'decision': None, 'blockers': [], 'artifacts': []}, 'gate': {'ready_for_test': False, 'ready_for_review': False, 'ready_for_phase_exit': False}, 'summary': {'result': 'pass', 'reason_codes': []}}",
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


def test_build_preflight_blocks_when_profile_selection_missing():
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
        profile_path = root / "reports" / "optimus-prime" / "planning" / "PROFILE_SELECTION.json"
        profile_path.unlink(missing_ok=True)
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
        assert any(item.get("code") == "profile_selection_missing" for item in out.get("warnings", []))


def test_build_preflight_blocks_when_profile_selection_invalid():
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
        profile_path = root / "reports" / "optimus-prime" / "planning" / "PROFILE_SELECTION.json"
        profile_path.write_text(
            json.dumps({"schema_version": "1.0", "selected_aliases": []}, indent=2) + "\n",
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
        assert out["status"] == "blocked_preflight"
        assert any(item.get("code") == "profile_selection_invalid" for item in out.get("warnings", []))


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
        build_state["profile_aliases"] = ["codex"]

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
        events_path = root / "reports" / "optimus-prime" / "controller" / "EVENTS.jsonl"
        events_path.parent.mkdir(parents=True, exist_ok=True)
        events_path.write_text("", encoding="utf-8")
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
            lambda _req, **_kwargs: {
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
            payload = {
                "profiles": {
                    "codex": {"recommended_action": "continue"},
                    "codex-second": {"recommended_action": "continue"},
                },
            }
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
        assert "--profile" in cmd
        assert "codex=default" in cmd
        assert any(str(item).startswith("codex-second=") for item in cmd)


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
            lambda _req, **_kwargs: (
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
            lambda _req, **_kwargs: {
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
        planning_root = (root / "reports" / "optimus-prime" / "planning").resolve()
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
        build_state = json.loads((root / "reports" / "optimus-prime" / "planning" / "BUILD_STATE.json").read_text(encoding="utf-8"))
        recovery = build_state.get("gap_artifact_recovery", {})
        assert recovery.get("reason") is None


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
        planning_root = (root / "reports" / "optimus-prime" / "planning").resolve()
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
        assert out["status"] == "running_needs_resume"
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
        planning_root = (root / "reports" / "optimus-prime" / "planning").resolve()
        task_state_path = planning_root / "TASK_EXECUTION_STATE.json"
        task_state = json.loads(task_state_path.read_text(encoding="utf-8"))
        first_task = next(task for task in task_state["tasks"] if isinstance(task, dict))
        first_task["gaps_that_need_patching"] = [
            {
                "gap_id": "gap-preserve-001",
                "category": "task_blocked",
                "severity": "P1",
                "stage": "dev",
                "status": "open",
                "reason_codes": ["task_state_blocked"],
                "retry_count": 0,
                "max_retries": 5,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
                "closure_ref": None,
            }
        ]
        task_state_path.write_text(json.dumps(task_state, indent=2) + "\n", encoding="utf-8")
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
        refreshed = json.loads(task_state_path.read_text(encoding="utf-8"))
        open_ids = set()
        for row in refreshed.get("tasks", []):
            if not isinstance(row, dict):
                continue
            for gap in row.get("gaps_that_need_patching", []):
                if isinstance(gap, dict) and gap.get("status") == "open":
                    open_ids.add(gap.get("gap_id"))
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


def test_corruption_policy_matrix_malformed_legacy_gaps_across_commands():
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

        assert status["status"] == "completed"
        assert health["status"] == "completed"
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

        planning_root = (root / "reports" / "optimus-prime" / "planning").resolve()
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
        assert task_after["status"] == "pending"
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
        assert task_after["status"] == "dev_working"
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
        task_state["tasks"][0]["status"] = "blocked"
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
        task_state["tasks"][0]["status"] = "blocked"
        task_state["tasks"][1]["status"] = "blocked"

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
        task_state["tasks"][0]["status"] = "blocked"
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

        task_state["tasks"][0]["status"] = "blocked"
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
        tasks = plan_packets.get("tasks")
        assert isinstance(tasks, list) and tasks
        for task in tasks:
            assert isinstance(task, dict)
            assert isinstance(task.get("lane_id"), str) and task.get("lane_id")
            assert task.get("status") == "pending"
            assert isinstance(task.get("gaps_that_need_patching"), list)


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
        assert warnings == []
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
        assert MODULE._git_text(root, "show-ref", "--verify", "refs/heads/RAB-BASE")
        assert isinstance(warnings, list)
        assert artifacts


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


def test_dispatcher_consumes_work_dispatch_plan_only(monkeypatch: pytest.MonkeyPatch):
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
                row["branch"] = "codex/dev-1/task-002"
        registry_path.write_text(json.dumps(registry_payload, indent=2) + "\n", encoding="utf-8")

        for row in task_state.get("tasks", []):
            if row.get("task_id") in {"TASK-001", "TASK-002"}:
                row["status"] = "pending"
                row["owner_slot"] = None
        dispatched: list[str] = []

        def fake_dispatch(*_args, **kwargs):
            task = _args[1]
            dispatched.append(task.get("task_id"))
            task["dispatch_thread_id"] = "thread-1"
            return {"ok": True, "dispatch": {"dispatch_mode_used": "exec", "dispatch_thread_id": "thread-1"}}

        monkeypatch.setattr(MODULE, "_dispatch_task_packet", fake_dispatch)
        (planning / "WORK_DISPATCH_PLAN.json").write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "updated_at": "2026-01-01T00:00:00Z",
                    "active_phase_id": "phase-1",
                    "assignments": [
                        {
                            "task_id": "TASK-002",
                            "lane_id": "phase-1/lane-b",
                            "phase_id": "phase-1",
                            "next_stage": "dev",
                            "next_role": "developer",
                            "slot": "dev-1",
                            "dispatch_policy": "resume_if_same_lane",
                        }
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        out = MODULE._manager_dispatcher_cycle(
            req,
            plan_packets=plan_packets,
            task_state=task_state,
            build_state=build_state,
            active_phase_id="phase-1",
        )
        assert out.get("ok") is True
        assert dispatched == ["TASK-002"]


def test_dispatcher_invalid_work_dispatch_plan_returns_deterministic_warning():
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
        (planning / "WORK_DISPATCH_PLAN.json").write_text("{invalid", encoding="utf-8")
        out = MODULE._manager_dispatcher_cycle(
            req,
            plan_packets=plan_packets,
            task_state=task_state,
            build_state=build_state,
            active_phase_id="phase-1",
        )
        warning_codes = {
            item.get("code")
            for item in out.get("warnings", [])
            if isinstance(item, dict)
        }
        assert out.get("status") == "skipped"
        assert out.get("reason") == "dispatch_plan_invalid"
        assert "dispatch_plan_invalid" in warning_codes


def test_manager_dispatcher_empty_assignments_returns_dispatch_plan_no_assignments():
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
        (planning / "WORK_DISPATCH_PLAN.json").write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "updated_at": "2026-01-01T00:00:00Z",
                    "active_phase_id": "phase-1",
                    "assignments": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        out = MODULE._manager_dispatcher_cycle(
            req,
            plan_packets=plan_packets,
            task_state=task_state,
            build_state=build_state,
            active_phase_id="phase-1",
        )
        warning_codes = {
            item.get("code")
            for item in out.get("warnings", [])
            if isinstance(item, dict)
        }
        assert out.get("status") == "noop"
        assert out.get("reason") == "dispatch_plan_no_assignments"
        assert "dispatch_plan_no_assignments" in warning_codes
        assert out.get("assignment_observations") == []


def test_dispatch_packet_uses_slot_worktree_root_and_branch(monkeypatch: pytest.MonkeyPatch):
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
        custom_worktree = root / "custom-worktree"
        custom_worktree.mkdir(parents=True, exist_ok=True)
        registry_path = root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
        registry_payload = json.loads(registry_path.read_text(encoding="utf-8"))
        for row in registry_payload.get("workers", []):
            if row.get("slot") == "dev-1":
                row["worktree_root"] = str(custom_worktree)
                row["branch"] = "codex/dev-1/task-001"
        registry_path.write_text(json.dumps(registry_payload, indent=2) + "\n", encoding="utf-8")
        for row in task_state.get("tasks", []):
            if row.get("task_id") == "TASK-001":
                row["status"] = "pending"
                row["owner_slot"] = None
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
                        }
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        captured_payloads: list[dict[str, object]] = []

        def fake_run_tool(_script, payload, _cwd):
            captured_payloads.append(dict(payload))
            return {"ok": True, "dispatch_thread_id": "thread-123"}

        monkeypatch.setattr(MODULE, "_run_tool_json", fake_run_tool)
        out = MODULE._manager_dispatcher_cycle(
            req,
            plan_packets=plan_packets,
            task_state=task_state,
            build_state=build_state,
            active_phase_id="phase-1",
        )
        assert out.get("ok") is True
        assert captured_payloads
        assert captured_payloads[0].get("worktree_root") == str(custom_worktree)
        assert captured_payloads[0].get("branch_name") == "codex/dev-1/task-001"


def test_test_stage_dispatch_packet_uses_dev_branch_head_and_slot_context(monkeypatch: pytest.MonkeyPatch):
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
        build_state["slot_profile_assignments"] = {"test-1": "codex"}
        MODULE._ensure_worker_registry_v2(root, build_state)

        custom_worktree = root / "custom-test-worktree"
        custom_worktree.mkdir(parents=True, exist_ok=True)
        registry_path = root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
        registry_payload = json.loads(registry_path.read_text(encoding="utf-8"))
        for row in registry_payload.get("workers", []):
            if row.get("slot") == "test-1":
                row["worktree_root"] = str(custom_worktree)
                row["branch"] = "codex/test-1/bootstrap"
        registry_path.write_text(json.dumps(registry_payload, indent=2) + "\n", encoding="utf-8")

        for row in task_state.get("tasks", []):
            if row.get("task_id") == "TASK-001":
                row["status"] = "dev_done"
                row["owner_slot"] = None
                row["active_branch"] = "codex/dev-1/task-001"

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
                            "next_stage": "test",
                            "next_role": "tester",
                            "slot": "test-1",
                            "dispatch_policy": "resume_if_same_lane",
                        }
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        captured_payloads: list[dict[str, object]] = []

        def fake_git_text(_repo_root: Path, *args: str) -> str:
            if args == ("rev-parse", "codex/dev-1/task-001"):
                return "a" * 40
            if args == ("rev-parse", "RAB-BASE"):
                return "b" * 40
            if args == ("rev-parse", "HEAD"):
                return "c" * 40
            return ""

        def fake_run_tool(_script, payload, _cwd):
            captured_payloads.append(dict(payload))
            return {"ok": True, "dispatch_thread_id": "thread-test-1"}

        monkeypatch.setattr(MODULE, "_git_text", fake_git_text)
        monkeypatch.setattr(MODULE, "_run_tool_json", fake_run_tool)
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
        out = MODULE._manager_dispatcher_cycle(
            req,
            plan_packets=plan_packets,
            task_state=task_state,
            build_state=build_state,
            active_phase_id="phase-1",
        )
        assert out.get("ok") is True
        assert captured_payloads
        payload = captured_payloads[0]
        assert payload.get("worktree_root") == str(custom_worktree)
        assert payload.get("branch_name") == "codex/test-1/task-001-test"
        assert payload.get("start_from_branch") == "codex/dev-1/task-001"
        assert payload.get("start_from_commit") == "a" * 40
        assert payload.get("test_source_branch") == "codex/dev-1/task-001"
        assert payload.get("test_source_commit") == "a" * 40


def test_test_stage_dispatch_skips_when_dev_branch_missing(monkeypatch: pytest.MonkeyPatch):
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
        build_state["slot_profile_assignments"] = {"test-1": "codex"}
        MODULE._ensure_worker_registry_v2(root, build_state)

        registry_path = root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
        registry_payload = json.loads(registry_path.read_text(encoding="utf-8"))
        for row in registry_payload.get("workers", []):
            if row.get("slot") == "test-1":
                row["worktree_root"] = str(root)
                row["branch"] = "codex/test-1/bootstrap"
        registry_path.write_text(json.dumps(registry_payload, indent=2) + "\n", encoding="utf-8")

        for row in task_state.get("tasks", []):
            if row.get("task_id") == "TASK-001":
                row["status"] = "dev_done"
                row["owner_slot"] = None
                row["active_branch"] = None

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
                            "next_stage": "test",
                            "next_role": "tester",
                            "slot": "test-1",
                            "dispatch_policy": "resume_if_same_lane",
                        }
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        called = {"value": False}

        def fake_run_tool(_script, _payload, _cwd):
            called["value"] = True
            return {"ok": True}

        monkeypatch.setattr(MODULE, "_run_tool_json", fake_run_tool)
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

        out = MODULE._manager_dispatcher_cycle(
            req,
            plan_packets=plan_packets,
            task_state=task_state,
            build_state=build_state,
            active_phase_id="phase-1",
        )
        assert called["value"] is False
        warning_codes = {
            item.get("code")
            for item in out.get("warnings", [])
            if isinstance(item, dict)
        }
        assert "dispatch_assignment_missing_dev_branch" in warning_codes
        observations = out.get("assignment_observations")
        assert isinstance(observations, list)
        assert any(
            isinstance(item, dict) and item.get("reason_code") == "dispatch_assignment_missing_dev_branch"
            for item in observations
        )


def test_first_assignment_sets_lane_and_previous_lane_equal(monkeypatch: pytest.MonkeyPatch):
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
                row["lane_id"] = None
                row["previous_lane_id"] = "n/a"
                row["worktree_root"] = str(root)
                row["branch"] = "codex/dev-1/task-001"
        registry_path.write_text(json.dumps(registry_payload, indent=2) + "\n", encoding="utf-8")
        monkeypatch.setattr(
            MODULE,
            "_dispatch_task_packet",
            lambda *_args, **_kwargs: {
                "ok": True,
                "dispatch": {"dispatch_mode_used": "exec", "dispatch_thread_id": "thread-1"},
            },
        )
        monkeypatch.setattr(
            MODULE,
            "_select_profile_alias_for_slot",
            lambda *_args, **_kwargs: {"ok": True, "alias": "codex"},
        )
        monkeypatch.setattr(MODULE, "_active_worker_count_by_alias", lambda *_args, **_kwargs: {})
        monkeypatch.setattr(
            MODULE,
            "_read_profile_rate_states",
            lambda *_args, **_kwargs: {"codex": {"hard_gated": False, "soft_gated": False}},
        )
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
                        }
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        out = MODULE._manager_dispatcher_cycle(
            req,
            plan_packets=plan_packets,
            task_state=task_state,
            build_state=build_state,
            active_phase_id="phase-1",
        )
        assert out.get("ok") is True
        registry_after = json.loads(registry_path.read_text(encoding="utf-8"))
        row = next(item for item in registry_after.get("workers", []) if isinstance(item, dict) and item.get("slot") == "dev-1")
        assert row.get("lane_id") == "phase-1/lane-a"
        assert row.get("previous_lane_id") == "phase-1/lane-a"


def test_lane_change_rotates_previous_lane(monkeypatch: pytest.MonkeyPatch):
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
                row["lane_id"] = "phase-1/lane-a"
                row["previous_lane_id"] = "phase-1/lane-a"
                row["worktree_root"] = str(root)
                row["branch"] = "codex/dev-1/task-002"
        registry_path.write_text(json.dumps(registry_payload, indent=2) + "\n", encoding="utf-8")
        for row in task_state.get("tasks", []):
            if row.get("task_id") == "TASK-002":
                row["status"] = "pending"
        monkeypatch.setattr(
            MODULE,
            "_dispatch_task_packet",
            lambda *_args, **_kwargs: {
                "ok": True,
                "dispatch": {"dispatch_mode_used": "exec", "dispatch_thread_id": "thread-2"},
            },
        )
        monkeypatch.setattr(
            MODULE,
            "_select_profile_alias_for_slot",
            lambda *_args, **_kwargs: {"ok": True, "alias": "codex"},
        )
        monkeypatch.setattr(MODULE, "_active_worker_count_by_alias", lambda *_args, **_kwargs: {})
        monkeypatch.setattr(
            MODULE,
            "_read_profile_rate_states",
            lambda *_args, **_kwargs: {"codex": {"hard_gated": False, "soft_gated": False}},
        )
        (planning / "WORK_DISPATCH_PLAN.json").write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "updated_at": "2026-01-01T00:00:00Z",
                    "active_phase_id": "phase-1",
                    "assignments": [
                        {
                            "task_id": "TASK-002",
                            "lane_id": "phase-1/lane-b",
                            "phase_id": "phase-1",
                            "next_stage": "dev",
                            "next_role": "developer",
                            "slot": "dev-1",
                            "dispatch_policy": "resume_if_same_lane",
                        }
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        MODULE._manager_dispatcher_cycle(
            req,
            plan_packets=plan_packets,
            task_state=task_state,
            build_state=build_state,
            active_phase_id="phase-1",
        )
        registry_after = json.loads(registry_path.read_text(encoding="utf-8"))
        row = next(item for item in registry_after.get("workers", []) if isinstance(item, dict) and item.get("slot") == "dev-1")
        assert row.get("lane_id") == "phase-1/lane-b"
        assert row.get("previous_lane_id") == "phase-1/lane-a"


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


def test_fan_in_syncs_task_evidence_from_worktree_before_state_resolution():
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
        task = next(item for item in task_state["tasks"] if item.get("task_id") == "TASK-001")
        task["status"] = "dev_working"
        task["owner_slot"] = "dev-1"
        task["lane_id"] = "phase-1/lane-a"
        worktree_root = root / ".MyBoard-workstations" / "workstation-dev-1"
        evidence_path = worktree_root / "reports" / "optimus-prime" / "planning" / "evidence" / "TASK-001" / "TASK_EVIDENCE.json"
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_payload = {
            "schema_version": "1.0",
            "plan_id": plan_packets.get("plan_id"),
            "phase_id": "phase-1",
            "task_id": "TASK-001",
            "requirement_ids": ["REQ-001"],
            "updated_at": "2026-01-01T00:00:00Z",
            "dev": {"status": "done", "checks": [], "verify_results": [], "dev_ready": True, "blockers": [], "artifacts": []},
            "test": {"status": "pending", "checks": [], "verify_results": [], "uat_results": [], "blockers": [], "artifacts": []},
            "review": {"status": "pending", "decision": None, "status": "pending", "blockers": [], "artifacts": []},
            "gate": {"ready_for_test": True, "ready_for_review": False, "ready_for_phase_exit": False},
            "summary": {"result": "pass", "reason_codes": ["fan_in_sync"]},
        }
        evidence_path.write_text(json.dumps(evidence_payload, indent=2) + "\n", encoding="utf-8")
        MODULE._ensure_worker_registry_v2(root, build_state)
        registry_path = root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
        registry_payload = json.loads(registry_path.read_text(encoding="utf-8"))
        for row in registry_payload.get("workers", []):
            if row.get("slot") == "dev-1":
                row["worktree_root"] = str(worktree_root)
                row["active_task_id"] = "TASK-001"
                row["active_task"] = "TASK-001"
                row["lane_id"] = "phase-1/lane-a"
                row["previous_lane_id"] = "phase-1/lane-a"
        registry_path.write_text(json.dumps(registry_payload, indent=2) + "\n", encoding="utf-8")

        out = MODULE._manager_production_line_cycle(
            req,
            plan_packets=plan_packets,
            task_state=task_state,
            build_state=build_state,
        )
        warning_codes = {item.get("code") for item in out.get("warnings", []) if isinstance(item, dict)}
        assert "worktree_artifacts_synced" in warning_codes
        task_after = next(item for item in task_state["tasks"] if item.get("task_id") == "TASK-001")
        assert task_after.get("status") == "dev_done"


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
        evidence_payload["gate"]["ready_for_test"] = True
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
        assert task.get("status") == "dev_done"
        assert task.get("owner_slot") is None


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
        assert task.get("status") == "blocked"
        assert "worker_completion_artifact_missing" in warning_codes
        gap_rows = task.get("gaps_that_need_patching")
        assert isinstance(gap_rows, list) and gap_rows
        assert any((row.get("status") == "open" and row.get("stage") == "dev") for row in gap_rows if isinstance(row, dict))


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


def test_branch_manager_llm_action_schema_invalid_retries_then_blocks_task(monkeypatch: pytest.MonkeyPatch):
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
        req = MODULE.parse_request({"command": "/op-build", "repo_root": str(root)})
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        task = next(item for item in task_state["tasks"] if item.get("task_id") == "TASK-001")
        task["status"] = "review_done"
        task["active_branch"] = "codex/dev-1/task-001"
        monkeypatch.setattr(
            MODULE,
            "run_codex_exec",
            lambda **_kwargs: 0,
        )
        warnings = MODULE._manager_branch_merge_cycle(
            req,
            plan_packets=plan_packets,
            task_state=task_state,
            build_state=build_state,
        )
        warning_codes = {item.get("code") for item in warnings if isinstance(item, dict)}
        assert "merge_manager_retry_exhausted" in warning_codes
        assert "branch_manager_action_invalid" in warning_codes
        assert task["status"] == "blocked"
        assert any(
            isinstance(item, dict) and item.get("category") == "merge_blocked"
            for item in task.get("gaps_that_need_patching", [])
        )


def test_workstation_manager_llm_action_schema_invalid_retries_then_blocks_task(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
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
        req = MODULE.parse_request({"command": "/op-build", "repo_root": str(root)})
        planning = root / "reports" / "optimus-prime" / "planning"
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        MODULE._ensure_worker_registry_v2(root, build_state)
        task = next(item for item in task_state["tasks"] if item.get("task_id") == "TASK-001")
        task["status"] = "dev_working"
        task["owner_slot"] = "dev-1"
        registry_path = root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
        registry_payload = json.loads(registry_path.read_text(encoding="utf-8"))
        for row in registry_payload.get("workers", []):
            if row.get("slot") == "dev-1":
                row["active_task_id"] = "TASK-001"
                row["active_task"] = "TASK-001"
                row["lane_id"] = "phase-1/lane-a"
                row["previous_lane_id"] = "phase-1/lane-b"
                row["branch"] = "codex/dev-1/task-001"
                row["worktree_root"] = None
        registry_path.write_text(json.dumps(registry_payload, indent=2) + "\n", encoding="utf-8")
        monkeypatch.setattr(
            MODULE,
            "run_codex_exec",
            lambda **_kwargs: 0,
        )
        monkeypatch.setattr(MODULE.sys.stdout, "isatty", lambda: True)
        out = MODULE._manager_workstation_cycle(req, task_state=task_state, build_state=build_state)
        logs = capsys.readouterr().out
        warnings = out.get("warnings", [])
        warning_codes = {item.get("code") for item in warnings if isinstance(item, dict)}
        assert "workstation_manager_retry_exhausted" in warning_codes
        assert "workstation_action_invalid" in warning_codes
        assert "retrying." in logs
        assert task["status"] == "blocked"


def _write_manager_action_from_prompt(prompt_text: str, payload: dict[str, object]) -> None:
    marker = "Write JSON action file to: "
    path_line = next((line for line in prompt_text.splitlines() if marker in line), "")
    action_path = Path(path_line.split(marker, 1)[1].strip())
    action_path.parent.mkdir(parents=True, exist_ok=True)
    action_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_branch_manager_success_updates_done_registry_with_verification_ref(monkeypatch: pytest.MonkeyPatch):
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
        req = MODULE.parse_request({"command": "/op-build", "repo_root": str(root)})
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        task = next(item for item in task_state["tasks"] if item.get("task_id") == "TASK-001")
        task["status"] = "review_done"
        task["active_branch"] = "codex/dev-1/task-001"

        def fake_codex_exec(**kwargs):
            prompt = str(kwargs.get("prompt_text") or "")
            _write_manager_action_from_prompt(
                prompt,
                {
                    "schema_version": "1.0",
                    "task_id": "TASK-001",
                    "attempt": 1,
                    "target_branch": "RAB-BASE",
                    "source_branch": "codex/dev-1/task-001",
                    "merge_strategy": "no_ff",
                    "commands": [
                        "git checkout RAB-BASE",
                        "git merge --no-ff --no-edit codex/dev-1/task-001",
                    ],
                    "verification_commands": ["python3 -m pytest"],
                },
            )
            return 0

        monkeypatch.setattr(MODULE, "run_codex_exec", fake_codex_exec)
        monkeypatch.setattr(
            MODULE,
            "_run_manager_command",
            lambda *args, **kwargs: {
                "ok": True,
                "code": None,
                "message": "",
                "stdout": "",
                "stderr": "",
                "exit_code": 0,
                "timed_out": False,
            },
        )
        monkeypatch.setattr(MODULE, "_git_text", lambda *_args, **_kwargs: "abc123")
        warnings = MODULE._manager_branch_merge_cycle(
            req,
            plan_packets=plan_packets,
            task_state=task_state,
            build_state=build_state,
        )
        warning_codes = {item.get("code") for item in warnings if isinstance(item, dict)}
        assert "merge_manager_retry_exhausted" not in warning_codes
        assert "branch_merge_pending_tasks" not in warning_codes
        done_registry = json.loads((planning / "DONE_TASKS_REGISTRY.json").read_text(encoding="utf-8"))
        merged_rows = done_registry.get("merged_tasks", [])
        row = next(item for item in merged_rows if isinstance(item, dict) and item.get("task_id") == "TASK-001")
        assert row["verification_passed"] is True
        assert row["verification_ref"]
        validation_path = root / MODULE._as_str(row["verification_ref"])
        validation_payload = json.loads(validation_path.read_text(encoding="utf-8"))
        assert validation_payload.get("merge_proof_passed") is True


def test_branch_manager_merge_proof_required_before_done_registry_update(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
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
        req = MODULE.parse_request({"command": "/op-build", "repo_root": str(root)})
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        task = next(item for item in task_state["tasks"] if item.get("task_id") == "TASK-001")
        task["status"] = "review_done"
        task["active_branch"] = "codex/dev-1/task-001"

        def fake_codex_exec(**kwargs):
            prompt = str(kwargs.get("prompt_text") or "")
            _write_manager_action_from_prompt(
                prompt,
                {
                    "schema_version": "1.0",
                    "task_id": "TASK-001",
                    "attempt": 1,
                    "target_branch": "RAB-BASE",
                    "source_branch": "codex/dev-1/task-001",
                    "merge_strategy": "no_ff",
                    "commands": [
                        "git checkout RAB-BASE",
                        "git merge --no-ff --no-edit codex/dev-1/task-001",
                    ],
                    "verification_commands": ["python3 -m pytest"],
                },
            )
            return 0

        command_log: list[str] = []

        def fake_run_manager_command(command_text, **_kwargs):
            text = str(command_text).strip()
            command_log.append(text)
            if "merge-base --is-ancestor" in text:
                return {
                    "ok": False,
                    "code": "merge_proof_failed",
                    "message": "merge proof failed",
                    "stdout": "",
                    "stderr": "",
                    "exit_code": 1,
                    "timed_out": False,
                }
            return {
                "ok": True,
                "code": None,
                "message": "",
                "stdout": "",
                "stderr": "",
                "exit_code": 0,
                "timed_out": False,
            }

        monkeypatch.setattr(MODULE, "run_codex_exec", fake_codex_exec)
        monkeypatch.setattr(MODULE.sys.stdout, "isatty", lambda: True)
        monkeypatch.setattr(MODULE, "_run_manager_command", fake_run_manager_command)

        warnings = MODULE._manager_branch_merge_cycle(
            req,
            plan_packets=plan_packets,
            task_state=task_state,
            build_state=build_state,
        )
        logs = capsys.readouterr().out
        warning_codes = {item.get("code") for item in warnings if isinstance(item, dict)}
        assert "merge_proof_failed" in warning_codes
        assert "merge_manager_retry_exhausted" in warning_codes
        assert "branch-merge-manager: task=TASK-001 attempt 1/10" in logs
        assert "Applying necessary fixes and retrying." in logs
        assert task["status"] == "blocked"
        assert any(
            isinstance(item, dict) and item.get("category") == "merge_blocked"
            for item in task.get("gaps_that_need_patching", [])
        )
        done_registry = json.loads((planning / "DONE_TASKS_REGISTRY.json").read_text(encoding="utf-8"))
        merged_task_ids = {
            item.get("task_id")
            for item in done_registry.get("merged_tasks", [])
            if isinstance(item, dict)
        }
        assert "TASK-001" not in merged_task_ids
        assert any(item.startswith("git reset --hard ") for item in command_log)
        assert not any("HEAD~1" in item for item in command_log)
        validation_path = (
            root
            / "reports"
            / "optimus-prime"
            / "branch-manager"
            / "attempt-task-001-1"
            / "MERGE_VALIDATION.json"
        )
        payload = json.loads(validation_path.read_text(encoding="utf-8"))
        assert payload.get("rollback_applied") is True
        rollback_target = payload.get("rollback_target")
        assert isinstance(rollback_target, str) and rollback_target.strip()


def test_branch_manager_rollback_uses_pre_merge_head_not_head_parent(monkeypatch: pytest.MonkeyPatch):
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
        req = MODULE.parse_request({"command": "/op-build", "repo_root": str(root)})
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        task = next(item for item in task_state["tasks"] if item.get("task_id") == "TASK-001")
        task["status"] = "review_done"
        task["active_branch"] = "codex/dev-1/task-001"

        def fake_codex_exec(**kwargs):
            prompt = str(kwargs.get("prompt_text") or "")
            _write_manager_action_from_prompt(
                prompt,
                {
                    "schema_version": "1.0",
                    "task_id": "TASK-001",
                    "attempt": 1,
                    "target_branch": "RAB-BASE",
                    "source_branch": "codex/dev-1/task-001",
                    "merge_strategy": "no_ff",
                    "commands": [
                        "git checkout RAB-BASE",
                        "git merge --no-ff --no-edit codex/dev-1/task-001",
                    ],
                    "verification_commands": ["python3 -m pytest"],
                },
            )
            return 0

        command_log: list[str] = []
        verify_attempts = {"count": 0}

        def fake_run_manager_command(command_text, **_kwargs):
            text = str(command_text).strip()
            command_log.append(text)
            if text.startswith("python3 -m pytest"):
                verify_attempts["count"] += 1
                if verify_attempts["count"] == 1:
                    return {
                        "ok": False,
                        "code": "branch_manager_execution_failed",
                        "message": "simulated verify failure",
                        "stdout": "",
                        "stderr": "",
                        "exit_code": 1,
                        "timed_out": False,
                    }
            return {
                "ok": True,
                "code": None,
                "message": "",
                "stdout": "",
                "stderr": "",
                "exit_code": 0,
                "timed_out": False,
            }

        head_values = iter(["pre-merge-1", "merged-1", "pre-merge-2", "merged-2"])

        def fake_git_text(_repo_root, *args):
            if args == ("rev-parse", "HEAD"):
                return next(head_values, "head-final")
            return "abc123"

        monkeypatch.setattr(MODULE, "run_codex_exec", fake_codex_exec)
        monkeypatch.setattr(MODULE, "_run_manager_command", fake_run_manager_command)
        monkeypatch.setattr(MODULE, "_git_text", fake_git_text)

        warnings = MODULE._manager_branch_merge_cycle(
            req,
            plan_packets=plan_packets,
            task_state=task_state,
            build_state=build_state,
        )
        warning_codes = {item.get("code") for item in warnings if isinstance(item, dict)}
        assert "merge_manager_retry_exhausted" not in warning_codes
        assert "git reset --hard pre-merge-1" in command_log
        assert not any("HEAD~1" in item for item in command_log)


def test_branch_manager_validation_records_rollback_metadata_on_verify_fail(monkeypatch: pytest.MonkeyPatch):
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
        req = MODULE.parse_request({"command": "/op-build", "repo_root": str(root)})
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        task = next(item for item in task_state["tasks"] if item.get("task_id") == "TASK-001")
        task["status"] = "review_done"
        task["active_branch"] = "codex/dev-1/task-001"

        def fake_codex_exec(**kwargs):
            prompt = str(kwargs.get("prompt_text") or "")
            _write_manager_action_from_prompt(
                prompt,
                {
                    "schema_version": "1.0",
                    "task_id": "TASK-001",
                    "attempt": 1,
                    "target_branch": "RAB-BASE",
                    "source_branch": "codex/dev-1/task-001",
                    "merge_strategy": "no_ff",
                    "commands": [
                        "git checkout RAB-BASE",
                        "git merge --no-ff --no-edit codex/dev-1/task-001",
                    ],
                    "verification_commands": ["python3 -m pytest"],
                },
            )
            return 0

        verify_attempts = {"count": 0}

        def fake_run_manager_command(command_text, **_kwargs):
            text = str(command_text).strip()
            if text.startswith("python3 -m pytest"):
                verify_attempts["count"] += 1
                if verify_attempts["count"] == 1:
                    return {
                        "ok": False,
                        "code": "branch_manager_execution_failed",
                        "message": "simulated verify failure",
                        "stdout": "",
                        "stderr": "",
                        "exit_code": 1,
                        "timed_out": False,
                    }
            return {
                "ok": True,
                "code": None,
                "message": "",
                "stdout": "",
                "stderr": "",
                "exit_code": 0,
                "timed_out": False,
            }

        head_values = iter(["pre-merge-1", "merged-1", "pre-merge-2", "merged-2"])

        def fake_git_text(_repo_root, *args):
            if args == ("rev-parse", "HEAD"):
                return next(head_values, "head-final")
            return "abc123"

        monkeypatch.setattr(MODULE, "run_codex_exec", fake_codex_exec)
        monkeypatch.setattr(MODULE, "_run_manager_command", fake_run_manager_command)
        monkeypatch.setattr(MODULE, "_git_text", fake_git_text)

        MODULE._manager_branch_merge_cycle(
            req,
            plan_packets=plan_packets,
            task_state=task_state,
            build_state=build_state,
        )
        validation_path = (
            root
            / "reports"
            / "optimus-prime"
            / "branch-manager"
            / "attempt-task-001-1"
            / "MERGE_VALIDATION.json"
        )
        payload = json.loads(validation_path.read_text(encoding="utf-8"))
        assert payload.get("pre_merge_head") == "pre-merge-1"
        assert payload.get("rollback_applied") is True
        assert payload.get("rollback_target") == "pre-merge-1"


def test_workstation_manager_success_updates_slot_worktree_and_branch(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
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
        req = MODULE.parse_request({"command": "/op-build", "repo_root": str(root)})
        monkeypatch.setattr(MODULE.sys.stdout, "isatty", lambda: True)
        planning = root / "reports" / "optimus-prime" / "planning"
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        MODULE._ensure_worker_registry_v2(root, build_state)
        task = next(item for item in task_state["tasks"] if item.get("task_id") == "TASK-001")
        task["status"] = "dev_working"
        task["owner_slot"] = "dev-1"
        registry_path = root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
        registry_payload = json.loads(registry_path.read_text(encoding="utf-8"))
        for row in registry_payload.get("workers", []):
            if row.get("slot") == "dev-1":
                row["active_task_id"] = "TASK-001"
                row["active_task"] = "TASK-001"
                row["lane_id"] = "phase-1/lane-a"
                row["previous_lane_id"] = "phase-1/lane-b"
                row["branch"] = "codex/dev-1/task-001"
                row["worktree_root"] = None
            elif row.get("role") in {"developer", "tester", "reviewer"}:
                # Keep non-target slots stable so this test asserts only dev-1 success path.
                row["lane_id"] = "phase-1/lane-z"
                row["previous_lane_id"] = "phase-1/lane-z"
                row["worktree_root"] = str(root / "prepared-worktrees" / str(row.get("slot") or "slot"))
        registry_path.write_text(json.dumps(registry_payload, indent=2) + "\n", encoding="utf-8")
        target_path = MODULE._expected_slot_worktree_path(root, "dev-1")
        assert isinstance(target_path, Path)
        target_path.mkdir(parents=True, exist_ok=True)

        def fake_codex_exec(**kwargs):
            prompt = str(kwargs.get("prompt_text") or "")
            _write_manager_action_from_prompt(
                prompt,
                {
                    "schema_version": "1.0",
                    "slot": "dev-1",
                    "lane_id": "phase-1/lane-a",
                    "task_id": "TASK-001",
                    "branch_name": "codex/dev-1/task-001",
                    "worktree_name": "workstation-dev-1",
                    "prepare_command": f"python3 {MODULE._resolve_skill_script('workstation-preparation', 'prepare_workstation.py')} --repo-root {root} --base-ref RAB-BASE --branch-name codex/dev-1/task-001 --slot-role developer --output json --force-reset-existing --worktree-name workstation-dev-1",
                    "prereq_policy": "copy_env_files",
                },
            )
            return 0

        monkeypatch.setattr(MODULE, "run_codex_exec", fake_codex_exec)

        def fake_run_manager_command(command_text, **_kwargs):
            return {
                "ok": True,
                "code": None,
                "message": "",
                "stdout": json.dumps(
                    {
                        "ok": True,
                        "target_path": str(target_path),
                        "branch_name_resolved": "codex/dev-1/task-001",
                    }
                ),
                "stderr": "",
                "exit_code": 0,
                "timed_out": False,
            }

        monkeypatch.setattr(MODULE, "_run_manager_command", fake_run_manager_command)
        monkeypatch.setattr(
            MODULE,
            "_git_text",
            lambda repo_root, *args: "codex/dev-1/task-001" if str(repo_root) == str(target_path) else "abc123",
        )
        out = MODULE._manager_workstation_cycle(req, task_state=task_state, build_state=build_state)
        logs = capsys.readouterr().out
        assert out.get("fatal") is False
        warning_codes = {item.get("code") for item in out.get("warnings", []) if isinstance(item, dict)}
        assert "workstation_manager_retry_exhausted" not in warning_codes
        assert "workstation_action_invalid" not in warning_codes
        assert "workstation-manager: preparing slot=dev-1" in logs
        assert "workstation-manager: slot=dev-1 attempt 1/10" in logs
        assert "workstation-manager: slot=dev-1 ready worktree=" in logs
        registry_after = json.loads(registry_path.read_text(encoding="utf-8"))
        slot_row = next(item for item in registry_after.get("workers", []) if isinstance(item, dict) and item.get("slot") == "dev-1")
        assert slot_row.get("worktree_root") == str(target_path)
        assert slot_row.get("branch") == "codex/dev-1/task-001"


def test_workstation_missing_skill_is_fatal_and_writes_validation_artifact(monkeypatch: pytest.MonkeyPatch):
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
        req = MODULE.parse_request({"command": "/op-build", "repo_root": str(root)})
        planning = root / "reports" / "optimus-prime" / "planning"
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        build_state["last_cycle"] = 7
        original_resolver = MODULE._resolve_skill_script

        def fake_resolver(skill_name, script_name, required=True):
            if skill_name == "workstation-preparation":
                return None
            return original_resolver(skill_name, script_name, required=required)

        monkeypatch.setattr(MODULE, "_resolve_skill_script", fake_resolver)
        out = MODULE._manager_workstation_cycle(req, task_state=task_state, build_state=build_state)
        assert out.get("fatal") is True
        assert out.get("fatal_code") == "workstation_manager_missing_skill_fatal"
        validation_path = (
            root
            / "reports"
            / "optimus-prime"
            / "workstation-manager"
            / "attempt-7"
            / "WORKSTATION_VALIDATION.json"
        )
        assert validation_path.exists()
        payload = json.loads(validation_path.read_text(encoding="utf-8"))
        assert payload.get("ok") is False
        assert payload.get("status") == "blocked_fatal"
        assert (payload.get("error") or {}).get("code") == "workstation_manager_missing_skill_fatal"


def test_workstation_manager_rejects_prepare_command_non_bundled_script_path(monkeypatch: pytest.MonkeyPatch):
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
        req = MODULE.parse_request({"command": "/op-build", "repo_root": str(root)})
        planning = root / "reports" / "optimus-prime" / "planning"
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        MODULE._ensure_worker_registry_v2(root, build_state)
        task = next(item for item in task_state["tasks"] if item.get("task_id") == "TASK-001")
        task["status"] = "dev_working"
        task["owner_slot"] = "dev-1"
        registry_path = root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
        registry_payload = json.loads(registry_path.read_text(encoding="utf-8"))
        for row in registry_payload.get("workers", []):
            if row.get("slot") == "dev-1":
                row["active_task_id"] = "TASK-001"
                row["active_task"] = "TASK-001"
                row["lane_id"] = "phase-1/lane-a"
                row["previous_lane_id"] = "phase-1/lane-b"
                row["branch"] = "codex/dev-1/task-001"
                row["worktree_root"] = None
            elif row.get("role") in {"developer", "tester", "reviewer"}:
                row["lane_id"] = "phase-1/lane-z"
                row["previous_lane_id"] = "phase-1/lane-z"
                row["worktree_root"] = str(root / "prepared-worktrees" / str(row.get("slot") or "slot"))
        registry_path.write_text(json.dumps(registry_payload, indent=2) + "\n", encoding="utf-8")

        def fake_codex_exec(**kwargs):
            prompt = str(kwargs.get("prompt_text") or "")
            _write_manager_action_from_prompt(
                prompt,
                {
                    "schema_version": "1.0",
                    "slot": "dev-1",
                    "lane_id": "phase-1/lane-a",
                    "task_id": "TASK-001",
                    "branch_name": "codex/dev-1/task-001",
                    "worktree_name": "workstation-dev-1",
                    "prepare_command": "python3 /tmp/prepare_workstation.py --repo-root /tmp",
                    "prereq_policy": "copy_env_files",
                },
            )
            return 0

        monkeypatch.setattr(MODULE, "run_codex_exec", fake_codex_exec)
        monkeypatch.setattr(
            MODULE,
            "_run_manager_command",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("prepare command should not execute for non-bundled path")),
        )
        out = MODULE._manager_workstation_cycle(req, task_state=task_state, build_state=build_state)
        warning_codes = {item.get("code") for item in out.get("warnings", []) if isinstance(item, dict)}
        assert "workstation_action_invalid" in warning_codes
        assert "workstation_manager_retry_exhausted" in warning_codes
        assert task["status"] == "blocked"


def test_workstation_action_rejects_shared_worktree_name(monkeypatch: pytest.MonkeyPatch):
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
        req = MODULE.parse_request({"command": "/op-build", "repo_root": str(root)})
        planning = root / "reports" / "optimus-prime" / "planning"
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        MODULE._ensure_worker_registry_v2(root, build_state)
        task = next(item for item in task_state["tasks"] if item.get("task_id") == "TASK-001")
        task["status"] = "dev_working"
        task["owner_slot"] = "dev-1"
        registry_path = root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
        registry_payload = json.loads(registry_path.read_text(encoding="utf-8"))
        for row in registry_payload.get("workers", []):
            if row.get("slot") == "dev-1":
                row["active_task_id"] = "TASK-001"
                row["active_task"] = "TASK-001"
                row["lane_id"] = "phase-1/lane-a"
                row["previous_lane_id"] = "phase-1/lane-b"
                row["branch"] = "codex/dev-1/task-001"
                row["worktree_root"] = None
            elif row.get("role") in {"developer", "tester", "reviewer"}:
                row["lane_id"] = "phase-1/lane-z"
                row["previous_lane_id"] = "phase-1/lane-z"
                row["worktree_root"] = str(root / "prepared-worktrees" / str(row.get("slot") or "slot"))
        registry_path.write_text(json.dumps(registry_payload, indent=2) + "\n", encoding="utf-8")

        def fake_codex_exec(**kwargs):
            prompt = str(kwargs.get("prompt_text") or "")
            _write_manager_action_from_prompt(
                prompt,
                {
                    "schema_version": "1.0",
                    "slot": "dev-1",
                    "lane_id": "phase-1/lane-a",
                    "task_id": "TASK-001",
                    "branch_name": "codex/dev-1/task-001",
                    "worktree_name": "workstation-1",
                    "prepare_command": (
                        f"python3 {MODULE._resolve_skill_script('workstation-preparation', 'prepare_workstation.py')} "
                        f"--repo-root {root} --base-ref RAB-BASE --branch-name codex/dev-1/task-001 --slot-role developer "
                        "--output json --force-reset-existing --worktree-name workstation-1"
                    ),
                    "prereq_policy": "copy_env_files",
                },
            )
            return 0

        monkeypatch.setattr(MODULE, "run_codex_exec", fake_codex_exec)
        monkeypatch.setattr(
            MODULE,
            "_run_manager_command",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("prepare command should not execute")),
        )
        out = MODULE._manager_workstation_cycle(req, task_state=task_state, build_state=build_state)
        warning_codes = {item.get("code") for item in out.get("warnings", []) if isinstance(item, dict)}
        assert "workstation_action_invalid" in warning_codes
        assert "workstation_manager_retry_exhausted" in warning_codes


def test_workstation_manager_nonexistent_target_path_does_not_crash(monkeypatch: pytest.MonkeyPatch):
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
        req = MODULE.parse_request({"command": "/op-build", "repo_root": str(root)})
        planning = root / "reports" / "optimus-prime" / "planning"
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        MODULE._ensure_worker_registry_v2(root, build_state)
        task = next(item for item in task_state["tasks"] if item.get("task_id") == "TASK-001")
        task["status"] = "dev_working"
        task["owner_slot"] = "dev-1"
        registry_path = root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
        registry_payload = json.loads(registry_path.read_text(encoding="utf-8"))
        for row in registry_payload.get("workers", []):
            if row.get("slot") == "dev-1":
                row["active_task_id"] = "TASK-001"
                row["active_task"] = "TASK-001"
                row["lane_id"] = "phase-1/lane-a"
                row["previous_lane_id"] = "phase-1/lane-b"
                row["branch"] = "codex/dev-1/task-001"
                row["worktree_root"] = None
            elif row.get("role") in {"developer", "tester", "reviewer"}:
                row["lane_id"] = "phase-1/lane-z"
                row["previous_lane_id"] = "phase-1/lane-z"
                row["worktree_root"] = str(root / "prepared-worktrees" / str(row.get("slot") or "slot"))
        registry_path.write_text(json.dumps(registry_payload, indent=2) + "\n", encoding="utf-8")
        missing_target = root / "prepared-worktrees" / "missing-worktree"

        def fake_codex_exec(**kwargs):
            prompt = str(kwargs.get("prompt_text") or "")
            _write_manager_action_from_prompt(
                prompt,
                {
                    "schema_version": "1.0",
                    "slot": "dev-1",
                    "lane_id": "phase-1/lane-a",
                    "task_id": "TASK-001",
                    "branch_name": "codex/dev-1/task-001",
                    "worktree_name": "workstation-dev-1",
                    "prepare_command": (
                        f"python3 {MODULE._resolve_skill_script('workstation-preparation', 'prepare_workstation.py')} "
                        f"--repo-root {root} --base-ref RAB-BASE --branch-name codex/dev-1/task-001 --slot-role developer "
                        "--output json --force-reset-existing --worktree-name workstation-dev-1"
                    ),
                    "prereq_policy": "copy_env_files",
                },
            )
            return 0

        monkeypatch.setattr(MODULE, "run_codex_exec", fake_codex_exec)
        monkeypatch.setattr(
            MODULE,
            "_run_manager_command",
            lambda *_args, **_kwargs: {
                "ok": True,
                "code": None,
                "message": "",
                "stdout": json.dumps(
                    {
                        "ok": True,
                        "target_path": str(missing_target),
                        "branch_name_resolved": "codex/dev-1/task-001",
                    }
                ),
                "stderr": "",
                "exit_code": 0,
                "timed_out": False,
            },
        )
        monkeypatch.setattr(
            MODULE,
            "_git_text",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("_git_text should not be called for missing target_path")),
        )

        out = MODULE._manager_workstation_cycle(req, task_state=task_state, build_state=build_state)
        warning_codes = {item.get("code") for item in out.get("warnings", []) if isinstance(item, dict)}
        assert "workstation_manager_retry_exhausted" in warning_codes
        assert "workstation_execution_failed" in warning_codes
        assert task["status"] == "blocked"
        validation_path = (
            root
            / "reports"
            / "optimus-prime"
            / "workstation-manager"
            / "attempt-dev-1-1"
            / "WORKSTATION_VALIDATION.json"
        )
        payload = json.loads(validation_path.read_text(encoding="utf-8"))
        checks = payload.get("checks", [])
        by_id = {item.get("id"): item for item in checks if isinstance(item, dict)}
        assert by_id.get("prepare_target_path_exists", {}).get("passed") is False
        assert payload.get("branch_check_error")


def test_workstation_success_rejects_non_deterministic_target_path(monkeypatch: pytest.MonkeyPatch):
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
        req = MODULE.parse_request({"command": "/op-build", "repo_root": str(root)})
        planning = root / "reports" / "optimus-prime" / "planning"
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        MODULE._ensure_worker_registry_v2(root, build_state)
        task = next(item for item in task_state["tasks"] if item.get("task_id") == "TASK-001")
        task["status"] = "dev_working"
        task["owner_slot"] = "dev-1"
        registry_path = root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
        registry_payload = json.loads(registry_path.read_text(encoding="utf-8"))
        for row in registry_payload.get("workers", []):
            if row.get("slot") == "dev-1":
                row["active_task_id"] = "TASK-001"
                row["active_task"] = "TASK-001"
                row["lane_id"] = "phase-1/lane-a"
                row["previous_lane_id"] = "phase-1/lane-b"
                row["branch"] = "codex/dev-1/task-001"
                row["worktree_root"] = None
            elif row.get("role") in {"developer", "tester", "reviewer"}:
                row["lane_id"] = "phase-1/lane-z"
                row["previous_lane_id"] = "phase-1/lane-z"
                row["worktree_root"] = str(root / "prepared-worktrees" / str(row.get("slot") or "slot"))
        registry_path.write_text(json.dumps(registry_payload, indent=2) + "\n", encoding="utf-8")
        wrong_target = root / ".MyBoard-workstations" / "workstation-wrong-dev-1"
        wrong_target.mkdir(parents=True, exist_ok=True)
        expected_target = MODULE._expected_slot_worktree_path(root, "dev-1")
        assert isinstance(expected_target, Path)

        def fake_codex_exec(**kwargs):
            prompt = str(kwargs.get("prompt_text") or "")
            _write_manager_action_from_prompt(
                prompt,
                {
                    "schema_version": "1.0",
                    "slot": "dev-1",
                    "lane_id": "phase-1/lane-a",
                    "task_id": "TASK-001",
                    "branch_name": "codex/dev-1/task-001",
                    "worktree_name": "workstation-dev-1",
                    "prepare_command": (
                        f"python3 {MODULE._resolve_skill_script('workstation-preparation', 'prepare_workstation.py')} "
                        f"--repo-root {root} --base-ref RAB-BASE --branch-name codex/dev-1/task-001 --slot-role developer "
                        "--output json --force-reset-existing --worktree-name workstation-dev-1"
                    ),
                    "prereq_policy": "copy_env_files",
                },
            )
            return 0

        monkeypatch.setattr(MODULE, "run_codex_exec", fake_codex_exec)
        monkeypatch.setattr(
            MODULE,
            "_run_manager_command",
            lambda *_args, **_kwargs: {
                "ok": True,
                "code": None,
                "message": "",
                "stdout": json.dumps(
                    {
                        "ok": True,
                        "target_path": str(wrong_target),
                        "branch_name_resolved": "codex/dev-1/task-001",
                    }
                ),
                "stderr": "",
                "exit_code": 0,
                "timed_out": False,
            },
        )
        monkeypatch.setattr(
            MODULE,
            "_git_text",
            lambda repo_root, *args: "codex/dev-1/task-001" if str(repo_root) == str(wrong_target) else "abc123",
        )

        out = MODULE._manager_workstation_cycle(req, task_state=task_state, build_state=build_state)
        warning_codes = {item.get("code") for item in out.get("warnings", []) if isinstance(item, dict)}
        assert "workstation_manager_retry_exhausted" in warning_codes
        assert "workstation_execution_failed" in warning_codes
        assert task["status"] == "blocked"
        registry_after = json.loads(registry_path.read_text(encoding="utf-8"))
        slot_row = next(item for item in registry_after.get("workers", []) if isinstance(item, dict) and item.get("slot") == "dev-1")
        assert slot_row.get("worktree_root") in {None, ""}
        validation_path = (
            root
            / "reports"
            / "optimus-prime"
            / "workstation-manager"
            / "attempt-dev-1-1"
            / "WORKSTATION_VALIDATION.json"
        )
        payload = json.loads(validation_path.read_text(encoding="utf-8"))
        checks = payload.get("checks", [])
        by_id = {item.get("id"): item for item in checks if isinstance(item, dict)}
        assert by_id.get("prepare_target_path_expected", {}).get("passed") is False
        assert isinstance(payload.get("branch_check_error"), str)
        assert str(expected_target) in str(payload.get("branch_check_error"))


def test_workstation_manager_surfaces_prepare_script_error_message(monkeypatch: pytest.MonkeyPatch):
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
        req = MODULE.parse_request({"command": "/op-build", "repo_root": str(root)})
        planning = root / "reports" / "optimus-prime" / "planning"
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        MODULE._ensure_worker_registry_v2(root, build_state)
        task = next(item for item in task_state["tasks"] if item.get("task_id") == "TASK-001")
        task["status"] = "dev_working"
        task["owner_slot"] = "dev-1"
        task["lane_id"] = "phase-1/lane-a"
        registry_path = root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
        registry_payload = json.loads(registry_path.read_text(encoding="utf-8"))
        for row in registry_payload.get("workers", []):
            if row.get("slot") == "dev-1":
                row["active_task_id"] = "TASK-001"
                row["active_task"] = "TASK-001"
                row["lane_id"] = "phase-1/lane-a"
                row["previous_lane_id"] = "phase-1/lane-b"
                row["branch"] = "codex/dev-1/task-001"
                row["worktree_root"] = None
            elif row.get("role") in {"developer", "tester", "reviewer"}:
                row["lane_id"] = "phase-1/lane-z"
                row["previous_lane_id"] = "phase-1/lane-z"
                row["worktree_root"] = str(root / "prepared-worktrees" / str(row.get("slot") or "slot"))
        registry_path.write_text(json.dumps(registry_payload, indent=2) + "\n", encoding="utf-8")

        def fake_codex_exec(**kwargs):
            prompt = str(kwargs.get("prompt_text") or "")
            branch_line = next((line for line in prompt.splitlines() if line.startswith("Branch name: ")), "")
            prompt_branch = branch_line.split("Branch name: ", 1)[1].strip() if branch_line else "codex/dev-1/bootstrap"
            _write_manager_action_from_prompt(
                prompt,
                {
                    "schema_version": "1.0",
                    "slot": "dev-1",
                    "lane_id": "phase-1/lane-a",
                    "task_id": "TASK-001",
                    "branch_name": prompt_branch,
                    "worktree_name": "workstation-dev-1",
                    "prepare_command": (
                        f"python3 {MODULE._resolve_skill_script('workstation-preparation', 'prepare_workstation.py')} "
                        f"--repo-root {root} --base-ref RAB-BASE --branch-name {prompt_branch} --slot-role developer --output json "
                        "--force-reset-existing --worktree-name workstation-dev-1"
                    ),
                    "prereq_policy": "copy_env_files",
                },
            )
            return 0

        monkeypatch.setattr(MODULE, "run_codex_exec", fake_codex_exec)
        monkeypatch.setattr(
            MODULE,
            "_run_manager_command",
            lambda *_args, **_kwargs: {
                "ok": False,
                "code": None,
                "message": "",
                "stdout": json.dumps(
                    {
                        "ok": False,
                        "error": "branch 'RAB-BASE' is checked out in another worktree; set --branch-in-use-fallback-suffix to auto-resolve",
                        "target_path": str(root / ".MyBoard-workstations" / "workstation-dev-1"),
                    }
                ),
                "stderr": "",
                "exit_code": 2,
                "timed_out": False,
            },
        )
        out = MODULE._manager_workstation_cycle(req, task_state=task_state, build_state=build_state)
        warning_rows = [item for item in out.get("warnings", []) if isinstance(item, dict)]
        assert any(
            item.get("code") == "workstation_execution_failed"
            and "checked out in another worktree" in str(item.get("message") or "")
            for item in warning_rows
        )
        validation_path = (
            root
            / "reports"
            / "optimus-prime"
            / "workstation-manager"
            / "attempt-dev-1-1"
            / "WORKSTATION_VALIDATION.json"
        )
        payload = json.loads(validation_path.read_text(encoding="utf-8"))
        assert "prepare_workstation failed:" in str(payload.get("branch_check_error") or "")
        checks = {item.get("id"): item.get("passed") for item in payload.get("checks", []) if isinstance(item, dict)}
        assert checks.get("prepare_payload_ok") is False


def test_workstation_manager_skips_prepare_for_same_lane_in_progress_slot(
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
        req = MODULE.parse_request({"command": "/op-build", "repo_root": str(root)})
        planning = root / "reports" / "optimus-prime" / "planning"
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        MODULE._ensure_worker_registry_v2(root, build_state)
        registry_path = root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
        task = next(item for item in task_state["tasks"] if item.get("task_id") == "TASK-001")
        task["status"] = "dev_working"
        task["owner_slot"] = "dev-1"
        task["lane_id"] = "phase-1/lane-a"
        stable_worktree = MODULE._expected_slot_worktree_path(root, "dev-1")
        assert isinstance(stable_worktree, Path)
        stable_worktree.mkdir(parents=True, exist_ok=True)
        registry_payload = json.loads(registry_path.read_text(encoding="utf-8"))
        for row in registry_payload.get("workers", []):
            if row.get("slot") == "dev-1":
                row["active_task_id"] = "TASK-001"
                row["active_task"] = "TASK-001"
                row["lane_id"] = "phase-1/lane-a"
                row["previous_lane_id"] = "phase-1/lane-a"
                row["branch"] = "codex/dev-1/task-001"
                row["worktree_root"] = str(stable_worktree)
            elif row.get("role") in {"developer", "tester", "reviewer"}:
                row["lane_id"] = "phase-1/lane-z"
                row["previous_lane_id"] = "phase-1/lane-z"
                row["worktree_root"] = str(root / "prepared-worktrees" / str(row.get("slot") or "slot"))
                row["branch"] = "RAB-BASE"
        registry_path.write_text(json.dumps(registry_payload, indent=2) + "\n", encoding="utf-8")
        monkeypatch.setattr(
            MODULE,
            "run_codex_exec",
            lambda **_kwargs: (_ for _ in ()).throw(AssertionError("LLM workstation prep should not run")),
        )

        out = MODULE._manager_workstation_cycle(req, task_state=task_state, build_state=build_state)
        warning_codes = {item.get("code") for item in out.get("warnings", []) if isinstance(item, dict)}
        assert "workstation_skip_same_lane_in_progress" in warning_codes
        registry_after = json.loads(registry_path.read_text(encoding="utf-8"))
        slot_row = next(item for item in registry_after.get("workers", []) if isinstance(item, dict) and item.get("slot") == "dev-1")
        assert slot_row.get("worktree_root") == str(stable_worktree)
        assert slot_row.get("branch") == "codex/dev-1/task-001"


def test_workstation_same_lane_skip_requires_slot_branch_prefix(monkeypatch: pytest.MonkeyPatch):
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
        req = MODULE.parse_request({"command": "/op-build", "repo_root": str(root)})
        planning = root / "reports" / "optimus-prime" / "planning"
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        MODULE._ensure_worker_registry_v2(root, build_state)
        registry_path = root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
        task = next(item for item in task_state["tasks"] if item.get("task_id") == "TASK-001")
        task["status"] = "dev_working"
        task["owner_slot"] = "dev-1"
        task["lane_id"] = "phase-1/lane-a"
        stable_worktree = MODULE._expected_slot_worktree_path(root, "dev-1")
        assert isinstance(stable_worktree, Path)
        stable_worktree.mkdir(parents=True, exist_ok=True)
        registry_payload = json.loads(registry_path.read_text(encoding="utf-8"))
        for row in registry_payload.get("workers", []):
            if row.get("slot") == "dev-1":
                row["active_task_id"] = "TASK-001"
                row["active_task"] = "TASK-001"
                row["lane_id"] = "phase-1/lane-a"
                row["previous_lane_id"] = "phase-1/lane-a"
                row["branch"] = "feature/random"
                row["worktree_root"] = str(stable_worktree)
        registry_path.write_text(json.dumps(registry_payload, indent=2) + "\n", encoding="utf-8")
        codex_calls = {"count": 0}

        def fake_codex_exec(**kwargs):
            codex_calls["count"] += 1
            prompt = str(kwargs.get("prompt_text") or "")
            _write_manager_action_from_prompt(
                prompt,
                {
                    "schema_version": "1.0",
                    "slot": "dev-1",
                    "lane_id": "phase-1/lane-a",
                    "task_id": "TASK-001",
                    "branch_name": "feature/random",
                    "worktree_name": "workstation-dev-1",
                    "prepare_command": (
                        f"python3 {MODULE._resolve_skill_script('workstation-preparation', 'prepare_workstation.py')} "
                        f"--repo-root {root} --base-ref RAB-BASE --branch-name feature/random --slot-role developer "
                        "--output json --force-reset-existing --worktree-name workstation-dev-1"
                    ),
                    "prereq_policy": "copy_env_files",
                },
            )
            return 0

        monkeypatch.setattr(MODULE, "run_codex_exec", fake_codex_exec)
        monkeypatch.setattr(
            MODULE,
            "_run_manager_command",
            lambda *_args, **_kwargs: {
                "ok": True,
                "code": None,
                "message": "",
                "stdout": json.dumps(
                    {
                        "ok": True,
                        "target_path": str(stable_worktree),
                        "branch_name_resolved": "feature/random",
                    }
                ),
                "stderr": "",
                "exit_code": 0,
                "timed_out": False,
            },
        )
        monkeypatch.setattr(
            MODULE,
            "_git_text",
            lambda repo_root, *args: "feature/random" if str(repo_root) == str(stable_worktree) else "abc123",
        )
        out = MODULE._manager_workstation_cycle(req, task_state=task_state, build_state=build_state)
        warning_codes = {item.get("code") for item in out.get("warnings", []) if isinstance(item, dict)}
        assert codex_calls["count"] >= 1
        assert "workstation_skip_same_lane_in_progress" not in warning_codes
        assert "workstation_manager_retry_exhausted" not in warning_codes


def test_workstation_same_lane_skip_requires_exact_deterministic_path(monkeypatch: pytest.MonkeyPatch):
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
        req = MODULE.parse_request({"command": "/op-build", "repo_root": str(root)})
        planning = root / "reports" / "optimus-prime" / "planning"
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        MODULE._ensure_worker_registry_v2(root, build_state)
        registry_path = root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
        task = next(item for item in task_state["tasks"] if item.get("task_id") == "TASK-001")
        task["status"] = "dev_working"
        task["owner_slot"] = "dev-1"
        task["lane_id"] = "phase-1/lane-a"
        wrong_worktree = root / ".MyBoard-workstations" / "workstation-dev-x"
        wrong_worktree.mkdir(parents=True, exist_ok=True)
        expected_worktree = MODULE._expected_slot_worktree_path(root, "dev-1")
        assert isinstance(expected_worktree, Path)
        expected_worktree.mkdir(parents=True, exist_ok=True)
        registry_payload = json.loads(registry_path.read_text(encoding="utf-8"))
        for row in registry_payload.get("workers", []):
            if row.get("slot") == "dev-1":
                row["active_task_id"] = "TASK-001"
                row["active_task"] = "TASK-001"
                row["lane_id"] = "phase-1/lane-a"
                row["previous_lane_id"] = "phase-1/lane-a"
                row["branch"] = "codex/dev-1/task-001"
                row["worktree_root"] = str(wrong_worktree)
        registry_path.write_text(json.dumps(registry_payload, indent=2) + "\n", encoding="utf-8")
        codex_calls = {"count": 0}

        def fake_codex_exec(**kwargs):
            codex_calls["count"] += 1
            prompt = str(kwargs.get("prompt_text") or "")
            _write_manager_action_from_prompt(
                prompt,
                {
                    "schema_version": "1.0",
                    "slot": "dev-1",
                    "lane_id": "phase-1/lane-a",
                    "task_id": "TASK-001",
                    "branch_name": "codex/dev-1/task-001",
                    "worktree_name": "workstation-dev-1",
                    "prepare_command": (
                        f"python3 {MODULE._resolve_skill_script('workstation-preparation', 'prepare_workstation.py')} "
                        f"--repo-root {root} --base-ref RAB-BASE --branch-name codex/dev-1/task-001 --slot-role developer "
                        "--output json --force-reset-existing --worktree-name workstation-dev-1"
                    ),
                    "prereq_policy": "copy_env_files",
                },
            )
            return 0

        monkeypatch.setattr(MODULE, "run_codex_exec", fake_codex_exec)
        monkeypatch.setattr(
            MODULE,
            "_run_manager_command",
            lambda *_args, **_kwargs: {
                "ok": True,
                "code": None,
                "message": "",
                "stdout": json.dumps(
                    {
                        "ok": True,
                        "target_path": str(expected_worktree),
                        "branch_name_resolved": "codex/dev-1/task-001",
                    }
                ),
                "stderr": "",
                "exit_code": 0,
                "timed_out": False,
            },
        )
        monkeypatch.setattr(
            MODULE,
            "_git_text",
            lambda repo_root, *args: "codex/dev-1/task-001" if str(repo_root) == str(expected_worktree) else "abc123",
        )
        out = MODULE._manager_workstation_cycle(req, task_state=task_state, build_state=build_state)
        warning_codes = {item.get("code") for item in out.get("warnings", []) if isinstance(item, dict)}
        assert codex_calls["count"] >= 1
        assert "workstation_skip_same_lane_in_progress" not in warning_codes
        assert "workstation_manager_retry_exhausted" not in warning_codes


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
        MODULE._ensure_worker_registry_v2(root, build_state)
        registry_after = json.loads(registry_path.read_text(encoding="utf-8"))
        slot_row = next(item for item in registry_after.get("workers", []) if isinstance(item, dict) and item.get("slot") == "dev-1")
        assert slot_row.get("branch") == "codex/dev-1/bootstrap"


def test_manager_command_disallowed_fails_attempt_deterministically(monkeypatch: pytest.MonkeyPatch):
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
        req = MODULE.parse_request({"command": "/op-build", "repo_root": str(root)})
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        task = next(item for item in task_state["tasks"] if item.get("task_id") == "TASK-001")
        task["status"] = "review_done"
        task["active_branch"] = "codex/dev-1/task-001"

        def fake_codex_exec(**kwargs):
            prompt = str(kwargs.get("prompt_text") or "")
            _write_manager_action_from_prompt(
                prompt,
                {
                    "schema_version": "1.0",
                    "task_id": "TASK-001",
                    "attempt": 1,
                    "target_branch": "RAB-BASE",
                    "source_branch": "codex/dev-1/task-001",
                    "merge_strategy": "no_ff",
                    "commands": ["sudo whoami"],
                    "verification_commands": ["python3 -m pytest"],
                },
            )
            return 0

        monkeypatch.setattr(MODULE, "run_codex_exec", fake_codex_exec)
        original_run_manager_command = MODULE._run_manager_command

        def fake_run_manager_command(command_text, **kwargs):
            if str(command_text).strip().startswith("git checkout RAB-BASE"):
                return {
                    "ok": True,
                    "code": None,
                    "message": "",
                    "stdout": "",
                    "stderr": "",
                    "exit_code": 0,
                    "timed_out": False,
                }
            return original_run_manager_command(command_text, **kwargs)

        monkeypatch.setattr(MODULE, "_run_manager_command", fake_run_manager_command)
        warnings = MODULE._manager_branch_merge_cycle(
            req,
            plan_packets=plan_packets,
            task_state=task_state,
            build_state=build_state,
        )
        warning_codes = {item.get("code") for item in warnings if isinstance(item, dict)}
        assert "manager_command_disallowed" in warning_codes
        assert "merge_manager_retry_exhausted" in warning_codes


def test_manager_command_timeout_fails_attempt_deterministically(monkeypatch: pytest.MonkeyPatch):
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
        req = MODULE.parse_request({"command": "/op-build", "repo_root": str(root)})
        planning = root / "reports" / "optimus-prime" / "planning"
        plan_packets = json.loads((planning / "PLAN_PACKETS.json").read_text(encoding="utf-8"))
        task_state = json.loads((planning / "TASK_EXECUTION_STATE.json").read_text(encoding="utf-8"))
        build_state = MODULE._load_build_state(planning / "BUILD_STATE.json")
        task = next(item for item in task_state["tasks"] if item.get("task_id") == "TASK-001")
        task["status"] = "review_done"
        task["active_branch"] = "codex/dev-1/task-001"

        def fake_codex_exec(**kwargs):
            prompt = str(kwargs.get("prompt_text") or "")
            _write_manager_action_from_prompt(
                prompt,
                {
                    "schema_version": "1.0",
                    "task_id": "TASK-001",
                    "attempt": 1,
                    "target_branch": "RAB-BASE",
                    "source_branch": "codex/dev-1/task-001",
                    "merge_strategy": "no_ff",
                    "commands": ["git checkout RAB-BASE"],
                    "verification_commands": ["python3 -m pytest"],
                },
            )
            return 0

        monkeypatch.setattr(MODULE, "run_codex_exec", fake_codex_exec)
        monkeypatch.setattr(
            MODULE,
            "_run_manager_command",
            lambda *args, **kwargs: {
                "ok": False,
                "code": "manager_command_timeout",
                "message": "command timed out after 1s",
                "stdout": "",
                "stderr": "",
                "exit_code": None,
                "timed_out": True,
            },
        )
        warnings = MODULE._manager_branch_merge_cycle(
            req,
            plan_packets=plan_packets,
            task_state=task_state,
            build_state=build_state,
        )
        warning_codes = {item.get("code") for item in warnings if isinstance(item, dict)}
        assert "manager_command_timeout" in warning_codes
        assert "merge_manager_retry_exhausted" in warning_codes


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
            return {"ok": True, "dispatch": {"dispatch_mode_used": "exec", "dispatch_thread_id": "thread-abc"}}

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


def test_manager_dispatcher_cycle_orders_nonforced_before_forced(monkeypatch: pytest.MonkeyPatch):
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
        for row in task_state.get("tasks", []):
            if row.get("task_id") in {"TASK-001", "TASK-002"}:
                row["status"] = "pending"

        monkeypatch.setattr(
            MODULE,
            "_load_work_dispatch_plan_assignments",
            lambda *_args, **_kwargs: (
                [
                    {
                        "task_id": "TASK-002",
                        "lane_id": "phase-1/lane-b",
                        "phase_id": "phase-1",
                        "next_stage": "dev",
                        "next_role": "developer",
                        "slot": "dev-2",
                        "dispatch_policy": "resume_if_same_lane",
                    }
                ],
                [],
                True,
            ),
        )
        captured: list[dict[str, object]] = []

        def fake_dispatch_next(_req, _plan_packets, _task_state, _build_state, _active_phase_id, authoritative_assignments):
            captured.extend([dict(row) for row in authoritative_assignments or []])
            return {"ok": True, "status": "noop", "reason": "dispatch_plan_no_assignments", "warnings": [], "assignment_observations": []}

        monkeypatch.setattr(MODULE, "_dispatch_next_task", fake_dispatch_next)

        MODULE._manager_dispatcher_cycle(
            req,
            plan_packets=plan_packets,
            task_state=task_state,
            build_state=build_state,
            active_phase_id="phase-1",
            forced_assignments=[
                {
                    "task_id": "TASK-001",
                    "lane_id": "phase-1/lane-a",
                    "phase_id": "phase-1",
                    "next_stage": "dev",
                    "next_role": "developer",
                    "slot": "dev-1",
                    "dispatch_policy": "resume_if_same_lane",
                }
            ],
        )
        assert captured
        assert captured[0]["task_id"] == "TASK-002"
        assert captured[0].get("_forced") is False
        assert captured[1]["task_id"] == "TASK-001"
        assert captured[1].get("_forced") is True


def test_dispatch_observations_exposed_in_build_response_data(monkeypatch: pytest.MonkeyPatch):
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
                        }
                    ],
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
        monkeypatch.setattr(
            MODULE,
            "_dispatch_task_packet",
            lambda *_args, **_kwargs: {"ok": True, "dispatch": {"dispatch_mode_used": "exec", "dispatch_thread_id": "thread-1"}},
        )
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
        out = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 1,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        data = out.get("data") if isinstance(out.get("data"), dict) else {}
        observations = data.get("assignment_observations")
        assert isinstance(observations, list)
        assert observations
        assert all(MODULE._as_str(item.get("reason_code")) for item in observations if isinstance(item, dict))


def test_build_prints_watchdog_findings_each_cycle(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
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
        planning = root / "reports" / "optimus-prime" / "planning"
        (planning / "WORK_DISPATCH_PLAN.json").write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "updated_at": "2026-01-01T00:00:00Z",
                    "active_phase_id": "phase-1",
                    "assignments": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        events_path = root / "reports" / "optimus-prime" / "controller" / "EVENTS.jsonl"
        events_path.parent.mkdir(parents=True, exist_ok=True)
        events_path.write_text("", encoding="utf-8")
        monkeypatch.setattr(MODULE.sys.stdout, "isatty", lambda: True)
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
        monkeypatch.setattr(
            MODULE,
            "_manager_branch_merge_cycle",
            lambda *_args, **_kwargs: [],
        )
        monkeypatch.setattr(
            MODULE,
            "_manager_workstation_cycle",
            lambda *_args, **_kwargs: {"warnings": [], "fatal": False, "fatal_code": None, "fatal_message": None},
        )
        out = run_payload(
            {
                "command": "/op-build",
                "repo_root": str(root),
                "max_build_cycles": 2,
                "dry_run": True,
                "sleep_minutes": 0,
            }
        )
        assert out.get("status") == "running_needs_resume"
        logs = capsys.readouterr().out
        assert "cycle 1: watchdog findings:" in logs
        assert "cycle 2: watchdog findings:" in logs
        assert "reasons=initial_baseline" in logs
        assert "reasons=no_task_state_delta" in logs
