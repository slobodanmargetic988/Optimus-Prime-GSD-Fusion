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
SCRIPTS_ROOT = SCRIPT_DIR.parent
ENGINE_ROOT = SCRIPT_DIR.parents[1]
for _path in (SCRIPT_DIR, SCRIPTS_ROOT, ENGINE_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from boss_config import (
    DEFAULT_BOSS_MODEL,
    DEFAULT_BOSS_REASONING_EFFORT,
    sanitize_boss_model,
    sanitize_boss_reasoning_effort,
)

SKILLS_ROOT = ENGINE_ROOT / "skills"

from op_router import SUPPORTED_COMMANDS, normalize_command
from langsmith_tracing import emit_op_event_trace
from planner.llm_planner import (
    materialize_bundle,
    render_prompt,
    run_codex_exec,
)
from planner.validate_git_bootstrap import validate_git_bootstrap
from planner.validate_plan_bundle import validate_bundle_contract
import strategy_runner

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
WORKSTATION_REGISTRY_JSON = PLANNING_REL / "WORKSTATION_REGISTRY.json"
GAP_CONSUMPTION_PLAN_JSON = PLANNING_REL / "GAP_CONSUMPTION_PLAN.json"
GAP_CONSUMPTION_LEDGER_JSONL = PLANNING_REL / "GAP_CONSUMPTION_LEDGER.jsonl"

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
APP_LIFECYCLE_JSON = Path("app_lifecycle.json")
RATE_SNAPSHOT_SCRIPT_REL = Path("skills") / "minimal-rate-snapshot" / "scripts" / "minimal_rate_snapshot.py"
PLANNER_PROMPT_TEMPLATE_PATH = SCRIPT_DIR / "planner" / "prompts" / "llm_plan_prompt.md"
PLANNER_VALIDATOR_SCRIPT_PATH = SCRIPT_DIR / "planner" / "validate_plan_bundle.py"
PLANNER_EXAMPLE_ROOT_PATH = SCRIPT_DIR / "llm" / "examples" / "op-plan" / "reports" / "optimus-prime" / "planning"
GIT_BOOTSTRAP_PROMPT_TEMPLATE_PATH = SCRIPT_DIR / "planner" / "prompts" / "git_bootstrap_prompt.md"
GIT_BOOTSTRAP_VALIDATOR_SCRIPT_PATH = SCRIPT_DIR / "planner" / "validate_git_bootstrap.py"
GIT_BOOTSTRAP_ARTIFACT_REL = PLANNER_REL / "git-bootstrap"
GIT_BOOTSTRAP_REQUIRED_BRANCH = "RAB-BASE"
GIT_BOOTSTRAP_PRIMARY_BRANCH = "main"
GITHUB_REMOTE_NAME = "origin"
GITHUB_HOST = "github.com"
GIT_BOOTSTRAP_PUBLISH_ARTIFACT = GIT_BOOTSTRAP_ARTIFACT_REL / "PUBLISH_REPO.json"
DEFAULT_STRATEGY_MANIFEST_REL = strategy_runner.DEFAULT_STRATEGY_MANIFEST_REL
DEFAULT_STRATEGY_PACKET_MD_REL = strategy_runner.DEFAULT_STRATEGY_PACKET_REL
DEFAULT_STRATEGY_SUMMARY_MD_REL = strategy_runner.DEFAULT_STRATEGY_SUMMARY_REL

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
DEAD_PID_REDISPATCH_GRACE_SEC = 600
NO_PROGRESS_THRESHOLD_CYCLES = 25
TASK_FORWARD_PROGRESS_THRESHOLD_CYCLES = 25

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

VERIFICATION_MODES = {
    "tdd_red",
    "implementation_green",
    "hardening",
    "lane_test",
    "lane_review",
    "deep_review",
    "merge_validation",
}
VERIFICATION_EXPECTATIONS = {
    "expect_fail",
    "expect_pass",
}
EVIDENCE_FAILURE_CLASSES = {
    "expected_red",
    "infra",
    "unexpected",
    "none",
}
DEFAULT_EXPECTED_FAILURE_REASON_CODES = [
    "tdd_expected_failure_observed",
]
DEFAULT_INFRA_FAILURE_REASON_CODES = [
    "verification_environment_error",
    "verification_command_target_missing",
]
TASK_KIND_IMPLEMENTATION = "implementation"
TASK_KIND_LANE_TEST = "lane_test"
TASK_KIND_TEST_FIX = "test_fix"
TASK_KIND_LANE_REVIEW = "lane_review"
TASK_KIND_REVIEW_FIX = "review_fix"
TASK_KIND_DEEP_REVIEW = "deep_review"
TASK_KIND_DEEP_FIX = "deep_fix"
TASK_KIND_MERGE = "merge"
TASK_KIND_ALLOWED = {
    TASK_KIND_IMPLEMENTATION,
    TASK_KIND_LANE_TEST,
    TASK_KIND_TEST_FIX,
    TASK_KIND_LANE_REVIEW,
    TASK_KIND_REVIEW_FIX,
    TASK_KIND_DEEP_REVIEW,
    TASK_KIND_DEEP_FIX,
    TASK_KIND_MERGE,
}
HUMAN_BLOCKED_GAP_REASON_TOKENS = (
    "secret",
    "token",
    "oauth",
    "manual",
    "human",
    "credential",
    "api_key",
)

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
    "/.op-simple/",
    "/reports/optimus-prime/**",
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
    "/reports/optimus-prime/planning/WORKSTATION_REGISTRY.json",
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
    max_parallel_workers: int
    sleep_minutes: float
    enable_artifact_fan_in: bool
    worktrees_parent: Path | None
    selected_aliases: list[str] | None
    dry_run: bool
    reset_exhausted_retries: bool
    strategy_manifest: str | None = None
    strategy_manifest_file: str | None = None
    skip_strategy: bool = False
    publish_private_repo: bool = False
    github_owner: str | None = None
    github_repo_name: str | None = None
    start_policy: str | None = None
    run_base_source_branch: str | None = None
    boss_model: str = DEFAULT_BOSS_MODEL
    boss_reasoning_effort: str = DEFAULT_BOSS_REASONING_EFFORT
    profile: str | None = None
    codex_profile: str | None = None
    executor_provider: str = "codex"
    executor_model: str | None = None
    blackbox_lane: str = "free"
    allow_worker_executor_override: bool = False
    cycle_release_mode: str = "token_conservative"
    cycle_release_timeout_seconds: int = 900
    cycle_release_poll_seconds: int = 5


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


def _default_worktrees_parent(repo_root: Path) -> Path:
    return (repo_root.parent / f".{repo_root.name}-workstations").resolve()


def _effective_worktrees_parent(repo_root: Path, configured_parent: Path | None) -> Path:
    if isinstance(configured_parent, Path):
        return configured_parent
    return _default_worktrees_parent(repo_root)


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


def _normalize_task_kind(value: Any) -> str:
    text = (_as_str(value) or TASK_KIND_IMPLEMENTATION).lower()
    return text if text in TASK_KIND_ALLOWED else TASK_KIND_IMPLEMENTATION


def _default_verification_mode_for_task_kind(task_kind: str) -> str:
    if task_kind == TASK_KIND_LANE_TEST:
        return "lane_test"
    if task_kind == TASK_KIND_LANE_REVIEW:
        return "lane_review"
    if task_kind == TASK_KIND_DEEP_REVIEW:
        return "deep_review"
    if task_kind == TASK_KIND_MERGE:
        return "merge_validation"
    return "implementation_green"


def _normalize_verification_mode(value: Any) -> str:
    text = (_as_str(value) or "implementation_green").lower()
    return text if text in VERIFICATION_MODES else "implementation_green"


def _normalize_stage_expectation(value: Any) -> str:
    text = (_as_str(value) or "expect_pass").lower()
    return text if text in VERIFICATION_EXPECTATIONS else "expect_pass"


def _normalize_failure_class(value: Any) -> str:
    text = (_as_str(value) or "none").lower()
    return text if text in EVIDENCE_FAILURE_CLASSES else "unexpected"


def _allowed_verification_modes_for_task_kind(task_kind: str) -> set[str]:
    if task_kind == TASK_KIND_IMPLEMENTATION:
        return {"tdd_red", "implementation_green", "hardening"}
    if task_kind in {TASK_KIND_TEST_FIX, TASK_KIND_REVIEW_FIX, TASK_KIND_DEEP_FIX}:
        return {"implementation_green", "hardening"}
    if task_kind == TASK_KIND_LANE_TEST:
        return {"lane_test"}
    if task_kind == TASK_KIND_LANE_REVIEW:
        return {"lane_review"}
    if task_kind == TASK_KIND_DEEP_REVIEW:
        return {"deep_review"}
    if task_kind == TASK_KIND_MERGE:
        return {"merge_validation"}
    return {"implementation_green"}


def _primary_stage_for_task_kind(task_kind: str) -> str:
    if task_kind == TASK_KIND_LANE_TEST:
        return "test"
    if task_kind in {TASK_KIND_LANE_REVIEW, TASK_KIND_DEEP_REVIEW}:
        return "review"
    return "dev"


def _task_kind(task: dict[str, Any], plan_task: dict[str, Any] | None = None) -> str:
    task_value = task.get("task_kind") if isinstance(task, dict) else None
    plan_value = plan_task.get("task_kind") if isinstance(plan_task, dict) else None
    plan_kind = _normalize_task_kind(plan_value)
    task_kind = _normalize_task_kind(task_value)
    normalized = plan_kind if isinstance(plan_task, dict) and plan_kind in TASK_KIND_ALLOWED else task_kind
    if isinstance(task, dict):
        task["task_kind"] = normalized
    if isinstance(plan_task, dict):
        plan_task["task_kind"] = plan_kind
    return normalized


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = _as_str(item)
        if text:
            out.append(text)
    return out


def _as_alias_list(value: Any) -> list[str] | None:
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
                text = _as_str(item)
                if text:
                    raw_items.extend(text.split(","))
    else:
        text = _as_str(value)
        if text:
            raw_items.extend(text.split(","))

    aliases: list[str] = []
    seen: set[str] = set()
    for raw in raw_items:
        alias = str(raw or "").strip().lower()
        if not alias or alias in seen:
            continue
        seen.add(alias)
        aliases.append(alias)
    return aliases or None


def _default_verification_contract(*, mode: str | None = None, task_kind: str = TASK_KIND_IMPLEMENTATION) -> dict[str, Any]:
    normalized_task_kind = _normalize_task_kind(task_kind)
    normalized_mode = _normalize_verification_mode(mode or _default_verification_mode_for_task_kind(normalized_task_kind))
    if normalized_mode not in _allowed_verification_modes_for_task_kind(normalized_task_kind):
        normalized_mode = _default_verification_mode_for_task_kind(normalized_task_kind)
    return {
        "mode": normalized_mode,
        "expected_failure_reason_codes": list(DEFAULT_EXPECTED_FAILURE_REASON_CODES),
        "infra_failure_reason_codes": list(DEFAULT_INFRA_FAILURE_REASON_CODES),
    }


def _normalize_verification_contract(value: Any, *, task_kind: str = TASK_KIND_IMPLEMENTATION) -> dict[str, Any]:
    row = value if isinstance(value, dict) else {}
    normalized_task_kind = _normalize_task_kind(task_kind)
    contract = _default_verification_contract(
        mode=_as_str(row.get("mode")) or None,
        task_kind=normalized_task_kind,
    )
    expected_failure_reason_codes = _as_str_list(row.get("expected_failure_reason_codes"))
    infra_failure_reason_codes = _as_str_list(row.get("infra_failure_reason_codes"))
    if not expected_failure_reason_codes:
        expected_failure_reason_codes = list(DEFAULT_EXPECTED_FAILURE_REASON_CODES)
    if not infra_failure_reason_codes:
        infra_failure_reason_codes = list(DEFAULT_INFRA_FAILURE_REASON_CODES)
    contract["expected_failure_reason_codes"] = expected_failure_reason_codes
    contract["infra_failure_reason_codes"] = infra_failure_reason_codes
    return contract


def _task_verification_contract(task: dict[str, Any], plan_task: dict[str, Any] | None = None) -> dict[str, Any]:
    task_kind = _task_kind(task, plan_task)
    task_contract = task.get("verification_contract") if isinstance(task.get("verification_contract"), dict) else None
    plan_contract = (
        plan_task.get("verification_contract")
        if isinstance(plan_task, dict) and isinstance(plan_task.get("verification_contract"), dict)
        else None
    )
    normalized = _normalize_verification_contract(task_contract or plan_contract or {}, task_kind=task_kind)
    task["verification_contract"] = normalized
    return normalized


def _current_stage_for_task_status(status: str, owner_slot: str | None = None) -> str:
    if status in {TASK_STATUS_PENDING, TASK_STATUS_DEV_WORKING}:
        return "dev"
    if status in {TASK_STATUS_DEV_DONE, TASK_STATUS_TESTING}:
        return "test"
    if status in {TASK_STATUS_TESTS_DONE, TASK_STATUS_REVIEWING, TASK_STATUS_REVIEW_DONE}:
        return "review"
    if owner_slot:
        if owner_slot.startswith("test-"):
            return "test"
        if owner_slot.startswith("review-"):
            return "review"
    return "dev"


def _expected_for_stage(contract: dict[str, Any], stage: str) -> str:
    del stage
    return "expect_fail" if _normalize_verification_mode(contract.get("mode")) == "tdd_red" else "expect_pass"


def _current_evidence_stage(task: dict[str, Any], plan_task: dict[str, Any] | None = None) -> str:
    gapfix_state = _normalize_gapfix_state(task.get("gapfix_state"))
    if _as_bool_field(gapfix_state.get("active")):
        target = (_as_str(gapfix_state.get("target_gap_stage")) or "").lower()
        if target in {"dev", "test", "review"}:
            return target
    return _primary_stage_for_task_kind(_task_kind(task, plan_task))


def _task_has_open_embedded_gap(
    task: dict[str, Any],
    *,
    include_consumed: bool = True,
) -> bool:
    rows = task.get("gaps_that_need_patching") if isinstance(task.get("gaps_that_need_patching"), list) else []
    for row in rows:
        if not isinstance(row, dict):
            continue
        status = (_as_str(row.get("status")) or "open").lower()
        if status == "consumed" and not include_consumed:
            continue
        if status not in {"closed", "verified", "patched"}:
            return True
    return False


def _evaluate_evidence_expectation(
    *,
    payload: dict[str, Any],
    expected: str,
) -> dict[str, Any]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    summary_result = (_as_str(summary.get("result")) or "").lower()
    summary_expectation = _normalize_stage_expectation(summary.get("expectation"))
    expectation_met = _as_bool_field(summary.get("expectation_met"))
    failure_class = _normalize_failure_class(summary.get("failure_class"))
    if summary_expectation != expected:
        return {
            "progress": False,
            "blocked": True,
            "reason_code": "tdd_expectation_not_met",
            "message": f"summary.expectation mismatch (expected={expected}, actual={summary_expectation})",
            "failure_class": failure_class,
        }
    if expected == "expect_fail":
        if expectation_met and summary_result in {"pass", "fail", "blocked"} and failure_class == "expected_red":
            return {
                "progress": True,
                "blocked": False,
                "reason_code": "tdd_expectation_met",
                "message": "expected failure observed for red-phase task",
                "failure_class": failure_class,
            }
        return {
            "progress": False,
            "blocked": True,
            "reason_code": "tdd_expectation_not_met",
            "message": "expected red-phase failure was not observed",
            "failure_class": failure_class,
        }
    if expectation_met and summary_result == "pass" and failure_class == "none":
        return {
            "progress": True,
            "blocked": False,
            "reason_code": "tdd_expectation_met",
            "message": "expected pass observed for implementation/hardening task",
            "failure_class": failure_class,
        }
    blocked_reason = (
        "infrastructure verification failure"
        if failure_class == "infra"
        else "unexpected verification failure"
        if failure_class == "unexpected"
        else "expected pass was not observed"
    )
    return {
        "progress": False,
        "blocked": True,
        "reason_code": "tdd_expectation_not_met",
        "message": blocked_reason,
        "failure_class": failure_class,
    }


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
    elif command in {"op-simple-build"}:
        label = "op-simple-build"
    else:
        label = "op-runtime"
    stamp = datetime.now().astimezone().strftime("%H:%M:%S")
    print(f"[{label} {stamp}] {message}", flush=True)


def _merge_response_data(*parts: dict[str, Any] | None) -> dict[str, Any] | None:
    merged: dict[str, Any] = {}
    for part in parts:
        if isinstance(part, dict):
            merged.update(part)
    return merged or None


def _build_start_policy_payload(
    *,
    requested_start_policy: str | None,
    resolved_start_mode: str | None,
    reason_code: str,
) -> dict[str, Any]:
    return {
        "requested_start_policy": requested_start_policy or "auto",
        "resolved_start_mode": resolved_start_mode,
        "start_policy_reason_code": reason_code,
    }


def _build_fresh_run_intent_flags(req: OpRequest) -> list[str]:
    flags: list[str] = []
    if req.mission:
        flags.append("--mission")
    if req.mission_file:
        flags.append("--mission-file")
    if req.scope:
        flags.append("--scope")
    if req.scope_file:
        flags.append("--scope-file")
    if req.override_old_plan:
        flags.append("--override-old-plan")
    if req.run_base_source_branch:
        flags.append("--run-base-source-branch")
    return flags


def _resolve_build_start_mode(req: OpRequest) -> tuple[str, str]:
    requested_start_policy = req.start_policy or "auto"
    fresh_run_flags = _build_fresh_run_intent_flags(req)
    if requested_start_policy == "new":
        return "new", "explicit_new_requested"
    if requested_start_policy == "resume":
        from op_simple_build import inspect_resume_run_base_meta

        inspect_resume_run_base_meta(req.repo_root, run_base_source_branch=req.run_base_source_branch)
        return "resume", "explicit_resume_requested"
    if fresh_run_flags:
        return "new", "fresh_run_intent"
    simple_runtime_marker = req.repo_root / ".op-simple" / "current" / "initialize_state.json"
    if not simple_runtime_marker.exists():
        return "new", "no_existing_op_simple_state"
    from op_simple_build import inspect_resume_run_base_meta

    inspect_resume_run_base_meta(req.repo_root, run_base_source_branch=req.run_base_source_branch)
    return "resume", "resume_state_valid"


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


def _canonical_codex_alias(alias: Any, codex_home: Any) -> str:
    alias_text = (_as_str(alias) or "").lower()
    home_name = Path(_as_str(codex_home) or "").name.lower()
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


def _remaining_percent_from_used_percent(value: Any) -> float | None:
    try:
        used = float(value)
    except (TypeError, ValueError):
        return None
    remaining = 100.0 - used
    if remaining < 0.0:
        return 0.0
    if remaining > 100.0:
        return 100.0
    return round(remaining, 3)


def _normalize_rate_snapshot_reset_iso(value: Any) -> str | None:
    if isinstance(value, (int, float)):
        timestamp = float(value)
    else:
        text = _as_str(value) or ""
        if not text:
            return None
        try:
            timestamp = float(text)
        except (TypeError, ValueError):
            dt = _parse_iso_utc(text)
            if dt is None:
                return None
            return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    if timestamp > 10_000_000_000:
        timestamp = timestamp / 1000.0
    try:
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_minimal_rate_snapshot_payload(
    payload: Any,
    *,
    selected_aliases: list[str] | None = None,
) -> dict[str, Any] | None:
    rows: list[dict[str, Any]] = []
    if isinstance(payload, list):
        rows = [row for row in payload if isinstance(row, dict)]
    elif isinstance(payload, dict):
        profiles = payload.get("profiles")
        if isinstance(profiles, dict):
            # Backward-safe fallback when output already matches legacy registry.
            return payload
        if isinstance(profiles, list):
            rows = [row for row in profiles if isinstance(row, dict)]
        else:
            return None
    else:
        return None

    requested_aliases = [(_as_str(alias) or "").lower() for alias in (selected_aliases or []) if _as_str(alias)]
    profiles: dict[str, dict[str, Any]] = {}
    for row in rows:
        codex_home = _as_str(row.get("codex_home")) or _as_str(row.get("home"))
        alias = _canonical_codex_alias(row.get("alias"), codex_home)
        if not alias or not codex_home:
            continue
        if requested_aliases and alias not in requested_aliases:
            continue

        primary = row.get("primary_window") if isinstance(row.get("primary_window"), dict) else {}
        secondary = row.get("secondary_window") if isinstance(row.get("secondary_window"), dict) else {}
        five_remaining = _remaining_percent_from_used_percent(primary.get("used_percent"))
        week_remaining = _remaining_percent_from_used_percent(secondary.get("used_percent"))
        gated_text = (_as_str(row.get("gated")) or "").lower()
        hard_gated = gated_text in {"hard-gated", "not-available"} or bool(row.get("hard_gated"))
        soft_gated = gated_text == "soft-gated" or bool(row.get("soft_concurrency_gated"))
        if not hard_gated and ((five_remaining is not None and five_remaining <= 1.0) or (week_remaining is not None and week_remaining <= 1.0)):
            hard_gated = True
            soft_gated = False
        elif not soft_gated and ((five_remaining is not None and five_remaining <= 5.0) or (week_remaining is not None and week_remaining <= 5.0)):
            soft_gated = True

        five_reset = _normalize_rate_snapshot_reset_iso(primary.get("reset_at"))
        weekly_reset = _normalize_rate_snapshot_reset_iso(secondary.get("reset_at"))
        reset_candidates = [item for item in [five_reset, weekly_reset] if item]
        reset_at: str | None = None
        if reset_candidates:
            parsed = [(item, _parse_iso_utc(item)) for item in reset_candidates]
            parsed = [(item, dt) for item, dt in parsed if dt is not None]
            if parsed:
                parsed.sort(key=lambda item: item[1])
                reset_at = parsed[0][0]
        if hard_gated:
            recommended_action = "wait_until_reset" if reset_at else "wind_down"
        else:
            recommended_action = "continue"

        entry = {
            "alias": alias,
            "codex_home": codex_home,
            "recommended_action": recommended_action,
            "eligible_for_new_work": not hard_gated,
            "hard_gated": hard_gated,
            "soft_concurrency_gated": soft_gated,
            "window_5h_remaining_pct": five_remaining,
            "window_week_remaining_pct": week_remaining,
            "gated": hard_gated,
            "reset_at": reset_at,
            "five_hour": {
                "remaining_percent": five_remaining,
                "used_percent": primary.get("used_percent"),
                "reset_at": five_reset,
                "gated": hard_gated if five_remaining is None else bool(five_remaining <= 1.0),
            },
            "weekly": {
                "remaining_percent": week_remaining,
                "used_percent": secondary.get("used_percent"),
                "reset_at": weekly_reset,
                "gated": hard_gated if week_remaining is None else bool(week_remaining <= 1.0),
            },
        }
        if gated_text == "not-available":
            entry["errors"] = ["not_available"]
        profiles[alias] = entry

    normalized_payload = {
        "generated_at": utc_now_iso(),
        "source": "minimal-rate-snapshot",
        "profiles": profiles,
    }
    return normalized_payload


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
                "message": "minimal-rate-snapshot script not found; PROFILE_RATE_REGISTRY.json was not generated",
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
    except OpError as exc:
        warnings.append(
            {
                "code": exc.code,
                "message": exc.message,
                "stage": stage,
            }
        )
        return warnings

    cmd = [sys.executable, str(script_path), "--json-pretty"]
    code, out, err = _run(cmd, cwd=repo_root)
    if code != 0:
        stderr = (err or "").strip()
        warnings.append(
            {
                "code": "rate_registry_seed_failed",
                "message": (
                    "failed to generate PROFILE_RATE_REGISTRY.json via minimal-rate-snapshot"
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
                "message": f"minimal-rate-snapshot emitted invalid JSON: {exc}",
                "stage": stage,
            }
        )
        return warnings

    selected_aliases = [
        alias
        for alias in (_as_str(item) for item in resolved_selection.get("selected_aliases", []))
        if alias
    ]
    payload = _normalize_minimal_rate_snapshot_payload(payload, selected_aliases=selected_aliases)
    if not isinstance(payload, dict):
        warnings.append(
            {
                "code": "rate_registry_seed_failed",
                "message": "minimal-rate-snapshot output must be a JSON array of profile rows",
                "stage": stage,
            }
        )
        return warnings

    profiles = payload.get("profiles")
    if not isinstance(profiles, dict):
        warnings.append(
            {
                "code": "rate_registry_seed_failed",
                "message": "minimal-rate-snapshot output normalization produced no valid profiles map",
                "stage": stage,
            }
        )
        return warnings

    existing_payload: dict[str, Any] | None = None
    if registry_path.exists():
        try:
            loaded = _read_json(registry_path)
            if isinstance(loaded, dict):
                existing_payload = loaded
        except OpError:
            existing_payload = None
    payload = _merge_preserved_profile_hard_blocks(existing_payload, payload)

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
                "message": "generated PROFILE_RATE_REGISTRY.json via minimal-rate-snapshot",
                "stage": stage,
            }
        )
    return warnings


