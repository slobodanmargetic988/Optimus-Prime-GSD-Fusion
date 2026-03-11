#!/usr/bin/env python3
"""OP Simple build loop runtime."""

from __future__ import annotations

import json
import hashlib
import os
import re
import shutil
import signal
import subprocess
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent

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
BOSS_SESSION_STATE_FILE = CURRENT_DIR / "boss_session_state.json"
APP_LIFECYCLE_FILE = Path("app_lifecycle.json")
TRACE_EVENT_LOG_FILE = CURRENT_DIR / "trace_event_envelope.jsonl"

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
    "wrapup_manager_report": CURRENT_DIR / "wrapup_manager_report.json",
    "watchdog_state": CURRENT_DIR / "watchdog_state.json",
    "watchdog_exit_signal": CURRENT_DIR / "watchdog_exit_signal.json",
    "workstation_prep": CURRENT_DIR / "workstation_prep.json",
}

MANAGER_TIMEOUT_SECONDS = {
    "BOSS": 720,
    "wrapup-manager": 720,
    "watchdog": 120,
    "summary": 120,
}

QUIET_CYCLE_FORCE_FULL_EVERY = 5
WATCHDOG_STALE_COMMIT_MINUTES = 150
WATCHDOG_NEAR_STALE_MARGIN_MINUTES = 10
WAIT_HEARTBEAT_SECONDS = 300
WAIT_RESCAN_SECONDS = 900
RATE_SNAPSHOT_SCRIPT_REL = Path("skills") / "codex-rate-snapshot" / "scripts" / "read_codex_rate_snapshots.py"
NON_TERMINAL_STOP_REASONS = {
    "skip_cycle",
    "active_workers_in_progress_no_safe_new_dispatch",
}

PLANNER_PLAN_PACKETS_FILE = Path("reports/optimus-prime/planning/PLAN_PACKETS.json")
BOSS_REQUIRED_ARTIFACTS = [
    "production_line_register",
    "worker_packets",
    "plan_packets",
    "task_execution_state",
    "worker_registry",
    "cycle_summary",
]
TASK_ATTEMPT_STAGES = ("dev", "lane_test", "test_fix", "lane_review", "review_fix", "deep_review", "deep_fix")
SESSION_ID_REGEX = re.compile(r"(?:session id|session_id)\s*[:=]\s*([0-9a-fA-F-]{36})", re.IGNORECASE)
CANONICAL_ID_PATTERNS: dict[str, re.Pattern[str]] = {
    "project_id": re.compile(r"^prj\.[a-z0-9][a-z0-9-]{1,95}$"),
    "era_id": re.compile(r"^era\.[a-z0-9][a-z0-9-]{1,95}$"),
    "plan_id": re.compile(r"^plan\.[a-z0-9][a-z0-9-]{1,95}$"),
    "phase_id": re.compile(r"^phase\.[a-z0-9][a-z0-9-]{1,95}$"),
    "lane_id": re.compile(r"^lane\.[a-z0-9][a-z0-9-]{1,95}$"),
    "task_id": re.compile(r"^task\.[a-z0-9][a-z0-9-]{1,95}$"),
    "run_id": re.compile(r"^run\.[a-z0-9][a-z0-9-]{1,95}$"),
    "thread_id": re.compile(r"^thread\.[a-z0-9][a-z0-9-]{1,95}$"),
    "event_id": re.compile(r"^event\.[a-z0-9][a-z0-9-]{1,95}$"),
    "decision_id": re.compile(r"^decision\.[a-z0-9][a-z0-9-]{1,95}$"),
    "artifact_id": re.compile(r"^artifact\.[a-z0-9][a-z0-9-]{1,95}$"),
}
TRACE_EVENT_TIMESTAMP_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
TRACE_EVENT_SOURCE_SHA_REGEX = re.compile(r"^[a-f0-9]{7,40}$")
TRACE_EVENT_OUTCOME_STATUS = {"success", "failure", "partial", "noop", "blocked"}
TRACE_EVENT_RISK_LEVELS = {"low", "medium", "high", "critical"}
TRACE_EVENT_ACTOR_TYPES = {"manager", "worker", "service", "operator", "system"}


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
    reason_code: str | None = None
    details: dict[str, Any] | None = None
    session_id: str | None = None


@dataclass
class RunConfig:
    repo_root: Path
    sleep_minutes: float
    max_build_cycles: int | None
    max_parallel_workers: int
    dry_run: bool
    resume_mode: bool = False
    run_base_source_branch: str = "main"
    boss_model: str = "gpt-5.3-codex"
    boss_reasoning_effort: str = "medium"


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


def _extract_session_id(*parts: str) -> str | None:
    for part in parts:
        text = (part or "").strip()
        if not text:
            continue
        match = SESSION_ID_REGEX.search(text)
        if match:
            return match.group(1)
    return None


def _slugify_identifier(raw: Any) -> str:
    text = str(raw or "").strip().lower()
    if not text:
        return "unknown0"
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    if not text:
        text = "unknown0"
    if len(text) < 2:
        text = f"{text}0"
    return text[:96]


def _canonical_id(prefix: str, raw: Any) -> str:
    return f"{prefix}.{_slugify_identifier(raw)}"


def _canonical_identity_for_cycle(cfg: RunConfig, cycle_number: int) -> dict[str, str]:
    lock_payload = _read_json(cfg.repo_root / RUN_LOCK_FILE, default={})
    lock_id = ""
    if isinstance(lock_payload, dict):
        lock_id = str(lock_payload.get("lock_id") or "").strip()

    if not lock_id:
        init_state = _read_json(cfg.repo_root / INITIALIZE_STATE_FILE, default={})
        run_context = init_state.get("run_context") if isinstance(init_state, dict) else {}
        run_base_branch = str((run_context or {}).get("run_base_branch") or "").strip()
        lock_id = run_base_branch or f"cycle-{cycle_number}"

    event_seed = f"{datetime.now(timezone.utc).strftime('%Y%m%dt%H%M%Sz').lower()}-{cycle_number}-wrapup"
    out = {
        "project_id": _canonical_id("prj", cfg.repo_root.name),
        "run_id": _canonical_id("run", lock_id),
        "event_id": _canonical_id("event", event_seed),
    }
    era_id = _active_lifecycle_era_id(cfg)
    if era_id:
        out["era_id"] = _canonical_id("era", era_id)
    return out


def _validate_cross_project_ids_v1(identity: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(identity, dict):
        return ["identity must be an object"]
    for key in ("project_id", "run_id", "event_id"):
        value = identity.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"identity.{key} is required")
            continue
        pattern = CANONICAL_ID_PATTERNS[key]
        if not pattern.fullmatch(value.strip()):
            errors.append(f"identity.{key} fails canonical pattern")
    for key, pattern in CANONICAL_ID_PATTERNS.items():
        if key not in identity:
            continue
        value = identity.get(key)
        if value is None:
            continue
        if not isinstance(value, str) or not pattern.fullmatch(value.strip()):
            errors.append(f"identity.{key} fails canonical pattern")
    return errors


