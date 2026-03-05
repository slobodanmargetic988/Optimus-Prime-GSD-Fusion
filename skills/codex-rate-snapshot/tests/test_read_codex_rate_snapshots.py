import importlib.util
import json
import os
import sys
import unittest
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "read_codex_rate_snapshots.py"
SPEC = importlib.util.spec_from_file_location("read_codex_rate_snapshots", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class CodexRateSnapshotTests(unittest.TestCase):
    def test_newest_session_jsonl_uses_last_modified_time(self):
        with TemporaryDirectory() as tmp:
            home = Path(tmp) / ".codex-test"
            d1 = home / "sessions" / "2026" / "03" / "05"
            d2 = home / "sessions" / "2026" / "03" / "06"
            d1.mkdir(parents=True, exist_ok=True)
            d2.mkdir(parents=True, exist_ok=True)
            older = d1 / "older.jsonl"
            newer = d2 / "newer.jsonl"
            older.write_text("{}\n", encoding="utf-8")
            newer.write_text("{}\n", encoding="utf-8")
            os.utime(older, (1000, 1000))
            os.utime(newer, (500, 500))
            # Edit the older-created file later; selector should pick this one.
            os.utime(older, (2000, 2000))
            selected = MODULE.newest_session_jsonl(home)
            self.assertEqual(selected, older)

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

    def test_missing_rate_limits_does_not_hard_gate_profile(self):
        with TemporaryDirectory() as tmp:
            home = Path(tmp) / ".codex-test"
            session_dir = home / "sessions" / "2026" / "03" / "05"
            session_dir.mkdir(parents=True, exist_ok=True)
            session_file = session_dir / "rollout.jsonl"
            session_file.write_text(
                json.dumps(
                    {
                        "timestamp": "2026-03-05T07:37:47.212Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "rate_limits": None,
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            profile = MODULE.build_profile_snapshot(
                alias="test",
                codex_home=home,
                gate_5h=15.0,
                gate_weekly=10.0,
                soft_gate_5h=40.0,
                soft_gate_weekly=25.0,
                wait_max_hours=4.0,
            )
            self.assertEqual(profile.recommended_action, "continue")
            self.assertFalse(profile.soft_concurrency_gated)
            self.assertIn("rate_limits_missing", profile.errors)

    def test_auth_markers_force_wind_down(self):
        with TemporaryDirectory() as tmp:
            home = Path(tmp) / ".codex-test"
            session_dir = home / "sessions" / "2026" / "03" / "05"
            session_dir.mkdir(parents=True, exist_ok=True)
            session_file = session_dir / "rollout.jsonl"
            session_file.write_text(
                json.dumps(
                    {
                        "timestamp": "2026-03-05T07:37:47.212Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "assistant_message",
                            "text": "401 Unauthorized code: refresh_token_reused",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            profile = MODULE.build_profile_snapshot(
                alias="test",
                codex_home=home,
                gate_5h=15.0,
                gate_weekly=10.0,
                soft_gate_5h=40.0,
                soft_gate_weekly=25.0,
                wait_max_hours=4.0,
            )
            self.assertEqual(profile.recommended_action, "wind_down")
            self.assertIn("refresh_token_reused", profile.errors)

    def test_auth_error_then_token_count_recovery_clears_auth_gate(self):
        with TemporaryDirectory() as tmp:
            home = Path(tmp) / ".codex-test"
            session_dir = home / "sessions" / "2026" / "03" / "05"
            session_dir.mkdir(parents=True, exist_ok=True)
            session_file = session_dir / "rollout.jsonl"
            session_file.write_text(
                json.dumps(
                    {
                        "timestamp": "2026-03-05T07:37:47.212Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "assistant_message",
                            "text": "401 Unauthorized code: refresh_token_reused",
                        },
                    }
                )
                + "\n"
                + json.dumps(
                    {
                        "timestamp": "2026-03-05T07:38:47.212Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "rate_limits": {
                                "primary": {"used_percent": 3.0, "resets_at": 1772714191},
                                "secondary": {"used_percent": 1.0, "resets_at": 1773148868},
                            },
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            profile = MODULE.build_profile_snapshot(
                alias="test",
                codex_home=home,
                gate_5h=15.0,
                gate_weekly=10.0,
                soft_gate_5h=40.0,
                soft_gate_weekly=25.0,
                wait_max_hours=4.0,
            )
            self.assertEqual(profile.recommended_action, "continue")
            self.assertIn("refresh_token_reused_resolved", profile.errors)
            self.assertNotIn("refresh_token_reused", profile.errors)

    def test_older_auth_failed_file_does_not_gate_when_newest_file_is_clean(self):
        with TemporaryDirectory() as tmp:
            home = Path(tmp) / ".codex-test"
            old_dir = home / "sessions" / "2026" / "03" / "05"
            new_dir = home / "sessions" / "2026" / "03" / "06"
            old_dir.mkdir(parents=True, exist_ok=True)
            new_dir.mkdir(parents=True, exist_ok=True)
            old_file = old_dir / "old.jsonl"
            new_file = new_dir / "new.jsonl"
            old_file.write_text(
                json.dumps(
                    {
                        "type": "assistant_message",
                        "payload": {"text": "401 Unauthorized code: refresh_token_reused"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            new_file.write_text(
                json.dumps(
                    {
                        "type": "event_msg",
                        "payload": {"type": "token_count", "rate_limits": None},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            os.utime(old_file, (1000, 1000))
            os.utime(new_file, (2000, 2000))

            profile = MODULE.build_profile_snapshot(
                alias="test",
                codex_home=home,
                gate_5h=15.0,
                gate_weekly=10.0,
                soft_gate_5h=40.0,
                soft_gate_weekly=25.0,
                wait_max_hours=4.0,
            )
            self.assertEqual(profile.recommended_action, "continue")
            self.assertNotIn("refresh_token_reused", profile.errors)

    def test_function_call_output_auth_string_does_not_trigger_auth_gate(self):
        with TemporaryDirectory() as tmp:
            home = Path(tmp) / ".codex-test"
            session_dir = home / "sessions" / "2026" / "03" / "05"
            session_dir.mkdir(parents=True, exist_ok=True)
            session_file = session_dir / "rollout.jsonl"
            session_file.write_text(
                json.dumps(
                    {
                        "type": "response_item",
                        "payload": {
                            "type": "function_call_output",
                            "output": "401 Unauthorized code: refresh_token_reused",
                        },
                    }
                )
                + "\n"
                + json.dumps(
                    {
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "rate_limits": {
                                "primary": {"used_percent": 3.0, "resets_at": 1772714191},
                                "secondary": {"used_percent": 1.0, "resets_at": 1773148868},
                            },
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            profile = MODULE.build_profile_snapshot(
                alias="test",
                codex_home=home,
                gate_5h=15.0,
                gate_weekly=10.0,
                soft_gate_5h=40.0,
                soft_gate_weekly=25.0,
                wait_max_hours=4.0,
            )
            self.assertEqual(profile.recommended_action, "continue")
            self.assertNotIn("refresh_token_reused", profile.errors)


if __name__ == "__main__":
    unittest.main()
