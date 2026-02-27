#!/usr/bin/env python3
"""Runtime strategy/lease coordinator plus blocker index aggregation."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TOOL = "runtime-coordinator"
TOOL_VERSION = "0.3.0"
SCHEMA_VERSION = "1.0"

STRATEGIES = {"none", "external_url", "shared_runtime", "isolated_runtime"}
ACTIONS = {"resolve", "release_lease", "upsert_runtime", "refresh_blocker_index", "log_blocker"}
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
        shared_test_base_url=_str(payload.get("shared_test_base_url")),
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
    if is_shared_test_train_flow(inp) and inp.shared_test_base_url and not inp.runtime_strategy_override:
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

    registry = load_registry(inp.runtime_registry_path)
    leases_state = load_leases(inp.runtime_leases_path)

    runtime: dict[str, Any] | None = None
    lease: dict[str, Any] | None = None
    blocked: dict[str, Any] | None = None
    tester_must_not_start_runtime = False
    base_url = inp.shared_test_base_url or inp.external_base_url

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
                "code": "shared_test_base_url_missing",
                "message": "test-train mode requires shared_test_base_url or runtime profile default_base_url",
                "stage": "resolve",
            }

    registry["updated_at"] = utc_now_iso()
    leases_state["updated_at"] = utc_now_iso()
    _write_json(inp.runtime_registry_path, registry)
    _write_json(inp.runtime_leases_path, leases_state)

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

    dispatch_payload = {
        "runtime_strategy": strategy,
        "runtime_profile_id": _str(profile.get("profile_id")) if profile else None,
        "runtime_id": _str(runtime.get("runtime_id") if runtime else None),
        "base_url": base_url,
        "lease_id": _str(lease.get("lease_id") if lease else None),
        "tester_must_not_start_runtime": tester_must_not_start_runtime,
        "test_train_mode": inp.test_train_mode,
    }

    return {
        "ok": True,
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "schema_version": SCHEMA_VERSION,
        "action": "resolve",
        "runtime_strategy": strategy,
        "dispatch_payload": dispatch_payload,
    }


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