def _validate_trace_event_envelope_v1(payload: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["trace event payload must be an object"]

    if payload.get("schema_version") != "trace-event-envelope.v1":
        errors.append("schema_version must be trace-event-envelope.v1")

    event_name = payload.get("event_name")
    if not isinstance(event_name, str) or len(event_name.strip()) < 3:
        errors.append("event_name must be a non-empty string")

    timestamp_utc = payload.get("timestamp_utc")
    if not isinstance(timestamp_utc, str) or not TRACE_EVENT_TIMESTAMP_REGEX.fullmatch(timestamp_utc):
        errors.append("timestamp_utc must match YYYY-MM-DDTHH:MM:SSZ")

    errors.extend(_validate_cross_project_ids_v1(payload.get("identity")))

    actor = payload.get("actor")
    if not isinstance(actor, dict):
        errors.append("actor must be an object")
    else:
        actor_type = actor.get("type")
        actor_id = actor.get("id")
        if actor_type not in TRACE_EVENT_ACTOR_TYPES:
            errors.append("actor.type is invalid")
        if not isinstance(actor_id, str) or not actor_id.strip():
            errors.append("actor.id is required")

    decision = payload.get("decision")
    if not isinstance(decision, dict):
        errors.append("decision must be an object")
    else:
        question = decision.get("question")
        rationale = decision.get("rationale")
        reason_codes = decision.get("reason_codes")
        if not isinstance(question, str) or len(question.strip()) < 10:
            errors.append("decision.question must be at least 10 characters")
        if not isinstance(rationale, str) or len(rationale.strip()) < 10:
            errors.append("decision.rationale must be at least 10 characters")
        if not isinstance(reason_codes, list) or not reason_codes:
            errors.append("decision.reason_codes must be a non-empty list")
        elif any(not isinstance(item, str) or not item.strip() for item in reason_codes):
            errors.append("decision.reason_codes must contain non-empty strings")

    operation = payload.get("operation")
    if not isinstance(operation, dict):
        errors.append("operation must be an object")
    else:
        if not isinstance(operation.get("name"), str) or len(str(operation.get("name")).strip()) < 3:
            errors.append("operation.name must be a non-empty string")
        if not isinstance(operation.get("intent"), str) or len(str(operation.get("intent")).strip()) < 3:
            errors.append("operation.intent must be a non-empty string")

    outcome = payload.get("outcome")
    if not isinstance(outcome, dict):
        errors.append("outcome must be an object")
    else:
        status = outcome.get("status")
        summary = outcome.get("summary")
        if status not in TRACE_EVENT_OUTCOME_STATUS:
            errors.append("outcome.status is invalid")
        if not isinstance(summary, str) or len(summary.strip()) < 3:
            errors.append("outcome.summary must be a non-empty string")

    risk = payload.get("risk")
    if not isinstance(risk, dict):
        errors.append("risk must be an object")
    else:
        if risk.get("level") not in TRACE_EVENT_RISK_LEVELS:
            errors.append("risk.level is invalid")

    evidence = payload.get("evidence")
    if not isinstance(evidence, dict):
        errors.append("evidence must be an object")
    else:
        artifacts = evidence.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            errors.append("evidence.artifacts must be a non-empty list")
        else:
            for idx, artifact in enumerate(artifacts):
                if not isinstance(artifact, dict):
                    errors.append(f"evidence.artifacts[{idx}] must be an object")
                    continue
                artifact_id = artifact.get("artifact_id")
                if not isinstance(artifact_id, str) or not CANONICAL_ID_PATTERNS["artifact_id"].fullmatch(artifact_id):
                    errors.append(f"evidence.artifacts[{idx}].artifact_id is invalid")
                if not isinstance(artifact.get("kind"), str) or not str(artifact.get("kind")).strip():
                    errors.append(f"evidence.artifacts[{idx}].kind is required")
                if not isinstance(artifact.get("uri"), str) or not str(artifact.get("uri")).strip():
                    errors.append(f"evidence.artifacts[{idx}].uri is required")

    source = payload.get("source")
    if not isinstance(source, dict):
        errors.append("source must be an object")
    else:
        repo = source.get("repo")
        commit_sha = source.get("commit_sha")
        if not isinstance(repo, str) or not repo.strip():
            errors.append("source.repo is required")
        if commit_sha is not None:
            if not isinstance(commit_sha, str) or not TRACE_EVENT_SOURCE_SHA_REGEX.fullmatch(commit_sha.strip()):
                errors.append("source.commit_sha is invalid")

    return errors


def _build_wrapup_trace_event(
    cfg: RunConfig,
    *,
    cycle_number: int,
    stop_reason: str,
    run_context: dict[str, Any],
    result: ManagerResult,
) -> dict[str, Any]:
    event_ts = utc_now_iso()
    identity = _canonical_identity_for_cycle(cfg, cycle_number)
    decision_id_seed = f"wrapup-{cycle_number}-{stop_reason}-{result.status}"
    identity["decision_id"] = _canonical_id("decision", decision_id_seed)

    reason_code = str(result.reason_code or f"wrapup_manager_{result.status}" or "wrapup_manager_unknown").strip()
    outcome_status = "success" if result.status == "ok" else "failure"
    risk_level = "low" if result.status == "ok" else "medium"
    report_uri = str(ARTIFACT_FILES["wrapup_manager_report"])
    manager_log_uri = str(MANAGER_CALL_LOG_FILE)

    source_branch = str(run_context.get("run_base_branch") or "").strip() or (_git_text(cfg.repo_root, "branch", "--show-current") or "")
    source_commit_sha = _git_text(cfg.repo_root, "rev-parse", "HEAD") or ""

    event = {
        "schema_version": "trace-event-envelope.v1",
        "event_name": "merge.lifecycle.wrapup_manager",
        "timestamp_utc": event_ts,
        "identity": identity,
        "actor": {
            "type": "service",
            "id": "wrapup-manager",
        },
        "decision": {
            "question": f"Should wrapup manager run for stop reason '{stop_reason}' at cycle {cycle_number}?",
            "rationale": (
                "Wrapup manager execution is required on project completion to finalize merge lifecycle context and "
                "produce deterministic end-of-run evidence."
            ),
            "reason_codes": [reason_code],
        },
        "operation": {
            "name": "invoke_wrapup_manager",
            "intent": "Finalize run and capture merge lifecycle outcome.",
            "target_ref": source_branch,
            "inputs": {
                "stop_reason": stop_reason,
                "cycle_number": cycle_number,
                "manager_status": result.status,
            },
        },
        "outcome": {
            "status": outcome_status,
            "summary": (
                "wrapup-manager completed and produced post-run summary artifacts"
                if result.status == "ok"
                else f"wrapup-manager failed with status={result.status}"
            ),
            "error_code": reason_code if result.status != "ok" else None,
            "retryable": bool(result.timeout),
            "metrics": {
                "duration_seconds": result.duration_seconds,
            },
        },
        "risk": {
            "level": risk_level,
            "notes": (
                "Wrapup failure can delay merge/finalization transparency and should be triaged."
                if result.status != "ok"
                else "Low risk finalization event."
            ),
        },
        "evidence": {
            "artifacts": [
                {
                    "artifact_id": _canonical_id("artifact", f"wrapup-report-c{cycle_number}"),
                    "kind": "wrapup_manager_report",
                    "uri": report_uri,
                    "generated_at_utc": event_ts,
                },
                {
                    "artifact_id": _canonical_id("artifact", f"manager-call-log-c{cycle_number}"),
                    "kind": "manager_call_log",
                    "uri": manager_log_uri,
                    "generated_at_utc": event_ts,
                },
            ]
        },
        "source": {
            "repo": cfg.repo_root.name,
            "branch": source_branch,
        },
    }
    if source_commit_sha and TRACE_EVENT_SOURCE_SHA_REGEX.fullmatch(source_commit_sha):
        event["source"]["commit_sha"] = source_commit_sha
    return event


def _emit_trace_event_envelope(
    cfg: RunConfig,
    *,
    cycle_number: int,
    payload: dict[str, Any],
) -> None:
    errors = _validate_trace_event_envelope_v1(payload)
    if errors:
        message = "; ".join(errors[:8])
        raise SimpleBuildError(
            "trace_event_envelope_invalid",
            f"trace event envelope validation failed at cycle {cycle_number}: {message}",
        )

    _append_jsonl(cfg.repo_root / TRACE_EVENT_LOG_FILE, payload)
    print(
        "[op-simple-build] "
        f"[{utc_now_iso()}] "
        f"cycle={cycle_number} trace_event={payload.get('event_name')} schema_validation=passed",
        flush=True,
    )


def _effective_codex_home(codex_home: str | None) -> str:
    codex_home_text = (codex_home or "").strip()
    if codex_home_text:
        return str(Path(codex_home_text).expanduser())
    env_home = (os.environ.get("CODEX_HOME") or "").strip()
    if env_home:
        return str(Path(env_home).expanduser())
    return str(Path.home() / ".codex")


def _read_boss_session_state(cfg: RunConfig) -> dict[str, str]:
    payload = _read_json(cfg.repo_root / BOSS_SESSION_STATE_FILE, default={})
    if not isinstance(payload, dict):
        return {}
    session_id = str(payload.get("session_id") or "").strip()
    codex_home = str(payload.get("codex_home") or "").strip()
    profile_alias = str(payload.get("profile_alias") or "").strip()
    previous_profile_alias = str(payload.get("previous_profile_alias") or "").strip()
    if not session_id:
        return {}
    out = {"session_id": session_id}
    if codex_home:
        out["codex_home"] = codex_home
    if profile_alias:
        out["profile_alias"] = profile_alias
    if previous_profile_alias:
        out["previous_profile_alias"] = previous_profile_alias
    return out


def _write_boss_session_state(
    cfg: RunConfig,
    *,
    session_id: str,
    codex_home: str | None,
    profile_alias: str | None,
    previous_profile_alias: str | None = None,
) -> None:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "updated_at": utc_now_iso(),
        "session_id": session_id,
        "codex_home": _effective_codex_home(codex_home),
        "profile_alias": str(profile_alias or "").strip(),
        "previous_profile_alias": str(previous_profile_alias or profile_alias or "").strip(),
    }
    _atomic_write_json(cfg.repo_root / BOSS_SESSION_STATE_FILE, payload)


def _active_lifecycle_era_id(cfg: RunConfig) -> str | None:
    payload = _read_json(cfg.repo_root / APP_LIFECYCLE_FILE, default={})
    if not isinstance(payload, dict):
        return None
    rows = payload.get("app_lifecycle")
    if not isinstance(rows, list):
        return None
    for row in reversed(rows):
        if not isinstance(row, dict):
            continue
        if str(row.get("status") or "").strip() != "in_progress":
            continue
        era_id = str(row.get("era_id") or "").strip()
        if era_id:
            return era_id
    return None


def _default_attempts() -> dict[str, int]:
    return {stage: 0 for stage in TASK_ATTEMPT_STAGES}


def _default_last_handoff_outcome() -> dict[str, Any]:
    return {
        "status": "unknown",
        "reason_codes": [],
        "timestamp": None,
    }


def _task_execution_state_payload(cycle_number: int, tasks: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "updated_at": utc_now_iso(),
        "cycle_number": int(cycle_number),
        "tasks": tasks or [],
        "blockers": [],
        "attempts": _default_attempts(),
        "last_handoff_outcome": _default_last_handoff_outcome(),
    }


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


def _git_commit_epoch_seconds(repo_root: Path, ref: str) -> int | None:
    raw = _git_text(repo_root, "show", "-s", "--format=%ct", ref)
    if not raw:
        return None
    try:
        epoch = int(raw.strip())
    except (TypeError, ValueError):
        return None
    if epoch <= 0:
        return None
    return epoch


def _git_run(repo_root: Path, *args: str) -> tuple[int, str, str]:
    proc = subprocess.run(["git", *args], cwd=str(repo_root), capture_output=True, text=True, check=False)
    return int(proc.returncode), (proc.stdout or "").strip(), (proc.stderr or "").strip()


def _create_run_base_branch(cfg: RunConfig) -> dict[str, Any]:
    active_branch = _git_text(cfg.repo_root, "branch", "--show-current") or "main"
    source_branch = str(cfg.run_base_source_branch or "").strip() or "main"
    if cfg.dry_run:
        return {
            "run_base_branch": active_branch,
            "run_base_from_branch": source_branch,
            "run_base_from_commit": _git_text(cfg.repo_root, "rev-parse", "HEAD") or "",
            "run_base_created_at": utc_now_iso(),
            "created_new": False,
            "dry_run": True,
        }

    source_ref = f"refs/heads/{source_branch}"
    source_commit = _git_text(cfg.repo_root, "rev-parse", "--verify", source_ref)
    if not source_commit:
        raise SimpleBuildError(
            "op_simple_missing_source_branch",
            f"Cannot start /op-simple-build: source branch '{source_branch}' does not exist.",
        )

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for _attempt in range(10):
        candidate = f"op-simple-canary-{timestamp}-{uuid.uuid4().hex[:8]}"
        code, _out, err = _git_run(cfg.repo_root, "checkout", "-b", candidate, source_ref)
        if code == 0:
            return {
                "run_base_branch": candidate,
                "run_base_from_branch": source_branch,
                "run_base_from_commit": source_commit,
                "run_base_created_at": utc_now_iso(),
                "created_new": True,
                "dry_run": False,
            }
        err_l = err.lower()
        if "already exists" in err_l:
            continue
        raise SimpleBuildError(
            "op_simple_base_branch_create_failed",
            f"Cannot create run base branch from '{source_branch}': {err or 'unknown git error'}",
        )

    raise SimpleBuildError(
        "op_simple_base_branch_exhausted",
        "Cannot create unique run base branch after multiple attempts.",
    )


