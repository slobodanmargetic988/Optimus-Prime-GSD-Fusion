#!/usr/bin/env python3
"""Core implementation for OP command surface."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from op_router import SUPPORTED_COMMANDS, normalize_command

SCHEMA_VERSION = "1.0"
TOOL = "opctl"
TOOL_VERSION = "0.1.0"

PLANNING_REL = Path("reports") / "optimus-prime" / "planning"
MAP_PATH = PLANNING_REL / "MAP_CODEBASE.json"
MAP_MD_PATH = PLANNING_REL / "MAP_CODEBASE.md"
INDEX_PATH = PLANNING_REL / "CODEBASE_INDEX.json"
ARCH_PATH = PLANNING_REL / "ARCHITECTURE_NOTES.md"
RISK_PATH = PLANNING_REL / "RISK_REGISTER.json"

PROJECT_MD = PLANNING_REL / "PROJECT.md"
REQUIREMENTS_MD = PLANNING_REL / "REQUIREMENTS.md"
ROADMAP_MD = PLANNING_REL / "ROADMAP.md"
STATE_MD = PLANNING_REL / "STATE.md"
STATE_JSON = PLANNING_REL / "STATE.json"

PLAN_PACKETS_JSON = PLANNING_REL / "PLAN_PACKETS.json"
PLAN_CHECK_JSON = PLANNING_REL / "PLAN_CHECK.json"
TEST_CONTRACT_MD = PLANNING_REL / "TEST_CONTRACT.md"
PLAYWRIGHT_UAT_MD = PLANNING_REL / "PLAYWRIGHT_UAT_MATRIX.md"
GAPS_JSON = PLANNING_REL / "GAPS.json"
GAP_CLOSURE_PLAN_PACKETS_JSON = PLANNING_REL / "GAP_CLOSURE_PLAN_PACKETS.json"
VERIFICATION_MD = PLANNING_REL / "VERIFICATION.md"
UAT_MD = PLANNING_REL / "UAT.md"
EVIDENCE_REL = PLANNING_REL / "evidence"

BUILD_STATE_JSON = PLANNING_REL / "BUILD_STATE.json"
TASK_EXECUTION_STATE_JSON = PLANNING_REL / "TASK_EXECUTION_STATE.json"
BUILD_LOOP_LOCK = PLANNING_REL / "BUILD_LOOP.lock"

MANDATORY_BUILD_BASELINE = [
    PROJECT_MD,
    REQUIREMENTS_MD,
    ROADMAP_MD,
    STATE_MD,
    STATE_JSON,
    PLAN_PACKETS_JSON,
    PLAN_CHECK_JSON,
    TEST_CONTRACT_MD,
    PLAYWRIGHT_UAT_MD,
    GAPS_JSON,
    GAP_CLOSURE_PLAN_PACKETS_JSON,
    VERIFICATION_MD,
    UAT_MD,
    TASK_EXECUTION_STATE_JSON,
]

STRATEGY_LADDER = [
    "self_heal",
    "runtime_repair",
    "targeted_replan",
    "alternate_implementation",
    "blocker_escalation",
]

TERMINAL_HARD_STOPS = {
    "insurmountable_blocker",
    "all_rate_gates_blocking",
    "operator_stop",
}


class OpError(Exception):
    def __init__(self, code: str, message: str, stage: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.stage = stage


@dataclass
class OpRequest:
    command: str
    repo_root: Path
    mission: str | None
    scope: str | None
    constraints: list[str]
    non_interactive: bool
    output_mode: str
    max_build_cycles: int | None
    sleep_minutes: float
    dry_run: bool


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    text = str(value).strip()
    return text or None


def _as_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return default


def _coerce_nonneg_int(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def _as_constraints(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = [item.strip() for item in value.split(";")]
        return [item for item in parts if item]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
            elif item is not None:
                out.append(str(item).strip())
        return [item for item in out if item]
    return [str(value).strip()]


def _repo_path(repo_root: Path, rel: Path) -> Path:
    return (repo_root / rel).resolve()


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _atomic_write_json(path: Path, payload: Any) -> None:
    _ensure_parent(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _write_text(path: Path, text: str) -> None:
    _ensure_parent(path)
    path.write_text(text, encoding="utf-8")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise OpError("state_read_error", f"invalid JSON at {path}: {exc}", stage="state") from exc
    except OSError as exc:
        raise OpError("state_read_error", f"unable to read {path}: {exc}", stage="state") from exc


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    except OSError as exc:
        raise OpError("state_read_error", f"unable to read {path}: {exc}", stage="state") from exc
    return rows


def _parse_iso_utc(value: Any) -> datetime | None:
    text = _as_str(value)
    if not text:
        return None
    raw = text.strip()
    try:
        if raw.endswith("Z"):
            dt = datetime.fromisoformat(raw[:-1] + "+00:00")
        else:
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _acquire_build_loop_lock(lock_path: Path) -> tuple[bool, str, int | None]:
    _ensure_parent(lock_path)
    now = utc_now_iso()
    pid = os.getpid()
    lock_id = f"op-build-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    if lock_path.exists():
        try:
            existing = _read_json(lock_path)
        except OpError:
            existing = None
        if isinstance(existing, dict):
            active_pid = existing.get("pid")
            if isinstance(active_pid, int) and _pid_is_running(active_pid):
                return False, lock_id, active_pid
        try:
            lock_path.unlink()
        except OSError:
            pass
    payload = {
        "schema_version": SCHEMA_VERSION,
        "lock_id": lock_id,
        "pid": pid,
        "acquired_at": now,
    }
    _atomic_write_json(lock_path, payload)
    return True, lock_id, None


def _release_build_loop_lock(lock_path: Path, lock_id: str | None) -> None:
    if not lock_path.exists():
        return
    if lock_id is None:
        try:
            lock_path.unlink()
        except OSError:
            pass
        return
    try:
        payload = _read_json(lock_path)
    except OpError:
        payload = None
    if isinstance(payload, dict) and _as_str(payload.get("lock_id")) not in {None, lock_id}:
        return
    try:
        lock_path.unlink()
    except OSError:
        pass


def _canonical_task_evidence_rel(task_id: str) -> Path:
    return EVIDENCE_REL / task_id / "TASK_EVIDENCE.json"


def _default_task_evidence(plan_id: str, phase_id: str, task_id: str, requirement_ids: list[str]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "plan_id": plan_id,
        "phase_id": phase_id,
        "task_id": task_id,
        "requirement_ids": requirement_ids,
        "updated_at": utc_now_iso(),
        "dev": {
            "status": "pending",
            "checks": [],
            "verify_results": [],
            "dev_ready": False,
            "blockers": [],
            "artifacts": [],
        },
        "test": {
            "status": "pending",
            "checks": [],
            "verify_results": [],
            "uat_results": [],
            "blockers": [],
            "artifacts": [],
        },
        "review": {
            "status": "pending",
            "decision": "pending",
            "blockers": [],
            "artifacts": [],
        },
        "gate": {
            "ready_for_test": False,
            "ready_for_review": False,
            "ready_for_phase_exit": False,
        },
        "summary": {
            "result": "blocked",
            "reason_codes": ["not_started"],
        },
    }


def _write_task_evidence_files(repo_root: Path, plan_packets: dict[str, Any]) -> dict[str, str]:
    refs: dict[str, str] = {}
    plan_id = _as_str(plan_packets.get("plan_id")) or "plan-unknown"
    for task in plan_packets.get("tasks", []):
        if not isinstance(task, dict):
            continue
        task_id = _as_str(task.get("task_id"))
        if not task_id:
            continue
        phase_id = _as_str(task.get("phase_id")) or "phase-1"
        req_ids = [
            rid
            for rid in ((_as_str(item) for item in task.get("requirement_ids", [])))
            if rid
        ]
        rel = _canonical_task_evidence_rel(task_id)
        abs_path = _repo_path(repo_root, rel)
        payload = _default_task_evidence(plan_id, phase_id, task_id, req_ids)
        _atomic_write_json(abs_path, payload)
        refs[task_id] = str(rel)
    return refs


def _task_state_from_plan(plan_packets: dict[str, Any], evidence_refs: dict[str, str] | None = None) -> dict[str, Any]:
    tasks = plan_packets.get("tasks") if isinstance(plan_packets.get("tasks"), list) else []
    out_tasks: list[dict[str, Any]] = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = _as_str(task.get("task_id"))
        if not task_id:
            continue
        phase_id = _as_str(task.get("phase_id")) or "phase-1"
        req_ids = []
        for rid in task.get("requirement_ids", []):
            rid_text = _as_str(rid)
            if rid_text:
                req_ids.append(rid_text)
        evidence_ref = (
            evidence_refs.get(task_id)
            if isinstance(evidence_refs, dict)
            else str(_canonical_task_evidence_rel(task_id))
        )
        out_tasks.append(
            {
                "task_id": task_id,
                "phase_id": phase_id,
                "requirement_ids": req_ids,
                "status": "queued",
                "owner_slot": None,
                "attempts": {"dev": 0, "test": 0, "review": 0},
                "evidence": {
                    "task_evidence_ref": evidence_ref,
                    "dev_ready_evidence_ref": evidence_ref,
                    "verify_results": [],
                    "uat_results": [],
                },
                "blockers": [],
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "plan_id": _as_str(plan_packets.get("plan_id")),
        "updated_at": utc_now_iso(),
        "tasks": out_tasks,
    }


def _validate_task_execution_state(task_state: dict[str, Any], plan_packets: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    tasks = task_state.get("tasks")
    if not isinstance(tasks, list):
        errors.append({"code": "task_state_invalid", "message": "TASK_EXECUTION_STATE.tasks must be a list"})
        return errors
    allowed = {
        "queued",
        "dev_in_progress",
        "dev_done",
        "test_in_progress",
        "test_done",
        "review_in_progress",
        "review_done",
        "blocked",
    }
    seen: set[str] = set()
    plan_phase_ids: set[str] = set()
    for phase in plan_packets.get("phases", []):
        if not isinstance(phase, dict):
            continue
        phase_id = _as_str(phase.get("phase_id"))
        if phase_id:
            plan_phase_ids.add(phase_id)
    for item in tasks:
        if not isinstance(item, dict):
            errors.append({"code": "task_state_invalid", "message": "task entries must be objects"})
            continue
        task_id = _as_str(item.get("task_id"))
        if not task_id:
            errors.append({"code": "task_state_invalid", "message": "task_id is required"})
            continue
        seen.add(task_id)
        status = _as_str(item.get("status")) or ""
        if status not in allowed:
            errors.append({"code": "task_state_invalid", "message": f"task {task_id} has invalid status {status}"})
        phase_id = _as_str(item.get("phase_id"))
        if not phase_id:
            errors.append({"code": "task_state_invalid", "message": f"task {task_id} phase_id is required"})
        elif plan_phase_ids and phase_id not in plan_phase_ids:
            errors.append({"code": "task_state_invalid", "message": f"task {task_id} phase_id not found in plan phases"})
        attempts = item.get("attempts")
        if not isinstance(attempts, dict):
            errors.append({"code": "task_state_invalid", "message": f"task {task_id} attempts must be object"})
            continue
        for key in ("dev", "test", "review"):
            value = attempts.get(key)
            if not isinstance(value, int) or value < 0:
                errors.append({"code": "task_state_invalid", "message": f"task {task_id} attempts.{key} must be >=0 int"})
        evidence = item.get("evidence")
        if not isinstance(evidence, dict):
            errors.append({"code": "task_state_invalid", "message": f"task {task_id} evidence must be object"})
            continue
        task_evidence_ref = _as_str(evidence.get("task_evidence_ref"))
        if not task_evidence_ref:
            errors.append({"code": "task_state_invalid", "message": f"task {task_id} evidence.task_evidence_ref is required"})
        for key in ("verify_results", "uat_results"):
            val = evidence.get(key)
            if not isinstance(val, list):
                errors.append({"code": "task_state_invalid", "message": f"task {task_id} evidence.{key} must be list"})
    expected_task_ids = []
    for task in plan_packets.get("tasks", []):
        if isinstance(task, dict):
            task_id = _as_str(task.get("task_id"))
            if task_id:
                expected_task_ids.append(task_id)
    missing = [task_id for task_id in expected_task_ids if task_id not in seen]
    if missing:
        errors.append(
            {
                "code": "task_state_plan_mismatch",
                "message": "TASK_EXECUTION_STATE missing plan task IDs",
                "missing_task_ids": missing,
            }
        )
    return errors


def _extract_cycle_directives(events_path: Path, cycle_number: int) -> list[dict[str, Any]]:
    rows = _read_jsonl(events_path)
    out: list[dict[str, Any]] = []
    for row in rows:
        if int(row.get("cycle_number") or 0) != int(cycle_number):
            continue
        if _as_str(row.get("event_type")) != "directive":
            continue
        payload = row.get("payload")
        if isinstance(payload, dict):
            out.append(payload)
    return out


def _task_by_id(task_state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in task_state.get("tasks", []):
        if not isinstance(item, dict):
            continue
        task_id = _as_str(item.get("task_id"))
        if task_id:
            out[task_id] = item
    return out


def _run_tool_json(script: Path, payload: dict[str, Any], cwd: Path) -> dict[str, Any]:
    if not script.exists():
        return {"ok": False, "error": "script_missing", "message": f"script not found: {script}"}
    code, out, err = _run([sys.executable, str(script), "--input-json", "-"], cwd=cwd, stdin_text=json.dumps(payload))
    raw = out.strip()
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                parsed.setdefault("exit_code", code)
                return parsed
        except json.JSONDecodeError:
            pass
    return {"ok": False, "error": "runtime_error", "message": err.strip() or raw or "tool execution failed", "exit_code": code}


def _as_bool_field(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on", "passed", "ok", "success"}
    return False


def _plan_task_map(plan_packets: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for task in plan_packets.get("tasks", []):
        if not isinstance(task, dict):
            continue
        task_id = _as_str(task.get("task_id"))
        if task_id:
            out[task_id] = task
    return out


def _phase_map(plan_packets: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for phase in plan_packets.get("phases", []):
        if not isinstance(phase, dict):
            continue
        phase_id = _as_str(phase.get("phase_id"))
        if phase_id:
            out[phase_id] = phase
    return out


def _ordered_phase_ids(plan_packets: dict[str, Any]) -> list[str]:
    phase_ids = [phase_id for phase_id in _phase_map(plan_packets)]
    def _sort_key(value: str) -> tuple[int, str]:
        tail = value.split("-")[-1]
        return (int(tail), value) if tail.isdigit() else (10_000, value)
    return sorted(phase_ids, key=_sort_key)


def _task_evidence_path(repo_root: Path, task: dict[str, Any]) -> Path:
    evidence = task.get("evidence") if isinstance(task.get("evidence"), dict) else {}
    ref = _as_str(evidence.get("task_evidence_ref"))
    if ref:
        return (repo_root / ref).resolve()
    task_id = _as_str(task.get("task_id")) or "TASK-UNKNOWN"
    return _repo_path(repo_root, _canonical_task_evidence_rel(task_id))


def _validate_task_evidence_payload(payload: dict[str, Any], task_id: str, phase_id: str) -> list[str]:
    errors: list[str] = []
    if _as_str(payload.get("task_id")) != task_id:
        errors.append("task_id mismatch")
    if _as_str(payload.get("phase_id")) != phase_id:
        errors.append("phase_id mismatch")
    for section in ("dev", "test", "review", "gate", "summary"):
        if not isinstance(payload.get(section), dict):
            errors.append(f"missing section '{section}'")
    dev = payload.get("dev") if isinstance(payload.get("dev"), dict) else {}
    test = payload.get("test") if isinstance(payload.get("test"), dict) else {}
    review = payload.get("review") if isinstance(payload.get("review"), dict) else {}
    gate = payload.get("gate") if isinstance(payload.get("gate"), dict) else {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    for key in ("checks", "verify_results", "blockers", "artifacts"):
        if not isinstance(dev.get(key), list):
            errors.append(f"dev.{key} must be list")
    for key in ("checks", "verify_results", "uat_results", "blockers", "artifacts"):
        if not isinstance(test.get(key), list):
            errors.append(f"test.{key} must be list")
    for key in ("blockers", "artifacts"):
        if not isinstance(review.get(key), list):
            errors.append(f"review.{key} must be list")
    for key in ("ready_for_test", "ready_for_review", "ready_for_phase_exit"):
        if not isinstance(gate.get(key), bool):
            errors.append(f"gate.{key} must be bool")
    if (_as_str(summary.get("result")) or "").lower() not in {"pass", "fail", "blocked"}:
        errors.append("summary.result must be pass|fail|blocked")
    if not isinstance(summary.get("reason_codes"), list):
        errors.append("summary.reason_codes must be list")
    return errors


def _collect_passed_verify_commands(evidence_payload: dict[str, Any]) -> set[str]:
    passed: set[str] = set()
    for section in ("dev", "test"):
        block = evidence_payload.get(section) if isinstance(evidence_payload.get(section), dict) else {}
        rows = block.get("verify_results")
        if not isinstance(rows, list):
            continue
        for item in rows:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    passed.add(text)
                continue
            if isinstance(item, dict) and _as_bool_field(item.get("passed")):
                cmd = _as_str(item.get("command"))
                if cmd:
                    passed.add(cmd)
    return passed


def _collect_passed_uat_requirement_ids(evidence_payload: dict[str, Any], fallback_requirement_ids: list[str]) -> set[str]:
    passed: set[str] = set()
    test = evidence_payload.get("test") if isinstance(evidence_payload.get("test"), dict) else {}
    rows = test.get("uat_results")
    if not isinstance(rows, list):
        return passed
    for item in rows:
        if not isinstance(item, dict):
            continue
        if not _as_bool_field(item.get("passed")):
            continue
        requirement_id = _as_str(item.get("requirement_id"))
        if requirement_id:
            passed.add(requirement_id)
        requirement_ids = item.get("requirement_ids")
        if isinstance(requirement_ids, list):
            for value in requirement_ids:
                rid = _as_str(value)
                if rid:
                    passed.add(rid)
        if not requirement_id:
            for rid in fallback_requirement_ids:
                passed.add(rid)
    return passed


def _sync_task_state_from_evidence(repo_root: Path, plan_packets: dict[str, Any], task_state: dict[str, Any]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    plan_map = _plan_task_map(plan_packets)
    for task in task_state.get("tasks", []):
        if not isinstance(task, dict):
            continue
        task_id = _as_str(task.get("task_id"))
        phase_id = _as_str(task.get("phase_id")) or "phase-1"
        if not task_id:
            continue
        evidence_path = _task_evidence_path(repo_root, task)
        if not evidence_path.exists():
            task["status"] = "blocked"
            warnings.append(
                {
                    "code": "task_evidence_missing",
                    "message": f"missing TASK_EVIDENCE.json for {task_id}: {evidence_path}",
                    "stage": "build_loop",
                }
            )
            continue
        try:
            payload = _read_json(evidence_path)
        except OpError as exc:
            task["status"] = "blocked"
            warnings.append(
                {
                    "code": "task_evidence_invalid",
                    "message": f"invalid TASK_EVIDENCE.json for {task_id}: {exc.message}",
                    "stage": "build_loop",
                }
            )
            continue
        if not isinstance(payload, dict):
            task["status"] = "blocked"
            warnings.append(
                {
                    "code": "task_evidence_invalid",
                    "message": f"TASK_EVIDENCE.json for {task_id} must be object JSON",
                    "stage": "build_loop",
                }
            )
            continue
        validation_errors = _validate_task_evidence_payload(payload, task_id, phase_id)
        if validation_errors:
            task["status"] = "blocked"
            warnings.append(
                {
                    "code": "task_evidence_invalid",
                    "message": f"TASK_EVIDENCE schema invalid for {task_id}",
                    "stage": "build_loop",
                    "details": validation_errors,
                }
            )
            continue

        evidence = task.get("evidence")
        if not isinstance(evidence, dict):
            evidence = {}
            task["evidence"] = evidence
        evidence_ref = str(evidence_path.relative_to(repo_root))
        evidence["task_evidence_ref"] = evidence_ref
        evidence["dev_ready_evidence_ref"] = evidence_ref

        verify_results = []
        for section in ("dev", "test"):
            block = payload.get(section) if isinstance(payload.get(section), dict) else {}
            rows = block.get("verify_results")
            if isinstance(rows, list):
                verify_results.extend(rows)
        evidence["verify_results"] = verify_results
        test_block = payload.get("test") if isinstance(payload.get("test"), dict) else {}
        evidence["uat_results"] = test_block.get("uat_results") if isinstance(test_block.get("uat_results"), list) else []

        gate = payload["gate"]
        review = payload["review"]
        summary = payload["summary"]
        if _as_bool_field(gate.get("ready_for_review")):
            task["status"] = "test_done"
            task["owner_slot"] = None
        if (_as_str(review.get("decision")) or "").lower() in {"accepted", "approved", "ready_for_merge", "pass"}:
            task["status"] = "review_done"
            task["owner_slot"] = None
        if (_as_str(review.get("status")) or "").lower() in {"done", "completed", "review_done"}:
            task["status"] = "review_done"
            task["owner_slot"] = None
        if _as_bool_field(gate.get("ready_for_test")) and (_as_str(task.get("status")) or "") in {"queued", "dev_in_progress", "blocked"}:
            task["status"] = "dev_done"
            task["owner_slot"] = None
        summary_result = (_as_str(summary.get("result")) or "").lower()
        reason_codes = summary.get("reason_codes") if isinstance(summary.get("reason_codes"), list) else []
        is_not_started_placeholder = summary_result == "blocked" and any(
            _as_str(item) == "not_started" for item in reason_codes
        )
        if summary_result in {"fail", "blocked"} and not is_not_started_placeholder and (_as_str(task.get("status")) or "") not in {"review_done"}:
            if not _as_bool_field(gate.get("ready_for_test")) and not _as_bool_field(gate.get("ready_for_review")):
                task["status"] = "blocked"
                task["owner_slot"] = None

        plan_task = plan_map.get(task_id) if isinstance(plan_map.get(task_id), dict) else {}
        if isinstance(plan_task, dict) and not task.get("requirement_ids"):
            task["requirement_ids"] = [
                rid
                for rid in ((_as_str(item) for item in plan_task.get("requirement_ids", [])))
                if rid
            ]
    return warnings


def _load_gaps_payload(path: Path, plan_id: str) -> dict[str, Any]:
    if not path.exists():
        return {
            "schema_version": SCHEMA_VERSION,
            "plan_id": plan_id,
            "updated_at": utc_now_iso(),
            "gaps": [],
        }
    try:
        payload = _read_json(path)
    except OpError:
        return {
            "schema_version": SCHEMA_VERSION,
            "plan_id": plan_id,
            "updated_at": utc_now_iso(),
            "gaps": [],
        }
    if not isinstance(payload, dict):
        return {
            "schema_version": SCHEMA_VERSION,
            "plan_id": plan_id,
            "updated_at": utc_now_iso(),
            "gaps": [],
        }
    gaps = payload.get("gaps")
    if not isinstance(gaps, list):
        payload["gaps"] = []
    payload.setdefault("schema_version", SCHEMA_VERSION)
    payload["plan_id"] = _as_str(payload.get("plan_id")) or plan_id
    payload["updated_at"] = utc_now_iso()
    return payload


def _gap_id(plan_id: str, phase_id: str, task_id: str, scope_key: str, result: str) -> str:
    digest = _sha256(f"{plan_id}|{phase_id}|{task_id}|{scope_key}|{result}")[:10]
    return f"gap-{digest}"


def _refresh_gap_artifacts(repo_root: Path, plan_packets: dict[str, Any], task_state: dict[str, Any], build_state: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    plan_id = _as_str(plan_packets.get("plan_id")) or "plan-unknown"
    task_map = _task_by_id(task_state)
    plan_task_map = _plan_task_map(plan_packets)
    retry_attempts = build_state.get("gap_retry_attempts")
    if not isinstance(retry_attempts, dict):
        retry_attempts = {}
        build_state["gap_retry_attempts"] = retry_attempts
    exhausted_ids_raw = build_state.get("gap_retry_exhausted_ids")
    exhausted_ids = (
        [item for item in (_as_str(v) for v in exhausted_ids_raw) if item]
        if isinstance(exhausted_ids_raw, list)
        else []
    )
    exhausted_set = set(exhausted_ids)
    build_state["gap_retry_exhausted_ids"] = sorted(exhausted_set)
    retry_policy = build_state.get("gap_retry_policy")
    if not isinstance(retry_policy, dict):
        retry_policy = {"max_attempts": 5}
        build_state["gap_retry_policy"] = retry_policy
    max_retry_attempts = _coerce_nonneg_int(retry_policy.get("max_attempts"), default=5)
    build_state["gap_retry_policy"] = {"max_attempts": max(1, max_retry_attempts)}
    gaps_path = _repo_path(repo_root, GAPS_JSON)
    existing = _load_gaps_payload(gaps_path, plan_id)
    existing_by_id: dict[str, dict[str, Any]] = {}
    for item in existing.get("gaps", []):
        if not isinstance(item, dict):
            continue
        gap_id = _as_str(item.get("gap_id"))
        if gap_id:
            existing_by_id[gap_id] = dict(item)

    active_gap_ids: set[str] = set()
    active_rows: dict[str, dict[str, Any]] = {}
    for task_id, plan_task in plan_task_map.items():
        if not isinstance(plan_task, dict):
            continue
        task = task_map.get(task_id)
        if not isinstance(task, dict):
            continue
        if bool(task.get("is_gap_closure")) or bool(plan_task.get("is_gap_closure")):
            continue
        phase_id = _as_str(plan_task.get("phase_id")) or _as_str(task.get("phase_id")) or "phase-1"
        task_status = _as_str(task.get("status")) or "queued"
        evidence = task.get("evidence") if isinstance(task.get("evidence"), dict) else {}
        evidence_ref = _as_str(evidence.get("task_evidence_ref")) or str(_canonical_task_evidence_rel(task_id))
        verify_required = {
            cmd
            for cmd in ((_as_str(item) for item in plan_task.get("verify_commands", [])))
            if cmd
        }
        verify_passed = set()
        for item in evidence.get("verify_results", []):
            if isinstance(item, str):
                text = item.strip()
                if text:
                    verify_passed.add(text)
            elif isinstance(item, dict) and _as_bool_field(item.get("passed")):
                cmd = _as_str(item.get("command"))
                if cmd:
                    verify_passed.add(cmd)
        if task_status in {"test_done", "review_done", "blocked"}:
            for cmd in sorted(verify_required - verify_passed):
                gap_id = _gap_id(plan_id, phase_id, task_id, f"verify:{cmd}", "fail")
                active_gap_ids.add(gap_id)
                active_rows[gap_id] = {
                    "gap_id": gap_id,
                    "phase_id": phase_id,
                    "task_id": task_id,
                    "requirement_id": None,
                    "severity": "high",
                    "result": "fail",
                    "evidence_ref": evidence_ref,
                    "opened_at": utc_now_iso(),
                    "status": "open",
                    "reason": f"verify command not passed: {cmd}",
                }

        requirement_ids = [
            rid
            for rid in ((_as_str(item) for item in plan_task.get("requirement_ids", [])))
            if rid
        ]
        passed_uat: set[str] = set()
        for item in evidence.get("uat_results", []):
            if not isinstance(item, dict) or not _as_bool_field(item.get("passed")):
                continue
            rid = _as_str(item.get("requirement_id"))
            if rid:
                passed_uat.add(rid)
            rids = item.get("requirement_ids")
            if isinstance(rids, list):
                for rid_item in rids:
                    rid_text = _as_str(rid_item)
                    if rid_text:
                        passed_uat.add(rid_text)
        if task_status in {"review_done", "blocked"}:
            for rid in sorted(set(requirement_ids) - passed_uat):
                gap_id = _gap_id(plan_id, phase_id, task_id, f"uat:{rid}", "blocked")
                active_gap_ids.add(gap_id)
                active_rows[gap_id] = {
                    "gap_id": gap_id,
                    "phase_id": phase_id,
                    "task_id": task_id,
                    "requirement_id": rid,
                    "severity": "high",
                    "result": "blocked",
                    "evidence_ref": evidence_ref,
                    "opened_at": utc_now_iso(),
                    "status": "open",
                    "reason": f"UAT requirement not passed: {rid}",
                }

        if (_as_str(task.get("status")) or "") == "blocked":
            gap_id = _gap_id(plan_id, phase_id, task_id, "task:blocked", "blocked")
            active_gap_ids.add(gap_id)
            active_rows[gap_id] = {
                "gap_id": gap_id,
                "phase_id": phase_id,
                "task_id": task_id,
                "requirement_id": None,
                "severity": "high",
                "result": "blocked",
                "evidence_ref": evidence_ref,
                "opened_at": utc_now_iso(),
                "status": "open",
                "reason": "task state blocked",
            }

    merged_gaps: list[dict[str, Any]] = []
    for gap_id, row in active_rows.items():
        prior = existing_by_id.get(gap_id, {})
        merged = dict(row)
        merged["opened_at"] = _as_str(prior.get("opened_at")) or row["opened_at"]
        merged["updated_at"] = utc_now_iso()
        merged["status"] = "open"
        retry_count = _coerce_nonneg_int(retry_attempts.get(gap_id, 0), default=0)
        is_escalated = gap_id in exhausted_set
        merged["retry_count"] = max(0, retry_count)
        merged["escalated"] = is_escalated
        merged["escalated_at"] = (
            _as_str(prior.get("escalated_at")) or utc_now_iso()
            if is_escalated
            else None
        )
        merged_gaps.append(merged)
    for gap_id, prior in existing_by_id.items():
        if gap_id in active_gap_ids:
            continue
        prior = dict(prior)
        prior["status"] = "closed"
        prior["updated_at"] = utc_now_iso()
        prior.setdefault("closed_at", utc_now_iso())
        prior.setdefault("retry_count", 0)
        prior.setdefault("escalated", False)
        prior.setdefault("escalated_at", None)
        merged_gaps.append(prior)
    merged_gaps.sort(key=lambda item: (_as_str(item.get("status")) != "open", _as_str(item.get("gap_id")) or ""))
    gaps_payload = {
        "schema_version": SCHEMA_VERSION,
        "plan_id": plan_id,
        "updated_at": utc_now_iso(),
        "gaps": merged_gaps,
    }
    _atomic_write_json(gaps_path, gaps_payload)

    open_gap_rows = [item for item in merged_gaps if _as_str(item.get("status")) == "open"]
    active_open_gap_ids = {_as_str(item.get("gap_id")) for item in open_gap_rows if _as_str(item.get("gap_id"))}
    for gap_id in list(retry_attempts.keys()):
        if gap_id not in active_open_gap_ids:
            retry_attempts.pop(gap_id, None)
    build_state["gap_retry_exhausted_ids"] = sorted(gap_id for gap_id in exhausted_set if gap_id in active_open_gap_ids)
    closure_tasks: list[dict[str, Any]] = []
    for gap in sorted(open_gap_rows, key=lambda item: _as_str(item.get("gap_id")) or ""):
        gap_id = _as_str(gap.get("gap_id"))
        phase_id = _as_str(gap.get("phase_id")) or "phase-1"
        task_id = _as_str(gap.get("task_id")) or "TASK-UNKNOWN"
        requirement_id = _as_str(gap.get("requirement_id"))
        if not gap_id:
            continue
        closure_task_id = f"GAPFIX-{_sha256(gap_id)[:8].upper()}"
        req_ids = [requirement_id] if requirement_id else []
        closure_tasks.append(
            {
                "task_id": closure_task_id,
                "phase_id": phase_id,
                "source_gap_id": gap_id,
                "title": f"Close gap {gap_id}",
                "requirement_ids": req_ids,
                "depends_on": [task_id],
                "must_haves": [f"Resolve {gap.get('reason') or gap_id}"],
                "verify_commands": ["python3 -m pytest"],
                "is_gap_closure": True,
            }
        )
    closure_payload = {
        "schema_version": SCHEMA_VERSION,
        "plan_id": plan_id,
        "generated_at": utc_now_iso(),
        "tasks": closure_tasks,
    }
    _atomic_write_json(_repo_path(repo_root, GAP_CLOSURE_PLAN_PACKETS_JSON), closure_payload)

    build_state["open_gap_ids"] = sorted([_as_str(item.get("gap_id")) for item in open_gap_rows if _as_str(item.get("gap_id"))])
    build_state["last_gap_generation_at"] = utc_now_iso()
    if open_gap_rows:
        build_state["active_gap_closure_phase_id"] = _as_str(open_gap_rows[0].get("phase_id")) or "phase-1"
    else:
        build_state["active_gap_closure_phase_id"] = None
    return gaps_payload, closure_payload


def _merge_plan_with_gap_closure(plan_packets: dict[str, Any], gap_closure_payload: dict[str, Any]) -> dict[str, Any]:
    merged = dict(plan_packets)
    base_tasks = [task for task in plan_packets.get("tasks", []) if isinstance(task, dict)]
    gap_tasks = [task for task in gap_closure_payload.get("tasks", []) if isinstance(task, dict)]
    task_ids = {_as_str(task.get("task_id")) for task in base_tasks if _as_str(task.get("task_id"))}
    merged_tasks = list(base_tasks)
    for task in gap_tasks:
        task_id = _as_str(task.get("task_id"))
        if not task_id or task_id in task_ids:
            continue
        merged_tasks.append(task)
        task_ids.add(task_id)
    merged["tasks"] = merged_tasks
    return merged


def _ensure_gap_closure_task_state(repo_root: Path, task_state: dict[str, Any], gap_closure_payload: dict[str, Any], plan_id: str) -> None:
    existing = _task_by_id(task_state)
    for task in gap_closure_payload.get("tasks", []):
        if not isinstance(task, dict):
            continue
        task_id = _as_str(task.get("task_id"))
        if not task_id or task_id in existing:
            continue
        phase_id = _as_str(task.get("phase_id")) or "phase-1"
        req_ids = [
            rid
            for rid in ((_as_str(item) for item in task.get("requirement_ids", [])))
            if rid
        ]
        rel = _canonical_task_evidence_rel(task_id)
        _atomic_write_json(
            _repo_path(repo_root, rel),
            _default_task_evidence(plan_id, phase_id, task_id, req_ids),
        )
        task_state.setdefault("tasks", []).append(
            {
                "task_id": task_id,
                "phase_id": phase_id,
                "source_gap_id": _as_str(task.get("source_gap_id")),
                "requirement_ids": req_ids,
                "status": "queued",
                "owner_slot": None,
                "attempts": {"dev": 0, "test": 0, "review": 0},
                "evidence": {
                    "task_evidence_ref": str(rel),
                    "dev_ready_evidence_ref": str(rel),
                    "verify_results": [],
                    "uat_results": [],
                },
                "blockers": [],
                "is_gap_closure": True,
            }
        )


def _phase_exit_checks(repo_root: Path, phase_id: str, plan_packets: dict[str, Any], task_state: dict[str, Any], gaps_payload: dict[str, Any]) -> dict[str, Any]:
    plan_tasks = [task for task in plan_packets.get("tasks", []) if isinstance(task, dict) and _as_str(task.get("phase_id")) == phase_id]
    task_map = _task_by_id(task_state)
    all_tasks_review_done = True
    verify_required: set[str] = set()
    verify_passed: set[str] = set()
    uat_required: set[str] = set()
    uat_passed: set[str] = set()
    for plan_task in plan_tasks:
        task_id = _as_str(plan_task.get("task_id"))
        if not task_id:
            continue
        task = task_map.get(task_id)
        if not isinstance(task, dict):
            all_tasks_review_done = False
            continue
        status = _as_str(task.get("status")) or ""
        if status != "review_done":
            all_tasks_review_done = False
        for cmd in plan_task.get("verify_commands", []):
            cmd_text = _as_str(cmd)
            if cmd_text:
                verify_required.add(cmd_text)
        evidence_path = _task_evidence_path(repo_root, task)
        if evidence_path.exists():
            try:
                payload = _read_json(evidence_path)
            except OpError:
                payload = None
            if isinstance(payload, dict):
                verify_passed.update(_collect_passed_verify_commands(payload))
                req_ids = [rid for rid in ((_as_str(item) for item in plan_task.get("requirement_ids", []))) if rid]
                uat_passed.update(_collect_passed_uat_requirement_ids(payload, req_ids))
        for rid in plan_task.get("requirement_ids", []):
            rid_text = _as_str(rid)
            if rid_text:
                uat_required.add(rid_text)
    open_gap_ids = [
        _as_str(item.get("gap_id"))
        for item in gaps_payload.get("gaps", [])
        if isinstance(item, dict)
        and _as_str(item.get("status")) == "open"
        and (_as_str(item.get("phase_id")) or "phase-1") == phase_id
        and _as_str(item.get("gap_id"))
    ]
    verify_commands_passed = verify_required.issubset(verify_passed)
    uat_matrix_passed = uat_required.issubset(uat_passed)
    checks = {
        "phase_id": phase_id,
        "all_tasks_review_done": all_tasks_review_done,
        "verify_commands_passed": verify_commands_passed,
        "uat_matrix_passed": uat_matrix_passed,
        "zero_open_gaps": len(open_gap_ids) == 0,
        "open_gap_ids": open_gap_ids,
    }
    checks["all_passed"] = (
        checks["all_tasks_review_done"]
        and checks["verify_commands_passed"]
        and checks["uat_matrix_passed"]
        and checks["zero_open_gaps"]
    )
    return checks


def _resolve_active_phase(plan_packets: dict[str, Any], task_state: dict[str, Any], gaps_payload: dict[str, Any], repo_root: Path) -> tuple[str | None, dict[str, Any]]:
    ordered = _ordered_phase_ids(plan_packets)
    if not ordered:
        return None, {}
    all_checks: dict[str, Any] = {}
    for phase_id in ordered:
        checks = _phase_exit_checks(repo_root, phase_id, plan_packets, task_state, gaps_payload)
        all_checks[phase_id] = checks
        if not checks.get("all_passed"):
            return phase_id, all_checks
    return None, all_checks


def _read_rate_gate_window(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "reports" / "optimus-prime" / "PROFILE_RATE_REGISTRY.json"
    if not path.exists():
        return {"hard_gated": False, "min_reset_at": None, "min_reset_hours": None, "profiles": []}
    payload = _read_json(path)
    if not isinstance(payload, dict):
        return {"hard_gated": False, "min_reset_at": None, "min_reset_hours": None, "profiles": []}
    profiles_raw = payload.get("profiles")
    profile_items: list[tuple[str, dict[str, Any]]] = []
    if isinstance(profiles_raw, dict):
        for alias, data in profiles_raw.items():
            if isinstance(data, dict):
                profile_items.append((str(alias), data))
    elif isinstance(profiles_raw, list):
        for idx, data in enumerate(profiles_raw):
            if isinstance(data, dict):
                alias = _as_str(data.get("alias")) or f"profile-{idx+1}"
                profile_items.append((alias, data))

    hard_gated_profiles: list[dict[str, Any]] = []
    min_reset_dt: datetime | None = None
    now = datetime.now(timezone.utc)
    for alias, data in profile_items:
        five = data.get("five_hour") if isinstance(data.get("five_hour"), dict) else {}
        weekly = data.get("weekly") if isinstance(data.get("weekly"), dict) else {}
        recommended = (_as_str(data.get("recommended_action")) or "").lower()
        hard = bool(data.get("hard_gated") or data.get("gated") or five.get("gated") or weekly.get("gated"))
        if recommended in {"wind_down", "wait_until_reset"}:
            hard = True
        if not hard:
            continue
        reset_at = (
            _as_str(data.get("reset_at"))
            or _as_str(data.get("next_reset_at"))
            or _as_str(five.get("reset_at"))
            or _as_str(five.get("resets_at"))
            or _as_str(five.get("resetAt"))
            or _as_str(five.get("resetsAt"))
            or _as_str(weekly.get("reset_at"))
            or _as_str(weekly.get("resets_at"))
            or _as_str(weekly.get("resetAt"))
            or _as_str(weekly.get("resetsAt"))
        )
        reset_dt = _parse_iso_utc(reset_at)
        hard_gated_profiles.append({"alias": alias, "reset_at": reset_at})
        if reset_dt is not None and reset_dt > now and (min_reset_dt is None or reset_dt < min_reset_dt):
            min_reset_dt = reset_dt
    min_reset_at = None
    min_reset_hours = None
    if min_reset_dt is not None:
        min_reset_at = min_reset_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        min_reset_hours = max(0.0, (min_reset_dt - now).total_seconds() / 3600.0)
    return {
        "hard_gated": bool(hard_gated_profiles),
        "min_reset_at": min_reset_at,
        "min_reset_hours": min_reset_hours,
        "profiles": hard_gated_profiles,
    }


def _resolve_test_train_mode(repo_root: Path) -> str:
    path = repo_root / "reports" / "optimus-prime" / "TEST_TRAIN_STATE.json"
    if not path.exists():
        return "off"
    try:
        payload = _read_json(path)
    except OpError:
        return "off"
    if not isinstance(payload, dict):
        return "off"
    mode = (_as_str(payload.get("test_train_mode")) or "off").lower()
    if mode not in {"off", "final-stage", "forced-shared-env"}:
        return "off"
    return mode


def _active_workers_count(repo_root: Path) -> int | None:
    reports = repo_root / "reports" / "optimus-prime"
    snapshot_path = reports / "STATUS_SNAPSHOT.json"
    if snapshot_path.exists():
        try:
            snapshot = _read_json(snapshot_path)
        except OpError:
            snapshot = None
        if isinstance(snapshot, dict):
            counts = snapshot.get("counts") if isinstance(snapshot.get("counts"), dict) else {}
            active = counts.get("active_workers")
            if isinstance(active, int):
                return max(0, active)
    registry_path = reports / "WORKER_REGISTRY.json"
    if not registry_path.exists():
        return None
    try:
        registry = _read_json(registry_path)
    except OpError:
        return None
    workers: list[dict[str, Any]] = []
    if isinstance(registry, dict):
        raw = registry.get("workers")
        if isinstance(raw, list):
            workers = [item for item in raw if isinstance(item, dict)]
        elif isinstance(raw, dict):
            workers = [item for item in raw.values() if isinstance(item, dict)]
    elif isinstance(registry, list):
        workers = [item for item in registry if isinstance(item, dict)]
    active = 0
    for worker in workers:
        state = (_as_str(worker.get("state")) or _as_str(worker.get("session_state")) or _as_str(worker.get("status")) or "").lower()
        if state in {"running", "active", "busy"}:
            active += 1
    return active

def _run(cmd: list[str], *, cwd: Path, stdin_text: str | None = None) -> tuple[int, str, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        input=stdin_text,
        text=True,
        capture_output=True,
        check=False,
    )
    return proc.returncode, (proc.stdout or ""), (proc.stderr or "")


def _git_text(repo_root: Path, *args: str) -> str | None:
    code, out, _ = _run(["git", *args], cwd=repo_root)
    if code != 0:
        return None
    text = out.strip()
    return text or None


def _git_branch_and_clean(repo_root: Path) -> tuple[str, bool]:
    branch = _git_text(repo_root, "branch", "--show-current") or "detached"
    status = _git_text(repo_root, "status", "--porcelain=v1")
    clean = (status or "") == ""
    return branch, clean


def _list_repo_files(repo_root: Path) -> list[str]:
    paths: list[str] = []
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(repo_root)
        parts = rel.parts
        if parts and parts[0] == ".git":
            continue
        rel_text = str(rel)
        if rel_text.startswith("reports/optimus-prime/planning/"):
            continue
        paths.append(rel_text)
    return sorted(paths)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _repo_fingerprint(repo_root: Path) -> str:
    branch, _ = _git_branch_and_clean(repo_root)
    head = _git_text(repo_root, "rev-parse", "HEAD") or "no-head"
    tracked_raw = _git_text(repo_root, "ls-files")
    if tracked_raw is not None:
        files = sorted([line.strip() for line in tracked_raw.splitlines() if line.strip()])
    else:
        files = [
            rel
            for rel in _list_repo_files(repo_root)
            if not rel.startswith("reports/optimus-prime/planning/")
        ]
    payload = {
        "branch": branch,
        "head": head,
        "files": files,
    }
    return _sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def _collect_code_inventory(repo_root: Path, files: list[str]) -> dict[str, Any]:
    by_ext: dict[str, int] = {}
    src_files: list[str] = []
    for rel in files:
        p = Path(rel)
        ext = (p.suffix or "<none>").lower()
        by_ext[ext] = by_ext.get(ext, 0) + 1
        if p.parts and p.parts[0] in {"skills", "scripts", "agents", "docs", "mcp"}:
            src_files.append(rel)
    return {
        "total_files": len(files),
        "tracked_source_like_files": len(src_files),
        "by_extension": dict(sorted(by_ext.items())),
    }


def _collect_test_inventory(files: list[str]) -> dict[str, Any]:
    tests = [
        rel
        for rel in files
        if "test" in Path(rel).name.lower()
        or "/tests/" in rel
        or rel.startswith("tests/")
    ]
    python_tests = [rel for rel in tests if rel.endswith(".py")]
    js_tests = [rel for rel in tests if rel.endswith((".js", ".ts", ".tsx"))]
    return {
        "total_test_files": len(tests),
        "python_test_files": len(python_tests),
        "js_ts_test_files": len(js_tests),
        "sample_paths": tests[:50],
    }


def _collect_toolchain(repo_root: Path) -> dict[str, Any]:
    manifests = [
        "pyproject.toml",
        "requirements.txt",
        "package.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "Makefile",
    ]
    detected = [name for name in manifests if (repo_root / name).exists()]
    return {
        "detected_files": detected,
        "python": any(name in detected for name in ["pyproject.toml", "requirements.txt"]),
        "node": any(name in detected for name in ["package.json", "pnpm-lock.yaml", "yarn.lock"]),
        "make": "Makefile" in detected,
    }


def _collect_runtime_hooks(repo_root: Path) -> dict[str, Any]:
    hooks = [
        "scripts/test-train/ttctl.sh",
        "scripts/deploy-test.sh",
        "scripts/runtime-heal.sh",
        "scripts/runtime/start.sh",
        "scripts/runtime/health.sh",
        "scripts/runtime/stop.sh",
        "scripts/db-impact-detector.sh",
        "scripts/db-reset-migrate-seed.sh",
    ]
    present = [hook for hook in hooks if (repo_root / hook).exists()]
    return {
        "configured_hooks": present,
        "missing_hooks": [hook for hook in hooks if hook not in present],
    }


def _collect_plan_doc_coverage(repo_root: Path) -> dict[str, Any]:
    plans_dir = repo_root / "docs" / "plans"
    docs = []
    if plans_dir.exists():
        docs = sorted(str(path.relative_to(repo_root)) for path in plans_dir.glob("*.md"))
    return {
        "plan_docs_count": len(docs),
        "plan_docs": docs,
        "has_lane_b_plan": any("LANE_B_FULL_GSD_FUSION_PLAN.md" in p for p in docs),
        "has_lane_b_status": any("LANE_B_IMPLEMENTATION_STATUS.md" in p for p in docs),
    }


def _collect_reports_health(repo_root: Path) -> dict[str, Any]:
    reports_root = repo_root / "reports" / "optimus-prime"
    out: dict[str, Any] = {
        "reports_root_exists": reports_root.exists(),
        "runtime_health_exists": (reports_root / "runtime" / "RUNTIME_HEALTH.json").exists(),
        "controller_final_state_exists": (reports_root / "controller" / "FINAL_STATE.json").exists(),
        "planning_state_exists": (reports_root / "planning" / "STATE.json").exists(),
    }
    return out


def _response(
    req: OpRequest,
    *,
    ok: bool,
    status: str,
    summary: str,
    warnings: list[dict[str, Any]] | None = None,
    errors: list[dict[str, Any]] | None = None,
    artifacts: list[str] | None = None,
    next_action: str | None = None,
    state_ref: str | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out = {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "ok": bool(ok),
        "command": req.command,
        "status": status,
        "summary": summary,
        "errors": errors or [],
        "warnings": warnings or [],
        "artifacts": artifacts or [],
        "next_action": next_action,
        "state_ref": state_ref,
    }
    if data:
        out["data"] = data
    if req.output_mode == "json+text":
        out["text_summary"] = summary
    return out


def _require_mission_scope(req: OpRequest) -> None:
    if not req.mission:
        raise OpError("input_error", "mission is required", stage="input")
    if not req.scope:
        raise OpError("input_error", "scope is required", stage="input")


def command_map_codebase(req: OpRequest) -> dict[str, Any]:
    repo_root = req.repo_root
    planning_dir = _repo_path(repo_root, PLANNING_REL)
    files = _list_repo_files(repo_root)
    branch, clean = _git_branch_and_clean(repo_root)

    code_inventory = _collect_code_inventory(repo_root, files)
    test_inventory = _collect_test_inventory(files)
    toolchain = _collect_toolchain(repo_root)
    runtime_hooks = _collect_runtime_hooks(repo_root)
    planning_coverage = _collect_plan_doc_coverage(repo_root)
    reports_health = _collect_reports_health(repo_root)

    warnings: list[dict[str, Any]] = []
    for missing in runtime_hooks["missing_hooks"]:
        warnings.append(
            {
                "code": "missing_runtime_hook",
                "message": f"runtime/deploy hook missing: {missing}",
                "stage": "map",
            }
        )

    risks = [
        {
            "id": "risk-runtime-hook-coverage",
            "severity": "medium",
            "summary": "Missing runtime hook scripts reduce deterministic deploy/runtime control.",
            "evidence": runtime_hooks["missing_hooks"],
        },
        {
            "id": "risk-planning-coverage",
            "severity": "medium",
            "summary": "Planning docs may be incomplete for strict autonomous execution.",
            "evidence": {
                "plan_docs_count": planning_coverage["plan_docs_count"],
                "has_lane_b_plan": planning_coverage["has_lane_b_plan"],
                "has_lane_b_status": planning_coverage["has_lane_b_status"],
            },
        },
    ]

    repo_fingerprint = _repo_fingerprint(repo_root)
    stable_payload = {
        "repo_fingerprint": repo_fingerprint,
        "branch": branch,
        "code_inventory": code_inventory,
        "test_inventory": test_inventory,
        "toolchain": toolchain,
        "runtime_hooks": runtime_hooks,
        "planning_coverage": planning_coverage,
        "risks": risks,
    }
    map_fingerprint = _sha256(json.dumps(stable_payload, sort_keys=True, separators=(",", ":")))

    map_payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "repo_root": str(repo_root),
        "branch": branch,
        "worktree_clean": clean,
        "repo_fingerprint": repo_fingerprint,
        "map_fingerprint": map_fingerprint,
        "code_inventory": code_inventory,
        "test_inventory": test_inventory,
        "toolchain": toolchain,
        "runtime_hooks": runtime_hooks,
        "planning_coverage": planning_coverage,
        "reports_health": reports_health,
        "risks": risks,
    }

    index_payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "code_files": [rel for rel in files if rel.startswith(("skills/", "scripts/", "agents/"))],
        "test_files": [rel for rel in files if "/tests/" in rel or rel.startswith("tests/")],
        "docs_files": [rel for rel in files if rel.startswith("docs/")],
        "config_files": [
            rel
            for rel in files
            if rel.endswith((".json", ".toml", ".yaml", ".yml"))
            and rel.startswith(("reports/", "skills/", "scripts/", "docs/"))
        ],
    }

    arch_md = "\n".join(
        [
            "# Architecture Notes",
            "",
            f"- Generated at: {utc_now_iso()}",
            f"- Repo root: {repo_root}",
            f"- Branch: {branch}",
            f"- Worktree clean: {str(clean).lower()}",
            "",
            "## Core Areas",
            "- `skills/`: reusable deterministic skill scripts and tests.",
            "- `scripts/`: operational shell tooling (runtime/deploy/test-train).",
            "- `agents/`: orchestrator and worker agent prompts/templates.",
            "- `docs/plans/`: lane plans and implementation statuses.",
            "- `reports/optimus-prime/`: operational artifacts/state.",
        ]
    )

    map_md = "\n".join(
        [
            "# MAP CODEBASE",
            "",
            f"- Generated at: {map_payload['generated_at']}",
            f"- Repo fingerprint: `{repo_fingerprint}`",
            f"- Map fingerprint: `{map_fingerprint}`",
            f"- Branch: `{branch}`",
            f"- Worktree clean: `{str(clean).lower()}`",
            "",
            "## Inventory",
            f"- Total files: {code_inventory['total_files']}",
            f"- Test files: {test_inventory['total_test_files']}",
            f"- Plan docs: {planning_coverage['plan_docs_count']}",
            "",
            "## Runtime Hooks",
            *[f"- present: `{hook}`" for hook in runtime_hooks["configured_hooks"]],
            *[f"- missing: `{hook}`" for hook in runtime_hooks["missing_hooks"]],
        ]
    )

    risk_payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "map_fingerprint": map_fingerprint,
        "risks": risks,
    }

    _atomic_write_json(_repo_path(repo_root, MAP_PATH), map_payload)
    _atomic_write_json(_repo_path(repo_root, INDEX_PATH), index_payload)
    _write_text(_repo_path(repo_root, MAP_MD_PATH), map_md + "\n")
    _write_text(_repo_path(repo_root, ARCH_PATH), arch_md + "\n")
    _atomic_write_json(_repo_path(repo_root, RISK_PATH), risk_payload)

    return _response(
        req,
        ok=True,
        status="completed",
        summary="Codebase map artifacts generated.",
        warnings=warnings,
        artifacts=[
            str(_repo_path(repo_root, MAP_PATH)),
            str(_repo_path(repo_root, MAP_MD_PATH)),
            str(_repo_path(repo_root, INDEX_PATH)),
            str(_repo_path(repo_root, ARCH_PATH)),
            str(_repo_path(repo_root, RISK_PATH)),
        ],
        state_ref=str(_repo_path(repo_root, MAP_PATH)),
        data={
            "repo_fingerprint": repo_fingerprint,
            "map_fingerprint": map_fingerprint,
        },
    )


def _requirements_from_request(req: OpRequest) -> list[dict[str, Any]]:
    scope = req.scope or "project scope"
    return [
        {
            "id": "REQ-001",
            "title": f"Deliver core functionality for {scope}",
            "acceptance_criteria": [
                "Core workflow is implemented end-to-end.",
                "Critical errors are handled deterministically.",
            ],
            "verify_commands": ["python3 -m pytest"],
        },
        {
            "id": "REQ-002",
            "title": f"Verify quality gates for {scope}",
            "acceptance_criteria": [
                "Relevant checks are automated.",
                "Evidence is persisted in reports artifacts.",
            ],
            "verify_commands": ["python3 -m pytest"],
        },
        {
            "id": "REQ-003",
            "title": f"Operationalize rollout for {scope}",
            "acceptance_criteria": [
                "Runtime/deploy flow is deterministic.",
                "Recovery path is documented and testable.",
            ],
            "verify_commands": ["python3 -m pytest"],
        },
    ]


def _map_needs_refresh(repo_root: Path) -> tuple[bool, str]:
    map_path = _repo_path(repo_root, MAP_PATH)
    if not map_path.exists():
        return True, "missing"
    payload = _read_json(map_path)
    if not isinstance(payload, dict):
        return True, "invalid"
    current = _repo_fingerprint(repo_root)
    mapped = _as_str(payload.get("repo_fingerprint"))
    if not mapped or mapped != current:
        return True, "stale"
    return False, "fresh"


def command_new_project(req: OpRequest) -> dict[str, Any]:
    _require_mission_scope(req)
    repo_root = req.repo_root

    map_refresh, refresh_reason = _map_needs_refresh(repo_root)
    warnings: list[dict[str, Any]] = []
    auto_map_performed = False
    if map_refresh:
        map_result = command_map_codebase(req)
        auto_map_performed = True
        warnings.extend(map_result.get("warnings", []))
        warnings.append(
            {
                "code": "map_refreshed",
                "message": f"map-codebase executed automatically ({refresh_reason})",
                "stage": "new-project",
            }
        )

    map_payload = _read_json(_repo_path(repo_root, MAP_PATH))
    if not isinstance(map_payload, dict):
        raise OpError("state_read_error", "map artifact is invalid", stage="new-project")

    requirements = _requirements_from_request(req)
    constraints = req.constraints
    constraint_lines = [f"- {item}" for item in constraints] if constraints else ["- none"]
    initialized_at = utc_now_iso()

    project_md = "\n".join(
        [
            "# PROJECT",
            "",
            f"- Mission: {req.mission}",
            f"- Scope: {req.scope}",
            f"- Initialized At: {initialized_at}",
            f"- Map Fingerprint: `{map_payload.get('map_fingerprint')}`",
            "",
            "## Constraints",
            *constraint_lines,
        ]
    )

    requirements_md_lines = [
        "# REQUIREMENTS",
        "",
        "| ID | Title |",
        "| --- | --- |",
    ]
    for req_item in requirements:
        requirements_md_lines.append(f"| {req_item['id']} | {req_item['title']} |")
    requirements_md = "\n".join(requirements_md_lines)

    roadmap_md = "\n".join(
        [
            "# ROADMAP",
            "",
            "1. Planning baseline finalized.",
            "2. Plan packets + plan-check pass.",
            "3. Autonomous build loop executes packets.",
            "4. Verification artifacts complete and terminal stop authorization passes.",
        ]
    )

    state_json = {
        "schema_version": SCHEMA_VERSION,
        "initialized_at": initialized_at,
        "updated_at": initialized_at,
        "mission": req.mission,
        "scope": req.scope,
        "constraints": constraints,
        "requirements": requirements,
        "map_fingerprint": map_payload.get("map_fingerprint"),
        "repo_fingerprint": map_payload.get("repo_fingerprint"),
        "baseline_ready": True,
        "plan_ready": False,
        "plan_id": None,
        "build_ready": False,
    }

    state_md = "\n".join(
        [
            "# STATE",
            "",
            f"- baseline_ready: true",
            f"- plan_ready: false",
            f"- build_ready: false",
            f"- mission: {req.mission}",
            f"- scope: {req.scope}",
            "",
            "## Traceability",
            *[f"- {item['id']} -> planned task pending" for item in requirements],
        ]
    )

    _write_text(_repo_path(repo_root, PROJECT_MD), project_md + "\n")
    _write_text(_repo_path(repo_root, REQUIREMENTS_MD), requirements_md + "\n")
    _write_text(_repo_path(repo_root, ROADMAP_MD), roadmap_md + "\n")
    _write_text(_repo_path(repo_root, STATE_MD), state_md + "\n")
    _atomic_write_json(_repo_path(repo_root, STATE_JSON), state_json)

    return _response(
        req,
        ok=True,
        status="completed",
        summary="Project baseline planning artifacts initialized.",
        warnings=warnings,
        artifacts=[
            str(_repo_path(repo_root, PROJECT_MD)),
            str(_repo_path(repo_root, REQUIREMENTS_MD)),
            str(_repo_path(repo_root, ROADMAP_MD)),
            str(_repo_path(repo_root, STATE_MD)),
            str(_repo_path(repo_root, STATE_JSON)),
        ],
        next_action="Run /op-plan to generate packets and enforce plan-check.",
        state_ref=str(_repo_path(repo_root, STATE_JSON)),
        data={"auto_map_performed": auto_map_performed},
    )


def _derive_phases_from_task_dag(tasks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str], list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    task_ids: list[str] = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = _as_str(task.get("task_id"))
        if task_id:
            task_ids.append(task_id)
    task_set = set(task_ids)

    indegree: dict[str, int] = {task_id: 0 for task_id in task_ids}
    outgoing: dict[str, list[str]] = {task_id: [] for task_id in task_ids}
    deps_by_task: dict[str, list[str]] = {}
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = _as_str(task.get("task_id"))
        if not task_id:
            continue
        deps: list[str] = []
        raw_deps = task.get("depends_on")
        if raw_deps is None:
            raw_deps = []
        if not isinstance(raw_deps, list):
            errors.append({"code": "dependency_graph_invalid", "message": f"task {task_id} depends_on must be a list"})
            continue
        for dep in raw_deps:
            dep_id = _as_str(dep)
            if not dep_id:
                continue
            if dep_id not in task_set:
                errors.append({"code": "dependency_graph_invalid", "message": f"task {task_id} depends on unknown task {dep_id}"})
                continue
            deps.append(dep_id)
            indegree[task_id] += 1
            outgoing[dep_id].append(task_id)
        deps_by_task[task_id] = deps

    if errors:
        return [], {}, errors

    phase_map: dict[str, str] = {}
    level: list[str] = sorted([task_id for task_id, count in indegree.items() if count == 0])
    phase_index = 1
    processed: set[str] = set()
    while level:
        phase_id = f"phase-{phase_index}"
        for task_id in level:
            phase_map[task_id] = phase_id
            processed.add(task_id)
        next_level: list[str] = []
        for task_id in level:
            for follower in outgoing.get(task_id, []):
                indegree[follower] -= 1
                if indegree[follower] == 0:
                    next_level.append(follower)
        phase_index += 1
        level = sorted(next_level)

    if len(processed) != len(task_set):
        errors.append({"code": "dependency_graph_invalid", "message": "cycle detected in task DAG"})
        return [], {}, errors

    phases: list[dict[str, Any]] = []
    phase_tasks: dict[str, list[str]] = defaultdict(list)
    for task_id in task_ids:
        phase_tasks[phase_map[task_id]].append(task_id)
    ordered_phase_ids = sorted(phase_tasks.keys(), key=lambda item: int(item.split("-")[-1]))
    for phase_id in ordered_phase_ids:
        depends_on_phase_ids: set[str] = set()
        for task_id in phase_tasks[phase_id]:
            for dep_id in deps_by_task.get(task_id, []):
                dep_phase = phase_map.get(dep_id)
                if dep_phase and dep_phase != phase_id:
                    depends_on_phase_ids.add(dep_phase)
        phases.append(
            {
                "phase_id": phase_id,
                "task_ids": sorted(phase_tasks[phase_id]),
                "depends_on_phase_ids": sorted(depends_on_phase_ids),
                "entry_criteria": ["phase_dependencies_done"],
                "exit_criteria": [
                    "all_tasks_review_done",
                    "verify_commands_passed",
                    "uat_matrix_passed",
                    "zero_open_gaps",
                ],
            }
        )
    return phases, phase_map, []


def _compute_plan_check(
    mission: str | None,
    scope: str | None,
    requirements: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
    phases: list[dict[str, Any]],
) -> dict[str, Any]:
    req_ids = [item.get("id") for item in requirements if isinstance(item, dict) and _as_str(item.get("id"))]
    covered_ids: set[str] = set()
    for task in tasks:
        if not isinstance(task, dict):
            continue
        for rid in task.get("requirement_ids", []):
            rid_text = _as_str(rid)
            if rid_text:
                covered_ids.add(rid_text)

    checks: list[dict[str, Any]] = []
    blocking_errors: list[dict[str, Any]] = []

    coverage_pass = all(req_id in covered_ids for req_id in req_ids) and len(req_ids) > 0
    checks.append({"id": "requirement_coverage", "passed": coverage_pass})
    if not coverage_pass:
        blocking_errors.append({"code": "requirement_coverage_failed", "message": "not all requirements are mapped to tasks"})

    task_complete = True
    for task in tasks:
        if not isinstance(task, dict):
            task_complete = False
            break
        if not _as_str(task.get("task_id")) or not _as_str(task.get("title")):
            task_complete = False
            break
        if not isinstance(task.get("requirement_ids"), list) or not task["requirement_ids"]:
            task_complete = False
            break
    checks.append({"id": "task_completeness", "passed": task_complete})
    if not task_complete:
        blocking_errors.append({"code": "task_completeness_failed", "message": "one or more tasks are incomplete"})

    verify_complete = True
    for req_item in requirements:
        verify_cmds = req_item.get("verify_commands") if isinstance(req_item, dict) else None
        if not isinstance(verify_cmds, list) or not verify_cmds:
            verify_complete = False
            break
    checks.append({"id": "verify_contract_completeness", "passed": verify_complete})
    if not verify_complete:
        blocking_errors.append({"code": "verify_contract_incomplete", "message": "missing verify commands on requirements"})

    scope_pass = bool(_as_str(mission) and _as_str(scope))
    checks.append({"id": "scope_sanity", "passed": scope_pass})
    if not scope_pass:
        blocking_errors.append({"code": "scope_sanity_failed", "message": "mission/scope missing"})

    dag_pass = True
    task_ids = {_as_str(task.get("task_id")) for task in tasks if isinstance(task, dict)}
    task_ids.discard(None)
    for task in tasks:
        deps = task.get("depends_on") if isinstance(task, dict) else None
        if deps is None:
            continue
        if not isinstance(deps, list):
            dag_pass = False
            break
        for dep in deps:
            dep_id = _as_str(dep)
            if dep_id and dep_id not in task_ids:
                dag_pass = False
                break
        if not dag_pass:
            break
    checks.append({"id": "dependency_dag_sanity", "passed": dag_pass})
    if not dag_pass:
        blocking_errors.append({"code": "dependency_graph_invalid", "message": "task dependency references unknown nodes"})

    phase_ids = {
        _as_str(phase.get("phase_id"))
        for phase in phases
        if isinstance(phase, dict) and _as_str(phase.get("phase_id"))
    }
    phase_traceability_pass = True
    for task in tasks:
        if not isinstance(task, dict):
            phase_traceability_pass = False
            break
        phase_id = _as_str(task.get("phase_id"))
        if not phase_id or phase_id not in phase_ids:
            phase_traceability_pass = False
            break
    checks.append({"id": "phase_traceability", "passed": phase_traceability_pass})
    if not phase_traceability_pass:
        blocking_errors.append({"code": "phase_traceability_failed", "message": "tasks must map to valid plan phases"})

    phase_dag_pass = True
    for phase in phases:
        if not isinstance(phase, dict):
            phase_dag_pass = False
            break
        phase_id = _as_str(phase.get("phase_id"))
        deps = phase.get("depends_on_phase_ids")
        if not phase_id or not isinstance(deps, list):
            phase_dag_pass = False
            break
        for dep in deps:
            dep_id = _as_str(dep)
            if not dep_id or dep_id == phase_id or dep_id not in phase_ids:
                phase_dag_pass = False
                break
        if not phase_dag_pass:
            break
    checks.append({"id": "phase_dependency_dag_sanity", "passed": phase_dag_pass})
    if not phase_dag_pass:
        blocking_errors.append({"code": "phase_dependency_invalid", "message": "phase dependency graph is invalid"})

    passed = all(item["passed"] for item in checks)
    return {
        "schema_version": SCHEMA_VERSION,
        "passed": passed,
        "checks": checks,
        "coverage": {
            "requirements_total": len(req_ids),
            "requirements_covered": len(covered_ids),
            "missing_requirement_ids": [rid for rid in req_ids if rid not in covered_ids],
        },
        "dependency_graph": {
            "nodes": sorted(task_ids),
            "edges": [
                {"from": _as_str(dep), "to": _as_str(task.get("task_id"))}
                for task in tasks
                for dep in (task.get("depends_on") or [])
                if _as_str(dep) and _as_str(task.get("task_id"))
            ],
            "cycle_detected": False,
            "valid": dag_pass,
        },
        "verify_contract_completeness": verify_complete,
        "phase_traceability": phase_traceability_pass,
        "blocking_errors": blocking_errors,
    }


def command_plan(req: OpRequest) -> dict[str, Any]:
    repo_root = req.repo_root
    state_path = _repo_path(repo_root, STATE_JSON)
    if not state_path.exists():
        raise OpError("input_error", "state baseline missing; run /op-new-project first", stage="plan")

    state = _read_json(state_path)
    if not isinstance(state, dict):
        raise OpError("state_read_error", "planning STATE.json must be an object", stage="plan")

    mission = _as_str(state.get("mission"))
    scope = _as_str(state.get("scope"))
    requirements = state.get("requirements")
    if not isinstance(requirements, list) or not requirements:
        raise OpError("validation_error", "requirements missing from STATE.json", stage="plan")

    tasks: list[dict[str, Any]] = []
    prev_task_id: str | None = None
    for idx, req_item in enumerate(requirements, start=1):
        if not isinstance(req_item, dict):
            continue
        req_id = _as_str(req_item.get("id")) or f"REQ-{idx:03d}"
        title = _as_str(req_item.get("title")) or f"Requirement {req_id}"
        task_id = f"TASK-{idx:03d}"
        task = {
            "task_id": task_id,
            "title": f"Implement {title}",
            "requirement_ids": [req_id],
            "depends_on": [prev_task_id] if prev_task_id else [],
            "must_haves": req_item.get("acceptance_criteria") if isinstance(req_item.get("acceptance_criteria"), list) else [],
            "verify_commands": req_item.get("verify_commands") if isinstance(req_item.get("verify_commands"), list) else ["python3 -m pytest"],
        }
        tasks.append(task)
        prev_task_id = task_id

    phases, phase_map, phase_errors = _derive_phases_from_task_dag(tasks)
    if phase_errors:
        raise OpError("validation_error", phase_errors[0]["message"], stage="plan")
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = _as_str(task.get("task_id"))
        if task_id:
            task["phase_id"] = phase_map.get(task_id, "phase-1")

    plan_id = f"plan-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    plan_packets = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "plan_id": plan_id,
        "phase": "multi-phase",
        "phases": phases,
        "requirements": [item.get("id") for item in requirements if isinstance(item, dict)],
        "tasks": tasks,
        "depends_on": [],
        "must_haves": sorted({crit for task in tasks for crit in task.get("must_haves", []) if isinstance(crit, str)}),
        "verify_commands": sorted({cmd for task in tasks for cmd in task.get("verify_commands", []) if isinstance(cmd, str)}),
    }

    plan_check = _compute_plan_check(mission, scope, requirements, tasks, phases)

    test_contract_md_lines = [
        "# TEST CONTRACT",
        "",
        f"Plan ID: `{plan_id}`",
        "",
    ]
    for req_item in requirements:
        if not isinstance(req_item, dict):
            continue
        req_id = _as_str(req_item.get("id")) or "REQ-UNKNOWN"
        title = _as_str(req_item.get("title")) or "Untitled"
        test_contract_md_lines.append(f"## {req_id} - {title}")
        ac = req_item.get("acceptance_criteria") if isinstance(req_item.get("acceptance_criteria"), list) else []
        vc = req_item.get("verify_commands") if isinstance(req_item.get("verify_commands"), list) else []
        if ac:
            test_contract_md_lines.append("Acceptance Criteria:")
            for item in ac:
                test_contract_md_lines.append(f"- {item}")
        if vc:
            test_contract_md_lines.append("Verification Commands:")
            for cmd in vc:
                test_contract_md_lines.append(f"- `{cmd}`")
        test_contract_md_lines.append("")

    uat_md_lines = [
        "# PLAYWRIGHT UAT MATRIX",
        "",
        f"Plan ID: `{plan_id}`",
        "",
        "| Requirement | Scenario | Expected |",
        "| --- | --- | --- |",
    ]
    for req_item in requirements:
        if not isinstance(req_item, dict):
            continue
        req_id = _as_str(req_item.get("id")) or "REQ-UNKNOWN"
        title = _as_str(req_item.get("title")) or "Untitled"
        uat_md_lines.append(f"| {req_id} | Validate flow for {title} | Scenario passes without blocker |")

    verification_md_lines = [
        "# VERIFICATION",
        "",
        f"Plan ID: `{plan_id}`",
        "",
        "## Required Verify Commands",
    ]
    for cmd in plan_packets["verify_commands"]:
        verification_md_lines.append(f"- `{cmd}`")
    verification_md_lines.extend(["", "## Phase Exit Rules", "- all tasks review_done", "- verify commands passed", "- UAT requirements passed", "- open gaps = 0"])

    uat_phase_md_lines = [
        "# UAT",
        "",
        f"Plan ID: `{plan_id}`",
        "",
        "Autonomous tester-driven UAT: pass/fail results are consumed from canonical task evidence artifacts.",
    ]

    gaps_payload = {
        "schema_version": SCHEMA_VERSION,
        "plan_id": plan_id,
        "updated_at": utc_now_iso(),
        "gaps": [],
    }
    gap_closure_payload = {
        "schema_version": SCHEMA_VERSION,
        "plan_id": plan_id,
        "generated_at": utc_now_iso(),
        "tasks": [],
    }

    evidence_refs = _write_task_evidence_files(repo_root, plan_packets)
    task_state_payload = _task_state_from_plan(plan_packets, evidence_refs=evidence_refs)

    state["updated_at"] = utc_now_iso()
    state["plan_id"] = plan_id
    state["plan_ready"] = bool(plan_check["passed"])
    state["build_ready"] = bool(plan_check["passed"])
    state["phase_count"] = len(phases)

    state_md_lines = [
        "# STATE",
        "",
        "- baseline_ready: true",
        f"- plan_ready: {str(bool(plan_check['passed'])).lower()}",
        f"- build_ready: {str(bool(plan_check['passed'])).lower()}",
        f"- plan_id: {plan_id}",
        f"- phase_count: {len(phases)}",
        "",
        "## Plan Checks",
    ]
    for check in plan_check["checks"]:
        state_md_lines.append(f"- {check['id']}: {str(bool(check['passed'])).lower()}")

    _atomic_write_json(_repo_path(repo_root, PLAN_PACKETS_JSON), plan_packets)
    _atomic_write_json(_repo_path(repo_root, PLAN_CHECK_JSON), plan_check)
    _atomic_write_json(_repo_path(repo_root, TASK_EXECUTION_STATE_JSON), task_state_payload)
    _atomic_write_json(_repo_path(repo_root, GAPS_JSON), gaps_payload)
    _atomic_write_json(_repo_path(repo_root, GAP_CLOSURE_PLAN_PACKETS_JSON), gap_closure_payload)
    _write_text(_repo_path(repo_root, TEST_CONTRACT_MD), "\n".join(test_contract_md_lines) + "\n")
    _write_text(_repo_path(repo_root, PLAYWRIGHT_UAT_MD), "\n".join(uat_md_lines) + "\n")
    _write_text(_repo_path(repo_root, VERIFICATION_MD), "\n".join(verification_md_lines) + "\n")
    _write_text(_repo_path(repo_root, UAT_MD), "\n".join(uat_phase_md_lines) + "\n")
    _atomic_write_json(state_path, state)
    _write_text(_repo_path(repo_root, STATE_MD), "\n".join(state_md_lines) + "\n")

    status = "completed" if plan_check["passed"] else "blocked_plan_check"
    summary = "Plan artifacts generated and plan-check passed." if plan_check["passed"] else "Plan artifacts generated but plan-check failed."
    next_action = "/op-build" if plan_check["passed"] else "Fix plan-check blockers and run /op-plan again."

    return _response(
        req,
        ok=True,
        status=status,
        summary=summary,
        artifacts=[
            str(_repo_path(repo_root, PLAN_PACKETS_JSON)),
            str(_repo_path(repo_root, PLAN_CHECK_JSON)),
            str(_repo_path(repo_root, TASK_EXECUTION_STATE_JSON)),
            str(_repo_path(repo_root, GAPS_JSON)),
            str(_repo_path(repo_root, GAP_CLOSURE_PLAN_PACKETS_JSON)),
            str(_repo_path(repo_root, TEST_CONTRACT_MD)),
            str(_repo_path(repo_root, PLAYWRIGHT_UAT_MD)),
            str(_repo_path(repo_root, VERIFICATION_MD)),
            str(_repo_path(repo_root, UAT_MD)),
            str(state_path),
        ],
        next_action=next_action,
        state_ref=str(state_path),
        data={
            "plan_id": plan_id,
            "plan_ready": bool(plan_check["passed"]),
        },
    )


def command_initialize(req: OpRequest) -> dict[str, Any]:
    _require_mission_scope(req)
    map_result = command_map_codebase(req)
    new_result = command_new_project(req)
    plan_result = command_plan(req)

    artifacts = []
    artifacts.extend(map_result.get("artifacts", []))
    artifacts.extend(new_result.get("artifacts", []))
    artifacts.extend(plan_result.get("artifacts", []))

    warnings = []
    warnings.extend(map_result.get("warnings", []))
    warnings.extend(new_result.get("warnings", []))
    warnings.extend(plan_result.get("warnings", []))

    plan_ready = bool(plan_result.get("data", {}).get("plan_ready", False))
    summary = (
        "Initialization completed: map, project baseline, and plan artifacts generated. "
        "Review planned scope and optionally add more features before running /op-build."
    )

    return _response(
        req,
        ok=True,
        status="completed",
        summary=summary,
        warnings=warnings,
        artifacts=artifacts,
        next_action="Use /op-build when ready to execute autonomously.",
        state_ref=str(_repo_path(req.repo_root, STATE_JSON)),
        data={"plan_ready": plan_ready},
    )


def _load_build_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        now = utc_now_iso()
        return {
            "schema_version": SCHEMA_VERSION,
            "build_id": f"build-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
            "started_at": now,
            "updated_at": now,
            "last_cycle": 0,
            "current_strategy": STRATEGY_LADDER[0],
            "strategy_ladder": STRATEGY_LADDER,
            "fingerprint_attempts": {},
            "terminal_state": None,
            "completion_evidence": {},
            "loop_lock_id": None,
            "dispatch_window": {
                "max_running_workers": 6,
                "soft_cap_active": False,
            },
            "rate_gate_state": {
                "hard_gated": False,
                "min_reset_at": None,
                "sleep_until": None,
                "manual_rerun_required": False,
            },
            "cycle_gate_decision": {
                "dispatch_blocked": False,
                "reason": None,
                "terminal_reason": None,
            },
            "remediation_state": {
                "active": False,
                "reason": None,
                "last_queued_at": None,
                "fingerprint": None,
            },
            "offset_recovery": {
                "handoff_offset_resets": 0,
                "last_reset_at": None,
            },
            "strict_done_checks": {},
            "current_task_pointer": None,
            "current_phase_id": None,
            "phase_exit_checks": {},
            "open_gap_ids": [],
            "active_gap_closure_phase_id": None,
            "last_gap_generation_at": None,
            "gap_retry_attempts": {},
            "gap_retry_exhausted_ids": [],
            "gap_retry_policy": {
                "max_attempts": 5,
            },
            "handoff_log_offset": 0,
            "history": [],
        }
    payload = _read_json(path)
    if not isinstance(payload, dict):
        raise OpError("state_read_error", "BUILD_STATE.json must be a JSON object", stage="build")
    payload.setdefault("strategy_ladder", STRATEGY_LADDER)
    payload.setdefault("fingerprint_attempts", {})
    payload.setdefault("history", [])
    payload.setdefault("loop_lock_id", None)
    payload.setdefault("dispatch_window", {"max_running_workers": 6, "soft_cap_active": False})
    payload.setdefault(
        "rate_gate_state",
        {
            "hard_gated": False,
            "min_reset_at": None,
            "sleep_until": None,
            "manual_rerun_required": False,
        },
    )
    payload.setdefault("strict_done_checks", {})
    payload.setdefault("current_task_pointer", None)
    payload.setdefault("current_phase_id", None)
    payload.setdefault("phase_exit_checks", {})
    payload.setdefault("open_gap_ids", [])
    payload.setdefault("active_gap_closure_phase_id", None)
    payload.setdefault("last_gap_generation_at", None)
    payload.setdefault("gap_retry_attempts", {})
    payload.setdefault("gap_retry_exhausted_ids", [])
    payload.setdefault("gap_retry_policy", {"max_attempts": 5})
    payload.setdefault("handoff_log_offset", 0)
    payload.setdefault(
        "cycle_gate_decision",
        {
            "dispatch_blocked": False,
            "reason": None,
            "terminal_reason": None,
        },
    )
    payload.setdefault(
        "remediation_state",
        {
            "active": False,
            "reason": None,
            "last_queued_at": None,
            "fingerprint": None,
        },
    )
    payload.setdefault(
        "offset_recovery",
        {
            "handoff_offset_resets": 0,
            "last_reset_at": None,
        },
    )
    return payload


def _run_controller_cycle(req: OpRequest) -> dict[str, Any]:
    script = req.repo_root / "skills" / "optimus-cycle-controller" / "scripts" / "optimus_cycle_controller.py"
    if not script.exists():
        raise OpError("runtime_error", f"controller script not found: {script}", stage="build")

    payload = {
        "repo_root": str(req.repo_root),
        "sleep_minutes": req.sleep_minutes,
        "allow_autonomous_ops": True,
        "max_cycles": 1,
        "dry_run": req.dry_run,
        "emit_stdout": False,
    }

    code, out, err = _run([sys.executable, str(script), "--input-json", "-"], cwd=req.repo_root, stdin_text=json.dumps(payload))
    raw = out.strip()
    if not raw:
        raise OpError("runtime_error", f"controller returned empty output (stderr={err.strip()})", stage="build")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise OpError("runtime_error", f"controller output is not valid JSON: {exc}", stage="build") from exc

    if code not in {0, 1}:
        raise OpError(
            "runtime_error",
            f"controller returned unexpected exit code {code}: {err.strip() or raw}",
            stage="build",
        )
    if not isinstance(parsed, dict):
        raise OpError("runtime_error", "controller output must be object JSON", stage="build")
    return parsed


def _verify_final_state(req: OpRequest, final_state_path: Path) -> dict[str, Any]:
    script = req.repo_root / "skills" / "optimus-cycle-controller" / "scripts" / "optimus_cycle_controller.py"
    code, out, err = _run(
        [
            sys.executable,
            str(script),
            "--verify-final-state",
            str(final_state_path),
        ],
        cwd=req.repo_root,
    )
    raw = out.strip()
    if not raw:
        raise OpError("runtime_error", f"verify-final-state returned empty output (stderr={err.strip()})", stage="build")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise OpError("runtime_error", f"verify-final-state output is not valid JSON: {exc}", stage="build") from exc
    if code not in {0, 1}:
        raise OpError("runtime_error", f"verify-final-state exit={code}: {err.strip() or raw}", stage="build")
    if not isinstance(parsed, dict):
        raise OpError("runtime_error", "verify-final-state output must be object JSON", stage="build")
    return parsed


def _detect_blocker_fingerprint(repo_root: Path, *, warnings_sink: list[dict[str, Any]] | None = None) -> str:
    runtime_health_path = repo_root / "reports" / "optimus-prime" / "runtime" / "RUNTIME_HEALTH.json"
    if runtime_health_path.exists():
        try:
            payload = _read_json(runtime_health_path)
        except OpError as exc:
            if isinstance(warnings_sink, list):
                warnings_sink.append(
                    {
                        "code": "runtime_health_invalid_json",
                        "message": f"runtime health unreadable; falling back to unknown fingerprint: {exc.message}",
                        "stage": "build_loop",
                    }
                )
            payload = None
        if isinstance(payload, dict):
            fp = _as_str(payload.get("last_failure_fingerprint"))
            if fp:
                return fp

    blockers_path = repo_root / "reports" / "optimus-prime" / "BLOCKERS.jsonl"
    if blockers_path.exists():
        try:
            lines = blockers_path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as exc:
            if isinstance(warnings_sink, list):
                warnings_sink.append(
                    {
                        "code": "blockers_log_unreadable",
                        "message": f"blockers log unreadable; falling back to unknown fingerprint: {exc}",
                        "stage": "build_loop",
                    }
                )
            lines = []
        for line in reversed(lines):
            text = line.strip()
            if not text:
                continue
            try:
                obj = json.loads(text)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            status = _as_str(obj.get("status")) or ""
            if status.lower() in {"active", "open", "blocked"}:
                fp = _as_str(obj.get("fingerprint"))
                if fp:
                    return fp
                summary = _as_str(obj.get("summary")) or "unknown-blocker"
                category = _as_str(obj.get("category")) or "unknown"
                return f"{category}|{summary}"

    return "unknown-fingerprint"


def _strategy_index(state: dict[str, Any]) -> int:
    strategy = _as_str(state.get("current_strategy")) or STRATEGY_LADDER[0]
    if strategy in STRATEGY_LADDER:
        return STRATEGY_LADDER.index(strategy)
    return 0


def _apply_strategy_action(req: OpRequest, strategy: str) -> dict[str, Any]:
    repo_root = req.repo_root
    resolved_mode = _resolve_test_train_mode(repo_root)
    if strategy in {"self_heal", "runtime_repair"}:
        script = repo_root / "skills" / "runtime-coordinator" / "scripts" / "runtime_coordinator.py"
        if not script.exists():
            return {"action": strategy, "status": "skipped", "reason": "runtime-coordinator missing"}
        payload = {
            "repo_root": str(repo_root),
            "action": "repair",
            "test_train_mode": resolved_mode,
            "runtime_profile_id": "default-web",
            "runtime_id": "rt-shared-default-web",
            "test_train_pipeline_path": str(repo_root / "reports" / "optimus-prime" / "config" / "TEST_TRAIN_PIPELINE.json"),
            "runtime_health_path": str(repo_root / "reports" / "optimus-prime" / "runtime" / "RUNTIME_HEALTH.json"),
            "runtime_action_log_path": str(repo_root / "reports" / "optimus-prime" / "runtime" / "RUNTIME_ACTION_LOG.jsonl"),
            "runtime_repair_tasks_path": str(repo_root / "reports" / "optimus-prime" / "runtime" / "RUNTIME_REPAIR_TASKS.json"),
            "runtime_locks_dir": str(repo_root / "reports" / "optimus-prime" / "runtime" / "locks"),
        }
        code, out, err = _run([sys.executable, str(script), "--input-json", "-"], cwd=repo_root, stdin_text=json.dumps(payload))
        if code in {0, 1} and out.strip():
            try:
                parsed = json.loads(out.strip())
                return {"action": strategy, "status": "applied", "result": parsed}
            except json.JSONDecodeError:
                pass
        return {"action": strategy, "status": "failed", "stderr": err.strip(), "stdout": out.strip()}

    if strategy == "targeted_replan":
        plan_res = command_plan(req)
        return {
            "action": strategy,
            "status": "applied" if plan_res.get("ok") else "failed",
            "result": plan_res,
        }

    if strategy == "alternate_implementation":
        return {
            "action": strategy,
            "status": "applied",
            "result": {
                "message": "alternate implementation path selected; next cycles should dispatch alternate packet decomposition",
            },
        }

    return {
        "action": strategy,
        "status": "applied",
        "result": {
            "message": "blocker escalation selected; unresolved blockers should be escalated via blocker lane",
        },
    }


def _apply_handoff_updates(repo_root: Path, task_state: dict[str, Any], build_state: dict[str, Any]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    handoff_path = repo_root / "reports" / "optimus-prime" / "HANDOFF_LOG.jsonl"
    rows = _read_jsonl(handoff_path)
    offset = int(build_state.get("handoff_log_offset", 0))
    if offset < 0:
        offset = 0
    if offset > len(rows):
        old_offset = offset
        offset = 0
        recovery = build_state.get("offset_recovery")
        if not isinstance(recovery, dict):
            recovery = {
                "handoff_offset_resets": 0,
                "last_reset_at": None,
            }
            build_state["offset_recovery"] = recovery
        recovery["handoff_offset_resets"] = int(recovery.get("handoff_offset_resets", 0)) + 1
        recovery["last_reset_at"] = utc_now_iso()
        warnings.append(
            {
                "code": "handoff_offset_reset",
                "message": f"handoff_log_offset reset due to truncation: old_offset={old_offset}, line_count={len(rows)}",
                "stage": "build_loop",
            }
        )
    task_map = _task_by_id(task_state)
    for row in rows[offset:]:
        task_id = _as_str(row.get("task_identifier")) or _as_str(row.get("task_id"))
        if not task_id:
            continue
        task = task_map.get(task_id)
        if not isinstance(task, dict):
            continue
        evidence = task.get("evidence")
        if not isinstance(evidence, dict):
            evidence = {
                "task_evidence_ref": str(_canonical_task_evidence_rel(task_id)),
                "dev_ready_evidence_ref": str(_canonical_task_evidence_rel(task_id)),
                "verify_results": [],
                "uat_results": [],
            }
            task["evidence"] = evidence

        task_evidence_ref = _as_str(row.get("task_evidence_ref")) or _as_str(row.get("dev_ready_evidence_ref"))
        if task_evidence_ref:
            evidence["task_evidence_ref"] = task_evidence_ref
            evidence["dev_ready_evidence_ref"] = task_evidence_ref

        result = (_as_str(row.get("result")) or _as_str(row.get("status")) or "").lower()
        if result in {"blocked", "failed", "error", "dispatch_failed"}:
            task["status"] = "blocked"
            task["owner_slot"] = None
            blockers = task.get("blockers")
            if not isinstance(blockers, list):
                blockers = []
                task["blockers"] = blockers
            blockers.append(
                {
                    "timestamp": utc_now_iso(),
                    "summary": _as_str(row.get("reason")) or _as_str(row.get("message")) or "handoff blocked",
                }
            )
    build_state["handoff_log_offset"] = len(rows)
    return warnings


def _dispatch_task_packet(
    req: OpRequest,
    task: dict[str, Any],
    plan_task: dict[str, Any],
    stage: str,
    plan_id: str,
) -> dict[str, Any]:
    script = req.repo_root / "skills" / "dispatch-worker-packet" / "scripts" / "dispatch_worker_packet.py"
    task_id = _as_str(task.get("task_id")) or "TASK-UNKNOWN"
    requirement_ids = [
        rid
        for rid in ((_as_str(item) for item in task.get("requirement_ids", [])))
        if rid
    ]
    acceptance_refs = [
        item
        for item in ((_as_str(item) for item in plan_task.get("must_haves", [])))
        if item
    ]
    if not acceptance_refs:
        acceptance_refs = [f"{task_id} acceptance"]
    evidence_ref = _as_str((task.get("evidence") or {}).get("task_evidence_ref"))
    if not evidence_ref:
        evidence_ref = str(_canonical_task_evidence_rel(task_id))
        task.setdefault("evidence", {})["task_evidence_ref"] = evidence_ref
    task.setdefault("evidence", {})["dev_ready_evidence_ref"] = evidence_ref

    stage_cfg = {
        "dev": {"slot": "dev-1", "role": "developer", "status": "dev_in_progress", "attempt_key": "dev"},
        "test": {"slot": "test-1", "role": "tester", "status": "test_in_progress", "attempt_key": "test"},
        "review": {"slot": "review-1", "role": "reviewer", "status": "review_in_progress", "attempt_key": "review"},
    }
    cfg = stage_cfg[stage]
    start_from_commit = _git_text(req.repo_root, "rev-parse", "HEAD") or "HEAD"
    payload = {
        "slot": cfg["slot"],
        "role": cfg["role"],
        "task_identifier": task_id,
        "repo_root": str(req.repo_root),
        "worktree_root": str(req.repo_root),
        "branch_name": f"codex/{cfg['slot']}/{task_id.lower()}",
        "start_from_branch": "main",
        "start_from_commit": start_from_commit,
        "acceptance_criteria": acceptance_refs,
        "packet_version": 1,
        "codex_profile_alias": "codex",
        "mcp_mode": "disable-all",
        "mcp_allowlist": [],
        "sandbox_mode": "danger-full-access",
        "sandbox_add_dirs": [],
        "test_train_mode": "off",
        "op_build_mode": True,
        "plan_id": plan_id,
        "requirement_ids": requirement_ids,
        "task_acceptance_refs": acceptance_refs,
        "dev_ready_evidence_ref": evidence_ref,
        "dry_run": req.dry_run,
        "cycle_note": f"/op-build:{stage}:{task_id}",
    }
    result = _run_tool_json(script, payload, req.repo_root)
    if _as_bool_field(result.get("ok")):
        task["status"] = cfg["status"]
        task["owner_slot"] = cfg["slot"]
        attempts = task.get("attempts")
        if not isinstance(attempts, dict):
            attempts = {"dev": 0, "test": 0, "review": 0}
            task["attempts"] = attempts
        attempts[cfg["attempt_key"]] = int(attempts.get(cfg["attempt_key"], 0)) + 1
        return {"ok": True, "task_id": task_id, "stage": stage, "dispatch": result}
    task["status"] = "blocked"
    task["owner_slot"] = None
    blockers = task.get("blockers")
    if not isinstance(blockers, list):
        blockers = []
        task["blockers"] = blockers
    blockers.append(
        {
            "timestamp": utc_now_iso(),
            "summary": f"dispatch failed for {stage}",
            "details": result,
        }
    )
    return {"ok": False, "task_id": task_id, "stage": stage, "dispatch": result}


def _dispatch_next_task(
    req: OpRequest,
    plan_packets: dict[str, Any],
    task_state: dict[str, Any],
    build_state: dict[str, Any],
    active_phase_id: str | None = None,
) -> dict[str, Any]:
    task_map = _task_by_id(task_state)
    plan_map = _plan_task_map(plan_packets)
    retry_policy = build_state.get("gap_retry_policy")
    if not isinstance(retry_policy, dict):
        retry_policy = {"max_attempts": 5}
        build_state["gap_retry_policy"] = retry_policy
    max_retry_attempts = max(1, _coerce_nonneg_int(retry_policy.get("max_attempts"), default=5))
    retry_attempts = build_state.get("gap_retry_attempts")
    if not isinstance(retry_attempts, dict):
        retry_attempts = {}
        build_state["gap_retry_attempts"] = retry_attempts
    exhausted_ids_raw = build_state.get("gap_retry_exhausted_ids")
    exhausted_ids = (
        [item for item in (_as_str(v) for v in exhausted_ids_raw) if item]
        if isinstance(exhausted_ids_raw, list)
        else []
    )
    exhausted_set = set(exhausted_ids)
    build_state["gap_retry_exhausted_ids"] = sorted(exhausted_set)
    ordered_ids = [
        task_id
        for task_id in plan_map.keys()
        if not active_phase_id or (_as_str(plan_map.get(task_id, {}).get("phase_id")) or "phase-1") == active_phase_id
    ]
    has_in_progress = any(
        (_as_str(task_map.get(task_id, {}).get("status")) or "").endswith("_in_progress")
        for task_id in ordered_ids
    )
    if has_in_progress:
        return {"ok": True, "status": "skipped", "reason": "task already in progress"}

    plan_id = _as_str(plan_packets.get("plan_id")) or "plan-unknown"
    for task_id in ordered_ids:
        task = task_map.get(task_id)
        plan_task = plan_map.get(task_id) or {}
        if not isinstance(task, dict):
            continue
        status = _as_str(task.get("status")) or "queued"
        if status == "review_done":
            continue
        build_state["current_task_pointer"] = task_id
        if status == "queued":
            return _dispatch_task_packet(req, task, plan_task, "dev", plan_id)
        if status == "blocked" and bool(task.get("is_gap_closure")):
            source_gap_id = _as_str(task.get("source_gap_id")) or _as_str(plan_task.get("source_gap_id")) or f"gap:{task_id}"
            retries = _coerce_nonneg_int(retry_attempts.get(source_gap_id, 0), default=0)
            if source_gap_id in exhausted_set:
                return {
                    "ok": False,
                    "status": "blocked",
                    "task_id": task_id,
                    "reason": "gap_closure_retry_suppressed",
                    "source_gap_id": source_gap_id,
                    "retry_count": retries,
                    "warning": {
                        "code": "gap_closure_retry_suppressed",
                        "message": f"gap closure retries already exhausted for {source_gap_id}; dispatch suppressed",
                        "stage": "build_loop",
                        "gap_id": source_gap_id,
                        "retry_count": retries,
                    },
                }
            retries += 1
            retry_attempts[source_gap_id] = retries
            if retries >= max_retry_attempts:
                exhausted_set.add(source_gap_id)
                build_state["gap_retry_exhausted_ids"] = sorted(exhausted_set)
                return {
                    "ok": False,
                    "status": "blocked",
                    "task_id": task_id,
                    "reason": "gap_retry_exhausted",
                    "source_gap_id": source_gap_id,
                    "retry_count": retries,
                    "warning": {
                        "code": "gap_retry_exhausted",
                        "message": f"gap closure retry limit reached for {source_gap_id} (max_attempts={max_retry_attempts})",
                        "stage": "build_loop",
                        "gap_id": source_gap_id,
                        "retry_count": retries,
                        "max_attempts": max_retry_attempts,
                    },
                }
            task["status"] = "queued"
            task["owner_slot"] = None
            return _dispatch_task_packet(req, task, plan_task, "dev", plan_id)
        if status == "dev_done":
            evidence_path = _task_evidence_path(req.repo_root, task)
            if not evidence_path.exists():
                return {
                    "ok": False,
                    "status": "blocked",
                    "task_id": task_id,
                    "reason": "missing_task_evidence",
                }
            payload = _read_json(evidence_path)
            if not isinstance(payload, dict) or not _as_bool_field((payload.get("gate") or {}).get("ready_for_test")):
                return {
                    "ok": False,
                    "status": "blocked",
                    "task_id": task_id,
                    "reason": "dev_gate_not_ready_for_test",
                }
            return _dispatch_task_packet(req, task, plan_task, "test", plan_id)
        if status == "test_done":
            evidence_path = _task_evidence_path(req.repo_root, task)
            if not evidence_path.exists():
                return {
                    "ok": False,
                    "status": "blocked",
                    "task_id": task_id,
                    "reason": "missing_task_evidence",
                }
            payload = _read_json(evidence_path)
            if not isinstance(payload, dict) or not _as_bool_field((payload.get("gate") or {}).get("ready_for_review")):
                return {
                    "ok": False,
                    "status": "blocked",
                    "task_id": task_id,
                    "reason": "test_gate_not_ready_for_review",
                }
            return _dispatch_task_packet(req, task, plan_task, "review", plan_id)
    return {"ok": True, "status": "noop", "reason": "no dispatchable tasks"}


def _apply_directives(
    req: OpRequest,
    directives: list[dict[str, Any]],
    build_state: dict[str, Any],
    plan_packets: dict[str, Any],
    task_state: dict[str, Any],
) -> dict[str, Any]:
    outcomes: list[dict[str, Any]] = []
    runtime_script = req.repo_root / "skills" / "runtime-coordinator" / "scripts" / "runtime_coordinator.py"
    train_script = req.repo_root / "skills" / "test-train-manager" / "scripts" / "test_train_manager.py"
    resolved_mode = _resolve_test_train_mode(req.repo_root)
    dispatch_requested = False
    dispatch_blocked = False
    dispatch_block_reason: str | None = None
    remediation_queued = False
    runtime_defaults = {
        "repo_root": str(req.repo_root),
        "test_train_mode": resolved_mode,
        "runtime_profile_id": "default-web",
        "runtime_id": "rt-shared-default-web",
        "test_train_pipeline_path": str(req.repo_root / "reports" / "optimus-prime" / "config" / "TEST_TRAIN_PIPELINE.json"),
        "runtime_health_path": str(req.repo_root / "reports" / "optimus-prime" / "runtime" / "RUNTIME_HEALTH.json"),
        "runtime_action_log_path": str(req.repo_root / "reports" / "optimus-prime" / "runtime" / "RUNTIME_ACTION_LOG.jsonl"),
        "runtime_repair_tasks_path": str(req.repo_root / "reports" / "optimus-prime" / "runtime" / "RUNTIME_REPAIR_TASKS.json"),
        "runtime_locks_dir": str(req.repo_root / "reports" / "optimus-prime" / "runtime" / "locks"),
    }
    train_defaults = {
        "repo_root": str(req.repo_root),
        "test_train_mode": resolved_mode,
        "dry_run": req.dry_run,
    }

    runtime_directives = {
        "runtime_health_check",
        "runtime_repair",
        "runtime_strategy_resolve",
        "refresh_blocker_index",
    }
    train_directives = {
        "close_test_wave",
        "evaluate_promotion_gate",
        "promote_test_next_to_test",
        "deploy_test_branch",
        "start_new_test_wave",
        "hold_test_promotion",
    }

    for directive in directives:
        if not isinstance(directive, dict):
            continue
        directive_type = _as_str(directive.get("directive_type")) or "unknown"
        if directive.get("requires_optimus_action") is False:
            outcomes.append({"directive_type": directive_type, "status": "skipped", "reason": "no action required"})
            continue
        args = directive.get("recommended_args") if isinstance(directive.get("recommended_args"), dict) else {}
        if directive_type in runtime_directives:
            payload = dict(runtime_defaults)
            payload.update(args)
            if directive_type == "runtime_health_check":
                payload["action"] = "health"
            elif directive_type == "runtime_repair":
                payload["action"] = "repair"
            elif directive_type == "runtime_strategy_resolve":
                payload["action"] = "resolve"
            elif directive_type == "refresh_blocker_index":
                payload["action"] = "refresh_blocker_index"
            result = _run_tool_json(runtime_script, payload, req.repo_root)
            if not _as_bool_field(result.get("ok")):
                remediation_payload = dict(runtime_defaults)
                remediation_payload["action"] = "repair"
                remediation_payload["test_train_mode"] = resolved_mode
                remediation = _run_tool_json(runtime_script, remediation_payload, req.repo_root)
                fingerprint = _detect_blocker_fingerprint(req.repo_root)
                build_state["remediation_state"] = {
                    "active": True,
                    "reason": f"{directive_type}_failed",
                    "last_queued_at": utc_now_iso(),
                    "fingerprint": None if fingerprint == "unknown-fingerprint" else fingerprint,
                }
                remediation_queued = True
                dispatch_blocked = True
                dispatch_block_reason = "directive_tool_failure"
                outcomes.append(
                    {
                        "directive_type": directive_type,
                        "status": "failed",
                        "result": result,
                        "warning_code": "directive_tool_failed_remediation_queued",
                        "remediation": remediation,
                    }
                )
                continue
            outcomes.append({"directive_type": directive_type, "status": "applied", "result": result})
            continue
        if directive_type in train_directives:
            payload = dict(train_defaults)
            payload.update(args)
            if directive_type == "hold_test_promotion":
                payload["action"] = "evaluate_promotion_gate"
            result = _run_tool_json(train_script, payload, req.repo_root)
            if not _as_bool_field(result.get("ok")):
                remediation_payload = dict(runtime_defaults)
                remediation_payload["action"] = "repair"
                remediation_payload["test_train_mode"] = resolved_mode
                remediation = _run_tool_json(runtime_script, remediation_payload, req.repo_root)
                fingerprint = _detect_blocker_fingerprint(req.repo_root)
                build_state["remediation_state"] = {
                    "active": True,
                    "reason": f"{directive_type}_failed",
                    "last_queued_at": utc_now_iso(),
                    "fingerprint": None if fingerprint == "unknown-fingerprint" else fingerprint,
                }
                remediation_queued = True
                dispatch_blocked = True
                dispatch_block_reason = "directive_tool_failure"
                outcomes.append(
                    {
                        "directive_type": directive_type,
                        "status": "failed",
                        "result": result,
                        "warning_code": "directive_tool_failed_remediation_queued",
                        "remediation": remediation,
                    }
                )
                continue
            outcomes.append({"directive_type": directive_type, "status": "applied", "result": result})
            continue
        if directive_type == "review_dispatch_queue":
            dispatch_requested = True
            outcomes.append({"directive_type": directive_type, "status": "queued", "reason": "dispatch reviewed by build loop"})
            continue
        if directive_type == "soft_throttle":
            soft_cap = int(args.get("soft_cap") or build_state.get("dispatch_window", {}).get("max_running_workers") or 3)
            build_state["dispatch_window"] = {
                "max_running_workers": max(1, soft_cap),
                "soft_cap_active": True,
            }
            outcomes.append({"directive_type": directive_type, "status": "applied", "result": {"soft_cap": soft_cap}})
            continue
        if directive_type == "dispatch_filter":
            build_state.setdefault("rate_gate_state", {})
            build_state["rate_gate_state"]["hard_gated"] = True
            dispatch_blocked = True
            dispatch_block_reason = "dispatch_filter"
            outcomes.append({"directive_type": directive_type, "status": "applied", "result": {"hard_gated": True}})
            continue
        outcomes.append({"directive_type": directive_type, "status": "skipped", "reason": "unsupported directive"})
    return {
        "outcomes": outcomes,
        "dispatch_requested": dispatch_requested,
        "dispatch_blocked": dispatch_blocked,
        "dispatch_block_reason": dispatch_block_reason,
        "remediation_queued": remediation_queued,
        "resolved_test_train_mode": resolved_mode,
    }


def _collect_required_uat_ids(repo_root: Path, plan_packets: dict[str, Any]) -> set[str]:
    path = _repo_path(repo_root, PLAYWRIGHT_UAT_MD)
    out: set[str] = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text.startswith("|"):
                continue
            parts = [item.strip() for item in text.split("|")]
            if len(parts) < 3:
                continue
            req_id = _as_str(parts[1])
            if req_id and req_id.startswith("REQ-"):
                out.add(req_id)
    if out:
        return out
    for task in plan_packets.get("tasks", []):
        if not isinstance(task, dict):
            continue
        for rid in task.get("requirement_ids", []):
            rid_text = _as_str(rid)
            if rid_text:
                out.add(rid_text)
    return out


def _evaluate_strict_done(
    repo_root: Path,
    plan_packets: dict[str, Any],
    task_state: dict[str, Any],
    verification: dict[str, Any] | None,
    gaps_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    plan_tasks = []
    required_verify_cmds: set[str] = set()
    for task in plan_packets.get("tasks", []):
        if not isinstance(task, dict):
            continue
        task_id = _as_str(task.get("task_id"))
        if task_id:
            plan_tasks.append(task_id)
        for cmd in task.get("verify_commands", []):
            cmd_text = _as_str(cmd)
            if cmd_text:
                required_verify_cmds.add(cmd_text)

    task_map = _task_by_id(task_state)
    task_ids_present = all(task_id in task_map for task_id in plan_tasks)
    all_review_done = True
    all_dev_refs = True
    passed_verify_cmds: set[str] = set()
    passed_uat_reqs: set[str] = set()
    for task_id in plan_tasks:
        task = task_map.get(task_id)
        if not isinstance(task, dict):
            all_review_done = False
            all_dev_refs = False
            continue
        status = _as_str(task.get("status")) or ""
        if status != "review_done":
            all_review_done = False
        evidence = task.get("evidence") if isinstance(task.get("evidence"), dict) else {}
        dev_ref = _as_str(evidence.get("task_evidence_ref")) or _as_str(evidence.get("dev_ready_evidence_ref"))
        if not dev_ref:
            all_dev_refs = False
        verify_results = evidence.get("verify_results") if isinstance(evidence.get("verify_results"), list) else []
        for item in verify_results:
            if isinstance(item, str):
                passed_verify_cmds.add(item.strip())
            elif isinstance(item, dict) and _as_bool_field(item.get("passed")):
                cmd = _as_str(item.get("command"))
                if cmd:
                    passed_verify_cmds.add(cmd)
        uat_results = evidence.get("uat_results") if isinstance(evidence.get("uat_results"), list) else []
        for item in uat_results:
            if isinstance(item, dict) and _as_bool_field(item.get("passed")):
                rid = _as_str(item.get("requirement_id"))
                if rid:
                    passed_uat_reqs.add(rid)
                rid_list = item.get("requirement_ids")
                if isinstance(rid_list, list):
                    for rid_item in rid_list:
                        rid_text = _as_str(rid_item)
                        if rid_text:
                            passed_uat_reqs.add(rid_text)
                if not rid:
                    for rid_item in task.get("requirement_ids", []):
                        rid_text = _as_str(rid_item)
                        if rid_text:
                            passed_uat_reqs.add(rid_text)

    required_uat_ids = _collect_required_uat_ids(repo_root, plan_packets)
    verify_commands_passed = required_verify_cmds.issubset(passed_verify_cmds)
    uat_passed = required_uat_ids.issubset(passed_uat_reqs)
    final_state_ok = bool(verification and verification.get("ok") is True)
    open_gap_ids = [
        _as_str(item.get("gap_id"))
        for item in (gaps_payload or {}).get("gaps", [])
        if isinstance(item, dict) and _as_str(item.get("status")) == "open" and _as_str(item.get("gap_id"))
    ]
    phase_checks: dict[str, Any] = {}
    for phase_id in _ordered_phase_ids(plan_packets):
        phase_checks[phase_id] = _phase_exit_checks(repo_root, phase_id, plan_packets, task_state, gaps_payload or {"gaps": []})
    all_phases_complete = bool(phase_checks) and all(bool(item.get("all_passed")) for item in phase_checks.values())
    checks = {
        "tasks_exist_in_task_state": task_ids_present,
        "all_tasks_review_done": all_review_done,
        "all_tasks_have_dev_ready_evidence_ref": all_dev_refs,
        "verify_commands_passed": verify_commands_passed,
        "uat_matrix_passed": uat_passed,
        "all_phases_complete": all_phases_complete,
        "zero_open_gaps": len(open_gap_ids) == 0,
        "final_state_authorized": final_state_ok,
    }
    checks["all_passed"] = all(checks.values())
    checks["missing_verify_commands"] = sorted(required_verify_cmds - passed_verify_cmds)
    checks["missing_uat_requirement_ids"] = sorted(required_uat_ids - passed_uat_reqs)
    checks["open_gap_ids"] = [gap_id for gap_id in open_gap_ids if gap_id]
    checks["phase_checks"] = phase_checks
    return checks


def _preflight_build(req: OpRequest) -> tuple[list[dict[str, Any]], list[str], dict[str, Any], dict[str, Any], dict[str, Any]]:
    missing: list[str] = []
    for rel in MANDATORY_BUILD_BASELINE:
        if not _repo_path(req.repo_root, rel).exists():
            missing.append(str(rel))

    warnings: list[dict[str, Any]] = []
    if missing:
        warnings.append(
            {
                "code": "missing_baseline_artifacts",
                "message": "required planning artifacts are missing",
                "stage": "build_preflight",
                "missing": missing,
            }
        )

    state_payload: dict[str, Any] = {}
    state_path = _repo_path(req.repo_root, STATE_JSON)
    if state_path.exists():
        try:
            parsed = _read_json(state_path)
        except OpError as exc:
            warnings.append(
                {
                    "code": "state_payload_invalid",
                    "message": f"STATE.json unreadable: {exc.message}",
                    "stage": "build_preflight",
                }
            )
            parsed = None
        if isinstance(parsed, dict):
            state_payload = parsed

    plan_ready = bool(state_payload.get("plan_ready"))
    if not plan_ready:
        warnings.append(
            {
                "code": "plan_not_ready",
                "message": "plan_ready is false in planning state",
                "stage": "build_preflight",
            }
        )

    plan_packets: dict[str, Any] = {}
    plan_packets_path = _repo_path(req.repo_root, PLAN_PACKETS_JSON)
    if plan_packets_path.exists():
        try:
            parsed_plan = _read_json(plan_packets_path)
        except OpError as exc:
            warnings.append(
                {
                    "code": "plan_packets_invalid",
                    "message": f"PLAN_PACKETS.json unreadable: {exc.message}",
                    "stage": "build_preflight",
                }
            )
            parsed_plan = None
        if isinstance(parsed_plan, dict):
            plan_packets = parsed_plan
        else:
            warnings.append(
                {
                    "code": "plan_packets_invalid",
                    "message": "PLAN_PACKETS.json must be a JSON object",
                    "stage": "build_preflight",
                }
            )

    task_state: dict[str, Any] = {}
    task_state_path = _repo_path(req.repo_root, TASK_EXECUTION_STATE_JSON)
    if task_state_path.exists():
        try:
            parsed_task = _read_json(task_state_path)
        except OpError as exc:
            warnings.append(
                {
                    "code": "task_state_invalid",
                    "message": f"TASK_EXECUTION_STATE.json unreadable: {exc.message}",
                    "stage": "build_preflight",
                }
            )
            parsed_task = None
        if isinstance(parsed_task, dict):
            task_state = parsed_task
        else:
            warnings.append(
                {
                    "code": "task_state_invalid",
                    "message": "TASK_EXECUTION_STATE.json must be a JSON object",
                    "stage": "build_preflight",
                }
            )
    validation_errors = _validate_task_execution_state(task_state, plan_packets) if task_state and plan_packets else []
    for item in validation_errors:
        warnings.append(
            {
                "code": item.get("code") or "task_state_invalid",
                "message": item.get("message") or "TASK_EXECUTION_STATE validation failed",
                "stage": "build_preflight",
                "details": item,
            }
        )

    return warnings, missing, state_payload, plan_packets, task_state


def command_build(req: OpRequest) -> dict[str, Any]:
    warnings, missing, _, plan_packets, task_state = _preflight_build(req)
    preflight_failed = bool(missing) or any(
        item.get("code") in {"plan_not_ready", "task_state_invalid", "task_state_plan_mismatch", "plan_packets_invalid", "state_payload_invalid"}
        for item in warnings
    )
    if preflight_failed:
        return _response(
            req,
            ok=False,
            status="blocked_preflight",
            summary="Build blocked: strict planning baseline is incomplete.",
            warnings=warnings,
            errors=[
                {
                    "code": "build_preflight_failed",
                    "message": "Run /op-initialize to generate/repair required planning artifacts.",
                    "stage": "build_preflight",
                }
            ],
            next_action="Run /op-initialize, review plan artifacts, then rerun /op-build.",
            state_ref=str(_repo_path(req.repo_root, STATE_JSON)),
        )

    build_state_path = _repo_path(req.repo_root, BUILD_STATE_JSON)
    try:
        build_state = _load_build_state(build_state_path)
    except OpError as exc:
        warnings.append(
            {
                "code": "build_state_invalid",
                "message": exc.message,
                "stage": "build_preflight",
            }
        )
        return _response(
            req,
            ok=False,
            status="blocked_preflight",
            summary="Build blocked: strict planning baseline is incomplete.",
            warnings=warnings,
            errors=[
                {
                    "code": "build_preflight_failed",
                    "message": "Repair BUILD_STATE.json and rerun /op-build.",
                    "stage": "build_preflight",
                }
            ],
            next_action="Fix malformed build state artifacts or rerun /op-initialize, then rerun /op-build.",
            state_ref=str(build_state_path),
        )
    task_state_path = _repo_path(req.repo_root, TASK_EXECUTION_STATE_JSON)
    lock_path = _repo_path(req.repo_root, BUILD_LOOP_LOCK)
    lock_ok, lock_id, active_pid = _acquire_build_loop_lock(lock_path)
    if not lock_ok:
        return _response(
            req,
            ok=False,
            status="lock_conflict",
            summary="Build blocked: another /op-build loop is active.",
            errors=[
                {
                    "code": "lock_conflict",
                    "message": f"BUILD_LOOP.lock is held by pid {active_pid}",
                    "stage": "build_lock",
                }
            ],
            state_ref=str(lock_path),
            next_action="Wait for active /op-build to finish, or clear stale lock after confirming owner process is gone.",
            data={"active_pid": active_pid},
        )
    build_state["loop_lock_id"] = lock_id
    build_state["updated_at"] = utc_now_iso()
    _atomic_write_json(build_state_path, build_state)

    operator_stop_path = req.repo_root / "reports" / "optimus-prime" / "control" / "OPERATOR_STOP.json"
    plan_id = _as_str(plan_packets.get("plan_id")) or "plan-unknown"
    gaps_payload = _load_gaps_payload(_repo_path(req.repo_root, GAPS_JSON), plan_id)
    gap_closure_payload = _read_json(_repo_path(req.repo_root, GAP_CLOSURE_PLAN_PACKETS_JSON)) if _repo_path(req.repo_root, GAP_CLOSURE_PLAN_PACKETS_JSON).exists() else {"tasks": []}
    if not isinstance(gap_closure_payload, dict):
        gap_closure_payload = {"tasks": []}
    resume_cmd = "/op-resume" if req.command == "op-resume" else "/op-build"

    cycles = 0
    history: list[dict[str, Any]] = build_state.get("history", [])
    if not isinstance(history, list):
        history = []
    try:
        while req.max_build_cycles is None or cycles < req.max_build_cycles:
            cycles += 1
            cycle_local_warnings: list[dict[str, Any]] = []
            build_state["last_cycle"] = int(build_state.get("last_cycle", 0)) + 1
            build_state["updated_at"] = utc_now_iso()
            build_state["cycle_gate_decision"] = {
                "dispatch_blocked": False,
                "reason": None,
                "terminal_reason": None,
            }
            remediation_state = build_state.get("remediation_state")
            if not isinstance(remediation_state, dict):
                remediation_state = {
                    "active": False,
                    "reason": None,
                    "last_queued_at": None,
                    "fingerprint": None,
                }
                build_state["remediation_state"] = remediation_state
            else:
                remediation_state["active"] = False
                remediation_state["reason"] = None

            handoff_warnings = _apply_handoff_updates(req.repo_root, task_state, build_state)
            warnings.extend(handoff_warnings)
            cycle_local_warnings.extend(handoff_warnings)
            evidence_warnings = _sync_task_state_from_evidence(req.repo_root, plan_packets, task_state)
            warnings.extend(evidence_warnings)
            cycle_local_warnings.extend(evidence_warnings)
            gaps_payload, gap_closure_payload = _refresh_gap_artifacts(req.repo_root, plan_packets, task_state, build_state)
            _ensure_gap_closure_task_state(req.repo_root, task_state, gap_closure_payload, plan_id)
            merged_plan_packets = _merge_plan_with_gap_closure(plan_packets, gap_closure_payload)
            active_phase_id, phase_checks = _resolve_active_phase(merged_plan_packets, task_state, gaps_payload, req.repo_root)
            build_state["current_phase_id"] = active_phase_id
            build_state["phase_exit_checks"] = phase_checks

            if operator_stop_path.exists():
                build_state["terminal_state"] = {
                    "reason": "operator_stop",
                    "timestamp": utc_now_iso(),
                }
                _atomic_write_json(task_state_path, {**task_state, "updated_at": utc_now_iso()})
                _atomic_write_json(build_state_path, build_state)
                return _response(
                    req,
                    ok=False,
                    status="stopped_operator",
                    summary="Build stopped by explicit operator stop signal.",
                    warnings=warnings,
                    errors=[
                        {
                            "code": "operator_stop",
                            "message": f"operator stop marker found: {operator_stop_path}",
                            "stage": "build_loop",
                        }
                    ],
                    state_ref=str(build_state_path),
                    next_action=f"Remove operator stop marker and rerun {resume_cmd} to continue.",
                    data={"terminal_reason": "operator_stop"},
                )

            cycle_result = _run_controller_cycle(req)
            last_cycle_number = int(cycle_result.get("last_cycle_number") or 0)
            events_path_raw = _as_str(cycle_result.get("events_path"))
            directives: list[dict[str, Any]] = []
            if events_path_raw and last_cycle_number > 0:
                directives = _extract_cycle_directives(Path(events_path_raw).expanduser().resolve(), last_cycle_number)
            directive_state = _apply_directives(req, directives, build_state, merged_plan_packets, task_state)
            directive_outcomes = directive_state.get("outcomes", [])
            for outcome in directive_outcomes:
                warning_code = _as_str(outcome.get("warning_code"))
                if warning_code == "directive_tool_failed_remediation_queued":
                    warning = {
                        "code": "directive_tool_failed_remediation_queued",
                        "message": "directive tool failed; remediation was queued and dispatch skipped for this cycle",
                        "stage": "build_loop",
                        "directive_type": outcome.get("directive_type"),
                    }
                    warnings.append(warning)
                    cycle_local_warnings.append(warning)
            handoff_warnings = _apply_handoff_updates(req.repo_root, task_state, build_state)
            warnings.extend(handoff_warnings)
            cycle_local_warnings.extend(handoff_warnings)
            evidence_warnings = _sync_task_state_from_evidence(req.repo_root, merged_plan_packets, task_state)
            warnings.extend(evidence_warnings)
            cycle_local_warnings.extend(evidence_warnings)
            gaps_payload, gap_closure_payload = _refresh_gap_artifacts(req.repo_root, merged_plan_packets, task_state, build_state)
            _ensure_gap_closure_task_state(req.repo_root, task_state, gap_closure_payload, plan_id)
            merged_plan_packets = _merge_plan_with_gap_closure(plan_packets, gap_closure_payload)
            active_phase_id, phase_checks = _resolve_active_phase(merged_plan_packets, task_state, gaps_payload, req.repo_root)
            build_state["current_phase_id"] = active_phase_id
            build_state["phase_exit_checks"] = phase_checks

            history.append(
                {
                    "timestamp": utc_now_iso(),
                    "cycle_result": cycle_result,
                    "directives": directive_outcomes,
                    "cycle_warnings": cycle_local_warnings,
                    "strategy": build_state.get("current_strategy"),
                    "active_phase_id": active_phase_id,
                }
            )
            build_state["history"] = history[-200:]

            terminal_reason = _as_str(cycle_result.get("terminal_reason"))
            build_state["cycle_gate_decision"]["terminal_reason"] = terminal_reason
            if cycle_result.get("ok") is True and terminal_reason:
                if terminal_reason == "project_done":
                    final_state_path = req.repo_root / "reports" / "optimus-prime" / "controller" / "FINAL_STATE.json"
                    verification = _verify_final_state(req, final_state_path)
                    strict_checks = _evaluate_strict_done(req.repo_root, merged_plan_packets, task_state, verification, gaps_payload)
                    build_state["strict_done_checks"] = strict_checks
                    if verification.get("ok") is True and strict_checks.get("all_passed") is True:
                        build_state["terminal_state"] = {
                            "reason": "project_done",
                            "timestamp": utc_now_iso(),
                        }
                        build_state["completion_evidence"] = {
                            "final_state_path": str(final_state_path),
                            "verify_result": verification,
                            "strict_done_checks": strict_checks,
                        }
                        build_state["updated_at"] = utc_now_iso()
                        _atomic_write_json(task_state_path, {**task_state, "updated_at": utc_now_iso()})
                        _atomic_write_json(build_state_path, build_state)
                        return _response(
                            req,
                            ok=True,
                            status="completed",
                            summary="Build completed with strict done verification.",
                            warnings=warnings,
                            artifacts=[str(build_state_path), str(task_state_path), str(final_state_path)],
                            state_ref=str(build_state_path),
                            data={
                                "terminal_reason": "project_done",
                                "cycles_executed": cycles,
                                "current_strategy": build_state.get("current_strategy"),
                                "strict_done_checks": strict_checks,
                            },
                        )
                    warnings.append(
                        {
                            "code": "strict_done_incomplete",
                            "message": "project_done detected but strict done checks failed; continuing autonomous execution",
                            "stage": "build_loop",
                            "strict_done_checks": strict_checks,
                            "verification": verification,
                        }
                    )
                elif terminal_reason == "all_rate_gates_blocking":
                    build_state["cycle_gate_decision"] = {
                        "dispatch_blocked": True,
                        "reason": "all_rate_gates_blocking",
                        "terminal_reason": terminal_reason,
                    }
                    rate_window = _read_rate_gate_window(req.repo_root)
                    min_reset_at = _as_str(rate_window.get("min_reset_at"))
                    min_reset_hours = rate_window.get("min_reset_hours")
                    within_window = isinstance(min_reset_hours, (int, float)) and float(min_reset_hours) <= 2.0
                    build_state["rate_gate_state"] = {
                        "hard_gated": bool(rate_window.get("hard_gated")),
                        "min_reset_at": min_reset_at,
                        "sleep_until": min_reset_at if within_window else None,
                        "manual_rerun_required": not within_window,
                    }
                    if within_window and min_reset_at:
                        if not req.dry_run:
                            reset_dt = _parse_iso_utc(min_reset_at)
                            if reset_dt is not None:
                                seconds = int(max(0, (reset_dt - datetime.now(timezone.utc)).total_seconds()))
                                if seconds > 0:
                                    time.sleep(seconds)
                        build_state["updated_at"] = utc_now_iso()
                        _atomic_write_json(task_state_path, {**task_state, "updated_at": utc_now_iso()})
                        _atomic_write_json(build_state_path, build_state)
                        continue
                    build_state["terminal_state"] = {
                        "reason": terminal_reason,
                        "timestamp": utc_now_iso(),
                    }
                    build_state["updated_at"] = utc_now_iso()
                    _atomic_write_json(task_state_path, {**task_state, "updated_at": utc_now_iso()})
                    _atomic_write_json(build_state_path, build_state)
                    return _response(
                        req,
                        ok=False,
                        status="blocked_terminal",
                        summary="Build halted: all rate gates blocking beyond auto-wait window.",
                        warnings=warnings,
                        errors=[
                            {
                                "code": "hard_terminal_condition",
                                "message": "rate reset window exceeds 2h; rerun /op-build after reset",
                                "stage": "build_loop",
                            }
                        ],
                        state_ref=str(build_state_path),
                        next_action=(
                            f"Rerun /op-build after rate reset at {min_reset_at}."
                            if min_reset_at
                            else "Rerun /op-build after rate gates recover."
                        ),
                        data={
                            "terminal_reason": terminal_reason,
                            "cycles_executed": cycles,
                            "rate_gate_state": build_state.get("rate_gate_state"),
                        },
                    )
                elif terminal_reason in TERMINAL_HARD_STOPS:
                    build_state["terminal_state"] = {
                        "reason": terminal_reason,
                        "timestamp": utc_now_iso(),
                    }
                    build_state["updated_at"] = utc_now_iso()
                    _atomic_write_json(task_state_path, {**task_state, "updated_at": utc_now_iso()})
                    _atomic_write_json(build_state_path, build_state)
                    return _response(
                        req,
                        ok=False,
                        status="blocked_terminal",
                        summary=f"Build halted on hard terminal condition: {terminal_reason}.",
                        warnings=warnings,
                        errors=[
                            {
                                "code": "hard_terminal_condition",
                                "message": f"controller reported terminal reason {terminal_reason}",
                                "stage": "build_loop",
                            }
                        ],
                        state_ref=str(build_state_path),
                        data={"terminal_reason": terminal_reason, "cycles_executed": cycles},
                    )

            dispatch_blocked = bool(directive_state.get("dispatch_blocked"))
            dispatch_block_reason = _as_str(directive_state.get("dispatch_block_reason"))
            if active_phase_id is None:
                build_state["cycle_gate_decision"] = {
                    "dispatch_blocked": True,
                    "reason": "phase_barrier_complete_waiting_terminal",
                    "terminal_reason": terminal_reason,
                }
                warning = {
                    "code": "dispatch_skipped_hard_gate",
                    "message": "dispatch skipped for cycle: all phase barriers complete, awaiting terminal authorization",
                    "stage": "build_loop",
                }
                warnings.append(warning)
                cycle_local_warnings.append(warning)
            elif dispatch_blocked:
                build_state["cycle_gate_decision"] = {
                    "dispatch_blocked": True,
                    "reason": dispatch_block_reason or "dispatch_filter",
                    "terminal_reason": terminal_reason,
                }
                warning = {
                    "code": "dispatch_skipped_hard_gate",
                    "message": f"dispatch skipped for cycle due to hard gate: {dispatch_block_reason or 'dispatch_filter'}",
                    "stage": "build_loop",
                }
                warnings.append(warning)
                cycle_local_warnings.append(warning)
            else:
                max_running_workers = int(build_state.get("dispatch_window", {}).get("max_running_workers", 6))
                active_workers = _active_workers_count(req.repo_root)
                if active_workers is not None and active_workers >= max_running_workers:
                    build_state["cycle_gate_decision"] = {
                        "dispatch_blocked": True,
                        "reason": "dispatch_window_cap",
                        "terminal_reason": terminal_reason,
                    }
                    warning = {
                        "code": "dispatch_skipped_soft_cap",
                        "message": (
                            "dispatch skipped for cycle due to active worker cap: "
                            f"active={active_workers}, cap={max_running_workers}"
                        ),
                        "stage": "build_loop",
                    }
                    warnings.append(warning)
                    cycle_local_warnings.append(warning)
                else:
                    dispatch_result = _dispatch_next_task(req, merged_plan_packets, task_state, build_state, active_phase_id)
                    dispatch_warning = dispatch_result.get("warning") if isinstance(dispatch_result, dict) else None
                    if isinstance(dispatch_warning, dict):
                        warnings.append(dispatch_warning)
                        cycle_local_warnings.append(dispatch_warning)
                    dispatch_reason = _as_str(dispatch_result.get("reason")) if isinstance(dispatch_result, dict) else None
                    if dispatch_reason in {"gap_retry_exhausted", "gap_closure_retry_suppressed"}:
                        build_state["cycle_gate_decision"] = {
                            "dispatch_blocked": True,
                            "reason": dispatch_reason,
                            "terminal_reason": terminal_reason,
                        }
                        gaps_payload, gap_closure_payload = _refresh_gap_artifacts(
                            req.repo_root,
                            merged_plan_packets,
                            task_state,
                            build_state,
                        )
                    directive_outcomes.append(
                        {
                            "directive_type": "review_dispatch_queue"
                            if directive_state.get("dispatch_requested")
                            else "auto_dispatch",
                            "status": "applied",
                            "result": dispatch_result,
                        }
                    )
                    handoff_warnings = _apply_handoff_updates(req.repo_root, task_state, build_state)
                    warnings.extend(handoff_warnings)
                    cycle_local_warnings.extend(handoff_warnings)

            fingerprint_warnings: list[dict[str, Any]] = []
            fingerprint = _detect_blocker_fingerprint(req.repo_root, warnings_sink=fingerprint_warnings)
            warnings.extend(fingerprint_warnings)
            cycle_local_warnings.extend(fingerprint_warnings)
            if fingerprint != "unknown-fingerprint":
                strategy = _as_str(build_state.get("current_strategy")) or STRATEGY_LADDER[0]
                counter_key = f"{strategy}|{fingerprint}"
                attempts = int(build_state.get("fingerprint_attempts", {}).get(counter_key, 0)) + 1
                build_state.setdefault("fingerprint_attempts", {})[counter_key] = attempts
                if attempts >= 5:
                    current_idx = _strategy_index(build_state)
                    next_idx = min(current_idx + 1, len(STRATEGY_LADDER) - 1)
                    next_strategy = STRATEGY_LADDER[next_idx]
                    if next_strategy != strategy:
                        build_state["current_strategy"] = next_strategy
                    action_result = _apply_strategy_action(req, build_state.get("current_strategy") or next_strategy)
                    warnings.append(
                        {
                            "code": "strategy_escalated",
                            "message": (
                                f"strategy escalated after 5 attempts for fingerprint '{fingerprint}': "
                                f"{strategy} -> {build_state.get('current_strategy')}"
                            ),
                            "stage": "build_loop",
                            "action_result": action_result,
                        }
                    )

            build_state["updated_at"] = utc_now_iso()
            _atomic_write_json(task_state_path, {**task_state, "updated_at": utc_now_iso()})
            _atomic_write_json(build_state_path, build_state)

        return _response(
            req,
            ok=False,
            status="running_needs_resume",
            summary=f"Build loop executed bounded cycles without terminal resolution; resume with {resume_cmd}.",
            warnings=warnings,
            errors=[
                {
                    "code": "max_build_cycles_reached",
                    "message": "bounded build run reached max_build_cycles before terminal condition",
                    "stage": "build_loop",
                }
            ],
            state_ref=str(build_state_path),
            next_action=f"Rerun {resume_cmd} to continue from BUILD_STATE.json.",
            data={
                "cycles_executed": cycles,
                "current_strategy": build_state.get("current_strategy"),
                "current_phase_id": build_state.get("current_phase_id"),
                "open_gap_ids": build_state.get("open_gap_ids", []),
                "strict_done_checks": build_state.get("strict_done_checks", {}),
            },
        )
    finally:
        try:
            build_state["loop_lock_id"] = None
            build_state["updated_at"] = utc_now_iso()
            _atomic_write_json(build_state_path, build_state)
            _atomic_write_json(task_state_path, {**task_state, "updated_at": utc_now_iso()})
        finally:
            _release_build_loop_lock(lock_path, lock_id)


def command_health(req: OpRequest) -> dict[str, Any]:
    try:
        warnings, missing, _, plan_packets, task_state = _preflight_build(req)
    except OpError as exc:
        warning = {
            "code": "build_preflight_read_error",
            "message": exc.message,
            "stage": "health",
        }
        checks = [
            {
                "id": "build_preflight_ready",
                "passed": False,
                "blockers": [warning],
            }
        ]
        return _response(
            req,
            ok=False,
            status="blocked",
            summary="OP health checks detected blocking issues.",
            warnings=[warning],
            errors=[{"code": "health_check_failed", "message": "one or more health checks failed", "stage": "health"}],
            artifacts=[
                str(_repo_path(req.repo_root, PLAN_PACKETS_JSON)),
                str(_repo_path(req.repo_root, TASK_EXECUTION_STATE_JSON)),
                str(_repo_path(req.repo_root, BUILD_STATE_JSON)),
                str(_repo_path(req.repo_root, GAPS_JSON)),
                str(_repo_path(req.repo_root, GAP_CLOSURE_PLAN_PACKETS_JSON)),
            ],
            state_ref=str(_repo_path(req.repo_root, BUILD_STATE_JSON)),
            data={"checks": checks, "open_gap_ids": []},
        )
    checks: list[dict[str, Any]] = []
    preflight_block_codes = {"plan_not_ready", "task_state_invalid", "task_state_plan_mismatch", "plan_packets_invalid", "state_payload_invalid"}
    preflight_blockers = [item for item in warnings if _as_str(item.get("code")) in preflight_block_codes]
    checks.append(
        {
            "id": "build_preflight_ready",
            "passed": len(missing) == 0 and len(preflight_blockers) == 0,
            "blockers": preflight_blockers,
        }
    )
    checks.append(
        {
            "id": "baseline_artifacts",
            "passed": len(missing) == 0,
            "missing": missing,
        }
    )

    build_state_path = _repo_path(req.repo_root, BUILD_STATE_JSON)
    build_state_valid = True
    if build_state_path.exists():
        try:
            payload = _read_json(build_state_path)
        except OpError as exc:
            warnings.append(
                {
                    "code": "build_state_invalid",
                    "message": f"BUILD_STATE.json unreadable: {exc.message}",
                    "stage": "health",
                }
            )
            build_state_valid = False
            payload = None
        build_state_valid = build_state_valid and isinstance(payload, dict)
    checks.append({"id": "build_state_integrity", "passed": build_state_valid})

    validation_errors = _validate_task_execution_state(task_state, plan_packets) if task_state and plan_packets else []
    checks.append({"id": "task_state_integrity", "passed": len(validation_errors) == 0, "errors": validation_errors})

    evidence_errors: list[dict[str, Any]] = []
    for task in task_state.get("tasks", []):
        if not isinstance(task, dict):
            continue
        task_id = _as_str(task.get("task_id")) or "TASK-UNKNOWN"
        phase_id = _as_str(task.get("phase_id")) or "phase-1"
        evidence_path = _task_evidence_path(req.repo_root, task)
        if not evidence_path.exists():
            evidence_errors.append({"task_id": task_id, "error": "missing", "path": str(evidence_path)})
            continue
        try:
            payload = _read_json(evidence_path)
        except OpError as exc:
            evidence_errors.append({"task_id": task_id, "error": exc.message, "path": str(evidence_path)})
            continue
        if not isinstance(payload, dict):
            evidence_errors.append({"task_id": task_id, "error": "not_object", "path": str(evidence_path)})
            continue
        schema_errors = _validate_task_evidence_payload(payload, task_id, phase_id)
        if schema_errors:
            evidence_errors.append({"task_id": task_id, "error": "schema_invalid", "details": schema_errors, "path": str(evidence_path)})
    checks.append({"id": "task_evidence_integrity", "passed": len(evidence_errors) == 0, "errors": evidence_errors})

    gaps_payload = _load_gaps_payload(_repo_path(req.repo_root, GAPS_JSON), _as_str(plan_packets.get("plan_id")) or "plan-unknown")
    open_gap_ids = [
        _as_str(item.get("gap_id"))
        for item in gaps_payload.get("gaps", [])
        if isinstance(item, dict) and _as_str(item.get("status")) == "open" and _as_str(item.get("gap_id"))
    ]
    if _repo_path(req.repo_root, GAP_CLOSURE_PLAN_PACKETS_JSON).exists():
        try:
            gap_closure_payload = _read_json(_repo_path(req.repo_root, GAP_CLOSURE_PLAN_PACKETS_JSON))
        except OpError as exc:
            warnings.append(
                {
                    "code": "gap_closure_packets_invalid",
                    "message": f"GAP_CLOSURE_PLAN_PACKETS.json unreadable: {exc.message}",
                    "stage": "health",
                }
            )
            gap_closure_payload = {"tasks": []}
    else:
        gap_closure_payload = {"tasks": []}
    if not isinstance(gap_closure_payload, dict):
        gap_closure_payload = {"tasks": []}
    closure_task_ids = {
        _as_str(task.get("source_gap_id"))
        for task in gap_closure_payload.get("tasks", [])
        if isinstance(task, dict) and _as_str(task.get("source_gap_id"))
    }
    gap_closure_ready = set(open_gap_ids).issubset(closure_task_ids)
    checks.append(
        {
            "id": "gap_closure_readiness",
            "passed": gap_closure_ready,
            "open_gap_ids": open_gap_ids,
        }
    )

    passed = all(bool(item.get("passed")) for item in checks)
    status = "completed" if passed else "blocked"
    summary = "OP health checks passed." if passed else "OP health checks detected blocking issues."
    return _response(
        req,
        ok=passed,
        status=status,
        summary=summary,
        warnings=warnings,
        errors=[] if passed else [{"code": "health_check_failed", "message": "one or more health checks failed", "stage": "health"}],
        artifacts=[
            str(_repo_path(req.repo_root, PLAN_PACKETS_JSON)),
            str(_repo_path(req.repo_root, TASK_EXECUTION_STATE_JSON)),
            str(_repo_path(req.repo_root, BUILD_STATE_JSON)),
            str(_repo_path(req.repo_root, GAPS_JSON)),
            str(_repo_path(req.repo_root, GAP_CLOSURE_PLAN_PACKETS_JSON)),
        ],
        state_ref=str(_repo_path(req.repo_root, BUILD_STATE_JSON)),
        data={
            "checks": checks,
            "open_gap_ids": open_gap_ids,
        },
    )


def command_status(req: OpRequest) -> dict[str, Any]:
    planning_root = _repo_path(req.repo_root, PLANNING_REL)
    plan_packets = _read_json(_repo_path(req.repo_root, PLAN_PACKETS_JSON)) if _repo_path(req.repo_root, PLAN_PACKETS_JSON).exists() else {}
    task_state = _read_json(_repo_path(req.repo_root, TASK_EXECUTION_STATE_JSON)) if _repo_path(req.repo_root, TASK_EXECUTION_STATE_JSON).exists() else {"tasks": []}
    build_state = _load_build_state(_repo_path(req.repo_root, BUILD_STATE_JSON)) if _repo_path(req.repo_root, BUILD_STATE_JSON).exists() else {"current_strategy": STRATEGY_LADDER[0]}
    gaps_payload = _load_gaps_payload(_repo_path(req.repo_root, GAPS_JSON), _as_str((plan_packets or {}).get("plan_id")) or "plan-unknown")
    merged_plan = _merge_plan_with_gap_closure(
        plan_packets if isinstance(plan_packets, dict) else {},
        _read_json(_repo_path(req.repo_root, GAP_CLOSURE_PLAN_PACKETS_JSON))
        if _repo_path(req.repo_root, GAP_CLOSURE_PLAN_PACKETS_JSON).exists()
        else {"tasks": []},
    )
    active_phase_id, phase_checks = _resolve_active_phase(
        merged_plan if isinstance(merged_plan, dict) else {"tasks": [], "phases": []},
        task_state if isinstance(task_state, dict) else {"tasks": []},
        gaps_payload,
        req.repo_root,
    )
    task_rows = task_state.get("tasks", []) if isinstance(task_state, dict) and isinstance(task_state.get("tasks"), list) else []
    counts_by_status: dict[str, int] = {}
    for task in task_rows:
        if not isinstance(task, dict):
            continue
        status = _as_str(task.get("status")) or "unknown"
        counts_by_status[status] = counts_by_status.get(status, 0) + 1
    open_gap_ids = [
        _as_str(item.get("gap_id"))
        for item in gaps_payload.get("gaps", [])
        if isinstance(item, dict) and _as_str(item.get("status")) == "open" and _as_str(item.get("gap_id"))
    ]
    next_action = (
        "/op-initialize"
        if not _repo_path(req.repo_root, STATE_JSON).exists()
        else "/op-resume" if _repo_path(req.repo_root, BUILD_STATE_JSON).exists() else "/op-build"
    )
    return _response(
        req,
        ok=True,
        status="completed",
        summary="OP status snapshot generated.",
        artifacts=[str(planning_root)],
        next_action=f"Use {next_action} for the next autonomous step.",
        state_ref=str(_repo_path(req.repo_root, BUILD_STATE_JSON)),
        data={
            "plan_id": _as_str((plan_packets or {}).get("plan_id")),
            "active_phase_id": active_phase_id,
            "phase_exit_checks": phase_checks,
            "task_counts_by_status": counts_by_status,
            "open_gap_ids": [gap_id for gap_id in open_gap_ids if gap_id],
            "active_workers": _active_workers_count(req.repo_root),
            "current_strategy": _as_str((build_state or {}).get("current_strategy")) or STRATEGY_LADDER[0],
            "gap_retry_attempts": (build_state or {}).get("gap_retry_attempts", {}),
            "gap_retry_exhausted_ids": (build_state or {}).get("gap_retry_exhausted_ids", []),
            "next_action": next_action,
        },
    )


def command_resume(req: OpRequest) -> dict[str, Any]:
    build_state_path = _repo_path(req.repo_root, BUILD_STATE_JSON)
    if not build_state_path.exists():
        return _response(
            req,
            ok=False,
            status="blocked_preflight",
            summary="Resume blocked: no existing build state found.",
            errors=[
                {
                    "code": "resume_unavailable",
                    "message": "BUILD_STATE.json is missing; run /op-build first.",
                    "stage": "resume",
                }
            ],
            next_action="Run /op-build to initialize autonomous execution state.",
            state_ref=str(build_state_path),
        )
    payload = _read_json(build_state_path)
    if not isinstance(payload, dict) or int(payload.get("last_cycle", 0)) <= 0:
        return _response(
            req,
            ok=False,
            status="blocked_preflight",
            summary="Resume blocked: existing build state is invalid for resume.",
            errors=[
                {
                    "code": "resume_unavailable",
                    "message": "BUILD_STATE.json has no resumable cycle history.",
                    "stage": "resume",
                }
            ],
            next_action="Run /op-build to start a fresh autonomous run.",
            state_ref=str(build_state_path),
        )
    return command_build(req)


def parse_request(payload: dict[str, Any]) -> OpRequest:
    command_raw = _as_str(payload.get("command"))
    if not command_raw:
        raise OpError("input_error", "command is required", stage="input")

    try:
        command = normalize_command(command_raw).canonical
    except ValueError as exc:
        raise OpError("input_error", str(exc), stage="input") from exc

    repo_root_raw = _as_str(payload.get("repo_root"))
    if not repo_root_raw:
        raise OpError("input_error", "repo_root is required", stage="input")

    repo_root = Path(repo_root_raw).expanduser().resolve()
    if not repo_root.exists():
        raise OpError("input_error", f"repo_root does not exist: {repo_root}", stage="input")

    if command not in SUPPORTED_COMMANDS:
        raise OpError(
            "input_error",
            "unsupported command; expected one of: " + ", ".join(sorted(SUPPORTED_COMMANDS)),
            stage="input",
        )

    max_build_cycles = payload.get("max_build_cycles")
    max_cycles_out: int | None
    if max_build_cycles is None:
        max_cycles_out = None
    else:
        try:
            parsed = int(max_build_cycles)
        except (TypeError, ValueError) as exc:
            raise OpError("input_error", "max_build_cycles must be integer", stage="input") from exc
        max_cycles_out = parsed if parsed > 0 else None

    default_sleep = 5 if command in {"op-build", "op-resume"} else 0
    sleep_minutes = payload.get("sleep_minutes", default_sleep)
    try:
        sleep_val = float(sleep_minutes)
    except (TypeError, ValueError) as exc:
        raise OpError("input_error", "sleep_minutes must be numeric", stage="input") from exc

    return OpRequest(
        command=command,
        repo_root=repo_root,
        mission=_as_str(payload.get("mission")),
        scope=_as_str(payload.get("scope")),
        constraints=_as_constraints(payload.get("constraints")),
        non_interactive=_as_bool(payload.get("non_interactive"), default=True),
        output_mode=_as_str(payload.get("output_mode")) or "json",
        max_build_cycles=max_cycles_out,
        sleep_minutes=max(0.0, sleep_val),
        dry_run=_as_bool(payload.get("dry_run"), default=False),
    )


def execute_request(req: OpRequest) -> dict[str, Any]:
    if req.command == "op-map-codebase":
        return command_map_codebase(req)
    if req.command == "op-new-project":
        return command_new_project(req)
    if req.command == "op-plan":
        return command_plan(req)
    if req.command == "op-initialize":
        return command_initialize(req)
    if req.command == "op-build":
        return command_build(req)
    if req.command == "op-health":
        return command_health(req)
    if req.command == "op-status":
        return command_status(req)
    if req.command == "op-resume":
        return command_resume(req)
    raise OpError(
        "input_error",
        "unsupported command; expected one of: " + ", ".join(sorted(SUPPORTED_COMMANDS)),
        stage="input",
    )


def run_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    req = parse_request(payload)
    return execute_request(req)
