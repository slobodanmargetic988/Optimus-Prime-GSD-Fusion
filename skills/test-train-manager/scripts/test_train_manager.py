#!/usr/bin/env python3
"""Manage Optimus shared test-train wave state, promotion, deploy, and loop escalation."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

TOOL = "test-train-manager"
TOOL_VERSION = "0.1.0"
SCHEMA_VERSION = "1.0"

ACTIONS = {
    "bootstrap",
    "sync_state",
    "close_test_wave",
    "evaluate_promotion_gate",
    "promote_test_next_to_test",
    "deploy_test_branch",
    "start_new_test_wave",
    "record_test_outcome",
    "render_wave_summary",
}

WAVE_STATES = {
    "WAVE_ACTIVE",
    "WAVE_CLOSING",
    "PROMOTION_EVAL",
    "PROMOTE_AND_DEPLOY",
    "WAVE_BOOTSTRAP",
}

TEST_TRAIN_MODES = {"off", "final-stage", "forced-shared-env"}
TASK_OUTCOMES = {"passed", "failed", "pass_with_rework", "blocked"}
CRITICAL_BLOCKER_CATEGORIES = {"env", "runtime", "test-train", "infra"}


class ToolError(Exception):
    def __init__(self, code: str, message: str, stage: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.stage = stage


@dataclass
class TrainInput:
    repo_root: Path
    action: str
    test_branch: str
    test_next_branch: str
    test_train_mode: str
    shared_test_base_url: str | None
    deploy_test_branch_cmd: str | None
    dry_run: bool
    create_branches_if_missing: bool
    force: bool
    wave_id: str | None
    planned_flow_pass_completed: bool | None
    task_identifier: str | None
    task_outcome: str | None
    blocker_fingerprint: str | None
    critical_blocker_active_hours: float
    state_path: Path
    attempts_path: Path
    wave_log_path: Path
    wave_summary_path: Path
    blockers_path: Path
    handoff_log_path: Path
    thread_token_summary_path: Path


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    text = str(value).strip()
    return text or None


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


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _read_input(path: str) -> dict[str, Any]:
    raw = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ToolError("input_error", "input payload must be JSON object", stage="input")
    return payload


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ToolError("state_read_error", f"expected object JSON at {path}", stage="state")
    return data


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")


def _parse_iso(value: Any) -> datetime | None:
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Optimus shared test-train manager")
    parser.add_argument("--input-json", required=True, help="Path to JSON input or '-' for stdin")
    parser.add_argument("--json-pretty", action="store_true")
    return parser.parse_args()


def build_input(payload: dict[str, Any]) -> TrainInput:
    repo_root_raw = _str(payload.get("repo_root"))
    if not repo_root_raw:
        raise ToolError("input_error", "repo_root is required", stage="input")
    repo_root = Path(repo_root_raw).expanduser().resolve()

    action = (_str(payload.get("action")) or "sync_state").strip()
    if action not in ACTIONS:
        raise ToolError("input_error", f"action must be one of {sorted(ACTIONS)}", stage="input")

    test_train_mode = (_str(payload.get("test_train_mode")) or "final-stage").lower()
    if test_train_mode not in TEST_TRAIN_MODES:
        raise ToolError(
            "input_error",
            f"test_train_mode must be one of {sorted(TEST_TRAIN_MODES)}",
            stage="input",
        )

    task_outcome = (_str(payload.get("task_outcome")) or None)
    if task_outcome and task_outcome not in TASK_OUTCOMES:
        raise ToolError("input_error", f"task_outcome must be one of {sorted(TASK_OUTCOMES)}", stage="input")

    reports = repo_root / "reports" / "optimus-prime"
    return TrainInput(
        repo_root=repo_root,
        action=action,
        test_branch=_str(payload.get("test_branch")) or "test",
        test_next_branch=_str(payload.get("test_next_branch")) or "test-next",
        test_train_mode=test_train_mode,
        shared_test_base_url=_str(payload.get("shared_test_base_url")),
        deploy_test_branch_cmd=_str(payload.get("deploy_test_branch_cmd")),
        dry_run=_bool(payload.get("dry_run"), False),
        create_branches_if_missing=_bool(payload.get("create_branches_if_missing"), True),
        force=_bool(payload.get("force"), False),
        wave_id=_str(payload.get("wave_id")),
        planned_flow_pass_completed=(
            None if payload.get("planned_flow_pass_completed") is None else _bool(payload.get("planned_flow_pass_completed"), False)
        ),
        task_identifier=_str(payload.get("task_identifier")),
        task_outcome=task_outcome,
        blocker_fingerprint=_str(payload.get("blocker_fingerprint")),
        critical_blocker_active_hours=max(1.0, _float(payload.get("critical_blocker_active_hours"), 6.0)),
        state_path=Path(_str(payload.get("state_path")) or str(reports / "TEST_TRAIN_STATE.json")).expanduser().resolve(),
        attempts_path=Path(_str(payload.get("attempts_path")) or str(reports / "TEST_TASK_ATTEMPTS.json")).expanduser().resolve(),
        wave_log_path=Path(_str(payload.get("wave_log_path")) or str(reports / "TEST_WAVE_LOG.jsonl")).expanduser().resolve(),
        wave_summary_path=Path(_str(payload.get("wave_summary_path")) or str(reports / "TEST_WAVE_SUMMARY.md")).expanduser().resolve(),
        blockers_path=Path(_str(payload.get("blockers_path")) or str(reports / "BLOCKERS.jsonl")).expanduser().resolve(),
        handoff_log_path=Path(_str(payload.get("handoff_log_path")) or str(reports / "HANDOFF_LOG.jsonl")).expanduser().resolve(),
        thread_token_summary_path=Path(
            _str(payload.get("thread_token_summary_path"))
            or str(reports / "THREAD_TOKEN_USAGE_SUMMARY.json")
        ).expanduser().resolve(),
    )


def _default_state(inp: TrainInput) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "updated_at": utc_now_iso(),
        "test_train_mode": inp.test_train_mode,
        "test_branch": inp.test_branch,
        "test_next_branch": inp.test_next_branch,
        "shared_test_base_url": inp.shared_test_base_url,
        "active_wave": None,
        "deployed_test_commit": None,
        "queued_test_next_commit": None,
        "promotion_eligibility": {
            "eligible": False,
            "reasons": ["wave_not_initialized"],
            "evaluated_at": utc_now_iso(),
        },
        "deploy_status": {
            "last_result": "none",
            "last_attempt_at": None,
            "last_success_at": None,
        },
    }


def _default_attempts() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "updated_at": utc_now_iso(),
        "tasks": {},
    }


def _git(inp: TrainInput, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(inp.repo_root),
        capture_output=True,
        text=True,
        check=check,
    )


def _branch_commit(inp: TrainInput, branch: str) -> str | None:
    proc = _git(inp, ["rev-parse", "--verify", branch], check=False)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def _ensure_branch(inp: TrainInput, branch: str, start_point: str) -> None:
    if _branch_commit(inp, branch):
        return
    if not inp.create_branches_if_missing:
        raise ToolError("branch_missing", f"branch '{branch}' does not exist", stage="git")
    if inp.dry_run:
        return
    _git(inp, ["branch", branch, start_point], check=True)


def _next_wave_id(state: dict[str, Any]) -> str:
    current = state.get("active_wave")
    if isinstance(current, dict):
        wave_id = _str(current.get("wave_id"))
        if wave_id and wave_id.startswith("wave-"):
            try:
                n = int(wave_id.split("-", 1)[1])
                return f"wave-{n + 1:04d}"
            except (TypeError, ValueError):
                pass
    return "wave-0001"


def _append_wave_event(inp: TrainInput, wave_id: str | None, event_type: str, payload: dict[str, Any]) -> None:
    row = {
        "timestamp": utc_now_iso(),
        "wave_id": wave_id,
        "event_type": event_type,
        "payload": payload,
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
    }
    _append_jsonl(inp.wave_log_path, row)


def _load_state(inp: TrainInput) -> tuple[dict[str, Any], dict[str, Any]]:
    state = _read_json(inp.state_path, _default_state(inp))
    attempts = _read_json(inp.attempts_path, _default_attempts())
    if "tasks" not in attempts or not isinstance(attempts.get("tasks"), dict):
        attempts["tasks"] = {}
    return state, attempts


def _save_state(inp: TrainInput, state: dict[str, Any], attempts: dict[str, Any]) -> None:
    state["updated_at"] = utc_now_iso()
    attempts["updated_at"] = utc_now_iso()
    _write_json(inp.state_path, state)
    _write_json(inp.attempts_path, attempts)


def _critical_env_blocker_active(inp: TrainInput) -> tuple[bool, list[dict[str, Any]]]:
    if not inp.blockers_path.exists():
        return False, []
    active_cutoff = utc_now() - timedelta(hours=inp.critical_blocker_active_hours)
    matches: list[dict[str, Any]] = []
    for line in inp.blockers_path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            row = json.loads(text)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        category = (_str(row.get("category")) or "unknown").lower()
        if category not in CRITICAL_BLOCKER_CATEGORIES:
            continue
        status = (_str(row.get("status")) or "active").lower()
        if status in {"resolved", "closed"}:
            continue
        ts = _parse_iso(row.get("timestamp"))
        if ts is not None and ts < active_cutoff:
            continue
        matches.append(row)
    return bool(matches), matches


def _auto_force_mode_if_needed(inp: TrainInput, state: dict[str, Any]) -> tuple[bool, str | None]:
    if inp.blockers_path.exists() is False:
        return False, None
    blocker_rows: list[dict[str, Any]] = []
    for line in inp.blockers_path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            row = json.loads(text)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        category = (_str(row.get("category")) or "").lower()
        role = (_str(row.get("worker_role")) or "").lower()
        if category not in {"env", "runtime", "test-train", "infra"}:
            continue
        if role not in {"tester", "flex-tester", ""}:
            continue
        blocker_rows.append(row)

    recent = blocker_rows[-5:]
    repeated_recent = len(recent) >= 3
    by_fingerprint: dict[str, int] = {}
    for row in blocker_rows:
        fp = _str(row.get("fingerprint"))
        if not fp:
            continue
        by_fingerprint[fp] = by_fingerprint.get(fp, 0) + 1

    repeated_fp = next((fp for fp, count in by_fingerprint.items() if count >= 3), None)

    if not repeated_recent and repeated_fp is None:
        return False, None

    current_mode = (_str(state.get("test_train_mode")) or "off").lower()
    if current_mode == "forced-shared-env":
        return False, None

    state["test_train_mode"] = "forced-shared-env"
    reason = (
        ">=3 env/runtime tester blockers in recent window"
        if repeated_recent
        else f"repeated blocker fingerprint >=3: {repeated_fp}"
    )
    return True, reason


def _evaluate_gate(inp: TrainInput, state: dict[str, Any]) -> dict[str, Any]:
    wave = state.get("active_wave") if isinstance(state.get("active_wave"), dict) else {}
    planned_pass_done = bool(wave.get("planned_flow_pass_completed"))
    critical_blocked, blocker_rows = _critical_env_blocker_active(inp)
    reasons: list[str] = []
    if not planned_pass_done:
        reasons.append("planned_flow_pass_not_completed")
    if critical_blocked:
        reasons.append("critical_environment_blocker_active")
    return {
        "eligible": planned_pass_done and not critical_blocked,
        "reasons": reasons or ["eligible"],
        "critical_blockers": blocker_rows[-3:],
        "evaluated_at": utc_now_iso(),
    }


def _sync_commits(inp: TrainInput, state: dict[str, Any]) -> None:
    state["deployed_test_commit"] = _branch_commit(inp, inp.test_branch)
    state["queued_test_next_commit"] = _branch_commit(inp, inp.test_next_branch)


def action_bootstrap(inp: TrainInput, state: dict[str, Any], attempts: dict[str, Any]) -> dict[str, Any]:
    head = _branch_commit(inp, "HEAD")
    if not head:
        raise ToolError("git_error", "cannot resolve HEAD commit", stage="git")

    _ensure_branch(inp, inp.test_branch, head)
    _ensure_branch(inp, inp.test_next_branch, inp.test_branch)

    if not isinstance(state.get("active_wave"), dict):
        wave_id = _next_wave_id(state)
        state["active_wave"] = {
            "wave_id": wave_id,
            "state": "WAVE_BOOTSTRAP",
            "started_at": utc_now_iso(),
            "planned_flow_pass_completed": False,
        }
        _append_wave_event(inp, wave_id, "wave_bootstrap", {"state": "WAVE_BOOTSTRAP"})

    _sync_commits(inp, state)
    switch, reason = _auto_force_mode_if_needed(inp, state)
    if switch:
        wave_id = _str((state.get("active_wave") or {}).get("wave_id"))
        _append_wave_event(inp, wave_id, "mode_switch", {"to_mode": "forced-shared-env", "reason": reason})

    _save_state(inp, state, attempts)
    return {
        "ok": True,
        "action": "bootstrap",
        "state_path": str(inp.state_path),
        "attempts_path": str(inp.attempts_path),
        "wave_log_path": str(inp.wave_log_path),
        "test_branch": inp.test_branch,
        "test_next_branch": inp.test_next_branch,
        "active_wave": state.get("active_wave"),
    }


def action_sync_state(inp: TrainInput, state: dict[str, Any], attempts: dict[str, Any]) -> dict[str, Any]:
    _sync_commits(inp, state)
    gate = _evaluate_gate(inp, state)
    state["promotion_eligibility"] = gate
    switch, reason = _auto_force_mode_if_needed(inp, state)
    if switch:
        wave_id = _str((state.get("active_wave") or {}).get("wave_id"))
        _append_wave_event(inp, wave_id, "mode_switch", {"to_mode": "forced-shared-env", "reason": reason})
    _save_state(inp, state, attempts)
    return {
        "ok": True,
        "action": "sync_state",
        "deployed_test_commit": state.get("deployed_test_commit"),
        "queued_test_next_commit": state.get("queued_test_next_commit"),
        "promotion_eligibility": gate,
        "test_train_mode": state.get("test_train_mode"),
    }


def action_close_wave(inp: TrainInput, state: dict[str, Any], attempts: dict[str, Any]) -> dict[str, Any]:
    wave = state.get("active_wave")
    if not isinstance(wave, dict):
        raise ToolError("state_error", "active_wave missing; run bootstrap first", stage="state")

    wave["state"] = "WAVE_CLOSING"
    wave["closed_at"] = utc_now_iso()
    if inp.planned_flow_pass_completed is not None:
        wave["planned_flow_pass_completed"] = inp.planned_flow_pass_completed

    _append_wave_event(
        inp,
        _str(wave.get("wave_id")),
        "close_test_wave",
        {
            "planned_flow_pass_completed": bool(wave.get("planned_flow_pass_completed")),
            "state": "WAVE_CLOSING",
        },
    )
    _save_state(inp, state, attempts)
    return {"ok": True, "action": "close_test_wave", "active_wave": wave}


def action_evaluate_gate(inp: TrainInput, state: dict[str, Any], attempts: dict[str, Any]) -> dict[str, Any]:
    wave = state.get("active_wave")
    if not isinstance(wave, dict):
        raise ToolError("state_error", "active_wave missing; run bootstrap first", stage="state")
    wave["state"] = "PROMOTION_EVAL"
    gate = _evaluate_gate(inp, state)
    state["promotion_eligibility"] = gate
    _append_wave_event(inp, _str(wave.get("wave_id")), "evaluate_promotion_gate", gate)
    _save_state(inp, state, attempts)
    return {"ok": True, "action": "evaluate_promotion_gate", "promotion_eligibility": gate}


def _git_current_branch(inp: TrainInput) -> str:
    proc = _git(inp, ["rev-parse", "--abbrev-ref", "HEAD"], check=True)
    branch = proc.stdout.strip()
    if not branch:
        raise ToolError("git_error", "could not resolve current branch", stage="git")
    return branch


def action_promote(inp: TrainInput, state: dict[str, Any], attempts: dict[str, Any]) -> dict[str, Any]:
    gate = _evaluate_gate(inp, state)
    state["promotion_eligibility"] = gate
    wave = state.get("active_wave") if isinstance(state.get("active_wave"), dict) else {}
    wave_id = _str(wave.get("wave_id"))

    if not gate["eligible"] and not inp.force:
        _append_wave_event(inp, wave_id, "promote_skipped", {"reasons": gate["reasons"]})
        _save_state(inp, state, attempts)
        return {"ok": False, "action": "promote_test_next_to_test", "blocked": gate}

    _ensure_branch(inp, inp.test_branch, "HEAD")
    _ensure_branch(inp, inp.test_next_branch, inp.test_branch)

    original_branch = _git_current_branch(inp)
    merge_stdout = ""
    try:
        if not inp.dry_run:
            _git(inp, ["checkout", inp.test_branch], check=True)
            merge_proc = _git(inp, ["merge", "--no-ff", "--no-edit", inp.test_next_branch], check=False)
            merge_stdout = (merge_proc.stdout or "") + (merge_proc.stderr or "")
            if merge_proc.returncode != 0:
                _git(inp, ["merge", "--abort"], check=False)
                raise ToolError("merge_failed", f"merge failed: {merge_stdout.strip()}", stage="git")
    finally:
        if not inp.dry_run:
            _git(inp, ["checkout", original_branch], check=False)

    wave["state"] = "PROMOTE_AND_DEPLOY"
    _sync_commits(inp, state)
    _append_wave_event(
        inp,
        wave_id,
        "promote_test_next_to_test",
        {
            "test_branch": inp.test_branch,
            "test_next_branch": inp.test_next_branch,
            "deployed_test_commit": state.get("deployed_test_commit"),
            "queued_test_next_commit": state.get("queued_test_next_commit"),
            "dry_run": inp.dry_run,
        },
    )
    _save_state(inp, state, attempts)
    return {
        "ok": True,
        "action": "promote_test_next_to_test",
        "deployed_test_commit": state.get("deployed_test_commit"),
        "dry_run": inp.dry_run,
        "merge_output": merge_stdout.strip() or None,
    }


def action_deploy(inp: TrainInput, state: dict[str, Any], attempts: dict[str, Any]) -> dict[str, Any]:
    wave = state.get("active_wave") if isinstance(state.get("active_wave"), dict) else {}
    wave_id = _str(wave.get("wave_id"))
    if not inp.deploy_test_branch_cmd:
        raise ToolError("input_error", "deploy_test_branch_cmd is required for deploy_test_branch", stage="input")

    deploy = state.get("deploy_status")
    if not isinstance(deploy, dict):
        deploy = {"last_result": "none", "last_attempt_at": None, "last_success_at": None}
        state["deploy_status"] = deploy

    deploy["last_attempt_at"] = utc_now_iso()
    if inp.dry_run:
        deploy["last_result"] = "dry_run"
        _append_wave_event(inp, wave_id, "deploy_test_branch", {"status": "dry_run", "command": inp.deploy_test_branch_cmd})
        _save_state(inp, state, attempts)
        return {"ok": True, "action": "deploy_test_branch", "status": "dry_run"}

    proc = subprocess.run(inp.deploy_test_branch_cmd, cwd=str(inp.repo_root), shell=True, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        deploy["last_result"] = "failed"
        _append_wave_event(
            inp,
            wave_id,
            "deploy_test_branch",
            {
                "status": "failed",
                "exit_code": proc.returncode,
                "stderr": (proc.stderr or "").strip()[:2000],
            },
        )
        _save_state(inp, state, attempts)
        return {
            "ok": False,
            "action": "deploy_test_branch",
            "status": "failed",
            "exit_code": proc.returncode,
            "stderr": (proc.stderr or "").strip(),
            "stdout": (proc.stdout or "").strip(),
        }

    deploy["last_result"] = "success"
    deploy["last_success_at"] = utc_now_iso()
    _append_wave_event(inp, wave_id, "deploy_test_branch", {"status": "success"})
    _save_state(inp, state, attempts)
    return {"ok": True, "action": "deploy_test_branch", "status": "success"}


def action_start_wave(inp: TrainInput, state: dict[str, Any], attempts: dict[str, Any]) -> dict[str, Any]:
    wave_id = inp.wave_id or _next_wave_id(state)
    state["active_wave"] = {
        "wave_id": wave_id,
        "state": "WAVE_ACTIVE",
        "started_at": utc_now_iso(),
        "planned_flow_pass_completed": False,
    }
    _sync_commits(inp, state)
    _append_wave_event(inp, wave_id, "start_new_test_wave", {"state": "WAVE_ACTIVE"})
    _save_state(inp, state, attempts)
    return {"ok": True, "action": "start_new_test_wave", "active_wave": state["active_wave"]}


def _append_blocker(inp: TrainInput, row: dict[str, Any]) -> None:
    _append_jsonl(inp.blockers_path, row)


def action_record_outcome(inp: TrainInput, state: dict[str, Any], attempts: dict[str, Any]) -> dict[str, Any]:
    if not inp.task_identifier:
        raise ToolError("input_error", "task_identifier is required for record_test_outcome", stage="input")
    if not inp.task_outcome:
        raise ToolError("input_error", "task_outcome is required for record_test_outcome", stage="input")

    tasks = attempts.get("tasks")
    if not isinstance(tasks, dict):
        tasks = {}
        attempts["tasks"] = tasks

    entry_raw = tasks.get(inp.task_identifier)
    entry = entry_raw if isinstance(entry_raw, dict) else {}
    entry.setdefault("failed_attempts", 0)
    entry.setdefault("pass_with_rework_count", 0)

    outcome = inp.task_outcome
    if outcome == "failed":
        entry["failed_attempts"] = int(entry.get("failed_attempts", 0)) + 1
    elif outcome == "pass_with_rework":
        entry["pass_with_rework_count"] = int(entry.get("pass_with_rework_count", 0)) + 1

    wave = state.get("active_wave") if isinstance(state.get("active_wave"), dict) else {}
    wave_id = _str(wave.get("wave_id"))
    entry["last_outcome"] = outcome
    entry["last_wave_id"] = wave_id
    entry["updated_at"] = utc_now_iso()

    escalated = False
    reasons: list[str] = []
    if int(entry.get("failed_attempts", 0)) >= 3:
        escalated = True
        reasons.append("failed_attempts>=3")
    if int(entry.get("pass_with_rework_count", 0)) >= 2:
        escalated = True
        reasons.append("pass_with_rework_count>=2")

    if escalated:
        entry["needs_orchestrator_review"] = True
        entry["escalation_reason"] = ", ".join(reasons)
        _append_blocker(
            inp,
            {
                "timestamp": utc_now_iso(),
                "status": "active",
                "task_identifier": inp.task_identifier,
                "wave_id": wave_id,
                "stage": "test-train",
                "worker_role": "tester",
                "blocker_code": "test_loop_escalation",
                "category": "test-train",
                "summary": f"task escalated due to loop limits ({entry['escalation_reason']})",
                "signature": inp.blocker_fingerprint or f"{inp.task_identifier}:{entry['escalation_reason']}",
                "fingerprint": f"test-train|test_loop_escalation|{inp.task_identifier}",
                "retryable": True,
                "source_tool": TOOL,
            },
        )

    tasks[inp.task_identifier] = entry
    _append_wave_event(
        inp,
        wave_id,
        "record_test_outcome",
        {
            "task_identifier": inp.task_identifier,
            "task_outcome": outcome,
            "failed_attempts": entry.get("failed_attempts"),
            "pass_with_rework_count": entry.get("pass_with_rework_count"),
            "escalated": escalated,
        },
    )
    _save_state(inp, state, attempts)
    return {
        "ok": True,
        "action": "record_test_outcome",
        "task_identifier": inp.task_identifier,
        "task_state": entry,
    }


def action_render_summary(inp: TrainInput, state: dict[str, Any], attempts: dict[str, Any]) -> dict[str, Any]:
    wave = state.get("active_wave") if isinstance(state.get("active_wave"), dict) else {}
    wave_id = _str(wave.get("wave_id")) or "unknown-wave"

    tasks = attempts.get("tasks") if isinstance(attempts.get("tasks"), dict) else {}
    wave_tasks = [v for v in tasks.values() if isinstance(v, dict) and _str(v.get("last_wave_id")) == wave_id]
    validated = sum(1 for v in wave_tasks if _str(v.get("last_outcome")) in {"passed", "pass_with_rework"})
    escalated = sum(1 for v in wave_tasks if _bool(v.get("needs_orchestrator_review"), False))

    token_summary = _read_json(
        inp.thread_token_summary_path,
        {
            "project_total_tokens": 0,
            "tokens_by_worker_type": {},
        },
    )
    project_total_tokens = int(token_summary.get("project_total_tokens", 0) or 0)
    by_worker = token_summary.get("tokens_by_worker_type")
    if not isinstance(by_worker, dict):
        by_worker = {}

    tokens_per_validated = (
        round(project_total_tokens / validated, 2) if validated > 0 else None
    )

    lines = [
        "# Test Wave Summary",
        "",
        f"Generated: {utc_now_iso()}",
        f"Wave ID: {wave_id}",
        f"Wave State: {_str(wave.get('state')) or 'unknown'}",
        "",
        "## Validation Throughput",
        f"- Tasks validated in wave: **{validated}**",
        f"- Escalated tasks in wave: **{escalated}**",
        "",
        "## Token Governance",
        f"- Project total tokens: **{project_total_tokens}**",
        f"- Tokens per validated task KPI: **{tokens_per_validated if tokens_per_validated is not None else 'n/a'}**",
        "- Tokens by worker type:",
    ]
    if by_worker:
        for worker_type in sorted(by_worker.keys()):
            lines.append(f"  - {worker_type}: **{by_worker[worker_type]}**")
    else:
        lines.append("  - none")

    inp.wave_summary_path.parent.mkdir(parents=True, exist_ok=True)
    inp.wave_summary_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    _append_wave_event(inp, wave_id, "render_wave_summary", {"path": str(inp.wave_summary_path)})
    _save_state(inp, state, attempts)
    return {
        "ok": True,
        "action": "render_wave_summary",
        "wave_summary_path": str(inp.wave_summary_path),
        "tasks_validated_in_wave": validated,
        "escalated_tasks_in_wave": escalated,
        "project_total_tokens": project_total_tokens,
    }


def run(inp: TrainInput) -> dict[str, Any]:
    state, attempts = _load_state(inp)
    state["test_train_mode"] = inp.test_train_mode
    state["test_branch"] = inp.test_branch
    state["test_next_branch"] = inp.test_next_branch
    if inp.shared_test_base_url:
        state["shared_test_base_url"] = inp.shared_test_base_url

    if inp.action == "bootstrap":
        return action_bootstrap(inp, state, attempts)
    if inp.action == "sync_state":
        return action_sync_state(inp, state, attempts)
    if inp.action == "close_test_wave":
        return action_close_wave(inp, state, attempts)
    if inp.action == "evaluate_promotion_gate":
        return action_evaluate_gate(inp, state, attempts)
    if inp.action == "promote_test_next_to_test":
        return action_promote(inp, state, attempts)
    if inp.action == "deploy_test_branch":
        return action_deploy(inp, state, attempts)
    if inp.action == "start_new_test_wave":
        return action_start_wave(inp, state, attempts)
    if inp.action == "record_test_outcome":
        return action_record_outcome(inp, state, attempts)
    if inp.action == "render_wave_summary":
        return action_render_summary(inp, state, attempts)

    raise ToolError("input_error", f"unsupported action: {inp.action}", stage="input")


def print_json(payload: dict[str, Any], pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=False))
    else:
        print(json.dumps(payload, sort_keys=False, separators=(",", ":")))


def main() -> int:
    args = parse_args()
    try:
        payload = _read_input(args.input_json)
        inp = build_input(payload)
        out = run(inp)
        print_json({"schema_version": SCHEMA_VERSION, "tool": TOOL, "tool_version": TOOL_VERSION, **out}, args.json_pretty)
        return 0 if out.get("ok") else 1
    except ToolError as exc:
        out = {
            "schema_version": SCHEMA_VERSION,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "ok": False,
            "error": {"code": exc.code, "message": exc.message, "stage": exc.stage},
        }
        print_json(out, args.json_pretty)
        return 1
    except Exception as exc:  # noqa: BLE001
        out = {
            "schema_version": SCHEMA_VERSION,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "ok": False,
            "error": {"code": "runtime_error", "message": str(exc), "stage": "runtime"},
        }
        print_json(out, args.json_pretty)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