def _profiles_map_from_rate_registry(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not isinstance(payload, dict):
        return out
    profiles_raw = payload.get("profiles")
    if isinstance(profiles_raw, dict):
        for alias, row in profiles_raw.items():
            if isinstance(row, dict):
                out[str(alias)] = row
    elif isinstance(profiles_raw, list):
        for idx, row in enumerate(profiles_raw):
            if not isinstance(row, dict):
                continue
            alias = _as_str(row.get("alias")) or f"profile-{idx+1}"
            out[alias] = row
    return out


def _enforce_profile_hard_block_payload(payload: dict[str, Any]) -> dict[str, Any]:
    profiles_map = _profiles_map_from_rate_registry(payload)
    if not profiles_map:
        return payload
    eligible: list[str] = []
    gated: list[str] = []
    soft_gated: list[str] = []
    for alias, row in profiles_map.items():
        permanently_blocked = _as_bool_field(row.get("permanently_blocked"))
        if permanently_blocked:
            row["recommended_action"] = "wind_down"
            row["hard_gated"] = True
            row["eligible_for_new_work"] = False
            row["soft_concurrency_gated"] = True
            errors = row.get("errors")
            if not isinstance(errors, list):
                errors = []
                row["errors"] = errors
            normalized_errors = [item for item in (_as_str(v) for v in errors) if item]
            if "permanently_blocked" not in normalized_errors:
                normalized_errors.append("permanently_blocked")
            row["errors"] = normalized_errors
        recommended = (_as_str(row.get("recommended_action")) or "").lower()
        if recommended == "continue" and not permanently_blocked:
            eligible.append(alias)
        else:
            gated.append(alias)
        if permanently_blocked or _as_bool_field(row.get("soft_concurrency_gated")):
            soft_gated.append(alias)
    payload["eligible_profiles"] = sorted(set(eligible))
    payload["gated_profiles"] = sorted(set(gated))
    payload["soft_concurrency_gated_profiles"] = sorted(set(soft_gated))
    return payload


def _merge_preserved_profile_hard_blocks(existing_payload: dict[str, Any] | None, new_payload: dict[str, Any]) -> dict[str, Any]:
    existing_map = _profiles_map_from_rate_registry(existing_payload)
    new_map = _profiles_map_from_rate_registry(new_payload)
    for alias, existing_row in existing_map.items():
        if not _as_bool_field(existing_row.get("permanently_blocked")):
            continue
        target = new_map.get(alias)
        if target is None:
            target = {"alias": alias}
            new_map[alias] = target
            profiles = new_payload.get("profiles")
            if isinstance(profiles, dict):
                profiles[alias] = target
        target["permanently_blocked"] = True
        reason = _as_str(existing_row.get("permanent_block_reason"))
        blocked_at = _as_str(existing_row.get("permanent_blocked_at"))
        if reason:
            target["permanent_block_reason"] = reason
        if blocked_at:
            target["permanent_blocked_at"] = blocked_at
    return _enforce_profile_hard_block_payload(new_payload)


def _set_profile_permanent_block(
    repo_root: Path,
    *,
    alias: str,
    reason_code: str,
    stage: str = "build_loop",
) -> dict[str, Any] | None:
    alias_text = _as_str(alias)
    reason_text = _as_str(reason_code)
    if not alias_text or not reason_text:
        return None
    registry_path = _repo_path(repo_root, PROFILE_RATE_REGISTRY_JSON)
    payload: dict[str, Any]
    if registry_path.exists():
        try:
            loaded = _read_json(registry_path)
            payload = loaded if isinstance(loaded, dict) else {}
        except OpError:
            payload = {}
    else:
        payload = {}
    profiles_raw = payload.get("profiles")
    if not isinstance(profiles_raw, dict):
        profiles_raw = {}
        payload["profiles"] = profiles_raw
    row = profiles_raw.get(alias_text)
    if not isinstance(row, dict):
        row = {"alias": alias_text}
        profiles_raw[alias_text] = row
    already_blocked = _as_bool_field(row.get("permanently_blocked"))
    row["permanently_blocked"] = True
    row["permanent_block_reason"] = reason_text
    if not _as_str(row.get("permanent_blocked_at")):
        row["permanent_blocked_at"] = utc_now_iso()
    errors = row.get("errors")
    normalized_errors = [item for item in (_as_str(v) for v in (errors if isinstance(errors, list) else [])) if item]
    for marker in ("auth_invalid_or_expired", reason_text):
        if marker not in normalized_errors:
            normalized_errors.append(marker)
    row["errors"] = normalized_errors
    row["recommended_action"] = "wind_down"
    row["hard_gated"] = True
    row["soft_concurrency_gated"] = True
    row["eligible_for_new_work"] = False
    payload = _enforce_profile_hard_block_payload(payload)
    try:
        _atomic_write_json(registry_path, payload)
    except OSError as exc:
        return {
            "code": "profile_permanent_block_write_failed",
            "message": f"unable to persist permanently_blocked for alias {alias_text}: {exc}",
            "stage": stage,
            "alias": alias_text,
        }
    if already_blocked:
        return None
    return {
        "code": "profile_permanently_blocked",
        "message": (
            f"profile alias {alias_text} marked permanently_blocked due to dispatch auth failure ({reason_text})"
        ),
        "stage": stage,
        "alias": alias_text,
        "reason_code": reason_text,
    }


def _payload_contains_text(value: Any, needle: str) -> bool:
    text = _as_str(needle).lower()
    if not text:
        return False
    if isinstance(value, str):
        return text in value.lower()
    if isinstance(value, dict):
        return any(_payload_contains_text(v, text) for v in value.values())
    if isinstance(value, list):
        return any(_payload_contains_text(v, text) for v in value)
    return False


def _is_refresh_token_reused_unauthorized(value: Any) -> bool:
    if not _payload_contains_text(value, "refresh_token_reused"):
        return False
    return _payload_contains_text(value, "401") or _payload_contains_text(value, "unauthorized")


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


def _task_forward_progress_rank(status: str) -> int:
    normalized = _normalize_task_status(status)
    return {
        TASK_STATUS_PENDING: 0,
        TASK_STATUS_DEV_WORKING: 1,
        TASK_STATUS_DEV_DONE: 2,
        TASK_STATUS_TESTING: 3,
        TASK_STATUS_TESTS_DONE: 4,
        TASK_STATUS_REVIEWING: 5,
        TASK_STATUS_REVIEW_DONE: 6,
        TASK_STATUS_BLOCKED: 0,
    }.get(normalized, 0)


def _apply_task_progress_watchdog(
    task_state: dict[str, Any],
    build_state: dict[str, Any],
    *,
    plan_id: str,
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    cycle = _coerce_nonneg_int(build_state.get("last_cycle"), default=0)
    now = utc_now_iso()
    for task in task_state.get("tasks", []):
        if not isinstance(task, dict):
            continue
        task_id = _as_str(task.get("task_id"))
        if not task_id:
            continue
        watchdog = _normalize_progress_watchdog(task.get("progress_watchdog"))
        threshold = max(
            1,
            _coerce_nonneg_int(
                watchdog.get("threshold_cycles"),
                default=TASK_FORWARD_PROGRESS_THRESHOLD_CYCLES,
            ),
        )
        if not _as_bool_field(watchdog.get("started")):
            watchdog["threshold_cycles"] = threshold
            task["progress_watchdog"] = watchdog
            continue
        if watchdog["task_started_cycle"] <= 0:
            watchdog["task_started_cycle"] = watchdog["first_dispatched_cycle"] or cycle
        status = _normalize_task_status(task.get("status"))
        rank = _task_forward_progress_rank(status)
        rows = _normalize_task_gap_rows(task)
        closed_gap_count = sum(
            1
            for row in rows
            if isinstance(row, dict) and (_as_str(row.get("status")) or "").lower() in {"closed", "verified", "patched"}
        )
        forward_progress = rank > _coerce_nonneg_int(watchdog.get("_last_rank"), default=0) or closed_gap_count > _coerce_nonneg_int(
            watchdog.get("_last_closed_gap_count"),
            default=0,
        )
        if forward_progress:
            watchdog["consecutive_no_forward_progress_cycles"] = 0
            watchdog["last_forward_progress_cycle"] = cycle
            watchdog["triggered"] = False
            watchdog["triggered_at"] = None
        elif status != TASK_STATUS_REVIEW_DONE:
            watchdog["consecutive_no_forward_progress_cycles"] = _coerce_nonneg_int(
                watchdog.get("consecutive_no_forward_progress_cycles"),
                default=0,
            ) + 1
        if (
            not _as_bool_field(watchdog.get("triggered"))
            and status != TASK_STATUS_REVIEW_DONE
            and _coerce_nonneg_int(watchdog.get("consecutive_no_forward_progress_cycles"), default=0) >= threshold
        ):
            watchdog["triggered"] = True
            watchdog["triggered_at"] = now
            task["status"] = TASK_STATUS_BLOCKED
            task["owner_slot"] = None
            task["blocking_source"] = "evidence"
            _upsert_task_gap(
                task,
                {
                    "gap_id": _gap_id(
                        plan_id,
                        _as_str(task.get("phase_id")) or "phase-1",
                        task_id,
                        "task:progress_stalled",
                        "blocked",
                    ),
                    "category": "task_blocked",
                    "severity": "P1",
                    "stage": "dev",
                    "status": "open",
                    "reason_codes": ["task_progress_stalled"],
                    "retry_count": 0,
                    "max_retries": 5,
                    "created_at": now,
                    "updated_at": now,
                    "closure_ref": _as_str((task.get("evidence") or {}).get("task_evidence_ref")),
                },
            )
            warnings.append(
                {
                    "code": "task_progress_stalled",
                    "message": (
                        f"task {task_id} hit per-task no-forward-progress threshold "
                        f"({_coerce_nonneg_int(watchdog.get('consecutive_no_forward_progress_cycles'), default=0)}/{threshold})"
                    ),
                    "stage": "build_loop",
                    "task_id": task_id,
                }
            )
        watchdog["threshold_cycles"] = threshold
        watchdog["_last_rank"] = rank
        watchdog["_last_closed_gap_count"] = closed_gap_count
        task["progress_watchdog"] = watchdog
    return warnings


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


def _fresh_workstation_registry_payload() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "updated_at": utc_now_iso(),
        "slots": {},
    }


def _normalize_workstation_registry_row(slot: str, row: dict[str, Any] | None) -> dict[str, Any]:
    now = utc_now_iso()
    data = dict(row) if isinstance(row, dict) else {}
    data["slot"] = slot
    data["status"] = (_as_str(data.get("status")) or "idle").lower()
    data["request_id"] = _as_str(data.get("request_id")) or None
    data["pid"] = int(data.get("pid")) if isinstance(data.get("pid"), int) else None
    data["attempt"] = _coerce_nonneg_int(data.get("attempt"), default=0)
    data["retry_count"] = _coerce_nonneg_int(data.get("retry_count"), default=0)
    data["requested_cycle"] = (
        _coerce_nonneg_int(data.get("requested_cycle"), default=0) if data.get("requested_cycle") is not None else None
    )
    data["started_at"] = _as_str(data.get("started_at")) or None
    data["completed_at"] = _as_str(data.get("completed_at")) or None
    data["last_update_at"] = _as_str(data.get("last_update_at")) or now
    data["target_task_id"] = _as_str(data.get("target_task_id")) or None
    data["target_lane_id"] = _as_str(data.get("target_lane_id")) or None
    data["target_stage"] = _as_str(data.get("target_stage")) or None
    data["target_branch"] = _as_str(data.get("target_branch")) or None
    data["target_base_ref"] = _as_str(data.get("target_base_ref")) or None
    data["target_worktree_name"] = _as_str(data.get("target_worktree_name")) or None
    data["target_worktree_root"] = _as_str(data.get("target_worktree_root")) or None
    data["attempt_dir"] = _as_str(data.get("attempt_dir")) or None
    data["action_path"] = _as_str(data.get("action_path")) or None
    data["validation_path"] = _as_str(data.get("validation_path")) or None
    data["stdout_path"] = _as_str(data.get("stdout_path")) or None
    data["stderr_path"] = _as_str(data.get("stderr_path")) or None
    data["last_message_path"] = _as_str(data.get("last_message_path")) or None
    data["llm_exit_code"] = int(data.get("llm_exit_code")) if isinstance(data.get("llm_exit_code"), int) else None
    last_error = data.get("last_error")
    data["last_error"] = dict(last_error) if isinstance(last_error, dict) else None
    return data


def _load_workstation_registry(path: Path) -> dict[str, Any]:
    payload = _fresh_workstation_registry_payload()
    if path.exists():
        try:
            parsed = _read_json(path)
        except OpError:
            parsed = None
        if isinstance(parsed, dict):
            payload.update(parsed)
    slots_raw = payload.get("slots")
    if not isinstance(slots_raw, dict):
        slots_raw = {}
    slots: dict[str, dict[str, Any]] = {}
    for slot in FIXED_WORKER_SLOTS:
        if not (slot.startswith("dev-") or slot.startswith("test-") or slot.startswith("review-")):
            continue
        slots[slot] = _normalize_workstation_registry_row(slot, slots_raw.get(slot) if isinstance(slots_raw.get(slot), dict) else None)
    payload["slots"] = slots
    payload["updated_at"] = utc_now_iso()
    return payload


def _write_workstation_registry(path: Path, payload: dict[str, Any]) -> None:
    out = dict(payload) if isinstance(payload, dict) else _fresh_workstation_registry_payload()
    slots_raw = out.get("slots")
    normalized_slots: dict[str, dict[str, Any]] = {}
    if isinstance(slots_raw, dict):
        for slot, row in slots_raw.items():
            slot_name = _as_str(slot)
            if not slot_name:
                continue
            normalized_slots[slot_name] = _normalize_workstation_registry_row(
                slot_name,
                row if isinstance(row, dict) else None,
            )
    out["schema_version"] = SCHEMA_VERSION
    out["updated_at"] = utc_now_iso()
    out["slots"] = normalized_slots
    _atomic_write_json(path, out)


def _start_codex_exec_background(
    *,
    repo_root: Path,
    prompt_text: str,
    output_last_message: Path,
    stdout_path: Path,
    stderr_path: Path,
) -> tuple[int | None, str | None]:
    output_last_message.parent.mkdir(parents=True, exist_ok=True)
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "codex",
        "exec",
        "--dangerously-bypass-approvals-and-sandbox",
        "-c",
        'model_reasoning_effort="xhigh"',
        "--cd",
        str(repo_root),
        "--output-last-message",
        str(output_last_message),
        "-",
    ]
    stdout_handle = stdout_path.open("w", encoding="utf-8")
    stderr_handle = stderr_path.open("w", encoding="utf-8")
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(repo_root),
            stdin=subprocess.PIPE,
            stdout=stdout_handle,
            stderr=stderr_handle,
            text=True,
            bufsize=1,
        )
        if proc.stdin is not None:
            proc.stdin.write(prompt_text)
            proc.stdin.close()
    except OSError as exc:
        return None, str(exc)
    finally:
        stdout_handle.close()
        stderr_handle.close()
    return int(proc.pid), None


def _poll_background_process(pid: int | None) -> tuple[bool, int | None]:
    if not isinstance(pid, int) or pid <= 0:
        return True, None
    try:
        done_pid, status = os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        if _pid_is_running(pid):
            return False, None
        return True, None
    if done_pid == 0:
        return False, None
    if os.WIFEXITED(status):
        return True, int(os.WEXITSTATUS(status))
    if os.WIFSIGNALED(status):
        return True, 128 + int(os.WTERMSIG(status))
    return True, None


def _terminate_pid(pid: int | None, *, term_grace_sec: int = 2, kill_grace_sec: int = 1) -> None:
    if not isinstance(pid, int) or pid <= 0:
        return
    if not _pid_is_running(pid):
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return
    if _wait_pid_exit(pid, term_grace_sec):
        return
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        return
    _wait_pid_exit(pid, kill_grace_sec)


def _default_worker_row(slot: str, *, run_id: str | None = None) -> dict[str, Any]:
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
    default_branch = _default_slot_branch(slot, role=role, run_id=run_id)
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
        "current_task_provider": None,
        "next_task_provider": None,
        "current_task_model": None,
        "next_task_model": None,
        "worktree_root": None,
        "updated_at": now,
    }
    if manager_type is not None:
        row["manager_type"] = manager_type
        row["active_job_id"] = None
    return row


def _run_id_from_lock_id(lock_id: str | None) -> str:
    text = (_as_str(lock_id) or "").strip()
    if not text:
        return ""
    text = text.lower()
    if text.startswith("op-build-"):
        text = text[len("op-build-") :]
    return re.sub(r"[^a-z0-9._-]+", "-", text).strip("-")


def _slot_suffix_for_lane(lane_id: str | None) -> str:
    lane_tail = (_as_str(lane_id) or "").rsplit("/", 1)[-1].lower()
    if lane_tail == "lane-b":
        return "2"
    if lane_tail == "lane-c":
        return "3"
    return "1"


def _slot_for_stage_and_lane(stage: str, lane_id: str | None) -> str:
    suffix = _slot_suffix_for_lane(lane_id)
    if stage == "dev":
        return f"dev-{suffix}"
    if stage == "test":
        return f"test-{suffix}"
    return f"review-{suffix}"


def _default_slot_branch(slot: str, *, role: str | None = None, run_id: str | None = None) -> str:
    resolved_role = role or ("developer" if slot.startswith("dev-") else "tester" if slot.startswith("test-") else "reviewer" if slot.startswith("review-") else "manager")
    if resolved_role in {"developer", "tester", "reviewer"}:
        rid = _run_id_from_lock_id(run_id)
        if rid:
            return f"codex/{rid}/{slot}/bootstrap"
        return f"codex/{slot}/bootstrap"
    return "RAB-BASE"


def _branch_name_for_stage(slot: str, task_id: str, stage: str, *, run_id: str | None = None) -> str:
    rid = _run_id_from_lock_id(run_id)
    if rid:
        base = f"codex/{rid}/{slot}/{task_id.lower()}"
    else:
        base = f"codex/{slot}/{task_id.lower()}"
    if stage == "test":
        return f"{base}-test"
    if stage == "review":
        return f"{base}-review"
    return base


def _developer_source_branch(task: dict[str, Any]) -> str | None:
    branch = _as_str(task.get("developer_branch"))
    if branch:
        return branch
    active_branch = _as_str(task.get("active_branch"))
    if active_branch and re.match(r"^codex/(?:[^/]+/)?dev-[^/]+/", active_branch):
        return active_branch
    return None


def _expected_slot_worktree_name(slot: str) -> str | None:
    if slot.startswith("dev-") or slot.startswith("test-") or slot.startswith("review-"):
        return f"workstation-{slot}"
    return None


def _expected_slot_worktree_path(
    repo_root: Path,
    slot: str,
    worktrees_parent: Path | None = None,
) -> Path | None:
    worktree_name = _expected_slot_worktree_name(slot)
    if not worktree_name:
        return None
    parent = _effective_worktrees_parent(repo_root, worktrees_parent)
    return (parent / worktree_name).resolve()