def _load_resume_run_base_meta(cfg: RunConfig) -> dict[str, Any]:
    state = _read_json(cfg.repo_root / INITIALIZE_STATE_FILE, default={})
    if not isinstance(state, dict):
        state = {}
    run_context = state.get("run_context") if isinstance(state.get("run_context"), dict) else {}

    run_base_branch = str(run_context.get("run_base_branch") or state.get("monitored_branch") or "").strip()
    if not run_base_branch:
        raise SimpleBuildError(
            "op_simple_resume_unavailable",
            "Cannot resume /op-simple-build: missing run_base_branch in initialize_state.json.",
        )

    ref = f"refs/heads/{run_base_branch}"
    branch_commit = _git_text(cfg.repo_root, "rev-parse", "--verify", ref)
    if not branch_commit:
        raise SimpleBuildError(
            "op_simple_resume_missing_branch",
            f"Cannot resume /op-simple-build: run base branch '{run_base_branch}' does not exist.",
        )

    if not cfg.dry_run:
        code, _out, err = _git_run(cfg.repo_root, "checkout", run_base_branch)
        if code != 0:
            raise SimpleBuildError(
                "op_simple_resume_checkout_failed",
                f"Cannot checkout run base branch '{run_base_branch}' for resume: {err or 'unknown git error'}",
            )

    return {
        "run_base_branch": run_base_branch,
        "run_base_from_branch": str(run_context.get("run_base_from_branch") or cfg.run_base_source_branch or "main"),
        "run_base_from_commit": str(run_context.get("run_base_from_commit") or branch_commit),
        "run_base_created_at": str(run_context.get("run_base_created_at") or utc_now_iso()),
        "created_new": False,
        "dry_run": bool(cfg.dry_run),
    }


def _default_initialize_state(repo_root: Path, max_parallel_workers: int, run_meta: dict[str, Any] | None = None) -> dict[str, Any]:
    monitored_branch = _git_text(repo_root, "branch", "--show-current") or "main"
    run_context = {
        "run_base_branch": monitored_branch,
        "run_base_from_branch": "main",
        "run_base_from_commit": _git_text(repo_root, "rev-parse", "HEAD") or "",
        "run_base_created_at": utc_now_iso(),
        "created_new": False,
        "dry_run": False,
    }
    if isinstance(run_meta, dict):
        monitored_branch = str(run_meta.get("run_base_branch") or "").strip() or monitored_branch
        run_context.update(
            {
                "run_base_branch": run_meta.get("run_base_branch") or run_context["run_base_branch"],
                "run_base_from_branch": run_meta.get("run_base_from_branch") or run_context["run_base_from_branch"],
                "run_base_from_commit": run_meta.get("run_base_from_commit") or run_context["run_base_from_commit"],
                "run_base_created_at": run_meta.get("run_base_created_at") or run_context["run_base_created_at"],
                "created_new": bool(run_meta.get("created_new")),
                "dry_run": bool(run_meta.get("dry_run")),
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "updated_at": utc_now_iso(),
        "monitored_branch": monitored_branch,
        "workflow": {
            "max_parallel_workers": max_parallel_workers,
        },
        "run_context": run_context,
    }


def _ensure_initialize_state(cfg: RunConfig, run_meta: dict[str, Any] | None = None) -> dict[str, Any]:
    state = _read_json(cfg.repo_root / INITIALIZE_STATE_FILE, default={})
    if not isinstance(state, dict) or not state:
        state = _default_initialize_state(cfg.repo_root, cfg.max_parallel_workers, run_meta=run_meta)
    workflow = state.get("workflow") if isinstance(state.get("workflow"), dict) else {}
    if not isinstance(workflow.get("max_parallel_workers"), int) or int(workflow.get("max_parallel_workers")) <= 0:
        workflow["max_parallel_workers"] = cfg.max_parallel_workers
    if isinstance(run_meta, dict):
        workflow["max_parallel_workers"] = cfg.max_parallel_workers
    state["workflow"] = workflow
    if not isinstance(state.get("monitored_branch"), str) or not str(state.get("monitored_branch")).strip():
        state["monitored_branch"] = _git_text(cfg.repo_root, "branch", "--show-current") or "main"
    if isinstance(run_meta, dict):
        run_base_branch = str(run_meta.get("run_base_branch") or "").strip()
        if run_base_branch:
            state["monitored_branch"] = run_base_branch
    run_context = state.get("run_context") if isinstance(state.get("run_context"), dict) else {}
    if isinstance(run_meta, dict):
        run_context.update(
            {
                "run_base_branch": run_meta.get("run_base_branch"),
                "run_base_from_branch": run_meta.get("run_base_from_branch"),
                "run_base_from_commit": run_meta.get("run_base_from_commit"),
                "run_base_created_at": run_meta.get("run_base_created_at"),
                "created_new": bool(run_meta.get("created_new")),
                "dry_run": bool(run_meta.get("dry_run")),
            }
        )
    run_context.setdefault("run_base_branch", state.get("monitored_branch"))
    run_context.setdefault("run_base_from_branch", "main")
    run_context.setdefault("run_base_from_commit", _git_text(cfg.repo_root, "rev-parse", "HEAD") or "")
    run_context.setdefault("run_base_created_at", utc_now_iso())
    run_context.setdefault("created_new", False)
    run_context.setdefault("dry_run", bool(cfg.dry_run))
    state["run_context"] = run_context
    state["updated_at"] = utc_now_iso()
    state["schema_version"] = SCHEMA_VERSION
    _atomic_write_json(cfg.repo_root / INITIALIZE_STATE_FILE, state)
    return state


def _resolve_workstation_prepare_script(cfg: RunConfig) -> Path | None:
    candidates: list[Path] = []
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        candidates.append(
            Path(codex_home).expanduser() / "skills" / "workstation-preparation" / "scripts" / "prepare_workstation.py"
        )
    candidates.append(Path.home() / ".codex" / "skills" / "workstation-preparation" / "scripts" / "prepare_workstation.py")
    candidates.append(cfg.repo_root / "skills" / "workstation-preparation" / "scripts" / "prepare_workstation.py")
    installed_root = SCRIPTS_ROOT.parent
    candidates.append(installed_root / "skills" / "workstation-preparation" / "scripts" / "prepare_workstation.py")
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return None


def _seed_worker_registry_from_workstations(cfg: RunConfig, workstations: list[dict[str, Any]], cycle_number: int = 0) -> None:
    workers: list[dict[str, Any]] = []
    for idx, row in enumerate(workstations, start=1):
        worker_id = f"worker-{idx}"
        workers.append(
            {
                "worker_id": worker_id,
                "worktree": str(row.get("worktree") or ""),
                "branch": str(row.get("branch") or ""),
                "status": "idle",
                "current_task_profile": None,
                "next_task_profile": None,
                "current_task_id": None,
                "current_packet_id": None,
                "pid": None,
                "thread_id": None,
                "last_update": utc_now_iso(),
            }
        )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "updated_at": utc_now_iso(),
        "cycle_number": int(cycle_number or 0),
        "workers": workers,
    }
    _atomic_write_json(cfg.repo_root / ARTIFACT_FILES["worker_registry"], payload)


