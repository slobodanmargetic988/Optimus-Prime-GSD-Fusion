import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "linear_handoff_sync.py"
SPEC = importlib.util.spec_from_file_location("linear_handoff_sync", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FakeGateway:
    def __init__(self, *, comment_fail: bool = False):
        self.comment_fail = comment_fail
        self.calls = []

    def resolve_issue(self, issue_identifier: str):
        self.calls.append(("resolve_issue", issue_identifier))
        return {
            "id": "issue-1",
            "identifier": issue_identifier,
            "state_id": "state-old",
            "state_name": "Backlog",
            "team_states": [
                {"id": "state-backlog", "name": "Backlog"},
                {"id": "state-testing", "name": "Agent testing"},
                {"id": "state-done", "name": "Done"},
            ],
        }

    def update_issue_status(self, issue_id: str, state_id: str):
        self.calls.append(("update_issue_status", issue_id, state_id))
        return {"id": issue_id, "state_id": state_id, "state_name": "Agent testing"}

    def list_issue_comments(self, issue_id: str, limit: int = 50):
        self.calls.append(("list_issue_comments", issue_id, limit))
        return []

    def create_comment(self, issue_id: str, body: str):
        self.calls.append(("create_comment", issue_id))
        if self.comment_fail:
            raise MODULE.ToolError("comment_create_failed", "simulated comment failure", stage="create_comment")
        return {"id": "comment-1", "body": body}


def make_workflow_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "- `agent_working_status`: `Agent working`",
                "- `agent_work_done_status`: `Agent work DONE`",
                "- `agent_testing_status`: `Agent testing`",
                "- `agent_test_done_status`: `Agent test DONE`",
                "- `agent_review_status`: `Agent review`",
                "- `agent_review_done_status`: `Agent review DONE`",
                "- `human_review_status`: `Human Review`",
            ]
        ),
        encoding="utf-8",
    )


def base_summary() -> dict:
    return {
        "task_identifier": "MYO-155",
        "branch": "codex/dev-1/MYO-155",
        "head_commit": "abc123",
        "decision": "ready_for_review",
        "checks": [{"name": "unit", "result": "pass", "details": None}],
        "blockers": [],
    }


class LinearHandoffSyncTests(unittest.TestCase):
    def make_config(self, root: Path, **overrides):
        workflow = root / "agents" / "_shared" / "LINEAR_WORKFLOW.md"
        make_workflow_file(workflow)
        log_path = root / "reports" / "optimus-prime" / "LINEAR_SYNC_LOG.jsonl"

        return MODULE.SyncInput(
            issue_identifier=str(overrides.get("issue_identifier", "MYO-155")),
            target_phase=str(overrides.get("target_phase", "agent_testing")),
            summary_payload=overrides.get("summary_payload", base_summary()),
            comment_template=overrides.get("comment_template", None),
            dry_run=bool(overrides.get("dry_run", False)),
            repo_root=root,
            linear_workflow_path=Path(overrides.get("linear_workflow_path", workflow)),
            linear_sync_log_path=Path(overrides.get("linear_sync_log_path", log_path)),
            linear_endpoint=str(overrides.get("linear_endpoint", MODULE.DEFAULT_LINEAR_ENDPOINT)),
            linear_api_key=overrides.get("linear_api_key", "fake"),
            status_override_name=overrides.get("status_override_name", None),
        )

    def test_mapping_resolution_from_workflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wf = root / "agents" / "_shared" / "LINEAR_WORKFLOW.md"
            make_workflow_file(wf)
            statuses = MODULE.parse_workflow_statuses(wf)
            mapped, override = MODULE.resolve_status_name("agent_testing", statuses, None)
            self.assertEqual(mapped, "Agent testing")
            self.assertFalse(override)

    def test_fingerprint_and_local_dedup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)

            _, fingerprint = MODULE.compute_fingerprint(
                config.issue_identifier,
                config.target_phase,
                config.summary_payload["head_commit"],
                config.summary_payload["decision"],
            )

            log = config.linear_sync_log_path
            log.parent.mkdir(parents=True, exist_ok=True)
            with log.open("w", encoding="utf-8") as fh:
                fh.write(
                    json.dumps(
                        {
                            "issue_identifier": config.issue_identifier,
                            "fingerprint": fingerprint,
                            "comment_created": True,
                        }
                    )
                    + "\n"
                )

            dedup, parse_warnings, warnings = MODULE.read_log_for_dedup(log, config.issue_identifier, fingerprint)
            self.assertTrue(dedup)
            self.assertEqual(parse_warnings, 0)
            self.assertEqual(warnings, [])

    def test_mocked_linear_full_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)
            gateway = FakeGateway(comment_fail=False)

            result = MODULE.run_sync(config, gateway=gateway)
            out = result.to_dict()

            self.assertTrue(out["ok"])
            self.assertTrue(out["status_applied"])
            self.assertTrue(out["comment_created"])
            self.assertTrue(out["log_written"])
            self.assertFalse(out["partial_success"])
            self.assertFalse(out["dedup_hit"])
            self.assertEqual(out["mapped_status_name"], "Agent testing")
            self.assertIn("fingerprint", out)

            log_lines = config.linear_sync_log_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(log_lines), 1)
            logged = json.loads(log_lines[0])
            self.assertEqual(logged["issue_identifier"], "MYO-155")
            self.assertTrue(logged["comment_created"])

    def test_mocked_linear_partial_status_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)
            gateway = FakeGateway(comment_fail=True)

            result = MODULE.run_sync(config, gateway=gateway)
            out = result.to_dict()

            self.assertFalse(out["ok"])
            self.assertTrue(out["status_applied"])
            self.assertFalse(out["comment_created"])
            self.assertTrue(out["partial_success"])
            self.assertTrue(out["log_written"])
            self.assertIsNotNone(out["retry_token"])

    def test_failure_before_writes_unknown_phase(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root, target_phase="unknown_phase")
            gateway = FakeGateway(comment_fail=False)

            with self.assertRaises(MODULE.ToolError) as ctx:
                MODULE.run_sync(config, gateway=gateway)
            self.assertEqual(ctx.exception.code, "config_error")
            self.assertFalse(config.linear_sync_log_path.exists())

    def test_dry_run_returns_plan_and_no_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root, dry_run=True)

            result = MODULE.run_sync(config, gateway=None)
            out = result.to_dict()

            self.assertTrue(out["ok"])
            self.assertFalse(out["status_applied"])
            self.assertFalse(out["comment_created"])
            self.assertFalse(out["log_written"])
            self.assertGreaterEqual(len(out["planned_actions"]), 5)
            self.assertFalse(config.linear_sync_log_path.exists())

    def test_resolve_workflow_path_uses_sibling_agents_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            myboard_root = base / "MyBoard"
            myboard_root.mkdir(parents=True, exist_ok=True)
            sibling_workflow = base / "Agents" / "agents" / "_shared" / "LINEAR_WORKFLOW.md"
            make_workflow_file(sibling_workflow)

            resolved = MODULE.resolve_linear_workflow_path(myboard_root, None)
            self.assertEqual(resolved, sibling_workflow.resolve())

    def test_resolve_workflow_path_prefers_env_override_when_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            custom_workflow = root / "custom" / "LINEAR_WORKFLOW.md"
            make_workflow_file(custom_workflow)

            with patch.dict(os.environ, {"LINEAR_WORKFLOW_PATH": "custom/LINEAR_WORKFLOW.md"}, clear=False):
                resolved = MODULE.resolve_linear_workflow_path(root, None)
                self.assertEqual(resolved, custom_workflow.resolve())


if __name__ == "__main__":
    unittest.main()
