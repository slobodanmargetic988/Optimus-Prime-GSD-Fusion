import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "dispatch_worker_packet.py"
SPEC = importlib.util.spec_from_file_location("dispatch_worker_packet", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FakeDispatcher:
    def __init__(self, *, should_fail: bool = False):
        self.should_fail = should_fail
        self.calls = []

    def dispatch(self, cfg, packet_path):
        self.calls.append((cfg.slot, cfg.task_identifier, str(packet_path)))
        if self.should_fail:
            raise MODULE.ToolError("dispatch_failed", "simulated dispatch failure", stage="dispatch")
        return {
            "dispatch_started": True,
            "pid": 4242,
            "dispatch_log": "/tmp/dispatch.log",
            "raw": {"status": "started"},
        }


def make_cfg(root: Path, **overrides):
    return MODULE.DispatchInput(
        slot=overrides.get("slot", "dev-1"),
        role=overrides.get("role", "developer"),
        task_identifier=overrides.get("task_identifier", "MYO-156"),
        repo_root=root,
        worktree_root=Path(overrides.get("worktree_root", root)),
        branch_name=overrides.get("branch_name", "codex/dev-1/MYO-156"),
        start_from_branch=overrides.get("start_from_branch", "main"),
        start_from_commit=overrides.get("start_from_commit", "abc1234"),
        acceptance_criteria=overrides.get("acceptance_criteria", ["tool works", "tests pass"]),
        packet_version=overrides.get("packet_version", 1),
        codex_profile_alias=overrides.get("codex_profile_alias", "codex"),
        mcp_mode=overrides.get("mcp_mode", "disable-all"),
        mcp_allowlist=overrides.get("mcp_allowlist", []),
        sandbox_mode=overrides.get("sandbox_mode", "danger-full-access"),
        sandbox_add_dirs=overrides.get("sandbox_add_dirs", []),
        runtime_strategy=overrides.get("runtime_strategy"),
        runtime_base_url=overrides.get("runtime_base_url"),
        tester_must_not_start_runtime=overrides.get("tester_must_not_start_runtime"),
        test_train_mode=overrides.get("test_train_mode", "off"),
        wave_id=overrides.get("wave_id"),
        deployed_test_commit=overrides.get("deployed_test_commit"),
        test_lane_account=overrides.get("test_lane_account"),
        dry_run=overrides.get("dry_run", False),
        cycle_note=overrides.get("cycle_note", None),
    )


class DispatchWorkerPacketTests(unittest.TestCase):
    def test_slot_role_validation(self):
        MODULE.validate_slot_role("dev-1", "developer")
        MODULE.validate_slot_role("test-1", "tester")
        MODULE.validate_slot_role("test-2", "flex-tester")
        MODULE.validate_slot_role("review-1", "reviewer")

        with self.assertRaises(MODULE.ToolError):
            MODULE.validate_slot_role("dev-1", "tester")
        with self.assertRaises(MODULE.ToolError):
            MODULE.validate_slot_role("review-1", "developer")

    def test_packet_render_contains_required_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(Path(tmp), role="tester", slot="test-1", branch_name="codex/test-1/MYO-156")
            content = MODULE.render_packet(cfg)
            self.assertIn("start_from_branch", content)
            self.assertIn("start_from_commit", content)
            self.assertIn("developer fallback suffix: -dev", content)
            self.assertIn("tester/flex-tester fallback suffix: -test", content)
            self.assertIn("intended_branch", content)
            self.assertIn("fallback_branch", content)
            self.assertIn("fallback_reason", content)

    def test_dry_run_returns_no_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = make_cfg(root, dry_run=True)
            out = MODULE.run_dispatch_worker_packet(cfg, dispatcher=FakeDispatcher())

            self.assertTrue(out["ok"])
            self.assertFalse(out["dispatch_started"])
            self.assertFalse(out["registry_updated"])
            self.assertFalse(out["handoff_logged"])
            self.assertTrue(any(w["code"] == "dry_run" for w in out["warnings"]))

            reports = root / "reports" / "optimus-prime"
            self.assertFalse((reports / "WORKER_REGISTRY.json").exists())
            self.assertFalse((reports / "HANDOFF_LOG.jsonl").exists())

    def test_success_flow_updates_registry_handoff_lineage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = make_cfg(root)
            out = MODULE.run_dispatch_worker_packet(cfg, dispatcher=FakeDispatcher())

            self.assertTrue(out["ok"])
            self.assertTrue(out["dispatch_started"])
            self.assertTrue(out["registry_updated"])
            self.assertTrue(out["handoff_logged"])
            self.assertEqual(out["pid"], 4242)
            self.assertTrue(Path(out["packet_path"]).exists())

            registry = json.loads((root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json").read_text(encoding="utf-8"))
            self.assertEqual(registry["workers"][0]["slot"], "dev-1")
            self.assertEqual(registry["workers"][0]["active_task"], "MYO-156")

            handoff_lines = (root / "reports" / "optimus-prime" / "HANDOFF_LOG.jsonl").read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(handoff_lines), 1)
            handoff = json.loads(handoff_lines[0])
            self.assertEqual(handoff["event"], "dispatch_attempt")
            self.assertEqual(handoff["task_identifier"], "MYO-156")

            lineage = json.loads((root / "reports" / "optimus-prime" / "BRANCH_LINEAGE.json").read_text(encoding="utf-8"))
            self.assertTrue(len(lineage["entries"]) >= 1)

            thread_history = (root / "reports" / "optimus-prime" / "THREAD_HISTORY.log").read_text(encoding="utf-8")
            self.assertIn("slot | worker type | thread-id", thread_history)
            self.assertIn("dev-1 | developer | unknown", thread_history)

    def test_dispatch_failure_keeps_registry_non_running(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = make_cfg(root)
            out = MODULE.run_dispatch_worker_packet(cfg, dispatcher=FakeDispatcher(should_fail=True))

            self.assertFalse(out["ok"])
            self.assertFalse(out["registry_updated"])
            self.assertFalse(out["handoff_logged"])
            error_codes = {e["code"] for e in out["errors"]}
            self.assertIn("dispatch_failed", error_codes)

            reports = root / "reports" / "optimus-prime"
            self.assertFalse((reports / "WORKER_REGISTRY.json").exists())
            self.assertFalse((reports / "HANDOFF_LOG.jsonl").exists())

    def test_registry_write_failure_after_dispatch_returns_critical_remediation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = make_cfg(root)

            reports = root / "reports" / "optimus-prime"
            reports.mkdir(parents=True, exist_ok=True)
            # Force registry write failure: path expected as file is a directory.
            (reports / "WORKER_REGISTRY.json").mkdir(parents=True, exist_ok=True)

            out = MODULE.run_dispatch_worker_packet(cfg, dispatcher=FakeDispatcher())
            self.assertFalse(out["ok"])
            self.assertTrue(out["dispatch_started"])
            self.assertFalse(out["registry_updated"])
            self.assertFalse(out["handoff_logged"])
            self.assertTrue(any(e["code"] == "registry_update_failed" for e in out["errors"]))
            critical = [e for e in out["errors"] if e["code"] == "registry_update_failed"][0]
            self.assertTrue(critical.get("critical"))
            self.assertIn("remediation", critical)
            self.assertEqual(critical["remediation"]["slot"], "dev-1")

    def test_validation_forbidden_worker_mcp(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(Path(tmp), mcp_mode="enable-only", mcp_allowlist=["linear"]) 
            with self.assertRaises(MODULE.ToolError) as ctx:
                MODULE.validate_policy(cfg)
            self.assertEqual(ctx.exception.code, "validation_error")

    def test_test_train_mode_requires_hosted_runtime_for_tester(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(
                Path(tmp),
                slot="test-1",
                role="tester",
                branch_name="codex/test-1/MYO-156",
                test_train_mode="final-stage",
                runtime_strategy="external_url",
                runtime_base_url="https://shared.example.test",
                tester_must_not_start_runtime=False,
            )
            with self.assertRaises(MODULE.ToolError) as ctx:
                MODULE.validate_policy(cfg)
            self.assertEqual(ctx.exception.code, "validation_error")

    def test_train_mode_dispatch_writes_wave_fields_to_handoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = make_cfg(
                root,
                slot="test-1",
                role="tester",
                branch_name="codex/test-1/MYO-156",
                test_train_mode="forced-shared-env",
                runtime_strategy="external_url",
                runtime_base_url="https://shared.example.test",
                tester_must_not_start_runtime=True,
                wave_id="wave-0007",
                deployed_test_commit="abc1234",
                test_lane_account="acct-02",
            )
            out = MODULE.run_dispatch_worker_packet(cfg, dispatcher=FakeDispatcher())
            self.assertTrue(out["ok"])

            handoff_line = (
                root / "reports" / "optimus-prime" / "HANDOFF_LOG.jsonl"
            ).read_text(encoding="utf-8").strip().splitlines()[-1]
            handoff = json.loads(handoff_line)
            self.assertEqual(handoff["wave_id"], "wave-0007")
            self.assertEqual(handoff["deployed_test_commit"], "abc1234")
            self.assertEqual(handoff["test_lane_account"], "acct-02")
            self.assertTrue(handoff["tester_must_not_start_runtime"])


if __name__ == "__main__":
    unittest.main()