def _ensure_workstation_prep(
    cfg: RunConfig,
    initialize_state: dict[str, Any] | None = None,
    *,
    force_refresh: bool = False,
) -> dict[str, Any]:
    target = cfg.repo_root / ARTIFACT_FILES["workstation_prep"]
    payload = _read_json(target, default={})
    state = initialize_state if isinstance(initialize_state, dict) else _read_json(cfg.repo_root / INITIALIZE_STATE_FILE, default={})
    run_context = state.get("run_context") if isinstance(state, dict) and isinstance(state.get("run_context"), dict) else {}
    run_base_branch = str(run_context.get("run_base_branch") or "").strip() or (_git_text(cfg.repo_root, "branch", "--show-current") or "main")
    max_slots = max(1, min(10, int(cfg.max_parallel_workers or 1)))

    if not force_refresh and isinstance(payload, dict):
        rows = payload.get("workstations")
        if isinstance(rows, list) and rows:
            valid_rows = []
            for row in rows[:max_slots]:
                if not isinstance(row, dict):
                    continue
                branch_ok = str(row.get("branch") or "").strip().startswith(run_base_branch)
                worktree_raw = str(row.get("worktree") or "").strip()
                worktree_ok = bool(worktree_raw) and Path(worktree_raw).exists()
                if branch_ok and worktree_ok:
                    valid_rows.append(row)
            if len(valid_rows) == max_slots:
                return payload

    if cfg.dry_run:
        current_sha = _git_text(cfg.repo_root, "rev-parse", "HEAD") or ""
        rows = []
        for idx in range(1, max_slots + 1):
            rows.append(
                {
                    "workstation_id": f"workstation-{idx}",
                    "branch": f"{run_base_branch}-w{idx:02d}",
                    "worktree": str((cfg.repo_root / f"workstation-{idx}").resolve()),
                    "prepared_at": utc_now_iso(),
                    "status": "prepared",
                    "preparation_notes": "dry-run baseline",
                    "git_head_sha": current_sha,
                }
            )
        out = {
            "schema_version": SCHEMA_VERSION,
            "prepared_at": utc_now_iso(),
            "workstations": rows,
        }
        _atomic_write_json(target, out)
        _seed_worker_registry_from_workstations(cfg, rows, cycle_number=_load_cycle_counter(cfg))
        return out

    script = _resolve_workstation_prepare_script(cfg)
    if script is None:
        raise SimpleBuildError(
            "op_simple_workstation_prep_script_missing",
            "Cannot prepare workstations: workstation-preparation script is not available.",
        )

    prepared_rows: list[dict[str, Any]] = []
    failures: list[str] = []
    for idx in range(1, max_slots + 1):
        workstation_id = f"workstation-{idx}"
        worker_branch = f"{run_base_branch}-w{idx:02d}"
        cmd = [
            "python3",
            str(script),
            "--repo-root",
            str(cfg.repo_root),
            "--worktree-name",
            workstation_id,
            "--branch-name",
            worker_branch,
            "--base-ref",
            run_base_branch,
            "--worktrees-parent",
            str(cfg.repo_root),
            "--force-reset-existing",
            "--output",
            "json",
        ]
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(cfg.repo_root),
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except subprocess.TimeoutExpired:
            failures.append(f"{workstation_id}: prepare_workstation timeout")
            continue

        raw_out = (proc.stdout or "").strip()
        parsed: dict[str, Any] = {}
        if raw_out:
            try:
                parsed = json.loads(raw_out)
            except json.JSONDecodeError:
                parsed = {}

        ok = proc.returncode == 0 and bool(parsed.get("ok", True))
        if not ok:
            err_text = str(parsed.get("error") or "").strip()
            if not err_text:
                err_text = (proc.stderr or "").strip() or "prepare_workstation failed"
            failures.append(f"{workstation_id}: {err_text}")
            continue

        target_path = str(parsed.get("target_path") or (cfg.repo_root / workstation_id))
        resolved_branch = str(parsed.get("branch_name_resolved") or worker_branch)
        head_sha = _git_text(Path(target_path), "rev-parse", "HEAD") if target_path else ""
        prepared_rows.append(
            {
                "workstation_id": workstation_id,
                "branch": resolved_branch,
                "worktree": str(Path(target_path).resolve()) if target_path else "",
                "prepared_at": utc_now_iso(),
                "status": "prepared",
                "preparation_notes": str(parsed.get("message") or "prepared"),
                "git_head_sha": head_sha,
            }
        )

    if failures:
        raise SimpleBuildError(
            "op_simple_workstation_prep_failed",
            "Cannot prepare all workstation slots: " + "; ".join(failures),
        )

    out = {
        "schema_version": SCHEMA_VERSION,
        "prepared_at": utc_now_iso(),
        "workstations": prepared_rows,
    }
    _atomic_write_json(target, out)
    _seed_worker_registry_from_workstations(cfg, prepared_rows, cycle_number=_load_cycle_counter(cfg))
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
            "cycle_number": 0,
            "assignments": [],
        },
        "worker_packets": {
            "schema_version": SCHEMA_VERSION,
            "updated_at": utc_now_iso(),
            "cycle_number": 0,
            "packets": [],
        },
        "plan_packets": {
            "schema_version": SCHEMA_VERSION,
            "updated_at": utc_now_iso(),
            "cycle_number": 0,
            "phase": "multi-phase",
            "phases": [],
            "requirements": [],
            "tasks": [],
        },
        "task_execution_state": _task_execution_state_payload(0),
        "worker_registry": {
            "schema_version": SCHEMA_VERSION,
            "updated_at": utc_now_iso(),
            "cycle_number": 0,
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
        "wrapup_manager_report": {
            "schema_version": SCHEMA_VERSION,
            "updated_at": utc_now_iso(),
            "cycle_number": 0,
            "status": "not_started",
            "summary": "",
        },
        "watchdog_state": {
            "schema_version": SCHEMA_VERSION,
            "cycle_number": 0,
            "monitored_branch": "main",
            "last_commit_sha": "",
            "commit_ref": "main",
            "last_commit_at_utc": "",
            "last_commit_age_minutes": None,
            "stale_after_minutes": WATCHDOG_STALE_COMMIT_MINUTES,
            "stale": False,
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


def _reset_runtime_state_for_new_run(cfg: RunConfig) -> None:
    reset_keys = [
        "cycle_manager_decision",
        "profile_snapshot",
        "production_line_register",
        "worker_packets",
        "plan_packets",
        "task_execution_state",
        "worker_registry",
        "dispatch_registry",
        "cycle_summary",
        "wrapup_manager_report",
        "watchdog_state",
        "watchdog_exit_signal",
        "workstation_prep",
    ]
    for key in reset_keys:
        path = cfg.repo_root / ARTIFACT_FILES[key]
        _safe_unlink(path)
    _safe_unlink(cfg.repo_root / DISPATCH_LAUNCH_LOG_FILE)
    _safe_unlink(cfg.repo_root / BOSS_SESSION_STATE_FILE)


def _seed_plan_artifacts_from_planner(cfg: RunConfig) -> bool:
    current_plan_path = cfg.repo_root / ARTIFACT_FILES["plan_packets"]
    current_plan = _read_json(current_plan_path, default={})
    if isinstance(current_plan, dict):
        current_tasks = current_plan.get("tasks")
        if isinstance(current_tasks, list) and current_tasks:
            return False

    planner_path = cfg.repo_root / PLANNER_PLAN_PACKETS_FILE
    planner_payload = _read_json(planner_path, default={})
    if not isinstance(planner_payload, dict):
        return False
    planner_tasks = planner_payload.get("tasks")
    if not isinstance(planner_tasks, list) or not planner_tasks:
        return False

    plan_payload = dict(planner_payload)
    plan_payload["schema_version"] = SCHEMA_VERSION
    plan_payload["updated_at"] = utc_now_iso()
    _atomic_write_json(current_plan_path, plan_payload)

    task_state_path = cfg.repo_root / ARTIFACT_FILES["task_execution_state"]
    task_state = _read_json(task_state_path, default={})
    task_rows = task_state.get("tasks") if isinstance(task_state, dict) else None
    if not isinstance(task_rows, list) or not task_rows:
        task_payload = _task_execution_state_payload(
            _load_cycle_counter(cfg),
            [task for task in planner_tasks if isinstance(task, dict)],
        )
        _atomic_write_json(task_state_path, task_payload)
    return True


def _artifact_path_map(cfg: RunConfig) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, rel in ARTIFACT_FILES.items():
        out[key] = str((cfg.repo_root / rel).resolve())
    out["dispatch_launch_log"] = str((cfg.repo_root / DISPATCH_LAUNCH_LOG_FILE).resolve())
    out["manager_call_log"] = str((cfg.repo_root / MANAGER_CALL_LOG_FILE).resolve())
    out["boss_evidence"] = str((cfg.repo_root / BOSS_EVIDENCE_FILE).resolve())
    out["boss_session_state"] = str((cfg.repo_root / BOSS_SESSION_STATE_FILE).resolve())
    out["app_lifecycle"] = str((cfg.repo_root / APP_LIFECYCLE_FILE).resolve())
    out["terminate_file"] = str((cfg.repo_root / TERMINATE_FILE_NAME).resolve())
    return out


def _manager_prompt_base_dirs(cfg: RunConfig) -> list[Path]:
    candidates = [
        cfg.repo_root / "scripts" / "op_simple" / "prompts" / "managers",
        SCRIPTS_ROOT / "op_simple" / "prompts" / "managers",
    ]
    deduped: list[Path] = []
    seen: set[str] = set()
    for item in candidates:
        key = str(item.resolve())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _manager_prompt_template_path(cfg: RunConfig, manager_name: str) -> Path:
    slug = manager_name.lower().replace(" ", "-")
    candidates = [base / f"{slug}.md" for base in _manager_prompt_base_dirs(cfg)]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def _schema_catalog_path(cfg: RunConfig) -> Path:
    candidates = [
        cfg.repo_root / "docs" / "plans" / "OP_SIMPLE_SCHEMA_CATALOG_V2.md",
        SCRIPTS_ROOT.parent / "docs" / "plans" / "OP_SIMPLE_SCHEMA_CATALOG_V2.md",
    ]
    for path in candidates:
        if path.exists():
            return path.resolve()
    return candidates[0].resolve()


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
    *,
    codex_home: str | None = None,
    resume_session_id: str | None = None,
    model: str | None = None,
    reasoning_effort: str | None = None,
) -> ManagerResult:
    started_at = utc_now_iso()
    start_time = time.monotonic()
    cycle_dir = _ensure_history_cycle_dir(cfg, cycle_number)
    safe_name = manager_name.lower().replace(" ", "-")
    stdout_path = cycle_dir / f"manager-{safe_name}.stdout.log"
    stderr_path = cycle_dir / f"manager-{safe_name}.stderr.log"
    last_message_path = cycle_dir / f"manager-{safe_name}.last_message.txt"

    reasoning_effort_text = str(reasoning_effort or "").strip()
    model_text = str(model or "").strip()
    if resume_session_id:
        cmd = [
            "codex",
            "exec",
            "resume",
            "--dangerously-bypass-approvals-and-sandbox",
        ]
        if model_text:
            cmd.extend(["--model", model_text])
        if reasoning_effort_text:
            cmd.extend(["-c", f'model_reasoning_effort="{reasoning_effort_text}"'])
        cmd.extend(
            [
                "--output-last-message",
                str(last_message_path),
                str(resume_session_id),
                "-",
            ]
        )
    else:
        cmd = [
            "codex",
            "exec",
            "--dangerously-bypass-approvals-and-sandbox",
        ]
        if model_text:
            cmd.extend(["--model", model_text])
        if reasoning_effort_text:
            cmd.extend(["-c", f'model_reasoning_effort="{reasoning_effort_text}"'])
        cmd.extend(
            [
                "--cd",
                str(cfg.repo_root),
                "--output-last-message",
                str(last_message_path),
                "-",
            ]
        )

    env = None
    codex_home_text = (codex_home or "").strip()
    if codex_home_text:
        env = os.environ.copy()
        env["CODEX_HOME"] = codex_home_text

    try:
        completed = subprocess.run(
            cmd,
            cwd=str(cfg.repo_root),
            input=prompt_text,
            text=True,
            capture_output=True,
            timeout=max(1, int(timeout_seconds)),
            check=False,
            env=env,
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
            reason_code=None if completed.returncode == 0 else "manager_non_zero_exit",
            session_id=_extract_session_id(completed.stdout or "", completed.stderr or ""),
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
            reason_code="manager_timeout",
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
            reason_code="manager_binary_missing",
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
    if len(rows) > 1:
        rows = [row for row in rows if str(row.get("alias") or "").strip() != "codex"]
    return rows


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
            "blockers": [],
            "attempts": _default_attempts(),
            "last_handoff_outcome": _default_last_handoff_outcome(),
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


def _write_wrapup_stub(cfg: RunConfig, cycle_number: int) -> None:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "updated_at": utc_now_iso(),
        "cycle_number": cycle_number,
        "status": "dry_run",
        "stop_reason": "project_done",
        "run_base_branch": str((_read_json(cfg.repo_root / INITIALIZE_STATE_FILE, default={}).get("run_context") or {}).get("run_base_branch") or ""),
        "app_lifecycle_path": str((cfg.repo_root / APP_LIFECYCLE_FILE).resolve()),
        "summary": "dry run wrapup manager report",
    }
    _atomic_write_json(cfg.repo_root / ARTIFACT_FILES["wrapup_manager_report"], payload)


def _validate_manager_artifacts(
    cfg: RunConfig,
    manager_name: str,
    expected_artifacts: list[str],
    cycle_number: int,
) -> tuple[str | None, str | None, dict[str, Any] | None]:
    for artifact_key in expected_artifacts:
        artifact_path = cfg.repo_root / ARTIFACT_FILES[artifact_key]
        if not artifact_path.exists():
            code = "boss_missing_artifact" if manager_name == "BOSS" else "manager_missing_artifact"
            return (
                code,
                f"missing expected artifact: {artifact_key}",
                {"artifact_key": artifact_key},
            )
        if manager_name != "BOSS":
            continue
        payload = _read_json(artifact_path, default=None)
        if not isinstance(payload, dict):
            return (
                "boss_invalid_artifact",
                f"required BOSS artifact is not a JSON object: {artifact_key}",
                {"artifact_key": artifact_key},
            )
        try:
            artifact_cycle_number = int(payload.get("cycle_number"))
        except (TypeError, ValueError):
            artifact_cycle_number = None
        if artifact_cycle_number != cycle_number:
            return (
                "boss_stale_artifact",
                f"required BOSS artifact has stale or missing cycle_number: {artifact_key}",
                {"artifact_key": artifact_key, "cycle_number": artifact_cycle_number},
            )
    return None, None, None


def _write_cycle_manager_decision(
    cfg: RunConfig,
    cycle_number: int,
    *,
    decision: str,
    reason_code: str,
    message: str,
    worker_registry_ready: bool,
) -> None:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "cycle_number": cycle_number,
        "decision": decision,
        "reason_code": reason_code,
        "message": message,
        "worker_registry_ready": worker_registry_ready,
    }
    _atomic_write_json(cfg.repo_root / ARTIFACT_FILES["cycle_manager_decision"], payload)


