import importlib.util
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "minimal_rate_snapshot.py"
SPEC = importlib.util.spec_from_file_location("minimal_rate_snapshot", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class _StubLogger:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def log(self, message: str) -> None:
        self.lines.append(message)


class MinimalRateSnapshotTests(unittest.TestCase):
    def test_discover_profiles_excludes_default_when_multiple(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".codex").mkdir()
            (root / ".codex-first").mkdir()
            (root / ".codex-second").mkdir()

            paths = MODULE.discover_profile_paths(root / ".codex", root)
            aliases = [MODULE.alias_from_codex_home(path, root / ".codex") for path in paths]

            self.assertEqual(aliases, ["first", "second"])

    def test_discover_profiles_keeps_default_when_single(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".codex").mkdir()

            paths = MODULE.discover_profile_paths(root / ".codex", root)
            aliases = [MODULE.alias_from_codex_home(path, root / ".codex") for path in paths]

            self.assertEqual(aliases, ["codex"])

    def test_classify_gate_rules(self):
        self.assertFalse(MODULE.classify_gate(59.9, 79.9))
        self.assertEqual(MODULE.classify_gate(60.0, 20.0), "soft-gated")
        self.assertEqual(MODULE.classify_gate(40.0, 80.0), "soft-gated")
        self.assertEqual(MODULE.classify_gate(93.0, 10.0), "hard-gated")
        self.assertEqual(MODULE.classify_gate(30.0, 97.0), "hard-gated")

    def test_build_profile_snapshot_maps_usage_payload(self):
        payload = {
            "email": "test@example.com",
            "rate_limit": {
                "primary_window": {"used_percent": 61, "reset_at": 1773529474},
                "secondary_window": {"used_percent": 34, "reset_at": 1774002467},
            },
        }
        snapshot = MODULE.build_profile_snapshot(
            alias="first",
            codex_home=Path("/tmp/.codex-first"),
            payload=payload,
            unavailable=False,
        )
        self.assertEqual(snapshot["email"], "test@example.com")
        self.assertEqual(snapshot["primary_window"]["used_percent"], 61.0)
        self.assertEqual(snapshot["secondary_window"]["used_percent"], 34.0)
        self.assertEqual(snapshot["gated"], "soft-gated")

    def test_fetch_usage_with_retries_attempts_three_times(self):
        logger = _StubLogger()
        attempts = {"count": 0}

        def flaky(_: str):
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise ValueError("temporary failure")
            return {"email": "ok@example.com", "rate_limit": {}}

        with patch.object(MODULE.time, "sleep", return_value=None):
            payload, err = MODULE.fetch_usage_with_retries(
                alias="first",
                access_token="token",
                logger=logger,
                retries=2,
                fetcher=flaky,
            )
        self.assertIsNotNone(payload)
        self.assertIsNone(err)
        self.assertEqual(attempts["count"], 3)

    def test_fetch_usage_with_retries_returns_not_available_after_three_failures(self):
        logger = _StubLogger()
        attempts = {"count": 0}

        def always_fail(_: str):
            attempts["count"] += 1
            raise ValueError("down")

        with patch.object(MODULE.time, "sleep", return_value=None):
            payload, err = MODULE.fetch_usage_with_retries(
                alias="first",
                access_token="token",
                logger=logger,
                retries=2,
                fetcher=always_fail,
            )
        self.assertIsNone(payload)
        self.assertEqual(err, "down")
        self.assertEqual(attempts["count"], 3)

        snapshot = MODULE.build_profile_snapshot(
            alias="first",
            codex_home=Path("/tmp/.codex-first"),
            payload=None,
            unavailable=True,
        )
        self.assertEqual(snapshot["gated"], "not-available")

    def test_reduce_minimal_mode(self):
        reduced = MODULE.reduce_minimal(
            [
                {
                    "alias": "first",
                    "codex_home": "/tmp/.codex-first",
                    "gated": False,
                    "email": "a@example.com",
                }
            ]
        )
        self.assertEqual(reduced, [{"alias": "first", "codex_home": "/tmp/.codex-first", "gated": False}])

    def test_remaining_percent(self):
        self.assertEqual(MODULE.remaining_percent(12.0), 88.0)
        self.assertEqual(MODULE.remaining_percent(112.0), 0.0)
        self.assertEqual(MODULE.remaining_percent(-5.0), 100.0)
        self.assertIsNone(MODULE.remaining_percent(None))

    def test_render_table_headers_and_values(self):
        table = MODULE.render_table(
            [
                {
                    "alias": "first",
                    "email": "a@example.com",
                    "primary_window": {"used_percent": 12.0},
                    "secondary_window": {"used_percent": 34.0},
                },
                {
                    "alias": "second",
                    "email": None,
                    "primary_window": {"used_percent": None},
                    "secondary_window": {"used_percent": 99.0},
                },
            ]
        )
        self.assertIn("alias", table)
        self.assertIn("remaining 5h", table)
        self.assertIn("remaining weekly", table)
        self.assertIn("email", table)
        self.assertIn("88%", table)
        self.assertIn("66%", table)
        self.assertIn("1%", table)
        self.assertIn("n/a", table)


if __name__ == "__main__":
    unittest.main()
