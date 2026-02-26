#!/usr/bin/env python3
"""Build a deterministic, read-only orchestration status snapshot."""

from __future__ import annotations

import argparse
import json
import os
import signal
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TOOL_NAME = "orchestrator-status-snapshot"
TOOL_VERSION = "0.1.0"
SCHEMA_VERSION = "1.0"

SLOT_ORDER = ["dev-1", "dev-2", "dev-3", "test-1", "test-2", "review-1"]
ROLE_BY_SLOT = {
    "dev-1": "developer",
    "dev-2": "developer",
    "dev-3": "developer",
    "test-1": "tester",
    "test-2": "tester",
    "review-1": "reviewer",
}
ALLOWED_STATES = {"running", "idle", "blocked", "stopped"}
ALLOWED_HARD_GATES = {"eligible", "gated", "waiting-reset", "wind-down"}
ALLOWED_NEXT_ACTIONS = {
    "idle_ready",
    "waiting_for_test",
    "waiting_for_review",
    "needs_rework",
    "waiting_on_user",
    "waiting_on_dependency",
}


@dataclass
class InputConfig:
    repo_root: Path
    include_history: bool
    max_history_items: int
    include_process_check: bool
    output_mode: str


@dataclass
class SnapshotContext:
    warnings: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    parse_warning_count: int

    def warn(self, code: str, message: str, path: Path | None = None, **extra: Any) -> None:
        item: dict[str, Any] = {"code": code, "message": message}
        if path is not None:
            item["path"] = str(path)
        if extra:
            item.update(extra)
        self.warnings.append(item)

    def error(self, code: str, message: str, path: Path | None = None, **extra: Any) -> None:
        item: dict[str, Any] = {"code": code, "message": message}
        if path is not None:
            item["path"] = str(path)
        if extra:
            item.update(extra)
        self.errors.append(item)


# ---------- parsing helpers ----------


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def to_utc_iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        except (ValueError, OSError):
            return None
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            dt = datetime.fromisoformat(raw[:-1] + "+00:00")
        else:
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except ValueError:
        return None


def first_present(obj: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in obj and obj[key] is not None:
            return obj[key]
    return None


def as_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, (int, float, bool)):
        return str(value)
    return None


def as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_state(raw: Any) -> str:
    text = (as_str(raw) or "").strip().lower().replace("_", "-")
    if text in ALLOWED_STATES:
        return text
    if "block" in text:
        return "blocked"
    if "run" in text or "active" in text or "busy" in text:
        return "running"
    if "stop" in text or "exit" in text or "done" in text:
        return "stopped"
    return "idle"


def normalize_next_expected_action(raw: Any, state: str, last_result: str | None, blocker_summary: str | None) -> str:
    text = (as_str(raw) or "").strip().lower().replace("_", "-")
    if text in ALLOWED_NEXT_ACTIONS:
        return text
    if "review" in text:
        return "waiting_for_review"
    if "test" in text:
        return "waiting_for_test"
    if "rework" in text or "fix" in text:
        return "needs_rework"
    if "user" in text:
        return "waiting_on_user"
    if "depend" in text or "external" in text:
        return "waiting_on_dependency"
    if state == "blocked":
        summary = (blocker_summary or "").lower()
        if "user" in summary:
            return "waiting_on_user"
        if "depend" in summary or "external" in summary:
            return "waiting_on_dependency"
        return "needs_rework"
    if last_result:
        lr = last_result.lower()
        if "review" in lr:
            return "waiting_for_review"
        if "test" in lr:
            return "waiting_for_test"
        if "block" in lr:
            return "needs_rework"
    return "idle_ready"


