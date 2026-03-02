import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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
        runtime_profile_id=overrides.get("runtime_profile_id"),
        runtime_id=overrides.get("runtime_id"),
        runtime_base_url=overrides.get("runtime_base_url"),
        runtime_lease_id=overrides.get("runtime_lease_id"),
        tester_must_not_start_runtime=overrides.get("tester_must_not_start_runtime"),
        test_train_mode=overrides.get("test_train_mode", "off"),
        wave_id=overrides.get("wave_id"),
        deployed_test_commit=overrides.get("deployed_test_commit"),
        test_lane_account=overrides.get("test_lane_account"),
        dispatch_mode=overrides.get("dispatch_mode", "exec"),
        resume_thread_id=overrides.get("resume_thread_id"),
        lane_id=overrides.get("lane_id"),
        test_source_branch=overrides.get("test_source_branch"),
        test_source_commit=overrides.get("test_source_commit"),
        op_build_mode=overrides.get("op_build_mode", False),
        plan_id=overrides.get("plan_id"),
        requirement_ids=overrides.get("requirement_ids", []),
        task_acceptance_refs=overrides.get("task_acceptance_refs", []),
        dev_ready_evidence_ref=overrides.get("dev_ready_evidence_ref"),
        dry_run=overrides.get("dry_run", False),
        cycle_note=overrides.get("cycle_note", None),
    )


