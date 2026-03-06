#!/usr/bin/env python3
"""OP Simple build loop runtime."""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"

TERMINATE_FILE_NAME = "terminate_run.json"
SIMPLE_ROOT = Path(".op-simple")
CURRENT_DIR = SIMPLE_ROOT / "current"
HISTORY_DIR = SIMPLE_ROOT / "history"

CYCLE_COUNTER_FILE = CURRENT_DIR / "cycle_counter.json"
RUN_LOCK_FILE = CURRENT_DIR / "run_lock.json"
MANAGER_CALL_LOG_FILE = CURRENT_DIR / "manager_call_log.jsonl"
DISPATCH_LAUNCH_LOG_FILE = CURRENT_DIR / "dispatch_launch_log.jsonl"
INITIALIZE_STATE_FILE = CURRENT_DIR / "initialize_state.json"
BOSS_EVIDENCE_FILE = CURRENT_DIR / "boss_evidence.json"

ARTIFACT_FILES = {
    "cycle_manager_decision": CURRENT_DIR / "cycle_manager_decision.json",
    "profile_snapshot": CURRENT_DIR / "profile_snapshot.json",
    "production_line_register": CURRENT_DIR / "production_line_register.json",
    "worker_packets": CURRENT_DIR / "worker_packets.json",
    "plan_packets": CURRENT_DIR / "plan_packets.json",
    "task_execution_state": CURRENT_DIR / "task_execution_state.json",
    "worker_registry": CURRENT_DIR / "worker_registry.json",
    "dispatch_registry": CURRENT_DIR / "dispatch_registry.json",
    "cycle_summary": CURRENT_DIR / "cycle_summary.json",
    "watchdog_state": CURRENT_DIR / "watchdog_state.json",
    "watchdog_exit_signal": CURRENT_DIR / "watchdog_exit_signal.json",
    "workstation_prep": CURRENT_DIR / "workstation_prep.json",
}

MANAGER_TIMEOUT_SECONDS = {
    "cycle-manager": 300,
    "profile-manager": 420,
    "BOSS": 720,
    "watchdog": 120,
    "summary": 120,
}

WATCHDOG_IDLE_THRESHOLD = 10
WAIT_HEARTBEAT_SECONDS = 300
WAIT_RESCAN_SECONDS = 900


@dataclass
class ManagerResult:
    manager: str
    status: str
    timeout: bool
    returncode: int | None
    started_at: str
    finished_at: str
    duration_seconds: float
    stdout_path: str | None = None
    stderr_path: str | None = None
    message: str | None = None


@dataclass
class RunConfig:
    repo_root: Path
    sleep_minutes: float
    max_build_cycles: int | None
    max_parallel_workers: int
    dry_run: bool


class SimpleBuildError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=False) + "\n"


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(_json_dumps(payload), encoding="utf-8")
    tmp.replace(path)


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=False) + "\n")


