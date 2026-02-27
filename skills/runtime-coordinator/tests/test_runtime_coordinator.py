import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "runtime_coordinator.py"
SPEC = importlib.util.spec_from_file_location("runtime_coordinator", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, rows: list[object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            if isinstance(row, str):
                fh.write(row)
                if not row.endswith("\n"):
                    fh.write("\n")
            else:
                fh.write(json.dumps(row) + "\n")


class RuntimeCoordinatorTests(unittest.TestCase):
    def _make_repo(self, tmp: str) -> Path:
        root = Path(tmp)
        write_json(
            root / "reports" / "optimus-prime" / "config" / "RUNTIME_PROFILES.json",
            {
                "schema_version": "1.0",
                "profiles": [
                    {
                        "profile_id": "default-web",
                        "kind": "web",
                        "start_cmd": "true",
                        "healthcheck": {"type": "none", "value": ""},
                        "stop_cmd": "true",
                        "env": {"PW_FRONTEND_MODE": "preview"},
                        "supports_shared": True,
                        "supports_isolated": True,
                        "default_for_playwright": True,
                        "default_base_url": "http://127.0.0.1:4173",
                        "mutating_flow_policy": "serialized",
                        "test_accounts": [],
                    }
                ],
            },
        )
        write_json(
            root / "reports" / "optimus-prime" / "config" / "TEST_TRAIN_PIPELINE.json",
            {
                "schema_version": "1.0",
                "pipeline_id": "default",
                "mode_policy": {
                    "off": {"hard_gate": False},
                    "final-stage": {"hard_gate": True},
                    "forced-shared-env": {"hard_gate": True},
                },
                "deploy": {
                    "command": "echo deploy",
                    "cwd": "${REPO_ROOT}",
                    "timeout_sec": 30,
                },
                "health": {
                    "require_consecutive_passes": 2,
                    "checks": [
                        {
                            "id": "cmd-ok",
                            "type": "cmd",
                            "value": "true",
                            "timeout_sec": 10,
                        }
                    ],
                    "profile_check_required": True,
                },
                "repair": {
                    "self_heal_commands": ["true"],
                    "cooldown_sec": 300,
                    "max_attempts_per_fingerprint_window": 1,
                    "create_dev_task": True,
                    "create_blocker": True,
                },
                "locking": {
                    "enable_single_flight": True,
                    "lock_ttl_sec": 1800,
                },
                "lease_policy": {
                    "stale_ttl_sec": 900,
                },
            },
        )
        return root

    def _build_input(self, repo_root: Path, **overrides: object):
        payload = {
            "repo_root": str(repo_root),
            "action": overrides.get("action", "resolve"),
            "task_identifier": overrides.get("task_identifier", "MYO-100"),
            "worker_slot": overrides.get("worker_slot", "test-1"),
            "worker_role": overrides.get("worker_role", "tester"),
            "task_kind": overrides.get("task_kind", "ui_flow"),
            "requires_browser": overrides.get("requires_browser", True),
            "mutating_flow": overrides.get("mutating_flow", False),
            "runtime_strategy_override": overrides.get("runtime_strategy_override"),
            "test_train_mode": overrides.get("test_train_mode", "off"),
            "shared_test_base_url": overrides.get("shared_test_base_url"),
            "runtime_profile_id": overrides.get("runtime_profile_id"),
            "external_base_url": overrides.get("external_base_url"),
            "runtime_id": overrides.get("runtime_id"),
            "lease_id": overrides.get("lease_id"),
            "requested_status": overrides.get("requested_status"),
            "blocker_stage": overrides.get("blocker_stage"),
            "blocker_code": overrides.get("blocker_code"),
            "blocker_category": overrides.get("blocker_category"),
            "blocker_summary": overrides.get("blocker_summary"),
            "blocker_signature": overrides.get("blocker_signature"),
            "blocker_retryable": overrides.get("blocker_retryable"),
            "blocker_evidence_paths": overrides.get("blocker_evidence_paths"),
            "repair_force_fingerprint": overrides.get("repair_force_fingerprint"),
            "repair_force_delegate": overrides.get("repair_force_delegate"),
        }
        return MODULE.build_input(payload)

    def test_resolve_none_for_non_browser_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_repo(tmp)
            inp = self._build_input(
                root,
                task_kind="api",
                requires_browser=False,
                mutating_flow=False,
            )
            out = MODULE.run(inp)
            self.assertTrue(out["ok"])
            self.assertEqual(out["runtime_strategy"], "none")
            self.assertEqual(out["dispatch_payload"]["runtime_id"], None)

    def test_resolve_shared_runtime_returns_dispatch_payload_and_lease(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_repo(tmp)
            inp = self._build_input(root, task_identifier="MYO-101", worker_slot="test-1")
            out = MODULE.run(inp)
            self.assertTrue(out["ok"])
            self.assertEqual(out["runtime_strategy"], "shared_runtime")
            payload = out["dispatch_payload"]
            self.assertEqual(payload["runtime_id"], "rt-shared-default-web")
            self.assertEqual(payload["runtime_profile_id"], "default-web")
            self.assertTrue(payload["tester_must_not_start_runtime"])
            self.assertIsNotNone(payload["lease_id"])
            self.assertEqual(payload["runtime_lease_id"], payload["lease_id"])

            registry = json.loads((root / "reports" / "optimus-prime" / "RUNTIME_REGISTRY.json").read_text(encoding="utf-8"))
            self.assertEqual(registry["instances"][0]["runtime_id"], "rt-shared-default-web")

    def test_serialized_mutating_lease_conflict_logs_blocker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_repo(tmp)

            first = self._build_input(root, task_identifier="MYO-102", worker_slot="test-1", mutating_flow=True)
            out_first = MODULE.run(first)
            self.assertTrue(out_first["ok"])
            self.assertEqual(out_first["runtime_strategy"], "shared_runtime")

            second = self._build_input(root, task_identifier="MYO-103", worker_slot="test-2", mutating_flow=True)
            out_second = MODULE.run(second)
            self.assertFalse(out_second["ok"])
            self.assertEqual(out_second["blocked"]["code"], "serialized_runtime_locked")

            blockers_path = root / "reports" / "optimus-prime" / "BLOCKERS.jsonl"
            lines = blockers_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertGreaterEqual(len(lines), 1)
            row = json.loads(lines[-1])
            self.assertEqual(row["blocker_code"], "serialized_runtime_locked")
            self.assertEqual(row["category"], "runtime")

    def test_release_lease_marks_released(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_repo(tmp)
            resolve_inp = self._build_input(root, task_identifier="MYO-104", worker_slot="test-1")
            out = MODULE.run(resolve_inp)
            self.assertTrue(out["ok"])
            lease_id = out["dispatch_payload"]["lease_id"]
            self.assertIsNotNone(lease_id)

            release_inp = self._build_input(
                root,
                action="release_lease",
                lease_id=lease_id,
                task_identifier="MYO-104",
                worker_slot="test-1",
            )
            rel_out = MODULE.run(release_inp)
            self.assertTrue(rel_out["ok"])

            leases = json.loads((root / "reports" / "optimus-prime" / "TEST_RUNTIME_LEASES.json").read_text(encoding="utf-8"))
            matching = [l for l in leases["leases"] if l["lease_id"] == lease_id]
            self.assertEqual(matching[0]["status"], "released")

    def test_refresh_blocker_index_aggregates_and_writes_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_repo(tmp)
            blockers = root / "reports" / "optimus-prime" / "BLOCKERS.jsonl"
            append_jsonl(
                blockers,
                [
                    {
                        "timestamp": "2026-02-26T20:00:00Z",
                        "task_identifier": "MYO-201",
                        "stage": "runtime",
                        "blocker_code": "runtime_start_failed",
                        "category": "infra",
                        "summary": "Nuxt startup EMFILE",
                        "signature": "EMFILE: too many open files",
                        "fingerprint": "runtime|runtime_start_failed|EMFILE: too many open files",
                    },
                    {
                        "timestamp": "2026-02-26T21:00:00Z",
                        "task_identifier": "MYO-202",
                        "stage": "runtime",
                        "blocker_code": "runtime_start_failed",
                        "category": "infra",
                        "summary": "Nuxt startup EMFILE",
                        "signature": "EMFILE: too many open files",
                        "fingerprint": "runtime|runtime_start_failed|EMFILE: too many open files",
                    },
                    "{malformed json\n",
                ],
            )

            inp = self._build_input(root, action="refresh_blocker_index")
            out = MODULE.run(inp)
            self.assertTrue(out["ok"])
            self.assertEqual(out["rows_processed"], 3)
            self.assertEqual(out["rows_malformed"], 1)
            self.assertEqual(out["entries"], 1)
            self.assertEqual(out["recurring_entries"], 1)

            index_payload = json.loads((root / "reports" / "optimus-prime" / "BLOCKER_INDEX.json").read_text(encoding="utf-8"))
            self.assertEqual(index_payload["entries"][0]["count"], 2)
            self.assertIn("recommended_playbook", index_payload["entries"][0])

            report_text = (root / "reports" / "optimus-prime" / "BLOCKER_ADAPTATION_CANDIDATES.md").read_text(encoding="utf-8")
            self.assertIn("runtime_start_failed", report_text)

    def test_upsert_runtime_failed_logs_blocker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_repo(tmp)
            inp = self._build_input(
                root,
                action="upsert_runtime",
                runtime_id="rt-shared-default-web",
                requested_status="failed",
            )
            out = MODULE.run(inp)
            self.assertTrue(out["ok"])

            blockers_path = root / "reports" / "optimus-prime" / "BLOCKERS.jsonl"
            lines = blockers_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertGreaterEqual(len(lines), 1)
            row = json.loads(lines[-1])
            self.assertEqual(row["blocker_code"], "runtime_failed")

    def test_log_blocker_action_writes_structured_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_repo(tmp)
            inp = self._build_input(
                root,
                action="log_blocker",
                task_identifier="MYO-333",
                worker_slot="dev-1",
                worker_role="developer",
                blocker_stage="build",
                blocker_code="build_failed",
                blocker_category="code",
                blocker_summary="Typecheck failed",
                blocker_signature="mypy: module not found",
                blocker_retryable=False,
                blocker_evidence_paths=["reports/optimus-prime/logs/build.log"],
            )
            out = MODULE.run(inp)
            self.assertTrue(out["ok"])
            self.assertEqual(out["action"], "log_blocker")

            blockers_path = root / "reports" / "optimus-prime" / "BLOCKERS.jsonl"
            rows = [json.loads(line) for line in blockers_path.read_text(encoding="utf-8").strip().splitlines()]
            row = rows[-1]
            self.assertEqual(row["stage"], "build")
            self.assertEqual(row["blocker_code"], "build_failed")
            self.assertEqual(row["category"], "code")
            self.assertFalse(row["retryable"])
            self.assertEqual(row["evidence_paths"], ["reports/optimus-prime/logs/build.log"])

    def test_train_mode_rejects_legacy_shared_url_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_repo(tmp)
            with self.assertRaises(MODULE.ToolError) as ctx:
                self._build_input(
                    root,
                    test_train_mode="final-stage",
                    shared_test_base_url="https://test.example.internal",
                )
            self.assertEqual(ctx.exception.code, "input_error")

    def test_train_mode_blocks_local_runtime_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_repo(tmp)
            inp = self._build_input(
                root,
                test_train_mode="forced-shared-env",
                runtime_strategy_override="none",
                worker_role="tester",
                requires_browser=True,
                task_kind="ui_flow",
            )
            out = MODULE.run(inp)
            self.assertFalse(out["ok"])
            self.assertEqual(out["blocked"]["code"], "test_train_local_runtime_denied")

            blockers_path = root / "reports" / "optimus-prime" / "BLOCKERS.jsonl"
            row = json.loads(blockers_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row["category"], "test-train")

    def test_bootstrap_creates_runtime_state_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_repo(tmp)
            inp = self._build_input(root, action="bootstrap")
            out = MODULE.run(inp)
            self.assertTrue(out["ok"])
            runtime_root = root / "reports" / "optimus-prime" / "runtime"
            self.assertTrue((runtime_root / "RUNTIME_HEALTH.json").exists())
            self.assertTrue((runtime_root / "RUNTIME_REPAIR_TASKS.json").exists())
            self.assertTrue((runtime_root / "RUNTIME_ACTION_LOG.jsonl").exists())

    def test_health_requires_two_consecutive_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_repo(tmp)
            resolve_out = MODULE.run(self._build_input(root, action="resolve"))
            self.assertTrue(resolve_out["ok"])
            runtime_id = resolve_out["dispatch_payload"]["runtime_id"]

            # Mark runtime healthy so profile check can pass.
            MODULE.run(
                self._build_input(
                    root,
                    action="upsert_runtime",
                    runtime_id=runtime_id,
                    runtime_profile_id="default-web",
                    requested_status="healthy",
                )
            )

            first = MODULE.run(
                self._build_input(
                    root,
                    action="health",
                    runtime_id=runtime_id,
                )
            )
            self.assertTrue(first["ok"])
            self.assertEqual(first["gate_state"], "degraded")
            second = MODULE.run(
                self._build_input(
                    root,
                    action="health",
                    runtime_id=runtime_id,
                )
            )
            self.assertTrue(second["ok"])
            self.assertEqual(second["gate_state"], "healthy")

    def test_health_sweeps_stale_leases(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_repo(tmp)
            leases_path = root / "reports" / "optimus-prime" / "TEST_RUNTIME_LEASES.json"
            write_json(
                leases_path,
                {
                    "schema_version": "1.0",
                    "updated_at": "2026-02-27T00:00:00Z",
                    "leases": [
                        {
                            "lease_id": "lease-old-1",
                            "runtime_id": "rt-shared-default-web",
                            "status": "active",
                            "created_at": "2026-01-01T00:00:00Z",
                            "updated_at": "2026-01-01T00:00:00Z",
                        }
                    ],
                },
            )
            out = MODULE.run(self._build_input(root, action="health"))
            self.assertTrue(out["ok"])
            self.assertIn("lease-old-1", out["released_lease_ids"])
            leases = json.loads(leases_path.read_text(encoding="utf-8"))
            self.assertEqual(leases["leases"][0]["status"], "released")

    def test_repair_delegates_when_heal_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_repo(tmp)
            pipeline_path = root / "reports" / "optimus-prime" / "config" / "TEST_TRAIN_PIPELINE.json"
            pipeline = json.loads(pipeline_path.read_text(encoding="utf-8"))
            pipeline["health"]["checks"] = [{"id": "always-fail", "type": "cmd", "value": "false", "timeout_sec": 5}]
            pipeline["repair"]["self_heal_commands"] = ["false"]
            write_json(pipeline_path, pipeline)

            MODULE.run(self._build_input(root, action="health", test_train_mode="final-stage"))
            out = MODULE.run(self._build_input(root, action="repair", test_train_mode="final-stage"))
            self.assertFalse(out["ok"])
            self.assertEqual(out["result"], "delegated")
            self.assertEqual(out["repair_task"]["lane"], "runtime-infra")
            self.assertEqual(out["repair_task"]["quality_flow"], "dev_only")

            blockers_path = root / "reports" / "optimus-prime" / "BLOCKERS.jsonl"
            row = json.loads(blockers_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row["blocker_code"], "runtime_repair_required")

    def test_repair_can_force_delegate_even_when_gate_healthy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_repo(tmp)
            write_json(
                root / "reports" / "optimus-prime" / "runtime" / "RUNTIME_HEALTH.json",
                {
                    "schema_version": "1.0",
                    "updated_at": MODULE.utc_now_iso(),
                    "test_train_mode": "final-stage",
                    "gate_state": "healthy",
                    "consecutive_passes": 2,
                    "required_passes": 2,
                    "pipeline_checks": [],
                    "profile_checks": [],
                    "both_sources_pass": True,
                    "last_failure_fingerprint": None,
                    "next_heal_allowed_at": None,
                },
            )
            out = MODULE.run(
                self._build_input(
                    root,
                    action="repair",
                    test_train_mode="final-stage",
                    repair_force_fingerprint="deploy|command_failed|exit_code=42",
                    repair_force_delegate=True,
                )
            )
            self.assertFalse(out["ok"])
            self.assertEqual(out["result"], "delegated")
            self.assertEqual(out["repair_task"]["dedup_key"], "deploy|command_failed|exit_code=42")

    def test_repair_respects_max_attempt_counter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_repo(tmp)
            pipeline_path = root / "reports" / "optimus-prime" / "config" / "TEST_TRAIN_PIPELINE.json"
            pipeline = json.loads(pipeline_path.read_text(encoding="utf-8"))
            pipeline["health"]["checks"] = [{"id": "always-fail", "type": "cmd", "value": "false", "timeout_sec": 5}]
            pipeline["repair"]["self_heal_commands"] = ["true"]
            pipeline["repair"]["max_attempts_per_fingerprint_window"] = 1
            write_json(pipeline_path, pipeline)

            MODULE.run(self._build_input(root, action="health", test_train_mode="final-stage"))
            health = json.loads((root / "reports" / "optimus-prime" / "runtime" / "RUNTIME_HEALTH.json").read_text(encoding="utf-8"))
            fingerprint = health["last_failure_fingerprint"]
            append_jsonl(
                root / "reports" / "optimus-prime" / "runtime" / "RUNTIME_ACTION_LOG.jsonl",
                [
                    {
                        "timestamp": MODULE.utc_now_iso(),
                        "action": "heal",
                        "result": "ok",
                        "runtime_id": None,
                        "fingerprint": fingerprint,
                        "details": {"source": "test"},
                    }
                ],
            )

            out = MODULE.run(self._build_input(root, action="repair", test_train_mode="final-stage"))
            self.assertFalse(out["ok"])
            self.assertEqual(out["result"], "delegated")
            self.assertIsNotNone(out.get("repair_task"))

    def test_repair_attempt_counter_expires_outside_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_repo(tmp)
            pipeline_path = root / "reports" / "optimus-prime" / "config" / "TEST_TRAIN_PIPELINE.json"
            pipeline = json.loads(pipeline_path.read_text(encoding="utf-8"))
            pipeline["health"]["checks"] = [{"id": "always-fail", "type": "cmd", "value": "false", "timeout_sec": 5}]
            pipeline["repair"]["self_heal_commands"] = ["true"]
            pipeline["repair"]["cooldown_sec"] = 60
            pipeline["repair"]["max_attempts_per_fingerprint_window"] = 1
            pipeline["repair"]["attempt_window_sec"] = 60
            write_json(pipeline_path, pipeline)

            MODULE.run(self._build_input(root, action="health", test_train_mode="final-stage"))
            health_path = root / "reports" / "optimus-prime" / "runtime" / "RUNTIME_HEALTH.json"
            health = json.loads(health_path.read_text(encoding="utf-8"))
            fingerprint = health["last_failure_fingerprint"]
            append_jsonl(
                root / "reports" / "optimus-prime" / "runtime" / "RUNTIME_ACTION_LOG.jsonl",
                [
                    {
                        "timestamp": "2020-01-01T00:00:00Z",
                        "action": "heal",
                        "result": "ok",
                        "runtime_id": None,
                        "fingerprint": fingerprint,
                        "details": {"source": "old-window"},
                    }
                ],
            )

            out = MODULE.run(self._build_input(root, action="repair", test_train_mode="final-stage"))
            self.assertFalse(out["ok"])
            self.assertEqual(out["result"], "delegated")
            refreshed = json.loads(health_path.read_text(encoding="utf-8"))
            self.assertIsNotNone(refreshed.get("next_heal_allowed_at"))

    def test_health_lock_conflict_raises_locked_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_repo(tmp)
            lock_path = root / "reports" / "optimus-prime" / "runtime" / "locks" / "health-default.lock"
            write_json(lock_path, {"created_at": MODULE.utc_now_iso(), "lock_name": "health-default"})
            with self.assertRaises(MODULE.ToolError) as ctx:
                MODULE.run(self._build_input(root, action="health"))
            self.assertEqual(ctx.exception.code, "locked")


if __name__ == "__main__":
    unittest.main()
