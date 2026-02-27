import importlib.util
import json
import sys
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "opctl_product.py"
SPEC = importlib.util.spec_from_file_location("opctl_product", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_version_command_returns_contract(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    monkeypatch.setattr(sys, "argv", ["opctl_product.py", "version"])
    rc = MODULE.main()
    captured = capsys.readouterr().out.strip()
    payload = json.loads(captured)
    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "completed"
    assert "version" in payload["data"]


def test_unknown_command_returns_structured_error(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    monkeypatch.setattr(sys, "argv", ["opctl_product.py", "unknown-cmd"])
    rc = MODULE.main()
    captured = capsys.readouterr().out.strip()
    payload = json.loads(captured)
    assert rc == 1
    assert payload["ok"] is False
    assert payload["status"] == "failed"
    assert payload["errors"][0]["code"] == "input_error"


def test_workflow_command_delegates_to_opctl(monkeypatch: pytest.MonkeyPatch):
    seen: dict[str, list[str]] = {}

    def fake_run(cmd, cwd, text, capture_output, check):
        seen["cmd"] = cmd

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(MODULE.subprocess, "run", fake_run)
    rc = MODULE._delegate_op_command(["/op-status", "--json-pretty"])
    assert rc == 0
    assert seen["cmd"][0] == "python3"
    assert "--command" in seen["cmd"]
    assert "/op-status" in seen["cmd"]

