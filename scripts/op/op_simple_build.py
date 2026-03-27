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
from datetime import datetime, timedelta, timezone
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
    "lane_base_watchdog_registry": CURRENT_DIR / "lane_base_watchdog_registry.json",
    "dispatch_registry": CURRENT_DIR / "dispatch_registry.json",
    "cycle_summary": CURRENT_DIR / "cycle_summary.json",
    "mergeability_report": CURRENT_DIR / "mergeability_report.json",
    "merge_queue": CURRENT_DIR / "merge_queue.json",
    "unmergable_merges": CURRENT_DIR / "unmergable_merges.json",
    "merge_manager_report": CURRENT_DIR / "merge_manager_report.json",
    "terminal_capsule": CURRENT_DIR / "terminal_capsule.json",
    "wrapup_manager_report": CURRENT_DIR / "wrapup_manager_report.json",
    "watchdog_state": CURRENT_DIR / "watchdog_state.json",
    "watchdog_exit_signal": CURRENT_DIR / "watchdog_exit_signal.json",
    "workstation_prep": CURRENT_DIR / "workstation_prep.json",
    "llm_profile_mode": CURRENT_DIR / "llm_profile_mode.json",
    "llm_profile_rate_registry": CURRENT_DIR / "llm_profile_rate_registry.json",
    "timeout_adaptation_state": CURRENT_DIR / "timeout_adaptation_state.json",
    "restart_determinism_state": CURRENT_DIR / "restart_determinism_state.json",
}

MANAGER_TIMEOUT_SECONDS = {
    "BOSS": 900,
    "merge-manager": 900,
    "wrapup-manager": 900,
    "watchdog": 120,
    "summary": 120,
}
BLACKBOX_MANAGER_TIMEOUT_SECONDS = {
    "BOSS": 1800,
    "merge-manager": 1800,
    "wrapup-manager": 1800,
}