def _read_json(path: Path, *, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    return payload


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return


def _is_pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _git_text(repo_root: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=str(repo_root), capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return ""
    return (proc.stdout or "").strip()


def _default_initialize_state(repo_root: Path, max_parallel_workers: int) -> dict[str, Any]:
    monitored_branch = _git_text(repo_root, "branch", "--show-current") or "main"
    return {
        "schema_version": SCHEMA_VERSION,
        "updated_at": utc_now_iso(),
        "monitored_branch": monitored_branch,
        "workflow": {
            "max_parallel_workers": max_parallel_workers,
        },
    }


def _ensure_initialize_state(cfg: RunConfig) -> dict[str, Any]:
    state = _read_json(cfg.repo_root / INITIALIZE_STATE_FILE, default={})
    if not isinstance(state, dict) or not state:
        state = _default_initialize_state(cfg.repo_root, cfg.max_parallel_workers)
    workflow = state.get("workflow") if isinstance(state.get("workflow"), dict) else {}
    if not isinstance(workflow.get("max_parallel_workers"), int) or int(workflow.get("max_parallel_workers")) <= 0:
        workflow["max_parallel_workers"] = cfg.max_parallel_workers
    state["workflow"] = workflow
    if not isinstance(state.get("monitored_branch"), str) or not str(state.get("monitored_branch")).strip():
        state["monitored_branch"] = _git_text(cfg.repo_root, "branch", "--show-current") or "main"
    state["updated_at"] = utc_now_iso()
    state["schema_version"] = SCHEMA_VERSION
    _atomic_write_json(cfg.repo_root / INITIALIZE_STATE_FILE, state)
    return state


def _ensure_workstation_prep(cfg: RunConfig) -> dict[str, Any]:
    target = cfg.repo_root / ARTIFACT_FILES["workstation_prep"]
    payload = _read_json(target, default={})
    if isinstance(payload, dict) and isinstance(payload.get("workstations"), list) and payload.get("workstations"):
        return payload

    current_branch = _git_text(cfg.repo_root, "branch", "--show-current") or "main"
    current_sha = _git_text(cfg.repo_root, "rev-parse", "HEAD") or ""
    rows = []
    for idx in range(1, 11):
        rows.append(
            {
                "workstation_id": f"workstation-{idx}",
                "branch": current_branch,
                "worktree": str((cfg.repo_root / f"workstation-{idx}").resolve()),
                "prepared_at": utc_now_iso(),
                "status": "prepared",
                "preparation_notes": "initialize baseline",
                "git_head_sha": current_sha,
            }
        )

    out = {
        "schema_version": SCHEMA_VERSION,
        "prepared_at": utc_now_iso(),
        "workstations": rows,
    }
    _atomic_write_json(target, out)
    return out


def _ensure_default_artifacts(cfg: RunConfig) -> None:
    defaults: dict[str, Any] = {
        "cycle_manager_decision": {
            "schema_version": SCHEMA_VERSION,
            "cycle_number": 0,
            "decision": "proceed",
            "reason_code": "default_bootstrap",
            "message": "default bootstrap decision",
            "worker_registry_ready": True,
        },
        "profile_snapshot": {
            "schema_version": SCHEMA_VERSION,
            "updated_at": utc_now_iso(),
            "profiles": [],
        },
        "production_line_register": {
            "schema_version": SCHEMA_VERSION,
            "updated_at": utc_now_iso(),
            "assignments": [],
        },
        "worker_packets": {
            "schema_version": SCHEMA_VERSION,
            "updated_at": utc_now_iso(),
            "packets": [],
        },
        "plan_packets": {
            "schema_version": SCHEMA_VERSION,
            "updated_at": utc_now_iso(),
            "phase": "multi-phase",
            "phases": [],
            "requirements": [],
            "tasks": [],
        },
        "task_execution_state": {
            "schema_version": SCHEMA_VERSION,
            "updated_at": utc_now_iso(),
            "tasks": [],
        },
        "worker_registry": {
            "schema_version": SCHEMA_VERSION,
            "updated_at": utc_now_iso(),
            "workers": [],
        },
        "dispatch_registry": {
            "schema_version": SCHEMA_VERSION,
            "updated_at": utc_now_iso(),
            "events": [],
        },
        "cycle_summary": {
            "schema_version": SCHEMA_VERSION,
            "cycle_number": 0,
            "manager_statuses": {},
            "task_counts": {"pending": 0, "in_progress": 0, "done": 0, "blocked": 0},
            "dispatch_counts": {"attempted": 0, "launched": 0, "launch_failed": 0, "unknown": 0},
            "project_done": False,
            "insurmountable_blocker": False,
            "termination": {},
            "stop_reason": "",
            "notes": "",
        },
        "watchdog_state": {
            "schema_version": SCHEMA_VERSION,
            "cycle_number": 0,
            "monitored_branch": "main",
            "last_commit_sha": "",
            "last_commit_seen_cycle": 0,
            "idle_cycles": 0,
            "threshold_cycles": WATCHDOG_IDLE_THRESHOLD,
        },
    }

    for key, rel in ARTIFACT_FILES.items():
        if key in {"watchdog_exit_signal", "workstation_prep"}:
            continue
        abs_path = cfg.repo_root / rel
        if abs_path.exists():
            continue
        payload = defaults.get(key, {"schema_version": SCHEMA_VERSION, "updated_at": utc_now_iso()})
        _atomic_write_json(abs_path, payload)


def _artifact_path_map(cfg: RunConfig) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, rel in ARTIFACT_FILES.items():
        out[key] = str((cfg.repo_root / rel).resolve())
    out["dispatch_launch_log"] = str((cfg.repo_root / DISPATCH_LAUNCH_LOG_FILE).resolve())
    out["manager_call_log"] = str((cfg.repo_root / MANAGER_CALL_LOG_FILE).resolve())
    out["boss_evidence"] = str((cfg.repo_root / BOSS_EVIDENCE_FILE).resolve())
    out["terminate_file"] = str((cfg.repo_root / TERMINATE_FILE_NAME).resolve())
    return out


def _manager_prompt_template_path(cfg: RunConfig, manager_name: str) -> Path:
    base = cfg.repo_root / "scripts" / "op_simple" / "prompts" / "managers"
    slug = manager_name.lower().replace(" ", "-")
    return base / f"{slug}.md"


def _load_prompt_template(cfg: RunConfig, manager_name: str) -> str:
    path = _manager_prompt_template_path(cfg, manager_name)
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _ensure_history_cycle_dir(cfg: RunConfig, cycle_number: int) -> Path:
    path = cfg.repo_root / HISTORY_DIR / f"cycle-{cycle_number:06d}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _append_manager_log(cfg: RunConfig, row: dict[str, Any]) -> None:
    _append_jsonl(cfg.repo_root / MANAGER_CALL_LOG_FILE, row)


def _codex_exec_prompt(
    cfg: RunConfig,
    manager_name: str,
    cycle_number: int,
    timeout_seconds: int,
    prompt_text: str,
) -> ManagerResult:
    started_at = utc_now_iso()
    start_time = time.monotonic()
    cycle_dir = _ensure_history_cycle_dir(cfg, cycle_number)
    safe_name = manager_name.lower().replace(" ", "-")
    stdout_path = cycle_dir / f"manager-{safe_name}.stdout.log"
    stderr_path = cycle_dir / f"manager-{safe_name}.stderr.log"
    last_message_path = cycle_dir / f"manager-{safe_name}.last_message.txt"

    cmd = [
        "codex",
        "exec",
        "--dangerously-bypass-approvals-and-sandbox",
        "--full-auto",
        "--cd",
        str(cfg.repo_root),
        "--output-last-message",
        str(last_message_path),
        "-",
    ]

    try:
        completed = subprocess.run(
            cmd,
            cwd=str(cfg.repo_root),
            input=prompt_text,
            text=True,
            capture_output=True,
            timeout=max(1, int(timeout_seconds)),
            check=False,
        )
        stdout_path.write_text(completed.stdout or "", encoding="utf-8")
        stderr_path.write_text(completed.stderr or "", encoding="utf-8")
        finished_at = utc_now_iso()
        return ManagerResult(
            manager=manager_name,
            status="ok" if completed.returncode == 0 else "failed",
            timeout=False,
            returncode=int(completed.returncode),
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=round(time.monotonic() - start_time, 3),
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
            message=None if completed.returncode == 0 else "codex exec returned non-zero",
        )
    except subprocess.TimeoutExpired:
        finished_at = utc_now_iso()
        return ManagerResult(
            manager=manager_name,
            status="timeout",
            timeout=True,
            returncode=None,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=round(time.monotonic() - start_time, 3),
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
            message="manager call timed out",
        )
    except FileNotFoundError:
        finished_at = utc_now_iso()
        return ManagerResult(
            manager=manager_name,
            status="failed",
            timeout=False,
            returncode=None,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=round(time.monotonic() - start_time, 3),
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
            message="codex binary not found",
        )


def _profile_rows_from_disk() -> list[dict[str, Any]]:
    root = Path.home()
    rows: list[dict[str, Any]] = []
    try:
        entries = sorted(root.iterdir(), key=lambda path: path.name)
    except OSError:
        return rows

    for entry in entries:
        if not entry.is_dir() or not entry.name.startswith(".codex"):
            continue
        auth_path = entry / "auth.json"
        if not auth_path.exists():
            continue
        alias = "codex" if entry.name == ".codex" else entry.name.lstrip(".")
        rows.append(
            {
                "alias": alias,
                "codex_home": str(entry.resolve()),
                "window_5h_remaining_pct": 100.0,
                "window_week_remaining_pct": 100.0,
                "hard_gated": False,
                "soft_gated": False,
                "reset_at": None,
            }
        )
    return rows


def _write_cycle_manager_stub(cfg: RunConfig, cycle_number: int) -> None:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "cycle_number": cycle_number,
        "decision": "proceed",
        "reason_code": "dry_run_default",
        "message": "dry run proceeds",
        "worker_registry_ready": True,
    }
    _atomic_write_json(cfg.repo_root / ARTIFACT_FILES["cycle_manager_decision"], payload)


def _write_profile_manager_stub(cfg: RunConfig) -> None:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "updated_at": utc_now_iso(),
        "profiles": _profile_rows_from_disk(),
    }
    _atomic_write_json(cfg.repo_root / ARTIFACT_FILES["profile_snapshot"], payload)


