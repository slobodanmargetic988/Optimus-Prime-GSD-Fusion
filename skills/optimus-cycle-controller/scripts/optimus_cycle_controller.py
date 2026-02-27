#!/usr/bin/env python3
"""Optimus cycle controller.

Deterministic long-running loop that centralizes cycle timing and terminal checks.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TERMINAL_REASONS = {
    "project_done",
    "insurmountable_blocker",
    "all_rate_gates_blocking",
}

EVIDENCE_RULES: Dict[str, Dict[str, Any]] = {
    "project_done": {
        "expected_status": "done",
        "required_keys": ["status", "evidence"],
    },
    "insurmountable_blocker": {
        "expected_status": "blocked",
        "required_keys": ["status", "reason"],
    },
    "all_rate_gates_blocking": {
        "expected_status": "all_rate_gates_blocking",
        "required_keys": ["status", "reason", "generated_at", "profiles"],
    },
}

LINEAR_PHASES = {
    "agent_working",
    "agent_work_done",
    "agent_testing",
    "agent_test_done",
    "agent_review",
    "agent_review_done",
    "human_review",
    "done",
    "backlog",
}

STATUS_TO_PHASE_HINT = {
    "agent_working": "agent_working",
    "working": "agent_working",
    "agent_work_done": "agent_work_done",
    "dev_done": "agent_work_done",
    "developer_done": "agent_work_done",
    "ready_for_test": "agent_work_done",
    "agent_testing": "agent_testing",
    "testing": "agent_testing",
    "agent_test_done": "agent_test_done",
    "test_done": "agent_test_done",
    "ready_for_review": "agent_test_done",
    "agent_review": "agent_review",
    "reviewing": "agent_review",
    "agent_review_done": "agent_review_done",
    "review_done": "agent_review_done",
    "done": "done",
    "blocked": "backlog",
    "failed": "backlog",
}


@dataclass
class ControllerConfig:
    repo_root: Path
    sleep_minutes: float
    profile_aliases: List[str]
    rate_gate_5h_percent: float
    rate_gate_weekly_percent: float
    soft_rate_gate_5h_percent: float
    soft_rate_gate_weekly_percent: float
    soft_rate_gated_max_running_workers: int
    control_flags_dir: Path
    events_path: Path
    heartbeat_path: Path
    final_state_path: Path
    lock_path: Path
    worker_registry_path: Path
    cycle_log_path: Path
    handoff_log_path: Path
    rate_registry_path: Path
    rate_status_log_path: Path
    allow_autonomous_ops: bool
    max_cycles: Optional[int]
    dry_run: bool
    emit_stdout: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Optimus cycle controller")
    parser.add_argument("--input-json", help="Path to JSON file or '-' for stdin")
    parser.add_argument(
        "--verify-final-state",
        help="Validate FINAL_STATE.json + evidence to authorize terminal stop",
    )
    parser.add_argument("--json-pretty", action="store_true", help="Pretty-print output JSON")
    args = parser.parse_args()
    if bool(args.input_json) == bool(args.verify_final_state):
        parser.error("Provide exactly one of --input-json or --verify-final-state")
    return args


def _read_input_payload(input_json: str) -> Dict[str, Any]:
    if input_json == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(input_json).read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("input JSON must be an object")
    return data


def _bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return default


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_path(value: Any, default: Path) -> Path:
    if isinstance(value, str) and value.strip():
        return Path(value).expanduser().resolve()
    return default


def normalize_config(payload: Dict[str, Any]) -> ControllerConfig:
    if "repo_root" not in payload:
        raise ValueError("repo_root is required")

    repo_root = Path(str(payload["repo_root"]))
    repo_root = repo_root.expanduser().resolve()

    reports_root = repo_root / "reports" / "optimus-prime"
    controller_dir = reports_root / "controller"
    control_flags_dir = _as_path(payload.get("control_flags_dir"), reports_root / "control")

    events_path = _as_path(payload.get("events_path"), controller_dir / "EVENTS.jsonl")
    heartbeat_path = _as_path(payload.get("heartbeat_path"), controller_dir / "HEARTBEAT.json")
    final_state_path = _as_path(payload.get("final_state_path"), controller_dir / "FINAL_STATE.json")
    lock_path = _as_path(payload.get("lock_path"), controller_dir / "lock.pid")

    worker_registry_path = _as_path(
        payload.get("worker_registry_path"), reports_root / "WORKER_REGISTRY.json"
    )
    cycle_log_path = _as_path(payload.get("cycle_log_path"), reports_root / "CYCLE_LOG.jsonl")
    handoff_log_path = _as_path(payload.get("handoff_log_path"), reports_root / "HANDOFF_LOG.jsonl")
    rate_registry_path = _as_path(
        payload.get("rate_registry_path"), reports_root / "PROFILE_RATE_REGISTRY.json"
    )
    rate_status_log_path = _as_path(
        payload.get("rate_status_log_path"), reports_root / "RATE_STATUS_LOG.jsonl"
    )

    aliases_raw = payload.get("profile_aliases", ["codex"])
    if isinstance(aliases_raw, str):
        profile_aliases = [a.strip() for a in aliases_raw.split(",") if a.strip()]
    elif isinstance(aliases_raw, list):
        profile_aliases = [str(a).strip() for a in aliases_raw if str(a).strip()]
    else:
        profile_aliases = ["codex"]
    if not profile_aliases:
        profile_aliases = ["codex"]

    max_cycles = payload.get("max_cycles")
    max_cycles_int = _as_int(max_cycles, 0)
    if max_cycles is None or max_cycles_int <= 0:
        max_cycles_normalized: Optional[int] = None
    else:
        max_cycles_normalized = max_cycles_int

    return ControllerConfig(
        repo_root=repo_root,
        sleep_minutes=max(0.0, _as_float(payload.get("sleep_minutes"), 5.0)),
        profile_aliases=profile_aliases,
        rate_gate_5h_percent=max(0.0, _as_float(payload.get("rate_gate_5h_percent"), 15.0)),
        rate_gate_weekly_percent=max(
            0.0, _as_float(payload.get("rate_gate_weekly_percent"), 10.0)
        ),
        soft_rate_gate_5h_percent=max(
            0.0, _as_float(payload.get("soft_rate_gate_5h_percent"), 40.0)
        ),
        soft_rate_gate_weekly_percent=max(
            0.0, _as_float(payload.get("soft_rate_gate_weekly_percent"), 25.0)
        ),
        soft_rate_gated_max_running_workers=max(
            1, _as_int(payload.get("soft_rate_gated_max_running_workers"), 3)
        ),
        control_flags_dir=control_flags_dir,
        events_path=events_path,
        heartbeat_path=heartbeat_path,
        final_state_path=final_state_path,
        lock_path=lock_path,
        worker_registry_path=worker_registry_path,
        cycle_log_path=cycle_log_path,
        handoff_log_path=handoff_log_path,
        rate_registry_path=rate_registry_path,
        rate_status_log_path=rate_status_log_path,
        allow_autonomous_ops=_bool(payload.get("allow_autonomous_ops"), False),
        max_cycles=max_cycles_normalized,
        dry_run=_bool(payload.get("dry_run"), False),
        emit_stdout=_bool(payload.get("emit_stdout"), True),
    )


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    _ensure_parent(path)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, data: Dict[str, Any]) -> None:
    _ensure_parent(path)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(data, sort_keys=True) + "\n")


def _read_json(path: Path) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not path.exists():
        return None, "missing"
    try:
        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            return None, "empty"
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return None, "not_object"
        return parsed, None
    except json.JSONDecodeError:
        return None, "invalid_json"


def _read_last_jsonl(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        if not lines:
            return None
        last = json.loads(lines[-1])
        if isinstance(last, dict):
            return last
    except Exception:
        return None
    return None


def _is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def acquire_lock(lock_path: Path) -> Tuple[bool, Optional[int]]:
    _ensure_parent(lock_path)
    current_pid = os.getpid()

    if lock_path.exists():
        raw = lock_path.read_text(encoding="utf-8").strip()
        active_pid: Optional[int] = None

        if raw:
            try:
                maybe_json = json.loads(raw)
                if isinstance(maybe_json, dict):
                    active_pid = _as_int(maybe_json.get("pid"), 0)
                else:
                    active_pid = _as_int(maybe_json, 0)
            except json.JSONDecodeError:
                active_pid = _as_int(raw, 0)

        if active_pid and active_pid != current_pid and _is_pid_alive(active_pid):
            return False, active_pid

    lock_payload = {
        "pid": current_pid,
        "started_at": utc_now(),
        "status": "running",
    }
    _write_json(lock_path, lock_payload)
    return True, None


def release_lock(lock_path: Path) -> None:
    try:
        if lock_path.exists():
            raw = lock_path.read_text(encoding="utf-8").strip()
            current_pid = os.getpid()
            owner_pid = None
            if raw:
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, dict):
                        owner_pid = _as_int(parsed.get("pid"), 0)
                    else:
                        owner_pid = _as_int(parsed, 0)
                except json.JSONDecodeError:
                    owner_pid = _as_int(raw, 0)

            if owner_pid in (None, 0, current_pid):
                lock_path.unlink(missing_ok=True)
    except Exception:
        pass


def _extract_remaining_percent(window: Any) -> Optional[float]:
    if not isinstance(window, dict):
        return None
    keys = ("remaining_percent", "remaining_pct", "remaining")
    for key in keys:
        value = window.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
    return None


def _extract_profiles_map(raw: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    if "profiles" in raw and isinstance(raw["profiles"], dict):
        return {
            str(alias): data
            for alias, data in raw["profiles"].items()
            if isinstance(data, dict)
        }

    out: Dict[str, Dict[str, Any]] = {}
    for alias, data in raw.items():
        if isinstance(data, dict) and (
            "five_hour" in data
            or "weekly" in data
            or "5h" in data
            or "recommended_action" in data
        ):
            out[str(alias)] = data
    return out


def evaluate_rate_state(config: ControllerConfig) -> Dict[str, Any]:
    warnings: List[str] = []
    raw_registry, err = _read_json(config.rate_registry_path)
    profiles_map: Dict[str, Dict[str, Any]] = {}

    if err:
        warnings.append(f"rate_registry_unavailable:{err}")
    elif raw_registry:
        profiles_map = _extract_profiles_map(raw_registry)

    aliases = list(dict.fromkeys(config.profile_aliases))
    if not aliases and profiles_map:
        aliases = sorted(profiles_map.keys())

    states: List[Dict[str, Any]] = []
    for alias in aliases:
        data = profiles_map.get(alias)
        if data is None:
            warnings.append(f"profile_missing:{alias}")
            states.append(
                {
                    "alias": alias,
                    "hard_gated": False,
                    "soft_gated": False,
                    "recommended_action": "unknown",
                    "five_hour_remaining": None,
                    "weekly_remaining": None,
                    "data_present": False,
                }
            )
            continue

        five = data.get("five_hour") if isinstance(data.get("five_hour"), dict) else data.get("5h")
        weekly = data.get("weekly")

        five_remaining = _extract_remaining_percent(five)
        weekly_remaining = _extract_remaining_percent(weekly)

        hard_gated = bool(data.get("hard_gated"))
        if isinstance(five, dict):
            hard_gated = hard_gated or bool(five.get("gated"))
        if isinstance(weekly, dict):
            hard_gated = hard_gated or bool(weekly.get("gated"))

        if five_remaining is not None and five_remaining <= config.rate_gate_5h_percent:
            hard_gated = True
        if weekly_remaining is not None and weekly_remaining <= config.rate_gate_weekly_percent:
            hard_gated = True

        soft_gated = bool(data.get("soft_concurrency_gated"))
        if five_remaining is not None and five_remaining <= config.soft_rate_gate_5h_percent:
            soft_gated = True
        if weekly_remaining is not None and weekly_remaining <= config.soft_rate_gate_weekly_percent:
            soft_gated = True

        recommended_action = str(data.get("recommended_action") or "continue")
        if recommended_action in {"wind_down", "wait_until_reset"}:
            hard_gated = True

        states.append(
            {
                "alias": alias,
                "hard_gated": hard_gated,
                "soft_gated": soft_gated,
                "recommended_action": recommended_action,
                "five_hour_remaining": five_remaining,
                "weekly_remaining": weekly_remaining,
                "data_present": True,
            }
        )

    hard_gated_aliases = [s["alias"] for s in states if s["hard_gated"]]
    soft_gated_aliases = [s["alias"] for s in states if s["soft_gated"]]
    all_rate_gates_blocking = bool(states) and len(hard_gated_aliases) == len(states)

    return {
        "profiles": states,
        "hard_gated_aliases": hard_gated_aliases,
        "soft_gated_aliases": soft_gated_aliases,
        "all_rate_gates_blocking": all_rate_gates_blocking,
        "warnings": warnings,
    }


def build_snapshot(config: ControllerConfig) -> Dict[str, Any]:
    warnings: List[str] = []

    worker_registry, worker_err = _read_json(config.worker_registry_path)
    if worker_err:
        warnings.append(f"worker_registry_unavailable:{worker_err}")

    workers: List[Dict[str, Any]] = []
    raw_workers: Any = None
    if worker_registry:
        if isinstance(worker_registry.get("workers"), dict):
            raw_workers = list(worker_registry["workers"].values())
        elif isinstance(worker_registry.get("workers"), list):
            raw_workers = worker_registry.get("workers")
        elif isinstance(worker_registry, dict):
            raw_workers = [
                v
                for v in worker_registry.values()
                if isinstance(v, dict) and ("slot" in v or "role" in v or "state" in v)
            ]

    if isinstance(raw_workers, list):
        for item in raw_workers:
            if not isinstance(item, dict):
                continue
            slot = str(item.get("slot") or item.get("name") or "unknown")
            state = str(item.get("state") or "unknown")
            active_task = item.get("active_task")
            role = str(item.get("role") or "unknown")
            workers.append(
                {
                    "slot": slot,
                    "role": role,
                    "state": state,
                    "active_task": active_task,
                }
            )

    workers.sort(key=lambda x: x["slot"])
    active_workers = [
        w
        for w in workers
        if w["state"] in {"running", "busy"} or bool(w.get("active_task"))
    ]

    return {
        "generated_at": utc_now(),
        "workers": workers,
        "active_workers_summary": {
            "active_count": len(active_workers),
            "active_slots": [w["slot"] for w in active_workers],
            "total_known_workers": len(workers),
        },
        "latest_cycle_log": _read_last_jsonl(config.cycle_log_path),
        "latest_handoff_log": _read_last_jsonl(config.handoff_log_path),
        "latest_rate_status_log": _read_last_jsonl(config.rate_status_log_path),
        "warnings": warnings,
    }


def validate_evidence_file(
    path: Path,
    *,
    expected_status: str,
    required_keys: List[str],
) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    payload, err = _read_json(path)
    if err:
        if err == "missing":
            return False, None, None
        return False, None, f"malformed:{err}"

    assert payload is not None
    missing_keys = [k for k in required_keys if k not in payload]
    if missing_keys:
        return False, None, f"malformed:missing_keys:{','.join(missing_keys)}"

    status = str(payload.get("status") or "")
    if status != expected_status:
        return False, payload, "status_mismatch"

    return True, payload, None


def maybe_emit_stdout(config: ControllerConfig, message: str) -> None:
    if config.emit_stdout:
        print(message, flush=True)


def _first_non_empty(data: Dict[str, Any], keys: List[str]) -> Optional[str]:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _normalize_blockers(raw: Any) -> List[str]:
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    return []


def _derive_handoff_linear_phase(latest_handoff: Dict[str, Any]) -> Optional[str]:
    direct_phase = _first_non_empty(
        latest_handoff, ["target_phase", "next_phase", "phase", "linear_target_phase"]
    )
    if direct_phase:
        normalized = direct_phase.strip().lower()
        if normalized in LINEAR_PHASES:
            return normalized

    status_hint = _first_non_empty(
        latest_handoff, ["status", "result", "handoff_result", "outcome"]
    )
    if status_hint:
        normalized = status_hint.strip().lower().replace("-", "_")
        return STATUS_TO_PHASE_HINT.get(normalized)

    return None


def _build_handoff_sync_directive(
    cycle_number: int, latest_handoff: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    issue_identifier = _first_non_empty(
        latest_handoff,
        ["task_identifier", "issue_identifier", "issue", "task"],
    )
    if not issue_identifier:
        return None

    target_phase = _derive_handoff_linear_phase(latest_handoff)
    if not target_phase:
        return None

    blockers = _normalize_blockers(latest_handoff.get("blockers"))
    if not blockers:
        blocker_summary = _first_non_empty(
            latest_handoff, ["blocker", "blocker_summary", "reason"]
        )
        if blocker_summary:
            blockers = [blocker_summary]

    summary_payload = {
        "task_identifier": issue_identifier,
        "branch": _first_non_empty(latest_handoff, ["branch", "branch_name"]),
        "head_commit": _first_non_empty(latest_handoff, ["head_commit", "commit"]),
        "decision": _first_non_empty(latest_handoff, ["result", "status", "outcome"]) or "update",
        "blockers": blockers,
    }

    return {
        "directive_id": f"cycle-{cycle_number:06d}-sync-{issue_identifier.lower()}",
        "directive_type": "sync_linear_phase",
        "recommended_tool": "linear-handoff-sync",
        "recommended_args": {
            "issue_identifier": issue_identifier,
            "target_phase": target_phase,
            "summary_payload": summary_payload,
        },
        "reason": f"handoff suggests phase transition for {issue_identifier} -> {target_phase}",
        "requires_optimus_action": True,
    }


def _read_test_train_state(repo_root: Path) -> Optional[Dict[str, Any]]:
    path = repo_root / "reports" / "optimus-prime" / "TEST_TRAIN_STATE.json"
    payload, err = _read_json(path)
    if err or not isinstance(payload, dict):
        return None
    return payload


def build_test_train_directives(cycle_number: int, config: ControllerConfig) -> List[Dict[str, Any]]:
    state = _read_test_train_state(config.repo_root)
    if not isinstance(state, dict):
        return []

    mode = str(state.get("test_train_mode") or "off").strip().lower()
    if mode == "off":
        return []

    wave = state.get("active_wave") if isinstance(state.get("active_wave"), dict) else {}
    wave_id = str(wave.get("wave_id") or "wave-unknown")
    wave_state = str(wave.get("state") or "WAVE_ACTIVE")
    planned_pass_done = bool(wave.get("planned_flow_pass_completed"))

    eligibility = state.get("promotion_eligibility")
    eligible = bool(eligibility.get("eligible")) if isinstance(eligibility, dict) else False

    test_branch = str(state.get("test_branch") or "test")
    test_next_branch = str(state.get("test_next_branch") or "test-next")
    shared_url = state.get("shared_test_base_url")

    directives: List[Dict[str, Any]] = []

    if wave_state == "WAVE_ACTIVE" and planned_pass_done:
        directives.append(
            {
                "directive_id": f"cycle-{cycle_number:06d}-wave-close-{wave_id}",
                "directive_type": "close_test_wave",
                "recommended_tool": "test-train-manager",
                "recommended_args": {
                    "action": "close_test_wave",
                    "wave_id": wave_id,
                    "planned_flow_pass_completed": True,
                    "test_branch": test_branch,
                    "test_next_branch": test_next_branch,
                },
                "reason": "planned flow pass completed; wave should close before promotion evaluation",
                "requires_optimus_action": True,
            }
        )

    if wave_state in {"WAVE_CLOSING", "PROMOTION_EVAL"} or planned_pass_done:
        directives.append(
            {
                "directive_id": f"cycle-{cycle_number:06d}-wave-gate-{wave_id}",
                "directive_type": "evaluate_promotion_gate",
                "recommended_tool": "test-train-manager",
                "recommended_args": {
                    "action": "evaluate_promotion_gate",
                    "wave_id": wave_id,
                    "test_branch": test_branch,
                    "test_next_branch": test_next_branch,
                },
                "reason": "evaluate promotion gate for shared test train",
                "requires_optimus_action": True,
            }
        )

    if eligible:
        directives.extend(
            [
                {
                    "directive_id": f"cycle-{cycle_number:06d}-wave-promote-{wave_id}",
                    "directive_type": "promote_test_next_to_test",
                    "recommended_tool": "test-train-manager",
                    "recommended_args": {
                        "action": "promote_test_next_to_test",
                        "wave_id": wave_id,
                        "test_branch": test_branch,
                        "test_next_branch": test_next_branch,
                    },
                    "reason": "promotion gate eligible; promote queued integration branch",
                    "requires_optimus_action": True,
                },
                {
                    "directive_id": f"cycle-{cycle_number:06d}-wave-deploy-{wave_id}",
                    "directive_type": "deploy_test_branch",
                    "recommended_tool": "test-train-manager",
                    "recommended_args": {
                        "action": "deploy_test_branch",
                        "wave_id": wave_id,
                        "test_branch": test_branch,
                        "test_next_branch": test_next_branch,
                    },
                    "reason": "promotion eligible; deploy test branch for shared runtime validation",
                    "requires_optimus_action": True,
                },
                {
                    "directive_id": f"cycle-{cycle_number:06d}-wave-start-{wave_id}",
                    "directive_type": "start_new_test_wave",
                    "recommended_tool": "test-train-manager",
                    "recommended_args": {
                        "action": "start_new_test_wave",
                        "test_branch": test_branch,
                        "test_next_branch": test_next_branch,
                        "shared_test_base_url": shared_url,
                    },
                    "reason": "start next shared validation wave after promotion/deploy",
                    "requires_optimus_action": True,
                },
            ]
        )

    return directives


def build_directives(
    cycle_number: int,
    snapshot: Dict[str, Any],
    rate_state: Dict[str, Any],
    config: ControllerConfig,
) -> List[Dict[str, Any]]:
    directives: List[Dict[str, Any]] = []

    directives.append(
        {
            "directive_id": f"cycle-{cycle_number:06d}-show-snapshot",
            "directive_type": "show_snapshot",
            "recommended_tool": "orchestrator-status-snapshot",
            "recommended_args": {
                "output_mode": "json+text",
            },
            "reason": "cycle heartbeat snapshot",
            "requires_optimus_action": True,
        }
    )

    hard = rate_state.get("hard_gated_aliases", [])
    soft = rate_state.get("soft_gated_aliases", [])

    if hard:
        directives.append(
            {
                "directive_id": f"cycle-{cycle_number:06d}-rate-hard",
                "directive_type": "dispatch_filter",
                "recommended_tool": "cycle-tick",
                "recommended_args": {
                    "blocked_profiles": hard,
                    "mode": "hard_gate",
                },
                "reason": "one or more profiles are hard-gated",
                "requires_optimus_action": True,
            }
        )

    if soft:
        directives.append(
            {
                "directive_id": f"cycle-{cycle_number:06d}-rate-soft",
                "directive_type": "soft_throttle",
                "recommended_tool": "cycle-tick",
                "recommended_args": {
                    "soft_gated_profiles": soft,
                    "soft_cap": rate_state.get("soft_cap"),
                },
                "reason": "soft throttle should be applied",
                "requires_optimus_action": True,
            }
        )

    if snapshot.get("active_workers_summary", {}).get("active_count", 0) == 0:
        directives.append(
            {
                "directive_id": f"cycle-{cycle_number:06d}-idle-dispatch",
                "directive_type": "review_dispatch_queue",
                "recommended_tool": "dispatch-worker-packet",
                "recommended_args": {
                    "reason": "no active workers detected",
                },
                "reason": "controller detected idle workers",
                "requires_optimus_action": True,
            }
        )

    workers = snapshot.get("workers", [])
    latest_handoff = snapshot.get("latest_handoff_log")
    handoff_runtime_strategy = None
    if isinstance(latest_handoff, dict):
        handoff_runtime_strategy = latest_handoff.get("runtime_strategy")

    for worker in workers:
        if not isinstance(worker, dict):
            continue
        role = str(worker.get("role") or "").lower()
        state = str(worker.get("state") or "").lower()
        if role not in {"tester", "flex-tester"}:
            continue
        if state not in {"running", "busy"} and not worker.get("active_task"):
            continue
        if handoff_runtime_strategy in {"external_url", "shared_runtime", "isolated_runtime"}:
            continue

        directives.append(
            {
                "directive_id": f"cycle-{cycle_number:06d}-runtime-{worker.get('slot','tester')}",
                "directive_type": "runtime_strategy_resolve",
                "recommended_tool": "runtime-coordinator",
                "recommended_args": {
                    "action": "resolve",
                    "task_identifier": worker.get("active_task"),
                    "worker_slot": worker.get("slot"),
                    "worker_role": worker.get("role"),
                    "task_kind": "ui_flow",
                    "requires_browser": True,
                },
                "reason": "tester activity detected without explicit runtime strategy in latest handoff",
                "requires_optimus_action": True,
            }
        )
        break

    blocked_workers = [
        worker
        for worker in workers
        if isinstance(worker, dict) and str(worker.get("state") or "").lower() == "blocked"
    ]
    latest_handoff_result = (
        str(latest_handoff.get("result") or latest_handoff.get("status") or "").lower()
        if isinstance(latest_handoff, dict)
        else ""
    )
    if blocked_workers or "block" in latest_handoff_result:
        directives.append(
            {
                "directive_id": f"cycle-{cycle_number:06d}-blocker-index-refresh",
                "directive_type": "refresh_blocker_index",
                "recommended_tool": "runtime-coordinator",
                "recommended_args": {
                    "action": "refresh_blocker_index",
                },
                "reason": "blocked worker or blocked handoff detected; refresh recurring blocker intelligence",
                "requires_optimus_action": True,
            }
        )

    if isinstance(latest_handoff, dict):
        handoff_directive = _build_handoff_sync_directive(cycle_number, latest_handoff)
        if handoff_directive:
            directives.append(handoff_directive)

    directives.extend(build_test_train_directives(cycle_number, config))

    return directives


def can_optimus_stop_from_final_state(final_state_path: Path) -> bool:
    validation = validate_stop_authorization(final_state_path)
    return bool(validation.get("authorized"))


def validate_stop_authorization(
    final_state_path: Path,
    *,
    require_evidence_exists: bool = True,
) -> Dict[str, Any]:
    final_state_resolved = final_state_path.expanduser().resolve()
    payload, err = _read_json(final_state_resolved)
    if err or not payload:
        return {
            "authorized": False,
            "code": "final_state_missing_or_invalid",
            "message": f"Final state unavailable or malformed: {err or 'unknown'}",
            "final_state_path": str(final_state_resolved),
        }

    terminal_reason = payload.get("terminal_reason")
    if terminal_reason not in TERMINAL_REASONS:
        return {
            "authorized": False,
            "code": "invalid_terminal_reason",
            "message": f"terminal_reason must be one of {sorted(TERMINAL_REASONS)}",
            "terminal_reason": terminal_reason,
            "final_state_path": str(final_state_resolved),
        }

    evidence_raw = payload.get("evidence_file")
    if not isinstance(evidence_raw, str) or not evidence_raw.strip():
        return {
            "authorized": False,
            "code": "missing_evidence_file",
            "message": "evidence_file is required and must be non-empty",
            "terminal_reason": terminal_reason,
            "final_state_path": str(final_state_resolved),
        }

    evidence_path = Path(evidence_raw).expanduser()
    if not evidence_path.is_absolute():
        evidence_path = (final_state_resolved.parent / evidence_path).resolve()
    else:
        evidence_path = evidence_path.resolve()

    if require_evidence_exists and not evidence_path.exists():
        return {
            "authorized": False,
            "code": "evidence_missing",
            "message": "evidence_file path from final state does not exist",
            "terminal_reason": terminal_reason,
            "evidence_file": str(evidence_path),
            "final_state_path": str(final_state_resolved),
        }

    rule = EVIDENCE_RULES[terminal_reason]
    valid, _, evidence_err = validate_evidence_file(
        evidence_path,
        expected_status=str(rule["expected_status"]),
        required_keys=list(rule["required_keys"]),
    )
    if not valid:
        if evidence_err is None:
            code = "evidence_missing"
            message = "evidence_file missing"
        elif evidence_err.startswith("malformed"):
            code = "evidence_malformed"
            message = f"evidence malformed: {evidence_err}"
        elif evidence_err == "status_mismatch":
            code = "evidence_status_mismatch"
            message = "evidence status does not match terminal reason"
        else:
            code = "evidence_invalid"
            message = f"evidence invalid: {evidence_err}"

        return {
            "authorized": False,
            "code": code,
            "message": message,
            "terminal_reason": terminal_reason,
            "evidence_file": str(evidence_path),
            "final_state_path": str(final_state_resolved),
        }

    return {
        "authorized": True,
        "code": "authorized",
        "message": "terminal final state and evidence are valid",
        "terminal_reason": terminal_reason,
        "evidence_file": str(evidence_path),
        "final_state_path": str(final_state_resolved),
    }


def run_controller(config: ControllerConfig) -> Dict[str, Any]:
    config.control_flags_dir.mkdir(parents=True, exist_ok=True)
    _ensure_parent(config.events_path)
    _ensure_parent(config.heartbeat_path)
    _ensure_parent(config.final_state_path)

    if not config.events_path.exists():
        config.events_path.touch()

    lock_ok, active_pid = acquire_lock(config.lock_path)
    if not lock_ok:
        return {
            "ok": False,
            "tool": "optimus-cycle-controller",
            "error": "lock_conflict",
            "active_pid": active_pid,
            "lock_path": str(config.lock_path),
        }

    try:
        cycle_number = 0
        pending_directives: List[Dict[str, Any]] = []

        while True:
            cycle_number += 1
            timestamp = utc_now()
            cycle_warnings: List[str] = []

            snapshot = build_snapshot(config)
            cycle_warnings.extend(snapshot.get("warnings", []))

            rate_state = evaluate_rate_state(config)
            rate_state["soft_cap"] = config.soft_rate_gated_max_running_workers
            cycle_warnings.extend(rate_state.get("warnings", []))

            snapshot_event = {
                "timestamp": timestamp,
                "cycle_number": cycle_number,
                "event_type": "snapshot",
                "action_code": "snapshot_state",
                "payload": {
                    "active_workers_summary": snapshot.get("active_workers_summary"),
                    "profiles": rate_state.get("profiles", []),
                },
                "requires_optimus_action": False,
            }
            _append_jsonl(config.events_path, snapshot_event)

            done_path = config.control_flags_dir / "PROJECT_DONE.json"
            blocker_path = config.control_flags_dir / "INSURMOUNTABLE_BLOCKER.json"
            all_rate_path = config.control_flags_dir / "ALL_RATE_GATES_BLOCKING.json"

            done_ok, done_payload, done_err = validate_evidence_file(
                done_path,
                expected_status="done",
                required_keys=["status", "evidence"],
            )
            blocker_ok, blocker_payload, blocker_err = validate_evidence_file(
                blocker_path,
                expected_status="blocked",
                required_keys=["status", "reason"],
            )

            if done_err and done_err.startswith("malformed"):
                cycle_warnings.append(f"project_done_file_{done_err}")
            if blocker_err and blocker_err.startswith("malformed"):
                cycle_warnings.append(f"insurmountable_blocker_file_{blocker_err}")

            for warning in sorted(set(cycle_warnings)):
                _append_jsonl(
                    config.events_path,
                    {
                        "timestamp": timestamp,
                        "cycle_number": cycle_number,
                        "event_type": "warning",
                        "action_code": "warning",
                        "payload": {"message": warning},
                        "requires_optimus_action": False,
                    },
                )

            terminal_reason: Optional[str] = None
            evidence_file: Optional[str] = None

            if done_ok:
                terminal_reason = "project_done"
                evidence_file = str(done_path)
            elif blocker_ok:
                terminal_reason = "insurmountable_blocker"
                evidence_file = str(blocker_path)
            elif rate_state.get("all_rate_gates_blocking"):
                terminal_reason = "all_rate_gates_blocking"
                evidence_file = str(all_rate_path)
                _write_json(
                    all_rate_path,
                    {
                        "status": "all_rate_gates_blocking",
                        "reason": "all configured profiles are hard-gated",
                        "generated_at": timestamp,
                        "profiles": rate_state.get("profiles", []),
                    },
                )

            directives = build_directives(cycle_number, snapshot, rate_state, config)
            pending_directives = directives

            for directive in directives:
                _append_jsonl(
                    config.events_path,
                    {
                        "timestamp": timestamp,
                        "cycle_number": cycle_number,
                        "event_type": "directive",
                        "action_code": directive["directive_type"],
                        "payload": directive,
                        "requires_optimus_action": bool(directive.get("requires_optimus_action")),
                    },
                )

            heartbeat_payload = {
                "timestamp": timestamp,
                "cycle_number": cycle_number,
                "status": "terminal" if terminal_reason else "running",
                "active_workers_summary": snapshot.get("active_workers_summary", {}),
                "profiles_state": rate_state.get("profiles", []),
                "warnings": sorted(set(cycle_warnings)),
                "pending_directives_count": len(pending_directives),
                "allow_autonomous_ops": config.allow_autonomous_ops,
            }
            _write_json(config.heartbeat_path, heartbeat_payload)

            maybe_emit_stdout(
                config,
                (
                    f"[cycle {cycle_number}] terminal={terminal_reason or 'none'} "
                    f"active_workers={heartbeat_payload['active_workers_summary'].get('active_count', 0)} "
                    f"directives={len(pending_directives)}"
                ),
            )

            if terminal_reason:
                final_state = {
                    "terminal_reason": terminal_reason,
                    "evidence_file": evidence_file,
                    "last_cycle_number": cycle_number,
                    "profiles_state": rate_state.get("profiles", []),
                    "active_workers_summary": snapshot.get("active_workers_summary", {}),
                    "pending_directives": pending_directives,
                    "generated_at": timestamp,
                }
                _write_json(config.final_state_path, final_state)

                _append_jsonl(
                    config.events_path,
                    {
                        "timestamp": timestamp,
                        "cycle_number": cycle_number,
                        "event_type": "terminal",
                        "action_code": terminal_reason,
                        "payload": final_state,
                        "requires_optimus_action": True,
                    },
                )

                return {
                    "ok": True,
                    "tool": "optimus-cycle-controller",
                    "terminal_reason": terminal_reason,
                    "evidence_file": evidence_file,
                    "final_state_path": str(config.final_state_path),
                    "events_path": str(config.events_path),
                    "heartbeat_path": str(config.heartbeat_path),
                    "last_cycle_number": cycle_number,
                }

            if config.max_cycles is not None and cycle_number >= config.max_cycles:
                return {
                    "ok": False,
                    "tool": "optimus-cycle-controller",
                    "status": "running",
                    "terminal_reason": None,
                    "reason": "max_cycles_reached_without_terminal",
                    "last_cycle_number": cycle_number,
                    "events_path": str(config.events_path),
                    "heartbeat_path": str(config.heartbeat_path),
                }

            sleep_seconds = int(config.sleep_minutes * 60)
            _append_jsonl(
                config.events_path,
                {
                    "timestamp": timestamp,
                    "cycle_number": cycle_number,
                    "event_type": "sleep",
                    "action_code": "sleep_interval",
                    "payload": {
                        "sleep_seconds": sleep_seconds,
                        "dry_run": config.dry_run,
                    },
                    "requires_optimus_action": False,
                },
            )

            if not config.dry_run and sleep_seconds > 0:
                time.sleep(sleep_seconds)

    finally:
        release_lock(config.lock_path)


def main() -> int:
    args = parse_args()
    if args.verify_final_state:
        try:
            validation = validate_stop_authorization(Path(args.verify_final_state))
            result = {
                "ok": bool(validation.get("authorized")),
                "tool": "optimus-cycle-controller",
                "mode": "verify_final_state",
                **validation,
            }
        except Exception as exc:  # pylint: disable=broad-except
            result = {
                "ok": False,
                "tool": "optimus-cycle-controller",
                "mode": "verify_final_state",
                "error": "runtime_error",
                "message": str(exc),
            }
    else:
        try:
            payload = _read_input_payload(args.input_json)
            config = normalize_config(payload)
            result = run_controller(config)
        except Exception as exc:  # pylint: disable=broad-except
            result = {
                "ok": False,
                "tool": "optimus-cycle-controller",
                "error": "runtime_error",
                "message": str(exc),
            }

    if args.json_pretty:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(json.dumps(result, sort_keys=True))

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
