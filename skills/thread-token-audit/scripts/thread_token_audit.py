#!/usr/bin/env python3
"""Summarize token usage by project/session/worker type from THREAD_HISTORY.log."""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TOOL = "thread-token-audit"
TOOL_VERSION = "0.1.0"
SCHEMA_VERSION = "1.0"


class ToolError(Exception):
    def __init__(self, code: str, message: str, stage: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.stage = stage


@dataclass
class AuditInput:
    repo_root: Path
    thread_history_path: Path
    worker_registry_path: Path
    output_json_path: Path
    output_markdown_path: Path
    codex_homes: dict[str, Path]


@dataclass
class SessionUsage:
    thread_id: str
    slot: str
    worker_type: str
    codex_alias: str | None
    codex_home: str | None
    session_file: str | None
    input_tokens: int | None
    cached_input_tokens: int | None
    output_tokens: int | None
    reasoning_output_tokens: int | None
    total_tokens: int | None
    resolved: bool


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit token usage using thread history + codex session logs")
    parser.add_argument("--input-json", required=True, help="Path to JSON input or '-' for stdin")
    parser.add_argument("--json-pretty", action="store_true")
    return parser.parse_args()


def _str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    text = str(value).strip()
    return text or None


def _resolve_path(raw: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(raw))).resolve()


def parse_json_input(path: str) -> dict[str, Any]:
    if path == "-":
        import sys

        raw = sys.stdin.read()
    else:
        raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ToolError("input_error", "input must be JSON object", stage="input")
    return data


def resolve_codex_home(alias: str) -> Path:
    if alias == "codex":
        env_home = os.environ.get("CODEX_HOME")
        if env_home:
            return _resolve_path(env_home)
        return (Path.home() / ".codex").resolve()
    return (Path.home() / f".{alias}").resolve()


def parse_codex_homes(raw: Any) -> dict[str, Path]:
    if raw is None:
        return {}

    result: dict[str, Path] = {}
    if isinstance(raw, dict):
        for alias, value in raw.items():
            alias_text = _str(alias)
            value_text = _str(value)
            if alias_text and value_text:
                result[alias_text] = _resolve_path(value_text)
        return result

    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str) and "=" in item:
                alias, value = item.split("=", 1)
                alias_text = _str(alias)
                value_text = _str(value)
                if alias_text and value_text:
                    result[alias_text] = _resolve_path(value_text)
        return result

    raise ToolError("input_error", "codex_homes must be object or alias=path list", stage="input")


def build_input(payload: dict[str, Any]) -> AuditInput:
    repo_root_raw = _str(payload.get("repo_root"))
    if not repo_root_raw:
        raise ToolError("input_error", "repo_root is required", stage="input")

    repo_root = _resolve_path(repo_root_raw)
    reports_root = repo_root / "reports" / "optimus-prime"

    thread_history_path = _resolve_path(
        _str(payload.get("thread_history_path")) or str(reports_root / "THREAD_HISTORY.log")
    )
    worker_registry_path = _resolve_path(
        _str(payload.get("worker_registry_path")) or str(reports_root / "WORKER_REGISTRY.json")
    )
    output_json_path = _resolve_path(
        _str(payload.get("output_json_path"))
        or str(reports_root / "THREAD_TOKEN_USAGE_SUMMARY.json")
    )
    output_markdown_path = _resolve_path(
        _str(payload.get("output_markdown_path"))
        or str(reports_root / "THREAD_TOKEN_USAGE_SUMMARY.md")
    )

    codex_homes = parse_codex_homes(payload.get("codex_homes"))

    return AuditInput(
        repo_root=repo_root,
        thread_history_path=thread_history_path,
        worker_registry_path=worker_registry_path,
        output_json_path=output_json_path,
        output_markdown_path=output_markdown_path,
        codex_homes=codex_homes,
    )


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    data = json.loads(path.read_text(encoding="utf-8"))
    return data