def _write_boss_stub(cfg: RunConfig, cycle_number: int) -> None:
    worker_registry = _read_json(cfg.repo_root / ARTIFACT_FILES["worker_registry"], default={})
    workers = worker_registry.get("workers") if isinstance(worker_registry, dict) else None
    if not isinstance(workers, list):
        workers = []
    payloads: dict[str, Any] = {
        "production_line_register": {
            "schema_version": SCHEMA_VERSION,
            "updated_at": utc_now_iso(),
            "cycle_number": cycle_number,
            "assignments": [],
            "counts": {"assigned": 0, "unassigned": 0, "deferred": 0},
        },
        "worker_packets": {
            "schema_version": SCHEMA_VERSION,
            "updated_at": utc_now_iso(),
            "cycle_number": cycle_number,
            "packets": [],
        },
        "plan_packets": {
            "schema_version": SCHEMA_VERSION,
            "updated_at": utc_now_iso(),
            "cycle_number": cycle_number,
            "phase": "multi-phase",
            "phases": [],
            "requirements": [],
            "tasks": [],
        },
        "task_execution_state": {
            "schema_version": SCHEMA_VERSION,
            "updated_at": utc_now_iso(),
            "cycle_number": cycle_number,
            "tasks": [],
        },
        "worker_registry": {
            "schema_version": SCHEMA_VERSION,
            "updated_at": utc_now_iso(),
            "cycle_number": cycle_number,
            "workers": workers,
        },
        "cycle_summary": {
            "schema_version": SCHEMA_VERSION,
            "cycle_number": cycle_number,
            "manager_statuses": {},
            "task_counts": {"pending": 0, "in_progress": 0, "done": 0, "blocked": 0},
            "dispatch_counts": {"attempted": 0, "launched": 0, "launch_failed": 0, "unknown": 0},
            "project_done": False,
            "insurmountable_blocker": False,
            "termination": {},
            "stop_reason": "",
            "notes": "dry run summary",
        },
    }
    for key, payload in payloads.items():
        _atomic_write_json(cfg.repo_root / ARTIFACT_FILES[key], payload)


def _invoke_manager(
    cfg: RunConfig,
    *,
    manager_name: str,
    cycle_number: int,
    context: dict[str, Any],
    expected_artifacts: list[str],
) -> ManagerResult:
    if cfg.dry_run:
        if manager_name == "cycle-manager":
            _write_cycle_manager_stub(cfg, cycle_number)
        elif manager_name == "profile-manager":
            _write_profile_manager_stub(cfg)
        elif manager_name == "BOSS":
            _write_boss_stub(cfg, cycle_number)
        started = utc_now_iso()
        finished = utc_now_iso()
        result = ManagerResult(
            manager=manager_name,
            status="ok",
            timeout=False,
            returncode=0,
            started_at=started,
            finished_at=finished,
            duration_seconds=0.0,
            message="dry run manager stub",
        )
    else:
        template = _load_prompt_template(cfg, manager_name)
        path_map = _artifact_path_map(cfg)
        packet = {
            "schema_version": SCHEMA_VERSION,
            "manager": manager_name,
            "cycle_number": cycle_number,
            "context": context,
            "artifact_paths": path_map,
            "validator_paths": {
                "op_simple_schema_catalog": str((cfg.repo_root / "docs" / "plans" / "OP_SIMPLE_SCHEMA_CATALOG_V2.md").resolve()),
            },
            "required_outputs": [path_map[item] for item in expected_artifacts],
        }
        prompt_text = template.strip()
        if prompt_text:
            prompt_text += "\n\n"
        prompt_text += "Runtime packet (JSON):\n```json\n"
        prompt_text += json.dumps(packet, indent=2, sort_keys=False)
        prompt_text += "\n```\n"
        timeout = int(MANAGER_TIMEOUT_SECONDS.get(manager_name, 300))
        result = _codex_exec_prompt(cfg, manager_name, cycle_number, timeout, prompt_text)

    _append_manager_log(
        cfg,
        {
            "schema_version": SCHEMA_VERSION,
            "cycle_number": cycle_number,
            "manager": manager_name,
            "status": result.status,
            "timeout": result.timeout,
            "returncode": result.returncode,
            "started_at": result.started_at,
            "finished_at": result.finished_at,
            "duration_seconds": result.duration_seconds,
            "stdout_path": result.stdout_path,
            "stderr_path": result.stderr_path,
            "message": result.message,
        },
    )

    if result.status == "ok":
        missing = []
        for artifact_key in expected_artifacts:
            artifact_path = cfg.repo_root / ARTIFACT_FILES[artifact_key]
            if not artifact_path.exists():
                missing.append(artifact_key)
        if missing:
            result.status = "failed"
            result.message = "missing expected artifacts: " + ", ".join(sorted(missing))
    return result


