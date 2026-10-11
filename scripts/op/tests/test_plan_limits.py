"""Planning cap contract, including persisted build/resume enforcement."""

import json
import sys
from pathlib import Path

import pytest

from scripts.op import op_core as core
from scripts.op import opctl as cli
from planner.llm_planner import canonical_checksum
from planner.validate_plan_bundle import _validate_plan_packets, validate_bundle_contract


@pytest.mark.parametrize("value", [0, 401, -1, True, 2.5, "nope", "1.5"])
def test_invalid_limits_rejected_at_request_boundary(tmp_path, value):
    with pytest.raises(core.OpError, match="integer between 1 and 400"):
        core.parse_request({"command": "/op-plan", "repo_root": str(tmp_path), "max_plan_tasks": value})


@pytest.mark.parametrize("value", [None, 1, 400, "12"])
def test_limit_is_optional_and_boundary_values_work(tmp_path, value):
    req = core.parse_request({"command": "/op-plan", "repo_root": str(tmp_path), "max_plan_tasks": value})
    assert req.max_plan_tasks == (None if value is None else int(value))


def test_cli_transmits_explicit_cap(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["opctl.py", "--command", "/op-plan", "--repo-root", str(tmp_path), "--max-plan-tasks", "1"])
    assert cli.merge_payload(cli.parse_args())["max_plan_tasks"] == 1


def test_bundle_validator_rejects_excess_without_truncating(tmp_path):
    root = core.PLANNER_EXAMPLE_ROOT_PATH
    rows = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        kind = "json" if path.suffix == ".json" else "text"
        content = json.loads(path.read_text()) if kind == "json" else path.read_text()
        rows.append({"artifact_path": path.relative_to(root).as_posix(), "content_type": kind, "content": content, "checksum_sha256": canonical_checksum(kind, content)})
    path = tmp_path / "bundle.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in rows))
    original = path.read_bytes()
    bundle, errors = validate_bundle_contract(path, root)
    assert errors == []
    count = len(bundle["PLAN_PACKETS.json"].content["tasks"])
    accepted, errors = validate_bundle_contract(path, root, max_plan_tasks=count)
    assert accepted is not None and errors == []
    rejected, errors = validate_bundle_contract(path, root, max_plan_tasks=1)
    assert rejected is None
    assert any(row["code"] == "planner_task_limit_exceeded" for row in errors)
    assert path.read_bytes() == original


def test_single_task_schema_has_no_hidden_400_minimum():
    plan = json.loads((core.PLANNER_EXAMPLE_ROOT_PATH / "PLAN_PACKETS.json").read_text())
    plan["tasks"] = plan["tasks"][:1]
    plan["phases"] = plan["phases"][:1]
    plan["requirements"] = plan["requirements"][:1]
    plan["lane_base_branches"] = {plan["tasks"][0]["lane_id"]: "lane-phase-1-a"}
    errors = []
    _validate_plan_packets(plan, errors)
    assert errors == []


def test_cap_injected_without_editing_template(tmp_path):
    template = core.PLANNER_PROMPT_TEMPLATE_PATH.read_bytes()
    req = core.parse_request({"command": "/op-plan", "repo_root": str(tmp_path), "max_plan_tasks": 7})
    prompt = core._planner_prompt_text(req=req, bundle_path=tmp_path / "bundle.jsonl", mission_source={}, scope_source={}, prior_errors=[])
    assert "between 1 and 7 total tasks" in prompt
    assert "--max-plan-tasks 7" in prompt
    assert "maximum, not a target" in prompt
    assert core.PLANNER_PROMPT_TEMPLATE_PATH.read_bytes() == template


@pytest.mark.parametrize("command", ["/op-simple-build", "/op-resume"])
def test_saved_cap_blocks_build_and_resume_before_dispatch(tmp_path, command):
    planning = tmp_path / core.PLANNING_REL
    planning.mkdir(parents=True)
    (planning / "STATE.json").write_text(json.dumps({"max_plan_tasks": 1}))
    (planning / "PLAN_PACKETS.json").write_text(json.dumps({"tasks": [{"task_id": "one"}, {"task_id": "two"}]}))
    req = core.parse_request({"command": command, "repo_root": str(tmp_path)})
    with pytest.raises(core.OpError) as caught:
        core.execute_request(req)
    assert caught.value.code == "planner_task_limit_exceeded"
    assert not (tmp_path / ".op-simple").exists()


def test_omitted_limit_preserves_existing_large_plans(tmp_path):
    planning = tmp_path / core.PLANNING_REL
    planning.mkdir(parents=True)
    (planning / "STATE.json").write_text("{}")
    (planning / "PLAN_PACKETS.json").write_text(json.dumps({"tasks": [{}] * 450}))
    req = core.parse_request({"command": "/op-build", "repo_root": str(tmp_path)})
    core._enforce_existing_plan_task_limit(req)
