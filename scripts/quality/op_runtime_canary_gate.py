#!/usr/bin/env python3
"""Runtime canary gate for real OP project runs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
DEFAULT_STALE_SECONDS = 3600
DEFAULT_FIX_STREAK = 3

PLANNING_REL = Path("reports") / "optimus-prime" / "planning"
CONTROL_REL = Path("reports") / "optimus-prime" / "controller"
ROOT_REL = Path("reports") / "optimus-prime"
VOLATILE_DETAIL_KEYS = {
    "age_seconds",
    "latest_at",
    "generated_at",
    "updated_at",
    "first_seen_at",
    "last_seen_at",
    "lock_path",
    "registry_path",
    "watchdog_path",
    "events_path",
    "project_root",
    "dispatch_pid",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


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


def _read_json(path: Path) -> tuple[Any, str | None]:
    if not path.exists():
        return None, "missing"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except json.JSONDecodeError as exc:
        return None, f"invalid_json:{exc}"
    except OSError as exc:
        return None, f"unreadable:{exc}"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
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
                out.append(row)
    except OSError:
        return []
    return out


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def _workers_from_registry(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        raw = payload.get("workers")
        if isinstance(raw, list):
            return [item for item in raw if isinstance(item, dict)]
        if isinstance(raw, dict):
            return [item for item in raw.values() if isinstance(item, dict)]
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _severity_rank(value: str) -> int:
    order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    return order.get(value, 9)


def _owner_batch_for_severity(severity: str) -> str:
    if severity in {"P0", "P1"}:
        return "A"
    if severity == "P2":
        return "B"
    return "C"


def _check_lock_consistency(project_root: Path) -> dict[str, Any]:
    lock_path = project_root / PLANNING_REL / "BUILD_LOOP.lock"
    payload, err = _read_json(lock_path)
    if err == "missing":
        return {"id": "lock_consistency", "passed": True, "severity": "P1", "details": {"lock_exists": False}}
    if err:
        return {
            "id": "lock_consistency",
            "passed": False,
            "severity": "P1",
            "details": {"error": err, "lock_path": str(lock_path)},
        }
    if not isinstance(payload, dict):
        return {
            "id": "lock_consistency",
            "passed": False,
            "severity": "P1",
            "details": {"error": "lock_not_object", "lock_path": str(lock_path)},
        }
    pid = payload.get("pid")
    pid_alive = isinstance(pid, int) and _pid_is_running(pid)
    return {
        "id": "lock_consistency",
        "passed": pid_alive,
        "severity": "P1",
        "details": {
            "lock_exists": True,
            "pid": pid,
            "pid_alive": pid_alive,
            "lock_path": str(lock_path),
        },
    }


def _check_worker_registry_pid_state_parity(project_root: Path) -> dict[str, Any]:
    registry_path = project_root / ROOT_REL / "WORKER_REGISTRY.json"
    payload, err = _read_json(registry_path)
    if err == "missing":
        return {"id": "worker_registry_pid_state_parity", "passed": True, "severity": "P1", "details": {"workers": 0}}
    if err:
        return {
            "id": "worker_registry_pid_state_parity",
            "passed": False,
            "severity": "P1",
            "details": {"error": err, "registry_path": str(registry_path)},
        }
    workers = _workers_from_registry(payload)
    stale_rows: list[dict[str, Any]] = []
    for worker in workers:
        state = (_as_str(worker.get("session_state")) or _as_str(worker.get("state")) or _as_str(worker.get("status")) or "").lower()
        if state not in {"running", "active", "busy"}:
            continue
        pid = worker.get("dispatch_pid")
        pid_alive = isinstance(pid, int) and _pid_is_running(pid)
        if not pid_alive:
            stale_rows.append(
                {
                    "slot": _as_str(worker.get("slot")) or "unknown-slot",
                    "state": state,
                    "dispatch_pid": pid,
                }
            )
    return {
        "id": "worker_registry_pid_state_parity",
        "passed": len(stale_rows) == 0,
        "severity": "P1",
        "details": {
            "workers": len(workers),
            "stale_running_workers": stale_rows,
            "registry_path": str(registry_path),
        },
    }


def _check_watchdog_alignment(project_root: Path) -> dict[str, Any]:
    watchdog_path = project_root / PLANNING_REL / "NO_PROGRESS_WATCHDOG_STATE.json"
    task_state_path = project_root / PLANNING_REL / "TASK_EXECUTION_STATE.json"
    build_state_path = project_root / PLANNING_REL / "BUILD_STATE.json"

    watchdog, watchdog_err = _read_json(watchdog_path)
    if watchdog_err:
        return {
            "id": "watchdog_alignment",
            "passed": False,
            "severity": "P1",
            "details": {"error": watchdog_err, "watchdog_path": str(watchdog_path)},
        }
    if not isinstance(watchdog, dict):
        return {
            "id": "watchdog_alignment",
            "passed": False,
            "severity": "P1",
            "details": {"error": "watchdog_not_object", "watchdog_path": str(watchdog_path)},
        }

    task_state, task_err = _read_json(task_state_path)
    build_state, build_err = _read_json(build_state_path)
    in_progress_count = 0
    if isinstance(task_state, dict) and isinstance(task_state.get("tasks"), list):
        for row in task_state["tasks"]:
            if isinstance(row, dict):
                status = (_as_str(row.get("status")) or "").lower()
                if status.endswith("_in_progress"):
                    in_progress_count += 1
    consecutive = int(watchdog.get("consecutive_no_progress_cycles") or 0)
    threshold = int(watchdog.get("threshold_cycles") or 25)
    triggered = bool(watchdog.get("triggered"))
    terminal_state = (build_state or {}).get("terminal_state") if isinstance(build_state, dict) else None
    if isinstance(terminal_state, dict):
        terminal_reason = _as_str(terminal_state.get("reason"))
    else:
        terminal_reason = _as_str(terminal_state)
    blocked = in_progress_count > 0 and consecutive >= threshold and not triggered and terminal_reason != "no_progress_watchdog"
    return {
        "id": "watchdog_alignment",
        "passed": (task_err is None and build_err is None and not blocked),
        "severity": "P1",
        "details": {
            "consecutive_no_progress_cycles": consecutive,
            "threshold_cycles": threshold,
            "triggered": triggered,
            "in_progress_tasks": in_progress_count,
            "terminal_reason": terminal_reason,
            "task_state_error": task_err,
            "build_state_error": build_err,
            "watchdog_path": str(watchdog_path),
        },
    }


def _check_plan_id_parity(project_root: Path) -> dict[str, Any]:
    plan_packets_path = project_root / PLANNING_REL / "PLAN_PACKETS.json"
    task_state_path = project_root / PLANNING_REL / "TASK_EXECUTION_STATE.json"
    plan_packets, plan_err = _read_json(plan_packets_path)
    task_state, task_err = _read_json(task_state_path)
    ids: dict[str, str] = {}
    missing_sources: list[str] = []
    if isinstance(plan_packets, dict):
        pid = _as_str(plan_packets.get("plan_id"))
        if pid:
            ids["PLAN_PACKETS"] = pid
        else:
            missing_sources.append("PLAN_PACKETS")
    else:
        missing_sources.append("PLAN_PACKETS")
    evidence_ids: set[str] = set()
    if isinstance(task_state, dict):
        tid = _as_str(task_state.get("plan_id"))
        if tid:
            ids["TASK_EXECUTION_STATE"] = tid
        else:
            missing_sources.append("TASK_EXECUTION_STATE")
        tasks = task_state.get("tasks") if isinstance(task_state.get("tasks"), list) else []
        for row in tasks:
            if not isinstance(row, dict):
                continue
            task_id = _as_str(row.get("task_id"))
            if not task_id:
                continue
            evidence_path = project_root / PLANNING_REL / "evidence" / task_id / "TASK_EVIDENCE.json"
            payload, err = _read_json(evidence_path)
            if err:
                missing_sources.append(f"EVIDENCE:{task_id}:{err}")
                continue
            if not isinstance(payload, dict):
                missing_sources.append(f"EVIDENCE:{task_id}:not_object")
                continue
            eid = _as_str(payload.get("plan_id"))
            if not eid:
                missing_sources.append(f"EVIDENCE:{task_id}:missing_plan_id")
                continue
            evidence_ids.add(eid)
    else:
        missing_sources.append(f"TASK_EXECUTION_STATE:{task_err or 'invalid'}")
    for idx, eid in enumerate(sorted(evidence_ids)):
        ids[f"EVIDENCE_GROUP_{idx+1}"] = eid
    distinct_ids = sorted(set(ids.values()))
    passed = plan_err is None and task_err is None and len(missing_sources) == 0 and len(distinct_ids) == 1
    return {
        "id": "plan_id_parity",
        "passed": passed,
        "severity": "P1",
        "details": {
            "plan_ids": ids,
            "distinct_plan_ids": distinct_ids,
            "missing_sources": missing_sources,
            "plan_packets_error": plan_err,
            "task_state_error": task_err,
        },
    }


def _check_handoff_freshness(project_root: Path, *, stale_seconds: int) -> dict[str, Any]:
    task_state_path = project_root / PLANNING_REL / "TASK_EXECUTION_STATE.json"
    handoff_path = project_root / ROOT_REL / "HANDOFF_LOG.jsonl"
    task_state, task_err = _read_json(task_state_path)
    handoff_rows = _read_jsonl(handoff_path)
    latest_handoff_by_task: dict[str, datetime] = {}
    for row in handoff_rows:
        task_id = _as_str(row.get("task_identifier")) or _as_str(row.get("task_id"))
        if not task_id:
            continue
        ts = _parse_iso_utc(row.get("timestamp"))
        if ts is None:
            continue
        prior = latest_handoff_by_task.get(task_id)
        if prior is None or ts > prior:
            latest_handoff_by_task[task_id] = ts
    now = datetime.now(timezone.utc)
    stale_rows: list[dict[str, Any]] = []
    in_progress_count = 0
    if isinstance(task_state, dict):
        tasks = task_state.get("tasks") if isinstance(task_state.get("tasks"), list) else []
        for row in tasks:
            if not isinstance(row, dict):
                continue
            task_id = _as_str(row.get("task_id")) or "TASK-UNKNOWN"
            status = (_as_str(row.get("status")) or "").lower()
            if not status.endswith("_in_progress"):
                continue
            in_progress_count += 1
            task_ts = _parse_iso_utc(row.get("last_progress_at")) or _parse_iso_utc(row.get("updated_at"))
            handoff_ts = latest_handoff_by_task.get(task_id)
            latest_ts = handoff_ts if task_ts is None else (task_ts if handoff_ts is None or task_ts > handoff_ts else handoff_ts)
            if latest_ts is None:
                stale_rows.append({"task_id": task_id, "reason": "no_progress_or_handoff_timestamp"})
                continue
            age_sec = int((now - latest_ts).total_seconds())
            if age_sec > stale_seconds:
                stale_rows.append({"task_id": task_id, "age_seconds": age_sec, "latest_at": latest_ts.isoformat().replace("+00:00", "Z")})
    return {
        "id": "handoff_freshness",
        "passed": task_err is None and len(stale_rows) == 0,
        "severity": "P1",
        "details": {
            "in_progress_tasks": in_progress_count,
            "stale_rows": stale_rows,
            "stale_seconds": stale_seconds,
            "task_state_error": task_err,
        },
    }


def _check_control_correlation(project_root: Path) -> dict[str, Any]:
    events_path = project_root / CONTROL_REL / "EVENTS.jsonl"
    rows = _read_jsonl(events_path)
    run_ids_by_control: dict[int, set[str]] = {}
    missing_run_id_rows: list[dict[str, Any]] = []
    for row in rows:
        control_number = row.get("control_number")
        if not isinstance(control_number, int) or control_number <= 0:
            continue
        run_id = _as_str(row.get("control_run_id"))
        if not run_id:
            missing_run_id_rows.append(
                {
                    "control_number": control_number,
                    "event_type": _as_str(row.get("event_type")),
                    "action_code": _as_str(row.get("action_code")),
                }
            )
            continue
        run_ids_by_control.setdefault(control_number, set()).add(run_id)
    mismatches = {
        str(control): sorted(list(ids))
        for control, ids in run_ids_by_control.items()
        if len(ids) > 1
    }
    passed = len(missing_run_id_rows) == 0 and len(mismatches) == 0
    return {
        "id": "control_correlation_continuity",
        "passed": passed,
        "severity": "P2",
        "details": {
            "missing_run_id_rows": missing_run_id_rows,
            "control_run_id_mismatches": mismatches,
            "events_path": str(events_path),
        },
    }


def _default_findings_payload(project_name: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "project": project_name,
        "updated_at": utc_now_iso(),
        "findings": [],
    }


def _load_findings(path: Path, project_name: str) -> dict[str, Any]:
    payload, err = _read_json(path)
    if err or not isinstance(payload, dict):
        return _default_findings_payload(project_name)
    findings = payload.get("findings")
    if not isinstance(findings, list):
        payload["findings"] = []
    payload["schema_version"] = SCHEMA_VERSION
    payload["project"] = _as_str(payload.get("project")) or project_name
    payload["updated_at"] = utc_now_iso()
    return payload


def _finding_category(check_id: str) -> str:
    mapping = {
        "lock_consistency": "deadlock",
        "worker_registry_pid_state_parity": "deadlock",
        "watchdog_alignment": "deadlock",
        "plan_id_parity": "state_drift",
        "handoff_freshness": "ingestion",
        "control_correlation_continuity": "control_correlation",
    }
    return mapping.get(check_id, "other")


def _sanitize_fingerprint_value(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key in sorted(value.keys()):
            if key in VOLATILE_DETAIL_KEYS:
                continue
            out[key] = _sanitize_fingerprint_value(value[key])
        return out
    if isinstance(value, list):
        normalized = [_sanitize_fingerprint_value(item) for item in value]
        try:
            return sorted(normalized, key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")))
        except TypeError:
            return normalized
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _fingerprint_input_for_check(check: dict[str, Any]) -> dict[str, Any]:
    check_id = _as_str(check.get("id")) or "unknown_check"
    details = check.get("details") if isinstance(check.get("details"), dict) else {"details": check.get("details")}

    if check_id == "handoff_freshness":
        stale_rows = details.get("stale_rows") if isinstance(details.get("stale_rows"), list) else []
        stale_task_ids = sorted(
            {
                task_id
                for task_id in (_as_str(item.get("task_id")) for item in stale_rows if isinstance(item, dict))
                if task_id
            }
        )
        stale_reasons = sorted(
            {
                reason
                for reason in (_as_str(item.get("reason")) for item in stale_rows if isinstance(item, dict))
                if reason
            }
        )
        return {
            "check_id": check_id,
            "stale_task_ids": stale_task_ids,
            "stale_reasons": stale_reasons,
            "stale_count": len(stale_task_ids),
            "task_state_error": _as_str(details.get("task_state_error")),
        }

    if check_id == "worker_registry_pid_state_parity":
        stale_rows = details.get("stale_running_workers") if isinstance(details.get("stale_running_workers"), list) else []
        stale_worker_keys = sorted(
            {
                f"{_as_str(item.get('slot')) or 'unknown-slot'}|{_as_str(item.get('state')) or 'unknown-state'}"
                for item in stale_rows
                if isinstance(item, dict)
            }
        )
        return {
            "check_id": check_id,
            "stale_workers": stale_worker_keys,
            "error": _as_str(details.get("error")),
        }

    if check_id == "plan_id_parity":
        distinct_ids = details.get("distinct_plan_ids")
        if not isinstance(distinct_ids, list):
            distinct_ids = []
        missing_sources = details.get("missing_sources")
        if not isinstance(missing_sources, list):
            missing_sources = []
        return {
            "check_id": check_id,
            "distinct_plan_ids": sorted(str(item) for item in distinct_ids),
            "missing_sources": sorted(str(item) for item in missing_sources),
        }

    if check_id == "watchdog_alignment":
        return {
            "check_id": check_id,
            "error": _as_str(details.get("error")),
            "consecutive_no_progress_cycles": int(details.get("consecutive_no_progress_cycles") or 0),
            "threshold_cycles": int(details.get("threshold_cycles") or 0),
            "triggered": bool(details.get("triggered")),
            "in_progress_tasks": int(details.get("in_progress_tasks") or 0),
            "terminal_reason": _as_str(details.get("terminal_reason")),
        }

    if check_id == "lock_consistency":
        return {
            "check_id": check_id,
            "error": _as_str(details.get("error")),
            "lock_exists": bool(details.get("lock_exists")),
            "pid_alive": bool(details.get("pid_alive")),
        }

    if check_id == "control_correlation_continuity":
        missing_rows = details.get("missing_run_id_rows") if isinstance(details.get("missing_run_id_rows"), list) else []
        missing_controls = sorted(
            {
                int(item.get("control_number"))
                for item in missing_rows
                if isinstance(item, dict) and isinstance(item.get("control_number"), int)
            }
        )
        mismatches = details.get("control_run_id_mismatches")
        mismatch_controls = sorted(str(key) for key in mismatches.keys()) if isinstance(mismatches, dict) else []
        return {
            "check_id": check_id,
            "missing_control_numbers": missing_controls,
            "mismatch_control_numbers": mismatch_controls,
        }

    return {
        "check_id": check_id,
        "details": _sanitize_fingerprint_value(details),
    }


def _update_findings(
    findings_payload: dict[str, Any],
    project_root: Path,
    checks: list[dict[str, Any]],
    *,
    fix_streak: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    now = utc_now_iso()
    findings_raw = findings_payload.get("findings") if isinstance(findings_payload.get("findings"), list) else []
    findings: list[dict[str, Any]] = [item for item in findings_raw if isinstance(item, dict)]
    by_id: dict[str, dict[str, Any]] = {}
    for row in findings:
        fid = _as_str(row.get("finding_id"))
        if fid:
            by_id[fid] = row
    seen_ids: set[str] = set()
    for check in checks:
        if bool(check.get("passed")):
            continue
        check_id = _as_str(check.get("id")) or "unknown_check"
        fingerprint_payload = _fingerprint_input_for_check(check)
        fingerprint = _sha256(json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")))[:12]
        finding_id = f"rf-{fingerprint}"
        seen_ids.add(finding_id)
        severity = _as_str(check.get("severity")) or "P2"
        category = _finding_category(check_id)
        evidence_refs = sorted(
            {
                str(project_root / CONTROL_REL / "EVENTS.jsonl"),
                str(project_root / PLANNING_REL / "BUILD_STATE.json"),
                str(project_root / PLANNING_REL / "TASK_EXECUTION_STATE.json"),
                str(project_root / ROOT_REL / "WORKER_REGISTRY.json"),
            }
        )
        current = by_id.get(finding_id)
        if current is None:
            current = {
                "finding_id": finding_id,
                "severity": severity,
                "category": category,
                "first_seen_at": now,
                "last_seen_at": now,
                "count": 1,
                "status": "open",
                "evidence_refs": evidence_refs,
                "owner_batch": _owner_batch_for_severity(severity),
                "clean_pass_streak": 0,
            }
            findings.append(current)
            by_id[finding_id] = current
            continue
        current["severity"] = severity
        current["category"] = category
        current["last_seen_at"] = now
        current["count"] = int(current.get("count") or 0) + 1
        prev_status = _as_str(current.get("status")) or "open"
        current["status"] = "regressed" if prev_status == "fixed" else "open"
        current["owner_batch"] = _owner_batch_for_severity(severity)
        existing_refs = current.get("evidence_refs")
        ref_set = set(existing_refs) if isinstance(existing_refs, list) else set()
        ref_set.update(evidence_refs)
        current["evidence_refs"] = sorted(ref_set)
        current["clean_pass_streak"] = 0

    for row in findings:
        fid = _as_str(row.get("finding_id"))
        if not fid:
            continue
        if fid in seen_ids:
            continue
        status = _as_str(row.get("status")) or "open"
        if status not in {"open", "in_progress", "regressed"}:
            continue
        streak = int(row.get("clean_pass_streak") or 0) + 1
        row["clean_pass_streak"] = streak
        if streak >= fix_streak:
            row["status"] = "fixed"
            row["last_seen_at"] = now

    findings.sort(key=lambda item: (_severity_rank(_as_str(item.get("severity")) or "P3"), _as_str(item.get("first_seen_at")) or ""))
    findings_payload["findings"] = findings
    findings_payload["updated_at"] = now
    open_rows = [
        {
            "finding_id": _as_str(row.get("finding_id")),
            "severity": _as_str(row.get("severity")) or "P3",
            "category": _as_str(row.get("category")) or "other",
            "status": _as_str(row.get("status")) or "open",
            "owner_batch": _as_str(row.get("owner_batch")) or "C",
        }
        for row in findings
        if (_as_str(row.get("status")) or "open") in {"open", "in_progress", "regressed"}
    ]
    return findings_payload, [row for row in open_rows if row.get("finding_id")]


def run_canary(project_root: Path, project_name: str, *, stale_seconds: int, fix_streak: int) -> dict[str, Any]:
    checks = [
        _check_lock_consistency(project_root),
        _check_worker_registry_pid_state_parity(project_root),
        _check_watchdog_alignment(project_root),
        _check_plan_id_parity(project_root),
        _check_handoff_freshness(project_root, stale_seconds=stale_seconds),
        _check_control_correlation(project_root),
    ]
    findings_path = project_root / PLANNING_REL / "RUN_FINDINGS.json"
    findings_payload = _load_findings(findings_path, project_name)
    findings_payload, findings_open = _update_findings(
        findings_payload,
        project_root,
        checks,
        fix_streak=fix_streak,
    )
    _write_json(findings_path, findings_payload)

    status = "passed" if all(bool(check.get("passed")) for check in checks) else "blocked"
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "project": project_name,
        "checks": checks,
        "findings_open": findings_open,
        "status": status,
        "next_action": (
            "Runtime canary gate passed."
            if status == "passed"
            else "Fix open runtime findings (prioritize P0/P1), rerun canary gate, then continue remediation."
        ),
        "artifacts": {
            "canary_gate": str(project_root / PLANNING_REL / "LANE_B_RUNTIME_CANARY_GATE.json"),
            "run_findings": str(findings_path),
        },
    }
    artifact_path = project_root / PLANNING_REL / "LANE_B_RUNTIME_CANARY_GATE.json"
    _write_json(artifact_path, artifact)
    return artifact


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deterministic OP runtime canary gate for a real project.")
    parser.add_argument("--project-root", required=True, help="Absolute path to canary project root (for example MyBoard)")
    parser.add_argument("--project-name", default="MyBoard")
    parser.add_argument("--stale-seconds", type=int, default=DEFAULT_STALE_SECONDS)
    parser.add_argument("--fix-streak", type=int, default=DEFAULT_FIX_STREAK)
    parser.add_argument("--json-pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).expanduser().resolve()
    if not project_root.exists() or not project_root.is_dir():
        out = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": utc_now_iso(),
            "project": args.project_name,
            "status": "blocked",
            "checks": [
                {
                    "id": "project_root_exists",
                    "passed": False,
                    "severity": "P1",
                    "details": {"project_root": str(project_root), "error": "missing_or_not_directory"},
                }
            ],
            "findings_open": [],
            "next_action": "Set a valid canary --project-root and rerun the runtime canary gate.",
        }
        print(json.dumps(out, indent=2 if args.json_pretty else None, sort_keys=False))
        return 1

    stale_seconds = max(60, int(args.stale_seconds))
    fix_streak = max(1, int(args.fix_streak))
    out = run_canary(project_root, args.project_name, stale_seconds=stale_seconds, fix_streak=fix_streak)
    print(json.dumps(out, indent=2 if args.json_pretty else None, sort_keys=False))
    return 0 if out.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
