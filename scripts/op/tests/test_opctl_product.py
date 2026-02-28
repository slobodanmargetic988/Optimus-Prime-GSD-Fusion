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


def test_resolve_version_uses_install_state_when_running_from_installed_payload(monkeypatch: pytest.MonkeyPatch):
    fake_root = Path("/tmp/fake/.optimus-prime/install/current")
    monkeypatch.setattr(MODULE, "REPO_ROOT", fake_root)
    monkeypatch.setattr(MODULE, "_is_installed_payload_root", lambda _path: True)
    monkeypatch.setattr(
        MODULE,
        "_read_json_silent",
        lambda path: {"installed_version": "9.9.9-rc.1"} if path.name == "INSTALL_STATE.json" else None,
    )
    assert MODULE._resolve_version() == "9.9.9-rc.1"


def test_resolve_version_falls_back_to_manifest_when_install_state_missing(monkeypatch: pytest.MonkeyPatch):
    fake_root = Path("/tmp/fake/.optimus-prime/install/current")
    monkeypatch.setattr(MODULE, "REPO_ROOT", fake_root)
    monkeypatch.setattr(MODULE, "_is_installed_payload_root", lambda _path: True)

    def fake_read(path: Path):
        if path.name == "INSTALL_STATE.json":
            return None
        if path.name == "bundle_manifest.json":
            return {"product_version": "8.8.8-rc.2"}
        return None

    monkeypatch.setattr(MODULE, "_read_json_silent", fake_read)
    assert MODULE._resolve_version() == "8.8.8-rc.2"


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


def test_doctor_command_uses_lifecycle_handler(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    monkeypatch.setattr(
        MODULE,
        "run_doctor",
        lambda payload: {
            "schema_version": "1.0",
            "ok": True,
            "status": "passed",
            "summary": "doctor passed",
            "warnings": [],
            "errors": [],
        },
    )
    monkeypatch.setattr(sys, "argv", ["opctl_product.py", "doctor", "--mode", "global", "--json-pretty"])
    rc = MODULE.main()
    payload = json.loads(capsys.readouterr().out.strip())
    assert rc == 0
    assert payload["status"] == "passed"