def _read_cycle_decision(cfg: RunConfig) -> dict[str, Any]:
    payload = _read_json(cfg.repo_root / ARTIFACT_FILES["cycle_manager_decision"], default={})
    if not isinstance(payload, dict):
        return {}
    return payload


def _profiles_all_hard_gated(cfg: RunConfig) -> bool:
    payload = _read_json(cfg.repo_root / ARTIFACT_FILES["profile_snapshot"], default={})
    if not isinstance(payload, dict):
        return False
    rows = payload.get("profiles")
    if not isinstance(rows, list) or not rows:
        return False
    hard_values = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        hard_values.append(bool(row.get("hard_gated")))
    return bool(hard_values) and all(hard_values)


def _run_rate_gate_wait(cfg: RunConfig, cycle_number: int, warnings: list[dict[str, Any]]) -> None:
    if cfg.dry_run:
        return
    if not _profiles_all_hard_gated(cfg):
        return

    next_heartbeat = time.monotonic()
    next_rescan = time.monotonic()
    while _profiles_all_hard_gated(cfg):
        if (cfg.repo_root / TERMINATE_FILE_NAME).exists():
            warnings.append(
                {
                    "code": "rate_gate_wait_interrupted",
                    "message": "terminate signal detected during rate-gate wait",
                    "stage": "op-simple-build",
                }
            )
            return
        now = time.monotonic()
        if now >= next_heartbeat:
            _append_manager_log(
                cfg,
                {
                    "schema_version": SCHEMA_VERSION,
                    "cycle_number": cycle_number,
                    "manager": "rate-gate",
                    "status": "heartbeat",
                    "timeout": False,
                    "returncode": 0,
                    "started_at": utc_now_iso(),
                    "finished_at": utc_now_iso(),
                    "duration_seconds": 0,
                    "message": "still waiting for rate gates to clear",
                },
            )
            next_heartbeat = now + WAIT_HEARTBEAT_SECONDS
        if now >= next_rescan:
            profile_result = _invoke_manager(
                cfg,
                manager_name="profile-manager",
                cycle_number=cycle_number,
                context={"reason": "rate_wait_rescan"},
                expected_artifacts=["profile_snapshot"],
            )
            if profile_result.status != "ok":
                warnings.append(
                    {
                        "code": "profile_rescan_failed",
                        "message": profile_result.message or "profile-manager rescan failed",
                        "stage": "op-simple-build",
                    }
                )
            next_rescan = now + WAIT_RESCAN_SECONDS
        time.sleep(5)


def _resolve_dispatch_script(cfg: RunConfig) -> Path | None:
    codex_home = os.environ.get("CODEX_HOME")
    candidates: list[Path] = []
    if codex_home:
        candidates.append(Path(codex_home).expanduser() / "skills" / "thread-dispatch" / "scripts" / "dispatch_codex_run.py")
    candidates.append(Path.home() / ".codex" / "skills" / "thread-dispatch" / "scripts" / "dispatch_codex_run.py")
    candidates.append(cfg.repo_root / "skills" / "thread-dispatch" / "scripts" / "dispatch_codex_run.py")
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return None


def _profile_alias_to_home(cfg: RunConfig) -> dict[str, str]:
    payload = _read_json(cfg.repo_root / ARTIFACT_FILES["profile_snapshot"], default={})
    if not isinstance(payload, dict):
        return {}
    out: dict[str, str] = {}
    rows = payload.get("profiles")
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        alias = row.get("alias")
        home = row.get("codex_home")
        if isinstance(alias, str) and alias and isinstance(home, str) and home:
            out[alias] = home
    return out


def _load_worker_packets(cfg: RunConfig) -> list[dict[str, Any]]:
    payload = _read_json(cfg.repo_root / ARTIFACT_FILES["worker_packets"], default={})
    rows: list[dict[str, Any]] = []
    if isinstance(payload, list):
        rows = [row for row in payload if isinstance(row, dict)]
    elif isinstance(payload, dict):
        packets = payload.get("packets")
        if isinstance(packets, list):
            rows = [row for row in packets if isinstance(row, dict)]
    return rows


def _update_dispatch_registry(cfg: RunConfig, event_rows: list[dict[str, Any]]) -> None:
    path = cfg.repo_root / ARTIFACT_FILES["dispatch_registry"]
    payload = _read_json(path, default={})
    if not isinstance(payload, dict):
        payload = {}
    events = payload.get("events") if isinstance(payload.get("events"), list) else []
    events.extend(event_rows)
    payload["schema_version"] = SCHEMA_VERSION
    payload["updated_at"] = utc_now_iso()
    payload["events"] = events[-500:]
    _atomic_write_json(path, payload)


