import importlib.util
import json
import sys
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "opctl.py"
SPEC = importlib.util.spec_from_file_location("opctl_cli", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _ok_result(command: str) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "tool": "opctl",
        "tool_version": "0.1.0",
        "ok": True,
        "command": command,
        "status": "completed",
        "summary": "ok",
        "errors": [],
        "warnings": [],
        "artifacts": [],
        "next_action": None,
        "state_ref": None,
    }


def test_build_prints_start_banner_on_tty(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(
        MODULE,
        "run_from_payload",
        lambda payload: _ok_result(str(payload.get("command") or "")),
    )
    monkeypatch.setattr(sys, "argv", ["opctl.py", "--command", "/op-build", "--repo-root", "/tmp/repo", "--json-pretty"])
    monkeypatch.setattr(MODULE.sys.stdout, "isatty", lambda: True)

    rc = MODULE.main()

    out = capsys.readouterr().out
    assert rc == 0
    assert "[opctl] /op-build started for /tmp/repo." in out
    assert "opctl /op-report --repo-root /tmp/repo --json-pretty" in out
    payload = json.loads(out[out.find("{") :].strip())
    assert payload["command"] == "/op-build"


def test_non_build_command_does_not_print_start_banner(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        MODULE,
        "run_from_payload",
        lambda payload: _ok_result(str(payload.get("command") or "")),
    )
    monkeypatch.setattr(sys, "argv", ["opctl.py", "--command", "/op-status", "--repo-root", "/tmp/repo", "--json-pretty"])
    monkeypatch.setattr(MODULE.sys.stdout, "isatty", lambda: True)

    rc = MODULE.main()

    out = capsys.readouterr().out
    assert rc == 0
    assert "[opctl] /op-build started" not in out
    payload = json.loads(out.strip())
    assert payload["command"] == "/op-status"
