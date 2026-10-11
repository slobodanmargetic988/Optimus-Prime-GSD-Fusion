"""Local Claude Code execution for Optimus managers, planners, and workers.

Authentication stays with the user's Claude installation. ANTHROPIC_API_KEY,
when present, selects API billing; otherwise the CLI uses its existing login.
The adapter never reads, copies, or persists credentials. It does not translate
Claude into a Codex profile or silently fall back to a different provider.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class ClaudeResult:
    returncode: int
    timeout: bool = False
    session_id: str | None = None
    message: str | None = None
    reason_code: str | None = None


@dataclass(frozen=True)
class ClaudeLaunchResult:
    pid: int
    session_id: str


def build_claude_command(
    *,
    model: str | None = None,
    reasoning_effort: str | None = None,
    resume_session_id: str | None = None,
    session_id: str | None = None,
) -> list[str]:
    """Build an unattended command without putting prompts or keys in argv.

    dontAsk respects explicit Claude deny rules and refuses tools outside the
    configured grants. Bash access is intentional for trusted local projects:
    this is an autonomous coding worker, not an OS security sandbox.
    """
    binary = os.environ.get("OP_CLAUDE_BIN", "claude").strip() or "claude"
    command = [
        binary,
        "--print",
        "--output-format", "json",
        "--permission-mode", "dontAsk",
        "--allowedTools", "Read,Write,Edit,Bash,Glob,Grep",
    ]
    if model and model.strip():
        command.extend(["--model", model.strip()])
    if reasoning_effort and reasoning_effort.strip():
        effort = reasoning_effort.strip().lower()
        effort = {"minimal": "low", "none": "low", "ultra": "max"}.get(effort, effort)
        if effort not in {"low", "medium", "high", "xhigh", "max"}:
            raise ValueError(f"Unsupported Claude reasoning effort: {reasoning_effort}")
        command.extend(["--effort", effort])
    if resume_session_id:
        command.extend(["--resume", str(uuid.UUID(resume_session_id))])
    elif session_id:
        command.extend(["--session-id", str(uuid.UUID(session_id))])
    return command


def _output_text(value: str | bytes | None) -> str:
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value or ""


def _decode_result(stdout: str, returncode: int) -> tuple[str, ClaudeResult]:
    try:
        payload = json.loads(stdout)
    except (ValueError, TypeError):
        return "", ClaudeResult(
            returncode=returncode or 1,
            message="Claude returned no valid JSON result; see execution logs.",
            reason_code="claude_invalid_result",
        )
    if not isinstance(payload, dict) or payload.get("type") != "result":
        return "", ClaudeResult(
            returncode=returncode or 1,
            message="Claude returned an unexpected result envelope; see execution logs.",
            reason_code="claude_invalid_result",
        )
    final = payload.get("result")
    final_text = final if isinstance(final, str) else ""
    session_id = payload.get("session_id")
    session_id = session_id if isinstance(session_id, str) else None
    denied = bool(payload.get("permission_denials"))
    failed = returncode != 0 or bool(payload.get("is_error")) or denied
    reason = "claude_permission_denied" if denied else "claude_execution_failed" if failed else None
    return final_text, ClaudeResult(
        returncode=returncode or int(failed),
        session_id=session_id,
        message="Claude could not complete the run; see execution logs." if failed else None,
        reason_code=reason,
    )


def run_claude_exec(
    *,
    repo_root: Path,
    prompt_text: str,
    output_last_message: Path,
    stdout_path: Path,
    stderr_path: Path,
    timeout_seconds: float = 1800,
    model: str | None = None,
    reasoning_effort: str | None = None,
    resume_session_id: str | None = None,
) -> ClaudeResult:
    # LLM interaction classification: reasoning_effort=high_effort, tooling_effort=medium_tooling.
    for path in (output_last_message, stdout_path, stderr_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    # Never mistake a previous successful response for this attempt's output.
    output_last_message.write_text("", encoding="utf-8")
    try:
        command = build_claude_command(
            model=model,
            reasoning_effort=reasoning_effort,
            resume_session_id=resume_session_id,
        )
        completed = subprocess.run(
            command,
            cwd=str(repo_root),
            input=prompt_text,
            capture_output=True,
            text=True,
            timeout=max(0.01, float(timeout_seconds)),
            check=False,
        )
        stdout_path.write_text(completed.stdout or "", encoding="utf-8")
        stderr_path.write_text(completed.stderr or "", encoding="utf-8")
        final_text, result = _decode_result(completed.stdout, completed.returncode)
        output_last_message.write_text(final_text, encoding="utf-8")
        return result
    except subprocess.TimeoutExpired as exc:
        stdout_path.write_text(_output_text(exc.stdout), encoding="utf-8")
        stderr_path.write_text(_output_text(exc.stderr), encoding="utf-8")
        return ClaudeResult(124, timeout=True, message="Claude execution timed out.", reason_code="claude_timeout")
    except (OSError, ValueError) as exc:
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text(str(exc), encoding="utf-8")
        return ClaudeResult(127, message="Claude could not start; check the CLI installation and configuration.", reason_code="claude_launch_failed")


def launch_claude_background(
    *,
    repo_root: Path,
    prompt_text: str,
    stdout_path: Path,
    stderr_path: Path | None = None,
    model: str | None = None,
    reasoning_effort: str | None = None,
    resume_session_id: str | None = None,
) -> ClaudeLaunchResult:
    # LLM interaction classification: reasoning_effort=high_effort, tooling_effort=medium_tooling.
    session_id = str(uuid.UUID(resume_session_id)) if resume_session_id else str(uuid.uuid4())
    command = build_claude_command(
        model=model,
        reasoning_effort=reasoning_effort,
        resume_session_id=resume_session_id,
        session_id=session_id,
    )
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path = stderr_path or stdout_path.with_suffix(".stderr.log")
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path = stdout_path.with_suffix(".prompt.txt")
    prompt_path.write_text(prompt_text, encoding="utf-8")
    # Keep the worker in the desktop run's process group so Stop can cancel it.
    with prompt_path.open("r", encoding="utf-8") as source, stdout_path.open("w", encoding="utf-8") as out, stderr_path.open("w", encoding="utf-8") as err:
        proc = subprocess.Popen(command, cwd=str(repo_root), stdin=source, stdout=out, stderr=err, text=True)
    return ClaudeLaunchResult(pid=proc.pid, session_id=session_id)
