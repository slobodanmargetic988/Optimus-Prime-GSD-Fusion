import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "dispatch_codex_run.py"
)


@pytest.fixture
def mod():
    spec = importlib.util.spec_from_file_location("dispatch_codex_run", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_load_prompt_requires_exactly_one_source(mod):
    with pytest.raises(ValueError, match="exactly one"):
        mod.load_prompt(SimpleNamespace(prompt=None, prompt_file=None))

    with pytest.raises(ValueError, match="exactly one"):
        mod.load_prompt(SimpleNamespace(prompt="x", prompt_file="y"))


def test_load_prompt_from_file(mod, tmp_path):
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("hello world\n", encoding="utf-8")
    value = mod.load_prompt(SimpleNamespace(prompt=None, prompt_file=str(prompt_file)))
    assert value == "hello world"


def test_effective_codex_home_precedence(mod, monkeypatch, tmp_path):
    explicit = tmp_path / ".codex-explicit"
    env_home = tmp_path / ".codex-env"
    monkeypatch.setenv("CODEX_HOME", str(env_home))

    result = mod.effective_codex_home(SimpleNamespace(codex_home=str(explicit)))
    assert result == explicit.resolve()


def test_resolve_mcp_disable_overrides_enable_only(mod, tmp_path):
    codex_home = tmp_path / ".codex"
    codex_home.mkdir(parents=True)
    config = codex_home / "config.toml"
    config.write_text(
        """
[mcp_servers.alpha]
command = "alpha"

[mcp_servers.beta]
command = "beta"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    args = SimpleNamespace(
        enable_only_mcp=["alpha"],
        disable_all_mcp=False,
        codex_home=str(codex_home),
    )
    overrides, meta = mod.resolve_mcp_disable_overrides(args)

    assert overrides == ["mcp_servers.beta.enabled=false"]
    assert meta["mcp_mode"] == "enable_only"
    assert meta["mcp_servers_enabled"] == ["alpha"]
    assert meta["mcp_servers_disabled"] == ["beta"]


def test_build_command_resume_path(mod):
    args = SimpleNamespace(
        resume_session_id="123e4567-e89b-12d3-a456-426614174000",
        cwd="/tmp/work",
        extra_arg=["--json"],
    )

    cmd = mod.build_command(
        args,
        "continue task",
        mcp_disable_overrides=["mcp_servers.foo.enabled=false"],
    )

    assert cmd[:3] == ["codex", "resume", args.resume_session_id]
    assert "--cd" in cmd
    assert "continue task" == cmd[-1]
    assert "--json" in cmd


def test_main_dry_run_background_json_payload(mod, monkeypatch, capsys, tmp_path):
    cwd = tmp_path / "workspace"
    cwd.mkdir()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "dispatch_codex_run.py",
            "--cwd",
            str(cwd),
            "--prompt",
            "Do work",
            "--dry-run",
        ],
    )

    exit_code = mod.main()
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["mode"] == "background"
    assert payload["cwd"] == str(cwd.resolve())
    assert payload["command"][0:2] == ["codex", "exec"]


def test_main_dry_run_resume_payload(mod, monkeypatch, capsys, tmp_path):
    cwd = tmp_path / "workspace"
    cwd.mkdir()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "dispatch_codex_run.py",
            "--cwd",
            str(cwd),
            "--prompt",
            "Continue work",
            "--resume-session-id",
            "123e4567-e89b-12d3-a456-426614174000",
            "--dry-run",
        ],
    )

    exit_code = mod.main()
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["command"][0:2] == ["codex", "resume"]


def test_wait_for_session_id_reads_log(mod, tmp_path):
    log_path = tmp_path / "dispatch.log"
    log_path.write_text(
        "some logs\nSession ID: 123e4567-e89b-12d3-a456-426614174000\n",
        encoding="utf-8",
    )

    session_id = mod.wait_for_session_id(log_path, timeout_seconds=0.2)
    assert session_id == "123e4567-e89b-12d3-a456-426614174000"
