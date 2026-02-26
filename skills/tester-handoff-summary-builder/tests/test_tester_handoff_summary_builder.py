import importlib.util
import json
import sys
import tempfile
from pathlib import Path
import unittest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "tester_handoff_summary_builder.py"
SPEC = importlib.util.spec_from_file_location("tester_handoff_summary_builder", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def make_cfg(root: Path, **overrides):
    return MODULE.BuilderInput(
        task_identifier=overrides.get("task_identifier", "MYO-168"),
        resolved_branch=overrides.get("resolved_branch", "codex/dev-2/myo-168"),
        start_from_branch=overrides.get("start_from_branch", "main"),
        start_from_commit=overrides.get("start_from_commit", "abc123"),
        head_commit=overrides.get("head_commit", "def456"),
        preflight_json_path=overrides.get("preflight_json_path"),
        test_results_json_path=overrides.get("test_results_json_path"),
        decision_override=overrides.get("decision_override"),
        findings=overrides.get("findings", []),
        blockers=overrides.get("blockers", []),
        dry_run=overrides.get("dry_run", False),
        include_metadata=overrides.get("include_metadata", False),
    )


class TesterHandoffSummaryBuilderTests(unittest.TestCase):
    def test_payload_completeness_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = MODULE.build_summary(make_cfg(root, dry_run=True))
            required = {
                "task_identifier",
                "branch",
                "start_from_branch",
                "start_from_commit",
                "head_commit",
                "checks",
                "decision",
                "findings",
                "blockers",
            }
            self.assertTrue(required.issubset(set(out.keys())))

    def test_decision_validation_override_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = MODULE.build_summary(make_cfg(root, dry_run=True, blockers=["manual blocker"], decision_override="ready_for_review"))
            self.assertEqual(out["decision"], "blocked")

            out2 = MODULE.build_summary(make_cfg(root, dry_run=True, decision_override="needs_dev_fix"))
            self.assertEqual(out2["decision"], "needs_dev_fix")

    def test_integration_compose_from_preflight_and_test_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            preflight = root / "preflight.json"
            test_results = root / "test-results.json"

            preflight.write_text(
                json.dumps(
                    {
                        "ok": True,
                        "tool": "tester-preflight-resolver",
                        "next_step": "run_tests",
                        "errors": [],
                    }
                ),
                encoding="utf-8",
            )
            test_results.write_text(
                json.dumps(
                    {
                        "ok": True,
                        "tool": "tester-targeted-pytest-runner",
                        "decision_hint": "needs_dev_fix",
                        "runs": [
                            {"name": "users_auth", "result": "pass", "summary": "passed=1 failed=0 skipped=0 errors=0", "signature": None},
                            {"name": "users_ordering", "result": "fail", "summary": "passed=0 failed=1 skipped=0 errors=0", "signature": "test_failure"},
                        ],
                        "errors": [],
                    }
                ),
                encoding="utf-8",
            )

            cfg = make_cfg(root, preflight_json_path=preflight, test_results_json_path=test_results)
            out = MODULE.build_summary(cfg)
            self.assertEqual(out["decision"], "needs_dev_fix")
            self.assertEqual(out["checks"][0], {"name": "preflight", "result": "pass"})
            self.assertEqual(out["checks"][1]["name"], "users_auth")
            self.assertEqual(out["checks"][2]["name"], "users_ordering")
            self.assertTrue(any("users_ordering" in finding for finding in out["findings"]))

    def test_contract_snapshot_stable_order_and_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = MODULE.build_summary(make_cfg(root, dry_run=True))
            expected_order = [
                "task_identifier",
                "branch",
                "start_from_branch",
                "start_from_commit",
                "head_commit",
                "checks",
                "decision",
                "findings",
                "blockers",
            ]
            self.assertEqual(list(out.keys()), expected_order)

    def test_synthesized_test_runner_blocked_check_when_only_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            preflight = root / "preflight.json"
            test_results = root / "test-results.json"
            preflight.write_text(json.dumps({"ok": True, "next_step": "run_tests", "errors": []}), encoding="utf-8")
            test_results.write_text(
                json.dumps(
                    {
                        "ok": False,
                        "decision_hint": "blocked",
                        "runs": [],
                        "errors": [{"code": "db_unreachable", "message": "db down"}],
                    }
                ),
                encoding="utf-8",
            )
            out = MODULE.build_summary(make_cfg(root, preflight_json_path=preflight, test_results_json_path=test_results))
            self.assertTrue(any(c["name"] == "test_runner" and c["result"] == "blocked" for c in out["checks"]))

    def test_include_metadata_envelope(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = MODULE.build_summary(make_cfg(root, dry_run=True, include_metadata=True))
            self.assertEqual(out["tool"], "tester-handoff-summary-builder")
            self.assertEqual(out["schema_version"], "1.0")


if __name__ == "__main__":
    unittest.main()
