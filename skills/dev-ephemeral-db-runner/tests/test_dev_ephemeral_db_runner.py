import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "dev_ephemeral_db_runner.py"
SPEC = importlib.util.spec_from_file_location("dev_ephemeral_db_runner", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FakeRunner(MODULE.CommandRunner):
    def __init__(self, *, port_occupied: bool = False, invalid_dynamic_shm_once: bool = False):
        self.running = False
        self.dbs = set()
        self.port_occupied = port_occupied
        self.invalid_dynamic_shm_once = invalid_dynamic_shm_once
        self.calls = []

    def run(self, cmd):
        self.calls.append(cmd)
        exe = Path(cmd[0]).name

        if exe == "initdb":
            pgdata = Path(cmd[2])
            pgdata.mkdir(parents=True, exist_ok=True)
            (pgdata / "PG_VERSION").write_text("16\n", encoding="utf-8")
            return MODULE.CmdResult(0, "", "")

        if exe == "pg_ctl":
            action = cmd[-1]
            if action == "status":
                return MODULE.CmdResult(0 if self.running else 3, "running" if self.running else "", "")
            if action == "start":
                if self.invalid_dynamic_shm_once:
                    self.invalid_dynamic_shm_once = False
                    if "-l" in cmd:
                        log_path = Path(cmd[cmd.index("-l") + 1])
                        log_path.parent.mkdir(parents=True, exist_ok=True)
                        log_path.write_text(
                            'FATAL:  invalid value for parameter "dynamic_shared_memory_type": "none"\n'
                            "HINT:  Available values: posix, sysv, mmap.\n",
                            encoding="utf-8",
                        )
                    return MODULE.CmdResult(1, "", "pg_ctl: could not start server\nExamine the log output.")
                if self.port_occupied:
                    return MODULE.CmdResult(1, "", "address already in use")
                self.running = True
                return MODULE.CmdResult(0, "server starting", "")
            if action == "fast":
                self.running = False
                return MODULE.CmdResult(0, "server stopped", "")

        if exe == "pg_isready":
            return MODULE.CmdResult(0 if self.running else 1, "ready" if self.running else "not ready", "")

        if exe == "createdb":
            db_name = cmd[-1]
            if db_name in self.dbs:
                return MODULE.CmdResult(1, "", "already exists")
            self.dbs.add(db_name)
            return MODULE.CmdResult(0, "", "")

        return MODULE.CmdResult(0, "", "")


def fake_which(binary: str) -> str | None:
    paths = {
        "initdb": "/usr/local/bin/initdb",
        "pg_ctl": "/usr/local/bin/pg_ctl",
        "createdb": "/usr/local/bin/createdb",
        "pg_isready": "/usr/local/bin/pg_isready",
    }
    return paths.get(binary)


def missing_which(binary: str) -> str | None:
    return None


def cfg(root: Path, **overrides):
    return MODULE.RunnerInput(
        action=overrides.get("action", "start"),
        profile_name=overrides.get("profile_name", "myo-160"),
        port=overrides.get("port", 55432),
        db_name=overrides.get("db_name", "myboard_test_v2"),
        host=overrides.get("host", "127.0.0.1"),
        cleanup_mode=overrides.get("cleanup_mode", "preserve"),
        shared_memory_compat=overrides.get("shared_memory_compat", True),
        dry_run=overrides.get("dry_run", False),
        base_dir=overrides.get("base_dir", root / "db-profile"),
    )


class DevEphemeralDbRunnerTests(unittest.TestCase):
    def test_parse_and_dsn(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = type("Args", (), {
                "input_json": None,
                "action": "start",
                "profile_name": "myo-160",
                "port": 55432,
                "db_name": "myboard_test_v2",
                "host": "127.0.0.1",
                "cleanup_mode": "preserve",
                "shared_memory_compat": True,
                "dry_run": False,
                "base_dir": str(Path(tmp) / "x"),
            })
            parsed = MODULE.parse_config(args)
            self.assertEqual(parsed.profile_name, "myo-160")
            self.assertEqual(MODULE.dsn_sqlalchemy("127.0.0.1", 55432, "mydb"), "postgresql+psycopg2://postgres@127.0.0.1:55432/mydb")

    def test_start_ready_stop_cycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner = FakeRunner()
            start_cfg = cfg(root, action="start", cleanup_mode="preserve")
            out_start = MODULE.run(start_cfg, runner=runner, which_fn=fake_which)

            self.assertTrue(out_start["ok"])
            self.assertTrue(out_start["started"])
            self.assertEqual(out_start["profile_name"], "myo-160")
            self.assertTrue((start_cfg.base_dir / "state.json").exists())

            stop_cfg = cfg(root, action="stop", cleanup_mode="destroy_on_exit", base_dir=start_cfg.base_dir)
            out_stop = MODULE.run(stop_cfg, runner=runner, which_fn=fake_which)

            self.assertTrue(out_stop["ok"])
            self.assertFalse(out_stop["started"])
            self.assertTrue(out_stop["stopped"])
            self.assertFalse(start_cfg.base_dir.exists())

    def test_idempotent_repeated_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner = FakeRunner()
            c = cfg(root, action="start")
            out1 = MODULE.run(c, runner=runner, which_fn=fake_which)
            out2 = MODULE.run(c, runner=runner, which_fn=fake_which)

            self.assertTrue(out1["ok"])
            self.assertTrue(out2["ok"])
            warn_codes = {w["code"] for w in out2["warnings"]}
            self.assertIn("already_running", warn_codes)

            start_calls = [call for call in runner.calls if Path(call[0]).name == "pg_ctl" and call[-1] == "start"]
            self.assertEqual(len(start_calls), 1)

    def test_failure_occupied_port(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner = FakeRunner(port_occupied=True)
            c = cfg(root, action="start")
            with self.assertRaises(MODULE.ToolError) as ctx:
                MODULE.run(c, runner=runner, which_fn=fake_which)
            self.assertEqual(ctx.exception.code, "port_occupied")

    def test_failure_missing_binaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = cfg(Path(tmp), action="start")
            with self.assertRaises(MODULE.ToolError) as ctx:
                MODULE.run(c, runner=FakeRunner(), which_fn=missing_which)
            self.assertEqual(ctx.exception.code, "missing_binaries")

    def test_shared_memory_compat_fallback_when_none_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner = FakeRunner(invalid_dynamic_shm_once=True)
            c = cfg(root, action="start", shared_memory_compat=True)
            out = MODULE.run(c, runner=runner, which_fn=fake_which)

            self.assertTrue(out["ok"])
            warn_codes = {w["code"] for w in out["warnings"]}
            self.assertIn("shared_memory_compat_fallback", warn_codes)

            start_calls = [call for call in runner.calls if Path(call[0]).name == "pg_ctl" and call[-1] == "start"]
            self.assertEqual(len(start_calls), 2)
            self.assertIn("dynamic_shared_memory_type=none", " ".join(start_calls[0]))
            self.assertIn("dynamic_shared_memory_type=mmap", " ".join(start_calls[1]))

    def test_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = cfg(Path(tmp), action="start", dry_run=True)
            out = MODULE.run(c, runner=FakeRunner(), which_fn=missing_which)
            self.assertTrue(out["ok"])
            self.assertTrue(any(w["code"] == "dry_run" for w in out["warnings"]))


if __name__ == "__main__":
    unittest.main()
