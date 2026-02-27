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


def _task_state_from_plan(plan_packets: dict[str, Any]) -> dict[str, Any]:
    tasks = plan_packets.get("tasks") if isinstance(plan_packets.get("tasks"), list) else []
    out_tasks: list[dict[str, Any]] = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = _as_str(task.get("task_id"))
        if not task_id:
            continue
        req_ids = []
        for rid in task.get("requirement_ids", []):
            rid_text = _as_str(rid)
            if rid_text:
                req_ids.append(rid_text)
        out_tasks.append(
            {
                "task_id": task_id,
                "requirement_ids": req_ids,
                "status": "queued",
                "owner_slot": None,
                "attempts": {"dev": 0, "test": 0, "review": 0},
                "evidence": {
                    "dev_ready_evidence_ref": None,
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


def _compute_plan_check(mission: str | None, scope: str | None, requirements: list[dict[str, Any]], tasks: list[dict[str, Any]]) -> dict[str, Any]:
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

    plan_id = f"plan-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    plan_packets = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "plan_id": plan_id,
        "phase": "phase-1",
        "requirements": [item.get("id") for item in requirements if isinstance(item, dict)],
        "tasks": tasks,
        "depends_on": [],
        "must_haves": sorted({crit for task in tasks for crit in task.get("must_haves", []) if isinstance(crit, str)}),
        "verify_commands": sorted({cmd for task in tasks for cmd in task.get("verify_commands", []) if isinstance(cmd, str)}),
    }

    plan_check = _compute_plan_check(mission, scope, requirements, tasks)

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

    state["updated_at"] = utc_now_iso()
    state["plan_id"] = plan_id
    state["plan_ready"] = bool(plan_check["passed"])
    state["build_ready"] = bool(plan_check["passed"])

    state_md_lines = [
        "# STATE",
        "",
        "- baseline_ready: true",
        f"- plan_ready: {str(bool(plan_check['passed'])).lower()}",
        f"- build_ready: {str(bool(plan_check['passed'])).lower()}",
        f"- plan_id: {plan_id}",
        "",
        "## Plan Checks",
    ]
    for check in plan_check["checks"]:
        state_md_lines.append(f"- {check['id']}: {str(bool(check['passed'])).lower()}")

    _atomic_write_json(_repo_path(repo_root, PLAN_PACKETS_JSON), plan_packets)
    _atomic_write_json(_repo_path(repo_root, PLAN_CHECK_JSON), plan_check)
    _atomic_write_json(_repo_path(repo_root, TASK_EXECUTION_STATE_JSON), _task_state_from_plan(plan_packets))
    _write_text(_repo_path(repo_root, TEST_CONTRACT_MD), "\n".join(test_contract_md_lines) + "\n")
    _write_text(_repo_path(repo_root, PLAYWRIGHT_UAT_MD), "\n".join(uat_md_lines) + "\n")
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
            str(_repo_path(repo_root, TEST_CONTRACT_MD)),
            str(_repo_path(repo_root, PLAYWRIGHT_UAT_MD)),
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
            "strict_done_checks": {},
            "current_task_pointer": None,
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
    payload.setdefault("handoff_log_offset", 0)
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


def _detect_blocker_fingerprint(repo_root: Path) -> str:
    runtime_health_path = repo_root / "reports" / "optimus-prime" / "runtime" / "RUNTIME_HEALTH.json"
    if runtime_health_path.exists():
        payload = _read_json(runtime_health_path)
        if isinstance(payload, dict):
            fp = _as_str(payload.get("last_failure_fingerprint"))
            if fp:
                return fp

    blockers_path = repo_root / "reports" / "optimus-prime" / "BLOCKERS.jsonl"
    if blockers_path.exists():
        lines = blockers_path.read_text(encoding="utf-8").splitlines()
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
    if strategy in {"self_heal", "runtime_repair"}:
        script = repo_root / "skills" / "runtime-coordinator" / "scripts" / "runtime_coordinator.py"
        if not script.exists():
            return {"action": strategy, "status": "skipped", "reason": "runtime-coordinator missing"}
        payload = {
            "repo_root": str(repo_root),
            "action": "repair",
            "test_train_mode": "final-stage",
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


def _apply_handoff_updates(repo_root: Path, task_state: dict[str, Any], build_state: dict[str, Any]) -> None:
    handoff_path = repo_root / "reports" / "optimus-prime" / "HANDOFF_LOG.jsonl"
    rows = _read_jsonl(handoff_path)
    offset = int(build_state.get("handoff_log_offset", 0))
    if offset < 0:
        offset = 0
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
            evidence = {"dev_ready_evidence_ref": None, "verify_results": [], "uat_results": []}
            task["evidence"] = evidence
        verify_results = evidence.get("verify_results")
        if not isinstance(verify_results, list):
            verify_results = []
            evidence["verify_results"] = verify_results
        uat_results = evidence.get("uat_results")
        if not isinstance(uat_results, list):
            uat_results = []
            evidence["uat_results"] = uat_results

        row_verify = row.get("verify_results")
        if isinstance(row_verify, list):
            verify_results.extend(item for item in row_verify if isinstance(item, (str, dict)))
        row_uat = row.get("uat_results")
        if isinstance(row_uat, list):
            uat_results.extend(item for item in row_uat if isinstance(item, (str, dict)))

        dev_ready = _as_str(row.get("dev_ready_evidence_ref"))
        if dev_ready:
            evidence["dev_ready_evidence_ref"] = dev_ready

        result = (_as_str(row.get("result")) or _as_str(row.get("status")) or _as_str(row.get("phase")) or "").lower()
        if result in {"blocked", "failed", "error"}:
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
            continue
        if result in {"dev_done", "developer_done", "implementation_done"}:
            task["status"] = "dev_done"
            task["owner_slot"] = None
            continue
        if result in {"test_done", "tests_passed", "qa_done"}:
            task["status"] = "test_done"
            task["owner_slot"] = None
            continue
        if result in {"review_done", "accepted", "merged"}:
            task["status"] = "review_done"
            task["owner_slot"] = None
            continue
        if result in {"dev_in_progress", "developer_started"}:
            task["status"] = "dev_in_progress"
            continue
        if result in {"test_in_progress", "tester_started"}:
            task["status"] = "test_in_progress"
            continue
        if result in {"review_in_progress", "reviewer_started"}:
            task["status"] = "review_in_progress"
            continue
    build_state["handoff_log_offset"] = len(rows)


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
    dev_ready_ref = _as_str((task.get("evidence") or {}).get("dev_ready_evidence_ref"))
    if not dev_ready_ref:
        dev_ready_ref = f"reports/optimus-prime/planning/evidence/{task_id}/DEV_READY.json"
        task.setdefault("evidence", {})["dev_ready_evidence_ref"] = dev_ready_ref

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
        "dev_ready_evidence_ref": dev_ready_ref,
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


def _dispatch_next_task(req: OpRequest, plan_packets: dict[str, Any], task_state: dict[str, Any], build_state: dict[str, Any]) -> dict[str, Any]:
    task_map = _task_by_id(task_state)
    plan_map = _plan_task_map(plan_packets)
    ordered_ids = [task_id for task_id in plan_map.keys()]
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
        build_state["current_task_pointer"] = task_id
        if status == "queued":
            return _dispatch_task_packet(req, task, plan_task, "dev", plan_id)
        if status == "dev_done":
            dev_ref = _as_str((task.get("evidence") or {}).get("dev_ready_evidence_ref"))
            if not dev_ref:
                return {
                    "ok": False,
                    "status": "blocked",
                    "task_id": task_id,
                    "reason": "missing_dev_ready_evidence_ref",
                }
            return _dispatch_task_packet(req, task, plan_task, "test", plan_id)
        if status == "test_done":
            return _dispatch_task_packet(req, task, plan_task, "review", plan_id)
    return {"ok": True, "status": "noop", "reason": "no dispatchable tasks"}


def _apply_directives(
    req: OpRequest,
    directives: list[dict[str, Any]],
    build_state: dict[str, Any],
    plan_packets: dict[str, Any],
    task_state: dict[str, Any],
) -> list[dict[str, Any]]:
    outcomes: list[dict[str, Any]] = []
    runtime_script = req.repo_root / "skills" / "runtime-coordinator" / "scripts" / "runtime_coordinator.py"
    train_script = req.repo_root / "skills" / "test-train-manager" / "scripts" / "test_train_manager.py"
    runtime_defaults = {
        "repo_root": str(req.repo_root),
        "test_train_mode": "final-stage",
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
        "test_train_mode": "final-stage",
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
            outcomes.append({"directive_type": directive_type, "status": "applied", "result": result})
            continue
        if directive_type in train_directives:
            payload = dict(train_defaults)
            payload.update(args)
            if directive_type == "hold_test_promotion":
                payload["action"] = "evaluate_promotion_gate"
            result = _run_tool_json(train_script, payload, req.repo_root)
            outcomes.append({"directive_type": directive_type, "status": "applied", "result": result})
            continue
        if directive_type == "review_dispatch_queue":
            result = _dispatch_next_task(req, plan_packets, task_state, build_state)
            outcomes.append({"directive_type": directive_type, "status": "applied", "result": result})
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
            outcomes.append({"directive_type": directive_type, "status": "applied", "result": {"hard_gated": True}})
            continue
        outcomes.append({"directive_type": directive_type, "status": "skipped", "reason": "unsupported directive"})
    return outcomes


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
        dev_ref = _as_str(evidence.get("dev_ready_evidence_ref"))
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
    checks = {
        "tasks_exist_in_task_state": task_ids_present,
        "all_tasks_review_done": all_review_done,
        "all_tasks_have_dev_ready_evidence_ref": all_dev_refs,
        "verify_commands_passed": verify_commands_passed,
        "uat_matrix_passed": uat_passed,
        "final_state_authorized": final_state_ok,
    }
    checks["all_passed"] = all(checks.values())
    checks["missing_verify_commands"] = sorted(required_verify_cmds - passed_verify_cmds)
    checks["missing_uat_requirement_ids"] = sorted(required_uat_ids - passed_uat_reqs)
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
        parsed = _read_json(state_path)
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
        parsed_plan = _read_json(plan_packets_path)
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
        parsed_task = _read_json(task_state_path)
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
        item.get("code") in {"plan_not_ready", "task_state_invalid", "task_state_plan_mismatch", "plan_packets_invalid"}
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
    build_state = _load_build_state(build_state_path)
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

    cycles = 0
    history: list[dict[str, Any]] = build_state.get("history", [])
    if not isinstance(history, list):
        history = []
    try:
        while req.max_build_cycles is None or cycles < req.max_build_cycles:
            cycles += 1
            build_state["last_cycle"] = int(build_state.get("last_cycle", 0)) + 1
            build_state["updated_at"] = utc_now_iso()
            _apply_handoff_updates(req.repo_root, task_state, build_state)

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
                    next_action="Remove operator stop marker and rerun /op-build to resume.",
                    data={"terminal_reason": "operator_stop"},
                )

            cycle_result = _run_controller_cycle(req)
            last_cycle_number = int(cycle_result.get("last_cycle_number") or 0)
            events_path_raw = _as_str(cycle_result.get("events_path"))
            directives: list[dict[str, Any]] = []
            if events_path_raw and last_cycle_number > 0:
                directives = _extract_cycle_directives(Path(events_path_raw).expanduser().resolve(), last_cycle_number)
            directive_outcomes = _apply_directives(req, directives, build_state, plan_packets, task_state)
            if not any(item.get("directive_type") == "review_dispatch_queue" for item in directive_outcomes):
                directive_outcomes.append(
                    {
                        "directive_type": "auto_dispatch",
                        "status": "applied",
                        "result": _dispatch_next_task(req, plan_packets, task_state, build_state),
                    }
                )
            _apply_handoff_updates(req.repo_root, task_state, build_state)

            history.append(
                {
                    "timestamp": utc_now_iso(),
                    "cycle_result": cycle_result,
                    "directives": directive_outcomes,
                    "strategy": build_state.get("current_strategy"),
                }
            )
            build_state["history"] = history[-200:]

            terminal_reason = _as_str(cycle_result.get("terminal_reason"))
            if cycle_result.get("ok") is True and terminal_reason:
                if terminal_reason == "project_done":
                    final_state_path = req.repo_root / "reports" / "optimus-prime" / "controller" / "FINAL_STATE.json"
                    verification = _verify_final_state(req, final_state_path)
                    strict_checks = _evaluate_strict_done(req.repo_root, plan_packets, task_state, verification)
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

            fingerprint = _detect_blocker_fingerprint(req.repo_root)
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
            summary="Build loop executed bounded cycles without terminal resolution; resume with /op-build.",
            warnings=warnings,
            errors=[
                {
                    "code": "max_build_cycles_reached",
                    "message": "bounded build run reached max_build_cycles before terminal condition",
                    "stage": "build_loop",
                }
            ],
            state_ref=str(build_state_path),
            next_action="Rerun /op-build to continue from BUILD_STATE.json.",
            data={
                "cycles_executed": cycles,
                "current_strategy": build_state.get("current_strategy"),
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

    default_sleep = 5 if command == "op-build" else 0
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
    raise OpError(
        "input_error",
        "unsupported command; expected one of: " + ", ".join(sorted(SUPPORTED_COMMANDS)),
        stage="input",
    )


def run_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    req = parse_request(payload)
    return execute_request(req)
