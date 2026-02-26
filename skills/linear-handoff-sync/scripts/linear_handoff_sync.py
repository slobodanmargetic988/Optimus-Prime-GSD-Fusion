#!/usr/bin/env python3
"""Atomic Linear status/comment sync with deterministic local logging."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

TOOL = "linear-handoff-sync"
TOOL_VERSION = "0.1.0"
SCHEMA_VERSION = "1.0"

DEFAULT_LINEAR_WORKFLOW_PATH = Path("agents/_shared/LINEAR_WORKFLOW.md")
DEFAULT_LINEAR_SYNC_LOG_PATH = Path("reports/optimus-prime/LINEAR_SYNC_LOG.jsonl")
DEFAULT_LINEAR_ENDPOINT = "https://api.linear.app/graphql"

PHASE_TO_WORKFLOW_KEY = {
    "agent_working": "agent_working_status",
    "agent_work_done": "agent_work_done_status",
    "agent_testing": "agent_testing_status",
    "agent_test_done": "agent_test_done_status",
    "agent_review": "agent_review_status",
    "agent_review_done": "agent_review_done_status",
    "human_review": "human_review_status",
    "done": "done",
    "backlog": "backlog",
}

BUILTIN_PHASE_STATUS = {
    "done": "Done",
    "backlog": "Backlog",
}

CHECK_RESULT_ALLOWED = {"pass", "fail", "skip"}


class ToolError(Exception):
    def __init__(self, code: str, message: str, *, stage: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.stage = stage


@dataclass
class SyncInput:
    issue_identifier: str
    target_phase: str
    summary_payload: dict[str, Any]
    comment_template: str | None
    dry_run: bool
    repo_root: Path
    linear_workflow_path: Path
    linear_sync_log_path: Path
    linear_endpoint: str
    linear_api_key: str | None
    status_override_name: str | None


@dataclass
class SyncResult:
    ok: bool
    issue_identifier: str
    target_phase: str
    mapped_status_name: str | None
    status_applied: bool
    comment_created: bool
    comment_id: str | None
    dedup_hit: bool
    log_written: bool
    partial_success: bool
    override_used: bool
    warnings: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    retry_token: str | None = None
    fingerprint: str | None = None
    planned_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "ok": self.ok,
            "issue_identifier": self.issue_identifier,
            "target_phase": self.target_phase,
            "mapped_status_name": self.mapped_status_name,
            "status_applied": self.status_applied,
            "comment_created": self.comment_created,
            "comment_id": self.comment_id,
            "dedup_hit": self.dedup_hit,
            "log_written": self.log_written,
            "partial_success": self.partial_success,
            "override_used": self.override_used,
            "retry_token": self.retry_token,
            "fingerprint": self.fingerprint,
            "planned_actions": self.planned_actions,
            "warnings": self.warnings,
            "errors": self.errors,
        }


class LinearGateway(Protocol):
    def resolve_issue(self, issue_identifier: str) -> dict[str, Any]: ...

    def update_issue_status(self, issue_id: str, state_id: str) -> dict[str, Any]: ...

    def list_issue_comments(self, issue_id: str, limit: int = 50) -> list[dict[str, Any]]: ...

    def create_comment(self, issue_id: str, body: str) -> dict[str, Any]: ...


class GraphqlLinearGateway:
    def __init__(self, api_key: str, endpoint: str = DEFAULT_LINEAR_ENDPOINT) -> None:
        self.api_key = api_key
        self.endpoint = endpoint

    def _post(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint,
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": self.api_key,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            try:
                body = exc.read().decode("utf-8")
            except Exception:
                body = ""
            raise ToolError("linear_http_error", f"Linear API HTTP error: {exc.code} {body}", stage="remote") from exc
        except urllib.error.URLError as exc:
            raise ToolError("linear_network_error", f"Linear API network error: {exc}", stage="remote") from exc

        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ToolError("linear_protocol_error", "Linear API returned non-JSON response", stage="remote") from exc

        if not isinstance(parsed, dict):
            raise ToolError("linear_protocol_error", "Linear API returned invalid response object", stage="remote")

        if parsed.get("errors"):
            msg = "; ".join(str(err.get("message", err)) for err in parsed["errors"] if isinstance(err, dict))
            if not msg:
                msg = "Unknown GraphQL error"
            raise ToolError("linear_graphql_error", msg, stage="remote")

        data = parsed.get("data")
        if not isinstance(data, dict):
            raise ToolError("linear_protocol_error", "Linear API response missing data object", stage="remote")
        return data

    def resolve_issue(self, issue_identifier: str) -> dict[str, Any]:
        attempts: list[tuple[str, str, dict[str, Any]]] = []

        q_issue = """
        query ResolveIssueById($id: String!) {
          issue(id: $id) {
            id
            identifier
            title
            state { id name }
            team {
              id
              key
              name
              states(first: 200) {
                nodes { id name type }
              }
            }
          }
        }
        """
        attempts.append(("issue_by_id", q_issue, {"id": issue_identifier}))

        match = re.fullmatch(r"([A-Za-z]+)-(\d+)", issue_identifier)
        if match:
            team_key = match.group(1).upper()
            number = float(match.group(2))
            q_issue_number = """
            query ResolveIssueByNumber($teamKey: String!, $number: Float!) {
              issueByNumber(teamKey: $teamKey, number: $number) {
                id
                identifier
                title
                state { id name }
                team {
                  id
                  key
                  name
                  states(first: 200) {
                    nodes { id name type }
                  }
                }
              }
            }
            """
            attempts.append(("issue_by_number", q_issue_number, {"teamKey": team_key, "number": number}))

        q_issues_filter = """
        query ResolveIssueByFilter($identifier: String!) {
          issues(filter: { identifier: { eq: $identifier } }, first: 1) {
            nodes {
              id
              identifier
              title
              state { id name }
              team {
                id
                key
                name
                states(first: 200) {
                  nodes { id name type }
                }
              }
            }
          }
        }
        """
        attempts.append(("issue_by_filter", q_issues_filter, {"identifier": issue_identifier}))

        last_error: ToolError | None = None

        for mode, query, variables in attempts:
            try:
                data = self._post(query, variables)
            except ToolError as exc:
                last_error = exc
                continue

            issue = data.get("issue")
            if mode == "issue_by_number":
                issue = data.get("issueByNumber")
            if mode == "issue_by_filter":
                issues = data.get("issues")
                nodes = issues.get("nodes") if isinstance(issues, dict) else None
                issue = nodes[0] if isinstance(nodes, list) and nodes else None

            if isinstance(issue, dict):
                team = issue.get("team") if isinstance(issue.get("team"), dict) else {}
                states = team.get("states") if isinstance(team.get("states"), dict) else {}
                nodes = states.get("nodes") if isinstance(states.get("nodes"), list) else []
                return {
                    "id": issue.get("id"),
                    "identifier": issue.get("identifier"),
                    "title": issue.get("title"),
                    "state_id": (issue.get("state") or {}).get("id") if isinstance(issue.get("state"), dict) else None,
                    "state_name": (issue.get("state") or {}).get("name") if isinstance(issue.get("state"), dict) else None,
                    "team_id": team.get("id"),
                    "team_key": team.get("key"),
                    "team_states": [node for node in nodes if isinstance(node, dict)],
                }

        if last_error is not None:
            raise last_error
        raise ToolError("not_found", f"Issue not found: {issue_identifier}", stage="resolve_issue")

    def update_issue_status(self, issue_id: str, state_id: str) -> dict[str, Any]:
        query = """
        mutation UpdateIssueState($id: String!, $stateId: String!) {
          issueUpdate(id: $id, input: { stateId: $stateId }) {
            success
            issue {
              id
              identifier
              state { id name }
            }
          }
        }
        """
        data = self._post(query, {"id": issue_id, "stateId": state_id})
        payload = data.get("issueUpdate")
        if not isinstance(payload, dict) or not payload.get("success"):
            raise ToolError("status_update_failed", "Linear issue status update failed", stage="update_status")
        issue = payload.get("issue") if isinstance(payload.get("issue"), dict) else {}
        return {
            "id": issue.get("id"),
            "identifier": issue.get("identifier"),
            "state_id": (issue.get("state") or {}).get("id") if isinstance(issue.get("state"), dict) else None,
            "state_name": (issue.get("state") or {}).get("name") if isinstance(issue.get("state"), dict) else None,
        }

    def list_issue_comments(self, issue_id: str, limit: int = 50) -> list[dict[str, Any]]:
        query = """
        query IssueComments($id: String!, $limit: Int!) {
          issue(id: $id) {
            comments(first: $limit) {
              nodes {
                id
                body
                createdAt
              }
            }
          }
        }
        """
        data = self._post(query, {"id": issue_id, "limit": limit})
        issue = data.get("issue") if isinstance(data.get("issue"), dict) else None
        if not issue:
            return []
        comments = issue.get("comments") if isinstance(issue.get("comments"), dict) else {}
        nodes = comments.get("nodes") if isinstance(comments.get("nodes"), list) else []
        return [node for node in nodes if isinstance(node, dict)]

    def create_comment(self, issue_id: str, body: str) -> dict[str, Any]:
        query = """
        mutation CreateIssueComment($issueId: String!, $body: String!) {
          commentCreate(input: { issueId: $issueId, body: $body }) {
            success
            comment {
              id
              body
            }
          }
        }
        """
        data = self._post(query, {"issueId": issue_id, "body": body})
        payload = data.get("commentCreate")
        if not isinstance(payload, dict) or not payload.get("success"):
            raise ToolError("comment_create_failed", "Linear comment creation failed", stage="create_comment")
        comment = payload.get("comment") if isinstance(payload.get("comment"), dict) else {}
        return {
            "id": comment.get("id"),
            "body": comment.get("body"),
        }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_workflow_statuses(path: Path) -> dict[str, str]:
    if not path.exists():
        raise ToolError("config_missing", f"Linear workflow file not found: {path}", stage="config")

    pattern = re.compile(r"-\s+`([^`]+)`:\s+`([^`]+)`")
    statuses: dict[str, str] = {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                match = pattern.search(line)
                if match:
                    statuses[match.group(1).strip()] = match.group(2).strip()
    except OSError as exc:
        raise ToolError("config_read_error", f"Failed to read workflow file: {exc}", stage="config") from exc

    return statuses


def normalize_phase(value: str) -> str:
    return value.strip().lower()


def resolve_status_name(target_phase: str, workflow_statuses: dict[str, str], override_name: str | None) -> tuple[str, bool]:
    if override_name:
        return override_name.strip(), True

    phase_key = PHASE_TO_WORKFLOW_KEY.get(target_phase)
    if not phase_key:
        raise ToolError("config_error", f"Unknown target_phase: {target_phase}", stage="resolve_phase")

    if target_phase in BUILTIN_PHASE_STATUS:
        return BUILTIN_PHASE_STATUS[target_phase], False

    mapped = workflow_statuses.get(phase_key)
    if not mapped:
        raise ToolError(
            "config_error",
            f"Missing status mapping for phase '{target_phase}' (expected key: {phase_key})",
            stage="resolve_status",
        )
    return mapped, False


def normalize_checks(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    result: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        out = str(item.get("result", "skip")).strip().lower()
        details = item.get("details")
        if out not in CHECK_RESULT_ALLOWED:
            out = "skip"
        result.append(
            {
                "name": name or "unnamed-check",
                "result": out,
                "details": None if details is None else str(details),
            }
        )
    return result


def normalize_summary_payload(payload: Any, issue_identifier: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ToolError("input_error", "summary_payload must be a JSON object", stage="input")

    task_identifier = str(payload.get("task_identifier", issue_identifier)).strip() or issue_identifier
    branch = payload.get("branch")
    head_commit = payload.get("head_commit")
    decision = str(payload.get("decision", "unknown")).strip() or "unknown"
    blockers_raw = payload.get("blockers")
    blockers: list[str] = []
    if isinstance(blockers_raw, list):
        blockers = [str(item).strip() for item in blockers_raw if str(item).strip()]

    return {
        "task_identifier": task_identifier,
        "branch": None if branch in (None, "", "null") else str(branch),
        "head_commit": None if head_commit in (None, "", "null") else str(head_commit),
        "decision": decision,
        "checks": normalize_checks(payload.get("checks", [])),
        "blockers": blockers,
    }


def compute_fingerprint(issue_identifier: str, target_phase: str, head_commit: str | None, decision: str) -> tuple[str, str]:
    key = f"{issue_identifier}|{target_phase}|{head_commit or 'null'}|{decision}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return key, digest


def find_state_id(team_states: list[dict[str, Any]], mapped_status_name: str) -> str:
    target = mapped_status_name.strip().lower()
    for state in team_states:
        name = str(state.get("name", "")).strip()
        if name.lower() == target:
            state_id = state.get("id")
            if isinstance(state_id, str) and state_id.strip():
                return state_id
    raise ToolError(
        "config_error",
        f"Mapped status '{mapped_status_name}' not found in issue team workflow states",
        stage="resolve_status",
    )


def fingerprint_marker(fingerprint: str) -> str:
    return f"<!-- {TOOL}:fingerprint={fingerprint} -->"


def format_checks_markdown(checks: list[dict[str, Any]]) -> str:
    if not checks:
        return "- none"
    rows = []
    for check in checks:
        details = f" - {check['details']}" if check.get("details") else ""
        rows.append(f"- {check['name']}: {check['result']}{details}")
    return "\n".join(rows)


def format_blockers_markdown(blockers: list[str]) -> str:
    if not blockers:
        return "- none"
    return "\n".join(f"- {item}" for item in blockers)


def build_comment_body(
    issue_identifier: str,
    target_phase: str,
    mapped_status_name: str,
    summary_payload: dict[str, Any],
    template: str | None,
    fingerprint: str,
) -> str:
    checks_md = format_checks_markdown(summary_payload["checks"])
    blockers_md = format_blockers_markdown(summary_payload["blockers"])

    branch = summary_payload.get("branch") or "null"
    head_commit = summary_payload.get("head_commit") or "null"

    context = {
        "issue_identifier": issue_identifier,
        "target_phase": target_phase,
        "mapped_status_name": mapped_status_name,
        "task_identifier": summary_payload["task_identifier"],
        "branch": branch,
        "head_commit": head_commit,
        "decision": summary_payload["decision"],
        "checks": checks_md,
        "blockers": blockers_md,
        "fingerprint": fingerprint,
    }

    if template and ("\n" in template or "{" in template):
        body = template.format(**context)
    elif template == "compact":
        body = (
            f"{summary_payload['task_identifier']} -> {summary_payload['decision']}\n"
            f"branch={branch} head={head_commit}\n"
            f"status={mapped_status_name}\n"
            f"blockers={', '.join(summary_payload['blockers']) if summary_payload['blockers'] else 'none'}"
        )
    else:
        body = (
            f"### Handoff Sync\n"
            f"- issue: `{issue_identifier}`\n"
            f"- task: `{summary_payload['task_identifier']}`\n"
            f"- phase: `{target_phase}`\n"
            f"- mapped_status: `{mapped_status_name}`\n"
            f"- decision: `{summary_payload['decision']}`\n"
            f"- branch: `{branch}`\n"
            f"- head_commit: `{head_commit}`\n"
            f"\n"
            f"Checks:\n{checks_md}\n"
            f"\n"
            f"Blockers:\n{blockers_md}\n"
        )

    return f"{body.strip()}\n\n{fingerprint_marker(fingerprint)}"


def read_log_for_dedup(log_path: Path, issue_identifier: str, fingerprint: str) -> tuple[bool, int, list[dict[str, Any]]]:
    if not log_path.exists():
        return False, 0, []

    parse_warning_count = 0
    warnings: list[dict[str, Any]] = []

    try:
        with log_path.open("r", encoding="utf-8") as fh:
            for idx, line in enumerate(fh, start=1):
                raw = line.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except json.JSONDecodeError:
                    parse_warning_count += 1
                    warnings.append(
                        {
                            "code": "malformed_jsonl_line",
                            "message": "Skipping malformed LINEAR_SYNC_LOG line while dedup-checking",
                            "line_number": idx,
                            "path": str(log_path),
                        }
                    )
                    continue

                if not isinstance(obj, dict):
                    continue
                if obj.get("issue_identifier") != issue_identifier:
                    continue
                if obj.get("fingerprint") == fingerprint and (obj.get("comment_created") or obj.get("dedup_hit")):
                    return True, parse_warning_count, warnings
    except OSError:
        return False, parse_warning_count, warnings

    return False, parse_warning_count, warnings


def append_sync_log(log_path: Path, payload: dict[str, Any]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, sort_keys=False)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(line)
        fh.write("\n")


def make_retry_token(issue_identifier: str, target_phase: str, fingerprint: str) -> str:
    base = f"{issue_identifier}|{target_phase}|{fingerprint}|{utc_now_iso()}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:24]


def run_sync(config: SyncInput, gateway: LinearGateway | None = None) -> SyncResult:
    result = SyncResult(
        ok=False,
        issue_identifier=config.issue_identifier,
        target_phase=config.target_phase,
        mapped_status_name=None,
        status_applied=False,
        comment_created=False,
        comment_id=None,
        dedup_hit=False,
        log_written=False,
        partial_success=False,
        override_used=False,
    )

    workflow_statuses = parse_workflow_statuses(config.linear_workflow_path)
    mapped_status_name, override_used = resolve_status_name(config.target_phase, workflow_statuses, config.status_override_name)
    result.mapped_status_name = mapped_status_name
    result.override_used = override_used
    if override_used:
        result.warnings.append(
            {
                "code": "override_used",
                "message": "Status override was provided and used instead of LINEAR_WORKFLOW mapping",
                "mapped_status_name": mapped_status_name,
            }
        )

    summary_payload = normalize_summary_payload(config.summary_payload, config.issue_identifier)
    _, fingerprint = compute_fingerprint(
        config.issue_identifier,
        config.target_phase,
        summary_payload.get("head_commit"),
        summary_payload["decision"],
    )
    result.fingerprint = fingerprint

    if config.dry_run:
        result.ok = True
        result.planned_actions = [
            "resolve_issue",
            "resolve_target_status",
            "update_status",
            "dedup_check_comment",
            "create_comment_if_needed",
            "append_local_sync_log",
        ]
        result.warnings.append({"code": "dry_run", "message": "Dry-run mode enabled; no remote or local writes performed"})
        return result

    if gateway is None:
        if not config.linear_api_key:
            raise ToolError(
                "auth_error",
                "LINEAR_API_KEY is required for non-dry-run execution",
                stage="auth",
            )
        gateway = GraphqlLinearGateway(api_key=config.linear_api_key, endpoint=config.linear_endpoint)

    issue = gateway.resolve_issue(config.issue_identifier)
    issue_id = issue.get("id")
    if not isinstance(issue_id, str) or not issue_id:
        raise ToolError("not_found", f"Issue not found: {config.issue_identifier}", stage="resolve_issue")

    state_id = find_state_id(issue.get("team_states") or [], mapped_status_name)

    updated = gateway.update_issue_status(issue_id, state_id)
    result.status_applied = bool(updated)

    dedup_local, parse_warning_count, dedup_warnings = read_log_for_dedup(
        config.linear_sync_log_path,
        config.issue_identifier,
        fingerprint,
    )
    if parse_warning_count:
        result.warnings.extend(dedup_warnings)

    comments = gateway.list_issue_comments(issue_id, limit=50)
    marker = fingerprint_marker(fingerprint)
    dedup_remote = any(marker in str(comment.get("body", "")) for comment in comments)

    dedup_hit = dedup_local or dedup_remote
    result.dedup_hit = dedup_hit

    comment_created = False
    comment_id: str | None = None
    try:
        if not dedup_hit:
            body = build_comment_body(
                issue_identifier=config.issue_identifier,
                target_phase=config.target_phase,
                mapped_status_name=mapped_status_name,
                summary_payload=summary_payload,
                template=config.comment_template,
                fingerprint=fingerprint,
            )
            created = gateway.create_comment(issue_id, body)
            comment_id = str(created.get("id")) if created.get("id") is not None else None
            comment_created = True
    except ToolError as exc:
        result.partial_success = result.status_applied
        if result.partial_success:
            result.retry_token = make_retry_token(config.issue_identifier, config.target_phase, fingerprint)
        result.errors.append(
            {
                "code": exc.code,
                "message": exc.message,
                "stage": exc.stage,
            }
        )

    result.comment_created = comment_created
    result.comment_id = comment_id

    log_payload = {
        "timestamp": utc_now_iso(),
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "schema_version": SCHEMA_VERSION,
        "issue_identifier": config.issue_identifier,
        "target_phase": config.target_phase,
        "mapped_status_name": mapped_status_name,
        "status_applied": result.status_applied,
        "comment_created": result.comment_created,
        "comment_id": result.comment_id,
        "dedup_hit": result.dedup_hit,
        "partial_success": result.partial_success,
        "retry_token": result.retry_token,
        "fingerprint": fingerprint,
        "override_used": result.override_used,
        "summary_payload": summary_payload,
        "warnings": result.warnings,
        "errors": result.errors,
    }

    try:
        append_sync_log(config.linear_sync_log_path, log_payload)
        result.log_written = True
    except OSError as exc:
        result.errors.append(
            {
                "code": "log_write_failed",
                "message": f"Failed to append LINEAR_SYNC_LOG: {exc}",
                "stage": "write_log",
                "path": str(config.linear_sync_log_path),
            }
        )
        result.log_written = False
        result.ok = False
        return result

    result.ok = len(result.errors) == 0
    return result


def load_input_json(path: str) -> dict[str, Any]:
    if path == "-":
        raw = os.sys.stdin.read()
    else:
        raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ToolError("input_error", "input payload must be a JSON object", stage="input")
    return data


def resolve_linear_workflow_path(repo_root: Path, override: str | None) -> Path:
    if override:
        requested = Path(str(override)).expanduser()
        if not requested.is_absolute():
            requested = (repo_root / requested).resolve()
        return requested

    env_path = os.environ.get("LINEAR_WORKFLOW_PATH")
    if env_path:
        candidate = Path(env_path).expanduser()
        if not candidate.is_absolute():
            candidate = (repo_root / candidate).resolve()
        if candidate.exists():
            return candidate

    candidates = [
        (repo_root / DEFAULT_LINEAR_WORKFLOW_PATH).resolve(),
        (repo_root / "Agents" / "agents" / "_shared" / "LINEAR_WORKFLOW.md").resolve(),
        (repo_root.parent / "Agents" / "agents" / "_shared" / "LINEAR_WORKFLOW.md").resolve(),
        (Path.cwd() / "agents" / "_shared" / "LINEAR_WORKFLOW.md").resolve(),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    return candidates[0]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Atomic Linear status/comment synchronization with local log append.")
    parser.add_argument("--input-json", help="Path to JSON payload (or '-' for stdin).")
    parser.add_argument("--issue-identifier")
    parser.add_argument("--target-phase")
    parser.add_argument("--summary-payload-json", help="Inline JSON object string for summary_payload.")
    parser.add_argument("--comment-template")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--linear-workflow-path")
    parser.add_argument("--linear-sync-log-path")
    parser.add_argument("--linear-endpoint", default=DEFAULT_LINEAR_ENDPOINT)
    parser.add_argument("--linear-api-key")
    parser.add_argument("--status-override-name")
    parser.add_argument("--json-pretty", action="store_true")
    return parser.parse_args()


def merge_cli_and_json(args: argparse.Namespace) -> SyncInput:
    payload: dict[str, Any] = {}
    if args.input_json:
        payload = load_input_json(args.input_json)

    issue_identifier = args.issue_identifier or payload.get("issue_identifier")
    target_phase = args.target_phase or payload.get("target_phase")

    summary_payload: dict[str, Any] = {}
    if isinstance(payload.get("summary_payload"), dict):
        summary_payload = payload["summary_payload"]
    if args.summary_payload_json:
        parsed = json.loads(args.summary_payload_json)
        if not isinstance(parsed, dict):
            raise ToolError("input_error", "--summary-payload-json must be a JSON object", stage="input")
        summary_payload = parsed

    if not isinstance(issue_identifier, str) or not issue_identifier.strip():
        raise ToolError("input_error", "issue_identifier is required", stage="input")
    if not isinstance(target_phase, str) or not target_phase.strip():
        raise ToolError("input_error", "target_phase is required", stage="input")

    dry_run = bool(payload.get("dry_run", False)) or bool(args.dry_run)

    repo_root = Path(args.repo_root).expanduser().resolve()

    wf = payload.get("linear_workflow_path") or args.linear_workflow_path
    linear_workflow_path = resolve_linear_workflow_path(repo_root, None if wf in (None, "") else str(wf))

    log_path_raw = payload.get("linear_sync_log_path") or args.linear_sync_log_path
    if log_path_raw:
        linear_sync_log_path = Path(str(log_path_raw)).expanduser()
        if not linear_sync_log_path.is_absolute():
            linear_sync_log_path = (repo_root / linear_sync_log_path).resolve()
    else:
        linear_sync_log_path = (repo_root / DEFAULT_LINEAR_SYNC_LOG_PATH).resolve()

    comment_template = args.comment_template if args.comment_template is not None else payload.get("comment_template")
    status_override_name = args.status_override_name if args.status_override_name is not None else payload.get("status_override_name")

    linear_api_key = args.linear_api_key or payload.get("linear_api_key") or os.environ.get("LINEAR_API_KEY")

    return SyncInput(
        issue_identifier=issue_identifier.strip(),
        target_phase=normalize_phase(target_phase),
        summary_payload=summary_payload,
        comment_template=None if comment_template in (None, "") else str(comment_template),
        dry_run=dry_run,
        repo_root=repo_root,
        linear_workflow_path=linear_workflow_path,
        linear_sync_log_path=linear_sync_log_path,
        linear_endpoint=str(payload.get("linear_endpoint") or args.linear_endpoint or DEFAULT_LINEAR_ENDPOINT),
        linear_api_key=None if linear_api_key in (None, "") else str(linear_api_key),
        status_override_name=None if status_override_name in (None, "") else str(status_override_name),
    )


def main() -> int:
    args = parse_args()
    try:
        config = merge_cli_and_json(args)
        result = run_sync(config)
        out = result.to_dict()
        if args.json_pretty:
            print(json.dumps(out, indent=2, sort_keys=False))
        else:
            print(json.dumps(out, separators=(",", ":"), sort_keys=False))
        return 0 if out.get("ok") else 1
    except ToolError as exc:
        out = {
            "schema_version": SCHEMA_VERSION,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "ok": False,
            "issue_identifier": args.issue_identifier,
            "target_phase": args.target_phase,
            "mapped_status_name": None,
            "status_applied": False,
            "comment_created": False,
            "comment_id": None,
            "dedup_hit": False,
            "log_written": False,
            "partial_success": False,
            "override_used": False,
            "retry_token": None,
            "fingerprint": None,
            "planned_actions": [],
            "warnings": [],
            "errors": [{"code": exc.code, "message": exc.message, "stage": exc.stage}],
        }
        if args.json_pretty:
            print(json.dumps(out, indent=2, sort_keys=False))
        else:
            print(json.dumps(out, separators=(",", ":"), sort_keys=False))
        return 1
    except json.JSONDecodeError as exc:
        out = {
            "schema_version": SCHEMA_VERSION,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "ok": False,
            "errors": [{"code": "input_error", "message": f"Invalid JSON input: {exc}", "stage": "input"}],
        }
        if args.json_pretty:
            print(json.dumps(out, indent=2, sort_keys=False))
        else:
            print(json.dumps(out, separators=(",", ":"), sort_keys=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
