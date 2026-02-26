#!/usr/bin/env python3
"""Evaluate orchestration cycle rate gates, dispatch policy, and sleep decision."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

TOOL = "cycle-tick"
TOOL_VERSION = "0.1.0"
SCHEMA_VERSION = "1.0"

ACTIONS = {
    "continue_dispatch",
    "continue_with_soft_cap",
    "hold_and_sleep_until_reset",
    "wind_down_no_new_dispatch",
}

DEFAULT_MAX_RUNNING_WORKERS = 6


class ToolError(Exception):
    def __init__(self, code: str, message: str, stage: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.stage = stage


@dataclass
class TickInput:
    repo_root: Path
    cycle_number: int
    status_profiles_scope: str
    rate_gate_5h_percent: float
    rate_gate_weekly_percent: float
    soft_rate_gate_5h_percent: float
    soft_rate_gate_weekly_percent: float
    soft_rate_gated_max_running_workers: int
    rate_reset_wait_max_hours: float
    sleep_minutes: int
    allow_dispatch: bool
    user_steering_active: bool
    dry_run: bool


@dataclass
class RateProfile:
    alias: str
    hard_gated: bool
    soft_gated: bool
    reset_at: str | None
    reset_in_hours: float | None
    recommended_action: str | None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso_to_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
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


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def as_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        s = value.strip()
        return s or None
    return str(value)


def first_present(obj: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in obj and obj[key] is not None:
            return obj[key]
    return None


def validate_thresholds(cfg: TickInput) -> None:
    numeric_bounds = [
        ("rate_gate_5h_percent", cfg.rate_gate_5h_percent),
        ("rate_gate_weekly_percent", cfg.rate_gate_weekly_percent),
        ("soft_rate_gate_5h_percent", cfg.soft_rate_gate_5h_percent),
        ("soft_rate_gate_weekly_percent", cfg.soft_rate_gate_weekly_percent),
    ]
    for name, value in numeric_bounds:
        if value < 0 or value > 100:
            raise ToolError("validation_error", f"{name} must be within [0,100]", stage="validate")

    if cfg.soft_rate_gate_5h_percent < cfg.rate_gate_5h_percent:
        raise ToolError(
            "validation_error",
            "soft_rate_gate_5h_percent must be >= rate_gate_5h_percent",
            stage="validate",
        )
    if cfg.soft_rate_gate_weekly_percent < cfg.rate_gate_weekly_percent:
        raise ToolError(
            "validation_error",
            "soft_rate_gate_weekly_percent must be >= rate_gate_weekly_percent",
            stage="validate",
        )

    if cfg.soft_rate_gated_max_running_workers < 1:
        raise ToolError("validation_error", "soft_rate_gated_max_running_workers must be >= 1", stage="validate")
    if cfg.rate_reset_wait_max_hours < 0:
        raise ToolError("validation_error", "rate_reset_wait_max_hours must be >= 0", stage="validate")
    if cfg.sleep_minutes < 0:
        raise ToolError("validation_error", "sleep_minutes must be >= 0", stage="validate")


def parse_args_to_input(args: argparse.Namespace) -> TickInput:
    payload: dict[str, Any] = {}
    if args.input_json:
        payload = load_json_input(args.input_json)

    repo_root = as_str(args.repo_root or payload.get("repo_root"))
    if not repo_root:
        raise ToolError("input_error", "repo_root is required", stage="input")

    cycle_number = as_int(args.cycle_number if args.cycle_number is not None else payload.get("cycle_number"))
    if cycle_number is None:
        raise ToolError("input_error", "cycle_number is required", stage="input")

    cfg = TickInput(
        repo_root=Path(repo_root).expanduser().resolve(),
        cycle_number=cycle_number,
        status_profiles_scope=as_str(args.status_profiles_scope or payload.get("status_profiles_scope") or "all-configured-plus-primary") or "all-configured-plus-primary",
        rate_gate_5h_percent=float(args.rate_gate_5h_percent if args.rate_gate_5h_percent is not None else payload.get("rate_gate_5h_percent", 15)),
        rate_gate_weekly_percent=float(args.rate_gate_weekly_percent if args.rate_gate_weekly_percent is not None else payload.get("rate_gate_weekly_percent", 10)),
        soft_rate_gate_5h_percent=float(args.soft_rate_gate_5h_percent if args.soft_rate_gate_5h_percent is not None else payload.get("soft_rate_gate_5h_percent", 40)),
        soft_rate_gate_weekly_percent=float(args.soft_rate_gate_weekly_percent if args.soft_rate_gate_weekly_percent is not None else payload.get("soft_rate_gate_weekly_percent", 25)),
        soft_rate_gated_max_running_workers=int(args.soft_rate_gated_max_running_workers if args.soft_rate_gated_max_running_workers is not None else payload.get("soft_rate_gated_max_running_workers", 3)),
        rate_reset_wait_max_hours=float(args.rate_reset_wait_max_hours if args.rate_reset_wait_max_hours is not None else payload.get("rate_reset_wait_max_hours", 4)),
        sleep_minutes=int(args.sleep_minutes if args.sleep_minutes is not None else payload.get("sleep_minutes", 5)),
        allow_dispatch=bool(payload.get("allow_dispatch", True) if args.allow_dispatch is None else args.allow_dispatch),
        user_steering_active=bool(payload.get("user_steering_active", False) if args.user_steering_active is None else args.user_steering_active),
        dry_run=bool(payload.get("dry_run", False) or args.dry_run),
    )

    validate_thresholds(cfg)
    return cfg


def load_json_input(path: str) -> dict[str, Any]:
    if path == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ToolError("input_error", "input payload must be a JSON object", stage="input")
    return data


def read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ToolError("state_read_error", f"Malformed JSON file {path}: {exc}", stage="state_read") from exc
    except OSError as exc:
        raise ToolError("state_read_error", f"Failed to read {path}: {exc}", stage="state_read") from exc


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=False))
        fh.write("\n")


def extract_workers_active_count(repo_root: Path, warnings: list[dict[str, Any]]) -> int | None:
    reports_root = repo_root / "reports" / "optimus-prime"

    snapshot_file = reports_root / "STATUS_SNAPSHOT.json"
    if snapshot_file.exists():
        data = read_json(snapshot_file)
        if isinstance(data, dict):
            counts = data.get("counts")
            if isinstance(counts, dict):
                active = as_int(counts.get("active_workers"))
                if active is not None:
                    return active

    registry_file = reports_root / "WORKER_REGISTRY.json"
    data = read_json(registry_file)
    if data is None:
        warnings.append(
            {
                "code": "missing_worker_registry",
                "message": "WORKER_REGISTRY.json missing; active worker count unavailable",
                "path": str(registry_file),
            }
        )
        return None

    workers: list[dict[str, Any]] = []
    if isinstance(data, dict):
        if isinstance(data.get("workers"), list):
            workers = [item for item in data["workers"] if isinstance(item, dict)]
        elif isinstance(data.get("workers"), dict):
            workers = [item for item in data["workers"].values() if isinstance(item, dict)]
    elif isinstance(data, list):
        workers = [item for item in data if isinstance(item, dict)]

    active = 0
    for worker in workers:
        state = as_str(first_present(worker, ["session_state", "state", "status"])) or ""
        norm = state.lower().replace("_", "-")
        if norm in {"running", "active", "busy"}:
            active += 1
    return active


def parse_rate_profiles(cfg: TickInput, warnings: list[dict[str, Any]]) -> tuple[str, list[RateProfile], dict[str, Any] | None]:
    reports_root = cfg.repo_root / "reports" / "optimus-prime"
    registry_path = reports_root / "PROFILE_RATE_REGISTRY.json"
    registry = read_json(registry_path)

    if not isinstance(registry, dict):
        warnings.append(
            {
                "code": "missing_rate_snapshot",
                "message": "PROFILE_RATE_REGISTRY.json missing or invalid; using conservative no-dispatch policy",
                "path": str(registry_path),
            }
        )
        return "unknown", [], None

    running_mode = as_str(registry.get("profile_running_mode")) or "unknown"
    profiles_raw = registry.get("profiles")

    profile_map: dict[str, dict[str, Any]] = {}
    if isinstance(profiles_raw, dict):
        for alias, value in profiles_raw.items():
            if isinstance(value, dict):
                profile_map[str(alias)] = value
    elif isinstance(profiles_raw, list):
        for item in profiles_raw:
            if isinstance(item, dict):
                alias = as_str(first_present(item, ["alias", "profile", "name"]))
                if alias:
                    profile_map[alias] = item

    if not profile_map:
        warnings.append(
            {
                "code": "missing_rate_profiles",
                "message": "No profiles found in PROFILE_RATE_REGISTRY.json; using conservative no-dispatch policy",
                "path": str(registry_path),
            }
        )
        return running_mode, [], registry

    parsed: list[RateProfile] = []
    for alias in sorted(profile_map.keys()):
        p = profile_map[alias]

        remaining_5h = as_float(first_present(p, ["five_hour_remaining_percent", "remaining_5h_percent"]))
        remaining_weekly = as_float(first_present(p, ["weekly_remaining_percent", "remaining_weekly_percent"]))

        five_hour = p.get("five_hour") if isinstance(p.get("five_hour"), dict) else p.get("primary") if isinstance(p.get("primary"), dict) else None
        weekly = p.get("weekly") if isinstance(p.get("weekly"), dict) else p.get("secondary") if isinstance(p.get("secondary"), dict) else None

        if remaining_5h is None and isinstance(five_hour, dict):
            used = as_float(five_hour.get("used_percent"))
            remaining_5h = max(0.0, 100.0 - used) if used is not None else as_float(five_hour.get("remaining_percent"))
        if remaining_weekly is None and isinstance(weekly, dict):
            used_w = as_float(weekly.get("used_percent"))
            remaining_weekly = max(0.0, 100.0 - used_w) if used_w is not None else as_float(weekly.get("remaining_percent"))

        hard_flag = bool(first_present(p, ["hard_gated", "gated"]))
        if isinstance(five_hour, dict) and bool(five_hour.get("gated")):
            hard_flag = True
        if isinstance(weekly, dict) and bool(weekly.get("gated")):
            hard_flag = True

        if remaining_5h is not None and remaining_5h <= cfg.rate_gate_5h_percent:
            hard_flag = True
        if remaining_weekly is not None and remaining_weekly <= cfg.rate_gate_weekly_percent:
            hard_flag = True

        soft_flag = bool(first_present(p, ["soft_concurrency_gated", "soft_gated"]))
        if remaining_5h is not None and remaining_5h <= cfg.soft_rate_gate_5h_percent:
            soft_flag = True
        if remaining_weekly is not None and remaining_weekly <= cfg.soft_rate_gate_weekly_percent:
            soft_flag = True

        reset_at = as_str(first_present(p, ["reset_at", "next_reset_at"]))
        if reset_at is None and isinstance(five_hour, dict):
            reset_at = as_str(first_present(five_hour, ["reset_at", "resets_at", "resetAt", "resetsAt"]))
        if reset_at is None and isinstance(weekly, dict):
            reset_at = as_str(first_present(weekly, ["reset_at", "resets_at", "resetAt", "resetsAt"]))

        reset_in_hours = as_float(first_present(p, ["reset_in_hours", "wait_hours"]))
        if reset_in_hours is None and reset_at:
            dt = parse_iso_to_utc(reset_at)
            if dt is not None:
                reset_in_hours = (dt - utc_now()).total_seconds() / 3600.0

        recommended_action = as_str(first_present(p, ["recommended_action", "action"]))

        parsed.append(
            RateProfile(
                alias=alias,
                hard_gated=hard_flag,
                soft_gated=soft_flag,
                reset_at=reset_at,
                reset_in_hours=reset_in_hours,
                recommended_action=recommended_action,
            )
        )

    return running_mode, parsed, registry


def earliest_reset_within_window(gated_profiles: list[RateProfile], max_hours: float) -> tuple[str | None, float | None]:
    candidate: tuple[datetime, str] | None = None
    now = utc_now()

    for p in gated_profiles:
        dt = parse_iso_to_utc(p.reset_at)
        if dt is None:
            continue
        delta_hours = (dt - now).total_seconds() / 3600.0
        if delta_hours < 0:
            continue
        if delta_hours <= max_hours:
            if candidate is None or dt < candidate[0]:
                candidate = (dt, p.alias)

    if candidate is None:
        return None, None
    until = candidate[0].replace(microsecond=0).isoformat().replace("+00:00", "Z")
    duration = max(0.0, (candidate[0] - now).total_seconds() / 3600.0)
    return until, duration


def evaluate_policy(cfg: TickInput) -> dict[str, Any]:
    warnings: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    active_workers = extract_workers_active_count(cfg.repo_root, warnings)

    running_mode, profiles, raw_registry = parse_rate_profiles(cfg, warnings)

    gated_profiles = [p for p in profiles if p.hard_gated]
    soft_profiles = [p for p in profiles if p.soft_gated and not p.hard_gated]

    missing_rate_snapshot = len(profiles) == 0

    dispatch_allowed = bool(cfg.allow_dispatch)
    action = "continue_dispatch"

    if cfg.user_steering_active:
        warnings.append(
            {
                "code": "user_steering_active",
                "message": "User steering active; sleep recommendation will be disabled",
            }
        )

    if not cfg.allow_dispatch:
        dispatch_allowed = False
        action = "wind_down_no_new_dispatch"

    if missing_rate_snapshot:
        dispatch_allowed = False
        action = "wind_down_no_new_dispatch"
        warnings.append(
            {
                "code": "conservative_no_dispatch",
                "message": "Rate snapshot missing; conservative no-dispatch policy applied",
            }
        )

    elif gated_profiles:
        if running_mode in {"single-profile", "single-user", "unknown"}:
            dispatch_allowed = False
            until, _ = earliest_reset_within_window(gated_profiles, cfg.rate_reset_wait_max_hours)
            if until and not cfg.user_steering_active:
                action = "hold_and_sleep_until_reset"
            else:
                action = "wind_down_no_new_dispatch"
        elif running_mode == "multiple-users":
            eligible_profiles = [p for p in profiles if not p.hard_gated]
            dispatch_allowed = bool(cfg.allow_dispatch and eligible_profiles)
            if dispatch_allowed:
                action = "continue_dispatch"
            else:
                until, _ = earliest_reset_within_window(gated_profiles, cfg.rate_reset_wait_max_hours)
                if until and not cfg.user_steering_active:
                    action = "hold_and_sleep_until_reset"
                else:
                    action = "wind_down_no_new_dispatch"

    effective_max_running_workers = DEFAULT_MAX_RUNNING_WORKERS

    if action in {"wind_down_no_new_dispatch", "hold_and_sleep_until_reset"}:
        effective_max_running_workers = 0
    elif soft_profiles:
        action = "continue_with_soft_cap"
        effective_max_running_workers = min(DEFAULT_MAX_RUNNING_WORKERS, cfg.soft_rate_gated_max_running_workers)

    sleep_should = False
    sleep_duration = 0
    sleep_until: str | None = None

    if not cfg.user_steering_active:
        if action == "hold_and_sleep_until_reset":
            sleep_until, _ = earliest_reset_within_window(gated_profiles, cfg.rate_reset_wait_max_hours)
            if sleep_until is not None:
                dt = parse_iso_to_utc(sleep_until)
                if dt is not None:
                    mins = int(max(0, round((dt - utc_now()).total_seconds() / 60.0)))
                    sleep_duration = mins
                    sleep_should = True
            if sleep_until is None:
                action = "wind_down_no_new_dispatch"
        elif action in {"continue_dispatch", "continue_with_soft_cap"} and cfg.sleep_minutes > 0:
            sleep_should = True
            sleep_duration = cfg.sleep_minutes

    per_profile_caps: dict[str, int] = {}
    if running_mode == "multiple-users" and soft_profiles:
        for p in soft_profiles:
            per_profile_caps[p.alias] = cfg.soft_rate_gated_max_running_workers

    if action not in ACTIONS:
        errors.append({"code": "internal_error", "message": f"Invalid action resolved: {action}", "stage": "policy"})

    sleep_obj = {
        "should_sleep": sleep_should,
        "duration_minutes": sleep_duration,
        "until": sleep_until,
    }

    human_summary = (
        f"cycle={cfg.cycle_number} action={action} dispatch_allowed={'yes' if dispatch_allowed else 'no'} "
        f"effective_max_running_workers={effective_max_running_workers} mode={running_mode} "
        f"gated={','.join(p.alias for p in gated_profiles) or 'none'} "
        f"soft_gated={','.join(p.alias for p in soft_profiles) or 'none'} "
        f"sleep={'yes' if sleep_should else 'no'}({sleep_duration}m)"
    )

    return {
        "ok": len(errors) == 0,
        "cycle_number": cfg.cycle_number,
        "action": action,
        "dispatch_allowed": dispatch_allowed,
        "effective_max_running_workers": effective_max_running_workers,
        "profile_running_mode": running_mode,
        "gated_profiles": [p.alias for p in gated_profiles],
        "soft_gated_profiles": [p.alias for p in soft_profiles],
        "sleep_recommendation": sleep_obj,
        "human_summary_line": human_summary,
        "warnings": warnings,
        "errors": errors,
        "active_workers": active_workers,
        "per_profile_soft_caps": per_profile_caps,
        "profiles_detail": [
            {
                "alias": p.alias,
                "hard_gated": p.hard_gated,
                "soft_gated": p.soft_gated,
                "reset_at": p.reset_at,
                "reset_in_hours": p.reset_in_hours,
                "recommended_action": p.recommended_action,
            }
            for p in profiles
        ],
        "raw_rate_registry": raw_registry,
    }


def write_logs(cfg: TickInput, policy: dict[str, Any]) -> tuple[bool, bool]:
    reports_root = cfg.repo_root / "reports" / "optimus-prime"
    cycle_path = reports_root / "CYCLE_LOG.jsonl"
    rate_path = reports_root / "RATE_STATUS_LOG.jsonl"

    cycle_entry = {
        "timestamp": utc_now_iso(),
        "event": "cycle_tick",
        "cycle_number": cfg.cycle_number,
        "action": policy["action"],
        "dispatch_allowed": policy["dispatch_allowed"],
        "effective_max_running_workers": policy["effective_max_running_workers"],
        "profile_running_mode": policy["profile_running_mode"],
        "gated_profiles": policy["gated_profiles"],
        "soft_gated_profiles": policy["soft_gated_profiles"],
        "sleep_recommendation": policy["sleep_recommendation"],
        "human_summary_line": policy["human_summary_line"],
        "active_workers": policy.get("active_workers"),
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
    }

    rate_entry = {
        "timestamp": utc_now_iso(),
        "event": "cycle_tick_rate_eval",
        "cycle_number": cfg.cycle_number,
        "profile_running_mode": policy["profile_running_mode"],
        "profiles": policy["profiles_detail"],
        "gated_profiles": policy["gated_profiles"],
        "soft_gated_profiles": policy["soft_gated_profiles"],
        "thresholds": {
            "rate_gate_5h_percent": cfg.rate_gate_5h_percent,
            "rate_gate_weekly_percent": cfg.rate_gate_weekly_percent,
            "soft_rate_gate_5h_percent": cfg.soft_rate_gate_5h_percent,
            "soft_rate_gate_weekly_percent": cfg.soft_rate_gate_weekly_percent,
            "soft_rate_gated_max_running_workers": cfg.soft_rate_gated_max_running_workers,
            "rate_reset_wait_max_hours": cfg.rate_reset_wait_max_hours,
        },
        "action": policy["action"],
        "dispatch_allowed": policy["dispatch_allowed"],
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
    }

    append_jsonl(cycle_path, cycle_entry)
    append_jsonl(rate_path, rate_entry)
    return True, True


def run_cycle_tick(cfg: TickInput) -> dict[str, Any]:
    policy = evaluate_policy(cfg)

    logs_written = {"cycle_log": False, "rate_log": False}

    if not cfg.dry_run and policy["ok"]:
        try:
            cycle_ok, rate_ok = write_logs(cfg, policy)
            logs_written = {"cycle_log": cycle_ok, "rate_log": rate_ok}
        except OSError as exc:
            policy["ok"] = False
            policy["errors"].append(
                {
                    "code": "log_write_failed",
                    "message": f"Failed to write cycle/rate logs: {exc}",
                    "stage": "log_write",
                }
            )
        except ToolError as exc:
            policy["ok"] = False
            policy["errors"].append(
                {"code": exc.code, "message": exc.message, "stage": exc.stage},
            )

    if cfg.dry_run:
        policy["warnings"].append(
            {
                "code": "dry_run",
                "message": "Dry-run mode enabled; decision returned without file mutations",
            }
        )

    out = {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "ok": bool(policy["ok"]),
        "cycle_number": cfg.cycle_number,
        "action": policy["action"],
        "dispatch_allowed": bool(policy["dispatch_allowed"]),
        "effective_max_running_workers": int(policy["effective_max_running_workers"]),
        "profile_running_mode": policy["profile_running_mode"],
        "gated_profiles": policy["gated_profiles"],
        "soft_gated_profiles": policy["soft_gated_profiles"],
        "sleep_recommendation": policy["sleep_recommendation"],
        "logs_written": logs_written,
        "human_summary_line": policy["human_summary_line"],
        "warnings": policy["warnings"],
        "errors": policy["errors"],
        "per_profile_soft_caps": policy.get("per_profile_soft_caps", {}),
    }
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cycle decision tick for Optimus orchestration")
    parser.add_argument("--input-json", help="JSON input file path or '-' for stdin")
    parser.add_argument("--repo-root")
    parser.add_argument("--cycle-number", type=int)
    parser.add_argument("--status-profiles-scope")
    parser.add_argument("--rate-gate-5h-percent", type=float)
    parser.add_argument("--rate-gate-weekly-percent", type=float)
    parser.add_argument("--soft-rate-gate-5h-percent", type=float)
    parser.add_argument("--soft-rate-gate-weekly-percent", type=float)
    parser.add_argument("--soft-rate-gated-max-running-workers", type=int)
    parser.add_argument("--rate-reset-wait-max-hours", type=float)
    parser.add_argument("--sleep-minutes", type=int)
    parser.add_argument("--allow-dispatch", dest="allow_dispatch", action="store_true")
    parser.add_argument("--no-allow-dispatch", dest="allow_dispatch", action="store_false")
    parser.set_defaults(allow_dispatch=None)
    parser.add_argument("--user-steering-active", dest="user_steering_active", action="store_true")
    parser.add_argument("--user-steering-inactive", dest="user_steering_active", action="store_false")
    parser.set_defaults(user_steering_active=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json-pretty", action="store_true")
    return parser.parse_args()


def print_json(obj: dict[str, Any], pretty: bool) -> None:
    if pretty:
        print(json.dumps(obj, indent=2, sort_keys=False))
    else:
        print(json.dumps(obj, separators=(",", ":"), sort_keys=False))


def main() -> int:
    args = parse_args()
    try:
        cfg = parse_args_to_input(args)
        out = run_cycle_tick(cfg)
        print_json(out, args.json_pretty)
        return 0 if out.get("ok") else 1
    except ToolError as exc:
        out = {
            "schema_version": SCHEMA_VERSION,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "ok": False,
            "cycle_number": args.cycle_number,
            "action": "wind_down_no_new_dispatch",
            "dispatch_allowed": False,
            "effective_max_running_workers": 0,
            "profile_running_mode": "unknown",
            "gated_profiles": [],
            "soft_gated_profiles": [],
            "sleep_recommendation": {"should_sleep": False, "duration_minutes": 0, "until": None},
            "logs_written": {"cycle_log": False, "rate_log": False},
            "human_summary_line": "",
            "warnings": [],
            "errors": [{"code": exc.code, "message": exc.message, "stage": exc.stage}],
            "per_profile_soft_caps": {},
        }
        print_json(out, args.json_pretty)
        return 1
    except json.JSONDecodeError as exc:
        out = {
            "schema_version": SCHEMA_VERSION,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "ok": False,
            "errors": [{"code": "input_error", "message": f"Invalid JSON input: {exc}", "stage": "input"}],
        }
        print_json(out, args.json_pretty)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