def _update_worker_registry_dispatch_state(cfg: RunConfig, event_rows: list[dict[str, Any]]) -> None:
    path = cfg.repo_root / ARTIFACT_FILES["worker_registry"]
    payload = _read_json(path, default={})
    if not isinstance(payload, dict):
        payload = {}

    workers = payload.get("workers")
    if not isinstance(workers, list):
        workers = []

    worker_index: dict[str, dict[str, Any]] = {}
    for row in workers:
        if not isinstance(row, dict):
            continue
        worker_id = row.get("worker_id")
        if isinstance(worker_id, str) and worker_id:
            worker_index[worker_id] = row

    latest_cycle = int(payload.get("cycle_number") or 0)
    for event in event_rows:
        if not isinstance(event, dict):
            continue
        worker_id = str(event.get("worker_id") or "").strip()
        if not worker_id:
            continue
        cycle_number = int(event.get("cycle_number") or 0)
        if cycle_number > latest_cycle:
            latest_cycle = cycle_number
        row = worker_index.get(worker_id)
        if row is None:
            row = {
                "worker_id": worker_id,
                "worktree": "",
                "branch": "",
                "status": "idle",
                "current_task_profile": None,
                "next_task_profile": None,
                "current_task_id": None,
                "current_packet_id": None,
                "pid": None,
                "thread_id": None,
                "last_update": utc_now_iso(),
            }
            workers.append(row)
            worker_index[worker_id] = row

        dispatch_status = str(event.get("status") or "").strip()
        if dispatch_status == "launched":
            row["status"] = "in_progress"
        elif dispatch_status == "launch_failed":
            row["status"] = "dispatch_failed"
        else:
            row["status"] = row.get("status") or "unknown"
        row["current_packet_id"] = event.get("packet_id")
        row["pid"] = event.get("pid")
        row["thread_id"] = event.get("thread_id")
        row["last_update"] = event.get("timestamp") or utc_now_iso()

    payload["schema_version"] = SCHEMA_VERSION
    payload["updated_at"] = utc_now_iso()
    payload["cycle_number"] = latest_cycle
    payload["workers"] = workers
    _atomic_write_json(path, payload)


def _active_worker_count(cfg: RunConfig) -> int:
    payload = _read_json(cfg.repo_root / ARTIFACT_FILES["worker_registry"], default={})
    if not isinstance(payload, dict):
        return 0
    workers = payload.get("workers")
    if not isinstance(workers, list):
        return 0
    active_statuses = {"in_progress", "dev_working", "testing", "reviewing"}
    active_count = 0
    for row in workers:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "").strip().lower()
        pid = row.get("pid")
        thread_id = row.get("thread_id")
        has_live_marker = pid not in {None, ""} or (isinstance(thread_id, str) and bool(thread_id.strip()))
        if status in active_statuses or has_live_marker:
            active_count += 1
    return active_count


def _dispatch_packets(cfg: RunConfig, cycle_number: int) -> dict[str, int]:
    counters = {"attempted": 0, "launched": 0, "launch_failed": 0, "unknown": 0}
    packets = _load_worker_packets(cfg)
    if not packets:
        return counters

    script = _resolve_dispatch_script(cfg)
    alias_to_home = _profile_alias_to_home(cfg)
    event_rows: list[dict[str, Any]] = []
    active_count = _active_worker_count(cfg)

    for row in packets:
        if active_count >= cfg.max_parallel_workers:
            break
        counters["attempted"] += 1
        worker_id = str(row.get("worker_id") or "")
        packet_id = str(row.get("packet_id") or "")
        prompt = str(row.get("prompt") or "").strip()
        profile_alias = str(row.get("profile_alias") or "")

        timestamp = utc_now_iso()
        event = {
            "cycle_number": cycle_number,
            "worker_id": worker_id,
            "packet_id": packet_id,
            "thread_id": None,
            "pid": None,
            "status": "unknown",
            "timestamp": timestamp,
            "message": "",
        }

        if script is None:
            event["status"] = "launch_failed"
            event["message"] = "thread-dispatch script not found"
            counters["launch_failed"] += 1
            event_rows.append(event)
            _append_jsonl(cfg.repo_root / DISPATCH_LAUNCH_LOG_FILE, event)
            continue

        if not prompt:
            event["status"] = "launch_failed"
            event["message"] = "missing worker packet prompt"
            counters["launch_failed"] += 1
            event_rows.append(event)
            _append_jsonl(cfg.repo_root / DISPATCH_LAUNCH_LOG_FILE, event)
            continue

        cmd = [
            "python3",
            str(script),
            "--cwd",
            str(cfg.repo_root),
            "--prompt",
            prompt,
            "--background",
        ]
        profile_home = alias_to_home.get(profile_alias)
        if profile_home:
            cmd.extend(["--codex-home", profile_home])

        try:
            proc = subprocess.run(cmd, cwd=str(cfg.repo_root), capture_output=True, text=True, timeout=30, check=False)
            stdout_text = (proc.stdout or "").strip()
            stderr_text = (proc.stderr or "").strip()
            if proc.returncode == 0:
                parsed = None
                try:
                    parsed = json.loads(stdout_text) if stdout_text else {}
                except json.JSONDecodeError:
                    parsed = {}
                status_text = str((parsed or {}).get("status") or "").strip().lower()
                thread_id = str((parsed or {}).get("session_id") or "") or None
                pid_value = (parsed or {}).get("pid")
                try:
                    pid_int = int(pid_value) if pid_value is not None else None
                except (TypeError, ValueError):
                    pid_int = None
                event["thread_id"] = thread_id
                event["pid"] = pid_int
                if status_text == "started":
                    event["status"] = "launched"
                    event["message"] = "dispatch started"
                    counters["launched"] += 1
                    active_count += 1
                else:
                    event["status"] = "unknown"
                    event["message"] = "dispatch returned ambiguous status"
                    counters["unknown"] += 1
                    active_count += 1
            else:
                event["status"] = "launch_failed"
                event["message"] = stderr_text or stdout_text or "dispatch command failed"
                counters["launch_failed"] += 1
        except subprocess.TimeoutExpired:
            event["status"] = "unknown"
            event["message"] = "dispatch command timeout"
            counters["unknown"] += 1
            active_count += 1

        event_rows.append(event)
        _append_jsonl(cfg.repo_root / DISPATCH_LAUNCH_LOG_FILE, event)

    if event_rows:
        _update_dispatch_registry(cfg, event_rows)
        _update_worker_registry_dispatch_state(cfg, event_rows)
    return counters


