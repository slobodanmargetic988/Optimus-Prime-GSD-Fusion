import importlib.util
import sys
import unittest
from datetime import timedelta
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "read_codex_rate_snapshots.py"
SPEC = importlib.util.spec_from_file_location("read_codex_rate_snapshots", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class CodexRateSnapshotTests(unittest.TestCase):
    def test_build_window_past_reset_treated_as_refreshed(self):
        past = (MODULE.now_utc() - timedelta(hours=1)).replace(microsecond=0).isoformat()
        window = MODULE.build_window({"used_percent": 95, "resets_at": past}, gate_percent=15.0)
        self.assertEqual(window.used_percent, 0.0)
        self.assertEqual(window.remaining_percent, 100.0)
        self.assertEqual(window.reset_in_hours, 0.0)
        self.assertFalse(window.gated)

    def test_extract_reset_at_accepts_unix_timestamp_values(self):
        now_epoch = int(MODULE.now_utc().timestamp())
        iso = MODULE.extract_reset_at({"resets_at": now_epoch})
        self.assertIsInstance(iso, str)
        parsed = MODULE.parse_iso_datetime(iso)
        self.assertIsNotNone(parsed)


if __name__ == "__main__":
    unittest.main()
