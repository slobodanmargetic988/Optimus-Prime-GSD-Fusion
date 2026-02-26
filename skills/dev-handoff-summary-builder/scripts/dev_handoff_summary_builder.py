#!/usr/bin/env python3
"""Build strict developer handoff summary payload from git/check artifacts."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TOOL = "dev-handoff-summary-builder"
DECISION_VALUES = {"ready_for_test", "blocked", "auto"}
PASS_RESULTS = {"pass"}


class ToolError(Exception):
    def __init__(self, code: str, message: str, stage: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.stage = stage


@dataclass
class SummaryInput:
    task_identifier: str
    branch: str
    start_from_branch: str
    start_from_commit: str
    checks_json_path: Path | None
    decision_hint: str
    blockers: list[str]
    dry_run: bool
    repo_root: Path


class CommandRunner:
    def run(self, cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)


def as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"1", "true", "yes", "on"}:
            return True
        if v in {"0", "false", "no", "off"}:
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build strict handoff summary payload")
    parser.add_argument("--input-json", help="JSON payload path or '-' for stdin")
    parser.add_argument("--task-identifier")
    parser.add_argument("--branch")
    parser.add_argument("--start-from-branch")
    parser.add_argument("--start-from-commit")
    parser.add_argument("--checks-json-path")
    parser.add_argument("--decision-hint")
    parser.add_argument("--repo-root")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json-pretty", action="store_true")
    return parser.parse_args()


def parse_input(args: argparse.Namespace) -> SummaryInput:
    payload: dict[str, Any] = {}
    if args.input_json:
        payload = load_json(args.input_json)

    def required_str(key: str, fallback: Any = None) -> str:
        value = payload.get(key, fallback)
        if not isinstance(value, str) or not value.strip():
            raise ToolError("input_error", f"{key} is required and must be a non-empty string", stage="input")
        return value.strip()

    repo_root_raw = payload.get("repo_root", args.repo_root or ".")
    if not isinstance(repo_root_raw, str) or not repo_root_raw.strip():
        raise ToolError("input_error", "repo_root must be a non-empty string", stage="input")
    repo_root = Path(repo_root_raw).expanduser().resolve()
    if not repo_root.exists() or not repo_root.is_dir():
        raise ToolError("input_error", f"repo_root does not exist or is not a directory: {repo_root}", stage="input")

    checks_json_raw = payload.get("checks_json_path", args.checks_json_path)
    checks_json_path: Path | None = None
    if checks_json_raw is not None:
        if not isinstance(checks_json_raw, str) or not checks_json_raw.strip():
            raise ToolError("input_error", "checks_json_path must be a non-empty string when provided", stage="input")
        checks_json_path = Path(checks_json_raw).expanduser()
        if not checks_json_path.is_absolute():
            checks_json_path = (repo_root / checks_json_path).resolve()

    decision_hint = payload.get("decision_hint", args.decision_hint or "auto")
    if not isinstance(decision_hint, str) or decision_hint.strip() not in DECISION_VALUES:
        raise ToolError(
            "input_error",
            "decision_hint must be one of: ready_for_test, blocked, auto",
            stage="input",
        )

    blockers_raw = payload.get("blockers", [])
    blockers: list[str] = []
    if blockers_raw is None:
        blockers_raw = []
    if not isinstance(blockers_raw, list):
        raise ToolError("input_error", "blockers must be a list when provided", stage="input")
    for idx, item in enumerate(blockers_raw):
        if not isinstance(item, str) or not item.strip():
            raise ToolError("input_error", f"blockers[{idx}] must be a non-empty string", stage="input")
        blockers.append(item.strip())

    return SummaryInput(
        task_identifier=required_str("task_identifier", args.task_identifier),
        branch=required_str("branch", args.branch),
        start_from_branch=required_str("start_from_branch", args.start_from_branch),
        start_from_commit=required_str("start_from_commit", args.start_from_commit),
        checks_json_path=checks_json_path,
        decision_hint=decision_hint.strip(),
        blockers=blockers,
        dry_run=as_bool(payload.get("dry_run", args.dry_run), default=False),
        repo_root=repo_root,
    )


def dedupe_preserve(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def normalize_checks_payload(data: dict[str, Any]) -> tuple[dict[str, str], list[str]]:
    checks_map: dict[str, str] = {}
    bundle_blockers: list[str] = []

    checks_raw = data.get("checks")
    if isinstance(checks_raw, list):
        for idx, item in enumerate(checks_raw):
            if not isinstance(item, dict):
                raise ToolError("data", f"checks[{idx}] in checks_json_path must be an object", stage="checks")
            name = item.get("name")
            result = item.get("result")
            if not isinstance(name, str) or not name.strip():
                raise ToolError("data", f"checks[{idx}].name must be non-empty string", stage="checks")
            if not isinstance(result, str) or not result.strip():
                raise ToolError("data", f"checks[{idx}].result must be non-empty string", stage="checks")
            checks_map[name.strip()] = result.strip()
    elif isinstance(checks_raw, dict):
        for key, value in checks_raw.items():
            if not isinstance(key, str) or not key.strip() or not isinstance(value, str) or not value.strip():
                raise ToolError("data", "checks object must map non-empty strings to non-empty strings", stage="checks")
            checks_map[key.strip()] = value.strip()
    elif checks_raw is not None:
        raise ToolError("data", "checks in checks_json_path must be a list or object", stage="checks")

    blockers_raw = data.get("blockers", [])
    if blockers_raw is None:
        blockers_raw = []
    if not isinstance(blockers_raw, list):
        raise ToolError("data", "blockers in checks_json_path must be a list", stage="checks")
    for idx, item in enumerate(blockers_raw):
        if not isinstance(item, str) or not item.strip():
            raise ToolError("data", f"blockers[{idx}] in checks_json_path must be non-empty string", stage="checks")
        bundle_blockers.append(item.strip())

    overall = data.get("overall")
    if isinstance(overall, str) and overall.strip() and "bundle_overall" not in checks_map:
        checks_map["bundle_overall"] = overall.strip()

    return checks_map, bundle_blockers


def load_checks(checks_path: Path | None) -> tuple[dict[str, str], list[str]]:
    if checks_path is None:
        return ({"checks_source": "not_provided"}, ["checks_json_path not provided; using placeholder checks"])
    if not checks_path.exists():
        raise ToolError("data", f"checks_json_path not found: {checks_path}", stage="checks")
    data = json.loads(checks_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ToolError("data", "checks_json_path must contain a JSON object", stage="checks")
    checks_map, bundle_blockers = normalize_checks_payload(data)
    if not checks_map:
        checks_map = {"checks_source": "empty"}
        bundle_blockers.append("checks_json_path contained no checks; using placeholder")
    return checks_map, bundle_blockers


def git_head_commit(repo_root: Path, runner: CommandRunner) -> str:
    proc = runner.run(["git", "rev-parse", "HEAD"], cwd=repo_root)
    if proc.returncode != 0:
        raise ToolError("script", f"Failed to resolve HEAD commit: {proc.stderr.strip() or proc.stdout.strip()}", stage="git")
    head = proc.stdout.strip()
    if not head:
        raise ToolError("script", "Resolved empty HEAD commit", stage="git")
    return head


def git_changed_files_count(repo_root: Path, start_from_commit: str, runner: CommandRunner) -> int:
    verify = runner.run(["git", "rev-parse", "--verify", f"{start_from_commit}^{{commit}}"], cwd=repo_root)
    if verify.returncode != 0:
        raise ToolError("data", f"Invalid start_from_commit: {start_from_commit}", stage="git")

    proc = runner.run(["git", "diff", "--name-only", f"{start_from_commit}..HEAD"], cwd=repo_root)
    if proc.returncode != 0:
        raise ToolError("script", f"Failed to count changed files: {proc.stderr.strip() or proc.stdout.strip()}", stage="git")
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    return len(lines)


def derive_decision(checks: dict[str, str], blockers: list[str], decision_hint: str) -> tuple[str, list[str]]:
    merged_blockers = list(blockers)

    has_failing_check = any(value not in PASS_RESULTS for value in checks.values())
    inferred = "blocked" if merged_blockers or has_failing_check else "ready_for_test"

    if decision_hint == "auto":
        return inferred, dedupe_preserve(merged_blockers)
    if decision_hint == "blocked":
        return "blocked", dedupe_preserve(merged_blockers)

    if inferred == "blocked":
        merged_blockers.append("decision_hint=ready_for_test overridden due to blockers/failing checks")
        return "blocked", dedupe_preserve(merged_blockers)
    return "ready_for_test", dedupe_preserve(merged_blockers)


def build_summary(cfg: SummaryInput, runner: CommandRunner | None = None) -> dict[str, Any]:
    if runner is None:
        runner = CommandRunner()

    checks, check_blockers = load_checks(cfg.checks_json_path)
    merged_blockers = dedupe_preserve(cfg.blockers + check_blockers)

    if cfg.dry_run:
        head_commit = "DRY_RUN_HEAD"
        files_changed_count = 0
    else:
        head_commit = git_head_commit(cfg.repo_root, runner)
        files_changed_count = git_changed_files_count(cfg.repo_root, cfg.start_from_commit, runner)

    decision, final_blockers = derive_decision(checks, merged_blockers, cfg.decision_hint)

    payload = {
        "task_identifier": cfg.task_identifier,
        "branch": cfg.branch,
        "start_from_branch": cfg.start_from_branch,
        "start_from_commit": cfg.start_from_commit,
        "head_commit": head_commit,
        "files_changed_count": files_changed_count,
        "checks": checks,
        "decision": decision,
        "blockers": final_blockers,
    }
    return payload


def print_json(obj: dict[str, Any], pretty: bool) -> None:
    if pretty:
        print(json.dumps(obj, indent=2, sort_keys=False))
    else:
        print(json.dumps(obj, separators=(",", ":"), sort_keys=False))


def main() -> int:
    args = parse_args()
    try:
        cfg = parse_input(args)
        out = build_summary(cfg)
        print_json(out, args.json_pretty)
        return 0
    except ToolError as exc:
        out = {
            "task_identifier": args.task_identifier or "",
            "branch": args.branch or "",
            "start_from_branch": args.start_from_branch or "",
            "start_from_commit": args.start_from_commit or "",
            "head_commit": "",
            "files_changed_count": 0,
            "checks": {"tool": "error"},
            "decision": "blocked",
            "blockers": [f"{exc.code}: {exc.message}"],
        }
        print_json(out, args.json_pretty)
        return 1
    except json.JSONDecodeError as exc:
        out = {
            "task_identifier": args.task_identifier or "",
            "branch": args.branch or "",
            "start_from_branch": args.start_from_branch or "",
            "start_from_commit": args.start_from_commit or "",
            "head_commit": "",
            "files_changed_count": 0,
            "checks": {"tool": "error"},
            "decision": "blocked",
            "blockers": [f"input_error: Invalid JSON input: {exc}"],
        }
        print_json(out, args.json_pretty)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