def _invoke_manager(
    cfg: RunConfig,
    *,
    manager_name: str,
    cycle_number: int,
    context: dict[str, Any],
    expected_artifacts: list[str],
) -> ManagerResult:
    manager_uses_boss_profile = manager_name in {"BOSS", "wrapup-manager"}
    manager_uses_boss_model = manager_name in {"BOSS", "wrapup-manager"}
    if cfg.dry_run:
        if manager_name == "BOSS":
            _write_boss_stub(cfg, cycle_number)
        if manager_name == "wrapup-manager":
            _write_wrapup_stub(cfg, cycle_number)
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
        selected_manager_alias: str | None = None
        selected_manager_home: str | None = None
        resume_session_id: str | None = None
        prior_profile_alias: str | None = None
        prior_previous_profile_alias: str | None = None
        if manager_uses_boss_profile:
            boss_session_state = _read_boss_session_state(cfg)
            prior_session_id = str(boss_session_state.get("session_id") or "").strip() or None
            prior_profile_alias = str(boss_session_state.get("profile_alias") or "").strip() or None
            prior_previous_profile_alias = str(boss_session_state.get("previous_profile_alias") or "").strip() or None
            selected_manager_alias, selected_manager_home = _select_boss_profile_from_snapshot(
                cfg,
                preferred_alias=prior_profile_alias,
            )
            if not selected_manager_home:
                selected_manager_home = str(boss_session_state.get("codex_home") or "").strip() or None
            if manager_name == "BOSS" and prior_session_id and selected_manager_alias and prior_profile_alias:
                profile_matches = selected_manager_alias == prior_profile_alias
                previous_profile_matches = (
                    prior_previous_profile_alias in {None, "", prior_profile_alias}
                    or selected_manager_alias == prior_previous_profile_alias
                )
                if profile_matches and previous_profile_matches:
                    resume_session_id = prior_session_id
                else:
                    resume_session_id = None
        packet = {
            "schema_version": SCHEMA_VERSION,
            "manager": manager_name,
            "cycle_number": cycle_number,
            "context": context,
            "artifact_paths": path_map,
            "validator_paths": {
                "op_simple_schema_catalog": str(_schema_catalog_path(cfg)),
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
        result = _codex_exec_prompt(
            cfg,
            manager_name,
            cycle_number,
            timeout,
            prompt_text,
            codex_home=selected_manager_home,
            resume_session_id=resume_session_id,
            model=cfg.boss_model if manager_uses_boss_model else None,
            reasoning_effort=cfg.boss_reasoning_effort if manager_uses_boss_model else None,
        )
        if manager_name == "BOSS" and resume_session_id and result.status == "failed" and not result.timeout:
            retry = _codex_exec_prompt(
                cfg,
                manager_name,
                cycle_number,
                timeout,
                prompt_text,
                codex_home=selected_manager_home,
                resume_session_id=None,
                model=cfg.boss_model,
                reasoning_effort=cfg.boss_reasoning_effort,
            )
            if retry.status == "ok":
                result = retry
                result.message = "fresh_session_retry_after_resume_failure"
            else:
                result.message = (
                    f"{result.message or 'resume_failed'}; fresh_session_retry_failed"
                    if result.message
                    else "fresh_session_retry_failed"
                )
        if manager_name == "BOSS" and result.status == "ok":
            persisted_session_id = str(result.session_id or resume_session_id or "").strip()
            if persisted_session_id:
                switched_profile = bool(
                    selected_manager_alias and prior_profile_alias and selected_manager_alias != prior_profile_alias
                )
                previous_profile_alias = (
                    prior_profile_alias
                    if switched_profile
                    else selected_manager_alias or prior_profile_alias or ""
                )
                _write_boss_session_state(
                    cfg,
                    session_id=persisted_session_id,
                    codex_home=selected_manager_home,
                    profile_alias=selected_manager_alias,
                    previous_profile_alias=previous_profile_alias,
                )
        if manager_name == "BOSS" and result.status != "ok":
            _safe_unlink(cfg.repo_root / BOSS_SESSION_STATE_FILE)
        if selected_manager_alias:
            result.message = (
                f"{result.message}; manager_profile_alias={selected_manager_alias}"
                if result.message
                else f"manager_profile_alias={selected_manager_alias}"
            )

    if result.status == "ok":
        reason_code, message, details = _validate_manager_artifacts(cfg, manager_name, expected_artifacts, cycle_number)
        if reason_code:
            result.status = "failed"
            result.reason_code = reason_code
            result.message = message
            result.details = details

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
            "session_id": result.session_id,
            "message": result.message,
        },
    )
    return result


def _read_cycle_decision(cfg: RunConfig) -> dict[str, Any]:
    payload = _read_json(cfg.repo_root / ARTIFACT_FILES["cycle_manager_decision"], default={})
    if not isinstance(payload, dict):
        return {}
    return payload


def _parse_iso_datetime(raw: str) -> datetime | None:
    text = (raw or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _extract_remaining_percent(window: Any) -> float | None:
    if not isinstance(window, dict):
        return None
    for key in ("remaining_percent", "remaining_pct", "remaining"):
        value = window.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    return None


def _select_boss_profile_from_snapshot(cfg: RunConfig, *, preferred_alias: str | None = None) -> tuple[str | None, str | None]:
    payload = _read_json(cfg.repo_root / ARTIFACT_FILES["profile_snapshot"], default={})
    if not isinstance(payload, dict):
        return None, None
    rows = payload.get("profiles")
    if not isinstance(rows, list):
        return None, None

    candidate_rows = [row for row in rows if isinstance(row, dict)]
    if len(candidate_rows) > 1:
        candidate_rows = [row for row in candidate_rows if str(row.get("alias") or "").strip() != "codex"]

    ranked: list[tuple[float, float, str, str]] = []
    for row in candidate_rows:
        alias = str(row.get("alias") or "").strip()
        codex_home = str(row.get("codex_home") or "").strip()
        if not alias or not codex_home:
            continue
        if bool(row.get("hard_gated")):
            continue

        five_hour_remaining = _extract_remaining_percent(row.get("window_5h_remaining_pct"))
        if five_hour_remaining is None:
            try:
                five_hour_remaining = float(row.get("window_5h_remaining_pct"))
            except (TypeError, ValueError):
                five_hour_remaining = None
        if five_hour_remaining is None and isinstance(row.get("five_hour"), dict):
            five_hour_remaining = _extract_remaining_percent(row.get("five_hour"))
        if five_hour_remaining is None or five_hour_remaining <= 1.0:
            continue

        week_remaining = _extract_remaining_percent(row.get("window_week_remaining_pct"))
        if week_remaining is None:
            try:
                week_remaining = float(row.get("window_week_remaining_pct"))
            except (TypeError, ValueError):
                week_remaining = None
        if week_remaining is None and isinstance(row.get("weekly"), dict):
            week_remaining = _extract_remaining_percent(row.get("weekly"))
        if week_remaining is None:
            continue

        ranked.append((week_remaining, five_hour_remaining, alias, codex_home))

    if not ranked:
        return None, None

    preferred_alias_text = str(preferred_alias or "").strip()
    if preferred_alias_text:
        for week_remaining, _five_hour_remaining, alias, codex_home in ranked:
            if alias == preferred_alias_text and week_remaining >= 50.0:
                return alias, codex_home

    ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))
    _week_remaining, _five_hour_remaining, alias, codex_home = ranked[0]
    return alias, codex_home


def _resolve_rate_snapshot_script(cfg: RunConfig) -> Path | None:
    codex_home = os.environ.get("CODEX_HOME")
    candidates: list[Path] = []
    candidates.append(cfg.repo_root / RATE_SNAPSHOT_SCRIPT_REL)
    candidates.append(SCRIPTS_ROOT.parent / RATE_SNAPSHOT_SCRIPT_REL)
    if codex_home:
        candidates.append(Path(codex_home).expanduser() / RATE_SNAPSHOT_SCRIPT_REL)
    candidates.append(Path.home() / ".codex" / RATE_SNAPSHOT_SCRIPT_REL)

    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        if candidate.exists():
            return candidate.resolve()
    return None


def _rate_snapshot_profile_args() -> list[str]:
    rows = _profile_rows_from_disk()
    args: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        alias = str(row.get("alias") or "").strip()
        if not alias or alias in seen:
            continue
        seen.add(alias)
        if alias == "codex":
            args.append("codex=default")
            continue
        codex_home = str(row.get("codex_home") or "").strip()
        if not codex_home:
            continue
        args.append(f"{alias}={codex_home}")
    if not args:
        args.append("codex=default")
    return args


def _profile_rows_from_rate_snapshot_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    profiles = payload.get("profiles")
    profile_rows: list[tuple[str, dict[str, Any]]] = []
    if isinstance(profiles, dict):
        for alias, row in profiles.items():
            if isinstance(row, dict):
                profile_rows.append((str(alias), row))
    elif isinstance(profiles, list):
        for idx, row in enumerate(profiles):
            if not isinstance(row, dict):
                continue
            alias = str(row.get("alias") or f"profile-{idx + 1}")
            profile_rows.append((alias, row))

    out: list[dict[str, Any]] = []
    for alias, row in profile_rows:
        alias_text = (alias or "").strip() or str(row.get("alias") or "").strip()
        if not alias_text:
            continue
        five = row.get("five_hour") if isinstance(row.get("five_hour"), dict) else {}
        weekly = row.get("weekly") if isinstance(row.get("weekly"), dict) else {}
        five_remaining = _extract_remaining_percent(five)
        week_remaining = _extract_remaining_percent(weekly)
        recommended = str(row.get("recommended_action") or "").strip().lower()
        hard_gated = bool(
            row.get("hard_gated")
            or row.get("gated")
            or five.get("gated")
            or weekly.get("gated")
        )
        if recommended in {"wait_until_reset", "wind_down"}:
            hard_gated = True
        if row.get("eligible_for_new_work") is False:
            hard_gated = True
        if (five_remaining is not None and five_remaining <= 1.0) or (week_remaining is not None and week_remaining <= 1.0):
            hard_gated = True
        soft_gated = bool(row.get("soft_concurrency_gated"))
        if (five_remaining is not None and five_remaining <= 5.0) or (week_remaining is not None and week_remaining <= 5.0):
            soft_gated = True

        reset_at = (
            str(row.get("reset_at") or "").strip()
            or str(row.get("next_reset_at") or "").strip()
            or str(five.get("reset_at") or five.get("resets_at") or five.get("resetAt") or "").strip()
            or str(weekly.get("reset_at") or weekly.get("resets_at") or weekly.get("resetAt") or "").strip()
        )
        if not reset_at:
            reset_at = None

        out.append(
            {
                "alias": alias_text,
                "codex_home": str(row.get("codex_home") or "").strip(),
                "window_5h_remaining_pct": five_remaining,
                "window_week_remaining_pct": week_remaining,
                "hard_gated": hard_gated,
                "soft_gated": soft_gated,
                "reset_at": reset_at,
                "recommended_action": recommended or None,
            }
        )
    return out


