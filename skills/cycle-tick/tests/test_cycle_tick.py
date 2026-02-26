import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "cycle_tick.py"
SPEC = importlib.util.spec_from_file_location("cycle_tick", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class CycleTickTests(unittest.TestCase):
    def make_input(self, root: Path, **overrides):
        return MODULE.TickInput(
            repo_root=root,
            cycle_number=int(overrides.get("cycle_number", 60)),
            status_profiles_scope=str(overrides.get("status_profiles_scope", "all-configured-plus-primary")),
            rate_gate_5h_percent=float(overrides.get("rate_gate_5h_percent", 15)),
            rate_gate_weekly_percent=float(overrides.get("rate_gate_weekly_percent", 10)),
            soft_rate_gate_5h_percent=float(overrides.get("soft_rate_gate_5h_percent", 40)),
            soft_rate_gate_weekly_percent=float(overrides.get("soft_rate_gate_weekly_percent", 25)),
            soft_rate_gated_max_running_workers=int(overrides.get("soft_rate_gated_max_running_workers", 3)),
            rate_reset_wait_max_hours=float(overrides.get("rate_reset_wait_max_hours", 4)),
            sleep_minutes=int(overrides.get("sleep_minutes", 5)),
            allow_dispatch=bool(overrides.get("allow_dispatch", True)),
            user_steering_active=bool(overrides.get("user_steering_active", False)),
            dry_run=bool(overrides.get("dry_run", True)),
        )

    def write_workers(self, root: Path, running: int = 0):
        workers = []
        for i, slot in enumerate(["dev-1", "dev-2", "dev-3", "test-1", "test-2", "review-1"]):
            workers.append(
                {
                    "slot": slot,
                    "session_state": "running" if i < running else "idle",
                }
            )
        write_json(root / "reports" / "optimus-prime" / "WORKER_REGISTRY.json", {"workers": workers})

    def write_rate_registry(self, root: Path, mode: str, profiles: dict):
        write_json(
            root / "reports" / "optimus-prime" / "PROFILE_RATE_REGISTRY.json",
            {
                "profile_running_mode": mode,
                "profiles": profiles,
            },
        )

    def test_single_profile_hard_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_workers(root, running=2)
            self.write_rate_registry(
                root,
                "single-profile",
                {
                    "codex": {
                        "five_hour": {"remaining_percent": 10, "gated": True, "reset_at": "2099-01-01T00:00:00Z"},
                        "weekly": {"remaining_percent": 50, "gated": False},
                    }
                },
            )
            cfg = self.make_input(root, dry_run=True)
            out = MODULE.run_cycle_tick(cfg)
            self.assertTrue(out["ok"])
            self.assertEqual(out["action"], "wind_down_no_new_dispatch")
            self.assertFalse(out["dispatch_allowed"])
            self.assertEqual(out["effective_max_running_workers"], 0)
            self.assertIn("codex", out["gated_profiles"])

    def test_single_user_shared_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_workers(root, running=1)
            self.write_rate_registry(
                root,
                "single-user",
                {
                    "codex": {
                        "five_hour": {"remaining_percent": 20, "gated": False},
                        "weekly": {"remaining_percent": 5, "gated": True, "reset_at": "2099-01-01T00:00:00Z"},
                    },
                    "codex-second": {
                        "five_hour": {"remaining_percent": 80, "gated": False},
                        "weekly": {"remaining_percent": 80, "gated": False},
                    },
                },
            )
            out = MODULE.run_cycle_tick(self.make_input(root, dry_run=True))
            self.assertEqual(out["action"], "wind_down_no_new_dispatch")
            self.assertFalse(out["dispatch_allowed"])

    def test_multi_user_partial_profile_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_workers(root, running=3)
            self.write_rate_registry(
                root,
                "multiple-users",
                {
                    "codex": {
                        "five_hour": {"remaining_percent": 8, "gated": True},
                        "weekly": {"remaining_percent": 80, "gated": False},
                    },
                    "codex-second": {
                        "five_hour": {"remaining_percent": 60, "gated": False},
                        "weekly": {"remaining_percent": 70, "gated": False},
                    },
                },
            )
            out = MODULE.run_cycle_tick(self.make_input(root, dry_run=True))
            self.assertTrue(out["dispatch_allowed"])
            self.assertEqual(out["action"], "continue_dispatch")
            self.assertIn("codex", out["gated_profiles"])

    def test_soft_gate_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_workers(root, running=4)
            self.write_rate_registry(
                root,
                "single-profile",
                {
                    "codex": {
                        "five_hour": {"remaining_percent": 35, "gated": False},
                        "weekly": {"remaining_percent": 30, "gated": False},
                    }
                },
            )
            out = MODULE.run_cycle_tick(self.make_input(root, dry_run=True))
            self.assertEqual(out["action"], "continue_with_soft_cap")
            self.assertEqual(out["effective_max_running_workers"], 3)
            self.assertTrue(out["dispatch_allowed"])

    def test_reset_within_wait_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            soon = (MODULE.utc_now() + MODULE.timedelta(hours=1)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            self.write_workers(root, running=2)
            self.write_rate_registry(
                root,
                "single-profile",
                {
                    "codex": {
                        "five_hour": {"remaining_percent": 5, "gated": True, "reset_at": soon},
                        "weekly": {"remaining_percent": 50, "gated": False},
                    }
                },
            )
            out = MODULE.run_cycle_tick(self.make_input(root, dry_run=True, rate_reset_wait_max_hours=4))
            self.assertEqual(out["action"], "hold_and_sleep_until_reset")
            self.assertFalse(out["dispatch_allowed"])
            self.assertTrue(out["sleep_recommendation"]["should_sleep"])
            self.assertIsNotNone(out["sleep_recommendation"]["until"])

    def test_reset_outside_wait_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            later = (MODULE.utc_now() + MODULE.timedelta(hours=8)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            self.write_workers(root, running=2)
            self.write_rate_registry(
                root,
                "single-profile",
                {
                    "codex": {
                        "five_hour": {"remaining_percent": 5, "gated": True, "reset_at": later},
                        "weekly": {"remaining_percent": 50, "gated": False},
                    }
                },
            )
            out = MODULE.run_cycle_tick(self.make_input(root, dry_run=True, rate_reset_wait_max_hours=4))
            self.assertEqual(out["action"], "wind_down_no_new_dispatch")
            self.assertFalse(out["sleep_recommendation"]["should_sleep"])

    def test_integration_logs_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_workers(root, running=1)
            self.write_rate_registry(
                root,
                "single-profile",
                {
                    "codex": {
                        "five_hour": {"remaining_percent": 70, "gated": False},
                        "weekly": {"remaining_percent": 60, "gated": False},
                    }
                },
            )
            out = MODULE.run_cycle_tick(self.make_input(root, dry_run=False))
            self.assertTrue(out["ok"])
            self.assertTrue(out["logs_written"]["cycle_log"])
            self.assertTrue(out["logs_written"]["rate_log"])

            cycle_lines = (root / "reports" / "optimus-prime" / "CYCLE_LOG.jsonl").read_text(encoding="utf-8").strip().splitlines()
            rate_lines = (root / "reports" / "optimus-prime" / "RATE_STATUS_LOG.jsonl").read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(cycle_lines), 1)
            self.assertEqual(len(rate_lines), 1)
            cycle = json.loads(cycle_lines[0])
            rate = json.loads(rate_lines[0])
            self.assertEqual(cycle["event"], "cycle_tick")
            self.assertEqual(rate["event"], "cycle_tick_rate_eval")


if __name__ == "__main__":
    unittest.main()