WATCHDOG_STALE_COMMIT_MINUTES = 150
WATCHDOG_NEAR_STALE_MARGIN_MINUTES = 10
WATCHDOG_RECOVERY_NUDGE_MINUTES = 30
WATCHDOG_RUN_BASE_HARD_LIMIT_MULTIPLIER = 2
WATCHDOG_TERMINAL_WARNING_LEAD_MINUTES = 20
WATCHDOG_TERMINAL_WARNING_COOLDOWN_CYCLES = 4
WAIT_HEARTBEAT_SECONDS = 300
WAIT_RESCAN_SECONDS = 900
THREAD_LIVENESS_MAX_AGE_SECONDS = 1200
MERGE_RECOVERY_RESERVED_SLOTS = 2
MERGE_MANAGER_CADENCE_CYCLES = 5
LLM_PROFILE_PER_MINUTE_LIMIT = 20
LLM_PROFILE_PER_DAY_LIMIT = 1000
RATE_SNAPSHOT_SCRIPT_REL = Path("skills") / "minimal-rate-snapshot" / "scripts" / "minimal_rate_snapshot.py"
RECOVERY_INSTRUCTIONS_FILE = Path("recovery_instructions.md")
TERMINAL_WARNING_INSTRUCTIONS_FILE = Path("recovery_instructions_terminal_warning.md")
WATCHDOG_RECOVERY_NUDGE_BODY_TEMPLATE_FILE = SCRIPT_DIR / "templates" / "watchdog_recovery_nudge_body.md"
MERGE_JOURNAL_FILE = CURRENT_DIR / "merge_journal.jsonl"
WATCHDOG_TERMINAL_WARNING_NUDGE_BODY_TEMPLATE_FILE = SCRIPT_DIR / "templates" / "watchdog_terminal_warning_nudge_body.md"
WATCHDOG_RECOVERY_NUDGE_BODY_FALLBACK = """This nudge is broad by design. Run a full diagnostics sweep before deciding to skip repeatedly.

## Broad diagnostics checklist (not limited to one failure mode)
1. Inspect repeated cycle-gate skip reasons in `.op-simple/current/cycle_manager_decision.json` and recent `.op-simple/history/cycle-*/cycle_manager_decision.json`.
2. Reconcile all in-progress workers with `pid=null` by scanning canonical and non-obvious evidence locations.
3. Ingest reviewer outcomes from:
   - `<worker_worktree>/reports/handoffs/<task_identifier>.handoff.json`
   - `<worker_worktree>/.codex-dispatch/dispatch-*.log`
4. Normalize decision aliases during ingestion when needed (`reviewer_decision` -> `decision`) and update canonical artifacts.
5. Verify `task_execution_state.json`, `worker_registry.json`, and `production_line_register.json` are aligned after reconciliation.
6. Validate worker packet/worktree integrity (`worker_packets.json` entries map to valid worker rows and existing worktrees).
7. Validate profile gating posture (`profile_snapshot.json`) so dispatch is not starved by hard/soft gate mistakes.
8. Check for dispatch launch failures/timeouts in `.op-simple/current/dispatch_launch_log.jsonl`.
9. If evidence is still missing, create explicit remediation tasks instead of repeating passive skips.

After applying this nudge, rename this file to `recovery_instructions_CONSUMED.md`."""
WATCHDOG_TERMINAL_WARNING_NUDGE_BODY_FALLBACK = """This is a terminal-warning nudge for run-base inactivity.

The run-base branch is nearing the hard watchdog stop window.
Prioritize merge/fan-in recovery now so run-base receives fresh commits before hard-limit stop.

After applying this warning, rename this file to `recovery_instructions_terminal_warning_CONSUMED.md`."""
NON_TERMINAL_STOP_REASONS = {
    "skip_cycle",
}
TERMINAL_STOP_REASONS = {
    "project_done",
    "insurmountable_blocker",
}
WATCHDOG_TERMINAL_STOP_REASONS = {
    "watchdog_idle_stop",
    "stale_base_branch_commit",
    "stale_run_base_hard_limit",
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
MANAGER_PROFILE_ALIAS_REGEX = re.compile(r"manager_profile_alias=([A-Za-z0-9._-]+)")
RETRYABLE_BOSS_PROFILE_ERROR_PATTERNS = (
    "unexpected status 402 payment required",
    "unexpected status 401 unauthorized",
    '"code":"deactivated_workspace"',
    '"code":"invalid_api_key"',
    "auth error: 402",
    "auth error: 401",
    "failed to connect to websocket: http error: 402 payment required",
    "failed to connect to websocket: http error: 401 unauthorized",
)
EXECUTOR_PROVIDERS = {"codex", "openrouter", "blackbox"}
BLACKBOX_LANES = {"free", "api_key"}
BLACKBOX_DEFAULT_MODELS = {
    "free": "blackboxai/minimax/minimax-free",
    "api_key": "blackboxai/minimax/minimax-m2.5",
}
BLACKBOX_KEYCHAIN_SERVICE = "BLACKBOXAI_KEY"
NEW_EXECUTOR_LOG_ROOT = Path("/Users/slobodan/projects/LOGS") / "op-executors"
NEW_EXECUTOR_LOG_MAX_BYTES = 3 * 1024 * 1024 * 1024
NEW_EXECUTOR_LOG_CHECK_INTERVAL_SECONDS = 900
NEW_EXECUTOR_LOG_STATE_FILE = NEW_EXECUTOR_LOG_ROOT / "MAINTENANCE_STATE.json"
TRACE_EVENT_SCHEMA_VERSION = "trace-event-envelope.v1"
CANONICAL_ID_PATTERN = re.compile(r"^[a-z]+\.[a-z0-9][a-z0-9-]{1,95}$")
GROUND_SYNC_DEFAULT_EVERY_N_CYCLES = 1
GROUND_SYNC_DEFAULT_TIMEOUT_SECONDS = 120
GROUND_SYNC_MANAGER_NAME = "ground-sync"
GROUND_SYNC_SNAPSHOT_BASENAME = "current.trace_event_envelope.jsonl"
DEFAULT_CYCLE_RELEASE_MODE = "token_conservative"
DEFAULT_CYCLE_RELEASE_TIMEOUT_SECONDS = 900
DEFAULT_CYCLE_RELEASE_POLL_SECONDS = 5
CYCLE_RELEASE_DEAD_PID_GUARD_SECONDS = 10
CYCLE_RELEASE_MODES = {"token_conservative", "max_work"}
DEFAULT_WORKTREES_PARENT = Path("/Users/slobodan/Forest")
TRACE_EVENT_TIMESTAMP_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
TRACE_EVENT_SOURCE_SHA_REGEX = re.compile(r"^[0-9a-f]{7,40}$")
TRACE_EVENT_ACTOR_TYPES = {"manager", "worker", "service", "operator", "system"}
TRACE_EVENT_OUTCOME_STATUS = {"success", "failure", "partial", "blocked", "noop", "unknown"}
TRACE_EVENT_RISK_LEVELS = {"low", "medium", "high", "critical"}
LLM_HARDENING_CHECKER_RESULTS = {"pass", "fail", "not_applicable"}
LLM_HARDENING_RISK_LEVELS = {"low", "medium", "high", "critical"}
LLM_HARDENING_TELEMETRY_STATES = {"present", "missing", "unknown"}
CANONICAL_ID_PATTERNS = {
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
    worktrees_parent: Path = DEFAULT_WORKTREES_PARENT
    selected_aliases: list[str] | None = None
    resume_mode: bool = False
    run_base_source_branch: str = "main"
    boss_model: str = "gpt-5.3-codex"
    boss_reasoning_effort: str = "xhigh"
    codex_profile: str | None = None
    executor_provider: str = "codex"
    executor_model: str | None = None
    blackbox_lane: str = "free"
    allow_worker_executor_override: bool = False
    ground_sync_enabled: bool = True
    ground_sync_every_n_cycles: int = GROUND_SYNC_DEFAULT_EVERY_N_CYCLES
    ground_sync_timeout_seconds: int = GROUND_SYNC_DEFAULT_TIMEOUT_SECONDS
    cycle_release_mode: str = DEFAULT_CYCLE_RELEASE_MODE
    cycle_release_timeout_seconds: int = DEFAULT_CYCLE_RELEASE_TIMEOUT_SECONDS
    cycle_release_poll_seconds: int = DEFAULT_CYCLE_RELEASE_POLL_SECONDS


class SimpleBuildError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=False) + "\n"


def _path_within_parent(path_value: Path, parent: Path) -> bool:
    try:
        path_value.relative_to(parent)
        return True
    except ValueError:
        return False


def _coerce_output_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _normalize_selected_aliases(value: Any) -> list[str] | None:
    if value is None:
        return None
    raw_items: list[str] = []
    if isinstance(value, str):
        raw_items.extend(value.split(","))
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                raw_items.extend(item.split(","))
            else:
                raw_items.append(str(item))
    else:
        raw_items.append(str(value))

    aliases: list[str] = []
    seen: set[str] = set()
    for raw in raw_items:
        alias = str(raw or "").strip().lower()
        if not alias or alias in seen:
            continue
        seen.add(alias)
        aliases.append(alias)
    return aliases or None


def _repo_workstation_prefix(repo_root: Path) -> str:
    # Workstation-preparation validates optional prefixes against the git toplevel
    # repository name, so nested repo-root runs (e.g. op-tools/strategy) must
    # derive the same prefix to avoid false invalid-name failures.
    toplevel = _git_text(repo_root, "rev-parse", "--show-toplevel")
    if toplevel:
        raw = str(Path(toplevel).name or "").strip().lower()
    else:
        raw = str(repo_root.name or "").strip().lower()
    normalized = re.sub(r"[^a-z0-9._-]+", "-", raw)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-._")
    return normalized or "repo"


def _workstation_id_for_index(cfg: RunConfig, idx: int) -> str:
    return f"{_repo_workstation_prefix(cfg.repo_root)}-workstation-{idx}"


def _alias_candidates(alias: str) -> list[str]:
    text = str(alias or "").strip().lower()
    if not text:
        return []
    out = [text]
    if text == "codex":
        return out
    if text.startswith("codex-"):
        short = text[len("codex-") :].strip()
        if short:
            out.append(short)
        return out
    out.append(f"codex-{text}")
    return out


def _canonical_codex_alias(alias: Any, codex_home: Any) -> str:
    alias_text = str(alias or "").strip().lower()
    home_name = Path(str(codex_home or "").strip()).name.lower()
    if home_name == ".codex":
        return "codex"
    if home_name.startswith(".codex-") and len(home_name) > len(".codex-"):
        return f"codex-{home_name[len('.codex-'):]}"
    if alias_text == "codex":
        return "codex"
    if alias_text.startswith("codex-"):
        return alias_text
    if alias_text:
        return f"codex-{alias_text}"
    return ""


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


def _normalize_executor_provider(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in EXECUTOR_PROVIDERS:
        return text
    return "codex"


def _normalize_blackbox_lane(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in BLACKBOX_LANES:
        return text
    return "free"


def _normalize_cycle_release_mode(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in CYCLE_RELEASE_MODES:
        return text
    return DEFAULT_CYCLE_RELEASE_MODE


def _executor_uses_codex_backend(provider: str) -> bool:
    return provider in {"codex", "openrouter"}


def _resolve_executor_model(cfg: RunConfig, *, provider: str | None = None, model_override: str | None = None) -> str | None:
    resolved_provider = _normalize_executor_provider(provider or cfg.executor_provider)
    model_text = str(model_override or cfg.executor_model or "").strip()
    if model_text:
        return model_text
    if resolved_provider == "blackbox":
        lane = _normalize_blackbox_lane(cfg.blackbox_lane)
        return BLACKBOX_DEFAULT_MODELS.get(lane, BLACKBOX_DEFAULT_MODELS["free"])
    return None


def _maintenance_epoch(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _maintain_new_executor_logs() -> None:
    now_epoch = time.time()
    state = _read_json(NEW_EXECUTOR_LOG_STATE_FILE, default={})
    if isinstance(state, dict):
        last_checked_epoch = _maintenance_epoch(state.get("last_checked_epoch"))
        if now_epoch - last_checked_epoch < float(NEW_EXECUTOR_LOG_CHECK_INTERVAL_SECONDS):
            return

    NEW_EXECUTOR_LOG_ROOT.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    for path in NEW_EXECUTOR_LOG_ROOT.rglob("*"):
        if not path.is_file() or path == NEW_EXECUTOR_LOG_STATE_FILE:
            continue
        files.append(path)
    total_bytes = 0
    for path in files:
        try:
            total_bytes += int(path.stat().st_size)
        except OSError:
            continue

    if total_bytes > NEW_EXECUTOR_LOG_MAX_BYTES:
        def _mtime(item: Path) -> float:
            try:
                return float(item.stat().st_mtime)
            except OSError:
                return 0.0

        for path in sorted(files, key=_mtime):
            if total_bytes <= NEW_EXECUTOR_LOG_MAX_BYTES:
                break
            try:
                original_size = int(path.stat().st_size)
                path.write_text("", encoding="utf-8")
            except OSError:
                continue
            total_bytes = max(0, total_bytes - original_size)

    _atomic_write_json(
        NEW_EXECUTOR_LOG_STATE_FILE,
        {
            "schema_version": SCHEMA_VERSION,
            "updated_at": utc_now_iso(),
            "last_checked_epoch": int(now_epoch),
            "total_bytes": int(total_bytes),
            "max_bytes": int(NEW_EXECUTOR_LOG_MAX_BYTES),
        },
    )


def _write_new_executor_blob(scope: str, filename: str, content: str) -> str | None:
    try:
        _maintain_new_executor_logs()
        target = NEW_EXECUTOR_LOG_ROOT / scope / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return str(target.resolve())
    except OSError:
        return None


def _append_new_executor_event(scope: str, row: dict[str, Any]) -> None:
    try:
        _maintain_new_executor_logs()
        path = NEW_EXECUTOR_LOG_ROOT / scope / "events.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=False) + "\n")
    except OSError:
        return


def _resolve_blackbox_api_key() -> str | None:
    user = str(os.environ.get("USER") or "").strip()
    if not user:
        return None
    try:
        proc = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-a",
                user,
                "-s",
                BLACKBOX_KEYCHAIN_SERVICE,
                "-w",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    key = str(proc.stdout or "").strip()
    return key or None


def _build_blackbox_exec_command(cfg: RunConfig, prompt_text: str, *, model: str | None = None) -> tuple[list[str], dict[str, str] | None, str | None]:
    resolved_model = str(model or _resolve_executor_model(cfg, provider="blackbox") or "").strip()
    if not resolved_model:
        return [], None, "blackbox model could not be resolved"
    lane = _normalize_blackbox_lane(cfg.blackbox_lane)
    env = os.environ.copy()
    if lane == "free":
        env.pop("BLACKBOX_API_KEY", None)
        env.pop("OPENAI_API_KEY", None)
    else:
        api_key = _resolve_blackbox_api_key()
        if not api_key:
            return [], None, "BLACKBOXAI_KEY is missing in macOS Keychain"
        env["BLACKBOX_API_KEY"] = api_key
    return [
        "blackbox",
        "-m",
        resolved_model,
        "--approval-mode",
        "yolo",
        "--include-directories",
        ".",
        "-p",
        prompt_text,
    ], env, None


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
    wrapup_log_row = _latest_manager_event_for_cycle(cfg, cycle_number=cycle_number, manager_name="wrapup-manager")
    wrapup_llm = _manager_llm_metadata(cfg, manager_name="wrapup-manager", log_row=wrapup_log_row)
    wrapup_inputs: dict[str, Any] = {
        "stop_reason": stop_reason,
        "cycle_number": cycle_number,
        "manager_status": result.status,
    }
    if wrapup_llm:
        wrapup_inputs["llm"] = wrapup_llm

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
            "inputs": wrapup_inputs,
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


def _default_timeout_adaptation_state() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "updated_at": utc_now_iso(),
        "consecutive_boss_timeouts": 0,
        "timeout_threshold": 2,
        "adaptation_active": False,
        "rotation_required": False,
        "last_timeout_cycle": None,
        "last_timeout_profile_alias": "",
        "last_timeout_reason": "",
        "last_non_timeout_failed_profile_alias": "",
        "last_non_timeout_failed_cycle": None,
        "last_non_timeout_failed_reason": "",
        "last_rotation_decision": {},
        "last_boss_runtime_checks": {},
    }


def _load_timeout_adaptation_state(cfg: RunConfig) -> dict[str, Any]:
    payload = _read_json(cfg.repo_root / ARTIFACT_FILES["timeout_adaptation_state"], default={})
    if not isinstance(payload, dict):
        payload = {}
    out = _default_timeout_adaptation_state()
    out.update(payload)
    try:
        out["consecutive_boss_timeouts"] = max(0, int(out.get("consecutive_boss_timeouts") or 0))
    except (TypeError, ValueError):
        out["consecutive_boss_timeouts"] = 0
    try:
        out["timeout_threshold"] = max(1, int(out.get("timeout_threshold") or 2))
    except (TypeError, ValueError):
        out["timeout_threshold"] = 2
    out["adaptation_active"] = bool(out.get("adaptation_active"))
    out["rotation_required"] = bool(out.get("rotation_required"))
    out["last_timeout_profile_alias"] = str(out.get("last_timeout_profile_alias") or "").strip()
    out["last_timeout_reason"] = str(out.get("last_timeout_reason") or "").strip()
    out["last_non_timeout_failed_profile_alias"] = str(out.get("last_non_timeout_failed_profile_alias") or "").strip()
    try:
        last_non_timeout_failed_cycle = out.get("last_non_timeout_failed_cycle")
        out["last_non_timeout_failed_cycle"] = int(last_non_timeout_failed_cycle) if last_non_timeout_failed_cycle is not None else None
    except (TypeError, ValueError):
        out["last_non_timeout_failed_cycle"] = None
    out["last_non_timeout_failed_reason"] = str(out.get("last_non_timeout_failed_reason") or "").strip()
    if not isinstance(out.get("last_rotation_decision"), dict):
        out["last_rotation_decision"] = {}
    if not isinstance(out.get("last_boss_runtime_checks"), dict):
        out["last_boss_runtime_checks"] = {}
    return out


def _write_timeout_adaptation_state(cfg: RunConfig, payload: dict[str, Any]) -> dict[str, Any]:
    out = _load_timeout_adaptation_state(cfg)
    out.update(payload if isinstance(payload, dict) else {})
    out["schema_version"] = SCHEMA_VERSION
    out["updated_at"] = utc_now_iso()
    _atomic_write_json(cfg.repo_root / ARTIFACT_FILES["timeout_adaptation_state"], out)
    return out


def _profile_alias_from_manager_result(result: ManagerResult | None) -> str | None:
    if not isinstance(result, ManagerResult):
        return None
    message = str(result.message or "")
    match = MANAGER_PROFILE_ALIAS_REGEX.search(message)
    if not match:
        return None
    alias = str(match.group(1) or "").strip()
    return alias or None


def _record_boss_timeout_state(
    cfg: RunConfig,
    *,
    cycle_number: int,
    result: ManagerResult | None,
    reason_code: str,
) -> dict[str, Any]:
    state = _load_timeout_adaptation_state(cfg)
    threshold = int(state.get("timeout_threshold") or 2)
    streak = int(state.get("consecutive_boss_timeouts") or 0) + 1
    timeout_alias = _profile_alias_from_manager_result(result) or str(state.get("last_timeout_profile_alias") or "").strip()
    eligible_aliases = [
        item.get("alias")
        for item in _boss_profile_candidates_from_snapshot(cfg)
        if isinstance(item, dict) and bool(item.get("eligible"))
    ]
    eligible_aliases = [str(alias) for alias in eligible_aliases if isinstance(alias, str) and alias.strip()]
    rotation_required = streak >= threshold and len(set(eligible_aliases)) > 1
    updated = _write_timeout_adaptation_state(
        cfg,
        {
            "consecutive_boss_timeouts": streak,
            "adaptation_active": streak >= threshold,
            "rotation_required": rotation_required,
            "last_timeout_cycle": int(cycle_number),
            "last_timeout_profile_alias": timeout_alias,
            "last_timeout_reason": str(reason_code or "").strip() or "manager_timeout",
            "eligible_profile_aliases": sorted(set(eligible_aliases)),
        },
    )
    return updated


def _record_boss_non_timeout_state(
    cfg: RunConfig,
    *,
    cycle_number: int,
    status: str,
    result: ManagerResult | None = None,
) -> dict[str, Any]:
    state = _load_timeout_adaptation_state(cfg)
    normalized_status = str(status or "").strip()
    has_timeout_adaptation_state = int(state.get("consecutive_boss_timeouts") or 0) > 0 or bool(state.get("rotation_required"))
    prior_non_timeout_failed_alias = str(state.get("last_non_timeout_failed_profile_alias") or "").strip()
    should_track_non_timeout_failure = normalized_status != "ok"
    if not has_timeout_adaptation_state and not should_track_non_timeout_failure and not prior_non_timeout_failed_alias:
        return state

    selected_alias = _profile_alias_from_manager_result(result)
    if not selected_alias:
        last_rotation_decision = state.get("last_rotation_decision")
        if isinstance(last_rotation_decision, dict):
            selected_alias = str(last_rotation_decision.get("selected_alias") or "").strip() or None
    failure_reason = ""
    if isinstance(result, ManagerResult):
        failure_reason = str(result.reason_code or "").strip()

    payload: dict[str, Any] = {
        "last_boss_status_after_timeout": normalized_status,
        "last_boss_status_cycle": int(cycle_number),
    }
    if has_timeout_adaptation_state:
        payload.update(
            {
                "consecutive_boss_timeouts": 0,
                "adaptation_active": False,
                "rotation_required": False,
                "last_timeout_cycle": state.get("last_timeout_cycle"),
            }
        )
    if should_track_non_timeout_failure:
        payload.update(
            {
                "last_non_timeout_failed_profile_alias": str(selected_alias or "").strip(),
                "last_non_timeout_failed_cycle": int(cycle_number),
                "last_non_timeout_failed_reason": failure_reason or normalized_status or "failed",
            }
        )
    else:
        payload.update(
            {
                "last_non_timeout_failed_profile_alias": "",
                "last_non_timeout_failed_cycle": None,
                "last_non_timeout_failed_reason": "",
            }
        )
    return _write_timeout_adaptation_state(cfg, payload)


def _boss_non_timeout_excluded_alias(timeout_state: dict[str, Any]) -> str:
    if not isinstance(timeout_state, dict):
        return ""
    failed_alias = str(timeout_state.get("last_non_timeout_failed_profile_alias") or "").strip()
    return failed_alias


def _profile_snapshot_source(cfg: RunConfig) -> str:
    payload = _read_json(cfg.repo_root / ARTIFACT_FILES["profile_snapshot"], default={})
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("source") or "").strip()


def _refresh_profile_snapshot_before_boss_selection(cfg: RunConfig, *, cycle_number: int) -> tuple[bool, str]:
    if _llm_profile_mode_enabled(cfg):
        return False, "profile snapshot refresh skipped in llm profile mode"
    snapshot_source = _profile_snapshot_source(cfg)
    if snapshot_source != "filesystem-profile-discovery-bootstrap":
        return False, f"profile snapshot refresh skipped source={snapshot_source}"
    refreshed, message = _refresh_profile_snapshot_via_skill(cfg, cycle_number)
    return refreshed, message


def _read_manager_output_text(path_text: str | None) -> str:
    candidate = str(path_text or "").strip()
    if not candidate:
        return ""
    try:
        return Path(candidate).read_text(encoding="utf-8")
    except OSError:
        return ""


def _manager_result_has_retryable_profile_auth_failure(result: ManagerResult | None) -> bool:
    if not isinstance(result, ManagerResult):
        return False
    haystacks = [
        str(result.message or ""),
        _read_manager_output_text(result.stderr_path),
        _read_manager_output_text(result.stdout_path),
    ]
    lowered = "\n".join(haystacks).lower()
    return any(pattern in lowered for pattern in RETRYABLE_BOSS_PROFILE_ERROR_PATTERNS)


def _mark_profile_snapshot_alias_unavailable(cfg: RunConfig, *, alias: str, reason: str) -> bool:
    alias_text = str(alias or "").strip()
    if not alias_text:
        return False
    snapshot_path = cfg.repo_root / ARTIFACT_FILES["profile_snapshot"]
    payload = _read_json(snapshot_path, default={})
    if not isinstance(payload, dict):
        return False
    rows = payload.get("profiles")
    if not isinstance(rows, list):
        return False
    updated = False
    normalized_reason = str(reason or "").strip() or "profile_marked_unavailable"
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("alias") or "").strip() != alias_text:
            continue
        row["hard_gated"] = True
        row["soft_gated"] = False
        row["recommended_action"] = "wind_down"
        row["availability_reason"] = normalized_reason
        updated = True
    if not updated:
        return False
    payload["schema_version"] = SCHEMA_VERSION
    payload["updated_at"] = utc_now_iso()
    payload["profiles"] = rows
    _atomic_write_json(snapshot_path, payload)
    return True


def _preserve_manager_attempt_logs(result: ManagerResult | None, *, label: str) -> None:
    if not isinstance(result, ManagerResult):
        return
    for attr_name, suffix in (("stdout_path", "stdout.log"), ("stderr_path", "stderr.log")):
        source_text = str(getattr(result, attr_name, "") or "").strip()
        if not source_text:
            continue
        source_path = Path(source_text)
        if not source_path.exists():
            continue
        target_path = source_path.with_name(f"{source_path.stem}.{label}.{suffix}")
        try:
            shutil.copyfile(source_path, target_path)
        except OSError:
            continue


def _record_boss_non_timeout_exclusion_evidence(
    rotation_selection_evidence: dict[str, Any],
    excluded_aliases: set[str],
    *,
    timed_out_alias: str,
    non_timeout_failed_alias: str,
) -> None:
    if timed_out_alias:
        rotation_selection_evidence["timeout_excluded_alias"] = timed_out_alias
    if non_timeout_failed_alias:
        rotation_selection_evidence["non_timeout_failed_excluded_alias"] = non_timeout_failed_alias
    if excluded_aliases:
        rotation_selection_evidence["excluded_aliases"] = sorted(excluded_aliases)


def _is_boss_failed_cycle(manager_statuses: dict[str, dict[str, str]]) -> bool:
    boss_status = str((manager_statuses.get("BOSS") or {}).get("status") or "").strip().lower()
    return boss_status == "failed"


def _boss_failed_note(manager_statuses: dict[str, dict[str, str]], summary_notes: str) -> str:
    text = str((manager_statuses.get("BOSS") or {}).get("note") or summary_notes or "BOSS failed").strip()
    if len(text) <= 240:
        return text
    return f"{text[:237]}..."


def _record_boss_rotation_decision(cfg: RunConfig, *, decision: dict[str, Any]) -> dict[str, Any]:
    return _write_timeout_adaptation_state(cfg, {"last_rotation_decision": decision if isinstance(decision, dict) else {}})


def _record_boss_runtime_checks(cfg: RunConfig, *, checks: dict[str, Any]) -> dict[str, Any]:
    return _write_timeout_adaptation_state(cfg, {"last_boss_runtime_checks": checks if isinstance(checks, dict) else {}})


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


def _git_is_ancestor_commit(repo_root: Path, *, ancestor: str, descendant: str) -> bool | None:
    ancestor_text = str(ancestor or "").strip()
    descendant_text = str(descendant or "").strip()
    if not ancestor_text or not descendant_text:
        return None
    code, _out, _err = _git_run(repo_root, "merge-base", "--is-ancestor", ancestor_text, descendant_text)
    if code == 0:
        return True
    if code == 1:
        return False
    return None


def _git_branch_exists(repo_root: Path, branch_name: str) -> bool:
    branch_text = str(branch_name or "").strip()
    if not branch_text:
        return False
    return bool(_git_text(repo_root, "rev-parse", "--verify", f"refs/heads/{branch_text}"))


def _git_resolve_commit(repo_root: Path, ref: str) -> str:
    ref_text = str(ref or "").strip()
    if not ref_text:
        return ""
    return _git_text(repo_root, "rev-parse", "--verify", f"{ref_text}^{{commit}}")


def _git_current_branch(repo_root: Path) -> str:
    return _git_text(repo_root, "branch", "--show-current")


def _git_conflicted_files(repo_root: Path) -> list[str]:
    code, out, _err = _git_run(repo_root, "diff", "--name-only", "--diff-filter=U")
    if code != 0:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def _git_abort_merge_if_needed(repo_root: Path) -> None:
    merge_head = repo_root / ".git" / "MERGE_HEAD"
    if not merge_head.exists():
        return
    _git_run(repo_root, "merge", "--abort")


def _queue_payload(cycle_number: int, items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "updated_at": utc_now_iso(),
        "cycle_number": int(cycle_number),
        "items": items or [],
    }


def _load_queue_items(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path, default={})
    if not isinstance(payload, dict):
        return []
    items = payload.get("items")
    if not isinstance(items, list):
        return []
    return [row for row in items if isinstance(row, dict)]


def _write_queue_items(path: Path, *, cycle_number: int, items: list[dict[str, Any]]) -> None:
    _atomic_write_json(path, _queue_payload(cycle_number, items))


def _merge_queue_item_id(kind: str, target_branch: str, source_commit: str) -> str:
    raw = f"{str(kind or '').strip()}::{str(target_branch or '').strip()}::{str(source_commit or '').strip()}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"merge-{digest}"


def _append_merge_journal(
    cfg: RunConfig,
    *,
    cycle_number: int,
    event: str,
    kind: str,
    lane_id: str,
    task_id: str | None,
    target_branch: str,
    source_commit: str,
    status: str,
    message: str,
    source_ref: str | None = None,
    queue_item_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    row = {
        "schema_version": SCHEMA_VERSION,
        "timestamp": utc_now_iso(),
        "cycle_number": int(cycle_number),
        "event": str(event or "").strip() or "unknown",
        "kind": str(kind or "").strip(),
        "lane_id": str(lane_id or "").strip(),
        "task_id": str(task_id or "").strip() or None,
        "target_branch": str(target_branch or "").strip(),
        "source_commit": str(source_commit or "").strip(),
        "source_ref": str(source_ref or "").strip() or None,
        "queue_item_id": str(queue_item_id or "").strip() or None,
        "status": str(status or "").strip() or "unknown",
        "message": str(message or "").strip(),
        "details": details if isinstance(details, dict) else {},
    }
    _append_jsonl(cfg.repo_root / MERGE_JOURNAL_FILE, row)


def _upsert_merge_queue_item(
    items_by_id: dict[str, dict[str, Any]],
    *,
    cycle_number: int,
    kind: str,
    lane_id: str,
    task_id: str | None,
    target_branch: str,
    source_commit: str,
    source_ref: str | None,
    failure_reason_code: str,
    failure_message: str,
) -> dict[str, Any]:
    queue_item_id = _merge_queue_item_id(kind, target_branch, source_commit)
    existing = items_by_id.get(queue_item_id)
    now_iso = utc_now_iso()
    if existing is None:
        row = {
            "queue_item_id": queue_item_id,
            "kind": str(kind or "").strip(),
            "lane_id": str(lane_id or "").strip(),
            "task_id": str(task_id or "").strip() or None,
            "target_branch": str(target_branch or "").strip(),
            "source_commit": str(source_commit or "").strip(),
            "source_ref": str(source_ref or "").strip() or None,
            "first_failed_cycle": int(cycle_number),
            "last_failed_cycle": int(cycle_number),
            "attempt_count": 1,
            "failure_reason_code": str(failure_reason_code or "").strip() or "merge_failed",
            "failure_message": str(failure_message or "").strip() or "merge failed",
            "status": "queued",
            "updated_at": now_iso,
        }
        items_by_id[queue_item_id] = row
        return row
    existing["last_failed_cycle"] = int(cycle_number)
    existing["attempt_count"] = int(existing.get("attempt_count") or 0) + 1
    existing["failure_reason_code"] = str(failure_reason_code or "").strip() or "merge_failed"
    existing["failure_message"] = str(failure_message or "").strip() or "merge failed"
    existing["status"] = "queued"
    existing["updated_at"] = now_iso
    if task_id:
        existing["task_id"] = str(task_id).strip()
    if source_ref:
        existing["source_ref"] = str(source_ref).strip()
    return existing


def _remove_queue_item(items_by_id: dict[str, dict[str, Any]], kind: str, target_branch: str, source_commit: str) -> str | None:
    queue_item_id = _merge_queue_item_id(kind, target_branch, source_commit)
    removed = items_by_id.pop(queue_item_id, None)
    if isinstance(removed, dict):
        return queue_item_id
    return None


def _git_merge_source_into_target(
    repo_root: Path,
    *,
    target_branch: str,
    source_spec: str,
) -> dict[str, Any]:
    target_text = str(target_branch or "").strip()
    source_text = str(source_spec or "").strip()
    if not target_text or not source_text:
        return {"ok": False, "reason_code": "merge_input_invalid", "message": "missing merge target or source"}

    original_branch = _git_current_branch(repo_root) or target_text
    checked_out_target = False
    try:
        if original_branch != target_text:
            code, _out, err = _git_run(repo_root, "checkout", target_text)
            if code != 0:
                return {
                    "ok": False,
                    "reason_code": "target_checkout_failed",
                    "message": f"cannot checkout target branch '{target_text}': {err or 'unknown git error'}",
                }
            checked_out_target = True

        code, out, err = _git_run(repo_root, "merge", "--no-ff", "--no-edit", source_text)
        if code == 0:
            merged_sha = _git_text(repo_root, "rev-parse", "HEAD")
            return {
                "ok": True,
                "reason_code": "merged",
                "message": out or f"merged {source_text} into {target_text}",
                "merged_sha": merged_sha,
            }

        conflicted_files = _git_conflicted_files(repo_root)
        _git_abort_merge_if_needed(repo_root)
        return {
            "ok": False,
            "reason_code": "git_merge_conflict" if conflicted_files else "git_merge_failed",
            "message": err or out or f"git merge failed for {source_text} -> {target_text}",
            "conflicted_files": conflicted_files,
        }
    finally:
        if checked_out_target and original_branch and original_branch != target_text:
            _git_run(repo_root, "checkout", original_branch)


def _reason_code(value: Any, *, fallback: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", str(value or "")).strip("_").upper()
    if not text:
        text = fallback
    return text[:96]


def _is_watchdog_terminal_reason(value: Any) -> bool:
    reason = str(value or "").strip()
    return reason in WATCHDOG_TERMINAL_STOP_REASONS


def _discover_earth_root(repo_root: Path) -> Path | None:
    for candidate in [repo_root, *repo_root.parents]:
        script_path = candidate / "ground-control-hub" / "scripts" / "ground_ingestion_normalize.py"
        contracts_path = candidate / "contracts"
        if script_path.exists() and contracts_path.exists():
            return candidate
    return None


def _trace_identity_context(cfg: RunConfig, cycle_number: int) -> dict[str, str]:
    base_identity = _canonical_identity_for_cycle(cfg, cycle_number)
    repo_slug = _slugify_identifier(cfg.repo_root.name)
    out = {
        "project_id": base_identity["project_id"],
        "run_id": base_identity["run_id"],
        "plan_id": _canonical_id("plan", "op-simple-build"),
        "phase_id": _canonical_id("phase", "runtime-orchestration"),
        "lane_id": _canonical_id("lane", "op-simple-cycle"),
        "task_id": _canonical_id("task", f"cycle-{cycle_number:06d}"),
        "repo_slug": repo_slug,
    }
    era_id = base_identity.get("era_id")
    if isinstance(era_id, str) and era_id.strip():
        out["era_id"] = era_id
    return out


def _dispatch_events_for_cycle(cfg: RunConfig, cycle_number: int) -> list[dict[str, Any]]:
    path = cfg.repo_root / DISPATCH_LAUNCH_LOG_FILE
    if not path.exists():
        return []
    try:
        rows = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for raw in rows:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        try:
            row_cycle = int(payload.get("cycle_number") or 0)
        except (TypeError, ValueError):
            row_cycle = 0
        if row_cycle == cycle_number:
            out.append(payload)
    return out


def _latest_dispatch_event_for_cycle(cfg: RunConfig, cycle_number: int) -> dict[str, Any]:
    rows = _dispatch_events_for_cycle(cfg, cycle_number)
    return rows[-1] if rows else {}


def _manager_events_for_cycle(cfg: RunConfig, cycle_number: int) -> list[dict[str, Any]]:
    path = cfg.repo_root / MANAGER_CALL_LOG_FILE
    if not path.exists():
        return []
    try:
        rows = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for raw in rows:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        try:
            row_cycle = int(payload.get("cycle_number") or 0)
        except (TypeError, ValueError):
            row_cycle = 0
        if row_cycle != cycle_number:
            continue
        out.append(payload)
    return out


def _latest_manager_event_for_cycle(cfg: RunConfig, *, cycle_number: int, manager_name: str) -> dict[str, Any]:
    for payload in reversed(_manager_events_for_cycle(cfg, cycle_number)):
        if str(payload.get("manager") or "").strip() != manager_name:
            continue
        return payload
    return {}


def _manager_profile_alias_from_log_row(row: dict[str, Any]) -> str | None:
    alias = str(row.get("profile_alias") or "").strip()
    if alias:
        return alias
    message = str(row.get("message") or "").strip()
    if not message:
        return None
    match = MANAGER_PROFILE_ALIAS_REGEX.search(message)
    if not match:
        return None
    parsed = str(match.group(1) or "").strip()
    return parsed or None


def _coerce_non_negative_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return parsed


def _normalize_prompt_complexity_score(value: Any) -> int | None:
    parsed = _coerce_non_negative_int(value)
    if parsed is None:
        return None
    return max(0, min(100, parsed))


def _coerce_bool(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "1", "yes", "y", "on"}:
            return True
        if text in {"false", "0", "no", "n", "off"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _normalize_string_list(payload: Any) -> list[str]:
    if not isinstance(payload, list):
        return []
    out: list[str] = []
    for item in payload:
        text = str(item or "").strip()
        if not text:
            continue
        out.append(text)
    return list(dict.fromkeys(out))


def _normalize_llm_hardening_payload(payload: Any) -> dict[str, Any]:
    row = payload if isinstance(payload, dict) else {}
    checker_result = str(row.get("checker_result") or "").strip().lower()
    if checker_result not in LLM_HARDENING_CHECKER_RESULTS:
        checker_result = "not_applicable"
    risk_level = str(row.get("risk_level") or "").strip().lower()
    if risk_level not in LLM_HARDENING_RISK_LEVELS:
        risk_level = ""

    out = {
        "mini_jobs": _coerce_non_negative_int(row.get("mini_jobs")),
        "prompt_complexity_score": _normalize_prompt_complexity_score(row.get("prompt_complexity_score")),
        "checker_result": checker_result,
        "checker_id": str(row.get("checker_id") or "").strip() or None,
        "override_applied": _coerce_bool(row.get("override_applied"), default=False),
        "override_reason_code": str(row.get("override_reason_code") or "").strip() or None,
        "override_explanation": str(row.get("override_explanation") or "").strip() or None,
        "override_evidence_refs": _normalize_string_list(row.get("override_evidence_refs")),
        "risk_level": risk_level or None,
        "fallback_or_followup_action": str(row.get("fallback_or_followup_action") or "").strip() or None,
    }
    if not out["override_applied"]:
        out["override_reason_code"] = None
        out["override_explanation"] = None
        out["override_evidence_refs"] = []
        out["risk_level"] = None
        out["fallback_or_followup_action"] = None
    return out


def _extract_manager_llm_hardening(
    cfg: RunConfig,
    *,
    manager_name: str,
    expected_artifacts: list[str],
    cycle_number: int,
) -> tuple[dict[str, Any], bool, str | None]:
    artifact_candidates: list[str] = list(expected_artifacts)
    if manager_name == "BOSS" and "cycle_manager_decision" not in artifact_candidates:
        artifact_candidates.append("cycle_manager_decision")
    if manager_name == "wrapup-manager" and "wrapup_manager_report" not in artifact_candidates:
        artifact_candidates.append("wrapup_manager_report")

    for artifact_key in artifact_candidates:
        path_ref = ARTIFACT_FILES.get(artifact_key)
        if path_ref is None:
            continue
        artifact_path = cfg.repo_root / path_ref
        if not artifact_path.exists():
            continue
        payload = _read_json(artifact_path, default=None)
        if not isinstance(payload, dict):
            continue
        if "cycle_number" in payload:
            try:
                artifact_cycle = int(payload.get("cycle_number"))
            except (TypeError, ValueError):
                continue
            if artifact_cycle != cycle_number:
                continue
        llm_hardening = payload.get("llm_hardening")
        if not isinstance(llm_hardening, dict):
            continue
        return _normalize_llm_hardening_payload(llm_hardening), True, artifact_key
    return _normalize_llm_hardening_payload({}), False, None


def _manager_llm_metadata(cfg: RunConfig, *, manager_name: str, log_row: dict[str, Any] | None) -> dict[str, Any]:
    row = log_row if isinstance(log_row, dict) else {}
    provider = _normalize_executor_provider(row.get("executor_provider") or cfg.executor_provider)
    model_from_row = str(row.get("executor_model") or "").strip() or None
    model = model_from_row or _resolve_executor_model(
        cfg,
        provider=provider,
        model_override=cfg.executor_model or (cfg.boss_model if manager_name == "BOSS" else None),
    )
    profile_alias = _manager_profile_alias_from_log_row(row)
    reasoning_effort = str(row.get("reasoning_effort") or "").strip() or (
        str(cfg.boss_reasoning_effort).strip() if manager_name == "BOSS" else ""
    )
    tooling_effort = str(row.get("tooling_effort") or "").strip() or (
        "medium_tooling" if manager_name in {"BOSS", "wrapup-manager"} else ""
    )
    llm_hardening = _normalize_llm_hardening_payload(row)
    telemetry_state = str(row.get("llm_hardening_state") or "").strip().lower()
    if telemetry_state not in LLM_HARDENING_TELEMETRY_STATES:
        telemetry_state = "unknown"
    telemetry_source = str(row.get("llm_hardening_source") or "").strip() or None
    if telemetry_state != "present":
        telemetry_source = None

    out = {
        "role": "manager",
        "manager_name": manager_name,
        "provider": provider,
        "model": model or None,
        "profile_alias": profile_alias,
        "reasoning_effort": reasoning_effort or None,
        "tooling_effort": tooling_effort or None,
        "mini_jobs": llm_hardening.get("mini_jobs"),
        "prompt_complexity_score": llm_hardening.get("prompt_complexity_score"),
        "checker_result": llm_hardening.get("checker_result"),
        "checker_id": llm_hardening.get("checker_id"),
        "override_applied": bool(llm_hardening.get("override_applied")),
        "override_reason_code": llm_hardening.get("override_reason_code"),
        "override_explanation": llm_hardening.get("override_explanation"),
        "override_evidence_refs": llm_hardening.get("override_evidence_refs") or None,
        "risk_level": llm_hardening.get("risk_level"),
        "fallback_or_followup_action": llm_hardening.get("fallback_or_followup_action"),
        "hardening_telemetry_state": telemetry_state,
        "hardening_telemetry_source": telemetry_source,
    }
    return {key: value for key, value in out.items() if value is not None and str(value).strip() != ""}


def _dispatch_routing_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    provider_stats: dict[str, dict[str, int]] = {}
    model_stats: dict[str, dict[str, int]] = {}
    profile_stats: dict[str, dict[str, int]] = {}

    def _ensure_bucket(container: dict[str, dict[str, int]], key: str) -> dict[str, int]:
        bucket = container.get(key)
        if bucket is None:
            bucket = {"attempted": 0, "launched": 0, "launch_failed": 0, "unknown": 0}
            container[key] = bucket
        return bucket

    def _apply_status(bucket: dict[str, int], status: str) -> None:
        bucket["attempted"] += 1
        if status == "launched":
            bucket["launched"] += 1
        elif status == "launch_failed":
            bucket["launch_failed"] += 1
        else:
            bucket["unknown"] += 1

    for row in rows:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "").strip().lower() or "unknown"
        provider_raw = str(row.get("executor_provider") or "").strip().lower()
        provider = provider_raw if provider_raw in EXECUTOR_PROVIDERS else "unknown"
        model = str(row.get("executor_model") or "").strip() or "unknown"
        profile = str(row.get("profile_alias") or "").strip() or "none"
        _apply_status(_ensure_bucket(provider_stats, provider), status)
        _apply_status(_ensure_bucket(model_stats, model), status)
        _apply_status(_ensure_bucket(profile_stats, profile), status)

    return {
        "rows_observed": len(rows),
        "provider_stats": provider_stats,
        "model_stats": model_stats,
        "profile_stats": profile_stats,
    }


def _emit_additional_manager_trace_events(
    cfg: RunConfig,
    *,
    cycle_number: int,
    identity: dict[str, Any],
    source_payload: dict[str, Any],
    excluded_managers: set[str] | None = None,
) -> list[str]:
    trace_errors: list[str] = []
    excluded = {str(item or "").strip() for item in (excluded_managers or set())}
    rows = _manager_events_for_cycle(cfg, cycle_number)
    for idx, row in enumerate(rows):
        manager_name = str(row.get("manager") or "").strip()
        if not manager_name or manager_name in excluded:
            continue
        manager_slug = _slugify_identifier(manager_name)
        manager_event_id = _canonical_id(
            "event",
            f"{identity['repo_slug']}-c{cycle_number:06d}-manager-{manager_slug}-{idx + 1}",
        )
        manager_decision_id = _canonical_id(
            "decision",
            f"{identity['repo_slug']}-c{cycle_number:06d}-manager-{manager_slug}-{idx + 1}",
        )
        message = str(row.get("message") or "").strip()
        rationale = (
            message
            if len(message) >= 10
            else f"Runtime manager {manager_name} invocation status was recorded for cycle {cycle_number}."
        )
        status = str(row.get("status") or "").strip().lower()
        timeout = bool(row.get("timeout"))
        if status == "ok":
            outcome_status = "success"
        elif timeout or status == "timeout":
            outcome_status = "blocked"
        elif status in {"failed", "error"}:
            outcome_status = "failure"
        else:
            outcome_status = "partial"
        reason_code = _reason_code(row.get("reason_code"), fallback=f"MANAGER_{manager_slug.upper()}_STATUS_RECORDED")
        llm_meta = _manager_llm_metadata(cfg, manager_name=manager_name, log_row=row)
        manager_inputs: dict[str, Any] = {
            "manager_name": manager_name,
            "status": status or "unknown",
            "timeout": timeout,
        }
        if llm_meta:
            manager_inputs["llm"] = llm_meta
        manager_metrics: dict[str, Any] = {}
        try:
            duration_seconds = float(row.get("duration_seconds"))
        except (TypeError, ValueError):
            duration_seconds = None
        if duration_seconds is not None and duration_seconds >= 0:
            manager_metrics["duration_seconds"] = duration_seconds
        returncode = row.get("returncode")
        if isinstance(returncode, int):
            manager_metrics["returncode"] = returncode
        event = {
            "schema_version": TRACE_EVENT_SCHEMA_VERSION,
            "event_name": "runtime.manager.invocation",
            "timestamp_utc": str(row.get("finished_at") or row.get("started_at") or utc_now_iso()),
            "identity": {
                "project_id": identity["project_id"],
                "era_id": identity.get("era_id"),
                "plan_id": identity["plan_id"],
                "phase_id": identity["phase_id"],
                "lane_id": identity["lane_id"],
                "task_id": identity["task_id"],
                "run_id": identity["run_id"],
                "thread_id": _canonical_id("thread", f"{identity['repo_slug']}-manager-{manager_slug}"),
                "event_id": manager_event_id,
                "decision_id": manager_decision_id,
            },
            "actor": {"type": "manager", "id": manager_slug},
            "decision": {
                "question": f"How did manager '{manager_name}' invocation resolve in cycle {cycle_number}?",
                "rationale": rationale,
                "reason_codes": [reason_code],
            },
            "operation": {
                "name": "invoke_manager",
                "intent": "Capture manager invocation telemetry for this cycle.",
                "inputs": manager_inputs,
            },
            "outcome": {
                "status": outcome_status,
                "summary": f"manager={manager_name} status={status or 'unknown'} timeout={str(timeout).lower()}",
                "error_code": reason_code if outcome_status in {"failure", "blocked"} else None,
                "retryable": timeout,
                "metrics": manager_metrics,
            },
            "risk": {"level": "low" if outcome_status == "success" else "medium"},
            "evidence": {
                "artifacts": [
                    {
                        "artifact_id": _canonical_id(
                            "artifact",
                            f"{identity['repo_slug']}-c{cycle_number:06d}-manager-log-{manager_slug}-{idx + 1}",
                        ),
                        "kind": "manager_call_log",
                        "uri": str(MANAGER_CALL_LOG_FILE),
                    }
                ]
            },
            "source": source_payload,
        }
        event_identity = event.get("identity")
        if isinstance(event_identity, dict):
            event["identity"] = {k: v for k, v in event_identity.items() if v is not None}
        try:
            _emit_trace_event_envelope(cfg, cycle_number=cycle_number, payload=event)
        except SimpleBuildError as exc:
            trace_errors.append(f"additional manager trace emission failed ({manager_name}): {exc.message}")
    return trace_errors


def _emit_cycle_trace_events(
    cfg: RunConfig,
    *,
    cycle_number: int,
    dispatch_counts: dict[str, int],
) -> list[str]:
    trace_errors: list[str] = []
    decision_payload = _read_cycle_decision(cfg)
    identity = _trace_identity_context(cfg, cycle_number)
    repo_name = cfg.repo_root.name
    repo_branch = _git_text(cfg.repo_root, "branch", "--show-current") or ""
    commit_sha = _git_text(cfg.repo_root, "rev-parse", "HEAD") or ""
    source_payload: dict[str, Any] = {
        "repo": repo_name,
        "branch": repo_branch,
    }
    if commit_sha and TRACE_EVENT_SOURCE_SHA_REGEX.fullmatch(commit_sha):
        source_payload["commit_sha"] = commit_sha

    def _normalize_event_ts(value: Any) -> str:
        text = str(value or "").strip()
        if text and TRACE_EVENT_TIMESTAMP_REGEX.fullmatch(text):
            return text
        return utc_now_iso()

    manager_log_row = _latest_manager_event_for_cycle(cfg, cycle_number=cycle_number, manager_name="BOSS")
    manager_llm = _manager_llm_metadata(cfg, manager_name="BOSS", log_row=manager_log_row)
    manager_inputs = {
        "decision": str(decision_payload.get("decision") or "").strip() or None,
        "reason_code": str(decision_payload.get("reason_code") or "").strip() or None,
        "worker_registry_ready": bool(decision_payload.get("worker_registry_ready")),
    }
    if manager_llm:
        manager_inputs["llm"] = manager_llm
    manager_inputs = {k: v for k, v in manager_inputs.items() if v is not None}

    manager_metrics: dict[str, Any] = {}
    try:
        manager_duration = float(manager_log_row.get("duration_seconds"))
    except (TypeError, ValueError):
        manager_duration = None
    if manager_duration is not None and manager_duration >= 0:
        manager_metrics["duration_seconds"] = manager_duration
    if "timeout" in manager_log_row:
        manager_metrics["timeout"] = bool(manager_log_row.get("timeout"))

    manager_reason_code = _reason_code(decision_payload.get("reason_code"), fallback="CYCLE_DECISION_RECORDED")
    manager_event_id = _canonical_id("event", f"{identity['repo_slug']}-c{cycle_number:06d}-manager")
    manager_decision_id = _canonical_id("decision", f"{identity['repo_slug']}-c{cycle_number:06d}-manager")
    manager_artifact_id = _canonical_id(
        "artifact",
        f"{identity['repo_slug']}-c{cycle_number:06d}-cycle-manager-decision",
    )
    manager_timestamp = _normalize_event_ts(decision_payload.get("updated_at"))
    manager_decision = str(decision_payload.get("decision") or "").strip().lower()
    manager_outcome_status = "success" if manager_decision == "proceed" else "blocked"
    manager_rationale = str(decision_payload.get("message") or "").strip()
    if len(manager_rationale) < 10:
        manager_rationale = "Cycle manager decision persisted to keep orchestration state deterministic."
    manager_event = {
        "schema_version": TRACE_EVENT_SCHEMA_VERSION,
        "event_name": "runtime.manager.cycle_decision",
        "timestamp_utc": manager_timestamp,
        "identity": {
            "project_id": identity["project_id"],
            "era_id": identity.get("era_id"),
            "plan_id": identity["plan_id"],
            "phase_id": identity["phase_id"],
            "lane_id": identity["lane_id"],
            "task_id": identity["task_id"],
            "run_id": identity["run_id"],
            "thread_id": _canonical_id("thread", f"{identity['repo_slug']}-manager-boss"),
            "event_id": manager_event_id,
            "decision_id": manager_decision_id,
        },
        "actor": {"type": "manager", "id": "boss-manager"},
        "decision": {
            "question": "Should this cycle proceed?",
            "rationale": manager_rationale,
            "reason_codes": [manager_reason_code],
        },
        "operation": {
            "name": "write_cycle_manager_decision",
            "intent": "Persist deterministic cycle manager decision for the current OP simple cycle.",
            "inputs": manager_inputs,
        },
        "outcome": {
            "status": manager_outcome_status,
            "summary": f"Cycle {cycle_number} decision={decision_payload.get('decision')}.",
            "metrics": manager_metrics,
        },
        "risk": {"level": "low"},
        "evidence": {
            "artifacts": [
                {
                    "artifact_id": manager_artifact_id,
                    "kind": "cycle_manager_decision",
                    "uri": str(ARTIFACT_FILES["cycle_manager_decision"]),
                }
            ]
        },
        "source": source_payload,
    }
    manager_identity = manager_event.get("identity")
    if isinstance(manager_identity, dict):
        manager_event["identity"] = {k: v for k, v in manager_identity.items() if v is not None}
    try:
        _emit_trace_event_envelope(cfg, cycle_number=cycle_number, payload=manager_event)
    except SimpleBuildError as exc:
        trace_errors.append(f"manager trace emission failed: {exc.message}")
    trace_errors.extend(
        _emit_additional_manager_trace_events(
            cfg,
            cycle_number=cycle_number,
            identity=identity,
            source_payload=source_payload,
            excluded_managers={"BOSS"},
        )
    )

    dispatch_attempted = int(dispatch_counts.get("attempted") or 0)
    dispatch_launched = int(dispatch_counts.get("launched") or 0)
    dispatch_failed = int(dispatch_counts.get("launch_failed") or 0)
    dispatch_unknown = int(dispatch_counts.get("unknown") or 0)
    dispatch_rows = _dispatch_events_for_cycle(cfg, cycle_number)
    dispatch_row = dispatch_rows[-1] if dispatch_rows else {}
    dispatch_timestamp = _normalize_event_ts(dispatch_row.get("timestamp"))
    dispatch_routing = _dispatch_routing_summary(dispatch_rows)
    dispatch_inputs = {
        "dispatch_counts": {
            "attempted": dispatch_attempted,
            "launched": dispatch_launched,
            "launch_failed": dispatch_failed,
            "unknown": dispatch_unknown,
        },
        "routing": dispatch_routing,
    }
    dispatch_metrics = {
        "rows_observed": int(dispatch_routing.get("rows_observed") or 0),
        "providers_observed": len(dispatch_routing.get("provider_stats") or {}),
        "models_observed": len(dispatch_routing.get("model_stats") or {}),
        "profiles_observed": len(dispatch_routing.get("profile_stats") or {}),
    }
    dispatch_event_id = _canonical_id("event", f"{identity['repo_slug']}-c{cycle_number:06d}-dispatch")
    dispatch_decision_id = _canonical_id("decision", f"{identity['repo_slug']}-c{cycle_number:06d}-dispatch")
    dispatch_status = "noop"
    if dispatch_attempted > 0 and dispatch_launched > 0 and dispatch_failed == 0 and dispatch_unknown == 0:
        dispatch_status = "success"
    elif dispatch_failed > 0 and dispatch_launched == 0:
        dispatch_status = "failure"
    elif dispatch_attempted > 0:
        dispatch_status = "partial"
    dispatch_event = {
        "schema_version": TRACE_EVENT_SCHEMA_VERSION,
        "event_name": "runtime.dispatch.launch_cycle",
        "timestamp_utc": dispatch_timestamp,
        "identity": {
            "project_id": identity["project_id"],
            "era_id": identity.get("era_id"),
            "plan_id": identity["plan_id"],
            "phase_id": identity["phase_id"],
            "lane_id": identity["lane_id"],
            "task_id": identity["task_id"],
            "run_id": identity["run_id"],
            "thread_id": _canonical_id("thread", f"{identity['repo_slug']}-work-dispatcher"),
            "event_id": dispatch_event_id,
            "decision_id": dispatch_decision_id,
        },
        "actor": {"type": "service", "id": "work-dispatcher"},
        "decision": {
            "question": "Should dispatch launch worker packets in this cycle?",
            "rationale": (
                f"dispatch attempted={dispatch_attempted} launched={dispatch_launched} "
                f"failed={dispatch_failed} unknown={dispatch_unknown}"
            ),
            "reason_codes": ["DISPATCH_COUNTS_RECORDED"],
        },
        "operation": {
            "name": "dispatch_packets",
            "intent": "Launch available worker packets according to runtime policies and capacity limits.",
            "inputs": dispatch_inputs,
        },
        "outcome": {
            "status": dispatch_status,
            "summary": (
                f"Cycle {cycle_number} dispatch attempted={dispatch_attempted}, launched={dispatch_launched}, "
                f"failed={dispatch_failed}, unknown={dispatch_unknown}."
            ),
            "metrics": dispatch_metrics,
        },
        "risk": {"level": "medium" if dispatch_attempted > 0 else "low"},
        "evidence": {
            "artifacts": [
                {
                    "artifact_id": _canonical_id(
                        "artifact",
                        f"{identity['repo_slug']}-c{cycle_number:06d}-dispatch-launch-log",
                    ),
                    "kind": "dispatch_launch_log",
                    "uri": str(DISPATCH_LAUNCH_LOG_FILE),
                },
                {
                    "artifact_id": _canonical_id(
                        "artifact",
                        f"{identity['repo_slug']}-c{cycle_number:06d}-dispatch-registry",
                    ),
                    "kind": "dispatch_registry",
                    "uri": str(ARTIFACT_FILES["dispatch_registry"]),
                },
            ]
        },
        "source": source_payload,
    }
    dispatch_identity = dispatch_event.get("identity")
    if isinstance(dispatch_identity, dict):
        dispatch_event["identity"] = {k: v for k, v in dispatch_identity.items() if v is not None}
    try:
        _emit_trace_event_envelope(cfg, cycle_number=cycle_number, payload=dispatch_event)
    except SimpleBuildError as exc:
        trace_errors.append(f"dispatch trace emission failed: {exc.message}")
    return trace_errors


def _project_trace_snapshot_path(earth_root: Path, project_id: str) -> Path:
    return earth_root / "reports" / "ground-ingest-inputs" / project_id / GROUND_SYNC_SNAPSHOT_BASENAME


def _sync_trace_snapshot_to_ground_inbox(cfg: RunConfig, *, earth_root: Path, project_id: str) -> Path:
    source = cfg.repo_root / TRACE_EVENT_LOG_FILE
    target = _project_trace_snapshot_path(earth_root, project_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    text = source.read_text(encoding="utf-8")
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(target)
    return target


def _collect_ground_ingest_inputs(earth_root: Path) -> list[Path]:
    base = earth_root / "reports" / "ground-ingest-inputs"
    if not base.exists():
        return []
    rows: list[Path] = []
    for path in sorted(base.rglob(GROUND_SYNC_SNAPSHOT_BASENAME)):
        if not path.is_file():
            continue
        try:
            if path.stat().st_size <= 0:
                continue
        except OSError:
            continue
        rows.append(path.resolve())
    return rows


def _run_ground_sync(
    cfg: RunConfig,
    *,
    cycle_number: int,
    trigger: str,
) -> tuple[str, str]:
    if cfg.dry_run:
        return "skipped_dry_run", "ground sync skipped for dry run"
    earth_root = _discover_earth_root(cfg.repo_root)
    if earth_root is None:
        return "skipped_no_earth_root", "ground sync skipped: Earth root not detected"

    identity = _trace_identity_context(cfg, cycle_number)
    source_trace = cfg.repo_root / TRACE_EVENT_LOG_FILE
    if not source_trace.exists():
        return "skipped_no_trace_file", f"ground sync skipped: missing trace file {source_trace}"

    script_path = earth_root / "ground-control-hub" / "scripts" / "ground_ingestion_normalize.py"
    if not script_path.exists():
        return "skipped_no_ground_script", f"ground sync skipped: normalizer script missing at {script_path}"

    try:
        snapshot_path = _sync_trace_snapshot_to_ground_inbox(
            cfg,
            earth_root=earth_root,
            project_id=identity["project_id"],
        )
    except OSError as exc:
        return "failed", f"ground sync snapshot write failed: {exc}"

    inputs = _collect_ground_ingest_inputs(earth_root)
    if not inputs:
        return "skipped_no_inputs", "ground sync skipped: no ingest input snapshots discovered"

    output_graph = earth_root / "ground-control-hub" / "artifacts" / "ground_portfolio_graph.v1.json"
    output_normalized = earth_root / "ground-control-hub" / "artifacts" / "ground_normalized_events.v1.jsonl"
    checkpoint_state = earth_root / "ground-control-hub" / "artifacts" / "ground_ingestion_checkpoint.v1.json"
    cmd: list[str] = ["python3", str(script_path)]
    for path in inputs:
        cmd.extend(["--trace-jsonl", str(path)])
    cmd.extend(
        [
            "--output",
            str(output_graph),
            "--normalized-events-output",
            str(output_normalized),
            "--checkpoint-state",
            str(checkpoint_state),
            "--lock-timeout-seconds",
            str(max(30, int(cfg.ground_sync_timeout_seconds))),
        ]
    )
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cfg.repo_root),
            capture_output=True,
            text=True,
            timeout=max(30, int(cfg.ground_sync_timeout_seconds)),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return "failed", "ground sync timed out while running normalizer"
    if proc.returncode != 0:
        detail = (proc.stderr or "").strip() or (proc.stdout or "").strip() or "unknown error"
        return "failed", f"ground sync normalizer failed: {detail}"
    return (
        "ok",
        (
            f"ground sync completed trigger={trigger} snapshot={snapshot_path} "
            f"inputs={len(inputs)} output={output_graph}"
        ),
    )


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


def inspect_resume_run_base_meta(repo_root: Path, *, run_base_source_branch: str | None = None) -> dict[str, Any]:
    state = _read_json(repo_root / INITIALIZE_STATE_FILE, default={})
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
    branch_commit = _git_text(repo_root, "rev-parse", "--verify", ref)
    if not branch_commit:
        raise SimpleBuildError(
            "op_simple_resume_missing_branch",
            f"Cannot resume /op-simple-build: run base branch '{run_base_branch}' does not exist.",
        )

    return {
        "run_base_branch": run_base_branch,
        "run_base_from_branch": str(run_context.get("run_base_from_branch") or run_base_source_branch or "main"),
        "run_base_from_commit": str(run_context.get("run_base_from_commit") or branch_commit),
        "run_base_created_at": str(run_context.get("run_base_created_at") or utc_now_iso()),
        "created_new": False,
        "dry_run": False,
    }


def _load_resume_run_base_meta(cfg: RunConfig) -> dict[str, Any]:
    out = inspect_resume_run_base_meta(cfg.repo_root, run_base_source_branch=cfg.run_base_source_branch)
    if not cfg.dry_run:
        code, _out, err = _git_run(cfg.repo_root, "checkout", str(out["run_base_branch"]))
        if code != 0:
            raise SimpleBuildError(
                "op_simple_resume_checkout_failed",
                f"Cannot checkout run base branch '{str(out['run_base_branch'])}' for resume: {err or 'unknown git error'}",
            )
    out["dry_run"] = bool(cfg.dry_run)
    return out


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
            "worktrees_parent": str(DEFAULT_WORKTREES_PARENT),
            "selected_aliases": [],
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
    workflow["worktrees_parent"] = str(cfg.worktrees_parent)
    workflow["selected_aliases"] = list(cfg.selected_aliases or [])
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
                "current_task_provider": None,
                "next_task_provider": None,
                "current_task_model": None,
                "next_task_model": None,
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
    expected_parent = cfg.worktrees_parent.expanduser().resolve()

    if not force_refresh and isinstance(payload, dict):
        payload_parent_raw = str(payload.get("worktrees_parent") or "").strip()
        payload_parent_ok = False
        if payload_parent_raw:
            try:
                payload_parent_ok = Path(payload_parent_raw).expanduser().resolve() == expected_parent
            except OSError:
                payload_parent_ok = False
        rows = payload.get("workstations")
        if payload_parent_ok and isinstance(rows, list) and rows:
            valid_rows = []
            for idx, row in enumerate(rows[:max_slots], start=1):
                if not isinstance(row, dict):
                    continue
                workstation_id = _workstation_id_for_index(cfg, idx)
                if str(row.get("workstation_id") or "").strip() != workstation_id:
                    continue
                branch_ok = str(row.get("branch") or "").strip().startswith(run_base_branch)
                worktree_raw = str(row.get("worktree") or "").strip()
                worktree_ok = False
                if worktree_raw:
                    try:
                        worktree_path = Path(worktree_raw).expanduser().resolve()
                    except OSError:
                        worktree_path = None
                    if (
                        isinstance(worktree_path, Path)
                        and worktree_path.exists()
                        and worktree_path.is_dir()
                        and worktree_path.name == workstation_id
                        and _path_within_parent(worktree_path, expected_parent)
                    ):
                        worktree_ok = True
                if branch_ok and worktree_ok:
                    valid_rows.append(row)
            if len(valid_rows) == max_slots:
                return payload

    if cfg.dry_run:
        current_sha = _git_text(cfg.repo_root, "rev-parse", "HEAD") or ""
        rows = []
        for idx in range(1, max_slots + 1):
            workstation_id = _workstation_id_for_index(cfg, idx)
            rows.append(
                {
                    "workstation_id": workstation_id,
                    "branch": f"{run_base_branch}-w{idx:02d}",
                    "worktree": str((expected_parent / workstation_id).resolve()),
                    "prepared_at": utc_now_iso(),
                    "status": "prepared",
                    "preparation_notes": "dry-run baseline",
                    "git_head_sha": current_sha,
                }
            )
        out = {
            "schema_version": SCHEMA_VERSION,
            "prepared_at": utc_now_iso(),
            "worktrees_parent": str(expected_parent),
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
        workstation_id = _workstation_id_for_index(cfg, idx)
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
            str(expected_parent),
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

        expected_target_path = (expected_parent / workstation_id).resolve()
        target_path = str(parsed.get("target_path") or expected_target_path)
        resolved_branch = str(parsed.get("branch_name_resolved") or worker_branch)
        try:
            resolved_target_path = Path(target_path).expanduser().resolve()
        except OSError:
            failures.append(f"{workstation_id}: invalid target_path")
            continue
        if resolved_target_path != expected_target_path:
            failures.append(
                f"{workstation_id}: target_path mismatch (expected {expected_target_path}, got {resolved_target_path})"
            )
            continue
        if not resolved_target_path.exists() or not resolved_target_path.is_dir():
            failures.append(f"{workstation_id}: target_path missing or not a directory")
            continue
        head_sha = _git_text(resolved_target_path, "rev-parse", "HEAD") if target_path else ""
        prepared_rows.append(
            {
                "workstation_id": workstation_id,
                "branch": resolved_branch,
                "worktree": str(resolved_target_path),
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
        "worktrees_parent": str(expected_parent),
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
            "cycle_mode": "normal",
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
            "lane_base_branches": {},
        },
        "task_execution_state": _task_execution_state_payload(0),
        "worker_registry": {
            "schema_version": SCHEMA_VERSION,
            "updated_at": utc_now_iso(),
            "cycle_number": 0,
            "workers": [],
        },
        "lane_base_watchdog_registry": {
            "schema_version": SCHEMA_VERSION,
            "updated_at": utc_now_iso(),
            "cycle_number": 0,
            "plan_cycle_number": 0,
            "lane_base_branches": {},
            "lanes": [],
            "aggregate": {
                "seen_lane_count": 0,
                "missing_lane_count": 0,
                "latest_seen_commit_sha": "",
                "latest_seen_commit_at_utc": "",
                "latest_seen_commit_age_minutes": None,
                "watchdog_age_offset_minutes": None,
                "watchdog_age_minutes": None,
                "watchdog_target_reset_at_utc": "",
                "progress_signal": "",
                "progress_changed": False,
            },
        },
        "dispatch_registry": {
            "schema_version": SCHEMA_VERSION,
            "updated_at": utc_now_iso(),
            "events": [],
        },
        "cycle_summary": {
            "schema_version": SCHEMA_VERSION,
            "cycle_number": 0,
            "cycle_mode": "normal",
            "manager_statuses": {},
            "task_counts": {"pending": 0, "in_progress": 0, "done": 0, "blocked": 0},
            "dispatch_counts": {"attempted": 0, "launched": 0, "launch_failed": 0, "unknown": 0},
            "project_done": False,
            "insurmountable_blocker": False,
            "termination": {},
            "stop_reason": "",
            "notes": "",
        },
        "mergeability_report": {
            "schema_version": SCHEMA_VERSION,
            "updated_at": utc_now_iso(),
            "cycle_number": 0,
            "cycle_mode": "normal",
            "run_base_ref": "",
            "run_base_sha": "",
            "lane_shas": {},
            "unmerged_commit_count": 0,
            "merge_blockers": [],
            "gate_owner": "none",
            "lane_status": {},
            "lane_merge_gate_pending_cleared_count": 0,
            "mergeability_advanced": False,
            "progression": {
                "done_worker_commits": 0,
                "lane_fan_in_ready": 0,
                "lane_tester_gate_passed": 0,
                "lane_to_run_merge_ready": 0,
            },
        },
        "merge_queue": {
            "schema_version": SCHEMA_VERSION,
            "updated_at": utc_now_iso(),
            "cycle_number": 0,
            "items": [],
        },
        "unmergable_merges": {
            "schema_version": SCHEMA_VERSION,
            "updated_at": utc_now_iso(),
            "cycle_number": 0,
            "items": [],
        },
        "merge_manager_report": {
            "schema_version": SCHEMA_VERSION,
            "updated_at": utc_now_iso(),
            "cycle_number": 0,
            "status": "not_started",
            "summary": "",
            "resolved_items": [],
            "unresolved_items": [],
        },
        "terminal_capsule": {
            "schema_version": SCHEMA_VERSION,
            "updated_at": utc_now_iso(),
            "cycle_number": 0,
            "reason_code": "not_terminal",
            "stop_reason": "",
            "cycle_mode": "normal",
            "manager": None,
            "manager_status": "",
            "manager_timeout": False,
            "manager_message": "",
            "dispatch_counts": {"attempted": 0, "launched": 0, "launch_failed": 0, "unknown": 0},
            "watchdog_signal": {},
            "details": {},
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
            "watchdog_age_offset_minutes": None,
            "watchdog_age_minutes": None,
            "watchdog_target_reset_at_utc": "",
            "run_base_hard_age_offset_minutes": None,
            "run_base_hard_age_minutes": None,
            "run_base_hard_target_reset_at_utc": "",
            "terminal_warning_last_emitted_cycle": None,
            "terminal_warning_last_emitted_at_utc": "",
            "terminal_warning_cooldown_cycles": WATCHDOG_TERMINAL_WARNING_COOLDOWN_CYCLES,
            "lane_aggregate_watchdog_age_minutes": None,
            "lane_seen_branch_count": 0,
            "lane_missing_branch_count": 0,
            "stale_after_minutes": WATCHDOG_STALE_COMMIT_MINUTES,
            "stale": False,
        },
        "llm_profile_mode": {
            "schema_version": SCHEMA_VERSION,
            "updated_at": utc_now_iso(),
            "enabled": False,
            "llm_profile": None,
            "profile_policy": "force_default_codex",
            "rate_policy": None,
        },
        "llm_profile_rate_registry": {
            "schema_version": SCHEMA_VERSION,
            "updated_at": utc_now_iso(),
            "enabled": False,
            "llm_profile": None,
            "limits": {
                "per_minute": int(LLM_PROFILE_PER_MINUTE_LIMIT),
                "per_day": int(LLM_PROFILE_PER_DAY_LIMIT),
            },
            "windows": {
                "minute": {"started_at": utc_now_iso(), "window_seconds": 60, "count": 0},
                "day": {"started_at": utc_now_iso(), "window_seconds": 86400, "count": 0},
            },
            "total_count": 0,
            "last_request_at": None,
            "last_request_source": None,
        },
        "timeout_adaptation_state": {
            "schema_version": SCHEMA_VERSION,
            "updated_at": utc_now_iso(),
            "consecutive_boss_timeouts": 0,
            "timeout_threshold": 2,
            "adaptation_active": False,
            "rotation_required": False,
            "last_timeout_cycle": None,
            "last_timeout_profile_alias": "",
            "last_timeout_reason": "",
            "last_non_timeout_failed_profile_alias": "",
            "last_non_timeout_failed_cycle": None,
            "last_non_timeout_failed_reason": "",
            "last_rotation_decision": {},
            "last_boss_runtime_checks": {},
        },
        "restart_determinism_state": {
            "schema_version": SCHEMA_VERSION,
            "updated_at": utc_now_iso(),
            "scenario": "fresh_start",
            "resume_mode": False,
            "checkpoint_fingerprint": "",
            "last_applied_cycle": 0,
            "idempotent_continuation": False,
            "invariants": {
                "watchdog_resume": {"enabled": True, "last_verified": None},
                "process_kill_resume": {"enabled": True, "last_verified": None},
                "checkpoint_replay": {"enabled": True, "last_verified": None},
            },
            "continuation_log": [],
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
        "lane_base_watchdog_registry",
        "dispatch_registry",
        "cycle_summary",
        "mergeability_report",
        "merge_queue",
        "unmergable_merges",
        "merge_manager_report",
        "terminal_capsule",
        "wrapup_manager_report",
        "watchdog_state",
        "watchdog_exit_signal",
        "workstation_prep",
        "llm_profile_mode",
        "llm_profile_rate_registry",
        "timeout_adaptation_state",
        "restart_determinism_state",
    ]
    for key in reset_keys:
        path = cfg.repo_root / ARTIFACT_FILES[key]
        _safe_unlink(path)
    _safe_unlink(cfg.repo_root / DISPATCH_LAUNCH_LOG_FILE)
    _safe_unlink(cfg.repo_root / BOSS_SESSION_STATE_FILE)
    _safe_unlink(cfg.repo_root / MERGE_JOURNAL_FILE)


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


def _normalize_lane_base_branches(value: Any) -> tuple[dict[str, str], list[dict[str, Any]]]:
    if not isinstance(value, dict):
        return {}, [{"code": "lane_base_branches_missing", "message": "lane_base_branches must be an object map"}]
    normalized: dict[str, str] = {}
    errors: list[dict[str, Any]] = []
    for raw_lane_id, raw_branch in value.items():
        lane_id = str(raw_lane_id or "").strip()
        branch = str(raw_branch or "").strip()
        if not lane_id:
            errors.append(
                {
                    "code": "lane_base_branches_invalid_key",
                    "message": "lane_base_branches contains empty lane_id key",
                    "lane_id": lane_id,
                }
            )
            continue
        if not branch:
            errors.append(
                {
                    "code": "lane_base_branches_invalid_value",
                    "message": f"lane_base_branches[{lane_id}] must be non-empty branch name",
                    "lane_id": lane_id,
                }
            )
            continue
        normalized[lane_id] = branch
    return normalized, errors


def _plan_lane_base_branches_contract(cfg: RunConfig) -> tuple[bool, dict[str, Any]]:
    plan_path = cfg.repo_root / ARTIFACT_FILES["plan_packets"]
    payload = _read_json(plan_path, default={})
    if not isinstance(payload, dict):
        return False, {
            "code": "lane_base_branches_missing",
            "message": "plan_packets must be a JSON object with lane_base_branches map",
            "details": {"plan_packets_path": str(plan_path.resolve())},
        }
    lane_map_raw = payload.get("lane_base_branches")
    lane_map, lane_errors = _normalize_lane_base_branches(lane_map_raw)
    if lane_errors:
        return False, {
            "code": "lane_base_branches_invalid",
            "message": "plan_packets lane_base_branches is malformed",
            "details": {
                "plan_packets_path": str(plan_path.resolve()),
                "errors": lane_errors,
            },
        }
    tasks_raw = payload.get("tasks")
    task_rows = [row for row in tasks_raw if isinstance(row, dict)] if isinstance(tasks_raw, list) else []
    lane_ids = sorted({str(row.get("lane_id") or "").strip() for row in task_rows if str(row.get("lane_id") or "").strip()})
    missing_lane_ids = [lane_id for lane_id in lane_ids if lane_id not in lane_map]
    if missing_lane_ids:
        return False, {
            "code": "lane_base_branches_incomplete",
            "message": (
                "plan_packets lane_base_branches must include every tasks[].lane_id before /op-simple-build can start"
            ),
            "details": {
                "plan_packets_path": str(plan_path.resolve()),
                "missing_lane_ids": missing_lane_ids,
            },
        }
    return True, {
        "lane_base_branches": lane_map,
        "lane_ids": lane_ids,
        "plan_packets_path": str(plan_path.resolve()),
        "plan_cycle_number": int(payload.get("cycle_number") or 0),
    }


def _write_lane_base_watchdog_registry(
    cfg: RunConfig,
    *,
    cycle_number: int,
    lane_base_branches: dict[str, str],
    plan_cycle_number: int | None = None,
) -> None:
    rows = [
        {
            "lane_id": lane_id,
            "lane_base_branch": branch,
            "exists": False,
            "ever_seen": False,
            "first_seen_at": None,
            "first_seen_cycle": None,
            "last_seen_commit_sha": "",
            "last_seen_commit_at_utc": "",
            "last_seen_cycle": None,
        }
        for lane_id, branch in sorted(lane_base_branches.items(), key=lambda item: item[0])
    ]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "updated_at": utc_now_iso(),
        "cycle_number": int(cycle_number),
        "plan_cycle_number": int(plan_cycle_number or 0),
        "lane_base_branches": dict(sorted(lane_base_branches.items(), key=lambda item: item[0])),
        "lanes": rows,
        "aggregate": {
            "seen_lane_count": 0,
            "missing_lane_count": len(rows),
            "latest_seen_commit_sha": "",
            "latest_seen_commit_at_utc": "",
            "latest_seen_commit_age_minutes": None,
            "watchdog_age_offset_minutes": None,
            "watchdog_age_minutes": None,
            "watchdog_target_reset_at_utc": "",
            "progress_signal": "",
            "progress_changed": False,
        },
    }
    _atomic_write_json(cfg.repo_root / ARTIFACT_FILES["lane_base_watchdog_registry"], payload)


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


def _resolve_manager_timeout_seconds(cfg: RunConfig, manager_name: str, *, provider: str) -> int:
    timeout = int(MANAGER_TIMEOUT_SECONDS.get(manager_name, 300))
    resolved_provider = _normalize_executor_provider(provider)
    if resolved_provider == "blackbox":
        timeout = int(BLACKBOX_MANAGER_TIMEOUT_SECONDS.get(manager_name, timeout))
    return max(1, timeout)


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
    codex_profile: str | None = None,
) -> ManagerResult:
    # LLM interaction classification: reasoning_effort=high_effort, tooling_effort=medium_tooling.
    started_at = utc_now_iso()
    start_time = time.monotonic()
    cycle_dir = _ensure_history_cycle_dir(cfg, cycle_number)
    safe_name = manager_name.lower().replace(" ", "-")
    stdout_path = cycle_dir / f"manager-{safe_name}.stdout.log"
    stderr_path = cycle_dir / f"manager-{safe_name}.stderr.log"
    last_message_path = cycle_dir / f"manager-{safe_name}.last_message.txt"

    reasoning_effort_text = str(reasoning_effort or "").strip()
    model_text = str(model or "").strip()
    codex_profile_text = str(codex_profile or "").strip()
    if resume_session_id:
        cmd = [
            "codex",
            "exec",
            "resume",
            "--dangerously-bypass-approvals-and-sandbox",
        ]
        if codex_profile_text:
            cmd.extend(["-p", codex_profile_text])
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
        if codex_profile_text:
            cmd.extend(["-p", codex_profile_text])
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

    if _llm_profile_mode_enabled(cfg):
        allowed, reset_at = _llm_profile_consume_request_budget(
            cfg,
            source=f"manager:{manager_name.lower().replace(' ', '-')}",
        )
        if not allowed:
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
                message=(
                    f"llm profile rate limit active; retry after {reset_at}"
                    if reset_at
                    else "llm profile rate limit active"
                ),
                reason_code="llm_profile_rate_limited",
            )

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
    except subprocess.TimeoutExpired as exc:
        stdout_text = _coerce_output_text(exc.stdout)
        stderr_text = _coerce_output_text(exc.stderr)
        stdout_path.write_text(stdout_text, encoding="utf-8")
        stderr_path.write_text(stderr_text, encoding="utf-8")
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


def _blackbox_exec_prompt(
    cfg: RunConfig,
    manager_name: str,
    cycle_number: int,
    timeout_seconds: int,
    prompt_text: str,
    *,
    model: str | None = None,
) -> ManagerResult:
    # LLM interaction classification: reasoning_effort=medium_effort, tooling_effort=low_tooling.
    started_at = utc_now_iso()
    start_time = time.monotonic()
    cycle_dir = _ensure_history_cycle_dir(cfg, cycle_number)
    safe_name = manager_name.lower().replace(" ", "-")
    stdout_path = cycle_dir / f"manager-{safe_name}.stdout.log"
    stderr_path = cycle_dir / f"manager-{safe_name}.stderr.log"
    scope = "op-simple-build/manager-blackbox"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    cmd, env, prep_error = _build_blackbox_exec_command(cfg, prompt_text, model=model)
    if prep_error:
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
            message=prep_error,
            reason_code="manager_blackbox_prepare_failed",
        )

    try:
        completed = subprocess.run(
            cmd,
            cwd=str(cfg.repo_root),
            text=True,
            capture_output=True,
            timeout=max(1, int(timeout_seconds)),
            check=False,
            env=env,
        )
        stdout_text = _coerce_output_text(completed.stdout)
        stderr_text = _coerce_output_text(completed.stderr)
        stdout_path.write_text(stdout_text, encoding="utf-8")
        stderr_path.write_text(stderr_text, encoding="utf-8")
        _write_new_executor_blob(scope, f"{stamp}-cycle{cycle_number:06d}-{safe_name}.stdout.log", stdout_text)
        _write_new_executor_blob(scope, f"{stamp}-cycle{cycle_number:06d}-{safe_name}.stderr.log", stderr_text)
        _append_new_executor_event(
            scope,
            {
                "schema_version": SCHEMA_VERSION,
                "timestamp": utc_now_iso(),
                "manager": manager_name,
                "cycle_number": int(cycle_number),
                "executor_provider": "blackbox",
                "executor_model": str(model or _resolve_executor_model(cfg, provider="blackbox") or ""),
                "blackbox_lane": _normalize_blackbox_lane(cfg.blackbox_lane),
                "status": "ok" if completed.returncode == 0 else "failed",
                "returncode": int(completed.returncode),
                "timeout_seconds": int(timeout_seconds),
            },
        )
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
            message=None if completed.returncode == 0 else "blackbox returned non-zero",
            reason_code=None if completed.returncode == 0 else "manager_non_zero_exit",
            session_id=None,
        )
    except subprocess.TimeoutExpired as exc:
        stdout_text = _coerce_output_text(exc.stdout)
        stderr_text = _coerce_output_text(exc.stderr)
        stdout_path.write_text(stdout_text, encoding="utf-8")
        stderr_path.write_text(stderr_text, encoding="utf-8")
        _write_new_executor_blob(scope, f"{stamp}-cycle{cycle_number:06d}-{safe_name}.stdout.log", stdout_text)
        _write_new_executor_blob(scope, f"{stamp}-cycle{cycle_number:06d}-{safe_name}.stderr.log", stderr_text)
        _append_new_executor_event(
            scope,
            {
                "schema_version": SCHEMA_VERSION,
                "timestamp": utc_now_iso(),
                "manager": manager_name,
                "cycle_number": int(cycle_number),
                "executor_provider": "blackbox",
                "executor_model": str(model or _resolve_executor_model(cfg, provider="blackbox") or ""),
                "blackbox_lane": _normalize_blackbox_lane(cfg.blackbox_lane),
                "status": "timeout",
                "returncode": None,
                "timeout_seconds": int(timeout_seconds),
                "timed_out": True,
            },
        )
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
            message=f"manager call timed out after {int(timeout_seconds)}s",
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
            message="blackbox binary not found",
            reason_code="manager_binary_missing",
        )