def _refresh_profile_snapshot_via_skill(cfg: RunConfig, cycle_number: int) -> tuple[bool, str]:
    script = _resolve_rate_snapshot_script(cfg)
    if script is None:
        return False, "codex-rate-snapshot script not found"

    cmd: list[str] = ["python3", str(script)]
    for arg in _rate_snapshot_profile_args():
        cmd.extend(["--profile", arg])
    cmd.append("--json-pretty")

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cfg.repo_root),
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, "codex-rate-snapshot timed out"

    if proc.returncode != 0:
        err = (proc.stderr or "").strip() or (proc.stdout or "").strip() or "unknown error"
        return False, f"codex-rate-snapshot failed: {err}"

    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        return False, f"codex-rate-snapshot emitted invalid JSON: {exc}"
    if not isinstance(payload, dict):
        return False, "codex-rate-snapshot output must be a JSON object"

    rows = _profile_rows_from_rate_snapshot_payload(payload)
    if not rows:
        return False, "codex-rate-snapshot returned no usable profile rows"

    snapshot_payload = {
        "schema_version": SCHEMA_VERSION,
        "updated_at": utc_now_iso(),
        "cycle_number": cycle_number,
        "source": "codex-rate-snapshot",
        "generated_at": str(payload.get("generated_at") or ""),
        "profiles": rows,
    }
    _atomic_write_json(cfg.repo_root / ARTIFACT_FILES["profile_snapshot"], snapshot_payload)
    return True, f"profile snapshot refreshed via codex-rate-snapshot ({len(rows)} profiles)"


def _profiles_all_hard_gated(cfg: RunConfig) -> bool:
    return _profile_snapshot_gate_state(cfg) == "all_hard_gated"


def _profile_snapshot_gate_state(cfg: RunConfig) -> str:
    payload = _read_json(cfg.repo_root / ARTIFACT_FILES["profile_snapshot"], default={})
    if not isinstance(payload, dict):
        return "unknown"
    rows = payload.get("profiles")
    if not isinstance(rows, list) or not rows:
        return "unknown"
    has_row = False
    for row in rows:
        if not isinstance(row, dict):
            continue
        has_row = True
        if not bool(row.get("hard_gated")):
            return "has_ungated"
    if not has_row:
        return "unknown"
    return "all_hard_gated"


def _refresh_rate_gate_snapshot(cfg: RunConfig) -> bool:
    snapshot_path = cfg.repo_root / ARTIFACT_FILES["profile_snapshot"]
    payload = _read_json(snapshot_path, default={})
    if not isinstance(payload, dict):
        return False
    rows = payload.get("profiles")
    if not isinstance(rows, list):
        return False

    now = datetime.now(timezone.utc)
    changed = False
    for row in rows:
        if not isinstance(row, dict):
            continue
        if not bool(row.get("hard_gated")):
            continue
        reset_at = _parse_iso_datetime(str(row.get("reset_at") or ""))
        if reset_at is None or reset_at > now:
            continue
        row["hard_gated"] = False
        if "soft_gated" in row:
            row["soft_gated"] = False
        changed = True

    if changed:
        payload["schema_version"] = SCHEMA_VERSION
        payload["updated_at"] = utc_now_iso()
        _atomic_write_json(snapshot_path, payload)
    return changed