def hard_gate_from_profile(profile: dict[str, Any]) -> str:
    direct = as_str(first_present(profile, ["hard_gate", "gate_state", "dispatch_gate"]))
    if direct in ALLOWED_HARD_GATES:
        return direct

    rec_action = (as_str(first_present(profile, ["recommended_action", "action"])) or "").lower()
    if rec_action == "wait_until_reset":
        return "waiting-reset"
    if rec_action == "wind_down":
        return "wind-down"

    five_h = first_present(profile, ["five_hour", "primary", "window_5h"])
    weekly = first_present(profile, ["weekly", "secondary", "window_weekly"])
    gated = False
    if isinstance(five_h, dict) and bool(five_h.get("gated")):
        gated = True
    if isinstance(weekly, dict) and bool(weekly.get("gated")):
        gated = True
    if bool(first_present(profile, ["gated", "hard_gated"])):
        gated = True
    return "gated" if gated else "eligible"


def pid_alive(pid: int | None, include_process_check: bool) -> bool | None:
    if pid is None:
        return None
    if not include_process_check:
        return None
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def read_json_file(path: Path, ctx: SnapshotContext) -> tuple[Any | None, bool]:
    if not path.exists():
        ctx.error("missing_file", "Required file is missing", path)
        return None, False
    try:
        return json.loads(path.read_text(encoding="utf-8")), True
    except json.JSONDecodeError as exc:
        ctx.error("malformed_json", f"Malformed JSON file: {exc}", path)
        return None, False
    except OSError as exc:
        ctx.error("read_error", f"Failed to read JSON file: {exc}", path)
        return None, False


