import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "dispatch_codex_desktop_thread.py"
)


@pytest.fixture
def mod():
    spec = importlib.util.spec_from_file_location(
        "dispatch_codex_desktop_thread",
        SCRIPT_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_load_prompt_requires_exactly_one_source(mod):
    with pytest.raises(ValueError, match="exactly one"):
        mod.load_prompt(SimpleNamespace(prompt=None, prompt_file=None))

    with pytest.raises(ValueError, match="exactly one"):
        mod.load_prompt(SimpleNamespace(prompt="hello", prompt_file="x.txt"))


def test_load_prompt_from_file(mod, tmp_path):
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("run workflow\n", encoding="utf-8")

    prompt = mod.load_prompt(SimpleNamespace(prompt=None, prompt_file=str(prompt_file)))
    assert prompt == "run workflow"


def test_main_dry_run_prints_osascript_command(mod, monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "dispatch_codex_desktop_thread.py",
            "--prompt",
            "Test prompt",
            "--dry-run",
            "--no-send",
        ],
    )

    exit_code = mod.main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.startswith("osascript -e ")
    assert "Test prompt" in captured.out
    assert captured.out.strip().split()[-1] in {"0", "'0'"}


def test_main_fails_for_missing_prompt_file(mod, monkeypatch, capsys, tmp_path):
    missing = tmp_path / "missing.txt"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "dispatch_codex_desktop_thread.py",
            "--prompt-file",
            str(missing),
        ],
    )

    exit_code = mod.main()
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "prompt_file_not_found" in captured.err
