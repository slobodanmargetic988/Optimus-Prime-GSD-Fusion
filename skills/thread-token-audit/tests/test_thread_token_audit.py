import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "thread_token_audit.py"
SPEC = importlib.util.spec_from_file_location("thread_token_audit", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


class ThreadTokenAuditTests(unittest.TestCase):
    def test_audit_summarizes_by_worker_type_and_slot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = root / "reports" / "optimus-prime"

            write_text(
                reports / "THREAD_HISTORY.log",
                "slot | worker type | thread-id\n"
                "dev-1 | developer | 11111111-1111-7111-8111-111111111111\n"
                "test-1 | tester | 22222222-2222-7222-8222-222222222222\n",
            )

            write_json(
                reports / "WORKER_REGISTRY.json",
                {
                    "workers": [
                        {"slot": "dev-1", "codex_profile_alias": "codex"},
                        {"slot": "test-1", "codex_profile_alias": "codex-second"},
                    ]
                },
            )

            codex_home_1 = root / ".codex"
            codex_home_2 = root / ".codex-second"

            session_1 = codex_home_1 / "sessions" / "2026" / "02" / "27" / "rollout-foo-11111111-1111-7111-8111-111111111111.jsonl"
            session_2 = codex_home_2 / "sessions" / "2026" / "02" / "27" / "rollout-bar-22222222-2222-7222-8222-222222222222.jsonl"

            write_text(
                session_1,
                json.dumps(
                    {
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "info": {
                                "total_token_usage": {
                                    "input_tokens": 1000,
                                    "cached_input_tokens": 200,
                                    "output_tokens": 100,
                                    "reasoning_output_tokens": 50,
                                    "total_tokens": 1100,
                                }
                            },
                        },
                    }
                )
                + "\n",
            )
            write_text(
                session_2,
                json.dumps(
                    {
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "info": {
                                "total_token_usage": {
                                    "input_tokens": 2000,
                                    "cached_input_tokens": 500,
                                    "output_tokens": 200,
                                    "reasoning_output_tokens": 70,
                                    "total_tokens": 2200,
                                }
                            },
                        },
                    }
                )
                + "\n",
            )

            inp = MODULE.build_input(
                {
                    "repo_root": str(root),
                    "codex_homes": {
                        "codex": str(codex_home_1),
                        "codex-second": str(codex_home_2),
                    },
                }
            )
            out = MODULE.run(inp)

            self.assertEqual(out["project_total_tokens"], 3300)
            self.assertEqual(out["tokens_by_worker_type"]["developer"], 1100)
            self.assertEqual(out["tokens_by_worker_type"]["tester"], 2200)
            self.assertEqual(out["tokens_by_slot"]["dev-1"], 1100)
            self.assertEqual(out["tokens_by_slot"]["test-1"], 2200)
            self.assertEqual(out["sessions_resolved"], 2)

            self.assertTrue((reports / "THREAD_TOKEN_USAGE_SUMMARY.json").exists())
            self.assertTrue((reports / "THREAD_TOKEN_USAGE_SUMMARY.md").exists())

    def test_unresolved_session_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = root / "reports" / "optimus-prime"

            write_text(
                reports / "THREAD_HISTORY.log",
                "slot | worker type | thread-id\n"
                "review-1 | reviewer | 33333333-3333-7333-8333-333333333333\n",
            )
            write_json(reports / "WORKER_REGISTRY.json", {"workers": []})

            inp = MODULE.build_input(
                {
                    "repo_root": str(root),
                    "codex_homes": {"codex": str(root / ".codex")},
                }
            )
            out = MODULE.run(inp)

            self.assertEqual(out["project_total_tokens"], 0)
            self.assertEqual(out["sessions_tracked"], 1)
            self.assertEqual(out["sessions_unresolved"], 1)
            self.assertIsNone(out["sessions"][0]["session_file"])
            self.assertFalse(out["sessions"][0]["resolved"])


if __name__ == "__main__":
    unittest.main()
