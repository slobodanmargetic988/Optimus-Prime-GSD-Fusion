#!/usr/bin/env python3
"""Create or update blocker issue in Linear project Agents with deterministic dedup."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

TOOL = "blocker-escalate-to-agents"
TOOL_VERSION = "0.1.0"
SCHEMA_VERSION = "1.0"

BLOCKER_KINDS = {"workflow", "infra", "rate_limit", "review_noise", "worktree", "other"}
SEVERITIES = {"low", "medium", "high"}

DEFAULT_LINEAR_ENDPOINT = "https://api.linear.app/graphql"
DEFAULT_PROJECT_NAME = "Agents"
DEFAULT_ASSIGNEE = "me"
DEFAULT_LOG_PATH = Path("reports/optimus-prime/BLOCKER_ESCALATION_LOG.jsonl")


class ToolError(Exception):
    def __init__(self, code: str, message: str, stage: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.stage = stage


@dataclass
class EscalationInput:
    blocker_kind: str
    title: str
    reproduction_context: str
    impact: str
    attempted_mitigation: list[str]
    requested_user_action: str
    related_task_identifier: str | None
    severity: str
    project_name: str
    assignee: str
    dedup_key: str | None
    dry_run: bool
    repo_root: Path
    linear_endpoint: str
    linear_api_key: str | None
    local_log_path: Path


class LinearGateway(Protocol):
    def resolve_project(self, project_name: str) -> dict[str, Any]: ...

    def resolve_user(self, assignee: str) -> dict[str, Any] | None: ...

    def list_open_project_issues(self, project_id: str, limit: int = 250) -> list[dict[str, Any]]: ...

    def create_issue(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def update_issue(self, issue_id: str, payload: dict[str, Any]) -> dict[str, Any]: ...


class GraphqlLinearGateway:
    def __init__(self, api_key: str, endpoint: str = DEFAULT_LINEAR_ENDPOINT):
        self.api_key = api_key
        self.endpoint = endpoint

    def _post(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        req = urllib.request.Request(
            self.endpoint,
            data=json.dumps({"query": query, "variables": variables}).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json", "Authorization": self.api_key},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8")
            except Exception:
                pass
            raise ToolError("linear_unavailable", f"Linear API HTTP error {exc.code}: {body}", stage="remote") from exc
        except urllib.error.URLError as exc:
            raise ToolError("linear_unavailable", f"Linear API network error: {exc}", stage="remote") from exc

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ToolError("linear_unavailable", "Linear returned non-JSON payload", stage="remote") from exc

        if not isinstance(parsed, dict):
            raise ToolError("linear_unavailable", "Linear returned invalid payload", stage="remote")

        errors = parsed.get("errors")
        if isinstance(errors, list) and errors:
            msg = "; ".join(str(e.get("message", e)) for e in errors if isinstance(e, dict))
            raise ToolError("linear_unavailable", msg or "GraphQL error", stage="remote")

        data = parsed.get("data")
        if not isinstance(data, dict):
            raise ToolError("linear_unavailable", "Linear response missing data", stage="remote")
        return data

    def resolve_project(self, project_name: str) -> dict[str, Any]:
        query = """
        query ProjectsList($first: Int!) {
          projects(first: $first) {
            nodes {
              id
              name
              teams(first: 20) {
                nodes { id name key }
              }
            }
          }
        }
        """
        data = self._post(query, {"first": 200})
        nodes = (((data.get("projects") or {}).get("nodes")) if isinstance(data.get("projects"), dict) else None) or []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            if str(node.get("name", "")).strip().lower() == project_name.strip().lower():
                teams = ((node.get("teams") or {}).get("nodes")) if isinstance(node.get("teams"), dict) else []
                team_id = None
                if isinstance(teams, list) and teams:
                    first_team = teams[0]
                    if isinstance(first_team, dict):
                        team_id = first_team.get("id")
                return {
                    "id": node.get("id"),
                    "name": node.get("name"),
                    "team_id": team_id,
                }
        raise ToolError("setup_error", f"Project '{project_name}' not found", stage="resolve_project")

    def resolve_user(self, assignee: str) -> dict[str, Any] | None:
        if assignee == "me":
            query = "query { viewer { id name email } }"
            data = self._post(query, {})
            viewer = data.get("viewer")
            if isinstance(viewer, dict) and viewer.get("id"):
                return {"id": viewer.get("id"), "name": viewer.get("name"), "email": viewer.get("email")}
            return None

        query = """
        query Users($first: Int!) {
          users(first: $first) {
            nodes { id name email }
          }
        }
        """
        data = self._post(query, {"first": 250})
        nodes = (((data.get("users") or {}).get("nodes")) if isinstance(data.get("users"), dict) else None) or []
        key = assignee.strip().lower()
        for node in nodes:
            if not isinstance(node, dict):
                continue
            if str(node.get("id", "")).lower() == key:
                return node
            if str(node.get("name", "")).strip().lower() == key:
                return node
            if str(node.get("email", "")).strip().lower() == key:
                return node
        return None

    def list_open_project_issues(self, project_id: str, limit: int = 250) -> list[dict[str, Any]]:
        query = """
        query ProjectIssues($id: String!, $first: Int!) {
          project(id: $id) {
            issues(first: $first) {
              nodes {
                id
                identifier
                title
                url
                description
                state { id name type }
                assignee { id name email }
              }
            }
          }
        }
        """
        data = self._post(query, {"id": project_id, "first": limit})
        project = data.get("project") if isinstance(data.get("project"), dict) else None
        if not project:
            return []
        issues = project.get("issues") if isinstance(project.get("issues"), dict) else {}
        nodes = issues.get("nodes") if isinstance(issues.get("nodes"), list) else []

        open_nodes: list[dict[str, Any]] = []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            state = node.get("state") if isinstance(node.get("state"), dict) else {}
            stype = str(state.get("type", "")).lower()
            if stype in {"completed", "canceled"}:
                continue
            open_nodes.append(node)
        return open_nodes

    def create_issue(self, payload: dict[str, Any]) -> dict[str, Any]:
        query = """
        mutation IssueCreate($input: IssueCreateInput!) {
          issueCreate(input: $input) {
            success
            issue {
              id
              identifier
              title
              url
              assignee { id name email }
              project { id name }
            }
          }
        }
        """
        data = self._post(query, {"input": payload})
        block = data.get("issueCreate") if isinstance(data.get("issueCreate"), dict) else None
        if not block or not block.get("success"):
            raise ToolError("linear_unavailable", "Issue create failed", stage="create")
        issue = block.get("issue") if isinstance(block.get("issue"), dict) else None
        if not issue:
            raise ToolError("linear_unavailable", "Issue create returned empty issue", stage="create")
        return issue

    def update_issue(self, issue_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        query = """
        mutation IssueUpdate($id: String!, $input: IssueUpdateInput!) {
          issueUpdate(id: $id, input: $input) {
            success
            issue {
              id
              identifier
              title
              url
              assignee { id name email }
              project { id name }
            }
          }
        }
        """
        data = self._post(query, {"id": issue_id, "input": payload})
        block = data.get("issueUpdate") if isinstance(data.get("issueUpdate"), dict) else None
        if not block or not block.get("success"):
            raise ToolError("linear_unavailable", "Issue update failed", stage="update")
        issue = block.get("issue") if isinstance(block.get("issue"), dict) else None
        if not issue:
            raise ToolError("linear_unavailable", "Issue update returned empty issue", stage="update")
        return issue


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def primary_symptom_phrase(reproduction_context: str, impact: str) -> str:
    source = reproduction_context.strip() or impact.strip()
    if not source:
        return "none"
    first = re.split(r"[\n\.!?]", source)[0]
    return normalize_text(first)[:120]


def compute_dedup_key(inp: EscalationInput) -> str:
    if inp.dedup_key:
        return inp.dedup_key.strip()
    material = "|".join(
        [
            normalize_text(inp.blocker_kind),
            normalize_text(inp.title),
            normalize_text(inp.related_task_identifier or "none"),
            primary_symptom_phrase(inp.reproduction_context, inp.impact),
        ]
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f"blk-{digest[:20]}"


def dedup_marker(dedup_key: str) -> str:
    return f"<!-- {TOOL}:dedup_key={dedup_key} -->"


def severity_to_priority(severity: str) -> int:
    # Linear: 1 urgent, 2 high, 3 normal, 4 low
    if severity == "high":
        return 2
    if severity == "medium":
        return 3
    return 4


def build_issue_title(inp: EscalationInput) -> str:
    related = f" [{inp.related_task_identifier}]" if inp.related_task_identifier else ""
    return f"[{inp.blocker_kind}] {inp.title}{related}".strip()


def build_issue_body(inp: EscalationInput, dedup_key: str) -> str:
    mitigation_lines = "\n".join(f"- {item}" for item in inp.attempted_mitigation)
    related = inp.related_task_identifier or "none"
    return (
        f"## Problem Statement\n"
        f"{inp.title}\n\n"
        f"## Reproduction Context\n"
        f"{inp.reproduction_context}\n\n"
        f"## Impact Scope\n"
        f"{inp.impact}\n\n"
        f"## Attempted Mitigations\n"
        f"{mitigation_lines}\n\n"
        f"## Requested User Action\n"
        f"{inp.requested_user_action}\n\n"
        f"## Metadata\n"
        f"- blocker_kind: `{inp.blocker_kind}`\n"
        f"- severity: `{inp.severity}`\n"
        f"- related_task_identifier: `{related}`\n"
        f"- dedup_key: `{dedup_key}`\n"
        f"- status_timestamp_utc: `{utc_now_iso()}`\n\n"
        f"{dedup_marker(dedup_key)}"
    )


def find_matching_issue(issues: list[dict[str, Any]], dedup_key: str) -> dict[str, Any] | None:
    marker = dedup_marker(dedup_key)
    for issue in issues:
        desc = str(issue.get("description") or "")
        if marker in desc:
            return issue

    for issue in issues:
        desc = str(issue.get("description") or "")
        if dedup_key in desc:
            return issue
    return None


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=False))
        fh.write("\n")


def validate_input(inp: EscalationInput) -> None:
    if inp.blocker_kind not in BLOCKER_KINDS:
        raise ToolError("input_error", f"invalid blocker_kind '{inp.blocker_kind}'", stage="input")
    if inp.severity not in SEVERITIES:
        raise ToolError("input_error", f"invalid severity '{inp.severity}'", stage="input")
    if not inp.title.strip():
        raise ToolError("input_error", "title is required", stage="input")
    if not inp.reproduction_context.strip():
        raise ToolError("input_error", "reproduction_context is required", stage="input")
    if not inp.impact.strip():
        raise ToolError("input_error", "impact is required", stage="input")
    if not inp.requested_user_action.strip():
        raise ToolError("input_error", "requested_user_action is required", stage="input")
    if not inp.attempted_mitigation:
        raise ToolError("input_error", "attempted_mitigation cannot be empty", stage="input")


def parse_input(args: argparse.Namespace) -> EscalationInput:
    payload: dict[str, Any] = {}
    if args.input_json:
        payload = load_json(args.input_json)

    def pstr(key: str, default: Any = None, required: bool = False) -> str | None:
        value = payload.get(key, default)
        if value is None:
            if required:
                raise ToolError("input_error", f"{key} is required", stage="input")
            return None
        if not isinstance(value, str):
            raise ToolError("input_error", f"{key} must be a string", stage="input")
        val = value.strip()
        if required and not val:
            raise ToolError("input_error", f"{key} is required", stage="input")
        return val or None

    mitigation = payload.get("attempted_mitigation")
    if not isinstance(mitigation, list):
        raise ToolError("input_error", "attempted_mitigation must be a list of strings", stage="input")
    attempts = []
    for item in mitigation:
        if not isinstance(item, str) or not item.strip():
            raise ToolError("input_error", "attempted_mitigation must be a list of non-empty strings", stage="input")
        attempts.append(item.strip())

    repo_root = pstr("repo_root", default=args.repo_root or ".", required=True)
    assert repo_root is not None

    project_name = pstr("project_name", default=DEFAULT_PROJECT_NAME, required=True)
    assignee = pstr("assignee", default=DEFAULT_ASSIGNEE, required=True)

    log_path_raw = pstr("local_log_path", default=str(DEFAULT_LOG_PATH), required=True)

    inp = EscalationInput(
        blocker_kind=pstr("blocker_kind", required=True) or "",
        title=pstr("title", required=True) or "",
        reproduction_context=pstr("reproduction_context", required=True) or "",
        impact=pstr("impact", required=True) or "",
        attempted_mitigation=attempts,
        requested_user_action=pstr("requested_user_action", required=True) or "",
        related_task_identifier=pstr("related_task_identifier", default=None, required=False),
        severity=pstr("severity", required=True) or "",
        project_name=project_name or DEFAULT_PROJECT_NAME,
        assignee=assignee or DEFAULT_ASSIGNEE,
        dedup_key=pstr("dedup_key", default=None, required=False),
        dry_run=bool(payload.get("dry_run", False) or args.dry_run),
        repo_root=Path(repo_root).expanduser().resolve(),
        linear_endpoint=pstr("linear_endpoint", default=DEFAULT_LINEAR_ENDPOINT, required=True) or DEFAULT_LINEAR_ENDPOINT,
        linear_api_key=pstr("linear_api_key", default=args.linear_api_key, required=False) or args.linear_api_key,
        local_log_path=(Path(log_path_raw).expanduser() if Path(log_path_raw).is_absolute() else (Path(repo_root).expanduser().resolve() / log_path_raw)).resolve(),
    )

    validate_input(inp)
    return inp


def load_json(path: str) -> dict[str, Any]:
    if path == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ToolError("input_error", "input JSON must be an object", stage="input")
    return data


def run_escalation(inp: EscalationInput, gateway: LinearGateway | None = None) -> dict[str, Any]:
    dedup = compute_dedup_key(inp)
    warnings: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    output = {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "ok": False,
        "action": "create",
        "issue_identifier": None,
        "issue_url": None,
        "project": inp.project_name,
        "assignee": inp.assignee,
        "dedup_key": dedup,
        "linear_sync_logged": False,
        "callout_text": None,
        "warnings": warnings,
        "errors": errors,
    }

    event = {
        "timestamp": utc_now_iso(),
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "blocker_kind": inp.blocker_kind,
        "severity": inp.severity,
        "related_task_identifier": inp.related_task_identifier,
        "dedup_key": dedup,
        "project": inp.project_name,
        "assignee": inp.assignee,
        "dry_run": inp.dry_run,
        "status": "pending",
        "action": None,
        "issue_identifier": None,
        "issue_url": None,
    }

    if inp.dry_run:
        output["ok"] = True
        output["warnings"].append(
            {
                "code": "dry_run",
                "message": "Dry-run mode enabled; no Linear writes performed",
            }
        )
        output["callout_text"] = f"Please review blocker <TBD> in {inp.project_name}: <url>"
        event["status"] = "dry_run"
        event["action"] = "create_or_update"
        try:
            append_jsonl(inp.local_log_path, event)
            output["linear_sync_logged"] = True
        except OSError as exc:
            output["errors"].append(
                {
                    "code": "local_log_write_failed",
                    "message": f"Failed to append local escalation log: {exc}",
                    "stage": "local_log",
                    "path": str(inp.local_log_path),
                }
            )
        return output

    if gateway is None:
        api_key = inp.linear_api_key
        if not api_key:
            api_key = __import__("os").environ.get("LINEAR_API_KEY")
        if not api_key:
            raise ToolError("auth_error", "LINEAR_API_KEY required for non-dry-run escalation", stage="auth")
        gateway = GraphqlLinearGateway(api_key=api_key, endpoint=inp.linear_endpoint)

    try:
        project = gateway.resolve_project(inp.project_name)
    except ToolError as exc:
        output["errors"].append({"code": exc.code, "message": exc.message, "stage": exc.stage})
        event["status"] = "pending_retry"
        event["action"] = "none"
        event["retry_instructions"] = "Verify Linear connectivity and project setup, then replay escalation with same dedup_key."
        try:
            append_jsonl(inp.local_log_path, event)
            output["linear_sync_logged"] = True
        except OSError as write_exc:
            output["errors"].append(
                {
                    "code": "local_log_write_failed",
                    "message": f"Failed to append local escalation log: {write_exc}",
                    "stage": "local_log",
                    "path": str(inp.local_log_path),
                }
            )
        return output

    user: dict[str, Any] | None
    try:
        user = gateway.resolve_user(inp.assignee)
    except ToolError as exc:
        warnings.append(
            {
                "code": "assignment_resolution_failed",
                "message": f"Assignee '{inp.assignee}' lookup failed ({exc.code}); proceeding without assignment",
                "stage": exc.stage,
            }
        )
        user = None
    assignee_id = None
    if user and isinstance(user, dict):
        assignee_id = user.get("id")
    else:
        warnings.append(
            {
                "code": "assignment_unresolved",
                "message": f"Assignee '{inp.assignee}' could not be resolved; proceeding without assignment",
            }
        )

    try:
        open_issues = gateway.list_open_project_issues(project["id"])
    except ToolError as exc:
        output["errors"].append({"code": exc.code, "message": exc.message, "stage": exc.stage})
        event["status"] = "pending_retry"
        event["action"] = "none"
        event["retry_instructions"] = "Linear unavailable while listing open blockers; retry with same dedup_key."
        try:
            append_jsonl(inp.local_log_path, event)
            output["linear_sync_logged"] = True
        except OSError as write_exc:
            output["errors"].append(
                {
                    "code": "local_log_write_failed",
                    "message": f"Failed to append local escalation log: {write_exc}",
                    "stage": "local_log",
                    "path": str(inp.local_log_path),
                }
            )
        return output

    existing = find_matching_issue(open_issues, dedup)

    issue_body = build_issue_body(inp, dedup)
    issue_title = build_issue_title(inp)

    action = "update" if existing else "create"
    output["action"] = action

    try:
        if existing:
            update_payload: dict[str, Any] = {
                "title": issue_title,
                "description": issue_body,
                "priority": severity_to_priority(inp.severity),
                "projectId": project["id"],
            }
            if assignee_id:
                update_payload["assigneeId"] = assignee_id
            issue = gateway.update_issue(existing["id"], update_payload)
        else:
            create_payload: dict[str, Any] = {
                "title": issue_title,
                "description": issue_body,
                "projectId": project["id"],
                "teamId": project.get("team_id"),
                "priority": severity_to_priority(inp.severity),
            }
            if assignee_id:
                create_payload["assigneeId"] = assignee_id
            issue = gateway.create_issue(create_payload)
    except ToolError as exc:
        output["errors"].append({"code": exc.code, "message": exc.message, "stage": exc.stage})
        event["status"] = "pending_retry"
        event["action"] = action
        event["retry_instructions"] = "Linear write failed; replay escalation with same dedup_key to avoid duplicates."
        try:
            append_jsonl(inp.local_log_path, event)
            output["linear_sync_logged"] = True
        except OSError as write_exc:
            output["errors"].append(
                {
                    "code": "local_log_write_failed",
                    "message": f"Failed to append local escalation log: {write_exc}",
                    "stage": "local_log",
                    "path": str(inp.local_log_path),
                }
            )
        return output

    issue_identifier = issue.get("identifier")
    issue_url = issue.get("url")

    output["issue_identifier"] = issue_identifier
    output["issue_url"] = issue_url
    output["callout_text"] = f"Please review blocker {issue_identifier} in {inp.project_name}: {issue_url}"

    event["status"] = "synced"
    event["action"] = action
    event["issue_identifier"] = issue_identifier
    event["issue_url"] = issue_url

    try:
        append_jsonl(inp.local_log_path, event)
        output["linear_sync_logged"] = True
    except OSError as exc:
        output["errors"].append(
            {
                "code": "local_log_write_failed",
                "message": f"Failed to append local escalation log: {exc}",
                "stage": "local_log",
                "path": str(inp.local_log_path),
            }
        )

    output["ok"] = len(output["errors"]) == 0
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Escalate unresolved blockers to Linear project Agents")
    parser.add_argument("--input-json", help="JSON input path or '-' for stdin")
    parser.add_argument("--repo-root", help="Repo root path (fallback when not passed in JSON)")
    parser.add_argument("--linear-api-key")
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
        inp = parse_input(args)
        out = run_escalation(inp)
        print_json(out, args.json_pretty)
        return 0 if out.get("ok") else 1
    except ToolError as exc:
        out = {
            "schema_version": SCHEMA_VERSION,
            "tool": TOOL,
            "tool_version": TOOL_VERSION,
            "ok": False,
            "action": "create",
            "issue_identifier": None,
            "issue_url": None,
            "project": None,
            "assignee": None,
            "dedup_key": None,
            "linear_sync_logged": False,
            "callout_text": None,
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
