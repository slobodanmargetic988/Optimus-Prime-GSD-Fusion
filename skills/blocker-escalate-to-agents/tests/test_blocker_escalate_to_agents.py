import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "blocker_escalate_to_agents.py"
SPEC = importlib.util.spec_from_file_location("blocker_escalate_to_agents", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FakeGateway:
    def __init__(
        self,
        *,
        existing=None,
        fail_on_write=False,
        project_missing=False,
        user_missing=False,
        fail_on_user_lookup=False,
        fail_on_list=False,
    ):
        self.existing = existing or []
        self.fail_on_write = fail_on_write
        self.project_missing = project_missing
        self.user_missing = user_missing
        self.fail_on_user_lookup = fail_on_user_lookup
        self.fail_on_list = fail_on_list
        self.created = []
        self.updated = []

    def resolve_project(self, project_name: str):
        if self.project_missing:
            raise MODULE.ToolError("setup_error", "project missing", stage="resolve_project")
        return {"id": "project-1", "name": project_name, "team_id": "team-1"}

    def resolve_user(self, assignee: str):
        if self.fail_on_user_lookup:
            raise MODULE.ToolError("linear_unavailable", "cannot resolve user", stage="resolve_user")
        if self.user_missing:
            return None
        return {"id": "user-1", "name": "Me", "email": "me@example.com"}

    def list_open_project_issues(self, project_id: str, limit: int = 250):
        if self.fail_on_list:
            raise MODULE.ToolError("linear_unavailable", "cannot list issues", stage="remote")
        return self.existing

    def create_issue(self, payload: dict):
        if self.fail_on_write:
            raise MODULE.ToolError("linear_unavailable", "create failed", stage="create")
        self.created.append(payload)
        return {
            "id": "issue-1",
            "identifier": "MYO-900",
            "title": payload.get("title"),
            "url": "https://linear.app/myownmint/issue/MYO-900/test",
        }

    def update_issue(self, issue_id: str, payload: dict):
        if self.fail_on_write:
            raise MODULE.ToolError("linear_unavailable", "update failed", stage="update")
        self.updated.append((issue_id, payload))
        return {
            "id": issue_id,
            "identifier": "MYO-901",
            "title": payload.get("title"),
            "url": "https://linear.app/myownmint/issue/MYO-901/test",
        }


def base_input(root: Path, **overrides):
    return MODULE.EscalationInput(
        blocker_kind=overrides.get("blocker_kind", "workflow"),
        title=overrides.get("title", "Worker cannot proceed"),
        reproduction_context=overrides.get("reproduction_context", "Repro steps here."),
        impact=overrides.get("impact", "Task blocked."),
        attempted_mitigation=overrides.get("attempted_mitigation", ["retry", "inspect logs"]),
        requested_user_action=overrides.get("requested_user_action", "Please review and decide."),
        related_task_identifier=overrides.get("related_task_identifier", "MYO-158"),
        severity=overrides.get("severity", "high"),
        project_name=overrides.get("project_name", "Agents"),
        assignee=overrides.get("assignee", "me"),
        dedup_key=overrides.get("dedup_key", None),
        dry_run=overrides.get("dry_run", False),
        repo_root=root,
        linear_endpoint=MODULE.DEFAULT_LINEAR_ENDPOINT,
        linear_api_key="fake",
        local_log_path=overrides.get("local_log_path", root / "reports" / "optimus-prime" / "BLOCKER_ESCALATION_LOG.jsonl"),
    )


class BlockerEscalateTests(unittest.TestCase):
    def test_dedup_generation_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            inp = base_input(Path(tmp), dedup_key=None)
            key1 = MODULE.compute_dedup_key(inp)
            key2 = MODULE.compute_dedup_key(inp)
            self.assertEqual(key1, key2)
            self.assertTrue(key1.startswith("blk-"))

    def test_create_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inp = base_input(root)
            gateway = FakeGateway(existing=[])
            out = MODULE.run_escalation(inp, gateway=gateway)

            self.assertTrue(out["ok"])
            self.assertEqual(out["action"], "create")
            self.assertEqual(out["issue_identifier"], "MYO-900")
            self.assertIn("Please review blocker MYO-900", out["callout_text"])
            self.assertTrue(out["linear_sync_logged"])
            self.assertEqual(len(gateway.created), 1)
            self.assertEqual(len(gateway.updated), 0)

    def test_update_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inp = base_input(root)
            dedup = MODULE.compute_dedup_key(inp)
            existing = [
                {
                    "id": "issue-existing",
                    "identifier": "MYO-777",
                    "url": "https://linear.app/myownmint/issue/MYO-777/test",
                    "description": MODULE.dedup_marker(dedup),
                }
            ]
            gateway = FakeGateway(existing=existing)
            out = MODULE.run_escalation(inp, gateway=gateway)

            self.assertTrue(out["ok"])
            self.assertEqual(out["action"], "update")
            self.assertEqual(out["issue_identifier"], "MYO-901")
            self.assertEqual(len(gateway.created), 0)
            self.assertEqual(len(gateway.updated), 1)

    def test_assignment_failure_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inp = base_input(root)
            gateway = FakeGateway(existing=[], user_missing=True)
            out = MODULE.run_escalation(inp, gateway=gateway)

            self.assertTrue(out["ok"])
            warn_codes = {w["code"] for w in out["warnings"]}
            self.assertIn("assignment_unresolved", warn_codes)

    def test_assignment_lookup_error_degrades_to_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inp = base_input(root)
            gateway = FakeGateway(existing=[], fail_on_user_lookup=True)
            out = MODULE.run_escalation(inp, gateway=gateway)

            self.assertTrue(out["ok"])
            self.assertEqual(out["action"], "create")
            self.assertEqual(out["issue_identifier"], "MYO-900")
            warn_codes = {w["code"] for w in out["warnings"]}
            self.assertIn("assignment_resolution_failed", warn_codes)

    def test_linear_unavailable_path_logs_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inp = base_input(root)
            gateway = FakeGateway(existing=[], fail_on_write=True)
            out = MODULE.run_escalation(inp, gateway=gateway)

            self.assertFalse(out["ok"])
            self.assertTrue(out["linear_sync_logged"])
            err_codes = {e["code"] for e in out["errors"]}
            self.assertIn("linear_unavailable", err_codes)

            log_lines = inp.local_log_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(log_lines), 1)
            payload = json.loads(log_lines[0])
            self.assertEqual(payload["status"], "pending_retry")
            self.assertEqual(payload["action"], "create")

    def test_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inp = base_input(root, dry_run=True)
            out = MODULE.run_escalation(inp, gateway=FakeGateway())
            self.assertTrue(out["ok"])
            self.assertEqual(out["action"], "create")
            self.assertTrue(out["linear_sync_logged"])
            warn_codes = {w["code"] for w in out["warnings"]}
            self.assertIn("dry_run", warn_codes)


if __name__ == "__main__":
    unittest.main()
