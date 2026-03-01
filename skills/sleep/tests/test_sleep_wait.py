import importlib.util
import sys
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "sleep_wait.py"


@pytest.fixture
def mod():
    spec = importlib.util.spec_from_file_location("sleep_wait", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_duration_compound(mod):
    assert mod.parse_duration("1h30m45s") == 5445


def test_parse_duration_invalid_unit(mod):
    with pytest.raises(ValueError, match="invalid duration syntax"):
        mod.parse_duration("15x")


def test_parse_until_iso_utc(mod):
    _, target = mod.parse_until("2026-03-01T10:00:00Z", "UTC")
    assert target.isoformat() == "2026-03-01T10:00:00+00:00"


def test_main_dry_run_outputs_wait_seconds(mod, monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        ["sleep_wait.py", "--for", "45s", "--dry-run", "--reason", "smoke"],
    )

    exit_code = mod.main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "wait_seconds=45" in captured.out
    assert "dry-run complete" in captured.out


def test_main_max_seconds_refusal(mod, monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        ["sleep_wait.py", "--for", "2m", "--max-seconds", "30"],
    )

    exit_code = mod.main()
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "computed wait 120s exceeds max 30s" in captured.err