def _watchdog_tick(cfg: RunConfig, cycle_number: int) -> tuple[bool, dict[str, Any]]:
    init_state = _read_json(cfg.repo_root / INITIALIZE_STATE_FILE, default={})
    monitored_branch = "main"
    if isinstance(init_state, dict):
        branch_raw = init_state.get("monitored_branch")
        if isinstance(branch_raw, str) and branch_raw.strip():
            monitored_branch = branch_raw.strip()

    current_sha = _git_text(cfg.repo_root, "rev-parse", monitored_branch)
    if not current_sha:
        current_sha = _git_text(cfg.repo_root, "rev-parse", "HEAD")

    state_path = cfg.repo_root / ARTIFACT_FILES["watchdog_state"]
    state = _read_json(state_path, default={})
    if not isinstance(state, dict):
        state = {}

    last_sha = state.get("last_commit_sha") if isinstance(state.get("last_commit_sha"), str) else ""
    idle_cycles = int(state.get("idle_cycles") or 0)
    threshold_cycles = int(state.get("threshold_cycles") or WATCHDOG_IDLE_THRESHOLD)
    if threshold_cycles <= 0:
        threshold_cycles = WATCHDOG_IDLE_THRESHOLD

    if current_sha and current_sha != last_sha:
        idle_cycles = 0
        last_seen_cycle = cycle_number
    else:
        idle_cycles += 1
        last_seen_cycle = int(state.get("last_commit_seen_cycle") or 0)

    next_state = {
        "schema_version": SCHEMA_VERSION,
        "cycle_number": cycle_number,
        "monitored_branch": monitored_branch,
        "last_commit_sha": current_sha,
        "last_commit_seen_cycle": last_seen_cycle,
        "idle_cycles": idle_cycles,
        "threshold_cycles": threshold_cycles,
    }
    _atomic_write_json(state_path, next_state)

    exit_signal = {
        "schema_version": SCHEMA_VERSION,
        "cycle_number": cycle_number,
        "reason_code": "no_new_commits",
        "message": f"no new commits detected for {idle_cycles} cycles",
        "monitored_branch": monitored_branch,
        "idle_cycles": idle_cycles,
    }

    should_stop = idle_cycles >= threshold_cycles
    exit_path = cfg.repo_root / ARTIFACT_FILES["watchdog_exit_signal"]
    if should_stop:
        _atomic_write_json(exit_path, exit_signal)
    else:
        _safe_unlink(exit_path)

    return should_stop, exit_signal


def _render_cycle_summary(cfg: RunConfig, cycle_number: int, manager_statuses: dict[str, dict[str, str]], dispatch_counts: dict[str, int]) -> dict[str, Any]:
    summary_path = cfg.repo_root / ARTIFACT_FILES["cycle_summary"]
    summary = _read_json(summary_path, default={})
    if not isinstance(summary, dict):
        summary = {}

    task_counts = summary.get("task_counts") if isinstance(summary.get("task_counts"), dict) else {}
    merged_counts = {
        "pending": int(task_counts.get("pending") or 0),
        "in_progress": int(task_counts.get("in_progress") or 0),
        "done": int(task_counts.get("done") or 0),
        "blocked": int(task_counts.get("blocked") or 0),
    }

    out = {
        "schema_version": SCHEMA_VERSION,
        "cycle_number": cycle_number,
        "manager_statuses": manager_statuses,
        "task_counts": merged_counts,
        "dispatch_counts": {
            "attempted": int(dispatch_counts.get("attempted") or 0),
            "launched": int(dispatch_counts.get("launched") or 0),
            "launch_failed": int(dispatch_counts.get("launch_failed") or 0),
            "unknown": int(dispatch_counts.get("unknown") or 0),
        },
        "project_done": bool(summary.get("project_done")),
        "insurmountable_blocker": bool(summary.get("insurmountable_blocker")),
        "termination": summary.get("termination") if isinstance(summary.get("termination"), dict) else {},
        "stop_reason": str(summary.get("stop_reason") or ""),
        "notes": str(summary.get("notes") or ""),
    }

    _atomic_write_json(summary_path, out)

    print(
        "[op-simple-build] "
        f"cycle={cycle_number} pending={merged_counts['pending']} in_progress={merged_counts['in_progress']} "
        f"done={merged_counts['done']} blocked={merged_counts['blocked']} "
        f"dispatch={{attempted:{out['dispatch_counts']['attempted']},launched:{out['dispatch_counts']['launched']},failed:{out['dispatch_counts']['launch_failed']},unknown:{out['dispatch_counts']['unknown']}}}",
        flush=True,
    )
    return out


def _termination_from_summary(summary: dict[str, Any]) -> str | None:
    if bool(summary.get("project_done")):
        return "project_done"
    if bool(summary.get("insurmountable_blocker")):
        return "insurmountable_blocker"
    termination = summary.get("termination")
    if isinstance(termination, dict):
        reason = termination.get("reason_code")
        if isinstance(reason, str) and reason.strip():
            return reason.strip()
    stop_reason = summary.get("stop_reason")
    if isinstance(stop_reason, str) and stop_reason.strip():
        return stop_reason.strip()
    return None


def _snapshot_cycle(cfg: RunConfig, cycle_number: int) -> None:
    cycle_dir = _ensure_history_cycle_dir(cfg, cycle_number)
    for rel in [*ARTIFACT_FILES.values(), MANAGER_CALL_LOG_FILE, DISPATCH_LAUNCH_LOG_FILE, CYCLE_COUNTER_FILE]:
        src = cfg.repo_root / rel
        if not src.exists() or not src.is_file():
            continue
        dst = cycle_dir / src.name
        try:
            shutil.copy2(src, dst)
        except OSError:
            continue


def _load_cycle_counter(cfg: RunConfig) -> int:
    payload = _read_json(cfg.repo_root / CYCLE_COUNTER_FILE, default={})
    if not isinstance(payload, dict):
        return 0
    try:
        return int(payload.get("cycle_number") or 0)
    except (TypeError, ValueError):
        return 0