def write_runtime_health(root: Path, *, gate_state: str = "healthy", both_sources_pass: bool = True) -> None:
    path = root / "reports" / "optimus-prime" / "runtime" / "RUNTIME_HEALTH.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "updated_at": MODULE.utc_now_iso(),
                "test_train_mode": "final-stage",
                "gate_state": gate_state,
                "consecutive_passes": 2 if gate_state == "healthy" else 0,
                "required_passes": 2,
                "pipeline_checks": [],
                "profile_checks": [],
                "both_sources_pass": both_sources_pass,
                "last_failure_fingerprint": None if gate_state == "healthy" else "pipeline|check|failed",
                "next_heal_allowed_at": None,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
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
            self.assertIn("Completion Artifact Contract", content)
            self.assertIn("summary.result: pass|fail|blocked", content)

    def test_packet_render_includes_test_source_sync_section_for_tester(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(
                Path(tmp),
                role="tester",
                slot="test-1",
                branch_name="codex/test-1/MYO-156",
                start_from_branch="codex/dev-1/MYO-156",
                test_source_branch="codex/dev-1/MYO-156",
                test_source_commit="a" * 40,
            )
            content = MODULE.render_packet(cfg)
            self.assertIn("## Test Stage Source Sync", content)
            self.assertIn("merge source branch before running tests", content)

    def test_tester_test_source_branch_must_align_start_from_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(MODULE.ToolError) as ctx:
                MODULE.validate_policy(
                    make_cfg(
                        Path(tmp),
                        role="tester",
                        slot="test-1",
                        branch_name="codex/test-1/MYO-156",
                        start_from_branch="RAB-BASE",
                        test_source_branch="codex/dev-1/MYO-156",
                        test_source_commit="a" * 40,
                    )
                )
            self.assertEqual(ctx.exception.code, "validation_error")
            self.assertIn("test_source_branch", ctx.exception.message)

    def test_optional_bool_coercion_edge_cases(self):
        self.assertTrue(MODULE._optional_bool("ON"))
        self.assertTrue(MODULE._optional_bool(" yes "))
        self.assertFalse(MODULE._optional_bool("off"))
        self.assertFalse(MODULE._optional_bool("0"))
        self.assertIsNone(MODULE._optional_bool(None))
        with self.assertRaises(MODULE.ToolError):
            MODULE._optional_bool("maybe")

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

    def test_dry_run_op_build_mode_contract_parity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = make_cfg(
                root,
                dry_run=True,
                op_build_mode=True,
                plan_id="plan-risk-gate",
                requirement_ids=["REQ-001"],
                task_acceptance_refs=["AC-001"],
                dev_ready_evidence_ref="reports/optimus-prime/planning/evidence/TASK-001/TASK_EVIDENCE.json",
            )
            out = MODULE.run_dispatch_worker_packet(cfg, dispatcher=FakeDispatcher())
            self.assertTrue(out["ok"])
            self.assertEqual(out["status"], "skipped_dry_run")
            self.assertFalse(out["dispatch_started"])
            self.assertFalse(out["registry_updated"])
            self.assertFalse(out["handoff_logged"])
            self.assertTrue(any(item.get("code") == "dry_run" for item in out.get("warnings", [])))

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

    def test_resume_dispatch_preserves_existing_thread_id_when_dispatch_payload_omits_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = make_cfg(
                root,
                dispatch_mode="resume",
                resume_thread_id="019caf43-0c03-7de0-b5a4-424935c63c33",
            )

            class ResumeDispatcher:
                def dispatch(self, *_args, **_kwargs):
                    return {
                        "dispatch_started": True,
                        "pid": 4243,
                        "dispatch_log": "/tmp/dispatch.log",
                        "dispatch_mode_used": "resume",
                        "raw": {"status": "started"},
                    }

            out = MODULE.run_dispatch_worker_packet(cfg, dispatcher=ResumeDispatcher())
            self.assertTrue(out["ok"])
            self.assertEqual(out["dispatch_thread_id"], cfg.resume_thread_id)
            self.assertEqual(out["dispatch"]["dispatch_thread_id"], cfg.resume_thread_id)

            registry = json.loads((root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json").read_text(encoding="utf-8"))
            self.assertEqual(registry["workers"][0]["dispatch_thread_id"], cfg.resume_thread_id)

            handoff_line = (
                root / "reports" / "optimus-prime" / "HANDOFF_LOG.jsonl"
            ).read_text(encoding="utf-8").strip().splitlines()[-1]
            handoff = json.loads(handoff_line)
            self.assertEqual(handoff["dispatch_thread_id"], cfg.resume_thread_id)

            thread_history = (root / "reports" / "optimus-prime" / "THREAD_HISTORY.log").read_text(encoding="utf-8")
            self.assertIn(cfg.resume_thread_id, thread_history)

    def test_thread_dispatch_runner_resume_early_exit_uses_exec_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = make_cfg(
                root,
                dispatch_mode="resume",
                resume_thread_id="019caf43-0c03-7de0-b5a4-424935c63c33",
            )
            packet = root / "packet.md"
            packet.write_text("test", encoding="utf-8")
            log_path = root / "dispatch-resume.log"
            log_path.write_text("Error: stdin is not a terminal\n", encoding="utf-8")
            exec_log_path = root / "dispatch-exec.log"
            exec_log_path.write_text("", encoding="utf-8")

            calls: list[list[str]] = []

            def fake_run(cmd, **_kwargs):
                calls.append(list(cmd))
                if len(calls) == 1:
                    return subprocess.CompletedProcess(
                        cmd,
                        0,
                        stdout=json.dumps({"status": "started", "pid": 11111, "log_file": str(log_path)}),
                        stderr="",
                    )
                return subprocess.CompletedProcess(
                    cmd,
                    0,
                    stdout=json.dumps({"status": "started", "pid": 22222, "log_file": str(exec_log_path)}),
                    stderr="",
                )

            def fake_kill(pid, _sig):
                if pid == 11111:
                    raise OSError("dead")
                return None

            with mock.patch.object(MODULE.subprocess, "run", side_effect=fake_run), mock.patch.object(
                MODULE.os, "kill", side_effect=fake_kill
            ), mock.patch.object(MODULE.time, "sleep", return_value=None):
                out = MODULE.ThreadDispatchRunner(repo_root=root).dispatch(cfg, packet)

            self.assertEqual(out["dispatch_mode_used"], "exec")
            self.assertEqual(out["pid"], 22222)
            self.assertEqual(out["fallback_reason_code"], "dispatch_resume_notty_detected")
            warning_codes = {
                item.get("code")
                for item in out.get("warnings", [])
                if isinstance(item, dict)
            }
            self.assertIn("dispatch_resume_notty_detected", warning_codes)
            self.assertIn("dispatch_resume_failed_fallback_exec", warning_codes)
            self.assertEqual(len(calls), 2)

    def test_registry_update_supports_workers_dict_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = root / "reports" / "optimus-prime"
            reports.mkdir(parents=True, exist_ok=True)
            (reports / "WORKER_REGISTRY.json").write_text(
                json.dumps({"workers": {"dev-2": {"slot": "dev-2"}}}, indent=2) + "\n",
                encoding="utf-8",
            )
            cfg = make_cfg(root)
            out = MODULE.run_dispatch_worker_packet(cfg, dispatcher=FakeDispatcher())
            self.assertTrue(out["ok"])
            registry = json.loads((reports / "WORKER_REGISTRY.json").read_text(encoding="utf-8"))
            self.assertIn("dev-1", registry["workers"])
            self.assertEqual(registry["workers"]["dev-1"]["active_task"], "MYO-156")

    def test_registry_update_supports_invalid_workers_field_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = root / "reports" / "optimus-prime"
            reports.mkdir(parents=True, exist_ok=True)
            (reports / "WORKER_REGISTRY.json").write_text(
                json.dumps({"workers": "invalid-shape"}, indent=2) + "\n",
                encoding="utf-8",
            )
            cfg = make_cfg(root)
            out = MODULE.run_dispatch_worker_packet(cfg, dispatcher=FakeDispatcher())
            self.assertTrue(out["ok"])
            registry = json.loads((reports / "WORKER_REGISTRY.json").read_text(encoding="utf-8"))
            self.assertIsInstance(registry["workers"], list)
            self.assertEqual(registry["workers"][0]["slot"], "dev-1")

    def test_registry_update_supports_root_list_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = root / "reports" / "optimus-prime"
            reports.mkdir(parents=True, exist_ok=True)
            (reports / "WORKER_REGISTRY.json").write_text(
                json.dumps([{"slot": "dev-2"}], indent=2) + "\n",
                encoding="utf-8",
            )
            cfg = make_cfg(root)
            out = MODULE.run_dispatch_worker_packet(cfg, dispatcher=FakeDispatcher())
            self.assertTrue(out["ok"])
            registry = json.loads((reports / "WORKER_REGISTRY.json").read_text(encoding="utf-8"))
            self.assertIsInstance(registry, dict)
            self.assertIsInstance(registry["workers"], list)
            self.assertEqual(registry["workers"][0]["slot"], "dev-1")

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

    def test_handoff_log_failure_is_structured_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = make_cfg(root)
            reports = root / "reports" / "optimus-prime"
            reports.mkdir(parents=True, exist_ok=True)
            (reports / "HANDOFF_LOG.jsonl").mkdir(parents=True, exist_ok=True)
            out = MODULE.run_dispatch_worker_packet(cfg, dispatcher=FakeDispatcher())
            self.assertFalse(out["ok"])
            self.assertEqual(out["status"], "handoff_log_failed")
            self.assertTrue(any(item.get("code") == "handoff_log_failed" for item in out.get("errors", [])))
            self.assertEqual(out["state_updates"]["handoff_log"], "failed")

    def test_branch_lineage_write_failure_is_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = make_cfg(root)
            reports = root / "reports" / "optimus-prime"
            reports.mkdir(parents=True, exist_ok=True)
            (reports / "BRANCH_LINEAGE.json").mkdir(parents=True, exist_ok=True)
            out = MODULE.run_dispatch_worker_packet(cfg, dispatcher=FakeDispatcher())
            self.assertTrue(out["ok"])
            self.assertEqual(out["status"], "completed")
            self.assertEqual(out["state_updates"]["branch_lineage"], "failed_warning")
            self.assertTrue(any(item.get("code") == "branch_lineage_update_failed" for item in out.get("warnings", [])))

    def test_validation_forbidden_worker_mcp(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(Path(tmp), mcp_mode="enable-only", mcp_allowlist=["linear"]) 
            with self.assertRaises(MODULE.ToolError) as ctx:
                MODULE.validate_policy(cfg)
            self.assertEqual(ctx.exception.code, "validation_error")

    def test_validation_mcp_mode_combinations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(MODULE.ToolError) as ctx1:
                MODULE.validate_policy(make_cfg(root, mcp_mode="enable-only", mcp_allowlist=[]))
            self.assertEqual(ctx1.exception.code, "validation_error")
            with self.assertRaises(MODULE.ToolError) as ctx2:
                MODULE.validate_policy(make_cfg(root, mcp_mode="disable-all", mcp_allowlist=["figma"]))
            self.assertEqual(ctx2.exception.code, "validation_error")

    def test_branch_name_prefix_validation_by_slot_family(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(MODULE.ToolError):
                MODULE.validate_policy(make_cfg(root, slot="dev-1", role="developer", branch_name="codex/test-1/MYO-156"))
            with self.assertRaises(MODULE.ToolError):
                MODULE.validate_policy(make_cfg(root, slot="test-1", role="tester", branch_name="codex/dev-1/MYO-156"))

    def test_start_from_commit_invalid_sha_fails_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(MODULE.ToolError) as ctx:
                MODULE.validate_policy(make_cfg(root, start_from_commit="not-a-sha"))
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
                runtime_profile_id="default-web",
                runtime_id="rt-external-default-web-11111111",
                runtime_base_url="https://shared.example.test",
                runtime_lease_id="lease-123",
                tester_must_not_start_runtime=False,
            )
            with self.assertRaises(MODULE.ToolError) as ctx:
                MODULE.validate_policy(cfg)
            self.assertEqual(ctx.exception.code, "validation_error")

    def test_test_train_mode_requires_runtime_identity_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(
                Path(tmp),
                slot="test-1",
                role="tester",
                branch_name="codex/test-1/MYO-156",
                test_train_mode="final-stage",
                runtime_strategy="shared_runtime",
                runtime_base_url="https://shared.example.test",
                tester_must_not_start_runtime=True,
            )
            with self.assertRaises(MODULE.ToolError) as ctx:
                MODULE.validate_policy(cfg)
            self.assertEqual(ctx.exception.code, "validation_error")

    def test_train_mode_dispatch_writes_wave_fields_to_handoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_runtime_health(root, gate_state="healthy")
            cfg = make_cfg(
                root,
                slot="test-1",
                role="tester",
                branch_name="codex/test-1/MYO-156",
                test_train_mode="forced-shared-env",
                runtime_strategy="external_url",
                runtime_profile_id="default-web",
                runtime_id="rt-external-default-web-11111111",
                runtime_base_url="https://shared.example.test",
                runtime_lease_id="lease-xyz",
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
            self.assertEqual(handoff["runtime_profile_id"], "default-web")
            self.assertEqual(handoff["runtime_lease_id"], "lease-xyz")

    def test_test_train_mode_blocks_when_runtime_health_not_healthy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_runtime_health(root, gate_state="blocked", both_sources_pass=False)
            cfg = make_cfg(
                root,
                slot="test-1",
                role="tester",
                branch_name="codex/test-1/MYO-156",
                test_train_mode="final-stage",
                runtime_strategy="external_url",
                runtime_profile_id="default-web",
                runtime_id="rt-external-default-web-11111111",
                runtime_base_url="https://shared.example.test",
                runtime_lease_id="lease-xyz",
                tester_must_not_start_runtime=True,
            )
            with self.assertRaises(MODULE.ToolError) as ctx:
                MODULE.validate_policy(cfg)
            self.assertEqual(ctx.exception.code, "validation_error")
            self.assertIn("runtime health gate is not healthy", ctx.exception.message)

    def test_test_train_mode_runtime_health_invalid_json_returns_validation_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            health_path = root / "reports" / "optimus-prime" / "runtime" / "RUNTIME_HEALTH.json"
            health_path.parent.mkdir(parents=True, exist_ok=True)
            health_path.write_text("{ invalid-json", encoding="utf-8")
            cfg = make_cfg(
                root,
                slot="test-1",
                role="tester",
                branch_name="codex/test-1/MYO-156",
                test_train_mode="final-stage",
                runtime_strategy="external_url",
                runtime_profile_id="default-web",
                runtime_id="rt-external-default-web-11111111",
                runtime_base_url="https://shared.example.test",
                runtime_lease_id="lease-xyz",
                tester_must_not_start_runtime=True,
            )
            with self.assertRaises(MODULE.ToolError) as ctx:
                MODULE.validate_policy(cfg)
            self.assertEqual(ctx.exception.code, "validation_error")
            self.assertIn("invalid JSON", ctx.exception.message)

    def test_test_train_mode_runtime_health_invalid_utf8_returns_validation_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            health_path = root / "reports" / "optimus-prime" / "runtime" / "RUNTIME_HEALTH.json"
            health_path.parent.mkdir(parents=True, exist_ok=True)
            health_path.write_bytes(b"\xff\xfe\xfd")
            cfg = make_cfg(
                root,
                slot="test-1",
                role="tester",
                branch_name="codex/test-1/MYO-156",
                test_train_mode="final-stage",
                runtime_strategy="external_url",
                runtime_profile_id="default-web",
                runtime_id="rt-external-default-web-11111111",
                runtime_base_url="https://shared.example.test",
                runtime_lease_id="lease-xyz",
                tester_must_not_start_runtime=True,
            )
            with self.assertRaises(MODULE.ToolError) as ctx:
                MODULE.validate_policy(cfg)
            self.assertEqual(ctx.exception.code, "validation_error")
            self.assertIn("unreadable", ctx.exception.message)

    def test_dispatch_runtime_health_non_object_payload_validation_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            health_path = root / "reports" / "optimus-prime" / "runtime" / "RUNTIME_HEALTH.json"
            health_path.parent.mkdir(parents=True, exist_ok=True)
            health_path.write_text(json.dumps(["not-an-object"], indent=2) + "\n", encoding="utf-8")
            cfg = make_cfg(
                root,
                slot="test-1",
                role="tester",
                branch_name="codex/test-1/MYO-156",
                test_train_mode="final-stage",
                runtime_strategy="external_url",
                runtime_profile_id="default-web",
                runtime_id="rt-external-default-web-11111111",
                runtime_base_url="https://shared.example.test",
                runtime_lease_id="lease-xyz",
                tester_must_not_start_runtime=True,
            )
            with self.assertRaises(MODULE.ToolError) as ctx:
                MODULE.validate_policy(cfg)
            self.assertEqual(ctx.exception.code, "validation_error")
            self.assertIn("must be a JSON object", ctx.exception.message)

    def test_dispatch_runtime_health_missing_gate_fields_validation_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            health_path = root / "reports" / "optimus-prime" / "runtime" / "RUNTIME_HEALTH.json"
            health_path.parent.mkdir(parents=True, exist_ok=True)
            health_path.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "updated_at": MODULE.utc_now_iso(),
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            cfg = make_cfg(
                root,
                slot="test-1",
                role="tester",
                branch_name="codex/test-1/MYO-156",
                test_train_mode="final-stage",
                runtime_strategy="external_url",
                runtime_profile_id="default-web",
                runtime_id="rt-external-default-web-11111111",
                runtime_base_url="https://shared.example.test",
                runtime_lease_id="lease-xyz",
                tester_must_not_start_runtime=True,
            )
            with self.assertRaises(MODULE.ToolError) as ctx:
                MODULE.validate_policy(cfg)
            self.assertEqual(ctx.exception.code, "validation_error")
            self.assertIn("runtime health gate is not healthy", ctx.exception.message)

    def test_dispatch_hard_gate_contract_for_flex_tester_matches_tester(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_runtime_health(root, gate_state="healthy")
            cfg = make_cfg(
                root,
                slot="test-2",
                role="flex-tester",
                branch_name="codex/test-2/MYO-156",
                test_train_mode="final-stage",
                runtime_strategy="external_url",
                runtime_profile_id="default-web",
                runtime_id="rt-external-default-web-11111111",
                runtime_base_url="https://shared.example.test",
                tester_must_not_start_runtime=True,
            )
            with self.assertRaises(MODULE.ToolError) as ctx:
                MODULE.validate_policy(cfg)
            self.assertEqual(ctx.exception.code, "validation_error")
            self.assertIn("runtime_lease_id", ctx.exception.message)

    def test_op_build_mode_requires_plan_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(Path(tmp), op_build_mode=True)
            with self.assertRaises(MODULE.ToolError) as ctx:
                MODULE.validate_policy(cfg)
            self.assertEqual(ctx.exception.code, "validation_error")
            self.assertIn("plan_id", ctx.exception.message)

    def test_op_build_mode_persists_plan_fields_in_handoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = make_cfg(
                root,
                op_build_mode=True,
                plan_id="plan-20260227T010101Z",
                requirement_ids=["REQ-001", "REQ-002"],
                task_acceptance_refs=["AC-001", "AC-002"],
                dev_ready_evidence_ref="reports/optimus-prime/planning/DEV_READY_EVIDENCE.json",
            )
            out = MODULE.run_dispatch_worker_packet(cfg, dispatcher=FakeDispatcher())
            self.assertTrue(out["ok"])

            handoff_line = (
                root / "reports" / "optimus-prime" / "HANDOFF_LOG.jsonl"
            ).read_text(encoding="utf-8").strip().splitlines()[-1]
            handoff = json.loads(handoff_line)
            self.assertTrue(handoff["op_build_mode"])
            self.assertEqual(handoff["plan_id"], "plan-20260227T010101Z")
            self.assertEqual(handoff["requirement_ids"], ["REQ-001", "REQ-002"])
            self.assertEqual(handoff["task_acceptance_refs"], ["AC-001", "AC-002"])
            self.assertEqual(
                handoff["dev_ready_evidence_ref"],
                "reports/optimus-prime/planning/DEV_READY_EVIDENCE.json",
            )
            self.assertEqual(
                handoff["task_evidence_ref"],
                "reports/optimus-prime/planning/DEV_READY_EVIDENCE.json",
            )


if __name__ == "__main__":
    unittest.main()