def _profile_rows_from_disk(*, selected_aliases: list[str] | None = None) -> list[dict[str, Any]]:
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
    if selected_aliases:
        discovered: dict[str, dict[str, Any]] = {}
        for row in rows:
            alias = str(row.get("alias") or "").strip().lower()
            if alias and alias not in discovered:
                discovered[alias] = row

        filtered: list[dict[str, Any]] = []
        used_aliases: set[str] = set()
        for requested in selected_aliases:
            for candidate in _alias_candidates(requested):
                row = discovered.get(candidate)
                if row is None:
                    continue
                alias = str(row.get("alias") or "").strip().lower()
                if alias in used_aliases:
                    continue
                filtered.append(row)
                used_aliases.add(alias)
                break
        return filtered

    # Default autodiscovery excludes the fallback ".codex" alias when multiple
    # profile homes exist. Keep it only when it is the sole discovered profile.
    if len(rows) > 1:
        rows = [row for row in rows if str(row.get("alias") or "").strip() != "codex"]
    return rows


def _default_selected_aliases_from_disk() -> list[str] | None:
    rows = _profile_rows_from_disk(selected_aliases=None)
    aliases: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        alias = str(row.get("alias") or "").strip().lower()
        if not alias or alias in seen:
            continue
        seen.add(alias)
        aliases.append(alias)
    return aliases or None


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
            "lane_base_branches": {},
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
            "cycle_mode": "normal",
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