def _write_cycle_counter(cfg: RunConfig, cycle_number: int) -> None:
    _atomic_write_json(
        cfg.repo_root / CYCLE_COUNTER_FILE,
        {
            "schema_version": SCHEMA_VERSION,
            "updated_at": utc_now_iso(),
            "cycle_number": cycle_number,
        },
    )


def _acquire_run_lock(cfg: RunConfig) -> tuple[bool, str, dict[str, Any] | None]:
    lock_path = cfg.repo_root / RUN_LOCK_FILE
    lock_payload = _read_json(lock_path, default={})
    if isinstance(lock_payload, dict):
        try:
            existing_pid = int(lock_payload.get("pid") or 0)
        except (TypeError, ValueError):
            existing_pid = 0
        if existing_pid > 0 and _is_pid_running(existing_pid):
            return False, "active_lock", lock_payload

    lock_id = f"op-simple-build-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "lock_id": lock_id,
        "pid": os.getpid(),
        "started_at": utc_now_iso(),
        "command": "op-simple-build",
    }
    _atomic_write_json(lock_path, payload)
    return True, lock_id, None


def _release_run_lock(cfg: RunConfig, lock_id: str | None) -> None:
    if not lock_id:
        return
    path = cfg.repo_root / RUN_LOCK_FILE
    payload = _read_json(path, default={})
    if not isinstance(payload, dict):
        return
    if str(payload.get("lock_id") or "") != lock_id:
        return
    _safe_unlink(path)


def _build_config(req: Any) -> RunConfig:
    repo_root = Path(req.repo_root).resolve()
    sleep_minutes = float(getattr(req, "sleep_minutes", 5.0) or 5.0)
    if sleep_minutes < 0:
        sleep_minutes = 0.0
    max_cycles = getattr(req, "max_build_cycles", None)
    if max_cycles is not None:
        try:
            max_cycles = int(max_cycles)
        except (TypeError, ValueError):
            max_cycles = None
        if isinstance(max_cycles, int) and max_cycles <= 0:
            max_cycles = None
    max_parallel_workers = getattr(req, "max_parallel_workers", 8)
    try:
        max_parallel_workers = int(max_parallel_workers)
    except (TypeError, ValueError):
        max_parallel_workers = 8
    if max_parallel_workers <= 0:
        max_parallel_workers = 8

    return RunConfig(
        repo_root=repo_root,
        sleep_minutes=sleep_minutes,
        max_build_cycles=max_cycles,
        max_parallel_workers=max_parallel_workers,
        dry_run=bool(getattr(req, "dry_run", False)),
    )