def parse_thread_history(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise ToolError("missing_file", f"thread history file not found: {path}", stage="history")

    rows: list[dict[str, str]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lower = line.lower()
        if lower == "slot | worker type | thread-id":
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 3:
            continue
        slot, worker_type, thread_id = parts[0], parts[1], parts[2]
        if not slot or not worker_type or not thread_id:
            continue
        rows.append(
            {
                "slot": slot,
                "worker_type": worker_type,
                "thread_id": thread_id,
            }
        )
    return rows


def alias_by_slot(worker_registry_path: Path) -> dict[str, str]:
    data = read_json(worker_registry_path, {"workers": []})
    workers = data.get("workers") if isinstance(data, dict) else []

    mapping: dict[str, str] = {}
    if isinstance(workers, list):
        for item in workers:
            if not isinstance(item, dict):
                continue
            slot = _str(item.get("slot"))
            alias = _str(item.get("codex_profile_alias"))
            if slot and alias:
                mapping[slot] = alias
    elif isinstance(workers, dict):
        for slot, item in workers.items():
            if not isinstance(item, dict):
                continue
            alias = _str(item.get("codex_profile_alias"))
            if _str(slot) and alias:
                mapping[str(slot)] = alias

    return mapping


def ensure_codex_home_map(inp: AuditInput, history_rows: list[dict[str, str]]) -> dict[str, Path]:
    mapping = dict(inp.codex_homes)
    slot_alias = alias_by_slot(inp.worker_registry_path)

    aliases = {"codex"}
    aliases.update(slot_alias.values())

    for row in history_rows:
        alias = slot_alias.get(row["slot"])
        if alias:
            aliases.add(alias)

    for alias in sorted(aliases):
        if alias not in mapping:
            mapping[alias] = resolve_codex_home(alias)

    return mapping


def find_session_file(codex_home: Path, thread_id: str) -> Path | None:
    sessions_root = codex_home / "sessions"
    if not sessions_root.exists():
        return None

    candidates = [p for p in sessions_root.rglob(f"*{thread_id}*.jsonl") if p.is_file()]
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def is_token_count_event(obj: dict[str, Any]) -> bool:
    if obj.get("type") == "token_count":
        return True
    payload = obj.get("payload")
    if isinstance(payload, dict):
        if payload.get("type") == "token_count":
            return True
        msg = payload.get("msg")
        if isinstance(msg, dict) and msg.get("type") == "token_count":
            return True
        event = payload.get("event")
        if isinstance(event, dict) and event.get("type") == "token_count":
            return True
    return False


def extract_token_usage(session_file: Path) -> dict[str, int | None]:
    last_usage: dict[str, int | None] = {
        "input_tokens": None,
        "cached_input_tokens": None,
        "output_tokens": None,
        "reasoning_output_tokens": None,
        "total_tokens": None,
    }

    with session_file.open("r", encoding="utf-8") as fh:
        for line in fh:
            text = line.strip()
            if not text:
                continue
            try:
                obj = json.loads(text)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            if not is_token_count_event(obj) and "token_count" not in text:
                continue

            payload = obj.get("payload") if isinstance(obj.get("payload"), dict) else obj
            info = payload.get("info") if isinstance(payload, dict) and isinstance(payload.get("info"), dict) else None
            usage = (
                info.get("total_token_usage")
                if isinstance(info, dict) and isinstance(info.get("total_token_usage"), dict)
                else None
            )
            if not isinstance(usage, dict):
                continue

            for key in last_usage.keys():
                value = usage.get(key)
                if isinstance(value, int):
                    last_usage[key] = value
                elif isinstance(value, float):
                    last_usage[key] = int(value)

    return last_usage


def markdown_report(summary: dict[str, Any]) -> str:
    lines: list[str] = [
        "# Thread Token Usage Summary",
        "",
        f"Generated: {summary['generated_at']}",
        "",
        "## Totals",
        f"- Project total tokens: **{summary['project_total_tokens']}**",
        f"- Sessions tracked: **{summary['sessions_tracked']}**",
        f"- Sessions resolved: **{summary['sessions_resolved']}**",
        f"- Sessions unresolved: **{summary['sessions_unresolved']}**",
        "",
        "## Tokens by Worker Type",
    ]

    by_worker = summary.get("tokens_by_worker_type", {})
    if by_worker:
        for worker_type in sorted(by_worker.keys()):
            lines.append(f"- {worker_type}: **{by_worker[worker_type]}**")
    else:
        lines.append("- none")

    lines.extend(["", "## Session Details", "", "| slot | worker type | thread-id | total tokens | resolved |", "|---|---|---|---:|---|",])
    for item in summary.get("sessions", []):
        total = item.get("total_tokens")
        total_text = str(total) if isinstance(total, int) else "-"
        resolved = "yes" if item.get("resolved") else "no"
        lines.append(
            f"| {item.get('slot')} | {item.get('worker_type')} | {item.get('thread_id')} | {total_text} | {resolved} |"
        )

    return "\n".join(lines).rstrip() + "\n"


def run(inp: AuditInput) -> dict[str, Any]:
    history_rows = parse_thread_history(inp.thread_history_path)
    codex_home_map = ensure_codex_home_map(inp, history_rows)
    slot_alias_map = alias_by_slot(inp.worker_registry_path)

    unique_sessions: dict[str, dict[str, str]] = {}
    for row in history_rows:
        thread_id = row["thread_id"]
        if thread_id == "unknown":
            continue
        if thread_id not in unique_sessions:
            unique_sessions[thread_id] = row

    sessions: list[SessionUsage] = []

    for thread_id, row in unique_sessions.items():
        slot = row["slot"]
        worker_type = row["worker_type"]
        alias = slot_alias_map.get(slot, "codex")
        home = codex_home_map.get(alias)

        session_file: Path | None = None
        resolved_alias: str | None = None
        if home is not None:
            session_file = find_session_file(home, thread_id)
            resolved_alias = alias if session_file else None

        if session_file is None:
            for candidate_alias, candidate_home in codex_home_map.items():
                candidate_file = find_session_file(candidate_home, thread_id)
                if candidate_file is not None:
                    session_file = candidate_file
                    resolved_alias = candidate_alias
                    home = candidate_home
                    break

        if session_file is None:
            sessions.append(
                SessionUsage(
                    thread_id=thread_id,
                    slot=slot,
                    worker_type=worker_type,
                    codex_alias=alias,
                    codex_home=str(home) if home else None,
                    session_file=None,
                    input_tokens=None,
                    cached_input_tokens=None,
                    output_tokens=None,
                    reasoning_output_tokens=None,
                    total_tokens=None,
                    resolved=False,
                )
            )
            continue

        usage = extract_token_usage(session_file)
        total_tokens = usage.get("total_tokens")
        sessions.append(
            SessionUsage(
                thread_id=thread_id,
                slot=slot,
                worker_type=worker_type,
                codex_alias=resolved_alias,
                codex_home=str(home) if home else None,
                session_file=str(session_file),
                input_tokens=usage.get("input_tokens"),
                cached_input_tokens=usage.get("cached_input_tokens"),
                output_tokens=usage.get("output_tokens"),
                reasoning_output_tokens=usage.get("reasoning_output_tokens"),
                total_tokens=total_tokens,
                resolved=total_tokens is not None,
            )
        )

    sessions.sort(key=lambda s: (s.slot, s.worker_type, s.thread_id))

    project_total = 0
    by_worker: dict[str, int] = defaultdict(int)
    by_slot: dict[str, int] = defaultdict(int)

    for item in sessions:
        if isinstance(item.total_tokens, int):
            project_total += item.total_tokens
            by_worker[item.worker_type] += item.total_tokens
            by_slot[item.slot] += item.total_tokens

    summary = {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "generated_at": utc_now_iso(),
        "repo_root": str(inp.repo_root),
        "thread_history_path": str(inp.thread_history_path),
        "project_total_tokens": project_total,
        "sessions_tracked": len(sessions),
        "sessions_resolved": sum(1 for s in sessions if s.resolved),
        "sessions_unresolved": sum(1 for s in sessions if not s.resolved),
        "tokens_by_worker_type": dict(sorted(by_worker.items())),
        "tokens_by_slot": dict(sorted(by_slot.items())),
        "sessions": [
            {
                "slot": s.slot,
                "worker_type": s.worker_type,
                "thread_id": s.thread_id,
                "codex_alias": s.codex_alias,
                "codex_home": s.codex_home,
                "session_file": s.session_file,
                "input_tokens": s.input_tokens,
                "cached_input_tokens": s.cached_input_tokens,
                "output_tokens": s.output_tokens,
                "reasoning_output_tokens": s.reasoning_output_tokens,
                "total_tokens": s.total_tokens,
                "resolved": s.resolved,
            }
            for s in sessions
        ],
    }

    inp.output_json_path.parent.mkdir(parents=True, exist_ok=True)
    inp.output_json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = markdown_report(summary)
    inp.output_markdown_path.parent.mkdir(parents=True, exist_ok=True)
    inp.output_markdown_path.write_text(report, encoding="utf-8")

    return summary


def print_json(payload: dict[str, Any], pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=False))
    else:
        print(json.dumps(payload, sort_keys=False, separators=(",", ":")))


def main() -> int:
    args = parse_args()
    try:
        payload = parse_json_input(args.input_json)
        inp = build_input(payload)
        result = run(inp)
        print_json(result, args.json_pretty)
        return 0
    except ToolError as exc:
        result = {
            "ok": False,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "schema_version": SCHEMA_VERSION,
            "error": {"code": exc.code, "message": exc.message, "stage": exc.stage},
        }
        print_json(result, args.json_pretty)
        return 1
    except Exception as exc:  # noqa: BLE001
        result = {
            "ok": False,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "schema_version": SCHEMA_VERSION,
            "error": {"code": "runtime_error", "message": str(exc), "stage": "runtime"},
        }
        print_json(result, args.json_pretty)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