def _write_merge_manager_stub(cfg: RunConfig, cycle_number: int) -> None:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "updated_at": utc_now_iso(),
        "cycle_number": cycle_number,
        "status": "dry_run",
        "summary": "dry run merge-manager report",
        "resolved_items": [],
        "unresolved_items": [],
    }
    _atomic_write_json(cfg.repo_root / ARTIFACT_FILES["merge_manager_report"], payload)


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
    cycle_mode: str = "normal",
) -> None:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "cycle_number": cycle_number,
        "decision": decision,
        "reason_code": reason_code,
        "message": message,
        "worker_registry_ready": worker_registry_ready,
        "cycle_mode": str(cycle_mode or "").strip() or "normal",
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
    manager_uses_boss_profile = manager_name in {"BOSS", "merge-manager", "wrapup-manager"}
    manager_uses_boss_model = manager_name in {"BOSS", "merge-manager", "wrapup-manager"}
    log_executor_provider = _normalize_executor_provider(cfg.executor_provider)
    log_executor_model = _resolve_executor_model(
        cfg,
        provider=log_executor_provider,
        model_override=cfg.executor_model or (cfg.boss_model if manager_uses_boss_model else None),
    )
    log_profile_alias = str(cfg.codex_profile or "").strip() or None
    if not _executor_uses_codex_backend(log_executor_provider):
        log_profile_alias = None
    log_reasoning_effort = str(cfg.boss_reasoning_effort).strip() if manager_uses_boss_model else None
    log_tooling_effort = "medium_tooling" if manager_name in {"BOSS", "merge-manager", "wrapup-manager"} else None
    if cfg.dry_run:
        if manager_name == "BOSS":
            _write_boss_stub(cfg, cycle_number)
        if manager_name == "merge-manager":
            _write_merge_manager_stub(cfg, cycle_number)
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
        executor_provider = _normalize_executor_provider(cfg.executor_provider)
        log_executor_provider = executor_provider
        if not _executor_uses_codex_backend(log_executor_provider):
            log_profile_alias = None
        uses_codex_backend = _executor_uses_codex_backend(executor_provider)
        selected_manager_alias: str | None = None
        selected_manager_home: str | None = None
        resume_session_id: str | None = None
        prior_profile_alias: str | None = None
        prior_previous_profile_alias: str | None = None
        timeout_state = _load_timeout_adaptation_state(cfg) if manager_name == "BOSS" else {}
        rotation_selection_evidence: dict[str, Any] = {}
        if manager_name == "BOSS" and uses_codex_backend:
            refreshed, refresh_message = _refresh_profile_snapshot_before_boss_selection(cfg, cycle_number=cycle_number)
            rotation_selection_evidence["profile_snapshot_refresh"] = {
                "attempted": True,
                "refreshed": bool(refreshed),
                "message": refresh_message,
            }
            print(
                "[op-simple-build] "
                f"[{utc_now_iso()}] "
                f"cycle={cycle_number} manager=BOSS profile-snapshot-refresh "
                f"status={'ok' if refreshed else 'skipped'} message={refresh_message}",
                flush=True,
            )
        if manager_uses_boss_profile and uses_codex_backend:
            boss_session_state = _read_boss_session_state(cfg)
            prior_session_id = str(boss_session_state.get("session_id") or "").strip() or None
            prior_profile_alias = str(boss_session_state.get("profile_alias") or "").strip() or None
            prior_previous_profile_alias = str(boss_session_state.get("previous_profile_alias") or "").strip() or None
            excluded_aliases: set[str] = set()
            timed_out_alias = ""
            non_timeout_failed_alias = ""
            if manager_name == "BOSS" and bool(timeout_state.get("rotation_required")):
                timed_out_alias = str(timeout_state.get("last_timeout_profile_alias") or "").strip()
                if timed_out_alias:
                    excluded_aliases.add(timed_out_alias)
            if manager_name == "BOSS":
                non_timeout_failed_alias = _boss_non_timeout_excluded_alias(timeout_state)
                if non_timeout_failed_alias:
                    excluded_aliases.add(non_timeout_failed_alias)
            selected_manager_alias, selected_manager_home, rotation_selection_evidence = (
                _select_boss_profile_from_snapshot_with_evidence(
                    cfg,
                    preferred_alias=prior_profile_alias,
                    excluded_aliases=excluded_aliases,
                )
            )
            _record_boss_non_timeout_exclusion_evidence(
                rotation_selection_evidence,
                excluded_aliases,
                timed_out_alias=timed_out_alias,
                non_timeout_failed_alias=non_timeout_failed_alias,
            )
            if manager_name == "BOSS" and selected_manager_alias is None and excluded_aliases:
                # Fallback preserves continuity when no alternate eligible alias exists.
                fallback_alias, fallback_home, fallback_evidence = _select_boss_profile_from_snapshot_with_evidence(
                    cfg,
                    preferred_alias=prior_profile_alias,
                    excluded_aliases=set(),
                )
                selected_manager_alias = fallback_alias
                selected_manager_home = fallback_home
                rotation_selection_evidence["fallback_without_exclusion"] = True
                rotation_selection_evidence["fallback_evidence"] = fallback_evidence
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
            if manager_name == "BOSS":
                rotation_decision = {
                    "cycle_number": int(cycle_number),
                    "rotation_required": bool(timeout_state.get("rotation_required")),
                    "last_timeout_profile_alias": str(timeout_state.get("last_timeout_profile_alias") or "").strip(),
                    "last_non_timeout_failed_profile_alias": str(
                        timeout_state.get("last_non_timeout_failed_profile_alias") or ""
                    ).strip(),
                    "preferred_alias": prior_profile_alias,
                    "selected_alias": selected_manager_alias,
                    "selected_home": selected_manager_home,
                    "selection_evidence": rotation_selection_evidence,
                }
                _record_boss_rotation_decision(cfg, decision=rotation_decision)
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
            "executor": {
                "provider": executor_provider,
                "model": _resolve_executor_model(
                    cfg,
                    provider=executor_provider,
                    model_override=cfg.executor_model or (cfg.boss_model if manager_uses_boss_model else None),
                ),
                "blackbox_lane": _normalize_blackbox_lane(cfg.blackbox_lane),
            },
        }
        prompt_text = template.strip()
        if manager_name == "BOSS" and _llm_profile_mode_enabled(cfg):
            profile_name = str(cfg.codex_profile or "").strip()
            note = (
                "Operator note: LLM profile mode is active. "
                f"Use llm_profile='{profile_name}' rate registry artifacts from the runtime packet. "
                "Do not run minimal-rate-snapshot in this mode."
            )
            prompt_text = f"{note}\n\n{prompt_text}" if prompt_text else note
        if prompt_text:
            prompt_text += "\n\n"
        prompt_text += "Runtime packet (JSON):\n```json\n"
        prompt_text += json.dumps(packet, indent=2, sort_keys=False)
        prompt_text += "\n```\n"
        timeout = _resolve_manager_timeout_seconds(
            cfg,
            manager_name,
            provider=executor_provider,
        )
        manager_model = _resolve_executor_model(
            cfg,
            provider=executor_provider,
            model_override=cfg.executor_model or (cfg.boss_model if manager_uses_boss_model else None),
        )
        log_executor_model = manager_model
        if uses_codex_backend:
            boss_profile_candidates = _boss_profile_candidates_from_snapshot(cfg) if manager_name == "BOSS" else []
            selected_profile_row = next(
                (
                    row
                    for row in boss_profile_candidates
                    if str(row.get("alias") or "").strip() == str(selected_manager_alias or "").strip()
                ),
                None,
            )
            runtime_checks = {
                "cycle_number": int(cycle_number),
                "manager": manager_name,
                "executor_provider": executor_provider,
                "uses_codex_backend": True,
                "codex_binary_available": bool(shutil.which("codex")),
                "llm_profile_mode_enabled": bool(_llm_profile_mode_enabled(cfg)),
                "llm_profile_value": str(cfg.codex_profile or "").strip() or None,
                "selected_profile_alias": selected_manager_alias,
                "selected_codex_home": selected_manager_home,
                "selected_codex_home_exists": bool(
                    Path(str(selected_manager_home)).expanduser().exists()
                )
                if selected_manager_home
                else None,
                "selected_profile_found_in_snapshot": isinstance(selected_profile_row, dict),
                "selected_profile_eligible": bool((selected_profile_row or {}).get("eligible"))
                if isinstance(selected_profile_row, dict)
                else None,
                "selected_profile_ineligible_reason": str((selected_profile_row or {}).get("ineligible_reason") or "").strip()
                if isinstance(selected_profile_row, dict)
                else None,
                "selected_profile_hard_gated": bool((selected_profile_row or {}).get("hard_gated"))
                if isinstance(selected_profile_row, dict)
                else None,
                "eligible_profile_count": int(sum(1 for row in boss_profile_candidates if bool(row.get("eligible")))),
            }
            invalid_reasons: list[str] = []
            if not bool(runtime_checks["codex_binary_available"]):
                invalid_reasons.append("codex_binary_missing")
            if bool(runtime_checks["llm_profile_mode_enabled"]) and not str(runtime_checks["llm_profile_value"] or "").strip():
                invalid_reasons.append("llm_profile_mode_missing_profile")
            if manager_name == "BOSS":
                if not str(selected_manager_alias or "").strip():
                    invalid_reasons.append("selected_profile_alias_missing")
                if not str(selected_manager_home or "").strip():
                    invalid_reasons.append("selected_codex_home_missing")
                elif runtime_checks["selected_codex_home_exists"] is False:
                    invalid_reasons.append("selected_codex_home_missing_on_disk")
                if not isinstance(selected_profile_row, dict):
                    if int(runtime_checks.get("eligible_profile_count") or 0) <= 0:
                        invalid_reasons.append("no_eligible_profile_in_snapshot")
                    else:
                        invalid_reasons.append("selected_profile_not_in_snapshot")
                elif not bool(selected_profile_row.get("eligible")):
                    ineligible_reason = str(selected_profile_row.get("ineligible_reason") or "").strip() or "unknown"
                    invalid_reasons.append(f"selected_profile_ineligible:{ineligible_reason}")
            runtime_checks["invalid_reasons"] = invalid_reasons
            runtime_checks["runtime_context_valid"] = len(invalid_reasons) == 0
            if manager_name == "BOSS":
                _record_boss_runtime_checks(cfg, checks=runtime_checks)
            if invalid_reasons:
                now_iso = utc_now_iso()
                result = ManagerResult(
                    manager=manager_name,
                    status="failed",
                    timeout=False,
                    returncode=None,
                    started_at=now_iso,
                    finished_at=now_iso,
                    duration_seconds=0.0,
                    message=(
                        "boss runtime context invalid: "
                        + ", ".join(invalid_reasons)
                    ),
                    reason_code="boss_runtime_context_invalid",
                    details={"invalid_reasons": invalid_reasons, "runtime_checks": runtime_checks},
                )
            else:
                result = _codex_exec_prompt(
                    cfg,
                    manager_name,
                    cycle_number,
                    timeout,
                    prompt_text,
                    codex_home=selected_manager_home,
                    resume_session_id=resume_session_id,
                    model=manager_model,
                    reasoning_effort=cfg.boss_reasoning_effort if manager_uses_boss_model else None,
                    codex_profile=cfg.codex_profile,
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
                        model=manager_model,
                        reasoning_effort=cfg.boss_reasoning_effort,
                        codex_profile=cfg.codex_profile,
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
                if manager_name == "BOSS" and result.status == "failed" and not result.timeout:
                    auth_retry_triggered = _manager_result_has_retryable_profile_auth_failure(result)
                    if auth_retry_triggered and selected_manager_alias:
                        failure_reason = "retryable_profile_auth_failure"
                        _preserve_manager_attempt_logs(result, label="initial-auth-failure")
                        _mark_profile_snapshot_alias_unavailable(
                            cfg,
                            alias=selected_manager_alias,
                            reason=failure_reason,
                        )
                        refreshed, refresh_message = _refresh_profile_snapshot_via_skill(cfg, cycle_number)
                        retry_excluded_aliases = set(excluded_aliases)
                        retry_excluded_aliases.add(selected_manager_alias)
                        retry_alias, retry_home, retry_evidence = _select_boss_profile_from_snapshot_with_evidence(
                            cfg,
                            preferred_alias=None,
                            excluded_aliases=retry_excluded_aliases,
                        )
                        same_cycle_retry = {
                            "triggered": True,
                            "reason": failure_reason,
                            "failed_alias": selected_manager_alias,
                            "snapshot_refreshed": bool(refreshed),
                            "snapshot_refresh_message": refresh_message,
                            "retry_selected_alias": retry_alias,
                            "retry_selection_evidence": retry_evidence,
                        }
                        rotation_selection_evidence["same_cycle_profile_retry"] = same_cycle_retry
                        if retry_alias and retry_home:
                            print(
                                "[op-simple-build] "
                                f"[{utc_now_iso()}] "
                                f"cycle={cycle_number} manager=BOSS profile-rotation-retry status=started "
                                f"failed_alias={selected_manager_alias} retry_alias={retry_alias} reason={failure_reason}",
                                flush=True,
                            )
                            retry_result = _codex_exec_prompt(
                                cfg,
                                manager_name,
                                cycle_number,
                                timeout,
                                prompt_text,
                                codex_home=retry_home,
                                resume_session_id=None,
                                model=manager_model,
                                reasoning_effort=cfg.boss_reasoning_effort if manager_uses_boss_model else None,
                                codex_profile=cfg.codex_profile,
                            )
                            retry_result.details = dict(retry_result.details or {})
                            retry_result.details["same_cycle_profile_retry"] = same_cycle_retry
                            result = retry_result
                            selected_manager_alias = retry_alias
                            selected_manager_home = retry_home
                        else:
                            print(
                                "[op-simple-build] "
                                f"[{utc_now_iso()}] "
                                f"cycle={cycle_number} manager=BOSS profile-rotation-retry status=skipped "
                                f"failed_alias={selected_manager_alias} reason=no_alternate_profile",
                                flush=True,
                            )
                if manager_name == "BOSS":
                    _record_boss_rotation_decision(
                        cfg,
                        decision={
                            "cycle_number": int(cycle_number),
                            "rotation_required": bool(timeout_state.get("rotation_required")),
                            "last_timeout_profile_alias": str(timeout_state.get("last_timeout_profile_alias") or "").strip(),
                            "last_non_timeout_failed_profile_alias": str(
                                timeout_state.get("last_non_timeout_failed_profile_alias") or ""
                            ).strip(),
                            "preferred_alias": prior_profile_alias,
                            "selected_alias": selected_manager_alias,
                            "selected_home": selected_manager_home,
                            "selection_evidence": rotation_selection_evidence,
                        },
                    )
        else:
            result = _blackbox_exec_prompt(
                cfg,
                manager_name,
                cycle_number,
                timeout,
                prompt_text,
                model=manager_model,
            )

        if manager_name == "BOSS" and uses_codex_backend and result.status == "ok":
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
        if manager_name == "BOSS" and uses_codex_backend and result.status != "ok":
            _safe_unlink(cfg.repo_root / BOSS_SESSION_STATE_FILE)
        if uses_codex_backend and selected_manager_alias:
            result.message = (
                f"{result.message}; manager_profile_alias={selected_manager_alias}"
                if result.message
                else f"manager_profile_alias={selected_manager_alias}"
            )
            log_profile_alias = selected_manager_alias

    if result.status == "ok":
        reason_code, message, details = _validate_manager_artifacts(cfg, manager_name, expected_artifacts, cycle_number)
        if reason_code:
            result.status = "failed"
            result.reason_code = reason_code
            result.message = message
            result.details = details

    llm_hardening, llm_hardening_present, llm_hardening_source = _extract_manager_llm_hardening(
        cfg,
        manager_name=manager_name,
        expected_artifacts=expected_artifacts,
        cycle_number=cycle_number,
    )
    print(
        "[op-simple-build] "
        f"[{utc_now_iso()}] "
        f"cycle={cycle_number} manager={manager_name} llm_hardening="
        f"{'present' if llm_hardening_present else 'missing'} "
        f"source={llm_hardening_source or 'none'} "
        f"checker_result={llm_hardening.get('checker_result')} "
        f"override_applied={str(bool(llm_hardening.get('override_applied'))).lower()}",
        flush=True,
    )

    timeout_log_state = _load_timeout_adaptation_state(cfg) if manager_name == "BOSS" else {}
    timeout_log_rotation = (
        timeout_log_state.get("last_rotation_decision")
        if isinstance(timeout_log_state.get("last_rotation_decision"), dict)
        else {}
    )
    timeout_log_runtime = (
        timeout_log_state.get("last_boss_runtime_checks")
        if isinstance(timeout_log_state.get("last_boss_runtime_checks"), dict)
        else {}
    )
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
            "executor_provider": log_executor_provider,
            "executor_model": log_executor_model,
            "profile_alias": log_profile_alias,
            "reasoning_effort": log_reasoning_effort,
            "tooling_effort": log_tooling_effort,
            "mini_jobs": llm_hardening.get("mini_jobs"),
            "prompt_complexity_score": llm_hardening.get("prompt_complexity_score"),
            "checker_result": llm_hardening.get("checker_result"),
            "checker_id": llm_hardening.get("checker_id"),
            "override_applied": bool(llm_hardening.get("override_applied")),
            "override_reason_code": llm_hardening.get("override_reason_code"),
            "override_explanation": llm_hardening.get("override_explanation"),
            "override_evidence_refs": llm_hardening.get("override_evidence_refs") or [],
            "risk_level": llm_hardening.get("risk_level"),
            "fallback_or_followup_action": llm_hardening.get("fallback_or_followup_action"),
            "llm_hardening_state": "present" if llm_hardening_present else "missing",
            "llm_hardening_source": llm_hardening_source,
            "timeout_streak": int(timeout_log_state.get("consecutive_boss_timeouts") or 0),
            "timeout_adaptation_active": bool(timeout_log_state.get("adaptation_active")),
            "timeout_rotation_required": bool(timeout_log_state.get("rotation_required")),
            "rotation_selected_alias": timeout_log_rotation.get("selected_alias"),
            "rotation_rejected_reason": timeout_log_rotation.get("selection_evidence", {}).get("prior_alias_rejected_reason")
            if isinstance(timeout_log_rotation.get("selection_evidence"), dict)
            else None,
            "runtime_context_valid": timeout_log_runtime.get("runtime_context_valid"),
            "runtime_context_invalid_reasons": timeout_log_runtime.get("invalid_reasons"),
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


def _llm_profile_mode_enabled(cfg: RunConfig) -> bool:
    return bool(str(cfg.codex_profile or "").strip())


def _utc_iso_from_datetime(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _default_llm_profile_rate_registry(cfg: RunConfig) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return {
        "schema_version": SCHEMA_VERSION,
        "updated_at": _utc_iso_from_datetime(now),
        "enabled": _llm_profile_mode_enabled(cfg),
        "llm_profile": str(cfg.codex_profile or "").strip() or None,
        "limits": {
            "per_minute": int(LLM_PROFILE_PER_MINUTE_LIMIT),
            "per_day": int(LLM_PROFILE_PER_DAY_LIMIT),
        },
        "windows": {
            "minute": {
                "started_at": _utc_iso_from_datetime(now),
                "window_seconds": 60,
                "count": 0,
            },
            "day": {
                "started_at": _utc_iso_from_datetime(day_start),
                "window_seconds": 86400,
                "count": 0,
            },
        },
        "total_count": 0,
        "last_request_at": None,
        "last_request_source": None,
    }


def _normalize_llm_profile_rate_registry(cfg: RunConfig, payload: Any) -> dict[str, Any]:
    out = payload if isinstance(payload, dict) else _default_llm_profile_rate_registry(cfg)
    now = datetime.now(timezone.utc)
    profile_text = str(cfg.codex_profile or "").strip() or None
    if out.get("llm_profile") != profile_text:
        out = _default_llm_profile_rate_registry(cfg)
    out["schema_version"] = SCHEMA_VERSION
    out["enabled"] = _llm_profile_mode_enabled(cfg)
    out["llm_profile"] = profile_text
    limits = out.get("limits") if isinstance(out.get("limits"), dict) else {}
    minute_limit = limits.get("per_minute")
    day_limit = limits.get("per_day")
    try:
        minute_limit = int(minute_limit)
    except (TypeError, ValueError):
        minute_limit = LLM_PROFILE_PER_MINUTE_LIMIT
    try:
        day_limit = int(day_limit)
    except (TypeError, ValueError):
        day_limit = LLM_PROFILE_PER_DAY_LIMIT
    out["limits"] = {"per_minute": max(1, minute_limit), "per_day": max(1, day_limit)}

    windows = out.get("windows") if isinstance(out.get("windows"), dict) else {}
    minute = windows.get("minute") if isinstance(windows.get("minute"), dict) else {}
    day = windows.get("day") if isinstance(windows.get("day"), dict) else {}

    minute_started = _parse_iso_datetime(str(minute.get("started_at") or ""))
    if minute_started is None:
        minute_started = now
    minute_window_seconds = 60
    try:
        minute_count = int(minute.get("count") or 0)
    except (TypeError, ValueError):
        minute_count = 0
    if minute_started + timedelta(seconds=minute_window_seconds) <= now:
        minute_started = now
        minute_count = 0
    if minute_count < 0:
        minute_count = 0

    day_started = _parse_iso_datetime(str(day.get("started_at") or ""))
    if day_started is None:
        day_started = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_window_seconds = 86400
    try:
        day_count = int(day.get("count") or 0)
    except (TypeError, ValueError):
        day_count = 0
    if day_started + timedelta(seconds=day_window_seconds) <= now:
        day_started = now.replace(hour=0, minute=0, second=0, microsecond=0)
        day_count = 0
    if day_count < 0:
        day_count = 0

    out["windows"] = {
        "minute": {
            "started_at": _utc_iso_from_datetime(minute_started),
            "window_seconds": minute_window_seconds,
            "count": minute_count,
        },
        "day": {
            "started_at": _utc_iso_from_datetime(day_started),
            "window_seconds": day_window_seconds,
            "count": day_count,
        },
    }
    try:
        total_count = int(out.get("total_count") or 0)
    except (TypeError, ValueError):
        total_count = 0
    out["total_count"] = max(0, total_count)
    out["updated_at"] = _utc_iso_from_datetime(now)
    return out


def _load_llm_profile_rate_registry(cfg: RunConfig) -> dict[str, Any]:
    path = cfg.repo_root / ARTIFACT_FILES["llm_profile_rate_registry"]
    payload = _read_json(path, default={})
    normalized = _normalize_llm_profile_rate_registry(cfg, payload)
    _atomic_write_json(path, normalized)
    return normalized


def _llm_profile_gate_state(payload: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    limits = payload.get("limits") if isinstance(payload.get("limits"), dict) else {}
    windows = payload.get("windows") if isinstance(payload.get("windows"), dict) else {}
    minute = windows.get("minute") if isinstance(windows.get("minute"), dict) else {}
    day = windows.get("day") if isinstance(windows.get("day"), dict) else {}

    try:
        minute_limit = int(limits.get("per_minute") or LLM_PROFILE_PER_MINUTE_LIMIT)
    except (TypeError, ValueError):
        minute_limit = LLM_PROFILE_PER_MINUTE_LIMIT
    try:
        day_limit = int(limits.get("per_day") or LLM_PROFILE_PER_DAY_LIMIT)
    except (TypeError, ValueError):
        day_limit = LLM_PROFILE_PER_DAY_LIMIT
    try:
        minute_count = int(minute.get("count") or 0)
    except (TypeError, ValueError):
        minute_count = 0
    try:
        day_count = int(day.get("count") or 0)
    except (TypeError, ValueError):
        day_count = 0

    minute_started = _parse_iso_datetime(str(minute.get("started_at") or ""))
    if minute_started is None:
        minute_started = now
    day_started = _parse_iso_datetime(str(day.get("started_at") or ""))
    if day_started is None:
        day_started = now.replace(hour=0, minute=0, second=0, microsecond=0)

    minute_blocked = minute_count >= max(1, minute_limit)
    day_blocked = day_count >= max(1, day_limit)

    minute_reset_at = minute_started + timedelta(seconds=60)
    day_reset_at = day_started + timedelta(seconds=86400)
    reset_candidates: list[datetime] = []
    if minute_blocked and minute_reset_at > now:
        reset_candidates.append(minute_reset_at)
    if day_blocked and day_reset_at > now:
        reset_candidates.append(day_reset_at)
    min_reset = min(reset_candidates) if reset_candidates else None

    minute_remaining = max(0, minute_limit - minute_count)
    day_remaining = max(0, day_limit - day_count)
    return {
        "hard_gated": bool(minute_blocked or day_blocked),
        "minute_blocked": minute_blocked,
        "day_blocked": day_blocked,
        "minute_remaining": minute_remaining,
        "day_remaining": day_remaining,
        "minute_limit": minute_limit,
        "day_limit": day_limit,
        "reset_at": _utc_iso_from_datetime(min_reset) if min_reset else None,
    }


def _refresh_profile_snapshot_via_llm_profile_registry(cfg: RunConfig, cycle_number: int) -> tuple[bool, str]:
    mode_path = cfg.repo_root / ARTIFACT_FILES["llm_profile_mode"]
    mode_payload = {
        "schema_version": SCHEMA_VERSION,
        "updated_at": utc_now_iso(),
        "enabled": True,
        "llm_profile": str(cfg.codex_profile or "").strip(),
        "profile_policy": "force_default_codex",
        "rate_policy": {
            "source": "local-counter-timer",
            "per_minute_limit": int(LLM_PROFILE_PER_MINUTE_LIMIT),
            "per_day_limit": int(LLM_PROFILE_PER_DAY_LIMIT),
            "skip_codex_rate_snapshot_skill": True,
        },
    }
    _atomic_write_json(mode_path, mode_payload)

    registry = _load_llm_profile_rate_registry(cfg)
    gate = _llm_profile_gate_state(registry)
    codex_home = _effective_codex_home(None)
    minute_pct = round(100.0 * float(gate["minute_remaining"]) / max(1, int(gate["minute_limit"])), 3)
    day_pct = round(100.0 * float(gate["day_remaining"]) / max(1, int(gate["day_limit"])), 3)
    snapshot_payload = {
        "schema_version": SCHEMA_VERSION,
        "updated_at": utc_now_iso(),
        "cycle_number": cycle_number,
        "source": "llm-profile-mode-local-counter",
        "profiles": [
            {
                "alias": "codex",
                "codex_home": codex_home,
                "window_5h_remaining_pct": minute_pct,
                "window_week_remaining_pct": day_pct,
                "hard_gated": bool(gate["hard_gated"]),
                "soft_gated": False,
                "reset_at": gate.get("reset_at"),
                "recommended_action": "wait_until_reset" if gate["hard_gated"] else "continue",
                "llm_profile": str(cfg.codex_profile or "").strip(),
                "llm_limits": {
                    "per_minute": int(gate["minute_limit"]),
                    "per_day": int(gate["day_limit"]),
                    "minute_remaining": int(gate["minute_remaining"]),
                    "day_remaining": int(gate["day_remaining"]),
                },
            }
        ],
    }
    _atomic_write_json(cfg.repo_root / ARTIFACT_FILES["profile_snapshot"], snapshot_payload)
    return True, "profile snapshot refreshed via local LLM profile counter"


def _llm_profile_consume_request_budget(cfg: RunConfig, *, source: str) -> tuple[bool, str | None]:
    if not _llm_profile_mode_enabled(cfg):
        return True, None
    registry_path = cfg.repo_root / ARTIFACT_FILES["llm_profile_rate_registry"]
    payload = _load_llm_profile_rate_registry(cfg)
    gate = _llm_profile_gate_state(payload)
    if gate["hard_gated"]:
        _atomic_write_json(registry_path, payload)
        _refresh_profile_snapshot_via_llm_profile_registry(cfg, _load_cycle_counter(cfg))
        return False, str(gate.get("reset_at") or "") or None

    windows = payload.get("windows") if isinstance(payload.get("windows"), dict) else {}
    minute = windows.get("minute") if isinstance(windows.get("minute"), dict) else {}
    day = windows.get("day") if isinstance(windows.get("day"), dict) else {}
    minute["count"] = int(minute.get("count") or 0) + 1
    day["count"] = int(day.get("count") or 0) + 1
    payload["windows"] = {"minute": minute, "day": day}
    payload["total_count"] = int(payload.get("total_count") or 0) + 1
    payload["last_request_at"] = utc_now_iso()
    payload["last_request_source"] = source
    payload["updated_at"] = utc_now_iso()
    _atomic_write_json(registry_path, payload)
    _refresh_profile_snapshot_via_llm_profile_registry(cfg, _load_cycle_counter(cfg))
    return True, None


def _boss_profile_candidates_from_snapshot(cfg: RunConfig) -> list[dict[str, Any]]:
    payload = _read_json(cfg.repo_root / ARTIFACT_FILES["profile_snapshot"], default={})
    if not isinstance(payload, dict):
        return []
    rows = payload.get("profiles")
    if not isinstance(rows, list):
        return []

    candidate_rows = [row for row in rows if isinstance(row, dict)]

    candidates: list[dict[str, Any]] = []
    for row in candidate_rows:
        alias = str(row.get("alias") or "").strip()
        codex_home = str(row.get("codex_home") or "").strip()

        five_hour_remaining = _extract_remaining_percent(row.get("window_5h_remaining_pct"))
        if five_hour_remaining is None:
            try:
                five_hour_remaining = float(row.get("window_5h_remaining_pct"))
            except (TypeError, ValueError):
                five_hour_remaining = None
        if five_hour_remaining is None and isinstance(row.get("five_hour"), dict):
            five_hour_remaining = _extract_remaining_percent(row.get("five_hour"))

        week_remaining = _extract_remaining_percent(row.get("window_week_remaining_pct"))
        if week_remaining is None:
            try:
                week_remaining = float(row.get("window_week_remaining_pct"))
            except (TypeError, ValueError):
                week_remaining = None
        if week_remaining is None and isinstance(row.get("weekly"), dict):
            week_remaining = _extract_remaining_percent(row.get("weekly"))
        candidate = {
            "alias": alias,
            "codex_home": codex_home,
            "hard_gated": bool(row.get("hard_gated")),
            "five_hour_remaining": five_hour_remaining,
            "week_remaining": week_remaining,
            "eligible": False,
            "ineligible_reason": "",
        }
        if not alias or not codex_home:
            candidate["ineligible_reason"] = "missing_alias_or_codex_home"
        elif bool(candidate["hard_gated"]):
            candidate["ineligible_reason"] = "hard_gated"
        elif five_hour_remaining is None:
            candidate["ineligible_reason"] = "missing_5h_remaining"
        elif float(five_hour_remaining) <= 1.0:
            candidate["ineligible_reason"] = "five_hour_depleted"
        elif week_remaining is None:
            candidate["ineligible_reason"] = "missing_week_remaining"
        else:
            candidate["eligible"] = True
            candidate["ineligible_reason"] = ""
        candidates.append(candidate)
    candidates.sort(key=lambda item: str(item.get("alias") or ""))
    return candidates


def _select_boss_profile_from_snapshot_with_evidence(
    cfg: RunConfig,
    *,
    preferred_alias: str | None = None,
    excluded_aliases: set[str] | None = None,
) -> tuple[str | None, str | None, dict[str, Any]]:
    candidates = _boss_profile_candidates_from_snapshot(cfg)
    preferred_alias_text = str(preferred_alias or "").strip()
    excluded = {str(item or "").strip() for item in (excluded_aliases or set()) if str(item or "").strip()}
    eligible = [item for item in candidates if bool(item.get("eligible"))]
    eligible_after_exclusion = [item for item in eligible if str(item.get("alias") or "").strip() not in excluded]
    selected_alias: str | None = None
    selected_home: str | None = None
    selected_reason = "no_eligible_profile"
    prior_alias_rejected_reason = ""

    if preferred_alias_text:
        preferred_row = next((item for item in eligible_after_exclusion if item.get("alias") == preferred_alias_text), None)
        if preferred_row is not None and float(preferred_row.get("week_remaining") or 0.0) >= 50.0:
            selected_alias = str(preferred_row.get("alias") or "").strip() or None
            selected_home = str(preferred_row.get("codex_home") or "").strip() or None
            selected_reason = "keep_preferred_alias_weekly_ge_50"
        else:
            if preferred_row is None and preferred_alias_text in excluded:
                prior_alias_rejected_reason = "excluded_for_timeout_rotation"
            elif preferred_row is None:
                prior_alias_rejected_reason = "preferred_alias_not_eligible"
            else:
                prior_alias_rejected_reason = "preferred_alias_weekly_below_50"

    if selected_alias is None and eligible_after_exclusion:
        ranked = sorted(
            eligible_after_exclusion,
            key=lambda item: (
                -float(item.get("week_remaining") or 0.0),
                -float(item.get("five_hour_remaining") or 0.0),
                str(item.get("alias") or ""),
            ),
        )
        top = ranked[0]
        selected_alias = str(top.get("alias") or "").strip() or None
        selected_home = str(top.get("codex_home") or "").strip() or None
        selected_reason = "highest_weekly_then_5h_capacity"

    evidence = {
        "preferred_alias": preferred_alias_text,
        "excluded_aliases": sorted(excluded),
        "eligible_aliases": sorted(str(item.get("alias") or "") for item in eligible),
        "eligible_aliases_after_exclusion": sorted(
            str(item.get("alias") or "") for item in eligible_after_exclusion
        ),
        "selected_alias": selected_alias,
        "selected_reason": selected_reason,
        "prior_alias_rejected_reason": prior_alias_rejected_reason,
        "candidates": candidates,
    }
    return selected_alias, selected_home, evidence


def _select_boss_profile_from_snapshot(cfg: RunConfig, *, preferred_alias: str | None = None) -> tuple[str | None, str | None]:
    alias, codex_home, _evidence = _select_boss_profile_from_snapshot_with_evidence(
        cfg,
        preferred_alias=preferred_alias,
    )
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


def _rate_snapshot_profile_args(cfg: RunConfig) -> tuple[list[str], list[str]]:
    selected_aliases = list(cfg.selected_aliases or [])
    rows = _profile_rows_from_disk(selected_aliases=selected_aliases or None)
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
    if not args and not selected_aliases:
        args.append("codex=default")
    discovered = {str(row.get("alias") or "").strip().lower() for row in rows if isinstance(row, dict)}
    missing: list[str] = []
    for alias in selected_aliases:
        candidates = _alias_candidates(alias)
        if any(candidate in discovered for candidate in candidates):
            continue
        missing.append(alias)
    return args, missing


def _remaining_percent_from_used(used_percent: Any) -> float | None:
    try:
        used = float(used_percent)
    except (TypeError, ValueError):
        return None
    remaining = 100.0 - used
    if remaining < 0.0:
        return 0.0
    if remaining > 100.0:
        return 100.0
    return round(remaining, 3)


def _normalize_rate_snapshot_reset_at(raw: Any) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        timestamp = float(raw)
    elif isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        try:
            timestamp = float(text)
        except ValueError:
            dt = _parse_iso_datetime(text)
            if dt is None:
                return None
            return _utc_iso_from_datetime(dt)
    else:
        return None
    if timestamp > 10_000_000_000:
        timestamp = timestamp / 1000.0
    try:
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None
    return _utc_iso_from_datetime(dt)


def _normalize_rate_snapshot_gated_value(raw: Any) -> str:
    if isinstance(raw, bool):
        return "hard-gated" if raw else "false"
    text = str(raw or "").strip().lower()
    if text in {"", "false", "ungated", "not_gated", "open"}:
        return "false"
    if text == "soft-gated":
        return "soft-gated"
    if text in {"hard-gated", "not-available"}:
        return text
    return "hard-gated"


def _profile_rows_from_rate_snapshot_payload(payload: Any) -> list[dict[str, Any]]:
    profile_rows: list[dict[str, Any]] = []
    if isinstance(payload, list):
        profile_rows = [row for row in payload if isinstance(row, dict)]
    elif isinstance(payload, dict):
        profiles = payload.get("profiles")
        if isinstance(profiles, list):
            profile_rows = [row for row in profiles if isinstance(row, dict)]
        elif isinstance(profiles, dict):
            for alias, row in profiles.items():
                if not isinstance(row, dict):
                    continue
                copied = dict(row)
                copied.setdefault("alias", str(alias))
                profile_rows.append(copied)

    out: list[dict[str, Any]] = []
    for row in profile_rows:
        codex_home = str(row.get("codex_home") or row.get("home") or "").strip()
        alias_text = _canonical_codex_alias(row.get("alias"), codex_home)
        if not alias_text or not codex_home:
            continue

        primary = row.get("primary_window") if isinstance(row.get("primary_window"), dict) else {}
        secondary = row.get("secondary_window") if isinstance(row.get("secondary_window"), dict) else {}
        five_remaining = _remaining_percent_from_used(primary.get("used_percent"))
        week_remaining = _remaining_percent_from_used(secondary.get("used_percent"))
        gated_text = _normalize_rate_snapshot_gated_value(row.get("gated"))
        soft_gated = gated_text == "soft-gated"
        hard_gated = gated_text in {"hard-gated", "not-available"}
        if not hard_gated and ((five_remaining is not None and five_remaining <= 1.0) or (week_remaining is not None and week_remaining <= 1.0)):
            hard_gated = True
            soft_gated = False
        elif not soft_gated and ((five_remaining is not None and five_remaining <= 5.0) or (week_remaining is not None and week_remaining <= 5.0)):
            soft_gated = True

        reset_candidates: list[str] = []
        for value in (
            primary.get("reset_at"),
            secondary.get("reset_at"),
            row.get("reset_at"),
            row.get("next_reset_at"),
        ):
            normalized = _normalize_rate_snapshot_reset_at(value)
            if normalized:
                reset_candidates.append(normalized)
        reset_at: str | None = None
        if reset_candidates:
            parsed = [
                (candidate, _parse_iso_datetime(candidate))
                for candidate in reset_candidates
            ]
            parsed = [(candidate, dt) for candidate, dt in parsed if dt is not None]
            if parsed:
                parsed.sort(key=lambda item: item[1])
                reset_at = parsed[0][0]

        if hard_gated:
            recommended = "wait_until_reset" if reset_at else "wind_down"
        else:
            recommended = "continue"

        out.append(
            {
                "alias": alias_text,
                "codex_home": codex_home,
                "window_5h_remaining_pct": five_remaining,
                "window_week_remaining_pct": week_remaining,
                "hard_gated": hard_gated,
                "soft_gated": soft_gated,
                "reset_at": reset_at,
                "recommended_action": recommended,
            }
        )
    return out


def _refresh_profile_snapshot_via_skill(cfg: RunConfig, cycle_number: int) -> tuple[bool, str]:
    if _llm_profile_mode_enabled(cfg):
        return _refresh_profile_snapshot_via_llm_profile_registry(cfg, cycle_number)

    script = _resolve_rate_snapshot_script(cfg)
    if script is None:
        return False, "minimal-rate-snapshot script not found"

    cmd: list[str] = ["python3", str(script), "--json-pretty"]

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cfg.repo_root),
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, "minimal-rate-snapshot timed out"

    if proc.returncode != 0:
        err = (proc.stderr or "").strip() or (proc.stdout or "").strip() or "unknown error"
        return False, f"minimal-rate-snapshot failed: {err}"

    try:
        payload = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError as exc:
        return False, f"minimal-rate-snapshot emitted invalid JSON: {exc}"
    if not isinstance(payload, list):
        return False, "minimal-rate-snapshot output must be a JSON array"

    rows = _profile_rows_from_rate_snapshot_payload(payload)
    if cfg.selected_aliases:
        requested = [str(alias or "").strip().lower() for alias in cfg.selected_aliases if str(alias or "").strip()]
        filtered: list[dict[str, Any]] = []
        for requested_alias in requested:
            for candidate in _alias_candidates(requested_alias):
                matched = next(
                    (
                        row
                        for row in rows
                        if str(row.get("alias") or "").strip().lower() == candidate
                    ),
                    None,
                )
                if matched and matched not in filtered:
                    filtered.append(matched)
                    break
        rows = filtered
        if not rows:
            selected_text = ", ".join(cfg.selected_aliases or [])
            return False, f"minimal-rate-snapshot selected_aliases filter resolved to zero profiles: {selected_text}"
    if not rows:
        return False, "minimal-rate-snapshot returned no usable profile rows"

    snapshot_payload = {
        "schema_version": SCHEMA_VERSION,
        "updated_at": utc_now_iso(),
        "cycle_number": cycle_number,
        "source": "minimal-rate-snapshot",
        "profiles": rows,
    }
    _atomic_write_json(cfg.repo_root / ARTIFACT_FILES["profile_snapshot"], snapshot_payload)
    return True, f"profile snapshot refreshed via minimal-rate-snapshot ({len(rows)} profiles)"


def _profile_snapshot_row_count(cfg: RunConfig) -> int:
    payload = _read_json(cfg.repo_root / ARTIFACT_FILES["profile_snapshot"], default={})
    if not isinstance(payload, dict):
        return 0
    rows = payload.get("profiles")
    if not isinstance(rows, list):
        return 0
    return sum(1 for row in rows if isinstance(row, dict))


def _bootstrap_profile_snapshot_before_first_boss(cfg: RunConfig, *, cycle_number: int) -> tuple[bool, str]:
    if not _executor_uses_codex_backend(_normalize_executor_provider(cfg.executor_provider)):
        return True, "profile snapshot bootstrap skipped for non-codex executor provider"
    if _llm_profile_mode_enabled(cfg):
        existing_rows = _profile_snapshot_row_count(cfg)
        if existing_rows > 0:
            suffix = "" if existing_rows == 1 else "s"
            return True, f"profile snapshot available via llm profile mode ({existing_rows} profile row{suffix})"
        refreshed, refresh_message = _refresh_profile_snapshot_via_llm_profile_registry(cfg, cycle_number)
        if refreshed:
            return True, refresh_message
        return False, f"{refresh_message}; profile snapshot remains empty in llm profile mode"

    # Seed from local profile discovery first so BOSS does not start from an empty snapshot.
    discovered_rows = _profile_rows_from_disk(selected_aliases=list(cfg.selected_aliases or []) or None)
    if discovered_rows:
        snapshot_payload = {
            "schema_version": SCHEMA_VERSION,
            "updated_at": utc_now_iso(),
            "cycle_number": int(cycle_number),
            "source": "filesystem-profile-discovery-bootstrap",
            "profiles": discovered_rows,
        }
        _atomic_write_json(cfg.repo_root / ARTIFACT_FILES["profile_snapshot"], snapshot_payload)
        return True, f"profile snapshot bootstrapped from filesystem discovery ({len(discovered_rows)} profiles)"

    refreshed, refresh_message = _refresh_profile_snapshot_via_skill(cfg, cycle_number)
    if refreshed:
        return True, refresh_message

    existing_rows = _profile_snapshot_row_count(cfg)
    if existing_rows > 0:
        suffix = "" if existing_rows == 1 else "s"
        return True, f"{refresh_message}; retained existing snapshot with {existing_rows} profile row{suffix}"
    return False, f"{refresh_message}; profile snapshot remains empty"


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
    if not _executor_uses_codex_backend(_normalize_executor_provider(cfg.executor_provider)):
        return
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
                "current_task_provider": None,
                "next_task_provider": None,
                "current_task_model": None,
                "next_task_model": None,
                "current_task_id": None,
                "current_packet_id": None,
                "pid": None,
                "thread_id": None,
                "last_update": utc_now_iso(),
            }
            workers.append(row)
            worker_index[worker_id] = row

        dispatch_status = str(event.get("status") or "").strip()
        event_profile = str(event.get("profile_alias") or "").strip() or None
        event_provider = str(event.get("executor_provider") or "").strip() or None
        event_model = str(event.get("executor_model") or "").strip() or None
        if dispatch_status == "launched":
            row["status"] = "in_progress"
            row["current_task_profile"] = event_profile
            row["current_task_provider"] = event_provider
            row["current_task_model"] = event_model
            row["next_task_profile"] = None
            row["next_task_provider"] = None
            row["next_task_model"] = None
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


def _is_recent_timestamp(value: Any, *, max_age_seconds: int) -> bool:
    parsed = _parse_iso_datetime(value if isinstance(value, str) else "")
    if parsed is None:
        return False
    age_seconds = (datetime.now(timezone.utc) - parsed).total_seconds()
    return age_seconds <= float(max(1, int(max_age_seconds)))


def _worker_has_live_marker(row: dict[str, Any]) -> bool:
    pid = _coerce_pid(row.get("pid"))
    if pid is not None and _is_pid_alive(pid):
        return True
    thread_id = str(row.get("thread_id") or "").strip()
    if not thread_id:
        return False
    last_update = str(row.get("last_update") or "").strip()
    return _is_recent_timestamp(last_update, max_age_seconds=THREAD_LIVENESS_MAX_AGE_SECONDS)


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
        # Count only workers with concrete runtime liveness markers so
        # pre-dispatch placeholders and stale thread IDs do not consume capacity.
        if _worker_has_live_marker(row):
            active_count += 1
    return active_count


def _live_pid_in_progress_worker_count(cfg: RunConfig) -> int:
    payload = _read_json(cfg.repo_root / ARTIFACT_FILES["worker_registry"], default={})
    if not isinstance(payload, dict):
        return 0
    workers = payload.get("workers")
    if not isinstance(workers, list):
        return 0
    live_count = 0
    for row in workers:
        if not isinstance(row, dict):
            continue
        if str(row.get("status") or "").strip() != "in_progress":
            continue
        if _worker_has_live_marker(row):
            live_count += 1
    return live_count


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
                    "current_task_provider": str(row.get("current_task_provider") or "").strip(),
                    "current_task_model": str(row.get("current_task_model") or "").strip(),
                    "next_task_provider": str(row.get("next_task_provider") or "").strip(),
                    "next_task_model": str(row.get("next_task_model") or "").strip(),
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
                    "assigned_provider": str(row.get("assigned_provider") or "").strip(),
                    "assigned_model": str(row.get("assigned_model") or "").strip(),
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
        age_minutes = float(payload.get("watchdog_age_minutes"))
    except (TypeError, ValueError):
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


def _cycle_release_baseline(cfg: RunConfig) -> tuple[str, int, int, int]:
    signature, in_progress_workers = _worker_task_state_signature(cfg)
    live_workers = _live_pid_in_progress_worker_count(cfg)
    task_counts = _task_counts_from_execution_state(cfg)
    task_in_progress = int(task_counts.get("in_progress") or 0)
    return signature, in_progress_workers, live_workers, task_in_progress


def _cycle_release_watchset_from_dispatch_cycle(cfg: RunConfig, cycle_number: int) -> list[int]:
    rows = _dispatch_events_for_cycle(cfg, cycle_number)
    pids: set[int] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("status") or "").strip() != "launched":
            continue
        pid_int = _coerce_pid(row.get("pid"))
        if pid_int is None:
            continue
        pids.add(pid_int)
    return sorted(pids)


def _cycle_release_watchset_from_live_workers(cfg: RunConfig) -> list[int]:
    payload = _read_json(cfg.repo_root / ARTIFACT_FILES["worker_registry"], default={})
    if not isinstance(payload, dict):
        return []
    worker_rows = payload.get("workers")
    if not isinstance(worker_rows, list):
        return []
    pids: set[int] = set()
    for row in worker_rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("status") or "").strip() != "in_progress":
            continue
        pid_int = _coerce_pid(row.get("pid"))
        if pid_int is None:
            continue
        if _is_pid_alive(pid_int):
            pids.add(pid_int)
    return sorted(pids)


