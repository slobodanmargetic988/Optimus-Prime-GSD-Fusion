#!/usr/bin/env python3
"""Validate planner JSONL bundle contract (strict)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
OP_ROOT = SCRIPT_DIR.parent
if str(OP_ROOT) not in sys.path:
    sys.path.insert(0, str(OP_ROOT))

from planner.llm_planner import BundleArtifact, PlannerError, parse_bundle_jsonl

REQUIRED_STATIC = {
    "PLAN_PACKETS.json",
    "PLAN_CHECK.json",
    "TASK_EXECUTION_STATE.json",
    "TEST_CONTRACT.md",
    "PLAYWRIGHT_UAT_MATRIX.md",
    "VERIFICATION.md",
    "UAT.md",
    "STATE.json",
    "STATE.md",
}

OPTIONAL_STATIC = {
    "GAPS.json",
    "GAP_CLOSURE_PLAN_PACKETS.json",
}

TEXT_HEADINGS = {
    "TEST_CONTRACT.md": "# TEST CONTRACT",
    "PLAYWRIGHT_UAT_MATRIX.md": "# PLAYWRIGHT UAT MATRIX",
    "VERIFICATION.md": "# VERIFICATION",
    "UAT.md": "# UAT",
    "STATE.md": "# STATE",
}

TASK_STATUS = {
    "pending",
    "queued",
    "dev_working",
    "dev_in_progress",
    "dev_done",
    "testing",
    "test_in_progress",
    "tests_done",
    "test_done",
    "reviewing",
    "review_in_progress",
    "review_done",
    "blocked",
}

EVIDENCE_RESULT = {"pass", "fail", "blocked"}
EVIDENCE_STATUS = {"queued", "in_progress", "done", "blocked"}
VERIFICATION_MODES = {
    "tdd_red",
    "implementation_green",
    "hardening",
    "lane_test",
    "lane_review",
    "deep_review",
    "merge_validation",
}
VERIFICATION_EXPECTATIONS = {"expect_fail", "expect_pass"}
EVIDENCE_FAILURE_CLASS = {"expected_red", "infra", "unexpected", "none"}
TASK_KINDS = {
    "implementation",
    "lane_test",
    "test_fix",
    "lane_review",
    "review_fix",
    "deep_review",
    "deep_fix",
    "merge",
}


def _as_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _err(errors: list[dict[str, object]], code: str, message: str, **details: object) -> None:
    row: dict[str, object] = {"code": code, "message": message}
    row.update(details)
    errors.append(row)


def _is_iso8601(text: object) -> bool:
    if not isinstance(text, str) or not text.strip():
        return False
    normalized = text.replace("Z", "+00:00")
    try:
        datetime.fromisoformat(normalized)
    except ValueError:
        return False
    return True


def _strict_keys(
    obj: dict[str, Any],
    *,
    label: str,
    required: set[str],
    optional: set[str],
    errors: list[dict[str, object]],
) -> None:
    keys = set(obj.keys())
    missing = sorted(required - keys)
    if missing:
        _err(errors, "planner_bundle_schema_error", f"{label} missing required keys", missing=missing)
    allowed = required | optional
    extra = sorted(keys - allowed)
    if extra:
        _err(errors, "planner_bundle_schema_error", f"{label} has unexpected keys", extra=extra)


def _require_nonempty_str(value: object, *, label: str, errors: list[dict[str, object]]) -> str | None:
    if not isinstance(value, str):
        _err(errors, "planner_bundle_schema_error", f"{label} must be string")
        return None
    text = value.strip()
    if not text:
        _err(errors, "planner_bundle_schema_error", f"{label} must be non-empty string")
        return None
    return text


def _require_bool(value: object, *, label: str, errors: list[dict[str, object]]) -> bool | None:
    if not isinstance(value, bool):
        _err(errors, "planner_bundle_schema_error", f"{label} must be boolean")
        return None
    return value


def _require_str_list(
    value: object,
    *,
    label: str,
    errors: list[dict[str, object]],
    min_items: int = 0,
) -> list[str]:
    out: list[str] = []
    if not isinstance(value, list):
        _err(errors, "planner_bundle_schema_error", f"{label} must be list")
        return out
    for idx, item in enumerate(value):
        if not isinstance(item, str):
            _err(errors, "planner_bundle_schema_error", f"{label}[{idx}] must be string")
            continue
        text = item.strip()
        if not text:
            _err(errors, "planner_bundle_schema_error", f"{label}[{idx}] must be non-empty string")
            continue
        out.append(text)
    if len(out) < min_items:
        _err(errors, "planner_bundle_schema_error", f"{label} must contain at least {min_items} item(s)")
    return out


def _require_object(value: object, *, label: str, errors: list[dict[str, object]]) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        _err(errors, "planner_bundle_schema_error", f"{label} must be object JSON")
        return None
    return value


def _require_str_or_none(value: object, *, label: str, errors: list[dict[str, object]]) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        _err(errors, "planner_bundle_schema_error", f"{label} must be string|null")
        return None
    return value.strip() or None


def _allowed_modes_for_task_kind(task_kind: str) -> set[str]:
    if task_kind == "implementation":
        return {"tdd_red", "implementation_green", "hardening"}
    if task_kind in {"test_fix", "review_fix", "deep_fix"}:
        return {"implementation_green", "hardening"}
    if task_kind == "lane_test":
        return {"lane_test"}
    if task_kind == "lane_review":
        return {"lane_review"}
    if task_kind == "deep_review":
        return {"deep_review"}
    if task_kind == "merge":
        return {"merge_validation"}
    return {"implementation_green"}


def _validate_verification_contract(
    value: object,
    *,
    task_kind: str,
    label: str,
    errors: list[dict[str, object]],
) -> None:
    contract = _require_object(value, label=label, errors=errors)
    if contract is None:
        return
    _strict_keys(
        contract,
        label=label,
        required={
            "mode",
            "expected_failure_reason_codes",
            "infra_failure_reason_codes",
        },
        optional=set(),
        errors=errors,
    )
    mode = _require_nonempty_str(contract.get("mode"), label=f"{label}.mode", errors=errors)
    allowed_modes = _allowed_modes_for_task_kind(task_kind)
    if mode and mode not in allowed_modes:
        _err(errors, "planner_bundle_schema_error", f"{label}.mode must be one of {'|'.join(sorted(allowed_modes))}")
    _require_str_list(
        contract.get("expected_failure_reason_codes"),
        label=f"{label}.expected_failure_reason_codes",
        errors=errors,
        min_items=1,
    )
    _require_str_list(
        contract.get("infra_failure_reason_codes"),
        label=f"{label}.infra_failure_reason_codes",
        errors=errors,
        min_items=1,
    )


def _validate_plan_packets(payload: dict[str, Any], errors: list[dict[str, object]]) -> tuple[str | None, list[str], list[str], set[str]]:
    _strict_keys(
        payload,
        label="PLAN_PACKETS.json",
        required={"schema_version", "generated_at", "plan_id", "phases", "requirements", "tasks", "lane_base_branches"},
        optional={"phase", "depends_on", "must_haves", "verify_commands"},
        errors=errors,
    )

    _require_nonempty_str(payload.get("schema_version"), label="PLAN_PACKETS.schema_version", errors=errors)
    _require_nonempty_str(payload.get("generated_at"), label="PLAN_PACKETS.generated_at", errors=errors)
    if not _is_iso8601(payload.get("generated_at")):
        _err(errors, "planner_bundle_schema_error", "PLAN_PACKETS.generated_at must be ISO-8601")
    plan_id = _require_nonempty_str(payload.get("plan_id"), label="PLAN_PACKETS.plan_id", errors=errors)

    phases_raw = payload.get("phases")
    tasks_raw = payload.get("tasks")
    reqs_raw = payload.get("requirements")
    lane_base_raw = payload.get("lane_base_branches")
    lane_base_branches: dict[str, str] = {}
    if not isinstance(lane_base_raw, dict):
        _err(errors, "planner_bundle_schema_error", "PLAN_PACKETS.lane_base_branches must be object map")
    else:
        for raw_lane_id, raw_branch_name in lane_base_raw.items():
            lane_id = str(raw_lane_id or "").strip()
            branch_name = str(raw_branch_name or "").strip()
            if not lane_id:
                _err(
                    errors,
                    "planner_bundle_schema_error",
                    "PLAN_PACKETS.lane_base_branches contains empty lane_id key",
                )
                continue
            if not branch_name:
                _err(
                    errors,
                    "planner_bundle_schema_error",
                    "PLAN_PACKETS.lane_base_branches contains empty branch name",
                    lane_id=lane_id,
                )
                continue
            lane_base_branches[lane_id] = branch_name

    phase_ids: list[str] = []
    phase_deps: dict[str, list[str]] = {}
    phase_task_ids: dict[str, list[str]] = {}
    if isinstance(phases_raw, list) and phases_raw:
        for idx, row in enumerate(phases_raw):
            if not isinstance(row, dict):
                _err(errors, "planner_bundle_schema_error", f"PLAN_PACKETS.phases[{idx}] must be object")
                continue
            _strict_keys(
                row,
                label=f"PLAN_PACKETS.phases[{idx}]",
                required={"phase_id", "task_ids", "depends_on_phase_ids", "entry_criteria", "exit_criteria"},
                optional=set(),
                errors=errors,
            )
            phase_id = _require_nonempty_str(row.get("phase_id"), label=f"PLAN_PACKETS.phases[{idx}].phase_id", errors=errors)
            if phase_id:
                if phase_id in phase_ids:
                    _err(errors, "planner_bundle_schema_error", "PLAN_PACKETS.phases contains duplicate phase_id", phase_id=phase_id)
                phase_ids.append(phase_id)
            task_ids_in_phase = _require_str_list(row.get("task_ids"), label=f"PLAN_PACKETS.phases[{idx}].task_ids", errors=errors)
            dep_ids = _require_str_list(row.get("depends_on_phase_ids"), label=f"PLAN_PACKETS.phases[{idx}].depends_on_phase_ids", errors=errors)
            if phase_id:
                phase_task_ids[phase_id] = task_ids_in_phase
                phase_deps[phase_id] = dep_ids
            _require_str_list(row.get("entry_criteria"), label=f"PLAN_PACKETS.phases[{idx}].entry_criteria", errors=errors, min_items=1)
            _require_str_list(row.get("exit_criteria"), label=f"PLAN_PACKETS.phases[{idx}].exit_criteria", errors=errors, min_items=1)
    else:
        _err(errors, "planner_bundle_schema_error", "PLAN_PACKETS.phases must be non-empty list")

    requirement_ids: list[str] = []
    if isinstance(reqs_raw, list) and reqs_raw:
        for idx, row in enumerate(reqs_raw):
            if not isinstance(row, dict):
                _err(errors, "planner_bundle_schema_error", f"PLAN_PACKETS.requirements[{idx}] must be object")
                continue
            _strict_keys(
                row,
                label=f"PLAN_PACKETS.requirements[{idx}]",
                required={"id", "title", "acceptance_criteria", "verify_commands"},
                optional=set(),
                errors=errors,
            )
            req_id = _require_nonempty_str(row.get("id"), label=f"PLAN_PACKETS.requirements[{idx}].id", errors=errors)
            if req_id:
                requirement_ids.append(req_id)
            _require_nonempty_str(row.get("title"), label=f"PLAN_PACKETS.requirements[{idx}].title", errors=errors)
            _require_str_list(row.get("acceptance_criteria"), label=f"PLAN_PACKETS.requirements[{idx}].acceptance_criteria", errors=errors, min_items=1)
            _require_str_list(row.get("verify_commands"), label=f"PLAN_PACKETS.requirements[{idx}].verify_commands", errors=errors, min_items=1)
    else:
        _err(errors, "planner_bundle_schema_error", "PLAN_PACKETS.requirements must be non-empty list")

    task_ids: list[str] = []
    covered: set[str] = set()
    task_dep_map: dict[str, list[str]] = {}
    lane_members: dict[str, set[str]] = {}
    task_lane_ids: set[str] = set()
    if isinstance(tasks_raw, list) and tasks_raw:
        for idx, row in enumerate(tasks_raw):
            if not isinstance(row, dict):
                _err(errors, "planner_bundle_schema_error", f"PLAN_PACKETS.tasks[{idx}] must be object")
                continue
            _strict_keys(
                row,
                label=f"PLAN_PACKETS.tasks[{idx}]",
                required={
                    "task_id",
                    "title",
                    "phase_id",
                    "lane_id",
                    "task_kind",
                    "status",
                    "verification_contract",
                    "requirement_ids",
                    "depends_on",
                    "must_haves",
                    "verify_commands",
                    "gaps_that_need_patching",
                },
                optional=set(),
                errors=errors,
            )
            task_id = _require_nonempty_str(row.get("task_id"), label=f"PLAN_PACKETS.tasks[{idx}].task_id", errors=errors)
            if task_id:
                task_ids.append(task_id)
            _require_nonempty_str(row.get("title"), label=f"PLAN_PACKETS.tasks[{idx}].title", errors=errors)
            phase_id = _require_nonempty_str(row.get("phase_id"), label=f"PLAN_PACKETS.tasks[{idx}].phase_id", errors=errors)
            if phase_id and phase_ids and phase_id not in phase_ids:
                _err(errors, "planner_bundle_schema_error", f"task {task_id or idx} references unknown phase_id", phase_id=phase_id)
            lane_id = _require_nonempty_str(row.get("lane_id"), label=f"PLAN_PACKETS.tasks[{idx}].lane_id", errors=errors)
            if lane_id:
                task_lane_ids.add(lane_id)
            if lane_id and phase_id:
                expected_prefix = f"{phase_id}/lane-"
                if not lane_id.startswith(expected_prefix):
                    _err(errors, "planner_bundle_schema_error", f"PLAN_PACKETS.tasks[{idx}].lane_id must be phase-scoped", expected_prefix=expected_prefix)
                lane_members.setdefault(phase_id, set()).add(lane_id)
            status = _require_nonempty_str(row.get("status"), label=f"PLAN_PACKETS.tasks[{idx}].status", errors=errors)
            if status != "pending":
                _err(errors, "planner_bundle_schema_error", f"PLAN_PACKETS.tasks[{idx}].status must be 'pending'")
            task_kind = _require_nonempty_str(row.get("task_kind"), label=f"PLAN_PACKETS.tasks[{idx}].task_kind", errors=errors)
            if task_kind and task_kind not in TASK_KINDS:
                _err(errors, "planner_bundle_schema_error", f"PLAN_PACKETS.tasks[{idx}].task_kind invalid", task_kind=task_kind)
            _validate_verification_contract(
                row.get("verification_contract"),
                task_kind=task_kind or "implementation",
                label=f"PLAN_PACKETS.tasks[{idx}].verification_contract",
                errors=errors,
            )
            req_ids = _require_str_list(row.get("requirement_ids"), label=f"PLAN_PACKETS.tasks[{idx}].requirement_ids", errors=errors, min_items=1)
            for rid in req_ids:
                covered.add(rid)
            deps = _require_str_list(row.get("depends_on"), label=f"PLAN_PACKETS.tasks[{idx}].depends_on", errors=errors)
            _require_str_list(row.get("must_haves"), label=f"PLAN_PACKETS.tasks[{idx}].must_haves", errors=errors, min_items=1)
            _require_str_list(row.get("verify_commands"), label=f"PLAN_PACKETS.tasks[{idx}].verify_commands", errors=errors, min_items=1)
            gaps = row.get("gaps_that_need_patching")
            if not isinstance(gaps, list):
                _err(errors, "planner_bundle_schema_error", f"PLAN_PACKETS.tasks[{idx}].gaps_that_need_patching must be list")
            else:
                for gidx, gap in enumerate(gaps):
                    if not isinstance(gap, dict):
                        _err(
                            errors,
                            "planner_bundle_schema_error",
                            f"PLAN_PACKETS.tasks[{idx}].gaps_that_need_patching[{gidx}] must be object",
                        )
                        continue
                    _strict_keys(
                        gap,
                        label=f"PLAN_PACKETS.tasks[{idx}].gaps_that_need_patching[{gidx}]",
                        required={
                            "gap_id",
                            "category",
                            "severity",
                            "stage",
                            "status",
                            "reason_codes",
                            "retry_count",
                            "max_retries",
                            "created_at",
                            "updated_at",
                            "closure_ref",
                        },
                        optional=set(),
                        errors=errors,
                    )
                    _require_nonempty_str(gap.get("gap_id"), label=f"PLAN_PACKETS.tasks[{idx}].gaps_that_need_patching[{gidx}].gap_id", errors=errors)
                    _require_nonempty_str(gap.get("category"), label=f"PLAN_PACKETS.tasks[{idx}].gaps_that_need_patching[{gidx}].category", errors=errors)
                    _require_nonempty_str(gap.get("severity"), label=f"PLAN_PACKETS.tasks[{idx}].gaps_that_need_patching[{gidx}].severity", errors=errors)
                    _require_nonempty_str(gap.get("stage"), label=f"PLAN_PACKETS.tasks[{idx}].gaps_that_need_patching[{gidx}].stage", errors=errors)
                    _require_nonempty_str(gap.get("status"), label=f"PLAN_PACKETS.tasks[{idx}].gaps_that_need_patching[{gidx}].status", errors=errors)
                    _require_str_list(gap.get("reason_codes"), label=f"PLAN_PACKETS.tasks[{idx}].gaps_that_need_patching[{gidx}].reason_codes", errors=errors, min_items=1)
                    retry_count = gap.get("retry_count")
                    max_retries = gap.get("max_retries")
                    if not isinstance(retry_count, int) or retry_count < 0:
                        _err(errors, "planner_bundle_schema_error", f"PLAN_PACKETS.tasks[{idx}].gaps_that_need_patching[{gidx}].retry_count must be non-negative int")
                    if not isinstance(max_retries, int) or max_retries < 1:
                        _err(errors, "planner_bundle_schema_error", f"PLAN_PACKETS.tasks[{idx}].gaps_that_need_patching[{gidx}].max_retries must be positive int")
                    if not _is_iso8601(gap.get("created_at")):
                        _err(errors, "planner_bundle_schema_error", f"PLAN_PACKETS.tasks[{idx}].gaps_that_need_patching[{gidx}].created_at must be ISO-8601")
                    if not _is_iso8601(gap.get("updated_at")):
                        _err(errors, "planner_bundle_schema_error", f"PLAN_PACKETS.tasks[{idx}].gaps_that_need_patching[{gidx}].updated_at must be ISO-8601")
                    _require_str_or_none(gap.get("closure_ref"), label=f"PLAN_PACKETS.tasks[{idx}].gaps_that_need_patching[{gidx}].closure_ref", errors=errors)
            if task_id:
                task_dep_map[task_id] = deps
            contract = row.get("verification_contract") if isinstance(row.get("verification_contract"), dict) else {}
            mode = _as_str(contract.get("mode"))
            task_kind = _as_str(row.get("task_kind")) or "implementation"
            if phase_id == "phase-1":
                if task_kind == "implementation" and mode != "tdd_red":
                    _err(
                        errors,
                        "planner_bundle_schema_error",
                        f"PLAN_PACKETS.tasks[{idx}] in phase-1 must use verification_contract.mode=tdd_red",
                    )
    else:
        _err(errors, "planner_bundle_schema_error", "PLAN_PACKETS.tasks must be non-empty list")

    missing_lane_base_entries = sorted(task_lane_ids - set(lane_base_branches.keys()))
    if missing_lane_base_entries:
        _err(
            errors,
            "planner_bundle_schema_error",
            "PLAN_PACKETS.lane_base_branches must include every tasks[].lane_id",
            missing_lane_ids=missing_lane_base_entries,
        )

    seen_tasks = set()
    for tid in task_ids:
        if tid in seen_tasks:
            _err(errors, "planner_bundle_schema_error", "PLAN_PACKETS.tasks contains duplicate task_id", task_id=tid)
        seen_tasks.add(tid)

    task_set = set(task_ids)
    for tid, deps in task_dep_map.items():
        for dep in deps:
            if dep not in task_set:
                _err(errors, "planner_bundle_schema_error", f"task {tid} depends on unknown task", dependency=dep)

    # Validate task DAG acyclic.
    indegree: dict[str, int] = {task_id: 0 for task_id in task_set}
    succs: dict[str, list[str]] = {task_id: [] for task_id in task_set}
    for task_id, deps in task_dep_map.items():
        for dep in deps:
            if dep in task_set:
                indegree[task_id] += 1
                succs[dep].append(task_id)
    queue = [task_id for task_id, value in indegree.items() if value == 0]
    visited = 0
    while queue:
        node = queue.pop()
        visited += 1
        for child in succs.get(node, []):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if visited != len(task_set):
        _err(errors, "planner_bundle_schema_error", "PLAN_PACKETS task DAG contains cycle")

    # Validate phase graph and task<->phase mapping.
    phase_set = set(phase_ids)
    for phase_id, deps in phase_deps.items():
        for dep in deps:
            if dep not in phase_set:
                _err(errors, "planner_bundle_schema_error", f"phase {phase_id} depends on unknown phase", dependency=dep)
            if dep == phase_id:
                _err(errors, "planner_bundle_schema_error", f"phase {phase_id} must not depend on itself")

    phase_indegree: dict[str, int] = {phase_id: 0 for phase_id in phase_set}
    phase_succs: dict[str, list[str]] = {phase_id: [] for phase_id in phase_set}
    for phase_id, deps in phase_deps.items():
        for dep in deps:
            if dep in phase_set:
                phase_indegree[phase_id] += 1
                phase_succs[dep].append(phase_id)
    phase_queue = [phase_id for phase_id, value in phase_indegree.items() if value == 0]
    phase_visited = 0
    while phase_queue:
        node = phase_queue.pop()
        phase_visited += 1
        for child in phase_succs.get(node, []):
            phase_indegree[child] -= 1
            if phase_indegree[child] == 0:
                phase_queue.append(child)
    if phase_visited != len(phase_set):
        _err(errors, "planner_bundle_schema_error", "PLAN_PACKETS phase DAG contains cycle")

    tasks_in_phases: list[str] = []
    for phase_id, members in phase_task_ids.items():
        for member in members:
            if member not in task_set:
                _err(errors, "planner_bundle_schema_error", f"phase {phase_id} references unknown task_id", task_id=member)
            tasks_in_phases.append(member)
    counts: dict[str, int] = {}
    for task_id in tasks_in_phases:
        counts[task_id] = counts.get(task_id, 0) + 1
    for task_id, count in counts.items():
        if count > 1:
            _err(errors, "planner_bundle_schema_error", "task_id appears in multiple phases", task_id=task_id, count=count)
    missing_phase_assignment = sorted(task_set - set(tasks_in_phases))
    if missing_phase_assignment:
        _err(errors, "planner_bundle_schema_error", "tasks missing from phase.task_ids mapping", missing_task_ids=missing_phase_assignment)

    if requirement_ids:
        for rid in requirement_ids:
            if rid not in covered:
                _err(errors, "planner_bundle_schema_error", "requirement id not covered by any task", requirement_id=rid)

    for phase_id, lanes in lane_members.items():
        if len(lanes) > 3:
            _err(
                errors,
                "planner_bundle_schema_error",
                f"phase {phase_id} has more than 3 lanes",
                lane_count=len(lanes),
                lanes=sorted(lanes),
            )

    # Keep hardening/review terminal-task enforcement aligned with op_core validation.
    by_requirement: dict[str, set[str]] = {}
    task_rows: dict[str, dict[str, Any]] = {}
    for row in tasks_raw:
        if not isinstance(row, dict):
            continue
        task_id = _as_str(row.get("task_id"))
        if not task_id:
            continue
        task_rows[task_id] = row
        req_ids = row.get("requirement_ids")
        if not isinstance(req_ids, list):
            continue
        for req in req_ids:
            req_id = _as_str(req)
            if not req_id:
                continue
            by_requirement.setdefault(req_id, set()).add(task_id)

    for req_id, req_task_ids in by_requirement.items():
        if len(req_task_ids) <= 2:
            continue
        terminals: list[dict[str, Any]] = []
        for task_id in sorted(req_task_ids):
            children = succs.get(task_id, [])
            if any(child in req_task_ids for child in children):
                continue
            row = task_rows.get(task_id)
            if isinstance(row, dict):
                terminals.append(row)
        hardening_terminals = 0
        for row in terminals:
            title = (_as_str(row.get("title")) or "").lower()
            if "harden" in title or "hardening" in title or "review" in title:
                hardening_terminals += 1
        if hardening_terminals < 2:
            _err(
                errors,
                "planner_bundle_schema_error",
                f"requirement {req_id} needs at least 2 terminal hardening/review tasks when task count > 2",
            )

    return plan_id, task_ids, requirement_ids, covered


def _validate_plan_check(payload: dict[str, Any], errors: list[dict[str, object]]) -> None:
    _strict_keys(
        payload,
        label="PLAN_CHECK.json",
        required={
            "schema_version",
            "passed",
            "checks",
            "coverage",
            "dependency_graph",
            "verify_contract_completeness",
            "phase_traceability",
            "blocking_errors",
        },
        optional=set(),
        errors=errors,
    )
    _require_nonempty_str(payload.get("schema_version"), label="PLAN_CHECK.schema_version", errors=errors)
    passed = _require_bool(payload.get("passed"), label="PLAN_CHECK.passed", errors=errors)
    if passed is False:
        _err(errors, "planner_plan_check_failed", "PLAN_CHECK.passed must be true")
    checks = payload.get("checks")
    if not isinstance(checks, list) or not checks:
        _err(errors, "planner_bundle_schema_error", "PLAN_CHECK.checks must be non-empty list")
    else:
        for idx, row in enumerate(checks):
            if not isinstance(row, dict):
                _err(errors, "planner_bundle_schema_error", f"PLAN_CHECK.checks[{idx}] must be object")
                continue
            _require_nonempty_str(row.get("id"), label=f"PLAN_CHECK.checks[{idx}].id", errors=errors)
            _require_bool(row.get("passed"), label=f"PLAN_CHECK.checks[{idx}].passed", errors=errors)
    coverage = _require_object(payload.get("coverage"), label="PLAN_CHECK.coverage", errors=errors)
    if coverage is not None:
        _strict_keys(
            coverage,
            label="PLAN_CHECK.coverage",
            required={"requirements_total", "requirements_covered", "missing_requirement_ids"},
            optional=set(),
            errors=errors,
        )
        total = coverage.get("requirements_total")
        covered = coverage.get("requirements_covered")
        missing_ids = coverage.get("missing_requirement_ids")
        if not isinstance(total, int) or total < 0:
            _err(errors, "planner_bundle_schema_error", "PLAN_CHECK.coverage.requirements_total must be non-negative int")
        if not isinstance(covered, int) or covered < 0:
            _err(errors, "planner_bundle_schema_error", "PLAN_CHECK.coverage.requirements_covered must be non-negative int")
        if not isinstance(missing_ids, list):
            _err(errors, "planner_bundle_schema_error", "PLAN_CHECK.coverage.missing_requirement_ids must be list")
        elif any(not isinstance(item, str) or not item.strip() for item in missing_ids):
            _err(errors, "planner_bundle_schema_error", "PLAN_CHECK.coverage.missing_requirement_ids entries must be non-empty strings")
    dep_graph = _require_object(payload.get("dependency_graph"), label="PLAN_CHECK.dependency_graph", errors=errors)
    if dep_graph is not None:
        _strict_keys(
            dep_graph,
            label="PLAN_CHECK.dependency_graph",
            required={"nodes", "edges", "cycle_detected", "valid"},
            optional=set(),
            errors=errors,
        )
        nodes = dep_graph.get("nodes")
        edges = dep_graph.get("edges")
        if not isinstance(nodes, list):
            _err(errors, "planner_bundle_schema_error", "PLAN_CHECK.dependency_graph.nodes must be list")
        elif any(not isinstance(item, str) or not item.strip() for item in nodes):
            _err(errors, "planner_bundle_schema_error", "PLAN_CHECK.dependency_graph.nodes entries must be non-empty strings")
        if not isinstance(edges, list):
            _err(errors, "planner_bundle_schema_error", "PLAN_CHECK.dependency_graph.edges must be list")
        else:
            for idx, edge in enumerate(edges):
                if not isinstance(edge, dict):
                    _err(errors, "planner_bundle_schema_error", f"PLAN_CHECK.dependency_graph.edges[{idx}] must be object")
                    continue
                if set(edge.keys()) != {"from", "to"}:
                    _err(errors, "planner_bundle_schema_error", f"PLAN_CHECK.dependency_graph.edges[{idx}] must have keys from|to only")
                _require_nonempty_str(edge.get("from"), label=f"PLAN_CHECK.dependency_graph.edges[{idx}].from", errors=errors)
                _require_nonempty_str(edge.get("to"), label=f"PLAN_CHECK.dependency_graph.edges[{idx}].to", errors=errors)
        _require_bool(dep_graph.get("cycle_detected"), label="PLAN_CHECK.dependency_graph.cycle_detected", errors=errors)
        _require_bool(dep_graph.get("valid"), label="PLAN_CHECK.dependency_graph.valid", errors=errors)
    _require_bool(payload.get("verify_contract_completeness"), label="PLAN_CHECK.verify_contract_completeness", errors=errors)
    _require_bool(payload.get("phase_traceability"), label="PLAN_CHECK.phase_traceability", errors=errors)
    if not isinstance(payload.get("blocking_errors"), list):
        _err(errors, "planner_bundle_schema_error", "PLAN_CHECK.blocking_errors must be list")


def _validate_task_execution_state(payload: dict[str, Any], task_ids: set[str], errors: list[dict[str, object]]) -> str | None:
    _strict_keys(
        payload,
        label="TASK_EXECUTION_STATE.json",
        required={"schema_version", "plan_id", "updated_at", "tasks"},
        optional=set(),
        errors=errors,
    )
    _require_nonempty_str(payload.get("schema_version"), label="TASK_EXECUTION_STATE.schema_version", errors=errors)
    plan_id = _require_nonempty_str(payload.get("plan_id"), label="TASK_EXECUTION_STATE.plan_id", errors=errors)
    if not _is_iso8601(payload.get("updated_at")):
        _err(errors, "planner_bundle_schema_error", "TASK_EXECUTION_STATE.updated_at must be ISO-8601")

    rows = payload.get("tasks")
    state_ids: set[str] = set()
    if not isinstance(rows, list):
        _err(errors, "planner_bundle_schema_error", "TASK_EXECUTION_STATE.tasks must be list")
        return plan_id

    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            _err(errors, "planner_bundle_schema_error", f"TASK_EXECUTION_STATE.tasks[{idx}] must be object")
            continue
        _strict_keys(
            row,
            label=f"TASK_EXECUTION_STATE.tasks[{idx}]",
            required={
                "task_id",
                "phase_id",
                "lane_id",
                "task_kind",
                "requirement_ids",
                "verification_contract",
                "status",
                "owner_slot",
                "dispatch_thread_id",
                "last_progress_at",
                "attempts",
                "evidence",
                "gaps_that_need_patching",
                "blockers",
                "last_handoff_outcome",
                "blocking_source",
                "gapfix_state",
                "progress_watchdog",
            },
            optional=set(),
            errors=errors,
        )
        task_id = _require_nonempty_str(row.get("task_id"), label=f"TASK_EXECUTION_STATE.tasks[{idx}].task_id", errors=errors)
        if task_id:
            state_ids.add(task_id)
            if task_id not in task_ids:
                _err(errors, "planner_bundle_schema_error", "TASK_EXECUTION_STATE includes unknown task_id", task_id=task_id)
        _require_nonempty_str(row.get("phase_id"), label=f"TASK_EXECUTION_STATE.tasks[{idx}].phase_id", errors=errors)
        lane_id = _require_nonempty_str(row.get("lane_id"), label=f"TASK_EXECUTION_STATE.tasks[{idx}].lane_id", errors=errors)
        phase_id = _as_str(row.get("phase_id")) or "phase-1"
        if lane_id and not lane_id.startswith(f"{phase_id}/lane-"):
            _err(errors, "planner_bundle_schema_error", f"TASK_EXECUTION_STATE.tasks[{idx}].lane_id must be phase-scoped")
        task_kind = _require_nonempty_str(row.get("task_kind"), label=f"TASK_EXECUTION_STATE.tasks[{idx}].task_kind", errors=errors)
        if task_kind and task_kind not in TASK_KINDS:
            _err(errors, "planner_bundle_schema_error", f"TASK_EXECUTION_STATE.tasks[{idx}].task_kind invalid", task_kind=task_kind)
        _require_str_list(row.get("requirement_ids"), label=f"TASK_EXECUTION_STATE.tasks[{idx}].requirement_ids", errors=errors, min_items=1)

        status = _as_str(row.get("status"))
        if status not in TASK_STATUS:
            _err(errors, "planner_bundle_schema_error", f"TASK_EXECUTION_STATE.tasks[{idx}].status invalid", status=status)
        _validate_verification_contract(
            row.get("verification_contract"),
            task_kind=task_kind or "implementation",
            label=f"TASK_EXECUTION_STATE.tasks[{idx}].verification_contract",
            errors=errors,
        )

        owner_slot = row.get("owner_slot")
        _require_str_or_none(owner_slot, label=f"TASK_EXECUTION_STATE.tasks[{idx}].owner_slot", errors=errors)
        _require_str_or_none(row.get("dispatch_thread_id"), label=f"TASK_EXECUTION_STATE.tasks[{idx}].dispatch_thread_id", errors=errors)
        if row.get("last_progress_at") is not None and not _is_iso8601(row.get("last_progress_at")):
            _err(errors, "planner_bundle_schema_error", f"TASK_EXECUTION_STATE.tasks[{idx}].last_progress_at must be ISO-8601|null")

        attempts = _require_object(row.get("attempts"), label=f"TASK_EXECUTION_STATE.tasks[{idx}].attempts", errors=errors)
        if attempts is not None:
            _strict_keys(
                attempts,
                label=f"TASK_EXECUTION_STATE.tasks[{idx}].attempts",
                required={"dev", "test", "review"},
                optional=set(),
                errors=errors,
            )
            for key in ("dev", "test", "review"):
                value = attempts.get(key)
                if not isinstance(value, int) or value < 0:
                    _err(errors, "planner_bundle_schema_error", f"TASK_EXECUTION_STATE.tasks[{idx}].attempts.{key} must be non-negative int")

        evidence = _require_object(row.get("evidence"), label=f"TASK_EXECUTION_STATE.tasks[{idx}].evidence", errors=errors)
        if evidence is not None:
            _strict_keys(
                evidence,
                label=f"TASK_EXECUTION_STATE.tasks[{idx}].evidence",
                required={"task_evidence_ref", "dev_ready_evidence_ref", "verify_results", "uat_results"},
                optional=set(),
                errors=errors,
            )
            _require_nonempty_str(evidence.get("task_evidence_ref"), label=f"TASK_EXECUTION_STATE.tasks[{idx}].evidence.task_evidence_ref", errors=errors)
            _require_nonempty_str(evidence.get("dev_ready_evidence_ref"), label=f"TASK_EXECUTION_STATE.tasks[{idx}].evidence.dev_ready_evidence_ref", errors=errors)
            if not isinstance(evidence.get("verify_results"), list):
                _err(errors, "planner_bundle_schema_error", f"TASK_EXECUTION_STATE.tasks[{idx}].evidence.verify_results must be list")
            if not isinstance(evidence.get("uat_results"), list):
                _err(errors, "planner_bundle_schema_error", f"TASK_EXECUTION_STATE.tasks[{idx}].evidence.uat_results must be list")

        gaps = row.get("gaps_that_need_patching")
        if not isinstance(gaps, list):
            _err(errors, "planner_bundle_schema_error", f"TASK_EXECUTION_STATE.tasks[{idx}].gaps_that_need_patching must be list")
        if not isinstance(row.get("blockers"), list):
            _err(errors, "planner_bundle_schema_error", f"TASK_EXECUTION_STATE.tasks[{idx}].blockers must be list")
        handoff = _require_object(row.get("last_handoff_outcome"), label=f"TASK_EXECUTION_STATE.tasks[{idx}].last_handoff_outcome", errors=errors)
        if handoff is not None:
            _strict_keys(
                handoff,
                label=f"TASK_EXECUTION_STATE.tasks[{idx}].last_handoff_outcome",
                required={"status", "reason_codes", "timestamp"},
                optional=set(),
                errors=errors,
            )
            _require_str_or_none(
                handoff.get("status"),
                label=f"TASK_EXECUTION_STATE.tasks[{idx}].last_handoff_outcome.status",
                errors=errors,
            )
            _require_str_list(
                handoff.get("reason_codes"),
                label=f"TASK_EXECUTION_STATE.tasks[{idx}].last_handoff_outcome.reason_codes",
                errors=errors,
            )
            timestamp = handoff.get("timestamp")
            if timestamp is not None and not _is_iso8601(timestamp):
                _err(errors, "planner_bundle_schema_error", f"TASK_EXECUTION_STATE.tasks[{idx}].last_handoff_outcome.timestamp must be ISO-8601|null")
        blocking_source = _as_str(row.get("blocking_source"))
        if blocking_source not in {"handoff", "evidence", "merge", "none"}:
            _err(errors, "planner_bundle_schema_error", f"TASK_EXECUTION_STATE.tasks[{idx}].blocking_source must be handoff|evidence|merge|none")

        gapfix_state = _require_object(
            row.get("gapfix_state"),
            label=f"TASK_EXECUTION_STATE.tasks[{idx}].gapfix_state",
            errors=errors,
        )
        if gapfix_state is not None:
            _strict_keys(
                gapfix_state,
                label=f"TASK_EXECUTION_STATE.tasks[{idx}].gapfix_state",
                required={
                    "active_batch_id",
                    "active",
                    "target_gap_stage",
                    "consumed_gap_ids",
                    "batch_started_cycle",
                    "batch_last_updated_at",
                },
                optional=set(),
                errors=errors,
            )
            _require_str_or_none(
                gapfix_state.get("active_batch_id"),
                label=f"TASK_EXECUTION_STATE.tasks[{idx}].gapfix_state.active_batch_id",
                errors=errors,
            )
            _require_bool(
                gapfix_state.get("active"),
                label=f"TASK_EXECUTION_STATE.tasks[{idx}].gapfix_state.active",
                errors=errors,
            )
            target_stage = gapfix_state.get("target_gap_stage")
            _require_str_or_none(
                target_stage,
                label=f"TASK_EXECUTION_STATE.tasks[{idx}].gapfix_state.target_gap_stage",
                errors=errors,
            )
            if isinstance(target_stage, str) and target_stage not in {"dev", "test", "review"}:
                _err(
                    errors,
                    "planner_bundle_schema_error",
                    f"TASK_EXECUTION_STATE.tasks[{idx}].gapfix_state.target_gap_stage must be dev|test|review|null",
                )
            _require_str_list(
                gapfix_state.get("consumed_gap_ids"),
                label=f"TASK_EXECUTION_STATE.tasks[{idx}].gapfix_state.consumed_gap_ids",
                errors=errors,
            )
            batch_started = gapfix_state.get("batch_started_cycle")
            if batch_started is not None and (not isinstance(batch_started, int) or batch_started < 1):
                _err(
                    errors,
                    "planner_bundle_schema_error",
                    f"TASK_EXECUTION_STATE.tasks[{idx}].gapfix_state.batch_started_cycle must be positive int|null",
                )
            batch_updated = gapfix_state.get("batch_last_updated_at")
            if batch_updated is not None and not _is_iso8601(batch_updated):
                _err(
                    errors,
                    "planner_bundle_schema_error",
                    f"TASK_EXECUTION_STATE.tasks[{idx}].gapfix_state.batch_last_updated_at must be ISO-8601|null",
                )

        progress_watchdog = _require_object(
            row.get("progress_watchdog"),
            label=f"TASK_EXECUTION_STATE.tasks[{idx}].progress_watchdog",
            errors=errors,
        )
        if progress_watchdog is not None:
            _strict_keys(
                progress_watchdog,
                label=f"TASK_EXECUTION_STATE.tasks[{idx}].progress_watchdog",
                required={
                    "started",
                    "first_dispatched_cycle",
                    "task_started_cycle",
                    "last_forward_progress_cycle",
                    "consecutive_no_forward_progress_cycles",
                    "threshold_cycles",
                    "triggered",
                    "triggered_at",
                },
                optional=set(),
                errors=errors,
            )
            task_started = progress_watchdog.get("task_started_cycle")
            if task_started is not None and (not isinstance(task_started, int) or task_started < 1):
                _err(
                    errors,
                    "planner_bundle_schema_error",
                    f"TASK_EXECUTION_STATE.tasks[{idx}].progress_watchdog.task_started_cycle must be positive int|null",
                )
            last_forward = progress_watchdog.get("last_forward_progress_cycle")
            if last_forward is not None and (not isinstance(last_forward, int) or last_forward < 1):
                _err(
                    errors,
                    "planner_bundle_schema_error",
                    f"TASK_EXECUTION_STATE.tasks[{idx}].progress_watchdog.last_forward_progress_cycle must be positive int|null",
                )
            no_progress = progress_watchdog.get("consecutive_no_forward_progress_cycles")
            if not isinstance(no_progress, int) or no_progress < 0:
                _err(
                    errors,
                    "planner_bundle_schema_error",
                    f"TASK_EXECUTION_STATE.tasks[{idx}].progress_watchdog.consecutive_no_forward_progress_cycles must be non-negative int",
                )
            threshold_cycles = progress_watchdog.get("threshold_cycles")
            if not isinstance(threshold_cycles, int) or threshold_cycles < 1:
                _err(
                    errors,
                    "planner_bundle_schema_error",
                    f"TASK_EXECUTION_STATE.tasks[{idx}].progress_watchdog.threshold_cycles must be positive int",
                )
            _require_bool(
                progress_watchdog.get("started"),
                label=f"TASK_EXECUTION_STATE.tasks[{idx}].progress_watchdog.started",
                errors=errors,
            )
            first_dispatched = progress_watchdog.get("first_dispatched_cycle")
            if first_dispatched is not None and (not isinstance(first_dispatched, int) or first_dispatched < 1):
                _err(
                    errors,
                    "planner_bundle_schema_error",
                    f"TASK_EXECUTION_STATE.tasks[{idx}].progress_watchdog.first_dispatched_cycle must be positive int|null",
                )
            _require_bool(
                progress_watchdog.get("triggered"),
                label=f"TASK_EXECUTION_STATE.tasks[{idx}].progress_watchdog.triggered",
                errors=errors,
            )
            triggered_at = progress_watchdog.get("triggered_at")
            if triggered_at is not None and not _is_iso8601(triggered_at):
                _err(
                    errors,
                    "planner_bundle_schema_error",
                    f"TASK_EXECUTION_STATE.tasks[{idx}].progress_watchdog.triggered_at must be ISO-8601|null",
                )

    missing = sorted(task_ids - state_ids)
    if missing:
        _err(errors, "planner_bundle_schema_error", "TASK_EXECUTION_STATE missing plan task IDs", missing_task_ids=missing)
    extra = sorted(state_ids - task_ids)
    if extra:
        _err(errors, "planner_bundle_schema_error", "TASK_EXECUTION_STATE has unexpected task IDs", extra_task_ids=extra)
    return plan_id


def _validate_gaps(payload: dict[str, Any], errors: list[dict[str, object]]) -> str | None:
    _strict_keys(
        payload,
        label="GAPS.json",
        required={"schema_version", "plan_id", "updated_at", "gaps"},
        optional=set(),
        errors=errors,
    )
    _require_nonempty_str(payload.get("schema_version"), label="GAPS.schema_version", errors=errors)
    plan_id = _require_nonempty_str(payload.get("plan_id"), label="GAPS.plan_id", errors=errors)
    if not _is_iso8601(payload.get("updated_at")):
        _err(errors, "planner_bundle_schema_error", "GAPS.updated_at must be ISO-8601")
    rows = payload.get("gaps")
    if not isinstance(rows, list):
        _err(errors, "planner_bundle_schema_error", "GAPS.gaps must be list")
        return plan_id

    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            _err(errors, "planner_bundle_schema_error", f"GAPS.gaps[{idx}] must be object")
            continue
        _strict_keys(
            row,
            label=f"GAPS.gaps[{idx}]",
            required={
                "gap_id",
                "phase_id",
                "severity",
                "result",
                "evidence_ref",
                "opened_at",
                "status",
                "category",
                "reason_codes",
                "closure_task_id",
                "last_seen_open_at",
                "closure_required",
                "closure_evidence_ref",
                "closed_by_task_id",
                "closed_at",
                "resolution_candidate_at",
            },
            optional={"task_id", "requirement_id", "reason", "updated_at", "escalated", "escalated_at", "retry_count"},
            errors=errors,
        )
        _require_nonempty_str(row.get("gap_id"), label=f"GAPS.gaps[{idx}].gap_id", errors=errors)
        _require_nonempty_str(row.get("phase_id"), label=f"GAPS.gaps[{idx}].phase_id", errors=errors)
        _require_nonempty_str(row.get("severity"), label=f"GAPS.gaps[{idx}].severity", errors=errors)
        _require_nonempty_str(row.get("result"), label=f"GAPS.gaps[{idx}].result", errors=errors)
        _require_nonempty_str(row.get("evidence_ref"), label=f"GAPS.gaps[{idx}].evidence_ref", errors=errors)
        _require_nonempty_str(row.get("status"), label=f"GAPS.gaps[{idx}].status", errors=errors)
        _require_nonempty_str(row.get("category"), label=f"GAPS.gaps[{idx}].category", errors=errors)
        _require_str_list(row.get("reason_codes"), label=f"GAPS.gaps[{idx}].reason_codes", errors=errors, min_items=1)
        _require_nonempty_str(row.get("closure_task_id"), label=f"GAPS.gaps[{idx}].closure_task_id", errors=errors)
        closure_required = _require_bool(row.get("closure_required"), label=f"GAPS.gaps[{idx}].closure_required", errors=errors)
        if closure_required is False:
            _err(errors, "planner_bundle_schema_error", f"GAPS.gaps[{idx}].closure_required must be true")
        if not _is_iso8601(row.get("opened_at")):
            _err(errors, "planner_bundle_schema_error", f"GAPS.gaps[{idx}].opened_at must be ISO-8601")
        if not _is_iso8601(row.get("last_seen_open_at")):
            _err(errors, "planner_bundle_schema_error", f"GAPS.gaps[{idx}].last_seen_open_at must be ISO-8601")
        _require_str_or_none(row.get("closure_evidence_ref"), label=f"GAPS.gaps[{idx}].closure_evidence_ref", errors=errors)
        _require_str_or_none(row.get("closed_by_task_id"), label=f"GAPS.gaps[{idx}].closed_by_task_id", errors=errors)
        if row.get("closed_at") is not None and not _is_iso8601(row.get("closed_at")):
            _err(errors, "planner_bundle_schema_error", f"GAPS.gaps[{idx}].closed_at must be ISO-8601|null")
        if row.get("resolution_candidate_at") is not None and not _is_iso8601(row.get("resolution_candidate_at")):
            _err(errors, "planner_bundle_schema_error", f"GAPS.gaps[{idx}].resolution_candidate_at must be ISO-8601|null")
    return plan_id


def _validate_gap_closure(payload: dict[str, Any], errors: list[dict[str, object]]) -> str | None:
    _strict_keys(
        payload,
        label="GAP_CLOSURE_PLAN_PACKETS.json",
        required={"schema_version", "plan_id", "generated_at", "tasks"},
        optional=set(),
        errors=errors,
    )
    _require_nonempty_str(payload.get("schema_version"), label="GAP_CLOSURE.schema_version", errors=errors)
    plan_id = _require_nonempty_str(payload.get("plan_id"), label="GAP_CLOSURE.plan_id", errors=errors)
    if not _is_iso8601(payload.get("generated_at")):
        _err(errors, "planner_bundle_schema_error", "GAP_CLOSURE.generated_at must be ISO-8601")
    rows = payload.get("tasks")
    if not isinstance(rows, list):
        _err(errors, "planner_bundle_schema_error", "GAP_CLOSURE.tasks must be list")
        return plan_id
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            _err(errors, "planner_bundle_schema_error", f"GAP_CLOSURE.tasks[{idx}] must be object")
            continue
        _strict_keys(
            row,
            label=f"GAP_CLOSURE.tasks[{idx}]",
            required={
                "task_id",
                "phase_id",
                "source_gap_id",
                "title",
                "requirement_ids",
                "depends_on",
                "must_haves",
                "verify_commands",
                "is_gap_closure",
            },
            optional={"requirement_fallback_used"},
            errors=errors,
        )
        _require_nonempty_str(row.get("task_id"), label=f"GAP_CLOSURE.tasks[{idx}].task_id", errors=errors)
        _require_nonempty_str(row.get("phase_id"), label=f"GAP_CLOSURE.tasks[{idx}].phase_id", errors=errors)
        _require_nonempty_str(row.get("source_gap_id"), label=f"GAP_CLOSURE.tasks[{idx}].source_gap_id", errors=errors)
        _require_nonempty_str(row.get("title"), label=f"GAP_CLOSURE.tasks[{idx}].title", errors=errors)
        _require_str_list(row.get("requirement_ids"), label=f"GAP_CLOSURE.tasks[{idx}].requirement_ids", errors=errors, min_items=1)
        _require_str_list(row.get("depends_on"), label=f"GAP_CLOSURE.tasks[{idx}].depends_on", errors=errors)
        _require_str_list(row.get("must_haves"), label=f"GAP_CLOSURE.tasks[{idx}].must_haves", errors=errors, min_items=1)
        _require_str_list(row.get("verify_commands"), label=f"GAP_CLOSURE.tasks[{idx}].verify_commands", errors=errors, min_items=1)
        is_gap = _require_bool(row.get("is_gap_closure"), label=f"GAP_CLOSURE.tasks[{idx}].is_gap_closure", errors=errors)
        if is_gap is False:
            _err(errors, "planner_bundle_schema_error", f"GAP_CLOSURE.tasks[{idx}].is_gap_closure must be true")
        if "requirement_fallback_used" in row:
            _require_bool(row.get("requirement_fallback_used"), label=f"GAP_CLOSURE.tasks[{idx}].requirement_fallback_used", errors=errors)


def _validate_state_json(payload: dict[str, Any], errors: list[dict[str, object]]) -> str | None:
    _strict_keys(
        payload,
        label="STATE.json",
        required={
            "schema_version",
            "initialized_at",
            "updated_at",
            "mission",
            "scope",
            "mission_source",
            "scope_source",
            "constraints",
            "requirements",
            "map_fingerprint",
            "repo_fingerprint",
            "baseline_ready",
            "plan_ready",
            "plan_id",
            "build_ready",
        },
        optional={"phase_count", "profile_aliases", "profile_selection_ref"},
        errors=errors,
    )
    _require_nonempty_str(payload.get("schema_version"), label="STATE.schema_version", errors=errors)
    if not _is_iso8601(payload.get("initialized_at")):
        _err(errors, "planner_bundle_schema_error", "STATE.initialized_at must be ISO-8601")
    if not _is_iso8601(payload.get("updated_at")):
        _err(errors, "planner_bundle_schema_error", "STATE.updated_at must be ISO-8601")
    _require_nonempty_str(payload.get("mission"), label="STATE.mission", errors=errors)
    _require_nonempty_str(payload.get("scope"), label="STATE.scope", errors=errors)
    mission_source = payload.get("mission_source")
    if not isinstance(mission_source, dict):
        _err(errors, "planner_bundle_schema_error", "STATE.mission_source must be object")
    else:
        _strict_keys(
            mission_source,
            label="STATE.mission_source",
            required={"mode", "value", "path", "display"},
            optional=set(),
            errors=errors,
        )
        mode = _require_nonempty_str(mission_source.get("mode"), label="STATE.mission_source.mode", errors=errors)
        if mode not in {"inline", "file"}:
            _err(errors, "planner_bundle_schema_error", "STATE.mission_source.mode must be inline|file")
        _require_nonempty_str(mission_source.get("display"), label="STATE.mission_source.display", errors=errors)
        _require_str_or_none(mission_source.get("value"), label="STATE.mission_source.value", errors=errors)
        _require_str_or_none(mission_source.get("path"), label="STATE.mission_source.path", errors=errors)
    scope_source = payload.get("scope_source")
    if not isinstance(scope_source, dict):
        _err(errors, "planner_bundle_schema_error", "STATE.scope_source must be object")
    else:
        _strict_keys(
            scope_source,
            label="STATE.scope_source",
            required={"mode", "value", "path", "display"},
            optional=set(),
            errors=errors,
        )
        mode = _require_nonempty_str(scope_source.get("mode"), label="STATE.scope_source.mode", errors=errors)
        if mode not in {"inline", "file"}:
            _err(errors, "planner_bundle_schema_error", "STATE.scope_source.mode must be inline|file")
        _require_nonempty_str(scope_source.get("display"), label="STATE.scope_source.display", errors=errors)
        _require_str_or_none(scope_source.get("value"), label="STATE.scope_source.value", errors=errors)
        _require_str_or_none(scope_source.get("path"), label="STATE.scope_source.path", errors=errors)
    constraints = payload.get("constraints")
    if not isinstance(constraints, list):
        _err(errors, "planner_bundle_schema_error", "STATE.constraints must be list")
    elif any(not isinstance(item, str) for item in constraints):
        _err(errors, "planner_bundle_schema_error", "STATE.constraints entries must be strings")
    requirements = payload.get("requirements")
    if not isinstance(requirements, list):
        _err(errors, "planner_bundle_schema_error", "STATE.requirements must be list")
    elif any(not isinstance(item, dict) for item in requirements):
        _err(errors, "planner_bundle_schema_error", "STATE.requirements entries must be objects")
    _require_nonempty_str(payload.get("map_fingerprint"), label="STATE.map_fingerprint", errors=errors)
    _require_nonempty_str(payload.get("repo_fingerprint"), label="STATE.repo_fingerprint", errors=errors)
    _require_bool(payload.get("baseline_ready"), label="STATE.baseline_ready", errors=errors)
    _require_bool(payload.get("plan_ready"), label="STATE.plan_ready", errors=errors)
    _require_bool(payload.get("build_ready"), label="STATE.build_ready", errors=errors)
    return _require_nonempty_str(payload.get("plan_id"), label="STATE.plan_id", errors=errors)


def _validate_evidence(path: str, payload: dict[str, Any], errors: list[dict[str, object]]) -> tuple[str | None, str | None]:
    _strict_keys(
        payload,
        label=path,
        required={
            "schema_version",
            "plan_id",
            "phase_id",
            "task_id",
            "task_kind",
            "requirement_ids",
            "updated_at",
            "dev",
            "test",
            "review",
            "summary",
        },
        optional=set(),
        errors=errors,
    )
    _require_nonempty_str(payload.get("schema_version"), label=f"{path}.schema_version", errors=errors)
    plan_id = _require_nonempty_str(payload.get("plan_id"), label=f"{path}.plan_id", errors=errors)
    task_id = _require_nonempty_str(payload.get("task_id"), label=f"{path}.task_id", errors=errors)
    _require_nonempty_str(payload.get("phase_id"), label=f"{path}.phase_id", errors=errors)
    task_kind = _require_nonempty_str(payload.get("task_kind"), label=f"{path}.task_kind", errors=errors)
    if task_kind and task_kind not in TASK_KINDS:
        _err(errors, "planner_bundle_schema_error", f"{path}.task_kind invalid", task_kind=task_kind)
    _require_str_list(payload.get("requirement_ids"), label=f"{path}.requirement_ids", errors=errors, min_items=1)
    if not _is_iso8601(payload.get("updated_at")):
        _err(errors, "planner_bundle_schema_error", f"{path}.updated_at must be ISO-8601")

    dev = _require_object(payload.get("dev"), label=f"{path}.dev", errors=errors)
    if dev is not None:
        _strict_keys(dev, label=f"{path}.dev", required={"status", "checks", "verify_results", "dev_ready", "blockers", "artifacts"}, optional=set(), errors=errors)
        if _as_str(dev.get("status")) not in EVIDENCE_STATUS:
            _err(errors, "planner_bundle_schema_error", f"{path}.dev.status invalid")
        _require_bool(dev.get("dev_ready"), label=f"{path}.dev.dev_ready", errors=errors)
        for key in ("checks", "verify_results", "blockers", "artifacts"):
            if not isinstance(dev.get(key), list):
                _err(errors, "planner_bundle_schema_error", f"{path}.dev.{key} must be list")

    test = _require_object(payload.get("test"), label=f"{path}.test", errors=errors)
    if test is not None:
        _strict_keys(test, label=f"{path}.test", required={"status", "checks", "verify_results", "uat_results", "blockers", "artifacts"}, optional=set(), errors=errors)
        if _as_str(test.get("status")) not in EVIDENCE_STATUS:
            _err(errors, "planner_bundle_schema_error", f"{path}.test.status invalid")
        for key in ("checks", "verify_results", "uat_results", "blockers", "artifacts"):
            if not isinstance(test.get(key), list):
                _err(errors, "planner_bundle_schema_error", f"{path}.test.{key} must be list")

    review = _require_object(payload.get("review"), label=f"{path}.review", errors=errors)
    if review is not None:
        _strict_keys(review, label=f"{path}.review", required={"status", "decision", "blockers", "artifacts"}, optional=set(), errors=errors)
        if _as_str(review.get("status")) not in EVIDENCE_STATUS:
            _err(errors, "planner_bundle_schema_error", f"{path}.review.status invalid")
        _require_str_or_none(review.get("decision"), label=f"{path}.review.decision", errors=errors)
        for key in ("blockers", "artifacts"):
            if not isinstance(review.get(key), list):
                _err(errors, "planner_bundle_schema_error", f"{path}.review.{key} must be list")

    summary = _require_object(payload.get("summary"), label=f"{path}.summary", errors=errors)
    if summary is not None:
        _strict_keys(
            summary,
            label=f"{path}.summary",
            required={"result", "expectation", "expectation_met", "failure_class", "reason_codes"},
            optional=set(),
            errors=errors,
        )
        result = _as_str(summary.get("result"))
        if result not in EVIDENCE_RESULT:
            _err(errors, "planner_bundle_schema_error", f"{path}.summary.result must be one of pass|fail|blocked")
        expectation = _as_str(summary.get("expectation"))
        if expectation not in VERIFICATION_EXPECTATIONS:
            _err(errors, "planner_bundle_schema_error", f"{path}.summary.expectation must be expect_fail|expect_pass")
        _require_bool(summary.get("expectation_met"), label=f"{path}.summary.expectation_met", errors=errors)
        failure_class = _as_str(summary.get("failure_class"))
        if failure_class not in EVIDENCE_FAILURE_CLASS:
            _err(errors, "planner_bundle_schema_error", f"{path}.summary.failure_class must be expected_red|infra|unexpected|none")
        _require_str_list(summary.get("reason_codes"), label=f"{path}.summary.reason_codes", errors=errors)

    return plan_id, task_id


def _validate_text(path: str, artifact: BundleArtifact, errors: list[dict[str, object]]) -> None:
    if artifact.content_type != "text":
        _err(errors, "planner_bundle_schema_error", f"{path} must be text content_type")
        return
    text = artifact.content
    if not isinstance(text, str) or not text.strip():
        _err(errors, "planner_bundle_schema_error", f"{path} must be non-empty text")
        return
    header = TEXT_HEADINGS.get(path)
    if header and not text.lstrip().startswith(header):
        _err(errors, "planner_bundle_schema_error", f"{path} must start with heading '{header}'")


def validate_bundle_contract(bundle_path: Path, planning_root: Path) -> tuple[dict[str, BundleArtifact] | None, list[dict[str, object]]]:
    errors: list[dict[str, object]] = []
    try:
        bundle = parse_bundle_jsonl(bundle_path, planning_root)
    except PlannerError as exc:
        return None, [{"code": exc.code, "message": exc.message}]

    keys = set(bundle.keys())
    missing = sorted(REQUIRED_STATIC - keys)
    if missing:
        _err(errors, "planner_bundle_schema_error", "planner bundle missing required artifacts", missing=missing)

    unexpected = sorted(
        path
        for path in keys
        if path not in REQUIRED_STATIC
        and path not in OPTIONAL_STATIC
        and not (path.startswith("evidence/") and path.endswith("/TASK_EVIDENCE.json"))
    )
    if unexpected:
        _err(errors, "planner_bundle_schema_error", "planner bundle has unexpected artifacts", extra=unexpected)

    if errors:
        return None, errors

    plan_packets = _require_object(bundle["PLAN_PACKETS.json"].content, label="PLAN_PACKETS.json", errors=errors)
    plan_check = _require_object(bundle["PLAN_CHECK.json"].content, label="PLAN_CHECK.json", errors=errors)
    task_state = _require_object(bundle["TASK_EXECUTION_STATE.json"].content, label="TASK_EXECUTION_STATE.json", errors=errors)
    gaps_artifact = bundle.get("GAPS.json")
    gap_closure_artifact = bundle.get("GAP_CLOSURE_PLAN_PACKETS.json")
    gaps = _require_object(gaps_artifact.content, label="GAPS.json", errors=errors) if isinstance(gaps_artifact, BundleArtifact) else None
    gap_closure = _require_object(gap_closure_artifact.content, label="GAP_CLOSURE_PLAN_PACKETS.json", errors=errors) if isinstance(gap_closure_artifact, BundleArtifact) else None
    state_json = _require_object(bundle["STATE.json"].content, label="STATE.json", errors=errors)

    for text_path in TEXT_HEADINGS:
        _validate_text(text_path, bundle[text_path], errors)

    plan_id: str | None = None
    task_ids: list[str] = []
    req_ids: list[str] = []
    if plan_packets is not None:
        plan_id, task_ids, req_ids, _ = _validate_plan_packets(plan_packets, errors)
    if plan_check is not None:
        _validate_plan_check(plan_check, errors)

    state_plan_id = _validate_task_execution_state(task_state, set(task_ids), errors) if task_state is not None else None
    gaps_plan_id = _validate_gaps(gaps, errors) if gaps is not None else None
    closure_plan_id = _validate_gap_closure(gap_closure, errors) if gap_closure is not None else None
    state_json_plan_id = _validate_state_json(state_json, errors) if state_json is not None else None

    plan_ids = [value for value in [plan_id, state_plan_id, gaps_plan_id, closure_plan_id, state_json_plan_id] if value]
    if plan_ids and len(set(plan_ids)) != 1:
        _err(errors, "planner_bundle_schema_error", "plan_id must match across all planning artifacts", plan_ids=sorted(set(plan_ids)))

    evidence_keys = sorted(path for path in keys if path.startswith("evidence/") and path.endswith("/TASK_EVIDENCE.json"))
    evidence_expected = {f"evidence/{task_id}/TASK_EVIDENCE.json" for task_id in task_ids}
    missing_evidence = sorted(evidence_expected - set(evidence_keys))
    extra_evidence = sorted(set(evidence_keys) - evidence_expected)
    if missing_evidence:
        _err(errors, "planner_bundle_schema_error", "missing task evidence artifacts", missing=missing_evidence)
    if extra_evidence:
        _err(errors, "planner_bundle_schema_error", "unexpected task evidence artifacts", extra=extra_evidence)

    for path in evidence_keys:
        artifact = bundle[path]
        if artifact.content_type != "json":
            _err(errors, "planner_bundle_schema_error", f"{path} must be json content_type")
            continue
        payload = _require_object(artifact.content, label=path, errors=errors)
        if payload is None:
            continue
        evidence_plan_id, evidence_task_id = _validate_evidence(path, payload, errors)
        expected_task_id = path.split("/")[1] if "/" in path else None
        if expected_task_id and evidence_task_id and evidence_task_id != expected_task_id:
            _err(errors, "planner_bundle_schema_error", f"{path} task_id mismatch", expected_task_id=expected_task_id, actual_task_id=evidence_task_id)
        if plan_id and evidence_plan_id and evidence_plan_id != plan_id:
            _err(errors, "planner_bundle_schema_error", f"{path} plan_id mismatch", expected_plan_id=plan_id, actual_plan_id=evidence_plan_id)

    if req_ids and state_json is not None:
        state_reqs = state_json.get("requirements")
        if isinstance(state_reqs, list):
            state_req_ids = {
                _as_str(item.get("id"))
                for item in state_reqs
                if isinstance(item, dict) and _as_str(item.get("id"))
            }
            missing_from_state = sorted(set(req_ids) - state_req_ids)
            if missing_from_state:
                _err(errors, "planner_bundle_schema_error", "STATE.requirements missing requirement IDs", missing=missing_from_state)
        else:
            _err(errors, "planner_bundle_schema_error", "STATE.requirements must be list")

    return (None, errors) if errors else (bundle, [])


def validate(bundle_path: Path, planning_root: Path) -> tuple[bool, list[dict[str, object]]]:
    _bundle, errors = validate_bundle_contract(bundle_path, planning_root)
    return len(errors) == 0, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate OP planner JSONL bundle")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--bundle-path", required=True)
    args = parser.parse_args()

    repo_root = Path(args.repo_root).expanduser().resolve()
    bundle_path = Path(args.bundle_path).expanduser().resolve()
    planning_root = (repo_root / "reports" / "optimus-prime" / "planning").resolve()

    ok, errors = validate(bundle_path, planning_root)
    out = {
        "schema_version": "1.0",
        "ok": ok,
        "errors": errors,
        "bundle_path": str(bundle_path),
    }
    print(json.dumps(out, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