def run_op_simple_build(req: Any) -> dict[str, Any]:
    cfg = _build_config(req)
    warnings: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    artifacts = [str((cfg.repo_root / rel).resolve()) for rel in ARTIFACT_FILES.values()]
    artifacts.extend(
        [
            str((cfg.repo_root / MANAGER_CALL_LOG_FILE).resolve()),
            str((cfg.repo_root / DISPATCH_LAUNCH_LOG_FILE).resolve()),
            str((cfg.repo_root / CYCLE_COUNTER_FILE).resolve()),
            str((cfg.repo_root / RUN_LOCK_FILE).resolve()),
        ]
    )

    lock_ok, lock_ref, active_lock = _acquire_run_lock(cfg)
    if not lock_ok:
        return {
            "ok": False,
            "status": "blocked_preflight",
            "summary": "Build blocked: another /op-simple-build loop is active.",
            "errors": [
                {
                    "code": "op_simple_lock_active",
                    "message": "active op-simple run lock detected",
                    "stage": "build_loop",
                    "details": active_lock or {},
                }
            ],
            "warnings": [],
            "artifacts": artifacts,
            "next_action": "Wait for active /op-simple-build to finish, or clear stale lock after confirming owner process is gone.",
            "state_ref": str((cfg.repo_root / RUN_LOCK_FILE).resolve()),
            "data": {},
        }

    final_status = "completed"
    final_summary = "OP Simple build finished."
    final_next_action: str | None = None
    stop_reason: str | None = None

    try:
        (cfg.repo_root / CURRENT_DIR).mkdir(parents=True, exist_ok=True)
        (cfg.repo_root / HISTORY_DIR).mkdir(parents=True, exist_ok=True)

        init_state = _ensure_initialize_state(cfg)
        _ensure_workstation_prep(cfg)
        _ensure_default_artifacts(cfg)

        cycle_number = _load_cycle_counter(cfg)

        while True:
            cycle_number += 1
            _write_cycle_counter(cfg, cycle_number)

            terminate_path = cfg.repo_root / TERMINATE_FILE_NAME
            if terminate_path.exists():
                stop_reason = "operator_terminate_file"
                final_summary = "OP Simple build stopped by terminate_run.json signal."
                break

            manager_statuses: dict[str, dict[str, str]] = {}
            dispatch_counts = {"attempted": 0, "launched": 0, "launch_failed": 0, "unknown": 0}

            cycle_result = _invoke_manager(
                cfg,
                manager_name="cycle-manager",
                cycle_number=cycle_number,
                context={"max_parallel_workers": init_state.get("workflow", {}).get("max_parallel_workers")},
                expected_artifacts=["cycle_manager_decision", "worker_registry"],
            )
            manager_statuses["cycle-manager"] = {"status": cycle_result.status, "note": cycle_result.message or ""}
            if cycle_result.timeout:
                if cfg.max_build_cycles is not None and cycle_number >= cfg.max_build_cycles:
                    final_summary = f"Reached max_build_cycles={cfg.max_build_cycles} after cycle-manager timeout."
                    break
                if cfg.sleep_minutes > 0:
                    time.sleep(cfg.sleep_minutes * 60.0)
                continue
            if cycle_result.status != "ok":
                warnings.append(
                    {
                        "code": "cycle_manager_failed",
                        "message": cycle_result.message or "cycle-manager failed",
                        "stage": "op-simple-build",
                    }
                )

            decision = _read_cycle_decision(cfg)
            if str(decision.get("decision") or "proceed") == "skip_cycle":
                summary = _render_cycle_summary(cfg, cycle_number, manager_statuses, dispatch_counts)
                stop_reason = _termination_from_summary(summary)
                _snapshot_cycle(cfg, cycle_number)
                if stop_reason:
                    final_summary = f"OP Simple build stopped: {stop_reason}."
                    break
                if cfg.max_build_cycles is not None and cycle_number >= cfg.max_build_cycles:
                    final_summary = f"Reached max_build_cycles={cfg.max_build_cycles}."
                    break
                if cfg.sleep_minutes > 0:
                    time.sleep(cfg.sleep_minutes * 60.0)
                continue

            profile_result = _invoke_manager(
                cfg,
                manager_name="profile-manager",
                cycle_number=cycle_number,
                context={"reason": "cycle"},
                expected_artifacts=["profile_snapshot"],
            )
            manager_statuses["profile-manager"] = {"status": profile_result.status, "note": profile_result.message or ""}
            if profile_result.status != "ok":
                warnings.append(
                    {
                        "code": "profile_manager_failed",
                        "message": profile_result.message or "profile-manager failed",
                        "stage": "op-simple-build",
                    }
                )

            boss_expected = [
                "production_line_register",
                "worker_packets",
                "plan_packets",
                "task_execution_state",
                "worker_registry",
                "cycle_summary",
            ]
            boss_result = _invoke_manager(
                cfg,
                manager_name="BOSS",
                cycle_number=cycle_number,
                context={
                    "max_parallel_workers": init_state.get("workflow", {}).get("max_parallel_workers"),
                    "boss_evidence_path": str((cfg.repo_root / BOSS_EVIDENCE_FILE).resolve()),
                },
                expected_artifacts=boss_expected,
            )
            manager_statuses["BOSS"] = {"status": boss_result.status, "note": boss_result.message or ""}

            if boss_result.timeout:
                _atomic_write_json(
                    cfg.repo_root / BOSS_EVIDENCE_FILE,
                    {
                        "schema_version": SCHEMA_VERSION,
                        "cycle_number": cycle_number,
                        "manager": "BOSS",
                        "event": "timeout",
                        "timestamp": utc_now_iso(),
                    },
                )
                time.sleep(180)
                if cfg.max_build_cycles is not None and cycle_number >= cfg.max_build_cycles:
                    final_summary = f"Reached max_build_cycles={cfg.max_build_cycles} after BOSS timeout."
                    break
                continue
            _safe_unlink(cfg.repo_root / BOSS_EVIDENCE_FILE)

            if boss_result.status != "ok":
                warnings.append(
                    {
                        "code": "boss_failed",
                        "message": boss_result.message or "BOSS failed",
                        "stage": "op-simple-build",
                    }
                )

            _run_rate_gate_wait(cfg, cycle_number, warnings)

            dispatch_counts = _dispatch_packets(cfg, cycle_number)
            manager_statuses["work-dispatcher"] = {"status": "ok", "note": "dispatch cycle completed"}

            watchdog_stop, watchdog_signal = _watchdog_tick(cfg, cycle_number)
            manager_statuses["watchdog"] = {
                "status": "stop" if watchdog_stop else "ok",
                "note": watchdog_signal.get("message") if watchdog_stop else "watchdog healthy",
            }

            summary = _render_cycle_summary(cfg, cycle_number, manager_statuses, dispatch_counts)
            manager_statuses["summary"] = {"status": "ok", "note": "summary written"}

            terminate_path = cfg.repo_root / TERMINATE_FILE_NAME
            if terminate_path.exists():
                stop_reason = "operator_terminate_file"
            else:
                stop_reason = _termination_from_summary(summary)
                if stop_reason not in {"project_done", "insurmountable_blocker"} and watchdog_stop:
                    stop_reason = "watchdog_idle_stop"

            _snapshot_cycle(cfg, cycle_number)

            if stop_reason:
                final_summary = f"OP Simple build stopped: {stop_reason}."
                break

            if cfg.max_build_cycles is not None and cycle_number >= cfg.max_build_cycles:
                final_summary = f"Reached max_build_cycles={cfg.max_build_cycles}."
                break

            if cfg.sleep_minutes > 0:
                time.sleep(cfg.sleep_minutes * 60.0)

        data = {
            "cycle_number": cycle_number,
            "stop_reason": stop_reason,
            "max_parallel_workers": cfg.max_parallel_workers,
            "artifact_root": str((cfg.repo_root / SIMPLE_ROOT).resolve()),
        }
        return {
            "ok": final_status == "completed",
            "status": final_status,
            "summary": final_summary,
            "errors": errors,
            "warnings": warnings,
            "artifacts": artifacts,
            "next_action": final_next_action,
            "state_ref": str((cfg.repo_root / ARTIFACT_FILES["cycle_summary"]).resolve()),
            "data": data,
        }
    except SimpleBuildError as exc:
        return {
            "ok": False,
            "status": "failed",
            "summary": "OP Simple build failed.",
            "errors": [{"code": exc.code, "message": exc.message, "stage": "op-simple-build"}],
            "warnings": warnings,
            "artifacts": artifacts,
            "next_action": "Repair OP Simple runtime artifacts/config and rerun /op-simple-build.",
            "state_ref": str((cfg.repo_root / CURRENT_DIR).resolve()),
            "data": {},
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "status": "failed",
            "summary": "OP Simple build failed.",
            "errors": [{"code": "op_simple_runtime_error", "message": str(exc), "stage": "op-simple-build"}],
            "warnings": warnings,
            "artifacts": artifacts,
            "next_action": "Inspect manager logs under .op-simple/history and rerun /op-simple-build.",
            "state_ref": str((cfg.repo_root / CURRENT_DIR).resolve()),
            "data": {},
        }
    finally:
        _release_run_lock(cfg, lock_ref if isinstance(lock_ref, str) else None)