def _cycle_release_alive_pids(tracked_pids: list[int]) -> list[int]:
    return sorted(pid for pid in tracked_pids if _is_pid_alive(pid))


def _await_cycle_release_signal(
    cfg: RunConfig,
    *,
    cycle_number: int,
) -> dict[str, Any]:
    wait_started_at = time.monotonic()
    mode = _normalize_cycle_release_mode(cfg.cycle_release_mode)
    timeout_seconds = max(1, int(cfg.cycle_release_timeout_seconds))
    poll_seconds = max(1, int(cfg.cycle_release_poll_seconds))
    guard_seconds = max(0, int(CYCLE_RELEASE_DEAD_PID_GUARD_SECONDS))
    if mode == "token_conservative":
        tracked_pids = _cycle_release_watchset_from_dispatch_cycle(cfg, cycle_number)
        watchset_source = "current_cycle_dispatch"
    else:
        tracked_pids = _cycle_release_watchset_from_live_workers(cfg)
        watchset_source = "current_live_in_progress_workers"

    if not tracked_pids:
        return {
            "mode": mode,
            "watchset_source": watchset_source,
            "decision": "no_wait_no_tracked_pids",
            "waited_seconds": 0.0,
            "timed_out": False,
            "tracked_pid_count": 0,
            "tracked_pids": [],
            "alive_pid_count": 0,
            "alive_pids": [],
            "dead_pid_count": 0,
            "dead_pids": [],
        }

    print(
        "[op-simple-build] "
        f"[{utc_now_iso()}] "
        f"cycle={cycle_number} cycle-release mode={mode} wait_start "
        f"watchset_source={watchset_source} tracked_pid_count={len(tracked_pids)} "
        f"tracked_pids={tracked_pids} timeout_s={timeout_seconds} poll_s={poll_seconds} "
        f"guard_s={guard_seconds}",
        flush=True,
    )

    previous_alive: set[int] = set(_cycle_release_alive_pids(tracked_pids))
    heartbeat_due_at = wait_started_at + float(WAIT_HEARTBEAT_SECONDS)

    def _result(*, decision: str, timed_out: bool, alive_set: set[int]) -> dict[str, Any]:
        waited = round(float(time.monotonic() - wait_started_at), 3)
        alive_sorted = sorted(alive_set)
        dead_sorted = sorted(pid for pid in tracked_pids if pid not in alive_set)
        return {
            "mode": mode,
            "watchset_source": watchset_source,
            "decision": decision,
            "waited_seconds": waited,
            "timed_out": timed_out,
            "tracked_pid_count": int(len(tracked_pids)),
            "tracked_pids": list(tracked_pids),
            "alive_pid_count": int(len(alive_sorted)),
            "alive_pids": alive_sorted,
            "dead_pid_count": int(len(dead_sorted)),
            "dead_pids": dead_sorted,
        }

    def _guard_wait(alive_before_guard: set[int], *, release_decision: str) -> dict[str, Any] | None:
        if guard_seconds <= 0:
            print(
                "[op-simple-build] "
                f"[{utc_now_iso()}] "
                f"cycle={cycle_number} cycle-release mode={mode} guard_skipped guard_s=0 "
                f"decision={release_decision}",
                flush=True,
            )
            return _result(decision=release_decision, timed_out=False, alive_set=alive_before_guard)

        guard_started_at = time.monotonic()
        print(
            "[op-simple-build] "
            f"[{utc_now_iso()}] "
            f"cycle={cycle_number} cycle-release mode={mode} guard_start "
            f"guard_s={guard_seconds} decision_candidate={release_decision}",
            flush=True,
        )
        while True:
            now = time.monotonic()
            elapsed_total = now - wait_started_at
            if elapsed_total >= float(timeout_seconds):
                alive_set = set(_cycle_release_alive_pids(tracked_pids))
                print(
                    "[op-simple-build] "
                    f"[{utc_now_iso()}] "
                    f"cycle={cycle_number} cycle-release mode={mode} wait_timeout "
                    f"release_reason=timeout_ceiling_reached_during_guard "
                    f"alive_pid_count={len(alive_set)} alive_pids={sorted(alive_set)}",
                    flush=True,
                )
                return _result(decision="timeout_release", timed_out=True, alive_set=alive_set)
            guard_elapsed = now - guard_started_at
            if guard_elapsed >= float(guard_seconds):
                break
            guard_remaining = float(guard_seconds) - guard_elapsed
            timeout_remaining = float(timeout_seconds) - elapsed_total
            sleep_seconds = min(float(poll_seconds), guard_remaining, timeout_remaining)
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

        alive_after_guard = set(_cycle_release_alive_pids(tracked_pids))
        print(
            "[op-simple-build] "
            f"[{utc_now_iso()}] "
            f"cycle={cycle_number} cycle-release mode={mode} guard_end "
            f"guard_s={guard_seconds} alive_pid_count={len(alive_after_guard)} "
            f"alive_pids={sorted(alive_after_guard)}",
            flush=True,
        )

        if mode == "token_conservative":
            if alive_after_guard:
                return None
            return _result(
                decision="all_tracked_pids_dead_guarded",
                timed_out=False,
                alive_set=alive_after_guard,
            )

        dead_after_guard = [pid for pid in tracked_pids if pid not in alive_after_guard]
        if not dead_after_guard:
            return None
        return _result(
            decision="first_tracked_pid_dead_guarded",
            timed_out=False,
            alive_set=alive_after_guard,
        )

    while True:
        now = time.monotonic()
        elapsed = now - wait_started_at
        if elapsed >= float(timeout_seconds):
            alive_set = set(_cycle_release_alive_pids(tracked_pids))
            print(
                "[op-simple-build] "
                f"[{utc_now_iso()}] "
                f"cycle={cycle_number} cycle-release mode={mode} wait_timeout "
                "release_reason=timeout_ceiling_reached "
                f"alive_pid_count={len(alive_set)} alive_pids={sorted(alive_set)}",
                flush=True,
            )
            return _result(decision="timeout_release", timed_out=True, alive_set=alive_set)

        alive_set = set(_cycle_release_alive_pids(tracked_pids))
        newly_dead = sorted(previous_alive - alive_set)
        newly_alive = sorted(alive_set - previous_alive)
        if newly_dead:
            print(
                "[op-simple-build] "
                f"[{utc_now_iso()}] "
                f"cycle={cycle_number} cycle-release mode={mode} pid_transition "
                f"event=dead pids={newly_dead} alive_pid_count={len(alive_set)}",
                flush=True,
            )
        if newly_alive:
            print(
                "[op-simple-build] "
                f"[{utc_now_iso()}] "
                f"cycle={cycle_number} cycle-release mode={mode} pid_transition "
                f"event=alive pids={newly_alive} alive_pid_count={len(alive_set)}",
                flush=True,
            )

        if mode == "token_conservative":
            if not alive_set:
                guard_result = _guard_wait(alive_set, release_decision="all_tracked_pids_dead_guarded")
                if guard_result is not None:
                    print(
                        "[op-simple-build] "
                        f"[{utc_now_iso()}] "
                        f"cycle={cycle_number} cycle-release mode={mode} release_signal={guard_result['decision']} "
                        f"waited_s={guard_result['waited_seconds']}",
                        flush=True,
                    )
                    return guard_result
        else:
            dead_now = [pid for pid in tracked_pids if pid not in alive_set]
            if dead_now:
                guard_result = _guard_wait(alive_set, release_decision="first_tracked_pid_dead_guarded")
                if guard_result is not None:
                    print(
                        "[op-simple-build] "
                        f"[{utc_now_iso()}] "
                        f"cycle={cycle_number} cycle-release mode={mode} release_signal={guard_result['decision']} "
                        f"waited_s={guard_result['waited_seconds']}",
                        flush=True,
                    )
                    return guard_result

        if now >= heartbeat_due_at:
            print(
                "[op-simple-build] "
                f"[{utc_now_iso()}] "
                f"cycle={cycle_number} cycle-release mode={mode} heartbeat "
                f"waited_s={round(float(elapsed), 3)} tracked_pid_count={len(tracked_pids)} "
                f"alive_pid_count={len(alive_set)} dead_pid_count={len(tracked_pids) - len(alive_set)}",
                flush=True,
            )
            heartbeat_due_at = now + float(WAIT_HEARTBEAT_SECONDS)

        previous_alive = alive_set
        remaining = float(timeout_seconds) - float(elapsed)
        sleep_seconds = poll_seconds if remaining > float(poll_seconds) else remaining
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)


def _load_watchdog_recovery_nudge_body() -> str:
    try:
        body = WATCHDOG_RECOVERY_NUDGE_BODY_TEMPLATE_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        body = ""
    if body:
        return body
    print(
        "[op-simple-build] "
        f"[{utc_now_iso()}] "
        "watchdog recovery nudge template missing or empty; using embedded fallback body",
        flush=True,
    )
    return WATCHDOG_RECOVERY_NUDGE_BODY_FALLBACK


def _write_watchdog_recovery_nudge(
    cfg: RunConfig,
    *,
    cycle_number: int,
    monitored_branch: str,
    commit_ref: str,
    last_commit_sha: str,
    last_commit_at_utc: str,
    watchdog_age_minutes: float,
    stale_after_minutes: int,
) -> None:
    nudge_path = cfg.repo_root / RECOVERY_INSTRUCTIONS_FILE
    if nudge_path.exists():
        return

    generated_at = utc_now_iso()
    age_minutes = round(float(watchdog_age_minutes), 3)
    body_header = f"""# Recovery Nudge: Broad Runtime Sweep

Generated at: {generated_at}
Cycle: {cycle_number}
Reason: Watchdog observed no repository movement for {age_minutes} minutes.
Branch: {monitored_branch}
Commit ref: {commit_ref}
Last observed commit sha: {last_commit_sha}
Last observed commit timestamp: {last_commit_at_utc}
Watchdog stop threshold: {stale_after_minutes} minutes"""
    narrative = _load_watchdog_recovery_nudge_body()
    body = f"{body_header}\n\n{narrative}\n"

    try:
        nudge_path.write_text(body, encoding="utf-8")
    except OSError:
        return

    print(
        "[op-simple-build] "
        f"[{utc_now_iso()}] "
        f"cycle={cycle_number} watchdog emitted recovery nudge "
        f"path={RECOVERY_INSTRUCTIONS_FILE} age_minutes={age_minutes}",
        flush=True,
    )


def _load_watchdog_terminal_warning_nudge_body() -> str:
    try:
        body = WATCHDOG_TERMINAL_WARNING_NUDGE_BODY_TEMPLATE_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        body = ""
    if body:
        return body
    print(
        "[op-simple-build] "
        f"[{utc_now_iso()}] "
        "watchdog terminal-warning nudge template missing or empty; using embedded fallback body",
        flush=True,
    )
    return WATCHDOG_TERMINAL_WARNING_NUDGE_BODY_FALLBACK


def _write_watchdog_terminal_warning_nudge(
    cfg: RunConfig,
    *,
    cycle_number: int,
    monitored_branch: str,
    commit_ref: str,
    last_commit_sha: str,
    last_commit_at_utc: str,
    run_base_hard_age_minutes: float,
    run_base_hard_limit_minutes: int,
    warning_lead_minutes: int,
) -> bool:
    nudge_path = cfg.repo_root / TERMINAL_WARNING_INSTRUCTIONS_FILE
    if nudge_path.exists():
        return False

    generated_at = utc_now_iso()
    hard_age_minutes = round(float(run_base_hard_age_minutes), 3)
    threshold_minutes = max(0, int(run_base_hard_limit_minutes))
    lead_minutes = max(0, int(warning_lead_minutes))
    body_header = f"""# Recovery Nudge: Terminal Warning

Generated at: {generated_at}
Cycle: {cycle_number}
Reason: Watchdog hard-limit terminal stop is approaching.
Branch: {monitored_branch}
Commit ref: {commit_ref}
Last observed commit sha: {last_commit_sha}
Last observed commit timestamp: {last_commit_at_utc}
Run-base hard-limit age: {hard_age_minutes} minutes
Run-base hard-limit threshold: {threshold_minutes} minutes
Warning lead window: {lead_minutes} minutes"""
    narrative = _load_watchdog_terminal_warning_nudge_body()
    body = f"{body_header}\n\n{narrative}\n"

    try:
        nudge_path.write_text(body, encoding="utf-8")
    except OSError:
        return False

    print(
        "[op-simple-build] "
        f"[{utc_now_iso()}] "
        f"cycle={cycle_number} watchdog emitted terminal-warning nudge "
        f"path={TERMINAL_WARNING_INSTRUCTIONS_FILE} run_base_hard_age_minutes={hard_age_minutes}",
        flush=True,
    )
    return True


def _resolve_worker_dispatch_executor(cfg: RunConfig, worker_row: dict[str, Any] | None) -> tuple[str, str | None, str | None]:
    provider = _normalize_executor_provider(cfg.executor_provider)
    model = _resolve_executor_model(cfg, provider=provider) if provider == "blackbox" else str(cfg.executor_model or "").strip() or None
    warning: str | None = None
    if not cfg.allow_worker_executor_override or not isinstance(worker_row, dict):
        return provider, model, warning

    override_provider = str(worker_row.get("next_task_provider") or "").strip().lower()
    override_model = str(worker_row.get("next_task_model") or "").strip()
    if override_provider:
        if override_provider in EXECUTOR_PROVIDERS:
            provider = override_provider
            if provider == "blackbox" and not override_model:
                model = _resolve_executor_model(cfg, provider=provider)
            elif provider in {"codex", "openrouter"} and not override_model:
                model = str(cfg.executor_model or "").strip() or None
        else:
            warning = (
                f"invalid worker next_task_provider='{override_provider}' ignored; using base provider '{provider}'"
            )
    if override_model:
        model = override_model
    return provider, model, warning


def _launch_blackbox_dispatch(
    cfg: RunConfig,
    *,
    cycle_number: int,
    worker_id: str,
    packet_id: str,
    worker_worktree: Path,
    prompt: str,
    model: str | None,
) -> tuple[str, int | None, str | None, str]:
    # LLM interaction classification: reasoning_effort=medium_effort, tooling_effort=low_tooling.
    cmd, env, prep_error = _build_blackbox_exec_command(cfg, prompt, model=model)
    if prep_error:
        return "launch_failed", None, None, prep_error

    cycle_dir = _ensure_history_cycle_dir(cfg, cycle_number)
    safe_worker = re.sub(r"[^A-Za-z0-9._-]+", "-", worker_id or "worker")
    safe_packet = re.sub(r"[^A-Za-z0-9._-]+", "-", packet_id or "packet")
    dispatch_log = cycle_dir / f"dispatch-blackbox-{safe_worker}-{safe_packet}.log"
    try:
        with dispatch_log.open("w", encoding="utf-8") as handle:
            proc = subprocess.Popen(
                cmd,
                cwd=str(worker_worktree),
                stdout=handle,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )
    except FileNotFoundError:
        return "launch_failed", None, None, "blackbox binary not found"
    except OSError as exc:
        return "launch_failed", None, None, f"blackbox dispatch failed to start: {exc}"

    _append_new_executor_event(
        "op-simple-build/dispatch-blackbox",
        {
            "schema_version": SCHEMA_VERSION,
            "timestamp": utc_now_iso(),
            "cycle_number": int(cycle_number),
            "worker_id": worker_id,
            "packet_id": packet_id,
            "executor_provider": "blackbox",
            "executor_model": str(model or _resolve_executor_model(cfg, provider="blackbox") or ""),
            "blackbox_lane": _normalize_blackbox_lane(cfg.blackbox_lane),
            "pid": int(proc.pid),
            "dispatch_log": str(dispatch_log.resolve()),
            "status": "started",
        },
    )
    return "launched", int(proc.pid), None, "blackbox dispatch started"


def _dispatch_packets(
    cfg: RunConfig,
    cycle_number: int,
    *,
    reserved_slots: int = 0,
) -> dict[str, int]:
    # LLM interaction classification: reasoning_effort=high_effort, tooling_effort=medium_tooling.
    counters = {"attempted": 0, "launched": 0, "launch_failed": 0, "unknown": 0}
    packets = _load_worker_packets(cfg)
    if not packets:
        return counters

    script = _resolve_dispatch_script(cfg)
    alias_to_home = _profile_alias_to_home(cfg)
    worker_by_id = _worker_registry_index(cfg)
    expected_parent = cfg.worktrees_parent.expanduser().resolve()
    event_rows: list[dict[str, Any]] = []
    active_count = _active_worker_count(cfg)
    reserve = max(0, int(reserved_slots))
    effective_limit = max(0, int(cfg.max_parallel_workers) - reserve)

    for row in packets:
        if active_count >= effective_limit:
            break
        counters["attempted"] += 1
        worker_id = str(row.get("worker_id") or "")
        packet_id = str(row.get("packet_id") or "")
        prompt = str(row.get("prompt") or "").strip()
        profile_alias = str(row.get("profile_alias") or "")
        worker_row = worker_by_id.get(worker_id) if worker_id else None
        worker_worktree_raw = str((worker_row or {}).get("worktree") or "").strip()
        worker_worktree = Path(worker_worktree_raw).expanduser() if worker_worktree_raw else None
        dispatch_provider, dispatch_model, dispatch_warning = _resolve_worker_dispatch_executor(cfg, worker_row)

        timestamp = utc_now_iso()
        event = {
            "cycle_number": cycle_number,
            "worker_id": worker_id,
            "packet_id": packet_id,
            "profile_alias": profile_alias,
            "thread_id": None,
            "pid": None,
            "executor_provider": dispatch_provider,
            "executor_model": dispatch_model,
            "status": "unknown",
            "timestamp": timestamp,
            "message": "",
        }

        if _executor_uses_codex_backend(dispatch_provider) and script is None:
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
        try:
            worker_worktree_resolved = worker_worktree.resolve()
        except OSError:
            event["status"] = "launch_failed"
            event["message"] = "worker worktree path cannot be resolved"
            counters["launch_failed"] += 1
            event_rows.append(event)
            _append_jsonl(cfg.repo_root / DISPATCH_LAUNCH_LOG_FILE, event)
            continue
        if not _path_within_parent(worker_worktree_resolved, expected_parent):
            event["status"] = "launch_failed"
            event["message"] = (
                "worker worktree outside configured worktrees_parent: "
                f"{worker_worktree_resolved}"
            )
            counters["launch_failed"] += 1
            event_rows.append(event)
            _append_jsonl(cfg.repo_root / DISPATCH_LAUNCH_LOG_FILE, event)
            continue

        if _executor_uses_codex_backend(dispatch_provider):
            cmd = [
                "python3",
                str(script),
                "--cwd",
                str(worker_worktree_resolved),
                "--prompt",
                prompt,
                "--background",
                "--no-full-auto",
                "--extra-arg=--dangerously-bypass-approvals-and-sandbox",
            ]
            codex_profile_text = str(cfg.codex_profile or "").strip()
            if codex_profile_text:
                cmd.extend(["--extra-arg=-p", f"--extra-arg={codex_profile_text}"])
            model_text = str(dispatch_model or "").strip()
            if model_text:
                cmd.extend(["--extra-arg=--model", f"--extra-arg={model_text}"])
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
        else:
            status, pid, thread_id, message = _launch_blackbox_dispatch(
                cfg,
                cycle_number=cycle_number,
                worker_id=worker_id,
                packet_id=packet_id,
                worker_worktree=worker_worktree.resolve(),
                prompt=prompt,
                model=dispatch_model,
            )
            event["status"] = status
            event["pid"] = pid
            event["thread_id"] = thread_id
            event["message"] = message
            if status == "launched":
                counters["launched"] += 1
                active_count += 1
            elif status == "launch_failed":
                counters["launch_failed"] += 1
            else:
                counters["unknown"] += 1

        if dispatch_warning:
            current_message = str(event.get("message") or "").strip()
            event["message"] = f"{current_message}; {dispatch_warning}" if current_message else dispatch_warning

        event_rows.append(event)
        _append_jsonl(cfg.repo_root / DISPATCH_LAUNCH_LOG_FILE, event)

    if event_rows:
        _update_dispatch_registry(cfg, event_rows)
        _update_worker_registry_dispatch_state(cfg, event_rows)
    return counters


def _lane_base_watchdog_branch_map(cfg: RunConfig) -> tuple[dict[str, str], int]:
    plan_cycle_number = 0
    plan_lane_map: dict[str, str] | None = None
    plan_payload = _read_json(cfg.repo_root / ARTIFACT_FILES["plan_packets"], default={})
    if isinstance(plan_payload, dict):
        lane_map, lane_errors = _normalize_lane_base_branches(plan_payload.get("lane_base_branches"))
        if not lane_errors:
            plan_cycle_number = int(plan_payload.get("cycle_number") or 0)
            plan_lane_map = lane_map
            if lane_map:
                return lane_map, plan_cycle_number
    registry_payload = _read_json(cfg.repo_root / ARTIFACT_FILES["lane_base_watchdog_registry"], default={})
    if isinstance(registry_payload, dict):
        existing_map, existing_errors = _normalize_lane_base_branches(registry_payload.get("lane_base_branches"))
        if not existing_errors and existing_map:
            return existing_map, int(registry_payload.get("plan_cycle_number") or 0)
    if plan_lane_map is not None:
        return plan_lane_map, plan_cycle_number
    return {}, 0


