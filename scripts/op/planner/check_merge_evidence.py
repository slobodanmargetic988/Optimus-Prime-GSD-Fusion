#!/usr/bin/env python3
"""Deterministic merge-evidence checker for lane merge-validation tasks."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TOOL_NAME = "check-merge-evidence"
TOOL_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
DEFAULT_TASK_IDS = ("TASK-003", "TASK-006", "TASK-009")
DEFAULT_DONE_REGISTRY_PATH = Path("reports/optimus-prime/planning/DONE_TASKS_REGISTRY.json")
DEFAULT_LOG_ROOT = Path("/Users/slobodan/projects/LOGS")
LOG_SCOPE = "op-merge-evidence-checker"
LOG_MAX_BYTES = 3 * 1024 * 1024 * 1024
LOG_CHECK_INTERVAL_SECONDS = 900


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_str(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ""
    return str(value).strip()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return _load_json(path)
    except (OSError, json.JSONDecodeError):
        return default


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def _maintenance_epoch(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _maintain_logs(log_root: Path) -> None:
    now_epoch = time.time()
    scope_root = log_root / LOG_SCOPE
    state_path = scope_root / "MAINTENANCE_STATE.json"
    state = _safe_load_json(state_path, {})
    if isinstance(state, dict):
        last_checked_epoch = _maintenance_epoch(state.get("last_checked_epoch"))
        if now_epoch - last_checked_epoch < float(LOG_CHECK_INTERVAL_SECONDS):
            return

    log_root.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    for path in log_root.rglob("*"):
        if not path.is_file() or path == state_path:
            continue
        files.append(path)

    total_bytes = 0
    for path in files:
        try:
            total_bytes += int(path.stat().st_size)
        except OSError:
            continue

    if total_bytes > LOG_MAX_BYTES:
        def _mtime(item: Path) -> float:
            try:
                return float(item.stat().st_mtime)
            except OSError:
                return 0.0

        for path in sorted(files, key=_mtime):
            if total_bytes <= LOG_MAX_BYTES:
                break
            try:
                original_size = int(path.stat().st_size)
                path.write_bytes(b"")
            except OSError:
                continue
            total_bytes = max(0, total_bytes - original_size)

    _atomic_write_json(
        state_path,
        {
            "schema_version": SCHEMA_VERSION,
            "updated_at": utc_now_iso(),
            "last_checked_epoch": int(now_epoch),
            "total_bytes": int(total_bytes),
            "max_bytes": int(LOG_MAX_BYTES),
            "root": str(log_root),
        },
    )


def _append_log(log_root: Path, line: str) -> None:
    try:
        _maintain_logs(log_root)
        log_path = log_root / LOG_SCOPE / "events.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        return


def _emit(log_root: Path, message: str) -> None:
    line = f"[{utc_now_iso()}] {message}"
    print(line, flush=True)
    _append_log(log_root, line)


def _normalize_task_ids(task_ids: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in task_ids:
        text = _as_str(raw)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _as_bool(value: Any) -> bool:
    return bool(value)


def _as_rel_path(path_text: str, repo_root: Path) -> Path:
    candidate = Path(path_text).expanduser()
    if candidate.is_absolute():
        return candidate
    return (repo_root / candidate).resolve()


def _task_result(
    task_id: str,
    *,
    ok: bool,
    merged_commit: str | None,
    verification_ref: str | None,
    branch: str | None,
    issues: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "ok": ok,
        "branch": branch,
        "merged_commit": merged_commit,
        "verification_ref": verification_ref,
        "issues": issues,
    }


def check_merge_evidence(
    *,
    repo_root: Path,
    done_registry_path: Path,
    required_task_ids: list[str],
    expected_branch: str,
) -> dict[str, Any]:
    checked_at = utc_now_iso()
    tasks = _normalize_task_ids(required_task_ids)
    errors: list[dict[str, str]] = []
    task_results: list[dict[str, Any]] = []

    if not done_registry_path.exists():
        return {
            "ok": False,
            "tool": TOOL_NAME,
            "tool_version": TOOL_VERSION,
            "checked_at": checked_at,
            "repo_root": str(repo_root),
            "done_registry": str(done_registry_path),
            "required_task_ids": tasks,
            "expected_branch": expected_branch,
            "tasks": [],
            "errors": [
                {
                    "code": "done_registry_missing",
                    "message": f"done registry file not found: {done_registry_path}",
                }
            ],
        }

    try:
        registry_payload = _load_json(done_registry_path)
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "tool": TOOL_NAME,
            "tool_version": TOOL_VERSION,
            "checked_at": checked_at,
            "repo_root": str(repo_root),
            "done_registry": str(done_registry_path),
            "required_task_ids": tasks,
            "expected_branch": expected_branch,
            "tasks": [],
            "errors": [
                {
                    "code": "done_registry_invalid_json",
                    "message": f"unable to parse done registry JSON: {exc}",
                }
            ],
        }

    if not isinstance(registry_payload, dict):
        return {
            "ok": False,
            "tool": TOOL_NAME,
            "tool_version": TOOL_VERSION,
            "checked_at": checked_at,
            "repo_root": str(repo_root),
            "done_registry": str(done_registry_path),
            "required_task_ids": tasks,
            "expected_branch": expected_branch,
            "tasks": [],
            "errors": [
                {
                    "code": "done_registry_invalid_shape",
                    "message": "done registry must be a JSON object",
                }
            ],
        }

    merged_rows_raw = registry_payload.get("merged_tasks")
    merged_rows = [row for row in merged_rows_raw if isinstance(row, dict)] if isinstance(merged_rows_raw, list) else []
    merged_index: dict[str, list[dict[str, Any]]] = {}
    for row in merged_rows:
        task_id = _as_str(row.get("task_id"))
        if not task_id:
            continue
        merged_index.setdefault(task_id, []).append(row)

    done_task_ids_raw = registry_payload.get("done_task_ids")
    done_task_ids = {
        _as_str(item)
        for item in done_task_ids_raw
        if isinstance(item, str) and _as_str(item)
    } if isinstance(done_task_ids_raw, list) else set()

    for task_id in tasks:
        issues: list[dict[str, str]] = []
        task_rows = merged_index.get(task_id, [])
        if not task_rows:
            issues.append(
                {
                    "code": "merge_row_missing",
                    "message": f"task {task_id} has no merged entry in DONE_TASKS_REGISTRY.merged_tasks",
                }
            )
            task_results.append(
                _task_result(
                    task_id,
                    ok=False,
                    merged_commit=None,
                    verification_ref=None,
                    branch=None,
                    issues=issues,
                )
            )
            errors.extend(issues)
            continue

        merged_row = task_rows[-1]
        if len(task_rows) > 1:
            issues.append(
                {
                    "code": "merge_row_duplicate",
                    "message": f"task {task_id} has {len(task_rows)} merge rows; newest row was selected",
                }
            )
        merged_commit = _as_str(merged_row.get("merged_commit"))
        verification_ref = _as_str(merged_row.get("verification_ref"))
        branch = _as_str(merged_row.get("branch"))

        if done_task_ids and task_id not in done_task_ids:
            issues.append(
                {
                    "code": "done_task_missing",
                    "message": f"task {task_id} is merged but absent from done_task_ids",
                }
            )

        if branch != expected_branch:
            issues.append(
                {
                    "code": "branch_mismatch",
                    "message": f"task {task_id} merged branch mismatch: expected {expected_branch}, got {branch or 'empty'}",
                }
            )

        if not _as_bool(merged_row.get("verification_passed")):
            issues.append(
                {
                    "code": "verification_not_passed",
                    "message": f"task {task_id} has verification_passed=false in DONE_TASKS_REGISTRY",
                }
            )

        if not merged_commit:
            issues.append(
                {
                    "code": "merged_commit_missing",
                    "message": f"task {task_id} merged_commit is missing in DONE_TASKS_REGISTRY",
                }
            )

        if not verification_ref:
            issues.append(
                {
                    "code": "verification_ref_missing",
                    "message": f"task {task_id} verification_ref is missing in DONE_TASKS_REGISTRY",
                }
            )
        else:
            verification_path = _as_rel_path(verification_ref, repo_root)
            if not verification_path.exists():
                issues.append(
                    {
                        "code": "verification_file_missing",
                        "message": f"task {task_id} MERGE_VALIDATION file missing: {verification_path}",
                    }
                )
            else:
                try:
                    validation_payload = _load_json(verification_path)
                except (OSError, json.JSONDecodeError) as exc:
                    issues.append(
                        {
                            "code": "verification_file_invalid_json",
                            "message": f"task {task_id} MERGE_VALIDATION parse error: {exc}",
                        }
                    )
                else:
                    if not isinstance(validation_payload, dict):
                        issues.append(
                            {
                                "code": "verification_invalid_shape",
                                "message": f"task {task_id} MERGE_VALIDATION must be a JSON object",
                            }
                        )
                    else:
                        validation_task = _as_str(validation_payload.get("task_id"))
                        if validation_task != task_id:
                            issues.append(
                                {
                                    "code": "verification_task_mismatch",
                                    "message": f"task {task_id} MERGE_VALIDATION task_id mismatch: {validation_task or 'empty'}",
                                }
                            )
                        if not _as_bool(validation_payload.get("ok")):
                            issues.append(
                                {
                                    "code": "verification_not_ok",
                                    "message": f"task {task_id} MERGE_VALIDATION reports ok=false",
                                }
                            )
                        if not _as_bool(validation_payload.get("merge_proof_passed")):
                            issues.append(
                                {
                                    "code": "merge_proof_not_passed",
                                    "message": f"task {task_id} MERGE_VALIDATION reports merge_proof_passed=false",
                                }
                            )
                        validation_commit = _as_str(validation_payload.get("merged_commit"))
                        if merged_commit and validation_commit and validation_commit != merged_commit:
                            issues.append(
                                {
                                    "code": "merged_commit_mismatch",
                                    "message": (
                                        f"task {task_id} merged_commit mismatch between "
                                        f"DONE_TASKS_REGISTRY ({merged_commit}) and MERGE_VALIDATION ({validation_commit})"
                                    ),
                                }
                            )

        task_ok = not any(issue.get("code") != "merge_row_duplicate" for issue in issues)
        task_results.append(
            _task_result(
                task_id,
                ok=task_ok,
                merged_commit=merged_commit or None,
                verification_ref=verification_ref or None,
                branch=branch or None,
                issues=issues,
            )
        )
        if not task_ok:
            errors.extend(issue for issue in issues if issue.get("code") != "merge_row_duplicate")

    return {
        "ok": len(errors) == 0,
        "tool": TOOL_NAME,
        "tool_version": TOOL_VERSION,
        "checked_at": checked_at,
        "repo_root": str(repo_root),
        "done_registry": str(done_registry_path),
        "required_task_ids": tasks,
        "expected_branch": expected_branch,
        "tasks": task_results,
        "errors": errors,
    }


def _emit_human_report(result: dict[str, Any], *, log_root: Path) -> None:
    required_tasks = result.get("required_task_ids")
    tasks = result.get("tasks")
    errors = result.get("errors")
    task_count = len(tasks) if isinstance(tasks, list) else 0
    error_count = len(errors) if isinstance(errors, list) else 0

    _emit(log_root, "Merge evidence checker started.")
    _emit(log_root, f"Repo root: {result.get('repo_root')}")
    _emit(log_root, f"Done registry: {result.get('done_registry')}")
    _emit(log_root, f"Expected branch: {result.get('expected_branch')}")
    _emit(log_root, f"Required tasks: {', '.join(required_tasks) if isinstance(required_tasks, list) and required_tasks else '(none)'}")

    if isinstance(tasks, list):
        for row in tasks:
            if not isinstance(row, dict):
                continue
            task_id = _as_str(row.get("task_id")) or "TASK-UNKNOWN"
            if row.get("ok"):
                short_sha = _as_str(row.get("merged_commit"))[:12] or "unknown"
                verification_ref = _as_str(row.get("verification_ref")) or "unknown"
                _emit(
                    log_root,
                    f"PASS {task_id}: merge evidence verified (merged_commit={short_sha}, verification_ref={verification_ref}).",
                )
                continue

            row_issues = row.get("issues") if isinstance(row.get("issues"), list) else []
            if row_issues:
                first_issue = row_issues[0] if isinstance(row_issues[0], dict) else {}
                _emit(
                    log_root,
                    f"FAIL {task_id}: {_as_str(first_issue.get('message')) or 'merge evidence checks failed'}",
                )
                for issue in row_issues[1:]:
                    if not isinstance(issue, dict):
                        continue
                    _emit(log_root, f"DETAIL {task_id}: {_as_str(issue.get('message'))}")
            else:
                _emit(log_root, f"FAIL {task_id}: merge evidence checks failed")

    if result.get("ok"):
        _emit(log_root, f"Overall result: PASS ({task_count} tasks verified).")
    else:
        _emit(log_root, f"Overall result: FAIL ({error_count} blocking issue(s) across {task_count} task(s)).")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Check branch-merge evidence in DONE_TASKS_REGISTRY and referenced MERGE_VALIDATION artifacts. "
            "Defaults to TASK-003/TASK-006/TASK-009 for lane merge-validation gates."
        )
    )
    parser.add_argument("--repo-root", default=".", help="Repository root containing reports/optimus-prime")
    parser.add_argument(
        "--done-registry",
        default=str(DEFAULT_DONE_REGISTRY_PATH),
        help="Path to DONE_TASKS_REGISTRY.json (absolute or relative to --repo-root)",
    )
    parser.add_argument(
        "--task-id",
        action="append",
        default=[],
        help="Task ID to verify (repeatable). Defaults to TASK-003, TASK-006, TASK-009 when omitted.",
    )
    parser.add_argument("--expected-branch", default="RAB-BASE", help="Expected merge target branch in merged rows")
    parser.add_argument(
        "--log-root",
        default=str(DEFAULT_LOG_ROOT),
        help="Root log directory. Defaults to /Users/slobodan/projects/LOGS",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).expanduser().resolve()
    done_registry_arg = Path(args.done_registry).expanduser()
    done_registry_path = done_registry_arg if done_registry_arg.is_absolute() else (repo_root / done_registry_arg).resolve()
    task_ids = _normalize_task_ids(args.task_id) or list(DEFAULT_TASK_IDS)
    expected_branch = _as_str(args.expected_branch) or "RAB-BASE"
    log_root = Path(args.log_root).expanduser().resolve()

    result = check_merge_evidence(
        repo_root=repo_root,
        done_registry_path=done_registry_path,
        required_task_ids=task_ids,
        expected_branch=expected_branch,
    )
    _emit_human_report(result, log_root=log_root)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
