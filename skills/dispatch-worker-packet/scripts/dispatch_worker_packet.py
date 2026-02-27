#!/usr/bin/env python3
"""Create worker packet, dispatch worker thread, and update orchestration state."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

TOOL = "dispatch-worker-packet"
TOOL_VERSION = "0.1.0"
SCHEMA_VERSION = "1.0"

SLOTS = ["dev-1", "dev-2", "dev-3", "test-1", "test-2", "review-1"]
ROLES = {"developer", "tester", "reviewer", "flex-tester"}
MCP_MODES = {"disable-all", "enable-only"}
FORBIDDEN_WORKER_MCPS = {"linear", "linear_sse"}
SANDBOX_MODES = {"workspace-write", "danger-full-access"}
TEST_TRAIN_MODES = {"off", "final-stage", "forced-shared-env"}


class ToolError(Exception):
    def __init__(self, code: str, message: str, stage: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.stage = stage


@dataclass
class DispatchInput:
    slot: str
    role: str
    task_identifier: str
    repo_root: Path
    worktree_root: Path
    branch_name: str
    start_from_branch: str
    start_from_commit: str
    acceptance_criteria: list[str]
    packet_version: int
    codex_profile_alias: str
    mcp_mode: str
    mcp_allowlist: list[str]
    sandbox_mode: str
    sandbox_add_dirs: list[str]
    runtime_strategy: str | None
    runtime_base_url: str | None
    tester_must_not_start_runtime: bool | None
    test_train_mode: str
    wave_id: str | None
    deployed_test_commit: str | None
    test_lane_account: str | None
    dry_run: bool
    cycle_note: str | None


class Dispatcher(Protocol):
    def dispatch(self, cfg: DispatchInput, packet_path: Path) -> dict[str, Any]: ...


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def now_compact_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-") or "packet"


def parse_json_input(path: str) -> dict[str, Any]:
    if path == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(path).read_text(encoding="utf-8")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ToolError("input_error", "input must be a JSON object", stage="input")
    return parsed


def _must_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ToolError("input_error", f"{key} is required and must be a non-empty string", stage="input")
    return value.strip()


def _list_of_str(data: dict[str, Any], key: str, *, required: bool = False) -> list[str]:
    value = data.get(key)
    if value is None:
        if required:
            raise ToolError("input_error", f"{key} is required and must be a list of strings", stage="input")
        return []
    if not isinstance(value, list):
        raise ToolError("input_error", f"{key} must be a list", stage="input")
    out: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
        else:
            raise ToolError("input_error", f"{key} must contain only non-empty strings", stage="input")
    return out


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "y", "on"}:
            return True
        if text in {"0", "false", "no", "n", "off"}:
            return False
    raise ToolError("input_error", "tester_must_not_start_runtime must be boolean-like", stage="input")


def validate_slot_role(slot: str, role: str) -> None:
    if slot.startswith("dev-") and role != "developer":
        raise ToolError("validation_error", f"slot '{slot}' only supports role 'developer'", stage="validate")
    if slot.startswith("test-") and role not in {"tester", "flex-tester"}:
        raise ToolError("validation_error", f"slot '{slot}' supports only 'tester' or 'flex-tester'", stage="validate")
    if slot == "review-1" and role != "reviewer":
        raise ToolError("validation_error", "slot 'review-1' only supports role 'reviewer'", stage="validate")


def validate_policy(cfg: DispatchInput) -> None:
    if cfg.slot not in SLOTS:
        raise ToolError("input_error", f"invalid slot '{cfg.slot}'", stage="input")
    if cfg.role not in ROLES:
        raise ToolError("input_error", f"invalid role '{cfg.role}'", stage="input")
    validate_slot_role(cfg.slot, cfg.role)

    if cfg.mcp_mode not in MCP_MODES:
        raise ToolError("input_error", f"mcp_mode must be one of: {', '.join(sorted(MCP_MODES))}", stage="input")
    if cfg.mcp_mode == "enable-only" and not cfg.mcp_allowlist:
        raise ToolError("validation_error", "mcp_allowlist is required when mcp_mode=enable-only", stage="validate")
    if cfg.mcp_mode == "disable-all" and cfg.mcp_allowlist:
        raise ToolError("validation_error", "mcp_allowlist must be empty when mcp_mode=disable-all", stage="validate")

    forbidden = sorted(FORBIDDEN_WORKER_MCPS.intersection({item.lower() for item in cfg.mcp_allowlist}))
    if forbidden:
        raise ToolError(
            "validation_error",
            f"forbidden worker MCP in allowlist: {', '.join(forbidden)}",
            stage="validate",
        )

    if cfg.sandbox_mode not in SANDBOX_MODES:
        raise ToolError("validation_error", f"invalid sandbox_mode '{cfg.sandbox_mode}'", stage="validate")

    if cfg.test_train_mode not in TEST_TRAIN_MODES:
        raise ToolError(
            "validation_error",
            f"test_train_mode must be one of: {', '.join(sorted(TEST_TRAIN_MODES))}",
            stage="validate",
        )

    if cfg.role in {"tester", "flex-tester"} and cfg.test_train_mode != "off":
        if cfg.tester_must_not_start_runtime is not True:
            raise ToolError(
                "validation_error",
                "tester packets in test-train mode must set tester_must_not_start_runtime=true",
                stage="validate",
            )
        if cfg.runtime_strategy not in {"external_url", "shared_runtime"}:
            raise ToolError(
                "validation_error",
                "tester packets in test-train mode require runtime_strategy=external_url|shared_runtime",
                stage="validate",
            )
        if not isinstance(cfg.runtime_base_url, str) or not cfg.runtime_base_url.strip():
            raise ToolError(
                "validation_error",
                "tester packets in test-train mode require runtime_base_url",
                stage="validate",
            )

    expected_prefix = f"codex/{cfg.slot}/"
    if not cfg.branch_name.startswith(expected_prefix):
        raise ToolError(
            "validation_error",
            f"branch_name must start with '{expected_prefix}'",
            stage="validate",
        )

    if not re.fullmatch(r"[0-9a-fA-F]{7,40}", cfg.start_from_commit):
        raise ToolError("validation_error", "start_from_commit must be a git sha (7-40 hex chars)", stage="validate")



def config_from_args(args: argparse.Namespace) -> DispatchInput:
    data: dict[str, Any] = {}
    if args.input_json:
        data = parse_json_input(args.input_json)

    slot = args.slot or data.get("slot")
    role = args.role or data.get("role")
    task_identifier = args.task_identifier or data.get("task_identifier")

    if not isinstance(slot, str) or not slot.strip():
        raise ToolError("input_error", "slot is required", stage="input")
    if not isinstance(role, str) or not role.strip():
        raise ToolError("input_error", "role is required", stage="input")
    if not isinstance(task_identifier, str) or not task_identifier.strip():
        raise ToolError("input_error", "task_identifier is required", stage="input")

    repo_root_raw = args.repo_root or data.get("repo_root")
    worktree_root_raw = args.worktree_root or data.get("worktree_root")

    if not isinstance(repo_root_raw, str) or not repo_root_raw.strip():
        raise ToolError("input_error", "repo_root is required", stage="input")
    if not isinstance(worktree_root_raw, str) or not worktree_root_raw.strip():
        raise ToolError("input_error", "worktree_root is required", stage="input")

    repo_root = Path(repo_root_raw).expanduser().resolve()
    worktree_root = Path(worktree_root_raw).expanduser().resolve()

    cfg = DispatchInput(
        slot=slot.strip(),
        role=role.strip(),
        task_identifier=task_identifier.strip(),
        repo_root=repo_root,
        worktree_root=worktree_root,
        branch_name=(args.branch_name or _must_str(data, "branch_name")).strip(),
        start_from_branch=(args.start_from_branch or _must_str(data, "start_from_branch")).strip(),
        start_from_commit=(args.start_from_commit or _must_str(data, "start_from_commit")).strip(),
        acceptance_criteria=(
            _list_of_str(data, "acceptance_criteria", required=True)
            if args.acceptance_criteria_json is None
            else _list_of_str({"acceptance_criteria": json.loads(args.acceptance_criteria_json)}, "acceptance_criteria", required=True)
        ),
        packet_version=(
            int(args.packet_version)
            if args.packet_version is not None
            else int(data.get("packet_version", 1))
        ),
        codex_profile_alias=(args.codex_profile_alias or _must_str(data, "codex_profile_alias")).strip(),
        mcp_mode=(args.mcp_mode or _must_str(data, "mcp_mode")).strip(),
        mcp_allowlist=(
            _list_of_str(data, "mcp_allowlist", required=False)
            if args.mcp_allowlist is None
            else [item.strip() for item in args.mcp_allowlist if item.strip()]
        ),
        sandbox_mode=(args.sandbox_mode or _must_str(data, "sandbox_mode")).strip(),
        sandbox_add_dirs=(
            _list_of_str(data, "sandbox_add_dirs", required=False)
            if args.sandbox_add_dirs is None
            else [item.strip() for item in args.sandbox_add_dirs if item.strip()]
        ),
        runtime_strategy=((args.runtime_strategy or data.get("runtime_strategy") or "").strip() or None),
        runtime_base_url=((args.runtime_base_url or data.get("runtime_base_url") or "").strip() or None),
        tester_must_not_start_runtime=(
            _optional_bool(data.get("tester_must_not_start_runtime"))
            if args.tester_must_not_start_runtime is None
            else bool(args.tester_must_not_start_runtime)
        ),
        test_train_mode=((args.test_train_mode or data.get("test_train_mode") or "off").strip() or "off"),
        wave_id=((args.wave_id or data.get("wave_id") or "").strip() or None),
        deployed_test_commit=((args.deployed_test_commit or data.get("deployed_test_commit") or "").strip() or None),
        test_lane_account=((args.test_lane_account or data.get("test_lane_account") or "").strip() or None),
        dry_run=bool(data.get("dry_run", False) or args.dry_run),
        cycle_note=(args.cycle_note if args.cycle_note is not None else data.get("cycle_note")),
    )

    if not cfg.acceptance_criteria:
        raise ToolError("validation_error", "acceptance_criteria cannot be empty", stage="validate")
    if cfg.packet_version < 1:
        raise ToolError("validation_error", "packet_version must be >= 1", stage="validate")

    validate_policy(cfg)
    return cfg


def resolve_codex_home_from_alias(alias: str) -> Path | None:
    if alias == "codex":
        return None
    return (Path.home() / f".{alias}").resolve()


def fallback_suffix_for_role(role: str) -> str:
    if role == "developer":
        return "-dev"
    if role in {"tester", "flex-tester"}:
        return "-test"
    return ""


def render_packet(cfg: DispatchInput) -> str:
    fallback_suffix = fallback_suffix_for_role(cfg.role)
    mcp_line = "none" if cfg.mcp_mode == "disable-all" else ", ".join(cfg.mcp_allowlist)
    criteria_lines = "\n".join(f"- {item}" for item in cfg.acceptance_criteria)
    sandbox_dirs = "none" if not cfg.sandbox_add_dirs else ", ".join(cfg.sandbox_add_dirs)
    runtime_strategy = cfg.runtime_strategy or "none"
    runtime_base_url = cfg.runtime_base_url or "none"
    tester_no_local_runtime = (
        "true"
        if cfg.tester_must_not_start_runtime is True
        else "false"
        if cfg.tester_must_not_start_runtime is False
        else "unset"
    )

    return (
        f"# Worker Packet v{cfg.packet_version}\n"
        f"generated_at: {utc_now_iso()}\n"
        f"task_identifier: {cfg.task_identifier}\n"
        f"slot: {cfg.slot}\n"
        f"role: {cfg.role}\n"
        f"repo_root: {cfg.repo_root}\n"
        f"worktree_root: {cfg.worktree_root}\n"
        f"branch_name: {cfg.branch_name}\n"
        f"start_from_branch: {cfg.start_from_branch}\n"
        f"start_from_commit: {cfg.start_from_commit}\n"
        f"codex_profile_alias: {cfg.codex_profile_alias}\n"
        f"mcp_mode: {cfg.mcp_mode}\n"
        f"mcp_allowlist: {mcp_line}\n"
        f"sandbox_mode: {cfg.sandbox_mode}\n"
        f"sandbox_add_dirs: {sandbox_dirs}\n\n"
        f"runtime_strategy: {runtime_strategy}\n"
        f"runtime_base_url: {runtime_base_url}\n"
        f"tester_must_not_start_runtime: {tester_no_local_runtime}\n"
        f"test_train_mode: {cfg.test_train_mode}\n"
        f"wave_id: {cfg.wave_id or 'none'}\n"
        f"deployed_test_commit: {cfg.deployed_test_commit or 'none'}\n"
        f"test_lane_account: {cfg.test_lane_account or 'none'}\n\n"
        f"## Acceptance Criteria\n"
        f"{criteria_lines}\n\n"
        f"## Branch Fallback Policy\n"
        f"- developer fallback suffix: -dev\n"
        f"- tester/flex-tester fallback suffix: -test\n"
        f"- role-specific fallback for this packet: {fallback_suffix or 'none'}\n"
        f"- if assigned branch checkout fails because branch is active elsewhere, continue on fallback branch and report mapping\n\n"
        f"## Expected Worker Response Fields\n"
        f"- intended_branch\n"
        f"- fallback_branch\n"
        f"- fallback_reason\n"
        f"- branch\n"
        f"- head_commit\n"
        f"- checks\n"
        f"- blockers\n"
    )


def ensure_worktree_runtime_prereqs(cfg: DispatchInput) -> dict[str, Any]:
    """Ensure standard runtime prerequisites exist in the worker worktree.

    This keeps workstation setup deterministic even after force-reset cycles.
    Missing links are created as symlinks to the canonical repo-root artifacts.
    Existing files/directories are never replaced.
    """

    mappings: list[tuple[str, Path]] = [
        (".venv", cfg.repo_root / ".venv"),
        (".env", cfg.repo_root / ".env"),
        ("node_modules", cfg.repo_root / "node_modules"),
        ("web/nuxt-app/node_modules", cfg.repo_root / "web/nuxt-app/node_modules"),
        ("output/playwright/auth", cfg.repo_root / "output/playwright/auth"),
    ]

    out: dict[str, Any] = {
        "linked": [],
        "skipped_existing": [],
        "missing_target": [],
        "errors": [],
    }

    for rel_path, source in mappings:
        target = (cfg.worktree_root / rel_path).resolve(strict=False)
        source_resolved = source.resolve(strict=False)

        if target.exists() or target.is_symlink():
            out["skipped_existing"].append(rel_path)
            continue

        if not source_resolved.exists():
            out["missing_target"].append(rel_path)
            continue

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(source_resolved)
            out["linked"].append(rel_path)
        except OSError as exc:
            out["errors"].append({"path": rel_path, "message": str(exc)})

    return out


def packet_path(cfg: DispatchInput) -> Path:
    prompts_dir = cfg.repo_root / "reports" / "optimus-prime" / "prompts"
    filename = f"packet-{_slug(cfg.task_identifier)}-{cfg.slot}-v{cfg.packet_version}-{now_compact_utc()}.md"
    return (prompts_dir / filename).resolve()


def write_text_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def parse_dispatch_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if not text:
        raise ToolError("dispatch_failed", "dispatcher returned empty output", stage="dispatch")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError as exc:
                raise ToolError("dispatch_failed", f"dispatcher output is not valid JSON: {exc}", stage="dispatch") from exc
        raise ToolError("dispatch_failed", "dispatcher output is not valid JSON", stage="dispatch")


class ThreadDispatchRunner:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root

    def _script_path(self) -> Path:
        codex_home = os.environ.get("CODEX_HOME")
        if codex_home:
            runtime = Path(codex_home).expanduser().resolve() / "skills" / "thread-dispatch" / "scripts" / "dispatch_codex_run.py"
            if runtime.exists():
                return runtime
        runtime_default = Path.home() / ".codex" / "skills" / "thread-dispatch" / "scripts" / "dispatch_codex_run.py"
        if runtime_default.exists():
            return runtime_default
        repo_local = self.repo_root / "skills" / "thread-dispatch" / "scripts" / "dispatch_codex_run.py"
        if repo_local.exists():
            return repo_local
        raise ToolError("dispatch_failed", "thread-dispatch script not found", stage="dispatch")

    def dispatch(self, cfg: DispatchInput, packet_path: Path) -> dict[str, Any]:
        script = self._script_path()
        use_danger_full_access = cfg.sandbox_mode == "danger-full-access"
        cmd = [
            "python3",
            str(script),
            "--cwd",
            str(cfg.worktree_root),
            "--prompt-file",
            str(packet_path),
            "--background",
        ]

        # `codex exec --full-auto` currently forces workspace-write sandboxing.
        # For worker packets that require danger-full-access, disable the helper
        # alias and pass the dedicated bypass flag explicitly so the spawned
        # worker actually runs unsandboxed as requested.
        if use_danger_full_access:
            cmd.append("--no-full-auto")

        codex_home = resolve_codex_home_from_alias(cfg.codex_profile_alias)
        if codex_home is not None:
            cmd.extend(["--codex-home", str(codex_home)])

        if cfg.mcp_mode == "disable-all":
            cmd.append("--disable-all-mcp")
        else:
            for mcp in cfg.mcp_allowlist:
                cmd.extend(["--enable-only-mcp", mcp])

        if use_danger_full_access:
            cmd.extend(["--extra-arg=--dangerously-bypass-approvals-and-sandbox"])
        else:
            cmd.extend([f"--extra-arg=--sandbox", f"--extra-arg={cfg.sandbox_mode}"])
        for d in cfg.sandbox_add_dirs:
            cmd.extend([f"--extra-arg=--add-dir", f"--extra-arg={d}"])

        run = subprocess.run(cmd, cwd=str(cfg.repo_root), capture_output=True, text=True, check=False)
        if run.returncode != 0:
            stderr = (run.stderr or "").strip()
            stdout = (run.stdout or "").strip()
            raise ToolError(
                "dispatch_failed",
                f"thread-dispatch failed (exit={run.returncode}). stdout={stdout} stderr={stderr}",
                stage="dispatch",
            )

        payload = parse_dispatch_json(run.stdout)
        pid = payload.get("pid")
        if not isinstance(pid, int):
            raise ToolError("dispatch_failed", "dispatcher payload missing integer pid", stage="dispatch")

        log_path = payload.get("log_file")
        if not isinstance(log_path, str) or not log_path.strip():
            raise ToolError("dispatch_failed", "dispatcher payload missing log_file", stage="dispatch")

        return {
            "dispatch_started": bool(payload.get("status") == "started" or pid > 0),
            "pid": pid,
            "dispatch_log": str(Path(log_path).expanduser().resolve()),
            "raw": payload,
        }


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def read_json_or_default(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ToolError("state_read_error", f"Malformed JSON in {path}: {exc}", stage="state_read") from exc
    except OSError as exc:
        raise ToolError("state_read_error", f"Failed to read {path}: {exc}", stage="state_read") from exc


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, sort_keys=False)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line)
        fh.write("\n")


def append_thread_history(path: Path, cfg: DispatchInput, dispatch: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = dispatch.get("raw")
    thread_id = None
    if isinstance(raw, dict):
        for key in ("thread_id", "session_id", "conversation_id", "thread"):
            value = raw.get(key)
            if isinstance(value, str) and value.strip():
                thread_id = value.strip()
                break
    if not thread_id:
        thread_id = "unknown"

    header = "slot | worker type | thread-id\n"
    line = f"{cfg.slot} | {cfg.role} | {thread_id}\n"

    if not path.exists():
        path.write_text(header + line, encoding="utf-8")
        return

    with path.open("a", encoding="utf-8") as fh:
        fh.write(line)


def update_worker_registry(path: Path, cfg: DispatchInput, packet: Path, dispatch: dict[str, Any]) -> None:
    default_registry = {"workers": []}
    data = read_json_or_default(path, default_registry)

    worker_entry = {
        "slot": cfg.slot,
        "role": cfg.role,
        "session_state": "running",
        "active_task": cfg.task_identifier,
        "branch": cfg.branch_name,
        "dispatch_pid": dispatch["pid"],
        "dispatch_log": dispatch["dispatch_log"],
        "packet_path": str(packet),
        "packet_version": cfg.packet_version,
        "start_from_branch": cfg.start_from_branch,
        "start_from_commit": cfg.start_from_commit,
        "codex_profile_alias": cfg.codex_profile_alias,
        "mcp_mode": cfg.mcp_mode,
        "mcp_allowlist": cfg.mcp_allowlist,
        "sandbox_mode": cfg.sandbox_mode,
        "sandbox_add_dirs": cfg.sandbox_add_dirs,
        "runtime_strategy": cfg.runtime_strategy,
        "runtime_base_url": cfg.runtime_base_url,
        "tester_must_not_start_runtime": cfg.tester_must_not_start_runtime,
        "test_train_mode": cfg.test_train_mode,
        "wave_id": cfg.wave_id,
        "deployed_test_commit": cfg.deployed_test_commit,
        "test_lane_account": cfg.test_lane_account,
        "worktree_root": str(cfg.worktree_root),
        "updated_at": utc_now_iso(),
    }

    if isinstance(data, dict) and isinstance(data.get("workers"), list):
        workers = data["workers"]
        replaced = False
        for idx, item in enumerate(workers):
            if isinstance(item, dict) and item.get("slot") == cfg.slot:
                workers[idx] = worker_entry
                replaced = True
                break
        if not replaced:
            workers.append(worker_entry)
        atomic_write_json(path, data)
        return

    if isinstance(data, dict) and isinstance(data.get("workers"), dict):
        workers_dict = data["workers"]
        workers_dict[cfg.slot] = worker_entry
        atomic_write_json(path, data)
        return

    if isinstance(data, dict):
        data["workers"] = [worker_entry]
        atomic_write_json(path, data)
        return

    atomic_write_json(path, default_registry | {"workers": [worker_entry]})


def update_branch_lineage(path: Path, cfg: DispatchInput, dispatch: dict[str, Any]) -> None:
    data = read_json_or_default(path, {"entries": []})
    entry = {
        "task_identifier": cfg.task_identifier,
        "slot": cfg.slot,
        "role": cfg.role,
        "branch": cfg.branch_name,
        "start_from_branch": cfg.start_from_branch,
        "start_from_commit": cfg.start_from_commit,
        "worktree_root": str(cfg.worktree_root),
        "dispatch_pid": dispatch["pid"],
        "last_dispatch_at": utc_now_iso(),
    }

    if isinstance(data, dict) and isinstance(data.get("entries"), list):
        entries = data["entries"]
        replaced = False
        for idx, item in enumerate(entries):
            if isinstance(item, dict) and item.get("task_identifier") == cfg.task_identifier:
                entries[idx] = entry
                replaced = True
                break
        if not replaced:
            entries.append(entry)
        atomic_write_json(path, data)
        return

    if isinstance(data, list):
        replaced = False
        for idx, item in enumerate(data):
            if isinstance(item, dict) and item.get("task_identifier") == cfg.task_identifier:
                data[idx] = entry
                replaced = True
                break
        if not replaced:
            data.append(entry)
        atomic_write_json(path, data)
        return

    atomic_write_json(path, {"entries": [entry]})


def remediation_block(cfg: DispatchInput, pid: int) -> dict[str, Any]:
    return {
        "pid": pid,
        "task_identifier": cfg.task_identifier,
        "slot": cfg.slot,
        "manual_recovery_steps": [
            "Inspect dispatcher log path from output.dispatch_log for immediate worker state.",
            "Patch reports/optimus-prime/WORKER_REGISTRY.json to mark slot as running with active task and pid.",
            "Append a dispatch_attempt line to reports/optimus-prime/HANDOFF_LOG.jsonl for audit continuity.",
            "If worker should be stopped, terminate pid and mark slot non-running before retrying dispatch.",
        ],
    }


def build_result(cfg: DispatchInput, packet: Path) -> dict[str, Any]:
    cycle_note_state = "pending" if cfg.cycle_note else "not_requested"
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "ok": False,
        "dry_run": bool(cfg.dry_run),
        "status": "not_started",
        "slot": cfg.slot,
        "role": cfg.role,
        "task_identifier": cfg.task_identifier,
        "packet_path": str(packet),
        "dispatch_started": False,
        "pid": None,
        "dispatch_log": None,
        "dispatch": {
            "attempted": False,
            "status": "not_started",
            "pid": None,
            "dispatch_log": None,
        },
        "worktree_prereq_sync": {
            "linked": [],
            "skipped_existing": [],
            "missing_target": [],
            "errors": [],
        },
        "state_updates": {
            "worktree_prereqs": "not_started",
            "worker_registry": "not_started",
            "handoff_log": "not_started",
            "branch_lineage": "not_started",
            "thread_history": "not_started",
            "cycle_log_note": cycle_note_state,
        },
        "branch": cfg.branch_name,
        "start_anchor": {
            "start_from_branch": cfg.start_from_branch,
            "start_from_commit": cfg.start_from_commit,
        },
        "registry_updated": False,
        "handoff_logged": False,
        "warnings": [],
        "errors": [],
    }


def run_dispatch_worker_packet(cfg: DispatchInput, dispatcher: Dispatcher | None = None) -> dict[str, Any]:
    if dispatcher is None:
        dispatcher = ThreadDispatchRunner(repo_root=cfg.repo_root)

    packet = packet_path(cfg)
    result = build_result(cfg, packet)

    packet_content = render_packet(cfg)
    if cfg.dry_run:
        result["ok"] = True
        result["status"] = "skipped_dry_run"
        result["dispatch"] = {
            "attempted": False,
            "status": "skipped_dry_run",
            "pid": None,
            "dispatch_log": None,
        }
        result["state_updates"] = {
            "worktree_prereqs": "skipped_dry_run",
            "worker_registry": "skipped_dry_run",
            "handoff_log": "skipped_dry_run",
            "branch_lineage": "skipped_dry_run",
            "thread_history": "skipped_dry_run",
            "cycle_log_note": "skipped_dry_run" if cfg.cycle_note else "not_requested",
        }
        result["warnings"].append(
            {
                "code": "dry_run",
                "message": "Dry-run mode enabled; no writes or dispatch were performed",
                "planned_actions": [
                    "create_packet",
                    "dispatch_worker",
                    "update_worker_registry",
                    "append_handoff_log",
                    "update_branch_lineage",
                    "optional_cycle_log_note",
                ],
            }
        )
        return result

    prereq_sync = ensure_worktree_runtime_prereqs(cfg)
    result["worktree_prereq_sync"] = prereq_sync
    if prereq_sync.get("errors"):
        result["state_updates"]["worktree_prereqs"] = "failed_warning"
        result["warnings"].append(
            {
                "code": "worktree_prereq_sync_failed",
                "message": "One or more worktree prerequisite symlinks could not be created",
                "stage": "worktree_prereq_sync",
                "details": prereq_sync,
            }
        )
    else:
        result["state_updates"]["worktree_prereqs"] = "applied"
        if prereq_sync.get("missing_target"):
            result["warnings"].append(
                {
                    "code": "worktree_prereq_source_missing",
                    "message": "Some prerequisite sources were missing in repo_root; dispatch continued",
                    "stage": "worktree_prereq_sync",
                    "details": prereq_sync,
                }
            )

    try:
        write_text_file(packet, packet_content)
    except OSError as exc:
        result["status"] = "packet_create_failed"
        result["errors"].append(
            {
                "code": "packet_create_failed",
                "message": f"Failed to create packet: {exc}",
                "stage": "create_packet",
                "path": str(packet),
            }
        )
        return result

    try:
        dispatch = dispatcher.dispatch(cfg, packet)
    except ToolError as exc:
        result["status"] = "dispatch_failed"
        result["dispatch"]["attempted"] = True
        result["dispatch"]["status"] = "failed"
        result["errors"].append({"code": exc.code, "message": exc.message, "stage": exc.stage})
        return result

    result["dispatch_started"] = bool(dispatch["dispatch_started"])
    result["pid"] = int(dispatch["pid"])
    result["dispatch_log"] = str(dispatch["dispatch_log"])
    result["dispatch"] = {
        "attempted": True,
        "status": "started" if dispatch["dispatch_started"] else "failed",
        "pid": int(dispatch["pid"]),
        "dispatch_log": str(dispatch["dispatch_log"]),
    }
    result["status"] = "dispatch_started" if dispatch["dispatch_started"] else "dispatch_failed"

    reports_root = cfg.repo_root / "reports" / "optimus-prime"
    registry_path = reports_root / "WORKER_REGISTRY.json"
    handoff_path = reports_root / "HANDOFF_LOG.jsonl"
    lineage_path = reports_root / "BRANCH_LINEAGE.json"
    thread_history_path = reports_root / "THREAD_HISTORY.log"
    cycle_path = reports_root / "CYCLE_LOG.jsonl"

    try:
        update_worker_registry(registry_path, cfg, packet, dispatch)
        result["registry_updated"] = True
        result["state_updates"]["worker_registry"] = "applied"
    except (ToolError, OSError) as exc:
        msg = exc.message if isinstance(exc, ToolError) else str(exc)
        result["status"] = "registry_update_failed"
        result["state_updates"]["worker_registry"] = "failed"
        result["errors"].append(
            {
                "code": "registry_update_failed",
                "message": f"Failed to update worker registry after dispatch: {msg}",
                "stage": "update_registry",
                "path": str(registry_path),
                "critical": True,
                "remediation": remediation_block(cfg, int(dispatch["pid"])),
            }
        )
        return result

    handoff_row = {
        "timestamp": utc_now_iso(),
        "event": "dispatch_attempt",
        "slot": cfg.slot,
        "role": cfg.role,
        "task_identifier": cfg.task_identifier,
        "branch": cfg.branch_name,
        "start_from_branch": cfg.start_from_branch,
        "start_from_commit": cfg.start_from_commit,
        "packet_path": str(packet),
        "packet_version": cfg.packet_version,
        "dispatch_pid": dispatch["pid"],
        "dispatch_log": dispatch["dispatch_log"],
        "codex_profile_alias": cfg.codex_profile_alias,
        "mcp_mode": cfg.mcp_mode,
        "mcp_allowlist": cfg.mcp_allowlist,
        "sandbox_mode": cfg.sandbox_mode,
        "sandbox_add_dirs": cfg.sandbox_add_dirs,
        "runtime_strategy": cfg.runtime_strategy,
        "runtime_base_url": cfg.runtime_base_url,
        "tester_must_not_start_runtime": cfg.tester_must_not_start_runtime,
        "test_train_mode": cfg.test_train_mode,
        "wave_id": cfg.wave_id,
        "deployed_test_commit": cfg.deployed_test_commit,
        "test_lane_account": cfg.test_lane_account,
        "status": "started" if dispatch["dispatch_started"] else "failed",
    }

    try:
        append_jsonl(handoff_path, handoff_row)
        result["handoff_logged"] = True
        result["state_updates"]["handoff_log"] = "applied"
    except OSError as exc:
        result["status"] = "handoff_log_failed"
        result["state_updates"]["handoff_log"] = "failed"
        result["errors"].append(
            {
                "code": "handoff_log_failed",
                "message": f"Failed to append handoff log: {exc}",
                "stage": "handoff_log",
                "path": str(handoff_path),
            }
        )
        return result

    try:
        update_branch_lineage(lineage_path, cfg, dispatch)
        result["state_updates"]["branch_lineage"] = "applied"
    except (ToolError, OSError) as exc:
        msg = exc.message if isinstance(exc, ToolError) else str(exc)
        result["state_updates"]["branch_lineage"] = "failed_warning"
        result["warnings"].append(
            {
                "code": "branch_lineage_update_failed",
                "message": msg,
                "stage": "branch_lineage",
                "path": str(lineage_path),
            }
        )

    try:
        append_thread_history(thread_history_path, cfg, dispatch)
        result["state_updates"]["thread_history"] = "applied"
    except OSError as exc:
        result["state_updates"]["thread_history"] = "failed_warning"
        result["warnings"].append(
            {
                "code": "thread_history_append_failed",
                "message": f"Failed to append thread history: {exc}",
                "stage": "thread_history",
                "path": str(thread_history_path),
            }
        )

    if cfg.cycle_note:
        cycle_row = {
            "timestamp": utc_now_iso(),
            "event": "dispatch_note",
            "slot": cfg.slot,
            "task_identifier": cfg.task_identifier,
            "note": cfg.cycle_note,
        }
        try:
            append_jsonl(cycle_path, cycle_row)
            result["state_updates"]["cycle_log_note"] = "applied"
        except OSError as exc:
            result["state_updates"]["cycle_log_note"] = "failed_warning"
            result["warnings"].append(
                {
                    "code": "cycle_log_note_failed",
                    "message": f"Failed to append cycle note: {exc}",
                    "stage": "cycle_log",
                    "path": str(cycle_path),
                }
            )

    result["ok"] = len(result["errors"]) == 0
    if result["ok"]:
        result["status"] = "completed"
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dispatch worker packet with deterministic state updates")
    parser.add_argument("--input-json", help="JSON input file path or '-' for stdin")
    parser.add_argument("--slot")
    parser.add_argument("--role")
    parser.add_argument("--task-identifier")
    parser.add_argument("--repo-root")
    parser.add_argument("--worktree-root")
    parser.add_argument("--branch-name")
    parser.add_argument("--start-from-branch")
    parser.add_argument("--start-from-commit")
    parser.add_argument("--acceptance-criteria-json")
    parser.add_argument("--packet-version", type=int)
    parser.add_argument("--codex-profile-alias")
    parser.add_argument("--mcp-mode")
    parser.add_argument("--mcp-allowlist", action="append")
    parser.add_argument("--sandbox-mode")
    parser.add_argument("--sandbox-add-dirs", action="append")
    parser.add_argument("--runtime-strategy")
    parser.add_argument("--runtime-base-url")
    parser.add_argument("--tester-must-not-start-runtime", dest="tester_must_not_start_runtime", action="store_true")
    parser.add_argument("--allow-tester-local-runtime", dest="tester_must_not_start_runtime", action="store_false")
    parser.set_defaults(tester_must_not_start_runtime=None)
    parser.add_argument("--test-train-mode")
    parser.add_argument("--wave-id")
    parser.add_argument("--deployed-test-commit")
    parser.add_argument("--test-lane-account")
    parser.add_argument("--cycle-note")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json-pretty", action="store_true")
    return parser.parse_args()


def print_json(obj: dict[str, Any], pretty: bool) -> None:
    if pretty:
        print(json.dumps(obj, indent=2, sort_keys=False))
    else:
        print(json.dumps(obj, separators=(",", ":"), sort_keys=False))


def main() -> int:
    args = parse_args()
    try:
        cfg = config_from_args(args)
        out = run_dispatch_worker_packet(cfg)
        print_json(out, args.json_pretty)
        return 0 if out.get("ok") else 1
    except ToolError as exc:
        out = {
            "schema_version": SCHEMA_VERSION,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "ok": False,
            "slot": args.slot,
            "role": args.role,
            "task_identifier": args.task_identifier,
            "packet_path": None,
            "dispatch_started": False,
            "pid": None,
            "dispatch_log": None,
            "branch": args.branch_name,
            "start_anchor": {
                "start_from_branch": args.start_from_branch,
                "start_from_commit": args.start_from_commit,
            },
            "registry_updated": False,
            "handoff_logged": False,
            "warnings": [],
            "errors": [{"code": exc.code, "message": exc.message, "stage": exc.stage}],
        }
        print_json(out, args.json_pretty)
        return 1
    except json.JSONDecodeError as exc:
        out = {
            "schema_version": SCHEMA_VERSION,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "ok": False,
            "warnings": [],
            "errors": [{"code": "input_error", "message": f"Invalid JSON input: {exc}", "stage": "input"}],
        }
        print_json(out, args.json_pretty)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