def _refresh_lane_base_watchdog_registry(
    cfg: RunConfig,
    *,
    cycle_number: int,
    now_utc: datetime,
    force_reset_target: bool = False,
) -> dict[str, Any]:
    branch_map, plan_cycle_number = _lane_base_watchdog_branch_map(cfg)
    registry_path = cfg.repo_root / ARTIFACT_FILES["lane_base_watchdog_registry"]
    previous_payload = _read_json(registry_path, default={})
    if not isinstance(previous_payload, dict):
        previous_payload = {}
    previous_rows = previous_payload.get("lanes")
    previous_lanes = [row for row in previous_rows if isinstance(row, dict)] if isinstance(previous_rows, list) else []
    previous_by_lane: dict[str, dict[str, Any]] = {}
    for row in previous_lanes:
        lane_id = str(row.get("lane_id") or "").strip()
        if lane_id:
            previous_by_lane[lane_id] = row

    aggregate_prev = previous_payload.get("aggregate") if isinstance(previous_payload.get("aggregate"), dict) else {}
    previous_signal = str(aggregate_prev.get("progress_signal") or "").strip()
    previous_offset_raw = aggregate_prev.get("watchdog_age_offset_minutes")
    try:
        previous_offset = float(previous_offset_raw) if previous_offset_raw is not None else None
    except (TypeError, ValueError):
        previous_offset = None
    if previous_offset is not None and previous_offset < 0:
        previous_offset = 0.0
    previous_reset_at_text = str(aggregate_prev.get("watchdog_target_reset_at_utc") or "").strip()
    previous_reset_at = _parse_iso_datetime(previous_reset_at_text)
    reset_at_utc = previous_reset_at_text

    lane_rows: list[dict[str, Any]] = []
    seen_lane_count = 0
    missing_lane_count = 0
    latest_seen_sha = ""
    latest_seen_at_utc = ""
    latest_seen_age_minutes: float | None = None
    lane_progress_components: dict[str, str] = {}

    for lane_id, branch_name in sorted(branch_map.items(), key=lambda item: item[0]):
        prev = previous_by_lane.get(lane_id, {})
        prev_ever_seen = bool(prev.get("ever_seen"))
        prev_first_seen_at = prev.get("first_seen_at")
        prev_first_seen_cycle = prev.get("first_seen_cycle")
        prev_last_sha = str(prev.get("last_seen_commit_sha") or "").strip()
        current_sha = _git_text(cfg.repo_root, "rev-parse", branch_name) or ""
        exists = bool(current_sha)
        ever_seen = bool(prev_ever_seen or exists)
        first_seen_at = prev_first_seen_at
        first_seen_cycle = prev_first_seen_cycle
        if exists and not prev_ever_seen:
            first_seen_at = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
            first_seen_cycle = int(cycle_number)
        commit_epoch = _git_commit_epoch_seconds(cfg.repo_root, branch_name) if exists else None
        commit_at_utc = ""
        commit_age_minutes: float | None = None
        if commit_epoch is not None:
            commit_at = datetime.fromtimestamp(commit_epoch, timezone.utc)
            commit_at_utc = commit_at.strftime("%Y-%m-%dT%H:%M:%SZ")
            commit_age_minutes = max(0.0, (now_utc.timestamp() - float(commit_epoch)) / 60.0)

        if ever_seen and exists and commit_age_minutes is not None:
            seen_lane_count += 1
            lane_progress_components[lane_id] = current_sha
            if latest_seen_age_minutes is None or commit_age_minutes < latest_seen_age_minutes:
                latest_seen_age_minutes = commit_age_minutes
                latest_seen_sha = current_sha
                latest_seen_at_utc = commit_at_utc
        else:
            missing_lane_count += 1

        lane_rows.append(
            {
                "lane_id": lane_id,
                "lane_base_branch": branch_name,
                "exists": exists,
                "ever_seen": ever_seen,
                "first_seen_at": first_seen_at,
                "first_seen_cycle": first_seen_cycle,
                "last_seen_commit_sha": current_sha if exists else prev_last_sha,
                "last_seen_commit_at_utc": commit_at_utc if exists else str(prev.get("last_seen_commit_at_utc") or ""),
                "last_seen_cycle": int(cycle_number) if exists else prev.get("last_seen_cycle"),
            }
        )

    signal_seed = {"lane_commits": lane_progress_components}
    progress_signal = hashlib.sha256(
        json.dumps(signal_seed, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    progress_changed = bool(previous_signal and progress_signal and previous_signal != progress_signal)
    reset_target = bool(force_reset_target or previous_offset is None or progress_changed)
    if previous_reset_at is not None and previous_reset_at > now_utc:
        reset_target = True

    lane_watchdog_age_minutes: float | None = None
    offset_minutes = previous_offset
    if latest_seen_age_minutes is not None:
        if reset_target:
            offset_minutes = latest_seen_age_minutes
            reset_at_utc = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        lane_watchdog_age_minutes = max(0.0, latest_seen_age_minutes - float(offset_minutes or 0.0))
    else:
        offset_minutes = None
        reset_at_utc = ""

    aggregate_payload = {
        "seen_lane_count": int(seen_lane_count),
        "missing_lane_count": int(missing_lane_count),
        "latest_seen_commit_sha": latest_seen_sha,
        "latest_seen_commit_at_utc": latest_seen_at_utc,
        "latest_seen_commit_age_minutes": round(latest_seen_age_minutes, 3) if latest_seen_age_minutes is not None else None,
        "watchdog_age_offset_minutes": round(offset_minutes, 3) if offset_minutes is not None else None,
        "watchdog_age_minutes": round(lane_watchdog_age_minutes, 3) if lane_watchdog_age_minutes is not None else None,
        "watchdog_target_reset_at_utc": reset_at_utc,
        "progress_signal": progress_signal,
        "progress_changed": bool(progress_changed),
        "progress_components": lane_progress_components,
    }
    next_payload = {
        "schema_version": SCHEMA_VERSION,
        "updated_at": utc_now_iso(),
        "cycle_number": int(cycle_number),
        "plan_cycle_number": int(plan_cycle_number),
        "lane_base_branches": dict(sorted(branch_map.items(), key=lambda item: item[0])),
        "lanes": lane_rows,
        "aggregate": aggregate_payload,
    }
    _atomic_write_json(registry_path, next_payload)
    return {
        "lane_base_branches": branch_map,
        "seen_lane_count": int(seen_lane_count),
        "missing_lane_count": int(missing_lane_count),
        "lane_watchdog_age_minutes": lane_watchdog_age_minutes,
        "lane_progress_signal": progress_signal,
        "lane_progress_changed": bool(progress_changed),
        "registry_path": str(registry_path.resolve()),
    }


def _watchdog_progress_signal(cfg: RunConfig) -> dict[str, Any]:
    mergeability_payload = _read_json(cfg.repo_root / ARTIFACT_FILES["mergeability_report"], default={})
    if not isinstance(mergeability_payload, dict):
        mergeability_payload = {}
    task_payload = _read_json(cfg.repo_root / ARTIFACT_FILES["task_execution_state"], default={})
    if not isinstance(task_payload, dict):
        task_payload = {}
    worker_payload = _read_json(cfg.repo_root / ARTIFACT_FILES["worker_registry"], default={})
    if not isinstance(worker_payload, dict):
        worker_payload = {}

    task_rows = task_payload.get("tasks")
    tasks = [row for row in task_rows if isinstance(row, dict)] if isinstance(task_rows, list) else []
    worker_rows = worker_payload.get("workers")
    workers = [row for row in worker_rows if isinstance(row, dict)] if isinstance(worker_rows, list) else []
    handoff_payload = task_payload.get("last_handoff_outcome")
    handoff = handoff_payload if isinstance(handoff_payload, dict) else {}
    handoff_status = str(handoff.get("status") or "").strip()
    handoff_timestamp = str(handoff.get("timestamp") or "").strip()
    if handoff_status.lower() in {"", "unknown", "none"}:
        handoff_timestamp = ""

    fan_in_accepted_task_count = 0
    lane_merged_task_count = 0
    for row in tasks:
        if str(row.get("lane_fan_in_accepted_at") or "").strip():
            fan_in_accepted_task_count += 1
        if str(row.get("lane_to_run_merged_at") or "").strip():
            lane_merged_task_count += 1

    fan_in_accepted_worker_count = 0
    for row in workers:
        if str(row.get("fan_in_status") or "").strip() == "accepted":
            fan_in_accepted_worker_count += 1

    merge_blockers = mergeability_payload.get("merge_blockers")
    merge_blocker_count = len(merge_blockers) if isinstance(merge_blockers, list) else 0
    components = {
        "mergeability_fingerprint": str(mergeability_payload.get("progress_fingerprint") or "").strip(),
        "mergeability_unmerged_commit_count": int(mergeability_payload.get("unmerged_commit_count") or 0),
        "merge_blocker_count": int(merge_blocker_count),
        "fan_in_accepted_task_count": int(fan_in_accepted_task_count),
        "lane_merged_task_count": int(lane_merged_task_count),
        "fan_in_accepted_worker_count": int(fan_in_accepted_worker_count),
        "last_handoff_status": handoff_status,
        "last_handoff_timestamp": handoff_timestamp,
        "last_handoff_reason_codes": sorted(
            str(item).strip()
            for item in handoff.get("reason_codes", [])
            if str(item).strip()
        )
        if isinstance(handoff.get("reason_codes"), list)
        else [],
    }
    signal = hashlib.sha256(
        json.dumps(components, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "signal": signal,
        "components": components,
    }


def _watchdog_tick(cfg: RunConfig, cycle_number: int, *, force_reset_target: bool = False) -> tuple[bool, dict[str, Any]]:
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
    run_base_hard_limit_minutes = int(stale_after_minutes) * int(WATCHDOG_RUN_BASE_HARD_LIMIT_MULTIPLIER)
    run_base_hard_warning_minutes = max(0, int(run_base_hard_limit_minutes) - int(WATCHDOG_TERMINAL_WARNING_LEAD_MINUTES))
    previous_sha = str(state.get("last_commit_sha") or "").strip()
    offset_minutes_raw = state.get("watchdog_age_offset_minutes")
    hard_offset_minutes_raw = state.get("run_base_hard_age_offset_minutes")
    try:
        offset_minutes = float(offset_minutes_raw) if offset_minutes_raw is not None else None
    except (TypeError, ValueError):
        offset_minutes = None
    try:
        hard_offset_minutes = float(hard_offset_minutes_raw) if hard_offset_minutes_raw is not None else None
    except (TypeError, ValueError):
        hard_offset_minutes = None
    if offset_minutes is not None and offset_minutes < 0:
        offset_minutes = 0.0
    if hard_offset_minutes is not None and hard_offset_minutes < 0:
        hard_offset_minutes = 0.0

    reset_at_utc = str(state.get("watchdog_target_reset_at_utc") or "").strip()
    hard_reset_at_utc = str(state.get("run_base_hard_target_reset_at_utc") or "").strip()
    progress_row = _watchdog_progress_signal(cfg)
    progress_signal = str(progress_row.get("signal") or "").strip()
    previous_progress_signal = str(state.get("progress_signal") or "").strip()
    progress_changed = bool(previous_progress_signal and progress_signal and previous_progress_signal != progress_signal)
    reset_target = (
        force_reset_target
        or not previous_sha
        or previous_sha != current_sha
        or offset_minutes is None
        or progress_changed
    )
    hard_reset_target = (
        force_reset_target
        or not previous_sha
        or previous_sha != current_sha
        or hard_offset_minutes is None
    )
    run_lock = _read_json(cfg.repo_root / RUN_LOCK_FILE, default={})
    run_started_at_utc = ""
    if isinstance(run_lock, dict):
        run_started_at_utc = str(run_lock.get("started_at") or "").strip()
    run_started_at = _parse_iso_datetime(run_started_at_utc)
    previous_target_reset = _parse_iso_datetime(reset_at_utc)
    previous_hard_target_reset = _parse_iso_datetime(hard_reset_at_utc)
    if run_started_at is not None and (
        previous_target_reset is None or run_started_at > previous_target_reset
    ):
        reset_target = True
    if run_started_at is not None and (
        previous_hard_target_reset is None or run_started_at > previous_hard_target_reset
    ):
        hard_reset_target = True
    watchdog_age_minutes: float | None = None
    run_base_hard_age_minutes: float | None = None
    near_stale_threshold_minutes = max(0, int(stale_after_minutes) - int(WATCHDOG_NEAR_STALE_MARGIN_MINUTES))
    near_stale = False
    if commit_age_minutes is None:
        is_stale = False
        run_base_hard_stale = False
    else:
        if reset_target:
            offset_minutes = commit_age_minutes
            reset_at_utc = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        if hard_reset_target:
            hard_offset_minutes = commit_age_minutes
            hard_reset_at_utc = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        watchdog_age_minutes = max(0.0, commit_age_minutes - float(offset_minutes or 0.0))
        run_base_hard_age_minutes = max(0.0, commit_age_minutes - float(hard_offset_minutes or 0.0))
        is_stale = watchdog_age_minutes > float(stale_after_minutes)
        run_base_hard_stale = run_base_hard_age_minutes > float(run_base_hard_limit_minutes)
        near_stale = bool(
            not is_stale and watchdog_age_minutes is not None and watchdog_age_minutes >= float(near_stale_threshold_minutes)
        )

    lane_watchdog = _refresh_lane_base_watchdog_registry(
        cfg,
        cycle_number=cycle_number,
        now_utc=now_utc,
        force_reset_target=force_reset_target,
    )
    lane_seen_branch_count = int(lane_watchdog.get("seen_lane_count") or 0)
    lane_missing_branch_count = int(lane_watchdog.get("missing_lane_count") or 0)
    lane_watchdog_age_minutes = lane_watchdog.get("lane_watchdog_age_minutes")
    lane_is_stale = bool(
        lane_watchdog_age_minutes is not None and float(lane_watchdog_age_minutes) > float(stale_after_minutes)
    )
    all_monitored_branches_idle_stale = bool(is_stale and (lane_is_stale if lane_seen_branch_count > 0 else True))

    last_warning_cycle_raw = state.get("terminal_warning_last_emitted_cycle")
    try:
        last_warning_cycle = int(last_warning_cycle_raw) if last_warning_cycle_raw is not None else None
    except (TypeError, ValueError):
        last_warning_cycle = None
    warning_cooldown_cycles = max(1, int(WATCHDOG_TERMINAL_WARNING_COOLDOWN_CYCLES))
    warning_cooldown_active = bool(
        last_warning_cycle is not None and int(cycle_number) - int(last_warning_cycle) <= warning_cooldown_cycles
    )
    near_terminal_hard_limit = bool(
        run_base_hard_age_minutes is not None
        and run_base_hard_age_minutes >= float(run_base_hard_warning_minutes)
        and run_base_hard_age_minutes < float(run_base_hard_limit_minutes)
    )
    emitted_terminal_warning = False
    terminal_warning_last_emitted_cycle = last_warning_cycle
    terminal_warning_last_emitted_at_utc = str(state.get("terminal_warning_last_emitted_at_utc") or "").strip()
    if near_terminal_hard_limit and not warning_cooldown_active and commit_age_minutes is not None:
        emitted_terminal_warning = _write_watchdog_terminal_warning_nudge(
            cfg,
            cycle_number=cycle_number,
            monitored_branch=monitored_branch,
            commit_ref=commit_ref,
            last_commit_sha=str(current_sha or ""),
            last_commit_at_utc=last_commit_at_utc,
            run_base_hard_age_minutes=float(run_base_hard_age_minutes or 0.0),
            run_base_hard_limit_minutes=int(run_base_hard_limit_minutes),
            warning_lead_minutes=int(WATCHDOG_TERMINAL_WARNING_LEAD_MINUTES),
        )
        if emitted_terminal_warning:
            terminal_warning_last_emitted_cycle = int(cycle_number)
            terminal_warning_last_emitted_at_utc = utc_now_iso()

    should_stop = bool(run_base_hard_stale or all_monitored_branches_idle_stale)
    next_state = {
        "schema_version": SCHEMA_VERSION,
        "cycle_number": cycle_number,
        "monitored_branch": monitored_branch,
        "commit_ref": commit_ref,
        "last_commit_sha": current_sha,
        "last_commit_at_utc": last_commit_at_utc,
        "last_commit_age_minutes": round(commit_age_minutes, 3) if commit_age_minutes is not None else None,
        "watchdog_age_offset_minutes": round(offset_minutes, 3) if offset_minutes is not None else None,
        "watchdog_age_minutes": round(watchdog_age_minutes, 3) if watchdog_age_minutes is not None else None,
        "watchdog_target_reset_at_utc": reset_at_utc,
        "run_base_hard_age_offset_minutes": round(hard_offset_minutes, 3) if hard_offset_minutes is not None else None,
        "run_base_hard_age_minutes": round(run_base_hard_age_minutes, 3) if run_base_hard_age_minutes is not None else None,
        "run_base_hard_target_reset_at_utc": hard_reset_at_utc,
        "run_base_hard_limit_minutes": int(run_base_hard_limit_minutes),
        "run_base_hard_warning_minutes": int(run_base_hard_warning_minutes),
        "terminal_warning_last_emitted_cycle": terminal_warning_last_emitted_cycle,
        "terminal_warning_last_emitted_at_utc": terminal_warning_last_emitted_at_utc,
        "terminal_warning_cooldown_cycles": int(warning_cooldown_cycles),
        "near_terminal_hard_limit": bool(near_terminal_hard_limit),
        "terminal_warning_emitted_this_cycle": bool(emitted_terminal_warning),
        "lane_aggregate_watchdog_age_minutes": (
            round(float(lane_watchdog_age_minutes), 3) if lane_watchdog_age_minutes is not None else None
        ),
        "lane_seen_branch_count": int(lane_seen_branch_count),
        "lane_missing_branch_count": int(lane_missing_branch_count),
        "stale_after_minutes": stale_after_minutes,
        "stale": bool(should_stop),
        "all_monitored_branches_idle_stale": bool(all_monitored_branches_idle_stale),
        "run_base_hard_stale": bool(run_base_hard_stale),
        "near_stale_threshold_minutes": int(near_stale_threshold_minutes),
        "near_stale": bool(near_stale),
        "progress_signal": progress_signal,
        "progress_changed": bool(progress_changed),
        "progress_components": progress_row.get("components") if isinstance(progress_row.get("components"), dict) else {},
        "lane_progress_signal": str(lane_watchdog.get("lane_progress_signal") or "").strip(),
        "lane_progress_changed": bool(lane_watchdog.get("lane_progress_changed")),
        "lane_base_watchdog_registry_ref": str(lane_watchdog.get("registry_path") or ""),
    }
    _atomic_write_json(state_path, next_state)

    if watchdog_age_minutes is not None and float(watchdog_age_minutes) >= float(WATCHDOG_RECOVERY_NUDGE_MINUTES):
        _write_watchdog_recovery_nudge(
            cfg,
            cycle_number=cycle_number,
            monitored_branch=monitored_branch,
            commit_ref=commit_ref,
            last_commit_sha=str(current_sha or ""),
            last_commit_at_utc=last_commit_at_utc,
            watchdog_age_minutes=float(watchdog_age_minutes),
            stale_after_minutes=int(stale_after_minutes),
        )

    if commit_age_minutes is None:
        exit_signal = {
            "schema_version": SCHEMA_VERSION,
            "cycle_number": cycle_number,
            "reason_code": "watchdog_commit_age_unknown",
            "message": f"unable to resolve commit age for monitored branch '{monitored_branch}'",
            "monitored_branch": monitored_branch,
            "commit_ref": commit_ref,
            "stale_after_minutes": stale_after_minutes,
            "watchdog_age_minutes": None,
            "commit_age_minutes": None,
            "run_base_hard_limit_minutes": int(run_base_hard_limit_minutes),
            "run_base_hard_warning_minutes": int(run_base_hard_warning_minutes),
            "run_base_hard_age_minutes": None,
            "lane_aggregate_watchdog_age_minutes": (
                round(float(lane_watchdog_age_minutes), 3) if lane_watchdog_age_minutes is not None else None
            ),
            "lane_seen_branch_count": int(lane_seen_branch_count),
            "lane_missing_branch_count": int(lane_missing_branch_count),
            "near_stale_threshold_minutes": int(near_stale_threshold_minutes),
            "near_stale": False,
            "near_terminal_hard_limit": False,
            "progress_signal": progress_signal,
            "progress_changed": bool(progress_changed),
        }
    else:
        if run_base_hard_stale:
            reason_code = "stale_run_base_hard_limit"
            message = (
                f"run-base branch '{monitored_branch}' showed no commit movement for "
                f"{float(run_base_hard_age_minutes or 0.0):.1f} minutes; hard limit is "
                f"{run_base_hard_limit_minutes} minutes"
            )
        else:
            reason_code = "stale_base_branch_commit"
            if lane_seen_branch_count > 0:
                message = (
                    f"no new commit observed across monitored run/lane branches for base threshold "
                    f"{stale_after_minutes} minutes; run-base age={float(watchdog_age_minutes or 0.0):.1f}m "
                    f"lane-aggregate age={float(lane_watchdog_age_minutes or 0.0):.1f}m"
                )
            else:
                message = (
                    f"no new commit observed on '{monitored_branch}' for {float(watchdog_age_minutes or 0.0):.1f} minutes; "
                    f"watchdog limit is {stale_after_minutes} minutes"
                )
        exit_signal = {
            "schema_version": SCHEMA_VERSION,
            "cycle_number": cycle_number,
            "reason_code": reason_code,
            "message": message,
            "monitored_branch": monitored_branch,
            "commit_ref": commit_ref,
            "last_commit_sha": current_sha,
            "last_commit_at_utc": last_commit_at_utc,
            "watchdog_age_minutes": round(watchdog_age_minutes, 3) if watchdog_age_minutes is not None else None,
            "watchdog_target_reset_at_utc": reset_at_utc,
            "stale_after_minutes": stale_after_minutes,
            "commit_age_minutes": round(commit_age_minutes, 3),
            "run_base_hard_limit_minutes": int(run_base_hard_limit_minutes),
            "run_base_hard_warning_minutes": int(run_base_hard_warning_minutes),
            "run_base_hard_age_minutes": round(run_base_hard_age_minutes, 3) if run_base_hard_age_minutes is not None else None,
            "lane_aggregate_watchdog_age_minutes": (
                round(float(lane_watchdog_age_minutes), 3) if lane_watchdog_age_minutes is not None else None
            ),
            "lane_seen_branch_count": int(lane_seen_branch_count),
            "lane_missing_branch_count": int(lane_missing_branch_count),
            "all_monitored_branches_idle_stale": bool(all_monitored_branches_idle_stale),
            "run_base_hard_stale": bool(run_base_hard_stale),
            "near_stale_threshold_minutes": int(near_stale_threshold_minutes),
            "near_stale": bool(near_stale),
            "near_terminal_hard_limit": bool(near_terminal_hard_limit),
            "progress_signal": progress_signal,
            "progress_changed": bool(progress_changed),
        }

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
    mergeability_payload = _read_json(cfg.repo_root / ARTIFACT_FILES["mergeability_report"], default={})
    if not isinstance(mergeability_payload, dict):
        mergeability_payload = {}
    mergeability_snapshot = {
        "cycle_mode": str(mergeability_payload.get("cycle_mode") or "").strip(),
        "run_base_ref": str(mergeability_payload.get("run_base_ref") or "").strip(),
        "run_base_sha": str(mergeability_payload.get("run_base_sha") or "").strip(),
        "unmerged_commit_count": int(mergeability_payload.get("unmerged_commit_count") or 0),
        "merge_blockers": mergeability_payload.get("merge_blockers")
        if isinstance(mergeability_payload.get("merge_blockers"), list)
        else [],
        "lane_status": mergeability_payload.get("lane_status")
        if isinstance(mergeability_payload.get("lane_status"), dict)
        else {},
    }
    context = {
        "stop_reason": stop_reason,
        "run_base_branch": str(run_context.get("run_base_branch") or ""),
        "run_base_from_branch": str(run_context.get("run_base_from_branch") or ""),
        "run_base_from_commit": str(run_context.get("run_base_from_commit") or ""),
        "app_lifecycle_path": str((cfg.repo_root / APP_LIFECYCLE_FILE).resolve()),
        "app_lifecycle_active_era_id": _active_lifecycle_era_id(cfg),
        "mergeability_report_path": str((cfg.repo_root / ARTIFACT_FILES["mergeability_report"]).resolve()),
        "mergeability_snapshot": mergeability_snapshot,
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


def _normalized_dispatch_counts(dispatch_counts: dict[str, Any] | None) -> dict[str, int]:
    payload = dispatch_counts if isinstance(dispatch_counts, dict) else {}
    return {
        "attempted": int(payload.get("attempted") or 0),
        "launched": int(payload.get("launched") or 0),
        "launch_failed": int(payload.get("launch_failed") or 0),
        "unknown": int(payload.get("unknown") or 0),
    }


def _write_terminal_capsule(
    cfg: RunConfig,
    *,
    cycle_number: int,
    reason_code: str,
    stop_reason: str | None,
    cycle_mode: str,
    manager_name: str | None,
    manager_result: ManagerResult | None,
    manager_statuses: dict[str, dict[str, str]] | None,
    dispatch_counts: dict[str, Any] | None,
    watchdog_signal: dict[str, Any] | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    timeout_state = _load_timeout_adaptation_state(cfg)
    manager_status = ""
    manager_timeout = False
    manager_message = ""
    manager_stdout_path = None
    manager_stderr_path = None
    manager_duration_seconds = None
    if isinstance(manager_result, ManagerResult):
        manager_status = str(manager_result.status or "").strip()
        manager_timeout = bool(manager_result.timeout)
        manager_message = str(manager_result.message or "").strip()
        manager_stdout_path = manager_result.stdout_path
        manager_stderr_path = manager_result.stderr_path
        manager_duration_seconds = float(manager_result.duration_seconds)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "updated_at": utc_now_iso(),
        "cycle_number": int(cycle_number),
        "reason_code": str(reason_code or "").strip() or "unknown_terminal_reason",
        "stop_reason": str(stop_reason or "").strip(),
        "cycle_mode": str(cycle_mode or "").strip() or "normal",
        "manager": str(manager_name or "").strip() or None,
        "manager_status": manager_status,
        "manager_timeout": manager_timeout,
        "manager_message": manager_message,
        "manager_stdout_path": manager_stdout_path,
        "manager_stderr_path": manager_stderr_path,
        "manager_duration_seconds": manager_duration_seconds,
        "manager_statuses": manager_statuses if isinstance(manager_statuses, dict) else {},
        "dispatch_counts": _normalized_dispatch_counts(dispatch_counts),
        "watchdog_signal": watchdog_signal if isinstance(watchdog_signal, dict) else {},
        "details": details if isinstance(details, dict) else {},
        "timeout_state": {
            "consecutive_boss_timeouts": int(timeout_state.get("consecutive_boss_timeouts") or 0),
            "timeout_threshold": int(timeout_state.get("timeout_threshold") or 2),
            "adaptation_active": bool(timeout_state.get("adaptation_active")),
            "rotation_required": bool(timeout_state.get("rotation_required")),
            "last_timeout_profile_alias": str(timeout_state.get("last_timeout_profile_alias") or "").strip(),
            "last_timeout_reason": str(timeout_state.get("last_timeout_reason") or "").strip(),
        },
    }
    _atomic_write_json(cfg.repo_root / ARTIFACT_FILES["terminal_capsule"], payload)


def _persist_cycle_summary_stop_reason(cfg: RunConfig, *, cycle_number: int, stop_reason: str | None) -> None:
    normalized_reason = str(stop_reason or "").strip()
    if not normalized_reason:
        return
    summary_path = cfg.repo_root / ARTIFACT_FILES["cycle_summary"]
    summary_payload = _read_json(summary_path, default={})
    if not isinstance(summary_payload, dict):
        summary_payload = {}
    termination_payload = summary_payload.get("termination")
    if not isinstance(termination_payload, dict):
        termination_payload = {}
    if normalized_reason not in NON_TERMINAL_STOP_REASONS:
        termination_payload["reason_code"] = normalized_reason
    summary_payload["schema_version"] = SCHEMA_VERSION
    summary_payload["cycle_number"] = int(cycle_number)
    summary_payload["termination"] = termination_payload
    summary_payload["stop_reason"] = normalized_reason
    if normalized_reason == "project_done":
        summary_payload["project_done"] = True
    elif normalized_reason == "insurmountable_blocker":
        summary_payload["insurmountable_blocker"] = True
    _atomic_write_json(summary_path, summary_payload)


def _mergeability_run_base_ref(cfg: RunConfig) -> str:
    init_state = _read_json(cfg.repo_root / INITIALIZE_STATE_FILE, default={})
    run_context = init_state.get("run_context") if isinstance(init_state, dict) else {}
    if isinstance(run_context, dict):
        candidate = str(run_context.get("run_base_branch") or "").strip()
        if candidate:
            return candidate
    monitored_branch = str(init_state.get("monitored_branch") or "").strip() if isinstance(init_state, dict) else ""
    if monitored_branch:
        return monitored_branch
    return "main"


def _mergeability_progress_fingerprint(payload: dict[str, Any]) -> str:
    seed = {
        "run_base_sha": str(payload.get("run_base_sha") or ""),
        "lane_shas": payload.get("lane_shas") if isinstance(payload.get("lane_shas"), dict) else {},
        "lane_status": payload.get("lane_status") if isinstance(payload.get("lane_status"), dict) else {},
        "merge_blockers": payload.get("merge_blockers") if isinstance(payload.get("merge_blockers"), list) else [],
        "unmerged_commit_count": int(payload.get("unmerged_commit_count") or 0),
    }
    return hashlib.sha256(json.dumps(seed, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _task_last_handoff_head_commit(task_row: dict[str, Any]) -> str:
    last = task_row.get("last_handoff_outcome")
    if not isinstance(last, dict):
        return ""
    return str(last.get("head_commit") or "").strip()


def _task_last_handoff_branch(task_row: dict[str, Any]) -> str:
    last = task_row.get("last_handoff_outcome")
    if not isinstance(last, dict):
        return ""
    return str(last.get("branch") or "").strip()


def _lane_task_counts(task_rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    lane_counts: dict[str, dict[str, int]] = {}
    for row in task_rows:
        lane_id = str(row.get("lane_id") or "").strip() or "unscoped"
        counts = lane_counts.setdefault(lane_id, {"pending": 0, "in_progress": 0, "done": 0, "blocked": 0})
        status = str(row.get("status") or "").strip()
        if status in counts:
            counts[status] += 1
    return lane_counts


def _all_lane_tasks_done(counts: dict[str, int]) -> bool:
    pending = int(counts.get("pending") or 0)
    in_progress = int(counts.get("in_progress") or 0)
    blocked = int(counts.get("blocked") or 0)
    done = int(counts.get("done") or 0)
    return pending == 0 and in_progress == 0 and blocked == 0 and done > 0


def _retire_queue_item(
    cfg: RunConfig,
    *,
    cycle_number: int,
    queue_items_by_id: dict[str, dict[str, Any]],
    queue_item_id: str,
    retirement_reason_code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> bool:
    queue_item = queue_items_by_id.pop(queue_item_id, None)
    if not isinstance(queue_item, dict):
        return False
    _append_merge_journal(
        cfg,
        cycle_number=cycle_number,
        event="retired",
        kind=str(queue_item.get("kind") or "").strip(),
        lane_id=str(queue_item.get("lane_id") or "").strip(),
        task_id=str(queue_item.get("task_id") or "").strip() or None,
        target_branch=str(queue_item.get("target_branch") or "").strip(),
        source_commit=str(queue_item.get("source_commit") or "").strip(),
        source_ref=str(queue_item.get("source_ref") or "").strip() or None,
        queue_item_id=queue_item_id,
        status="retired",
        message=message,
        details={
            "retirement_reason_code": str(retirement_reason_code or "").strip() or "queue_item_obsolete",
            **(details if isinstance(details, dict) else {}),
        },
    )
    return True


def _reconcile_merge_queue_items(
    cfg: RunConfig,
    *,
    cycle_number: int,
    run_base_ref: str,
    task_rows: list[dict[str, Any]],
    lane_map: dict[str, str],
    queue_items_by_id: dict[str, dict[str, Any]],
) -> dict[str, int]:
    retired_count = 0
    task_rows_by_id = {
        str(row.get("task_id") or "").strip(): row
        for row in task_rows
        if isinstance(row, dict) and str(row.get("task_id") or "").strip()
    }
    lane_counts = _lane_task_counts(task_rows)
    for queue_item_id, queue_item in list(queue_items_by_id.items()):
        kind = str(queue_item.get("kind") or "").strip()
        lane_id = str(queue_item.get("lane_id") or "").strip() or "unscoped"
        task_id = str(queue_item.get("task_id") or "").strip()
        target_branch = str(queue_item.get("target_branch") or "").strip()
        source_commit = str(queue_item.get("source_commit") or "").strip()
        if _merge_item_has_git_proof(cfg, queue_item):
            if _retire_queue_item(
                cfg,
                cycle_number=cycle_number,
                queue_items_by_id=queue_items_by_id,
                queue_item_id=queue_item_id,
                retirement_reason_code="git_proof_present",
                message="queue item retired because git ancestry already proves merge completion",
            ):
                retired_count += 1
            continue
        if kind == "task_to_lane":
            task_row = task_rows_by_id.get(task_id)
            if not isinstance(task_row, dict):
                if _retire_queue_item(
                    cfg,
                    cycle_number=cycle_number,
                    queue_items_by_id=queue_items_by_id,
                    queue_item_id=queue_item_id,
                    retirement_reason_code="task_missing",
                    message=f"queue item retired because task '{task_id or 'unknown'}' no longer exists in task state",
                ):
                    retired_count += 1
                continue
            current_status = str(task_row.get("status") or "").strip()
            current_lane_id = str(task_row.get("lane_id") or "").strip() or "unscoped"
            current_head_commit = _task_last_handoff_head_commit(task_row)
            current_target_branch = str(lane_map.get(current_lane_id) or "").strip()
            if current_status != "done" or not current_head_commit:
                if _retire_queue_item(
                    cfg,
                    cycle_number=cycle_number,
                    queue_items_by_id=queue_items_by_id,
                    queue_item_id=queue_item_id,
                    retirement_reason_code="task_no_longer_done",
                    message=f"queue item retired because task '{task_id or 'unknown'}' is no longer done with authoritative head commit",
                ):
                    retired_count += 1
                continue
            if current_lane_id != lane_id:
                if _retire_queue_item(
                    cfg,
                    cycle_number=cycle_number,
                    queue_items_by_id=queue_items_by_id,
                    queue_item_id=queue_item_id,
                    retirement_reason_code="task_lane_changed",
                    message=f"queue item retired because task '{task_id or 'unknown'}' moved to lane '{current_lane_id}'",
                    details={"current_lane_id": current_lane_id},
                ):
                    retired_count += 1
                continue
            if current_head_commit != source_commit:
                if _retire_queue_item(
                    cfg,
                    cycle_number=cycle_number,
                    queue_items_by_id=queue_items_by_id,
                    queue_item_id=queue_item_id,
                    retirement_reason_code="superseded_by_newer_head_commit",
                    message=f"queue item retired because task '{task_id or 'unknown'}' advanced to newer head commit '{current_head_commit}'",
                    details={"current_head_commit": current_head_commit},
                ):
                    retired_count += 1
                continue
            if current_target_branch and target_branch != current_target_branch:
                if _retire_queue_item(
                    cfg,
                    cycle_number=cycle_number,
                    queue_items_by_id=queue_items_by_id,
                    queue_item_id=queue_item_id,
                    retirement_reason_code="target_branch_changed",
                    message=f"queue item retired because lane target branch changed to '{current_target_branch}'",
                    details={"current_target_branch": current_target_branch},
                ):
                    retired_count += 1
                continue
        elif kind == "lane_to_run":
            counts = lane_counts.get(lane_id, {"pending": 0, "in_progress": 0, "done": 0, "blocked": 0})
            current_source_ref = str(lane_map.get(lane_id) or "").strip()
            current_lane_tip = _git_resolve_commit(cfg.repo_root, current_source_ref) if current_source_ref else ""
            if target_branch != str(run_base_ref or "").strip():
                if _retire_queue_item(
                    cfg,
                    cycle_number=cycle_number,
                    queue_items_by_id=queue_items_by_id,
                    queue_item_id=queue_item_id,
                    retirement_reason_code="run_base_target_changed",
                    message=f"queue item retired because run-base target changed to '{run_base_ref}'",
                    details={"current_run_base_ref": str(run_base_ref or "").strip()},
                ):
                    retired_count += 1
                continue
            if not _all_lane_tasks_done(counts):
                if _retire_queue_item(
                    cfg,
                    cycle_number=cycle_number,
                    queue_items_by_id=queue_items_by_id,
                    queue_item_id=queue_item_id,
                    retirement_reason_code="lane_no_longer_complete",
                    message=f"queue item retired because lane '{lane_id}' no longer satisfies all-tasks-done gate",
                ):
                    retired_count += 1
                continue
            if current_source_ref and current_lane_tip and current_lane_tip != source_commit:
                if _retire_queue_item(
                    cfg,
                    cycle_number=cycle_number,
                    queue_items_by_id=queue_items_by_id,
                    queue_item_id=queue_item_id,
                    retirement_reason_code="superseded_by_newer_lane_tip",
                    message=f"queue item retired because lane '{lane_id}' advanced to newer tip '{current_lane_tip}'",
                    details={"current_lane_tip": current_lane_tip, "current_source_ref": current_source_ref},
                ):
                    retired_count += 1
                continue
    return {"retired_count": int(retired_count)}


def _deterministic_merge_sweep(cfg: RunConfig, *, cycle_number: int, run_base_ref: str) -> dict[str, Any]:
    task_path = cfg.repo_root / ARTIFACT_FILES["task_execution_state"]
    task_payload = _read_json(task_path, default={})
    if not isinstance(task_payload, dict):
        task_payload = {}
    task_rows_raw = task_payload.get("tasks")
    task_rows = [row for row in task_rows_raw if isinstance(row, dict)] if isinstance(task_rows_raw, list) else []
    lane_map, _plan_cycle = _lane_base_watchdog_branch_map(cfg)
    queue_path = cfg.repo_root / ARTIFACT_FILES["merge_queue"]
    queue_items_by_id = {
        str(row.get("queue_item_id") or "").strip(): dict(row)
        for row in _load_queue_items(queue_path)
        if str(row.get("queue_item_id") or "").strip()
    }

    task_merge_attempts = 0
    task_merge_successes = 0
    task_merge_skips = 0
    lane_merge_attempts = 0
    lane_merge_successes = 0
    lane_merge_skips = 0
    lane_merge_deferred = 0
    queue_updates = 0
    queue_resolved = 0
    queue_reconciliation = _reconcile_merge_queue_items(
        cfg,
        cycle_number=cycle_number,
        run_base_ref=run_base_ref,
        task_rows=task_rows,
        lane_map=lane_map,
        queue_items_by_id=queue_items_by_id,
    )
    queue_resolved += int(queue_reconciliation.get("retired_count") or 0)

    for task_row in task_rows:
        if str(task_row.get("status") or "").strip() != "done":
            continue
        task_id = str(task_row.get("task_id") or "").strip()
        lane_id = str(task_row.get("lane_id") or "").strip() or "unscoped"
        head_commit = _task_last_handoff_head_commit(task_row)
        if not head_commit:
            continue
        target_branch = str(lane_map.get(lane_id) or "").strip()
        source_ref = _task_last_handoff_branch(task_row) or None
        task_merge_attempts += 1

        if not target_branch:
            queued = _upsert_merge_queue_item(
                queue_items_by_id,
                cycle_number=cycle_number,
                kind="task_to_lane",
                lane_id=lane_id,
                task_id=task_id,
                target_branch="",
                source_commit=head_commit,
                source_ref=source_ref,
                failure_reason_code="lane_base_branch_missing",
                failure_message=f"no lane-base branch mapping found for lane '{lane_id}'",
            )
            queue_updates += 1
            _append_merge_journal(
                cfg,
                cycle_number=cycle_number,
                event="queued",
                kind="task_to_lane",
                lane_id=lane_id,
                task_id=task_id,
                target_branch="",
                source_commit=head_commit,
                source_ref=source_ref,
                queue_item_id=str(queued.get("queue_item_id") or ""),
                status="queued",
                message=str(queued.get("failure_message") or ""),
                details={"failure_reason_code": str(queued.get("failure_reason_code") or "")},
            )
            continue
        if not _git_branch_exists(cfg.repo_root, target_branch):
            queued = _upsert_merge_queue_item(
                queue_items_by_id,
                cycle_number=cycle_number,
                kind="task_to_lane",
                lane_id=lane_id,
                task_id=task_id,
                target_branch=target_branch,
                source_commit=head_commit,
                source_ref=source_ref,
                failure_reason_code="target_branch_missing",
                failure_message=f"lane-base branch '{target_branch}' does not exist",
            )
            queue_updates += 1
            _append_merge_journal(
                cfg,
                cycle_number=cycle_number,
                event="queued",
                kind="task_to_lane",
                lane_id=lane_id,
                task_id=task_id,
                target_branch=target_branch,
                source_commit=head_commit,
                source_ref=source_ref,
                queue_item_id=str(queued.get("queue_item_id") or ""),
                status="queued",
                message=str(queued.get("failure_message") or ""),
                details={"failure_reason_code": str(queued.get("failure_reason_code") or "")},
            )
            continue
        if not _git_resolve_commit(cfg.repo_root, head_commit):
            queued = _upsert_merge_queue_item(
                queue_items_by_id,
                cycle_number=cycle_number,
                kind="task_to_lane",
                lane_id=lane_id,
                task_id=task_id,
                target_branch=target_branch,
                source_commit=head_commit,
                source_ref=source_ref,
                failure_reason_code="source_commit_missing",
                failure_message=f"done head commit '{head_commit}' is not resolvable locally",
            )
            queue_updates += 1
            _append_merge_journal(
                cfg,
                cycle_number=cycle_number,
                event="queued",
                kind="task_to_lane",
                lane_id=lane_id,
                task_id=task_id,
                target_branch=target_branch,
                source_commit=head_commit,
                source_ref=source_ref,
                queue_item_id=str(queued.get("queue_item_id") or ""),
                status="queued",
                message=str(queued.get("failure_message") or ""),
                details={"failure_reason_code": str(queued.get("failure_reason_code") or "")},
            )
            continue
        if _git_is_ancestor_commit(cfg.repo_root, ancestor=head_commit, descendant=target_branch) is True:
            task_merge_skips += 1
            removed_queue_item_id = _remove_queue_item(queue_items_by_id, "task_to_lane", target_branch, head_commit)
            if removed_queue_item_id:
                queue_resolved += 1
            _append_merge_journal(
                cfg,
                cycle_number=cycle_number,
                event="skip",
                kind="task_to_lane",
                lane_id=lane_id,
                task_id=task_id,
                target_branch=target_branch,
                source_commit=head_commit,
                source_ref=source_ref,
                queue_item_id=removed_queue_item_id,
                status="already_merged",
                message=f"task commit already present in lane-base '{target_branch}'",
            )
            continue

        merge_result = _git_merge_source_into_target(cfg.repo_root, target_branch=target_branch, source_spec=head_commit)
        if bool(merge_result.get("ok")):
            task_merge_successes += 1
            removed_queue_item_id = _remove_queue_item(queue_items_by_id, "task_to_lane", target_branch, head_commit)
            if removed_queue_item_id:
                queue_resolved += 1
            _append_merge_journal(
                cfg,
                cycle_number=cycle_number,
                event="merged",
                kind="task_to_lane",
                lane_id=lane_id,
                task_id=task_id,
                target_branch=target_branch,
                source_commit=head_commit,
                source_ref=source_ref,
                queue_item_id=removed_queue_item_id,
                status="merged",
                message=str(merge_result.get("message") or f"merged task commit into '{target_branch}'"),
                details={"merged_sha": str(merge_result.get("merged_sha") or "")},
            )
            continue

        queued = _upsert_merge_queue_item(
            queue_items_by_id,
            cycle_number=cycle_number,
            kind="task_to_lane",
            lane_id=lane_id,
            task_id=task_id,
            target_branch=target_branch,
            source_commit=head_commit,
            source_ref=source_ref,
            failure_reason_code=str(merge_result.get("reason_code") or "git_merge_failed"),
            failure_message=str(merge_result.get("message") or "git merge failed"),
        )
        queue_updates += 1
        _append_merge_journal(
            cfg,
            cycle_number=cycle_number,
            event="queued",
            kind="task_to_lane",
            lane_id=lane_id,
            task_id=task_id,
            target_branch=target_branch,
            source_commit=head_commit,
            source_ref=source_ref,
            queue_item_id=str(queued.get("queue_item_id") or ""),
            status="queued",
            message=str(queued.get("failure_message") or ""),
            details={
                "failure_reason_code": str(queued.get("failure_reason_code") or ""),
                "conflicted_files": merge_result.get("conflicted_files") if isinstance(merge_result.get("conflicted_files"), list) else [],
            },
        )

    lane_counts = _lane_task_counts(task_rows)
    for lane_id, counts in sorted(lane_counts.items(), key=lambda item: item[0]):
        if not _all_lane_tasks_done(counts):
            continue
        lane_task_queue_items = [
            row
            for row in queue_items_by_id.values()
            if str(row.get("lane_id") or "").strip() == lane_id and str(row.get("kind") or "").strip() == "task_to_lane"
        ]
        if lane_task_queue_items:
            lane_merge_deferred += 1
            _append_merge_journal(
                cfg,
                cycle_number=cycle_number,
                event="deferred",
                kind="lane_to_run",
                lane_id=lane_id,
                task_id=None,
                target_branch=str(run_base_ref or "").strip(),
                source_commit="",
                source_ref=str(lane_map.get(lane_id) or "").strip() or None,
                status="blocked_on_task_fan_in",
                message=f"lane->run merge deferred because lane '{lane_id}' still has active task->lane merge debt",
                details={"active_task_queue_items": len(lane_task_queue_items)},
            )
            continue
        target_branch = str(run_base_ref or "").strip()
        source_ref = str(lane_map.get(lane_id) or "").strip()
        if not source_ref:
            continue
        lane_tip = _git_resolve_commit(cfg.repo_root, source_ref)
        if not lane_tip:
            continue
        lane_merge_attempts += 1
        if _git_is_ancestor_commit(cfg.repo_root, ancestor=lane_tip, descendant=target_branch) is True:
            lane_merge_skips += 1
            removed_queue_item_id = _remove_queue_item(queue_items_by_id, "lane_to_run", target_branch, lane_tip)
            if removed_queue_item_id:
                queue_resolved += 1
            _append_merge_journal(
                cfg,
                cycle_number=cycle_number,
                event="skip",
                kind="lane_to_run",
                lane_id=lane_id,
                task_id=None,
                target_branch=target_branch,
                source_commit=lane_tip,
                source_ref=source_ref,
                queue_item_id=removed_queue_item_id,
                status="already_merged",
                message=f"lane-base '{source_ref}' already present in run-base '{target_branch}'",
            )
            continue

        merge_result = _git_merge_source_into_target(cfg.repo_root, target_branch=target_branch, source_spec=source_ref)
        if bool(merge_result.get("ok")):
            lane_merge_successes += 1
            removed_queue_item_id = _remove_queue_item(queue_items_by_id, "lane_to_run", target_branch, lane_tip)
            if removed_queue_item_id:
                queue_resolved += 1
            _append_merge_journal(
                cfg,
                cycle_number=cycle_number,
                event="merged",
                kind="lane_to_run",
                lane_id=lane_id,
                task_id=None,
                target_branch=target_branch,
                source_commit=lane_tip,
                source_ref=source_ref,
                queue_item_id=removed_queue_item_id,
                status="merged",
                message=str(merge_result.get("message") or f"merged lane-base '{source_ref}' into '{target_branch}'"),
                details={"merged_sha": str(merge_result.get("merged_sha") or "")},
            )
            continue

        queued = _upsert_merge_queue_item(
            queue_items_by_id,
            cycle_number=cycle_number,
            kind="lane_to_run",
            lane_id=lane_id,
            task_id=None,
            target_branch=target_branch,
            source_commit=lane_tip,
            source_ref=source_ref,
            failure_reason_code=str(merge_result.get("reason_code") or "git_merge_failed"),
            failure_message=str(merge_result.get("message") or "git merge failed"),
        )
        queue_updates += 1
        _append_merge_journal(
            cfg,
            cycle_number=cycle_number,
            event="queued",
            kind="lane_to_run",
            lane_id=lane_id,
            task_id=None,
            target_branch=target_branch,
            source_commit=lane_tip,
            source_ref=source_ref,
            queue_item_id=str(queued.get("queue_item_id") or ""),
            status="queued",
            message=str(queued.get("failure_message") or ""),
            details={
                "failure_reason_code": str(queued.get("failure_reason_code") or ""),
                "conflicted_files": merge_result.get("conflicted_files") if isinstance(merge_result.get("conflicted_files"), list) else [],
            },
        )

    queue_items = sorted(
        queue_items_by_id.values(),
        key=lambda row: (
            str(row.get("kind") or ""),
            str(row.get("target_branch") or ""),
            str(row.get("source_commit") or ""),
        ),
    )
    _write_queue_items(queue_path, cycle_number=cycle_number, items=queue_items)
    return {
        "cycle_number": int(cycle_number),
        "task_merge_attempts": int(task_merge_attempts),
        "task_merge_successes": int(task_merge_successes),
        "task_merge_skips": int(task_merge_skips),
        "lane_merge_attempts": int(lane_merge_attempts),
        "lane_merge_successes": int(lane_merge_successes),
        "lane_merge_skips": int(lane_merge_skips),
        "lane_merge_deferred": int(lane_merge_deferred),
        "queue_item_count": len(queue_items),
        "queue_updates": int(queue_updates),
        "queue_resolved": int(queue_resolved),
    }


def _merge_item_has_git_proof(cfg: RunConfig, item: dict[str, Any]) -> bool:
    kind = str(item.get("kind") or "").strip()
    target_branch = str(item.get("target_branch") or "").strip()
    source_commit = str(item.get("source_commit") or "").strip()
    if kind not in {"task_to_lane", "lane_to_run"}:
        return False
    if not target_branch or not source_commit:
        return False
    return _git_is_ancestor_commit(cfg.repo_root, ancestor=source_commit, descendant=target_branch) is True


def _write_merge_manager_runtime_report(
    cfg: RunConfig,
    *,
    cycle_number: int,
    status: str,
    summary: str,
    result: ManagerResult | None = None,
    resolved_items: list[dict[str, Any]] | None = None,
    unresolved_items: list[dict[str, Any]] | None = None,
    queue_count_before: int = 0,
    queue_count_after: int = 0,
) -> dict[str, Any]:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "updated_at": utc_now_iso(),
        "cycle_number": int(cycle_number),
        "status": str(status or "").strip() or "unknown",
        "summary": str(summary or "").strip(),
        "queue_count_before": int(queue_count_before),
        "queue_count_after": int(queue_count_after),
        "resolved_items": resolved_items or [],
        "unresolved_items": unresolved_items or [],
        "manager_status": str((result.status if isinstance(result, ManagerResult) else "") or "").strip(),
        "manager_timeout": bool(result.timeout) if isinstance(result, ManagerResult) else False,
        "manager_message": str((result.message if isinstance(result, ManagerResult) else "") or "").strip(),
        "manager_reason_code": str((result.reason_code if isinstance(result, ManagerResult) else "") or "").strip(),
    }
    _atomic_write_json(cfg.repo_root / ARTIFACT_FILES["merge_manager_report"], payload)
    return payload


def _run_periodic_merge_manager(
    cfg: RunConfig,
    *,
    cycle_number: int,
    run_base_ref: str,
) -> dict[str, Any]:
    queue_path = cfg.repo_root / ARTIFACT_FILES["merge_queue"]
    queue_items = _load_queue_items(queue_path)
    if not queue_items:
        return {
            "ran": False,
            "status": "skipped",
            "reason": "empty_queue",
            "queue_count_before": 0,
            "queue_count_after": 0,
        }
    if int(cycle_number) % int(MERGE_MANAGER_CADENCE_CYCLES) != 0:
        return {
            "ran": False,
            "status": "skipped",
            "reason": "non_cadence_cycle",
            "queue_count_before": len(queue_items),
            "queue_count_after": len(queue_items),
        }

    result = _invoke_manager(
        cfg,
        manager_name="merge-manager",
        cycle_number=cycle_number,
        context={
            "run_base_branch": str(run_base_ref or "").strip(),
            "merge_queue_path": str(queue_path.resolve()),
            "unmergable_merges_path": str((cfg.repo_root / ARTIFACT_FILES["unmergable_merges"]).resolve()),
            "merge_journal_path": str((cfg.repo_root / MERGE_JOURNAL_FILE).resolve()),
            "plan_packets_path": str((cfg.repo_root / ARTIFACT_FILES["plan_packets"]).resolve()),
            "task_execution_state_path": str((cfg.repo_root / ARTIFACT_FILES["task_execution_state"]).resolve()),
            "merge_queue": queue_items,
        },
        expected_artifacts=[],
    )
    queue_count_before = len(queue_items)
    if result.status != "ok":
        report = _write_merge_manager_runtime_report(
            cfg,
            cycle_number=cycle_number,
            status="manager_failed",
            summary=result.message or "merge-manager failed",
            result=result,
            queue_count_before=queue_count_before,
            queue_count_after=queue_count_before,
        )
        return {
            "ran": True,
            "status": "failed",
            "reason": str(result.reason_code or "manager_failed"),
            "result": result,
            "report": report,
            "queue_count_before": queue_count_before,
            "queue_count_after": queue_count_before,
        }

    report_path = cfg.repo_root / ARTIFACT_FILES["merge_manager_report"]
    report_payload = _read_json(report_path, default={})
    if not isinstance(report_payload, dict):
        report_payload = {}
    resolved_rows = report_payload.get("resolved_items")
    unresolved_rows = report_payload.get("unresolved_items")
    resolved_items = [row for row in resolved_rows if isinstance(row, dict)] if isinstance(resolved_rows, list) else []
    unresolved_items = [row for row in unresolved_rows if isinstance(row, dict)] if isinstance(unresolved_rows, list) else []
    expected_ids = {
        str(row.get("queue_item_id") or "").strip()
        for row in queue_items
        if str(row.get("queue_item_id") or "").strip()
    }
    resolved_ids = {
        str(row.get("queue_item_id") or "").strip()
        for row in resolved_items
        if str(row.get("queue_item_id") or "").strip()
    }
    unresolved_ids = {
        str(row.get("queue_item_id") or "").strip()
        for row in unresolved_items
        if str(row.get("queue_item_id") or "").strip()
    }
    accounted_ids = resolved_ids | unresolved_ids
    valid_report = (
        int(report_payload.get("cycle_number") or 0) == int(cycle_number)
        and bool(expected_ids)
        and resolved_ids.isdisjoint(unresolved_ids)
        and accounted_ids == expected_ids
    )
    if not valid_report:
        report = _write_merge_manager_runtime_report(
            cfg,
            cycle_number=cycle_number,
            status="invalid_report",
            summary="merge-manager completed without a valid queue consumption report",
            result=result,
            queue_count_before=queue_count_before,
            queue_count_after=queue_count_before,
        )
        return {
            "ran": True,
            "status": "invalid_report",
            "reason": "merge_manager_invalid_report",
            "result": result,
            "report": report,
            "queue_count_before": queue_count_before,
            "queue_count_after": queue_count_before,
        }

    queue_by_id = {str(row.get("queue_item_id") or "").strip(): row for row in queue_items}
    unmergable_path = cfg.repo_root / ARTIFACT_FILES["unmergable_merges"]
    unmergable_items = _load_queue_items(unmergable_path)
    report_ref = str(report_path.resolve())
    normalized_resolved: list[dict[str, Any]] = []
    normalized_unresolved: list[dict[str, Any]] = []
    timestamp = utc_now_iso()

    for resolved_row in resolved_items:
        queue_item_id = str(resolved_row.get("queue_item_id") or "").strip()
        queue_item = queue_by_id.get(queue_item_id)
        if not isinstance(queue_item, dict):
            continue
        if _merge_item_has_git_proof(cfg, queue_item):
            normalized_resolved.append(
                {
                    "queue_item_id": queue_item_id,
                    "kind": str(queue_item.get("kind") or "").strip(),
                    "target_branch": str(queue_item.get("target_branch") or "").strip(),
                    "source_commit": str(queue_item.get("source_commit") or "").strip(),
                    "resolution_summary": str(resolved_row.get("resolution_summary") or "").strip(),
                }
            )
            _append_merge_journal(
                cfg,
                cycle_number=cycle_number,
                event="manager_resolved",
                kind=str(queue_item.get("kind") or "").strip(),
                lane_id=str(queue_item.get("lane_id") or "").strip(),
                task_id=str(queue_item.get("task_id") or "").strip() or None,
                target_branch=str(queue_item.get("target_branch") or "").strip(),
                source_commit=str(queue_item.get("source_commit") or "").strip(),
                source_ref=str(queue_item.get("source_ref") or "").strip() or None,
                queue_item_id=queue_item_id,
                status="resolved",
                message=str(resolved_row.get("resolution_summary") or "merge-manager resolved queued merge"),
            )
            continue
        moved_row = dict(queue_item)
        moved_row["moved_at"] = timestamp
        moved_row["moved_cycle"] = int(cycle_number)
        moved_row["last_manager_reason"] = "manager_marked_resolved_without_git_proof"
        moved_row["manager_report_ref"] = report_ref
        unmergable_items.append(moved_row)
        normalized_unresolved.append({"queue_item_id": queue_item_id, "last_manager_reason": moved_row["last_manager_reason"]})
        _append_merge_journal(
            cfg,
            cycle_number=cycle_number,
            event="manager_unresolved",
            kind=str(queue_item.get("kind") or "").strip(),
            lane_id=str(queue_item.get("lane_id") or "").strip(),
            task_id=str(queue_item.get("task_id") or "").strip() or None,
            target_branch=str(queue_item.get("target_branch") or "").strip(),
            source_commit=str(queue_item.get("source_commit") or "").strip(),
            source_ref=str(queue_item.get("source_ref") or "").strip() or None,
            queue_item_id=queue_item_id,
            status="unmergable",
            message="merge-manager marked item resolved but git proof was missing; moved to unmergable",
        )

    for unresolved_row in unresolved_items:
        queue_item_id = str(unresolved_row.get("queue_item_id") or "").strip()
        queue_item = queue_by_id.get(queue_item_id)
        if not isinstance(queue_item, dict):
            continue
        moved_row = dict(queue_item)
        moved_row["moved_at"] = timestamp
        moved_row["moved_cycle"] = int(cycle_number)
        moved_row["last_manager_reason"] = str(unresolved_row.get("last_manager_reason") or "").strip() or "merge_manager_unresolved"
        moved_row["manager_report_ref"] = report_ref
        unmergable_items.append(moved_row)
        normalized_unresolved.append({"queue_item_id": queue_item_id, "last_manager_reason": moved_row["last_manager_reason"]})
        _append_merge_journal(
            cfg,
            cycle_number=cycle_number,
            event="manager_unresolved",
            kind=str(queue_item.get("kind") or "").strip(),
            lane_id=str(queue_item.get("lane_id") or "").strip(),
            task_id=str(queue_item.get("task_id") or "").strip() or None,
            target_branch=str(queue_item.get("target_branch") or "").strip(),
            source_commit=str(queue_item.get("source_commit") or "").strip(),
            source_ref=str(queue_item.get("source_ref") or "").strip() or None,
            queue_item_id=queue_item_id,
            status="unmergable",
            message=moved_row["last_manager_reason"],
        )

    _write_queue_items(queue_path, cycle_number=cycle_number, items=[])
    _write_queue_items(unmergable_path, cycle_number=cycle_number, items=unmergable_items)
    report = _write_merge_manager_runtime_report(
        cfg,
        cycle_number=cycle_number,
        status="consumed",
        summary="merge-manager consumed active merge queue",
        result=result,
        resolved_items=normalized_resolved,
        unresolved_items=normalized_unresolved,
        queue_count_before=queue_count_before,
        queue_count_after=0,
    )
    return {
        "ran": True,
        "status": "consumed",
        "reason": "merge_manager_consumed_queue",
        "result": result,
        "report": report,
        "queue_count_before": queue_count_before,
        "queue_count_after": 0,
    }


def _build_mergeability_report(cfg: RunConfig, *, cycle_number: int, cycle_mode: str) -> dict[str, Any]:
    task_path = cfg.repo_root / ARTIFACT_FILES["task_execution_state"]
    task_payload = _read_json(task_path, default={})
    tasks = task_payload.get("tasks") if isinstance(task_payload, dict) else None
    task_rows = [row for row in tasks if isinstance(row, dict)] if isinstance(tasks, list) else []
    lane_counts = _lane_task_counts(task_rows)
    lane_map, _plan_cycle = _lane_base_watchdog_branch_map(cfg)
    queue_items = _load_queue_items(cfg.repo_root / ARTIFACT_FILES["merge_queue"])
    run_base_ref = _mergeability_run_base_ref(cfg)
    run_base_sha = _git_text(cfg.repo_root, "rev-parse", run_base_ref) or _git_text(cfg.repo_root, "rev-parse", "HEAD")

    lane_sha_sets: dict[str, set[str]] = {}
    for queue_row in queue_items:
        lane_id = str(queue_row.get("lane_id") or "").strip() or "unscoped"
        source_commit = str(queue_row.get("source_commit") or "").strip()
        if source_commit:
            lane_sha_sets.setdefault(lane_id, set()).add(source_commit)

    lane_ids = set(lane_counts.keys()) | set(lane_map.keys()) | set(lane_sha_sets.keys())
    lane_status: dict[str, dict[str, Any]] = {}
    merge_blockers: list[dict[str, Any]] = []
    progression = {
        "task_to_lane_queue_items": 0,
        "lane_to_run_queue_items": 0,
        "lane_ready_for_run_merge": 0,
    }

    for lane_id in sorted(lane_ids):
        counts = lane_counts.get(lane_id, {"pending": 0, "in_progress": 0, "done": 0, "blocked": 0})
        done_count = int(counts.get("done") or 0)
        pending_count = int(counts.get("pending") or 0)
        in_progress_count = int(counts.get("in_progress") or 0)
        blocked_count = int(counts.get("blocked") or 0)
        lane_queue_items = [row for row in queue_items if str(row.get("lane_id") or "").strip() == lane_id]
        task_queue_items = [row for row in lane_queue_items if str(row.get("kind") or "").strip() == "task_to_lane"]
        lane_to_run_queue_items = [row for row in lane_queue_items if str(row.get("kind") or "").strip() == "lane_to_run"]
        progression["task_to_lane_queue_items"] += len(task_queue_items)
        progression["lane_to_run_queue_items"] += len(lane_to_run_queue_items)

        lane_base_branch = str(lane_map.get(lane_id) or "").strip()
        lane_base_sha = _git_resolve_commit(cfg.repo_root, lane_base_branch) if lane_base_branch else ""

        if blocked_count > 0:
            tester_gate_status = "blocked_tasks_present"
            lane_to_run_merge_status = "blocked"
            merge_blockers.append(
                {
                    "lane_id": lane_id,
                    "reason_code": "lane_blocked_tasks",
                    "owner": "runtime",
                    "message": f"lane has blocked tasks={blocked_count}",
                }
            )
        elif pending_count > 0 or in_progress_count > 0:
            tester_gate_status = "pending_lane_completion"
            lane_to_run_merge_status = "waiting_for_lane_completion"
            merge_blockers.append(
                {
                    "lane_id": lane_id,
                    "reason_code": "lane_pending_tasks",
                    "owner": "runtime",
                    "message": f"lane has unfinished tasks (pending={pending_count}, in_progress={in_progress_count})",
                }
            )
        elif task_queue_items:
            tester_gate_status = "pending_task_fan_in"
            lane_to_run_merge_status = "blocked_on_task_fan_in"
            merge_blockers.append(
                {
                    "lane_id": lane_id,
                    "reason_code": "lane_task_merge_debt",
                    "owner": "runtime",
                    "message": f"lane has {len(task_queue_items)} active task->lane merge debt item(s)",
                }
            )
        elif lane_to_run_queue_items:
            tester_gate_status = "pass"
            lane_to_run_merge_status = "queued"
            merge_blockers.append(
                {
                    "lane_id": lane_id,
                    "reason_code": "lane_to_run_merge_queued",
                    "owner": "merge-manager",
                    "message": f"lane has {len(lane_to_run_queue_items)} queued lane->run merge failure(s)",
                }
            )
        elif lane_base_sha and run_base_sha and _git_is_ancestor_commit(cfg.repo_root, ancestor=lane_base_sha, descendant=run_base_sha) is True:
            tester_gate_status = "pass"
            lane_to_run_merge_status = "merged"
        elif _all_lane_tasks_done(counts):
            tester_gate_status = "pass"
            lane_to_run_merge_status = "ready"
            progression["lane_ready_for_run_merge"] += 1
        elif done_count > 0:
            tester_gate_status = "pending_lane_completion"
            lane_to_run_merge_status = "waiting_for_lane_completion"
        else:
            tester_gate_status = "not_required"
            lane_to_run_merge_status = "idle"

        fan_in_status = "queued" if task_queue_items else ("ready" if done_count > 0 else "idle")
        lane_status[lane_id] = {
            "task_counts": {
                "pending": pending_count,
                "in_progress": in_progress_count,
                "done": done_count,
                "blocked": blocked_count,
            },
            "fan_in_status": fan_in_status,
            "tester_gate_status": tester_gate_status,
            "lane_to_run_merge_status": lane_to_run_merge_status,
            "lane_merge_gate_pending": False,
            "lane_unmerged_commit_count": len(task_queue_items) + len(lane_to_run_queue_items),
        }

    lane_shas = {lane_id: sorted(values) for lane_id, values in sorted(lane_sha_sets.items(), key=lambda item: item[0])}
    unmerged_commit_count = sum(len(values) for values in lane_shas.values())
    report_payload = {
        "schema_version": SCHEMA_VERSION,
        "updated_at": utc_now_iso(),
        "cycle_number": int(cycle_number),
        "cycle_mode": str(cycle_mode or "").strip() or "normal",
        "run_base_ref": run_base_ref,
        "run_base_sha": run_base_sha,
        "lane_shas": lane_shas,
        "unmerged_commit_count": int(unmerged_commit_count),
        "merge_blockers": merge_blockers,
        "gate_owner": "runtime" if merge_blockers else "none",
        "lane_status": lane_status,
        "lane_merge_gate_pending_cleared_count": 0,
        "progression": progression,
    }
    report_payload["progress_fingerprint"] = _mergeability_progress_fingerprint(report_payload)
    previous_payload = _read_json(cfg.repo_root / ARTIFACT_FILES["mergeability_report"], default={})
    previous_fingerprint = (
        str(previous_payload.get("progress_fingerprint") or "").strip()
        if isinstance(previous_payload, dict)
        else ""
    )
    report_payload["mergeability_advanced"] = bool(
        previous_fingerprint and report_payload["progress_fingerprint"] != previous_fingerprint
    )
    _atomic_write_json(cfg.repo_root / ARTIFACT_FILES["mergeability_report"], report_payload)
    return report_payload


def _run_merge_progression_engine(
    cfg: RunConfig,
    *,
    cycle_number: int,
    cycle_mode: str,
    mergeability_report: dict[str, Any] | None,
) -> dict[str, Any]:
    report_payload = mergeability_report if isinstance(mergeability_report, dict) else {}
    queue_items = _load_queue_items(cfg.repo_root / ARTIFACT_FILES["merge_queue"])
    lane_queue_count = sum(1 for row in queue_items if str(row.get("kind") or "").strip() == "lane_to_run")
    task_queue_count = sum(1 for row in queue_items if str(row.get("kind") or "").strip() == "task_to_lane")
    return {
        "cycle_number": int(cycle_number),
        "state_changed": bool(report_payload.get("mergeability_advanced")),
        "fan_in_accept_count": 0,
        "lane_merge_ready_count": int((report_payload.get("progression") or {}).get("lane_ready_for_run_merge") or 0),
        "lane_merge_completed_count": 0,
        "lane_merge_blocked_count": int(lane_queue_count),
        "workers_released_count": 0,
        "blockers_opened_count": int(task_queue_count + lane_queue_count),
        "blockers_resolved_count": 0,
    }


def _restart_checkpoint_fingerprint(cfg: RunConfig) -> str:
    snapshot = {
        "cycle_counter": _read_json(cfg.repo_root / CYCLE_COUNTER_FILE, default={}),
        "task_execution_state": _read_json(cfg.repo_root / ARTIFACT_FILES["task_execution_state"], default={}),
        "worker_registry": _read_json(cfg.repo_root / ARTIFACT_FILES["worker_registry"], default={}),
        "dispatch_registry": _read_json(cfg.repo_root / ARTIFACT_FILES["dispatch_registry"], default={}),
        "watchdog_state": _read_json(cfg.repo_root / ARTIFACT_FILES["watchdog_state"], default={}),
        "watchdog_exit_signal": _read_json(cfg.repo_root / ARTIFACT_FILES["watchdog_exit_signal"], default={}),
    }
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _determine_restart_scenario(
    cfg: RunConfig,
    *,
    resume_mode: bool,
    prior_run_lock: dict[str, Any] | None = None,
) -> str:
    if not resume_mode:
        return "fresh_start"
    watchdog_signal = _read_json(cfg.repo_root / ARTIFACT_FILES["watchdog_exit_signal"], default={})
    if isinstance(watchdog_signal, dict) and str(watchdog_signal.get("reason_code") or "").strip():
        return "watchdog_resume"
    lock_payload = prior_run_lock if isinstance(prior_run_lock, dict) else _read_json(cfg.repo_root / RUN_LOCK_FILE, default={})
    stale_pid = _coerce_pid(lock_payload.get("pid")) if isinstance(lock_payload, dict) else None
    if stale_pid is not None and not _is_pid_running(stale_pid):
        return "process_kill_resume"
    return "checkpoint_replay"


def _apply_restart_determinism_hooks(
    cfg: RunConfig,
    *,
    cycle_number: int,
    resume_mode: bool,
    prior_run_lock: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = _read_json(cfg.repo_root / ARTIFACT_FILES["restart_determinism_state"], default={})
    if not isinstance(state, dict):
        state = {}
    previous_fingerprint = str(state.get("checkpoint_fingerprint") or "").strip()
    scenario = _determine_restart_scenario(cfg, resume_mode=resume_mode, prior_run_lock=prior_run_lock)
    checkpoint_fingerprint = _restart_checkpoint_fingerprint(cfg)
    idempotent_continuation = bool(
        previous_fingerprint
        and previous_fingerprint == checkpoint_fingerprint
        and str(state.get("scenario") or "").strip() == scenario
    )
    now_iso = utc_now_iso()
    invariants = state.get("invariants")
    if not isinstance(invariants, dict):
        invariants = {
            "watchdog_resume": {"enabled": True, "last_verified": None},
            "process_kill_resume": {"enabled": True, "last_verified": None},
            "checkpoint_replay": {"enabled": True, "last_verified": None},
        }
    scenario_key = scenario if scenario in {"watchdog_resume", "process_kill_resume", "checkpoint_replay"} else "checkpoint_replay"
    scenario_row = invariants.get(scenario_key) if isinstance(invariants.get(scenario_key), dict) else {"enabled": True}
    scenario_row["enabled"] = True
    scenario_row["last_verified"] = now_iso
    invariants[scenario_key] = scenario_row

    continuation_log = state.get("continuation_log") if isinstance(state.get("continuation_log"), list) else []
    prior_lock_pid = _coerce_pid((prior_run_lock or {}).get("pid")) if isinstance(prior_run_lock, dict) else None
    continuation_log.append(
        {
            "cycle_number": int(cycle_number),
            "timestamp": now_iso,
            "scenario": scenario,
            "resume_mode": bool(resume_mode),
            "checkpoint_fingerprint": checkpoint_fingerprint,
            "idempotent_continuation": idempotent_continuation,
            "prior_run_lock_pid": prior_lock_pid,
            "prior_run_lock_present": isinstance(prior_run_lock, dict) and bool(prior_run_lock),
        }
    )
    continuation_log = continuation_log[-20:]

    out = {
        "schema_version": SCHEMA_VERSION,
        "updated_at": now_iso,
        "scenario": scenario,
        "resume_mode": bool(resume_mode),
        "checkpoint_fingerprint": checkpoint_fingerprint,
        "last_applied_cycle": int(cycle_number),
        "idempotent_continuation": idempotent_continuation,
        "invariants": invariants,
        "continuation_log": continuation_log,
    }
    _atomic_write_json(cfg.repo_root / ARTIFACT_FILES["restart_determinism_state"], out)
    return out


def _update_restart_determinism_checkpoint(
    cfg: RunConfig,
    *,
    cycle_number: int,
    cycle_mode: str,
    stop_reason: str | None,
) -> dict[str, Any]:
    state = _read_json(cfg.repo_root / ARTIFACT_FILES["restart_determinism_state"], default={})
    if not isinstance(state, dict):
        state = {}
    checkpoint_fingerprint = _restart_checkpoint_fingerprint(cfg)
    continuation_log = state.get("continuation_log") if isinstance(state.get("continuation_log"), list) else []
    continuation_log.append(
        {
            "cycle_number": int(cycle_number),
            "timestamp": utc_now_iso(),
            "event": "cycle_checkpoint_update",
            "cycle_mode": str(cycle_mode or "").strip() or "normal",
            "stop_reason": str(stop_reason or "").strip(),
            "checkpoint_fingerprint": checkpoint_fingerprint,
        }
    )
    continuation_log = continuation_log[-20:]
    state["schema_version"] = SCHEMA_VERSION
    state["updated_at"] = utc_now_iso()
    state["checkpoint_fingerprint"] = checkpoint_fingerprint
    state["last_applied_cycle"] = int(cycle_number)
    state["continuation_log"] = continuation_log
    _atomic_write_json(cfg.repo_root / ARTIFACT_FILES["restart_determinism_state"], state)
    return state


def _packet4_gate_closure_scaffold_model(*, generated_at_utc: str, repo: str = "earth-root") -> dict[str, Any]:
    return {
        "generated_at_utc": generated_at_utc,
        "phase": "Phase 2",
        "packet": "Packet 4",
        "repo": repo,
        "status": "warn",
        "inputs": {
            "baseline_refs": [],
            "after_refs": [],
            "delta_refs": [],
            "canary_refs": ["Tetris"],
        },
        "metrics": {
            "non_actionable_cycle_ratio": None,
            "redispatch_loop_ratio": None,
            "throughput": {"per_cycle": None, "per_hour": None},
            "retry_quality_outcomes": {
                "launch_efficiency": None,
                "failed_or_unknown_ratio": None,
            },
            "restart_recovery_consistency": None,
        },
        "recommendation": {
            "decision": "hold",
            "rationale": "scaffold only; supervised canary evidence pending",
            "blockers": [],
        },
        "artifacts": [],
        "notes": [
            "Packet 4 scaffold generated by runtime internals only.",
            "Do not treat this scaffold as gate-ready evidence until supervised run artifacts are attached.",
        ],
    }


def _packet4_report_root() -> Path:
    return Path("/Users/slobodan/projects/Earth/reports/phase2")


def _packet4_gate_closure_paths(*, date_text: str) -> dict[str, Path]:
    report_root = _packet4_report_root()
    base = f"packet4_gate_evidence_bundle_{date_text}"
    return {
        "json": report_root / f"{base}.json",
        "md": report_root / f"{base}.md",
    }


def _write_packet4_gate_closure_scaffold(
    *,
    date_text: str,
    generated_at_utc: str | None = None,
    repo: str = "earth-root",
) -> dict[str, str]:
    now_iso = str(generated_at_utc or utc_now_iso())
    model = _packet4_gate_closure_scaffold_model(generated_at_utc=now_iso, repo=repo)
    paths = _packet4_gate_closure_paths(date_text=date_text)
    paths["json"].parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(paths["json"], model)
    md_lines = [
        "# Packet 4 Gate Evidence Bundle (Scaffold)",
        "",
        f"- Generated at: `{now_iso}`",
        f"- Phase: `{model['phase']}`",
        f"- Packet: `{model['packet']}`",
        f"- Repo: `{model['repo']}`",
        f"- Status: `{model['status']}`",
        "",
        "## Recommendation",
        f"- Decision: `{model['recommendation']['decision']}`",
        f"- Rationale: {model['recommendation']['rationale']}",
        "",
        "## Notes",
    ]
    for note in model.get("notes", []):
        md_lines.append(f"- {note}")
    paths["md"].write_text("\n".join(md_lines).rstrip() + "\n", encoding="utf-8")
    return {"json": str(paths["json"]), "md": str(paths["md"])}


def _packet4_kpi_trend_scaffold_model(*, generated_at_utc: str, repo: str = "earth-root") -> dict[str, Any]:
    return {
        "generated_at_utc": generated_at_utc,
        "phase": "Phase 2",
        "packet": "Packet 4",
        "repo": repo,
        "status": "warn",
        "inputs": {
            "before_refs": [],
            "after_refs": [],
            "delta_refs": [],
            "canary_refs": ["Tetris"],
        },
        "metrics": {
            "non_actionable_cycle_ratio": {"before": None, "after": None, "delta": None},
            "redispatch_loop_ratio": {"before": None, "after": None, "delta": None},
            "throughput": {
                "per_cycle": {"before": None, "after": None, "delta": None},
                "per_hour": {"before": None, "after": None, "delta": None},
            },
            "retry_quality_outcomes": {
                "launch_efficiency": {"before": None, "after": None, "delta": None},
                "failed_or_unknown_ratio": {"before": None, "after": None, "delta": None},
            },
            "restart_recovery_consistency": {"before": None, "after": None, "delta": None},
        },
        "notes": [
            "Packet 4 KPI trend scaffold generated by runtime internals only.",
            "Populate before/after/delta refs after supervised canary execution.",
        ],
    }


def _packet4_kpi_trend_paths(*, date_text: str) -> dict[str, Path]:
    report_root = _packet4_report_root()
    base = f"packet4_kpi_trend_summary_{date_text}"
    return {
        "json": report_root / f"{base}.json",
        "md": report_root / f"{base}.md",
    }


def _write_packet4_kpi_trend_scaffold(
    *,
    date_text: str,
    generated_at_utc: str | None = None,
    repo: str = "earth-root",
) -> dict[str, str]:
    now_iso = str(generated_at_utc or utc_now_iso())
    model = _packet4_kpi_trend_scaffold_model(generated_at_utc=now_iso, repo=repo)
    paths = _packet4_kpi_trend_paths(date_text=date_text)
    paths["json"].parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(paths["json"], model)
    md_lines = [
        "# Packet 4 KPI Trend Summary (Scaffold)",
        "",
        f"- Generated at: `{now_iso}`",
        f"- Phase: `{model['phase']}`",
        f"- Packet: `{model['packet']}`",
        f"- Repo: `{model['repo']}`",
        f"- Status: `{model['status']}`",
        "",
        "## Comparator Keys",
        "- non_actionable_cycle_ratio",
        "- redispatch_loop_ratio",
        "- throughput.per_cycle",
        "- throughput.per_hour",
        "- retry_quality_outcomes.launch_efficiency",
        "- retry_quality_outcomes.failed_or_unknown_ratio",
        "- restart_recovery_consistency",
        "",
        "## Notes",
    ]
    for note in model.get("notes", []):
        md_lines.append(f"- {note}")
    paths["md"].write_text("\n".join(md_lines).rstrip() + "\n", encoding="utf-8")
    return {"json": str(paths["json"]), "md": str(paths["md"])}


def _packet4_gate_recommendation_path(*, date_text: str) -> Path:
    return _packet4_report_root() / f"packet4_gate_recommendation_{date_text}.md"


def _write_packet4_gate_recommendation_scaffold(
    *,
    date_text: str,
    generated_at_utc: str | None = None,
    repo: str = "earth-root",
) -> str:
    now_iso = str(generated_at_utc or utc_now_iso())
    path = _packet4_gate_recommendation_path(date_text=date_text)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Packet 4 Gate Recommendation (Scaffold)",
        "",
        f"- Generated at: `{now_iso}`",
        f"- Phase: `Phase 2`",
        f"- Packet: `Packet 4`",
        f"- Repo: `{repo}`",
        "- Decision: `hold`",
        "- Rationale: Supervised canary evidence is pending; defer gate close/hold finalization.",
        "",
        "## Required Inputs Before Final Recommendation",
        "- packet2_kpis_after_<repo>_<YYYY-MM-DD>.json/.md",
        "- packet2_kpi_delta_<repo>_<YYYY-MM-DD>.json/.md",
        "- packet3 recovery determinism evidence artifacts",
        "- Tetris canary evidence links",
        "",
        "## Blockers (Owner + Due Date)",
        "- owner: OP runtime path",
        "- due_date: pending supervised run batch",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def _render_cycle_summary(
    cfg: RunConfig,
    cycle_number: int,
    manager_statuses: dict[str, dict[str, str]],
    dispatch_counts: dict[str, int],
    *,
    cycle_mode: str = "normal",
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
    timeout_state = _load_timeout_adaptation_state(cfg)
    timeout_summary = {
        "consecutive_boss_timeouts": int(timeout_state.get("consecutive_boss_timeouts") or 0),
        "timeout_threshold": int(timeout_state.get("timeout_threshold") or 2),
        "adaptation_active": bool(timeout_state.get("adaptation_active")),
        "rotation_required_next_cycle": bool(timeout_state.get("rotation_required")),
        "last_timeout_cycle": timeout_state.get("last_timeout_cycle"),
        "last_timeout_profile_alias": str(timeout_state.get("last_timeout_profile_alias") or "").strip(),
        "last_timeout_reason": str(timeout_state.get("last_timeout_reason") or "").strip(),
    }
    profile_rotation_evidence = (
        timeout_state.get("last_rotation_decision")
        if isinstance(timeout_state.get("last_rotation_decision"), dict)
        else {}
    )
    runtime_check_evidence = (
        timeout_state.get("last_boss_runtime_checks")
        if isinstance(timeout_state.get("last_boss_runtime_checks"), dict)
        else {}
    )

    out = {
        "schema_version": SCHEMA_VERSION,
        "cycle_number": cycle_number,
        "cycle_mode": str(cycle_mode or "").strip() or str(summary.get("cycle_mode") or "").strip() or "normal",
        "manager_statuses": manager_statuses,
        "task_counts": merged_counts,
        "dispatch_counts": _normalized_dispatch_counts(dispatch_counts),
        "project_done": bool(summary.get("project_done")),
        "insurmountable_blocker": bool(summary.get("insurmountable_blocker")),
        "termination": summary.get("termination") if isinstance(summary.get("termination"), dict) else {},
        "stop_reason": str(summary.get("stop_reason") or ""),
        "notes": str(summary.get("notes") or ""),
        "timeout_state": timeout_summary,
        "profile_rotation_evidence": profile_rotation_evidence,
        "boss_runtime_context_evidence": runtime_check_evidence,
    }

    _atomic_write_json(summary_path, out)

    if _is_boss_failed_cycle(manager_statuses):
        print(
            "[op-simple-build] "
            f"[{utc_now_iso()}] "
            f"cycle={cycle_number} summary=boss_failed "
            f"message={_boss_failed_note(manager_statuses, out.get('notes') or '')}",
            flush=True,
        )
    else:
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
            if normalized_reason in TERMINAL_STOP_REASONS:
                return normalized_reason
    stop_reason = summary.get("stop_reason")
    if isinstance(stop_reason, str) and stop_reason.strip():
        normalized_stop_reason = stop_reason.strip()
        if normalized_stop_reason in TERMINAL_STOP_REASONS:
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
    worktrees_parent_raw = getattr(req, "worktrees_parent", None)
    if isinstance(worktrees_parent_raw, str) and worktrees_parent_raw.strip():
        worktrees_parent = Path(worktrees_parent_raw).expanduser().resolve()
    elif isinstance(worktrees_parent_raw, Path):
        worktrees_parent = worktrees_parent_raw.expanduser().resolve()
    else:
        worktrees_parent = DEFAULT_WORKTREES_PARENT
    command = str(getattr(req, "command", "") or "").strip().lower()
    resume_mode = command == "op-resume"
    run_base_source_branch = str(getattr(req, "run_base_source_branch", "") or "").strip() or "main"
    boss_model = str(getattr(req, "boss_model", "") or "").strip() or "gpt-5.3-codex"
    boss_reasoning_effort = str(getattr(req, "boss_reasoning_effort", "") or "").strip() or "xhigh"
    codex_profile = str(getattr(req, "codex_profile", getattr(req, "profile", "")) or "").strip() or None
    executor_provider = _normalize_executor_provider(getattr(req, "executor_provider", "codex"))
    selected_aliases = _normalize_selected_aliases(getattr(req, "selected_aliases", None))
    if (
        selected_aliases is None
        and codex_profile is None
        and _executor_uses_codex_backend(executor_provider)
    ):
        selected_aliases = _default_selected_aliases_from_disk()
    executor_model = str(getattr(req, "executor_model", "") or "").strip() or None
    blackbox_lane = _normalize_blackbox_lane(getattr(req, "blackbox_lane", "free"))
    allow_worker_executor_override = bool(getattr(req, "allow_worker_executor_override", False))
    ground_sync_enabled_raw = getattr(req, "ground_sync_enabled", True)
    if isinstance(ground_sync_enabled_raw, str):
        ground_sync_enabled = ground_sync_enabled_raw.strip().lower() in {"1", "true", "yes", "on"}
    else:
        ground_sync_enabled = bool(ground_sync_enabled_raw)
    ground_sync_every_n_cycles = getattr(req, "ground_sync_every_n_cycles", GROUND_SYNC_DEFAULT_EVERY_N_CYCLES)
    try:
        ground_sync_every_n_cycles = int(ground_sync_every_n_cycles)
    except (TypeError, ValueError):
        ground_sync_every_n_cycles = GROUND_SYNC_DEFAULT_EVERY_N_CYCLES
    if ground_sync_every_n_cycles <= 0:
        ground_sync_every_n_cycles = GROUND_SYNC_DEFAULT_EVERY_N_CYCLES
    ground_sync_timeout_seconds = getattr(req, "ground_sync_timeout_seconds", GROUND_SYNC_DEFAULT_TIMEOUT_SECONDS)
    try:
        ground_sync_timeout_seconds = int(ground_sync_timeout_seconds)
    except (TypeError, ValueError):
        ground_sync_timeout_seconds = GROUND_SYNC_DEFAULT_TIMEOUT_SECONDS
    if ground_sync_timeout_seconds < 30:
        ground_sync_timeout_seconds = 30
    cycle_release_mode = _normalize_cycle_release_mode(
        getattr(req, "cycle_release_mode", DEFAULT_CYCLE_RELEASE_MODE)
    )
    cycle_release_timeout_seconds = getattr(
        req, "cycle_release_timeout_seconds", DEFAULT_CYCLE_RELEASE_TIMEOUT_SECONDS
    )
    try:
        cycle_release_timeout_seconds = int(cycle_release_timeout_seconds)
    except (TypeError, ValueError):
        cycle_release_timeout_seconds = DEFAULT_CYCLE_RELEASE_TIMEOUT_SECONDS
    if cycle_release_timeout_seconds <= 0:
        cycle_release_timeout_seconds = DEFAULT_CYCLE_RELEASE_TIMEOUT_SECONDS
    cycle_release_poll_seconds = getattr(req, "cycle_release_poll_seconds", DEFAULT_CYCLE_RELEASE_POLL_SECONDS)
    try:
        cycle_release_poll_seconds = int(cycle_release_poll_seconds)
    except (TypeError, ValueError):
        cycle_release_poll_seconds = DEFAULT_CYCLE_RELEASE_POLL_SECONDS
    if cycle_release_poll_seconds <= 0:
        cycle_release_poll_seconds = DEFAULT_CYCLE_RELEASE_POLL_SECONDS

    return RunConfig(
        repo_root=repo_root,
        sleep_minutes=0.0,
        max_build_cycles=max_cycles,
        max_parallel_workers=max_parallel_workers,
        dry_run=bool(getattr(req, "dry_run", False)),
        worktrees_parent=worktrees_parent,
        resume_mode=resume_mode,
        run_base_source_branch=run_base_source_branch,
        boss_model=boss_model,
        boss_reasoning_effort=boss_reasoning_effort,
        codex_profile=codex_profile,
        selected_aliases=selected_aliases,
        executor_provider=executor_provider,
        executor_model=executor_model,
        blackbox_lane=blackbox_lane,
        allow_worker_executor_override=allow_worker_executor_override,
        ground_sync_enabled=ground_sync_enabled,
        ground_sync_every_n_cycles=ground_sync_every_n_cycles,
        ground_sync_timeout_seconds=ground_sync_timeout_seconds,
        cycle_release_mode=cycle_release_mode,
        cycle_release_timeout_seconds=cycle_release_timeout_seconds,
        cycle_release_poll_seconds=cycle_release_poll_seconds,
    )


def run_op_simple_build(req: Any) -> dict[str, Any]:
    cfg = _build_config(req)
    warnings: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    preexisting_run_lock = _read_json(cfg.repo_root / RUN_LOCK_FILE, default={})
    if not isinstance(preexisting_run_lock, dict):
        preexisting_run_lock = {}
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
        if _llm_profile_mode_enabled(cfg):
            _refresh_profile_snapshot_via_llm_profile_registry(cfg, cycle_number=0)
        else:
            _atomic_write_json(
                cfg.repo_root / ARTIFACT_FILES["llm_profile_mode"],
                {
                    "schema_version": SCHEMA_VERSION,
                    "updated_at": utc_now_iso(),
                    "enabled": False,
                    "llm_profile": None,
                    "profile_policy": "force_default_codex",
                    "rate_policy": None,
                },
            )
        bootstrap_ok, bootstrap_message = _bootstrap_profile_snapshot_before_first_boss(cfg, cycle_number=0)
        if bootstrap_ok:
            print(
                "[op-simple-build] "
                f"[{utc_now_iso()}] "
                f"cycle=0 profile-snapshot-bootstrap status=ok message={bootstrap_message}",
                flush=True,
            )
        else:
            warnings.append(
                {
                    "code": "profile_snapshot_bootstrap_failed",
                    "message": bootstrap_message,
                    "stage": "op-simple-build",
                }
            )
            print(
                "[op-simple-build] "
                f"[{utc_now_iso()}] "
                f"cycle=0 profile-snapshot-bootstrap status=failed message={bootstrap_message}",
                flush=True,
            )
        _seed_plan_artifacts_from_planner(cfg)
        lane_contract_ok, lane_contract = _plan_lane_base_branches_contract(cfg)
        if not lane_contract_ok:
            return {
                "ok": False,
                "status": "blocked_preflight",
                "summary": "Build blocked: plan_packets lane-base contract is invalid.",
                "errors": [
                    {
                        "code": str(lane_contract.get("code") or "lane_base_branches_invalid"),
                        "message": str(lane_contract.get("message") or "lane_base_branches contract validation failed"),
                        "stage": "build_preflight",
                        "details": lane_contract.get("details") if isinstance(lane_contract.get("details"), dict) else {},
                    }
                ],
                "warnings": warnings,
                "artifacts": artifacts,
                "next_action": (
                    "Regenerate plan packets so they include top-level lane_base_branches map with full tasks[].lane_id "
                    "coverage, then rerun /op-build or /op-resume."
                ),
                "state_ref": str((cfg.repo_root / ARTIFACT_FILES["plan_packets"]).resolve()),
                "data": {
                    "lane_base_branches_required": True,
                    "plan_packets_ref": str((cfg.repo_root / ARTIFACT_FILES["plan_packets"]).resolve()),
                },
            }
        _refresh_lane_base_watchdog_registry(
            cfg,
            cycle_number=_load_cycle_counter(cfg),
            now_utc=datetime.now(timezone.utc),
            force_reset_target=False,
        )

        cycle_number = _load_cycle_counter(cfg)
        _apply_restart_determinism_hooks(
            cfg,
            cycle_number=cycle_number,
            resume_mode=bool(cfg.resume_mode),
            prior_run_lock=preexisting_run_lock,
        )
        cycles_this_run = 0
        previous_state_signature: str | None = None
        watchdog_reset_pending = bool(cfg.resume_mode)

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
            cycle_mode = "normal"
            mergeability_report: dict[str, Any] | None = None
            state_signature, _ = _worker_task_state_signature(cfg)
            task_counts_snapshot = _task_counts_from_execution_state(cfg)
            run_base_ref = _mergeability_run_base_ref(cfg)
            watchdog_stop = False
            watchdog_signal: dict[str, Any] = {}
            merge_sweep_result: dict[str, Any] | None = None
            merge_manager_result: dict[str, Any] | None = None

            try:
                merge_sweep_result = _deterministic_merge_sweep(
                    cfg,
                    cycle_number=cycle_number,
                    run_base_ref=run_base_ref,
                )
                manager_statuses["merge-sweep"] = {
                    "status": "ok",
                    "note": (
                        "pre-BOSS deterministic merge sweep completed "
                        f"task_merges={int(merge_sweep_result.get('task_merge_successes') or 0)}/"
                        f"{int(merge_sweep_result.get('task_merge_attempts') or 0)} "
                        f"lane_merges={int(merge_sweep_result.get('lane_merge_successes') or 0)}/"
                        f"{int(merge_sweep_result.get('lane_merge_attempts') or 0)} "
                        f"queue_items={int(merge_sweep_result.get('queue_item_count') or 0)}"
                    ),
                }
                print(
                    "[op-simple-build] "
                    f"[{utc_now_iso()}] "
                    f"cycle={cycle_number} merge-sweep "
                    f"task_merges={int(merge_sweep_result.get('task_merge_successes') or 0)}/"
                    f"{int(merge_sweep_result.get('task_merge_attempts') or 0)} "
                    f"lane_merges={int(merge_sweep_result.get('lane_merge_successes') or 0)}/"
                    f"{int(merge_sweep_result.get('lane_merge_attempts') or 0)} "
                    f"queue_items={int(merge_sweep_result.get('queue_item_count') or 0)}",
                    flush=True,
                )
            except Exception as exc:  # noqa: BLE001
                manager_statuses["merge-sweep"] = {"status": "failed", "note": f"deterministic merge sweep failed: {exc}"}
                warnings.append(
                    {
                        "code": "deterministic_merge_sweep_failed",
                        "message": str(exc),
                        "stage": "op-simple-build",
                        "details": {"cycle_number": cycle_number},
                    }
                )

            try:
                merge_manager_result = _run_periodic_merge_manager(
                    cfg,
                    cycle_number=cycle_number,
                    run_base_ref=run_base_ref,
                )
                manager_statuses["merge-manager"] = {
                    "status": str(merge_manager_result.get("status") or "unknown"),
                    "note": (
                        f"reason={str(merge_manager_result.get('reason') or 'unknown')} "
                        f"queue_before={int(merge_manager_result.get('queue_count_before') or 0)} "
                        f"queue_after={int(merge_manager_result.get('queue_count_after') or 0)}"
                    ),
                }
                print(
                    "[op-simple-build] "
                    f"[{utc_now_iso()}] "
                    f"cycle={cycle_number} merge-manager "
                    f"status={str(merge_manager_result.get('status') or 'unknown')} "
                    f"reason={str(merge_manager_result.get('reason') or 'unknown')} "
                    f"queue_before={int(merge_manager_result.get('queue_count_before') or 0)} "
                    f"queue_after={int(merge_manager_result.get('queue_count_after') or 0)}",
                    flush=True,
                )
            except Exception as exc:  # noqa: BLE001
                manager_statuses["merge-manager"] = {"status": "failed", "note": f"merge-manager stage failed: {exc}"}
                warnings.append(
                    {
                        "code": "merge_manager_stage_failed",
                        "message": str(exc),
                        "stage": "op-simple-build",
                        "details": {"cycle_number": cycle_number},
                    }
                )

            try:
                mergeability_report = _build_mergeability_report(
                    cfg,
                    cycle_number=cycle_number,
                    cycle_mode=cycle_mode,
                )
            except Exception as exc:  # noqa: BLE001
                manager_statuses["merge-engine"] = {"status": "failed", "note": f"mergeability refresh failed: {exc}"}
                warnings.append(
                    {
                        "code": "mergeability_report_failed",
                        "message": str(exc),
                        "stage": "op-simple-build",
                        "details": {"cycle_number": cycle_number},
                    }
                )

            watchdog_stop, watchdog_signal = _watchdog_tick(
                cfg,
                cycle_number,
                force_reset_target=watchdog_reset_pending,
            )
            watchdog_reset_pending = False
            if watchdog_stop:
                cycle_mode = "terminal_stale"
            elif bool(watchdog_signal.get("near_stale")):
                cycle_mode = "merge_recovery"

            if cycle_mode != "normal":
                try:
                    mergeability_report = _build_mergeability_report(
                        cfg,
                        cycle_number=cycle_number,
                        cycle_mode=cycle_mode,
                    )
                except Exception as exc:  # noqa: BLE001
                    manager_statuses["merge-engine"] = {"status": "failed", "note": f"mergeability refresh failed: {exc}"}
                    warnings.append(
                        {
                            "code": "mergeability_report_failed",
                            "message": str(exc),
                            "stage": "op-simple-build",
                            "details": {"cycle_number": cycle_number, "cycle_mode": cycle_mode},
                        }
                    )

            if isinstance(mergeability_report, dict):
                progression = mergeability_report.get("progression") if isinstance(mergeability_report.get("progression"), dict) else {}
                manager_statuses["merge-engine"] = {
                    "status": "ok",
                    "note": (
                        "mergeability report refreshed before watchdog/BOSS "
                        f"unmerged_commits={int(mergeability_report.get('unmerged_commit_count') or 0)} "
                        f"advanced={str(bool(mergeability_report.get('mergeability_advanced'))).lower()} "
                        f"task_queue={int(progression.get('task_to_lane_queue_items') or 0)} "
                        f"lane_queue={int(progression.get('lane_to_run_queue_items') or 0)}"
                    ),
                }

            boss_result: ManagerResult | None = None

            manager_statuses["watchdog"] = {
                "status": "stop" if watchdog_stop else "ok",
                "note": (
                    watchdog_signal.get("message")
                    if watchdog_stop
                    else (
                        "watchdog near-stale threshold reached; merge recovery mode enabled"
                        if cycle_mode == "merge_recovery"
                        else "watchdog healthy"
                    )
                ),
            }

            if watchdog_stop:
                manager_statuses["BOSS"] = {
                    "status": "skipped",
                    "note": "terminal stale detected before BOSS; runtime stopped dispatch work for this cycle",
                }
                manager_statuses["rate-gate"] = {
                    "status": "skipped",
                    "note": "terminal stale detected pre-BOSS",
                }
                manager_statuses["work-dispatcher"] = {
                    "status": "skipped",
                    "note": "terminal stale detected pre-BOSS",
                }
                _write_cycle_manager_decision(
                    cfg,
                    cycle_number,
                    decision="skip_cycle",
                    reason_code=str(watchdog_signal.get("reason_code") or "stale_base_branch_commit"),
                    message=str(watchdog_signal.get("message") or "watchdog terminal stale stop"),
                    worker_registry_ready=True,
                    cycle_mode=cycle_mode,
                )
                print(
                    "[op-simple-build] "
                    f"[{utc_now_iso()}] "
                    f"cycle={cycle_number} watchdog terminal stop before BOSS "
                    f"reason={str(watchdog_signal.get('reason_code') or 'stale_base_branch_commit')}",
                    flush=True,
                )
            else:
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
                        "llm_profile_mode_enabled": _llm_profile_mode_enabled(cfg),
                        "llm_profile": str(cfg.codex_profile or "").strip() or None,
                        "llm_profile_mode_ref": str((cfg.repo_root / ARTIFACT_FILES["llm_profile_mode"]).resolve()),
                        "llm_profile_rate_registry_ref": str(
                            (cfg.repo_root / ARTIFACT_FILES["llm_profile_rate_registry"]).resolve()
                        ),
                        "rate_snapshot_policy": (
                            "use_local_counter_registry_skip_skill"
                            if _llm_profile_mode_enabled(cfg)
                            else "default_codex_rate_snapshot_skill"
                        ),
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
                timeout_state = _record_boss_timeout_state(
                    cfg,
                    cycle_number=cycle_number,
                    result=boss_result,
                    reason_code=boss_result.reason_code or "manager_timeout",
                )
                timeout_streak = int(timeout_state.get("consecutive_boss_timeouts") or 0)
                timeout_threshold = int(timeout_state.get("timeout_threshold") or 2)
                adaptation_active = bool(timeout_state.get("adaptation_active"))
                rotation_required = bool(timeout_state.get("rotation_required"))
                timeout_alias = str(timeout_state.get("last_timeout_profile_alias") or "").strip()
                timeout_reason_code = (
                    "boss_timeout_fail_closed_adaptation_pending"
                    if adaptation_active
                    else "boss_timeout_fail_closed"
                )
                timeout_forensic_message = (
                    f"fail-closed after BOSS timeout; timeout_streak={timeout_streak}/{timeout_threshold}; "
                    f"adaptation_active={str(adaptation_active).lower()}; "
                    f"rotation_required_next_cycle={str(rotation_required).lower()}; "
                    f"timed_out_profile_alias={timeout_alias or 'unknown'}"
                )
                manager_statuses["BOSS"]["note"] = (
                    f"{manager_statuses['BOSS'].get('note')}; {timeout_forensic_message}"
                    if manager_statuses["BOSS"].get("note")
                    else timeout_forensic_message
                )
                manager_statuses["rate-gate"] = {
                    "status": "skipped",
                    "note": "cycle fail-closed after BOSS timeout",
                }
                manager_statuses["work-dispatcher"] = {
                    "status": "skipped",
                    "note": "cycle fail-closed after BOSS timeout",
                }
                manager_statuses["summary"] = {"status": "ok", "note": "summary written"}
                _write_cycle_manager_decision(
                    cfg,
                    cycle_number,
                    decision="skip_cycle",
                    reason_code=timeout_reason_code,
                    message=timeout_forensic_message,
                    worker_registry_ready=True,
                    cycle_mode=cycle_mode,
                )
                timeout_base_summary = {
                    "schema_version": SCHEMA_VERSION,
                    "cycle_number": cycle_number,
                    "cycle_mode": cycle_mode,
                    "manager_statuses": {},
                    "task_counts": task_counts_snapshot,
                    "dispatch_counts": _normalized_dispatch_counts(dispatch_counts),
                    "project_done": False,
                    "insurmountable_blocker": False,
                    "termination": {"reason_code": timeout_reason_code},
                    "stop_reason": "",
                    "notes": timeout_forensic_message,
                }
                _render_cycle_summary(
                    cfg,
                    cycle_number,
                    manager_statuses,
                    dispatch_counts,
                    cycle_mode=cycle_mode,
                    base_summary=timeout_base_summary,
                )
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
                try:
                    mergeability_report = _build_mergeability_report(
                        cfg,
                        cycle_number=cycle_number,
                        cycle_mode=cycle_mode,
                    )
                    progression = (
                        mergeability_report.get("progression")
                        if isinstance(mergeability_report.get("progression"), dict)
                        else {}
                    )
                    manager_statuses["merge-engine"] = {
                        "status": "ok",
                        "note": (
                            "mergeability report refreshed after timeout cycle "
                            f"unmerged_commits={int(mergeability_report.get('unmerged_commit_count') or 0)} "
                            f"advanced={str(bool(mergeability_report.get('mergeability_advanced'))).lower()} "
                            f"task_queue={int(progression.get('task_to_lane_queue_items') or 0)} "
                            f"lane_queue={int(progression.get('lane_to_run_queue_items') or 0)}"
                        ),
                    }
                except Exception as exc:  # noqa: BLE001
                    manager_statuses["merge-engine"] = {"status": "failed", "note": f"mergeability refresh failed: {exc}"}
                _write_terminal_capsule(
                    cfg,
                    cycle_number=cycle_number,
                    reason_code=timeout_reason_code,
                    stop_reason=None,
                    cycle_mode=cycle_mode,
                    manager_name="BOSS",
                    manager_result=boss_result,
                    manager_statuses=manager_statuses,
                    dispatch_counts=dispatch_counts,
                    details={
                        "event": "timeout_cycle_fail_closed",
                        "mergeability_report_ref": str((cfg.repo_root / ARTIFACT_FILES["mergeability_report"]).resolve()),
                        "unmerged_commit_count": int((mergeability_report or {}).get("unmerged_commit_count") or 0),
                        "timeout_state": timeout_state,
                    },
                )
                _snapshot_cycle(cfg, cycle_number)
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
                if not boss_result.timeout:
                    _record_boss_non_timeout_state(
                        cfg,
                        cycle_number=cycle_number,
                        status=boss_result.status,
                        result=boss_result,
                    )

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
                    cycle_mode=cycle_mode,
                )
                manager_statuses["rate-gate"] = {
                    "status": "skipped",
                    "note": "cycle skipped after BOSS failure",
                }
                manager_statuses["work-dispatcher"] = {
                    "status": "skipped",
                    "note": "cycle skipped after BOSS failure",
                }
            elif boss_result is not None and boss_result.status == "ok":
                _run_rate_gate_wait(cfg, cycle_number, warnings)
                manager_statuses["rate-gate"] = {"status": "ok", "note": "rate gate completed"}
                dispatch_reserved_slots = MERGE_RECOVERY_RESERVED_SLOTS if cycle_mode == "merge_recovery" else 0
                if dispatch_reserved_slots > 0:
                    dispatch_counts = _dispatch_packets(
                        cfg,
                        cycle_number,
                        reserved_slots=dispatch_reserved_slots,
                    )
                    manager_statuses["work-dispatcher"] = {
                        "status": "ok",
                        "note": (
                            "dispatch cycle completed with merge recovery reservation "
                            f"reserved_slots={dispatch_reserved_slots}"
                        ),
                    }
                else:
                    dispatch_counts = _dispatch_packets(cfg, cycle_number)
                    manager_statuses["work-dispatcher"] = {"status": "ok", "note": "dispatch cycle completed"}

            try:
                mergeability_report = _build_mergeability_report(
                    cfg,
                    cycle_number=cycle_number,
                    cycle_mode=cycle_mode,
                )
                progression = (
                    mergeability_report.get("progression")
                    if isinstance(mergeability_report.get("progression"), dict)
                    else {}
                )
                manager_statuses["merge-engine"] = {
                    "status": "ok",
                    "note": (
                        "mergeability report refreshed "
                        f"unmerged_commits={int(mergeability_report.get('unmerged_commit_count') or 0)} "
                        f"advanced={str(bool(mergeability_report.get('mergeability_advanced'))).lower()} "
                        f"task_queue={int(progression.get('task_to_lane_queue_items') or 0)} "
                        f"lane_queue={int(progression.get('lane_to_run_queue_items') or 0)}"
                    ),
                }
            except Exception as exc:  # noqa: BLE001
                manager_statuses["merge-engine"] = {"status": "failed", "note": f"mergeability refresh failed: {exc}"}
                warnings.append(
                    {
                        "code": "mergeability_report_failed",
                        "message": str(exc),
                        "stage": "op-simple-build",
                        "details": {"cycle_number": cycle_number},
                    }
                )

            manager_statuses["summary"] = {"status": "ok", "note": "summary written"}
            base_summary: dict[str, Any] | None = None
            if boss_result is not None and boss_result.status != "ok":
                base_summary = {
                    "schema_version": SCHEMA_VERSION,
                    "cycle_number": cycle_number,
                    "cycle_mode": cycle_mode,
                    "manager_statuses": {},
                    "task_counts": task_counts_snapshot,
                    "dispatch_counts": {"attempted": 0, "launched": 0, "launch_failed": 0, "unknown": 0},
                    "project_done": False,
                    "insurmountable_blocker": False,
                    "termination": {},
                    "stop_reason": "",
                    "notes": f"cycle skipped by runtime safety rules: {boss_result.message or 'BOSS failed'}",
                }
            elif watchdog_stop:
                base_summary = {
                    "schema_version": SCHEMA_VERSION,
                    "cycle_number": cycle_number,
                    "cycle_mode": cycle_mode,
                    "manager_statuses": {},
                    "task_counts": task_counts_snapshot,
                    "dispatch_counts": {"attempted": 0, "launched": 0, "launch_failed": 0, "unknown": 0},
                    "project_done": False,
                    "insurmountable_blocker": False,
                    "termination": {"reason_code": str(watchdog_signal.get("reason_code") or "stale_base_branch_commit")},
                    "stop_reason": "",
                    "notes": str(watchdog_signal.get("message") or "watchdog terminal stale stop"),
                }
            summary = _render_cycle_summary(
                cfg,
                cycle_number,
                manager_statuses,
                dispatch_counts,
                cycle_mode=cycle_mode,
                base_summary=base_summary,
            )
            trace_errors: list[str] = []
            try:
                trace_errors = _emit_cycle_trace_events(
                    cfg,
                    cycle_number=cycle_number,
                    dispatch_counts=dispatch_counts,
                )
            except Exception as exc:  # noqa: BLE001
                trace_errors.append(f"trace cycle emission runtime error: {exc}")
            for trace_error in trace_errors:
                warnings.append(
                    {
                        "code": "trace_event_emission_failed",
                        "message": trace_error,
                        "stage": "op-simple-build",
                        "details": {"cycle_number": cycle_number},
                    }
                )

            terminate_path = cfg.repo_root / TERMINATE_FILE_NAME
            if terminate_path.exists():
                stop_reason = "operator_terminate_file"
            else:
                stop_reason = _termination_from_summary(summary)
                if stop_reason not in {"project_done", "insurmountable_blocker"} and watchdog_stop:
                    watchdog_reason = str(watchdog_signal.get("reason_code") or "").strip()
                    stop_reason = watchdog_reason or "watchdog_idle_stop"

            if boss_result is not None and boss_result.status != "ok" and not boss_result.timeout and not stop_reason:
                _write_terminal_capsule(
                    cfg,
                    cycle_number=cycle_number,
                    reason_code=boss_result.reason_code or "boss_failed",
                    stop_reason=None,
                    cycle_mode=cycle_mode,
                    manager_name="BOSS",
                    manager_result=boss_result,
                    manager_statuses=manager_statuses,
                    dispatch_counts=dispatch_counts,
                    watchdog_signal=watchdog_signal if isinstance(watchdog_signal, dict) else None,
                    details={
                        "event": "boss_failure_fail_closed",
                        "mergeability_report_ref": str((cfg.repo_root / ARTIFACT_FILES["mergeability_report"]).resolve()),
                        "unmerged_commit_count": int((mergeability_report or {}).get("unmerged_commit_count") or 0),
                    },
                )

            _update_restart_determinism_checkpoint(
                cfg,
                cycle_number=cycle_number,
                cycle_mode=cycle_mode,
                stop_reason=stop_reason,
            )

            if cfg.ground_sync_enabled and not stop_reason and cycle_number % cfg.ground_sync_every_n_cycles == 0:
                sync_status, sync_message = _run_ground_sync(
                    cfg,
                    cycle_number=cycle_number,
                    trigger="cadence",
                )
                print(
                    "[op-simple-build] "
                    f"[{utc_now_iso()}] "
                    f"cycle={cycle_number} manager={GROUND_SYNC_MANAGER_NAME} status={sync_status} message={sync_message}",
                    flush=True,
                )
                if sync_status == "failed":
                    warnings.append(
                        {
                            "code": "ground_sync_failed",
                            "message": sync_message,
                            "stage": "op-simple-build",
                            "details": {"cycle_number": cycle_number, "trigger": "cadence"},
                        }
                    )

            _snapshot_cycle(cfg, cycle_number)
            previous_state_signature = _cycle_release_baseline(cfg)[0]

            if stop_reason:
                _persist_cycle_summary_stop_reason(cfg, cycle_number=cycle_number, stop_reason=stop_reason)
                _write_terminal_capsule(
                    cfg,
                    cycle_number=cycle_number,
                    reason_code=stop_reason,
                    stop_reason=stop_reason,
                    cycle_mode=cycle_mode,
                    manager_name="BOSS" if boss_result is not None else None,
                    manager_result=boss_result,
                    manager_statuses=manager_statuses,
                    dispatch_counts=dispatch_counts,
                    watchdog_signal=watchdog_signal if isinstance(watchdog_signal, dict) else None,
                    details={
                        "event": "terminal_cycle_resolution",
                        "mergeability_report_ref": str((cfg.repo_root / ARTIFACT_FILES["mergeability_report"]).resolve()),
                        "unmerged_commit_count": int((mergeability_report or {}).get("unmerged_commit_count") or 0),
                    },
                )
                final_summary = f"OP Simple build stopped: {stop_reason}."
                break

            if cfg.max_build_cycles is not None and cycles_this_run >= cfg.max_build_cycles:
                final_summary = f"Reached max_build_cycles={cfg.max_build_cycles}."
                break

            _await_cycle_release_signal(
                cfg,
                cycle_number=cycle_number,
            )

        if stop_reason:
            _persist_cycle_summary_stop_reason(cfg, cycle_number=cycle_number, stop_reason=stop_reason)

        if stop_reason == "project_done" or _is_watchdog_terminal_reason(stop_reason):
            _run_wrapup_manager(
                cfg,
                cycle_number=cycle_number,
                stop_reason=stop_reason,
                init_state=init_state,
                warnings=warnings,
            )

        if cfg.ground_sync_enabled:
            sync_status, sync_message = _run_ground_sync(
                cfg,
                cycle_number=cycle_number,
                trigger="terminal",
            )
            print(
                "[op-simple-build] "
                f"[{utc_now_iso()}] "
                f"cycle={cycle_number} manager={GROUND_SYNC_MANAGER_NAME} status={sync_status} message={sync_message}",
                flush=True,
            )
            if sync_status == "failed":
                warnings.append(
                    {
                        "code": "ground_sync_failed",
                        "message": sync_message,
                        "stage": "op-simple-build",
                        "details": {"cycle_number": cycle_number, "trigger": "terminal"},
                    }
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
