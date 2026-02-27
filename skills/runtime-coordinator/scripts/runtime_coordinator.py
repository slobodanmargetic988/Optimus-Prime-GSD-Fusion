#!/usr/bin/env python3
"""Runtime strategy/lease coordinator plus blocker index aggregation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

TOOL = "runtime-coordinator"
TOOL_VERSION = "0.4.0"
SCHEMA_VERSION = "1.0"

STRATEGIES = {"none", "external_url", "shared_runtime", "isolated_runtime"}
ACTIONS = {
    "resolve",
    "release_lease",
    "upsert_runtime",
    "refresh_blocker_index",
    "log_blocker",
    "bootstrap",
    "start",
    "health",
    "stop",
    "repair",
}
RUNTIME_STATUSES = {"starting", "healthy", "degraded", "failed", "stopped"}
TEST_TRAIN_MODES = {"off", "final-stage", "forced-shared-env"}
BLOCKER_CATEGORIES = {
    "infra",
    "runtime",
    "env",
    "test-train",
    "dependency",
    "code",
    "test",
    "review",
    "orchestration",
    "external",
    "unknown",
}
LOCK_NAME_RE = re.compile(r"[^a-zA-Z0-9._-]+")


class ToolError(Exception):
    def __init__(self, code: str, message: str, stage: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.stage = stage


@dataclass
class RuntimeInput:
    repo_root: Path
    action: str
    task_identifier: str | None
    worker_slot: str | None
    worker_role: str | None
    task_kind: str
    requires_browser: bool
    mutating_flow: bool
    runtime_strategy_override: str | None
    test_train_mode: str
    shared_test_base_url: str | None
    runtime_profile_id: str | None
    external_base_url: str | None
    runtime_id: str | None
    lease_id: str | None
    requested_status: str | None
    runtime_profiles_path: Path
    runtime_registry_path: Path
    runtime_leases_path: Path
    blockers_path: Path
    blocker_index_path: Path
    blocker_adaptation_report_path: Path
    blocker_index_min_count: int
    blocker_index_max_entries: int
    blocker_stage: str | None
    blocker_code: str | None
    blocker_category: str | None
    blocker_summary: str | None
    blocker_signature: str | None
    blocker_retryable: bool
    blocker_evidence_paths: list[str]
    test_train_pipeline_path: Path
    runtime_health_path: Path
    runtime_action_log_path: Path
    runtime_repair_tasks_path: Path
    runtime_locks_dir: Path
    repair_force_fingerprint: str | None
    repair_force_delegate: bool


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def _str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        t = value.strip()
        return t or None
    t = str(value).strip()
    return t or None


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _list_of_str(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            text = _str(item)
            if text:
                out.append(text)
        return out
    text = _str(value)
    return [text] if text else []


def _to_iso(value: Any) -> str | None:
    text = _str(value)
    if not text:
        return None
    try:
        if text.endswith("Z"):
            dt = datetime.fromisoformat(text[:-1] + "+00:00")
        else:
            dt = datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except ValueError:
        return None


def parse_json_input(path: str) -> dict[str, Any]:
    raw = Path(path).read_text(encoding="utf-8") if path != "-" else sys.stdin.read()
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ToolError("input_error", "input must be JSON object", stage="input")
    return data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Runtime strategy and lease coordinator")
    parser.add_argument("--input-json", required=True, help="Path to json input or '-' for stdin")
    parser.add_argument("--json-pretty", action="store_true")
    return parser.parse_args()


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ToolError("state_read_error", f"Expected JSON object in {path}", stage="state")
    return data


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")


def _parse_iso_dt(value: Any) -> datetime | None:
    text = _str(value)
    if not text:
        return None
    try:
        if text.endswith("Z"):
            dt = datetime.fromisoformat(text[:-1] + "+00:00")
        else:
            dt = datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def _default_pipeline_config() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "pipeline_id": "default",
        "mode_policy": {
            "off": {"hard_gate": False},
            "final-stage": {"hard_gate": True},
            "forced-shared-env": {"hard_gate": True},
        },
        "deploy": {
            "command": "",
            "cwd": "${REPO_ROOT}",
            "timeout_sec": 900,
        },
        "health": {
            "require_consecutive_passes": 2,
            "checks": [],
            "profile_check_required": True,
        },
        "repair": {
            "self_heal_commands": [],
            "cooldown_sec": 300,
            "max_attempts_per_fingerprint_window": 5,
            "create_dev_task": True,
            "create_blocker": True,
        },
        "locking": {
            "enable_single_flight": True,
            "lock_ttl_sec": 1800,
        },
        "lease_policy": {
            "stale_ttl_sec": 900,
        },
    }


def load_test_train_pipeline(inp: RuntimeInput, *, required: bool) -> dict[str, Any]:
    if not inp.test_train_pipeline_path.exists():
        if required:
            raise ToolError(
                "config_error",
                f"missing test-train pipeline config: {inp.test_train_pipeline_path}",
                stage="config",
            )
        return _default_pipeline_config()
    data = _read_json(inp.test_train_pipeline_path, _default_pipeline_config())
    if not isinstance(data, dict):
        raise ToolError(
            "config_error",
            f"invalid test-train pipeline config payload: {inp.test_train_pipeline_path}",
            stage="config",
        )
    return data


def _expand_env_placeholders(template: str, repo_root: Path) -> str:
    expanded = template.replace("${REPO_ROOT}", str(repo_root))
    missing: list[str] = []

    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        value = os.environ.get(key)
        if value is None:
            missing.append(key)
            return ""
        return value

    expanded = re.sub(r"\$\{([A-Z0-9_]+)\}", repl, expanded)
    if missing:
        joined = ", ".join(sorted(set(missing)))
        raise ToolError(
            "config_error",
            f"missing env placeholder value(s): {joined}",
            stage="config",
        )
    return expanded


def _safe_lock_name(name: str) -> str:
    text = LOCK_NAME_RE.sub("-", name.strip().lower()).strip("-")
    return text or "runtime-lock"


def _acquire_lock(inp: RuntimeInput, lock_name: str, ttl_sec: int) -> Path | None:
    pipeline = load_test_train_pipeline(inp, required=False)
    locking = pipeline.get("locking") if isinstance(pipeline.get("locking"), dict) else {}
    enable_locking = _bool((locking or {}).get("enable_single_flight"), True)
    if not enable_locking:
        return None

    lock_path = inp.runtime_locks_dir / f"{_safe_lock_name(lock_name)}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    if lock_path.exists():
        previous = _read_json(lock_path, {})
        created_at = _parse_iso_dt(previous.get("created_at")) if isinstance(previous, dict) else None
        if created_at is not None and (now - created_at).total_seconds() > max(30, ttl_sec):
            lock_path.unlink(missing_ok=True)
        else:
            raise ToolError(
                "locked",
                f"action '{lock_name}' already in progress",
                stage="lock",
            )
    payload = {
        "created_at": utc_now_iso(),
        "lock_name": lock_name,
        "tool": TOOL,
    }
    _write_json(lock_path, payload)
    return lock_path


def _release_lock(lock_path: Path | None) -> None:
    if lock_path is None:
        return
    try:
        lock_path.unlink(missing_ok=True)
    except OSError:
        return


def _runtime_health_default(inp: RuntimeInput, required_passes: int) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "updated_at": utc_now_iso(),
        "test_train_mode": inp.test_train_mode,
        "gate_state": "degraded" if inp.test_train_mode == "off" else "blocked",
        "consecutive_passes": 0,
        "required_passes": required_passes,
        "pipeline_checks": [],
        "profile_checks": [],
        "both_sources_pass": False,
        "last_failure_fingerprint": None,
        "next_heal_allowed_at": None,
    }


def _read_runtime_health(inp: RuntimeInput, required_passes: int) -> dict[str, Any]:
    return _read_json(inp.runtime_health_path, _runtime_health_default(inp, required_passes))


def _write_runtime_health(inp: RuntimeInput, payload: dict[str, Any]) -> None:
    payload["updated_at"] = utc_now_iso()
    _write_json(inp.runtime_health_path, payload)


def _append_runtime_action(
    inp: RuntimeInput,
    *,
    action: str,
    result: str,
    runtime_id: str | None,
    fingerprint: str | None,
    details: dict[str, Any],
) -> None:
    row = {
        "timestamp": utc_now_iso(),
        "action": action,
        "result": result,
        "runtime_id": runtime_id,
        "fingerprint": fingerprint,
        "details": details,
    }
    _append_jsonl(inp.runtime_action_log_path, row)


def _read_repair_tasks(inp: RuntimeInput) -> dict[str, Any]:
    return _read_json(
        inp.runtime_repair_tasks_path,
        {
            "schema_version": SCHEMA_VERSION,
            "updated_at": utc_now_iso(),
            "tasks": [],
        },
    )


def _write_repair_tasks(inp: RuntimeInput, payload: dict[str, Any]) -> None:
    payload["updated_at"] = utc_now_iso()
    _write_json(inp.runtime_repair_tasks_path, payload)


def _count_heal_attempts(inp: RuntimeInput, fingerprint: str) -> int:
    if not inp.runtime_action_log_path.exists():
        return 0
    count = 0
    for line in inp.runtime_action_log_path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            row = json.loads(text)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        if (_str(row.get("action")) or "").lower() != "heal":
            continue
        if (_str(row.get("fingerprint")) or "") != fingerprint:
            continue
        count += 1
    return count


def _repair_task_id(fingerprint: str, now: datetime) -> str:
    date_bucket = now.strftime("%Y%m%d")
    digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:8]
    return f"rr-{date_bucket}-{digest}"


def _sweep_stale_leases(leases_state: dict[str, Any], stale_ttl_sec: int) -> list[str]:
    released: list[str] = []
    leases = _leases(leases_state)
    now = datetime.now(timezone.utc)
    for lease in leases:
        if not isinstance(lease, dict):
            continue
        if (_str(lease.get("status")) or "").lower() != "active":
            continue
        seen = _parse_iso_dt(lease.get("updated_at")) or _parse_iso_dt(lease.get("created_at"))
        if seen is None:
            continue
        if (now - seen).total_seconds() <= stale_ttl_sec:
            continue
        lease["status"] = "released"
        lease["released_at"] = utc_now_iso()
        lease["updated_at"] = utc_now_iso()
        lease_id = _str(lease.get("lease_id"))
        if lease_id:
            released.append(lease_id)
    if released:
        leases_state["updated_at"] = utc_now_iso()
    return released


def _execute_shell(command: str, *, cwd: Path, timeout_sec: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd),
        shell=True,
        capture_output=True,
        text=True,
        timeout=max(1, timeout_sec),
        check=False,
    )


def _profile_health_checks(
    inp: RuntimeInput,
    registry: dict[str, Any],
    runtime_id: str | None = None,
) -> tuple[bool, list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    instances = _instances(registry)
    candidates: list[dict[str, Any]] = []
    for inst in instances:
        if not isinstance(inst, dict):
            continue
        if runtime_id and _str(inst.get("runtime_id")) != runtime_id:
            continue
        if inp.runtime_profile_id and _str(inst.get("profile_id")) != inp.runtime_profile_id:
            continue
        candidates.append(inst)

    if not candidates:
        checks.append(
            {
                "id": "profile-runtime-present",
                "type": "profile",
                "passed": False,
                "message": "no matching runtime instance found",
            }
        )
        return False, checks

    healthy_like = 0
    for inst in candidates:
        status = (_str(inst.get("status")) or "unknown").lower()
        passed = status in {"healthy", "degraded"}
        if passed:
            healthy_like += 1
        checks.append(
            {
                "id": f"profile-{_str(inst.get('runtime_id')) or 'runtime'}",
                "type": "profile",
                "runtime_id": _str(inst.get("runtime_id")),
                "status": status,
                "passed": passed,
            }
        )
    return healthy_like > 0, checks


def _pipeline_health_checks(
    inp: RuntimeInput,
    pipeline: dict[str, Any],
) -> tuple[bool, list[dict[str, Any]], str | None]:
    health = pipeline.get("health") if isinstance(pipeline.get("health"), dict) else {}
    checks_raw = health.get("checks") if isinstance(health, dict) else []
    checks = checks_raw if isinstance(checks_raw, list) else []

    results: list[dict[str, Any]] = []
    first_failure_fp: str | None = None
    all_pass = True
    for idx, item in enumerate(checks, start=1):
        if not isinstance(item, dict):
            continue
        check_id = _str(item.get("id")) or f"check-{idx}"
        check_type = (_str(item.get("type")) or "none").lower()
        timeout_sec = max(1, _int(item.get("timeout_sec"), 10))
        value = _str(item.get("value")) or ""
        passed = True
        message = "ok"
        try:
            if check_type == "none":
                passed = True
                message = "skipped"
            elif check_type == "url":
                if not value:
                    raise ToolError("config_error", f"url check '{check_id}' missing value", stage="config")
                req = urllib_request.Request(value, method="GET")
                with urllib_request.urlopen(req, timeout=timeout_sec) as resp:  # nosec B310
                    code = int(getattr(resp, "status", 200))
                    passed = 200 <= code < 400
                    message = f"http_status={code}"
            elif check_type == "cmd":
                if not value:
                    raise ToolError("config_error", f"cmd check '{check_id}' missing value", stage="config")
                cmd = _expand_env_placeholders(value, inp.repo_root)
                proc = _execute_shell(cmd, cwd=inp.repo_root, timeout_sec=timeout_sec)
                passed = proc.returncode == 0
                message = f"exit_code={proc.returncode}"
            else:
                raise ToolError(
                    "config_error",
                    f"unsupported health check type '{check_type}' for '{check_id}'",
                    stage="config",
                )
        except (ToolError, urllib_error.URLError, TimeoutError, subprocess.TimeoutExpired) as exc:
            passed = False
            message = str(exc)
        result = {
            "id": check_id,
            "type": check_type,
            "passed": passed,
            "message": message,
        }
        results.append(result)
        if not passed:
            all_pass = False
            if first_failure_fp is None:
                first_failure_fp = f"pipeline|{check_id}|{message}"
    return all_pass, results, first_failure_fp


def build_input(payload: dict[str, Any]) -> RuntimeInput:
    repo_root_raw = _str(payload.get("repo_root"))
    if not repo_root_raw:
        raise ToolError("input_error", "repo_root is required", stage="input")
    repo_root = Path(repo_root_raw).expanduser().resolve()

    action = (_str(payload.get("action")) or "resolve").lower()
    if action not in ACTIONS:
        raise ToolError("input_error", f"action must be one of {sorted(ACTIONS)}", stage="input")

    reports_root = repo_root / "reports" / "optimus-prime"

    runtime_profiles_path = Path(
        _str(payload.get("runtime_profiles_path"))
        or str(reports_root / "config" / "RUNTIME_PROFILES.json")
    ).expanduser().resolve()
    runtime_registry_path = Path(
        _str(payload.get("runtime_registry_path"))
        or str(reports_root / "RUNTIME_REGISTRY.json")
    ).expanduser().resolve()
    runtime_leases_path = Path(
        _str(payload.get("runtime_leases_path"))
        or str(reports_root / "TEST_RUNTIME_LEASES.json")
    ).expanduser().resolve()
    blockers_path = Path(
        _str(payload.get("blockers_path"))
        or str(reports_root / "BLOCKERS.jsonl")
    ).expanduser().resolve()
    blocker_index_path = Path(
        _str(payload.get("blocker_index_path"))
        or str(reports_root / "BLOCKER_INDEX.json")
    ).expanduser().resolve()
    blocker_adaptation_report_path = Path(
        _str(payload.get("blocker_adaptation_report_path"))
        or str(reports_root / "BLOCKER_ADAPTATION_CANDIDATES.md")
    ).expanduser().resolve()
    test_train_pipeline_path = Path(
        _str(payload.get("test_train_pipeline_path"))
        or str(reports_root / "config" / "TEST_TRAIN_PIPELINE.json")
    ).expanduser().resolve()
    runtime_health_path = Path(
        _str(payload.get("runtime_health_path"))
        or str(reports_root / "runtime" / "RUNTIME_HEALTH.json")
    ).expanduser().resolve()
    runtime_action_log_path = Path(
        _str(payload.get("runtime_action_log_path"))
        or str(reports_root / "runtime" / "RUNTIME_ACTION_LOG.jsonl")
    ).expanduser().resolve()
    runtime_repair_tasks_path = Path(
        _str(payload.get("runtime_repair_tasks_path"))
        or str(reports_root / "runtime" / "RUNTIME_REPAIR_TASKS.json")
    ).expanduser().resolve()
    runtime_locks_dir = Path(
        _str(payload.get("runtime_locks_dir"))
        or str(reports_root / "runtime" / "locks")
    ).expanduser().resolve()
    repair_force_fingerprint = _str(payload.get("repair_force_fingerprint"))
    repair_force_delegate = _bool(payload.get("repair_force_delegate"), False)

    runtime_strategy_override = (_str(payload.get("runtime_strategy_override")) or None)
    if runtime_strategy_override and runtime_strategy_override not in STRATEGIES:
        raise ToolError(
            "input_error",
            f"runtime_strategy_override must be one of {sorted(STRATEGIES)}",
            stage="input",
        )

    test_train_mode = (_str(payload.get("test_train_mode")) or "off").lower()
    if test_train_mode not in TEST_TRAIN_MODES:
        raise ToolError(
            "input_error",
            f"test_train_mode must be one of {sorted(TEST_TRAIN_MODES)}",
            stage="input",
        )
    shared_test_base_url = _str(payload.get("shared_test_base_url"))
    if test_train_mode != "off" and shared_test_base_url:
        raise ToolError(
            "input_error",
            "shared_test_base_url is deprecated for test-train mode; use reports/optimus-prime/config/TEST_TRAIN_PIPELINE.json",
            stage="input",
        )

    requested_status = _str(payload.get("requested_status"))
    if requested_status and requested_status not in RUNTIME_STATUSES:
        raise ToolError(
            "input_error",
            f"requested_status must be one of {sorted(RUNTIME_STATUSES)}",
            stage="input",
        )

    return RuntimeInput(
        repo_root=repo_root,
        action=action,
        task_identifier=_str(payload.get("task_identifier")),
        worker_slot=_str(payload.get("worker_slot")),
        worker_role=_str(payload.get("worker_role")),
        task_kind=(_str(payload.get("task_kind")) or "other").lower(),
        requires_browser=_bool(payload.get("requires_browser"), False),
        mutating_flow=_bool(payload.get("mutating_flow"), False),
        runtime_strategy_override=runtime_strategy_override,
        test_train_mode=test_train_mode,
        shared_test_base_url=shared_test_base_url,
        runtime_profile_id=_str(payload.get("runtime_profile_id")),
        external_base_url=_str(payload.get("external_base_url")),
        runtime_id=_str(payload.get("runtime_id")),
        lease_id=_str(payload.get("lease_id")),
        requested_status=requested_status,
        runtime_profiles_path=runtime_profiles_path,
        runtime_registry_path=runtime_registry_path,
        runtime_leases_path=runtime_leases_path,
        blockers_path=blockers_path,
        blocker_index_path=blocker_index_path,
        blocker_adaptation_report_path=blocker_adaptation_report_path,
        blocker_index_min_count=max(1, _int(payload.get("blocker_index_min_count"), 2)),
        blocker_index_max_entries=max(1, _int(payload.get("blocker_index_max_entries"), 20)),
        blocker_stage=_str(payload.get("blocker_stage")),
        blocker_code=_str(payload.get("blocker_code")),
        blocker_category=_str(payload.get("blocker_category")),
        blocker_summary=_str(payload.get("blocker_summary")),
        blocker_signature=_str(payload.get("blocker_signature")),
        blocker_retryable=_bool(payload.get("blocker_retryable"), True),
        blocker_evidence_paths=_list_of_str(payload.get("blocker_evidence_paths")),
        test_train_pipeline_path=test_train_pipeline_path,
        runtime_health_path=runtime_health_path,
        runtime_action_log_path=runtime_action_log_path,
        runtime_repair_tasks_path=runtime_repair_tasks_path,
        runtime_locks_dir=runtime_locks_dir,
        repair_force_fingerprint=repair_force_fingerprint,
        repair_force_delegate=repair_force_delegate,
    )


def load_profiles(path: Path) -> list[dict[str, Any]]:
    data = _read_json(path, {"schema_version": "1.0", "profiles": []})
    profiles = data.get("profiles")
    if not isinstance(profiles, list):
        raise ToolError("config_error", f"profiles array missing in {path}", stage="profiles")
    return [p for p in profiles if isinstance(p, dict)]


def choose_profile(inp: RuntimeInput, profiles: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not profiles:
        return None

    if inp.runtime_profile_id:
        for p in profiles:
            if _str(p.get("profile_id")) == inp.runtime_profile_id:
                return p
        raise ToolError("config_error", f"runtime profile not found: {inp.runtime_profile_id}", stage="profiles")

    defaults = [p for p in profiles if _bool(p.get("default_for_playwright"), False)]
    return defaults[0] if defaults else profiles[0]


def is_shared_test_train_flow(inp: RuntimeInput) -> bool:
    if inp.test_train_mode not in {"final-stage", "forced-shared-env"}:
        return False
    role = (inp.worker_role or "").lower()
    if role in {"tester", "flex-tester"}:
        return True
    return bool(inp.requires_browser and inp.task_kind in {"ui_flow", "browser", "e2e"})


def resolve_strategy(inp: RuntimeInput, profile: dict[str, Any] | None) -> str:
    if is_shared_test_train_flow(inp) and not inp.runtime_strategy_override:
        if inp.external_base_url:
            return "external_url"
        if profile is not None and _bool(profile.get("supports_shared"), False):
            return "shared_runtime"
        return "external_url"

    if inp.runtime_strategy_override:
        return inp.runtime_strategy_override

    if inp.external_base_url:
        return "external_url"

    if not inp.requires_browser and inp.task_kind not in {"ui_flow", "browser", "e2e"}:
        return "none"

    if profile is None:
        return "none"

    supports_shared = _bool(profile.get("supports_shared"), False)
    supports_isolated = _bool(profile.get("supports_isolated"), False)
    mutating_policy = (_str(profile.get("mutating_flow_policy")) or "serialized").lower()

    if inp.mutating_flow and mutating_policy == "isolated" and supports_isolated:
        return "isolated_runtime"
    if supports_shared:
        return "shared_runtime"
    if supports_isolated:
        return "isolated_runtime"
    return "none"


def blocker_fingerprint(stage: str, code: str, signature: str) -> str:
    return f"{stage}|{code}|{signature.strip()}"


def log_blocker(
    inp: RuntimeInput,
    *,
    stage: str,
    blocker_code: str,
    category: str,
    summary: str,
    signature: str,
    retryable: bool,
    runtime_id: str | None,
    evidence_paths: list[str] | None = None,
) -> None:
    row = {
        "timestamp": utc_now_iso(),
        "task_identifier": inp.task_identifier,
        "worker_slot": inp.worker_slot,
        "worker_role": inp.worker_role,
        "stage": stage,
        "blocker_code": blocker_code,
        "category": category if category in BLOCKER_CATEGORIES else "unknown",
        "summary": summary,
        "signature": signature,
        "fingerprint": blocker_fingerprint(stage, blocker_code, signature),
        "retryable": bool(retryable),
        "runtime_id": runtime_id,
        "evidence_paths": evidence_paths or [],
        "source_tool": TOOL,
    }
    _append_jsonl(inp.blockers_path, row)


def load_registry(path: Path) -> dict[str, Any]:
    return _read_json(path, {"schema_version": "1.0", "updated_at": None, "instances": []})


def load_leases(path: Path) -> dict[str, Any]:
    return _read_json(path, {"schema_version": "1.0", "updated_at": None, "leases": []})


def _instances(registry: dict[str, Any]) -> list[dict[str, Any]]:
    raw = registry.get("instances")
    if not isinstance(raw, list):
        raw = []
        registry["instances"] = raw
    return [r for r in raw if isinstance(r, dict)]


def _leases(leases_state: dict[str, Any]) -> list[dict[str, Any]]:
    raw = leases_state.get("leases")
    if not isinstance(raw, list):
        raw = []
        leases_state["leases"] = raw
    return [l for l in raw if isinstance(l, dict)]


def ensure_shared_runtime(
    inp: RuntimeInput,
    profile: dict[str, Any],
    registry: dict[str, Any],
) -> dict[str, Any]:
    profile_id = _str(profile.get("profile_id")) or "default"
    instances = _instances(registry)

    for inst in instances:
        if inst.get("profile_id") != profile_id:
            continue
        if inst.get("mode") != "shared":
            continue
        status = _str(inst.get("status")) or "unknown"
        if status in {"starting", "healthy", "degraded"}:
            inst["updated_at"] = utc_now_iso()
            return inst

    runtime_id = f"rt-shared-{profile_id}"
    base_url = _str(profile.get("default_base_url")) or inp.external_base_url
    inst = {
        "runtime_id": runtime_id,
        "profile_id": profile_id,
        "mode": "shared",
        "owner": "optimus",
        "base_url": base_url,
        "status": "starting",
        "active_testers": [],
        "lease_policy": (_str(profile.get("mutating_flow_policy")) or "serialized").lower(),
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "last_healthcheck_at": None,
    }
    instances.append(inst)
    registry["instances"] = instances
    registry["updated_at"] = utc_now_iso()
    return inst


def create_or_get_isolated_runtime(
    inp: RuntimeInput,
    profile: dict[str, Any],
    registry: dict[str, Any],
) -> dict[str, Any]:
    profile_id = _str(profile.get("profile_id")) or "default"
    task = (_str(inp.task_identifier) or "task").replace("/", "-")
    slot = (_str(inp.worker_slot) or "slot").replace("/", "-")
    runtime_id = f"rt-iso-{profile_id}-{task.lower()}-{slot.lower()}"

    instances = _instances(registry)
    for inst in instances:
        if inst.get("runtime_id") == runtime_id:
            inst["updated_at"] = utc_now_iso()
            return inst

    inst = {
        "runtime_id": runtime_id,
        "profile_id": profile_id,
        "mode": "isolated",
        "owner": inp.worker_slot or "worker",
        "base_url": _str(profile.get("default_base_url")),
        "status": "starting",
        "active_testers": [inp.worker_slot] if inp.worker_slot else [],
        "lease_policy": "isolated",
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "last_healthcheck_at": None,
    }
    instances.append(inst)
    registry["instances"] = instances
    registry["updated_at"] = utc_now_iso()
    return inst


def ensure_external_runtime(
    inp: RuntimeInput,
    registry: dict[str, Any],
    *,
    profile_id: str | None,
    base_url: str,
) -> dict[str, Any]:
    profile_segment = profile_id or "external"
    url_digest = hashlib.sha256(base_url.encode("utf-8")).hexdigest()[:8]
    runtime_id = f"rt-external-{profile_segment}-{url_digest}"
    instances = _instances(registry)
    for inst in instances:
        if _str(inst.get("runtime_id")) != runtime_id:
            continue
        inst["base_url"] = base_url
        inst["updated_at"] = utc_now_iso()
        return inst

    inst = {
        "runtime_id": runtime_id,
        "profile_id": profile_segment,
        "mode": "external",
        "owner": "optimus",
        "base_url": base_url,
        "status": "healthy",
        "active_testers": [],
        "lease_policy": "serialized",
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "last_healthcheck_at": None,
    }
    instances.append(inst)
    registry["instances"] = instances
    registry["updated_at"] = utc_now_iso()
    return inst


def _attach_worker_to_runtime(runtime: dict[str, Any], worker_slot: str | None) -> None:
    if not worker_slot:
        return
    active = runtime.get("active_testers")
    if not isinstance(active, list):
        active = []
        runtime["active_testers"] = active
    if worker_slot not in active:
        active.append(worker_slot)


def allocate_lease(
    inp: RuntimeInput,
    *,
    runtime: dict[str, Any],
    profile: dict[str, Any],
    leases_state: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    leases = _leases(leases_state)
    runtime_id = _str(runtime.get("runtime_id"))
    if not runtime_id:
        return None, None

    # Reuse existing active lease for same task+slot when present.
    for lease in leases:
        if lease.get("runtime_id") != runtime_id:
            continue
        if lease.get("status") != "active":
            continue
        if lease.get("task_identifier") == inp.task_identifier and lease.get("worker_slot") == inp.worker_slot:
            lease["updated_at"] = utc_now_iso()
            leases_state["updated_at"] = utc_now_iso()
            return lease, None

    policy = (_str(profile.get("mutating_flow_policy")) or "serialized").lower()
    active = [l for l in leases if l.get("runtime_id") == runtime_id and l.get("status") == "active"]

    if not inp.mutating_flow:
        lease = {
            "lease_id": str(uuid.uuid4()),
            "runtime_id": runtime_id,
            "task_identifier": inp.task_identifier,
            "worker_slot": inp.worker_slot,
            "worker_role": inp.worker_role,
            "mode": "shared_read",
            "status": "active",
            "created_at": utc_now_iso(),
            "updated_at": utc_now_iso(),
        }
        leases.append(lease)
        leases_state["leases"] = leases
        leases_state["updated_at"] = utc_now_iso()
        return lease, None

    if policy == "serialized":
        blockers = [l for l in active if l.get("mode") == "exclusive"]
        if blockers:
            return None, {
                "code": "serialized_runtime_locked",
                "message": "shared runtime has active exclusive mutating lease",
                "stage": "lease",
            }
        lease = {
            "lease_id": str(uuid.uuid4()),
            "runtime_id": runtime_id,
            "task_identifier": inp.task_identifier,
            "worker_slot": inp.worker_slot,
            "worker_role": inp.worker_role,
            "mode": "exclusive",
            "status": "active",
            "created_at": utc_now_iso(),
            "updated_at": utc_now_iso(),
        }
        leases.append(lease)
        leases_state["leases"] = leases
        leases_state["updated_at"] = utc_now_iso()
        return lease, None

    if policy == "account_pool":
        accounts = profile.get("test_accounts")
        if not isinstance(accounts, list) or not accounts:
            return None, {
                "code": "account_pool_missing",
                "message": "mutating account_pool policy requires non-empty test_accounts",
                "stage": "lease",
            }
        used_accounts = {l.get("test_account") for l in active if l.get("test_account")}
        free = [a for a in accounts if isinstance(a, str) and a not in used_accounts]
        if not free:
            return None, {
                "code": "account_pool_exhausted",
                "message": "no free test account available for shared mutating flow",
                "stage": "lease",
            }
        lease = {
            "lease_id": str(uuid.uuid4()),
            "runtime_id": runtime_id,
            "task_identifier": inp.task_identifier,
            "worker_slot": inp.worker_slot,
            "worker_role": inp.worker_role,
            "mode": "account",
            "test_account": free[0],
            "status": "active",
            "created_at": utc_now_iso(),
            "updated_at": utc_now_iso(),
        }
        leases.append(lease)
        leases_state["leases"] = leases
        leases_state["updated_at"] = utc_now_iso()
        return lease, None

    if policy == "isolated":
        return None, {
            "code": "isolated_policy_requires_isolated_strategy",
            "message": "profile mutating policy is isolated; use isolated runtime strategy",
            "stage": "lease",
        }

    return None, {
        "code": "unknown_mutating_policy",
        "message": f"unknown mutating_flow_policy: {policy}",
        "stage": "lease",
    }


def resolve(inp: RuntimeInput) -> dict[str, Any]:
    profiles = load_profiles(inp.runtime_profiles_path)
    profile = choose_profile(inp, profiles)
    strategy = resolve_strategy(inp, profile)
    shared_train_mode = is_shared_test_train_flow(inp)
    pipeline = load_test_train_pipeline(inp, required=inp.test_train_mode != "off")

    registry = load_registry(inp.runtime_registry_path)
    leases_state = load_leases(inp.runtime_leases_path)
    stale_ttl_sec = max(
        60,
        _int(
            ((pipeline.get("lease_policy") or {}).get("stale_ttl_sec") if isinstance(pipeline.get("lease_policy"), dict) else 900),
            900,
        ),
    )
    released_lease_ids = _sweep_stale_leases(leases_state, stale_ttl_sec)

    runtime: dict[str, Any] | None = None
    lease: dict[str, Any] | None = None
    blocked: dict[str, Any] | None = None
    tester_must_not_start_runtime = False
    base_url = inp.external_base_url

    if shared_train_mode and strategy not in {"external_url", "shared_runtime"}:
        blocked = {
            "code": "test_train_local_runtime_denied",
            "message": "test-train mode requires tester runtime_strategy=external_url|shared_runtime",
            "stage": "resolve",
        }

    if blocked:
        pass
    elif strategy == "none":
        pass
    elif strategy == "external_url":
        tester_must_not_start_runtime = True
        if not base_url and profile is not None:
            base_url = _str(profile.get("default_base_url"))
        if not base_url:
            blocked = {
                "code": "external_url_missing",
                "message": "external_url strategy requires base_url",
                "stage": "resolve",
            }
        else:
            runtime = ensure_external_runtime(
                inp,
                registry,
                profile_id=_str(profile.get("profile_id")) if profile else None,
                base_url=base_url,
            )
            pseudo_profile = profile or {"mutating_flow_policy": "serialized", "test_accounts": []}
            lease, blocked = allocate_lease(inp, runtime=runtime, profile=pseudo_profile, leases_state=leases_state)
            _attach_worker_to_runtime(runtime, inp.worker_slot)
    elif strategy in {"shared_runtime", "isolated_runtime"} and profile is None:
        blocked = {
            "code": "runtime_profile_missing",
            "message": "runtime strategy requires at least one runtime profile",
            "stage": "resolve",
        }
    elif strategy == "shared_runtime":
        assert profile is not None
        runtime = ensure_shared_runtime(inp, profile, registry)
        base_url = base_url or _str(runtime.get("base_url")) or _str(profile.get("default_base_url"))
        tester_must_not_start_runtime = True
        lease, blocked = allocate_lease(inp, runtime=runtime, profile=profile, leases_state=leases_state)
        _attach_worker_to_runtime(runtime, inp.worker_slot)
    elif strategy == "isolated_runtime":
        assert profile is not None
        runtime = create_or_get_isolated_runtime(inp, profile, registry)
        base_url = _str(runtime.get("base_url")) or _str(profile.get("default_base_url"))
        tester_must_not_start_runtime = False
        _attach_worker_to_runtime(runtime, inp.worker_slot)
    else:
        blocked = {
            "code": "strategy_invalid",
            "message": f"invalid strategy: {strategy}",
            "stage": "resolve",
        }

    if shared_train_mode:
        tester_must_not_start_runtime = True
        if blocked is None and not base_url:
            blocked = {
                "code": "shared_runtime_url_missing",
                "message": "test-train mode requires runtime profile default_base_url or explicit external_base_url",
                "stage": "resolve",
            }

    registry["updated_at"] = utc_now_iso()
    leases_state["updated_at"] = utc_now_iso()
    _write_json(inp.runtime_registry_path, registry)
    _write_json(inp.runtime_leases_path, leases_state)

    if released_lease_ids:
        _append_runtime_action(
            inp,
            action="lease_sweep",
            result="ok",
            runtime_id=_str(runtime.get("runtime_id") if runtime else None),
            fingerprint="lease_sweep",
            details={"released_lease_ids": released_lease_ids, "stale_ttl_sec": stale_ttl_sec},
        )

    if blocked:
        signature = f"{blocked.get('code')}:{blocked.get('message', '')}"
        log_blocker(
            inp,
            stage=str(blocked.get("stage") or "resolve"),
            blocker_code=str(blocked.get("code") or "runtime_blocked"),
            category="test-train" if shared_train_mode else "runtime",
            summary=str(blocked.get("message") or "runtime coordination blocked"),
            signature=signature,
            retryable=True,
            runtime_id=_str(runtime.get("runtime_id") if runtime else None),
        )
        _append_runtime_action(
            inp,
            action="resolve",
            result="blocked",
            runtime_id=_str(runtime.get("runtime_id") if runtime else None),
            fingerprint=str(blocked.get("code") or "runtime_blocked"),
            details={"blocked": blocked, "runtime_strategy": strategy},
        )
        return {
            "ok": False,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "schema_version": SCHEMA_VERSION,
            "action": "resolve",
            "runtime_strategy": strategy,
            "blocked": blocked,
            "dispatch_payload": None,
        }

    runtime_profile_id = (
        _str(profile.get("profile_id"))
        if profile
        else _str(runtime.get("profile_id") if runtime else None)
    )
    runtime_id = _str(runtime.get("runtime_id") if runtime else None)
    runtime_lease_id = _str(lease.get("lease_id") if lease else None)
    dispatch_payload = {
        "runtime_strategy": strategy,
        "runtime_profile_id": runtime_profile_id,
        "runtime_id": runtime_id,
        "runtime_base_url": base_url,
        "runtime_lease_id": runtime_lease_id,
        "base_url": base_url,
        "lease_id": runtime_lease_id,
        "tester_must_not_start_runtime": tester_must_not_start_runtime,
        "test_train_mode": inp.test_train_mode,
    }
    _append_runtime_action(
        inp,
        action="resolve",
        result="ok",
        runtime_id=runtime_id,
        fingerprint=str(strategy),
        details={"dispatch_payload": dispatch_payload, "released_lease_ids": released_lease_ids},
    )
    return {
        "ok": True,
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "schema_version": SCHEMA_VERSION,
        "action": "resolve",
        "runtime_strategy": strategy,
        "dispatch_payload": dispatch_payload,
    }


def _pipeline_lock_ttl(pipeline: dict[str, Any]) -> int:
    locking = pipeline.get("locking") if isinstance(pipeline.get("locking"), dict) else {}
    return max(60, _int((locking or {}).get("lock_ttl_sec"), 1800))


def _runtime_status_ok(status: str) -> bool:
    return status in {"healthy", "degraded"}


def bootstrap(inp: RuntimeInput) -> dict[str, Any]:
    pipeline = load_test_train_pipeline(inp, required=inp.test_train_mode != "off")
    ttl_sec = _pipeline_lock_ttl(pipeline)
    lock_path = _acquire_lock(inp, "bootstrap", ttl_sec)
    try:
        inp.runtime_locks_dir.mkdir(parents=True, exist_ok=True)
        inp.runtime_health_path.parent.mkdir(parents=True, exist_ok=True)
        inp.runtime_action_log_path.parent.mkdir(parents=True, exist_ok=True)
        inp.runtime_repair_tasks_path.parent.mkdir(parents=True, exist_ok=True)

        required_passes = max(
            1,
            _int(
                ((pipeline.get("health") or {}).get("require_consecutive_passes") if isinstance(pipeline.get("health"), dict) else 2),
                2,
            ),
        )
        if not inp.runtime_health_path.exists():
            _write_runtime_health(inp, _runtime_health_default(inp, required_passes))
        if not inp.runtime_repair_tasks_path.exists():
            _write_repair_tasks(inp, _read_repair_tasks(inp))

        leases_state = load_leases(inp.runtime_leases_path)
        stale_ttl_sec = max(
            60,
            _int(
                ((pipeline.get("lease_policy") or {}).get("stale_ttl_sec") if isinstance(pipeline.get("lease_policy"), dict) else 900),
                900,
            ),
        )
        released = _sweep_stale_leases(leases_state, stale_ttl_sec)
        if released:
            _write_json(inp.runtime_leases_path, leases_state)
            _append_runtime_action(
                inp,
                action="lease_sweep",
                result="ok",
                runtime_id=None,
                fingerprint="lease_sweep",
                details={"released_lease_ids": released, "stale_ttl_sec": stale_ttl_sec},
            )
        _append_runtime_action(
            inp,
            action="bootstrap",
            result="ok",
            runtime_id=None,
            fingerprint="bootstrap",
            details={
                "pipeline_path": str(inp.test_train_pipeline_path),
                "runtime_health_path": str(inp.runtime_health_path),
                "runtime_repair_tasks_path": str(inp.runtime_repair_tasks_path),
            },
        )
        return {
            "ok": True,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "schema_version": SCHEMA_VERSION,
            "action": "bootstrap",
            "released_lease_ids": released,
            "pipeline_path": str(inp.test_train_pipeline_path),
        }
    finally:
        _release_lock(lock_path)


def _resolve_runtime_for_start_stop(
    inp: RuntimeInput,
    profile: dict[str, Any] | None,
    registry: dict[str, Any],
) -> dict[str, Any] | None:
    if inp.runtime_id:
        for inst in _instances(registry):
            if _str(inst.get("runtime_id")) == inp.runtime_id:
                return inst
    if profile is None:
        return None
    mode = (_str(profile.get("default_runtime_mode")) or "shared").lower()
    if mode == "isolated":
        return create_or_get_isolated_runtime(inp, profile, registry)
    return ensure_shared_runtime(inp, profile, registry)


def start_runtime(inp: RuntimeInput) -> dict[str, Any]:
    pipeline = load_test_train_pipeline(inp, required=inp.test_train_mode != "off")
    lock_path = _acquire_lock(inp, f"start-{inp.runtime_id or inp.runtime_profile_id or 'default'}", _pipeline_lock_ttl(pipeline))
    try:
        profiles = load_profiles(inp.runtime_profiles_path)
        profile = choose_profile(inp, profiles)
        if profile is None:
            raise ToolError("config_error", "runtime profile required for start action", stage="profiles")
        start_cmd_raw = _str(profile.get("start_cmd"))
        if not start_cmd_raw:
            raise ToolError("config_error", "runtime profile start_cmd is required", stage="config")
        start_cmd = _expand_env_placeholders(start_cmd_raw, inp.repo_root)
        timeout_sec = max(1, _int(profile.get("start_timeout_sec"), 600))
        proc = _execute_shell(start_cmd, cwd=inp.repo_root, timeout_sec=timeout_sec)

        registry = load_registry(inp.runtime_registry_path)
        runtime = _resolve_runtime_for_start_stop(inp, profile, registry)
        runtime_id = _str(runtime.get("runtime_id")) if isinstance(runtime, dict) else inp.runtime_id
        if isinstance(runtime, dict):
            runtime["status"] = "healthy" if proc.returncode == 0 else "failed"
            runtime["updated_at"] = utc_now_iso()
            runtime["last_healthcheck_at"] = utc_now_iso()
            registry["updated_at"] = utc_now_iso()
            _write_json(inp.runtime_registry_path, registry)

        if proc.returncode != 0:
            log_blocker(
                inp,
                stage="start",
                blocker_code="runtime_start_failed",
                category="runtime",
                summary=f"runtime start command failed for {runtime_id or 'unknown-runtime'}",
                signature=f"exit_code={proc.returncode}",
                retryable=True,
                runtime_id=runtime_id,
            )
            _append_runtime_action(
                inp,
                action="start",
                result="failed",
                runtime_id=runtime_id,
                fingerprint=f"runtime_start_failed:{proc.returncode}",
                details={"exit_code": proc.returncode, "stderr": (proc.stderr or "").strip()[:1000]},
            )
            return {
                "ok": False,
                "tool": TOOL,
                "tool_version": TOOL_VERSION,
                "schema_version": SCHEMA_VERSION,
                "action": "start",
                "runtime_id": runtime_id,
                "exit_code": proc.returncode,
                "stderr": (proc.stderr or "").strip(),
                "stdout": (proc.stdout or "").strip(),
            }

        _append_runtime_action(
            inp,
            action="start",
            result="ok",
            runtime_id=runtime_id,
            fingerprint="runtime_start_ok",
            details={"exit_code": 0},
        )
        return {
            "ok": True,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "schema_version": SCHEMA_VERSION,
            "action": "start",
            "runtime_id": runtime_id,
        }
    finally:
        _release_lock(lock_path)


def _evaluate_health(inp: RuntimeInput) -> dict[str, Any]:
    pipeline = load_test_train_pipeline(inp, required=inp.test_train_mode != "off")
    health_cfg = pipeline.get("health") if isinstance(pipeline.get("health"), dict) else {}
    required_passes = max(1, _int((health_cfg or {}).get("require_consecutive_passes"), 2))
    profile_required = _bool((health_cfg or {}).get("profile_check_required"), True)
    mode_policy = pipeline.get("mode_policy") if isinstance(pipeline.get("mode_policy"), dict) else {}
    mode_cfg = mode_policy.get(inp.test_train_mode) if isinstance(mode_policy, dict) else {}
    hard_gate = _bool((mode_cfg or {}).get("hard_gate"), inp.test_train_mode != "off")

    previous = _read_runtime_health(inp, required_passes)
    registry = load_registry(inp.runtime_registry_path)
    pipeline_ok, pipeline_checks, pipeline_failure_fp = _pipeline_health_checks(inp, pipeline)
    profile_ok, profile_checks = _profile_health_checks(inp, registry, runtime_id=inp.runtime_id)

    both_sources_pass = pipeline_ok and ((not profile_required) or profile_ok)
    consecutive = int(previous.get("consecutive_passes", 0) or 0)
    consecutive = consecutive + 1 if both_sources_pass else 0

    if both_sources_pass and consecutive >= required_passes:
        gate_state = "healthy"
    elif both_sources_pass:
        gate_state = "degraded"
    elif hard_gate:
        gate_state = "blocked"
    else:
        gate_state = "degraded"

    failure_fp = None
    if not both_sources_pass:
        if pipeline_failure_fp:
            failure_fp = pipeline_failure_fp
        elif profile_required and not profile_ok:
            failure_fp = "profile|runtime|unhealthy"
        else:
            failure_fp = "health|unknown|failed"

    health_payload = {
        "schema_version": SCHEMA_VERSION,
        "updated_at": utc_now_iso(),
        "test_train_mode": inp.test_train_mode,
        "gate_state": gate_state,
        "consecutive_passes": consecutive,
        "required_passes": required_passes,
        "pipeline_checks": pipeline_checks,
        "profile_checks": profile_checks,
        "both_sources_pass": both_sources_pass,
        "last_failure_fingerprint": failure_fp,
        "next_heal_allowed_at": previous.get("next_heal_allowed_at"),
    }
    _write_runtime_health(inp, health_payload)
    _append_runtime_action(
        inp,
        action="health",
        result="ok" if _runtime_status_ok(gate_state) else "failed",
        runtime_id=inp.runtime_id,
        fingerprint=failure_fp,
        details={
            "gate_state": gate_state,
            "both_sources_pass": both_sources_pass,
            "consecutive_passes": consecutive,
            "required_passes": required_passes,
        },
    )
    return {
        "ok": True,
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "schema_version": SCHEMA_VERSION,
        "action": "health",
        "healthy": gate_state == "healthy",
        "gate_state": gate_state,
        "runtime_health_path": str(inp.runtime_health_path),
        "both_sources_pass": both_sources_pass,
        "consecutive_passes": consecutive,
        "required_passes": required_passes,
        "last_failure_fingerprint": failure_fp,
    }


def health_runtime(inp: RuntimeInput) -> dict[str, Any]:
    pipeline = load_test_train_pipeline(inp, required=inp.test_train_mode != "off")
    lock_path = _acquire_lock(inp, f"health-{inp.runtime_id or inp.runtime_profile_id or 'default'}", _pipeline_lock_ttl(pipeline))
    try:
        leases_state = load_leases(inp.runtime_leases_path)
        stale_ttl_sec = max(
            60,
            _int(
                ((pipeline.get("lease_policy") or {}).get("stale_ttl_sec") if isinstance(pipeline.get("lease_policy"), dict) else 900),
                900,
            ),
        )
        released = _sweep_stale_leases(leases_state, stale_ttl_sec)
        if released:
            _write_json(inp.runtime_leases_path, leases_state)
            _append_runtime_action(
                inp,
                action="lease_sweep",
                result="ok",
                runtime_id=inp.runtime_id,
                fingerprint="lease_sweep",
                details={"released_lease_ids": released, "stale_ttl_sec": stale_ttl_sec},
            )
        out = _evaluate_health(inp)
        out["released_lease_ids"] = released
        return out
    finally:
        _release_lock(lock_path)


def stop_runtime(inp: RuntimeInput) -> dict[str, Any]:
    pipeline = load_test_train_pipeline(inp, required=False)
    lock_path = _acquire_lock(inp, f"stop-{inp.runtime_id or inp.runtime_profile_id or 'default'}", _pipeline_lock_ttl(pipeline))
    try:
        profiles = load_profiles(inp.runtime_profiles_path)
        profile = choose_profile(inp, profiles)
        if profile is None:
            raise ToolError("config_error", "runtime profile required for stop action", stage="profiles")
        stop_cmd_raw = _str(profile.get("stop_cmd"))
        if not stop_cmd_raw:
            raise ToolError("config_error", "runtime profile stop_cmd is required", stage="config")
        stop_cmd = _expand_env_placeholders(stop_cmd_raw, inp.repo_root)
        timeout_sec = max(1, _int(profile.get("stop_timeout_sec"), 180))
        proc = _execute_shell(stop_cmd, cwd=inp.repo_root, timeout_sec=timeout_sec)

        registry = load_registry(inp.runtime_registry_path)
        runtime = _resolve_runtime_for_start_stop(inp, profile, registry)
        runtime_id = _str(runtime.get("runtime_id")) if isinstance(runtime, dict) else inp.runtime_id
        if isinstance(runtime, dict):
            runtime["status"] = "stopped" if proc.returncode == 0 else "failed"
            runtime["updated_at"] = utc_now_iso()
            registry["updated_at"] = utc_now_iso()
            _write_json(inp.runtime_registry_path, registry)

        _append_runtime_action(
            inp,
            action="stop",
            result="ok" if proc.returncode == 0 else "failed",
            runtime_id=runtime_id,
            fingerprint=f"runtime_stop:{proc.returncode}",
            details={"exit_code": proc.returncode},
        )
        return {
            "ok": proc.returncode == 0,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "schema_version": SCHEMA_VERSION,
            "action": "stop",
            "runtime_id": runtime_id,
            "exit_code": proc.returncode,
        }
    finally:
        _release_lock(lock_path)


def _create_repair_task(
    inp: RuntimeInput,
    *,
    fingerprint: str,
    health: dict[str, Any],
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    payload = _read_repair_tasks(inp)
    tasks_raw = payload.get("tasks")
    tasks = tasks_raw if isinstance(tasks_raw, list) else []
    repair_id = _repair_task_id(fingerprint, now)
    for item in tasks:
        if isinstance(item, dict) and _str(item.get("repair_id")) == repair_id:
            return item

    task = {
        "repair_id": repair_id,
        "dedup_key": fingerprint,
        "created_at": utc_now_iso(),
        "status": "queued",
        "priority": "high",
        "lane": "runtime-infra",
        "max_reserved_dev_slots": 1,
        "quality_flow": "dev_only",
        "gate_state": _str(health.get("gate_state")) or "blocked",
        "test_train_mode": inp.test_train_mode,
        "runtime_id": inp.runtime_id,
    }
    tasks.append(task)
    payload["tasks"] = tasks
    _write_repair_tasks(inp, payload)
    return task


def repair_runtime(inp: RuntimeInput) -> dict[str, Any]:
    pipeline = load_test_train_pipeline(inp, required=inp.test_train_mode != "off")
    lock_path = _acquire_lock(inp, f"repair-{inp.runtime_id or inp.runtime_profile_id or 'default'}", _pipeline_lock_ttl(pipeline))
    try:
        health_cfg = pipeline.get("health") if isinstance(pipeline.get("health"), dict) else {}
        required_passes = max(1, _int((health_cfg or {}).get("require_consecutive_passes"), 2))
        health_payload = _read_runtime_health(inp, required_passes)
        gate_state = _str(health_payload.get("gate_state")) or "blocked"
        force_fingerprint = _str(inp.repair_force_fingerprint)
        force_delegate = inp.repair_force_delegate
        if gate_state == "healthy" and not force_fingerprint and not force_delegate:
            return {
                "ok": True,
                "tool": TOOL,
                "tool_version": TOOL_VERSION,
                "schema_version": SCHEMA_VERSION,
                "action": "repair",
                "result": "not_needed",
                "gate_state": gate_state,
            }

        repair_cfg = pipeline.get("repair") if isinstance(pipeline.get("repair"), dict) else {}
        commands_raw = repair_cfg.get("self_heal_commands")
        self_heal_commands = [c for c in commands_raw if isinstance(c, str) and c.strip()] if isinstance(commands_raw, list) else []
        cooldown_sec = max(1, _int((repair_cfg or {}).get("cooldown_sec"), 300))
        max_attempts = max(1, _int((repair_cfg or {}).get("max_attempts_per_fingerprint_window"), 1))
        create_dev_task = _bool((repair_cfg or {}).get("create_dev_task"), True)
        create_blocker = _bool((repair_cfg or {}).get("create_blocker"), True)

        fingerprint = force_fingerprint or _str(health_payload.get("last_failure_fingerprint")) or "runtime|repair|unknown"
        next_heal_allowed_at = _parse_iso_dt(health_payload.get("next_heal_allowed_at"))
        now = datetime.now(timezone.utc)
        cooldown_blocked = next_heal_allowed_at is not None and now < next_heal_allowed_at

        attempted_recent = _count_heal_attempts(inp, fingerprint)

        can_attempt = (not force_delegate) and (not cooldown_blocked) and attempted_recent < max_attempts and bool(self_heal_commands)
        heal_results: list[dict[str, Any]] = []
        if can_attempt:
            for cmd_template in self_heal_commands:
                cmd = _expand_env_placeholders(cmd_template, inp.repo_root)
                proc = _execute_shell(cmd, cwd=inp.repo_root, timeout_sec=max(1, _int(repair_cfg.get("heal_timeout_sec"), 600)))
                heal_results.append(
                    {
                        "command_template": cmd_template,
                        "exit_code": proc.returncode,
                        "stdout": (proc.stdout or "").strip()[:1000],
                        "stderr": (proc.stderr or "").strip()[:1000],
                    }
                )
                if proc.returncode != 0:
                    break
            health_payload["next_heal_allowed_at"] = (
                now + timedelta(seconds=cooldown_sec)
            ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            _write_runtime_health(inp, health_payload)
            _append_runtime_action(
                inp,
                action="heal",
                result="ok" if all(item["exit_code"] == 0 for item in heal_results) else "failed",
                runtime_id=inp.runtime_id,
                fingerprint=fingerprint,
                details={"commands": [item["command_template"] for item in heal_results]},
            )
            health_after = _evaluate_health(inp)
            if health_after.get("gate_state") == "healthy" and not force_delegate:
                return {
                    "ok": True,
                    "tool": TOOL,
                    "tool_version": TOOL_VERSION,
                    "schema_version": SCHEMA_VERSION,
                    "action": "repair",
                    "result": "healed",
                    "heal_results": heal_results,
                    "health": health_after,
                }

        repair_task = None
        if create_dev_task:
            repair_task = _create_repair_task(inp, fingerprint=fingerprint, health=health_payload)
        if create_blocker:
            log_blocker(
                inp,
                stage="repair",
                blocker_code="runtime_repair_required",
                category="test-train" if inp.test_train_mode != "off" else "runtime",
                summary="runtime health gate requires developer remediation",
                signature=fingerprint,
                retryable=True,
                runtime_id=inp.runtime_id,
                evidence_paths=[str(inp.runtime_health_path)],
            )
        _append_runtime_action(
            inp,
            action="repair",
            result="blocked",
            runtime_id=inp.runtime_id,
            fingerprint=fingerprint,
            details={
                "cooldown_blocked": cooldown_blocked,
                "attempted_recent": attempted_recent,
                "max_attempts_per_fingerprint_window": max_attempts,
                "repair_task_id": _str(repair_task.get("repair_id")) if isinstance(repair_task, dict) else None,
                "force_delegate": force_delegate,
                "force_fingerprint": force_fingerprint,
            },
        )
        return {
            "ok": False,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "schema_version": SCHEMA_VERSION,
            "action": "repair",
            "result": "delegated",
            "repair_task": repair_task,
            "gate_state": _str(health_payload.get("gate_state")) or "blocked",
            "next_heal_allowed_at": health_payload.get("next_heal_allowed_at"),
        }
    finally:
        _release_lock(lock_path)


def release_lease(inp: RuntimeInput) -> dict[str, Any]:
    if not inp.lease_id:
        raise ToolError("input_error", "lease_id is required for release_lease", stage="input")

    leases_state = load_leases(inp.runtime_leases_path)
    leases = _leases(leases_state)
    found = None
    for lease in leases:
        if lease.get("lease_id") == inp.lease_id:
            found = lease
            break

    if found is None:
        _append_runtime_action(
            inp,
            action="release_lease",
            result="failed",
            runtime_id=None,
            fingerprint="lease_not_found",
            details={"lease_id": inp.lease_id},
        )
        return {
            "ok": False,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "schema_version": SCHEMA_VERSION,
            "action": "release_lease",
            "error": "lease_not_found",
            "lease_id": inp.lease_id,
        }

    found["status"] = "released"
    found["released_at"] = utc_now_iso()
    found["updated_at"] = utc_now_iso()
    leases_state["updated_at"] = utc_now_iso()
    _write_json(inp.runtime_leases_path, leases_state)

    runtime_id = _str(found.get("runtime_id"))
    if runtime_id and inp.worker_slot:
        registry = load_registry(inp.runtime_registry_path)
        instances = _instances(registry)
        for inst in instances:
            if inst.get("runtime_id") != runtime_id:
                continue
            active = inst.get("active_testers")
            if isinstance(active, list) and inp.worker_slot in active:
                inst["active_testers"] = [s for s in active if s != inp.worker_slot]
                inst["updated_at"] = utc_now_iso()
                break
        registry["updated_at"] = utc_now_iso()
        _write_json(inp.runtime_registry_path, registry)

    _append_runtime_action(
        inp,
        action="release_lease",
        result="ok",
        runtime_id=runtime_id,
        fingerprint="release_lease",
        details={"lease_id": inp.lease_id},
    )

    return {
        "ok": True,
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "schema_version": SCHEMA_VERSION,
        "action": "release_lease",
        "lease_id": inp.lease_id,
    }


def upsert_runtime(inp: RuntimeInput) -> dict[str, Any]:
    if not inp.runtime_id:
        raise ToolError("input_error", "runtime_id is required for upsert_runtime", stage="input")
    if not inp.requested_status:
        raise ToolError("input_error", "requested_status is required for upsert_runtime", stage="input")

    registry = load_registry(inp.runtime_registry_path)
    instances = _instances(registry)

    found = None
    for inst in instances:
        if inst.get("runtime_id") == inp.runtime_id:
            found = inst
            break

    if found is None:
        found = {
            "runtime_id": inp.runtime_id,
            "profile_id": inp.runtime_profile_id,
            "mode": "custom",
            "owner": "optimus",
            "base_url": inp.external_base_url,
            "active_testers": [],
            "lease_policy": "unknown",
            "created_at": utc_now_iso(),
        }
        instances.append(found)

    found["status"] = inp.requested_status
    found["updated_at"] = utc_now_iso()
    registry["instances"] = instances
    registry["updated_at"] = utc_now_iso()
    _write_json(inp.runtime_registry_path, registry)

    if inp.requested_status == "failed":
        log_blocker(
            inp,
            stage="runtime",
            blocker_code="runtime_failed",
            category="runtime",
            summary=f"runtime marked failed: {inp.runtime_id}",
            signature=f"runtime_failed:{inp.runtime_id}",
            retryable=True,
            runtime_id=inp.runtime_id,
        )

    return {
        "ok": True,
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "schema_version": SCHEMA_VERSION,
        "action": "upsert_runtime",
        "runtime_id": inp.runtime_id,
        "requested_status": inp.requested_status,
    }


def log_blocker_action(inp: RuntimeInput) -> dict[str, Any]:
    stage = _str(inp.blocker_stage)
    code = _str(inp.blocker_code)
    category = _str(inp.blocker_category) or "unknown"
    summary = _str(inp.blocker_summary)
    signature = _str(inp.blocker_signature)

    if not stage:
        raise ToolError("input_error", "blocker_stage is required for log_blocker", stage="input")
    if not code:
        raise ToolError("input_error", "blocker_code is required for log_blocker", stage="input")
    if not summary:
        raise ToolError("input_error", "blocker_summary is required for log_blocker", stage="input")
    if not signature:
        signature = summary

    runtime_id = inp.runtime_id
    if not runtime_id:
        registry = load_registry(inp.runtime_registry_path)
        instances = _instances(registry)
        for inst in instances:
            if inp.runtime_profile_id and _str(inst.get("profile_id")) != inp.runtime_profile_id:
                continue
            status = (_str(inst.get("status")) or "").lower()
            mode = (_str(inst.get("mode")) or "").lower()
            if mode in {"shared", "isolated"} and status in {"healthy", "degraded", "starting"}:
                runtime_id = _str(inst.get("runtime_id"))
                break

    log_blocker(
        inp,
        stage=stage,
        blocker_code=code,
        category=category,
        summary=summary,
        signature=signature,
        retryable=inp.blocker_retryable,
        runtime_id=runtime_id,
        evidence_paths=inp.blocker_evidence_paths,
    )

    return {
        "ok": True,
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "schema_version": SCHEMA_VERSION,
        "action": "log_blocker",
        "blocker": {
            "stage": stage,
            "blocker_code": code,
            "category": category if category in BLOCKER_CATEGORIES else "unknown",
            "summary": summary,
            "signature": signature,
            "fingerprint": blocker_fingerprint(stage, code, signature),
            "retryable": inp.blocker_retryable,
            "runtime_id": runtime_id,
            "evidence_paths": inp.blocker_evidence_paths,
        },
        "blockers_path": str(inp.blockers_path),
    }


def _playbook_hint(entry: dict[str, Any]) -> str:
    code = (_str(entry.get("blocker_code")) or "").lower()
    summary = (_str(entry.get("latest_summary")) or "").lower()
    fingerprint = (_str(entry.get("fingerprint")) or "").lower()

    if "emfile" in summary or "emfile" in fingerprint:
        return "Use shared preview runtime; avoid per-worker dev/watch startup; reduce watcher scope."
    if code in {"serialized_runtime_locked", "account_pool_exhausted"}:
        return "Use runtime leases and queue mutating tester flows; avoid parallel account collisions."
    if "env" in code or "credential" in summary:
        return "Track required workstation assets and symlink non-git env/auth files during preparation."
    if code.startswith("test_") or "playwright" in summary:
        return "Keep tester runs against single orchestrator-managed runtime and isolate only when required."
    return "Add/extend skill-level guardrails for this blocker class and codify remediation in runbooks."


def refresh_blocker_index(inp: RuntimeInput) -> dict[str, Any]:
    entries: dict[str, dict[str, Any]] = {}
    malformed_rows = 0
    total_rows = 0

    if inp.blockers_path.exists():
        with inp.blockers_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                text = line.strip()
                if not text:
                    continue
                total_rows += 1
                try:
                    row = json.loads(text)
                except json.JSONDecodeError:
                    malformed_rows += 1
                    continue
                if not isinstance(row, dict):
                    malformed_rows += 1
                    continue

                stage = _str(row.get("stage")) or "unknown"
                blocker_code = _str(row.get("blocker_code")) or "unknown_blocker"
                summary = _str(row.get("summary")) or "unspecified blocker"
                signature = _str(row.get("signature")) or summary
                fingerprint = _str(row.get("fingerprint")) or blocker_fingerprint(stage, blocker_code, signature)
                category = _str(row.get("category")) or "unknown"
                if category not in BLOCKER_CATEGORIES:
                    category = "unknown"

                timestamp = _to_iso(row.get("timestamp")) or utc_now_iso()
                task_identifier = _str(row.get("task_identifier"))

                current = entries.get(fingerprint)
                if current is None:
                    current = {
                        "fingerprint": fingerprint,
                        "first_seen": timestamp,
                        "last_seen": timestamp,
                        "count": 0,
                        "category": category,
                        "blocker_code": blocker_code,
                        "stages": [],
                        "tasks": [],
                        "latest_summary": summary,
                        "latest_signature": signature,
                        "recommended_playbook": None,
                    }
                    entries[fingerprint] = current

                current["count"] += 1
                if timestamp < current["first_seen"]:
                    current["first_seen"] = timestamp
                if timestamp >= current["last_seen"]:
                    current["last_seen"] = timestamp
                    current["latest_summary"] = summary
                    current["latest_signature"] = signature

                stages = current.get("stages")
                if isinstance(stages, list) and stage not in stages:
                    stages.append(stage)
                tasks = current.get("tasks")
                if isinstance(tasks, list) and task_identifier and task_identifier not in tasks:
                    tasks.append(task_identifier)

    ordered = sorted(entries.values(), key=lambda item: (-int(item.get("count", 0)), str(item.get("last_seen") or ""), item.get("fingerprint", "")))

    for entry in ordered:
        entry["recommended_playbook"] = _playbook_hint(entry)

    index_payload = {
        "schema_version": "1.0",
        "updated_at": utc_now_iso(),
        "source": {
            "blockers_path": str(inp.blockers_path),
            "rows_processed": total_rows,
            "rows_malformed": malformed_rows,
        },
        "entries": ordered[: inp.blocker_index_max_entries],
    }
    _write_json(inp.blocker_index_path, index_payload)

    recurring = [e for e in ordered if int(e.get("count", 0)) >= inp.blocker_index_min_count]
    report_lines = [
        "# Blocker Adaptation Candidates",
        "",
        f"Generated: {index_payload['updated_at']}",
        "",
        f"Source: `{inp.blockers_path}`",
        f"Rows processed: {total_rows}",
        f"Malformed rows skipped: {malformed_rows}",
        "",
    ]

    if not recurring:
        report_lines.append("No recurring blockers above the configured threshold.")
    else:
        for idx, entry in enumerate(recurring[: inp.blocker_index_max_entries], start=1):
            report_lines.extend(
                [
                    f"## {idx}. {entry['blocker_code']} ({entry['count']} occurrences)",
                    f"- Fingerprint: `{entry['fingerprint']}`",
                    f"- Category: `{entry['category']}`",
                    f"- First seen: {entry['first_seen']}",
                    f"- Last seen: {entry['last_seen']}",
                    f"- Stages: {', '.join(entry.get('stages', [])) or 'unknown'}",
                    f"- Tasks: {', '.join(entry.get('tasks', [])[:8]) or 'n/a'}",
                    f"- Latest summary: {entry['latest_summary']}",
                    f"- Suggested adaptation: {entry['recommended_playbook']}",
                    "",
                ]
            )

    inp.blocker_adaptation_report_path.parent.mkdir(parents=True, exist_ok=True)
    inp.blocker_adaptation_report_path.write_text("\n".join(report_lines).rstrip() + "\n", encoding="utf-8")

    return {
        "ok": True,
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "schema_version": SCHEMA_VERSION,
        "action": "refresh_blocker_index",
        "blockers_path": str(inp.blockers_path),
        "blocker_index_path": str(inp.blocker_index_path),
        "adaptation_report_path": str(inp.blocker_adaptation_report_path),
        "rows_processed": total_rows,
        "rows_malformed": malformed_rows,
        "entries": len(index_payload["entries"]),
        "recurring_entries": len(recurring),
    }


def run(inp: RuntimeInput) -> dict[str, Any]:
    if inp.action == "bootstrap":
        return bootstrap(inp)
    if inp.action == "start":
        return start_runtime(inp)
    if inp.action == "health":
        return health_runtime(inp)
    if inp.action == "stop":
        return stop_runtime(inp)
    if inp.action == "repair":
        return repair_runtime(inp)
    if inp.action == "resolve":
        return resolve(inp)
    if inp.action == "release_lease":
        return release_lease(inp)
    if inp.action == "upsert_runtime":
        return upsert_runtime(inp)
    if inp.action == "log_blocker":
        return log_blocker_action(inp)
    if inp.action == "refresh_blocker_index":
        return refresh_blocker_index(inp)
    raise ToolError("input_error", f"unsupported action: {inp.action}", stage="input")


def print_json(payload: dict[str, Any], pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=False))
    else:
        print(json.dumps(payload, sort_keys=False, separators=(",", ":")))


def main() -> int:
    args = parse_args()
    try:
        data = parse_json_input(args.input_json)
        inp = build_input(data)
        result = run(inp)
    except ToolError as exc:
        result = {
            "ok": False,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "schema_version": SCHEMA_VERSION,
            "error": {"code": exc.code, "message": exc.message, "stage": exc.stage},
        }
    except Exception as exc:  # noqa: BLE001
        result = {
            "ok": False,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "schema_version": SCHEMA_VERSION,
            "error": {"code": "runtime_error", "message": str(exc), "stage": "runtime"},
        }

    print_json(result, args.json_pretty)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
