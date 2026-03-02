#!/usr/bin/env python3
"""Core implementation for OP command surface."""

from __future__ import annotations

import hashlib
import json
import os
import re
import signal
import shlex
import shutil
import subprocess
import sys
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

ENGINE_ROOT = SCRIPT_DIR.parents[1]
SKILLS_ROOT = ENGINE_ROOT / "skills"

from op_router import SUPPORTED_COMMANDS, normalize_command
from planner.llm_planner import (
    materialize_bundle,
    render_prompt,
    run_codex_exec,
)
from planner.validate_git_bootstrap import validate_git_bootstrap
from planner.validate_plan_bundle import validate_bundle_contract

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
GAPS_JSON = PLANNING_REL / "GAPS.json"
GAP_CLOSURE_PLAN_PACKETS_JSON = PLANNING_REL / "GAP_CLOSURE_PLAN_PACKETS.json"
VERIFICATION_MD = PLANNING_REL / "VERIFICATION.md"
UAT_MD = PLANNING_REL / "UAT.md"
EVIDENCE_REL = PLANNING_REL / "evidence"
PRODUCTION_LINE_STATE_JSON = PLANNING_REL / "PRODUCTION_LINE_STATE.json"
DONE_TASKS_REGISTRY_JSON = PLANNING_REL / "DONE_TASKS_REGISTRY.json"
WORK_DISPATCH_PLAN_JSON = PLANNING_REL / "WORK_DISPATCH_PLAN.json"
DISPATCH_ASSIGNMENT_OBSERVATIONS_JSONL = PLANNING_REL / "DISPATCH_ASSIGNMENT_OBSERVATIONS.jsonl"

BUILD_STATE_JSON = PLANNING_REL / "BUILD_STATE.json"
TASK_EXECUTION_STATE_JSON = PLANNING_REL / "TASK_EXECUTION_STATE.json"
PROFILE_SELECTION_JSON = PLANNING_REL / "PROFILE_SELECTION.json"
PLANNER_REL = PLANNING_REL / "llm"
PLANNER_ATTEMPTS_JSONL = PLANNER_REL / "PLAN_GENERATION_ATTEMPTS.jsonl"
BUILD_LOOP_LOCK = PLANNING_REL / "BUILD_LOOP.lock"
RUN_PROGRESS_LEDGER_JSONL = PLANNING_REL / "RUN_PROGRESS_LEDGER.jsonl"
NO_PROGRESS_WATCHDOG_STATE_JSON = PLANNING_REL / "NO_PROGRESS_WATCHDOG_STATE.json"
NO_PROGRESS_WATCHDOG_EVENT_JSON = PLANNING_REL / "NO_PROGRESS_WATCHDOG_EVENT.json"
RUN_FINDINGS_JSON = PLANNING_REL / "RUN_FINDINGS.json"
LANE_B_RUNTIME_CANARY_GATE_JSON = PLANNING_REL / "LANE_B_RUNTIME_CANARY_GATE.json"
CONTROL_REL = Path("reports") / "optimus-prime" / "control"
OPERATOR_STOP_JSON = CONTROL_REL / "OPERATOR_STOP.json"
OPERATOR_STOP_STATE_JSON = CONTROL_REL / "OPERATOR_STOP_STATE.json"
PROFILE_RATE_REGISTRY_JSON = Path("reports") / "optimus-prime" / "PROFILE_RATE_REGISTRY.json"
RATE_SNAPSHOT_SCRIPT_REL = Path("skills") / "codex-rate-snapshot" / "scripts" / "read_codex_rate_snapshots.py"
PLANNER_PROMPT_TEMPLATE_PATH = SCRIPT_DIR / "planner" / "prompts" / "llm_plan_prompt.md"
PLANNER_VALIDATOR_SCRIPT_PATH = SCRIPT_DIR / "planner" / "validate_plan_bundle.py"
PLANNER_EXAMPLE_ROOT_PATH = SCRIPT_DIR / "llm" / "examples" / "op-plan" / "reports" / "optimus-prime" / "planning"
GIT_BOOTSTRAP_PROMPT_TEMPLATE_PATH = SCRIPT_DIR / "planner" / "prompts" / "git_bootstrap_prompt.md"
GIT_BOOTSTRAP_VALIDATOR_SCRIPT_PATH = SCRIPT_DIR / "planner" / "validate_git_bootstrap.py"
GIT_BOOTSTRAP_REQUIRED_BRANCH = "RAB-BASE"
BRANCH_MANAGER_PROMPT_TEMPLATE_PATH = SCRIPT_DIR / "planner" / "prompts" / "branch_manager_prompt.md"
WORKSTATION_MANAGER_PROMPT_TEMPLATE_PATH = SCRIPT_DIR / "planner" / "prompts" / "workstation_manager_prompt.md"

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
    VERIFICATION_MD,
    UAT_MD,
    TASK_EXECUTION_STATE_JSON,
    PROFILE_SELECTION_JSON,
]

PLANNING_OVERRIDE_SENTINELS = [
    PROJECT_MD,
    REQUIREMENTS_MD,
    ROADMAP_MD,
    STATE_MD,
    STATE_JSON,
    PLAN_PACKETS_JSON,
    PLAN_CHECK_JSON,
    TASK_EXECUTION_STATE_JSON,
    PRODUCTION_LINE_STATE_JSON,
    DONE_TASKS_REGISTRY_JSON,
    WORK_DISPATCH_PLAN_JSON,
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

STALE_IN_PROGRESS_TIMEOUT_SEC = 900
NO_PROGRESS_THRESHOLD_CYCLES = 25

BRANCH_ACTION_COMMAND_TIMEOUT_SEC = 300
BRANCH_VERIFY_COMMAND_TIMEOUT_SEC = 1800
WORKSTATION_PREP_COMMAND_TIMEOUT_SEC = 600

TASK_STATUS_PENDING = "pending"
TASK_STATUS_DEV_WORKING = "dev_working"
TASK_STATUS_DEV_DONE = "dev_done"
TASK_STATUS_TESTING = "testing"
TASK_STATUS_TESTS_DONE = "tests_done"
TASK_STATUS_REVIEWING = "reviewing"
TASK_STATUS_REVIEW_DONE = "review_done"
TASK_STATUS_BLOCKED = "blocked"

TASK_STATUS_ALLOWED = {
    TASK_STATUS_PENDING,
    TASK_STATUS_DEV_WORKING,
    TASK_STATUS_DEV_DONE,
    TASK_STATUS_TESTING,
    TASK_STATUS_TESTS_DONE,
    TASK_STATUS_REVIEWING,
    TASK_STATUS_REVIEW_DONE,
    TASK_STATUS_BLOCKED,
}

TASK_STATUS_NORMALIZE_MAP = {
    "queued": TASK_STATUS_PENDING,
    "dev_in_progress": TASK_STATUS_DEV_WORKING,
    "dev_done": TASK_STATUS_DEV_DONE,
    "test_in_progress": TASK_STATUS_TESTING,
    "test_done": TASK_STATUS_TESTS_DONE,
    "review_in_progress": TASK_STATUS_REVIEWING,
    "review_done": TASK_STATUS_REVIEW_DONE,
    "blocked": TASK_STATUS_BLOCKED,
    TASK_STATUS_PENDING: TASK_STATUS_PENDING,
    TASK_STATUS_DEV_WORKING: TASK_STATUS_DEV_WORKING,
    TASK_STATUS_DEV_DONE: TASK_STATUS_DEV_DONE,
    TASK_STATUS_TESTING: TASK_STATUS_TESTING,
    TASK_STATUS_TESTS_DONE: TASK_STATUS_TESTS_DONE,
    TASK_STATUS_REVIEWING: TASK_STATUS_REVIEWING,
    TASK_STATUS_REVIEW_DONE: TASK_STATUS_REVIEW_DONE,
    TASK_STATUS_BLOCKED: TASK_STATUS_BLOCKED,
}

FIXED_WORKER_TOPOLOGY: list[dict[str, str]] = [
    {"slot": "dev-1", "role": "developer"},
    {"slot": "dev-2", "role": "developer"},
    {"slot": "dev-3", "role": "developer"},
    {"slot": "test-1", "role": "tester"},
    {"slot": "test-2", "role": "tester"},
    {"slot": "test-3", "role": "tester"},
    {"slot": "review-1", "role": "reviewer"},
    {"slot": "review-2", "role": "reviewer"},
    {"slot": "review-3", "role": "reviewer"},
    {"slot": "production-line-manager-1", "role": "manager"},
    {"slot": "branch-manager-1", "role": "manager"},
]
FIXED_WORKER_SLOTS: list[str] = [row["slot"] for row in FIXED_WORKER_TOPOLOGY]

OPTIMUS_GITIGNORE_BEGIN = "# BEGIN OPTIMUS-PRIME MANAGED REPORT IGNORES"
OPTIMUS_GITIGNORE_END = "# END OPTIMUS-PRIME MANAGED REPORT IGNORES"
OPTIMUS_GITIGNORE_LINES = [
    OPTIMUS_GITIGNORE_BEGIN,
    "/reports/optimus-prime/runtime/**",
    "/reports/optimus-prime/controller/**",
    "/reports/optimus-prime/control/**",
    "/reports/optimus-prime/prompts/**",
    "/reports/optimus-prime/planning/evidence/**",
    "/reports/optimus-prime/planning/TASK_EXECUTION_STATE.json",
    "/reports/optimus-prime/planning/BUILD_STATE.json",
    "/reports/optimus-prime/planning/BUILD_LOOP.lock",
    "/reports/optimus-prime/planning/GAPS.json",
    "/reports/optimus-prime/planning/GAP_CLOSURE_PLAN_PACKETS.json",
    "/reports/optimus-prime/BLOCKERS.jsonl",
    "/reports/optimus-prime/BLOCKER_INDEX.json",
    "/reports/optimus-prime/BLOCKER_ADAPTATION_CANDIDATES.md",
    "/reports/optimus-prime/RUNTIME_REGISTRY.json",
    "/reports/optimus-prime/TEST_RUNTIME_LEASES.json",
    "/reports/optimus-prime/THREAD_HISTORY.log",
    "/reports/optimus-prime/THREAD_TOKEN_USAGE_SUMMARY.json",
    "/reports/optimus-prime/THREAD_TOKEN_USAGE_SUMMARY.md",
    "/reports/optimus-prime/WORKER_REGISTRY.json",
    "/reports/optimus-prime/TEST_TRAIN_STATE.json",
    "/reports/optimus-prime/TEST_TASK_ATTEMPTS.json",
    "/reports/optimus-prime/TEST_WAVE_LOG.jsonl",
    OPTIMUS_GITIGNORE_END,
]
OPTIMUS_GITIGNORE_BLOCK = "\n".join(OPTIMUS_GITIGNORE_LINES) + "\n"


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
    mission_file: str | None
    scope: str | None
    scope_file: str | None
    override_old_plan: bool
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


def _coerce_nonneg_int(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def _normalize_task_status(value: Any) -> str:
    text = (_as_str(value) or TASK_STATUS_PENDING).lower()
    return TASK_STATUS_NORMALIZE_MAP.get(text, TASK_STATUS_PENDING)


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


def _resolve_skill_script(
    skill_name: str,
    script_name: str,
    *,
    required: bool = True,
) -> Path | None:
    script = SKILLS_ROOT / skill_name / "scripts" / script_name
    if script.exists():
        return script
    if required:
        raise OpError("runtime_error", f"bundled skill script not found: {script}", stage="build")
    return None


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


def _emit_build_progress(req: OpRequest, message: str) -> None:
    if not sys.stdout.isatty():
        return
    command = (_as_str(getattr(req, "command", None)) or "").strip().lower().lstrip("/")
    if command in {"op-plan"}:
        label = "op-plan"
    elif command in {"op-initialize"}:
        label = "op-initialize"
    elif command in {"op-build", "op-resume"}:
        label = "op-build"
    else:
        label = "op-runtime"
    stamp = datetime.now().astimezone().strftime("%H:%M:%S")
    print(f"[{label} {stamp}] {message}", flush=True)


def _task_status_counts(task_state: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in task_state.get("tasks", []):
        if not isinstance(row, dict):
            continue
        status = _normalize_task_status(row.get("status"))
        counts[status] = counts.get(status, 0) + 1
    return counts


def _summarize_assignment_observations(rows: list[dict[str, Any]]) -> str:
    counts = {"dispatched": 0, "skipped": 0, "failed": 0, "invalid": 0}
    for row in rows:
        if not isinstance(row, dict):
            continue
        status = _as_str(row.get("status"))
        if status in counts:
            counts[status] += 1
    return (
        "dispatch observations: "
        f"dispatched={counts['dispatched']}, "
        f"skipped={counts['skipped']}, "
        f"failed={counts['failed']}, "
        f"invalid={counts['invalid']}"
    )


def _summarize_watchdog_findings(
    *,
    progress_delta: bool,
    progress_reason_codes: list[str],
    watchdog_state: dict[str, Any],
    cycle_warnings: list[dict[str, Any]],
) -> str:
    no_progress = _coerce_nonneg_int(watchdog_state.get("consecutive_no_progress_cycles"), default=0)
    threshold = _coerce_nonneg_int(watchdog_state.get("threshold_cycles"), default=NO_PROGRESS_THRESHOLD_CYCLES)
    warning_codes = sorted(
        {
            code
            for code in (
                _as_str(item.get("code"))
                for item in cycle_warnings
                if isinstance(item, dict)
            )
            if code and code.startswith("no_progress_watchdog")
        }
    )
    findings = ",".join(code for code in progress_reason_codes if code) or "none"
    warning_summary = ",".join(warning_codes) if warning_codes else "none"
    return (
        "watchdog findings: "
        f"progress={'changed' if progress_delta else 'stalled'}, "
        f"no_progress={no_progress}/{threshold}, "
        f"reasons={findings}, "
        f"warnings={warning_summary}"
    )


def _resolve_profile_detection_root() -> Path:
    codex_home = _as_str(os.environ.get("CODEX_HOME"))
    if codex_home:
        try:
            root = Path(codex_home).expanduser().resolve().parent
            if root.exists():
                return root
        except OSError:
            pass
    return Path.home().expanduser().resolve()


def _profile_alias_from_dir_name(name: str) -> str | None:
    if not name.startswith(".codex"):
        return None
    if name == ".codex":
        return "codex"
    alias = name[1:].strip()
    return alias or None


def _detect_profile_selection_payload() -> dict[str, Any]:
    detection_root = _resolve_profile_detection_root()
    profiles: list[dict[str, str]] = []
    try:
        entries = sorted(detection_root.iterdir(), key=lambda path: path.name.lower())
    except OSError as exc:
        raise OpError(
            "profile_detection_none_found",
            f"unable to scan profile root {detection_root}: {exc}",
            stage="initialize",
        ) from exc

    for entry in entries:
        if not entry.is_dir():
            continue
        alias = _profile_alias_from_dir_name(entry.name)
        if not alias:
            continue
        auth_path = entry / "auth.json"
        if not auth_path.is_file():
            continue
        profiles.append(
            {
                "alias": alias,
                "codex_home": str(entry.resolve()),
                "auth_path": str(auth_path.resolve()),
            }
        )

    profiles.sort(key=lambda item: (0 if item["alias"] == "codex" else 1, item["alias"]))
    if not profiles:
        raise OpError(
            "profile_detection_none_found",
            (
                f"no valid .codex* profiles with first-level auth.json found under {detection_root}. "
                "Install Codex profile(s) or add a symlink like ~/.codex -> <your-codex-home>."
            ),
            stage="initialize",
        )

    selected_aliases = [item["alias"] for item in profiles]
    notes: list[str] = []
    if "codex" not in selected_aliases:
        notes.append("default .codex profile not found; using alternate detected profiles")

    return {
        "schema_version": SCHEMA_VERSION,
        "detected_at": utc_now_iso(),
        "detection_root": str(detection_root),
        "profiles": profiles,
        "selected_aliases": selected_aliases,
        "selection_policy": "initialize_autodetect",
        "notes": notes,
    }


def _validate_profile_selection_payload(payload: Any, *, stage: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise OpError("profile_selection_invalid", "PROFILE_SELECTION.json must be a JSON object", stage=stage)

    profiles = payload.get("profiles")
    if not isinstance(profiles, list):
        raise OpError("profile_selection_invalid", "PROFILE_SELECTION.json field 'profiles' must be a list", stage=stage)

    normalized_profiles: list[dict[str, str]] = []
    alias_to_home: dict[str, str] = {}
    for idx, item in enumerate(profiles):
        if not isinstance(item, dict):
            raise OpError(
                "profile_selection_invalid",
                f"PROFILE_SELECTION.json profile row {idx} must be an object",
                stage=stage,
            )
        alias = _as_str(item.get("alias"))
        codex_home = _as_str(item.get("codex_home"))
        auth_path = _as_str(item.get("auth_path"))
        if not alias or not codex_home or not auth_path:
            raise OpError(
                "profile_selection_invalid",
                f"PROFILE_SELECTION.json profile row {idx} missing alias/codex_home/auth_path",
                stage=stage,
            )
        normalized_profiles.append(
            {
                "alias": alias,
                "codex_home": codex_home,
                "auth_path": auth_path,
            }
        )
        alias_to_home[alias] = codex_home

    selected_aliases_raw = payload.get("selected_aliases")
    if not isinstance(selected_aliases_raw, list):
        raise OpError(
            "profile_selection_invalid",
            "PROFILE_SELECTION.json field 'selected_aliases' must be a list",
            stage=stage,
        )
    selected_aliases = [alias for alias in (_as_str(item) for item in selected_aliases_raw) if alias]
    if not selected_aliases:
        raise OpError(
            "profile_selection_invalid",
            "PROFILE_SELECTION.json selected_aliases must contain at least one alias",
            stage=stage,
        )
    if len(set(selected_aliases)) != len(selected_aliases):
        raise OpError(
            "profile_selection_invalid",
            "PROFILE_SELECTION.json selected_aliases must not contain duplicates",
            stage=stage,
        )
    for alias in selected_aliases:
        if alias not in alias_to_home:
            raise OpError(
                "profile_selection_invalid",
                f"PROFILE_SELECTION.json selected alias '{alias}' missing from profiles[]",
                stage=stage,
            )

    return {
        "schema_version": _as_str(payload.get("schema_version")) or SCHEMA_VERSION,
        "detected_at": _as_str(payload.get("detected_at")) or utc_now_iso(),
        "detection_root": _as_str(payload.get("detection_root")) or str(_resolve_profile_detection_root()),
        "profiles": normalized_profiles,
        "selected_aliases": selected_aliases,
        "selection_policy": _as_str(payload.get("selection_policy")) or "initialize_autodetect",
        "notes": payload.get("notes") if isinstance(payload.get("notes"), list) else [],
        "alias_to_home": alias_to_home,
    }


def _load_profile_selection_required(repo_root: Path, *, stage: str) -> dict[str, Any]:
    path = _repo_path(repo_root, PROFILE_SELECTION_JSON)
    if not path.exists():
        raise OpError(
            "profile_selection_missing",
            "PROFILE_SELECTION.json is missing; run /op-initialize to detect profiles",
            stage=stage,
        )
    payload = _read_json(path)
    validated = _validate_profile_selection_payload(payload, stage=stage)
    validated["path"] = str(path)
    return validated


def _profile_args_from_selection(selection_payload: dict[str, Any], *, stage: str) -> list[str]:
    alias_to_home = selection_payload.get("alias_to_home")
    if not isinstance(alias_to_home, dict):
        validated = _validate_profile_selection_payload(selection_payload, stage=stage)
        alias_to_home = validated["alias_to_home"]
    selected_aliases = selection_payload.get("selected_aliases")
    if not isinstance(selected_aliases, list):
        raise OpError(
            "profile_selection_invalid",
            "PROFILE_SELECTION payload missing selected_aliases list",
            stage=stage,
        )

    args: list[str] = []
    for alias in selected_aliases:
        alias_text = _as_str(alias)
        if not alias_text:
            continue
        if alias_text == "codex":
            args.append("codex=default")
            continue
        home = _as_str(alias_to_home.get(alias_text))
        if not home:
            raise OpError(
                "profile_selection_invalid",
                f"PROFILE_SELECTION missing codex_home for alias '{alias_text}'",
                stage=stage,
            )
        args.append(f"{alias_text}={home}")
    if not args:
        raise OpError(
            "profile_selection_invalid",
            "PROFILE_SELECTION selected_aliases resolved to zero profile args",
            stage=stage,
        )
    return args


def _resolve_rate_snapshot_script(repo_root: Path) -> Path | None:
    candidates: list[Path] = []
    candidates.append(repo_root / RATE_SNAPSHOT_SCRIPT_REL)
    candidates.append(ENGINE_ROOT / RATE_SNAPSHOT_SCRIPT_REL)
    codex_home = _as_str(os.environ.get("CODEX_HOME"))
    if codex_home:
        candidates.append(Path(codex_home).expanduser().resolve() / RATE_SNAPSHOT_SCRIPT_REL)
    candidates.append(Path.home() / ".codex" / RATE_SNAPSHOT_SCRIPT_REL)

    seen: set[str] = set()
    for candidate in candidates:
        text = str(candidate)
        if text in seen:
            continue
        seen.add(text)
        if candidate.exists():
            return candidate
    return None


def _seed_rate_registry_if_missing(
    repo_root: Path,
    *,
    stage: str = "build_loop",
    force_refresh: bool = False,
    emit_success_warning: bool = True,
    profile_selection: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    registry_path = _repo_path(repo_root, PROFILE_RATE_REGISTRY_JSON)
    if registry_path.exists() and not force_refresh:
        return warnings

    script_path = _resolve_rate_snapshot_script(repo_root)
    if script_path is None:
        warnings.append(
            {
                "code": "rate_registry_seed_unavailable",
                "message": "codex-rate-snapshot script not found; PROFILE_RATE_REGISTRY.json was not generated",
                "stage": stage,
            }
        )
        return warnings

    try:
        resolved_selection = (
            _validate_profile_selection_payload(profile_selection, stage=stage)
            if profile_selection is not None
            else _load_profile_selection_required(repo_root, stage=stage)
        )
        profile_args = _profile_args_from_selection(resolved_selection, stage=stage)
    except OpError as exc:
        warnings.append(
            {
                "code": exc.code,
                "message": exc.message,
                "stage": stage,
            }
        )
        return warnings

    cmd = [sys.executable, str(script_path)]
    for arg in profile_args:
        cmd.extend(["--profile", arg])
    cmd.append("--json-pretty")
    code, out, err = _run(cmd, cwd=repo_root)
    if code != 0:
        stderr = (err or "").strip()
        warnings.append(
            {
                "code": "rate_registry_seed_failed",
                "message": (
                    "failed to generate PROFILE_RATE_REGISTRY.json via codex-rate-snapshot"
                    + (f": {stderr}" if stderr else "")
                ),
                "stage": stage,
            }
        )
        return warnings

    try:
        payload = json.loads(out)
    except json.JSONDecodeError as exc:
        warnings.append(
            {
                "code": "rate_registry_seed_failed",
                "message": f"codex-rate-snapshot emitted invalid JSON: {exc}",
                "stage": stage,
            }
        )
        return warnings

    if not isinstance(payload, dict):
        warnings.append(
            {
                "code": "rate_registry_seed_failed",
                "message": "codex-rate-snapshot output must be a JSON object",
                "stage": stage,
            }
        )
        return warnings

    profiles = payload.get("profiles")
    if not isinstance(profiles, dict):
        warnings.append(
            {
                "code": "rate_registry_seed_failed",
                "message": "codex-rate-snapshot output missing valid 'profiles' object",
                "stage": stage,
            }
        )
        return warnings

    try:
        _atomic_write_json(registry_path, payload)
    except OSError as exc:
        warnings.append(
            {
                "code": "rate_registry_seed_failed",
                "message": f"unable to write PROFILE_RATE_REGISTRY.json: {exc}",
                "stage": stage,
            }
        )
        return warnings

    if emit_success_warning:
        warnings.append(
            {
                "code": "rate_registry_seeded",
                "message": "generated PROFILE_RATE_REGISTRY.json via codex-rate-snapshot",
                "stage": stage,
            }
        )
    return warnings


def _ensure_managed_gitignore_block(repo_root: Path) -> None:
    gitignore_path = repo_root / ".gitignore"
    try:
        existing = gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""
    except OSError:
        return

    begin = existing.find(OPTIMUS_GITIGNORE_BEGIN)
    end = existing.find(OPTIMUS_GITIGNORE_END, begin if begin >= 0 else 0)

    if begin >= 0:
        prefix = existing[:begin]
        if end > begin:
            end_line = existing.find("\n", end)
            suffix_start = len(existing) if end_line < 0 else end_line + 1
            suffix = existing[suffix_start:]
        else:
            # Corrupted prior block (missing END): replace from BEGIN through EOF.
            suffix = ""
        if prefix and not prefix.endswith("\n"):
            prefix += "\n"
        updated = f"{prefix}{OPTIMUS_GITIGNORE_BLOCK}{suffix}"
    else:
        base = existing
        if base and not base.endswith("\n"):
            base += "\n"
        updated = f"{base}{OPTIMUS_GITIGNORE_BLOCK}"

    if updated == existing:
        return
    try:
        _write_text(gitignore_path, updated)
    except OSError:
        return


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise OpError("state_read_error", f"invalid JSON at {path}: {exc}", stage="state") from exc
    except OSError as exc:
        raise OpError("state_read_error", f"unable to read {path}: {exc}", stage="state") from exc


def _backup_corrupt_file(path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = path.with_name(f"{path.stem}.corrupt.{stamp}{path.suffix}")
    if backup.exists():
        backup = path.with_name(f"{path.stem}.corrupt.{stamp}.{uuid.uuid4().hex[:8]}{path.suffix}")
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise OpError("state_read_error", f"unable to backup corrupted artifact {path}: {exc}", stage="state") from exc
    _ensure_parent(backup)
    backup.write_bytes(payload)
    return backup


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


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    _ensure_parent(path)
    line = json.dumps(payload, sort_keys=False)
    try:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line)
            fh.write("\n")
    except OSError as exc:
        raise OpError("state_write_error", f"unable to append {path}: {exc}", stage="state") from exc


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


def _task_progress_payload(task_state: dict[str, Any], open_gap_ids: list[str]) -> dict[str, Any]:
    task_rows = task_state.get("tasks") if isinstance(task_state.get("tasks"), list) else []
    normalized_tasks: list[dict[str, Any]] = []
    for row in task_rows:
        if not isinstance(row, dict):
            continue
        task_id = _as_str(row.get("task_id"))
        if not task_id:
            continue
        normalized_tasks.append(
            {
                "task_id": task_id,
                "status": _as_str(row.get("status")) or "unknown",
                "owner_slot": _as_str(row.get("owner_slot")),
                "phase_id": _as_str(row.get("phase_id")) or "phase-1",
            }
        )
    normalized_tasks.sort(key=lambda item: item.get("task_id") or "")
    gaps = sorted([gap_id for gap_id in (_as_str(v) for v in open_gap_ids) if gap_id])
    return {
        "tasks": normalized_tasks,
        "open_gap_ids": gaps,
    }


def _task_progress_fingerprint(payload: dict[str, Any]) -> str:
    return _sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def _load_no_progress_watchdog_state(path: Path) -> dict[str, Any]:
    default = {
        "schema_version": SCHEMA_VERSION,
        "last_cycle": 0,
        "consecutive_no_progress_cycles": 0,
        "threshold_cycles": NO_PROGRESS_THRESHOLD_CYCLES,
        "last_progress_at": None,
        "triggered": False,
        "triggered_at": None,
        "trigger_reason": None,
    }
    if not path.exists():
        return default
    try:
        payload = _read_json(path)
    except OpError:
        return default
    if not isinstance(payload, dict):
        return default
    out = dict(default)
    out.update(payload)
    out["threshold_cycles"] = NO_PROGRESS_THRESHOLD_CYCLES
    out["consecutive_no_progress_cycles"] = _coerce_nonneg_int(out.get("consecutive_no_progress_cycles"), default=0)
    out["last_cycle"] = _coerce_nonneg_int(out.get("last_cycle"), default=0)
    out["triggered"] = _as_bool(out.get("triggered"), default=False)
    out["schema_version"] = SCHEMA_VERSION
    return out


def _init_no_progress_watchdog_state(path: Path, build_state: dict[str, Any]) -> dict[str, Any]:
    state = _load_no_progress_watchdog_state(path)
    build_watchdog = build_state.get("no_progress_watchdog")
    if isinstance(build_watchdog, dict):
        build_counter = _coerce_nonneg_int(build_watchdog.get("consecutive_no_progress_cycles"), default=0)
        file_counter = _coerce_nonneg_int(state.get("consecutive_no_progress_cycles"), default=0)
        if build_counter > file_counter:
            state["consecutive_no_progress_cycles"] = build_counter
        build_last_progress = _as_str(build_watchdog.get("last_progress_at"))
        file_last_progress = _as_str(state.get("last_progress_at"))
        if build_last_progress:
            build_last_progress_dt = _parse_iso_utc(build_last_progress)
            file_last_progress_dt = _parse_iso_utc(file_last_progress)
            if file_last_progress_dt is None:
                state["last_progress_at"] = build_last_progress
            elif build_last_progress_dt is not None and build_last_progress_dt > file_last_progress_dt:
                state["last_progress_at"] = build_last_progress
        if _as_bool(build_watchdog.get("triggered"), default=False):
            state["triggered"] = True
            state["triggered_at"] = _as_str(build_watchdog.get("triggered_at")) or _as_str(state.get("triggered_at"))
            state["trigger_reason"] = _as_str(state.get("trigger_reason")) or "task_state_no_progress_25_cycles"
    state["threshold_cycles"] = NO_PROGRESS_THRESHOLD_CYCLES
    state["schema_version"] = SCHEMA_VERSION
    return state


def _write_watchdog_stop_marker(repo_root: Path, *, reason: str, requested_at: str) -> Path:
    marker_path = _repo_path(repo_root, OPERATOR_STOP_JSON)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "stop": True,
        "reason": reason,
        "stop_mode": "graceful_then_force",
        "term_grace_sec": 10,
        "kill_grace_sec": 3,
        "resume_policy": "auto",
        "requested_at": requested_at,
    }
    _atomic_write_json(marker_path, payload)
    return marker_path


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _clamp_int(value: Any, *, default: int, low: int, high: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if parsed < low:
        return low
    if parsed > high:
        return high
    return parsed


def _wait_pid_exit(pid: int, timeout_sec: int) -> bool:
    if pid <= 0:
        return True
    deadline = time.monotonic() + max(0, timeout_sec)
    while time.monotonic() < deadline:
        if not _pid_is_running(pid):
            return True
        time.sleep(0.2)
    return not _pid_is_running(pid)


def _worker_state(worker: dict[str, Any]) -> str:
    return (
        _as_str(worker.get("state"))
        or _as_str(worker.get("session_state"))
        or _as_str(worker.get("status"))
        or ""
    ).lower()


def _load_worker_registry(path: Path) -> tuple[Any, list[dict[str, Any]], str]:
    if not path.exists():
        return {"workers": []}, [], "dict_list"
    try:
        raw = _read_json(path)
    except OpError:
        return {"workers": []}, [], "dict_list"
    workers: list[dict[str, Any]] = []
    shape = "dict_list"
    if isinstance(raw, dict):
        nested = raw.get("workers")
        if isinstance(nested, list):
            workers = [item for item in nested if isinstance(item, dict)]
            shape = "dict_list"
        elif isinstance(nested, dict):
            workers = [item for item in nested.values() if isinstance(item, dict)]
            shape = "dict_dict"
        else:
            workers = []
            shape = "dict_list"
    elif isinstance(raw, list):
        workers = [item for item in raw if isinstance(item, dict)]
        shape = "list"
    else:
        raw = {"workers": []}
        workers = []
        shape = "dict_list"
    return raw, workers, shape


def _write_worker_registry(path: Path, base_payload: Any, workers: list[dict[str, Any]], shape: str) -> None:
    normalized = [item for item in workers if isinstance(item, dict)]
    if shape == "list":
        _atomic_write_json(path, normalized)
        return
    if shape == "dict_dict":
        out = base_payload if isinstance(base_payload, dict) else {}
        workers_dict: dict[str, dict[str, Any]] = {}
        for idx, worker in enumerate(normalized):
            slot = _as_str(worker.get("slot")) or f"slot-{idx+1}"
            workers_dict[slot] = worker
        out["workers"] = workers_dict
        _atomic_write_json(path, out)
        return
    out = base_payload if isinstance(base_payload, dict) else {}
    out["workers"] = normalized
    _atomic_write_json(path, out)


def _default_worker_row(slot: str) -> dict[str, Any]:
    now = utc_now_iso()
    if slot.startswith("dev-"):
        role = "developer"
    elif slot.startswith("test-"):
        role = "tester"
    elif slot.startswith("review-"):
        role = "reviewer"
    elif slot.startswith("production-line-manager"):
        role = "manager"
    else:
        role = "manager"
    manager_type = None
    if slot == "production-line-manager-1":
        manager_type = "production_line"
    elif slot == "branch-manager-1":
        manager_type = "branch_merge"
    default_branch = _default_slot_branch(slot, role=role)
    row: dict[str, Any] = {
        "slot": slot,
        "role": role,
        "session_state": "not_running",
        "active_task_id": None,
        "active_task": None,
        "lane_id": None,
        "previous_lane_id": "n/a",
        "branch": default_branch,
        "dispatch_pid": None,
        "dispatch_thread_id": None,
        "codex_profile_alias": None,
        "worktree_root": None,
        "updated_at": now,
    }
    if manager_type is not None:
        row["manager_type"] = manager_type
        row["active_job_id"] = None
    return row


def _default_slot_branch(slot: str, *, role: str | None = None) -> str:
    resolved_role = role or ("developer" if slot.startswith("dev-") else "tester" if slot.startswith("test-") else "reviewer" if slot.startswith("review-") else "manager")
    if resolved_role in {"developer", "tester", "reviewer"}:
        return f"codex/{slot}/bootstrap"
    return "RAB-BASE"


def _expected_slot_worktree_name(slot: str) -> str | None:
    if slot.startswith("dev-") or slot.startswith("test-") or slot.startswith("review-"):
        return f"workstation-{slot}"
    return None


def _expected_slot_worktree_path(repo_root: Path, slot: str) -> Path | None:
    worktree_name = _expected_slot_worktree_name(slot)
    if not worktree_name:
        return None
    return (repo_root.parent / f".{repo_root.name}-workstations" / worktree_name).resolve()


def _apply_slot_lane_transition(row: dict[str, Any], lane_value: str | None) -> None:
    """Persist deterministic lane transition semantics on worker rows."""
    if not lane_value:
        if row.get("previous_lane_id") is None:
            row["previous_lane_id"] = "n/a"
        return
    current_lane = _as_str(row.get("lane_id"))
    previous_lane = _as_str(row.get("previous_lane_id"))
    if not current_lane:
        # First assignment: previous lane initializes to current lane.
        row["lane_id"] = lane_value
        row["previous_lane_id"] = lane_value
        return
    if current_lane == lane_value:
        # Same-lane work keeps prior lane state unchanged.
        if not previous_lane:
            row["previous_lane_id"] = current_lane
        return
    # Real lane change: rotate previous <- current, then set new lane.
    row["previous_lane_id"] = current_lane
    row["lane_id"] = lane_value


def _ensure_worker_registry_v2(repo_root: Path, build_state: dict[str, Any]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    registry_path = repo_root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
    base_payload, workers, shape = _load_worker_registry(registry_path)
    by_slot: dict[str, dict[str, Any]] = {}
    for worker in workers:
        if not isinstance(worker, dict):
            continue
        slot = _as_str(worker.get("slot"))
        if not slot:
            continue
        row = dict(worker)
        row.setdefault("active_task_id", _as_str(row.get("active_task")))
        row.setdefault("lane_id", None)
        row.setdefault("previous_lane_id", "n/a")
        row.setdefault("dispatch_thread_id", None)
        row.setdefault("codex_profile_alias", None)
        row.setdefault("worktree_root", None)
        row.setdefault("session_state", _worker_state(row) or "not_running")
        if row.get("active_task") is not None and row.get("active_task_id") is None:
            row["active_task_id"] = _as_str(row.get("active_task"))
        row_role = _as_str(row.get("role")) or ("developer" if slot.startswith("dev-") else "tester" if slot.startswith("test-") else "reviewer" if slot.startswith("review-") else "manager")
        default_branch = _default_slot_branch(slot, role=row_role)
        current_branch = _as_str(row.get("branch"))
        active_task_id = _as_str(row.get("active_task_id")) or _as_str(row.get("active_task"))
        if not current_branch:
            row["branch"] = default_branch
        elif row_role in {"developer", "tester", "reviewer"} and current_branch == "RAB-BASE" and not active_task_id:
            row["branch"] = default_branch
        by_slot[slot] = row

    out_workers: list[dict[str, Any]] = []
    inserted = 0
    for slot in FIXED_WORKER_SLOTS:
        row = by_slot.get(slot)
        if not isinstance(row, dict):
            row = _default_worker_row(slot)
            inserted += 1
        out_workers.append(row)

    _write_worker_registry(registry_path, base_payload, out_workers, shape if shape in {"dict_list", "dict_dict", "list"} else "dict_list")
    if inserted > 0:
        warnings.append(
            {
                "code": "worker_registry_initialized",
                "message": f"initialized/normalized worker registry v2 with fixed slots (inserted={inserted})",
                "stage": "build_preflight",
            }
        )
    assignments = build_state.get("slot_profile_assignments")
    if not isinstance(assignments, dict):
        assignments = {}
        build_state["slot_profile_assignments"] = assignments
    for slot in FIXED_WORKER_SLOTS:
        assignments.setdefault(slot, None)
    return warnings


def _load_operator_stop_request(marker_path: Path) -> tuple[dict[str, Any] | None, str | None, list[dict[str, Any]]]:
    if not marker_path.exists():
        return None, None, []
    warnings: list[dict[str, Any]] = []
    raw_text: str | None = None
    payload: dict[str, Any] = {}
    try:
        raw_text = marker_path.read_text(encoding="utf-8")
        parsed = json.loads(raw_text) if raw_text.strip() else {}
        if isinstance(parsed, dict):
            payload = parsed
        else:
            warnings.append(
                {
                    "code": "operator_stop_marker_invalid",
                    "message": "OPERATOR_STOP.json must be object JSON; defaults were applied.",
                    "stage": "build_loop",
                }
            )
    except json.JSONDecodeError as exc:
        warnings.append(
            {
                "code": "operator_stop_marker_invalid",
                "message": f"OPERATOR_STOP.json malformed; defaults were applied: {exc}",
                "stage": "build_loop",
            }
        )
    except OSError as exc:
        warnings.append(
            {
                "code": "operator_stop_marker_invalid",
                "message": f"OPERATOR_STOP.json unreadable; defaults were applied: {exc}",
                "stage": "build_loop",
            }
        )

    req = _normalize_operator_stop_request(payload)
    return req, raw_text, warnings


def _normalize_operator_stop_request(payload: dict[str, Any] | None) -> dict[str, Any]:
    body = payload if isinstance(payload, dict) else {}
    requested_at = _as_str(body.get("requested_at")) or utc_now_iso()
    stop_mode = (_as_str(body.get("stop_mode")) or "graceful_then_force").lower()
    if stop_mode != "graceful_then_force":
        stop_mode = "graceful_then_force"
    resume_policy = (_as_str(body.get("resume_policy")) or "auto").lower()
    if resume_policy != "auto":
        resume_policy = "auto"
    return {
        "schema_version": _as_str(body.get("schema_version")) or SCHEMA_VERSION,
        "stop": True,
        "reason": _as_str(body.get("reason")) or "operator_requested_stop",
        "stop_mode": stop_mode,
        "term_grace_sec": _clamp_int(body.get("term_grace_sec"), default=10, low=1, high=120),
        "kill_grace_sec": _clamp_int(body.get("kill_grace_sec"), default=3, low=1, high=30),
        "resume_policy": resume_policy,
        "requested_at": requested_at,
    }


def _next_operator_stop_archive_path(marker_path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archived = marker_path.with_name(f"OPERATOR_STOP.applied.{stamp}.json")
    if archived.exists():
        archived = marker_path.with_name(f"OPERATOR_STOP.applied.{stamp}.{uuid.uuid4().hex[:8]}.json")
    return archived


def _archive_operator_stop_marker(
    marker_path: Path,
    raw_text: str | None,
    request: dict[str, Any],
    *,
    archived_path: Path | None = None,
) -> Path:
    archived = archived_path if isinstance(archived_path, Path) else _next_operator_stop_archive_path(marker_path)
    _ensure_parent(archived)
    archive_text = raw_text if isinstance(raw_text, str) and raw_text.strip() else json.dumps(request, indent=2, sort_keys=True) + "\n"
    archived.write_text(archive_text, encoding="utf-8")
    marker_path.unlink(missing_ok=True)
    return archived


def _reconcile_running_workers_with_pid_state(workers: list[dict[str, Any]], *, now_iso: str, reason: str) -> int:
    normalized = 0
    for worker in workers:
        if not isinstance(worker, dict):
            continue
        state = _worker_state(worker)
        if state not in {"running", "active", "busy"}:
            continue
        pid = worker.get("dispatch_pid")
        if not isinstance(pid, int) or not _pid_is_running(pid):
            worker["session_state"] = "not_running"
            worker["state"] = "not_running"
            worker["updated_at"] = now_iso
            worker["last_state_reason"] = reason
            normalized += 1
    return normalized


def _apply_operator_stop(
    repo_root: Path,
    task_state: dict[str, Any],
    build_state: dict[str, Any],
    *,
    request_override: dict[str, Any] | None = None,
    raw_text_override: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    marker_path = _repo_path(repo_root, OPERATOR_STOP_JSON)
    stop_state_path = _repo_path(repo_root, OPERATOR_STOP_STATE_JSON)
    if isinstance(request_override, dict):
        request = _normalize_operator_stop_request(request_override)
        raw_text = raw_text_override
        warnings: list[dict[str, Any]] = []
    else:
        request, raw_text, warnings = _load_operator_stop_request(marker_path)
        if request is None:
            return {}, warnings

    applied_at = utc_now_iso()
    stop_id = f"stop-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    registry_path = repo_root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
    registry_base, workers, registry_shape = _load_worker_registry(registry_path)

    affected_task_ids: set[str] = set()
    worker_rows: list[dict[str, Any]] = []
    for worker in workers:
        if not isinstance(worker, dict):
            continue
        slot = _as_str(worker.get("slot")) or "unknown-slot"
        task_id = _as_str(worker.get("active_task"))
        initial_state = _worker_state(worker) or "unknown"
        pid = worker.get("dispatch_pid") if isinstance(worker.get("dispatch_pid"), int) else None
        running_state = initial_state in {"running", "active", "busy"}
        pid_live = isinstance(pid, int) and _pid_is_running(pid)
        if (running_state or pid_live) and task_id:
            affected_task_ids.add(task_id)

        stop_action = "none"
        result = "not_running"
        final_state = "not_running"
        if pid_live:
            try:
                os.kill(pid, signal.SIGTERM)
                stop_action = "sigterm"
                if _wait_pid_exit(pid, int(request["term_grace_sec"])):
                    result = "terminated"
                    final_state = "stopped_operator"
                else:
                    try:
                        os.kill(pid, signal.SIGKILL)
                        stop_action = "sigterm_sigkill"
                        if _wait_pid_exit(pid, int(request["kill_grace_sec"])):
                            result = "force_killed"
                            final_state = "stopped_operator"
                        else:
                            result = "kill_failed"
                            final_state = "stop_failed_running"
                    except OSError:
                        result = "kill_failed"
                        final_state = "stop_failed_running"
            except OSError:
                if not _pid_is_running(pid):
                    result = "not_running"
                    final_state = "stopped_operator"
                else:
                    result = "kill_failed"
                    final_state = "stop_failed_running"
        elif running_state:
            final_state = "stopped_operator"

        if result == "terminated":
            warnings.append(
                {
                    "code": "operator_stop_worker_terminated",
                    "message": f"worker {slot} terminated via SIGTERM",
                    "stage": "build_loop",
                    "slot": slot,
                    "task_id": task_id,
                }
            )
        elif result == "force_killed":
            warnings.append(
                {
                    "code": "operator_stop_worker_force_killed",
                    "message": f"worker {slot} required SIGKILL after SIGTERM timeout",
                    "stage": "build_loop",
                    "slot": slot,
                    "task_id": task_id,
                }
            )
        elif result == "kill_failed":
            warnings.append(
                {
                    "code": "operator_stop_worker_kill_failed",
                    "message": f"worker {slot} could not be stopped cleanly",
                    "stage": "build_loop",
                    "slot": slot,
                    "task_id": task_id,
                }
            )

        worker["session_state"] = final_state
        worker["state"] = final_state
        worker["updated_at"] = applied_at
        worker["last_stop_id"] = stop_id
        worker["last_stop_result"] = result
        worker_rows.append(
            {
                "slot": slot,
                "task_id": task_id,
                "pid": pid,
                "initial_state": initial_state,
                "stop_action": stop_action,
                "final_state": final_state,
                "result": result,
            }
        )

    try:
        _reconcile_running_workers_with_pid_state(workers, now_iso=applied_at, reason="operator_stop_post_check")
        _write_worker_registry(registry_path, registry_base, workers, registry_shape)

        archived_path = _next_operator_stop_archive_path(marker_path)
        stop_state: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "stop_id": stop_id,
            "requested_at": request["requested_at"],
            "applied_at": applied_at,
            "stop_mode": request["stop_mode"],
            "resume_policy": request["resume_policy"],
            "marker_path": str(marker_path),
            "marker_archived_path": str(archived_path),
            "workers": worker_rows,
            "affected_task_ids": sorted(affected_task_ids),
            "reconcile_pending": True,
            "reconciled_at": None,
            "reconcile_results": [],
        }
        _atomic_write_json(stop_state_path, stop_state)
        _archive_operator_stop_marker(marker_path, raw_text, request, archived_path=archived_path)
    except Exception as exc:  # noqa: BLE001
        raise OpError(
            "operator_stop_apply_failed",
            f"failed to apply operator stop state updates: {exc}",
            stage="build_loop",
        ) from exc

    build_state["operator_stop"] = {
        "last_stop_id": stop_id,
        "last_applied_at": applied_at,
        "reconcile_pending": True,
    }
    build_state["stop_affected_task_ids"] = sorted(affected_task_ids)

    warnings.append(
        {
            "code": "operator_stop_applied",
            "message": f"operator stop applied; {len(worker_rows)} worker slots inspected",
            "stage": "build_loop",
            "stop_id": stop_id,
        }
    )
    warnings.append(
        {
            "code": "operator_stop_marker_consumed",
            "message": f"operator stop marker consumed and archived at {archived_path.name}",
            "stage": "build_loop",
            "stop_id": stop_id,
        }
    )
    return {
        "stop_id": stop_id,
        "applied_at": applied_at,
        "affected_task_ids": sorted(affected_task_ids),
        "workers": worker_rows,
        "stop_state_path": str(stop_state_path),
        "marker_archived_path": str(archived_path),
    }, warnings


def _reconcile_post_operator_stop(repo_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    build_state_path = _repo_path(repo_root, BUILD_STATE_JSON)
    task_state_path = _repo_path(repo_root, TASK_EXECUTION_STATE_JSON)
    stop_state_path = _repo_path(repo_root, OPERATOR_STOP_STATE_JSON)
    if not stop_state_path.exists():
        return [], None

    stop_state = _read_json(stop_state_path)
    if not isinstance(stop_state, dict):
        raise OpError("resume_stop_reconcile_failed", "OPERATOR_STOP_STATE.json must be object JSON", stage="resume")
    if not _as_bool(stop_state.get("reconcile_pending"), default=False):
        return [], None

    build_state = _load_build_state(build_state_path)
    task_state = _read_json(task_state_path)
    if not isinstance(task_state, dict):
        raise OpError("resume_stop_reconcile_failed", "TASK_EXECUTION_STATE.json must be object JSON", stage="resume")
    plan_packets_path = _repo_path(repo_root, PLAN_PACKETS_JSON)
    plan_packets = _read_json(plan_packets_path) if plan_packets_path.exists() else {"tasks": []}
    if not isinstance(plan_packets, dict):
        plan_packets = {"tasks": []}

    _apply_handoff_updates(repo_root, task_state, build_state)
    _sync_task_state_from_evidence(repo_root, plan_packets, task_state)

    registry_path = repo_root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
    registry_base, workers, registry_shape = _load_worker_registry(registry_path)
    by_slot: dict[str, dict[str, Any]] = {}
    for worker in workers:
        if not isinstance(worker, dict):
            continue
        slot = _as_str(worker.get("slot"))
        if slot:
            by_slot[slot] = worker

    stop_applied_at = _parse_iso_utc(stop_state.get("applied_at"))
    affected = stop_state.get("affected_task_ids")
    affected_ids = [item for item in (_as_str(v) for v in (affected if isinstance(affected, list) else [])) if item]
    if not affected_ids:
        fallback = build_state.get("stop_affected_task_ids")
        affected_ids = [item for item in (_as_str(v) for v in (fallback if isinstance(fallback, list) else [])) if item]

    warnings: list[dict[str, Any]] = []
    reconcile_results: list[dict[str, Any]] = []
    task_map = _task_by_id(task_state)
    now_iso = utc_now_iso()

    for task_id in affected_ids:
        task = task_map.get(task_id)
        if not isinstance(task, dict):
            continue
        status = _normalize_task_status(task.get("status"))
        if status not in {TASK_STATUS_DEV_WORKING, TASK_STATUS_TESTING, TASK_STATUS_REVIEWING}:
            reconcile_results.append({"task_id": task_id, "decision": "ignored_not_in_progress"})
            continue

        owner_slot = _as_str(task.get("owner_slot"))
        worker = by_slot.get(owner_slot or "")
        pid = worker.get("dispatch_pid") if isinstance(worker, dict) and isinstance(worker.get("dispatch_pid"), int) else None
        alive = isinstance(pid, int) and _pid_is_running(pid)
        evidence_path = _task_evidence_path(repo_root, task)
        evidence_progress = False
        if evidence_path.exists():
            try:
                modified = datetime.fromtimestamp(evidence_path.stat().st_mtime, timezone.utc)
                if stop_applied_at is None or modified >= stop_applied_at:
                    evidence_progress = True
            except OSError:
                evidence_progress = False
        progress_at = _parse_iso_utc(task.get("last_progress_at"))
        if progress_at and (stop_applied_at is None or progress_at >= stop_applied_at):
            evidence_progress = True

        if alive and (evidence_progress or evidence_path.exists()):
            reconcile_results.append(
                {
                    "task_id": task_id,
                    "decision": "continued",
                    "reason": "worker_alive_and_progressing",
                    "owner_slot": owner_slot,
                }
            )
            warnings.append(
                {
                    "code": "resume_task_continued_after_stop",
                    "message": f"task {task_id} kept in progress during resume reconciliation",
                    "stage": "resume",
                    "task_id": task_id,
                }
            )
            continue

        task["status"] = TASK_STATUS_PENDING
        task["owner_slot"] = None
        task["last_progress_at"] = now_iso
        blockers = task.get("blockers")
        if not isinstance(blockers, list):
            blockers = []
            task["blockers"] = blockers
        blockers.append(
            {
                "timestamp": now_iso,
                "summary": "requeued after operator stop reconciliation",
            }
        )
        reconcile_results.append(
            {
                "task_id": task_id,
                "decision": "requeued",
                "reason": "worker_not_running_or_no_progress",
                "owner_slot": owner_slot,
            }
        )
        warnings.append(
            {
                "code": "resume_task_requeued_after_stop",
                "message": f"task {task_id} requeued during resume reconciliation",
                "stage": "resume",
                "task_id": task_id,
            }
        )

    normalized = _reconcile_running_workers_with_pid_state(workers, now_iso=now_iso, reason="resume_reconcile")
    if normalized:
        warnings.append(
            {
                "code": "resume_registry_normalized",
                "message": f"normalized {normalized} worker registry entries with dead running pids",
                "stage": "resume",
            }
        )

    _write_worker_registry(registry_path, registry_base, workers, registry_shape)
    _atomic_write_json(task_state_path, {**task_state, "updated_at": now_iso})
    stop_state["reconcile_pending"] = False
    stop_state["reconciled_at"] = now_iso
    stop_state["reconcile_results"] = reconcile_results
    _atomic_write_json(stop_state_path, stop_state)
    build_state["operator_stop"] = {
        "last_stop_id": _as_str(stop_state.get("stop_id")),
        "last_applied_at": _as_str(stop_state.get("applied_at")),
        "reconcile_pending": False,
    }
    build_state["stop_affected_task_ids"] = []
    build_state["updated_at"] = now_iso
    _atomic_write_json(build_state_path, build_state)

    warnings.insert(
        0,
        {
            "code": "resume_post_stop_reconciled",
            "message": f"post-stop reconciliation completed for {len(affected_ids)} task(s)",
            "stage": "resume",
        },
    )
    summary = {
        "stop_id": _as_str(stop_state.get("stop_id")),
        "affected_task_ids": affected_ids,
        "reconcile_results": reconcile_results,
        "stop_state_path": str(stop_state_path),
    }
    return warnings, summary


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


def _canonical_task_evidence_rel(task_id: str) -> Path:
    return EVIDENCE_REL / task_id / "TASK_EVIDENCE.json"


def _default_task_evidence(plan_id: str, phase_id: str, task_id: str, requirement_ids: list[str]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "plan_id": plan_id,
        "phase_id": phase_id,
        "task_id": task_id,
        "requirement_ids": requirement_ids,
        "updated_at": utc_now_iso(),
        "dev": {
            "status": "pending",
            "checks": [],
            "verify_results": [],
            "dev_ready": False,
            "blockers": [],
            "artifacts": [],
        },
        "test": {
            "status": "pending",
            "checks": [],
            "verify_results": [],
            "uat_results": [],
            "blockers": [],
            "artifacts": [],
        },
        "review": {
            "status": "pending",
            "decision": "pending",
            "blockers": [],
            "artifacts": [],
        },
        "gate": {
            "ready_for_test": False,
            "ready_for_review": False,
            "ready_for_phase_exit": False,
        },
        "summary": {
            "result": "blocked",
            "reason_codes": ["not_started"],
        },
    }


def _write_task_evidence_files(repo_root: Path, plan_packets: dict[str, Any]) -> dict[str, str]:
    refs: dict[str, str] = {}
    plan_id = _as_str(plan_packets.get("plan_id")) or "plan-unknown"
    for task in plan_packets.get("tasks", []):
        if not isinstance(task, dict):
            continue
        task_id = _as_str(task.get("task_id"))
        if not task_id:
            continue
        phase_id = _as_str(task.get("phase_id")) or "phase-1"
        req_ids = [
            rid
            for rid in ((_as_str(item) for item in task.get("requirement_ids", [])))
            if rid
        ]
        rel = _canonical_task_evidence_rel(task_id)
        abs_path = _repo_path(repo_root, rel)
        payload = _default_task_evidence(plan_id, phase_id, task_id, req_ids)
        _atomic_write_json(abs_path, payload)
        refs[task_id] = str(rel)
    return refs


def _task_state_from_plan(plan_packets: dict[str, Any], evidence_refs: dict[str, str] | None = None) -> dict[str, Any]:
    tasks = plan_packets.get("tasks") if isinstance(plan_packets.get("tasks"), list) else []
    out_tasks: list[dict[str, Any]] = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = _as_str(task.get("task_id"))
        if not task_id:
            continue
        phase_id = _as_str(task.get("phase_id")) or "phase-1"
        lane_id = _as_str(task.get("lane_id")) or f"{phase_id}/lane-a"
        req_ids = []
        for rid in task.get("requirement_ids", []):
            rid_text = _as_str(rid)
            if rid_text:
                req_ids.append(rid_text)
        evidence_ref = (
            evidence_refs.get(task_id)
            if isinstance(evidence_refs, dict)
            else str(_canonical_task_evidence_rel(task_id))
        )
        out_tasks.append(
            {
                "task_id": task_id,
                "phase_id": phase_id,
                "lane_id": lane_id,
                "requirement_ids": req_ids,
                "status": _normalize_task_status(task.get("status")),
                "owner_slot": None,
                "dispatch_thread_id": None,
                "last_progress_at": None,
                "attempts": {"dev": 0, "test": 0, "review": 0},
                "evidence": {
                    "task_evidence_ref": evidence_ref,
                    "dev_ready_evidence_ref": evidence_ref,
                    "verify_results": [],
                    "uat_results": [],
                },
                "gaps_that_need_patching": task.get("gaps_that_need_patching", []) if isinstance(task.get("gaps_that_need_patching"), list) else [],
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
    allowed = TASK_STATUS_ALLOWED
    seen: set[str] = set()
    plan_phase_ids: set[str] = set()
    for phase in plan_packets.get("phases", []):
        if not isinstance(phase, dict):
            continue
        phase_id = _as_str(phase.get("phase_id"))
        if phase_id:
            plan_phase_ids.add(phase_id)
    for item in tasks:
        if not isinstance(item, dict):
            errors.append({"code": "task_state_invalid", "message": "task entries must be objects"})
            continue
        task_id = _as_str(item.get("task_id"))
        if not task_id:
            errors.append({"code": "task_state_invalid", "message": "task_id is required"})
            continue
        seen.add(task_id)
        status = _normalize_task_status(item.get("status"))
        item["status"] = status
        if status not in allowed:
            errors.append({"code": "task_state_invalid", "message": f"task {task_id} has invalid status {status}"})
        phase_id = _as_str(item.get("phase_id"))
        if not phase_id:
            errors.append({"code": "task_state_invalid", "message": f"task {task_id} phase_id is required"})
        elif plan_phase_ids and phase_id not in plan_phase_ids:
            errors.append({"code": "task_state_invalid", "message": f"task {task_id} phase_id not found in plan phases"})
        lane_id = _as_str(item.get("lane_id"))
        if not lane_id:
            errors.append({"code": "task_state_invalid", "message": f"task {task_id} lane_id is required"})
        elif not lane_id.startswith(f"{phase_id}/lane-"):
            errors.append({"code": "task_state_invalid", "message": f"task {task_id} lane_id must be phase-scoped"})
        dispatch_thread_id = item.get("dispatch_thread_id")
        if dispatch_thread_id is not None and not _as_str(dispatch_thread_id):
            errors.append({"code": "task_state_invalid", "message": f"task {task_id} dispatch_thread_id must be string|null"})
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
        task_evidence_ref = _as_str(evidence.get("task_evidence_ref"))
        if not task_evidence_ref:
            errors.append({"code": "task_state_invalid", "message": f"task {task_id} evidence.task_evidence_ref is required"})
        for key in ("verify_results", "uat_results"):
            val = evidence.get(key)
            if not isinstance(val, list):
                errors.append({"code": "task_state_invalid", "message": f"task {task_id} evidence.{key} must be list"})
        gaps = item.get("gaps_that_need_patching")
        if not isinstance(gaps, list):
            errors.append({"code": "task_state_invalid", "message": f"task {task_id} gaps_that_need_patching must be list"})
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


def _extract_cycle_directives(
    events_path: Path,
    control_number: int,
    control_run_id: str | None = None,
) -> list[dict[str, Any]]:
    rows = _read_jsonl(events_path)
    out: list[dict[str, Any]] = []
    expected_run_id = _as_str(control_run_id)
    for row in rows:
        if int(row.get("control_number") or 0) != int(control_number):
            continue
        if expected_run_id and _as_str(row.get("control_run_id")) != expected_run_id:
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


def _status_counts(task_state: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    rows = task_state.get("tasks") if isinstance(task_state.get("tasks"), list) else []
    for row in rows:
        if not isinstance(row, dict):
            continue
        status = _normalize_task_status(row.get("status"))
        counts[status] = counts.get(status, 0) + 1
    return counts


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


def _phase_map(plan_packets: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for phase in plan_packets.get("phases", []):
        if not isinstance(phase, dict):
            continue
        phase_id = _as_str(phase.get("phase_id"))
        if phase_id:
            out[phase_id] = phase
    return out


def _ordered_phase_ids(plan_packets: dict[str, Any]) -> list[str]:
    phase_ids = [phase_id for phase_id in _phase_map(plan_packets)]
    def _sort_key(value: str) -> tuple[int, str]:
        tail = value.split("-")[-1]
        return (int(tail), value) if tail.isdigit() else (10_000, value)
    return sorted(phase_ids, key=_sort_key)


def _task_evidence_path(repo_root: Path, task: dict[str, Any]) -> Path:
    evidence = task.get("evidence") if isinstance(task.get("evidence"), dict) else {}
    ref = _as_str(evidence.get("task_evidence_ref"))
    if ref:
        return (repo_root / ref).resolve()
    task_id = _as_str(task.get("task_id")) or "TASK-UNKNOWN"
    return _repo_path(repo_root, _canonical_task_evidence_rel(task_id))


def _validate_task_evidence_payload(payload: dict[str, Any], task_id: str, phase_id: str) -> list[str]:
    errors: list[str] = []
    if _as_str(payload.get("task_id")) != task_id:
        errors.append("task_id mismatch")
    if _as_str(payload.get("phase_id")) != phase_id:
        errors.append("phase_id mismatch")
    for section in ("dev", "test", "review", "gate", "summary"):
        if not isinstance(payload.get(section), dict):
            errors.append(f"missing section '{section}'")
    dev = payload.get("dev") if isinstance(payload.get("dev"), dict) else {}
    test = payload.get("test") if isinstance(payload.get("test"), dict) else {}
    review = payload.get("review") if isinstance(payload.get("review"), dict) else {}
    gate = payload.get("gate") if isinstance(payload.get("gate"), dict) else {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    for key in ("checks", "verify_results", "blockers", "artifacts"):
        if not isinstance(dev.get(key), list):
            errors.append(f"dev.{key} must be list")
    for key in ("checks", "verify_results", "uat_results", "blockers", "artifacts"):
        if not isinstance(test.get(key), list):
            errors.append(f"test.{key} must be list")
    for key in ("blockers", "artifacts"):
        if not isinstance(review.get(key), list):
            errors.append(f"review.{key} must be list")
    for key in ("ready_for_test", "ready_for_review", "ready_for_phase_exit"):
        if not isinstance(gate.get(key), bool):
            errors.append(f"gate.{key} must be bool")
    if (_as_str(summary.get("result")) or "").lower() not in {"pass", "fail", "blocked"}:
        errors.append("summary.result must be pass|fail|blocked")
    if not isinstance(summary.get("reason_codes"), list):
        errors.append("summary.reason_codes must be list")
    return errors


def _collect_passed_verify_commands(evidence_payload: dict[str, Any]) -> set[str]:
    passed: set[str] = set()
    for section in ("dev", "test"):
        block = evidence_payload.get(section) if isinstance(evidence_payload.get(section), dict) else {}
        rows = block.get("verify_results")
        if not isinstance(rows, list):
            continue
        for item in rows:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    passed.add(text)
                continue
            if isinstance(item, dict) and _as_bool_field(item.get("passed")):
                cmd = _as_str(item.get("command"))
                if cmd:
                    passed.add(cmd)
    return passed


def _collect_passed_uat_requirement_ids(evidence_payload: dict[str, Any], fallback_requirement_ids: list[str]) -> set[str]:
    passed: set[str] = set()
    test = evidence_payload.get("test") if isinstance(evidence_payload.get("test"), dict) else {}
    rows = test.get("uat_results")
    if not isinstance(rows, list):
        return passed
    for item in rows:
        if not isinstance(item, dict):
            continue
        if not _as_bool_field(item.get("passed")):
            continue
        requirement_id = _as_str(item.get("requirement_id"))
        if requirement_id:
            passed.add(requirement_id)
        requirement_ids = item.get("requirement_ids")
        if isinstance(requirement_ids, list):
            for value in requirement_ids:
                rid = _as_str(value)
                if rid:
                    passed.add(rid)
        if not requirement_id:
            for rid in fallback_requirement_ids:
                passed.add(rid)
    return passed


def _sync_task_state_from_evidence(repo_root: Path, plan_packets: dict[str, Any], task_state: dict[str, Any]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    plan_map = _plan_task_map(plan_packets)
    for task in task_state.get("tasks", []):
        if not isinstance(task, dict):
            continue
        task_id = _as_str(task.get("task_id"))
        phase_id = _as_str(task.get("phase_id")) or "phase-1"
        if not task_id:
            continue
        evidence_path = _task_evidence_path(repo_root, task)
        if not evidence_path.exists():
            task["status"] = "blocked"
            task["owner_slot"] = None
            _append_task_blocker(
                task,
                summary=f"task evidence missing for {task_id}",
                details={
                    "code": "task_evidence_missing",
                    "evidence_path": str(evidence_path),
                },
            )
            warnings.append(
                {
                    "code": "task_evidence_missing",
                    "message": f"missing TASK_EVIDENCE.json for {task_id}: {evidence_path}",
                    "stage": "build_loop",
                }
            )
            continue
        try:
            payload = _read_json(evidence_path)
        except OpError as exc:
            task["status"] = "blocked"
            task["owner_slot"] = None
            _append_task_blocker(
                task,
                summary=f"task evidence invalid for {task_id}",
                details={
                    "code": "task_evidence_invalid",
                    "reason": exc.message,
                    "evidence_path": str(evidence_path),
                },
            )
            warnings.append(
                {
                    "code": "task_evidence_invalid",
                    "message": f"invalid TASK_EVIDENCE.json for {task_id}: {exc.message}",
                    "stage": "build_loop",
                }
            )
            continue
        if not isinstance(payload, dict):
            task["status"] = "blocked"
            task["owner_slot"] = None
            _append_task_blocker(
                task,
                summary=f"task evidence invalid for {task_id}",
                details={
                    "code": "task_evidence_invalid",
                    "reason": "payload_not_object",
                    "evidence_path": str(evidence_path),
                },
            )
            warnings.append(
                {
                    "code": "task_evidence_invalid",
                    "message": f"TASK_EVIDENCE.json for {task_id} must be object JSON",
                    "stage": "build_loop",
                }
            )
            continue
        if _normalize_task_evidence_payload(payload):
            try:
                _atomic_write_json(evidence_path, payload)
            except OSError as exc:
                warnings.append(
                    {
                        "code": "task_evidence_normalization_write_failed",
                        "message": f"failed to persist normalized TASK_EVIDENCE for {task_id}: {exc}",
                        "stage": "build_loop",
                    }
                )
            else:
                warnings.append(
                    {
                        "code": "task_evidence_normalized",
                        "message": f"normalized TASK_EVIDENCE summary.result for {task_id}",
                        "stage": "build_loop",
                        "task_id": task_id,
                    }
                )
        validation_errors = _validate_task_evidence_payload(payload, task_id, phase_id)
        if validation_errors:
            task["status"] = "blocked"
            task["owner_slot"] = None
            _append_task_blocker(
                task,
                summary=f"task evidence schema invalid for {task_id}",
                details={
                    "code": "task_evidence_invalid",
                    "validation_errors": validation_errors,
                    "evidence_path": str(evidence_path),
                },
            )
            warnings.append(
                {
                    "code": "task_evidence_invalid",
                    "message": f"TASK_EVIDENCE schema invalid for {task_id}",
                    "stage": "build_loop",
                    "details": validation_errors,
                }
            )
            continue

        evidence = task.get("evidence")
        if not isinstance(evidence, dict):
            evidence = {}
            task["evidence"] = evidence
        evidence_ref = os.path.relpath(str(evidence_path), str(repo_root))
        evidence["task_evidence_ref"] = evidence_ref
        evidence["dev_ready_evidence_ref"] = evidence_ref

        verify_results = []
        for section in ("dev", "test"):
            block = payload.get(section) if isinstance(payload.get(section), dict) else {}
            rows = block.get("verify_results")
            if isinstance(rows, list):
                verify_results.extend(rows)
        evidence["verify_results"] = verify_results
        test_block = payload.get("test") if isinstance(payload.get("test"), dict) else {}
        evidence["uat_results"] = test_block.get("uat_results") if isinstance(test_block.get("uat_results"), list) else []
        if not _as_str(task.get("last_progress_at")):
            task["last_progress_at"] = _as_str(payload.get("updated_at")) or utc_now_iso()

        gate = payload["gate"]
        review = payload["review"]
        summary = payload["summary"]
        if _as_bool_field(gate.get("ready_for_review")):
            task["status"] = TASK_STATUS_TESTS_DONE
            task["owner_slot"] = None
        if (_as_str(review.get("decision")) or "").lower() in {"accepted", "approved", "ready_for_merge", "pass"}:
            task["status"] = TASK_STATUS_REVIEW_DONE
            task["owner_slot"] = None
        if (_as_str(review.get("status")) or "").lower() in {"done", "completed", "review_done"}:
            task["status"] = TASK_STATUS_REVIEW_DONE
            task["owner_slot"] = None
        if _as_bool_field(gate.get("ready_for_test")) and _normalize_task_status(task.get("status")) in {
            TASK_STATUS_PENDING,
            TASK_STATUS_DEV_WORKING,
            TASK_STATUS_BLOCKED,
        }:
            task["status"] = TASK_STATUS_DEV_DONE
            task["owner_slot"] = None
        summary_result = (_as_str(summary.get("result")) or "").lower()
        reason_codes = summary.get("reason_codes") if isinstance(summary.get("reason_codes"), list) else []
        is_not_started_placeholder = _is_not_started_evidence_placeholder(payload, summary_result, reason_codes)
        if summary_result in {"fail", "blocked"} and not is_not_started_placeholder and _normalize_task_status(task.get("status")) != TASK_STATUS_REVIEW_DONE:
            if not _as_bool_field(gate.get("ready_for_test")) and not _as_bool_field(gate.get("ready_for_review")):
                task["status"] = TASK_STATUS_BLOCKED
                task["owner_slot"] = None

        plan_task = plan_map.get(task_id) if isinstance(plan_map.get(task_id), dict) else {}
        if isinstance(plan_task, dict) and not task.get("requirement_ids"):
            task["requirement_ids"] = [
                rid
                for rid in ((_as_str(item) for item in plan_task.get("requirement_ids", [])))
                if rid
            ]
    return warnings


def _load_gaps_payload(path: Path, plan_id: str) -> dict[str, Any]:
    if not path.exists():
        return {
            "schema_version": SCHEMA_VERSION,
            "plan_id": plan_id,
            "updated_at": utc_now_iso(),
            "gaps": [],
        }
    try:
        payload = _read_json(path)
    except OpError:
        return {
            "schema_version": SCHEMA_VERSION,
            "plan_id": plan_id,
            "updated_at": utc_now_iso(),
            "gaps": [],
        }
    if not isinstance(payload, dict):
        return {
            "schema_version": SCHEMA_VERSION,
            "plan_id": plan_id,
            "updated_at": utc_now_iso(),
            "gaps": [],
        }
    gaps = payload.get("gaps")
    if not isinstance(gaps, list):
        payload["gaps"] = []
    payload.setdefault("schema_version", SCHEMA_VERSION)
    payload["plan_id"] = _as_str(payload.get("plan_id")) or plan_id
    payload["updated_at"] = utc_now_iso()
    return payload


def _default_gap_row(
    *,
    plan_id: str,
    phase_id: str,
    task_id: str,
    requirement_id: str | None,
    result: str,
    evidence_ref: str,
    reason: str,
    gap_id: str,
    severity: str = "high",
    category: str = "other",
    reason_codes: list[str] | None = None,
) -> dict[str, Any]:
    closure_task_id = f"GAPFIX-{_sha256(gap_id)[:8].upper()}"
    now = utc_now_iso()
    normalized_reason_codes = [code for code in (_as_str(item) for item in (reason_codes or [])) if code]
    if not normalized_reason_codes:
        normalized_reason_codes = ["gap_detected"]
    return {
        "gap_id": gap_id,
        "phase_id": phase_id,
        "task_id": task_id,
        "requirement_id": requirement_id,
        "severity": severity,
        "result": result,
        "evidence_ref": evidence_ref,
        "opened_at": now,
        "status": "open",
        "reason": reason,
        "category": category,
        "reason_codes": normalized_reason_codes,
        "retry_count": 0,
        "escalated": False,
        "escalated_at": None,
        "closure_task_id": closure_task_id,
        "last_seen_open_at": now,
        "closure_required": True,
        "closure_evidence_ref": None,
        "closed_by_task_id": None,
        "closed_at": None,
        "resolution_candidate_at": None,
    }


def _normalize_gap_metadata(row: dict[str, Any]) -> None:
    reason = (_as_str(row.get("reason")) or "").lower()
    result = (_as_str(row.get("result")) or "").lower()
    requirement_id = _as_str(row.get("requirement_id"))
    category = _as_str(row.get("category"))
    if not category:
        if "verify command not passed" in reason:
            category = "verify_missing"
        elif "uat requirement not passed" in reason:
            category = "uat_missing"
        elif "task state blocked" in reason or (result == "blocked" and not requirement_id):
            category = "task_blocked"
        else:
            category = "other"
        row["category"] = category
    else:
        row["category"] = category

    reason_codes_raw = row.get("reason_codes")
    reason_codes = (
        [code for code in (_as_str(item) for item in reason_codes_raw) if code]
        if isinstance(reason_codes_raw, list)
        else []
    )
    if not reason_codes:
        category_to_code = {
            "verify_missing": "verify_command_not_passed",
            "uat_missing": "uat_requirement_not_passed",
            "task_blocked": "task_state_blocked",
            "other": "gap_detected",
        }
        reason_codes = [category_to_code.get(category, "gap_detected")]
    row["reason_codes"] = reason_codes


def _derive_gap_requirement_ids(
    gap_row: dict[str, Any],
    plan_task_map: dict[str, dict[str, Any]],
    task_map: dict[str, dict[str, Any]],
) -> tuple[list[str], bool]:
    requirement_id = _as_str(gap_row.get("requirement_id"))
    if requirement_id:
        return [requirement_id], False
    task_id = _as_str(gap_row.get("task_id"))
    req_ids: list[str] = []
    if task_id:
        plan_task = plan_task_map.get(task_id)
        if isinstance(plan_task, dict):
            req_ids.extend(
                rid
                for rid in ((_as_str(item) for item in plan_task.get("requirement_ids", [])))
                if rid
            )
        task = task_map.get(task_id)
        if isinstance(task, dict):
            req_ids.extend(
                rid
                for rid in ((_as_str(item) for item in task.get("requirement_ids", [])))
                if rid
            )
    out: list[str] = []
    seen: set[str] = set()
    for rid in sorted(req_ids):
        if rid in seen:
            continue
        seen.add(rid)
        out.append(rid)
    if out:
        return out, False
    return ["REQ-GAP-CLOSURE"], True


def _append_task_blocker(task: dict[str, Any], *, summary: str, details: dict[str, Any] | None = None) -> None:
    blockers = task.get("blockers")
    if not isinstance(blockers, list):
        blockers = []
        task["blockers"] = blockers
    now = utc_now_iso()
    details_payload = details if isinstance(details, dict) else {}
    fingerprint_payload = {
        "summary": summary,
        "code": _as_str(details_payload.get("code")) or "",
        "evidence_path": _as_str(details_payload.get("evidence_path")) or "",
        "reason": _as_str(details_payload.get("reason")) or "",
    }
    fingerprint = _sha256(json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")))[:16]
    for item in blockers:
        if not isinstance(item, dict):
            continue
        if _as_str(item.get("fingerprint")) != fingerprint:
            continue
        item["last_seen_at"] = now
        item["occurrences"] = int(item.get("occurrences") or 1) + 1
        if isinstance(details, dict):
            item["details"] = details
        return
    row: dict[str, Any] = {
        "timestamp": now,
        "first_seen_at": now,
        "last_seen_at": now,
        "occurrences": 1,
        "fingerprint": fingerprint,
        "summary": summary,
    }
    if isinstance(details, dict):
        row["details"] = details
    blockers.append(row)
    while len(blockers) > 25:
        blockers.pop(0)


def _normalize_task_evidence_payload(payload: dict[str, Any]) -> bool:
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        return False
    changed = False
    result = (_as_str(summary.get("result")) or "").lower()
    canonical = {
        "ready_for_test": "pass",
        "ready_for_review": "pass",
        "ready_for_phase_exit": "pass",
    }.get(result)
    if canonical and canonical != result:
        summary["result"] = canonical
        changed = True
    reason_codes = summary.get("reason_codes")
    if not isinstance(reason_codes, list):
        reason_codes = []
        changed = True
    cleaned: list[str] = []
    placeholder_aliases = {
        "awaiting_execution",
        "awaiting_start",
        "pending_execution",
        "not_executed",
        "not_started",
    }
    map_placeholder_aliases = result == "blocked"
    for item in reason_codes:
        raw = _as_str(item).strip()
        if not raw:
            changed = True
            continue
        normalized = raw.lower().replace("-", "_").replace(" ", "_")
        code = "not_started" if map_placeholder_aliases and normalized in placeholder_aliases else raw
        if code in cleaned:
            if code != raw:
                changed = True
            continue
        if code != raw:
            changed = True
        cleaned.append(code)
    if canonical and "normalized_noncanonical_result" not in cleaned:
        cleaned.append("normalized_noncanonical_result")
        changed = True
    if summary.get("reason_codes") != cleaned:
        changed = True
    summary["reason_codes"] = cleaned
    payload["summary"] = summary
    return changed


def _is_not_started_evidence_placeholder(payload: dict[str, Any], summary_result: str, reason_codes: list[Any]) -> bool:
    if summary_result != "blocked":
        return False
    normalized_codes = [
        _as_str(item).strip().lower().replace("-", "_").replace(" ", "_")
        for item in reason_codes
        if _as_str(item).strip()
    ]
    if not normalized_codes:
        return False
    not_started_codes = {
        "not_started",
        "awaiting_execution",
        "awaiting_start",
        "pending_execution",
        "not_executed",
    }
    if any(code not in not_started_codes for code in normalized_codes):
        return False

    gate = payload.get("gate") if isinstance(payload.get("gate"), dict) else {}
    if _as_bool_field(gate.get("ready_for_test")) or _as_bool_field(gate.get("ready_for_review")) or _as_bool_field(gate.get("ready_for_phase_exit")):
        return False

    dev = payload.get("dev") if isinstance(payload.get("dev"), dict) else {}
    test = payload.get("test") if isinstance(payload.get("test"), dict) else {}
    review = payload.get("review") if isinstance(payload.get("review"), dict) else {}

    activity_fields = (
        dev.get("checks"),
        dev.get("verify_results"),
        dev.get("blockers"),
        dev.get("artifacts"),
        test.get("checks"),
        test.get("verify_results"),
        test.get("uat_results"),
        test.get("blockers"),
        test.get("artifacts"),
        review.get("blockers"),
        review.get("artifacts"),
    )
    for field in activity_fields:
        if isinstance(field, list) and field:
            return False

    review_decision = (_as_str(review.get("decision")) or "").strip().lower()
    review_status = (_as_str(review.get("status")) or "").strip().lower()
    if review_decision in {"accepted", "approved", "ready_for_merge", "pass"}:
        return False
    if review_status in {"done", "completed", "review_done"}:
        return False
    return True


def _default_gaps_payload(plan_id: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "plan_id": plan_id,
        "updated_at": utc_now_iso(),
        "gaps": [],
    }


def _default_gap_closure_payload(plan_id: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "plan_id": plan_id,
        "generated_at": utc_now_iso(),
        "tasks": [],
    }


def _load_gaps_payload_strict(path: Path, plan_id: str, *, code: str, stage: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    warnings: list[dict[str, Any]] = []
    payload = _default_gaps_payload(plan_id)
    if not path.exists():
        warnings.append(
            {
                "code": code,
                "message": "GAPS.json is missing",
                "stage": stage,
                "artifact": str(path),
            }
        )
        return payload, warnings
    try:
        parsed = _read_json(path)
    except OpError as exc:
        warnings.append(
            {
                "code": code,
                "message": f"GAPS.json unreadable: {exc.message}",
                "stage": stage,
                "artifact": str(path),
            }
        )
        return payload, warnings
    if not isinstance(parsed, dict):
        warnings.append(
            {
                "code": code,
                "message": "GAPS.json must be a JSON object",
                "stage": stage,
                "artifact": str(path),
            }
        )
        return payload, warnings
    payload = dict(parsed)
    if not isinstance(payload.get("gaps"), list):
        warnings.append(
            {
                "code": code,
                "message": "GAPS.json field 'gaps' must be a list",
                "stage": stage,
                "artifact": str(path),
            }
        )
        payload["gaps"] = []
    payload.setdefault("schema_version", SCHEMA_VERSION)
    payload["plan_id"] = _as_str(payload.get("plan_id")) or plan_id
    payload["updated_at"] = utc_now_iso()
    return payload, warnings


def _load_gap_closure_payload_strict(path: Path, plan_id: str, *, code: str, stage: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    warnings: list[dict[str, Any]] = []
    payload = _default_gap_closure_payload(plan_id)
    if not path.exists():
        warnings.append(
            {
                "code": code,
                "message": "GAP_CLOSURE_PLAN_PACKETS.json is missing",
                "stage": stage,
                "artifact": str(path),
            }
        )
        return payload, warnings
    try:
        parsed = _read_json(path)
    except OpError as exc:
        warnings.append(
            {
                "code": code,
                "message": f"GAP_CLOSURE_PLAN_PACKETS.json unreadable: {exc.message}",
                "stage": stage,
                "artifact": str(path),
            }
        )
        return payload, warnings
    if not isinstance(parsed, dict):
        warnings.append(
            {
                "code": code,
                "message": "GAP_CLOSURE_PLAN_PACKETS.json must be a JSON object",
                "stage": stage,
                "artifact": str(path),
            }
        )
        return payload, warnings
    payload = dict(parsed)
    if not isinstance(payload.get("tasks"), list):
        warnings.append(
            {
                "code": code,
                "message": "GAP_CLOSURE_PLAN_PACKETS.json field 'tasks' must be a list",
                "stage": stage,
                "artifact": str(path),
            }
        )
        payload["tasks"] = []
    plan_id_value = _as_str(payload.get("plan_id"))
    if not plan_id_value:
        warnings.append(
            {
                "code": code,
                "message": "GAP_CLOSURE_PLAN_PACKETS.json field 'plan_id' must be a non-empty string",
                "stage": stage,
                "artifact": str(path),
            }
        )
    payload.setdefault("schema_version", SCHEMA_VERSION)
    payload["plan_id"] = plan_id_value or plan_id
    payload["generated_at"] = utc_now_iso()
    return payload, warnings


def _closure_task_resolved(repo_root: Path, task: dict[str, Any]) -> tuple[bool, str | None]:
    status = (_as_str(task.get("status")) or "").lower()
    if status != "review_done":
        return False, None
    evidence_path = _task_evidence_path(repo_root, task)
    if not evidence_path.exists():
        return False, None
    try:
        payload = _read_json(evidence_path)
    except OpError:
        return False, None
    if not isinstance(payload, dict):
        return False, None
    task_id = _as_str(task.get("task_id")) or "TASK-UNKNOWN"
    phase_id = _as_str(task.get("phase_id")) or "phase-1"
    if _validate_task_evidence_payload(payload, task_id, phase_id):
        return False, None
    review = payload.get("review") if isinstance(payload.get("review"), dict) else {}
    gate = payload.get("gate") if isinstance(payload.get("gate"), dict) else {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    decision = (_as_str(review.get("decision")) or "").lower()
    result = (_as_str(summary.get("result")) or "").lower()
    ready = _as_bool_field(gate.get("ready_for_phase_exit"))
    if decision not in {"accepted", "approved", "ready_for_merge", "pass"}:
        return False, None
    if result != "pass" or not ready:
        return False, None
    return True, os.path.relpath(str(evidence_path), str(repo_root))


def _recover_gap_artifacts_for_build(
    repo_root: Path,
    plan_packets: dict[str, Any],
    task_state: dict[str, Any],
    build_state: dict[str, Any],
    plan_id: str,
    gaps_invalid: bool,
    gap_closure_invalid: bool,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    warnings: list[dict[str, Any]] = []
    recovered_files: list[str] = []
    backup_paths: list[str] = []
    try:
        gaps_path = _repo_path(repo_root, GAPS_JSON)
        gap_closure_path = _repo_path(repo_root, GAP_CLOSURE_PLAN_PACKETS_JSON)
        if gaps_invalid:
            recovered_files.append(str(gaps_path))
            if gaps_path.exists():
                backup = _backup_corrupt_file(gaps_path)
                backup_paths.append(str(backup))
            warnings.append(
                {
                    "code": "gaps_artifact_recovered",
                    "message": "Recovered malformed GAPS.json via deterministic rebuild",
                    "stage": "build_preflight",
                    "artifact": str(gaps_path),
                }
            )
        if gap_closure_invalid:
            recovered_files.append(str(gap_closure_path))
            if gap_closure_path.exists():
                backup = _backup_corrupt_file(gap_closure_path)
                backup_paths.append(str(backup))
            warnings.append(
                {
                    "code": "gap_closure_artifact_recovered",
                    "message": "Recovered malformed GAP_CLOSURE_PLAN_PACKETS.json via deterministic rebuild",
                    "stage": "build_preflight",
                    "artifact": str(gap_closure_path),
                }
            )
        prior_open_gap_ids = [
            gap_id
            for gap_id in (_as_str(item) for item in build_state.get("open_gap_ids", []))
            if gap_id
        ]
        gaps_payload, gap_closure_payload = _refresh_gap_artifacts(repo_root, plan_packets, task_state, build_state)
        if prior_open_gap_ids:
            existing_rows = gaps_payload.get("gaps") if isinstance(gaps_payload.get("gaps"), list) else []
            existing_by_id = {
                _as_str(item.get("gap_id")): item
                for item in existing_rows
                if isinstance(item, dict) and _as_str(item.get("gap_id"))
            }
            preserved_rows: list[dict[str, Any]] = []
            phase_id = _as_str(build_state.get("active_gap_closure_phase_id")) or "phase-1"
            now = utc_now_iso()
            task_map = _task_by_id(task_state)
            plan_task_map = _plan_task_map(plan_packets)
            for gap_id in prior_open_gap_ids:
                if gap_id in existing_by_id:
                    continue
                row = _default_gap_row(
                    plan_id=plan_id,
                    phase_id=phase_id,
                    task_id="TASK-UNKNOWN",
                    requirement_id=None,
                    result="blocked",
                    evidence_ref=str(TASK_EXECUTION_STATE_JSON),
                    reason="preserved open gap from prior build state after artifact recovery",
                    gap_id=gap_id,
                    category="task_blocked",
                    reason_codes=["gap_preserved_from_build_state"],
                )
                row["updated_at"] = now
                preserved_rows.append(row)
            if preserved_rows:
                existing_rows.extend(preserved_rows)
                existing_rows.sort(key=lambda item: (_as_str(item.get("status")) != "open", _as_str(item.get("gap_id")) or ""))
                gaps_payload["gaps"] = existing_rows
                _atomic_write_json(gaps_path, gaps_payload)
                warnings.append(
                    {
                        "code": "gaps_artifact_recovered",
                        "message": f"Preserved {len(preserved_rows)} sticky open gap(s) from build state during recovery",
                        "stage": "build_preflight",
                        "artifact": str(gaps_path),
                    }
                )
            closure_tasks = gap_closure_payload.get("tasks") if isinstance(gap_closure_payload.get("tasks"), list) else []
            existing_closure_by_source = {
                _as_str(item.get("source_gap_id"))
                for item in closure_tasks
                if isinstance(item, dict) and _as_str(item.get("source_gap_id"))
            }
            closure_added = False
            for row in existing_rows:
                if not isinstance(row, dict):
                    continue
                _normalize_gap_metadata(row)
                gap_id = _as_str(row.get("gap_id"))
                if not gap_id or _as_str(row.get("status")) != "open":
                    continue
                if gap_id in existing_closure_by_source:
                    continue
                task_id = _as_str(row.get("task_id")) or "TASK-UNKNOWN"
                phase_id = _as_str(row.get("phase_id")) or "phase-1"
                closure_task_id = _as_str(row.get("closure_task_id")) or f"GAPFIX-{_sha256(gap_id)[:8].upper()}"
                depends_on = [task_id] if task_id and not task_id.startswith("GAPFIX-") and task_id != "TASK-UNKNOWN" else []
                req_ids, fallback_used = _derive_gap_requirement_ids(row, plan_task_map, task_map)
                closure_tasks.append(
                    {
                        "task_id": closure_task_id,
                        "phase_id": phase_id,
                        "source_gap_id": gap_id,
                        "title": f"Close gap {gap_id}",
                        "requirement_ids": req_ids,
                        "requirement_fallback_used": fallback_used,
                        "depends_on": depends_on,
                        "must_haves": [f"Resolve {row.get('reason') or gap_id}"],
                        "verify_commands": ["python3 -m pytest"],
                        "is_gap_closure": True,
                    }
                )
                existing_closure_by_source.add(gap_id)
                closure_added = True
            if closure_added:
                gap_closure_payload["tasks"] = closure_tasks
                _atomic_write_json(gap_closure_path, gap_closure_payload)
        _ensure_gap_closure_task_state(repo_root, task_state, gap_closure_payload, plan_id)
        build_state["gap_artifact_recovery"] = {
            "last_recovery_at": utc_now_iso(),
            "recovered_files": recovered_files,
            "backup_paths": backup_paths,
            "reason": "malformed_gap_artifacts",
        }
        return gaps_payload, gap_closure_payload, warnings
    except Exception as exc:  # noqa: BLE001
        raise OpError(
            "gap_artifact_recovery_failed",
            f"failed to recover gap artifacts: {exc}",
            stage="build_preflight",
        ) from exc


def _gap_id(plan_id: str, phase_id: str, task_id: str, scope_key: str, result: str) -> str:
    digest = _sha256(f"{plan_id}|{phase_id}|{task_id}|{scope_key}|{result}")[:10]
    return f"gap-{digest}"


def _refresh_gap_artifacts(repo_root: Path, plan_packets: dict[str, Any], task_state: dict[str, Any], build_state: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    plan_id = _as_str(plan_packets.get("plan_id")) or "plan-unknown"
    task_map = _task_by_id(task_state)
    plan_task_map = _plan_task_map(plan_packets)
    retry_attempts = build_state.get("gap_retry_attempts")
    if not isinstance(retry_attempts, dict):
        retry_attempts = {}
        build_state["gap_retry_attempts"] = retry_attempts
    exhausted_ids_raw = build_state.get("gap_retry_exhausted_ids")
    exhausted_ids = (
        [item for item in (_as_str(v) for v in exhausted_ids_raw) if item]
        if isinstance(exhausted_ids_raw, list)
        else []
    )
    exhausted_set = set(exhausted_ids)
    build_state["gap_retry_exhausted_ids"] = sorted(exhausted_set)
    retry_policy = build_state.get("gap_retry_policy")
    if not isinstance(retry_policy, dict):
        retry_policy = {"max_attempts": 5}
        build_state["gap_retry_policy"] = retry_policy
    max_retry_attempts = _coerce_nonneg_int(retry_policy.get("max_attempts"), default=5)
    build_state["gap_retry_policy"] = {"max_attempts": max(1, max_retry_attempts)}
    gaps_path = _repo_path(repo_root, GAPS_JSON)
    existing = _load_gaps_payload(gaps_path, plan_id)
    existing_by_id: dict[str, dict[str, Any]] = {}
    for item in existing.get("gaps", []):
        if not isinstance(item, dict):
            continue
        gap_id = _as_str(item.get("gap_id"))
        if gap_id:
            task_id = _as_str(item.get("task_id")) or ""
            # Never allow recursive gapfix-origin rows to participate in closure generation.
            if task_id.startswith("GAPFIX-"):
                continue
            existing_by_id[gap_id] = dict(item)

    closure_task_by_gap: dict[str, dict[str, Any]] = {}
    for task in task_map.values():
        if not isinstance(task, dict):
            continue
        if not bool(task.get("is_gap_closure")):
            continue
        source_gap_id = _as_str(task.get("source_gap_id"))
        if source_gap_id:
            closure_task_by_gap[source_gap_id] = task

    active_rows: dict[str, dict[str, Any]] = {}
    for task_id, plan_task in plan_task_map.items():
        if not isinstance(plan_task, dict):
            continue
        task = task_map.get(task_id)
        if not isinstance(task, dict):
            continue
        if bool(task.get("is_gap_closure")) or bool(plan_task.get("is_gap_closure")):
            continue
        phase_id = _as_str(plan_task.get("phase_id")) or _as_str(task.get("phase_id")) or "phase-1"
        task_status = _normalize_task_status(task.get("status"))
        evidence = task.get("evidence") if isinstance(task.get("evidence"), dict) else {}
        evidence_ref = _as_str(evidence.get("task_evidence_ref")) or str(_canonical_task_evidence_rel(task_id))
        verify_required = {
            cmd
            for cmd in ((_as_str(item) for item in plan_task.get("verify_commands", [])))
            if cmd
        }
        verify_passed = set()
        for item in evidence.get("verify_results", []):
            if isinstance(item, str):
                text = item.strip()
                if text:
                    verify_passed.add(text)
            elif isinstance(item, dict) and _as_bool_field(item.get("passed")):
                cmd = _as_str(item.get("command"))
                if cmd:
                    verify_passed.add(cmd)
        if task_status in {TASK_STATUS_TESTS_DONE, TASK_STATUS_REVIEW_DONE, TASK_STATUS_BLOCKED}:
            for cmd in sorted(verify_required - verify_passed):
                gap_id = _gap_id(plan_id, phase_id, task_id, f"verify:{cmd}", "fail")
                active_rows[gap_id] = _default_gap_row(
                    plan_id=plan_id,
                    phase_id=phase_id,
                    task_id=task_id,
                    requirement_id=None,
                    result="fail",
                    evidence_ref=evidence_ref,
                    reason=f"verify command not passed: {cmd}",
                    gap_id=gap_id,
                    category="verify_missing",
                    reason_codes=["verify_command_not_passed"],
                )

        requirement_ids = [
            rid
            for rid in ((_as_str(item) for item in plan_task.get("requirement_ids", [])))
            if rid
        ]
        passed_uat: set[str] = set()
        for item in evidence.get("uat_results", []):
            if not isinstance(item, dict) or not _as_bool_field(item.get("passed")):
                continue
            rid = _as_str(item.get("requirement_id"))
            if rid:
                passed_uat.add(rid)
            rids = item.get("requirement_ids")
            if isinstance(rids, list):
                for rid_item in rids:
                    rid_text = _as_str(rid_item)
                    if rid_text:
                        passed_uat.add(rid_text)
        if task_status in {TASK_STATUS_REVIEW_DONE, TASK_STATUS_BLOCKED}:
            for rid in sorted(set(requirement_ids) - passed_uat):
                gap_id = _gap_id(plan_id, phase_id, task_id, f"uat:{rid}", "blocked")
                active_rows[gap_id] = _default_gap_row(
                    plan_id=plan_id,
                    phase_id=phase_id,
                    task_id=task_id,
                    requirement_id=rid,
                    result="blocked",
                    evidence_ref=evidence_ref,
                    reason=f"UAT requirement not passed: {rid}",
                    gap_id=gap_id,
                    category="uat_missing",
                    reason_codes=["uat_requirement_not_passed"],
                )

        if _normalize_task_status(task.get("status")) == TASK_STATUS_BLOCKED:
            gap_id = _gap_id(plan_id, phase_id, task_id, "task:blocked", "blocked")
            active_rows[gap_id] = _default_gap_row(
                plan_id=plan_id,
                phase_id=phase_id,
                task_id=task_id,
                requirement_id=None,
                result="blocked",
                evidence_ref=evidence_ref,
                reason="task state blocked",
                gap_id=gap_id,
                category="task_blocked",
                reason_codes=["task_state_blocked"],
            )

    now = utc_now_iso()
    merged_by_id: dict[str, dict[str, Any]] = {}
    for gap_id, row in active_rows.items():
        prior = existing_by_id.get(gap_id, {})
        merged = dict(row)
        merged["opened_at"] = _as_str(prior.get("opened_at")) or row["opened_at"]
        merged["updated_at"] = now
        merged["status"] = "open"
        merged["closure_task_id"] = _as_str(prior.get("closure_task_id")) or _as_str(merged.get("closure_task_id")) or f"GAPFIX-{_sha256(gap_id)[:8].upper()}"
        merged["last_seen_open_at"] = now
        merged["closure_required"] = True
        merged["closure_evidence_ref"] = None
        merged["closed_by_task_id"] = None
        merged["closed_at"] = None
        merged["resolution_candidate_at"] = None
        retry_count = _coerce_nonneg_int(retry_attempts.get(gap_id, 0), default=0)
        is_escalated = gap_id in exhausted_set
        merged["retry_count"] = max(0, retry_count)
        merged["escalated"] = is_escalated
        merged["escalated_at"] = (_as_str(prior.get("escalated_at")) or now) if is_escalated else None
        _normalize_gap_metadata(merged)
        merged_by_id[gap_id] = merged

    for gap_id, prior in existing_by_id.items():
        if gap_id in merged_by_id:
            continue
        row = dict(prior)
        row["gap_id"] = gap_id
        row["updated_at"] = now
        row["plan_id"] = plan_id
        row["closure_task_id"] = _as_str(row.get("closure_task_id")) or f"GAPFIX-{_sha256(gap_id)[:8].upper()}"
        row["closure_required"] = True
        row["last_seen_open_at"] = (
            _as_str(row.get("last_seen_open_at"))
            or _as_str(row.get("updated_at"))
            or _as_str(row.get("opened_at"))
            or now
        )
        retry_count = _coerce_nonneg_int(retry_attempts.get(gap_id, 0), default=0)
        is_escalated = gap_id in exhausted_set
        row["retry_count"] = max(0, retry_count)
        row["escalated"] = is_escalated
        row["escalated_at"] = (_as_str(row.get("escalated_at")) or now) if is_escalated else None
        _normalize_gap_metadata(row)
        status = (_as_str(row.get("status")) or "open").lower()
        if status == "open":
            closure_task = closure_task_by_gap.get(gap_id)
            resolved = False
            closure_ref: str | None = None
            if isinstance(closure_task, dict):
                resolved, closure_ref = _closure_task_resolved(repo_root, closure_task)
            if resolved:
                row["status"] = "closed"
                row["closed_at"] = _as_str(row.get("closed_at")) or now
                row["closed_by_task_id"] = _as_str(closure_task.get("task_id")) if isinstance(closure_task, dict) else None
                row["closure_evidence_ref"] = closure_ref
                row["resolution_candidate_at"] = now
                row["escalated"] = False
                row["escalated_at"] = None
            else:
                row["status"] = "open"
                row["closed_at"] = None
                row["closed_by_task_id"] = None
                row["closure_evidence_ref"] = None
                row["resolution_candidate_at"] = now
        else:
            row["status"] = "closed"
            row["closed_at"] = _as_str(row.get("closed_at")) or now
            row["closed_by_task_id"] = _as_str(row.get("closed_by_task_id"))
            row["closure_evidence_ref"] = _as_str(row.get("closure_evidence_ref"))
            row["resolution_candidate_at"] = _as_str(row.get("resolution_candidate_at"))
        merged_by_id[gap_id] = row

    merged_gaps = list(merged_by_id.values())
    merged_gaps.sort(key=lambda item: (_as_str(item.get("status")) != "open", _as_str(item.get("gap_id")) or ""))
    gaps_payload = _default_gaps_payload(plan_id)
    gaps_payload["gaps"] = merged_gaps
    _atomic_write_json(gaps_path, gaps_payload)

    open_gap_rows = [item for item in merged_gaps if _as_str(item.get("status")) == "open"]
    active_open_gap_ids = {_as_str(item.get("gap_id")) for item in open_gap_rows if _as_str(item.get("gap_id"))}
    for gap_id in list(retry_attempts.keys()):
        if gap_id not in active_open_gap_ids:
            retry_attempts.pop(gap_id, None)
    build_state["gap_retry_exhausted_ids"] = sorted(gap_id for gap_id in exhausted_set if gap_id in active_open_gap_ids)
    closure_tasks: list[dict[str, Any]] = []
    for gap in sorted(open_gap_rows, key=lambda item: _as_str(item.get("gap_id")) or ""):
        gap_id = _as_str(gap.get("gap_id"))
        phase_id = _as_str(gap.get("phase_id")) or "phase-1"
        task_id = _as_str(gap.get("task_id")) or "TASK-UNKNOWN"
        if not gap_id:
            continue
        closure_task_id = _as_str(gap.get("closure_task_id")) or f"GAPFIX-{_sha256(gap_id)[:8].upper()}"
        req_ids, fallback_used = _derive_gap_requirement_ids(gap, plan_task_map, task_map)
        depends_on = [task_id] if task_id and not task_id.startswith("GAPFIX-") else []
        closure_tasks.append(
            {
                "task_id": closure_task_id,
                "phase_id": phase_id,
                "source_gap_id": gap_id,
                "title": f"Close gap {gap_id}",
                "requirement_ids": req_ids,
                "requirement_fallback_used": fallback_used,
                "depends_on": depends_on,
                "must_haves": [f"Resolve {gap.get('reason') or gap_id}"],
                "verify_commands": ["python3 -m pytest"],
                "is_gap_closure": True,
            }
        )
    closure_payload = _default_gap_closure_payload(plan_id)
    closure_payload["tasks"] = closure_tasks
    _atomic_write_json(_repo_path(repo_root, GAP_CLOSURE_PLAN_PACKETS_JSON), closure_payload)

    build_state["open_gap_ids"] = sorted([_as_str(item.get("gap_id")) for item in open_gap_rows if _as_str(item.get("gap_id"))])
    build_state["last_gap_generation_at"] = utc_now_iso()
    if open_gap_rows:
        build_state["active_gap_closure_phase_id"] = _as_str(open_gap_rows[0].get("phase_id")) or "phase-1"
    else:
        build_state["active_gap_closure_phase_id"] = None
    return gaps_payload, closure_payload


def _merge_plan_with_gap_closure(plan_packets: dict[str, Any], gap_closure_payload: dict[str, Any]) -> dict[str, Any]:
    merged = dict(plan_packets)
    base_tasks = [task for task in plan_packets.get("tasks", []) if isinstance(task, dict)]
    gap_tasks = [task for task in gap_closure_payload.get("tasks", []) if isinstance(task, dict)]
    task_ids = {_as_str(task.get("task_id")) for task in base_tasks if _as_str(task.get("task_id"))}
    merged_tasks = list(base_tasks)
    for task in gap_tasks:
        task_id = _as_str(task.get("task_id"))
        if not task_id or task_id in task_ids:
            continue
        merged_tasks.append(task)
        task_ids.add(task_id)
    merged["tasks"] = merged_tasks
    return merged


def _ensure_gap_closure_task_state(repo_root: Path, task_state: dict[str, Any], gap_closure_payload: dict[str, Any], plan_id: str) -> None:
    existing = _task_by_id(task_state)
    for task in gap_closure_payload.get("tasks", []):
        if not isinstance(task, dict):
            continue
        task_id = _as_str(task.get("task_id"))
        if not task_id or task_id in existing:
            continue
        phase_id = _as_str(task.get("phase_id")) or "phase-1"
        req_ids = [
            rid
            for rid in ((_as_str(item) for item in task.get("requirement_ids", [])))
            if rid
        ]
        rel = _canonical_task_evidence_rel(task_id)
        _atomic_write_json(
            _repo_path(repo_root, rel),
            _default_task_evidence(plan_id, phase_id, task_id, req_ids),
        )
        task_state.setdefault("tasks", []).append(
            {
                "task_id": task_id,
                "phase_id": phase_id,
                "source_gap_id": _as_str(task.get("source_gap_id")),
                "requirement_ids": req_ids,
                "requirement_fallback_used": _as_bool_field(task.get("requirement_fallback_used")),
                "status": TASK_STATUS_PENDING,
                "owner_slot": None,
                "last_progress_at": None,
                "attempts": {"dev": 0, "test": 0, "review": 0},
                "evidence": {
                    "task_evidence_ref": str(rel),
                    "dev_ready_evidence_ref": str(rel),
                    "verify_results": [],
                    "uat_results": [],
                },
                "blockers": [],
                "is_gap_closure": True,
            }
        )


def _normalize_task_gap_rows(task: dict[str, Any]) -> list[dict[str, Any]]:
    raw = task.get("gaps_that_need_patching")
    if not isinstance(raw, list):
        task["gaps_that_need_patching"] = []
        return []
    out: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        gap_id = _as_str(row.get("gap_id"))
        if not gap_id:
            continue
        status = (_as_str(row.get("status")) or "open").lower()
        category = _as_str(row.get("category")) or "other"
        severity = _as_str(row.get("severity")) or "P2"
        stage = _as_str(row.get("stage")) or "dev"
        reason_codes_raw = row.get("reason_codes")
        reason_codes = (
            [code for code in (_as_str(item) for item in reason_codes_raw) if code]
            if isinstance(reason_codes_raw, list)
            else []
        )
        if not reason_codes:
            reason_codes = ["gap_detected"]
        normalized = dict(row)
        normalized["gap_id"] = gap_id
        normalized["status"] = status
        normalized["category"] = category
        normalized["severity"] = severity
        normalized["stage"] = stage
        normalized["reason_codes"] = reason_codes
        normalized["retry_count"] = _coerce_nonneg_int(normalized.get("retry_count"), default=0)
        normalized["max_retries"] = max(1, _coerce_nonneg_int(normalized.get("max_retries"), default=5))
        normalized["created_at"] = _as_str(normalized.get("created_at")) or utc_now_iso()
        normalized["updated_at"] = _as_str(normalized.get("updated_at")) or utc_now_iso()
        normalized["closure_ref"] = _as_str(normalized.get("closure_ref"))
        out.append(normalized)
    task["gaps_that_need_patching"] = out
    return out


def _sync_task_embedded_gaps_from_payload(task_state: dict[str, Any], gaps_payload: dict[str, Any]) -> None:
    task_map = _task_by_id(task_state)
    gap_rows = gaps_payload.get("gaps") if isinstance(gaps_payload.get("gaps"), list) else []
    by_task: dict[str, list[dict[str, Any]]] = {}
    for row in gap_rows:
        if not isinstance(row, dict):
            continue
        task_id = _as_str(row.get("task_id"))
        if not task_id:
            continue
        by_task.setdefault(task_id, []).append(dict(row))
    for task_id, task in task_map.items():
        if not isinstance(task, dict):
            continue
        task["gaps_that_need_patching"] = by_task.get(task_id, [])
        _normalize_task_gap_rows(task)


def _upsert_task_gap(task: dict[str, Any], row: dict[str, Any]) -> None:
    now = utc_now_iso()
    target_gap_id = _as_str(row.get("gap_id"))
    if not target_gap_id:
        return
    rows = _normalize_task_gap_rows(task)
    for item in rows:
        if _as_str(item.get("gap_id")) != target_gap_id:
            continue
        prior_status = (_as_str(item.get("status")) or "open").lower()
        prior_retry_count = _coerce_nonneg_int(item.get("retry_count"), default=0)
        requested_status = (_as_str(row.get("status")) or "open").lower()
        item.update(row)
        item["updated_at"] = now
        item["status"] = _as_str(item.get("status")) or "open"
        requested_retry_count = _coerce_nonneg_int(row.get("retry_count"), default=prior_retry_count)
        if prior_status == "closed" and requested_status == "open":
            item["retry_count"] = max(prior_retry_count + 1, requested_retry_count)
        else:
            item["retry_count"] = requested_retry_count
        item["max_retries"] = max(1, _coerce_nonneg_int(item.get("max_retries"), default=5))
        item["reason_codes"] = [code for code in (_as_str(v) for v in item.get("reason_codes", [])) if code] or ["gap_detected"]
        task["gaps_that_need_patching"] = rows
        return
    inserted = dict(row)
    inserted.setdefault("status", "open")
    inserted.setdefault("retry_count", 0)
    inserted.setdefault("max_retries", 5)
    inserted.setdefault("created_at", now)
    inserted["updated_at"] = now
    inserted["reason_codes"] = [code for code in (_as_str(v) for v in inserted.get("reason_codes", [])) if code] or ["gap_detected"]
    rows.append(inserted)
    task["gaps_that_need_patching"] = rows


def _close_task_gap(task: dict[str, Any], *, gap_id: str, closure_ref: str | None = None) -> None:
    rows = _normalize_task_gap_rows(task)
    now = utc_now_iso()
    for row in rows:
        if _as_str(row.get("gap_id")) != gap_id:
            continue
        row["status"] = "closed"
        row["updated_at"] = now
        reason_codes = [
            code
            for code in (_as_str(item) for item in row.get("reason_codes", []))
            if code
        ]
        if "gap_closed_by_evidence" not in reason_codes:
            reason_codes.append("gap_closed_by_evidence")
        row["reason_codes"] = reason_codes or ["gap_closed_by_evidence"]
        if closure_ref:
            row["closure_ref"] = closure_ref
    task["gaps_that_need_patching"] = rows


def _refresh_task_embedded_gaps(repo_root: Path, plan_packets: dict[str, Any], task_state: dict[str, Any]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    task_map = _task_by_id(task_state)
    plan_map = _plan_task_map(plan_packets)
    plan_id = _as_str(plan_packets.get("plan_id")) or "plan-unknown"
    now = utc_now_iso()
    for task_id, task in task_map.items():
        if not isinstance(task, dict):
            continue
        _normalize_task_gap_rows(task)
        for row in task.get("gaps_that_need_patching", []):
            if isinstance(row, dict) and (_as_str(row.get("status")) or "").lower() == "open":
                row["updated_at"] = now
        phase_id = _as_str(task.get("phase_id")) or "phase-1"
        plan_task = plan_map.get(task_id) if isinstance(plan_map.get(task_id), dict) else {}
        evidence_path = _task_evidence_path(repo_root, task)
        evidence_ref = os.path.relpath(str(evidence_path), str(repo_root))
        status = _normalize_task_status(task.get("status"))
        active_gap_ids: set[str] = set()

        if status == TASK_STATUS_BLOCKED:
            gap_id = _gap_id(plan_id, phase_id, task_id, "task:blocked", "blocked")
            active_gap_ids.add(gap_id)
            _upsert_task_gap(
                task,
                {
                    "gap_id": gap_id,
                    "category": "task_blocked",
                    "severity": "P1",
                    "stage": "dev",
                    "status": "open",
                    "reason_codes": ["task_state_blocked"],
                    "retry_count": 0,
                    "max_retries": 5,
                    "created_at": now,
                    "updated_at": now,
                    "closure_ref": evidence_ref,
                },
            )

        verify_required = {
            cmd
            for cmd in ((_as_str(item) for item in plan_task.get("verify_commands", [])))
            if cmd
        }
        verify_passed: set[str] = set()
        if evidence_path.exists():
            try:
                payload = _read_json(evidence_path)
            except OpError:
                payload = None
            if isinstance(payload, dict):
                verify_passed = _collect_passed_verify_commands(payload)
                uat_passed = _collect_passed_uat_requirement_ids(
                    payload,
                    [rid for rid in ((_as_str(item) for item in plan_task.get("requirement_ids", []))) if rid],
                )
            else:
                uat_passed = set()
        else:
            uat_passed = set()

        if status in {TASK_STATUS_TESTS_DONE, TASK_STATUS_REVIEW_DONE, TASK_STATUS_BLOCKED}:
            for cmd in sorted(verify_required - verify_passed):
                gap_id = _gap_id(plan_id, phase_id, task_id, f"verify:{cmd}", "fail")
                active_gap_ids.add(gap_id)
                _upsert_task_gap(
                    task,
                    {
                        "gap_id": gap_id,
                        "category": "verify_missing",
                        "severity": "P1",
                        "stage": "test",
                        "status": "open",
                        "reason_codes": ["verify_command_not_passed"],
                        "retry_count": 0,
                        "max_retries": 5,
                        "created_at": now,
                        "updated_at": now,
                        "closure_ref": evidence_ref,
                    },
                )

        if status in {TASK_STATUS_REVIEW_DONE, TASK_STATUS_BLOCKED}:
            req_ids = [rid for rid in ((_as_str(item) for item in plan_task.get("requirement_ids", []))) if rid]
            for rid in sorted(set(req_ids) - uat_passed):
                gap_id = _gap_id(plan_id, phase_id, task_id, f"uat:{rid}", "blocked")
                active_gap_ids.add(gap_id)
                _upsert_task_gap(
                    task,
                    {
                        "gap_id": gap_id,
                        "category": "uat_missing",
                        "severity": "P1",
                        "stage": "review",
                        "status": "open",
                        "reason_codes": ["uat_requirement_not_passed"],
                        "retry_count": 0,
                        "max_retries": 5,
                        "created_at": now,
                        "updated_at": now,
                        "closure_ref": evidence_ref,
                    },
                )

        # Deterministic closure for task-local validation gaps:
        # close only when the previously failing condition is no longer true.
        closable_categories = {"verify_missing", "uat_missing", "task_blocked"}
        for row in list(_normalize_task_gap_rows(task)):
            if not isinstance(row, dict):
                continue
            if (_as_str(row.get("status")) or "").lower() != "open":
                continue
            gap_id = _as_str(row.get("gap_id"))
            if not gap_id:
                continue
            category = _as_str(row.get("category")) or "other"
            if category not in closable_categories:
                continue
            if gap_id in active_gap_ids:
                continue
            status_now = _normalize_task_status(task.get("status"))
            if category == "verify_missing":
                verify_resolved_statuses = {
                    TASK_STATUS_TESTS_DONE,
                    TASK_STATUS_REVIEW_DONE,
                    TASK_STATUS_BLOCKED,
                }
                if status_now not in verify_resolved_statuses:
                    continue
                if not verify_required.issubset(verify_passed):
                    continue
            if category == "uat_missing":
                uat_resolved_statuses = {
                    TASK_STATUS_REVIEW_DONE,
                    TASK_STATUS_BLOCKED,
                }
                if status_now not in uat_resolved_statuses:
                    continue
                req_ids = [rid for rid in ((_as_str(item) for item in plan_task.get("requirement_ids", []))) if rid]
                if not set(req_ids).issubset(uat_passed):
                    continue
            if category == "task_blocked":
                blockers = task.get("blockers")
                blockers_present = isinstance(blockers, list) and len(blockers) > 0
                resolved_statuses = {
                    TASK_STATUS_DEV_DONE,
                    TASK_STATUS_TESTING,
                    TASK_STATUS_TESTS_DONE,
                    TASK_STATUS_REVIEWING,
                    TASK_STATUS_REVIEW_DONE,
                }
                if blockers_present or status_now not in resolved_statuses:
                    continue
            _close_task_gap(task, gap_id=gap_id, closure_ref=evidence_ref)
            warnings.append(
                {
                    "code": "task_gap_closed",
                    "message": f"closed embedded task gap {gap_id} after failing condition passed",
                    "stage": "build_loop",
                    "task_id": task_id,
                    "gap_id": gap_id,
                }
            )
    return warnings


def _collect_workstation_validation_refs(repo_root: Path) -> tuple[dict[tuple[str, str], str], dict[str, str]]:
    keyed_refs: dict[tuple[str, str], tuple[float, str]] = {}
    task_refs: dict[str, tuple[float, str]] = {}
    root = repo_root / "reports" / "optimus-prime" / "workstation-manager"
    if not root.exists():
        return {}, {}
    for path in root.glob("attempt-*/WORKSTATION_VALIDATION.json"):
        try:
            payload = _read_json(path)
        except OpError:
            continue
        if not isinstance(payload, dict) or not _as_bool_field(payload.get("ok")):
            continue
        slot = _as_str(payload.get("slot"))
        task_id = _as_str(payload.get("task_id"))
        if not slot or not task_id:
            continue
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = 0.0
        rel_ref = os.path.relpath(str(path), str(repo_root))
        key = (slot, task_id)
        prev = keyed_refs.get(key)
        if prev is None or mtime >= prev[0]:
            keyed_refs[key] = (mtime, rel_ref)
        prev_task = task_refs.get(task_id)
        if prev_task is None or mtime >= prev_task[0]:
            task_refs[task_id] = (mtime, rel_ref)
    return {key: value[1] for key, value in keyed_refs.items()}, {key: value[1] for key, value in task_refs.items()}


def _reconcile_task_embedded_gap_closures(repo_root: Path, task_state: dict[str, Any]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    done_registry_path = _repo_path(repo_root, DONE_TASKS_REGISTRY_JSON)
    merged_by_task: dict[str, dict[str, Any]] = {}
    if done_registry_path.exists():
        try:
            payload = _read_json(done_registry_path)
        except OpError:
            payload = None
        if isinstance(payload, dict):
            merged_rows = payload.get("merged_tasks")
            if isinstance(merged_rows, list):
                merged_by_task = {
                    _as_str(row.get("task_id")): row
                    for row in merged_rows
                    if isinstance(row, dict) and _as_str(row.get("task_id"))
                }

    workstation_refs_by_slot_task, workstation_refs_by_task = _collect_workstation_validation_refs(repo_root)
    for task in task_state.get("tasks", []):
        if not isinstance(task, dict):
            continue
        task_id = _as_str(task.get("task_id")) or "TASK-UNKNOWN"
        rows = list(_normalize_task_gap_rows(task))
        if not rows:
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            if (_as_str(row.get("status")) or "").lower() != "open":
                continue
            gap_id = _as_str(row.get("gap_id"))
            if not gap_id:
                continue
            category = _as_str(row.get("category")) or "other"
            stage = _as_str(row.get("stage")) or "dev"
            closure_ref: str | None = None
            if category == "merge_blocked":
                merged_row = merged_by_task.get(task_id)
                if isinstance(merged_row, dict) and _as_bool_field(merged_row.get("verification_passed")):
                    closure_ref = _as_str(merged_row.get("verification_ref")) or str(DONE_TASKS_REGISTRY_JSON)
            elif stage == "workstation":
                slot = _as_str(row.get("slot")) or _as_str(task.get("owner_slot"))
                if slot:
                    closure_ref = workstation_refs_by_slot_task.get((slot, task_id))
                if not closure_ref:
                    closure_ref = workstation_refs_by_task.get(task_id)
            if not closure_ref:
                continue
            _close_task_gap(task, gap_id=gap_id, closure_ref=closure_ref)
            warnings.append(
                {
                    "code": "task_gap_closed",
                    "message": f"closed embedded task gap {gap_id} after manager evidence passed",
                    "stage": "build_loop",
                    "task_id": task_id,
                    "gap_id": gap_id,
                }
            )
    return warnings


def _open_task_gap_ids(task_state: dict[str, Any], *, phase_id: str | None = None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for task in task_state.get("tasks", []):
        if not isinstance(task, dict):
            continue
        if phase_id and (_as_str(task.get("phase_id")) or "phase-1") != phase_id:
            continue
        for row in _normalize_task_gap_rows(task):
            if (_as_str(row.get("status")) or "").lower() != "open":
                continue
            gap_id = _as_str(row.get("gap_id"))
            if gap_id and gap_id not in seen:
                seen.add(gap_id)
                out.append(gap_id)
    return sorted(out)


def _phase_exit_checks(repo_root: Path, phase_id: str, plan_packets: dict[str, Any], task_state: dict[str, Any]) -> dict[str, Any]:
    plan_tasks = [task for task in plan_packets.get("tasks", []) if isinstance(task, dict) and _as_str(task.get("phase_id")) == phase_id]
    task_map = _task_by_id(task_state)
    all_tasks_review_done = True
    verify_required: set[str] = set()
    verify_passed: set[str] = set()
    uat_required: set[str] = set()
    uat_passed: set[str] = set()
    for plan_task in plan_tasks:
        task_id = _as_str(plan_task.get("task_id"))
        if not task_id:
            continue
        task = task_map.get(task_id)
        if not isinstance(task, dict):
            all_tasks_review_done = False
            continue
        status = _as_str(task.get("status")) or ""
        if _normalize_task_status(status) != TASK_STATUS_REVIEW_DONE:
            all_tasks_review_done = False
        for cmd in plan_task.get("verify_commands", []):
            cmd_text = _as_str(cmd)
            if cmd_text:
                verify_required.add(cmd_text)
        evidence_path = _task_evidence_path(repo_root, task)
        if evidence_path.exists():
            try:
                payload = _read_json(evidence_path)
            except OpError:
                payload = None
            if isinstance(payload, dict):
                verify_passed.update(_collect_passed_verify_commands(payload))
                req_ids = [rid for rid in ((_as_str(item) for item in plan_task.get("requirement_ids", []))) if rid]
                uat_passed.update(_collect_passed_uat_requirement_ids(payload, req_ids))
        for rid in plan_task.get("requirement_ids", []):
            rid_text = _as_str(rid)
            if rid_text:
                uat_required.add(rid_text)
    open_gap_ids = _open_task_gap_ids(task_state, phase_id=phase_id)
    verify_commands_passed = verify_required.issubset(verify_passed)
    uat_matrix_passed = uat_required.issubset(uat_passed)
    checks = {
        "phase_id": phase_id,
        "all_tasks_review_done": all_tasks_review_done,
        "verify_commands_passed": verify_commands_passed,
        "uat_matrix_passed": uat_matrix_passed,
        "zero_open_gaps": len(open_gap_ids) == 0,
        "open_gap_ids": open_gap_ids,
    }
    checks["all_passed"] = (
        checks["all_tasks_review_done"]
        and checks["verify_commands_passed"]
        and checks["uat_matrix_passed"]
        and checks["zero_open_gaps"]
    )
    return checks


def _resolve_active_phase(plan_packets: dict[str, Any], task_state: dict[str, Any], repo_root: Path) -> tuple[str | None, dict[str, Any]]:
    ordered = _ordered_phase_ids(plan_packets)
    if not ordered:
        return None, {}
    all_checks: dict[str, Any] = {}
    for phase_id in ordered:
        checks = _phase_exit_checks(repo_root, phase_id, plan_packets, task_state)
        all_checks[phase_id] = checks
        if not checks.get("all_passed"):
            return phase_id, all_checks
    return None, all_checks


def _read_rate_gate_window(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "reports" / "optimus-prime" / "PROFILE_RATE_REGISTRY.json"
    if not path.exists():
        return {
            "hard_gated": False,
            "min_reset_at": None,
            "min_reset_hours": None,
            "profiles": [],
            "registry_invalid": False,
            "registry_error": None,
        }
    try:
        payload = _read_json(path)
    except OpError as exc:
        return {
            "hard_gated": False,
            "min_reset_at": None,
            "min_reset_hours": None,
            "profiles": [],
            "registry_invalid": True,
            "registry_error": exc.message,
        }
    if not isinstance(payload, dict):
        return {
            "hard_gated": False,
            "min_reset_at": None,
            "min_reset_hours": None,
            "profiles": [],
            "registry_invalid": True,
            "registry_error": "PROFILE_RATE_REGISTRY.json must be a JSON object",
        }
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
        "registry_invalid": False,
        "registry_error": None,
    }


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


def _read_profile_rate_states(repo_root: Path, aliases: list[str]) -> dict[str, dict[str, Any]]:
    states: dict[str, dict[str, Any]] = {}
    default_state = {
        "hard_gated": False,
        "soft_gated": False,
        "score": 50.0,
        "reset_at": None,
    }
    path = _repo_path(repo_root, PROFILE_RATE_REGISTRY_JSON)
    if not path.exists():
        return {alias: dict(default_state) for alias in aliases}
    try:
        payload = _read_json(path)
    except OpError:
        return {alias: dict(default_state) for alias in aliases}
    if not isinstance(payload, dict):
        return {alias: dict(default_state) for alias in aliases}

    profiles_raw = payload.get("profiles")
    profiles_map: dict[str, dict[str, Any]] = {}
    if isinstance(profiles_raw, dict):
        for alias, data in profiles_raw.items():
            if isinstance(data, dict):
                profiles_map[str(alias)] = data
    elif isinstance(profiles_raw, list):
        for idx, data in enumerate(profiles_raw):
            if isinstance(data, dict):
                alias = _as_str(data.get("alias")) or f"profile-{idx+1}"
                profiles_map[alias] = data

    for alias in aliases:
        data = profiles_map.get(alias)
        if not isinstance(data, dict):
            states[alias] = dict(default_state)
            continue
        five = data.get("five_hour") if isinstance(data.get("five_hour"), dict) else data.get("5h")
        weekly = data.get("weekly") if isinstance(data.get("weekly"), dict) else {}
        if not isinstance(five, dict):
            five = {}
        if not isinstance(weekly, dict):
            weekly = {}
        five_remaining = _extract_remaining_percent(five)
        weekly_remaining = _extract_remaining_percent(weekly)
        remaining_candidates = [value for value in (five_remaining, weekly_remaining) if value is not None]
        score = min(remaining_candidates) if remaining_candidates else 50.0

        hard_gated = bool(data.get("hard_gated") or data.get("gated") or five.get("gated") or weekly.get("gated"))
        if (five_remaining is not None and five_remaining <= 1.0) or (weekly_remaining is not None and weekly_remaining <= 1.0):
            hard_gated = True
        soft_gated = bool(data.get("soft_concurrency_gated"))
        if (five_remaining is not None and five_remaining <= 5.0) or (weekly_remaining is not None and weekly_remaining <= 5.0):
            soft_gated = True

        recommended_action = (_as_str(data.get("recommended_action")) or "").lower()
        if recommended_action in {"wind_down", "wait_until_reset"}:
            hard_gated = True
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

        states[alias] = {
            "hard_gated": hard_gated,
            "soft_gated": soft_gated,
            "score": float(score),
            "reset_at": reset_at,
        }
    return states


def _select_profile_alias_for_slot(
    repo_root: Path,
    build_state: dict[str, Any],
    *,
    slot: str,
    slot_count: int,
) -> dict[str, Any]:
    aliases_raw = build_state.get("profile_aliases")
    aliases = (
        [alias for alias in (_as_str(item) for item in aliases_raw) if alias]
        if isinstance(aliases_raw, list)
        else []
    )
    if not aliases:
        return {
            "ok": False,
            "reason": "profile_selection_invalid",
            "warning": {
                "code": "profile_selection_invalid",
                "message": "build state has no profile_aliases; rerun /op-initialize",
                "stage": "build_loop",
            },
        }

    rate_states = _read_profile_rate_states(repo_root, aliases)
    non_gated_aliases = [alias for alias in aliases if not rate_states.get(alias, {}).get("hard_gated")]
    if not non_gated_aliases:
        reset_candidates = [
            _as_str(rate_states.get(alias, {}).get("reset_at"))
            for alias in aliases
            if _as_str(rate_states.get(alias, {}).get("reset_at"))
        ]
        return {
            "ok": False,
            "reason": "profile_assignment_all_hard_gated",
            "warning": {
                "code": "profile_assignment_all_hard_gated",
                "message": "all selected profiles are hard-gated; dispatch skipped",
                "stage": "build_loop",
                "profiles": aliases,
                "reset_at_candidates": reset_candidates,
            },
        }

    assignments = build_state.get("slot_profile_assignments")
    if not isinstance(assignments, dict):
        assignments = {}
        build_state["slot_profile_assignments"] = assignments

    current_alias = _as_str(assignments.get(slot))
    if current_alias and current_alias in non_gated_aliases:
        return {"ok": True, "alias": current_alias}

    assigned_non_gated = {
        alias
        for value in assignments.values()
        for alias in [(_as_str(value))]
        if alias and alias in non_gated_aliases
    }
    candidate_aliases: list[str] = []
    if len(aliases) > max(1, slot_count):
        candidate_aliases = [alias for alias in non_gated_aliases if alias not in assigned_non_gated]

    if not candidate_aliases:
        candidate_aliases = sorted(
            non_gated_aliases,
            key=lambda alias: (-float(rate_states.get(alias, {}).get("score", 50.0)), alias),
        )

    selected_alias = candidate_aliases[0]
    assignments[slot] = selected_alias

    warning: dict[str, Any] | None = None
    if current_alias != selected_alias:
        warning = {
            "code": "profile_assignment_reassigned",
            "message": f"slot {slot} reassigned profile alias: {current_alias or 'unset'} -> {selected_alias}",
            "stage": "build_loop",
            "slot": slot,
            "from_alias": current_alias,
            "to_alias": selected_alias,
        }
    return {"ok": True, "alias": selected_alias, "warning": warning}


def _manager_profile_cycle(
    req: OpRequest,
    *,
    build_state: dict[str, Any],
    profile_selection: dict[str, Any],
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    seed_warnings = _seed_rate_registry_if_missing(
        req.repo_root,
        force_refresh=True,
        emit_success_warning=False,
        profile_selection=profile_selection,
    )
    warnings.extend(seed_warnings)

    selected_aliases = [
        alias for alias in (_as_str(item) for item in profile_selection.get("selected_aliases", [])) if alias
    ]
    if not selected_aliases:
        warnings.append(
            {
                "code": "profile_selection_invalid",
                "message": "PROFILE_SELECTION has no selected aliases",
                "stage": "build_loop",
            }
        )
        return warnings

    rate_states = _read_profile_rate_states(req.repo_root, selected_aliases)
    non_gated = [
        alias
        for alias in selected_aliases
        if not bool(rate_states.get(alias, {}).get("hard_gated"))
        and not bool(rate_states.get(alias, {}).get("soft_gated"))
    ]
    soft_gated = [
        alias
        for alias in selected_aliases
        if not bool(rate_states.get(alias, {}).get("hard_gated"))
        and bool(rate_states.get(alias, {}).get("soft_gated"))
    ]
    preferred_pool = non_gated or soft_gated
    if not preferred_pool:
        build_state["rate_gate_state"] = {
            "hard_gated": True,
            "min_reset_at": None,
            "sleep_until": None,
            "manual_rerun_required": False,
        }
        warnings.append(
            {
                "code": "profile_assignment_all_hard_gated",
                "message": "all selected profiles are hard-gated; dispatch will be skipped",
                "stage": "build_loop",
                "profiles": selected_aliases,
            }
        )
        return warnings

    primary_alias = preferred_pool[0]
    assignments = build_state.get("slot_profile_assignments")
    if not isinstance(assignments, dict):
        assignments = {}
        build_state["slot_profile_assignments"] = assignments

    for slot in ("production-line-manager-1", "branch-manager-1", "dev-1", "test-1", "review-1"):
        previous = _as_str(assignments.get(slot))
        assignments[slot] = primary_alias
        if previous != primary_alias:
            warnings.append(
                {
                    "code": "profile_assignment_reassigned",
                    "message": f"slot {slot} reassigned profile alias: {previous or 'unset'} -> {primary_alias}",
                    "stage": "build_loop",
                    "slot": slot,
                    "from_alias": previous,
                    "to_alias": primary_alias,
                }
            )

    triads = [
        ("dev-2", "test-2", "review-2"),
        ("dev-3", "test-3", "review-3"),
    ]
    triad_alias_candidates = [alias for alias in preferred_pool if alias != primary_alias]
    if not triad_alias_candidates:
        triad_alias_candidates = [primary_alias]
    for idx, triad in enumerate(triads):
        alias = triad_alias_candidates[idx % len(triad_alias_candidates)]
        for slot in triad:
            previous = _as_str(assignments.get(slot))
            assignments[slot] = alias
            if previous != alias:
                warnings.append(
                    {
                        "code": "profile_assignment_reassigned",
                        "message": f"slot {slot} reassigned profile alias: {previous or 'unset'} -> {alias}",
                        "stage": "build_loop",
                        "slot": slot,
                        "from_alias": previous,
                        "to_alias": alias,
                    }
                )

    registry_path = req.repo_root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
    base_payload, workers, shape = _load_worker_registry(registry_path)
    by_slot = {
        _as_str(worker.get("slot")): worker
        for worker in workers
        if isinstance(worker, dict) and _as_str(worker.get("slot"))
    }
    out_workers: list[dict[str, Any]] = []
    for slot in FIXED_WORKER_SLOTS:
        row = by_slot.get(slot)
        if not isinstance(row, dict):
            row = _default_worker_row(slot)
        row["codex_profile_alias"] = _as_str(assignments.get(slot))
        row["updated_at"] = utc_now_iso()
        out_workers.append(row)
    _write_worker_registry(registry_path, base_payload, out_workers, shape if shape in {"dict_list", "dict_dict", "list"} else "dict_list")
    return warnings


def _resolve_test_train_mode(repo_root: Path) -> str:
    path = repo_root / "reports" / "optimus-prime" / "TEST_TRAIN_STATE.json"
    if not path.exists():
        return "off"
    try:
        payload = _read_json(path)
    except OpError:
        return "off"
    if not isinstance(payload, dict):
        return "off"
    mode = (_as_str(payload.get("test_train_mode")) or "off").lower()
    if mode not in {"off", "final-stage", "forced-shared-env"}:
        return "off"
    return mode


def _active_workers_from_snapshot(reports_dir: Path) -> int | None:
    snapshot_path = reports_dir / "STATUS_SNAPSHOT.json"
    if not snapshot_path.exists():
        return None
    try:
        snapshot = _read_json(snapshot_path)
    except OpError:
        return None
    if not isinstance(snapshot, dict):
        return None
    counts = snapshot.get("counts") if isinstance(snapshot.get("counts"), dict) else {}
    active = counts.get("active_workers")
    if isinstance(active, int):
        return max(0, active)
    return None


def _active_workers_count(repo_root: Path) -> int | None:
    reports = repo_root / "reports" / "optimus-prime"
    registry_path = reports / "WORKER_REGISTRY.json"
    if not registry_path.exists():
        return _active_workers_from_snapshot(reports)
    try:
        registry = _read_json(registry_path)
    except OpError:
        return _active_workers_from_snapshot(reports)
    workers: list[dict[str, Any]] = []
    if isinstance(registry, dict):
        raw = registry.get("workers")
        if isinstance(raw, list):
            workers = [item for item in raw if isinstance(item, dict)]
        elif isinstance(raw, dict):
            workers = [item for item in raw.values() if isinstance(item, dict)]
    elif isinstance(registry, list):
        workers = [item for item in registry if isinstance(item, dict)]
    active = 0
    for worker in workers:
        state = (_as_str(worker.get("state")) or _as_str(worker.get("session_state")) or _as_str(worker.get("status")) or "").lower()
        if state in {"running", "active", "busy"}:
            pid = worker.get("dispatch_pid")
            if not isinstance(pid, int) or not _pid_is_running(pid):
                continue
            active += 1
    return active


def _recover_unreadable_worker_registry(repo_root: Path) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    registry_path = repo_root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
    if not registry_path.exists():
        return warnings
    corrupted_reason: str | None = None
    try:
        payload = _read_json(registry_path)
    except OpError as exc:
        corrupted_reason = exc.message
        payload = None
    if corrupted_reason is None:
        if isinstance(payload, dict):
            workers = payload.get("workers")
            if workers is not None and not isinstance(workers, (list, dict)):
                corrupted_reason = "field 'workers' must be list|object"
        elif not isinstance(payload, list):
            corrupted_reason = "payload must be object|list"
    if corrupted_reason is None:
        return warnings
    try:
        _atomic_write_json(registry_path, {"workers": []})
    except OSError as exc:
        warnings.append(
            {
                "code": "worker_registry_recovery_failed_dispatch_allowed",
                "message": (
                    f"WORKER_REGISTRY unreadable/invalid ({corrupted_reason}); "
                    f"recovery failed ({exc}); dispatch remains allowed"
                ),
                "stage": "build_loop",
                "artifact": str(registry_path),
            }
        )
        return warnings
    warnings.append(
        {
            "code": "worker_registry_recovered",
            "message": f"WORKER_REGISTRY unreadable/invalid ({corrupted_reason}); reset to canonical empty registry",
            "stage": "build_loop",
            "artifact": str(registry_path),
        }
    )
    return warnings


def _normalize_dead_worker_registry_entries(repo_root: Path) -> int:
    registry_path = repo_root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
    if not registry_path.exists():
        return 0
    registry_base, workers, registry_shape = _load_worker_registry(registry_path)
    if not workers:
        return 0
    now_iso = utc_now_iso()
    normalized = _reconcile_running_workers_with_pid_state(
        workers,
        now_iso=now_iso,
        reason="build_cycle_dead_pid_pre_dispatch",
    )
    if normalized > 0:
        _write_worker_registry(registry_path, registry_base, workers, registry_shape)
    return normalized


def _load_build_lock_snapshot(repo_root: Path) -> dict[str, Any]:
    lock_path = _repo_path(repo_root, BUILD_LOOP_LOCK)
    snapshot: dict[str, Any] = {
        "exists": False,
        "pid": None,
        "pid_alive": False,
        "lock_id": None,
    }
    if not lock_path.exists():
        return snapshot
    snapshot["exists"] = True
    try:
        payload = _read_json(lock_path)
    except OpError:
        return snapshot
    if not isinstance(payload, dict):
        return snapshot
    pid = payload.get("pid")
    if isinstance(pid, int):
        snapshot["pid"] = pid
        snapshot["pid_alive"] = _pid_is_running(pid)
    snapshot["lock_id"] = _as_str(payload.get("lock_id"))
    return snapshot


def _age_from_iso(value: Any) -> str:
    dt = _parse_iso_utc(value)
    if dt is None:
        return "n/a"
    delta = datetime.now(timezone.utc) - dt
    seconds = max(0, int(delta.total_seconds()))
    if seconds < 60:
        return f"{seconds}s ago"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


def _open_blockers_count(repo_root: Path) -> int:
    index_path = repo_root / "reports" / "optimus-prime" / "BLOCKER_INDEX.json"
    if not index_path.exists():
        return 0
    try:
        payload = _read_json(index_path)
    except OpError:
        return 0
    if not isinstance(payload, dict):
        return 0
    entries = payload.get("entries")
    if not isinstance(entries, list):
        return 0
    return len([entry for entry in entries if isinstance(entry, dict)])


def _active_worker_slots(repo_root: Path) -> set[str]:
    reports = repo_root / "reports" / "optimus-prime"
    registry_path = reports / "WORKER_REGISTRY.json"
    if not registry_path.exists():
        return set()
    try:
        registry = _read_json(registry_path)
    except OpError:
        return set()
    workers: list[dict[str, Any]] = []
    if isinstance(registry, dict):
        raw = registry.get("workers")
        if isinstance(raw, list):
            workers = [item for item in raw if isinstance(item, dict)]
        elif isinstance(raw, dict):
            workers = [item for item in raw.values() if isinstance(item, dict)]
    elif isinstance(registry, list):
        workers = [item for item in registry if isinstance(item, dict)]
    out: set[str] = set()
    for worker in workers:
        slot = _as_str(worker.get("slot"))
        if not slot:
            continue
        state = (
            _as_str(worker.get("state"))
            or _as_str(worker.get("session_state"))
            or _as_str(worker.get("status"))
            or ""
        ).lower()
        if state in {"running", "active", "busy"}:
            pid = worker.get("dispatch_pid")
            if not isinstance(pid, int) or not _pid_is_running(pid):
                continue
            out.add(slot)
    return out


def _active_worker_count_by_alias(repo_root: Path) -> dict[str, int]:
    reports = repo_root / "reports" / "optimus-prime"
    registry_path = reports / "WORKER_REGISTRY.json"
    if not registry_path.exists():
        return {}
    try:
        registry = _read_json(registry_path)
    except OpError:
        return {}
    workers: list[dict[str, Any]] = []
    if isinstance(registry, dict):
        raw = registry.get("workers")
        if isinstance(raw, list):
            workers = [item for item in raw if isinstance(item, dict)]
        elif isinstance(raw, dict):
            workers = [item for item in raw.values() if isinstance(item, dict)]
    elif isinstance(registry, list):
        workers = [item for item in registry if isinstance(item, dict)]
    counts: dict[str, int] = {}
    for worker in workers:
        state = _worker_state(worker)
        if state not in {"running", "active", "busy"}:
            continue
        pid = worker.get("dispatch_pid")
        if not isinstance(pid, int) or not _pid_is_running(pid):
            continue
        alias = _as_str(worker.get("codex_profile_alias"))
        if not alias:
            continue
        counts[alias] = counts.get(alias, 0) + 1
    return counts


def _recover_stale_in_progress_tasks(repo_root: Path, task_state: dict[str, Any], build_state: dict[str, Any]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    policy = build_state.get("stale_in_progress_policy")
    if not isinstance(policy, dict):
        policy = {"timeout_sec": STALE_IN_PROGRESS_TIMEOUT_SEC}
    timeout_sec = max(60, _coerce_nonneg_int(policy.get("timeout_sec"), default=STALE_IN_PROGRESS_TIMEOUT_SEC))
    build_state["stale_in_progress_policy"] = {"timeout_sec": timeout_sec}
    stale_cutoff = datetime.now(timezone.utc) - timedelta(seconds=timeout_sec)
    active_slots = _active_worker_slots(repo_root)
    for task in task_state.get("tasks", []):
        if not isinstance(task, dict):
            continue
        task_id = _as_str(task.get("task_id")) or "TASK-UNKNOWN"
        status = _normalize_task_status(task.get("status"))
        if status not in {TASK_STATUS_DEV_WORKING, TASK_STATUS_TESTING, TASK_STATUS_REVIEWING}:
            continue
        owner_slot = _as_str(task.get("owner_slot"))
        progress_at_raw = _as_str(task.get("last_progress_at")) or _as_str(task.get("updated_at"))
        progress_at = _parse_iso_utc(progress_at_raw)
        stale_reason: str | None = None
        if progress_at is None:
            stale_reason = "missing_last_progress_at"
        elif progress_at <= stale_cutoff:
            stale_reason = "timeout_elapsed"
        if stale_reason is None:
            continue
        if owner_slot and owner_slot in active_slots:
            warnings.append(
                {
                    "code": "stale_in_progress_blocked",
                    "message": (
                        f"task {task_id} appears stale in {status} but slot {owner_slot} is still active; "
                        "automatic recovery skipped"
                    ),
                    "stage": "build_loop",
                    "task_id": task_id,
                    "status": status,
                    "owner_slot": owner_slot,
                    "reason": stale_reason,
                }
            )
            continue
        recovered_status = {
            TASK_STATUS_DEV_WORKING: TASK_STATUS_PENDING,
            TASK_STATUS_TESTING: TASK_STATUS_DEV_DONE,
            TASK_STATUS_REVIEWING: TASK_STATUS_TESTS_DONE,
        }[status]
        task["status"] = recovered_status
        task["owner_slot"] = None
        task["last_progress_at"] = utc_now_iso()
        warnings.append(
            {
                "code": "stale_in_progress_recovered",
                "message": f"recovered stale task {task_id}: {status} -> {recovered_status}",
                "stage": "build_loop",
                "task_id": task_id,
                "from_status": status,
                "to_status": recovered_status,
                "reason": stale_reason,
            }
        )
    return warnings


def _prepare_dead_pid_redispatch_assignments(
    repo_root: Path,
    task_state: dict[str, Any],
    plan_packets: dict[str, Any],
    build_state: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    warnings: list[dict[str, Any]] = []
    assignments: list[dict[str, Any]] = []
    active_slots = _active_worker_slots(repo_root)
    plan_map = _plan_task_map(plan_packets)
    retry_counts = build_state.get("dead_pid_retry_counts")
    if not isinstance(retry_counts, dict):
        retry_counts = {}
        build_state["dead_pid_retry_counts"] = retry_counts
    completion_policy = build_state.get("worker_completion_policy")
    if not isinstance(completion_policy, dict):
        completion_policy = {"missing_threshold": 3}
    missing_threshold = max(1, _coerce_nonneg_int(completion_policy.get("missing_threshold"), default=3))
    build_state["worker_completion_policy"] = {"missing_threshold": missing_threshold}
    plan_id = _as_str(plan_packets.get("plan_id")) or "plan-unknown"

    status_to_stage: dict[str, tuple[str, str]] = {
        TASK_STATUS_DEV_WORKING: ("dev", "developer"),
        TASK_STATUS_TESTING: ("test", "tester"),
        TASK_STATUS_REVIEWING: ("review", "reviewer"),
    }
    for task in task_state.get("tasks", []):
        if not isinstance(task, dict):
            continue
        task_id = _as_str(task.get("task_id"))
        if not task_id:
            continue
        status = _normalize_task_status(task.get("status"))
        if status not in status_to_stage:
            continue
        owner_slot = _as_str(task.get("owner_slot"))
        if not owner_slot or owner_slot in active_slots:
            continue

        evidence_path = _task_evidence_path(repo_root, task)
        evidence_payload: dict[str, Any] = {}
        evidence_issue_code: str | None = None
        evidence_issue_message: str | None = None
        if evidence_path.exists():
            try:
                raw_payload = _read_json(evidence_path)
                if isinstance(raw_payload, dict):
                    evidence_payload = raw_payload
                else:
                    evidence_issue_code = "worker_completion_artifact_invalid"
                    evidence_issue_message = "completion artifact is not a JSON object"
            except OpError as exc:
                evidence_payload = {}
                evidence_issue_code = "worker_completion_artifact_invalid"
                evidence_issue_message = exc.message
        else:
            evidence_issue_code = "worker_completion_artifact_missing"
            evidence_issue_message = "completion artifact missing after worker dispatch"
        if evidence_issue_code:
            warnings.append(
                {
                    "code": evidence_issue_code,
                    "message": (
                        f"task {task_id} slot {owner_slot}: {evidence_issue_message or evidence_issue_code} "
                        f"(artifact={evidence_path})"
                    ),
                    "stage": "build_loop",
                    "task_id": task_id,
                    "slot": owner_slot,
                    "artifact": str(evidence_path),
                }
            )
        gate = evidence_payload.get("gate") if isinstance(evidence_payload.get("gate"), dict) else {}
        review = evidence_payload.get("review") if isinstance(evidence_payload.get("review"), dict) else {}
        evidence_progress = False
        if status == TASK_STATUS_DEV_WORKING and _as_bool_field(gate.get("ready_for_test")):
            evidence_progress = True
            task["status"] = TASK_STATUS_DEV_DONE
        elif status == TASK_STATUS_TESTING and _as_bool_field(gate.get("ready_for_review")):
            evidence_progress = True
            task["status"] = TASK_STATUS_TESTS_DONE
        elif status == TASK_STATUS_REVIEWING:
            review_decision = (_as_str(review.get("decision")) or "").lower()
            review_status = (_as_str(review.get("status")) or "").lower()
            if review_decision in {"accepted", "approved", "ready_for_merge", "pass"} or review_status in {
                "done",
                "completed",
                "review_done",
            }:
                evidence_progress = True
                task["status"] = TASK_STATUS_REVIEW_DONE

        if evidence_progress:
            task["owner_slot"] = None
            task["last_progress_at"] = utc_now_iso()
            retry_counts.pop(task_id, None)
            warnings.append(
                {
                    "code": "worker_completion_artifact_applied",
                    "message": (
                        f"task {task_id} progressed from completion artifact after dead-pid recovery "
                        f"(artifact={evidence_path})"
                    ),
                    "stage": "build_loop",
                    "task_id": task_id,
                    "slot": owner_slot,
                    "artifact": str(evidence_path),
                }
            )
            warnings.append(
                {
                    "code": "dead_pid_evidence_reconciled",
                    "message": (
                        f"task {task_id} advanced from evidence after dead pid recovery; "
                        "slot ownership cleared without redispatch"
                    ),
                    "stage": "build_loop",
                    "task_id": task_id,
                    "slot": owner_slot,
                }
            )
            continue

        stage_name, role_name = status_to_stage[status]
        redispatch_base_status = {
            TASK_STATUS_DEV_WORKING: TASK_STATUS_PENDING,
            TASK_STATUS_TESTING: TASK_STATUS_DEV_DONE,
            TASK_STATUS_REVIEWING: TASK_STATUS_TESTS_DONE,
        }[status]
        task["status"] = redispatch_base_status
        task["owner_slot"] = None
        task["last_progress_at"] = utc_now_iso()
        plan_task = plan_map.get(task_id) if isinstance(plan_map.get(task_id), dict) else {}
        lane_id = _as_str(task.get("lane_id")) or _as_str(plan_task.get("lane_id"))
        phase_id = _as_str(task.get("phase_id")) or _as_str(plan_task.get("phase_id")) or "phase-1"
        retry_count = int(retry_counts.get(task_id, 0)) + 1
        retry_counts[task_id] = retry_count
        if retry_count >= missing_threshold:
            task["status"] = TASK_STATUS_BLOCKED
            gap_code = evidence_issue_code or "worker_completion_artifact_missing"
            _upsert_task_gap(
                task,
                {
                    "gap_id": _gap_id(plan_id, phase_id, task_id, f"completion:{stage_name}", "blocked"),
                    "category": "task_blocked",
                    "severity": "P1",
                    "stage": stage_name,
                    "status": "open",
                    "reason_codes": [gap_code, "dead_pid_retry_threshold_reached"],
                    "retry_count": retry_count,
                    "max_retries": max(5, missing_threshold),
                    "closure_ref": str(evidence_path),
                },
            )
            warnings.append(
                {
                    "code": "worker_completion_artifact_missing"
                    if gap_code == "worker_completion_artifact_missing"
                    else "worker_completion_artifact_invalid",
                    "message": (
                        f"task {task_id} blocked after repeated missing/invalid completion artifact "
                        f"(retry={retry_count}, threshold={missing_threshold})"
                    ),
                    "stage": "build_loop",
                    "task_id": task_id,
                    "slot": owner_slot,
                    "retry_count": retry_count,
                    "threshold": missing_threshold,
                    "artifact": str(evidence_path),
                }
            )
            warnings.append(
                {
                    "code": "dead_pid_retry_watchdog_warning",
                    "message": f"task {task_id} hit repeated dead-pid redispatch retries ({retry_count}); task blocked",
                    "stage": "build_loop",
                    "task_id": task_id,
                    "slot": owner_slot,
                    "retry_count": retry_count,
                }
            )
            continue
        assignments.append(
            {
                "task_id": task_id,
                "lane_id": lane_id or f"{phase_id}/lane-a",
                "phase_id": phase_id,
                "next_stage": stage_name,
                "next_role": role_name,
                "slot": owner_slot,
                "dispatch_policy": "resume_if_same_lane",
            }
        )
        warnings.append(
            {
                "code": "dead_pid_no_evidence_redispatch",
                "message": (
                    f"task {task_id} owner slot {owner_slot} is not active and no progress evidence found; "
                    f"queued immediate same-cycle redispatch ({status} -> {redispatch_base_status})"
                ),
                "stage": "build_loop",
                "task_id": task_id,
                "slot": owner_slot,
                "retry_count": retry_count,
            }
        )
        if retry_count >= 3:
            warnings.append(
                {
                    "code": "dead_pid_retry_watchdog_warning",
                    "message": f"task {task_id} hit repeated dead-pid redispatch retries ({retry_count})",
                    "stage": "build_loop",
                    "task_id": task_id,
                    "slot": owner_slot,
                    "retry_count": retry_count,
                }
            )
    if assignments:
        build_state["last_dead_pid_recovery"] = {
            "updated_at": utc_now_iso(),
            "assignments": assignments,
        }
    return assignments, warnings


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


def _unwrap_bash_lc(command_text: str) -> str | None:
    try:
        tokens = shlex.split(command_text)
    except ValueError:
        return None
    if len(tokens) == 3 and tokens[0] in {"bash", "/bin/bash"} and tokens[1] == "-lc":
        return tokens[2]
    return None


def _extract_script_path_from_command(
    command_text: str,
    *,
    script_name: str,
    cwd: Path | None = None,
) -> Path | None:
    text = (command_text or "").strip()
    if not text:
        return None
    wrapped = _unwrap_bash_lc(text)
    if wrapped is not None:
        return _extract_script_path_from_command(wrapped, script_name=script_name, cwd=cwd)
    try:
        tokens = shlex.split(text)
    except ValueError:
        return None
    for token in tokens:
        candidate = token
        if "=" in candidate and not candidate.startswith("-"):
            _, candidate = candidate.split("=", 1)
        if not candidate.endswith(script_name):
            continue
        path = Path(candidate).expanduser()
        if not path.is_absolute() and cwd is not None:
            path = (cwd / path).expanduser()
        try:
            return path.resolve()
        except OSError:
            return path
    return None


def _extract_command_option_value(
    command_text: str,
    option_name: str,
    *,
    cwd: Path | None = None,
) -> str | None:
    text = (command_text or "").strip()
    if not text:
        return None
    wrapped = _unwrap_bash_lc(text)
    if wrapped is not None:
        return _extract_command_option_value(wrapped, option_name, cwd=cwd)
    try:
        tokens = shlex.split(text)
    except ValueError:
        return None
    for idx, token in enumerate(tokens):
        if token == option_name and idx + 1 < len(tokens):
            value = tokens[idx + 1]
        elif token.startswith(f"{option_name}="):
            value = token.split("=", 1)[1]
        else:
            continue
        path_like = Path(value).expanduser()
        if cwd is not None and not path_like.is_absolute() and value.startswith((".", "..")):
            try:
                return str((cwd / path_like).resolve())
            except OSError:
                return str(cwd / path_like)
        return value
    return None


def _validate_manager_command(
    command_text: str,
    *,
    manager: str,
    allow_bash_wrapper: bool = True,
) -> tuple[bool, str | None, str]:
    text = (command_text or "").strip()
    if not text:
        return False, "manager_command_disallowed", "empty command is not allowed"

    lowered = text.lower()
    forbidden_patterns = (
        " sudo ",
        "rm -rf /",
        "mkfs",
        "dd if=",
        "curl ",
        "wget ",
        "| bash",
        "| sh",
    )
    padded = f" {lowered} "
    if any(item in padded for item in forbidden_patterns):
        return False, "manager_command_disallowed", "command contains forbidden tokens/patterns"

    wrapped = _unwrap_bash_lc(text) if allow_bash_wrapper else None
    if wrapped is not None:
        return _validate_manager_command(wrapped, manager=manager, allow_bash_wrapper=False)

    try:
        tokens = shlex.split(text)
    except ValueError:
        return False, "manager_command_disallowed", "command has invalid shell quoting/syntax"
    if not tokens:
        return False, "manager_command_disallowed", "empty command is not allowed"

    head = tokens[0]
    if manager == "branch":
        if head not in {"git", "python", "python3", "pytest"}:
            return (
                False,
                "manager_command_disallowed",
                f"branch manager command head not allowed: {head}",
            )
        return True, None, ""
    if manager == "workstation":
        if head not in {"python", "python3"}:
            return (
                False,
                "manager_command_disallowed",
                f"workstation manager command head not allowed: {head}",
            )
        if "prepare_workstation.py" not in text:
            return (
                False,
                "manager_command_disallowed",
                "workstation command must invoke prepare_workstation.py",
            )
        return True, None, ""
    return False, "manager_command_disallowed", f"unsupported manager type: {manager}"


def _run_manager_command(
    command_text: str,
    *,
    cwd: Path,
    timeout_sec: int,
    manager: str,
) -> dict[str, Any]:
    ok, code, message = _validate_manager_command(command_text, manager=manager, allow_bash_wrapper=True)
    if not ok:
        return {
            "ok": False,
            "code": code or "manager_command_disallowed",
            "message": message,
            "stdout": "",
            "stderr": "",
            "exit_code": None,
            "timed_out": False,
        }
    try:
        proc = subprocess.run(
            ["bash", "-lc", command_text],
            cwd=str(cwd),
            text=True,
            capture_output=True,
            check=False,
            timeout=max(1, int(timeout_sec)),
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "code": "manager_command_timeout",
            "message": f"command timed out after {int(timeout_sec)}s",
            "stdout": "",
            "stderr": "",
            "exit_code": None,
            "timed_out": True,
        }
    return {
        "ok": proc.returncode == 0,
        "code": None,
        "message": "",
        "stdout": (proc.stdout or ""),
        "stderr": (proc.stderr or ""),
        "exit_code": proc.returncode,
        "timed_out": False,
    }


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


def _is_git_work_tree(repo_root: Path) -> bool:
    code, out, _ = _run(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo_root)
    return code == 0 and out.strip().lower() == "true"


def _ensure_rab_base_checked_out(repo_root: Path) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    if not _is_git_work_tree(repo_root):
        return warnings
    current = _git_text(repo_root, "branch", "--show-current")
    if current == "RAB-BASE":
        return warnings
    has_branch = _run(["git", "show-ref", "--verify", "--quiet", "refs/heads/RAB-BASE"], cwd=repo_root)[0] == 0
    checkout_cmd = ["git", "checkout", "RAB-BASE"] if has_branch else ["git", "checkout", "-b", "RAB-BASE"]
    code, _, err = _run(checkout_cmd, cwd=repo_root)
    if code != 0:
        warnings.append(
            {
                "code": "rab_base_checkout_failed",
                "message": f"unable to checkout RAB-BASE: {err.strip() or 'unknown error'}",
                "stage": "build_preflight",
            }
        )
    return warnings


def _git_bootstrap_prompt_text(
    *,
    req: OpRequest,
    prior_errors: list[dict[str, Any]],
) -> str:
    template_path = GIT_BOOTSTRAP_PROMPT_TEMPLATE_PATH.resolve()
    if not template_path.exists():
        raise OpError("git_bootstrap_execution_failed", f"git bootstrap prompt template not found: {template_path}", stage="initialize")
    template_text = template_path.read_text(encoding="utf-8")
    validator_script = GIT_BOOTSTRAP_VALIDATOR_SCRIPT_PATH.resolve()
    validator_command = (
        f"python3 {validator_script} --repo-root {req.repo_root} --required-branch {GIT_BOOTSTRAP_REQUIRED_BRANCH} --require-readme"
    )
    prompt = template_text
    replacements = {
        "{{REPO_ROOT}}": str(req.repo_root),
        "{{PROJECT_NAME}}": req.repo_root.name,
        "{{REQUIRED_BRANCH}}": GIT_BOOTSTRAP_REQUIRED_BRANCH,
        "{{VALIDATOR_COMMAND}}": validator_command,
    }
    for key, value in replacements.items():
        prompt = prompt.replace(key, value)
    if prior_errors:
        prompt += "\n\nRepair context from previous failed verification:\n"
        for idx, row in enumerate(prior_errors, start=1):
            code = _as_str(row.get("code")) or "unknown"
            message = _as_str(row.get("message")) or "verification failed"
            prompt += f"{idx}. [{code}] {message}\n"
    return prompt


def _ensure_git_initialized_for_initialize(req: OpRequest) -> tuple[list[dict[str, Any]], list[str]]:
    if _is_git_work_tree(req.repo_root):
        return [], []

    _emit_build_progress(
        req,
        "git workspace not detected; running LLM bootstrap to initialize repository and create RAB-BASE",
    )
    llm_root = _repo_path(req.repo_root, PLANNER_REL) / "git-bootstrap"
    llm_root.mkdir(parents=True, exist_ok=True)
    prompt_path = llm_root / "prompt.txt"
    stdout_path = llm_root / "llm_stdout.log"
    stderr_path = llm_root / "llm_stderr.log"
    last_message_path = llm_root / "last_message.txt"

    prompt = _git_bootstrap_prompt_text(req=req, prior_errors=[])
    prompt_path.write_text(prompt, encoding="utf-8")

    try:
        exit_code = run_codex_exec(
            repo_root=req.repo_root,
            prompt_text=prompt,
            output_last_message=last_message_path,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
    except OSError as exc:
        _emit_build_progress(req, f"git bootstrap failed before verification: {exc}")
        raise OpError("git_bootstrap_execution_failed", f"unable to invoke codex exec for git bootstrap: {exc}", stage="initialize") from exc

    result = validate_git_bootstrap(
        repo_root=req.repo_root,
        required_branch=GIT_BOOTSTRAP_REQUIRED_BRANCH,
        require_readme=True,
    )
    errors = result.get("errors")
    if not isinstance(errors, list):
        errors = []
    if errors:
        first = errors[0] if isinstance(errors[0], dict) else {}
        message = _as_str(first.get("message")) or "git bootstrap verification failed"
        _emit_build_progress(req, f"git bootstrap verification failed: {message}")
        raise OpError("git_bootstrap_failed", message, stage="initialize")

    warnings: list[dict[str, Any]] = []
    if exit_code != 0:
        warnings.append(
            {
                "code": "git_bootstrap_nonzero_exit",
                "message": f"codex exec exited with code {exit_code} during git bootstrap; verification still passed",
                "stage": "initialize",
            }
        )
    for row in result.get("warnings", []):
        if not isinstance(row, dict):
            continue
        code = _as_str(row.get("code")) or "git_bootstrap_warning"
        message = _as_str(row.get("message")) or "git bootstrap warning"
        warning: dict[str, Any] = {"code": code, "message": message, "stage": "initialize"}
        for key in ("details", "remote", "branch"):
            if key in row:
                warning[key] = row.get(key)
        warnings.append(warning)
    _emit_build_progress(req, "git bootstrap verification passed")
    return warnings, [str(prompt_path), str(stdout_path), str(stderr_path), str(last_message_path)]


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


def _resolve_text_or_file_source(
    *,
    inline_value: str | None,
    file_value: str | None,
    field: str,
    stage: str,
    required: bool,
) -> dict[str, Any]:
    has_inline = bool(_as_str(inline_value))
    has_file = bool(_as_str(file_value))
    if has_inline and has_file:
        raise OpError("input_error", f"{field} and {field}_file are mutually exclusive", stage=stage)
    if not has_inline and not has_file:
        if required:
            raise OpError("input_error", f"{field} is required", stage=stage)
        return {"mode": "none", "value": None, "path": None, "display": None}

    if has_file:
        raw = _as_str(file_value)
        assert raw is not None
        path = Path(raw).expanduser().resolve()
        if not path.exists():
            raise OpError("input_error", f"{field}_file does not exist: {path}", stage=stage)
        if not path.is_file():
            raise OpError("input_error", f"{field}_file must point to a file: {path}", stage=stage)
        return {
            "mode": "file",
            "value": None,
            "path": str(path),
            "display": f"@file:{path}",
        }

    value = _as_str(inline_value)
    assert value is not None
    return {
        "mode": "inline",
        "value": value,
        "path": None,
        "display": value,
    }


def _resolve_mission_scope_sources(req: OpRequest, *, stage: str, required: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    mission_source = _resolve_text_or_file_source(
        inline_value=req.mission,
        file_value=req.mission_file,
        field="mission",
        stage=stage,
        required=required,
    )
    scope_source = _resolve_text_or_file_source(
        inline_value=req.scope,
        file_value=req.scope_file,
        field="scope",
        stage=stage,
        required=required,
    )
    return mission_source, scope_source


def _planning_artifacts_exist(repo_root: Path) -> bool:
    for rel in PLANNING_OVERRIDE_SENTINELS:
        if _repo_path(repo_root, rel).exists():
            return True
    return False


def _require_override_if_existing_plan(req: OpRequest, *, stage: str) -> None:
    if not _planning_artifacts_exist(req.repo_root):
        return
    if req.override_old_plan:
        return
    raise OpError(
        "override_required",
        "existing planning artifacts detected; rerun with --override-old-plan to replace them",
        stage=stage,
    )


def _archive_existing_planning_artifacts(repo_root: Path) -> str | None:
    planning_root = _repo_path(repo_root, PLANNING_REL)
    if not planning_root.exists():
        return None
    archive_root = planning_root / "archive"
    archive_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_path = archive_root / f"override-{stamp}-{uuid.uuid4().hex[:8]}"
    archive_path.mkdir(parents=True, exist_ok=False)
    for rel in PLANNING_OVERRIDE_SENTINELS:
        src = _repo_path(repo_root, rel)
        if not src.exists():
            continue
        dst = archive_path / rel.name
        shutil.copy2(src, dst)
    return str(archive_path)


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
    _require_override_if_existing_plan(req, stage="new-project")
    mission_source, scope_source = _resolve_mission_scope_sources(req, stage="new-project", required=True)
    repo_root = req.repo_root
    _ensure_managed_gitignore_block(repo_root)
    override_archive_path: str | None = None
    if req.override_old_plan:
        override_archive_path = _archive_existing_planning_artifacts(repo_root)

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

    constraints = req.constraints
    constraint_lines = [f"- {item}" for item in constraints] if constraints else ["- none"]
    initialized_at = utc_now_iso()

    project_md = "\n".join(
        [
            "# PROJECT",
            "",
            f"- Mission: {mission_source['display']}",
            f"- Scope: {scope_source['display']}",
            f"- Initialized At: {initialized_at}",
            f"- Map Fingerprint: `{map_payload.get('map_fingerprint')}`",
            "",
            "## Constraints",
            *constraint_lines,
        ]
    )

    requirements_md = "\n".join(
        [
            "# REQUIREMENTS",
            "",
            "Generated by `/op-plan` from LLM planner output.",
        ]
    )

    roadmap_md = "\n".join(
        [
            "# ROADMAP",
            "",
            "1. Planning baseline finalized.",
            "2. LLM plan bundle generated + strict validation pass.",
            "3. Autonomous build loop executes validated plan packets.",
            "4. Verification artifacts complete and terminal stop authorization passes.",
        ]
    )

    state_json = {
        "schema_version": SCHEMA_VERSION,
        "initialized_at": initialized_at,
        "updated_at": initialized_at,
        "mission": mission_source["display"],
        "scope": scope_source["display"],
        "mission_source": mission_source,
        "scope_source": scope_source,
        "constraints": constraints,
        "requirements": [],
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
            "- baseline_ready: true",
            "- plan_ready: false",
            "- build_ready: false",
            f"- mission: {mission_source['display']}",
            f"- scope: {scope_source['display']}",
            "",
            "## Traceability",
            "- Requirements/tasks are generated by /op-plan.",
        ]
    )

    _write_text(_repo_path(repo_root, PROJECT_MD), project_md + "\n")
    _write_text(_repo_path(repo_root, REQUIREMENTS_MD), requirements_md + "\n")
    _write_text(_repo_path(repo_root, ROADMAP_MD), roadmap_md + "\n")
    _write_text(_repo_path(repo_root, STATE_MD), state_md + "\n")
    _atomic_write_json(_repo_path(repo_root, STATE_JSON), state_json)

    data: dict[str, Any] = {"auto_map_performed": auto_map_performed}
    if override_archive_path:
        data["override_archive_path"] = override_archive_path

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
        data=data,
    )


def _normalize_requirement_rows(requirements_raw: Any) -> list[dict[str, Any]]:
    requirements: list[dict[str, Any]] = []
    if not isinstance(requirements_raw, list):
        return requirements
    for idx, row in enumerate(requirements_raw, start=1):
        if not isinstance(row, dict):
            continue
        req_id = _as_str(row.get("id")) or f"REQ-{idx:03d}"
        title = _as_str(row.get("title")) or f"Requirement {req_id}"
        acceptance = row.get("acceptance_criteria")
        verify = row.get("verify_commands")
        requirements.append(
            {
                "id": req_id,
                "title": title,
                "acceptance_criteria": [item for item in acceptance if isinstance(item, str)] if isinstance(acceptance, list) else [],
                "verify_commands": [item for item in verify if isinstance(item, str)] if isinstance(verify, list) else [],
            }
        )
    return requirements


def _build_dag_edges(tasks: list[dict[str, Any]]) -> tuple[dict[str, list[str]], dict[str, list[str]], list[dict[str, Any]]]:
    task_ids = [_as_str(item.get("task_id")) for item in tasks if isinstance(item, dict)]
    known = {task_id for task_id in task_ids if task_id}
    preds: dict[str, list[str]] = {task_id: [] for task_id in known}
    succs: dict[str, list[str]] = {task_id: [] for task_id in known}
    errors: list[dict[str, Any]] = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = _as_str(task.get("task_id"))
        if not task_id:
            continue
        deps = task.get("depends_on")
        if not isinstance(deps, list):
            errors.append({"code": "planner_bundle_schema_error", "message": f"task {task_id} depends_on must be list"})
            continue
        for dep in deps:
            dep_id = _as_str(dep)
            if not dep_id:
                continue
            if dep_id not in known:
                errors.append({"code": "planner_bundle_schema_error", "message": f"task {task_id} depends on unknown task {dep_id}"})
                continue
            preds[task_id].append(dep_id)
            succs[dep_id].append(task_id)
    return preds, succs, errors


def _validate_task_dag(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    preds, succs, errors = _build_dag_edges(tasks)
    if errors:
        return errors
    indegree = {task_id: len(parents) for task_id, parents in preds.items()}
    queue = deque(sorted([task_id for task_id, value in indegree.items() if value == 0]))
    seen = 0
    while queue:
        node = queue.popleft()
        seen += 1
        for child in succs.get(node, []):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if seen != len(indegree):
        return [{"code": "planner_bundle_schema_error", "message": "task DAG contains cycle"}]
    return []


def _validate_phase_dag(phases: list[dict[str, Any]], tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    phase_ids = {_as_str(phase.get("phase_id")) for phase in phases if isinstance(phase, dict)}
    phase_ids.discard(None)
    if not phase_ids:
        errors.append({"code": "planner_bundle_schema_error", "message": "phases must be non-empty"})
        return errors
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = _as_str(task.get("task_id")) or "task-unknown"
        phase_id = _as_str(task.get("phase_id"))
        if not phase_id or phase_id not in phase_ids:
            errors.append({"code": "planner_bundle_schema_error", "message": f"task {task_id} has invalid phase_id"})

    phase_preds: dict[str, list[str]] = {phase_id: [] for phase_id in phase_ids}
    phase_succs: dict[str, list[str]] = {phase_id: [] for phase_id in phase_ids}
    for phase in phases:
        if not isinstance(phase, dict):
            continue
        phase_id = _as_str(phase.get("phase_id"))
        if not phase_id:
            continue
        deps = phase.get("depends_on_phase_ids")
        if not isinstance(deps, list):
            errors.append({"code": "planner_bundle_schema_error", "message": f"phase {phase_id} depends_on_phase_ids must be list"})
            continue
        for dep in deps:
            dep_id = _as_str(dep)
            if not dep_id:
                continue
            if dep_id not in phase_ids:
                errors.append({"code": "planner_bundle_schema_error", "message": f"phase {phase_id} depends on unknown phase {dep_id}"})
                continue
            phase_preds[phase_id].append(dep_id)
            phase_succs[dep_id].append(phase_id)
    if errors:
        return errors
    indegree = {phase_id: len(parents) for phase_id, parents in phase_preds.items()}
    queue = deque(sorted([phase_id for phase_id, value in indegree.items() if value == 0]))
    seen = 0
    while queue:
        node = queue.popleft()
        seen += 1
        for child in phase_succs.get(node, []):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if seen != len(indegree):
        errors.append({"code": "planner_bundle_schema_error", "message": "phase DAG contains cycle"})
    return errors


def _validate_hardening_rule(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    _, succs, dep_errors = _build_dag_edges(tasks)
    if dep_errors:
        return dep_errors
    by_requirement: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for task in tasks:
        if not isinstance(task, dict):
            continue
        req_ids = task.get("requirement_ids")
        if not isinstance(req_ids, list):
            continue
        for rid in req_ids:
            rid_text = _as_str(rid)
            if rid_text:
                by_requirement[rid_text].append(task)
    for req_id, req_tasks in by_requirement.items():
        if len(req_tasks) <= 2:
            continue
        req_task_ids = {
            _as_str(task.get("task_id"))
            for task in req_tasks
            if _as_str(task.get("task_id"))
        }
        terminals: list[dict[str, Any]] = []
        for task in req_tasks:
            task_id = _as_str(task.get("task_id"))
            if not task_id:
                continue
            children = succs.get(task_id, [])
            if not any(child in req_task_ids for child in children):
                terminals.append(task)
        hardening_count = 0
        for task in terminals:
            title = (_as_str(task.get("title")) or "").lower()
            if re.search(r"(harden|hardening|review)", title):
                hardening_count += 1
        if hardening_count < 2:
            errors.append(
                {
                    "code": "planner_bundle_schema_error",
                    "message": f"requirement {req_id} needs at least 2 terminal hardening/review tasks when task count > 2",
                }
            )
    return errors


def _planner_validate_bundle(req: OpRequest, bundle_path: Path) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    planning_root = _repo_path(req.repo_root, PLANNING_REL)
    strict_bundle, strict_errors = validate_bundle_contract(bundle_path, planning_root)
    if strict_errors:
        return None, [{"code": _as_str(item.get("code")) or "planner_bundle_schema_error", "message": _as_str(item.get("message")) or "planner bundle validation failed", **{k: v for k, v in item.items() if k not in {"code", "message"}}} for item in strict_errors]
    if strict_bundle is None:
        return None, [{"code": "planner_bundle_schema_error", "message": "planner bundle validation returned no bundle"}]

    bundle = strict_bundle
    errors: list[dict[str, Any]] = []

    plan_artifact = bundle["PLAN_PACKETS.json"]
    if not isinstance(plan_artifact.content, dict):
        errors.append({"code": "planner_bundle_schema_error", "message": "PLAN_PACKETS.json must be object JSON"})
        return None, errors
    plan_packets = plan_artifact.content
    plan_id = _as_str(plan_packets.get("plan_id"))
    if not plan_id:
        errors.append({"code": "planner_bundle_schema_error", "message": "PLAN_PACKETS.plan_id must be non-empty string"})

    tasks = plan_packets.get("tasks")
    phases = plan_packets.get("phases")
    requirements_raw = plan_packets.get("requirements")
    if not isinstance(tasks, list) or not tasks:
        errors.append({"code": "planner_bundle_schema_error", "message": "PLAN_PACKETS.tasks must be non-empty list"})
        return None, errors
    if not isinstance(phases, list) or not phases:
        errors.append({"code": "planner_bundle_schema_error", "message": "PLAN_PACKETS.phases must be non-empty list"})
        return None, errors

    requirement_ids: list[str] = []
    if isinstance(requirements_raw, list):
        for idx, req in enumerate(requirements_raw, start=1):
            if isinstance(req, dict):
                req_id = _as_str(req.get("id")) or f"REQ-{idx:03d}"
            else:
                req_id = _as_str(req)
            if req_id:
                requirement_ids.append(req_id)
    if not requirement_ids:
        errors.append({"code": "planner_bundle_schema_error", "message": "PLAN_PACKETS.requirements must include requirement IDs"})

    task_ids: list[str] = []
    covered_ids: set[str] = set()
    phase_lanes: dict[str, set[str]] = {}
    for task in tasks:
        if not isinstance(task, dict):
            errors.append({"code": "planner_bundle_schema_error", "message": "PLAN_PACKETS.tasks rows must be objects"})
            continue
        task_id = _as_str(task.get("task_id"))
        title = _as_str(task.get("title"))
        phase_id = _as_str(task.get("phase_id"))
        lane_id = _as_str(task.get("lane_id"))
        status = _normalize_task_status(task.get("status"))
        req_ids = task.get("requirement_ids")
        deps = task.get("depends_on")
        gaps = task.get("gaps_that_need_patching")
        if not task_id:
            errors.append({"code": "planner_bundle_schema_error", "message": "task_id is required"})
        else:
            task_ids.append(task_id)
        if not title:
            errors.append({"code": "planner_bundle_schema_error", "message": f"task {task_id or 'unknown'} title is required"})
        if not phase_id:
            errors.append({"code": "planner_bundle_schema_error", "message": f"task {task_id or 'unknown'} phase_id is required"})
        if not lane_id:
            lane_id = f"{phase_id or 'phase-1'}/lane-a"
            task["lane_id"] = lane_id
        elif phase_id and not lane_id.startswith(f"{phase_id}/lane-"):
            task["lane_id"] = f"{phase_id}/lane-a"
            lane_id = task["lane_id"]
        if _as_str(task.get("status")) is None:
            task["status"] = TASK_STATUS_PENDING
            status = TASK_STATUS_PENDING
        elif status != TASK_STATUS_PENDING:
            errors.append({"code": "planner_bundle_schema_error", "message": f"task {task_id or 'unknown'} status must be pending in initial plan"})
        if not isinstance(req_ids, list) or not [_as_str(item) for item in req_ids if _as_str(item)]:
            errors.append({"code": "planner_bundle_schema_error", "message": f"task {task_id or 'unknown'} requirement_ids must be non-empty list"})
        else:
            for rid in req_ids:
                rid_text = _as_str(rid)
                if rid_text:
                    covered_ids.add(rid_text)
        if not isinstance(deps, list):
            errors.append({"code": "planner_bundle_schema_error", "message": f"task {task_id or 'unknown'} depends_on must be list"})
        if not isinstance(gaps, list):
            task["gaps_that_need_patching"] = []
        if phase_id and lane_id:
            phase_lanes.setdefault(phase_id, set()).add(lane_id)

    for phase_id, lanes in phase_lanes.items():
        if len(lanes) > 3:
            errors.append(
                {
                    "code": "planner_bundle_schema_error",
                    "message": f"phase {phase_id} has more than 3 lanes",
                    "lane_ids": sorted(lanes),
                }
            )

    for rid in requirement_ids:
        if rid not in covered_ids:
            errors.append({"code": "planner_bundle_schema_error", "message": f"requirement {rid} is not covered by tasks"})

    errors.extend(_validate_task_dag([task for task in tasks if isinstance(task, dict)]))
    errors.extend(_validate_phase_dag([phase for phase in phases if isinstance(phase, dict)], [task for task in tasks if isinstance(task, dict)]))
    errors.extend(_validate_hardening_rule([task for task in tasks if isinstance(task, dict)]))
    if errors:
        return None, errors

    evidence_expected = {f"evidence/{task_id}/TASK_EVIDENCE.json" for task_id in task_ids}
    evidence_present = {path for path in bundle.keys() if path.startswith("evidence/") and path.endswith("/TASK_EVIDENCE.json")}
    missing_evidence = sorted(evidence_expected - evidence_present)
    extra_evidence = sorted(evidence_present - evidence_expected)
    if missing_evidence:
        errors.append({"code": "planner_bundle_schema_error", "message": "missing task evidence artifacts", "missing": missing_evidence})
    if extra_evidence:
        errors.append({"code": "planner_bundle_schema_error", "message": "unexpected task evidence artifacts", "extra": extra_evidence})
    for path in sorted(evidence_present):
        artifact = bundle[path]
        if not isinstance(artifact.content, dict):
            errors.append({"code": "planner_bundle_schema_error", "message": f"{path} must be object JSON"})
            continue
        evidence_task_id = _as_str(artifact.content.get("task_id"))
        expected_task_id = path.split("/")[1] if "/" in path else None
        if expected_task_id and evidence_task_id != expected_task_id:
            errors.append({"code": "planner_bundle_schema_error", "message": f"{path} task_id mismatch"})
        evidence_plan_id = _as_str(artifact.content.get("plan_id"))
        if plan_id and evidence_plan_id and evidence_plan_id != plan_id:
            errors.append({"code": "planner_bundle_schema_error", "message": f"{path} plan_id mismatch"})

    task_state_artifact = bundle["TASK_EXECUTION_STATE.json"]
    if not isinstance(task_state_artifact.content, dict):
        errors.append({"code": "planner_bundle_schema_error", "message": "TASK_EXECUTION_STATE.json must be object JSON"})
    else:
        task_state_plan_id = _as_str(task_state_artifact.content.get("plan_id"))
        if plan_id and task_state_plan_id and task_state_plan_id != plan_id:
            errors.append({"code": "planner_bundle_schema_error", "message": "TASK_EXECUTION_STATE.plan_id mismatch"})
        rows = task_state_artifact.content.get("tasks")
        if not isinstance(rows, list):
            errors.append({"code": "planner_bundle_schema_error", "message": "TASK_EXECUTION_STATE.tasks must be list"})
        else:
            row_ids = {
                _as_str(row.get("task_id"))
                for row in rows
                if isinstance(row, dict) and _as_str(row.get("task_id"))
            }
            missing_state_ids = sorted([task_id for task_id in task_ids if task_id not in row_ids])
            if missing_state_ids:
                errors.append({"code": "planner_bundle_schema_error", "message": "TASK_EXECUTION_STATE missing plan task IDs", "missing_task_ids": missing_state_ids})

    for name, key in (("GAPS.json", "gaps"), ("GAP_CLOSURE_PLAN_PACKETS.json", "tasks")):
        artifact = bundle.get(name)
        if artifact is None:
            continue
        if not isinstance(artifact.content, dict):
            errors.append({"code": "planner_bundle_schema_error", "message": f"{name} must be object JSON"})
            continue
        artifact_plan_id = _as_str(artifact.content.get("plan_id"))
        if plan_id and artifact_plan_id and artifact_plan_id != plan_id:
            errors.append({"code": "planner_bundle_schema_error", "message": f"{name} plan_id mismatch"})
        if not isinstance(artifact.content.get(key), list):
            errors.append({"code": "planner_bundle_schema_error", "message": f"{name} field '{key}' must be list"})

    plan_check_artifact = bundle["PLAN_CHECK.json"]
    if not isinstance(plan_check_artifact.content, dict):
        errors.append({"code": "planner_bundle_schema_error", "message": "PLAN_CHECK.json must be object JSON"})
    else:
        if not bool(plan_check_artifact.content.get("passed")):
            errors.append({"code": "planner_plan_check_failed", "message": "PLAN_CHECK.passed must be true"})

    requirements_for_check = _normalize_requirement_rows(requirements_raw)
    recomputed = _compute_plan_check(
        _as_str(bundle["STATE.json"].content.get("mission")) if isinstance(bundle["STATE.json"].content, dict) else None,
        _as_str(bundle["STATE.json"].content.get("scope")) if isinstance(bundle["STATE.json"].content, dict) else None,
        requirements_for_check,
        [task for task in tasks if isinstance(task, dict)],
        [phase for phase in phases if isinstance(phase, dict)],
    )
    if not bool(recomputed.get("passed")):
        errors.append(
            {
                "code": "planner_plan_check_failed",
                "message": "recomputed plan-check failed",
                "details": recomputed.get("blocking_errors", []),
            }
        )

    if errors:
        return None, errors
    return {"bundle": bundle, "plan_packets": plan_packets, "recomputed_plan_check": recomputed}, []


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    _ensure_parent(path)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=False))
        handle.write("\n")


def _planner_source_display(source: dict[str, Any], *, label: str) -> str:
    if source.get("mode") == "file":
        return f"{label}=file:{source.get('path')}"
    if source.get("mode") == "inline":
        return f"{label}=inline:{source.get('value')}"
    return f"{label}=none"


def _planner_prompt_text(
    *,
    req: OpRequest,
    bundle_path: Path,
    mission_source: dict[str, Any],
    scope_source: dict[str, Any],
    prior_errors: list[dict[str, Any]],
) -> str:
    template_path = PLANNER_PROMPT_TEMPLATE_PATH.resolve()
    if not template_path.exists():
        raise OpError("planner_execution_failed", f"planner prompt template not found: {template_path}", stage="plan")
    template_text = template_path.read_text(encoding="utf-8")
    validator_script = PLANNER_VALIDATOR_SCRIPT_PATH.resolve()
    validator_command = (
        f"python3 {validator_script} --repo-root {req.repo_root} --bundle-path {bundle_path}"
    )
    prompt = render_prompt(
        template_text,
        repo_root=req.repo_root,
        bundle_path=bundle_path,
        validator_command=validator_command,
        example_root=PLANNER_EXAMPLE_ROOT_PATH.resolve(),
        mission_source=_planner_source_display(mission_source, label="mission"),
        scope_source=_planner_source_display(scope_source, label="scope"),
        map_path=_repo_path(req.repo_root, MAP_PATH),
        arch_path=_repo_path(req.repo_root, ARCH_PATH),
    )
    if prior_errors:
        prompt += "\n\nRepair context from previous failed attempt:\n"
        for idx, row in enumerate(prior_errors, start=1):
            code = _as_str(row.get("code")) or "unknown"
            message = _as_str(row.get("message")) or "validation failed"
            prompt += f"{idx}. [{code}] {message}\n"
    return prompt


def _run_llm_plan_generation(
    req: OpRequest,
    *,
    mission_source: dict[str, Any],
    scope_source: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    planning_root = _repo_path(req.repo_root, PLANNING_REL)
    llm_root = _repo_path(req.repo_root, PLANNER_REL)
    attempts_log_path = _repo_path(req.repo_root, PLANNER_ATTEMPTS_JSONL)
    errors_for_retry: list[dict[str, Any]] = []
    final_validation: dict[str, Any] | None = None
    warnings: list[dict[str, Any]] = []
    attempt_artifacts: list[str] = []

    for attempt in range(1, 11):
        _emit_build_progress(req, f"planner generation attempt {attempt}/10")
        attempt_dir = llm_root / f"attempt-{attempt}"
        attempt_dir.mkdir(parents=True, exist_ok=True)
        bundle_path = attempt_dir / "PLAN_BUNDLE.jsonl"
        stdout_path = attempt_dir / "llm_stdout.log"
        stderr_path = attempt_dir / "llm_stderr.log"
        last_message_path = attempt_dir / "last_message.txt"
        prompt_path = attempt_dir / "prompt.txt"

        prompt = _planner_prompt_text(
            req=req,
            bundle_path=bundle_path,
            mission_source=mission_source,
            scope_source=scope_source,
            prior_errors=errors_for_retry,
        )
        prompt_path.write_text(prompt, encoding="utf-8")

        started_at = utc_now_iso()
        try:
            exit_code = run_codex_exec(
                repo_root=req.repo_root,
                prompt_text=prompt,
                output_last_message=last_message_path,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
            )
        except OSError as exc:
            finished_at = utc_now_iso()
            error_row = {
                "code": "planner_execution_failed",
                "message": f"unable to invoke codex exec: {exc}",
            }
            _append_jsonl(
                attempts_log_path,
                {
                    "attempt": attempt,
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "bundle_path": str(bundle_path),
                    "parse_ok": False,
                    "schema_ok": False,
                    "plan_check_ok": False,
                    "errors": [error_row],
                    "llm_stdout_ref": str(stdout_path),
                    "llm_stderr_ref": str(stderr_path),
                    "status": "failed",
                    "exit_code": None,
                },
            )
            _emit_build_progress(req, f"planner generation failed before validation on attempt #{attempt}: {exc}")
            raise OpError(error_row["code"], error_row["message"], stage="plan") from exc
        finished_at = utc_now_iso()
        attempt_artifacts.extend(
            [
                str(bundle_path),
                str(stdout_path),
                str(stderr_path),
                str(last_message_path),
                str(prompt_path),
            ]
        )

        parse_ok = False
        schema_ok = False
        plan_check_ok = False
        validation_payload: dict[str, Any] | None
        validation_payload, validation_errors = _planner_validate_bundle(req, bundle_path)
        if not validation_errors:
            parse_ok = True
            schema_ok = True
            plan_check_ok = True
            final_validation = validation_payload
        else:
            parse_ok = not any(item.get("code") in {"planner_bundle_parse_error", "planner_bundle_missing"} for item in validation_errors)
            schema_ok = not any(item.get("code") == "planner_bundle_schema_error" for item in validation_errors)
            plan_check_ok = not any(item.get("code") == "planner_plan_check_failed" for item in validation_errors)
            errors_for_retry = validation_errors

        _append_jsonl(
            attempts_log_path,
            {
                "attempt": attempt,
                "started_at": started_at,
                "finished_at": finished_at,
                "bundle_path": str(bundle_path),
                "parse_ok": parse_ok,
                "schema_ok": schema_ok,
                "plan_check_ok": plan_check_ok,
                "errors": validation_errors,
                "llm_stdout_ref": str(stdout_path),
                "llm_stderr_ref": str(stderr_path),
                "status": "passed" if final_validation else "failed",
                "exit_code": exit_code,
            },
        )

        if final_validation:
            _emit_build_progress(req, f"planner generation succeeded on attempt #{attempt}")
            break

        if exit_code != 0:
            warnings.append(
                {
                    "code": "planner_execution_failed",
                    "message": f"codex exec attempt {attempt} exited with code {exit_code}",
                    "stage": "plan",
                }
            )
            _emit_build_progress(
                req,
                (
                    f"planner generation failed on attempt #{attempt}; codex exited with {exit_code}. "
                    "Applying necessary fixes and retrying."
                ),
            )
        else:
            _emit_build_progress(
                req,
                f"planner generation failed on attempt #{attempt}; applying necessary fixes and retrying.",
            )

    if final_validation is None:
        raise OpError(
            "planner_retry_exhausted",
            "planner failed to produce a valid artifact bundle after 10 attempts",
            stage="plan",
        )

    bundle = final_validation["bundle"]
    if not isinstance(bundle, dict):
        raise OpError("planner_bundle_schema_error", "validated planner bundle missing", stage="plan")
    written = materialize_bundle(bundle, planning_root)
    return final_validation, warnings, [str(path) for path in written] + attempt_artifacts


def _state_from_bundle_inputs(
    mission_source: dict[str, Any],
    scope_source: dict[str, Any],
    constraints: list[str],
    map_payload: dict[str, Any],
    plan_id: str | None,
    plan_ready: bool,
) -> dict[str, Any]:
    now = utc_now_iso()
    return {
        "schema_version": SCHEMA_VERSION,
        "initialized_at": now,
        "updated_at": now,
        "mission": mission_source.get("display"),
        "scope": scope_source.get("display"),
        "mission_source": mission_source,
        "scope_source": scope_source,
        "constraints": constraints,
        "requirements": [],
        "map_fingerprint": map_payload.get("map_fingerprint"),
        "repo_fingerprint": map_payload.get("repo_fingerprint"),
        "baseline_ready": True,
        "plan_ready": bool(plan_ready),
        "plan_id": plan_id,
        "build_ready": bool(plan_ready),
    }


def _write_baseline_docs_from_sources(
    *,
    req: OpRequest,
    mission_source: dict[str, Any],
    scope_source: dict[str, Any],
    constraints: list[str],
    map_payload: dict[str, Any],
) -> None:
    constraint_lines = [f"- {item}" for item in constraints] if constraints else ["- none"]
    initialized_at = utc_now_iso()
    project_md = "\n".join(
        [
            "# PROJECT",
            "",
            f"- Mission: {mission_source['display']}",
            f"- Scope: {scope_source['display']}",
            f"- Initialized At: {initialized_at}",
            f"- Map Fingerprint: `{map_payload.get('map_fingerprint')}`",
            "",
            "## Constraints",
            *constraint_lines,
        ]
    )
    requirements_md = "\n".join(["# REQUIREMENTS", "", "Generated by `/op-plan` from LLM planner output."])
    roadmap_md = "\n".join(
        [
            "# ROADMAP",
            "",
            "1. Planning baseline finalized.",
            "2. LLM plan bundle generated + strict validation pass.",
            "3. Autonomous build loop executes validated plan packets.",
            "4. Verification artifacts complete and terminal stop authorization passes.",
        ]
    )
    state_md = "\n".join(
        [
            "# STATE",
            "",
            "- baseline_ready: true",
            "- plan_ready: false",
            "- build_ready: false",
            f"- mission: {mission_source['display']}",
            f"- scope: {scope_source['display']}",
            "",
            "## Traceability",
            "- Requirements/tasks are generated by /op-plan.",
        ]
    )
    _write_text(_repo_path(req.repo_root, PROJECT_MD), project_md + "\n")
    _write_text(_repo_path(req.repo_root, REQUIREMENTS_MD), requirements_md + "\n")
    _write_text(_repo_path(req.repo_root, ROADMAP_MD), roadmap_md + "\n")
    _write_text(_repo_path(req.repo_root, STATE_MD), state_md + "\n")


def _derive_phases_from_task_dag(tasks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str], list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    task_ids: list[str] = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = _as_str(task.get("task_id"))
        if task_id:
            task_ids.append(task_id)
    task_set = set(task_ids)

    indegree: dict[str, int] = {task_id: 0 for task_id in task_ids}
    outgoing: dict[str, list[str]] = {task_id: [] for task_id in task_ids}
    deps_by_task: dict[str, list[str]] = {}
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = _as_str(task.get("task_id"))
        if not task_id:
            continue
        deps: list[str] = []
        raw_deps = task.get("depends_on")
        if raw_deps is None:
            raw_deps = []
        if not isinstance(raw_deps, list):
            errors.append({"code": "dependency_graph_invalid", "message": f"task {task_id} depends_on must be a list"})
            continue
        for dep in raw_deps:
            dep_id = _as_str(dep)
            if not dep_id:
                continue
            if dep_id not in task_set:
                errors.append({"code": "dependency_graph_invalid", "message": f"task {task_id} depends on unknown task {dep_id}"})
                continue
            deps.append(dep_id)
            indegree[task_id] += 1
            outgoing[dep_id].append(task_id)
        deps_by_task[task_id] = deps

    if errors:
        return [], {}, errors

    phase_map: dict[str, str] = {}
    level: list[str] = sorted([task_id for task_id, count in indegree.items() if count == 0])
    phase_index = 1
    processed: set[str] = set()
    while level:
        phase_id = f"phase-{phase_index}"
        for task_id in level:
            phase_map[task_id] = phase_id
            processed.add(task_id)
        next_level: list[str] = []
        for task_id in level:
            for follower in outgoing.get(task_id, []):
                indegree[follower] -= 1
                if indegree[follower] == 0:
                    next_level.append(follower)
        phase_index += 1
        level = sorted(next_level)

    if len(processed) != len(task_set):
        errors.append({"code": "dependency_graph_invalid", "message": "cycle detected in task DAG"})
        return [], {}, errors

    phases: list[dict[str, Any]] = []
    phase_tasks: dict[str, list[str]] = defaultdict(list)
    for task_id in task_ids:
        phase_tasks[phase_map[task_id]].append(task_id)
    ordered_phase_ids = sorted(phase_tasks.keys(), key=lambda item: int(item.split("-")[-1]))
    for phase_id in ordered_phase_ids:
        depends_on_phase_ids: set[str] = set()
        for task_id in phase_tasks[phase_id]:
            for dep_id in deps_by_task.get(task_id, []):
                dep_phase = phase_map.get(dep_id)
                if dep_phase and dep_phase != phase_id:
                    depends_on_phase_ids.add(dep_phase)
        phases.append(
            {
                "phase_id": phase_id,
                "task_ids": sorted(phase_tasks[phase_id]),
                "depends_on_phase_ids": sorted(depends_on_phase_ids),
                "entry_criteria": ["phase_dependencies_done"],
                "exit_criteria": [
                    "all_tasks_review_done",
                    "verify_commands_passed",
                    "uat_matrix_passed",
                    "zero_open_gaps",
                ],
            }
        )
    return phases, phase_map, []


def _compute_plan_check(
    mission: str | None,
    scope: str | None,
    requirements: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
    phases: list[dict[str, Any]],
) -> dict[str, Any]:
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

    phase_ids = {
        _as_str(phase.get("phase_id"))
        for phase in phases
        if isinstance(phase, dict) and _as_str(phase.get("phase_id"))
    }
    phase_traceability_pass = True
    for task in tasks:
        if not isinstance(task, dict):
            phase_traceability_pass = False
            break
        phase_id = _as_str(task.get("phase_id"))
        if not phase_id or phase_id not in phase_ids:
            phase_traceability_pass = False
            break
    checks.append({"id": "phase_traceability", "passed": phase_traceability_pass})
    if not phase_traceability_pass:
        blocking_errors.append({"code": "phase_traceability_failed", "message": "tasks must map to valid plan phases"})

    phase_dag_pass = True
    for phase in phases:
        if not isinstance(phase, dict):
            phase_dag_pass = False
            break
        phase_id = _as_str(phase.get("phase_id"))
        deps = phase.get("depends_on_phase_ids")
        if not phase_id or not isinstance(deps, list):
            phase_dag_pass = False
            break
        for dep in deps:
            dep_id = _as_str(dep)
            if not dep_id or dep_id == phase_id or dep_id not in phase_ids:
                phase_dag_pass = False
                break
        if not phase_dag_pass:
            break
    checks.append({"id": "phase_dependency_dag_sanity", "passed": phase_dag_pass})
    if not phase_dag_pass:
        blocking_errors.append({"code": "phase_dependency_invalid", "message": "phase dependency graph is invalid"})

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
        "phase_traceability": phase_traceability_pass,
        "blocking_errors": blocking_errors,
    }


def command_plan(req: OpRequest) -> dict[str, Any]:
    repo_root = req.repo_root
    if req.command == "op-plan":
        _require_override_if_existing_plan(req, stage="plan")
    state_path = _repo_path(repo_root, STATE_JSON)
    if not state_path.exists():
        raise OpError("input_error", "state baseline missing; run /op-new-project first", stage="plan")

    state = _read_json(state_path)
    if not isinstance(state, dict):
        raise OpError("state_read_error", "planning STATE.json must be an object", stage="plan")

    mission_source, scope_source = _resolve_mission_scope_sources(req, stage="plan", required=False)
    if mission_source.get("mode") == "none":
        persisted = state.get("mission_source")
        if isinstance(persisted, dict):
            mission_source = persisted
        else:
            fallback = _as_str(state.get("mission"))
            if fallback:
                mission_source = {"mode": "inline", "value": fallback, "path": None, "display": fallback}
    if scope_source.get("mode") == "none":
        persisted = state.get("scope_source")
        if isinstance(persisted, dict):
            scope_source = persisted
        else:
            fallback = _as_str(state.get("scope"))
            if fallback:
                scope_source = {"mode": "inline", "value": fallback, "path": None, "display": fallback}
    if mission_source.get("mode") == "none" or scope_source.get("mode") == "none":
        raise OpError("input_error", "mission/scope inputs are required for planning", stage="plan")

    if req.command == "op-plan" and req.override_old_plan:
        _archive_existing_planning_artifacts(repo_root)

    validation_payload, planner_warnings, planner_artifacts = _run_llm_plan_generation(
        req,
        mission_source=mission_source,
        scope_source=scope_source,
    )

    plan_packets = validation_payload["plan_packets"]
    recomputed_plan_check = validation_payload["recomputed_plan_check"]
    plan_id = _as_str(plan_packets.get("plan_id")) or f"plan-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"

    map_payload = _read_json(_repo_path(repo_root, MAP_PATH)) if _repo_path(repo_root, MAP_PATH).exists() else {}
    if not isinstance(map_payload, dict):
        map_payload = {}

    merged_state = _state_from_bundle_inputs(
        mission_source,
        scope_source,
        req.constraints,
        map_payload,
        plan_id,
        bool(recomputed_plan_check.get("passed")),
    )
    requirements = _normalize_requirement_rows(plan_packets.get("requirements"))
    merged_state["requirements"] = requirements
    merged_state["phase_count"] = len(plan_packets.get("phases", [])) if isinstance(plan_packets.get("phases"), list) else 0
    _atomic_write_json(state_path, merged_state)

    if requirements:
        requirements_md_lines = ["# REQUIREMENTS", "", "| ID | Title |", "| --- | --- |"]
        for row in requirements:
            requirements_md_lines.append(f"| {row['id']} | {row['title']} |")
        _write_text(_repo_path(repo_root, REQUIREMENTS_MD), "\n".join(requirements_md_lines) + "\n")

    status = "completed" if bool(recomputed_plan_check.get("passed")) else "blocked_plan_check"
    summary = (
        "Plan artifacts generated by LLM planner and strict validation passed."
        if bool(recomputed_plan_check.get("passed"))
        else "Plan artifacts generated but strict plan-check failed."
    )
    return _response(
        req,
        ok=bool(recomputed_plan_check.get("passed")),
        status=status,
        summary=summary,
        warnings=planner_warnings,
        artifacts=planner_artifacts + [str(state_path)],
        next_action="/op-build" if bool(recomputed_plan_check.get("passed")) else "Fix planner bundle failures and rerun /op-plan.",
        state_ref=str(state_path),
        data={
            "plan_id": plan_id,
            "plan_ready": bool(recomputed_plan_check.get("passed")),
        },
    )


def command_initialize(req: OpRequest) -> dict[str, Any]:
    _require_override_if_existing_plan(req, stage="initialize")
    _resolve_mission_scope_sources(req, stage="initialize", required=True)
    git_bootstrap_warnings, git_bootstrap_artifacts = _ensure_git_initialized_for_initialize(req)
    _ensure_managed_gitignore_block(req.repo_root)
    map_result = command_map_codebase(req)
    new_result = command_new_project(req)

    profile_selection = _detect_profile_selection_payload()
    profile_selection_path = _repo_path(req.repo_root, PROFILE_SELECTION_JSON)
    _atomic_write_json(profile_selection_path, profile_selection)

    state_path = _repo_path(req.repo_root, STATE_JSON)
    state_payload = _read_json(state_path)
    if not isinstance(state_payload, dict):
        raise OpError("state_payload_invalid", "STATE.json must be a JSON object", stage="initialize")
    state_payload["profile_aliases"] = list(profile_selection.get("selected_aliases", []))
    state_payload["profile_selection_ref"] = str(profile_selection_path)
    state_payload["updated_at"] = utc_now_iso()
    _atomic_write_json(state_path, state_payload)

    plan_result = command_plan(req)
    state_payload = _read_json(state_path)
    if not isinstance(state_payload, dict):
        raise OpError("state_payload_invalid", "STATE.json must be a JSON object", stage="initialize")
    state_payload["profile_aliases"] = list(profile_selection.get("selected_aliases", []))
    state_payload["profile_selection_ref"] = str(profile_selection_path)
    state_payload["updated_at"] = utc_now_iso()
    _atomic_write_json(state_path, state_payload)

    rate_seed_warnings = _seed_rate_registry_if_missing(
        req.repo_root,
        stage="initialize",
        profile_selection=profile_selection,
    )

    artifacts = []
    artifacts.extend(git_bootstrap_artifacts)
    artifacts.extend(map_result.get("artifacts", []))
    artifacts.extend(new_result.get("artifacts", []))
    artifacts.extend(plan_result.get("artifacts", []))
    artifacts.append(str(profile_selection_path))
    artifacts.append(str(state_path))

    warnings = []
    warnings.extend(git_bootstrap_warnings)
    warnings.extend(map_result.get("warnings", []))
    warnings.extend(rate_seed_warnings)
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
        data={
            "plan_ready": plan_ready,
            "profile_aliases": profile_selection.get("selected_aliases", []),
        },
    )


def _fresh_build_state_payload() -> dict[str, Any]:
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
        "profile_aliases": [],
        "slot_profile_assignments": {},
        "profile_assignment_policy": "dynamic_reassign_on_gate",
        "rate_gate_state": {
            "hard_gated": False,
            "min_reset_at": None,
            "sleep_until": None,
            "manual_rerun_required": False,
        },
        "cycle_gate_decision": {
            "dispatch_blocked": False,
            "reason": None,
            "terminal_reason": None,
        },
        "remediation_state": {
            "active": False,
            "reason": None,
            "last_queued_at": None,
            "fingerprint": None,
        },
        "operator_stop": {
            "last_stop_id": None,
            "last_applied_at": None,
            "reconcile_pending": False,
        },
        "stop_affected_task_ids": [],
        "offset_recovery": {
            "handoff_offset_resets": 0,
            "last_reset_at": None,
        },
        "strict_done_checks": {},
        "current_task_pointer": None,
        "current_phase_id": None,
        "phase_exit_checks": {},
        "open_gap_ids": [],
        "active_gap_closure_phase_id": None,
        "last_gap_generation_at": None,
        "gap_retry_attempts": {},
        "gap_retry_exhausted_ids": [],
        "gap_retry_policy": {
            "max_attempts": 5,
        },
        "gap_artifact_recovery": {
            "last_recovery_at": None,
            "recovered_files": [],
            "backup_paths": [],
            "reason": None,
        },
        "stale_in_progress_policy": {
            "timeout_sec": STALE_IN_PROGRESS_TIMEOUT_SEC,
        },
        "last_task_state_fingerprint": None,
        "no_progress_watchdog": {
            "consecutive_no_progress_cycles": 0,
            "threshold_cycles": NO_PROGRESS_THRESHOLD_CYCLES,
            "last_progress_at": None,
            "triggered": False,
            "triggered_at": None,
        },
        "slot_resume_policy": {},
        "resume_fail_counts_by_slot": {},
        "last_dispatch_cycle_summary": {},
        "state_recovery": {
            "last_recovery_at": None,
            "reason": None,
            "backup_path": None,
        },
        "handoff_log_offset": 0,
        "history": [],
    }


def _load_build_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _fresh_build_state_payload()
    payload = _read_json(path)
    if not isinstance(payload, dict):
        raise OpError("state_read_error", "BUILD_STATE.json must be a JSON object", stage="build")
    payload.setdefault("strategy_ladder", STRATEGY_LADDER)
    payload.setdefault("fingerprint_attempts", {})
    payload.setdefault("history", [])
    payload.setdefault("loop_lock_id", None)
    payload.setdefault("dispatch_window", {"max_running_workers": 6, "soft_cap_active": False})
    payload.setdefault("profile_aliases", [])
    payload.setdefault("slot_profile_assignments", {})
    payload.setdefault("profile_assignment_policy", "dynamic_reassign_on_gate")
    if not isinstance(payload.get("profile_aliases"), list):
        payload["profile_aliases"] = []
    else:
        payload["profile_aliases"] = [
            alias for alias in (_as_str(item) for item in payload["profile_aliases"]) if alias
        ]
    if not isinstance(payload.get("slot_profile_assignments"), dict):
        payload["slot_profile_assignments"] = {}
    if not isinstance(payload.get("profile_assignment_policy"), str):
        payload["profile_assignment_policy"] = "dynamic_reassign_on_gate"
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
    payload.setdefault("current_phase_id", None)
    payload.setdefault("phase_exit_checks", {})
    payload.setdefault("open_gap_ids", [])
    payload.setdefault("active_gap_closure_phase_id", None)
    payload.setdefault("last_gap_generation_at", None)
    payload.setdefault("gap_retry_attempts", {})
    payload.setdefault("gap_retry_exhausted_ids", [])
    payload.setdefault("gap_retry_policy", {"max_attempts": 5})
    payload.setdefault(
        "gap_artifact_recovery",
        {
            "last_recovery_at": None,
            "recovered_files": [],
            "backup_paths": [],
            "reason": None,
        },
    )
    payload.setdefault(
        "stale_in_progress_policy",
        {
            "timeout_sec": STALE_IN_PROGRESS_TIMEOUT_SEC,
        },
    )
    payload.setdefault("last_task_state_fingerprint", None)
    payload.setdefault(
        "no_progress_watchdog",
        {
            "consecutive_no_progress_cycles": 0,
            "threshold_cycles": NO_PROGRESS_THRESHOLD_CYCLES,
            "last_progress_at": None,
            "triggered": False,
            "triggered_at": None,
        },
    )
    payload.setdefault("slot_resume_policy", {})
    payload.setdefault("resume_fail_counts_by_slot", {})
    payload.setdefault("last_dispatch_cycle_summary", {})
    if not isinstance(payload.get("slot_resume_policy"), dict):
        payload["slot_resume_policy"] = {}
    if not isinstance(payload.get("resume_fail_counts_by_slot"), dict):
        payload["resume_fail_counts_by_slot"] = {}
    if not isinstance(payload.get("last_dispatch_cycle_summary"), dict):
        payload["last_dispatch_cycle_summary"] = {}
    payload.setdefault(
        "state_recovery",
        {
            "last_recovery_at": None,
            "reason": None,
            "backup_path": None,
        },
    )
    payload.setdefault("handoff_log_offset", 0)
    payload.setdefault(
        "cycle_gate_decision",
        {
            "dispatch_blocked": False,
            "reason": None,
            "terminal_reason": None,
        },
    )
    payload.setdefault(
        "remediation_state",
        {
            "active": False,
            "reason": None,
            "last_queued_at": None,
            "fingerprint": None,
        },
    )
    payload.setdefault(
        "operator_stop",
        {
            "last_stop_id": None,
            "last_applied_at": None,
            "reconcile_pending": False,
        },
    )
    payload.setdefault("stop_affected_task_ids", [])
    payload.setdefault(
        "offset_recovery",
        {
            "handoff_offset_resets": 0,
            "last_reset_at": None,
        },
    )
    no_progress = payload.get("no_progress_watchdog")
    if not isinstance(no_progress, dict):
        no_progress = {}
    no_progress["consecutive_no_progress_cycles"] = _coerce_nonneg_int(
        no_progress.get("consecutive_no_progress_cycles"),
        default=0,
    )
    no_progress["threshold_cycles"] = NO_PROGRESS_THRESHOLD_CYCLES
    no_progress["triggered"] = _as_bool(no_progress.get("triggered"), default=False)
    no_progress.setdefault("last_progress_at", None)
    no_progress.setdefault("triggered_at", None)
    payload["no_progress_watchdog"] = no_progress
    return payload


def _run_controller_cycle(
    req: OpRequest,
    *,
    control_number: int,
    control_run_id: str,
    profile_aliases: list[str] | None = None,
) -> dict[str, Any]:
    script = _resolve_skill_script("optimus-cycle-controller", "optimus_cycle_controller.py")

    payload = {
        "repo_root": str(req.repo_root),
        "control_number": int(control_number),
        "control_run_id": control_run_id,
        "profile_aliases": profile_aliases or ["codex"],
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
    returned_control_number = _coerce_nonneg_int(parsed.get("control_number"), default=0)
    if returned_control_number != int(control_number):
        raise OpError(
            "runtime_error",
            (
                "controller control_number mismatch: "
                f"expected {int(control_number)} got {returned_control_number}"
            ),
            stage="build",
        )
    returned_run_id = _as_str(parsed.get("control_run_id"))
    if returned_run_id != control_run_id:
        raise OpError(
            "runtime_error",
            (
                "controller control_run_id mismatch: "
                f"expected {control_run_id} got {returned_run_id}"
            ),
            stage="build",
        )
    return parsed


def _verify_final_state(req: OpRequest, final_state_path: Path) -> dict[str, Any]:
    script = _resolve_skill_script("optimus-cycle-controller", "optimus_cycle_controller.py")
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


def _detect_blocker_fingerprint(repo_root: Path, *, warnings_sink: list[dict[str, Any]] | None = None) -> str:
    runtime_health_path = repo_root / "reports" / "optimus-prime" / "runtime" / "RUNTIME_HEALTH.json"
    if runtime_health_path.exists():
        try:
            payload = _read_json(runtime_health_path)
        except OpError as exc:
            if isinstance(warnings_sink, list):
                warnings_sink.append(
                    {
                        "code": "runtime_health_invalid_json",
                        "message": f"runtime health unreadable; falling back to unknown fingerprint: {exc.message}",
                        "stage": "build_loop",
                    }
                )
            payload = None
        if isinstance(payload, dict):
            fp = _as_str(payload.get("last_failure_fingerprint"))
            if fp:
                return fp

    blockers_path = repo_root / "reports" / "optimus-prime" / "BLOCKERS.jsonl"
    if blockers_path.exists():
        try:
            lines = blockers_path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as exc:
            if isinstance(warnings_sink, list):
                warnings_sink.append(
                    {
                        "code": "blockers_log_unreadable",
                        "message": f"blockers log unreadable; falling back to unknown fingerprint: {exc}",
                        "stage": "build_loop",
                    }
                )
            lines = []
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
    resolved_mode = _resolve_test_train_mode(repo_root)
    if strategy in {"self_heal", "runtime_repair"}:
        script = _resolve_skill_script("runtime-coordinator", "runtime_coordinator.py", required=False)
        if script is None:
            return {"action": strategy, "status": "skipped", "reason": "runtime-coordinator missing"}
        payload = {
            "repo_root": str(repo_root),
            "action": "repair",
            "test_train_mode": resolved_mode,
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


def _apply_handoff_updates(repo_root: Path, task_state: dict[str, Any], build_state: dict[str, Any]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    handoff_path = repo_root / "reports" / "optimus-prime" / "HANDOFF_LOG.jsonl"
    rows = _read_jsonl(handoff_path)
    offset = int(build_state.get("handoff_log_offset", 0))
    if offset < 0:
        offset = 0
    if offset > len(rows):
        old_offset = offset
        offset = 0
        recovery = build_state.get("offset_recovery")
        if not isinstance(recovery, dict):
            recovery = {
                "handoff_offset_resets": 0,
                "last_reset_at": None,
            }
            build_state["offset_recovery"] = recovery
        recovery["handoff_offset_resets"] = int(recovery.get("handoff_offset_resets", 0)) + 1
        recovery["last_reset_at"] = utc_now_iso()
        warnings.append(
            {
                "code": "handoff_offset_reset",
                "message": f"handoff_log_offset reset due to truncation: old_offset={old_offset}, line_count={len(rows)}",
                "stage": "build_loop",
            }
        )
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
            evidence = {
                "task_evidence_ref": str(_canonical_task_evidence_rel(task_id)),
                "dev_ready_evidence_ref": str(_canonical_task_evidence_rel(task_id)),
                "verify_results": [],
                "uat_results": [],
            }
            task["evidence"] = evidence

        task_evidence_ref = _as_str(row.get("task_evidence_ref")) or _as_str(row.get("dev_ready_evidence_ref"))
        if task_evidence_ref:
            evidence["task_evidence_ref"] = task_evidence_ref
            evidence["dev_ready_evidence_ref"] = task_evidence_ref
        task["last_progress_at"] = utc_now_iso()

        result = (_as_str(row.get("result")) or _as_str(row.get("status")) or "").lower()
        if result in {"blocked", "failed", "error", "dispatch_failed"}:
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
    build_state["handoff_log_offset"] = len(rows)
    return warnings


def _fan_in_worker_artifacts(repo_root: Path, build_state: dict[str, Any]) -> list[dict[str, Any]]:
    """Sync worker worktree artifacts into canonical repo reports before state reconciliation."""
    warnings: list[dict[str, Any]] = []
    registry_path = repo_root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
    _, workers, _ = _load_worker_registry(registry_path)
    canonical_evidence_root = _repo_path(repo_root, EVIDENCE_REL)
    canonical_handoff_path = repo_root / "reports" / "optimus-prime" / "HANDOFF_LOG.jsonl"

    canonical_handoff_rows = _read_jsonl(canonical_handoff_path)
    canonical_handoff_fingerprints: set[str] = set()
    for row in canonical_handoff_rows:
        if not isinstance(row, dict):
            continue
        canonical_handoff_fingerprints.add(
            _sha256(json.dumps(row, sort_keys=True, separators=(",", ":")))
        )

    worktrees_scanned = 0
    evidence_files_synced = 0
    handoff_rows_synced = 0

    for worker in workers:
        if not isinstance(worker, dict):
            continue
        role = _as_str(worker.get("role"))
        if role not in {"developer", "tester", "reviewer"}:
            continue
        worktree_root_raw = _as_str(worker.get("worktree_root"))
        if not worktree_root_raw:
            continue
        try:
            worktree_root = Path(worktree_root_raw).expanduser().resolve()
        except OSError as exc:
            warnings.append(
                {
                    "code": "worktree_artifact_scan_failed",
                    "message": f"invalid worktree_root for slot {_as_str(worker.get('slot')) or 'unknown'}: {exc}",
                    "stage": "build_loop",
                }
            )
            continue
        if worktree_root == repo_root or not worktree_root.exists() or not worktree_root.is_dir():
            continue
        worktrees_scanned += 1

        source_evidence_root = worktree_root / "reports" / "optimus-prime" / "planning" / "evidence"
        if source_evidence_root.exists() and source_evidence_root.is_dir():
            for evidence_path in source_evidence_root.rglob("TASK_EVIDENCE.json"):
                task_id = evidence_path.parent.name
                if not task_id:
                    continue
                try:
                    payload = _read_json(evidence_path)
                except OpError as exc:
                    warnings.append(
                        {
                            "code": "worktree_artifact_scan_failed",
                            "message": f"invalid worker TASK_EVIDENCE for {task_id}: {exc.message}",
                            "stage": "build_loop",
                            "artifact": str(evidence_path),
                        }
                    )
                    continue
                if not isinstance(payload, dict):
                    continue
                destination = canonical_evidence_root / task_id / "TASK_EVIDENCE.json"
                should_sync = not destination.exists()
                if not should_sync:
                    try:
                        should_sync = evidence_path.stat().st_mtime > destination.stat().st_mtime
                    except OSError:
                        should_sync = True
                if should_sync:
                    _atomic_write_json(destination, payload)
                    evidence_files_synced += 1

        source_handoff_path = worktree_root / "reports" / "optimus-prime" / "HANDOFF_LOG.jsonl"
        if source_handoff_path.exists():
            try:
                source_rows = _read_jsonl(source_handoff_path)
            except OpError as exc:
                warnings.append(
                    {
                        "code": "worktree_artifact_scan_failed",
                        "message": f"invalid worker HANDOFF_LOG.jsonl: {exc.message}",
                        "stage": "build_loop",
                        "artifact": str(source_handoff_path),
                    }
                )
                source_rows = []
            for row in source_rows:
                if not isinstance(row, dict):
                    continue
                fingerprint = _sha256(json.dumps(row, sort_keys=True, separators=(",", ":")))
                if fingerprint in canonical_handoff_fingerprints:
                    continue
                _append_jsonl(canonical_handoff_path, row)
                canonical_handoff_fingerprints.add(fingerprint)
                handoff_rows_synced += 1

    build_state["artifact_fan_in"] = {
        "last_sync_at": utc_now_iso(),
        "worktrees_scanned": worktrees_scanned,
        "evidence_files_synced": evidence_files_synced,
        "handoff_rows_synced": handoff_rows_synced,
    }
    if evidence_files_synced or handoff_rows_synced:
        warnings.append(
            {
                "code": "worktree_artifacts_synced",
                "message": (
                    "synced worker artifacts from worktrees "
                    f"(evidence_files={evidence_files_synced}, handoff_rows={handoff_rows_synced})"
                ),
                "stage": "build_loop",
                "details": build_state["artifact_fan_in"],
            }
        )
    return warnings


def _dispatch_task_packet(
    req: OpRequest,
    task: dict[str, Any],
    plan_task: dict[str, Any],
    stage: str,
    plan_id: str,
    codex_profile_alias: str,
    lane_id: str | None = None,
    dispatch_mode: str = "exec",
    resume_thread_id: str | None = None,
    slot_override: str | None = None,
    worktree_root_override: str | None = None,
    branch_name_override: str | None = None,
    start_from_branch_override: str | None = None,
    start_from_commit_override: str | None = None,
    test_source_branch_override: str | None = None,
    test_source_commit_override: str | None = None,
) -> dict[str, Any]:
    script = _resolve_skill_script("dispatch-worker-packet", "dispatch_worker_packet.py")
    task_id = _as_str(task.get("task_id")) or "TASK-UNKNOWN"
    requirement_ids = [
        rid
        for rid in ((_as_str(item) for item in task.get("requirement_ids", [])))
        if rid
    ]
    requirement_fallback_used = _as_bool_field(task.get("requirement_fallback_used")) or _as_bool_field(
        plan_task.get("requirement_fallback_used")
    )
    dispatch_warnings: list[dict[str, Any]] = []
    if requirement_fallback_used:
        dispatch_warnings.append(
            {
                "code": "gap_closure_requirement_fallback",
                "message": f"using fallback requirement_ids for gap closure task {task_id}",
                "stage": "build_loop",
                "task_id": task_id,
            }
        )
    acceptance_refs = [
        item
        for item in ((_as_str(item) for item in plan_task.get("must_haves", [])))
        if item
    ]
    if not acceptance_refs:
        acceptance_refs = [f"{task_id} acceptance"]
    evidence_ref = _as_str((task.get("evidence") or {}).get("task_evidence_ref"))
    if not evidence_ref:
        evidence_ref = str(_canonical_task_evidence_rel(task_id))
        task.setdefault("evidence", {})["task_evidence_ref"] = evidence_ref
    task.setdefault("evidence", {})["dev_ready_evidence_ref"] = evidence_ref

    stage_cfg = {
        "dev": {"slot": "dev-1", "role": "developer", "status": TASK_STATUS_DEV_WORKING, "attempt_key": "dev"},
        "test": {"slot": "test-1", "role": "tester", "status": TASK_STATUS_TESTING, "attempt_key": "test"},
        "review": {"slot": "review-1", "role": "reviewer", "status": TASK_STATUS_REVIEWING, "attempt_key": "review"},
    }
    cfg = stage_cfg[stage]
    slot_name = slot_override or cfg["slot"]
    start_from_branch = _as_str(start_from_branch_override) or "RAB-BASE"
    start_from_commit = _as_str(start_from_commit_override)
    if not start_from_commit:
        start_from_commit = _git_text(req.repo_root, "rev-parse", start_from_branch)
    if not start_from_commit:
        start_from_commit = _git_text(req.repo_root, "rev-parse", "HEAD") or "HEAD"
    worktree_root = worktree_root_override or str(req.repo_root)
    branch_name = branch_name_override or f"codex/{slot_name}/{task_id.lower()}"
    payload = {
        "slot": slot_name,
        "role": cfg["role"],
        "task_identifier": task_id,
        "repo_root": str(req.repo_root),
        "worktree_root": worktree_root,
        "branch_name": branch_name,
        "start_from_branch": start_from_branch,
        "start_from_commit": start_from_commit,
        "acceptance_criteria": acceptance_refs,
        "packet_version": 1,
        "codex_profile_alias": codex_profile_alias,
        "mcp_mode": "disable-all",
        "mcp_allowlist": [],
        "sandbox_mode": "danger-full-access",
        "sandbox_add_dirs": [],
        "test_train_mode": "off",
        "op_build_mode": True,
        "plan_id": plan_id,
        "requirement_ids": requirement_ids,
        "task_acceptance_refs": acceptance_refs,
        "dev_ready_evidence_ref": evidence_ref,
        "dispatch_mode": dispatch_mode,
        "resume_thread_id": resume_thread_id,
        "lane_id": lane_id,
        "test_source_branch": _as_str(test_source_branch_override) or None,
        "test_source_commit": _as_str(test_source_commit_override) or None,
        "dry_run": req.dry_run,
        "cycle_note": f"/op-build:{stage}:{task_id}",
    }
    result = _run_tool_json(script, payload, req.repo_root)
    if _as_bool_field(result.get("ok")):
        task["status"] = cfg["status"]
        task["owner_slot"] = slot_name
        if lane_id:
            task["lane_id"] = lane_id
        task["dispatch_thread_id"] = _as_str(result.get("dispatch_thread_id")) or _as_str(
            (result.get("dispatch") or {}).get("dispatch_thread_id")
        )
        task["active_branch"] = _as_str(payload.get("branch_name"))
        task["last_progress_at"] = utc_now_iso()
        attempts = task.get("attempts")
        if not isinstance(attempts, dict):
            attempts = {"dev": 0, "test": 0, "review": 0}
            task["attempts"] = attempts
        attempts[cfg["attempt_key"]] = int(attempts.get(cfg["attempt_key"], 0)) + 1
        out = {"ok": True, "task_id": task_id, "stage": stage, "dispatch": result}
        if dispatch_warnings:
            out["warnings"] = dispatch_warnings
        return out
    task["status"] = "blocked"
    task["owner_slot"] = None
    task["last_progress_at"] = utc_now_iso()
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
    out = {"ok": False, "task_id": task_id, "stage": stage, "dispatch": result}
    if dispatch_warnings:
        out["warnings"] = dispatch_warnings
    return out


def _load_work_dispatch_plan_assignments(
    repo_root: Path,
    *,
    active_phase_id: str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
    path = _repo_path(repo_root, WORK_DISPATCH_PLAN_JSON)
    warnings: list[dict[str, Any]] = []
    if not path.exists():
        warnings.append(
            {
                "code": "dispatch_plan_missing",
                "message": f"dispatch plan artifact is missing: {path}",
                "stage": "build_loop",
            }
        )
        return [], warnings, False
    try:
        payload = _read_json(path)
    except OpError as exc:
        warnings.append(
            {
                "code": "dispatch_plan_invalid",
                "message": f"dispatch plan unreadable: {exc.message}",
                "stage": "build_loop",
                "artifact": str(path),
            }
        )
        return [], warnings, False
    if not isinstance(payload, dict):
        warnings.append(
            {
                "code": "dispatch_plan_invalid",
                "message": "dispatch plan payload must be JSON object",
                "stage": "build_loop",
                "artifact": str(path),
            }
        )
        return [], warnings, False
    assignments_raw = payload.get("assignments")
    if not isinstance(assignments_raw, list):
        warnings.append(
            {
                "code": "dispatch_plan_invalid",
                "message": "dispatch plan assignments must be a list",
                "stage": "build_loop",
                "artifact": str(path),
            }
        )
        return [], warnings, False
    if not assignments_raw:
        warnings.append(
            {
                "code": "dispatch_plan_no_assignments",
                "message": "dispatch plan contains no assignments for this cycle",
                "stage": "build_loop",
                "artifact": str(path),
            }
        )
        return [], warnings, True

    expected_active_phase = active_phase_id or _as_str(payload.get("active_phase_id"))
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(assignments_raw):
        if not isinstance(row, dict):
            warnings.append(
                {
                    "code": "dispatch_assignment_invalid",
                    "message": f"assignment #{idx + 1} must be object",
                    "stage": "build_loop",
                    "artifact": str(path),
                    "index": idx,
                }
            )
            continue
        task_id = _as_str(row.get("task_id"))
        lane_id = _as_str(row.get("lane_id"))
        phase_id = _as_str(row.get("phase_id")) or expected_active_phase
        next_stage = _as_str(row.get("next_stage"))
        next_role = _as_str(row.get("next_role"))
        slot = _as_str(row.get("slot"))
        dispatch_policy = _as_str(row.get("dispatch_policy")) or "resume_if_same_lane"
        if not task_id or not lane_id or not phase_id or not next_stage or not next_role or not slot:
            warnings.append(
                {
                    "code": "dispatch_assignment_invalid",
                    "message": f"assignment #{idx + 1} missing required fields",
                    "stage": "build_loop",
                    "artifact": str(path),
                    "index": idx,
                }
            )
            continue
        if next_stage not in {"dev", "test", "review"}:
            warnings.append(
                {
                    "code": "dispatch_assignment_invalid",
                    "message": f"assignment #{idx + 1} has invalid next_stage={next_stage}",
                    "stage": "build_loop",
                    "artifact": str(path),
                    "index": idx,
                }
            )
            continue
        if dispatch_policy not in {"resume_if_same_lane", "new_thread"}:
            warnings.append(
                {
                    "code": "dispatch_assignment_invalid",
                    "message": f"assignment #{idx + 1} has invalid dispatch_policy={dispatch_policy}",
                    "stage": "build_loop",
                    "artifact": str(path),
                    "index": idx,
                }
            )
            continue
        if expected_active_phase and phase_id != expected_active_phase:
            continue
        out.append(
            {
                "task_id": task_id,
                "lane_id": lane_id,
                "phase_id": phase_id,
                "next_stage": next_stage,
                "next_role": next_role,
                "slot": slot,
                "dispatch_policy": dispatch_policy,
            }
        )
    if not out:
        warnings.append(
            {
                "code": "dispatch_plan_no_assignments",
                "message": "dispatch plan has no valid assignments for active phase",
                "stage": "build_loop",
                "artifact": str(path),
            }
        )
    return out, warnings, True


def _dispatch_next_task_from_assignments(
    req: OpRequest,
    plan_packets: dict[str, Any],
    task_state: dict[str, Any],
    build_state: dict[str, Any],
    assignments: list[dict[str, Any]],
) -> dict[str, Any]:
    task_map = _task_by_id(task_state)
    plan_map = _plan_task_map(plan_packets)
    registry_path = req.repo_root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
    registry_base, registry_workers, registry_shape = _load_worker_registry(registry_path)
    workers_by_slot = {
        _as_str(worker.get("slot")): worker
        for worker in registry_workers
        if isinstance(worker, dict) and _as_str(worker.get("slot"))
    }
    slot_count = len(FIXED_WORKER_SLOTS)
    plan_id = _as_str(plan_packets.get("plan_id")) or "plan-unknown"
    stage_status_requirements = {
        "dev": {TASK_STATUS_PENDING},
        "test": {TASK_STATUS_DEV_DONE},
        "review": {TASK_STATUS_TESTS_DONE},
    }
    dispatch_window = build_state.get("dispatch_window") if isinstance(build_state.get("dispatch_window"), dict) else {}
    max_dispatch_per_cycle = max(1, _coerce_nonneg_int(dispatch_window.get("max_assignments_per_cycle"), default=3))
    slot_resume_policy = build_state.get("slot_resume_policy")
    if not isinstance(slot_resume_policy, dict):
        slot_resume_policy = {}
        build_state["slot_resume_policy"] = slot_resume_policy
    resume_fail_counts = build_state.get("resume_fail_counts_by_slot")
    if not isinstance(resume_fail_counts, dict):
        resume_fail_counts = {}
        build_state["resume_fail_counts_by_slot"] = resume_fail_counts

    def _persist_worker_slot_transition(
        *,
        slot_name: str,
        lane_value: str | None,
        active_task_id: str | None,
        dispatch_thread_id: str | None,
        dispatch_mode_used: str | None,
        branch_name: str | None,
        worktree_root: str | None,
    ) -> None:
        row = workers_by_slot.get(slot_name)
        if not isinstance(row, dict):
            row = _default_worker_row(slot_name)
            registry_workers.append(row)
            workers_by_slot[slot_name] = row
        _apply_slot_lane_transition(row, lane_value)
        row["active_task_id"] = active_task_id
        row["active_task"] = active_task_id
        if dispatch_thread_id:
            row["dispatch_thread_id"] = dispatch_thread_id
        if branch_name:
            row["branch"] = branch_name
        if worktree_root:
            row["worktree_root"] = worktree_root
        row["session_state"] = "running"
        row["state"] = "running"
        row["updated_at"] = utc_now_iso()
        if _as_str(dispatch_mode_used):
            row["dispatch_mode"] = _as_str(dispatch_mode_used)
        _write_worker_registry(
            registry_path,
            registry_base,
            registry_workers,
            registry_shape if registry_shape in {"dict_list", "dict_dict", "list"} else "dict_list",
        )

    all_warnings: list[dict[str, Any]] = []
    first_failure: dict[str, Any] | None = None
    dispatch_successes: list[dict[str, Any]] = []
    dispatched_count = 0
    assignment_observations: list[dict[str, Any]] = []
    observations_path = _repo_path(req.repo_root, DISPATCH_ASSIGNMENT_OBSERVATIONS_JSONL)

    def _record_assignment_observation(
        *,
        row: dict[str, Any],
        status: str,
        reason_code: str,
        started_at: float,
        warning_codes: list[str] | None = None,
        selected_alias: str | None = None,
        dispatch_mode: str | None = None,
    ) -> None:
        assignment_observations.append(
            {
                "timestamp": utc_now_iso(),
                "cycle": int(build_state.get("last_cycle", 0)),
                "task_id": _as_str(row.get("task_id")),
                "slot": _as_str(row.get("slot")),
                "lane_id": _as_str(row.get("lane_id")),
                "next_stage": _as_str(row.get("next_stage")),
                "dispatch_policy": _as_str(row.get("dispatch_policy")),
                "status": status,
                "reason_code": reason_code,
                "duration_ms": int(max(0.0, (time.perf_counter() - started_at) * 1000.0)),
                "selected_alias": selected_alias,
                "dispatch_mode": dispatch_mode,
                "warning_codes": [code for code in (warning_codes or []) if code],
            }
        )

    def _persist_assignment_observations(warnings_target: list[dict[str, Any]]) -> None:
        if not assignment_observations:
            return
        write_failed = False
        for obs in assignment_observations:
            try:
                _append_jsonl(observations_path, obs)
            except OpError as exc:
                if not write_failed:
                    warnings_target.append(
                        {
                            "code": "dispatch_observation_write_failed",
                            "message": f"failed to persist dispatch assignment observations: {exc.message}",
                            "stage": "build_loop",
                            "artifact": str(observations_path),
                        }
                    )
                    write_failed = True

    for row in assignments:
        started = time.perf_counter()
        task_id = _as_str(row.get("task_id"))
        lane_id = _as_str(row.get("lane_id"))
        next_stage = _as_str(row.get("next_stage"))
        slot_name = _as_str(row.get("slot"))
        dispatch_policy = _as_str(row.get("dispatch_policy")) or "resume_if_same_lane"
        if dispatched_count >= max_dispatch_per_cycle:
            _record_assignment_observation(
                row=row,
                status="skipped",
                reason_code="dispatch_cycle_cap_reached",
                started_at=started,
            )
            continue
        if not task_id or not lane_id or next_stage not in {"dev", "test", "review"} or not slot_name:
            _record_assignment_observation(
                row=row,
                status="invalid",
                reason_code="dispatch_assignment_invalid",
                started_at=started,
                warning_codes=["dispatch_assignment_invalid"],
            )
            all_warnings.append(
                {
                    "code": "dispatch_assignment_invalid",
                    "message": f"invalid assignment row: {row}",
                    "stage": "build_loop",
                    "assignment": row,
                }
            )
            continue
        task = task_map.get(task_id)
        plan_task = plan_map.get(task_id) if isinstance(plan_map.get(task_id), dict) else {}
        if not isinstance(task, dict) or not isinstance(plan_task, dict):
            _record_assignment_observation(
                row=row,
                status="invalid",
                reason_code="dispatch_assignment_unknown_task",
                started_at=started,
                warning_codes=["dispatch_assignment_invalid"],
            )
            all_warnings.append(
                {
                    "code": "dispatch_assignment_invalid",
                    "message": f"assignment references unknown task: {task_id}",
                    "stage": "build_loop",
                    "assignment": row,
                }
            )
            continue
        status = _normalize_task_status(task.get("status"))
        if status not in stage_status_requirements[next_stage]:
            _record_assignment_observation(
                row=row,
                status="skipped",
                reason_code="dispatch_assignment_stage_not_ready",
                started_at=started,
            )
            continue

        slot_worker = workers_by_slot.get(slot_name) if isinstance(workers_by_slot.get(slot_name), dict) else {}
        worktree_root = _as_str(slot_worker.get("worktree_root"))
        branch_name = _as_str(slot_worker.get("branch"))
        if not worktree_root or not branch_name:
            if req.dry_run:
                worktree_root = str(req.repo_root)
                branch_name = f"codex/{slot_name}/{task_id.lower()}"
                all_warnings.append(
                    {
                        "code": "dispatch_assignment_invalid",
                        "message": f"slot {slot_name} missing prepared workstation; using dry-run fallback context",
                        "stage": "build_loop",
                        "task_id": task_id,
                        "slot": slot_name,
                    }
                )
            else:
                all_warnings.append(
                    {
                        "code": "dispatch_assignment_invalid",
                        "message": f"slot {slot_name} missing prepared worktree/branch context",
                        "stage": "build_loop",
                        "task_id": task_id,
                        "slot": slot_name,
                    }
                )
                _record_assignment_observation(
                    row=row,
                    status="skipped",
                    reason_code="dispatch_assignment_missing_workstation_context",
                    started_at=started,
                    warning_codes=["dispatch_assignment_invalid"],
                )
                continue
        if not worktree_root or not branch_name:
            _record_assignment_observation(
                row=row,
                status="invalid",
                reason_code="dispatch_assignment_invalid_context",
                started_at=started,
                warning_codes=["dispatch_assignment_invalid"],
            )
            all_warnings.append(
                {
                    "code": "dispatch_assignment_invalid",
                    "message": f"slot {slot_name} has invalid dispatch context",
                    "stage": "build_loop",
                    "task_id": task_id,
                    "slot": slot_name,
                }
            )
            continue

        start_from_branch_override = "RAB-BASE"
        start_from_commit_override: str | None = None
        test_source_branch_override: str | None = None
        test_source_commit_override: str | None = None
        if next_stage == "test":
            source_branch = _as_str(task.get("active_branch"))
            if not source_branch:
                all_warnings.append(
                    {
                        "code": "dispatch_assignment_missing_dev_branch",
                        "message": f"task {task_id} missing active developer branch for test-stage dispatch",
                        "stage": "build_loop",
                        "task_id": task_id,
                        "slot": slot_name,
                    }
                )
                _record_assignment_observation(
                    row=row,
                    status="skipped",
                    reason_code="dispatch_assignment_missing_dev_branch",
                    started_at=started,
                    warning_codes=["dispatch_assignment_missing_dev_branch"],
                )
                continue
            source_commit = _git_text(req.repo_root, "rev-parse", source_branch)
            if not source_commit:
                all_warnings.append(
                    {
                        "code": "dispatch_assignment_missing_dev_branch",
                        "message": f"unable to resolve HEAD commit for developer branch {source_branch}",
                        "stage": "build_loop",
                        "task_id": task_id,
                        "slot": slot_name,
                    }
                )
                _record_assignment_observation(
                    row=row,
                    status="skipped",
                    reason_code="dispatch_assignment_missing_dev_branch",
                    started_at=started,
                    warning_codes=["dispatch_assignment_missing_dev_branch"],
                )
                continue
            start_from_branch_override = source_branch
            start_from_commit_override = source_commit
            test_source_branch_override = source_branch
            test_source_commit_override = source_commit
            branch_name = f"codex/{slot_name}/{task_id.lower()}-test"

        previous_lane = _as_str(slot_worker.get("lane_id"))
        previous_thread_id = _as_str(task.get("dispatch_thread_id")) or _as_str(slot_worker.get("dispatch_thread_id"))
        slot_resume_mode = (_as_str(slot_resume_policy.get(slot_name)) or "resume_allowed").lower()
        same_lane_resume = (
            dispatch_policy == "resume_if_same_lane"
            and slot_resume_mode != "exec_only"
            and bool(lane_id and previous_lane and lane_id == previous_lane and previous_thread_id)
        )
        dispatch_mode = "resume" if same_lane_resume else "exec"
        resume_thread_id = previous_thread_id if same_lane_resume else None

        selection = _select_profile_alias_for_slot(
            req.repo_root,
            build_state,
            slot=slot_name,
            slot_count=slot_count,
        )
        if not _as_bool(selection.get("ok"), default=False):
            warning_row = selection.get("warning") if isinstance(selection.get("warning"), dict) else None
            if warning_row:
                all_warnings.append(warning_row)
            _record_assignment_observation(
                row=row,
                status="skipped",
                reason_code=_as_str(selection.get("reason")) or "profile_selection_invalid",
                started_at=started,
                warning_codes=[_as_str(warning_row.get("code"))] if isinstance(warning_row, dict) else None,
            )
            continue
        selected_alias = _as_str(selection.get("alias")) or "codex"
        alias_state = _read_profile_rate_states(req.repo_root, [selected_alias]).get(selected_alias, {})
        if bool(alias_state.get("hard_gated")):
            _record_assignment_observation(
                row=row,
                status="skipped",
                reason_code="dispatch_skipped_hard_gate_alias",
                started_at=started,
                selected_alias=selected_alias,
                warning_codes=["dispatch_skipped_hard_gate_alias"],
            )
            all_warnings.append(
                {
                    "code": "dispatch_skipped_hard_gate_alias",
                    "message": (
                        f"dispatch skipped: selected alias is hard-gated "
                        f"(alias={selected_alias}, slot={slot_name}, task={task_id})"
                    ),
                    "stage": "build_loop",
                    "alias": selected_alias,
                    "slot": slot_name,
                    "task_id": task_id,
                }
            )
            continue
        if bool(alias_state.get("soft_gated")):
            active_by_alias = _active_worker_count_by_alias(req.repo_root)
            if int(active_by_alias.get(selected_alias, 0)) >= 1:
                _record_assignment_observation(
                    row=row,
                    status="skipped",
                    reason_code="dispatch_skipped_soft_cap",
                    started_at=started,
                    selected_alias=selected_alias,
                    warning_codes=["dispatch_skipped_soft_cap"],
                )
                all_warnings.append(
                    {
                        "code": "dispatch_skipped_soft_cap",
                        "message": f"dispatch skipped for soft-gated alias cap (alias={selected_alias}, cap=1)",
                        "stage": "build_loop",
                        "alias": selected_alias,
                    }
                )
                continue

        result = _dispatch_task_packet(
            req,
            task,
            plan_task,
            next_stage,
            plan_id,
            selected_alias,
            lane_id=lane_id,
            dispatch_mode=dispatch_mode,
            resume_thread_id=resume_thread_id,
            slot_override=slot_name,
            worktree_root_override=worktree_root,
            branch_name_override=branch_name,
            start_from_branch_override=start_from_branch_override,
            start_from_commit_override=start_from_commit_override,
            test_source_branch_override=test_source_branch_override,
            test_source_commit_override=test_source_commit_override,
        )
        dispatch_payload_for_warnings = result.get("dispatch") if isinstance(result.get("dispatch"), dict) else {}
        warning_rows = result.get("warnings") if isinstance(result.get("warnings"), list) else []
        tool_warning_rows = (
            dispatch_payload_for_warnings.get("warnings")
            if isinstance(dispatch_payload_for_warnings.get("warnings"), list)
            else []
        )
        warning_rows.extend([item for item in tool_warning_rows if isinstance(item, dict)])
        effective_mode_hint = _as_str(dispatch_payload_for_warnings.get("dispatch_mode_used")) or dispatch_mode
        if dispatch_mode == "resume":
            warning_rows.append(
                {
                    "code": "dispatch_resumed_thread"
                    if effective_mode_hint == "resume"
                    else "dispatch_resume_failed_fallback_exec",
                    "message": (
                        f"slot {slot_name} resumed existing thread for same-lane task"
                        if effective_mode_hint == "resume"
                        else f"slot {slot_name} failed to resume thread; fallback dispatch used new thread"
                    ),
                    "stage": "build_loop",
                    "slot": slot_name,
                    "lane_id": lane_id,
                }
            )
        elif previous_lane and lane_id != previous_lane:
            warning_rows.append(
                {
                    "code": "dispatch_new_thread_lane_change",
                    "message": f"slot {slot_name} lane changed {previous_lane} -> {lane_id}; started new thread",
                    "stage": "build_loop",
                    "slot": slot_name,
                    "from_lane_id": previous_lane,
                    "to_lane_id": lane_id,
                }
            )
        selection_warning = selection.get("warning")
        if isinstance(selection_warning, dict):
            warning_rows.append(selection_warning)
        if warning_rows:
            result["warnings"] = warning_rows

        if _as_bool(result.get("ok"), default=False):
            dispatch_payload = result.get("dispatch") if isinstance(result.get("dispatch"), dict) else {}
            effective_mode = _as_str(dispatch_payload.get("dispatch_mode_used")) or dispatch_mode
            warning_codes = [
                _as_str(item.get("code"))
                for item in warning_rows
                if isinstance(item, dict) and _as_str(item.get("code"))
            ]
            _record_assignment_observation(
                row=row,
                status="dispatched",
                reason_code="dispatch_ok",
                started_at=started,
                selected_alias=selected_alias,
                dispatch_mode=effective_mode,
                warning_codes=warning_codes,
            )
            all_warnings.extend([item for item in warning_rows if isinstance(item, dict)])
            if dispatch_mode == "resume":
                resume_failure_codes = {
                    "dispatch_resume_early_exit",
                    "dispatch_resume_notty_detected",
                    "dispatch_resume_failed_fallback_exec",
                }
                if any(code in resume_failure_codes for code in warning_codes):
                    retry_value = _coerce_nonneg_int(resume_fail_counts.get(slot_name), default=0) + 1
                    resume_fail_counts[slot_name] = retry_value
                    slot_resume_policy[slot_name] = "exec_only"
                    all_warnings.append(
                        {
                            "code": "dispatch_resume_temporarily_disabled_slot",
                            "message": (
                                f"slot {slot_name} switched to exec_only after resume startup failure "
                                f"(count={retry_value})"
                            ),
                            "stage": "build_loop",
                            "slot": slot_name,
                            "retry_count": retry_value,
                        }
                    )
                elif effective_mode == "resume":
                    resume_fail_counts[slot_name] = 0
            if (
                dispatch_mode != "resume"
                and effective_mode == "exec"
                and _as_str(dispatch_payload.get("dispatch_thread_id"))
            ):
                slot_resume_policy[slot_name] = "resume_allowed"
                resume_fail_counts[slot_name] = 0
            _persist_worker_slot_transition(
                slot_name=slot_name,
                lane_value=lane_id,
                active_task_id=task_id,
                dispatch_thread_id=_as_str(task.get("dispatch_thread_id")) or _as_str(dispatch_payload.get("dispatch_thread_id")),
                dispatch_mode_used=effective_mode,
                branch_name=branch_name,
                worktree_root=worktree_root,
            )
            dispatch_successes.append(result)
            dispatched_count += 1
            continue

        _record_assignment_observation(
            row=row,
            status="failed",
            reason_code=_as_str(result.get("reason")) or "dispatch_failed",
            started_at=started,
            selected_alias=selected_alias,
            dispatch_mode=_as_str(((result.get("dispatch") or {}).get("dispatch_mode_used")) or dispatch_mode),
            warning_codes=[
                _as_str(item.get("code"))
                for item in warning_rows
                if isinstance(item, dict) and _as_str(item.get("code"))
            ],
        )
        if first_failure is None:
            first_failure = result
        result_warnings = result.get("warnings") if isinstance(result.get("warnings"), list) else []
        all_warnings.extend([row for row in result_warnings if isinstance(row, dict)])

    if dispatch_successes:
        status = "completed" if dispatched_count > 0 else "noop"
        reason = "dispatch_ok" if dispatched_count > 0 else "dispatch_plan_no_assignments"
        out = {
            "ok": True,
            "status": status,
            "reason": reason,
            "warnings": all_warnings,
            "assignment_observations": assignment_observations,
            "dispatch_count": dispatched_count,
            "dispatch_results": dispatch_successes,
        }
        _persist_assignment_observations(all_warnings)
        return out

    if first_failure is not None:
        existing = first_failure.get("warnings") if isinstance(first_failure.get("warnings"), list) else []
        existing.extend(all_warnings)
        if existing:
            first_failure["warnings"] = existing
        _persist_assignment_observations(existing)
        first_failure["assignment_observations"] = assignment_observations
        return first_failure
    out = {
        "ok": True,
        "status": "noop",
        "reason": (
            _as_str(
                next(
                    (
                        row.get("reason_code")
                        for row in assignment_observations
                        if isinstance(row, dict) and _as_str(row.get("status")) in {"skipped", "failed", "invalid"}
                    ),
                    None,
                )
            )
            or "dispatch_plan_no_assignments"
        ),
        "warnings": all_warnings,
        "assignment_observations": assignment_observations,
    }
    _persist_assignment_observations(all_warnings)
    return out


def _dispatch_next_task(
    req: OpRequest,
    plan_packets: dict[str, Any],
    task_state: dict[str, Any],
    build_state: dict[str, Any],
    active_phase_id: str | None = None,
    authoritative_assignments: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if isinstance(authoritative_assignments, list):
        return _dispatch_next_task_from_assignments(req, plan_packets, task_state, build_state, authoritative_assignments)

    task_map = _task_by_id(task_state)
    plan_map = _plan_task_map(plan_packets)
    retry_policy = build_state.get("gap_retry_policy")
    if not isinstance(retry_policy, dict):
        retry_policy = {"max_attempts": 5}
        build_state["gap_retry_policy"] = retry_policy
    max_retry_attempts = max(1, _coerce_nonneg_int(retry_policy.get("max_attempts"), default=5))
    retry_attempts = build_state.get("gap_retry_attempts")
    if not isinstance(retry_attempts, dict):
        retry_attempts = {}
        build_state["gap_retry_attempts"] = retry_attempts
    exhausted_ids_raw = build_state.get("gap_retry_exhausted_ids")
    exhausted_ids = (
        [item for item in (_as_str(v) for v in exhausted_ids_raw) if item]
        if isinstance(exhausted_ids_raw, list)
        else []
    )
    exhausted_set = set(exhausted_ids)
    build_state["gap_retry_exhausted_ids"] = sorted(exhausted_set)
    ordered_ids = [
        task_id
        for task_id in plan_map.keys()
        if not active_phase_id or (_as_str(plan_map.get(task_id, {}).get("phase_id")) or "phase-1") == active_phase_id
    ]
    in_progress_states = {
        TASK_STATUS_DEV_WORKING,
        TASK_STATUS_TESTING,
        TASK_STATUS_REVIEWING,
    }
    has_in_progress = any(
        _normalize_task_status(task_map.get(task_id, {}).get("status")) in in_progress_states
        for task_id in ordered_ids
    )
    if has_in_progress:
        return {"ok": True, "status": "skipped", "reason": "task already in progress"}
    deferred_block: dict[str, Any] | None = None
    carried_warning: dict[str, Any] | None = None

    stage_cfg = {
        "dev": {"role": "developer"},
        "test": {"role": "tester"},
        "review": {"role": "reviewer"},
    }
    slot_count = len(FIXED_WORKER_SLOTS)
    registry_path = req.repo_root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
    registry_base, registry_workers, registry_shape = _load_worker_registry(registry_path)
    workers_by_slot = {
        _as_str(worker.get("slot")): worker
        for worker in registry_workers
        if isinstance(worker, dict) and _as_str(worker.get("slot"))
    }

    def _persist_worker_slot_transition(
        *,
        slot_name: str,
        lane_value: str | None,
        active_task_id: str | None,
        dispatch_thread_id: str | None,
        dispatch_mode_used: str | None,
    ) -> None:
        row = workers_by_slot.get(slot_name)
        if not isinstance(row, dict):
            row = _default_worker_row(slot_name)
            registry_workers.append(row)
            workers_by_slot[slot_name] = row
        _apply_slot_lane_transition(row, lane_value)
        row["active_task_id"] = active_task_id
        row["active_task"] = active_task_id
        if dispatch_thread_id:
            row["dispatch_thread_id"] = dispatch_thread_id
        row["session_state"] = "running"
        row["state"] = "running"
        row["updated_at"] = utc_now_iso()
        if _as_str(dispatch_mode_used):
            row["dispatch_mode"] = _as_str(dispatch_mode_used)
        _write_worker_registry(
            registry_path,
            registry_base,
            registry_workers,
            registry_shape if registry_shape in {"dict_list", "dict_dict", "list"} else "dict_list",
        )

    def _lane_slot_suffix(task_payload: dict[str, Any], plan_task_payload: dict[str, Any]) -> str:
        lane_id = _as_str(task_payload.get("lane_id")) or _as_str(plan_task_payload.get("lane_id")) or ""
        tail = lane_id.rsplit("/", 1)[-1].lower()
        if tail == "lane-b":
            return "2"
        if tail == "lane-c":
            return "3"
        return "1"

    def _slot_for_stage(stage_name: str, task_payload: dict[str, Any], plan_task_payload: dict[str, Any]) -> str:
        suffix = _lane_slot_suffix(task_payload, plan_task_payload)
        if stage_name == "dev":
            return f"dev-{suffix}"
        if stage_name == "test":
            return f"test-{suffix}"
        return f"review-{suffix}"

    def _dispatch_for_stage(
        task_payload: dict[str, Any],
        plan_task_payload: dict[str, Any],
        stage_name: str,
        local_plan_id: str,
    ) -> dict[str, Any]:
        slot_name = _slot_for_stage(stage_name, task_payload, plan_task_payload)
        lane_value = _as_str(task_payload.get("lane_id")) or _as_str(plan_task_payload.get("lane_id"))
        slot_worker = workers_by_slot.get(slot_name) if isinstance(workers_by_slot.get(slot_name), dict) else {}
        previous_lane = _as_str(slot_worker.get("lane_id")) if isinstance(slot_worker, dict) else None
        previous_thread_id = _as_str(task_payload.get("dispatch_thread_id")) or _as_str(slot_worker.get("dispatch_thread_id"))
        same_lane_resume = bool(lane_value and previous_lane and lane_value == previous_lane and previous_thread_id)
        dispatch_mode = "resume" if same_lane_resume else "exec"
        resume_thread_id = previous_thread_id if same_lane_resume else None
        selection = _select_profile_alias_for_slot(
            req.repo_root,
            build_state,
            slot=slot_name,
            slot_count=slot_count,
        )
        if not _as_bool(selection.get("ok"), default=False):
            return {
                "ok": True,
                "status": "skipped",
                "reason": _as_str(selection.get("reason")) or "profile_selection_invalid",
                "warning": selection.get("warning"),
            }
        selected_alias = _as_str(selection.get("alias")) or "codex"
        alias_state = _read_profile_rate_states(req.repo_root, [selected_alias]).get(selected_alias, {})
        if bool(alias_state.get("soft_gated")):
            active_by_alias = _active_worker_count_by_alias(req.repo_root)
            if int(active_by_alias.get(selected_alias, 0)) >= 1:
                return {
                    "ok": True,
                    "status": "skipped",
                    "reason": "profile_soft_gated_alias_cap",
                    "warning": {
                        "code": "dispatch_skipped_soft_cap",
                        "message": f"dispatch skipped for soft-gated alias cap (alias={selected_alias}, cap=1)",
                        "stage": "build_loop",
                        "alias": selected_alias,
                    },
                }
        start_from_branch_override = "RAB-BASE"
        start_from_commit_override: str | None = None
        test_source_branch_override: str | None = None
        test_source_commit_override: str | None = None
        if stage_name == "test":
            source_branch = _as_str(task_payload.get("active_branch"))
            if not source_branch:
                return {
                    "ok": True,
                    "status": "skipped",
                    "reason": "dispatch_assignment_missing_dev_branch",
                    "warning": {
                        "code": "dispatch_assignment_missing_dev_branch",
                        "message": f"task {_as_str(task_payload.get('task_id')) or 'TASK-UNKNOWN'} missing active developer branch for test-stage dispatch",
                        "stage": "build_loop",
                    },
                }
            source_commit = _git_text(req.repo_root, "rev-parse", source_branch)
            if not source_commit:
                return {
                    "ok": True,
                    "status": "skipped",
                    "reason": "dispatch_assignment_missing_dev_branch",
                    "warning": {
                        "code": "dispatch_assignment_missing_dev_branch",
                        "message": f"unable to resolve HEAD commit for developer branch {source_branch}",
                        "stage": "build_loop",
                    },
                }
            start_from_branch_override = source_branch
            start_from_commit_override = source_commit
            test_source_branch_override = source_branch
            test_source_commit_override = source_commit
        result = _dispatch_task_packet(
            req,
            task_payload,
            plan_task_payload,
            stage_name,
            local_plan_id,
            selected_alias,
            lane_id=lane_value,
            dispatch_mode=dispatch_mode,
            resume_thread_id=resume_thread_id,
            start_from_branch_override=start_from_branch_override,
            start_from_commit_override=start_from_commit_override,
            test_source_branch_override=test_source_branch_override,
            test_source_commit_override=test_source_commit_override,
        )
        if _as_bool(result.get("ok"), default=False):
            dispatch_payload = result.get("dispatch") if isinstance(result.get("dispatch"), dict) else {}
            dispatch_mode_used = _as_str(dispatch_payload.get("dispatch_mode_used")) or dispatch_mode
            if dispatch_mode == "resume":
                warning_rows = result.get("warnings") if isinstance(result.get("warnings"), list) else []
                if dispatch_mode_used == "resume":
                    warning_rows.append(
                        {
                            "code": "dispatch_resumed_thread",
                            "message": f"slot {slot_name} resumed existing thread for same-lane task",
                            "stage": "build_loop",
                            "slot": slot_name,
                            "lane_id": lane_value,
                        }
                    )
                else:
                    warning_rows.append(
                        {
                            "code": "dispatch_resume_failed_fallback_exec",
                            "message": f"slot {slot_name} failed to resume thread; fallback dispatch used new thread",
                            "stage": "build_loop",
                            "slot": slot_name,
                            "lane_id": lane_value,
                        }
                    )
                result["warnings"] = warning_rows
            elif lane_value and previous_lane and lane_value != previous_lane:
                warning_rows = result.get("warnings") if isinstance(result.get("warnings"), list) else []
                warning_rows.append(
                    {
                        "code": "dispatch_new_thread_lane_change",
                        "message": f"slot {slot_name} lane changed {previous_lane} -> {lane_value}; started new thread",
                        "stage": "build_loop",
                        "slot": slot_name,
                        "from_lane_id": previous_lane,
                        "to_lane_id": lane_value,
                    }
                )
                result["warnings"] = warning_rows
            _persist_worker_slot_transition(
                slot_name=slot_name,
                lane_value=lane_value,
                active_task_id=_as_str(task_payload.get("task_id")),
                dispatch_thread_id=_as_str(task_payload.get("dispatch_thread_id")),
                dispatch_mode_used=dispatch_mode_used,
            )
        selection_warning = selection.get("warning")
        if isinstance(selection_warning, dict):
            warning_rows = result.get("warnings") if isinstance(result.get("warnings"), list) else []
            warning_rows.append(selection_warning)
            result["warnings"] = warning_rows
            if not isinstance(result.get("warning"), dict):
                result["warning"] = selection_warning
        return result

    plan_id = _as_str(plan_packets.get("plan_id")) or "plan-unknown"
    for task_id in ordered_ids:
        task = task_map.get(task_id)
        plan_task = plan_map.get(task_id) or {}
        if not isinstance(task, dict):
            continue
        status = _normalize_task_status(task.get("status"))
        if status == TASK_STATUS_REVIEW_DONE:
            continue
        build_state["current_task_pointer"] = task_id
        if status == TASK_STATUS_PENDING:
            result = _dispatch_for_stage(task, plan_task, "dev", plan_id)
            if carried_warning:
                warning_rows = result.get("warnings") if isinstance(result.get("warnings"), list) else []
                warning_rows.append(carried_warning)
                result["warnings"] = warning_rows
                if not isinstance(result.get("warning"), dict):
                    result["warning"] = carried_warning
            return result
        if status == TASK_STATUS_BLOCKED and bool(task.get("is_gap_closure")):
            source_gap_id = _as_str(task.get("source_gap_id")) or _as_str(plan_task.get("source_gap_id")) or f"gap:{task_id}"
            retries = _coerce_nonneg_int(retry_attempts.get(source_gap_id, 0), default=0)
            if source_gap_id in exhausted_set:
                deferred_block = deferred_block or {
                    "ok": False,
                    "status": "blocked",
                    "task_id": task_id,
                    "reason": "gap_closure_retry_suppressed",
                    "source_gap_id": source_gap_id,
                    "retry_count": retries,
                    "warning": {
                        "code": "gap_closure_retry_suppressed",
                        "message": f"gap closure retries already exhausted for {source_gap_id}; dispatch suppressed",
                        "stage": "build_loop",
                        "gap_id": source_gap_id,
                        "retry_count": retries,
                    },
                }
                carried_warning = {
                    "code": "gap_closure_skipped_exhausted_continue_scan",
                    "message": f"gap closure {task_id} already exhausted for {source_gap_id}; continuing queue scan",
                    "stage": "build_loop",
                    "gap_id": source_gap_id,
                    "task_id": task_id,
                }
                continue
            retries += 1
            retry_attempts[source_gap_id] = retries
            if retries >= max_retry_attempts:
                exhausted_set.add(source_gap_id)
                build_state["gap_retry_exhausted_ids"] = sorted(exhausted_set)
                deferred_block = deferred_block or {
                    "ok": False,
                    "status": "blocked",
                    "task_id": task_id,
                    "reason": "gap_retry_exhausted",
                    "source_gap_id": source_gap_id,
                    "retry_count": retries,
                    "warning": {
                        "code": "gap_retry_exhausted",
                        "message": f"gap closure retry limit reached for {source_gap_id} (max_attempts={max_retry_attempts})",
                        "stage": "build_loop",
                        "gap_id": source_gap_id,
                        "retry_count": retries,
                        "max_attempts": max_retry_attempts,
                    },
                }
                carried_warning = {
                    "code": "gap_closure_skipped_exhausted_continue_scan",
                    "message": (
                        f"gap closure {task_id} reached retry cap for {source_gap_id}; "
                        "continuing queue scan"
                    ),
                    "stage": "build_loop",
                    "gap_id": source_gap_id,
                    "task_id": task_id,
                    "retry_count": retries,
                    "max_attempts": max_retry_attempts,
                }
                continue
            task["status"] = TASK_STATUS_PENDING
            task["owner_slot"] = None
            result = _dispatch_for_stage(task, plan_task, "dev", plan_id)
            if carried_warning:
                warning_rows = result.get("warnings") if isinstance(result.get("warnings"), list) else []
                warning_rows.append(carried_warning)
                result["warnings"] = warning_rows
                if not isinstance(result.get("warning"), dict):
                    result["warning"] = carried_warning
            return result
        if status == TASK_STATUS_DEV_DONE:
            evidence_path = _task_evidence_path(req.repo_root, task)
            if not evidence_path.exists():
                return {
                    "ok": False,
                    "status": "blocked",
                    "task_id": task_id,
                    "reason": "missing_task_evidence",
                }
            payload = _read_json(evidence_path)
            if not isinstance(payload, dict) or not _as_bool_field((payload.get("gate") or {}).get("ready_for_test")):
                return {
                    "ok": False,
                    "status": "blocked",
                    "task_id": task_id,
                    "reason": "dev_gate_not_ready_for_test",
                }
            result = _dispatch_for_stage(task, plan_task, "test", plan_id)
            if carried_warning:
                warning_rows = result.get("warnings") if isinstance(result.get("warnings"), list) else []
                warning_rows.append(carried_warning)
                result["warnings"] = warning_rows
                if not isinstance(result.get("warning"), dict):
                    result["warning"] = carried_warning
            return result
        if status == TASK_STATUS_TESTS_DONE:
            evidence_path = _task_evidence_path(req.repo_root, task)
            if not evidence_path.exists():
                return {
                    "ok": False,
                    "status": "blocked",
                    "task_id": task_id,
                    "reason": "missing_task_evidence",
                }
            payload = _read_json(evidence_path)
            if not isinstance(payload, dict) or not _as_bool_field((payload.get("gate") or {}).get("ready_for_review")):
                return {
                    "ok": False,
                    "status": "blocked",
                    "task_id": task_id,
                    "reason": "test_gate_not_ready_for_review",
                }
            result = _dispatch_for_stage(task, plan_task, "review", plan_id)
            if carried_warning:
                warning_rows = result.get("warnings") if isinstance(result.get("warnings"), list) else []
                warning_rows.append(carried_warning)
                result["warnings"] = warning_rows
                if not isinstance(result.get("warning"), dict):
                    result["warning"] = carried_warning
            return result
    if deferred_block is not None:
        if carried_warning and not isinstance(deferred_block.get("warning"), dict):
            deferred_block["warning"] = carried_warning
        return deferred_block
    return {"ok": True, "status": "noop", "reason": "no dispatchable tasks", "warning": carried_warning}


def _manager_production_line_cycle(
    req: OpRequest,
    *,
    plan_packets: dict[str, Any],
    task_state: dict[str, Any],
    build_state: dict[str, Any],
) -> dict[str, Any]:
    warnings: list[dict[str, Any]] = []
    warnings.extend(_fan_in_worker_artifacts(req.repo_root, build_state))
    warnings.extend(_apply_handoff_updates(req.repo_root, task_state, build_state))
    warnings.extend(_sync_task_state_from_evidence(req.repo_root, plan_packets, task_state))
    warnings.extend(_refresh_task_embedded_gaps(req.repo_root, plan_packets, task_state))
    warnings.extend(_reconcile_task_embedded_gap_closures(req.repo_root, task_state))
    merged_plan_packets = plan_packets
    active_phase_id, phase_checks = _resolve_active_phase(
        merged_plan_packets,
        task_state,
        req.repo_root,
    )
    build_state["open_gap_ids"] = _open_task_gap_ids(task_state)
    build_state["current_phase_id"] = active_phase_id
    build_state["phase_exit_checks"] = phase_checks
    build_state["last_gap_generation_at"] = utc_now_iso()

    task_by_id = _task_by_id(task_state)
    plan_map = _plan_task_map(plan_packets)
    lane_busy: set[str] = set()
    for task in task_state.get("tasks", []):
        if not isinstance(task, dict):
            continue
        status = _normalize_task_status(task.get("status"))
        if status not in {TASK_STATUS_DEV_WORKING, TASK_STATUS_TESTING, TASK_STATUS_REVIEWING}:
            continue
        lane_id = _as_str(task.get("lane_id")) or _as_str((plan_map.get(_as_str(task.get("task_id")) or "") or {}).get("lane_id"))
        if lane_id:
            lane_busy.add(lane_id)

    assignments: list[dict[str, Any]] = []
    if active_phase_id:
        phase_tasks = [
            plan_task
            for plan_task in plan_packets.get("tasks", [])
            if isinstance(plan_task, dict) and (_as_str(plan_task.get("phase_id")) or "phase-1") == active_phase_id
        ]
        lanes: dict[str, list[dict[str, Any]]] = {}
        for plan_task in phase_tasks:
            lane_id = _as_str(plan_task.get("lane_id")) or f"{active_phase_id}/lane-a"
            lanes.setdefault(lane_id, []).append(plan_task)
        for lane_id in sorted(lanes.keys()):
            if lane_id in lane_busy:
                continue
            lane_tasks = sorted(
                lanes[lane_id],
                key=lambda row: _as_str(row.get("task_id")) or "TASK-UNKNOWN",
            )
            for plan_task in lane_tasks:
                task_id = _as_str(plan_task.get("task_id"))
                if not task_id:
                    continue
                task = task_by_id.get(task_id)
                if not isinstance(task, dict):
                    continue
                deps = [dep for dep in ((_as_str(item) for item in plan_task.get("depends_on", []))) if dep]
                if deps and any(
                    _normalize_task_status((task_by_id.get(dep) or {}).get("status")) != TASK_STATUS_REVIEW_DONE
                    for dep in deps
                ):
                    continue
                status = _normalize_task_status(task.get("status"))
                if status == TASK_STATUS_PENDING:
                    next_role = "developer"
                    next_stage = "dev"
                elif status == TASK_STATUS_DEV_DONE:
                    next_role = "tester"
                    next_stage = "test"
                elif status == TASK_STATUS_TESTS_DONE:
                    next_role = "reviewer"
                    next_stage = "review"
                else:
                    continue
                lane_tail = lane_id.rsplit("/", 1)[-1].lower()
                slot_suffix = "1"
                if lane_tail == "lane-b":
                    slot_suffix = "2"
                elif lane_tail == "lane-c":
                    slot_suffix = "3"
                if next_stage == "dev":
                    slot = f"dev-{slot_suffix}"
                elif next_stage == "test":
                    slot = f"test-{slot_suffix}"
                else:
                    slot = f"review-{slot_suffix}"
                assignments.append(
                    {
                        "task_id": task_id,
                        "lane_id": lane_id,
                        "phase_id": active_phase_id,
                        "next_stage": next_stage,
                        "next_role": next_role,
                        "slot": slot,
                        "dispatch_policy": "resume_if_same_lane",
                    }
                )
                break

    _atomic_write_json(
        _repo_path(req.repo_root, WORK_DISPATCH_PLAN_JSON),
        {
            "schema_version": SCHEMA_VERSION,
            "updated_at": utc_now_iso(),
            "active_phase_id": active_phase_id,
            "assignments": assignments,
        },
    )
    production_line_state = {
        "schema_version": SCHEMA_VERSION,
        "updated_at": utc_now_iso(),
        "active_phase_id": active_phase_id,
        "open_gap_ids": build_state.get("open_gap_ids", []),
        "phase_exit_checks": phase_checks,
        "task_counts_by_status": _status_counts(task_state),
    }
    _atomic_write_json(_repo_path(req.repo_root, PRODUCTION_LINE_STATE_JSON), production_line_state)
    return {
        "warnings": warnings,
        "merged_plan_packets": merged_plan_packets,
        "gaps_payload": {"schema_version": SCHEMA_VERSION, "gaps": []},
        "active_phase_id": active_phase_id,
        "phase_checks": phase_checks,
    }


def _manager_branch_merge_cycle(
    req: OpRequest,
    *,
    plan_packets: dict[str, Any],
    task_state: dict[str, Any],
    build_state: dict[str, Any],
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    registry_path = _repo_path(req.repo_root, DONE_TASKS_REGISTRY_JSON)
    if registry_path.exists():
        payload = _read_json(registry_path)
        done_registry = payload if isinstance(payload, dict) else {}
    else:
        done_registry = {}
    merged_rows_raw = done_registry.get("merged_tasks") if isinstance(done_registry.get("merged_tasks"), list) else []
    merged_rows = [row for row in merged_rows_raw if isinstance(row, dict) and _as_str(row.get("task_id"))]
    merged_ids = {_as_str(row.get("task_id")) for row in merged_rows if _as_str(row.get("task_id"))}
    review_done = [
        _as_str(task.get("task_id"))
        for task in task_state.get("tasks", [])
        if isinstance(task, dict) and _normalize_task_status(task.get("status")) == TASK_STATUS_REVIEW_DONE and _as_str(task.get("task_id"))
    ]
    pending_merge = [task_id for task_id in review_done if task_id not in merged_ids]
    if req.dry_run:
        out = {
            "schema_version": SCHEMA_VERSION,
            "updated_at": utc_now_iso(),
            "review_done_task_ids": sorted(review_done),
            "merged_task_ids": sorted(list(merged_ids)),
            "pending_merge_task_ids": sorted(pending_merge),
            "branch": "RAB-BASE",
            "merged_tasks": merged_rows,
        }
        _atomic_write_json(registry_path, out)
        if pending_merge:
            warnings.append(
                {
                    "code": "branch_merge_pending_tasks",
                    "message": f"{len(pending_merge)} review_done task(s) pending branch merge on RAB-BASE",
                    "stage": "build_loop",
                    "task_ids": pending_merge,
                }
            )
        return warnings
    task_map = _task_by_id(task_state)
    verify_commands: list[str] = []
    seen_cmds: set[str] = set()
    for plan_task in plan_packets.get("tasks", []):
        if not isinstance(plan_task, dict):
            continue
        for cmd in plan_task.get("verify_commands", []):
            cmd_text = _as_str(cmd)
            if cmd_text and cmd_text not in seen_cmds:
                seen_cmds.add(cmd_text)
                verify_commands.append(cmd_text)
    if not verify_commands:
        verify_commands = ["python3 -m pytest"]

    prompt_template_path = BRANCH_MANAGER_PROMPT_TEMPLATE_PATH.resolve()
    prompt_template_text = (
        prompt_template_path.read_text(encoding="utf-8")
        if prompt_template_path.exists()
        else ""
    )

    for task_id in sorted(pending_merge):
        task = task_map.get(task_id) if isinstance(task_map.get(task_id), dict) else {}
        branch_name = (
            _as_str(task.get("active_branch"))
            or _as_str(task.get("branch"))
            or f"codex/dev-1/{task_id.lower()}"
        )
        merged_ok = False
        verification_ok = False
        merged_commit: str | None = None
        verification_ref: str | None = None
        prior_errors: list[dict[str, Any]] = []
        for attempt in range(1, 11):
            pre_merge_head: str | None = None
            rollback_applied = False
            rollback_target: str | None = None
            _emit_build_progress(req, f"branch-merge-manager: task={task_id} attempt {attempt}/10")
            attempt_dir = req.repo_root / "reports" / "optimus-prime" / "branch-manager" / f"attempt-{task_id.lower()}-{attempt}"
            action_path = attempt_dir / "MERGE_ACTION.json"
            validation_path = attempt_dir / "MERGE_VALIDATION.json"
            stdout_path = attempt_dir / "llm_stdout.log"
            stderr_path = attempt_dir / "llm_stderr.log"
            last_message_path = attempt_dir / "last_message.txt"
            prompt_path = attempt_dir / "prompt.txt"
            if not prompt_template_text:
                _emit_build_progress(
                    req,
                    (
                        f"branch-merge-manager: task={task_id} attempt {attempt} failed: "
                        f"prompt template missing at {prompt_template_path}; retrying."
                    ),
                )
                validation_payload = {
                    "schema_version": SCHEMA_VERSION,
                    "task_id": task_id,
                    "attempt": attempt,
                    "ok": False,
                    "error": {
                        "code": "branch_manager_action_invalid",
                        "message": f"branch manager prompt template missing: {prompt_template_path}",
                        "stage": "build_loop",
                    },
                    "finished_at": utc_now_iso(),
                }
                _atomic_write_json(validation_path, validation_payload)
                prior_errors = [validation_payload["error"]]
                continue

            prompt = prompt_template_text
            prompt = prompt.replace("{{REPO_ROOT}}", str(req.repo_root))
            prompt = prompt.replace("{{TASK_ID}}", task_id)
            prompt = prompt.replace("{{SOURCE_BRANCH}}", branch_name)
            prompt = prompt.replace("{{TARGET_BRANCH}}", "RAB-BASE")
            prompt = prompt.replace("{{ACTION_PATH}}", str(action_path))
            prompt = prompt.replace("{{VERIFY_COMMANDS_JSON}}", json.dumps(verify_commands))
            if prior_errors:
                repair_lines = [
                    f"{idx}. [{_as_str(item.get('code')) or 'error'}] {_as_str(item.get('message')) or 'validation failed'}"
                    for idx, item in enumerate(prior_errors, start=1)
                ]
                prompt += "\n\nRepair context from previous failed attempt:\n" + "\n".join(repair_lines) + "\n"
            prompt_path.parent.mkdir(parents=True, exist_ok=True)
            prompt_path.write_text(prompt, encoding="utf-8")
            try:
                exit_code = run_codex_exec(
                    repo_root=req.repo_root,
                    prompt_text=prompt,
                    output_last_message=last_message_path,
                    stdout_path=stdout_path,
                    stderr_path=stderr_path,
                )
            except OSError as exc:
                _emit_build_progress(
                    req,
                    (
                        f"branch-merge-manager: task={task_id} attempt {attempt} failed: "
                        f"unable to invoke codex exec ({exc}); retrying."
                    ),
                )
                validation_payload = {
                    "schema_version": SCHEMA_VERSION,
                    "task_id": task_id,
                    "attempt": attempt,
                    "ok": False,
                    "error": {
                        "code": "branch_manager_execution_failed",
                        "message": f"unable to invoke codex exec: {exc}",
                        "stage": "build_loop",
                    },
                    "finished_at": utc_now_iso(),
                }
                _atomic_write_json(validation_path, validation_payload)
                prior_errors = [validation_payload["error"]]
                continue

            try:
                action_payload = _read_json(action_path)
            except OpError as exc:
                _emit_build_progress(
                    req,
                    (
                        f"branch-merge-manager: task={task_id} attempt {attempt} failed: "
                        f"invalid MERGE_ACTION artifact ({exc.message}); retrying."
                    ),
                )
                validation_payload = {
                    "schema_version": SCHEMA_VERSION,
                    "task_id": task_id,
                    "attempt": attempt,
                    "ok": False,
                    "error": {
                        "code": "branch_manager_action_invalid",
                        "message": f"missing/invalid MERGE_ACTION.json: {exc.message}",
                        "stage": "build_loop",
                    },
                    "finished_at": utc_now_iso(),
                }
                _atomic_write_json(validation_path, validation_payload)
                prior_errors = [validation_payload["error"]]
                continue

            if not isinstance(action_payload, dict):
                _emit_build_progress(
                    req,
                    (
                        f"branch-merge-manager: task={task_id} attempt {attempt} failed: "
                        "MERGE_ACTION.json must be object; retrying."
                    ),
                )
                validation_payload = {
                    "schema_version": SCHEMA_VERSION,
                    "task_id": task_id,
                    "attempt": attempt,
                    "ok": False,
                    "error": {
                        "code": "branch_manager_action_invalid",
                        "message": "MERGE_ACTION.json must be object",
                        "stage": "build_loop",
                    },
                    "finished_at": utc_now_iso(),
                }
                _atomic_write_json(validation_path, validation_payload)
                prior_errors = [validation_payload["error"]]
                continue

            action_errors: list[str] = []
            if _as_str(action_payload.get("task_id")) != task_id:
                action_errors.append("task_id mismatch")
            if _as_str(action_payload.get("target_branch")) != "RAB-BASE":
                action_errors.append("target_branch must be RAB-BASE")
            if _as_str(action_payload.get("source_branch")) != branch_name:
                action_errors.append("source_branch mismatch")
            if not _as_str(action_payload.get("merge_strategy")):
                action_errors.append("merge_strategy required")
            commands = action_payload.get("commands")
            if not isinstance(commands, list) or not commands or not all(isinstance(item, str) and item.strip() for item in commands):
                action_errors.append("commands must be non-empty list[str]")
            action_verify = action_payload.get("verification_commands")
            if not isinstance(action_verify, list) or not action_verify or not all(isinstance(item, str) and item.strip() for item in action_verify):
                action_errors.append("verification_commands must be non-empty list[str]")
            if action_errors:
                _emit_build_progress(
                    req,
                    (
                        f"branch-merge-manager: task={task_id} attempt {attempt} validation failed: "
                        f"{'; '.join(action_errors)}"
                    ),
                )
                validation_payload = {
                    "schema_version": SCHEMA_VERSION,
                    "task_id": task_id,
                    "attempt": attempt,
                    "ok": False,
                    "error": {
                        "code": "branch_manager_action_invalid",
                        "message": "; ".join(action_errors),
                        "stage": "build_loop",
                    },
                    "finished_at": utc_now_iso(),
                }
                _atomic_write_json(action_path, action_payload)
                _atomic_write_json(validation_path, validation_payload)
                prior_errors = [validation_payload["error"]]
                continue

            try:
                checkout_result = _run_manager_command(
                    "git checkout RAB-BASE",
                    cwd=req.repo_root,
                    timeout_sec=BRANCH_ACTION_COMMAND_TIMEOUT_SEC,
                    manager="branch",
                )
                if not _as_bool(checkout_result.get("ok"), default=False):
                    raise OpError(
                        _as_str(checkout_result.get("code")) or "branch_manager_execution_failed",
                        _as_str(checkout_result.get("message"))
                        or _as_str(checkout_result.get("stderr"))
                        or "unable to checkout RAB-BASE",
                        stage="build_loop",
                    )
                pre_merge_head = _git_text(req.repo_root, "rev-parse", "HEAD")
                if not pre_merge_head:
                    raise OpError(
                        "branch_manager_execution_failed",
                        "unable to resolve pre-merge HEAD on RAB-BASE",
                        stage="build_loop",
                    )
                command_rows: list[dict[str, Any]] = []
                for cmd in commands:
                    cmd_result = _run_manager_command(
                        cmd,
                        cwd=req.repo_root,
                        timeout_sec=BRANCH_ACTION_COMMAND_TIMEOUT_SEC,
                        manager="branch",
                    )
                    code = cmd_result.get("exit_code")
                    stdout = _as_str(cmd_result.get("stdout")) or ""
                    stderr = _as_str(cmd_result.get("stderr")) or ""
                    cmd_ok = _as_bool(cmd_result.get("ok"), default=False)
                    command_rows.append(
                        {
                            "command": cmd,
                            "exit_code": code,
                            "stdout": stdout.strip(),
                            "stderr": stderr.strip(),
                            "passed": cmd_ok,
                            "error_code": _as_str(cmd_result.get("code")),
                        }
                    )
                    if not cmd_ok:
                        raise OpError(
                            _as_str(cmd_result.get("code")) or "branch_manager_execution_failed",
                            _as_str(cmd_result.get("message"))
                            or f"merge action command failed: {cmd}",
                            stage="build_loop",
                        )
                merged_ok = True
                merged_commit = _git_text(req.repo_root, "rev-parse", "HEAD")
                merge_proof_cmd = f"git merge-base --is-ancestor {shlex.quote(branch_name)} HEAD"
                merge_proof_result = _run_manager_command(
                    merge_proof_cmd,
                    cwd=req.repo_root,
                    timeout_sec=BRANCH_ACTION_COMMAND_TIMEOUT_SEC,
                    manager="branch",
                )
                merge_proof_passed = _as_bool(merge_proof_result.get("ok"), default=False)
                if not merge_proof_passed:
                    raise OpError(
                        "merge_proof_failed",
                        f"merge proof failed: {branch_name} is not an ancestor of RAB-BASE HEAD",
                        stage="build_loop",
                    )
                verification_rows: list[dict[str, Any]] = []
                verification_ok = True
                for cmd in verify_commands:
                    verify_result = _run_manager_command(
                        cmd,
                        cwd=req.repo_root,
                        timeout_sec=BRANCH_VERIFY_COMMAND_TIMEOUT_SEC,
                        manager="branch",
                    )
                    verify_ok = _as_bool(verify_result.get("ok"), default=False)
                    row = {
                        "command": cmd,
                        "passed": verify_ok,
                        "exit_code": verify_result.get("exit_code"),
                        "stdout": (_as_str(verify_result.get("stdout")) or "").strip(),
                        "stderr": (_as_str(verify_result.get("stderr")) or "").strip(),
                        "error_code": _as_str(verify_result.get("code")),
                    }
                    verification_rows.append(row)
                    if not verify_ok:
                        verification_ok = False
                if not verification_ok and merged_commit:
                    rollback_target = _as_str(pre_merge_head)
                    if rollback_target:
                        rollback_result = _run_manager_command(
                            f"git reset --hard {rollback_target}",
                            cwd=req.repo_root,
                            timeout_sec=BRANCH_ACTION_COMMAND_TIMEOUT_SEC,
                            manager="branch",
                        )
                        rollback_applied = _as_bool(rollback_result.get("ok"), default=False)
                        if not rollback_applied:
                            raise OpError(
                                _as_str(rollback_result.get("code")) or "branch_manager_execution_failed",
                                _as_str(rollback_result.get("message"))
                                or f"failed rollback to pre-merge HEAD {rollback_target}",
                                stage="build_loop",
                            )
                validation_payload = {
                    "schema_version": SCHEMA_VERSION,
                    "task_id": task_id,
                    "attempt": attempt,
                    "ok": merged_ok and verification_ok,
                    "branch": "RAB-BASE",
                    "source_branch": branch_name,
                    "merged_commit": merged_commit,
                    "merge_proof_passed": merge_proof_passed,
                    "pre_merge_head": pre_merge_head,
                    "rollback_applied": rollback_applied,
                    "rollback_target": rollback_target,
                    "action_commands": command_rows,
                    "verification": verification_rows,
                    "llm_exit_code": exit_code,
                    "finished_at": utc_now_iso(),
                }
                _atomic_write_json(action_path, action_payload)
                _atomic_write_json(validation_path, validation_payload)
                verification_ref = os.path.relpath(str(validation_path), str(req.repo_root))
                if verification_ok:
                    _emit_build_progress(
                        req,
                        f"branch-merge-manager: task={task_id} merged and verified on attempt {attempt}",
                    )
                    break
                prior_errors = [
                    {
                        "code": "branch_manager_execution_failed",
                        "message": "post-merge verification suite failed",
                    }
                ]
                _emit_build_progress(
                    req,
                    (
                        f"branch-merge-manager: task={task_id} attempt {attempt} verification failed; "
                        "applying necessary fixes and retrying."
                    ),
                )
            except OpError as exc:
                rollback_error: dict[str, Any] | None = None
                if pre_merge_head and not rollback_applied:
                    rollback_target = _as_str(pre_merge_head)
                    if rollback_target:
                        rollback_result = _run_manager_command(
                            f"git reset --hard {rollback_target}",
                            cwd=req.repo_root,
                            timeout_sec=BRANCH_ACTION_COMMAND_TIMEOUT_SEC,
                            manager="branch",
                        )
                        rollback_applied = _as_bool(rollback_result.get("ok"), default=False)
                        if not rollback_applied:
                            rollback_error = {
                                "code": _as_str(rollback_result.get("code")) or "branch_manager_execution_failed",
                                "message": _as_str(rollback_result.get("message"))
                                or f"failed rollback to pre-merge HEAD {rollback_target}",
                            }
                validation_payload = {
                    "schema_version": SCHEMA_VERSION,
                    "task_id": task_id,
                    "attempt": attempt,
                    "ok": False,
                    "branch": "RAB-BASE",
                    "source_branch": branch_name,
                    "merge_proof_passed": False,
                    "pre_merge_head": pre_merge_head,
                    "rollback_applied": rollback_applied,
                    "rollback_target": rollback_target,
                    "error": {"code": exc.code, "message": exc.message, "stage": exc.stage},
                    "rollback_error": rollback_error,
                    "llm_exit_code": exit_code,
                    "finished_at": utc_now_iso(),
                }
                _atomic_write_json(action_path, action_payload)
                _atomic_write_json(validation_path, validation_payload)
                verification_ref = os.path.relpath(str(validation_path), str(req.repo_root))
                merged_ok = False
                verification_ok = False
                prior_errors = [validation_payload["error"]]
                _emit_build_progress(
                    req,
                    (
                        f"branch-merge-manager: task={task_id} attempt {attempt} failed: "
                        f"{exc.code}: {exc.message}. Applying necessary fixes and retrying."
                    ),
                )
                continue

        if merged_ok and verification_ok and merged_commit:
            merged_row = {
                "task_id": task_id,
                "merged_commit": merged_commit,
                "merged_at": utc_now_iso(),
                "branch": "RAB-BASE",
                "verification_passed": True,
                "verification_ref": verification_ref,
            }
            merged_rows.append(merged_row)
            merged_ids.add(task_id)
            continue

        task_row = task_map.get(task_id)
        if isinstance(task_row, dict):
            task_row["status"] = TASK_STATUS_BLOCKED
            task_row["owner_slot"] = None
            merge_gap_id = _gap_id(_as_str(plan_packets.get("plan_id")) or "plan-unknown", _as_str(task_row.get("phase_id")) or "phase-1", task_id, "merge:blocked", "blocked")
            _upsert_task_gap(
                task_row,
                {
                    "gap_id": merge_gap_id,
                    "category": "merge_blocked",
                    "severity": "P1",
                    "stage": "merge",
                    "status": "open",
                    "reason_codes": ["merge_or_verification_failed"],
                    "retry_count": 10,
                    "max_retries": 10,
                    "created_at": utc_now_iso(),
                    "updated_at": utc_now_iso(),
                    "closure_ref": verification_ref,
                },
            )
        last_error = prior_errors[0] if prior_errors else {}
        last_error_code = _as_str(last_error.get("code"))
        if last_error_code in {
            "branch_manager_action_invalid",
            "branch_manager_execution_failed",
            "merge_proof_failed",
            "manager_command_disallowed",
            "manager_command_timeout",
        }:
            warnings.append(
                {
                    "code": last_error_code,
                    "message": _as_str(last_error.get("message")) or f"branch manager failed for {task_id}",
                    "stage": "build_loop",
                    "task_id": task_id,
                }
            )
        warnings.append(
            {
                "code": "merge_manager_retry_exhausted",
                "message": f"branch manager exhausted retries for {task_id}; task blocked with merge gap",
                "stage": "build_loop",
                "task_id": task_id,
            }
        )
        _emit_build_progress(
            req,
            f"branch-merge-manager: task={task_id} exhausted retries (10/10), task blocked",
        )

    out = {
        "schema_version": SCHEMA_VERSION,
        "updated_at": utc_now_iso(),
        "review_done_task_ids": sorted(review_done),
        "merged_task_ids": sorted({_as_str(row.get('task_id')) for row in merged_rows if _as_str(row.get('task_id'))}),
        "pending_merge_task_ids": sorted([task_id for task_id in review_done if task_id not in {_as_str(row.get('task_id')) for row in merged_rows if _as_str(row.get('task_id'))}]),
        "branch": "RAB-BASE",
        "merged_tasks": merged_rows,
    }
    _atomic_write_json(registry_path, out)
    if out["pending_merge_task_ids"]:
        warnings.append(
            {
                "code": "branch_merge_pending_tasks",
                "message": f"{len(out['pending_merge_task_ids'])} review_done task(s) pending branch merge on RAB-BASE",
                "stage": "build_loop",
                "task_ids": out["pending_merge_task_ids"],
            }
        )
    return warnings


def _manager_workstation_cycle(
    req: OpRequest,
    *,
    task_state: dict[str, Any],
    build_state: dict[str, Any],
) -> dict[str, Any]:
    warnings: list[dict[str, Any]] = []
    out: dict[str, Any] = {
        "warnings": warnings,
        "fatal": False,
        "fatal_code": None,
        "fatal_message": None,
    }
    cycle = int(build_state.get("last_cycle", 0))
    script = _resolve_skill_script("workstation-preparation", "prepare_workstation.py", required=False)
    if script is None:
        fatal_message = "workstation-preparation skill script missing; build cannot continue safely"
        attempt_dir = req.repo_root / "reports" / "optimus-prime" / "workstation-manager" / f"attempt-{cycle}"
        _atomic_write_json(
            attempt_dir / "WORKSTATION_VALIDATION.json",
            {
                "schema_version": SCHEMA_VERSION,
                "cycle": cycle,
                "updated_at": utc_now_iso(),
                "ok": False,
                "status": "blocked_fatal",
                "error": {
                    "code": "workstation_manager_missing_skill_fatal",
                    "message": fatal_message,
                    "stage": "build_loop",
                },
            }
        )
        warnings.append(
            {
                "code": "workstation_manager_missing_skill_fatal",
                "message": fatal_message,
                "stage": "build_loop",
            }
        )
        out["fatal"] = True
        out["fatal_code"] = "workstation_manager_missing_skill_fatal"
        out["fatal_message"] = fatal_message
        return out
    script_path = str(script.resolve())
    prompt_template_path = WORKSTATION_MANAGER_PROMPT_TEMPLATE_PATH.resolve()
    prompt_template_text = (
        prompt_template_path.read_text(encoding="utf-8")
        if prompt_template_path.exists()
        else ""
    )
    if req.dry_run:
        attempt_dir = req.repo_root / "reports" / "optimus-prime" / "workstation-manager" / f"attempt-{cycle}"
        _atomic_write_json(
            attempt_dir / "WORKSTATION_ACTION.json",
            {
                "schema_version": SCHEMA_VERSION,
                "cycle": cycle,
                "updated_at": utc_now_iso(),
                "status": "skipped_dry_run",
            },
        )
        _atomic_write_json(
            attempt_dir / "WORKSTATION_VALIDATION.json",
            {
                "schema_version": SCHEMA_VERSION,
                "cycle": cycle,
                "updated_at": utc_now_iso(),
                "ok": True,
                "status": "passed",
                "checks": [{"id": "workstation_manager_dry_run", "passed": True}],
            },
        )
        return out
    registry_path = req.repo_root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
    registry_base, workers, registry_shape = _load_worker_registry(registry_path)
    task_map = _task_by_id(task_state)
    dispatch_assignments, _, dispatch_plan_ok = _load_work_dispatch_plan_assignments(
        req.repo_root,
        active_phase_id=_as_str(build_state.get("current_phase_id")),
    )
    assignments_by_slot: dict[str, dict[str, Any]] = {}
    if dispatch_plan_ok:
        for row in dispatch_assignments:
            if not isinstance(row, dict):
                continue
            slot_name = _as_str(row.get("slot"))
            if slot_name and slot_name not in assignments_by_slot:
                assignments_by_slot[slot_name] = row

    def _payload_text(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value.strip()
        return str(value).strip()

    for worker in workers:
        if not isinstance(worker, dict):
            continue
        role = _as_str(worker.get("role")) or ""
        if role not in {"developer", "tester", "reviewer"}:
            continue
        slot = _as_str(worker.get("slot")) or "unknown-slot"
        assignment = assignments_by_slot.get(slot) if isinstance(assignments_by_slot.get(slot), dict) else None
        lane_id = _as_str(worker.get("lane_id")) or _as_str((assignment or {}).get("lane_id"))
        prev_lane_id = _as_str(worker.get("previous_lane_id"))
        active_task_id = (
            _as_str(worker.get("active_task_id"))
            or _as_str(worker.get("active_task"))
            or _as_str((assignment or {}).get("task_id"))
        )
        if not active_task_id and assignment is None:
            continue
        current_worktree = _as_str(worker.get("worktree_root"))
        current_worktree_path = Path(current_worktree).expanduser() if current_worktree else None
        current_worktree_resolved: Path | None = None
        if current_worktree_path is not None:
            try:
                current_worktree_resolved = current_worktree_path.resolve()
            except OSError:
                current_worktree_resolved = current_worktree_path
        current_worktree_ok = bool(
            current_worktree_path
            and current_worktree_path.exists()
            and current_worktree_path.is_dir()
        )
        expected_worktree_name = _expected_slot_worktree_name(slot) or (
            current_worktree_path.name if current_worktree_path else None
        )
        expected_worktree_path = _expected_slot_worktree_path(req.repo_root, slot)
        current_worktree_matches_slot = bool(
            current_worktree_ok
            and expected_worktree_path
            and current_worktree_resolved
            and current_worktree_resolved == expected_worktree_path
        )
        task_status = _normalize_task_status((task_map.get(active_task_id) or {}).get("status")) if active_task_id else None
        current_branch = _as_str(worker.get("branch"))
        branch_prefix = f"codex/{slot}/"
        current_branch_prefix_ok = bool(current_branch and current_branch.startswith(branch_prefix))
        task_branch = _as_str((task_map.get(active_task_id) or {}).get("active_branch")) if active_task_id else None
        if not task_branch and active_task_id:
            next_stage = _as_str((assignment or {}).get("next_stage"))
            if next_stage == "test":
                task_branch = f"codex/{slot}/{active_task_id.lower()}-test"
            elif next_stage == "review":
                task_branch = f"codex/{slot}/{active_task_id.lower()}-review"
        if (
            active_task_id
            and task_status in {TASK_STATUS_DEV_WORKING, TASK_STATUS_TESTING, TASK_STATUS_REVIEWING}
            and lane_id
            and prev_lane_id
            and lane_id == prev_lane_id
            and current_worktree_matches_slot
            and current_branch_prefix_ok
        ):
            warnings.append(
                {
                    "code": "workstation_skip_same_lane_in_progress",
                    "message": f"skipping workstation prep for slot {slot}: same-lane in-progress task",
                    "stage": "build_loop",
                    "slot": slot,
                    "task_id": active_task_id,
                    "lane_id": lane_id,
                }
            )
            continue
        if not task_branch:
            worker_branch = _as_str(worker.get("branch"))
            if worker_branch and worker_branch != "RAB-BASE":
                task_branch = worker_branch
        if not task_branch:
            task_branch = _default_slot_branch(slot, role=role)
        branch_mismatch = bool(current_branch and task_branch and current_branch != task_branch)
        branch_prefix_mismatch = bool(current_branch and not current_branch_prefix_ok)
        lane_transition = bool(lane_id and prev_lane_id and lane_id != prev_lane_id)
        worktree_path_mismatch = bool(
            current_worktree_ok
            and expected_worktree_path
            and current_worktree_resolved
            and current_worktree_resolved != expected_worktree_path
        )
        needs_prep = (
            lane_transition
            or not current_worktree_ok
            or not current_branch
            or branch_mismatch
            or branch_prefix_mismatch
            or worktree_path_mismatch
        )
        if not needs_prep:
            continue
        _emit_build_progress(
            req,
            f"workstation-manager: preparing slot={slot} role={role} lane={lane_id or '-'} task={active_task_id or '-'}",
        )
        role_arg = "developer" if role == "developer" else "tester" if role == "tester" else "reviewer"
        prepared = False
        prior_errors: list[dict[str, Any]] = []
        for attempt in range(1, 11):
            _emit_build_progress(req, f"workstation-manager: slot={slot} attempt {attempt}/10")
            attempt_dir = req.repo_root / "reports" / "optimus-prime" / "workstation-manager" / f"attempt-{slot}-{attempt}"
            action_path = attempt_dir / "WORKSTATION_ACTION.json"
            validation_path = attempt_dir / "WORKSTATION_VALIDATION.json"
            stdout_path = attempt_dir / "llm_stdout.log"
            stderr_path = attempt_dir / "llm_stderr.log"
            last_message_path = attempt_dir / "last_message.txt"
            prompt_path = attempt_dir / "prompt.txt"
            if not prompt_template_text:
                _emit_build_progress(
                    req,
                    (
                        f"workstation-manager: slot={slot} attempt {attempt} failed: "
                        f"prompt template missing at {prompt_template_path}; retrying."
                    ),
                )
                validation_payload = {
                    "schema_version": SCHEMA_VERSION,
                    "slot": slot,
                    "task_id": active_task_id,
                    "lane_id": lane_id,
                    "attempt": attempt,
                    "ok": False,
                    "error": {
                        "code": "workstation_action_invalid",
                        "message": f"workstation manager prompt template missing: {prompt_template_path}",
                        "stage": "build_loop",
                    },
                    "updated_at": utc_now_iso(),
                }
                _atomic_write_json(validation_path, validation_payload)
                prior_errors = [validation_payload["error"]]
                continue
            prompt = prompt_template_text
            prompt = prompt.replace("{{REPO_ROOT}}", str(req.repo_root))
            prompt = prompt.replace("{{SLOT}}", slot)
            prompt = prompt.replace("{{ROLE}}", role_arg)
            prompt = prompt.replace("{{LANE_ID}}", lane_id or "")
            prompt = prompt.replace("{{TASK_ID}}", active_task_id or "")
            prompt = prompt.replace("{{BRANCH_NAME}}", task_branch)
            prompt = prompt.replace("{{ACTION_PATH}}", str(action_path))
            prompt = prompt.replace("{{WORKSTATION_SCRIPT_PATH}}", script_path)
            prompt = prompt.replace("{{EXPECTED_WORKTREE_NAME}}", expected_worktree_name or "")
            prompt = prompt.replace(
                "{{CURRENT_WORKTREE_NAME}}",
                Path(current_worktree).name if current_worktree else "",
            )
            if prior_errors:
                repair_lines = [
                    f"{idx}. [{_as_str(item.get('code')) or 'error'}] {_as_str(item.get('message')) or 'validation failed'}"
                    for idx, item in enumerate(prior_errors, start=1)
                ]
                prompt += "\n\nRepair context from previous failed attempt:\n" + "\n".join(repair_lines) + "\n"
            prompt_path.parent.mkdir(parents=True, exist_ok=True)
            prompt_path.write_text(prompt, encoding="utf-8")
            try:
                llm_exit_code = run_codex_exec(
                    repo_root=req.repo_root,
                    prompt_text=prompt,
                    output_last_message=last_message_path,
                    stdout_path=stdout_path,
                    stderr_path=stderr_path,
                )
            except OSError as exc:
                _emit_build_progress(
                    req,
                    (
                        f"workstation-manager: slot={slot} attempt {attempt} failed: "
                        f"unable to invoke codex exec ({exc}); retrying."
                    ),
                )
                validation_payload = {
                    "schema_version": SCHEMA_VERSION,
                    "slot": slot,
                    "task_id": active_task_id,
                    "lane_id": lane_id,
                    "attempt": attempt,
                    "ok": False,
                    "error": {
                        "code": "workstation_execution_failed",
                        "message": f"unable to invoke codex exec: {exc}",
                        "stage": "build_loop",
                    },
                    "updated_at": utc_now_iso(),
                }
                _atomic_write_json(validation_path, validation_payload)
                prior_errors = [validation_payload["error"]]
                continue
            try:
                action_payload = _read_json(action_path)
            except OpError as exc:
                _emit_build_progress(
                    req,
                    (
                        f"workstation-manager: slot={slot} attempt {attempt} failed: "
                        f"invalid WORKSTATION_ACTION artifact ({exc.message}); retrying."
                    ),
                )
                validation_payload = {
                    "schema_version": SCHEMA_VERSION,
                    "slot": slot,
                    "task_id": active_task_id,
                    "lane_id": lane_id,
                    "attempt": attempt,
                    "ok": False,
                    "error": {
                        "code": "workstation_action_invalid",
                        "message": f"missing/invalid WORKSTATION_ACTION.json: {exc.message}",
                        "stage": "build_loop",
                    },
                    "updated_at": utc_now_iso(),
                }
                _atomic_write_json(validation_path, validation_payload)
                prior_errors = [validation_payload["error"]]
                continue
            if not isinstance(action_payload, dict):
                _emit_build_progress(
                    req,
                    (
                        f"workstation-manager: slot={slot} attempt {attempt} failed: "
                        "WORKSTATION_ACTION.json must be object; retrying."
                    ),
                )
                validation_payload = {
                    "schema_version": SCHEMA_VERSION,
                    "slot": slot,
                    "task_id": active_task_id,
                    "lane_id": lane_id,
                    "attempt": attempt,
                    "ok": False,
                    "error": {
                        "code": "workstation_action_invalid",
                        "message": "WORKSTATION_ACTION.json must be object",
                        "stage": "build_loop",
                    },
                    "updated_at": utc_now_iso(),
                }
                _atomic_write_json(validation_path, validation_payload)
                prior_errors = [validation_payload["error"]]
                continue
            action_errors: list[str] = []
            if _as_str(action_payload.get("slot")) != slot:
                action_errors.append("slot mismatch")
            action_task_id = _payload_text(action_payload.get("task_id"))
            if action_task_id != (active_task_id or ""):
                action_errors.append("task_id mismatch")
            action_lane_id = _payload_text(action_payload.get("lane_id"))
            if action_lane_id != (lane_id or ""):
                action_errors.append("lane_id mismatch")
            if _as_str(action_payload.get("branch_name")) != task_branch:
                action_errors.append("branch_name mismatch")
            action_worktree_name = _as_str(action_payload.get("worktree_name"))
            if not action_worktree_name:
                action_errors.append("worktree_name required")
            elif expected_worktree_name and action_worktree_name != expected_worktree_name:
                action_errors.append(f"worktree_name mismatch (expected {expected_worktree_name})")
            prepare_command = _as_str(action_payload.get("prepare_command"))
            if not prepare_command:
                action_errors.append("prepare_command must invoke bundled prepare_workstation.py")
            else:
                prepare_script_path = _extract_script_path_from_command(
                    prepare_command,
                    script_name="prepare_workstation.py",
                    cwd=req.repo_root,
                )
                expected_script_path = Path(script_path).resolve()
                if prepare_script_path is None:
                    action_errors.append("prepare_command must invoke bundled prepare_workstation.py")
                elif prepare_script_path != expected_script_path:
                    action_errors.append(
                        f"prepare_command must invoke bundled prepare_workstation.py at {expected_script_path}"
                    )
                prepare_branch_name = _extract_command_option_value(
                    prepare_command,
                    "--branch-name",
                    cwd=req.repo_root,
                )
                if prepare_branch_name != task_branch:
                    action_errors.append("prepare_command --branch-name mismatch")
                prepare_base_ref = _extract_command_option_value(
                    prepare_command,
                    "--base-ref",
                    cwd=req.repo_root,
                )
                if prepare_base_ref != "RAB-BASE":
                    action_errors.append("prepare_command must include --base-ref RAB-BASE")
                prepare_worktree_name = _extract_command_option_value(
                    prepare_command,
                    "--worktree-name",
                    cwd=req.repo_root,
                )
                if expected_worktree_name and prepare_worktree_name != expected_worktree_name:
                    action_errors.append(
                        f"prepare_command --worktree-name mismatch (expected {expected_worktree_name})"
                    )
            prereq_policy = _as_str(action_payload.get("prereq_policy"))
            if prereq_policy not in {"copy_env_files", "symlink_deps", "copy_env_files|symlink_deps"}:
                action_errors.append("prereq_policy must be copy_env_files|symlink_deps")
            if action_errors:
                _emit_build_progress(
                    req,
                    (
                        f"workstation-manager: slot={slot} attempt {attempt} validation failed: "
                        f"{'; '.join(action_errors)}"
                        + ("; applying necessary fixes and retrying." if attempt < 10 else "")
                    ),
                )
                validation_payload = {
                    "schema_version": SCHEMA_VERSION,
                    "slot": slot,
                    "task_id": active_task_id,
                    "lane_id": lane_id,
                    "attempt": attempt,
                    "ok": False,
                    "error": {
                        "code": "workstation_action_invalid",
                        "message": "; ".join(action_errors),
                        "stage": "build_loop",
                    },
                    "updated_at": utc_now_iso(),
                }
                _atomic_write_json(action_path, action_payload)
                _atomic_write_json(validation_path, validation_payload)
                prior_errors = [validation_payload["error"]]
                continue

            prepare_result = _run_manager_command(
                prepare_command,
                cwd=req.repo_root,
                timeout_sec=WORKSTATION_PREP_COMMAND_TIMEOUT_SEC,
                manager="workstation",
            )
            code = prepare_result.get("exit_code")
            stdout_text = _as_str(prepare_result.get("stdout")) or ""
            err = _as_str(prepare_result.get("stderr")) or ""
            manager_error_code = _as_str(prepare_result.get("code"))
            parsed: dict[str, Any] | None = None
            try:
                parsed_raw = json.loads(stdout_text.strip() or "{}")
                if isinstance(parsed_raw, dict):
                    parsed = parsed_raw
            except json.JSONDecodeError:
                parsed = None
            prepare_payload_ok = isinstance(parsed, dict) and parsed.get("ok") is True
            prepare_payload_error = _as_str(parsed.get("error")) if isinstance(parsed, dict) else None
            target_path = _as_str(parsed.get("target_path")) if isinstance(parsed, dict) else None
            branch_name_resolved = _as_str(parsed.get("branch_name_resolved")) if isinstance(parsed, dict) else None
            branch_check_ok = False
            target_path_exists = False
            target_path_matches_expected = False
            resolved_target_path: Path | None = None
            branch_check_error: str | None = None
            resolved_branch = branch_name_resolved or task_branch
            if prepare_payload_ok and target_path:
                target_root = Path(target_path).expanduser()
                try:
                    resolved_target_path = target_root.resolve()
                except OSError:
                    resolved_target_path = target_root
                if expected_worktree_path and resolved_target_path != expected_worktree_path:
                    branch_check_error = (
                        "prepared target_path mismatch: "
                        f"expected {expected_worktree_path}, got {resolved_target_path}"
                    )
                else:
                    target_path_matches_expected = True
                    target_path_exists = target_root.exists() and target_root.is_dir()
                    if target_path_exists:
                        try:
                            branch_check = _git_text(target_root, "rev-parse", "--abbrev-ref", "HEAD")
                            branch_check_ok = bool(branch_check and branch_check == resolved_branch)
                        except (OSError, ValueError) as exc:
                            branch_check_error = f"unable to verify prepared worktree branch: {exc}"
                            branch_check_ok = False
                    else:
                        branch_check_error = f"prepared target_path does not exist: {target_path}"
            elif prepare_payload_error:
                branch_check_error = f"prepare_workstation failed: {prepare_payload_error}"
            validation_payload = {
                "schema_version": SCHEMA_VERSION,
                "slot": slot,
                "task_id": active_task_id,
                "lane_id": lane_id,
                "attempt": attempt,
                "ok": bool(
                    _as_bool(prepare_result.get("ok"), default=False)
                    and prepare_payload_ok
                    and parsed
                    and target_path
                    and target_path_matches_expected
                    and branch_check_ok
                ),
                "checks": [
                    {"id": "prepare_command_exit_zero", "passed": _as_bool(prepare_result.get("ok"), default=False)},
                    {"id": "prepare_output_json", "passed": isinstance(parsed, dict)},
                    {"id": "prepare_payload_ok", "passed": prepare_payload_ok},
                    {"id": "prepare_target_path", "passed": bool(target_path)},
                    {"id": "prepare_target_path_expected", "passed": target_path_matches_expected},
                    {"id": "prepare_target_path_exists", "passed": target_path_exists},
                    {"id": "prepare_branch_match", "passed": branch_check_ok},
                ],
                "result": parsed,
                "stderr": (err or "").strip(),
                "error_code": manager_error_code,
                "branch_check_error": branch_check_error,
                "llm_exit_code": llm_exit_code,
                "updated_at": utc_now_iso(),
            }
            _atomic_write_json(action_path, action_payload)
            _atomic_write_json(validation_path, validation_payload)
            if validation_payload["ok"]:
                worker["worktree_root"] = str(resolved_target_path or Path(target_path))
                worker["branch"] = resolved_branch
                _apply_slot_lane_transition(worker, lane_id)
                worker["updated_at"] = utc_now_iso()
                _emit_build_progress(
                    req,
                    f"workstation-manager: slot={slot} ready worktree={target_path} branch={resolved_branch}",
                )
                prepared = True
                break
            prior_errors = [
                {
                    "code": manager_error_code or "workstation_execution_failed",
                    "message": (
                        prepare_payload_error
                        or branch_check_error
                        or _as_str(prepare_result.get("message"))
                        or (_as_str(parsed.get("error")) if isinstance(parsed, dict) else None)
                        or "workstation action execution/validation failed"
                    ),
                }
            ]
            _emit_build_progress(
                req,
                (
                    f"workstation-manager: slot={slot} attempt {attempt} execution/validation failed: "
                    f"{_as_str(prior_errors[0].get('message')) or 'unknown'}"
                    + ("; applying necessary fixes and retrying." if attempt < 10 else "")
                ),
            )
        if prepared:
            continue
        if active_task_id and isinstance(task_map.get(active_task_id), dict):
            task = task_map[active_task_id]
            task["status"] = TASK_STATUS_BLOCKED
            task["owner_slot"] = None
            _upsert_task_gap(
                task,
                {
                    "gap_id": _gap_id(_as_str(build_state.get("plan_id")) or "plan-unknown", _as_str(task.get("phase_id")) or "phase-1", active_task_id, "workstation:blocked", "blocked"),
                    "category": "other",
                    "severity": "P1",
                    "stage": "workstation",
                    "status": "open",
                    "reason_codes": ["workstation_prepare_failed"],
                    "retry_count": 10,
                    "max_retries": 10,
                    "created_at": utc_now_iso(),
                    "updated_at": utc_now_iso(),
                    "closure_ref": None,
                    "slot": slot,
                },
            )
        last_error = prior_errors[0] if prior_errors else {}
        last_error_code = _as_str(last_error.get("code"))
        if last_error_code in {
            "workstation_action_invalid",
            "workstation_execution_failed",
            "manager_command_disallowed",
            "manager_command_timeout",
        }:
            warnings.append(
                {
                    "code": last_error_code,
                    "message": _as_str(last_error.get("message")) or f"workstation manager failed for slot {slot}",
                    "stage": "build_loop",
                    "slot": slot,
                    "task_id": active_task_id,
                }
            )
        warnings.append(
            {
                "code": "workstation_manager_retry_exhausted",
                "message": f"workstation preparation exhausted retries for slot {slot}",
                "stage": "build_loop",
                "slot": slot,
                "task_id": active_task_id,
            }
        )
        _emit_build_progress(
            req,
            f"workstation-manager: slot={slot} exhausted retries (10/10), task blocked",
        )
    _write_worker_registry(registry_path, registry_base, workers, registry_shape if registry_shape in {"dict_list", "dict_dict", "list"} else "dict_list")
    return out


def _manager_dispatcher_cycle(
    req: OpRequest,
    *,
    plan_packets: dict[str, Any],
    task_state: dict[str, Any],
    build_state: dict[str, Any],
    active_phase_id: str | None,
    forced_assignments: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    assignments, plan_warnings, plan_ok = _load_work_dispatch_plan_assignments(
        req.repo_root,
        active_phase_id=active_phase_id,
    )
    forced_rows = [row for row in (forced_assignments or []) if isinstance(row, dict)]
    if not plan_ok and not forced_rows:
        return {
            "ok": True,
            "status": "skipped",
            "reason": "dispatch_plan_invalid",
            "warnings": plan_warnings,
            "warning": plan_warnings[0] if plan_warnings else None,
            "assignment_observations": [],
        }
    combined_assignments: list[dict[str, Any]] = []
    seen_assignment_keys: set[tuple[str, str, str]] = set()
    ordered_rows = [dict(row) | {"_forced": False} for row in assignments] + [
        dict(row) | {"_forced": True} for row in forced_rows
    ]
    for row in ordered_rows:
        task_id = _as_str(row.get("task_id"))
        slot = _as_str(row.get("slot"))
        stage = _as_str(row.get("next_stage"))
        if not task_id or not slot or not stage:
            continue
        key = (task_id, slot, stage)
        if key in seen_assignment_keys:
            continue
        seen_assignment_keys.add(key)
        combined_assignments.append(row)
    if not combined_assignments:
        dispatch_result = _dispatch_next_task(
            req,
            plan_packets,
            task_state,
            build_state,
            active_phase_id,
            [],
        )
        dispatch_warnings = dispatch_result.get("warnings") if isinstance(dispatch_result.get("warnings"), list) else []
        if plan_warnings:
            dispatch_warnings.extend(plan_warnings)
            dispatch_result["warnings"] = dispatch_warnings
            if not isinstance(dispatch_result.get("warning"), dict):
                dispatch_result["warning"] = plan_warnings[0]
        if not _as_str(dispatch_result.get("reason")):
            dispatch_result["reason"] = "dispatch_plan_no_assignments"
        return dispatch_result
    dispatch_result = _dispatch_next_task(
        req,
        plan_packets,
        task_state,
        build_state,
        active_phase_id,
        combined_assignments,
    )
    dispatch_warnings = dispatch_result.get("warnings") if isinstance(dispatch_result.get("warnings"), list) else []
    if plan_warnings:
        dispatch_warnings.extend(plan_warnings)
        dispatch_result["warnings"] = dispatch_warnings
        if not isinstance(dispatch_result.get("warning"), dict):
            dispatch_result["warning"] = plan_warnings[0]
    return dispatch_result


def _apply_directives(
    req: OpRequest,
    directives: list[dict[str, Any]],
    build_state: dict[str, Any],
    plan_packets: dict[str, Any],
    task_state: dict[str, Any],
) -> dict[str, Any]:
    outcomes: list[dict[str, Any]] = []
    runtime_script = _resolve_skill_script("runtime-coordinator", "runtime_coordinator.py")
    train_script = _resolve_skill_script("test-train-manager", "test_train_manager.py")
    resolved_mode = _resolve_test_train_mode(req.repo_root)
    dispatch_requested = False
    dispatch_blocked = False
    dispatch_block_reason: str | None = None
    remediation_queued = False
    runtime_defaults = {
        "repo_root": str(req.repo_root),
        "test_train_mode": resolved_mode,
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
        "test_train_mode": resolved_mode,
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
            if not _as_bool_field(result.get("ok")):
                remediation_payload = dict(runtime_defaults)
                remediation_payload["action"] = "repair"
                remediation_payload["test_train_mode"] = resolved_mode
                remediation = _run_tool_json(runtime_script, remediation_payload, req.repo_root)
                fingerprint = _detect_blocker_fingerprint(req.repo_root)
                build_state["remediation_state"] = {
                    "active": True,
                    "reason": f"{directive_type}_failed",
                    "last_queued_at": utc_now_iso(),
                    "fingerprint": None if fingerprint == "unknown-fingerprint" else fingerprint,
                }
                remediation_queued = True
                dispatch_blocked = True
                dispatch_block_reason = "directive_tool_failure"
                outcomes.append(
                    {
                        "directive_type": directive_type,
                        "status": "failed",
                        "result": result,
                        "warning_code": "directive_tool_failed_remediation_queued",
                        "remediation": remediation,
                    }
                )
                continue
            outcomes.append({"directive_type": directive_type, "status": "applied", "result": result})
            continue
        if directive_type in train_directives:
            payload = dict(train_defaults)
            payload.update(args)
            if directive_type == "hold_test_promotion":
                payload["action"] = "evaluate_promotion_gate"
            result = _run_tool_json(train_script, payload, req.repo_root)
            if not _as_bool_field(result.get("ok")):
                remediation_payload = dict(runtime_defaults)
                remediation_payload["action"] = "repair"
                remediation_payload["test_train_mode"] = resolved_mode
                remediation = _run_tool_json(runtime_script, remediation_payload, req.repo_root)
                fingerprint = _detect_blocker_fingerprint(req.repo_root)
                build_state["remediation_state"] = {
                    "active": True,
                    "reason": f"{directive_type}_failed",
                    "last_queued_at": utc_now_iso(),
                    "fingerprint": None if fingerprint == "unknown-fingerprint" else fingerprint,
                }
                remediation_queued = True
                dispatch_blocked = True
                dispatch_block_reason = "directive_tool_failure"
                outcomes.append(
                    {
                        "directive_type": directive_type,
                        "status": "failed",
                        "result": result,
                        "warning_code": "directive_tool_failed_remediation_queued",
                        "remediation": remediation,
                    }
                )
                continue
            outcomes.append({"directive_type": directive_type, "status": "applied", "result": result})
            continue
        if directive_type == "review_dispatch_queue":
            dispatch_requested = True
            outcomes.append({"directive_type": directive_type, "status": "queued", "reason": "dispatch reviewed by build loop"})
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
            outcomes.append(
                {
                    "directive_type": directive_type,
                    "status": "applied",
                    "result": {
                        "hard_gated": True,
                        "scope": "per_assignment",
                    },
                }
            )
            continue
        outcomes.append({"directive_type": directive_type, "status": "skipped", "reason": "unsupported directive"})
    return {
        "outcomes": outcomes,
        "dispatch_requested": dispatch_requested,
        "dispatch_blocked": dispatch_blocked,
        "dispatch_block_reason": dispatch_block_reason,
        "remediation_queued": remediation_queued,
        "resolved_test_train_mode": resolved_mode,
    }


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
    gaps_payload: dict[str, Any] | None,
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
        status = _normalize_task_status(task.get("status"))
        if status != TASK_STATUS_REVIEW_DONE:
            all_review_done = False
        evidence = task.get("evidence") if isinstance(task.get("evidence"), dict) else {}
        dev_ref = _as_str(evidence.get("task_evidence_ref")) or _as_str(evidence.get("dev_ready_evidence_ref"))
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
    open_gap_ids = _open_task_gap_ids(task_state)
    done_registry_path = _repo_path(repo_root, DONE_TASKS_REGISTRY_JSON)
    merged_rows: list[dict[str, Any]] = []
    if done_registry_path.exists():
        try:
            done_registry_payload = _read_json(done_registry_path)
        except OpError:
            done_registry_payload = {}
        if isinstance(done_registry_payload, dict):
            merged_rows_raw = done_registry_payload.get("merged_tasks")
            if isinstance(merged_rows_raw, list):
                merged_rows = [row for row in merged_rows_raw if isinstance(row, dict)]
    merged_by_task = {
        _as_str(row.get("task_id")): row
        for row in merged_rows
        if _as_str(row.get("task_id"))
    }
    review_done_ids = [
        task_id
        for task_id in plan_tasks
        if _normalize_task_status((task_map.get(task_id) or {}).get("status")) == TASK_STATUS_REVIEW_DONE
    ]
    missing_merged_task_ids = sorted([task_id for task_id in review_done_ids if task_id not in merged_by_task])
    failed_merge_verification_task_ids = sorted(
        [
            task_id
            for task_id in review_done_ids
            if task_id in merged_by_task and not bool((merged_by_task.get(task_id) or {}).get("verification_passed"))
        ]
    )
    all_review_done_tasks_merged = len(missing_merged_task_ids) == 0
    merge_verification_passed = len(failed_merge_verification_task_ids) == 0
    phase_checks: dict[str, Any] = {}
    for phase_id in _ordered_phase_ids(plan_packets):
        phase_checks[phase_id] = _phase_exit_checks(repo_root, phase_id, plan_packets, task_state)
    all_phases_complete = bool(phase_checks) and all(bool(item.get("all_passed")) for item in phase_checks.values())
    checks = {
        "tasks_exist_in_task_state": task_ids_present,
        "all_tasks_review_done": all_review_done,
        "all_review_done_tasks_merged": all_review_done_tasks_merged,
        "merge_verification_passed": merge_verification_passed,
        "all_tasks_have_dev_ready_evidence_ref": all_dev_refs,
        "verify_commands_passed": verify_commands_passed,
        "uat_matrix_passed": uat_passed,
        "all_phases_complete": all_phases_complete,
        "zero_open_gaps": len(open_gap_ids) == 0,
        "final_state_authorized": final_state_ok,
    }
    checks["all_passed"] = all(checks.values())
    checks["missing_verify_commands"] = sorted(required_verify_cmds - passed_verify_cmds)
    checks["missing_uat_requirement_ids"] = sorted(required_uat_ids - passed_uat_reqs)
    checks["missing_merged_task_ids"] = missing_merged_task_ids
    checks["failed_merge_verification_task_ids"] = failed_merge_verification_task_ids
    checks["open_gap_ids"] = [gap_id for gap_id in open_gap_ids if gap_id]
    checks["phase_checks"] = phase_checks
    return checks


def _preflight_build(
    req: OpRequest,
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any] | None]:
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
        try:
            parsed = _read_json(state_path)
        except OpError as exc:
            warnings.append(
                {
                    "code": "state_payload_invalid",
                    "message": f"STATE.json unreadable: {exc.message}",
                    "stage": "build_preflight",
                }
            )
            parsed = None
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
        try:
            parsed_plan = _read_json(plan_packets_path)
        except OpError as exc:
            warnings.append(
                {
                    "code": "plan_packets_invalid",
                    "message": f"PLAN_PACKETS.json unreadable: {exc.message}",
                    "stage": "build_preflight",
                }
            )
            parsed_plan = None
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
        try:
            parsed_task = _read_json(task_state_path)
        except OpError as exc:
            warnings.append(
                {
                    "code": "task_state_invalid",
                    "message": f"TASK_EXECUTION_STATE.json unreadable: {exc.message}",
                    "stage": "build_preflight",
                }
            )
            parsed_task = None
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

    profile_selection: dict[str, Any] | None = None
    try:
        profile_selection = _load_profile_selection_required(req.repo_root, stage="build_preflight")
    except OpError as exc:
        warnings.append(
            {
                "code": exc.code,
                "message": exc.message,
                "stage": "build_preflight",
            }
        )

    return warnings, missing, state_payload, plan_packets, task_state, profile_selection


def command_build(req: OpRequest) -> dict[str, Any]:
    _emit_build_progress(req, f"starting build runtime for {req.repo_root}")
    auto_init_warnings: list[dict[str, Any]] = []
    mission_scope_supplied = bool(req.mission or req.mission_file or req.scope or req.scope_file)
    if mission_scope_supplied:
        state_path = _repo_path(req.repo_root, STATE_JSON)
        baseline_missing = any(
            not _repo_path(req.repo_root, rel).exists()
            for rel in MANDATORY_BUILD_BASELINE
        )
        strict_done_complete = False
        build_state_path = _repo_path(req.repo_root, BUILD_STATE_JSON)
        if build_state_path.exists():
            try:
                build_state_probe = _load_build_state(build_state_path)
            except OpError:
                build_state_probe = {}
            checks = build_state_probe.get("strict_done_checks") if isinstance(build_state_probe.get("strict_done_checks"), dict) else {}
            strict_done_complete = bool(checks.get("all_passed")) or (_as_str((build_state_probe.get("terminal_state") or {}).get("reason")) == "project_done")

        if baseline_missing or not state_path.exists():
            _emit_build_progress(req, "baseline missing, running /op-initialize (includes planner)")
            init_result = command_initialize(req)
            auto_init_warnings.extend(init_result.get("warnings", []) if isinstance(init_result.get("warnings"), list) else [])
            if not bool(init_result.get("ok")):
                return init_result
            _emit_build_progress(req, "auto-initialize completed")
        else:
            if strict_done_complete:
                _emit_build_progress(req, "strict-done baseline found, refreshing with /op-initialize --override-old-plan")
                init_req = replace(req, command="op-initialize", override_old_plan=True)
                init_result = command_initialize(init_req)
                auto_init_warnings.extend(init_result.get("warnings", []) if isinstance(init_result.get("warnings"), list) else [])
                if not bool(init_result.get("ok")):
                    return init_result
                _emit_build_progress(req, "auto-initialize refresh completed")
            elif req.override_old_plan:
                _emit_build_progress(req, "override requested, running /op-initialize --override-old-plan")
                init_req = replace(req, command="op-initialize", override_old_plan=True)
                init_result = command_initialize(init_req)
                auto_init_warnings.extend(init_result.get("warnings", []) if isinstance(init_result.get("warnings"), list) else [])
                if not bool(init_result.get("ok")):
                    return init_result
                _emit_build_progress(req, "override initialize completed")
            else:
                return _response(
                    req,
                    ok=False,
                    status="blocked_preflight",
                    summary="Build blocked: baseline exists and active plan is not strictly done.",
                    errors=[
                        {
                            "code": "resume_or_override_required",
                            "message": "Use /op-resume to continue existing run, or pass --override-old-plan with mission/scope to re-initialize.",
                            "stage": "build_preflight",
                        }
                    ],
                    next_action="Run /op-resume, or rerun /op-build with --override-old-plan and mission/scope.",
                    state_ref=str(state_path),
                )

    _emit_build_progress(req, "running preflight checks")
    warnings, missing, _, plan_packets, task_state, profile_selection = _preflight_build(req)
    if auto_init_warnings:
        warnings = [*auto_init_warnings, *warnings]
    preflight_failed = bool(missing) or any(
        item.get("code")
        in {
            "plan_not_ready",
            "task_state_invalid",
            "task_state_plan_mismatch",
            "plan_packets_invalid",
            "state_payload_invalid",
            "profile_selection_missing",
            "profile_selection_invalid",
        }
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
    try:
        build_state = _load_build_state(build_state_path)
    except OpError as exc:
        warnings.append(
            {
                "code": "build_state_invalid",
                "message": exc.message,
                "stage": "build_preflight",
            }
        )
        return _response(
            req,
            ok=False,
            status="blocked_preflight",
            summary="Build blocked: strict planning baseline is incomplete.",
            warnings=warnings,
            errors=[
                {
                    "code": "build_preflight_failed",
                    "message": "Repair BUILD_STATE.json and rerun /op-build.",
                    "stage": "build_preflight",
                }
            ],
            next_action="Fix malformed build state artifacts or rerun /op-initialize, then rerun /op-build.",
            state_ref=str(build_state_path),
        )
    if not isinstance(profile_selection, dict):
        return _response(
            req,
            ok=False,
            status="blocked_preflight",
            summary="Build blocked: profile selection artifact is missing or invalid.",
            warnings=warnings,
            errors=[
                {
                    "code": "build_preflight_failed",
                    "message": "Run /op-initialize to detect profiles and regenerate PROFILE_SELECTION.json.",
                    "stage": "build_preflight",
                }
            ],
            next_action="Run /op-initialize, then rerun /op-build.",
            state_ref=str(_repo_path(req.repo_root, STATE_JSON)),
        )
    selected_aliases = [
        alias for alias in (_as_str(item) for item in profile_selection.get("selected_aliases", [])) if alias
    ]
    build_state["profile_aliases"] = selected_aliases
    build_state["profile_assignment_policy"] = "dynamic_reassign_on_gate"
    if not isinstance(build_state.get("slot_profile_assignments"), dict):
        build_state["slot_profile_assignments"] = {}

    task_state_path = _repo_path(req.repo_root, TASK_EXECUTION_STATE_JSON)
    lock_path = _repo_path(req.repo_root, BUILD_LOOP_LOCK)
    _emit_build_progress(req, "acquiring build loop lock")
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
    _emit_build_progress(req, f"build loop lock acquired ({lock_id})")
    build_state["loop_lock_id"] = lock_id
    build_state["updated_at"] = utc_now_iso()
    if not isinstance(build_state.get("last_assignment_observations"), list):
        build_state["last_assignment_observations"] = []
    _atomic_write_json(build_state_path, build_state)

    def _response_data_with_assignment_observations(
        base: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = dict(base or {})
        rows = build_state.get("last_assignment_observations")
        payload["assignment_observations"] = rows if isinstance(rows, list) else []
        return payload

    try:
        operator_stop_path = _repo_path(req.repo_root, OPERATOR_STOP_JSON)
        progress_ledger_path = _repo_path(req.repo_root, RUN_PROGRESS_LEDGER_JSONL)
        watchdog_state_path = _repo_path(req.repo_root, NO_PROGRESS_WATCHDOG_STATE_JSON)
        watchdog_event_path = _repo_path(req.repo_root, NO_PROGRESS_WATCHDOG_EVENT_JSON)
        plan_id = _as_str(plan_packets.get("plan_id")) or "plan-unknown"
        resume_cmd = "/op-resume" if req.command == "op-resume" else "/op-build"
        _emit_build_progress(req, "initializing worker registry and enforcing RAB-BASE")
        warnings.extend(_ensure_worker_registry_v2(req.repo_root, build_state))
        rab_warnings = _ensure_rab_base_checked_out(req.repo_root)
        warnings.extend(rab_warnings)
        if rab_warnings:
            return _response(
                req,
                ok=False,
                status="blocked_preflight",
                summary="Build blocked: unable to enter required integration branch.",
                warnings=warnings,
                errors=[
                    {
                        "code": "rab_base_checkout_failed",
                        "message": "RAB-BASE checkout/create failed; cannot continue build loop.",
                        "stage": "build_preflight",
                    }
                ],
                next_action="Fix git branch state/permissions, ensure RAB-BASE is available, then rerun /op-build.",
                state_ref=str(build_state_path),
            )

        _emit_build_progress(req, "entering cycle loop")
        cycles = 0
        history: list[dict[str, Any]] = build_state.get("history", [])
        if not isinstance(history, list):
            history = []
        watchdog_state = _init_no_progress_watchdog_state(watchdog_state_path, build_state)
        while req.max_build_cycles is None or cycles < req.max_build_cycles:
            cycles += 1
            cycle_local_warnings: list[dict[str, Any]] = []
            build_state["last_cycle"] = int(build_state.get("last_cycle", 0)) + 1
            _emit_build_progress(
                req,
                f"cycle {build_state['last_cycle']} start",
            )
            build_state["updated_at"] = utc_now_iso()
            build_state["cycle_gate_decision"] = {
                "dispatch_blocked": False,
                "reason": None,
                "terminal_reason": None,
            }
            remediation_state = build_state.get("remediation_state")
            if not isinstance(remediation_state, dict):
                remediation_state = {
                    "active": False,
                    "reason": None,
                    "last_queued_at": None,
                    "fingerprint": None,
                }
                build_state["remediation_state"] = remediation_state
            else:
                remediation_state["active"] = False
                remediation_state["reason"] = None

            _emit_build_progress(req, f"cycle {build_state['last_cycle']}: profile-manager")
            profile_warnings = _manager_profile_cycle(
                req,
                build_state=build_state,
                profile_selection=profile_selection,
            )
            warnings.extend(profile_warnings)
            cycle_local_warnings.extend(profile_warnings)

            _emit_build_progress(req, f"cycle {build_state['last_cycle']}: production-line-manager")
            production_out = _manager_production_line_cycle(
                req,
                plan_packets=plan_packets,
                task_state=task_state,
                build_state=build_state,
            )
            production_warnings = production_out.get("warnings", []) if isinstance(production_out.get("warnings"), list) else []
            warnings.extend(production_warnings)
            cycle_local_warnings.extend(production_warnings)
            merged_plan_packets = production_out.get("merged_plan_packets") if isinstance(production_out.get("merged_plan_packets"), dict) else plan_packets
            gaps_payload = production_out.get("gaps_payload") if isinstance(production_out.get("gaps_payload"), dict) else _default_gaps_payload(plan_id)
            active_phase_id = _as_str(production_out.get("active_phase_id"))
            phase_checks = production_out.get("phase_checks") if isinstance(production_out.get("phase_checks"), dict) else {}

            _emit_build_progress(req, f"cycle {build_state['last_cycle']}: branch-merge-manager")
            branch_warnings = _manager_branch_merge_cycle(
                req,
                plan_packets=merged_plan_packets,
                task_state=task_state,
                build_state=build_state,
            )
            warnings.extend(branch_warnings)
            cycle_local_warnings.extend(branch_warnings)

            _emit_build_progress(req, f"cycle {build_state['last_cycle']}: workstation-manager")
            workstation_out = _manager_workstation_cycle(req, task_state=task_state, build_state=build_state)
            workstation_warnings = (
                workstation_out.get("warnings", [])
                if isinstance(workstation_out.get("warnings"), list)
                else []
            )
            warnings.extend(workstation_warnings)
            cycle_local_warnings.extend(workstation_warnings)
            if _as_bool(workstation_out.get("fatal"), default=False):
                fatal_code = _as_str(workstation_out.get("fatal_code")) or "workstation_manager_missing_skill_fatal"
                fatal_message = _as_str(workstation_out.get("fatal_message")) or "workstation manager reported fatal runtime error"
                build_state["terminal_state"] = {
                    "reason": fatal_code,
                    "timestamp": utc_now_iso(),
                }
                _atomic_write_json(task_state_path, {**task_state, "updated_at": utc_now_iso()})
                _atomic_write_json(build_state_path, build_state)
                return _response(
                    req,
                    ok=False,
                    status="blocked_terminal",
                    summary="Build halted: workstation manager reported fatal runtime error.",
                    warnings=warnings,
                    errors=[
                        {
                            "code": fatal_code,
                            "message": fatal_message,
                            "stage": "build_loop",
                        }
                    ],
                    state_ref=str(build_state_path),
                    next_action="Restore workstation-preparation skill and rerun /op-build.",
                    data=_response_data_with_assignment_observations({"terminal_reason": fatal_code}),
                )

            if operator_stop_path.exists():
                stop_summary: dict[str, Any] = {}
                try:
                    stop_summary, stop_warnings = _apply_operator_stop(req.repo_root, task_state, build_state)
                    warnings.extend(stop_warnings)
                except OpError as exc:
                    warnings.append(
                        {
                            "code": "operator_stop_apply_failed",
                            "message": f"operator stop encountered errors: {exc.message}",
                            "stage": "build_loop",
                        }
                    )
                    build_state["terminal_state"] = {
                        "reason": "operator_stop_apply_failed",
                        "timestamp": utc_now_iso(),
                    }
                    _atomic_write_json(task_state_path, {**task_state, "updated_at": utc_now_iso()})
                    _atomic_write_json(build_state_path, build_state)
                    return _response(
                        req,
                        ok=False,
                        status="blocked_terminal",
                        summary="Build halted: operator stop signal could not be safely applied.",
                        warnings=warnings,
                        errors=[
                            {
                                "code": "operator_stop_apply_failed",
                                "message": exc.message,
                                "stage": "build_loop",
                            }
                        ],
                        state_ref=str(build_state_path),
                        next_action="Fix operator stop/state artifact write failures and rerun /op-build.",
                        data=_response_data_with_assignment_observations({"terminal_reason": "operator_stop_apply_failed"}),
                    )
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
                            "message": f"operator stop applied from marker {operator_stop_path}",
                            "stage": "build_loop",
                        }
                    ],
                    state_ref=str(build_state_path),
                    next_action=f"Rerun {resume_cmd} to continue with post-stop reconciliation.",
                    data=_response_data_with_assignment_observations(
                        {"terminal_reason": "operator_stop", "operator_stop": stop_summary}
                    ),
                )

            _emit_build_progress(req, f"cycle {build_state['last_cycle']}: controller tick")
            cycle_control_number = int(build_state.get("last_cycle") or 0)
            cycle_control_run_id = _as_str(build_state.get("loop_lock_id")) or lock_id
            cycle_result = _run_controller_cycle(
                req,
                control_number=cycle_control_number,
                control_run_id=cycle_control_run_id,
                profile_aliases=selected_aliases,
            )
            events_path_raw = _as_str(cycle_result.get("events_path"))
            directives: list[dict[str, Any]] = []
            if events_path_raw and cycle_control_number > 0:
                directives = _extract_cycle_directives(
                    Path(events_path_raw).expanduser().resolve(),
                    cycle_control_number,
                    cycle_control_run_id,
                )
            directive_state = _apply_directives(req, directives, build_state, merged_plan_packets, task_state)
            directive_outcomes = directive_state.get("outcomes", [])
            for outcome in directive_outcomes:
                warning_code = _as_str(outcome.get("warning_code"))
                if warning_code == "directive_tool_failed_remediation_queued":
                    warning = {
                        "code": "directive_tool_failed_remediation_queued",
                        "message": "directive tool failed; remediation was queued and dispatch skipped for this cycle",
                        "stage": "build_loop",
                        "directive_type": outcome.get("directive_type"),
                    }
                    warnings.append(warning)
                    cycle_local_warnings.append(warning)
            production_out = _manager_production_line_cycle(
                req,
                plan_packets=merged_plan_packets,
                task_state=task_state,
                build_state=build_state,
            )
            production_warnings = production_out.get("warnings", []) if isinstance(production_out.get("warnings"), list) else []
            warnings.extend(production_warnings)
            cycle_local_warnings.extend(production_warnings)
            merged_plan_packets = production_out.get("merged_plan_packets") if isinstance(production_out.get("merged_plan_packets"), dict) else merged_plan_packets
            gaps_payload = production_out.get("gaps_payload") if isinstance(production_out.get("gaps_payload"), dict) else gaps_payload
            active_phase_id = _as_str(production_out.get("active_phase_id"))
            phase_checks = production_out.get("phase_checks") if isinstance(production_out.get("phase_checks"), dict) else phase_checks

            history.append(
                {
                    "timestamp": utc_now_iso(),
                    "cycle_result": cycle_result,
                    "directives": directive_outcomes,
                    "cycle_warnings": cycle_local_warnings,
                    "strategy": build_state.get("current_strategy"),
                    "active_phase_id": active_phase_id,
                }
            )
            build_state["history"] = history[-200:]

            terminal_reason = _as_str(cycle_result.get("terminal_reason"))
            build_state["cycle_gate_decision"]["terminal_reason"] = terminal_reason
            if cycle_result.get("ok") is True and terminal_reason:
                if terminal_reason == "project_done":
                    final_state_path = req.repo_root / "reports" / "optimus-prime" / "controller" / "FINAL_STATE.json"
                    verification = _verify_final_state(req, final_state_path)
                    strict_checks = _evaluate_strict_done(req.repo_root, merged_plan_packets, task_state, verification, gaps_payload)
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
                            data=_response_data_with_assignment_observations(
                                {
                                    "terminal_reason": "project_done",
                                    "cycles_executed": cycles,
                                    "current_strategy": build_state.get("current_strategy"),
                                    "strict_done_checks": strict_checks,
                                }
                            ),
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
                    build_state["cycle_gate_decision"] = {
                        "dispatch_blocked": True,
                        "reason": "all_rate_gates_blocking",
                        "terminal_reason": terminal_reason,
                    }
                    rate_window = _read_rate_gate_window(req.repo_root)
                    if bool(rate_window.get("registry_invalid")):
                        warning = {
                            "code": "rate_registry_invalid_ignored",
                            "message": "PROFILE_RATE_REGISTRY.json is invalid; ignoring all_rate_gates_blocking stop for this cycle",
                            "stage": "build_loop",
                        }
                        if _as_str(rate_window.get("registry_error")):
                            warning["details"] = {"registry_error": rate_window.get("registry_error")}
                        warnings.append(warning)
                        cycle_local_warnings.append(warning)
                        build_state["cycle_gate_decision"] = {
                            "dispatch_blocked": False,
                            "reason": "rate_registry_invalid_ignored",
                            "terminal_reason": terminal_reason,
                        }
                        build_state["rate_gate_state"] = {
                            "hard_gated": False,
                            "min_reset_at": None,
                            "sleep_until": None,
                            "manual_rerun_required": False,
                        }
                    else:
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
                            data=_response_data_with_assignment_observations(
                                {
                                    "terminal_reason": terminal_reason,
                                    "cycles_executed": cycles,
                                    "rate_gate_state": build_state.get("rate_gate_state"),
                                }
                            ),
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
                        data=_response_data_with_assignment_observations(
                            {"terminal_reason": terminal_reason, "cycles_executed": cycles}
                        ),
                    )

            dispatch_blocked = bool(directive_state.get("dispatch_blocked"))
            dispatch_block_reason = _as_str(directive_state.get("dispatch_block_reason"))
            dispatch_reason_for_print: str | None = None
            if active_phase_id is None:
                dispatch_reason_for_print = "phase_barrier_complete_waiting_terminal"
                build_state["cycle_gate_decision"] = {
                    "dispatch_blocked": True,
                    "reason": "phase_barrier_complete_waiting_terminal",
                    "terminal_reason": terminal_reason,
                }
                warning = {
                    "code": "dispatch_skipped_hard_gate",
                    "message": "dispatch skipped for cycle: all phase barriers complete, awaiting terminal authorization",
                    "stage": "build_loop",
                }
                warnings.append(warning)
                cycle_local_warnings.append(warning)
            elif dispatch_blocked:
                dispatch_reason_for_print = dispatch_block_reason or "dispatch_filter"
                build_state["cycle_gate_decision"] = {
                    "dispatch_blocked": True,
                    "reason": dispatch_block_reason or "dispatch_filter",
                    "terminal_reason": terminal_reason,
                }
                warning = {
                    "code": "dispatch_skipped_hard_gate",
                    "message": f"dispatch skipped for cycle due to hard gate: {dispatch_block_reason or 'dispatch_filter'}",
                    "stage": "build_loop",
                }
                warnings.append(warning)
                cycle_local_warnings.append(warning)
            else:
                registry_recovery_warnings = _recover_unreadable_worker_registry(req.repo_root)
                warnings.extend(registry_recovery_warnings)
                cycle_local_warnings.extend(registry_recovery_warnings)
                normalized_workers = _normalize_dead_worker_registry_entries(req.repo_root)
                if normalized_workers > 0:
                    warning = {
                        "code": "worker_registry_dead_pid_normalized",
                        "message": f"normalized {normalized_workers} dead running worker registry entrie(s) before dispatch",
                        "stage": "build_loop",
                        "normalized_workers": normalized_workers,
                    }
                    warnings.append(warning)
                    cycle_local_warnings.append(warning)
                stale_recovery_warnings = _recover_stale_in_progress_tasks(req.repo_root, task_state, build_state)
                warnings.extend(stale_recovery_warnings)
                cycle_local_warnings.extend(stale_recovery_warnings)
                if stale_recovery_warnings:
                    recovery_production = _manager_production_line_cycle(
                        req,
                        plan_packets=merged_plan_packets,
                        task_state=task_state,
                        build_state=build_state,
                    )
                    recovery_warnings = (
                        recovery_production.get("warnings", [])
                        if isinstance(recovery_production.get("warnings"), list)
                        else []
                    )
                    warnings.extend(recovery_warnings)
                    cycle_local_warnings.extend(recovery_warnings)
                    merged_plan_packets = (
                        recovery_production.get("merged_plan_packets")
                        if isinstance(recovery_production.get("merged_plan_packets"), dict)
                        else merged_plan_packets
                    )
                    active_phase_id = _as_str(recovery_production.get("active_phase_id")) or active_phase_id
                    phase_checks = (
                        recovery_production.get("phase_checks")
                        if isinstance(recovery_production.get("phase_checks"), dict)
                        else phase_checks
                    )
                dead_pid_assignments, dead_pid_warnings = _prepare_dead_pid_redispatch_assignments(
                    req.repo_root,
                    task_state,
                    merged_plan_packets,
                    build_state,
                )
                warnings.extend(dead_pid_warnings)
                cycle_local_warnings.extend(dead_pid_warnings)
                max_running_workers = int(build_state.get("dispatch_window", {}).get("max_running_workers", 6))
                active_workers = _active_workers_count(req.repo_root)
                if active_workers is not None and active_workers >= max_running_workers:
                    dispatch_reason_for_print = "dispatch_window_cap"
                    build_state["cycle_gate_decision"] = {
                        "dispatch_blocked": True,
                        "reason": "dispatch_window_cap",
                        "terminal_reason": terminal_reason,
                    }
                    warning = {
                        "code": "dispatch_skipped_soft_cap",
                        "message": (
                            "dispatch skipped for cycle due to active worker cap: "
                            f"active={active_workers}, cap={max_running_workers}"
                        ),
                        "stage": "build_loop",
                    }
                    warnings.append(warning)
                    cycle_local_warnings.append(warning)
                else:
                    _emit_build_progress(req, f"cycle {build_state['last_cycle']}: work-dispatcher")
                    dispatch_result = _manager_dispatcher_cycle(
                        req,
                        plan_packets=merged_plan_packets,
                        task_state=task_state,
                        build_state=build_state,
                        active_phase_id=active_phase_id,
                        forced_assignments=dead_pid_assignments,
                    )
                    dispatch_warning = dispatch_result.get("warning") if isinstance(dispatch_result, dict) else None
                    dispatch_warning_rows = dispatch_result.get("warnings") if isinstance(dispatch_result, dict) else None
                    appended_warning_keys: set[tuple[str, str]] = set()
                    if isinstance(dispatch_warning_rows, list):
                        for row in dispatch_warning_rows:
                            if isinstance(row, dict):
                                warnings.append(row)
                                cycle_local_warnings.append(row)
                                appended_warning_keys.add((_as_str(row.get("code")) or "", _as_str(row.get("message")) or ""))
                    if isinstance(dispatch_warning, dict):
                        warning_key = (_as_str(dispatch_warning.get("code")) or "", _as_str(dispatch_warning.get("message")) or "")
                        if warning_key not in appended_warning_keys:
                            warnings.append(dispatch_warning)
                            cycle_local_warnings.append(dispatch_warning)
                    dispatch_observations = (
                        dispatch_result.get("assignment_observations")
                        if isinstance(dispatch_result.get("assignment_observations"), list)
                        else []
                    )
                    build_state["last_assignment_observations"] = dispatch_observations
                    status_counts = {"dispatched": 0, "skipped": 0, "failed": 0, "invalid": 0}
                    for obs in dispatch_observations:
                        if not isinstance(obs, dict):
                            continue
                        status_key = _as_str(obs.get("status"))
                        if status_key in status_counts:
                            status_counts[status_key] += 1
                    build_state["last_dispatch_cycle_summary"] = {
                        "cycle": int(build_state.get("last_cycle", 0)),
                        "reason": _as_str(dispatch_result.get("reason")) or None,
                        "counts": status_counts,
                        "observations": len(dispatch_observations),
                        "updated_at": utc_now_iso(),
                    }
                    dispatch_reason = _as_str(dispatch_result.get("reason")) if isinstance(dispatch_result, dict) else None
                    dispatch_reason_for_print = dispatch_reason
                    if dispatch_reason in {"profile_assignment_all_hard_gated"}:
                        build_state["cycle_gate_decision"] = {
                            "dispatch_blocked": True,
                            "reason": dispatch_reason,
                            "terminal_reason": terminal_reason,
                        }
                    directive_outcomes.append(
                        {
                            "directive_type": "review_dispatch_queue"
                            if directive_state.get("dispatch_requested")
                            else "auto_dispatch",
                            "status": "applied",
                            "result": dispatch_result,
                        }
                    )
                    handoff_warnings = _apply_handoff_updates(req.repo_root, task_state, build_state)
                    warnings.extend(handoff_warnings)
                    cycle_local_warnings.extend(handoff_warnings)
                    _emit_build_progress(
                        req,
                        f"cycle {build_state['last_cycle']}: {_summarize_assignment_observations(dispatch_observations)}",
                    )

            open_gap_ids = [
                gap_id
                for gap_id in (_as_str(item) for item in build_state.get("open_gap_ids", []))
                if gap_id
            ]
            progress_payload = _task_progress_payload(task_state, open_gap_ids)
            progress_fingerprint = _task_progress_fingerprint(progress_payload)
            previous_fingerprint = _as_str(build_state.get("last_task_state_fingerprint"))
            progress_delta = previous_fingerprint is None or previous_fingerprint != progress_fingerprint
            progress_reason_codes = (
                ["initial_baseline"]
                if previous_fingerprint is None
                else ["task_state_fingerprint_changed"]
                if progress_delta
                else ["no_task_state_delta"]
            )
            build_state["last_task_state_fingerprint"] = progress_fingerprint

            watchdog_state["last_cycle"] = int(build_state.get("last_cycle", 0))
            watchdog_state["threshold_cycles"] = NO_PROGRESS_THRESHOLD_CYCLES
            trigger_watchdog_now = False
            if progress_delta:
                watchdog_state["consecutive_no_progress_cycles"] = 0
                watchdog_state["last_progress_at"] = utc_now_iso()
                watchdog_state["triggered"] = False
                watchdog_state["triggered_at"] = None
                watchdog_state["trigger_reason"] = None
            else:
                watchdog_state["consecutive_no_progress_cycles"] = int(watchdog_state.get("consecutive_no_progress_cycles", 0)) + 1
                if int(watchdog_state.get("consecutive_no_progress_cycles", 0)) > 1:
                    warning = {
                        "code": "no_progress_watchdog_warning",
                        "message": (
                            "no meaningful task-state progress detected in build cycle "
                            f"{int(build_state.get('last_cycle', 0))}"
                        ),
                        "stage": "build_loop",
                        "consecutive_no_progress_cycles": int(watchdog_state.get("consecutive_no_progress_cycles", 0)),
                        "threshold_cycles": NO_PROGRESS_THRESHOLD_CYCLES,
                    }
                    warnings.append(warning)
                    cycle_local_warnings.append(warning)
                if int(watchdog_state.get("consecutive_no_progress_cycles", 0)) >= NO_PROGRESS_THRESHOLD_CYCLES and not _as_bool(
                    watchdog_state.get("triggered"),
                    default=False,
                ):
                    trigger_watchdog_now = True
                    watchdog_state["triggered"] = True
                    watchdog_state["triggered_at"] = utc_now_iso()
                    watchdog_state["trigger_reason"] = "task_state_no_progress_25_cycles"

            build_state["no_progress_watchdog"] = {
                "consecutive_no_progress_cycles": int(watchdog_state.get("consecutive_no_progress_cycles", 0)),
                "threshold_cycles": NO_PROGRESS_THRESHOLD_CYCLES,
                "last_progress_at": _as_str(watchdog_state.get("last_progress_at")),
                "triggered": _as_bool(watchdog_state.get("triggered"), default=False),
                "triggered_at": _as_str(watchdog_state.get("triggered_at")),
            }
            try:
                _atomic_write_json(watchdog_state_path, watchdog_state)
            except Exception as exc:  # noqa: BLE001
                warning = {
                    "code": "no_progress_watchdog_state_persist_failed",
                    "message": f"failed persisting no-progress watchdog state: {exc}",
                    "stage": "build_loop",
                }
                warnings.append(warning)
                cycle_local_warnings.append(warning)

            progress_row = {
                "timestamp": utc_now_iso(),
                "build_cycle": int(build_state.get("last_cycle", 0)),
                "active_phase_id": active_phase_id,
                "task_state_fingerprint": progress_fingerprint,
                "open_gap_ids": open_gap_ids,
                "progress_delta": progress_delta,
                "progress_reason_codes": progress_reason_codes,
                "controller_control_number": cycle_control_number,
                "controller_control_run_id": cycle_control_run_id,
                "warnings_codes": [
                    code
                    for code in (_as_str(item.get("code")) for item in cycle_local_warnings if isinstance(item, dict))
                    if code
                ],
            }
            try:
                _append_jsonl(progress_ledger_path, progress_row)
            except OpError as exc:
                warning = {
                    "code": "state_write_error",
                    "message": f"failed appending run progress ledger: {exc.message}",
                    "stage": "build_loop",
                }
                warnings.append(warning)
                cycle_local_warnings.append(warning)

            _emit_build_progress(
                req,
                (
                    f"cycle {build_state['last_cycle']}: "
                    + _summarize_watchdog_findings(
                        progress_delta=progress_delta,
                        progress_reason_codes=progress_reason_codes,
                        watchdog_state=watchdog_state,
                        cycle_warnings=cycle_local_warnings,
                    )
                ),
            )

            if trigger_watchdog_now:
                trigger_warning = {
                    "code": "no_progress_watchdog_triggered",
                    "message": (
                        f"no meaningful task-state progress for {NO_PROGRESS_THRESHOLD_CYCLES} cycles; "
                        "initiating full stop (loop + workers)"
                    ),
                    "stage": "build_loop",
                    "consecutive_no_progress_cycles": int(watchdog_state.get("consecutive_no_progress_cycles", 0)),
                    "threshold_cycles": NO_PROGRESS_THRESHOLD_CYCLES,
                }
                warnings.append(trigger_warning)
                cycle_local_warnings.append(trigger_warning)
                _emit_build_progress(
                    req,
                    (
                        f"cycle {build_state['last_cycle']}: "
                        f"watchdog threshold reached ({int(watchdog_state.get('consecutive_no_progress_cycles', 0))}/"
                        f"{NO_PROGRESS_THRESHOLD_CYCLES}), initiating full stop"
                    ),
                )
                watchdog_stop_request = _normalize_operator_stop_request(
                    {
                        "schema_version": SCHEMA_VERSION,
                        "stop": True,
                        "reason": "no_progress_watchdog",
                        "stop_mode": "graceful_then_force",
                        "term_grace_sec": 10,
                        "kill_grace_sec": 3,
                        "resume_policy": "auto",
                        "requested_at": utc_now_iso(),
                    }
                )
                watchdog_stop_raw = json.dumps(watchdog_stop_request, indent=2, sort_keys=True) + "\n"
                try:
                    _write_watchdog_stop_marker(
                        req.repo_root,
                        reason=_as_str(watchdog_stop_request.get("reason")) or "no_progress_watchdog",
                        requested_at=_as_str(watchdog_stop_request.get("requested_at")) or utc_now_iso(),
                    )
                except Exception as exc:  # noqa: BLE001
                    warning = {
                        "code": "no_progress_watchdog_marker_write_failed",
                        "message": f"unable to persist watchdog stop marker: {exc}",
                        "stage": "build_loop",
                    }
                    warnings.append(warning)
                    cycle_local_warnings.append(warning)
                stop_summary: dict[str, Any] = {}
                try:
                    stop_summary, stop_warnings = _apply_operator_stop(
                        req.repo_root,
                        task_state,
                        build_state,
                        request_override=watchdog_stop_request,
                        raw_text_override=watchdog_stop_raw,
                    )
                    warnings.extend(stop_warnings)
                    cycle_local_warnings.extend(stop_warnings)
                except OpError as exc:
                    warnings.append(
                        {
                            "code": "operator_stop_apply_failed",
                            "message": f"watchdog stop encountered errors: {exc.message}",
                            "stage": "build_loop",
                        }
                    )
                    build_state["terminal_state"] = {
                        "reason": "operator_stop_apply_failed",
                        "timestamp": utc_now_iso(),
                    }
                    _atomic_write_json(task_state_path, {**task_state, "updated_at": utc_now_iso()})
                    _atomic_write_json(build_state_path, build_state)
                    return _response(
                        req,
                        ok=False,
                        status="blocked_terminal",
                        summary="Build halted: no-progress watchdog triggered but worker stop failed.",
                        warnings=warnings,
                        errors=[
                            {
                                "code": "operator_stop_apply_failed",
                                "message": exc.message,
                                "stage": "build_loop",
                            }
                        ],
                        state_ref=str(build_state_path),
                        next_action="Fix operator stop/state artifact write failures and rerun /op-build.",
                        data=_response_data_with_assignment_observations({"terminal_reason": "operator_stop_apply_failed"}),
                    )

                watchdog_event = {
                    "schema_version": SCHEMA_VERSION,
                    "triggered_at": _as_str(watchdog_state.get("triggered_at")) or utc_now_iso(),
                    "consecutive_no_progress_cycles": int(watchdog_state.get("consecutive_no_progress_cycles", 0)),
                    "affected_task_ids": stop_summary.get("affected_task_ids", []),
                    "active_workers": _active_workers_count(req.repo_root),
                    "action_taken": "stop_loop_and_workers",
                    "stop_state_ref": stop_summary.get("stop_state_path"),
                }
                try:
                    _atomic_write_json(watchdog_event_path, watchdog_event)
                except Exception as exc:  # noqa: BLE001
                    warning = {
                        "code": "no_progress_watchdog_event_write_failed",
                        "message": f"unable to persist watchdog event artifact: {exc}",
                        "stage": "build_loop",
                    }
                    warnings.append(warning)
                    cycle_local_warnings.append(warning)
                warnings.append(
                    {
                        "code": "no_progress_watchdog_stopped",
                        "message": "no-progress watchdog applied full stop to build loop and workers",
                        "stage": "build_loop",
                        "event_path": str(watchdog_event_path),
                    }
                )
                build_state["terminal_state"] = {
                    "reason": "no_progress_watchdog",
                    "timestamp": utc_now_iso(),
                }
                build_state["updated_at"] = utc_now_iso()
                _atomic_write_json(task_state_path, {**task_state, "updated_at": utc_now_iso()})
                _atomic_write_json(build_state_path, build_state)
                return _response(
                    req,
                    ok=False,
                    status="blocked_terminal",
                    summary="Build halted by no-progress watchdog after 25 cycles without meaningful task-state progress.",
                    warnings=warnings,
                    errors=[
                        {
                            "code": "no_progress_watchdog_triggered",
                            "message": "no task-state progress reached watchdog threshold",
                            "stage": "build_loop",
                        }
                    ],
                    state_ref=str(build_state_path),
                    next_action=f"Rerun {resume_cmd} after triaging watchdog event evidence.",
                    data=_response_data_with_assignment_observations(
                        {
                            "terminal_reason": "no_progress_watchdog",
                            "cycles_executed": cycles,
                            "watchdog_event_path": str(watchdog_event_path),
                        }
                    ),
                )

            fingerprint_warnings: list[dict[str, Any]] = []
            fingerprint = _detect_blocker_fingerprint(req.repo_root, warnings_sink=fingerprint_warnings)
            warnings.extend(fingerprint_warnings)
            cycle_local_warnings.extend(fingerprint_warnings)
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
            cycle_sleep_seconds = int(req.sleep_minutes * 60)
            more_cycles_pending = req.max_build_cycles is None or cycles < req.max_build_cycles
            status_counts = _task_status_counts(task_state)
            in_progress_count = (
                status_counts.get(TASK_STATUS_DEV_WORKING, 0)
                + status_counts.get(TASK_STATUS_TESTING, 0)
                + status_counts.get(TASK_STATUS_REVIEWING, 0)
            )
            _emit_build_progress(
                req,
                (
                    f"cycle {build_state['last_cycle']} complete: "
                    f"pending={status_counts.get(TASK_STATUS_PENDING, 0)}, "
                    f"in_progress={in_progress_count}, "
                    f"blocked={status_counts.get(TASK_STATUS_BLOCKED, 0)}, "
                    f"reason={dispatch_reason_for_print or 'none'}, "
                    f"sleep={req.sleep_minutes}m"
                ),
            )
            if more_cycles_pending and not req.dry_run and cycle_sleep_seconds > 0:
                _emit_build_progress(req, f"sleeping for {req.sleep_minutes} minute(s)")
                time.sleep(cycle_sleep_seconds)

        return _response(
            req,
            ok=False,
            status="running_needs_resume",
            summary=f"Build loop executed bounded cycles without terminal resolution; resume with {resume_cmd}.",
            warnings=warnings,
            errors=[
                {
                    "code": "max_build_cycles_reached",
                    "message": "bounded build run reached max_build_cycles before terminal condition",
                    "stage": "build_loop",
                }
            ],
            state_ref=str(build_state_path),
            next_action=f"Rerun {resume_cmd} to continue from BUILD_STATE.json.",
            data=_response_data_with_assignment_observations(
                {
                    "cycles_executed": cycles,
                    "current_strategy": build_state.get("current_strategy"),
                    "current_phase_id": build_state.get("current_phase_id"),
                    "open_gap_ids": build_state.get("open_gap_ids", []),
                    "strict_done_checks": build_state.get("strict_done_checks", {}),
                }
            ),
        )
    finally:
        try:
            build_state["loop_lock_id"] = None
            build_state["updated_at"] = utc_now_iso()
            _atomic_write_json(build_state_path, build_state)
            _atomic_write_json(task_state_path, {**task_state, "updated_at": utc_now_iso()})
        finally:
            _release_build_loop_lock(lock_path, lock_id)


def command_health(req: OpRequest) -> dict[str, Any]:
    try:
        warnings, missing, _, plan_packets, task_state, _ = _preflight_build(req)
    except OpError as exc:
        warning = {
            "code": "build_preflight_read_error",
            "message": exc.message,
            "stage": "health",
        }
        checks = [
            {
                "id": "build_preflight_ready",
                "passed": False,
                "blockers": [warning],
            }
        ]
        return _response(
            req,
            ok=False,
            status="blocked",
            summary="OP health checks detected blocking issues.",
            warnings=[warning],
            errors=[{"code": "health_check_failed", "message": "one or more health checks failed", "stage": "health"}],
            artifacts=[
                str(_repo_path(req.repo_root, PLAN_PACKETS_JSON)),
                str(_repo_path(req.repo_root, TASK_EXECUTION_STATE_JSON)),
                str(_repo_path(req.repo_root, BUILD_STATE_JSON)),
            ],
            state_ref=str(_repo_path(req.repo_root, BUILD_STATE_JSON)),
            data={"checks": checks, "open_gap_ids": []},
        )
    checks: list[dict[str, Any]] = []
    preflight_block_codes = {
        "plan_not_ready",
        "task_state_invalid",
        "task_state_plan_mismatch",
        "plan_packets_invalid",
        "state_payload_invalid",
        "profile_selection_missing",
        "profile_selection_invalid",
    }
    preflight_blockers = [item for item in warnings if _as_str(item.get("code")) in preflight_block_codes]
    checks.append(
        {
            "id": "build_preflight_ready",
            "passed": len(missing) == 0 and len(preflight_blockers) == 0,
            "blockers": preflight_blockers,
        }
    )
    checks.append(
        {
            "id": "baseline_artifacts",
            "passed": len(missing) == 0,
            "missing": missing,
        }
    )

    build_state_path = _repo_path(req.repo_root, BUILD_STATE_JSON)
    build_state_valid = True
    if build_state_path.exists():
        try:
            payload = _read_json(build_state_path)
        except OpError as exc:
            warnings.append(
                {
                    "code": "build_state_invalid",
                    "message": f"BUILD_STATE.json unreadable: {exc.message}",
                    "stage": "health",
                }
            )
            build_state_valid = False
            payload = None
        build_state_valid = build_state_valid and isinstance(payload, dict)
    checks.append({"id": "build_state_integrity", "passed": build_state_valid})

    validation_errors = _validate_task_execution_state(task_state, plan_packets) if task_state and plan_packets else []
    checks.append({"id": "task_state_integrity", "passed": len(validation_errors) == 0, "errors": validation_errors})

    evidence_errors: list[dict[str, Any]] = []
    for task in task_state.get("tasks", []):
        if not isinstance(task, dict):
            continue
        task_id = _as_str(task.get("task_id")) or "TASK-UNKNOWN"
        phase_id = _as_str(task.get("phase_id")) or "phase-1"
        evidence_path = _task_evidence_path(req.repo_root, task)
        if not evidence_path.exists():
            evidence_errors.append({"task_id": task_id, "error": "missing", "path": str(evidence_path)})
            continue
        try:
            payload = _read_json(evidence_path)
        except OpError as exc:
            evidence_errors.append({"task_id": task_id, "error": exc.message, "path": str(evidence_path)})
            continue
        if not isinstance(payload, dict):
            evidence_errors.append({"task_id": task_id, "error": "not_object", "path": str(evidence_path)})
            continue
        schema_errors = _validate_task_evidence_payload(payload, task_id, phase_id)
        if schema_errors:
            evidence_errors.append({"task_id": task_id, "error": "schema_invalid", "details": schema_errors, "path": str(evidence_path)})
    checks.append({"id": "task_evidence_integrity", "passed": len(evidence_errors) == 0, "errors": evidence_errors})

    gap_schema_errors: list[dict[str, Any]] = []
    for task in task_state.get("tasks", []):
        if not isinstance(task, dict):
            continue
        task_id = _as_str(task.get("task_id")) or "TASK-UNKNOWN"
        gaps = task.get("gaps_that_need_patching")
        if gaps is None:
            continue
        if not isinstance(gaps, list):
            gap_schema_errors.append({"task_id": task_id, "error": "gaps_not_list"})
            continue
        for idx, row in enumerate(gaps):
            if not isinstance(row, dict):
                gap_schema_errors.append({"task_id": task_id, "error": "gap_not_object", "index": idx})
                continue
            if not _as_str(row.get("gap_id")):
                gap_schema_errors.append({"task_id": task_id, "error": "gap_id_missing", "index": idx})
            if not _as_str(row.get("status")):
                gap_schema_errors.append({"task_id": task_id, "error": "status_missing", "index": idx})
    checks.append(
        {
            "id": "gap_artifact_integrity",
            "passed": len(gap_schema_errors) == 0,
            "errors": gap_schema_errors,
        }
    )
    open_gap_ids = _open_task_gap_ids(task_state)
    checks.append(
        {
            "id": "gap_closure_readiness",
            "passed": len(open_gap_ids) == 0,
            "open_gap_ids": open_gap_ids,
        }
    )

    passed = all(bool(item.get("passed")) for item in checks)
    status = "completed" if passed else "blocked"
    summary = "OP health checks passed." if passed else "OP health checks detected blocking issues."
    errors: list[dict[str, Any]] = []
    if not passed:
        if len(gap_schema_errors) > 0:
            errors.append(
                {
                    "code": "gap_artifact_integrity_blocked",
                    "message": "task-embedded gap payloads are malformed; run /op-build to re-normalize then rerun /op-health",
                    "stage": "health",
                }
            )
        errors.append({"code": "health_check_failed", "message": "one or more health checks failed", "stage": "health"})
    return _response(
        req,
        ok=passed,
        status=status,
        summary=summary,
        warnings=warnings,
        errors=errors,
        artifacts=[
            str(_repo_path(req.repo_root, PLAN_PACKETS_JSON)),
            str(_repo_path(req.repo_root, TASK_EXECUTION_STATE_JSON)),
            str(_repo_path(req.repo_root, BUILD_STATE_JSON)),
        ],
        state_ref=str(_repo_path(req.repo_root, BUILD_STATE_JSON)),
        data={
            "checks": checks,
            "open_gap_ids": open_gap_ids,
        },
    )


def command_status(req: OpRequest) -> dict[str, Any]:
    planning_root = _repo_path(req.repo_root, PLANNING_REL)
    warnings: list[dict[str, Any]] = []
    status_degraded = False

    plan_packets_path = _repo_path(req.repo_root, PLAN_PACKETS_JSON)
    if plan_packets_path.exists():
        try:
            plan_packets_raw = _read_json(plan_packets_path)
        except OpError as exc:
            warnings.append(
                {
                    "code": "status_artifact_invalid",
                    "message": f"PLAN_PACKETS.json unreadable: {exc.message}",
                    "stage": "status",
                    "artifact": str(plan_packets_path),
                }
            )
            plan_packets_raw = {}
            status_degraded = True
    else:
        plan_packets_raw = {}
    plan_packets = plan_packets_raw if isinstance(plan_packets_raw, dict) else {}
    if not isinstance(plan_packets_raw, dict):
        warnings.append(
            {
                "code": "status_artifact_invalid",
                "message": "PLAN_PACKETS.json must be a JSON object",
                "stage": "status",
                "artifact": str(plan_packets_path),
            }
        )
        status_degraded = True

    task_state_path = _repo_path(req.repo_root, TASK_EXECUTION_STATE_JSON)
    if task_state_path.exists():
        try:
            task_state_raw = _read_json(task_state_path)
        except OpError as exc:
            warnings.append(
                {
                    "code": "status_artifact_invalid",
                    "message": f"TASK_EXECUTION_STATE.json unreadable: {exc.message}",
                    "stage": "status",
                    "artifact": str(task_state_path),
                }
            )
            task_state_raw = {"tasks": []}
            status_degraded = True
    else:
        task_state_raw = {"tasks": []}
    task_state = task_state_raw if isinstance(task_state_raw, dict) else {"tasks": []}
    if not isinstance(task_state_raw, dict):
        warnings.append(
            {
                "code": "status_artifact_invalid",
                "message": "TASK_EXECUTION_STATE.json must be a JSON object",
                "stage": "status",
                "artifact": str(task_state_path),
            }
        )
        status_degraded = True

    build_state_path = _repo_path(req.repo_root, BUILD_STATE_JSON)
    if build_state_path.exists():
        try:
            build_state = _load_build_state(build_state_path)
        except OpError as exc:
            warnings.append(
                {
                    "code": "status_artifact_invalid",
                    "message": f"BUILD_STATE.json unreadable: {exc.message}",
                    "stage": "status",
                    "artifact": str(build_state_path),
                }
            )
            build_state = _fresh_build_state_payload()
            status_degraded = True
    else:
        build_state = _fresh_build_state_payload()

    gap_schema_errors: list[dict[str, Any]] = []
    for task in task_state.get("tasks", []):
        if not isinstance(task, dict):
            continue
        task_id = _as_str(task.get("task_id")) or "TASK-UNKNOWN"
        gaps = task.get("gaps_that_need_patching")
        if gaps is None:
            continue
        if not isinstance(gaps, list):
            gap_schema_errors.append({"task_id": task_id, "error": "gaps_not_list"})
            continue
        for idx, row in enumerate(gaps):
            if not isinstance(row, dict):
                gap_schema_errors.append({"task_id": task_id, "error": "gap_not_object", "index": idx})
                continue
            if not _as_str(row.get("gap_id")):
                gap_schema_errors.append({"task_id": task_id, "error": "gap_id_missing", "index": idx})
            if not _as_str(row.get("status")):
                gap_schema_errors.append({"task_id": task_id, "error": "status_missing", "index": idx})
    if gap_schema_errors:
        warnings.append(
            {
                "code": "status_artifact_invalid",
                "message": "TASK_EXECUTION_STATE embedded gap rows are malformed",
                "stage": "status",
                "details": gap_schema_errors,
            }
        )
        status_degraded = True

    merged_plan = plan_packets if isinstance(plan_packets, dict) else {"tasks": [], "phases": []}
    active_phase_id, phase_checks = _resolve_active_phase(
        merged_plan if isinstance(merged_plan, dict) else {"tasks": [], "phases": []},
        task_state if isinstance(task_state, dict) else {"tasks": []},
        req.repo_root,
    )
    task_rows = task_state.get("tasks", []) if isinstance(task_state, dict) and isinstance(task_state.get("tasks"), list) else []
    counts_by_status: dict[str, int] = {}
    for task in task_rows:
        if not isinstance(task, dict):
            continue
        status = _as_str(task.get("status")) or "unknown"
        counts_by_status[status] = counts_by_status.get(status, 0) + 1
    open_gap_ids = _open_task_gap_ids(task_state)
    lock_snapshot = _load_build_lock_snapshot(req.repo_root)
    build_active = bool(lock_snapshot.get("exists")) and bool(lock_snapshot.get("pid_alive"))
    next_command = (
        "/op-initialize"
        if not _repo_path(req.repo_root, STATE_JSON).exists()
        else "/op-resume" if _repo_path(req.repo_root, BUILD_STATE_JSON).exists() else "/op-build"
    )
    if status_degraded:
        next_action_text = "Repair malformed planning/build artifacts or rerun /op-initialize, then rerun /op-status."
        data_next_action = next_action_text
    elif build_active:
        next_action_text = "Build is active; wait for cycle progress or inspect with /op-report."
        data_next_action = "wait (build active)"
        warnings.append(
            {
                "code": "status_build_running",
                "message": "build loop lock is active; /op-build is currently running",
                "stage": "status",
            }
        )
    else:
        next_action_text = f"Use {next_command} for the next autonomous step."
        data_next_action = next_command
    if status_degraded:
        warnings.append(
            {
                "code": "status_snapshot_degraded",
                "message": "status snapshot degraded due to malformed critical planning/build artifacts",
                "stage": "status",
            }
        )
    return _response(
        req,
        ok=not status_degraded,
        status="blocked" if status_degraded else "completed",
        summary="OP status snapshot degraded by malformed artifacts." if status_degraded else "OP status snapshot generated.",
        warnings=warnings,
        errors=[]
        if not status_degraded
        else [
            {
                "code": "status_snapshot_degraded",
                "message": "critical planning/build artifacts are malformed; repair required",
                "stage": "status",
            }
        ],
        artifacts=[str(planning_root)],
        next_action=next_action_text,
        state_ref=str(_repo_path(req.repo_root, BUILD_STATE_JSON)),
        data={
            "plan_id": _as_str((plan_packets or {}).get("plan_id")),
            "active_phase_id": active_phase_id,
            "phase_exit_checks": phase_checks,
            "task_counts_by_status": counts_by_status,
            "open_gap_ids": [gap_id for gap_id in open_gap_ids if gap_id],
            "active_workers": _active_workers_count(req.repo_root),
            "current_strategy": _as_str((build_state or {}).get("current_strategy")) or STRATEGY_LADDER[0],
            "gap_retry_attempts": (build_state or {}).get("gap_retry_attempts", {}),
            "gap_retry_exhausted_ids": (build_state or {}).get("gap_retry_exhausted_ids", []),
            "next_action": data_next_action,
            "build": "running" if build_active else "not_running",
            "lock": lock_snapshot,
        },
    )


def command_report(req: OpRequest) -> dict[str, Any]:
    status_out = command_status(req)
    health_out = command_health(req)

    status_data = status_out.get("data") if isinstance(status_out, dict) and isinstance(status_out.get("data"), dict) else {}
    status_ok = bool(status_out.get("ok")) if isinstance(status_out, dict) else False
    health_ok = bool(health_out.get("ok")) if isinstance(health_out, dict) else False

    build_state_path = _repo_path(req.repo_root, BUILD_STATE_JSON)
    build_state: dict[str, Any] = {}
    if build_state_path.exists():
        try:
            payload = _read_json(build_state_path)
            if isinstance(payload, dict):
                build_state = payload
        except OpError:
            build_state = {}

    lock_snapshot = _load_build_lock_snapshot(req.repo_root)
    rate_gate = build_state.get("rate_gate_state") if isinstance(build_state.get("rate_gate_state"), dict) else {}
    sleep_until_iso = _as_str(rate_gate.get("sleep_until"))
    sleep_until_dt = _parse_iso_utc(sleep_until_iso)
    terminal_state = (_as_str(build_state.get("terminal_state")) or "").strip()

    if lock_snapshot.get("exists") and lock_snapshot.get("pid_alive"):
        if sleep_until_dt is not None and sleep_until_dt > datetime.now(timezone.utc):
            run_state = "sleeping"
        else:
            run_state = "running"
    elif terminal_state:
        run_state = "stopped" if terminal_state == "operator_stop" else "terminal"
    elif build_state_path.exists():
        run_state = "needs_resume"
    else:
        run_state = "not_started"

    health_color = "green" if (health_ok and status_ok) else "yellow" if health_ok else "red"
    health_reason: str | None = None
    no_progress_watchdog = build_state.get("no_progress_watchdog") if isinstance(build_state.get("no_progress_watchdog"), dict) else {}
    no_progress_cycles = _coerce_nonneg_int(no_progress_watchdog.get("consecutive_no_progress_cycles"), default=0)
    degrade_threshold = max(1, _coerce_nonneg_int(no_progress_watchdog.get("degrade_threshold_cycles"), default=3))
    resume_fail_counts = build_state.get("resume_fail_counts_by_slot") if isinstance(build_state.get("resume_fail_counts_by_slot"), dict) else {}
    max_resume_failures = 0
    for value in resume_fail_counts.values():
        max_resume_failures = max(max_resume_failures, _coerce_nonneg_int(value, default=0))
    if health_color == "green" and (no_progress_cycles >= degrade_threshold or max_resume_failures >= 2):
        health_color = "yellow"
        if no_progress_cycles >= degrade_threshold:
            health_reason = f"no_progress_watchdog:{no_progress_cycles}/{NO_PROGRESS_THRESHOLD_CYCLES}"
        else:
            health_reason = f"resume_failures:max={max_resume_failures}"

    counts_raw = status_data.get("task_counts_by_status") if isinstance(status_data.get("task_counts_by_status"), dict) else {}
    counts: dict[str, int] = {}
    for key, value in counts_raw.items():
        if not isinstance(key, str):
            continue
        try:
            counts[key] = int(value)
        except (TypeError, ValueError):
            continue
    total_tasks = sum(max(0, val) for val in counts.values())
    done_tasks = max(0, counts.get(TASK_STATUS_REVIEW_DONE, 0))
    in_progress_tasks = (
        max(0, counts.get(TASK_STATUS_DEV_WORKING, 0))
        + max(0, counts.get(TASK_STATUS_TESTING, 0))
        + max(0, counts.get(TASK_STATUS_REVIEWING, 0))
    )

    phase_id = _as_str(status_data.get("active_phase_id")) or _as_str(build_state.get("current_phase_id")) or "n/a"
    try:
        cycle = int(build_state.get("last_cycle", 0))
    except (TypeError, ValueError):
        cycle = 0
    active_workers = status_data.get("active_workers")
    if not isinstance(active_workers, int):
        active_workers = _active_workers_count(req.repo_root)
    if active_workers is None:
        active_workers = 0
    open_gap_ids = status_data.get("open_gap_ids") if isinstance(status_data.get("open_gap_ids"), list) else []
    open_gaps = len([item for item in open_gap_ids if _as_str(item)])
    blockers = _open_blockers_count(req.repo_root)
    strategy = _as_str(status_data.get("current_strategy")) or _as_str(build_state.get("current_strategy")) or STRATEGY_LADDER[0]
    last_update = _age_from_iso(build_state.get("updated_at"))

    if run_state in {"running", "sleeping"}:
        next_action = "wait (build active)"
    elif run_state in {"needs_resume", "stopped"}:
        next_action = "/op-resume"
    elif run_state == "not_started":
        next_action = "/op-build"
    elif terminal_state == "project_done":
        next_action = "completed"
    elif terminal_state == "all_rate_gates_blocking":
        next_action = "wait for rate reset, then /op-resume"
    else:
        next_action = "/op-status"

    warnings: list[dict[str, Any]] = []
    if not status_ok:
        warnings.append(
            {
                "code": "report_status_degraded",
                "message": "status snapshot is degraded; see /op-status for artifact-level details",
                "stage": "report",
            }
        )
    if not health_ok:
        warnings.append(
            {
                "code": "report_health_blocked",
                "message": "health checks are blocked; see /op-health for detailed failing checks",
                "stage": "report",
            }
        )
    if health_reason:
        warnings.append(
            {
                "code": "no_progress_watchdog_degraded",
                "message": f"runtime health degraded: {health_reason}",
                "stage": "report",
            }
        )

    summary = f"build: {run_state} | health: {health_color} | cycle: {cycle}"
    return _response(
        req,
        ok=True,
        status=run_state,
        summary=summary,
        warnings=warnings,
        artifacts=[str(_repo_path(req.repo_root, PLANNING_REL))],
        next_action=next_action,
        state_ref=str(build_state_path),
        data={
            "build": run_state,
            "health": health_color,
            "health_reason": health_reason,
            "cycle": cycle,
            "phase": phase_id,
            "tasks_done": done_tasks,
            "tasks_total": total_tasks,
            "tasks_in_progress": in_progress_tasks,
            "workers_active": active_workers,
            "gaps_open": open_gaps,
            "blockers_open": blockers,
            "strategy": strategy,
            "last_update": last_update,
            "next": next_action,
            "terminal_state": terminal_state or None,
            "lock": lock_snapshot,
        },
    )


def command_resume(req: OpRequest) -> dict[str, Any]:
    build_state_path = _repo_path(req.repo_root, BUILD_STATE_JSON)
    if not build_state_path.exists():
        return _response(
            req,
            ok=False,
            status="blocked_preflight",
            summary="Resume blocked: no existing build state found.",
            errors=[
                {
                    "code": "resume_unavailable",
                    "message": "BUILD_STATE.json is missing; run /op-build first.",
                    "stage": "resume",
                }
            ],
            next_action="Run /op-build to initialize autonomous execution state.",
            state_ref=str(build_state_path),
        )
    recovered_warning: dict[str, Any] | None = None
    recover_state = False
    payload: Any = None
    try:
        payload = _read_json(build_state_path)
    except OpError:
        recover_state = True

    if not recover_state and not isinstance(payload, dict):
        recover_state = True

    last_cycle: int | None = None
    if not recover_state and isinstance(payload, dict):
        last_cycle_raw = payload.get("last_cycle", 0)
        try:
            last_cycle = int(last_cycle_raw)
        except (TypeError, ValueError):
            recover_state = True

    if recover_state:
        try:
            backup_path = _backup_corrupt_file(build_state_path)
        except OpError as exc:
            return _response(
                req,
                ok=False,
                status="blocked_preflight",
                summary="Resume blocked: failed to recover malformed build state.",
                errors=[
                    {
                        "code": "resume_state_recovery_failed",
                        "message": exc.message,
                        "stage": "resume",
                    }
                ],
                next_action="Repair BUILD_STATE.json permissions/path and rerun /op-resume.",
                state_ref=str(build_state_path),
            )
        build_state = _fresh_build_state_payload()
        build_state["state_recovery"] = {
            "last_recovery_at": utc_now_iso(),
            "reason": "malformed_build_state",
            "backup_path": str(backup_path),
        }
        _atomic_write_json(build_state_path, build_state)
        recovered_warning = {
            "code": "resume_state_corrupt_reset",
            "message": f"BUILD_STATE.json was malformed and reset from backup {backup_path.name}",
            "stage": "resume",
            "backup_path": str(backup_path),
        }
    elif last_cycle is not None and last_cycle <= 0:
        return _response(
            req,
            ok=False,
            status="blocked_preflight",
            summary="Resume blocked: existing build state is invalid for resume.",
            errors=[
                {
                    "code": "resume_unavailable",
                    "message": "BUILD_STATE.json has no resumable cycle history.",
                    "stage": "resume",
                }
            ],
            next_action="Run /op-build to start a fresh autonomous run.",
            state_ref=str(build_state_path),
        )

    try:
        reconcile_warnings, reconcile_summary = _reconcile_post_operator_stop(req.repo_root)
    except OpError as exc:
        return _response(
            req,
            ok=False,
            status="blocked_preflight",
            summary="Resume blocked: failed to reconcile operator-stop state.",
            errors=[
                {
                    "code": "resume_stop_reconcile_failed",
                    "message": exc.message,
                    "stage": "resume",
                }
            ],
            next_action="Repair OPERATOR_STOP_STATE/BUILD_STATE/TASK_EXECUTION_STATE artifacts, then rerun /op-resume.",
            state_ref=str(build_state_path),
        )

    out = command_build(req)
    if reconcile_warnings:
        existing = out.get("warnings")
        if not isinstance(existing, list):
            existing = []
        out["warnings"] = [*reconcile_warnings, *existing]
    if reconcile_summary is not None:
        data = out.get("data")
        if not isinstance(data, dict):
            data = {}
        data["resume_reconcile"] = reconcile_summary
        out["data"] = data
    if recovered_warning is not None:
        existing = out.get("warnings")
        if not isinstance(existing, list):
            existing = []
        existing.insert(0, recovered_warning)
        out["warnings"] = existing
    return out


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

    default_sleep = 5 if command in {"op-build", "op-resume"} else 0
    sleep_minutes = payload.get("sleep_minutes", default_sleep)
    try:
        sleep_val = float(sleep_minutes)
    except (TypeError, ValueError) as exc:
        raise OpError("input_error", "sleep_minutes must be numeric", stage="input") from exc

    return OpRequest(
        command=command,
        repo_root=repo_root,
        mission=_as_str(payload.get("mission")),
        mission_file=_as_str(payload.get("mission_file")),
        scope=_as_str(payload.get("scope")),
        scope_file=_as_str(payload.get("scope_file")),
        override_old_plan=_as_bool(payload.get("override_old_plan"), default=False),
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
    if req.command == "op-health":
        return command_health(req)
    if req.command == "op-status":
        return command_status(req)
    if req.command == "op-report":
        return command_report(req)
    if req.command == "op-resume":
        return command_resume(req)
    raise OpError(
        "input_error",
        "unsupported command; expected one of: " + ", ".join(sorted(SUPPORTED_COMMANDS)),
        stage="input",
    )


def run_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    req = parse_request(payload)
    return execute_request(req)