def _ensure_worktree_artifact_root_symlink(repo_root: Path, worktree_root: Path) -> dict[str, Any]:
    """Ensure <worktree>/reports/optimus-prime is a symlink to repo reports/optimus-prime."""
    canonical_target = (repo_root / "reports" / "optimus-prime").resolve()
    link_path = worktree_root / "reports" / "optimus-prime"
    link_parent = link_path.parent
    try:
        canonical_target.mkdir(parents=True, exist_ok=True)
        if link_parent.exists():
            if not link_parent.is_dir():
                if link_parent.is_symlink() or link_parent.is_file():
                    link_parent.unlink()
                else:
                    shutil.rmtree(link_parent)
                link_parent.mkdir(parents=True, exist_ok=True)
        else:
            link_parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return {
            "ok": False,
            "code": "workstation_artifact_symlink_failed",
            "message": f"unable to prepare reports path in worktree {worktree_root}: {exc}",
            "replaced": False,
            "created": False,
        }

    replaced = False
    created = False
    try:
        if link_path.exists() or link_path.is_symlink():
            if link_path.is_symlink():
                try:
                    current_target = link_path.resolve()
                except OSError:
                    current_target = None
                if current_target == canonical_target:
                    return {
                        "ok": True,
                        "code": "workstation_artifact_symlink_enforced",
                        "message": "artifact-root symlink already enforced",
                        "replaced": False,
                        "created": False,
                        "target": str(canonical_target),
                        "link_path": str(link_path),
                    }
                link_path.unlink()
                replaced = True
            elif link_path.is_dir():
                shutil.rmtree(link_path)
                replaced = True
            else:
                link_path.unlink()
                replaced = True
        link_path.symlink_to(canonical_target)
        created = True
    except OSError as exc:
        return {
            "ok": False,
            "code": "workstation_artifact_symlink_failed",
            "message": f"unable to enforce artifact-root symlink for {worktree_root}: {exc}",
            "replaced": replaced,
            "created": created,
        }

    return {
        "ok": True,
        "code": "workstation_artifact_symlink_replaced" if replaced else "workstation_artifact_symlink_enforced",
        "message": (
            "replaced existing worktree artifact root with canonical symlink"
            if replaced
            else "artifact-root symlink enforced"
        ),
        "replaced": replaced,
        "created": created,
        "target": str(canonical_target),
        "link_path": str(link_path),
    }


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
    run_id = _run_id_from_lock_id(_as_str(build_state.get("loop_lock_id")))
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
        row.setdefault("current_task_provider", None)
        row.setdefault("next_task_provider", None)
        row.setdefault("current_task_model", None)
        row.setdefault("next_task_model", None)
        row.setdefault("worktree_root", None)
        row.setdefault("session_state", _worker_state(row) or "not_running")
        if row.get("active_task") is not None and row.get("active_task_id") is None:
            row["active_task_id"] = _as_str(row.get("active_task"))
        row_role = _as_str(row.get("role")) or ("developer" if slot.startswith("dev-") else "tester" if slot.startswith("test-") else "reviewer" if slot.startswith("review-") else "manager")
        default_branch = _default_slot_branch(slot, role=row_role, run_id=run_id)
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
            row = _default_worker_row(slot, run_id=run_id)
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


