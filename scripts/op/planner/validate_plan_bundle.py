#!/usr/bin/env python3
"""Validate planner JSONL bundle contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
OP_ROOT = SCRIPT_DIR.parent
if str(OP_ROOT) not in sys.path:
    sys.path.insert(0, str(OP_ROOT))

from planner.llm_planner import PlannerError, parse_bundle_jsonl

REQUIRED = {
    "PLAN_PACKETS.json",
    "PLAN_CHECK.json",
    "TASK_EXECUTION_STATE.json",
    "GAPS.json",
    "GAP_CLOSURE_PLAN_PACKETS.json",
    "TEST_CONTRACT.md",
    "PLAYWRIGHT_UAT_MATRIX.md",
    "VERIFICATION.md",
    "UAT.md",
    "STATE.json",
    "STATE.md",
}


def _as_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def validate(bundle_path: Path, planning_root: Path) -> tuple[bool, list[dict[str, object]]]:
    errors: list[dict[str, object]] = []
    try:
        bundle = parse_bundle_jsonl(bundle_path, planning_root)
    except PlannerError as exc:
        errors.append({"code": exc.code, "message": exc.message})
        return False, errors

    keys = set(bundle.keys())
    missing = sorted(REQUIRED - keys)
    if missing:
        errors.append({"code": "planner_bundle_schema_error", "message": "missing required artifacts", "missing": missing})

    plan = bundle.get("PLAN_PACKETS.json")
    task_state = bundle.get("TASK_EXECUTION_STATE.json")
    if plan and isinstance(plan.content, dict):
        tasks = plan.content.get("tasks")
        if not isinstance(tasks, list) or not tasks:
            errors.append({"code": "planner_bundle_schema_error", "message": "PLAN_PACKETS.tasks must be non-empty list"})
        else:
            task_ids = []
            for item in tasks:
                if not isinstance(item, dict):
                    continue
                task_id = _as_str(item.get("task_id"))
                if task_id:
                    task_ids.append(task_id)
                    evidence_path = f"evidence/{task_id}/TASK_EVIDENCE.json"
                    if evidence_path not in keys:
                        errors.append({
                            "code": "planner_bundle_schema_error",
                            "message": "missing task evidence artifact",
                            "task_id": task_id,
                            "artifact": evidence_path,
                        })
            requirements = plan.content.get("requirements")
            if not isinstance(requirements, list) or not requirements:
                errors.append({"code": "planner_bundle_schema_error", "message": "PLAN_PACKETS.requirements must be non-empty list"})
            if task_state and isinstance(task_state.content, dict):
                rows = task_state.content.get("tasks")
                if isinstance(rows, list):
                    state_ids = {
                        _as_str(row.get("task_id"))
                        for row in rows
                        if isinstance(row, dict) and _as_str(row.get("task_id"))
                    }
                    missing_state = sorted([task_id for task_id in task_ids if task_id not in state_ids])
                    if missing_state:
                        errors.append({
                            "code": "planner_bundle_schema_error",
                            "message": "TASK_EXECUTION_STATE missing task ids",
                            "missing_task_ids": missing_state,
                        })
                else:
                    errors.append({"code": "planner_bundle_schema_error", "message": "TASK_EXECUTION_STATE.tasks must be list"})

    plan_check = bundle.get("PLAN_CHECK.json")
    if plan_check and isinstance(plan_check.content, dict):
        if not bool(plan_check.content.get("passed")):
            errors.append({"code": "planner_plan_check_failed", "message": "PLAN_CHECK.passed must be true"})

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
