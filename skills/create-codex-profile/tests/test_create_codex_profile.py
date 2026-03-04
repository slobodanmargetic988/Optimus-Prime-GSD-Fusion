import importlib.util
import json
import sys
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "create_codex_profile.py"


@pytest.fixture
def mod():
    spec = importlib.util.spec_from_file_location("create_codex_profile", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _seed_source_codex_home(root: Path) -> Path:
    src = root / ".codex"
    src.mkdir()
    (src / "auth.json").write_text('{"user":"a@example.com"}\n', encoding="utf-8")
    (src / "sessions" / "2026" / "03" / "04").mkdir(parents=True)
    (src / "sessions" / "2026" / "03" / "04" / "rollout.jsonl").write_text("{}", encoding="utf-8")
    (src / "skills").mkdir()
    (src / "skills" / "sample").mkdir()
    (src / "agents").mkdir()
    (src / "state_5.sqlite").write_text("sqlite", encoding="utf-8")
    return src


def test_create_profile_copies_sessions_and_auth_and_symlinks_rest(mod, tmp_path):
    source = _seed_source_codex_home(tmp_path)

    out = mod.create_profile(
        source_codex_home=source,
        profile="second",
        target_codex_home=None,
        replace=False,
    )

    assert out["ok"] is True
    target = Path(out["data"]["target_codex_home"])
    assert target.name == ".codex-second"
    assert (target / "auth.json").is_file()
    assert (target / "auth.json").is_symlink() is False
    assert (target / "sessions" / "2026" / "03" / "04" / "rollout.jsonl").is_file()
    assert (target / "sessions").is_symlink() is False

    assert (target / "skills").is_symlink()
    assert (target / "skills").resolve() == (source / "skills").resolve()
    assert (target / "agents").is_symlink()
    assert (target / "state_5.sqlite").is_symlink()


def test_create_profile_profile_name_normalization(mod, tmp_path):
    source = _seed_source_codex_home(tmp_path)

    first = mod.create_profile(source_codex_home=source, profile="third", target_codex_home=None, replace=False)
    assert Path(first["data"]["target_codex_home"]).name == ".codex-third"

    second = mod.create_profile(
        source_codex_home=source,
        profile=".codex-fourth",
        target_codex_home=tmp_path / ".codex-fourth",
        replace=False,
    )
    assert Path(second["data"]["target_codex_home"]).name == ".codex-fourth"


def test_create_profile_requires_replace_when_target_exists(mod, tmp_path):
    source = _seed_source_codex_home(tmp_path)
    target = tmp_path / ".codex-second"
    target.mkdir()
    (target / "old.txt").write_text("old", encoding="utf-8")

    with pytest.raises(mod.ProfileError) as exc_info:
        mod.create_profile(source_codex_home=source, profile="second", target_codex_home=target, replace=False)
    assert exc_info.value.code == "target_exists"

    out = mod.create_profile(source_codex_home=source, profile="second", target_codex_home=target, replace=True)
    assert out["ok"] is True
    assert not (target / "old.txt").exists()


def test_main_json_pretty_output(mod, monkeypatch, capsys, tmp_path):
    source = _seed_source_codex_home(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "create_codex_profile.py",
            "--source-codex-home",
            str(source),
            "--profile",
            "fifth",
            "--json-pretty",
        ],
    )
    exit_code = mod.main()
    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["ok"] is True
    assert payload["data"]["profile_dir_name"] == ".codex-fifth"
