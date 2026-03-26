#!/usr/bin/env python3
"""Deterministic merge-evidence checker for lane merge-validation tasks."""

from __future__ import annotations

import argparse
import json
import subprocess
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


def _to_rel(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(path.resolve())


def _git_stdout(repo_root: Path, args: list[str]) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def _git_ok(repo_root: Path, args: list[str]) -> bool:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    return proc.returncode == 0


def _resolve_commit(repo_root: Path, ref: str) -> str:
    if not _as_str(ref):
        return ""
    return _git_stdout(repo_root, ["rev-parse", "--verify", f"{ref}^{{commit}}"])


def _load_lane_merge_evidence(
    *,
    repo_root: Path,
    task_id: str,
    lane_id: str,
) -> tuple[Path | None, dict[str, Any] | None]:
    candidates: list[tuple[str, str, Path, dict[str, Any]]] = []
    for path in sorted(repo_root.rglob("*MERGE_EVIDENCE*.json")):
        if not path.is_file():
            continue
        try:
            payload = _load_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        if _as_str(payload.get("task_identifier")) != task_id:
            continue
        if _as_str(payload.get("lane_id")) != lane_id:
            continue
        updated_at = _as_str(payload.get("updated_at"))
        candidates.append((updated_at, _to_rel(path, repo_root), path, payload))

    if not candidates:
        return None, None

    # Pick the newest timestamp; use relative path as deterministic tie-breaker.
    candidates.sort(key=lambda row: (row[0], row[1]))
    _, _, selected_path, selected_payload = candidates[-1]
    return selected_path, selected_payload


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


def check_lane_merge_evidence(
    *,
    repo_root: Path,
    required_task_ids: list[str],
    lane_id: str,
    require_ancestor: bool,
) -> dict[str, Any]:
    checked_at = utc_now_iso()
    tasks = _normalize_task_ids(required_task_ids)
    normalized_lane_id = _as_str(lane_id)
    errors: list[dict[str, str]] = []
    task_results: list[dict[str, Any]] = []

    for task_id in tasks:
        issues: list[dict[str, str]] = []
        evidence_path, payload = _load_lane_merge_evidence(
            repo_root=repo_root,
            task_id=task_id,
            lane_id=normalized_lane_id,
        )
        if evidence_path is None or payload is None:
            issues.append(
                {
                    "code": "lane_merge_evidence_missing",
                    "message": (
                        f"lane merge evidence not found for task {task_id} lane {normalized_lane_id}; "
                        "expected a *MERGE_EVIDENCE*.json file with matching task_identifier/lane_id"
                    ),
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

        run_base_before_sha = _as_str(payload.get("run_base_before_sha"))
        run_base_after_sha = _as_str(payload.get("run_base_after_sha"))
        merge_commit_sha = _as_str(payload.get("merge_commit_sha"))
        lane_base_branch = _as_str(payload.get("lane_base_branch"))
        run_base_branch = _as_str(payload.get("run_base_branch"))

        if not run_base_before_sha:
            issues.append(
                {
                    "code": "run_base_before_missing",
                    "message": f"task {task_id} merge evidence missing run_base_before_sha",
                }
            )
        if not run_base_after_sha:
            issues.append(
                {
                    "code": "run_base_after_missing",
                    "message": f"task {task_id} merge evidence missing run_base_after_sha",
                }
            )
        if not merge_commit_sha:
            issues.append(
                {
                    "code": "merge_commit_missing",
                    "message": f"task {task_id} merge evidence missing merge_commit_sha",
                }
            )

        if run_base_before_sha and not _resolve_commit(repo_root, run_base_before_sha):
            issues.append(
                {
                    "code": "run_base_before_unresolvable",
                    "message": f"task {task_id} run_base_before_sha does not resolve to a commit: {run_base_before_sha}",
                }
            )

        if run_base_after_sha and not _resolve_commit(repo_root, run_base_after_sha):
            issues.append(
                {
                    "code": "run_base_after_unresolvable",
                    "message": f"task {task_id} run_base_after_sha does not resolve to a commit: {run_base_after_sha}",
                }
            )

        if merge_commit_sha and not _resolve_commit(repo_root, merge_commit_sha):
            issues.append(
                {
                    "code": "merge_commit_unresolvable",
                    "message": f"task {task_id} merge_commit_sha does not resolve to a commit: {merge_commit_sha}",
                }
            )

        if run_base_before_sha and run_base_after_sha and not _git_ok(
            repo_root, ["merge-base", "--is-ancestor", run_base_before_sha, run_base_after_sha]
        ):
            issues.append(
                {
                    "code": "run_base_lineage_mismatch",
                    "message": (
                        f"task {task_id} run_base_before_sha is not an ancestor of run_base_after_sha "
                        f"({run_base_before_sha} !<= {run_base_after_sha})"
                    ),
                }
            )

        resolved_run_base_tip = _resolve_commit(repo_root, run_base_branch)
        if not run_base_branch:
            issues.append(
                {
                    "code": "run_base_branch_missing",
                    "message": f"task {task_id} merge evidence missing run_base_branch",
                }
            )
        elif not resolved_run_base_tip:
            issues.append(
                {
                    "code": "run_base_branch_unresolvable",
                    "message": f"task {task_id} run_base_branch does not resolve to a commit: {run_base_branch}",
                }
            )
        elif run_base_after_sha and resolved_run_base_tip != run_base_after_sha:
            issues.append(
                {
                    "code": "run_base_after_mismatch",
                    "message": (
                        f"task {task_id} run_base_after_sha does not match {run_base_branch} tip "
                        f"({run_base_after_sha} != {resolved_run_base_tip})"
                    ),
                }
            )

        if require_ancestor and run_base_after_sha and not _git_ok(
            repo_root, ["merge-base", "--is-ancestor", run_base_after_sha, "HEAD"]
        ):
            issues.append(
                {
                    "code": "required_ancestor_missing",
                    "message": (
                        f"task {task_id} requires run_base_after_sha to be ancestor of HEAD, "
                        f"but check failed for {run_base_after_sha}"
                    ),
                }
            )

        targeted_test = payload.get("targeted_test")
        if not isinstance(targeted_test, dict):
            issues.append(
                {
                    "code": "targeted_test_missing",
                    "message": f"task {task_id} merge evidence missing targeted_test object",
                }
            )
        else:
            if _as_str(targeted_test.get("result")).lower() != "pass":
                issues.append(
                    {
                        "code": "targeted_test_not_passed",
                        "message": f"task {task_id} targeted_test.result must be pass",
                    }
                )
            if not _as_str(targeted_test.get("command")):
                issues.append(
                    {
                        "code": "targeted_test_command_missing",
                        "message": f"task {task_id} targeted_test.command is missing",
                    }
                )

        review_summary = payload.get("review_summary")
        if not isinstance(review_summary, dict):
            issues.append(
                {
                    "code": "review_summary_missing",
                    "message": f"task {task_id} merge evidence missing review_summary object",
                }
            )
        else:
            review_status = _as_str(review_summary.get("review_status")).lower()
            blocker_status = _as_str(review_summary.get("blocker_status")).lower()
            if review_status != "pass":
                issues.append(
                    {
                        "code": "review_not_passed",
                        "message": f"task {task_id} review_summary.review_status must be pass",
                    }
                )
            if blocker_status != "none":
                issues.append(
                    {
                        "code": "review_has_blockers",
                        "message": f"task {task_id} review_summary.blocker_status must be none",
                    }
                )

        fan_in = payload.get("fan_in")
        conflicts = fan_in.get("conflicts") if isinstance(fan_in, dict) else []
        has_conflicts = isinstance(conflicts, list) and len(conflicts) > 0
        llm_route = payload.get("llm_merge_recovery_routing")
        if has_conflicts:
            if not isinstance(llm_route, dict):
                issues.append(
                    {
                        "code": "llm_merge_recovery_missing",
                        "message": (
                            f"task {task_id} has merge conflicts in fan_in.conflicts but missing "
                            "llm_merge_recovery_routing evidence"
                        ),
                    }
                )
            else:
                if not _as_bool(llm_route.get("triggered")):
                    issues.append(
                        {
                            "code": "llm_merge_recovery_not_triggered",
                            "message": (
                                f"task {task_id} has merge conflicts but llm_merge_recovery_routing.triggered is false"
                            ),
                        }
                    )
                if not _as_str(llm_route.get("route")):
                    issues.append(
                        {
                            "code": "llm_merge_recovery_route_missing",
                            "message": f"task {task_id} llm_merge_recovery_routing.route is missing",
                        }
                    )
                if _as_str(llm_route.get("status")).lower() != "applied":
                    issues.append(
                        {
                            "code": "llm_merge_recovery_not_applied",
                            "message": f"task {task_id} llm_merge_recovery_routing.status must be applied",
                        }
                    )

        task_ok = len(issues) == 0
        task_results.append(
            _task_result(
                task_id,
                ok=task_ok,
                merged_commit=merge_commit_sha or None,
                verification_ref=_to_rel(evidence_path, repo_root),
                branch=lane_base_branch or None,
                issues=issues,
            )
        )
        if not task_ok:
            errors.extend(issues)

    return {
        "ok": len(errors) == 0,
        "tool": TOOL_NAME,
        "tool_version": TOOL_VERSION,
        "checked_at": checked_at,
        "repo_root": str(repo_root),
        "mode": "lane-evidence",
        "lane_id": normalized_lane_id,
        "require_ancestor": require_ancestor,
        "required_task_ids": tasks,
        "expected_branch": "lane merge evidence",
        "done_registry": "",
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
    _emit(log_root, f"Mode: {_as_str(result.get('mode')) or 'done-registry'}")
    lane_id = _as_str(result.get("lane_id"))
    if lane_id:
        _emit(log_root, f"Lane id: {lane_id}")
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
    parser.add_argument(
        "--lane-id",
        default="",
        help="Optional lane id for lane-evidence mode (for example phase-1/lane-a).",
    )
    parser.add_argument(
        "--require-ancestor",
        action="store_true",
        help="When --lane-id is provided, require run_base_after_sha to be ancestor of HEAD.",
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
    explicit_task_ids = _normalize_task_ids(args.task_id)
    expected_branch = _as_str(args.expected_branch) or "RAB-BASE"
    log_root = Path(args.log_root).expanduser().resolve()
    lane_id = _as_str(args.lane_id)

    if lane_id:
        if not explicit_task_ids:
            result = {
                "ok": False,
                "tool": TOOL_NAME,
                "tool_version": TOOL_VERSION,
                "checked_at": utc_now_iso(),
                "repo_root": str(repo_root),
                "mode": "lane-evidence",
                "lane_id": lane_id,
                "require_ancestor": bool(args.require_ancestor),
                "required_task_ids": [],
                "expected_branch": "lane merge evidence",
                "done_registry": "",
                "tasks": [],
                "errors": [
                    {
                        "code": "lane_mode_requires_task_id",
                        "message": "--lane-id requires at least one --task-id",
                    }
                ],
            }
        else:
            result = check_lane_merge_evidence(
                repo_root=repo_root,
                required_task_ids=explicit_task_ids,
                lane_id=lane_id,
                require_ancestor=bool(args.require_ancestor),
            )
    else:
        task_ids = explicit_task_ids or list(DEFAULT_TASK_IDS)
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