def read_jsonl_file(path: Path, ctx: SnapshotContext) -> tuple[list[dict[str, Any]], bool]:
    if not path.exists():
        ctx.error("missing_file", "Required file is missing", path)
        return [], False

    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for idx, line in enumerate(fh, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    obj = json.loads(stripped)
                except json.JSONDecodeError:
                    ctx.parse_warning_count += 1
                    ctx.warn(
                        "malformed_jsonl_line",
                        "Skipping malformed JSONL line",
                        path,
                        line_number=idx,
                    )
                    continue
                if isinstance(obj, dict):
                    rows.append(obj)
                else:
                    ctx.parse_warning_count += 1
                    ctx.warn(
                        "jsonl_non_object",
                        "Skipping JSONL line because it is not a JSON object",
                        path,
                        line_number=idx,
                    )
    except OSError as exc:
        ctx.error("read_error", f"Failed to read JSONL file: {exc}", path)
        return [], False

    return rows, True


def read_json_optional(path: Path, ctx: SnapshotContext) -> tuple[Any | None, bool]:
    if not path.exists():
        return None, False
    try:
        return json.loads(path.read_text(encoding="utf-8")), True
    except json.JSONDecodeError as exc:
        ctx.warn("malformed_optional_json", f"Malformed optional JSON file: {exc}", path)
        return None, False
    except OSError as exc:
        ctx.warn("optional_read_error", f"Failed to read optional JSON file: {exc}", path)
        return None, False


def read_jsonl_optional(path: Path, ctx: SnapshotContext) -> tuple[list[dict[str, Any]], bool]:
    if not path.exists():
        return [], False
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for idx, line in enumerate(fh, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    obj = json.loads(stripped)
                except json.JSONDecodeError:
                    ctx.warn("malformed_optional_jsonl_line", "Skipping malformed optional JSONL line", path, line_number=idx)
                    continue
                if isinstance(obj, dict):
                    rows.append(obj)
    except OSError as exc:
        ctx.warn("optional_read_error", f"Failed to read optional JSONL file: {exc}", path)
        return [], False
    return rows, True


# ---------- domain extraction ----------


def latest_cycle(cycle_rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not cycle_rows:
        return {"number": None, "timestamp": None}
    last = cycle_rows[-1]

    cycle_obj = last.get("cycle") if isinstance(last.get("cycle"), dict) else {}
    number = first_present(last, ["cycle_number", "cycle", "number"])
    if isinstance(number, dict):
        number = None
    if number is None:
        number = first_present(cycle_obj, ["number", "cycle_number", "id"])
    number_int = as_int(number)

    timestamp_raw = first_present(last, ["timestamp", "generated_at", "created_at", "time", "at"])
    if timestamp_raw is None:
        timestamp_raw = first_present(cycle_obj, ["timestamp", "at", "created_at"])
    timestamp = to_utc_iso(timestamp_raw)

    return {"number": number_int, "timestamp": timestamp}


def worker_map_from_registry(worker_registry: Any) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}

    def add_worker(raw: dict[str, Any], slot_hint: str | None = None) -> None:
        slot = as_str(first_present(raw, ["slot", "worker_slot", "name", "id"])) or slot_hint
        if slot in SLOT_ORDER:
            result[slot] = raw

    if isinstance(worker_registry, dict):
        workers = worker_registry.get("workers")
        if isinstance(workers, list):
            for item in workers:
                if isinstance(item, dict):
                    add_worker(item)
        elif isinstance(workers, dict):
            for slot, item in workers.items():
                if isinstance(item, dict):
                    add_worker(item, slot_hint=slot)

        for key in ("worker_slots", "registry", "slots"):
            maybe = worker_registry.get(key)
            if isinstance(maybe, dict):
                for slot, item in maybe.items():
                    if isinstance(item, dict):
                        add_worker(item, slot_hint=slot)

        for slot in SLOT_ORDER:
            item = worker_registry.get(slot)
            if isinstance(item, dict):
                add_worker(item, slot_hint=slot)

    elif isinstance(worker_registry, list):
        for item in worker_registry:
            if isinstance(item, dict):
                add_worker(item)

    return result


def latest_handoff_by_slot(handoff_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in handoff_rows:
        slot = as_str(first_present(row, ["slot", "worker_slot", "owner_slot", "actor_slot"]))
        if slot in SLOT_ORDER:
            latest[slot] = row
    return latest


def blocker_items(handoff_rows: list[dict[str, Any]], workers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for worker in workers:
        if worker["state"] == "blocked" or worker.get("blocker_summary"):
            task = worker.get("active_task") or "unknown"
            owner = worker["slot"]
            summary = worker.get("blocker_summary") or "Blocked worker requires intervention"
            key = (task, owner, summary)
            if key not in seen:
                seen.add(key)
                items.append({"task_identifier": task, "owner": owner, "summary": summary})

    for row in handoff_rows:
        result = (as_str(first_present(row, ["result", "handoff_result", "outcome", "status"])) or "").lower()
        blocker_summary = as_str(first_present(row, ["blocker_summary", "blocker", "reason", "error_summary", "summary"]))
        is_blocked = "block" in result or blocker_summary is not None
        if not is_blocked:
            continue
        task = as_str(first_present(row, ["task_identifier", "issue_identifier", "task", "issue"])) or "unknown"
        owner = as_str(first_present(row, ["owner", "slot", "worker_slot", "assignee"])) or "external"
        summary = blocker_summary or (as_str(first_present(row, ["message", "details"])) or "Blocked during handoff")
        key = (task, owner, summary)
        if key in seen:
            continue
        seen.add(key)
        items.append({"task_identifier": task, "owner": owner, "summary": summary})

    return items


def extract_rate_profiles(
    profile_rate_registry: Any,
    rate_status_rows: list[dict[str, Any]],
    max_running_workers_default: int,
) -> tuple[str, list[dict[str, Any]]]:
    running_mode = "unknown"
    soft_cap = 3

    candidate_profiles: dict[str, dict[str, Any]] = {}

    if isinstance(profile_rate_registry, dict):
        running_mode = as_str(profile_rate_registry.get("profile_running_mode")) or running_mode

        soft = profile_rate_registry.get("soft_concurrency")
        if isinstance(soft, dict):
            soft_cap = as_int(first_present(soft, ["max_active_workers_when_gated", "soft_max_active_workers", "effective_cap"])) or soft_cap

        profiles = profile_rate_registry.get("profiles")
        if isinstance(profiles, dict):
            for alias, value in profiles.items():
                if isinstance(value, dict):
                    candidate_profiles[alias] = value
        elif isinstance(profiles, list):
            for value in profiles:
                if isinstance(value, dict):
                    alias = as_str(first_present(value, ["alias", "profile", "name"]))
                    if alias:
                        candidate_profiles[alias] = value

    if rate_status_rows:
        last = rate_status_rows[-1]
        if running_mode == "unknown":
            running_mode = as_str(first_present(last, ["profile_running_mode", "running_mode"])) or running_mode

        last_soft = first_present(last, ["soft_concurrency", "soft_gate", "soft"])
        if isinstance(last_soft, dict):
            soft_cap = as_int(first_present(last_soft, ["max_active_workers_when_gated", "soft_max_active_workers", "effective_cap"])) or soft_cap

        if not candidate_profiles:
            last_profiles = first_present(last, ["profiles", "profile_snapshots"])
            if isinstance(last_profiles, dict):
                for alias, value in last_profiles.items():
                    if isinstance(value, dict):
                        candidate_profiles[alias] = value

    items: list[dict[str, Any]] = []
    for alias in sorted(candidate_profiles.keys()):
        profile = candidate_profiles[alias]
        hard_gate = hard_gate_from_profile(profile)
        soft_gated = bool(first_present(profile, ["soft_concurrency_gated", "soft_gated"]))
        effective_cap = as_int(first_present(profile, ["effective_cap", "max_active_workers", "cap"]))
        if effective_cap is None:
            if hard_gate in {"gated", "waiting-reset", "wind-down"}:
                effective_cap = 0
            elif soft_gated:
                effective_cap = soft_cap
            else:
                effective_cap = max_running_workers_default

        items.append(
            {
                "alias": alias,
                "hard_gate": hard_gate,
                "soft_concurrency_gated": soft_gated,
                "effective_cap": effective_cap,
            }
        )

    return running_mode, items


def build_workers(
    worker_registry: Any,
    handoff_rows: list[dict[str, Any]],
    include_process_check: bool,
) -> list[dict[str, Any]]:
    from_registry = worker_map_from_registry(worker_registry)
    from_handoff = latest_handoff_by_slot(handoff_rows)

    workers: list[dict[str, Any]] = []
    for slot in SLOT_ORDER:
        reg = from_registry.get(slot, {})
        handoff = from_handoff.get(slot, {})

        role = as_str(first_present(reg, ["role", "worker_role"])) or ROLE_BY_SLOT[slot]
        state = normalize_state(first_present(reg, ["session_state", "state", "status", "run_state"]))

        active_task = as_str(first_present(reg, ["active_task", "task_identifier", "issue_identifier", "task", "issue"]))
        if active_task is None:
            active_task = as_str(first_present(handoff, ["task_identifier", "issue_identifier", "task", "issue"]))

        branch = as_str(first_present(reg, ["branch", "branch_name", "current_branch"]))
        if branch is None:
            branch = as_str(first_present(handoff, ["branch", "branch_name"]))

        dispatch_pid = as_int(first_present(reg, ["dispatch_pid", "pid", "process_id", "thread_pid"]))
        session_id = as_str(first_present(reg, ["session_id", "thread_session_id", "run_session_id"]))
        if session_id is None:
            session_id = as_str(first_present(handoff, ["session_id", "thread_session_id", "run_session_id"]))

        worker_last_result = as_str(first_present(reg, ["last_result", "result", "outcome", "handoff_result"]))
        handoff_result = as_str(first_present(handoff, ["result", "handoff_result", "outcome", "status"]))
        last_result = worker_last_result or handoff_result

        last_result_at = to_utc_iso(first_present(reg, ["last_result_at", "updated_at", "completed_at"]))
        if last_result_at is None:
            last_result_at = to_utc_iso(first_present(handoff, ["timestamp", "created_at", "at"]))

        blocker_summary = as_str(first_present(reg, ["blocker_summary", "blocker", "block_reason", "reason"]))
        if blocker_summary is None:
            blocker_summary = as_str(first_present(handoff, ["blocker_summary", "blocker", "reason", "error_summary"]))

        next_expected_action = normalize_next_expected_action(
            first_present(reg, ["next_expected_action", "next_action"]),
            state,
            last_result,
            blocker_summary,
        )

        workers.append(
            {
                "slot": slot,
                "role": role,
                "state": state,
                "active_task": active_task,
                "branch": branch,
                "dispatch_pid": dispatch_pid,
                "session_id": session_id,
                "pid_alive": pid_alive(dispatch_pid, include_process_check),
                "last_result": last_result,
                "last_result_at": last_result_at,
                "blocker_summary": blocker_summary,
                "next_expected_action": next_expected_action,
            }
        )

    return workers


def build_counts(workers: list[dict[str, Any]]) -> dict[str, int]:
    active = sum(1 for worker in workers if worker["state"] == "running")
    idle = sum(1 for worker in workers if worker["state"] == "idle")
    blocked = sum(1 for worker in workers if worker["state"] == "blocked")
    stopped = sum(1 for worker in workers if worker["state"] == "stopped")
    return {
        "active_workers": active,
        "idle_workers": idle,
        "blocked_workers": blocked,
        "stopped_workers": stopped,
    }


def extract_runtime_summary(runtime_registry: Any, runtime_leases: Any) -> dict[str, Any]:
    instances_raw = runtime_registry.get("instances") if isinstance(runtime_registry, dict) else []
    instances = [item for item in instances_raw if isinstance(item, dict)] if isinstance(instances_raw, list) else []

    shared_instances = [item for item in instances if (as_str(item.get("mode")) or "").lower() == "shared"]
    isolated_instances = [item for item in instances if (as_str(item.get("mode")) or "").lower() == "isolated"]
    healthy_like = [
        item
        for item in instances
        if (as_str(item.get("status")) or "").lower() in {"healthy", "degraded", "starting"}
    ]

    shared_base_urls = sorted(
        {
            as_str(item.get("base_url"))
            for item in shared_instances
            if as_str(item.get("base_url"))
        }
    )

    leases_raw = runtime_leases.get("leases") if isinstance(runtime_leases, dict) else []
    leases = [item for item in leases_raw if isinstance(item, dict)] if isinstance(leases_raw, list) else []
    active_leases = [item for item in leases if (as_str(item.get("status")) or "").lower() == "active"]
    active_exclusive = [item for item in active_leases if (as_str(item.get("mode")) or "").lower() == "exclusive"]

    return {
        "instances_total": len(instances),
        "shared_instances": len(shared_instances),
        "isolated_instances": len(isolated_instances),
        "healthy_like_instances": len(healthy_like),
        "shared_base_urls": shared_base_urls,
        "leases_total": len(leases),
        "active_leases": len(active_leases),
        "active_exclusive_leases": len(active_exclusive),
        "updated_at": to_utc_iso(first_present(runtime_registry if isinstance(runtime_registry, dict) else {}, ["updated_at"])),
    }


def extract_blocker_summary(blocker_index: Any, blocker_rows: list[dict[str, Any]]) -> dict[str, Any]:
    top_fingerprints: list[dict[str, Any]] = []
    if isinstance(blocker_index, dict):
        entries = blocker_index.get("entries")
        if isinstance(entries, list):
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                top_fingerprints.append(
                    {
                        "fingerprint": as_str(entry.get("fingerprint")),
                        "count": as_int(entry.get("count")) or 0,
                        "blocker_code": as_str(entry.get("blocker_code")),
                        "category": as_str(entry.get("category")) or "unknown",
                        "latest_summary": as_str(entry.get("latest_summary")),
                        "recommended_playbook": as_str(entry.get("recommended_playbook")),
                    }
                )
        top_fingerprints = sorted(top_fingerprints, key=lambda item: (-item["count"], item["fingerprint"] or ""))[:3]

    recent_rows = blocker_rows[-5:] if blocker_rows else []
    recent = [
        {
            "timestamp": to_utc_iso(first_present(row, ["timestamp", "created_at", "at"])),
            "task_identifier": as_str(first_present(row, ["task_identifier", "issue_identifier", "task"])),
            "worker_slot": as_str(first_present(row, ["worker_slot", "slot"])),
            "blocker_code": as_str(first_present(row, ["blocker_code", "code"])) or "unknown_blocker",
            "stage": as_str(first_present(row, ["stage"])) or "unknown",
            "summary": as_str(first_present(row, ["summary", "message"])) or "unspecified blocker",
        }
        for row in recent_rows
    ]

    return {
        "events_total": len(blocker_rows),
        "top_fingerprints": top_fingerprints,
        "recent_events": recent,
    }


def build_text_summary(snapshot: dict[str, Any]) -> str:
    cycle = snapshot.get("cycle", {})
    cycle_num = cycle.get("number")
    cycle_time = cycle.get("timestamp") or "unknown"

    counts = snapshot.get("counts", {})
    worker_segments: list[str] = []
    for worker in snapshot.get("workers", []):
        slot = worker.get("slot")
        state = worker.get("state") or "unknown"
        task = worker.get("active_task") or "none"
        session_id = worker.get("session_id") or "none"
        worker_segments.append(f"{slot}:{state}:{task}:session={session_id}")

    rate_segments: list[str] = []
    for profile in snapshot.get("rate", {}).get("profiles", []):
        alias = profile.get("alias") or "unknown"
        gate = profile.get("hard_gate") or "unknown"
        cap = profile.get("effective_cap")
        soft = "1" if profile.get("soft_concurrency_gated") else "0"
        rate_segments.append(f"{alias}={gate}(cap={cap},soft={soft})")

    blockers = snapshot.get("high_priority_blockers", [])
    blocker_segment = "none"
    if blockers:
        blocker_segment = ";".join(
            f"{item.get('task_identifier','unknown')}@{item.get('owner','external')}" for item in blockers
        )

    runtime = snapshot.get("runtime", {})
    runtime_segment = (
        f"instances={runtime.get('instances_total', 0)}"
        f",shared={runtime.get('shared_instances', 0)}"
        f",leases={runtime.get('active_leases', 0)}"
    )

    blocker_state = snapshot.get("blockers", {})
    top = blocker_state.get("top_fingerprints", [])
    top_segment = "none"
    if top:
        first = top[0]
        top_segment = f"{first.get('blocker_code','unknown')}:{first.get('count',0)}"

    cycle_label = "?" if cycle_num is None else str(cycle_num)
    return (
        f"cycle={cycle_label} at={cycle_time} "
        f"workers(active={counts.get('active_workers', 0)},idle={counts.get('idle_workers', 0)},"
        f"blocked={counts.get('blocked_workers', 0)},stopped={counts.get('stopped_workers', 0)}) "
        f"slots=[{'|'.join(worker_segments)}] "
        f"rates=[{'|'.join(rate_segments)}] "
        f"runtime[{runtime_segment}] "
        f"blockers={blocker_segment} "
        f"recurring={top_segment}"
    )


def build_status_text(snapshot: dict[str, Any]) -> str:
    generated_at = snapshot.get("generated_at") or "unknown"
    lines = [f"Current worker status ({generated_at} UTC):", ""]

    active_workers: list[dict[str, Any]] = []
    lines.append("slot | status | task | thread-id")
    for worker in snapshot.get("workers", []):
        slot = worker.get("slot") or "-"
        state = worker.get("state") or "-"
        task = worker.get("active_task") or "-"
        session_id = worker.get("session_id") or "-"
        lines.append(f"{slot} | {state} | {task} | {session_id}")

        if state == "running":
            active_workers.append(worker)

    lines.append("")
    if not active_workers:
        lines.append("No active workers right now.")
    elif len(active_workers) == 1:
        worker = active_workers[0]
        slot = worker.get("slot") or "-"
        task = worker.get("active_task") or "-"
        session_id = worker.get("session_id") or "-"
        lines.append(f"Only active worker right now is {slot} on {task} (thread-id {session_id}).")
    else:
        formatted = [
            f"{w.get('slot', '-')} on {w.get('active_task') or '-'} (thread-id {w.get('session_id') or '-'})"
            for w in active_workers
        ]
        lines.append("Active workers right now: " + ", ".join(formatted) + ".")

    runtime = snapshot.get("runtime", {})
    lines.append("")
    lines.append(
        "Runtime: "
        f"instances={runtime.get('instances_total', 0)}, "
        f"shared={runtime.get('shared_instances', 0)}, "
        f"active_leases={runtime.get('active_leases', 0)}"
    )

    blockers = snapshot.get("blockers", {})
    top = blockers.get("top_fingerprints", [])
    if top:
        first = top[0]
        lines.append(
            "Top recurring blocker: "
            f"{first.get('blocker_code') or 'unknown'} ({first.get('count', 0)} occurrences)"
        )
    else:
        lines.append("Top recurring blocker: none.")

    return "\n".join(lines)


def default_paths(repo_root: Path) -> dict[str, Path]:
    base = repo_root / "reports" / "optimus-prime"
    return {
        "worker_registry": base / "WORKER_REGISTRY.json",
        "cycle_log": base / "CYCLE_LOG.jsonl",
        "handoff_log": base / "HANDOFF_LOG.jsonl",
        "profile_rate_registry": base / "PROFILE_RATE_REGISTRY.json",
        "rate_status_log": base / "RATE_STATUS_LOG.jsonl",
        "runtime_registry": base / "RUNTIME_REGISTRY.json",
        "runtime_leases": base / "TEST_RUNTIME_LEASES.json",
        "blockers": base / "BLOCKERS.jsonl",
        "blocker_index": base / "BLOCKER_INDEX.json",
    }


def generate_snapshot(config: InputConfig) -> dict[str, Any]:
    ctx = SnapshotContext(warnings=[], errors=[], parse_warning_count=0)
    paths = default_paths(config.repo_root)

    available_sources = 0

    worker_registry, ok = read_json_file(paths["worker_registry"], ctx)
    if ok:
        available_sources += 1

    cycle_rows, ok = read_jsonl_file(paths["cycle_log"], ctx)
    if ok:
        available_sources += 1

    handoff_rows, ok = read_jsonl_file(paths["handoff_log"], ctx)
    if ok:
        available_sources += 1

    profile_rate_registry, ok = read_json_file(paths["profile_rate_registry"], ctx)
    if ok:
        available_sources += 1

    rate_status_rows, ok = read_jsonl_file(paths["rate_status_log"], ctx)
    if ok:
        available_sources += 1

    runtime_registry, _ = read_json_optional(paths["runtime_registry"], ctx)
    runtime_leases, _ = read_json_optional(paths["runtime_leases"], ctx)
    blocker_rows, _ = read_jsonl_optional(paths["blockers"], ctx)
    blocker_index, _ = read_json_optional(paths["blocker_index"], ctx)

    workers = build_workers(worker_registry, handoff_rows, include_process_check=config.include_process_check)
    counts = build_counts(workers)
    cycle = latest_cycle(cycle_rows)
    profile_running_mode, rate_profiles = extract_rate_profiles(
        profile_rate_registry,
        rate_status_rows,
        max_running_workers_default=6,
    )
    blockers = blocker_items(handoff_rows, workers)
    runtime = extract_runtime_summary(runtime_registry, runtime_leases)
    blocker_summary = extract_blocker_summary(blocker_index, blocker_rows)

    all_core_unavailable = available_sources == 0
    if all_core_unavailable:
        ctx.error(
            "all_core_sources_unavailable",
            "All required orchestration status sources are unavailable.",
            config.repo_root / "reports" / "optimus-prime",
            remediation=(
                "Create/populate WORKER_REGISTRY.json, CYCLE_LOG.jsonl, HANDOFF_LOG.jsonl, "
                "PROFILE_RATE_REGISTRY.json, and RATE_STATUS_LOG.jsonl."
            ),
        )

    snapshot: dict[str, Any] = {
        "ok": not all_core_unavailable,
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "tool_version": TOOL_VERSION,
        "generated_at": utc_now_iso(),
        "cycle": cycle,
        "workers": workers,
        "counts": counts,
        "rate": {
            "profile_running_mode": profile_running_mode,
            "profiles": rate_profiles,
        },
        "high_priority_blockers": blockers,
        "runtime": runtime,
        "blockers": blocker_summary,
        "warnings": ctx.warnings,
        "errors": ctx.errors,
        "parse_warning_count": ctx.parse_warning_count,
        "text_summary": None,
        "status_text": None,
    }

    if config.include_history:
        cycle_hist: list[dict[str, Any]] = []
        for row in cycle_rows[-config.max_history_items :]:
            cycle_hist.append(latest_cycle([row]))

        handoff_hist: list[dict[str, Any]] = []
        for row in handoff_rows[-config.max_history_items :]:
            handoff_hist.append(
                {
                    "slot": as_str(first_present(row, ["slot", "worker_slot", "owner_slot"])),
                    "task_identifier": as_str(first_present(row, ["task_identifier", "issue_identifier", "task"])),
                    "result": as_str(first_present(row, ["result", "handoff_result", "outcome", "status"])),
                    "timestamp": to_utc_iso(first_present(row, ["timestamp", "created_at", "at"])),
                    "blocker_summary": as_str(first_present(row, ["blocker_summary", "blocker", "reason"])),
                }
            )

        snapshot["history"] = {
            "cycle": cycle_hist,
            "handoff": handoff_hist,
        }

    if config.output_mode in {"json+text", "text"}:
        snapshot["text_summary"] = build_text_summary(snapshot)
        snapshot["status_text"] = build_status_text(snapshot)

    return snapshot


# ---------- CLI ----------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a deterministic orchestration status snapshot from local report files.")
    parser.add_argument("--input-json", help="Optional path to JSON object containing the required input contract.")
    parser.add_argument("--repo-root", help="Repository root path. Required unless provided via --input-json.")
    parser.add_argument("--include-history", action="store_true", help="Include compact cycle/handoff history in output.")
    parser.add_argument("--max-history-items", type=int, default=5)
    parser.add_argument("--include-process-check", dest="include_process_check", action="store_true", default=True)
    parser.add_argument("--no-process-check", dest="include_process_check", action="store_false")
    parser.add_argument("--output-mode", choices=["json", "json+text", "text"], default="json")
    parser.add_argument("--json-pretty", action="store_true")
    return parser.parse_args()


def load_input_json(path: str) -> dict[str, Any]:
    raw: str
    if path == "-":
        raw = os.sys.stdin.read()
    else:
        raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("input contract must be a JSON object")
    return data


def build_config(args: argparse.Namespace) -> InputConfig:
    json_input: dict[str, Any] = {}
    if args.input_json:
        json_input = load_input_json(args.input_json)

    repo_root_raw = args.repo_root or as_str(json_input.get("repo_root"))
    if not repo_root_raw:
        raise ValueError("repo_root is required")

    include_history = bool(json_input.get("include_history", False))
    if args.include_history:
        include_history = True

    max_history_items = as_int(json_input.get("max_history_items")) or args.max_history_items
    if args.max_history_items != 5:
        max_history_items = args.max_history_items
    if max_history_items < 1:
        raise ValueError("max_history_items must be >= 1")

    include_process_check = bool(json_input.get("include_process_check", True))
    if args.include_process_check is False:
        include_process_check = False

    output_mode = as_str(json_input.get("output_mode")) or args.output_mode
    if output_mode not in {"json", "json+text", "text"}:
        raise ValueError("output_mode must be one of: json, json+text, text")

    return InputConfig(
        repo_root=Path(repo_root_raw).expanduser().resolve(),
        include_history=include_history,
        max_history_items=max_history_items,
        include_process_check=include_process_check,
        output_mode=output_mode,
    )


def main() -> int:
    args = parse_args()
    try:
        config = build_config(args)
    except (ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc), "tool": TOOL_NAME, "schema_version": SCHEMA_VERSION}))
        return 2

    snapshot = generate_snapshot(config)
    if config.output_mode == "text":
        print(snapshot.get("status_text") or "")
    elif args.json_pretty:
        print(json.dumps(snapshot, indent=2, sort_keys=False))
    else:
        print(json.dumps(snapshot, separators=(",", ":"), sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
