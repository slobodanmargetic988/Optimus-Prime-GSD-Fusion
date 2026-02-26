import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "orchestrator_status_snapshot.py"
SPEC = importlib.util.spec_from_file_location("orchestrator_status_snapshot", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_jsonl(path: Path, rows: list[object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            if isinstance(row, str):
                fh.write(row)
                if not row.endswith("\n"):
                    fh.write("\n")
            else:
                fh.write(json.dumps(row))
                fh.write("\n")


class OrchestratorStatusSnapshotTests(unittest.TestCase):
    def _config(self, repo_root: Path, **overrides: object):
        return MODULE.InputConfig(
            repo_root=repo_root,
            include_history=bool(overrides.get("include_history", False)),
            max_history_items=int(overrides.get("max_history_items", 5)),
            include_process_check=bool(overrides.get("include_process_check", False)),
            output_mode=str(overrides.get("output_mode", "json")),
        )

    def test_all_workers_idle_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = root / "reports" / "optimus-prime"

            workers = []
            for slot in MODULE.SLOT_ORDER:
                workers.append(
                    {
                        "slot": slot,
                        "role": MODULE.ROLE_BY_SLOT[slot],
                        "session_state": "idle",
                        "session_id": f"session-{slot}",
                    }
                )

            write_json(reports / "WORKER_REGISTRY.json", {"workers": workers})
            write_jsonl(reports / "CYCLE_LOG.jsonl", [{"cycle_number": 12, "timestamp": "2026-02-24T18:00:00Z"}])
            write_jsonl(reports / "HANDOFF_LOG.jsonl", [])
            write_json(
                reports / "PROFILE_RATE_REGISTRY.json",
                {
                    "profile_running_mode": "single-profile",
                    "soft_concurrency": {"max_active_workers_when_gated": 3},
                    "profiles": {
                        "codex": {
                            "five_hour": {"gated": False},
                            "weekly": {"gated": False},
                            "soft_concurrency_gated": False,
                        }
                    },
                },
            )
            write_jsonl(reports / "RATE_STATUS_LOG.jsonl", [{"profile_running_mode": "single-profile"}])

            snapshot = MODULE.generate_snapshot(self._config(root, output_mode="json+text"))

            self.assertTrue(snapshot["ok"])
            self.assertEqual(snapshot["cycle"]["number"], 12)
            self.assertEqual([w["slot"] for w in snapshot["workers"]], MODULE.SLOT_ORDER)
            self.assertEqual(snapshot["counts"]["idle_workers"], 6)
            self.assertEqual(snapshot["counts"]["active_workers"], 0)
            self.assertEqual(snapshot["counts"]["blocked_workers"], 0)
            self.assertTrue(all("session_id" in worker for worker in snapshot["workers"]))
            self.assertIsInstance(snapshot["text_summary"], str)

    def test_mixed_running_blocked_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = root / "reports" / "optimus-prime"

            write_json(
                reports / "WORKER_REGISTRY.json",
                {
                    "workers": [
                        {
                            "slot": "dev-1",
                            "role": "developer",
                            "session_state": "running",
                            "active_task": "MYO-200",
                            "branch": "codex/dev-1/MYO-200",
                            "session_id": "dev-session-1",
                            "last_result": "ready_for_test",
                        },
                        {
                            "slot": "test-1",
                            "role": "tester",
                            "session_state": "blocked",
                            "active_task": "MYO-201",
                            "session_id": "test-session-1",
                            "blocker_summary": "Waiting on dependency migration",
                        },
                    ]
                },
            )
            write_jsonl(reports / "CYCLE_LOG.jsonl", [{"cycle_number": 13, "timestamp": "2026-02-24T18:05:00Z"}])
            write_jsonl(
                reports / "HANDOFF_LOG.jsonl",
                [
                    {
                        "slot": "test-1",
                        "task_identifier": "MYO-201",
                        "result": "blocked",
                        "blocker_summary": "Dependency service is down",
                        "timestamp": "2026-02-24T18:04:00Z",
                    }
                ],
            )
            write_json(
                reports / "PROFILE_RATE_REGISTRY.json",
                {
                    "profile_running_mode": "single-profile",
                    "soft_concurrency": {"max_active_workers_when_gated": 2},
                    "profiles": {
                        "codex": {
                            "soft_concurrency_gated": True,
                            "five_hour": {"gated": True},
                            "weekly": {"gated": False},
                        }
                    },
                },
            )
            write_jsonl(reports / "RATE_STATUS_LOG.jsonl", [{"profile_running_mode": "single-profile"}])

            snapshot = MODULE.generate_snapshot(self._config(root))

            self.assertTrue(snapshot["ok"])
            self.assertEqual(snapshot["counts"]["active_workers"], 1)
            self.assertEqual(snapshot["counts"]["blocked_workers"], 1)
            self.assertGreaterEqual(len(snapshot["high_priority_blockers"]), 1)
            self.assertEqual(snapshot["rate"]["profiles"][0]["alias"], "codex")
            self.assertEqual(snapshot["rate"]["profiles"][0]["hard_gate"], "gated")
            self.assertEqual(snapshot["rate"]["profiles"][0]["effective_cap"], 0)

    def test_runtime_and_blocker_sources_are_included(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = root / "reports" / "optimus-prime"

            write_json(reports / "WORKER_REGISTRY.json", {"workers": []})
            write_jsonl(reports / "CYCLE_LOG.jsonl", [{"cycle_number": 20, "timestamp": "2026-02-26T20:00:00Z"}])
            write_jsonl(reports / "HANDOFF_LOG.jsonl", [])
            write_json(reports / "PROFILE_RATE_REGISTRY.json", {"profiles": {}})
            write_jsonl(reports / "RATE_STATUS_LOG.jsonl", [])

            write_json(
                reports / "RUNTIME_REGISTRY.json",
                {
                    "schema_version": "1.0",
                    "updated_at": "2026-02-26T20:01:00Z",
                    "instances": [
                        {
                            "runtime_id": "rt-shared-default-web",
                            "mode": "shared",
                            "status": "healthy",
                            "base_url": "http://127.0.0.1:4173",
                        }
                    ],
                },
            )
            write_json(
                reports / "TEST_RUNTIME_LEASES.json",
                {
                    "schema_version": "1.0",
                    "updated_at": "2026-02-26T20:02:00Z",
                    "leases": [
                        {
                            "lease_id": "lease-1",
                            "runtime_id": "rt-shared-default-web",
                            "status": "active",
                            "mode": "exclusive",
                        }
                    ],
                },
            )
            write_jsonl(
                reports / "BLOCKERS.jsonl",
                [
                    {
                        "timestamp": "2026-02-26T20:03:00Z",
                        "task_identifier": "MYO-300",
                        "worker_slot": "test-1",
                        "stage": "runtime",
                        "blocker_code": "runtime_start_failed",
                        "summary": "EMFILE",
                    }
                ],
            )
            write_json(
                reports / "BLOCKER_INDEX.json",
                {
                    "schema_version": "1.0",
                    "updated_at": "2026-02-26T20:04:00Z",
                    "entries": [
                        {
                            "fingerprint": "runtime|runtime_start_failed|EMFILE",
                            "count": 4,
                            "blocker_code": "runtime_start_failed",
                            "category": "infra",
                            "latest_summary": "EMFILE",
                            "recommended_playbook": "Use shared preview runtime",
                        }
                    ],
                },
            )

            snapshot = MODULE.generate_snapshot(self._config(root, output_mode="json+text"))
            self.assertTrue(snapshot["ok"])
            self.assertEqual(snapshot["runtime"]["shared_instances"], 1)
            self.assertEqual(snapshot["runtime"]["active_exclusive_leases"], 1)
            self.assertEqual(snapshot["blockers"]["events_total"], 1)
            self.assertEqual(snapshot["blockers"]["top_fingerprints"][0]["blocker_code"], "runtime_start_failed")
            self.assertIn("Runtime:", snapshot["status_text"])

    def test_malformed_jsonl_lines_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = root / "reports" / "optimus-prime"

            write_json(reports / "WORKER_REGISTRY.json", {"workers": []})
            write_jsonl(
                reports / "CYCLE_LOG.jsonl",
                [
                    "this is not json\n",
                    {"cycle_number": 14, "timestamp": "2026-02-24T18:10:00Z"},
                ],
            )
            write_jsonl(
                reports / "HANDOFF_LOG.jsonl",
                [
                    "{bad json\n",
                    {"slot": "dev-1", "result": "ready_for_test", "timestamp": "2026-02-24T18:09:00Z"},
                ],
            )
            write_json(reports / "PROFILE_RATE_REGISTRY.json", {"profiles": {}})
            write_jsonl(reports / "RATE_STATUS_LOG.jsonl", [])

            snapshot = MODULE.generate_snapshot(self._config(root))

            self.assertTrue(snapshot["ok"])
            self.assertGreaterEqual(snapshot["parse_warning_count"], 2)
            warning_codes = {warning["code"] for warning in snapshot["warnings"]}
            self.assertIn("malformed_jsonl_line", warning_codes)

    def test_missing_core_files_returns_actionable_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot = MODULE.generate_snapshot(self._config(root))

            self.assertFalse(snapshot["ok"])
            error_codes = [error["code"] for error in snapshot["errors"]]
            self.assertIn("all_core_sources_unavailable", error_codes)
            self.assertGreaterEqual(error_codes.count("missing_file"), 5)


if __name__ == "__main__":
    unittest.main()