def _run_rate_gate_wait(cfg: RunConfig, cycle_number: int, warnings: list[dict[str, Any]]) -> None:
    if cfg.dry_run:
        return
    refreshed, refresh_message = _refresh_profile_snapshot_via_skill(cfg, cycle_number)
    entry_returncode = 0 if refreshed else 1
    if not refreshed:
        fallback_refreshed = _refresh_rate_gate_snapshot(cfg)
        if fallback_refreshed:
            refresh_message = f"{refresh_message}; fallback reset_at refresh applied"
            entry_returncode = 0
    _append_manager_log(
        cfg,
        {
            "schema_version": SCHEMA_VERSION,
            "cycle_number": cycle_number,
            "manager": "rate-gate",
            "status": "entry_rescan",
            "timeout": False,
            "returncode": entry_returncode,
            "started_at": utc_now_iso(),
            "finished_at": utc_now_iso(),
            "duration_seconds": 0,
            "message": refresh_message,
        },
    )
    if not refreshed:
        warnings.append(
            {
                "code": "rate_gate_snapshot_refresh_failed",
                "message": refresh_message,
                "stage": "op-simple-build",
            }
        )
    gate_state = _profile_snapshot_gate_state(cfg)
    if gate_state == "has_ungated":
        return
    if gate_state == "unknown":
        warnings.append(
            {
                "code": "rate_gate_snapshot_unknown",
                "message": "profile snapshot gating state is unknown; entering conservative rate-gate wait",
                "stage": "op-simple-build",
            }
        )

    next_heartbeat = time.monotonic()
    next_rescan = time.monotonic()
    while True:
        gate_state = _profile_snapshot_gate_state(cfg)
        if gate_state == "has_ungated":
            return
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
            refreshed, message = _refresh_profile_snapshot_via_skill(cfg, cycle_number)
            rescan_returncode = 0 if refreshed else 1
            if not refreshed:
                fallback_refreshed = _refresh_rate_gate_snapshot(cfg)
                if fallback_refreshed:
                    message = f"{message}; fallback reset_at refresh applied"
                    rescan_returncode = 0
                else:
                    warnings.append(
                        {
                            "code": "rate_gate_snapshot_refresh_failed",
                            "message": message,
                            "stage": "op-simple-build",
                        }
                    )
            _append_manager_log(
                cfg,
                {
                    "schema_version": SCHEMA_VERSION,
                    "cycle_number": cycle_number,
                    "manager": "rate-gate",
                    "status": "rescan",
                    "timeout": False,
                    "returncode": rescan_returncode,
                    "started_at": utc_now_iso(),
                    "finished_at": utc_now_iso(),
                    "duration_seconds": 0,
                    "message": message,
                },
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


def _worker_registry_index(cfg: RunConfig) -> dict[str, dict[str, Any]]:
    payload = _read_json(cfg.repo_root / ARTIFACT_FILES["worker_registry"], default={})
    if not isinstance(payload, dict):
        return {}
    rows = payload.get("workers")
    if not isinstance(rows, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        worker_id = str(row.get("worker_id") or "").strip()
        if worker_id:
            out[worker_id] = row
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


def _coerce_pid(pid_value: Any) -> int | None:
    try:
        pid_int = int(pid_value)
    except (TypeError, ValueError):
        return None
    if pid_int <= 0:
        return None
    return pid_int


def _is_pid_alive(pid_value: Any) -> bool:
    pid_int = _coerce_pid(pid_value)
    if pid_int is None:
        return False
    try:
        os.kill(pid_int, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _normalize_dead_worker_leases(cfg: RunConfig, cycle_number: int) -> dict[str, int]:
    registry_path = cfg.repo_root / ARTIFACT_FILES["worker_registry"]
    registry_payload = _read_json(registry_path, default={})
    if not isinstance(registry_payload, dict):
        return {"reclaimed_workers": 0, "requeued_tasks": 0}
    workers = registry_payload.get("workers")
    if not isinstance(workers, list):
        return {"reclaimed_workers": 0, "requeued_tasks": 0}

    now_iso = utc_now_iso()
    reclaimed_workers = 0

    for row in workers:
        if not isinstance(row, dict):
            continue
        pid_int = _coerce_pid(row.get("pid"))
        if pid_int is None or _is_pid_alive(pid_int):
            continue

        reclaimed_workers += 1

        # Dead PID only indicates runtime marker expiry; preserve assignment context for BOSS reconciliation.
        row["pid"] = None
        row["last_update"] = now_iso

    if reclaimed_workers:
        registry_payload["schema_version"] = SCHEMA_VERSION
        registry_payload["updated_at"] = now_iso
        try:
            previous_cycle = int(registry_payload.get("cycle_number") or 0)
        except (TypeError, ValueError):
            previous_cycle = 0
        registry_payload["cycle_number"] = max(previous_cycle, int(cycle_number))
        registry_payload["workers"] = workers
        _atomic_write_json(registry_path, registry_payload)

    requeued_tasks = 0

    if reclaimed_workers or requeued_tasks:
        print(
            "[op-simple-build] "
            f"[{utc_now_iso()}] "
            f"cycle={cycle_number} reclaimed_dead_workers={reclaimed_workers} "
            f"requeued_in_progress_tasks={requeued_tasks}",
            flush=True,
        )

    return {
        "reclaimed_workers": reclaimed_workers,
        "requeued_tasks": requeued_tasks,
    }


def _active_worker_count(cfg: RunConfig) -> int:
    payload = _read_json(cfg.repo_root / ARTIFACT_FILES["worker_registry"], default={})
    if not isinstance(payload, dict):
        return 0
    workers = payload.get("workers")
    if not isinstance(workers, list):
        return 0
    active_count = 0
    for row in workers:
        if not isinstance(row, dict):
            continue
        pid = _coerce_pid(row.get("pid"))
        thread_id = row.get("thread_id")
        has_live_marker = False
        if pid is not None:
            has_live_marker = _is_pid_alive(pid)
        elif isinstance(thread_id, str) and bool(thread_id.strip()):
            has_live_marker = True
        # Count only workers with concrete runtime liveness markers so
        # pre-dispatch "in_progress" placeholders do not consume capacity.
        if has_live_marker:
            active_count += 1
    return active_count


def _task_counts_from_execution_state(cfg: RunConfig) -> dict[str, int]:
    counts = {"pending": 0, "in_progress": 0, "done": 0, "blocked": 0}
    payload = _read_json(cfg.repo_root / ARTIFACT_FILES["task_execution_state"], default={})
    tasks = payload.get("tasks") if isinstance(payload, dict) else None
    if not isinstance(tasks, list):
        return counts
    for row in tasks:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "").strip()
        if status in counts:
            counts[status] += 1
    return counts


def _worker_task_state_signature(cfg: RunConfig) -> tuple[str, int]:
    worker_payload = _read_json(cfg.repo_root / ARTIFACT_FILES["worker_registry"], default={})
    worker_rows = worker_payload.get("workers") if isinstance(worker_payload, dict) else None
    normalized_workers: list[dict[str, Any]] = []
    in_progress_workers = 0
    if isinstance(worker_rows, list):
        for row in worker_rows:
            if not isinstance(row, dict):
                continue
            status = str(row.get("status") or "").strip()
            if status == "in_progress":
                in_progress_workers += 1
            normalized_workers.append(
                {
                    "worker_id": str(row.get("worker_id") or "").strip(),
                    "status": status,
                    "pid": _coerce_pid(row.get("pid")),
                    "thread_id": str(row.get("thread_id") or "").strip(),
                    "current_task_id": str(row.get("current_task_id") or "").strip(),
                    "current_packet_id": str(row.get("current_packet_id") or "").strip(),
                    "current_task_profile": str(row.get("current_task_profile") or "").strip(),
                    "next_task_profile": str(row.get("next_task_profile") or "").strip(),
                }
            )
    normalized_workers.sort(key=lambda item: item.get("worker_id") or "")

    task_payload = _read_json(cfg.repo_root / ARTIFACT_FILES["task_execution_state"], default={})
    task_rows = task_payload.get("tasks") if isinstance(task_payload, dict) else None
    normalized_tasks: list[dict[str, str]] = []
    if isinstance(task_rows, list):
        for row in task_rows:
            if not isinstance(row, dict):
                continue
            normalized_tasks.append(
                {
                    "task_id": str(row.get("task_id") or "").strip(),
                    "status": str(row.get("status") or "").strip(),
                    "assigned_worker": str(row.get("assigned_worker") or "").strip(),
                    "assigned_profile": str(row.get("assigned_profile") or "").strip(),
                }
            )
    normalized_tasks.sort(key=lambda item: item.get("task_id") or "")

    digest_payload = {"workers": normalized_workers, "tasks": normalized_tasks}
    digest = hashlib.sha256(
        json.dumps(digest_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return digest, in_progress_workers


def _watchdog_near_idle_threshold(cfg: RunConfig) -> bool:
    payload = _read_json(cfg.repo_root / ARTIFACT_FILES["watchdog_state"], default={})
    if not isinstance(payload, dict):
        return False
    try:
        age_minutes = float(payload.get("last_commit_age_minutes"))
    except (TypeError, ValueError):
        return False
    try:
        stale_after_minutes = int(payload.get("stale_after_minutes") or WATCHDOG_STALE_COMMIT_MINUTES)
    except (TypeError, ValueError):
        stale_after_minutes = WATCHDOG_STALE_COMMIT_MINUTES
    if stale_after_minutes <= 0:
        stale_after_minutes = WATCHDOG_STALE_COMMIT_MINUTES
    near_threshold = stale_after_minutes - WATCHDOG_NEAR_STALE_MARGIN_MINUTES
    if near_threshold < 0:
        near_threshold = 0
    return age_minutes >= float(near_threshold)


def _dispatch_packets(cfg: RunConfig, cycle_number: int) -> dict[str, int]:
    counters = {"attempted": 0, "launched": 0, "launch_failed": 0, "unknown": 0}
    packets = _load_worker_packets(cfg)
    if not packets:
        return counters

    script = _resolve_dispatch_script(cfg)
    alias_to_home = _profile_alias_to_home(cfg)
    worker_by_id = _worker_registry_index(cfg)
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
        worker_row = worker_by_id.get(worker_id) if worker_id else None
        worker_worktree_raw = str((worker_row or {}).get("worktree") or "").strip()
        worker_worktree = Path(worker_worktree_raw).expanduser() if worker_worktree_raw else None

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

        if worker_worktree is None or not worker_worktree.exists() or not worker_worktree.is_dir():
            event["status"] = "launch_failed"
            event["message"] = "worker worktree missing or invalid"
            counters["launch_failed"] += 1
            event_rows.append(event)
            _append_jsonl(cfg.repo_root / DISPATCH_LAUNCH_LOG_FILE, event)
            continue

        cmd = [
            "python3",
            str(script),
            "--cwd",
            str(worker_worktree.resolve()),
            "--prompt",
            prompt,
            "--background",
            "--no-full-auto",
            "--extra-arg=--dangerously-bypass-approvals-and-sandbox",
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

    commit_ref = monitored_branch
    current_sha = _git_text(cfg.repo_root, "rev-parse", commit_ref)
    if not current_sha:
        commit_ref = "HEAD"
        current_sha = _git_text(cfg.repo_root, "rev-parse", commit_ref)
    commit_epoch = _git_commit_epoch_seconds(cfg.repo_root, commit_ref)
    now_utc = datetime.now(timezone.utc)
    commit_age_minutes: float | None = None
    last_commit_at_utc = ""
    if commit_epoch is not None:
        last_commit_at = datetime.fromtimestamp(commit_epoch, timezone.utc)
        last_commit_at_utc = last_commit_at.strftime("%Y-%m-%dT%H:%M:%SZ")
        commit_age_minutes = max(0.0, (now_utc.timestamp() - float(commit_epoch)) / 60.0)

    state_path = cfg.repo_root / ARTIFACT_FILES["watchdog_state"]
    state = _read_json(state_path, default={})
    if not isinstance(state, dict):
        state = {}

    stale_after_minutes = WATCHDOG_STALE_COMMIT_MINUTES
    if commit_age_minutes is None:
        is_stale = False
    else:
        is_stale = commit_age_minutes > float(stale_after_minutes)

    next_state = {
        "schema_version": SCHEMA_VERSION,
        "cycle_number": cycle_number,
        "monitored_branch": monitored_branch,
        "commit_ref": commit_ref,
        "last_commit_sha": current_sha,
        "last_commit_at_utc": last_commit_at_utc,
        "last_commit_age_minutes": round(commit_age_minutes, 3) if commit_age_minutes is not None else None,
        "stale_after_minutes": stale_after_minutes,
        "stale": is_stale,
    }
    _atomic_write_json(state_path, next_state)

    if commit_age_minutes is None:
        exit_signal = {
            "schema_version": SCHEMA_VERSION,
            "cycle_number": cycle_number,
            "reason_code": "watchdog_commit_age_unknown",
            "message": f"unable to resolve commit age for monitored branch '{monitored_branch}'",
            "monitored_branch": monitored_branch,
            "commit_ref": commit_ref,
            "stale_after_minutes": stale_after_minutes,
            "commit_age_minutes": None,
        }
    else:
        exit_signal = {
            "schema_version": SCHEMA_VERSION,
            "cycle_number": cycle_number,
            "reason_code": "stale_base_branch_commit",
            "message": (
                f"latest commit on '{monitored_branch}' is {commit_age_minutes:.1f} minutes old; "
                f"watchdog limit is {stale_after_minutes} minutes"
            ),
            "monitored_branch": monitored_branch,
            "commit_ref": commit_ref,
            "last_commit_sha": current_sha,
            "last_commit_at_utc": last_commit_at_utc,
            "stale_after_minutes": stale_after_minutes,
            "commit_age_minutes": round(commit_age_minutes, 3),
        }

    should_stop = is_stale
    exit_path = cfg.repo_root / ARTIFACT_FILES["watchdog_exit_signal"]
    if should_stop:
        _atomic_write_json(exit_path, exit_signal)
    else:
        _safe_unlink(exit_path)

    return should_stop, exit_signal


def _run_wrapup_manager(
    cfg: RunConfig,
    *,
    cycle_number: int,
    stop_reason: str,
    init_state: dict[str, Any],
    warnings: list[dict[str, Any]],
) -> None:
    run_context = init_state.get("run_context") if isinstance(init_state, dict) else {}
    if not isinstance(run_context, dict):
        run_context = {}
    context = {
        "stop_reason": stop_reason,
        "run_base_branch": str(run_context.get("run_base_branch") or ""),
        "run_base_from_branch": str(run_context.get("run_base_from_branch") or ""),
        "run_base_from_commit": str(run_context.get("run_base_from_commit") or ""),
        "app_lifecycle_path": str((cfg.repo_root / APP_LIFECYCLE_FILE).resolve()),
        "app_lifecycle_active_era_id": _active_lifecycle_era_id(cfg),
    }
    result = _invoke_manager(
        cfg,
        manager_name="wrapup-manager",
        cycle_number=cycle_number,
        context=context,
        expected_artifacts=["wrapup_manager_report"],
    )
    if result.status != "ok":
        warnings.append(
            {
                "code": result.reason_code or "wrapup_manager_failed",
                "message": result.message or "wrapup-manager failed",
                "stage": "op-simple-build",
            }
        )
    trace_event = _build_wrapup_trace_event(
        cfg,
        cycle_number=cycle_number,
        stop_reason=stop_reason,
        run_context=run_context,
        result=result,
    )
    _emit_trace_event_envelope(
        cfg,
        cycle_number=cycle_number,
        payload=trace_event,
    )


def _render_cycle_summary(
    cfg: RunConfig,
    cycle_number: int,
    manager_statuses: dict[str, dict[str, str]],
    dispatch_counts: dict[str, int],
    *,
    base_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary_path = cfg.repo_root / ARTIFACT_FILES["cycle_summary"]
    summary = base_summary if isinstance(base_summary, dict) else _read_json(summary_path, default={})
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
        f"[{utc_now_iso()}] "
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
            normalized_reason = reason.strip()
            if normalized_reason not in NON_TERMINAL_STOP_REASONS:
                return normalized_reason
    stop_reason = summary.get("stop_reason")
    if isinstance(stop_reason, str) and stop_reason.strip():
        normalized_stop_reason = stop_reason.strip()
        if normalized_stop_reason not in NON_TERMINAL_STOP_REASONS:
            return normalized_stop_reason
    return None


def _snapshot_cycle(cfg: RunConfig, cycle_number: int) -> None:
    cycle_dir = _ensure_history_cycle_dir(cfg, cycle_number)
    for rel in [*ARTIFACT_FILES.values(), MANAGER_CALL_LOG_FILE, DISPATCH_LAUNCH_LOG_FILE, TRACE_EVENT_LOG_FILE, CYCLE_COUNTER_FILE]:
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
    sleep_minutes_raw = getattr(req, "sleep_minutes", None)
    if sleep_minutes_raw is None:
        sleep_minutes = 5.0
    else:
        sleep_minutes = float(sleep_minutes_raw)
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
    command = str(getattr(req, "command", "") or "").strip().lower()
    resume_mode = command == "op-resume"
    run_base_source_branch = str(getattr(req, "run_base_source_branch", "") or "").strip() or "main"
    boss_model = str(getattr(req, "boss_model", "") or "").strip() or "gpt-5.3-codex"
    boss_reasoning_effort = str(getattr(req, "boss_reasoning_effort", "") or "").strip() or "medium"

    return RunConfig(
        repo_root=repo_root,
        sleep_minutes=sleep_minutes,
        max_build_cycles=max_cycles,
        max_parallel_workers=max_parallel_workers,
        dry_run=bool(getattr(req, "dry_run", False)),
        resume_mode=resume_mode,
        run_base_source_branch=run_base_source_branch,
        boss_model=boss_model,
        boss_reasoning_effort=boss_reasoning_effort,
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
            str((cfg.repo_root / TRACE_EVENT_LOG_FILE).resolve()),
            str((cfg.repo_root / CYCLE_COUNTER_FILE).resolve()),
            str((cfg.repo_root / RUN_LOCK_FILE).resolve()),
            str((cfg.repo_root / BOSS_SESSION_STATE_FILE).resolve()),
            str((cfg.repo_root / APP_LIFECYCLE_FILE).resolve()),
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

        run_meta = _load_resume_run_base_meta(cfg) if cfg.resume_mode else _create_run_base_branch(cfg)
        init_state = _ensure_initialize_state(cfg, run_meta=run_meta)
        if bool((init_state.get("run_context") or {}).get("created_new")):
            _reset_runtime_state_for_new_run(cfg)
        _ensure_workstation_prep(
            cfg,
            initialize_state=init_state,
            force_refresh=bool((init_state.get("run_context") or {}).get("created_new")),
        )
        _ensure_default_artifacts(cfg)
        _seed_plan_artifacts_from_planner(cfg)

        cycle_number = _load_cycle_counter(cfg)
        cycles_this_run = 0
        previous_state_signature: str | None = None
        quiet_cycle_streak = 0

        while True:
            cycle_number += 1
            cycles_this_run += 1
            _write_cycle_counter(cfg, cycle_number)

            terminate_path = cfg.repo_root / TERMINATE_FILE_NAME
            if terminate_path.exists():
                stop_reason = "operator_terminate_file"
                final_summary = "OP Simple build stopped by terminate_run.json signal."
                break

            lease_recovery = _normalize_dead_worker_leases(cfg, cycle_number)
            if lease_recovery["reclaimed_workers"] or lease_recovery["requeued_tasks"]:
                warnings.append(
                    {
                        "code": "stale_worker_leases_recovered",
                        "message": (
                            "Cleared dead worker PID markers while preserving task/thread context so BOSS can "
                            "reconcile worker completion safely."
                        ),
                        "stage": "op-simple-build",
                        "details": {
                            "cycle_number": cycle_number,
                            "reclaimed_workers": int(lease_recovery["reclaimed_workers"]),
                            "requeued_tasks": int(lease_recovery["requeued_tasks"]),
                        },
                    }
                )

            manager_statuses: dict[str, dict[str, str]] = {}
            dispatch_counts = {"attempted": 0, "launched": 0, "launch_failed": 0, "unknown": 0}
            state_signature, in_progress_workers = _worker_task_state_signature(cfg)
            state_changed = previous_state_signature is None or state_signature != previous_state_signature
            force_full_cycle = quiet_cycle_streak >= (QUIET_CYCLE_FORCE_FULL_EVERY - 1)
            has_recovery_nudge = (cfg.repo_root / "recovery_instructions.md").exists()
            has_boss_timeout_marker = (cfg.repo_root / BOSS_EVIDENCE_FILE).exists()
            near_watchdog_idle = _watchdog_near_idle_threshold(cfg)
            has_lease_recovery = bool(lease_recovery["reclaimed_workers"] or lease_recovery["requeued_tasks"])

            skip_boss_for_quiet_cycle = (
                not has_lease_recovery
                and not has_recovery_nudge
                and not has_boss_timeout_marker
                and not near_watchdog_idle
                and not state_changed
                and in_progress_workers > 0
                and not force_full_cycle
            )
            boss_result: ManagerResult | None = None
            quiet_skip_reason = ""

            if skip_boss_for_quiet_cycle:
                quiet_cycle_streak += 1
                quiet_skip_reason = "active_workers_in_progress_no_safe_new_dispatch"
                manager_statuses["BOSS"] = {
                    "status": "skipped",
                    "note": (
                        f"quiet-cycle gate: no worker/task state change with {in_progress_workers} "
                        f"in-progress workers (quiet_streak={quiet_cycle_streak})"
                    ),
                }
                manager_statuses["rate-gate"] = {"status": "skipped", "note": "quiet-cycle gate skipped BOSS"}
                manager_statuses["work-dispatcher"] = {"status": "skipped", "note": "quiet-cycle gate skipped BOSS"}
                _write_cycle_manager_decision(
                    cfg,
                    cycle_number,
                    decision="skip_cycle",
                    reason_code=quiet_skip_reason,
                    message=manager_statuses["BOSS"]["note"],
                    worker_registry_ready=True,
                )
                print(
                    "[op-simple-build] "
                    f"[{utc_now_iso()}] "
                    f"cycle={cycle_number} quiet-cycle gate skipped BOSS "
                    f"in_progress_workers={in_progress_workers} quiet_streak={quiet_cycle_streak}",
                    flush=True,
                )
            else:
                quiet_cycle_streak = 0
                boss_expected = list(BOSS_REQUIRED_ARTIFACTS)
                print(
                    "[op-simple-build] "
                    f"[{utc_now_iso()}] "
                    f"cycle={cycle_number} BOSS started",
                    flush=True,
                )
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
                print(
                    "[op-simple-build] "
                    f"[{utc_now_iso()}] "
                    f"cycle={cycle_number} BOSS done "
                    f"status={boss_result.status} timeout={str(bool(boss_result.timeout)).lower()} "
                    f"duration_s={boss_result.duration_seconds:.3f}",
                    flush=True,
                )
                manager_statuses["BOSS"] = {"status": boss_result.status, "note": boss_result.message or ""}

            if boss_result is not None and boss_result.timeout:
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
                print(
                    "[op-simple-build] "
                    f"[{utc_now_iso()}] "
                    f"cycle={cycle_number} skipped due to BOSS timeout; sleeping 180s before next cycle",
                    flush=True,
                )
                previous_state_signature = state_signature
                time.sleep(180)
                if cfg.max_build_cycles is not None and cycles_this_run >= cfg.max_build_cycles:
                    final_summary = f"Reached max_build_cycles={cfg.max_build_cycles} after BOSS timeout."
                    break
                continue
            if boss_result is not None:
                _safe_unlink(cfg.repo_root / BOSS_EVIDENCE_FILE)

            if boss_result is not None and boss_result.status != "ok":
                warnings.append(
                    {
                        "code": boss_result.reason_code or "boss_failed",
                        "message": boss_result.message or "BOSS failed",
                        "stage": "op-simple-build",
                    }
                )
                worker_registry_ready = True
                if isinstance(boss_result.details, dict) and boss_result.details.get("artifact_key") == "worker_registry":
                    worker_registry_ready = False
                _write_cycle_manager_decision(
                    cfg,
                    cycle_number,
                    decision="skip_cycle",
                    reason_code=boss_result.reason_code or "boss_failed",
                    message=boss_result.message or "BOSS failed",
                    worker_registry_ready=worker_registry_ready,
                )
                manager_statuses["rate-gate"] = {
                    "status": "skipped",
                    "note": "cycle skipped after BOSS failure",
                }
                manager_statuses["work-dispatcher"] = {
                    "status": "skipped",
                    "note": "cycle skipped after BOSS failure",
                }
            elif boss_result is not None:
                _run_rate_gate_wait(cfg, cycle_number, warnings)
                manager_statuses["rate-gate"] = {"status": "ok", "note": "rate gate completed"}
                dispatch_counts = _dispatch_packets(cfg, cycle_number)
                manager_statuses["work-dispatcher"] = {"status": "ok", "note": "dispatch cycle completed"}

            watchdog_stop, watchdog_signal = _watchdog_tick(cfg, cycle_number)
            manager_statuses["watchdog"] = {
                "status": "stop" if watchdog_stop else "ok",
                "note": watchdog_signal.get("message") if watchdog_stop else "watchdog healthy",
            }

            manager_statuses["summary"] = {"status": "ok", "note": "summary written"}
            base_summary: dict[str, Any] | None = None
            if skip_boss_for_quiet_cycle:
                base_summary = {
                    "schema_version": SCHEMA_VERSION,
                    "cycle_number": cycle_number,
                    "manager_statuses": {},
                    "task_counts": _task_counts_from_execution_state(cfg),
                    "dispatch_counts": {"attempted": 0, "launched": 0, "launch_failed": 0, "unknown": 0},
                    "project_done": False,
                    "insurmountable_blocker": False,
                    "termination": {"reason_code": quiet_skip_reason},
                    "stop_reason": "skip_cycle",
                    "notes": manager_statuses["BOSS"]["note"],
                }
            elif boss_result is not None and boss_result.status != "ok":
                base_summary = {
                    "schema_version": SCHEMA_VERSION,
                    "cycle_number": cycle_number,
                    "manager_statuses": {},
                    "task_counts": {"pending": 0, "in_progress": 0, "done": 0, "blocked": 0},
                    "dispatch_counts": {"attempted": 0, "launched": 0, "launch_failed": 0, "unknown": 0},
                    "project_done": False,
                    "insurmountable_blocker": False,
                    "termination": {},
                    "stop_reason": "",
                    "notes": f"cycle skipped by runtime safety rules: {boss_result.message or 'BOSS failed'}",
                }
            summary = _render_cycle_summary(
                cfg,
                cycle_number,
                manager_statuses,
                dispatch_counts,
                base_summary=base_summary,
            )

            terminate_path = cfg.repo_root / TERMINATE_FILE_NAME
            if terminate_path.exists():
                stop_reason = "operator_terminate_file"
            else:
                stop_reason = _termination_from_summary(summary)
                if stop_reason not in {"project_done", "insurmountable_blocker"} and watchdog_stop:
                    stop_reason = "watchdog_idle_stop"

            _snapshot_cycle(cfg, cycle_number)
            previous_state_signature, _ = _worker_task_state_signature(cfg)

            if stop_reason:
                final_summary = f"OP Simple build stopped: {stop_reason}."
                break

            if cfg.max_build_cycles is not None and cycles_this_run >= cfg.max_build_cycles:
                final_summary = f"Reached max_build_cycles={cfg.max_build_cycles}."
                break

            if cfg.sleep_minutes > 0:
                time.sleep(cfg.sleep_minutes * 60.0)

        if stop_reason == "project_done":
            _run_wrapup_manager(
                cfg,
                cycle_number=cycle_number,
                stop_reason=stop_reason,
                init_state=init_state,
                warnings=warnings,
            )

        data = {
            "cycle_number": cycle_number,
            "cycles_this_run": cycles_this_run,
            "stop_reason": stop_reason,
            "max_parallel_workers": cfg.max_parallel_workers,
            "artifact_root": str((cfg.repo_root / SIMPLE_ROOT).resolve()),
            "run_base_branch": str((init_state.get("run_context") or {}).get("run_base_branch") or ""),
            "run_base_from_branch": str((init_state.get("run_context") or {}).get("run_base_from_branch") or ""),
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