def _default_task_evidence(
    plan_id: str,
    phase_id: str,
    task_id: str,
    requirement_ids: list[str],
    *,
    task_kind: str = TASK_KIND_IMPLEMENTATION,
    summary_expectation: str = "expect_pass",
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "plan_id": plan_id,
        "phase_id": phase_id,
        "task_id": task_id,
        "task_kind": _normalize_task_kind(task_kind),
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
        "summary": {
            "result": "blocked",
            "expectation": _normalize_stage_expectation(summary_expectation),
            "expectation_met": False,
            "failure_class": "none",
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
        task_kind = _normalize_task_kind(task.get("task_kind"))
        contract = _normalize_verification_contract(task.get("verification_contract"), task_kind=task_kind)
        payload = _default_task_evidence(
            plan_id,
            phase_id,
            task_id,
            req_ids,
            task_kind=task_kind,
            summary_expectation=_expected_for_stage(contract, "dev"),
        )
        _atomic_write_json(abs_path, payload)
        refs[task_id] = str(rel)
    return refs


def _normalize_gapfix_state(value: Any) -> dict[str, Any]:
    row = value if isinstance(value, dict) else {}
    consumed_ids_raw = row.get("consumed_gap_ids")
    consumed_gap_ids = (
        [gap_id for gap_id in (_as_str(item) for item in consumed_ids_raw) if gap_id]
        if isinstance(consumed_ids_raw, list)
        else []
    )
    return {
        "active_batch_id": _as_str(row.get("active_batch_id")),
        "active": _as_bool_field(row.get("active")),
        "target_gap_stage": (_as_str(row.get("target_gap_stage")) or "dev").lower(),
        "consumed_gap_ids": consumed_gap_ids,
        "batch_started_cycle": _coerce_nonneg_int(row.get("batch_started_cycle"), default=0),
        "batch_last_updated_at": _as_str(row.get("batch_last_updated_at")),
    }


def _clear_active_gapfix_state(task: dict[str, Any], *, timestamp: str | None = None) -> bool:
    gapfix_state = _normalize_gapfix_state(task.get("gapfix_state"))
    if not _as_bool_field(gapfix_state.get("active")):
        task["gapfix_state"] = gapfix_state
        return False
    gapfix_state["active"] = False
    gapfix_state["active_batch_id"] = None
    gapfix_state["batch_last_updated_at"] = _as_str(timestamp) or utc_now_iso()
    task["gapfix_state"] = gapfix_state
    return True


def _normalize_progress_watchdog(value: Any) -> dict[str, Any]:
    row = value if isinstance(value, dict) else {}
    return {
        "started": _as_bool_field(row.get("started")),
        "first_dispatched_cycle": _coerce_nonneg_int(row.get("first_dispatched_cycle"), default=0),
        "task_started_cycle": _coerce_nonneg_int(row.get("task_started_cycle"), default=0),
        "last_forward_progress_cycle": _coerce_nonneg_int(row.get("last_forward_progress_cycle"), default=0),
        "consecutive_no_forward_progress_cycles": _coerce_nonneg_int(
            row.get("consecutive_no_forward_progress_cycles"),
            default=0,
        ),
        "threshold_cycles": max(
            1,
            _coerce_nonneg_int(
                row.get("threshold_cycles"),
                default=TASK_FORWARD_PROGRESS_THRESHOLD_CYCLES,
            ),
        ),
        "triggered": _as_bool_field(row.get("triggered")),
        "triggered_at": _as_str(row.get("triggered_at")),
        "_last_rank": _coerce_nonneg_int(row.get("_last_rank"), default=0),
        "_last_closed_gap_count": _coerce_nonneg_int(row.get("_last_closed_gap_count"), default=0),
    }


def _mark_task_watchdog_started(task: dict[str, Any], build_state: dict[str, Any]) -> None:
    if not isinstance(task, dict):
        return
    watchdog = _normalize_progress_watchdog(task.get("progress_watchdog"))
    cycle = _coerce_nonneg_int(build_state.get("last_cycle"), default=0)
    if not _as_bool_field(watchdog.get("started")):
        watchdog["started"] = True
        if cycle > 0:
            if watchdog["first_dispatched_cycle"] <= 0:
                watchdog["first_dispatched_cycle"] = cycle
            if watchdog["task_started_cycle"] <= 0:
                watchdog["task_started_cycle"] = cycle
        watchdog["consecutive_no_forward_progress_cycles"] = 0
        watchdog["triggered"] = False
        watchdog["triggered_at"] = None
    else:
        if cycle > 0:
            if watchdog["first_dispatched_cycle"] <= 0:
                watchdog["first_dispatched_cycle"] = cycle
            if watchdog["task_started_cycle"] <= 0:
                watchdog["task_started_cycle"] = cycle
    task["progress_watchdog"] = watchdog


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
                "task_kind": _normalize_task_kind(task.get("task_kind")),
                "requirement_ids": req_ids,
                "verification_contract": _normalize_verification_contract(
                    task.get("verification_contract"),
                    task_kind=_normalize_task_kind(task.get("task_kind")),
                ),
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
                "last_handoff_outcome": {"status": None, "reason_codes": [], "timestamp": None},
                "blocking_source": "none",
                "gapfix_state": _normalize_gapfix_state({}),
                "progress_watchdog": _normalize_progress_watchdog({}),
                "last_dispatch": None,
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
    plan_task_map = _plan_task_map(plan_packets)
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
        plan_task = plan_task_map.get(task_id) if isinstance(plan_task_map.get(task_id), dict) else None
        task_kind = _task_kind(item, plan_task)
        item["task_kind"] = task_kind
        verification_contract = item.get("verification_contract")
        if not isinstance(verification_contract, dict):
            errors.append({"code": "task_state_invalid", "message": f"task {task_id} verification_contract must be object"})
        else:
            item["verification_contract"] = _normalize_verification_contract(verification_contract, task_kind=task_kind)
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
        else:
            item["gaps_that_need_patching"] = _normalize_task_gap_rows(item)
        blockers = item.get("blockers")
        if not isinstance(blockers, list):
            errors.append({"code": "task_state_invalid", "message": f"task {task_id} blockers must be list"})
        handoff_outcome = item.get("last_handoff_outcome")
        if not isinstance(handoff_outcome, dict):
            errors.append({"code": "task_state_invalid", "message": f"task {task_id} last_handoff_outcome must be object"})
        else:
            status_text = handoff_outcome.get("status")
            if status_text is not None and not _as_str(status_text):
                errors.append(
                    {
                        "code": "task_state_invalid",
                        "message": f"task {task_id} last_handoff_outcome.status must be string|null",
                    }
                )
            reason_codes = handoff_outcome.get("reason_codes")
            if not isinstance(reason_codes, list):
                errors.append(
                    {
                        "code": "task_state_invalid",
                        "message": f"task {task_id} last_handoff_outcome.reason_codes must be list",
                    }
                )
            timestamp = handoff_outcome.get("timestamp")
            if timestamp is not None and not _parse_iso_utc(timestamp):
                errors.append(
                    {
                        "code": "task_state_invalid",
                        "message": f"task {task_id} last_handoff_outcome.timestamp must be ISO-8601|null",
                    }
                )
        blocking_source = (_as_str(item.get("blocking_source")) or "").lower()
        if blocking_source not in {"handoff", "evidence", "merge", "none"}:
            errors.append(
                {
                    "code": "task_state_invalid",
                    "message": f"task {task_id} blocking_source must be handoff|evidence|merge|none",
                }
            )
        gapfix_state = item.get("gapfix_state")
        if not isinstance(gapfix_state, dict):
            errors.append({"code": "task_state_invalid", "message": f"task {task_id} gapfix_state must be object"})
            item["gapfix_state"] = _normalize_gapfix_state({})
        else:
            item["gapfix_state"] = _normalize_gapfix_state(gapfix_state)
        last_dispatch = item.get("last_dispatch")
        if last_dispatch is not None and not isinstance(last_dispatch, dict):
            errors.append({"code": "task_state_invalid", "message": f"task {task_id} last_dispatch must be object|null"})
        elif isinstance(last_dispatch, dict):
            for key in (
                "stage",
                "role",
                "branch_name",
                "start_from_commit",
                "start_from_branch",
                "dispatched_at",
            ):
                value = last_dispatch.get(key)
                if value is not None and not isinstance(value, str):
                    errors.append(
                        {"code": "task_state_invalid", "message": f"task {task_id} last_dispatch.{key} must be string|null"}
                    )
        progress_watchdog = item.get("progress_watchdog")
        if not isinstance(progress_watchdog, dict):
            errors.append({"code": "task_state_invalid", "message": f"task {task_id} progress_watchdog must be object"})
            item["progress_watchdog"] = _normalize_progress_watchdog({})
        else:
            item["progress_watchdog"] = _normalize_progress_watchdog(progress_watchdog)
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


def _repo_guard_scan(repo_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    script = (Path(__file__).resolve().parent / "repo_guard_scanner.py").resolve()
    return _run_tool_json(script, payload, repo_root)


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
    if _normalize_task_kind(payload.get("task_kind")) not in TASK_KIND_ALLOWED:
        errors.append("task_kind invalid")
    for section in ("dev", "test", "review", "summary"):
        if not isinstance(payload.get(section), dict):
            errors.append(f"missing section '{section}'")
    dev = payload.get("dev") if isinstance(payload.get("dev"), dict) else {}
    test = payload.get("test") if isinstance(payload.get("test"), dict) else {}
    review = payload.get("review") if isinstance(payload.get("review"), dict) else {}
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
    if (_as_str(summary.get("result")) or "").lower() not in {"pass", "fail", "blocked"}:
        errors.append("summary.result must be pass|fail|blocked")
    if (_as_str(summary.get("expectation")) or "").lower() not in VERIFICATION_EXPECTATIONS:
        errors.append("summary.expectation must be expect_fail|expect_pass")
    if not isinstance(summary.get("expectation_met"), bool):
        errors.append("summary.expectation_met must be bool")
    if (_as_str(summary.get("failure_class")) or "").lower() not in EVIDENCE_FAILURE_CLASSES:
        errors.append("summary.failure_class must be expected_red|infra|unexpected|none")
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
    merged_task_ids: set[str] = set()
    done_registry_path = _repo_path(repo_root, DONE_TASKS_REGISTRY_JSON)
    if done_registry_path.exists():
        try:
            done_registry = _read_json(done_registry_path)
        except OpError:
            done_registry = None
        if isinstance(done_registry, dict):
            merged_rows = done_registry.get("merged_tasks")
            if isinstance(merged_rows, list):
                for row in merged_rows:
                    if not isinstance(row, dict):
                        continue
                    merged_task_id = _as_str(row.get("task_id"))
                    if merged_task_id:
                        merged_task_ids.add(merged_task_id)
    for task in task_state.get("tasks", []):
        if not isinstance(task, dict):
            continue
        task_id = _as_str(task.get("task_id"))
        phase_id = _as_str(task.get("phase_id")) or "phase-1"
        if not task_id:
            continue
        plan_task = plan_map.get(task_id) if isinstance(plan_map.get(task_id), dict) else {}
        contract = _task_verification_contract(task, plan_task)
        gapfix_state = _normalize_gapfix_state(task.get("gapfix_state"))
        task["gapfix_state"] = gapfix_state
        evidence_path = _task_evidence_path(repo_root, task)
        if not evidence_path.exists():
            task["status"] = "blocked"
            task["owner_slot"] = None
            task["blocking_source"] = "evidence"
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
            task["blocking_source"] = "evidence"
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
            task["blocking_source"] = "evidence"
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
            task["blocking_source"] = "evidence"
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
        task_kind = _task_kind(task, plan_task)
        stage = _current_stage_for_task_status(_normalize_task_status(task.get("status")), _as_str(task.get("owner_slot")))
        evidence_stage = _current_evidence_stage(task, plan_task)
        expected = _expected_for_stage(contract, evidence_stage)
        summary = payload["summary"]
        summary_result = (_as_str(summary.get("result")) or "").lower()
        reason_codes = summary.get("reason_codes") if isinstance(summary.get("reason_codes"), list) else []
        is_not_started_placeholder = _is_not_started_evidence_placeholder(payload, summary_result, reason_codes)
        payload_updated_at = _as_str(payload.get("updated_at")) or utc_now_iso()
        if not _as_str(task.get("last_progress_at")):
            task["last_progress_at"] = payload_updated_at
        if is_not_started_placeholder:
            if isinstance(plan_task, dict) and not task.get("requirement_ids"):
                task["requirement_ids"] = [
                    rid
                    for rid in ((_as_str(item) for item in plan_task.get("requirement_ids", [])))
                    if rid
                ]
            continue

        last_dispatch = task.get("last_dispatch") if isinstance(task.get("last_dispatch"), dict) else {}
        last_dispatch_role = (_as_str(last_dispatch.get("role")) or "").lower()
        if last_dispatch_role == "developer":
            branch_name = _as_str(last_dispatch.get("branch_name"))
            start_from_commit = _as_str(last_dispatch.get("start_from_commit"))
            guard = _repo_guard_scan(
                repo_root,
                {
                    "mode": "dispatch_commit_link",
                    "repo_root": str(repo_root),
                    "branch_name": branch_name,
                    "start_from_commit": start_from_commit,
                },
            )
            if not _as_bool_field(guard.get("ok")):
                task["status"] = TASK_STATUS_BLOCKED
                task["owner_slot"] = None
                task["blocking_source"] = "evidence"
                task["last_progress_at"] = payload_updated_at
                blocker_code = _as_str(guard.get("reason_code")) or "dispatch_commit_link_missing"
                guard_error = _as_str(guard.get("error"))
                if not _as_str(guard.get("reason_code")) and guard_error in {"script_missing", "runtime_error"}:
                    blocker_code = "dispatch_commit_link_inspection_failed"
                _append_task_blocker(
                    task,
                    summary=f"task evidence commit-link guard failed for {task_id}",
                    details={
                        "code": blocker_code,
                        "stage": stage,
                        "reason": _as_str(guard.get("message")) or _as_str(guard.get("inspect_error")) or "commit-link guard failed",
                        "branch_name": branch_name,
                        "start_from_commit": start_from_commit,
                        "head_commit": _as_str(guard.get("head_commit")),
                        "changed_paths": guard.get("changed_paths") if isinstance(guard.get("changed_paths"), list) else [],
                        "forbidden_paths": guard.get("forbidden_paths") if isinstance(guard.get("forbidden_paths"), list) else [],
                    },
                )
                warnings.append(
                    {
                        "code": blocker_code,
                        "message": (
                            f"task {task_id} blocked by dispatch commit-link guard "
                            f"(role=developer, branch={branch_name or 'unknown'})"
                        ),
                        "stage": "build_loop",
                        "task_id": task_id,
                    }
                )
                continue

        expectation_eval = _evaluate_evidence_expectation(payload=payload, expected=expected)
        if expectation_eval.get("progress"):
            if _as_bool_field(gapfix_state.get("active")):
                _apply_successful_evidence_completion(
                    task,
                    payload_updated_at=payload_updated_at,
                    gapfix_state=gapfix_state,
                )
            else:
                _apply_successful_evidence_completion(task, payload_updated_at=payload_updated_at)
            warnings.append(
                {
                    "code": "tdd_expectation_met",
                    "message": (
                        f"task {task_id} advanced at stage={evidence_stage} with expected={expected} "
                        f"(failure_class={_as_str(expectation_eval.get('failure_class')) or 'none'})"
                    ),
                    "stage": "build_loop",
                    "task_id": task_id,
                    "expected": expected,
                    "stage_name": evidence_stage,
                }
            )
        elif expectation_eval.get("blocked"):
            if _as_bool_field(gapfix_state.get("active")):
                gapfix_state["active"] = False
                gapfix_state["active_batch_id"] = None
                gapfix_state["batch_last_updated_at"] = payload_updated_at
                task["gapfix_state"] = gapfix_state
            normalized_status = _normalize_task_status(task.get("status"))
            if normalized_status == TASK_STATUS_REVIEW_DONE and task_id in merged_task_ids:
                warnings.append(
                    {
                        "code": "tdd_expectation_not_met",
                        "message": (
                            f"task {task_id} has post-merge evidence mismatch but merge already recorded; "
                            "status kept at review_done"
                        ),
                        "stage": "build_loop",
                        "task_id": task_id,
                        "expected": expected,
                        "failure_class": _as_str(expectation_eval.get("failure_class")) or "unexpected",
                    }
                )
            else:
                task["status"] = TASK_STATUS_BLOCKED
                task["owner_slot"] = None
                task["blocking_source"] = "evidence"
                task["last_progress_at"] = payload_updated_at
                blocker_reason = _as_str(expectation_eval.get("message")) or "verification expectation mismatch"
                blocker_code = _as_str(expectation_eval.get("reason_code")) or "tdd_expectation_not_met"
                _append_task_blocker(
                    task,
                    summary=f"task evidence expectation failed for {task_id}",
                    details={
                        "code": blocker_code,
                        "failure_class": _as_str(expectation_eval.get("failure_class")) or "unexpected",
                        "expected": expected,
                        "stage": stage,
                        "reason": blocker_reason,
                        "evidence_path": str(evidence_path),
                    },
                )
                warnings.append(
                    {
                        "code": "tdd_expectation_not_met",
                        "message": (
                            f"task {task_id} blocked: stage={stage}, expected={expected}, "
                            f"failure_class={_as_str(expectation_eval.get('failure_class')) or 'unexpected'}"
                        ),
                        "stage": "build_loop",
                        "task_id": task_id,
                        "expected": expected,
                        "stage_name": stage,
                        "failure_class": _as_str(expectation_eval.get("failure_class")) or "unexpected",
                    }
                )

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
        "completed": "pass",
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
    expectation = _normalize_stage_expectation(summary.get("expectation"))
    if summary.get("expectation") != expectation:
        summary["expectation"] = expectation
        changed = True
    failure_class = _normalize_failure_class(summary.get("failure_class"))
    if summary.get("failure_class") != failure_class:
        summary["failure_class"] = failure_class
        changed = True
    payload["summary"] = summary
    return changed


def _normalize_handoff_result(value: Any) -> str:
    result = (_as_str(value) or "").strip().lower()
    return {
        "ready_for_test": "completed",
        "ready_for_review": "completed",
        "review_passed": "completed",
    }.get(result, result)


def _apply_successful_evidence_completion(
    task: dict[str, Any],
    *,
    payload_updated_at: str,
    gapfix_state: dict[str, Any] | None = None,
) -> None:
    task["status"] = TASK_STATUS_REVIEW_DONE
    task["owner_slot"] = None
    task["blocking_source"] = "none"
    task["last_progress_at"] = payload_updated_at
    if isinstance(gapfix_state, dict):
        gapfix_state["active"] = False
        gapfix_state["active_batch_id"] = None
        gapfix_state["batch_last_updated_at"] = payload_updated_at
        task["gapfix_state"] = gapfix_state


def _dead_pid_redispatch_base_status(
    task: dict[str, Any],
    plan_task: dict[str, Any] | None,
    *,
    status: str,
    stage_name: str,
) -> tuple[str, dict[str, Any] | None]:
    if bool(task.get("is_gap_closure")) or bool((plan_task or {}).get("is_gap_closure")):
        return {
            TASK_STATUS_DEV_WORKING: TASK_STATUS_PENDING,
            TASK_STATUS_TESTING: TASK_STATUS_DEV_DONE,
            TASK_STATUS_REVIEWING: TASK_STATUS_TESTS_DONE,
        }[status], None
    expected_stage = _dispatch_stage_for_task(task, plan_task)
    warning: dict[str, Any] | None = None
    if expected_stage != stage_name:
        warning = {
            "code": "dead_pid_legacy_stage_normalized",
            "message": (
                f"task {_as_str(task.get('task_id')) or 'TASK-UNKNOWN'} dead-pid recovery normalized "
                f"legacy stage {stage_name} to canonical redispatch stage {expected_stage}"
            ),
            "stage": "build_loop",
            "task_id": _as_str(task.get("task_id")) or None,
            "legacy_stage": stage_name,
            "canonical_stage": expected_stage,
            "task_kind": _task_kind(task, plan_task),
        }
    return TASK_STATUS_PENDING, warning


def _repair_task_state_task_kinds(task_state: dict[str, Any], plan_packets: dict[str, Any]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    tasks = task_state.get("tasks")
    if not isinstance(tasks, list):
        return warnings
    plan_map = _plan_task_map(plan_packets)
    for item in tasks:
        if not isinstance(item, dict):
            continue
        task_id = _as_str(item.get("task_id"))
        if not task_id:
            continue
        plan_task = plan_map.get(task_id) if isinstance(plan_map.get(task_id), dict) else None
        if not isinstance(plan_task, dict):
            item["task_kind"] = _normalize_task_kind(item.get("task_kind"))
            continue
        plan_kind = _normalize_task_kind(plan_task.get("task_kind"))
        state_kind_raw = _as_str(item.get("task_kind")) or ""
        state_kind = _normalize_task_kind(state_kind_raw)
        item["task_kind"] = plan_kind
        if state_kind != plan_kind:
            warnings.append(
                {
                    "code": "task_kind_repaired_from_plan",
                    "message": (
                        f"task {task_id} task_kind repaired from {state_kind_raw or 'missing'} "
                        f"to {plan_kind} using PLAN_PACKETS authority"
                    ),
                    "stage": "build_preflight",
                    "task_id": task_id,
                    "from_task_kind": state_kind_raw or None,
                    "to_task_kind": plan_kind,
                }
            )
    return warnings


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
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    result = (_as_str(summary.get("result")) or "").lower()
    if result != "pass" or not _as_bool_field(summary.get("expectation_met")):
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
        merge_ready = task_status == TASK_STATUS_REVIEW_DONE
        evidence = task.get("evidence") if isinstance(task.get("evidence"), dict) else {}
        evidence_ref = _as_str(evidence.get("task_evidence_ref")) or str(_canonical_task_evidence_rel(task_id))
        contract = _task_verification_contract(task, plan_task)
        review_expectation = _expected_for_stage(contract, "review")
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
        if merge_ready:
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
        if merge_ready and review_expectation != "expect_fail":
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
        if status not in {"open", "consumed", "closed", "exhausted", "human_blocked", "verified", "patched"}:
            status = "open"
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
        normalized["consumed_by_batch_id"] = _as_str(normalized.get("consumed_by_batch_id"))
        normalized["consumed_at"] = _as_str(normalized.get("consumed_at"))
        normalized["superseded_by_gap_id"] = _as_str(normalized.get("superseded_by_gap_id"))
        normalized["previous_gap_id"] = _as_str(normalized.get("previous_gap_id"))
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
        if requested_status not in {"open", "consumed", "closed", "exhausted", "human_blocked", "verified", "patched"}:
            requested_status = "open"
        # Consumed gaps stay immutable snapshots; unresolved conditions are tracked as child gaps.
        if prior_status == "consumed" and requested_status == "open":
            child_gap_id = _as_str(item.get("superseded_by_gap_id"))
            child_row: dict[str, Any] | None = None
            if child_gap_id:
                for candidate in rows:
                    if _as_str(candidate.get("gap_id")) == child_gap_id:
                        child_row = candidate
                        break
            if child_row is None:
                next_retry = max(prior_retry_count + 1, 1)
                child_gap_id = f"{target_gap_id}.r{next_retry}"
                while any(_as_str(candidate.get("gap_id")) == child_gap_id for candidate in rows):
                    next_retry += 1
                    child_gap_id = f"{target_gap_id}.r{next_retry}"
                child_row = {
                    "gap_id": child_gap_id,
                    "status": "open",
                    "category": _as_str(row.get("category")) or _as_str(item.get("category")) or "other",
                    "severity": _as_str(row.get("severity")) or _as_str(item.get("severity")) or "P2",
                    "stage": _as_str(row.get("stage")) or _as_str(item.get("stage")) or "dev",
                    "reason_codes": [
                        code
                        for code in (_as_str(v) for v in row.get("reason_codes", []))
                        if code
                    ]
                    or [
                        code
                        for code in (_as_str(v) for v in item.get("reason_codes", []))
                        if code
                    ]
                    or ["gap_detected"],
                    "retry_count": next_retry,
                    "max_retries": max(
                        1,
                        _coerce_nonneg_int(
                            row.get("max_retries"),
                            default=_coerce_nonneg_int(item.get("max_retries"), default=5),
                        ),
                    ),
                    "created_at": now,
                    "updated_at": now,
                    "closure_ref": _as_str(row.get("closure_ref")) or _as_str(item.get("closure_ref")),
                    "previous_gap_id": target_gap_id,
                }
                rows.append(child_row)
            else:
                child_row.update(row)
                child_row["updated_at"] = now
                child_row["status"] = "open"
                child_row["previous_gap_id"] = _as_str(child_row.get("previous_gap_id")) or target_gap_id
                child_row["retry_count"] = max(
                    _coerce_nonneg_int(child_row.get("retry_count"), default=0),
                    prior_retry_count + 1,
                )
                child_row["max_retries"] = max(1, _coerce_nonneg_int(child_row.get("max_retries"), default=5))
                child_row["reason_codes"] = [
                    code for code in (_as_str(v) for v in child_row.get("reason_codes", [])) if code
                ] or ["gap_detected"]
            item["superseded_by_gap_id"] = child_gap_id
            item["updated_at"] = now
            task["gaps_that_need_patching"] = rows
            return
        item.update(row)
        item["updated_at"] = now
        item["status"] = requested_status
        requested_retry_count = _coerce_nonneg_int(row.get("retry_count"), default=prior_retry_count)
        if prior_status == "closed" and requested_status == "open":
            item["retry_count"] = max(prior_retry_count + 1, requested_retry_count)
        else:
            item["retry_count"] = requested_retry_count
        item["max_retries"] = max(1, _coerce_nonneg_int(item.get("max_retries"), default=5))
        item["reason_codes"] = [code for code in (_as_str(v) for v in item.get("reason_codes", [])) if code] or ["gap_detected"]
        item["consumed_by_batch_id"] = _as_str(item.get("consumed_by_batch_id"))
        item["consumed_at"] = _as_str(item.get("consumed_at"))
        item["superseded_by_gap_id"] = _as_str(item.get("superseded_by_gap_id"))
        item["previous_gap_id"] = _as_str(item.get("previous_gap_id"))
        task["gaps_that_need_patching"] = rows
        return
    inserted = dict(row)
    inserted_status = (_as_str(inserted.get("status")) or "open").lower()
    if inserted_status not in {"open", "consumed", "closed", "exhausted", "human_blocked", "verified", "patched"}:
        inserted_status = "open"
    inserted["status"] = inserted_status
    inserted.setdefault("retry_count", 0)
    inserted.setdefault("max_retries", 5)
    inserted.setdefault("created_at", now)
    inserted["updated_at"] = now
    inserted["reason_codes"] = [code for code in (_as_str(v) for v in inserted.get("reason_codes", [])) if code] or ["gap_detected"]
    inserted["consumed_by_batch_id"] = _as_str(inserted.get("consumed_by_batch_id"))
    inserted["consumed_at"] = _as_str(inserted.get("consumed_at"))
    inserted["superseded_by_gap_id"] = _as_str(inserted.get("superseded_by_gap_id"))
    inserted["previous_gap_id"] = _as_str(inserted.get("previous_gap_id"))
    rows.append(inserted)
    task["gaps_that_need_patching"] = rows


def _close_task_gap(task: dict[str, Any], *, gap_id: str, closure_ref: str | None = None) -> None:
    rows = _normalize_task_gap_rows(task)
    now = utc_now_iso()
    closed_ids: set[str] = set()
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
        closed_ids.add(gap_id)
    # If a child gap closes, close consumed parent snapshots in the same lineage.
    changed = True
    while changed:
        changed = False
        for row in rows:
            parent_gap_id = _as_str(row.get("gap_id"))
            child_gap_id = _as_str(row.get("superseded_by_gap_id"))
            if not parent_gap_id or not child_gap_id:
                continue
            if child_gap_id not in closed_ids:
                continue
            if (_as_str(row.get("status")) or "").lower() != "consumed":
                continue
            row["status"] = "closed"
            row["updated_at"] = now
            reason_codes = [
                code for code in (_as_str(item) for item in row.get("reason_codes", [])) if code
            ]
            if "gap_closed_by_evidence" not in reason_codes:
                reason_codes.append("gap_closed_by_evidence")
            row["reason_codes"] = reason_codes or ["gap_closed_by_evidence"]
            if closure_ref and not _as_str(row.get("closure_ref")):
                row["closure_ref"] = closure_ref
            closed_ids.add(parent_gap_id)
            changed = True
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
        contract = _task_verification_contract(task, plan_task)
        review_expectation = _expected_for_stage(contract, "review")
        evidence_path = _task_evidence_path(repo_root, task)
        evidence_ref = os.path.relpath(str(evidence_path), str(repo_root))
        status = _normalize_task_status(task.get("status"))
        merge_ready = status == TASK_STATUS_REVIEW_DONE
        active_gap_ids: set[str] = set()

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

        if merge_ready:
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

        if merge_ready and review_expectation != "expect_fail":
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
            row_status = (_as_str(row.get("status")) or "").lower()
            if row_status not in {"open", "consumed"}:
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
                if review_expectation == "expect_fail":
                    pass
                else:
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
            if (_as_str(row.get("status")) or "").lower() not in {"open", "consumed"}:
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
            status = (_as_str(row.get("status")) or "").lower()
            if status in {"closed", "verified", "patched"}:
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
        hard = bool(
            data.get("permanently_blocked")
            or data.get("hard_gated")
            or data.get("gated")
            or five.get("gated")
            or weekly.get("gated")
        )
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


def _select_planner_profile_from_rate_registry(repo_root: Path, *, stage: str = "plan") -> tuple[str | None, str | None]:
    try:
        selection = _load_profile_selection_required(repo_root, stage=stage)
    except OpError:
        return None, None

    alias_to_home = selection.get("alias_to_home") if isinstance(selection.get("alias_to_home"), dict) else {}
    selected_aliases = [
        alias for alias in (_as_str(item) for item in selection.get("selected_aliases", [])) if alias
    ]
    if len(selected_aliases) > 1:
        selected_aliases = [alias for alias in selected_aliases if alias != "codex"]
    if not selected_aliases:
        return None, None

    path = _repo_path(repo_root, PROFILE_RATE_REGISTRY_JSON)
    if not path.exists():
        return None, None
    try:
        payload = _read_json(path)
    except OpError:
        return None, None
    if not isinstance(payload, dict):
        return None, None
    profiles = _profiles_map_from_rate_registry(payload)
    if not profiles:
        return None, None

    ranked: list[tuple[float, float, str, str]] = []
    for alias in selected_aliases:
        home = _as_str(alias_to_home.get(alias))
        if not home:
            continue
        row = profiles.get(alias)
        if not isinstance(row, dict):
            continue
        five = row.get("five_hour") if isinstance(row.get("five_hour"), dict) else row.get("5h")
        if not isinstance(five, dict):
            five = {}
        weekly = row.get("weekly") if isinstance(row.get("weekly"), dict) else {}
        if not isinstance(weekly, dict):
            weekly = {}

        five_remaining = _extract_remaining_percent(five)
        if five_remaining is None:
            raw_five = row.get("window_5h_remaining_pct")
            try:
                five_remaining = float(raw_five) if raw_five is not None else None
            except (TypeError, ValueError):
                five_remaining = None
        five_hard_gated = bool(five.get("gated")) or (five_remaining is not None and five_remaining <= 1.0)
        if five_hard_gated:
            continue

        weekly_remaining = _extract_remaining_percent(weekly)
        if weekly_remaining is None:
            raw_weekly = row.get("window_week_remaining_pct")
            try:
                weekly_remaining = float(raw_weekly) if raw_weekly is not None else None
            except (TypeError, ValueError):
                weekly_remaining = None
        if weekly_remaining is None:
            continue

        ranked.append((weekly_remaining, five_remaining or 0.0, alias, home))

    if not ranked:
        return None, None

    ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))
    _weekly_remaining, _five_remaining, alias, home = ranked[0]
    return alias, home


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

        hard_gated = bool(
            data.get("permanently_blocked")
            or data.get("hard_gated")
            or data.get("gated")
            or five.get("gated")
            or weekly.get("gated")
        )
        if (five_remaining is not None and five_remaining <= 1.0) or (weekly_remaining is not None and weekly_remaining <= 1.0):
            hard_gated = True
        soft_gated = bool(data.get("soft_concurrency_gated"))
        if (five_remaining is not None and five_remaining <= 5.0) or (weekly_remaining is not None and weekly_remaining <= 5.0):
            soft_gated = True

        recommended_action = (_as_str(data.get("recommended_action")) or "").lower()
        if recommended_action in {"wind_down", "wait_until_reset"}:
            hard_gated = True
        errors_raw = data.get("errors")
        error_codes = [
            (_as_str(item) or "").strip()
            for item in (errors_raw if isinstance(errors_raw, list) else [])
            if _as_str(item)
        ]
        auth_unhealthy_markers = (
            "refresh_token",
            "invalid_grant",
            "unauthorized",
            "auth_failed",
            "auth_error",
            "token refresh failed",
            "token_refresh_failed",
        )
        unhealthy = any(any(marker in code.lower() for marker in auth_unhealthy_markers) for code in error_codes)
        if unhealthy:
            # Auth-unhealthy profiles are excluded from fresh dispatch selection.
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
            "unhealthy": unhealthy,
            "errors": error_codes,
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
    non_gated_aliases = [
        alias
        for alias in aliases
        if not bool(rate_states.get(alias, {}).get("hard_gated"))
        and not bool(rate_states.get(alias, {}).get("unhealthy"))
    ]
    if not non_gated_aliases:
        reset_candidates = [
            _as_str(rate_states.get(alias, {}).get("reset_at"))
            for alias in aliases
            if _as_str(rate_states.get(alias, {}).get("reset_at"))
        ]
        error_rows = {
            alias: list(rate_states.get(alias, {}).get("errors") or [])
            for alias in aliases
            if isinstance(rate_states.get(alias, {}).get("errors"), list)
            and list(rate_states.get(alias, {}).get("errors") or [])
        }
        return {
            "ok": False,
            "reason": "profile_assignment_all_hard_gated",
            "warning": {
                "code": "profile_assignment_all_hard_gated",
                "message": "all selected profiles are hard-gated; dispatch skipped",
                "stage": "build_loop",
                "profiles": aliases,
                "reset_at_candidates": reset_candidates,
                "profile_errors": error_rows,
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
    run_id = _run_id_from_lock_id(_as_str(build_state.get("loop_lock_id")))
    for slot in FIXED_WORKER_SLOTS:
        row = by_slot.get(slot)
        if not isinstance(row, dict):
            row = _default_worker_row(slot, run_id=run_id)
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


def _infer_dispatch_failure_reason_from_worker_log(worker_row: dict[str, Any] | None) -> dict[str, str] | None:
    if not isinstance(worker_row, dict):
        return None
    log_path_raw = _as_str(worker_row.get("dispatch_log"))
    if not log_path_raw:
        return None
    log_path = Path(log_path_raw).expanduser()
    try:
        if not log_path.exists() or not log_path.is_file():
            return None
        log_mtime = datetime.fromtimestamp(log_path.stat().st_mtime, tz=timezone.utc)
        now = datetime.now(timezone.utc)
        if (now - log_mtime).total_seconds() > 1800:
            return None
        dispatch_started_at = _parse_iso_utc(_as_str(worker_row.get("dispatch_started_at")) or _as_str(worker_row.get("updated_at")))
        if dispatch_started_at is not None and (log_mtime + timedelta(seconds=5)) < dispatch_started_at:
            return None
        excerpt = log_path.read_text(encoding="utf-8", errors="ignore")[-8000:].lower()
    except OSError:
        return None
    patterns: tuple[tuple[str, str, str], ...] = (
        (
            "refresh_token_reused",
            "worker_dispatch_auth_failed",
            "dispatch log shows refresh_token_reused 401 unauthorized auth failure",
        ),
        ("invalid_grant", "worker_dispatch_auth_failed", "dispatch log shows invalid_grant auth failure"),
        ("token refresh failed", "worker_dispatch_auth_failed", "dispatch log shows token refresh failure"),
        ("unauthorized", "worker_dispatch_auth_failed", "dispatch log shows unauthorized auth failure"),
        ("stdin is not a terminal", "dispatch_resume_notty_detected", "dispatch log shows non-tty resume failure"),
    )
    for needle, code, summary in patterns:
        if needle in excerpt:
            return {
                "code": code,
                "message": summary,
                "log_path": str(log_path),
            }
    return None


def _prepare_dead_pid_redispatch_assignments(
    repo_root: Path,
    task_state: dict[str, Any],
    plan_packets: dict[str, Any],
    build_state: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    warnings: list[dict[str, Any]] = []
    assignments: list[dict[str, Any]] = []
    active_slots = _active_worker_slots(repo_root)
    registry_path = repo_root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json"
    _, registry_workers, _ = _load_worker_registry(registry_path)
    workers_by_slot = {
        _as_str(row.get("slot")): row
        for row in registry_workers
        if isinstance(row, dict) and _as_str(row.get("slot"))
    }
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
    dead_pid_policy = build_state.get("dead_pid_recovery_policy")
    if not isinstance(dead_pid_policy, dict):
        dead_pid_policy = {"grace_sec": DEAD_PID_REDISPATCH_GRACE_SEC}
    dead_pid_grace_sec = max(
        60,
        _coerce_nonneg_int(dead_pid_policy.get("grace_sec"), default=DEAD_PID_REDISPATCH_GRACE_SEC),
    )
    build_state["dead_pid_recovery_policy"] = {"grace_sec": dead_pid_grace_sec}
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
        worker_row = workers_by_slot.get(owner_slot)
        worker_state = (
            _as_str((worker_row or {}).get("state"))
            or _as_str((worker_row or {}).get("session_state"))
            or _as_str((worker_row or {}).get("status"))
            or ""
        ).lower()
        dispatch_thread_id = _as_str((worker_row or {}).get("dispatch_thread_id"))
        dispatch_started_at = _parse_iso_utc(
            _as_str((worker_row or {}).get("dispatch_started_at"))
            or _as_str((worker_row or {}).get("updated_at"))
        )
        if (
            worker_state in {"running", "active", "busy"}
            and dispatch_thread_id
            and dispatch_started_at is not None
            and (datetime.now(timezone.utc) - dispatch_started_at).total_seconds() < dead_pid_grace_sec
        ):
            warnings.append(
                {
                    "code": "dead_pid_awaiting_worker_heartbeat",
                    "message": (
                        f"task {task_id} slot {owner_slot} has no live pid yet, but running session thread "
                        f"{dispatch_thread_id} is within grace window ({dead_pid_grace_sec}s); redispatch deferred"
                    ),
                    "stage": "build_loop",
                    "task_id": task_id,
                    "slot": owner_slot,
                    "grace_sec": dead_pid_grace_sec,
                }
            )
            continue
        dispatch_failure_hint = _infer_dispatch_failure_reason_from_worker_log(worker_row)
        dispatch_failure_code = _as_str((dispatch_failure_hint or {}).get("code"))
        dispatch_failure_message = _as_str((dispatch_failure_hint or {}).get("message"))
        dispatch_failure_log = _as_str((dispatch_failure_hint or {}).get("log_path"))
        if dispatch_failure_code:
            warnings.append(
                {
                    "code": dispatch_failure_code,
                    "message": (
                        f"task {task_id} slot {owner_slot}: {dispatch_failure_message or dispatch_failure_code}"
                        + (f" (log={dispatch_failure_log})" if dispatch_failure_log else "")
                    ),
                    "stage": "build_loop",
                    "task_id": task_id,
                    "slot": owner_slot,
                    "artifact": dispatch_failure_log or None,
                }
            )
            if _is_refresh_token_reused_unauthorized(dispatch_failure_message):
                blocked_alias = _as_str((worker_row or {}).get("codex_profile_alias"))
                block_warning = _set_profile_permanent_block(
                    repo_root,
                    alias=blocked_alias,
                    reason_code="refresh_token_reused",
                    stage="build_loop",
                )
                if isinstance(block_warning, dict):
                    warnings.append(block_warning)

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
            issue_message = evidence_issue_message or evidence_issue_code
            if dispatch_failure_code:
                issue_message = (
                    f"{issue_message}; likely cause: {dispatch_failure_code}"
                    + (f" ({dispatch_failure_message})" if dispatch_failure_message else "")
                )
            warnings.append(
                {
                    "code": evidence_issue_code,
                    "message": (
                        f"task {task_id} slot {owner_slot}: {issue_message} "
                        f"(artifact={evidence_path})"
                    ),
                    "stage": "build_loop",
                    "task_id": task_id,
                    "slot": owner_slot,
                    "artifact": str(evidence_path),
                    "likely_cause_code": dispatch_failure_code or None,
                }
            )
        stage_name, role_name = status_to_stage[status]
        plan_task = plan_map.get(task_id) if isinstance(plan_map.get(task_id), dict) else {}
        contract = _task_verification_contract(task, plan_task)
        expected = _expected_for_stage(contract, stage_name)
        summary = evidence_payload.get("summary") if isinstance(evidence_payload.get("summary"), dict) else {}
        summary_result = (_as_str(summary.get("result")) or "").lower()
        reason_codes = summary.get("reason_codes") if isinstance(summary.get("reason_codes"), list) else []
        is_not_started_placeholder = _is_not_started_evidence_placeholder(
            evidence_payload,
            summary_result,
            reason_codes,
        )
        evidence_progress = False
        if evidence_payload and not is_not_started_placeholder:
            expectation_eval = _evaluate_evidence_expectation(payload=evidence_payload, expected=expected)
            if expectation_eval.get("progress"):
                evidence_progress = True
                _apply_successful_evidence_completion(task, payload_updated_at=utc_now_iso())
            else:
                warnings.append(
                    {
                        "code": "tdd_expectation_not_met",
                        "message": (
                            f"task {task_id} dead-pid recovery found non-progress evidence "
                            f"(stage={stage_name}, expected={expected}, "
                            f"failure_class={_as_str(expectation_eval.get('failure_class')) or 'unexpected'})"
                        ),
                        "stage": "build_loop",
                        "task_id": task_id,
                        "slot": owner_slot,
                    }
                )

        if evidence_progress:
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

        redispatch_base_status, normalization_warning = _dead_pid_redispatch_base_status(
            task,
            plan_task,
            status=status,
            stage_name=stage_name,
        )
        if isinstance(normalization_warning, dict):
            warnings.append(normalization_warning)
        task["status"] = redispatch_base_status
        task["owner_slot"] = None
        task["blocking_source"] = "none"
        task["last_progress_at"] = utc_now_iso()
        lane_id = _as_str(task.get("lane_id")) or _as_str(plan_task.get("lane_id"))
        phase_id = _as_str(task.get("phase_id")) or _as_str(plan_task.get("phase_id")) or "phase-1"
        retry_count = int(retry_counts.get(task_id, 0)) + 1
        retry_counts[task_id] = retry_count
        if retry_count >= missing_threshold:
            task["status"] = TASK_STATUS_BLOCKED
            gap_code = evidence_issue_code or "worker_completion_artifact_missing"
            gap_reason_codes = [gap_code, "dead_pid_retry_threshold_reached"]
            if dispatch_failure_code and dispatch_failure_code not in gap_reason_codes:
                gap_reason_codes.insert(0, dispatch_failure_code)
            _upsert_task_gap(
                task,
                {
                    "gap_id": _gap_id(plan_id, phase_id, task_id, f"completion:{stage_name}", "blocked"),
                    "category": "task_blocked",
                    "severity": "P1",
                    "stage": stage_name,
                    "status": "open",
                    "reason_codes": gap_reason_codes,
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
                    "likely_cause_code": dispatch_failure_code or None,
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
                    "likely_cause_code": dispatch_failure_code or None,
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
                "likely_cause_code": dispatch_failure_code or None,
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


def _ensure_command_flag(command_text: str, flag: str) -> str:
    text = (command_text or "").strip()
    if not text:
        return text
    wrapped = _unwrap_bash_lc(text)
    if wrapped is not None:
        updated = _ensure_command_flag(wrapped, flag)
        if updated == wrapped:
            return text
        return f"bash -lc {shlex.quote(updated)}"
    try:
        tokens = shlex.split(text)
    except ValueError:
        return f"{text} {flag}".strip()
    if not tokens:
        return text
    if flag in tokens or any(token.startswith(f"{flag}=") for token in tokens):
        return text
    tokens.append(flag)
    return shlex.join(tokens)


def _ensure_command_option_value(command_text: str, option: str, value: str) -> str:
    text = (command_text or "").strip()
    if not text:
        return text
    wrapped = _unwrap_bash_lc(text)
    if wrapped is not None:
        updated = _ensure_command_option_value(wrapped, option, value)
        if updated == wrapped:
            return text
        return f"bash -lc {shlex.quote(updated)}"
    try:
        tokens = shlex.split(text)
    except ValueError:
        return f"{text} {option} {shlex.quote(value)}".strip()
    if not tokens:
        return text

    idx = 0
    while idx < len(tokens):
        token = tokens[idx]
        if token == option:
            if idx + 1 < len(tokens):
                tokens[idx + 1] = value
                return shlex.join(tokens)
            tokens.append(value)
            return shlex.join(tokens)
        if token.startswith(f"{option}="):
            tokens[idx] = f"{option}={value}"
            return shlex.join(tokens)
        idx += 1

    tokens.extend([option, value])
    return shlex.join(tokens)


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


def _git_branch_exists(repo_root: Path, branch_name: str) -> bool:
    return _run(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}"], cwd=repo_root)[0] == 0


def _ensure_initialize_branch_layout(repo_root: Path) -> dict[str, Any]:
    if not _is_git_work_tree(repo_root):
        raise OpError("git_bootstrap_failed", "repository is not initialized as a git work tree", stage="initialize")
    head = _git_text(repo_root, "rev-parse", "HEAD")
    if not head:
        raise OpError("git_bootstrap_failed", "unable to resolve HEAD commit after bootstrap", stage="initialize")

    created_main = False
    created_rab_base = False

    if not _git_branch_exists(repo_root, GIT_BOOTSTRAP_PRIMARY_BRANCH):
        code, _, err = _run(["git", "branch", GIT_BOOTSTRAP_PRIMARY_BRANCH, head], cwd=repo_root)
        if code != 0:
            raise OpError(
                "git_bootstrap_failed",
                f"unable to create {GIT_BOOTSTRAP_PRIMARY_BRANCH} branch: {err.strip() or 'unknown error'}",
                stage="initialize",
            )
        created_main = True

    if not _git_branch_exists(repo_root, GIT_BOOTSTRAP_REQUIRED_BRANCH):
        code, _, err = _run(["git", "branch", GIT_BOOTSTRAP_REQUIRED_BRANCH, head], cwd=repo_root)
        if code != 0:
            raise OpError(
                "git_bootstrap_failed",
                f"unable to create {GIT_BOOTSTRAP_REQUIRED_BRANCH} branch: {err.strip() or 'unknown error'}",
                stage="initialize",
            )
        created_rab_base = True

    current_branch = _git_text(repo_root, "branch", "--show-current") or ""
    if current_branch != GIT_BOOTSTRAP_REQUIRED_BRANCH:
        code, _, err = _run(["git", "checkout", GIT_BOOTSTRAP_REQUIRED_BRANCH], cwd=repo_root)
        if code != 0:
            raise OpError(
                "git_bootstrap_failed",
                f"unable to checkout {GIT_BOOTSTRAP_REQUIRED_BRANCH}: {err.strip() or 'unknown error'}",
                stage="initialize",
            )

    return {
        "head": head,
        "created_primary_branch": created_main,
        "created_required_branch": created_rab_base,
        "primary_branch": GIT_BOOTSTRAP_PRIMARY_BRANCH,
        "required_branch": GIT_BOOTSTRAP_REQUIRED_BRANCH,
        "current_branch": GIT_BOOTSTRAP_REQUIRED_BRANCH,
    }


def _github_https_remote_url(owner: str, repo_name: str) -> str:
    return f"https://{GITHUB_HOST}/{owner}/{repo_name}.git"


def _parse_github_remote_slug(remote_url: str | None) -> tuple[str, str] | None:
    text = (remote_url or "").strip()
    if not text:
        return None
    https_match = re.match(r"^https://[^/]+/([^/]+)/([^/]+?)(?:\.git)?/?$", text)
    if https_match:
        return https_match.group(1), https_match.group(2)
    ssh_match = re.match(r"^git@[^:]+:([^/]+)/([^/]+?)(?:\.git)?$", text)
    if ssh_match:
        return ssh_match.group(1), ssh_match.group(2)
    return None


def _gh_run(repo_root: Path, *args: str) -> tuple[int, str, str]:
    return _run(["gh", *args], cwd=repo_root)


def _resolve_initialize_publish_target(req: OpRequest) -> tuple[str, str]:
    owner = _as_str(req.github_owner)
    repo_name = _as_str(req.github_repo_name) or req.repo_root.name
    if not owner:
        code, out, err = _gh_run(req.repo_root, "api", "user", "--jq", ".login")
        if code != 0 or not out.strip():
            raise OpError(
                "github_owner_resolution_failed",
                f"unable to resolve authenticated GitHub owner: {err.strip() or out.strip() or 'unknown error'}",
                stage="initialize",
            )
        owner = out.strip()
    return owner, repo_name


def _verify_github_auth_for_initialize(repo_root: Path) -> None:
    code, out, err = _gh_run(repo_root, "auth", "status", "--hostname", GITHUB_HOST)
    if code != 0:
        raise OpError(
            "github_auth_missing",
            f"GitHub CLI is not authenticated for {GITHUB_HOST}: {err.strip() or out.strip() or 'unknown error'}",
            stage="initialize",
        )


def _maybe_publish_private_repo_for_initialize(req: OpRequest) -> tuple[list[dict[str, Any]], list[str], dict[str, Any] | None]:
    if not req.publish_private_repo:
        return [], [], None

    _verify_github_auth_for_initialize(req.repo_root)
    owner, repo_name = _resolve_initialize_publish_target(req)
    repo_slug = f"{owner}/{repo_name}"
    expected_origin_url = _github_https_remote_url(owner, repo_name)
    _emit_build_progress(req, f"ensuring private GitHub repo {repo_slug} exists and origin is configured")

    origin_url = _git_text(req.repo_root, "remote", "get-url", GITHUB_REMOTE_NAME)
    existing_slug = _parse_github_remote_slug(origin_url)
    if origin_url and existing_slug is None:
        raise OpError(
            "github_origin_unrecognized",
            f"origin remote uses an unsupported URL format: {origin_url}",
            stage="initialize",
        )
    if existing_slug and existing_slug != (owner, repo_name):
        raise OpError(
            "github_origin_mismatch",
            f"origin remote points to {existing_slug[0]}/{existing_slug[1]}, expected {repo_slug}",
            stage="initialize",
        )

    code, _, _ = _gh_run(req.repo_root, "repo", "view", repo_slug, "--json", "nameWithOwner")
    created_repo = False
    if code != 0:
        create_code, _, create_err = _gh_run(
            req.repo_root,
            "repo",
            "create",
            repo_slug,
            "--private",
            "--source",
            str(req.repo_root),
            "--remote",
            GITHUB_REMOTE_NAME,
        )
        if create_code != 0:
            raise OpError(
                "github_repo_create_failed",
                f"unable to create private GitHub repo {repo_slug}: {create_err.strip() or 'unknown error'}",
                stage="initialize",
            )
        created_repo = True
        origin_url = _git_text(req.repo_root, "remote", "get-url", GITHUB_REMOTE_NAME)
    elif not origin_url:
        add_code, _, add_err = _run(["git", "remote", "add", GITHUB_REMOTE_NAME, expected_origin_url], cwd=req.repo_root)
        if add_code != 0:
            raise OpError(
                "github_origin_config_failed",
                f"unable to add origin remote for {repo_slug}: {add_err.strip() or 'unknown error'}",
                stage="initialize",
            )
        origin_url = expected_origin_url

    if not origin_url:
        raise OpError(
            "github_origin_missing_after_publish",
            f"origin remote is still missing after preparing {repo_slug}",
            stage="initialize",
        )

    for branch_name in (GIT_BOOTSTRAP_PRIMARY_BRANCH, GIT_BOOTSTRAP_REQUIRED_BRANCH):
        push_code, _, push_err = _run(["git", "push", "-u", GITHUB_REMOTE_NAME, branch_name], cwd=req.repo_root)
        if push_code != 0:
            raise OpError(
                "github_push_failed",
                f"unable to push {branch_name} to {repo_slug}: {push_err.strip() or 'unknown error'}",
                stage="initialize",
            )

    edit_code, _, edit_err = _gh_run(req.repo_root, "repo", "edit", repo_slug, "--default-branch", GIT_BOOTSTRAP_PRIMARY_BRANCH)
    if edit_code != 0:
        raise OpError(
            "github_default_branch_set_failed",
            f"unable to set default branch to {GIT_BOOTSTRAP_PRIMARY_BRANCH} for {repo_slug}: {edit_err.strip() or 'unknown error'}",
            stage="initialize",
        )

    verify_code, verify_out, verify_err = _gh_run(
        req.repo_root,
        "api",
        f"repos/{owner}/{repo_name}",
        "--jq",
        "{full_name: .full_name, visibility: .visibility, private: .private, default_branch: .default_branch, html_url: .html_url}",
    )
    if verify_code != 0 or not verify_out.strip():
        raise OpError(
            "github_repo_verify_failed",
            f"unable to verify GitHub repo state for {repo_slug}: {verify_err.strip() or verify_out.strip() or 'unknown error'}",
            stage="initialize",
        )
    try:
        verified = json.loads(verify_out)
    except json.JSONDecodeError as exc:
        raise OpError(
            "github_repo_verify_failed",
            f"unable to parse GitHub repo verification output for {repo_slug}: {exc}",
            stage="initialize",
        ) from exc

    visibility = _as_str(verified.get("visibility")) or ""
    default_branch = _as_str(verified.get("default_branch")) or ""
    if visibility != "private" or default_branch != GIT_BOOTSTRAP_PRIMARY_BRANCH:
        raise OpError(
            "github_repo_state_mismatch",
            f"GitHub repo {repo_slug} verification mismatch: visibility={visibility or 'unknown'} default_branch={default_branch or 'unknown'}",
            stage="initialize",
        )

    publish_payload = {
        "schema_version": SCHEMA_VERSION,
        "published_at": utc_now_iso(),
        "repo_slug": repo_slug,
        "origin_url": origin_url,
        "visibility": visibility,
        "default_branch": default_branch,
        "created_repo": created_repo,
        "pushed_branches": [GIT_BOOTSTRAP_PRIMARY_BRANCH, GIT_BOOTSTRAP_REQUIRED_BRANCH],
        "html_url": _as_str(verified.get("html_url")),
    }
    publish_artifact = _repo_path(req.repo_root, GIT_BOOTSTRAP_PUBLISH_ARTIFACT)
    _atomic_write_json(publish_artifact, publish_payload)
    _emit_build_progress(req, f"private GitHub repo ready at {repo_slug}; pushed main and RAB-BASE")
    return [], [str(publish_artifact)], publish_payload


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
    warnings: list[dict[str, Any]] = []
    artifacts: list[str] = []
    exit_code = 0
    llm_root = _repo_path(req.repo_root, GIT_BOOTSTRAP_ARTIFACT_REL)

    if not _is_git_work_tree(req.repo_root):
        _emit_build_progress(
            req,
            "git workspace not detected; running LLM bootstrap to initialize repository and create main + RAB-BASE",
        )
        llm_root.mkdir(parents=True, exist_ok=True)
        prompt_path = llm_root / "prompt.txt"
        stdout_path = llm_root / "llm_stdout.log"
        stderr_path = llm_root / "llm_stderr.log"
        last_message_path = llm_root / "last_message.txt"

        prompt = _git_bootstrap_prompt_text(req=req, prior_errors=[])
        prompt_path.write_text(prompt, encoding="utf-8")
        artifacts.extend([str(prompt_path), str(stdout_path), str(stderr_path), str(last_message_path)])

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

    branch_layout = _ensure_initialize_branch_layout(req.repo_root)
    _emit_build_progress(
        req,
        "git bootstrap branch layout ready: "
        f"{branch_layout['primary_branch']} and {branch_layout['required_branch']} at {branch_layout['head'][:12]} "
        f"(current={branch_layout['current_branch']})",
    )

    publish_warnings, publish_artifacts, _publish_payload = _maybe_publish_private_repo_for_initialize(req)
    warnings.extend(publish_warnings)
    artifacts.extend(publish_artifacts)

    result = validate_git_bootstrap(
        repo_root=req.repo_root,
        required_branch=GIT_BOOTSTRAP_REQUIRED_BRANCH,
        require_readme=True,
        required_primary_branch=GIT_BOOTSTRAP_PRIMARY_BRANCH,
    )
    errors = result.get("errors")
    if not isinstance(errors, list):
        errors = []
    if errors:
        first = errors[0] if isinstance(errors[0], dict) else {}
        message = _as_str(first.get("message")) or "git bootstrap verification failed"
        _emit_build_progress(req, f"git bootstrap verification failed: {message}")
        raise OpError("git_bootstrap_failed", message, stage="initialize")

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
    return warnings, artifacts


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


def _source_meta(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": _as_str(source.get("mode")),
        "path": _as_str(source.get("path")),
        "display": _as_str(source.get("display")),
        "value": _as_str(source.get("value")),
    }


def _resolved_source_text(source: dict[str, Any]) -> str:
    mode = _as_str(source.get("mode")) or ""
    if mode == "inline":
        return _as_str(source.get("value")) or _as_str(source.get("display")) or ""
    if mode == "file":
        raw_path = _as_str(source.get("path"))
        if raw_path:
            path = Path(raw_path)
            try:
                return path.read_text(encoding="utf-8")
            except OSError:
                return _as_str(source.get("display")) or ""
    return _as_str(source.get("display")) or ""


def _resolve_strategy_manifest_path_for_request(req: OpRequest) -> Path:
    return strategy_runner.resolve_strategy_manifest_path(req.repo_root, req.strategy_manifest_file)


def _strategy_request_state(req: OpRequest, *, auto_optional: bool) -> dict[str, Any]:
    inline_manifest = _as_str(req.strategy_manifest)
    manifest_path = _resolve_strategy_manifest_path_for_request(req)
    explicit = bool(_as_str(req.strategy_manifest_file) or inline_manifest)
    exists = bool(inline_manifest) or manifest_path.exists()
    manifest_ref = strategy_runner.INLINE_STRATEGY_MANIFEST_LABEL if inline_manifest else str(manifest_path)
    manifest_mode = "inline" if inline_manifest else "file"
    if req.skip_strategy:
        return {
            "mode": "skipped",
            "reason": "skip_strategy_requested",
            "manifest_path": manifest_path if not inline_manifest else None,
            "manifest_ref": manifest_ref,
            "manifest_mode": manifest_mode,
            "explicit": explicit,
            "exists": exists,
            "should_run": False,
        }
    if inline_manifest:
        return {
            "mode": "ready",
            "reason": "manifest_inline",
            "manifest_path": None,
            "manifest_ref": manifest_ref,
            "manifest_mode": manifest_mode,
            "explicit": True,
            "exists": True,
            "should_run": True,
        }
    if exists:
        return {
            "mode": "ready",
            "reason": "manifest_present",
            "manifest_path": manifest_path,
            "manifest_ref": manifest_ref,
            "manifest_mode": manifest_mode,
            "explicit": explicit,
            "exists": True,
            "should_run": True,
        }
    if explicit or not auto_optional:
        return {
            "mode": "missing",
            "reason": "manifest_missing",
            "manifest_path": manifest_path,
            "manifest_ref": manifest_ref,
            "manifest_mode": manifest_mode,
            "explicit": explicit,
            "exists": False,
            "should_run": False,
        }
    return {
        "mode": "skipped",
        "reason": "manifest_missing",
        "manifest_path": manifest_path,
        "manifest_ref": manifest_ref,
        "manifest_mode": manifest_mode,
        "explicit": explicit,
        "exists": False,
        "should_run": False,
    }


def _run_strategy_command(req: OpRequest, *, auto_optional: bool) -> dict[str, Any]:
    strategy_state = _strategy_request_state(req, auto_optional=auto_optional)
    manifest_path = strategy_state["manifest_path"]
    manifest_ref = _as_str(strategy_state.get("manifest_ref")) or ""
    packet_path = req.repo_root / DEFAULT_STRATEGY_PACKET_MD_REL
    summary_path = req.repo_root / DEFAULT_STRATEGY_SUMMARY_MD_REL

    if strategy_state["mode"] == "skipped":
        reason = _as_str(strategy_state.get("reason")) or "skipped"
        summary = (
            "Strategy generation skipped because --skip-strategy was requested."
            if reason == "skip_strategy_requested"
            else "Strategy manifest not found; continuing without strategy."
        )
        return {
            "ok": True,
            "status": "skipped",
            "summary": summary,
            "warnings": [],
            "errors": [],
            "artifacts": [str(manifest_path)] if isinstance(manifest_path, Path) and manifest_path.exists() else [],
            "data": {
                "strategy": {
                    "status": "skipped",
                    "reason": reason,
                    "manifest_path": manifest_ref,
                    "packet_path": str(packet_path.resolve()),
                    "summary_path": str(summary_path.resolve()),
                }
            },
        }

    if strategy_state["mode"] == "missing":
        return {
            "ok": False,
            "status": "blocked_preflight",
            "summary": "Strategy generation blocked: manifest file is missing.",
            "warnings": [],
            "errors": [
                {
                    "code": "strategy_manifest_missing",
                    "message": f"strategy manifest does not exist: {manifest_ref}",
                    "stage": "strategy",
                }
            ],
            "artifacts": [],
            "data": {
                "strategy": {
                    "status": "missing",
                    "reason": "manifest_missing",
                    "manifest_path": manifest_ref,
                    "packet_path": str(packet_path.resolve()),
                    "summary_path": str(summary_path.resolve()),
                }
            },
        }

    try:
        result = strategy_runner.run_strategy(
            repo_root=req.repo_root,
            manifest=req.strategy_manifest,
            manifest_file=req.strategy_manifest_file,
            emit=lambda message: _emit_build_progress(replace(req, command="op-strategy"), message),
        )
    except strategy_runner.StrategyRunnerError as exc:
        return {
            "ok": False,
            "status": "failed",
            "summary": "Strategy generation failed.",
            "warnings": [],
            "errors": [
                {
                    "code": exc.code,
                    "message": exc.message,
                    "stage": "strategy",
                }
            ],
            "artifacts": [],
            "data": {
                "strategy": {
                    "status": "failed",
                    "reason": exc.code,
                    "manifest_path": manifest_ref,
                    "packet_path": str(packet_path.resolve()),
                    "summary_path": str(summary_path.resolve()),
                }
            },
        }

    return {
        "ok": True,
        "status": "completed",
        "summary": "Strategy artifacts generated.",
        "warnings": [],
        "errors": [],
        "artifacts": result.artifacts,
        "data": {
            "strategy": {
                "status": "completed",
                "reason": "manifest_present",
                "manifest_path": result.manifest_ref,
                "packet_path": str(result.packet_path),
                "summary_path": str(result.summary_path),
            }
        },
    }


def _existing_strategy_markdown_artifacts(repo_root: Path) -> list[str]:
    found: list[str] = []
    for rel in (DEFAULT_STRATEGY_PACKET_MD_REL, DEFAULT_STRATEGY_SUMMARY_MD_REL):
        path = _repo_path(repo_root, rel)
        if path.exists() and path.is_file():
            found.append(str(rel))
    return found


def _load_app_lifecycle_payload(repo_root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    path = _repo_path(repo_root, APP_LIFECYCLE_JSON)
    warnings: list[dict[str, Any]] = []
    payload: Any
    if path.exists():
        try:
            payload = _read_json(path)
        except OpError:
            payload = {}
            warnings.append(
                {
                    "code": "app_lifecycle_invalid_recovered",
                    "message": "app_lifecycle.json was invalid and has been reinitialized.",
                    "stage": "initialize",
                }
            )
    else:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
        warnings.append(
            {
                "code": "app_lifecycle_invalid_recovered",
                "message": "app_lifecycle.json was invalid and has been reinitialized.",
                "stage": "initialize",
            }
        )
    rows = payload.get("app_lifecycle")
    if not isinstance(rows, list):
        rows = []
    payload["schema_version"] = SCHEMA_VERSION
    payload["updated_at"] = utc_now_iso()
    payload["app_lifecycle"] = rows
    return payload, warnings


def _append_app_lifecycle_era(
    repo_root: Path,
    *,
    mission_source: dict[str, Any],
    scope_source: dict[str, Any],
    run_base_source_branch: str | None,
) -> tuple[str, Path, list[dict[str, Any]]]:
    payload, warnings = _load_app_lifecycle_payload(repo_root)
    rows = payload.get("app_lifecycle")
    assert isinstance(rows, list)
    started_at = utc_now_iso()
    era_id = f"era-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    rows.append(
        {
            "era_id": era_id,
            "status": "in_progress",
            "started_at": started_at,
            "completed_at": None,
            "mission": {
                "text": _resolved_source_text(mission_source),
                "source": _source_meta(mission_source),
            },
            "scope": {
                "text": _resolved_source_text(scope_source),
                "source": _source_meta(scope_source),
            },
            "run_context": {
                "initialized_at": started_at,
                "run_base_source_branch": _as_str(run_base_source_branch),
                "plan_id": None,
            },
            "completion": {},
        }
    )
    payload["updated_at"] = utc_now_iso()
    path = _repo_path(repo_root, APP_LIFECYCLE_JSON)
    _atomic_write_json(path, payload)
    return era_id, path, warnings


def _update_app_lifecycle_era_plan_id(repo_root: Path, *, era_id: str, plan_id: str | None) -> None:
    path = _repo_path(repo_root, APP_LIFECYCLE_JSON)
    try:
        payload = _read_json(path)
    except OpError:
        return
    if not isinstance(payload, dict):
        return
    rows = payload.get("app_lifecycle")
    if not isinstance(rows, list):
        return
    era_id_text = _as_str(era_id)
    if not era_id_text:
        return
    for row in rows:
        if not isinstance(row, dict):
            continue
        if _as_str(row.get("era_id")) != era_id_text:
            continue
        run_context = row.get("run_context")
        if not isinstance(run_context, dict):
            run_context = {}
            row["run_context"] = run_context
        run_context["plan_id"] = _as_str(plan_id)
        payload["updated_at"] = utc_now_iso()
        _atomic_write_json(path, payload)
        return


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


def _planner_prompt_template_candidates(repo_root: Path) -> list[Path]:
    candidates = [
        repo_root / "scripts" / "op" / "planner" / "prompts" / "llm_plan_prompt.md",
        PLANNER_PROMPT_TEMPLATE_PATH,
    ]
    deduped: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(path)
    return deduped


def _planner_prompt_template_path(repo_root: Path) -> Path:
    candidates = _planner_prompt_template_candidates(repo_root)
    for path in candidates:
        if path.exists():
            return path.resolve()
    return candidates[0].resolve()


def _planner_prompt_text(
    *,
    req: OpRequest,
    bundle_path: Path,
    mission_source: dict[str, Any],
    scope_source: dict[str, Any],
    prior_errors: list[dict[str, Any]],
) -> str:
    template_path = _planner_prompt_template_path(req.repo_root)
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
    strategy_note = strategy_runner.build_planner_strategy_note(skip_strategy=req.skip_strategy)
    if strategy_note:
        prompt += "\n\n" + strategy_note
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
    _planner_alias, planner_codex_home = _select_planner_profile_from_rate_registry(req.repo_root, stage="plan")
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
        emit_op_event_trace(
            event_name="op.plan.planner_attempt.start",
            run_type="llm",
            payload={
                "command": req.command,
                "repo_root": str(req.repo_root),
                "attempt": attempt,
                "started_at": started_at,
                "bundle_path": str(bundle_path),
                "prompt_path": str(prompt_path),
                "prompt_preview": prompt,
                "model": "codex exec",
                "skip_strategy": req.skip_strategy,
                "executor_provider": req.executor_provider,
            },
        )
        try:
            exit_code = run_codex_exec(
                repo_root=req.repo_root,
                prompt_text=prompt,
                output_last_message=last_message_path,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                codex_home=planner_codex_home,
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
            emit_op_event_trace(
                event_name="op.plan.planner_attempt.error",
                run_type="llm",
                payload={
                    "command": req.command,
                    "repo_root": str(req.repo_root),
                    "attempt": attempt,
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "bundle_path": str(bundle_path),
                    "prompt_path": str(prompt_path),
                    "status": "failed",
                    "errors": [error_row],
                    "model": "codex exec",
                    "skip_strategy": req.skip_strategy,
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
        emit_op_event_trace(
            event_name="op.plan.planner_attempt.result",
            run_type="llm",
            payload={
                "command": req.command,
                "repo_root": str(req.repo_root),
                "attempt": attempt,
                "started_at": started_at,
                "finished_at": finished_at,
                "bundle_path": str(bundle_path),
                "prompt_path": str(prompt_path),
                "llm_stdout_ref": str(stdout_path),
                "llm_stderr_ref": str(stderr_path),
                "last_message_ref": str(last_message_path),
                "parse_ok": parse_ok,
                "schema_ok": schema_ok,
                "plan_check_ok": plan_check_ok,
                "status": "passed" if final_validation else "failed",
                "exit_code": exit_code,
                "errors": validation_errors,
                "model": "codex exec",
                "skip_strategy": req.skip_strategy,
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


def command_strategy(req: OpRequest) -> dict[str, Any]:
    result = _run_strategy_command(req, auto_optional=False)
    return _response(
        req,
        ok=bool(result.get("ok")),
        status=_as_str(result.get("status")) or ("completed" if result.get("ok") else "failed"),
        summary=_as_str(result.get("summary")) or "Strategy command finished.",
        warnings=result.get("warnings") if isinstance(result.get("warnings"), list) else [],
        errors=result.get("errors") if isinstance(result.get("errors"), list) else [],
        artifacts=result.get("artifacts") if isinstance(result.get("artifacts"), list) else [],
        next_action=_as_str(result.get("next_action")),
        state_ref=_as_str(result.get("state_ref")),
        data=result.get("data") if isinstance(result.get("data"), dict) else None,
    )

def command_initialize(req: OpRequest) -> dict[str, Any]:
    _require_override_if_existing_plan(req, stage="initialize")
    mission_source, scope_source = _resolve_mission_scope_sources(req, stage="initialize", required=True)
    git_bootstrap_warnings, git_bootstrap_artifacts = _ensure_git_initialized_for_initialize(req)
    _ensure_managed_gitignore_block(req.repo_root)
    strategy_result = _run_strategy_command(req, auto_optional=True)
    strategy_warnings = strategy_result.get("warnings") if isinstance(strategy_result.get("warnings"), list) else []
    strategy_errors = strategy_result.get("errors") if isinstance(strategy_result.get("errors"), list) else []
    strategy_artifacts = strategy_result.get("artifacts") if isinstance(strategy_result.get("artifacts"), list) else []
    strategy_data = strategy_result.get("data") if isinstance(strategy_result.get("data"), dict) else None
    if not bool(strategy_result.get("ok")):
        return _response(
            req,
            ok=False,
            status=_as_str(strategy_result.get("status")) or "failed",
            summary=_as_str(strategy_result.get("summary")) or "Initialization blocked by strategy preflight.",
            warnings=strategy_warnings,
            errors=strategy_errors,
            artifacts=strategy_artifacts,
            next_action="Add the requested strategy manifest file or rerun with --skip-strategy.",
            data=strategy_data,
        )
    strategy_state = strategy_data.get("strategy") if isinstance(strategy_data, dict) else {}
    if (
        isinstance(strategy_state, dict)
        and _as_str(strategy_state.get("status")) == "skipped"
        and _as_str(strategy_state.get("reason")) == "manifest_missing"
        and not req.skip_strategy
    ):
        existing_strategy_artifacts = _existing_strategy_markdown_artifacts(req.repo_root)
        if existing_strategy_artifacts:
            warning = {
                "code": "strategy_artifacts_present_without_regeneration",
                "message": (
                    "Strategy manifest was not found, so strategy was not regenerated. "
                    "Existing strategy artifacts are still present and will be available to planner."
                ),
                "stage": "initialize",
                "artifacts": existing_strategy_artifacts,
            }
            strategy_warnings.append(warning)
            _emit_build_progress(
                replace(req, command="op-plan"),
                "strategy manifest not found; existing strategy artifacts will still be considered by planner: "
                + ", ".join(existing_strategy_artifacts),
            )

    map_result = command_map_codebase(req)
    new_result = command_new_project(req)
    lifecycle_era_id, lifecycle_path, lifecycle_warnings = _append_app_lifecycle_era(
        req.repo_root,
        mission_source=mission_source,
        scope_source=scope_source,
        run_base_source_branch=req.run_base_source_branch,
    )

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

    rate_seed_warnings = _seed_rate_registry_if_missing(
        req.repo_root,
        stage="initialize",
        profile_selection=profile_selection,
    )

    plan_result = command_plan(req)
    _update_app_lifecycle_era_plan_id(
        req.repo_root,
        era_id=lifecycle_era_id,
        plan_id=_as_str((plan_result.get("data") or {}).get("plan_id")),
    )
    state_payload = _read_json(state_path)
    if not isinstance(state_payload, dict):
        raise OpError("state_payload_invalid", "STATE.json must be a JSON object", stage="initialize")
    state_payload["profile_aliases"] = list(profile_selection.get("selected_aliases", []))
    state_payload["profile_selection_ref"] = str(profile_selection_path)
    state_payload["updated_at"] = utc_now_iso()
    _atomic_write_json(state_path, state_payload)

    artifacts = []
    artifacts.extend(git_bootstrap_artifacts)
    artifacts.extend(strategy_artifacts)
    artifacts.extend(map_result.get("artifacts", []))
    artifacts.extend(new_result.get("artifacts", []))
    artifacts.extend(plan_result.get("artifacts", []))
    artifacts.append(str(profile_selection_path))
    artifacts.append(str(state_path))
    artifacts.append(str(lifecycle_path))

    warnings = []
    warnings.extend(git_bootstrap_warnings)
    warnings.extend(strategy_warnings)
    warnings.extend(map_result.get("warnings", []))
    warnings.extend(rate_seed_warnings)
    warnings.extend(new_result.get("warnings", []))
    warnings.extend(plan_result.get("warnings", []))
    warnings.extend(lifecycle_warnings)

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
        data=_merge_response_data(
            {
                "plan_ready": plan_ready,
                "profile_aliases": profile_selection.get("selected_aliases", []),
            },
            strategy_data,
        ),
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
        "dead_pid_retry_counts": {},
        "artifact_fan_in_enabled": False,
        "artifact_fan_in": {
            "last_sync_at": None,
            "worktrees_scanned": 0,
            "evidence_files_synced": 0,
            "handoff_rows_synced": 0,
        },
        "last_dead_pid_recovery": {},
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
    payload.setdefault("dead_pid_retry_counts", {})
    payload.setdefault("artifact_fan_in_enabled", False)
    payload.setdefault(
        "artifact_fan_in",
        {
            "last_sync_at": None,
            "worktrees_scanned": 0,
            "evidence_files_synced": 0,
            "handoff_rows_synced": 0,
        },
    )
    payload.setdefault("last_dead_pid_recovery", {})
    if not isinstance(payload.get("slot_resume_policy"), dict):
        payload["slot_resume_policy"] = {}
    if not isinstance(payload.get("resume_fail_counts_by_slot"), dict):
        payload["resume_fail_counts_by_slot"] = {}
    if not isinstance(payload.get("last_dispatch_cycle_summary"), dict):
        payload["last_dispatch_cycle_summary"] = {}
    if not isinstance(payload.get("dead_pid_retry_counts"), dict):
        payload["dead_pid_retry_counts"] = {}
    if not isinstance(payload.get("artifact_fan_in_enabled"), bool):
        payload["artifact_fan_in_enabled"] = False
    if not isinstance(payload.get("artifact_fan_in"), dict):
        payload["artifact_fan_in"] = {
            "last_sync_at": None,
            "worktrees_scanned": 0,
            "evidence_files_synced": 0,
            "handoff_rows_synced": 0,
        }
    if not isinstance(payload.get("last_dead_pid_recovery"), dict):
        payload["last_dead_pid_recovery"] = {}
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


def _sync_build_state_from_simple_result(repo_root: Path, result: dict[str, Any]) -> None:
    build_state_path = _repo_path(repo_root, BUILD_STATE_JSON)
    if not build_state_path.exists():
        return
    try:
        build_state = _load_build_state(build_state_path)
    except OpError:
        return

    data = result.get("data") if isinstance(result, dict) and isinstance(result.get("data"), dict) else {}
    stop_reason = _as_str(data.get("stop_reason"))
    current_terminal_state = _as_str(build_state.get("terminal_state"))
    rate_gate_state = build_state.get("rate_gate_state") if isinstance(build_state.get("rate_gate_state"), dict) else {}
    changed = False

    if stop_reason == "all_rate_gates_blocking":
        control_path = repo_root / "reports" / "optimus-prime" / "control" / "ALL_RATE_GATES_BLOCKING.json"
        soonest_reset_at = None
        if control_path.exists():
            try:
                payload = _read_json(control_path)
            except OpError:
                payload = None
            if isinstance(payload, dict):
                soonest_reset_at = _as_str(payload.get("soonest_reset_at")) or None
        build_state["terminal_state"] = "all_rate_gates_blocking"
        build_state["updated_at"] = utc_now_iso()
        build_state["rate_gate_state"] = {
            "hard_gated": True,
            "min_reset_at": soonest_reset_at,
            "sleep_until": None,
            "manual_rerun_required": False,
        }
        cycle_gate = build_state.get("cycle_gate_decision") if isinstance(build_state.get("cycle_gate_decision"), dict) else {}
        cycle_gate["terminal_reason"] = "all_rate_gates_blocking"
        build_state["cycle_gate_decision"] = cycle_gate
        changed = True
    elif current_terminal_state == "all_rate_gates_blocking":
        build_state["terminal_state"] = None
        build_state["updated_at"] = utc_now_iso()
        rate_gate_state["hard_gated"] = False
        rate_gate_state["min_reset_at"] = None
        rate_gate_state["sleep_until"] = None
        rate_gate_state["manual_rerun_required"] = False
        build_state["rate_gate_state"] = rate_gate_state
        cycle_gate = build_state.get("cycle_gate_decision") if isinstance(build_state.get("cycle_gate_decision"), dict) else {}
        if _as_str(cycle_gate.get("terminal_reason")) == "all_rate_gates_blocking":
            cycle_gate["terminal_reason"] = None
        build_state["cycle_gate_decision"] = cycle_gate
        changed = True

    if changed:
        _atomic_write_json(build_state_path, build_state)


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

    emit_op_event_trace(
        event_name="op.build.controller_cycle.start",
        run_type="tool",
        payload={
            "command": req.command,
            "repo_root": str(req.repo_root),
            "control_number": int(control_number),
            "control_run_id": control_run_id,
            "profile_aliases": profile_aliases or ["codex"],
            "sleep_minutes": req.sleep_minutes,
            "dry_run": req.dry_run,
        },
    )
    code, out, err = _run([sys.executable, str(script), "--input-json", "-"], cwd=req.repo_root, stdin_text=json.dumps(payload))
    raw = out.strip()
    if not raw:
        emit_op_event_trace(
            event_name="op.build.controller_cycle.error",
            run_type="tool",
            payload={
                "command": req.command,
                "repo_root": str(req.repo_root),
                "control_number": int(control_number),
                "control_run_id": control_run_id,
                "status": "failed",
                "errors": [{"code": "empty_output", "message": err.strip()}],
                "exit_code": code,
            },
        )
        raise OpError("runtime_error", f"controller returned empty output (stderr={err.strip()})", stage="build")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        emit_op_event_trace(
            event_name="op.build.controller_cycle.error",
            run_type="tool",
            payload={
                "command": req.command,
                "repo_root": str(req.repo_root),
                "control_number": int(control_number),
                "control_run_id": control_run_id,
                "status": "failed",
                "errors": [{"code": "invalid_json", "message": str(exc)}],
                "exit_code": code,
            },
        )
        raise OpError("runtime_error", f"controller output is not valid JSON: {exc}", stage="build") from exc

    if code not in {0, 1}:
        emit_op_event_trace(
            event_name="op.build.controller_cycle.error",
            run_type="tool",
            payload={
                "command": req.command,
                "repo_root": str(req.repo_root),
                "control_number": int(control_number),
                "control_run_id": control_run_id,
                "status": "failed",
                "errors": [{"code": "unexpected_exit", "message": err.strip() or raw}],
                "exit_code": code,
            },
        )
        raise OpError(
            "runtime_error",
            f"controller returned unexpected exit code {code}: {err.strip() or raw}",
            stage="build",
        )
    if not isinstance(parsed, dict):
        emit_op_event_trace(
            event_name="op.build.controller_cycle.error",
            run_type="tool",
            payload={
                "command": req.command,
                "repo_root": str(req.repo_root),
                "control_number": int(control_number),
                "control_run_id": control_run_id,
                "status": "failed",
                "errors": [{"code": "non_object_output", "message": "controller output must be object JSON"}],
                "exit_code": code,
            },
        )
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
    emit_op_event_trace(
        event_name="op.build.controller_cycle.result",
        run_type="tool",
        payload={
            "command": req.command,
            "repo_root": str(req.repo_root),
            "control_number": int(control_number),
            "control_run_id": control_run_id,
            "status": _as_str(parsed.get("status")) or "completed",
            "ok": bool(parsed.get("ok", code == 0)),
            "exit_code": code,
            "result": parsed,
        },
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

        result = _normalize_handoff_result(_as_str(row.get("result")) or _as_str(row.get("status")))
        if result in {"blocked", "failed", "error", "dispatch_failed"}:
            reason_codes = [
                code
                for code in (_as_str(item) for item in (row.get("reason_codes") if isinstance(row.get("reason_codes"), list) else []))
                if code
            ]
            task["last_handoff_outcome"] = {
                "status": result,
                "reason_codes": reason_codes,
                "timestamp": utc_now_iso(),
            }
            warnings.append(
                {
                    "code": "handoff_non_authoritative_state_only",
                    "message": f"handoff reported blocked result for {task_id}; task status will be decided by evidence contract",
                    "stage": "build_loop",
                    "task_id": task_id,
                    "reason_codes": reason_codes,
                }
            )
        else:
            task["last_handoff_outcome"] = {
                "status": result or None,
                "reason_codes": [],
                "timestamp": utc_now_iso(),
            }
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
    run_id: str | None = None,
    is_gapfix: bool = False,
    gap_batch_id: str | None = None,
    gap_batch_ref: str | None = None,
    source_gap_ids: list[str] | None = None,
    gap_stage: str | None = None,
) -> dict[str, Any]:
    # LLM interaction classification: reasoning_effort=high_effort, tooling_effort=medium_tooling.
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
    contract = _task_verification_contract(task, plan_task)
    stage_expectation = _expected_for_stage(contract, stage)
    cfg = stage_cfg[stage]
    slot_name = slot_override or cfg["slot"]
    start_from_branch = _as_str(start_from_branch_override) or "RAB-BASE"
    start_from_commit = _as_str(start_from_commit_override)
    if not start_from_commit:
        start_from_commit = _git_text(req.repo_root, "rev-parse", start_from_branch)
    if not start_from_commit:
        start_from_commit = _git_text(req.repo_root, "rev-parse", "HEAD") or "HEAD"
    worktree_root = worktree_root_override or str(req.repo_root)
    branch_name = branch_name_override or _branch_name_for_stage(slot_name, task_id, stage, run_id=run_id)
    executor_provider = (_as_str(getattr(req, "executor_provider", None)) or "codex").lower()
    executor_model = _as_str(getattr(req, "executor_model", None))
    blackbox_lane = (_as_str(getattr(req, "blackbox_lane", None)) or "free").lower()
    if _as_bool(getattr(req, "allow_worker_executor_override", False), default=False):
        provider_override = (_as_str(task.get("next_task_provider")) or "").lower()
        model_override = _as_str(task.get("next_task_model"))
        if provider_override:
            if provider_override in {"codex", "openrouter", "blackbox"}:
                executor_provider = provider_override
            else:
                dispatch_warnings.append(
                    {
                        "code": "dispatch_executor_override_invalid",
                        "message": (
                            f"invalid next_task_provider override '{provider_override}' for {task_id}; "
                            f"using build executor '{executor_provider}'"
                        ),
                        "stage": "build_loop",
                        "task_id": task_id,
                    }
                )
        if model_override:
            executor_model = model_override
    payload = {
        "slot": slot_name,
        "role": cfg["role"],
        "task_identifier": task_id,
        "task_kind": _task_kind(task, plan_task),
        "repo_root": str(req.repo_root),
        "worktree_root": worktree_root,
        "branch_name": branch_name,
        "start_from_branch": start_from_branch,
        "start_from_commit": start_from_commit,
        "acceptance_criteria": acceptance_refs,
        "packet_version": 1,
        "codex_profile_alias": codex_profile_alias,
        "executor_provider": executor_provider,
        "executor_model": executor_model,
        "blackbox_lane": blackbox_lane,
        "mcp_mode": "enable-only",
        "mcp_allowlist": ["figma"],
        "sandbox_mode": "danger-full-access",
        "sandbox_add_dirs": [],
        "test_train_mode": "off",
        "op_build_mode": True,
        "plan_id": plan_id,
        "phase_id": _as_str(task.get("phase_id")) or _as_str(plan_task.get("phase_id")) or "phase-1",
        "requirement_ids": requirement_ids,
        "task_acceptance_refs": acceptance_refs,
        "dev_ready_evidence_ref": evidence_ref,
        "verification_contract": contract,
        "stage_expectation": stage_expectation,
        "expected_failure_reason_codes": contract.get("expected_failure_reason_codes", []),
        "infra_failure_reason_codes": contract.get("infra_failure_reason_codes", []),
        "dispatch_mode": dispatch_mode,
        "resume_thread_id": resume_thread_id,
        "lane_id": lane_id,
        "test_source_branch": _as_str(test_source_branch_override) or None,
        "test_source_commit": _as_str(test_source_commit_override) or None,
        "is_gapfix": bool(is_gapfix),
        "gap_batch_id": _as_str(gap_batch_id) or None,
        "gap_batch_ref": _as_str(gap_batch_ref) or None,
        "gap_stage": (_as_str(gap_stage) or "").lower() or None,
        "source_gap_ids": [
            gap_id for gap_id in (_as_str(item) for item in (source_gap_ids or [])) if gap_id
        ],
        "dry_run": req.dry_run,
        "cycle_note": f"/op-build:{stage}:{task_id}",
    }
    emit_op_event_trace(
        event_name="op.build.dispatch.start",
        run_type="tool",
        payload={
            "command": req.command,
            "repo_root": str(req.repo_root),
            "task_id": task_id,
            "stage": stage,
            "plan_id": plan_id,
            "phase_id": payload.get("phase_id"),
            "lane_id": lane_id,
            "slot": slot_name,
            "role": cfg["role"],
            "dispatch_mode": dispatch_mode,
            "executor_provider": executor_provider,
            "executor_model": executor_model,
            "branch_name": branch_name,
            "worktree_root": worktree_root,
            "dry_run": req.dry_run,
        },
    )
    result = _run_tool_json(script, payload, req.repo_root)
    if _as_bool_field(result.get("ok")):
        if stage in {"test", "review"}:
            _clear_active_gapfix_state(task)
        task["status"] = cfg["status"]
        task["owner_slot"] = slot_name
        if lane_id:
            task["lane_id"] = lane_id
        task["dispatch_thread_id"] = _as_str(result.get("dispatch_thread_id")) or _as_str(
            (result.get("dispatch") or {}).get("dispatch_thread_id")
        )
        task["last_dispatch"] = {
            "stage": stage,
            "role": cfg["role"],
            "branch_name": _as_str(payload.get("branch_name")) or None,
            "start_from_commit": _as_str(payload.get("start_from_commit")) or None,
            "start_from_branch": _as_str(payload.get("start_from_branch")) or None,
            "dispatched_at": utc_now_iso(),
        }
        task["active_branch"] = _as_str(payload.get("branch_name"))
        if stage == "dev":
            task["developer_branch"] = _as_str(payload.get("branch_name"))
        else:
            source_branch_for_stage = _as_str(start_from_branch_override)
            if re.match(r"^codex/[^/]+/dev-[^/]+/", source_branch_for_stage) and not _as_str(task.get("developer_branch")):
                task["developer_branch"] = source_branch_for_stage
        task["last_progress_at"] = utc_now_iso()
        attempts = task.get("attempts")
        if not isinstance(attempts, dict):
            attempts = {"dev": 0, "test": 0, "review": 0}
            task["attempts"] = attempts
        attempts[cfg["attempt_key"]] = int(attempts.get(cfg["attempt_key"], 0)) + 1
        out = {"ok": True, "task_id": task_id, "stage": stage, "dispatch": result}
        if dispatch_warnings:
            out["warnings"] = dispatch_warnings
        emit_op_event_trace(
            event_name="op.build.dispatch.result",
            run_type="tool",
            payload={
                "command": req.command,
                "repo_root": str(req.repo_root),
                "task_id": task_id,
                "stage": stage,
                "plan_id": plan_id,
                "phase_id": payload.get("phase_id"),
                "lane_id": lane_id,
                "slot": slot_name,
                "role": cfg["role"],
                "dispatch_mode": dispatch_mode,
                "executor_provider": executor_provider,
                "executor_model": executor_model,
                "status": "dispatched",
                "ok": True,
                "dispatch": result,
                "warnings": dispatch_warnings,
            },
        )
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
    emit_op_event_trace(
        event_name="op.build.dispatch.result",
        run_type="tool",
        payload={
            "command": req.command,
            "repo_root": str(req.repo_root),
            "task_id": task_id,
            "stage": stage,
            "plan_id": plan_id,
            "phase_id": payload.get("phase_id"),
            "lane_id": lane_id,
            "slot": slot_name,
            "role": cfg["role"],
            "dispatch_mode": dispatch_mode,
            "executor_provider": executor_provider,
            "executor_model": executor_model,
            "status": "failed",
            "ok": False,
            "dispatch": result,
            "warnings": dispatch_warnings,
        },
    )
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
        is_gapfix = _as_bool_field(row.get("is_gapfix"))
        gap_batch_id = _as_str(row.get("gap_batch_id"))
        gap_batch_ref = _as_str(row.get("gap_batch_ref"))
        gap_stage = (_as_str(row.get("gap_stage")) or "").lower() or None
        source_gap_ids_raw = row.get("source_gap_ids")
        source_gap_ids = (
            [item for item in (_as_str(v) for v in source_gap_ids_raw) if item]
            if isinstance(source_gap_ids_raw, list)
            else []
        )
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
        if is_gapfix:
            if not gap_batch_id:
                warnings.append(
                    {
                        "code": "dispatch_assignment_invalid",
                        "message": f"assignment #{idx + 1} gapfix row missing gap_batch_id",
                        "stage": "build_loop",
                        "artifact": str(path),
                        "index": idx,
                    }
                )
                continue
            if gap_stage not in {"dev", "test", "review"}:
                warnings.append(
                    {
                        "code": "dispatch_assignment_invalid",
                        "message": f"assignment #{idx + 1} gapfix row has invalid gap_stage={gap_stage}",
                        "stage": "build_loop",
                        "artifact": str(path),
                        "index": idx,
                    }
                )
                continue
            if not gap_batch_ref:
                warnings.append(
                    {
                        "code": "dispatch_assignment_invalid",
                        "message": f"assignment #{idx + 1} gapfix row missing gap_batch_ref",
                        "stage": "build_loop",
                        "artifact": str(path),
                        "index": idx,
                    }
                )
                continue
            gap_batch_path = Path(gap_batch_ref).expanduser()
            if not gap_batch_path.is_absolute():
                gap_batch_path = repo_root / gap_batch_path
            if not gap_batch_path.exists():
                warnings.append(
                    {
                        "code": "dispatch_assignment_invalid",
                        "message": f"assignment #{idx + 1} gapfix row references missing gap_batch_ref={gap_batch_ref}",
                        "stage": "build_loop",
                        "artifact": str(path),
                        "index": idx,
                    }
                )
                continue
            gap_batch_ref = str(gap_batch_path.resolve())
            if not source_gap_ids:
                warnings.append(
                    {
                        "code": "dispatch_assignment_invalid",
                        "message": f"assignment #{idx + 1} gapfix row missing source_gap_ids",
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
                "is_gapfix": is_gapfix,
                "gap_batch_id": gap_batch_id,
                "gap_batch_ref": gap_batch_ref,
                "gap_stage": gap_stage,
                "source_gap_ids": source_gap_ids,
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
    workstation_registry = _load_workstation_registry(_repo_path(req.repo_root, WORKSTATION_REGISTRY_JSON))
    workstation_rows = (
        workstation_registry.get("slots")
        if isinstance(workstation_registry.get("slots"), dict)
        else {}
    )
    slot_count = len(FIXED_WORKER_SLOTS)
    plan_id = _as_str(plan_packets.get("plan_id")) or "plan-unknown"
    stage_status_requirements = {
        "dev": {TASK_STATUS_PENDING, TASK_STATUS_BLOCKED},
        "test": {TASK_STATUS_PENDING, TASK_STATUS_BLOCKED},
        "review": {TASK_STATUS_PENDING, TASK_STATUS_BLOCKED},
    }
    run_id = _run_id_from_lock_id(_as_str(build_state.get("loop_lock_id")))
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
        dispatch_pid: int | None = None,
        dispatch_log: str | None = None,
        branch_name: str | None,
        worktree_root: str | None,
    ) -> None:
        row = workers_by_slot.get(slot_name)
        if not isinstance(row, dict):
            row = _default_worker_row(slot_name, run_id=run_id)
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
        row["dispatch_started_at"] = row["updated_at"]
        if _as_str(dispatch_mode_used):
            row["dispatch_mode"] = _as_str(dispatch_mode_used)
        if isinstance(dispatch_pid, int) and dispatch_pid > 0:
            row["dispatch_pid"] = dispatch_pid
        if _as_str(dispatch_log):
            row["dispatch_log"] = _as_str(dispatch_log)
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
                "is_gapfix": _as_bool_field(row.get("is_gapfix")),
                "gap_batch_id": _as_str(row.get("gap_batch_id")),
                "gap_batch_ref": _as_str(row.get("gap_batch_ref")),
                "gap_stage": _as_str(row.get("gap_stage")),
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
        is_gapfix = _as_bool_field(row.get("is_gapfix"))
        gap_batch_id = _as_str(row.get("gap_batch_id"))
        gap_batch_ref = _as_str(row.get("gap_batch_ref"))
        gap_stage = (_as_str(row.get("gap_stage")) or "").lower() or None
        source_gap_ids = [
            gap_id
            for gap_id in (_as_str(item) for item in (row.get("source_gap_ids") if isinstance(row.get("source_gap_ids"), list) else []))
            if gap_id
        ]
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
        expected_stage = _dispatch_stage_for_task(task, plan_task)
        if not is_gapfix and next_stage != expected_stage:
            _record_assignment_observation(
                row=row,
                status="skipped",
                reason_code="dispatch_assignment_task_kind_stage_mismatch",
                started_at=started,
                warning_codes=["dispatch_assignment_task_kind_stage_mismatch"],
            )
            all_warnings.append(
                {
                    "code": "dispatch_assignment_task_kind_stage_mismatch",
                    "message": (
                        f"assignment stage {next_stage} does not match task_kind dispatch stage "
                        f"{expected_stage} for {task_id}"
                    ),
                    "stage": "build_loop",
                    "task_id": task_id,
                    "expected_stage": expected_stage,
                    "task_kind": _task_kind(task, plan_task),
                }
            )
            continue
        allowed_statuses = stage_status_requirements[next_stage]
        if is_gapfix and next_stage == "dev":
            allowed_statuses = {
                TASK_STATUS_PENDING,
                TASK_STATUS_DEV_DONE,
                TASK_STATUS_TESTS_DONE,
                TASK_STATUS_REVIEW_DONE,
                TASK_STATUS_BLOCKED,
            }
        if status not in allowed_statuses:
            _record_assignment_observation(
                row=row,
                status="skipped",
                reason_code="dispatch_assignment_stage_not_ready",
                started_at=started,
            )
            continue

        slot_worker = workers_by_slot.get(slot_name) if isinstance(workers_by_slot.get(slot_name), dict) else {}
        workstation_row = (
            workstation_rows.get(slot_name)
            if isinstance(workstation_rows.get(slot_name), dict)
            else None
        )
        if isinstance(workstation_row, dict):
            ws_status = (_as_str(workstation_row.get("status")) or "").lower()
            ws_task_id = _as_str(workstation_row.get("target_task_id"))
            ws_lane_id = _as_str(workstation_row.get("target_lane_id"))
            if (ws_task_id and ws_task_id != task_id) or (ws_lane_id and ws_lane_id != lane_id) or ws_status != "ready":
                _record_assignment_observation(
                    row=row,
                    status="skipped",
                    reason_code="dispatch_assignment_workstation_not_ready",
                    started_at=started,
                    warning_codes=["dispatch_assignment_workstation_not_ready"],
                )
                all_warnings.append(
                    {
                        "code": "dispatch_assignment_workstation_not_ready",
                        "message": (
                            f"slot {slot_name} workstation not ready for assignment "
                            f"(status={ws_status or 'unknown'}, target_task={ws_task_id or '-'}, target_lane={ws_lane_id or '-'})"
                        ),
                        "stage": "build_loop",
                        "task_id": task_id,
                        "slot": slot_name,
                    }
                )
                continue
        worktree_root = _as_str(slot_worker.get("worktree_root"))
        branch_name = _as_str(slot_worker.get("branch"))
        if isinstance(workstation_row, dict):
            worktree_root = _as_str(workstation_row.get("target_worktree_root")) or worktree_root
            branch_name = _as_str(workstation_row.get("target_branch")) or branch_name
        if not worktree_root or not branch_name:
            if req.dry_run:
                worktree_root = str(req.repo_root)
                branch_name = _branch_name_for_stage(slot_name, task_id, next_stage, run_id=run_id)
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
        if is_gapfix and next_stage == "dev":
            dev_branch = _developer_source_branch(task)
            if dev_branch:
                branch_name = dev_branch
                start_from_branch_override = dev_branch
                start_from_commit_override = _git_text(req.repo_root, "rev-parse", dev_branch)
            elif gap_stage in {"test", "review"}:
                all_warnings.append(
                    {
                        "code": "dispatch_assignment_missing_dev_branch",
                        "message": (
                            f"gapfix assignment for {task_id} requires existing developer branch "
                            f"(gap_stage={gap_stage})"
                        ),
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
        if next_stage in {"test", "review"}:
            expected_stage = _dispatch_stage_for_task(task, plan_task)
            source_branch: str | None
            source_commit: str | None
            if next_stage == expected_stage:
                source_branch = _lane_base_branch_for_task(plan_packets, task, plan_task) or "RAB-BASE"
                source_commit = _git_text(req.repo_root, "rev-parse", source_branch)
            else:
                source_branch = _developer_source_branch(task)
                if not source_branch:
                    all_warnings.append(
                        {
                            "code": "dispatch_assignment_missing_dev_branch",
                            "message": (
                                f"task {task_id} missing developer source branch "
                                f"for {next_stage}-stage dispatch"
                            ),
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
                        "message": (
                            f"unable to resolve HEAD commit for source branch {source_branch or 'unknown'}"
                        ),
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
            start_from_branch_override = source_branch or "RAB-BASE"
            start_from_commit_override = source_commit
            branch_name = _branch_name_for_stage(slot_name, task_id, next_stage, run_id=run_id)
            if next_stage == "test":
                test_source_branch_override = source_branch
                test_source_commit_override = source_commit

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
            run_id=run_id,
            is_gapfix=is_gapfix,
            gap_batch_id=gap_batch_id,
            gap_batch_ref=gap_batch_ref,
            source_gap_ids=source_gap_ids,
            gap_stage=gap_stage,
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
                dispatch_pid=dispatch_payload.get("pid") if isinstance(dispatch_payload.get("pid"), int) else None,
                dispatch_log=_as_str(dispatch_payload.get("dispatch_log")),
                branch_name=branch_name,
                worktree_root=worktree_root,
            )
            _mark_task_watchdog_started(task, build_state)
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
        if _is_refresh_token_reused_unauthorized({"result": result, "warnings": warning_rows}):
            block_warning = _set_profile_permanent_block(
                req.repo_root,
                alias=selected_alias,
                reason_code="refresh_token_reused",
                stage="build_loop",
            )
            if isinstance(block_warning, dict):
                all_warnings.append(block_warning)
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
    run_id = _run_id_from_lock_id(_as_str(build_state.get("loop_lock_id")))

    def _persist_worker_slot_transition(
        *,
        slot_name: str,
        lane_value: str | None,
        active_task_id: str | None,
        dispatch_thread_id: str | None,
        dispatch_mode_used: str | None,
        dispatch_pid: int | None = None,
        dispatch_log: str | None = None,
    ) -> None:
        row = workers_by_slot.get(slot_name)
        if not isinstance(row, dict):
            row = _default_worker_row(slot_name, run_id=run_id)
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
        if isinstance(dispatch_pid, int) and dispatch_pid > 0:
            row["dispatch_pid"] = dispatch_pid
        if _as_str(dispatch_log):
            row["dispatch_log"] = _as_str(dispatch_log)
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
        branch_name_override: str | None = None
        if stage_name in {"test", "review"}:
            expected_stage = _dispatch_stage_for_task(task_payload, plan_task_payload)
            if stage_name == expected_stage:
                source_branch = _lane_base_branch_for_task(plan_packets, task_payload, plan_task_payload) or "RAB-BASE"
            else:
                source_branch = _developer_source_branch(task_payload)
                if not source_branch:
                    return {
                        "ok": True,
                        "status": "skipped",
                        "reason": "dispatch_assignment_missing_dev_branch",
                        "warning": {
                            "code": "dispatch_assignment_missing_dev_branch",
                            "message": (
                                f"task {_as_str(task_payload.get('task_id')) or 'TASK-UNKNOWN'} "
                                f"missing developer source branch for {stage_name}-stage dispatch"
                            ),
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
                        "message": f"unable to resolve HEAD commit for source branch {source_branch}",
                        "stage": "build_loop",
                    },
                }
            start_from_branch_override = source_branch
            start_from_commit_override = source_commit
            branch_name_override = _branch_name_for_stage(
                slot_name,
                _as_str(task_payload.get("task_id")) or "TASK-UNKNOWN",
                stage_name,
                run_id=run_id,
            )
            if stage_name == "test":
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
            branch_name_override=branch_name_override,
            start_from_branch_override=start_from_branch_override,
            start_from_commit_override=start_from_commit_override,
            test_source_branch_override=test_source_branch_override,
            test_source_commit_override=test_source_commit_override,
            run_id=run_id,
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
                dispatch_pid=dispatch_payload.get("pid") if isinstance(dispatch_payload.get("pid"), int) else None,
                dispatch_log=_as_str(dispatch_payload.get("dispatch_log")),
            )
            _mark_task_watchdog_started(task_payload, build_state)
        selection_warning = selection.get("warning")
        if isinstance(selection_warning, dict):
            warning_rows = result.get("warnings") if isinstance(result.get("warnings"), list) else []
            warning_rows.append(selection_warning)
            result["warnings"] = warning_rows
            if not isinstance(result.get("warning"), dict):
                result["warning"] = selection_warning
        if not _as_bool(result.get("ok"), default=False) and _is_refresh_token_reused_unauthorized(result):
            block_warning = _set_profile_permanent_block(
                req.repo_root,
                alias=selected_alias,
                reason_code="refresh_token_reused",
                stage="build_loop",
            )
            if isinstance(block_warning, dict):
                warning_rows = result.get("warnings") if isinstance(result.get("warnings"), list) else []
                warning_rows.append(block_warning)
                result["warnings"] = warning_rows
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
        dispatch_stage = _dispatch_stage_for_task(task, plan_task)
        if status == TASK_STATUS_PENDING:
            result = _dispatch_for_stage(task, plan_task, dispatch_stage, plan_id)
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
    if deferred_block is not None:
        if carried_warning and not isinstance(deferred_block.get("warning"), dict):
            deferred_block["warning"] = carried_warning
        return deferred_block
    return {"ok": True, "status": "noop", "reason": "no dispatchable tasks", "warning": carried_warning}


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
    if task_state and plan_packets:
        warnings.extend(_repair_task_state_task_kinds(task_state, plan_packets))
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
    from op_simple_build import SimpleBuildError, run_op_simple_build

    _ensure_managed_gitignore_block(req.repo_root)
    requested_start_policy = req.start_policy or "auto"
    start_policy_data: dict[str, Any]
    try:
        resolved_start_mode, reason_code = _resolve_build_start_mode(req)
    except SimpleBuildError as exc:
        start_policy_data = _build_start_policy_payload(
            requested_start_policy=requested_start_policy,
            resolved_start_mode=None,
            reason_code="resume_state_invalid_existing_state_present",
        )
        _emit_build_progress(
            req,
            "build start policy requested="
            f"{requested_start_policy} resolved=blocked reason=resume_state_invalid_existing_state_present",
        )
        return _response(
            req,
            ok=False,
            status="blocked_preflight",
            summary="Build blocked: existing OP Simple runtime state is present but invalid for resume.",
            errors=[
                {
                    "code": exc.code,
                    "message": exc.message,
                    "stage": "build",
                }
            ],
            next_action="Repair .op-simple/current/initialize_state.json and run-base branch state, or rerun /op-build with --start-policy new.",
            state_ref=str(req.repo_root / ".op-simple" / "current" / "initialize_state.json"),
            data=start_policy_data,
        )

    start_policy_data = _build_start_policy_payload(
        requested_start_policy=requested_start_policy,
        resolved_start_mode=resolved_start_mode,
        reason_code=reason_code,
    )
    _emit_build_progress(
        req,
        f"build start policy requested={requested_start_policy} resolved={resolved_start_mode} reason={reason_code}",
    )

    combined_warnings: list[dict[str, Any]] = []
    if resolved_start_mode == "new":
        # /op-build fresh mode is the one-command entrypoint: optional initialize refresh + OP Simple runtime.
        mission_scope_supplied = bool(req.mission or req.mission_file or req.scope or req.scope_file)
        baseline_missing = any(
            not _repo_path(req.repo_root, rel).exists()
            for rel in MANDATORY_BUILD_BASELINE
        )
        should_initialize = (
            mission_scope_supplied
            or bool(req.override_old_plan)
            or baseline_missing
            or bool(req.publish_private_repo)
        )
        if should_initialize:
            _emit_build_progress(req, "running /op-initialize before /op-simple-build")
            init_req = replace(req, command="op-initialize")
            init_result = command_initialize(init_req)
            init_warnings = init_result.get("warnings")
            if isinstance(init_warnings, list):
                combined_warnings.extend(init_warnings)
            if not bool(init_result.get("ok")):
                return _response(
                    req,
                    ok=False,
                    status=_as_str(init_result.get("status")) or "failed",
                    summary=_as_str(init_result.get("summary")) or "Build failed during /op-initialize pre-step.",
                    warnings=combined_warnings,
                    errors=init_result.get("errors") if isinstance(init_result.get("errors"), list) else [],
                    artifacts=init_result.get("artifacts") if isinstance(init_result.get("artifacts"), list) else [],
                    next_action=_as_str(init_result.get("next_action")),
                    state_ref=_as_str(init_result.get("state_ref")),
                    data=_merge_response_data(
                        init_result.get("data") if isinstance(init_result.get("data"), dict) else None,
                        start_policy_data,
                    ),
                )
            _emit_build_progress(req, "initialize pre-step completed")
        simple_req = replace(req, command="op-simple-build")
    else:
        simple_req = replace(req, command="op-resume")

    result = run_op_simple_build(simple_req)
    _sync_build_state_from_simple_result(req.repo_root, result)
    simple_warnings = result.get("warnings") if isinstance(result.get("warnings"), list) else []
    return _response(
        req,
        ok=bool(result.get("ok")),
        status=_as_str(result.get("status")) or ("completed" if result.get("ok") else "failed"),
        summary=_as_str(result.get("summary")) or "OP build finished.",
        warnings=[*combined_warnings, *simple_warnings],
        errors=result.get("errors") if isinstance(result.get("errors"), list) else [],
        artifacts=result.get("artifacts") if isinstance(result.get("artifacts"), list) else [],
        next_action=_as_str(result.get("next_action")),
        state_ref=_as_str(result.get("state_ref")),
        data=_merge_response_data(
            result.get("data") if isinstance(result.get("data"), dict) else None,
            start_policy_data,
        ),
    )

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


def command_simple_build(req: OpRequest) -> dict[str, Any]:
    from op_simple_build import run_op_simple_build

    result = run_op_simple_build(req)
    _sync_build_state_from_simple_result(req.repo_root, result)
    return _response(
        req,
        ok=bool(result.get("ok")),
        status=_as_str(result.get("status")) or ("completed" if result.get("ok") else "failed"),
        summary=_as_str(result.get("summary")) or "OP Simple build finished.",
        warnings=result.get("warnings") if isinstance(result.get("warnings"), list) else [],
        errors=result.get("errors") if isinstance(result.get("errors"), list) else [],
        artifacts=result.get("artifacts") if isinstance(result.get("artifacts"), list) else [],
        next_action=_as_str(result.get("next_action")),
        state_ref=_as_str(result.get("state_ref")),
        data=result.get("data") if isinstance(result.get("data"), dict) else None,
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

    task_expectations: list[dict[str, Any]] = []
    tdd_mismatch_detected = False
    task_state_path = _repo_path(req.repo_root, TASK_EXECUTION_STATE_JSON)
    plan_packets_path = _repo_path(req.repo_root, PLAN_PACKETS_JSON)
    task_rows: list[dict[str, Any]] = []
    plan_map: dict[str, dict[str, Any]] = {}
    if task_state_path.exists():
        try:
            task_state_payload = _read_json(task_state_path)
        except OpError:
            task_state_payload = None
        if isinstance(task_state_payload, dict) and isinstance(task_state_payload.get("tasks"), list):
            task_rows = [row for row in task_state_payload.get("tasks", []) if isinstance(row, dict)]
    if plan_packets_path.exists():
        try:
            plan_payload = _read_json(plan_packets_path)
        except OpError:
            plan_payload = None
        if isinstance(plan_payload, dict):
            plan_map = _plan_task_map(plan_payload)
    for task in task_rows:
        task_id = _as_str(task.get("task_id"))
        if not task_id:
            continue
        plan_task = plan_map.get(task_id) if isinstance(plan_map.get(task_id), dict) else {}
        contract = _task_verification_contract(task, plan_task)
        stage = _current_evidence_stage(task, plan_task)
        expected = _expected_for_stage(contract, stage)
        evidence_path = _task_evidence_path(req.repo_root, task)
        expectation_met = False
        failure_class = "none"
        if evidence_path.exists():
            try:
                evidence_payload = _read_json(evidence_path)
            except OpError:
                evidence_payload = None
            if isinstance(evidence_payload, dict):
                summary = evidence_payload.get("summary") if isinstance(evidence_payload.get("summary"), dict) else {}
                expectation_met = _as_bool_field(summary.get("expectation_met"))
                failure_class = _normalize_failure_class(summary.get("failure_class"))
                if not expectation_met and failure_class in {"infra", "unexpected"}:
                    tdd_mismatch_detected = True
        task_expectations.append(
            {
                "task_id": task_id,
                "status": _normalize_task_status(task.get("status")),
                "expected": expected,
                "expectation_met": expectation_met,
                "failure_class": failure_class,
            }
        )
    if health_color == "green" and tdd_mismatch_detected:
        health_color = "yellow"
        health_reason = "tdd_expectation_not_met"

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
            "task_expectations": task_expectations,
        },
    )


def _resume_status_from_gap_stage(stage: str, *, slot: str | None) -> str:
    stage_key = stage.strip().lower()
    if stage_key == "merge":
        return TASK_STATUS_REVIEW_DONE
    if stage_key == "review":
        return TASK_STATUS_TESTS_DONE
    if stage_key == "test":
        return TASK_STATUS_DEV_DONE
    if stage_key == "workstation":
        slot_key = (slot or "").strip().lower()
        if slot_key.startswith("review-"):
            return TASK_STATUS_TESTS_DONE
        if slot_key.startswith("test-"):
            return TASK_STATUS_DEV_DONE
        return TASK_STATUS_PENDING
    return TASK_STATUS_PENDING


def _dispatch_stage_for_task(task: dict[str, Any], plan_task: dict[str, Any] | None = None) -> str:
    return _primary_stage_for_task_kind(_task_kind(task, plan_task))


def _lane_base_branch_for_task(
    plan_packets: dict[str, Any],
    task: dict[str, Any],
    plan_task: dict[str, Any] | None = None,
) -> str | None:
    lane_id = _as_str(task.get("lane_id")) or _as_str((plan_task or {}).get("lane_id"))
    lane_map = plan_packets.get("lane_base_branches") if isinstance(plan_packets.get("lane_base_branches"), dict) else {}
    branch = lane_map.get(lane_id) if lane_id else None
    return _as_str(branch)


def _resume_reset_exhausted_retries(repo_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    lock_snapshot = _load_build_lock_snapshot(repo_root)
    if bool(lock_snapshot.get("exists")) and bool(lock_snapshot.get("pid_alive")):
        active_pid = lock_snapshot.get("pid")
        raise OpError(
            "resume_reset_build_active",
            f"cannot reset exhausted retries while build lock is active (pid={active_pid})",
            stage="resume",
        )
    active_workers = _active_workers_count(repo_root)
    if isinstance(active_workers, int) and active_workers > 0:
        raise OpError(
            "resume_reset_workers_active",
            f"cannot reset exhausted retries while {active_workers} worker(s) are active",
            stage="resume",
        )

    task_state_path = _repo_path(repo_root, TASK_EXECUTION_STATE_JSON)
    if not task_state_path.exists():
        raise OpError("resume_reset_task_state_missing", "TASK_EXECUTION_STATE.json is missing", stage="resume")
    task_state_raw = _read_json(task_state_path)
    if not isinstance(task_state_raw, dict):
        raise OpError("resume_reset_task_state_invalid", "TASK_EXECUTION_STATE.json must be a JSON object", stage="resume")
    task_state = task_state_raw

    build_state_path = _repo_path(repo_root, BUILD_STATE_JSON)
    if not build_state_path.exists():
        raise OpError("resume_reset_build_state_missing", "BUILD_STATE.json is missing", stage="resume")
    build_state = _load_build_state(build_state_path)

    now = utc_now_iso()
    reset_gap_ids: set[str] = set()
    reset_task_ids: set[str] = set()
    reset_gap_count = 0
    reopened_task_count = 0

    for task in task_state.get("tasks", []):
        if not isinstance(task, dict):
            continue
        task_id = _as_str(task.get("task_id"))
        task["attempts"] = {"dev": 0, "test": 0, "review": 0}
        task_watchdog = _normalize_progress_watchdog(task.get("progress_watchdog"))
        task_watchdog["consecutive_no_forward_progress_cycles"] = 0
        task_watchdog["last_forward_progress_cycle"] = 0
        task_watchdog["triggered"] = False
        task_watchdog["triggered_at"] = None
        task_watchdog["_last_rank"] = _task_forward_progress_rank(_normalize_task_status(task.get("status")))
        task_watchdog["_last_closed_gap_count"] = 0
        task["progress_watchdog"] = task_watchdog
        gapfix_state = _normalize_gapfix_state(task.get("gapfix_state"))
        gapfix_state["active"] = False
        gapfix_state["active_batch_id"] = None
        gapfix_state["batch_last_updated_at"] = now
        task["gapfix_state"] = gapfix_state
        rows = _normalize_task_gap_rows(task)
        reopened_candidates: list[tuple[int, str]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            if (_as_str(row.get("status")) or "open").lower() != "open":
                continue
            retry_count = _coerce_nonneg_int(row.get("retry_count"), default=0)
            max_retries = max(1, _coerce_nonneg_int(row.get("max_retries"), default=5))
            if retry_count < max_retries:
                continue
            row["retry_count"] = 0
            row["updated_at"] = now
            reason_codes = [code for code in (_as_str(item) for item in row.get("reason_codes", [])) if code]
            if "resume_retry_reset" not in reason_codes:
                reason_codes.append("resume_retry_reset")
            row["reason_codes"] = reason_codes or ["resume_retry_reset"]
            gap_id = _as_str(row.get("gap_id"))
            if gap_id:
                reset_gap_ids.add(gap_id)
            reset_gap_count += 1
            if task_id:
                reset_task_ids.add(task_id)
            reopened_status = _resume_status_from_gap_stage(
                _as_str(row.get("stage")) or "",
                slot=_as_str(row.get("slot")),
            )
            rank = {
                TASK_STATUS_PENDING: 0,
                TASK_STATUS_DEV_DONE: 1,
                TASK_STATUS_TESTS_DONE: 2,
                TASK_STATUS_REVIEW_DONE: 3,
            }.get(reopened_status, 0)
            reopened_candidates.append((rank, reopened_status))
        if reopened_candidates and _normalize_task_status(task.get("status")) == TASK_STATUS_BLOCKED:
            reopened_candidates.sort(key=lambda item: item[0])
            task["status"] = reopened_candidates[0][1]
            task["owner_slot"] = None
            task["last_progress_at"] = now
            task["blocking_source"] = "none"
            reopened_task_count += 1

    build_state["gap_retry_attempts"] = {}

    build_state["gap_retry_exhausted_ids"] = []

    build_state["dead_pid_retry_counts"] = {}
    build_state["resume_fail_counts_by_slot"] = {}
    build_state["slot_resume_policy"] = {}
    build_state["last_dispatch_cycle_summary"] = {}
    build_state["last_assignment_observations"] = []
    build_state["last_task_state_fingerprint"] = None
    build_state["no_progress_watchdog"] = {
        "consecutive_no_progress_cycles": 0,
        "threshold_cycles": NO_PROGRESS_THRESHOLD_CYCLES,
        "last_progress_at": now,
        "triggered": False,
        "triggered_at": None,
    }
    build_state["open_gap_ids"] = _open_task_gap_ids(task_state)
    build_state["updated_at"] = now
    build_state["retry_reset"] = {
        "last_reset_at": now,
        "reset_gap_ids": sorted(reset_gap_ids),
        "reset_task_ids": sorted(reset_task_ids),
    }

    task_state["updated_at"] = now
    _atomic_write_json(
        _repo_path(repo_root, NO_PROGRESS_WATCHDOG_STATE_JSON),
        {
            "schema_version": SCHEMA_VERSION,
            "last_cycle": _coerce_nonneg_int(build_state.get("last_cycle"), default=0),
            "consecutive_no_progress_cycles": 0,
            "threshold_cycles": NO_PROGRESS_THRESHOLD_CYCLES,
            "last_progress_at": now,
            "triggered": False,
            "triggered_at": None,
            "trigger_reason": None,
        },
    )
    _atomic_write_json(task_state_path, task_state)
    _atomic_write_json(build_state_path, build_state)

    warning = {
        "code": "resume_exhausted_retries_reset",
        "message": (
            "reset exhausted retry counters "
            f"(gaps={reset_gap_count}, tasks_reopened={reopened_task_count})"
        ),
        "stage": "resume",
        "reset_gap_count": reset_gap_count,
        "reopened_task_count": reopened_task_count,
    }
    summary = {
        "reset_requested": True,
        "reset_gap_count": reset_gap_count,
        "reopened_task_count": reopened_task_count,
        "reset_gap_ids": sorted(reset_gap_ids),
        "reset_task_ids": sorted(reset_task_ids),
    }
    return [warning], summary


def command_resume(req: OpRequest) -> dict[str, Any]:
    simple_runtime_marker = req.repo_root / ".op-simple" / "current" / "initialize_state.json"
    if not simple_runtime_marker.exists():
        return _response(
            req,
            ok=False,
            status="blocked_preflight",
            summary="Resume blocked: OP Simple runtime state is missing.",
            errors=[
                {
                    "code": "op_simple_resume_unavailable",
                    "message": "Missing .op-simple/current/initialize_state.json; legacy resume fallback is removed.",
                    "stage": "resume",
                }
            ],
            next_action="Run /op-build to initialize a new OP Simple run, then use /op-resume.",
            state_ref=str(simple_runtime_marker),
        )

    from op_simple_build import run_op_simple_build

    simple_req = replace(req, command="op-resume")
    result = run_op_simple_build(simple_req)
    _sync_build_state_from_simple_result(req.repo_root, result)
    simple_warnings = result.get("warnings") if isinstance(result.get("warnings"), list) else []
    return _response(
        req,
        ok=bool(result.get("ok")),
        status=_as_str(result.get("status")) or ("completed" if result.get("ok") else "failed"),
        summary=_as_str(result.get("summary")) or "OP resume finished.",
        warnings=simple_warnings,
        errors=result.get("errors") if isinstance(result.get("errors"), list) else [],
        artifacts=result.get("artifacts") if isinstance(result.get("artifacts"), list) else [],
        next_action=_as_str(result.get("next_action")),
        state_ref=_as_str(result.get("state_ref")),
        data=result.get("data") if isinstance(result.get("data"), dict) else None,
    )


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

    # Public sleep control was removed once cycle release became watcher-driven.
    # Keep the field internally for compatibility with older helpers/tests.
    sleep_val = 0.0
    max_parallel_workers_raw = payload.get("max_parallel_workers", 8)
    try:
        max_parallel_workers = int(max_parallel_workers_raw)
    except (TypeError, ValueError) as exc:
        raise OpError("input_error", "max_parallel_workers must be integer", stage="input") from exc
    if max_parallel_workers <= 0:
        max_parallel_workers = 8
    enable_artifact_fan_in = _as_bool(payload.get("enable_artifact_fan_in"), default=False)
    worktrees_parent_raw = _as_str(payload.get("worktrees_parent"))
    worktrees_parent = (
        Path(worktrees_parent_raw).expanduser().resolve() if worktrees_parent_raw else None
    )
    selected_aliases = _as_alias_list(payload.get("selected_aliases"))
    start_policy = _as_str(payload.get("start_policy"))
    publish_private_repo = _as_bool(payload.get("publish_private_repo"), default=False)
    github_owner = _as_str(payload.get("github_owner"))
    github_repo_name = _as_str(payload.get("github_repo_name"))
    if start_policy is not None:
        start_policy = start_policy.lower()
    if start_policy is not None and start_policy not in {"auto", "new", "resume"}:
        raise OpError("input_error", "start_policy must be one of: auto, new, resume", stage="input")
    if start_policy is not None and command != "op-build":
        raise OpError("input_error", "start_policy is only supported for /op-build", stage="input")
    if command == "op-build" and start_policy is None:
        start_policy = "auto"
    run_base_source_branch = _as_str(payload.get("run_base_source_branch"))
    fresh_run_conflicts: list[str] = []
    if _as_str(payload.get("mission")):
        fresh_run_conflicts.append("--mission")
    if _as_str(payload.get("mission_file")):
        fresh_run_conflicts.append("--mission-file")
    if _as_str(payload.get("scope")):
        fresh_run_conflicts.append("--scope")
    if _as_str(payload.get("scope_file")):
        fresh_run_conflicts.append("--scope-file")
    if _as_bool(payload.get("override_old_plan"), default=False):
        fresh_run_conflicts.append("--override-old-plan")
    if run_base_source_branch:
        fresh_run_conflicts.append("--run-base-source-branch")
    if publish_private_repo:
        fresh_run_conflicts.append("--publish-private-repo")
    if github_owner:
        fresh_run_conflicts.append("--github-owner")
    if github_repo_name:
        fresh_run_conflicts.append("--github-repo-name")
    if start_policy == "resume" and fresh_run_conflicts:
        conflict_list = ", ".join(fresh_run_conflicts)
        raise OpError(
            "input_error",
            "start_policy=resume conflicts with fresh-run flags: "
            f"{conflict_list}. Remove those flags and retry resume, or use --start-policy new.",
            stage="input",
        )
    if (github_owner or github_repo_name) and not publish_private_repo:
        raise OpError(
            "input_error",
            "github_owner/github_repo_name require publish_private_repo=true",
            stage="input",
        )
    if publish_private_repo and command not in {"op-initialize", "op-build"}:
        raise OpError(
            "input_error",
            "publish_private_repo is only supported for /op-initialize and /op-build",
            stage="input",
        )
    if github_owner and "/" in github_owner:
        raise OpError("input_error", "github_owner must not contain '/'", stage="input")
    if github_repo_name and "/" in github_repo_name:
        raise OpError("input_error", "github_repo_name must not contain '/'", stage="input")

    boss_model = sanitize_boss_model(payload.get("boss_model")) or DEFAULT_BOSS_MODEL
    boss_reasoning_effort = (
        sanitize_boss_reasoning_effort(payload.get("boss_reasoning_effort")) or DEFAULT_BOSS_REASONING_EFFORT
    )
    profile = _as_str(payload.get("profile"))
    codex_profile = _as_str(payload.get("codex_profile")) or profile
    executor_provider = (_as_str(payload.get("executor_provider")) or "codex").lower()
    if executor_provider not in {"codex", "openrouter", "blackbox"}:
        raise OpError(
            "input_error",
            "executor_provider must be one of: codex, openrouter, blackbox",
            stage="input",
        )
    blackbox_lane = (_as_str(payload.get("blackbox_lane")) or "free").lower()
    if blackbox_lane not in {"free", "api_key"}:
        raise OpError(
            "input_error",
            "blackbox_lane must be one of: free, api_key",
            stage="input",
        )
    executor_model = _as_str(payload.get("executor_model"))
    allow_worker_executor_override = _as_bool(payload.get("allow_worker_executor_override"), default=False)
    cycle_release_mode = (_as_str(payload.get("cycle_release_mode")) or "token_conservative").lower()
    if cycle_release_mode not in {"token_conservative", "max_work"}:
        raise OpError(
            "input_error",
            "cycle_release_mode must be one of: token_conservative, max_work",
            stage="input",
        )
    cycle_release_timeout_raw = payload.get("cycle_release_timeout_seconds", 900)
    try:
        cycle_release_timeout_seconds = int(cycle_release_timeout_raw)
    except (TypeError, ValueError) as exc:
        raise OpError("input_error", "cycle_release_timeout_seconds must be integer", stage="input") from exc
    if cycle_release_timeout_seconds <= 0:
        cycle_release_timeout_seconds = 900
    cycle_release_poll_raw = payload.get("cycle_release_poll_seconds", 5)
    try:
        cycle_release_poll_seconds = int(cycle_release_poll_raw)
    except (TypeError, ValueError) as exc:
        raise OpError("input_error", "cycle_release_poll_seconds must be integer", stage="input") from exc
    if cycle_release_poll_seconds <= 0:
        cycle_release_poll_seconds = 5
    strategy_manifest = _as_str(payload.get("strategy_manifest"))
    strategy_manifest_file = _as_str(payload.get("strategy_manifest_file"))
    if strategy_manifest and strategy_manifest_file:
        raise OpError(
            "input_error",
            "provide strategy_manifest or strategy_manifest_file, not both",
            stage="input",
        )

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
        max_parallel_workers=max_parallel_workers,
        sleep_minutes=sleep_val,
        enable_artifact_fan_in=enable_artifact_fan_in,
        worktrees_parent=worktrees_parent,
        selected_aliases=selected_aliases,
        dry_run=_as_bool(payload.get("dry_run"), default=False),
        reset_exhausted_retries=_as_bool(payload.get("reset_exhausted_retries"), default=False),
        strategy_manifest=strategy_manifest,
        strategy_manifest_file=strategy_manifest_file,
        skip_strategy=_as_bool(payload.get("skip_strategy"), default=False),
        publish_private_repo=publish_private_repo,
        github_owner=github_owner,
        github_repo_name=github_repo_name,
        start_policy=start_policy if command == "op-build" else None,
        run_base_source_branch=run_base_source_branch,
        boss_model=boss_model,
        boss_reasoning_effort=boss_reasoning_effort,
        profile=profile,
        codex_profile=codex_profile,
        executor_provider=executor_provider,
        executor_model=executor_model,
        blackbox_lane=blackbox_lane,
        allow_worker_executor_override=allow_worker_executor_override,
        cycle_release_mode=cycle_release_mode,
        cycle_release_timeout_seconds=cycle_release_timeout_seconds,
        cycle_release_poll_seconds=cycle_release_poll_seconds,
    )


def execute_request(req: OpRequest) -> dict[str, Any]:
    if req.command == "op-map-codebase":
        return command_map_codebase(req)
    if req.command == "op-new-project":
        return command_new_project(req)
    if req.command == "op-strategy":
        return command_strategy(req)
    if req.command == "op-plan":
        return command_plan(req)
    if req.command == "op-initialize":
        return command_initialize(req)
    if req.command == "op-build":
        return command_build(req)
    if req.command == "op-simple-build":
        return command_simple_build(req)
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
    start_payload = {
        "command": req.command,
        "repo_root": str(req.repo_root),
        "mission": req.mission,
        "mission_file": req.mission_file,
        "scope": req.scope,
        "scope_file": req.scope_file,
        "skip_strategy": req.skip_strategy,
        "start_policy": req.start_policy,
        "executor_provider": req.executor_provider,
        "executor_model": req.executor_model,
        "selected_aliases": req.selected_aliases,
        "max_build_cycles": req.max_build_cycles,
        "max_parallel_workers": req.max_parallel_workers,
        "dry_run": req.dry_run,
        "override_old_plan": req.override_old_plan,
    }
    emit_op_event_trace(
        event_name="op.command.start",
        run_type="chain",
        payload=start_payload,
    )
    try:
        result = execute_request(req)
    except OpError as exc:
        emit_op_event_trace(
            event_name="op.command.error",
            run_type="chain",
            payload={
                **start_payload,
                "status": "failed",
                "ok": False,
                "errors": [{"code": exc.code, "message": exc.message, "stage": exc.stage}],
            },
        )
        raise
    emit_op_event_trace(
        event_name="op.command.result",
        run_type="chain",
        payload={
            **start_payload,
            "status": _as_str(result.get("status")) or "completed",
            "ok": bool(result.get("ok")),
            "summary": _as_str(result.get("summary")),
            "warnings": result.get("warnings") if isinstance(result.get("warnings"), list) else [],
            "errors": result.get("errors") if isinstance(result.get("errors"), list) else [],
            "artifacts": result.get("artifacts") if isinstance(result.get("artifacts"), list) else [],
            "data": result.get("data") if isinstance(result.get("data"), dict) else {},
        },
    )
    return result
