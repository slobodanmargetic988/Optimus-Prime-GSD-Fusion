#!/usr/bin/env python3
"""Deterministic tester preflight resolver for branch/lineage/fallback readiness."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TOOL = "tester-preflight-resolver"
DEFAULT_FALLBACK_SUFFIX = "-test"


class ToolError(Exception):
    def __init__(self, code: str, message: str, stage: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.stage = stage


@dataclass
class PreflightInput:
    worktree_root: Path
    task_identifier: str
    branch_name: str
    start_from_branch: str
    start_from_commit: str
    target_head_commit: str | None
    fallback_suffix: str
    allow_fallback: bool
    dry_run: bool


class CommandRunner:
    def run(self, cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)


def as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def load_json(path: str) -> dict[str, Any]:
    if path == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ToolError("input_error", "Input payload must be a JSON object", stage="input")
    return data


def must_nonempty_str(data: dict[str, Any], key: str, fallback: Any = None) -> str:
    value = data.get(key, fallback)
    if not isinstance(value, str) or not value.strip():
        raise ToolError("input_error", f"{key} is required and must be a non-empty string", stage="input")
    return value.strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve tester packet branch preflight state")
    parser.add_argument("--input-json", help="JSON payload path or '-' for stdin")
    parser.add_argument("--worktree-root")
    parser.add_argument("--task-identifier")
    parser.add_argument("--branch-name")
    parser.add_argument("--start-from-branch")
    parser.add_argument("--start-from-commit")
    parser.add_argument("--target-head-commit")
    parser.add_argument("--fallback-suffix")
    parser.add_argument("--allow-fallback", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json-pretty", action="store_true")
    return parser.parse_args()


def parse_input(args: argparse.Namespace) -> PreflightInput:
    payload: dict[str, Any] = {}
    if args.input_json:
        payload = load_json(args.input_json)

    worktree_raw = must_nonempty_str(payload, "worktree_root", fallback=args.worktree_root or ".")
    worktree_root = Path(worktree_raw).expanduser().resolve()
    if not worktree_root.exists() or not worktree_root.is_dir():
        raise ToolError("input_error", f"worktree_root does not exist or is not a directory: {worktree_root}", stage="input")

    fallback_suffix = payload.get("fallback_suffix", args.fallback_suffix or DEFAULT_FALLBACK_SUFFIX)
    if not isinstance(fallback_suffix, str) or not fallback_suffix.strip():
        raise ToolError("input_error", "fallback_suffix must be a non-empty string", stage="input")

    target_head_commit = payload.get("target_head_commit", args.target_head_commit)
    if target_head_commit is not None:
        if not isinstance(target_head_commit, str) or not target_head_commit.strip():
            raise ToolError("input_error", "target_head_commit must be a non-empty string when provided", stage="input")
        target_head_commit = target_head_commit.strip()

    return PreflightInput(
        worktree_root=worktree_root,
        task_identifier=must_nonempty_str(payload, "task_identifier", fallback=args.task_identifier),
        branch_name=must_nonempty_str(payload, "branch_name", fallback=args.branch_name),
        start_from_branch=must_nonempty_str(payload, "start_from_branch", fallback=args.start_from_branch),
        start_from_commit=must_nonempty_str(payload, "start_from_commit", fallback=args.start_from_commit),
        target_head_commit=target_head_commit,
        fallback_suffix=fallback_suffix.strip(),
        allow_fallback=as_bool(payload.get("allow_fallback", args.allow_fallback), default=True),
        dry_run=as_bool(payload.get("dry_run", args.dry_run), default=False),
    )


def git(runner: CommandRunner, cwd: Path, *parts: str) -> subprocess.CompletedProcess[str]:
    return runner.run(["git", *parts], cwd=cwd)


def ensure_git_context(cfg: PreflightInput, runner: CommandRunner) -> None:
    inside = git(runner, cfg.worktree_root, "rev-parse", "--is-inside-work-tree")
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        raise ToolError("worktree_invalid", "worktree_root is not a git worktree", stage="preflight")

    start_commit = git(runner, cfg.worktree_root, "rev-parse", "--verify", f"{cfg.start_from_commit}^{{commit}}")
    if start_commit.returncode != 0:
        raise ToolError("invalid_start_commit", f"start_from_commit not found: {cfg.start_from_commit}", stage="preflight")

    start_branch = git(runner, cfg.worktree_root, "rev-parse", "--verify", f"{cfg.start_from_branch}^{{commit}}")
    if start_branch.returncode != 0:
        raise ToolError("invalid_start_branch", f"start_from_branch not found: {cfg.start_from_branch}", stage="preflight")


def is_active_elsewhere_error(output: str) -> bool:
    text = output.lower()
    tokens = [
        "already checked out at",
        "is already checked out",
        "is already used by worktree",
        "branch is currently checked out",
    ]
    return any(token in text for token in tokens)


def fallback_branch_name(branch_name: str, suffix: str) -> str:
    if branch_name.endswith(suffix):
        return branch_name
    return f"{branch_name}{suffix}"


def branch_exists(cfg: PreflightInput, runner: CommandRunner, branch_name: str) -> bool:
    proc = git(runner, cfg.worktree_root, "show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}")
    return proc.returncode == 0


def checkout_existing_branch(cfg: PreflightInput, runner: CommandRunner, branch_name: str) -> subprocess.CompletedProcess[str]:
    return git(runner, cfg.worktree_root, "checkout", branch_name)


def create_branch_from_anchor(cfg: PreflightInput, runner: CommandRunner, branch_name: str) -> subprocess.CompletedProcess[str]:
    return git(runner, cfg.worktree_root, "checkout", "-b", branch_name, cfg.start_from_commit)


def resolve_branch(cfg: PreflightInput, runner: CommandRunner) -> tuple[str, bool, bool, bool, list[dict[str, Any]]]:
    warnings: list[dict[str, Any]] = []
    assigned_exists = branch_exists(cfg, runner, cfg.branch_name)

    checkout = checkout_existing_branch(cfg, runner, cfg.branch_name)
    if checkout.returncode == 0:
        return cfg.branch_name, False, assigned_exists, False, warnings

    combined = f"{checkout.stdout}\n{checkout.stderr}".strip()
    if not cfg.allow_fallback:
        raise ToolError("checkout_failed", f"Failed to checkout assigned branch: {combined}", stage="checkout")

    if not is_active_elsewhere_error(combined):
        raise ToolError("checkout_failed", f"Assigned branch checkout failed: {combined}", stage="checkout")

    fallback = fallback_branch_name(cfg.branch_name, cfg.fallback_suffix)
    if fallback == cfg.branch_name:
        raise ToolError("fallback_invalid", "Fallback branch resolves to assigned branch; choose a different fallback_suffix", stage="checkout")

    warnings.append(
        {
            "code": "fallback_used",
            "message": f"Assigned branch '{cfg.branch_name}' is active elsewhere; using fallback '{fallback}'",
        }
    )

    fallback_exists = branch_exists(cfg, runner, fallback)
    fallback_created = not fallback_exists
    if fallback_exists:
        fallback_checkout = checkout_existing_branch(cfg, runner, fallback)
    else:
        fallback_checkout = create_branch_from_anchor(cfg, runner, fallback)

    if fallback_checkout.returncode != 0:
        combined_fallback = f"{fallback_checkout.stdout}\n{fallback_checkout.stderr}".strip()
        raise ToolError("fallback_checkout_failed", f"Failed to checkout fallback branch '{fallback}': {combined_fallback}", stage="checkout")

    return fallback, True, assigned_exists, fallback_created, warnings


def current_head(cfg: PreflightInput, runner: CommandRunner) -> str:
    proc = git(runner, cfg.worktree_root, "rev-parse", "HEAD")
    if proc.returncode != 0:
        raise ToolError("head_resolve_failed", proc.stderr.strip() or proc.stdout.strip() or "Failed to resolve HEAD", stage="verify")
    return proc.stdout.strip()


def lineage_ok(cfg: PreflightInput, runner: CommandRunner, head_commit: str) -> bool:
    proc = git(runner, cfg.worktree_root, "merge-base", "--is-ancestor", cfg.start_from_commit, head_commit)
    return proc.returncode == 0


def head_matches_target(cfg: PreflightInput, runner: CommandRunner, head_commit: str) -> bool:
    if cfg.target_head_commit is None:
        return True
    target = git(runner, cfg.worktree_root, "rev-parse", "--verify", f"{cfg.target_head_commit}^{{commit}}")
    if target.returncode != 0:
        return False
    return head_commit == target.stdout.strip()


def execute(cfg: PreflightInput, runner: CommandRunner | None = None) -> dict[str, Any]:
    if runner is None:
        runner = CommandRunner()

    warnings: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    if cfg.dry_run:
        warnings.append({"code": "dry_run", "message": "Dry-run mode enabled; no branch checkout performed"})
        if cfg.target_head_commit is not None:
            warnings.append({"code": "target_head_skipped", "message": "target_head_commit verification skipped in dry-run mode"})
        return {
            "ok": True,
            "tool": TOOL,
            "intended_branch": cfg.branch_name,
            "resolved_branch": cfg.branch_name,
            "fallback_used": False,
            "branch_exists": None,
            "fallback_created": False,
            "resolved_head_commit": "DRY_RUN_HEAD",
            "lineage_ok": True,
            "head_matches_target": True,
            "next_step": "run_tests",
            "warnings": warnings,
            "errors": errors,
        }

    try:
        ensure_git_context(cfg, runner)
        resolved_branch, used_fallback, assigned_exists, fallback_created, resolve_warnings = resolve_branch(cfg, runner)
        warnings.extend(resolve_warnings)

        head_commit = current_head(cfg, runner)
        lineage = lineage_ok(cfg, runner, head_commit)
        head_match = head_matches_target(cfg, runner, head_commit)

        if not lineage:
            errors.append(
                {
                    "code": "lineage_mismatch",
                    "message": f"start_from_commit '{cfg.start_from_commit}' is not an ancestor of resolved HEAD '{head_commit}'",
                    "stage": "verify",
                }
            )

        if cfg.target_head_commit is not None and not head_match:
            errors.append(
                {
                    "code": "target_head_mismatch",
                    "message": f"Resolved HEAD '{head_commit}' does not match target_head_commit '{cfg.target_head_commit}'",
                    "stage": "verify",
                }
            )

        ok = len(errors) == 0
        return {
            "ok": ok,
            "tool": TOOL,
            "intended_branch": cfg.branch_name,
            "resolved_branch": resolved_branch,
            "fallback_used": used_fallback,
            "branch_exists": assigned_exists,
            "fallback_created": fallback_created,
            "resolved_head_commit": head_commit,
            "lineage_ok": lineage,
            "head_matches_target": head_match,
            "next_step": "run_tests" if ok else "blocked",
            "warnings": warnings,
            "errors": errors,
        }

    except ToolError as exc:
        errors.append({"code": exc.code, "message": exc.message, "stage": exc.stage})
        return {
            "ok": False,
            "tool": TOOL,
            "intended_branch": cfg.branch_name,
            "resolved_branch": "",
            "fallback_used": False,
            "branch_exists": False,
            "fallback_created": False,
            "resolved_head_commit": "",
            "lineage_ok": False,
            "head_matches_target": False,
            "next_step": "blocked",
            "warnings": warnings,
            "errors": errors,
        }


def print_json(payload: dict[str, Any], pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=False))
    else:
        print(json.dumps(payload, separators=(",", ":"), sort_keys=False))


def main() -> int:
    args = parse_args()
    try:
        cfg = parse_input(args)
    except ToolError as exc:
        out = {
            "ok": False,
            "tool": TOOL,
            "resolved_branch": "",
            "fallback_used": False,
            "resolved_head_commit": "",
            "lineage_ok": False,
            "head_matches_target": False,
            "next_step": "blocked",
            "warnings": [],
            "errors": [{"code": exc.code, "message": exc.message, "stage": exc.stage}],
        }
        print_json(out, args.json_pretty)
        return 1
    except json.JSONDecodeError as exc:
        out = {
            "ok": False,
            "tool": TOOL,
            "resolved_branch": "",
            "fallback_used": False,
            "resolved_head_commit": "",
            "lineage_ok": False,
            "head_matches_target": False,
            "next_step": "blocked",
            "warnings": [],
            "errors": [{"code": "input_error", "message": f"Invalid JSON input: {exc}", "stage": "input"}],
        }
        print_json(out, args.json_pretty)
        return 1

    out = execute(cfg)
    print_json(out, args.json_pretty)
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
