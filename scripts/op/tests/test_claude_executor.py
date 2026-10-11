import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import uuid

import pytest


SPEC = importlib.util.spec_from_file_location("claude_executor", Path(__file__).resolve().parents[1] / "claude_executor.py")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


@pytest.fixture
def fake_claude(tmp_path, monkeypatch):
    binary = tmp_path / "fake-claude"
    binary.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys, time\n"
        "from pathlib import Path\n"
        "prompt = sys.stdin.read()\n"
        "Path('invocation.json').write_text(json.dumps({'argv':sys.argv[1:], 'prompt':prompt, 'cwd':os.getcwd(), 'api_key_present':bool(os.environ.get('ANTHROPIC_API_KEY'))}))\n"
        "mode = os.environ.get('FAKE_CLAUDE_MODE', 'ok')\n"
        "if mode == 'timeout': time.sleep(5)\n"
        "if mode == 'invalid': print('not-json'); sys.exit(0)\n"
        "payload = {'type':'result', 'result':'finished', 'session_id':'fb576d3c-602e-49b4-8a3d-5818a13afba7', 'is_error':mode == 'error'}\n"
        "if mode == 'denied': payload['permission_denials'] = [{'tool_name':'Bash'}]\n"
        "print(json.dumps(payload))\n"
        "sys.exit(7 if mode == 'nonzero' else 0)\n",
        encoding="utf-8",
    )
    binary.chmod(0o700)
    monkeypatch.setenv("OP_CLAUDE_BIN", str(binary))
    return binary


def run(tmp_path, **kwargs):
    return MODULE.run_claude_exec(
        repo_root=tmp_path,
        prompt_text="Implement the task; literal `shell` $not_an_expansion",
        output_last_message=tmp_path / "last.txt",
        stdout_path=tmp_path / "stdout.log",
        stderr_path=tmp_path / "stderr.log",
        **kwargs,
    )


def test_real_subprocess_contract_preserves_prompt_and_local_auth(tmp_path, fake_claude, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fixture-not-a-real-key")
    result = run(tmp_path, model="sonnet", reasoning_effort="high")
    invocation = json.loads((tmp_path / "invocation.json").read_text())
    assert result.returncode == 0 and not result.timeout
    assert invocation["prompt"] == "Implement the task; literal `shell` $not_an_expansion"
    assert invocation["cwd"] == str(tmp_path)
    assert invocation["api_key_present"]
    assert "fixture-not-a-real-key" not in json.dumps(invocation)
    assert "sonnet" in invocation["argv"] and "--effort" in invocation["argv"]
    assert "--dangerously-skip-permissions" not in invocation["argv"]
    assert (tmp_path / "last.txt").read_text() == "finished"


@pytest.mark.parametrize("mode,code", [("error", 1), ("nonzero", 7), ("invalid", 1), ("denied", 1)])
def test_errors_cannot_be_reported_as_success(tmp_path, fake_claude, monkeypatch, mode, code):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", mode)
    (tmp_path / "last.txt").write_text("stale success")
    result = run(tmp_path)
    assert result.returncode == code
    assert result.reason_code
    assert "stale success" not in (tmp_path / "last.txt").read_text()


def test_timeout_returns_bounded_failure(tmp_path, fake_claude, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "timeout")
    result = run(tmp_path, timeout_seconds=0.05)
    assert result.returncode == 124 and result.timeout
    assert (tmp_path / "last.txt").read_text() == ""


def test_missing_binary_is_explicit(tmp_path, monkeypatch):
    monkeypatch.setenv("OP_CLAUDE_BIN", str(tmp_path / "missing"))
    result = run(tmp_path)
    assert result.returncode == 127
    assert result.reason_code == "claude_launch_failed"


def test_strategy_uses_selected_claude_cli_and_keeps_provider_model(tmp_path, monkeypatch):
    from scripts.op import op_core as core

    binary = tmp_path / "strategy-claude"
    binary.write_text(
        f"#!{sys.executable}\n"
        "import json, sys\n"
        "from pathlib import Path\n"
        "prompt = sys.stdin.read()\n"
        "Path('invocation.json').write_text(json.dumps({'argv':sys.argv[1:], 'prompt':prompt}))\n"
        "root = Path('strategy/current')\n"
        "root.mkdir(parents=True, exist_ok=True)\n"
        "(root/'strategy_packet.md').write_text('# Fixture strategy\\n')\n"
        "(root/'STRATEGY_SUMMARY.md').write_text('# Fixture summary\\n')\n"
        "print(json.dumps({'type':'result', 'result':'Strategy written', 'is_error':False}))\n",
        encoding="utf-8",
    )
    binary.chmod(0o700)
    monkeypatch.setenv("OP_CLAUDE_BIN", str(binary))
    monkeypatch.setattr(core, "run_codex_exec", lambda **_: pytest.fail("Claude strategy must not invoke Codex"))
    monkeypatch.setattr(core.strategy_runner, "run_codex_exec", lambda **_: pytest.fail("Strategy must use the selected executor"))
    req = core.parse_request({
        "command": "/op-strategy", "repo_root": str(tmp_path),
        "strategy_manifest": "Build a local project with one deliverable.",
        "executor_provider": "claude", "executor_model": "sonnet",
    })
    result = core.command_strategy(req)
    assert result["ok"]
    invocation = json.loads((tmp_path / "invocation.json").read_text())
    assert "sonnet" in invocation["argv"]
    assert "Build a local project with one deliverable." in invocation["prompt"]
    assert (tmp_path / "strategy/current/strategy_packet.md").read_text() == "# Fixture strategy\n"


def test_resume_uses_specific_session(tmp_path, fake_claude):
    session = str(uuid.uuid4())
    result = run(tmp_path, resume_session_id=session)
    invocation = json.loads((tmp_path / "invocation.json").read_text())
    assert invocation["argv"][-2:] == ["--resume", session]
    assert result.session_id


def test_background_worker_receives_prompt_and_session(tmp_path, fake_claude):
    launched = MODULE.launch_claude_background(repo_root=tmp_path, prompt_text="worker task", stdout_path=tmp_path / "worker.log", model="opus")
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not (tmp_path / "worker.log").read_text().strip():
            time.sleep(0.01)
        invocation = json.loads((tmp_path / "invocation.json").read_text())
        assert invocation["prompt"] == "worker task"
        assert invocation["argv"][-2:] == ["--session-id", launched.session_id]
        assert launched.pid > 0
        assert json.loads((tmp_path / "worker.log").read_text())["type"] == "result"
    finally:
        try:
            os.waitpid(launched.pid, 0)
        except ChildProcessError:
            pass


@pytest.fixture
def runtime():
    spec = importlib.util.spec_from_file_location("op_simple_build_claude_test", Path(__file__).resolve().parents[1] / "op_simple_build.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def claude_config(runtime, root):
    return runtime.RunConfig(repo_root=root, sleep_minutes=0, max_build_cycles=1, max_parallel_workers=2, dry_run=False, worktrees_parent=root, executor_provider="claude", codex_profile="must-not-use-codex", boss_reasoning_effort="high")


@pytest.mark.parametrize("manager", ["BOSS", "merge-manager", "wrapup-manager"])
def test_claude_managers_route_to_real_cli_without_codex_profiles(tmp_path, fake_claude, monkeypatch, runtime, manager):
    cfg = claude_config(runtime, tmp_path)
    runtime._ensure_default_artifacts(cfg)
    monkeypatch.setattr(runtime, "_load_prompt_template", lambda *_: "Perform the local task.")
    monkeypatch.setattr(runtime, "_codex_exec_prompt", lambda *a, **k: pytest.fail("Claude must not invoke Codex"))
    monkeypatch.setattr(runtime, "_blackbox_exec_prompt", lambda *a, **k: pytest.fail("Claude must not invoke Blackbox"))
    monkeypatch.setattr(runtime, "_refresh_profile_snapshot_via_skill", lambda *a, **k: pytest.fail("Claude must not query Codex quotas"))
    result = runtime._invoke_manager(cfg, manager_name=manager, cycle_number=1, context={}, expected_artifacts=[])
    assert result.status == "ok"
    invocation = json.loads((tmp_path / "invocation.json").read_text())
    assert "gpt-5.3-codex" not in invocation["argv"]
    assert "--model" not in invocation["argv"]
    assert '"provider": "claude"' in invocation["prompt"]
    rows = [json.loads(row) for row in (tmp_path / runtime.MANAGER_CALL_LOG_FILE).read_text().splitlines()]
    assert rows[-1]["executor_provider"] == "claude"
    assert rows[-1]["profile_alias"] is None


def test_claude_ignores_stale_codex_quota_and_profile_mode(tmp_path, runtime):
    cfg = claude_config(runtime, tmp_path)
    runtime._atomic_write_json(tmp_path / runtime.ARTIFACT_FILES["profile_snapshot"], {"profiles":[{"alias":"codex", "hard_gated":True}]})
    assert not runtime._llm_profile_mode_enabled(cfg)
    assert runtime._evaluate_rate_exhaustion_state(cfg).outcome == "has_capacity"
    assert runtime._bootstrap_profile_snapshot_before_first_boss(cfg, cycle_number=2)[0]
    snapshot = json.loads((tmp_path / runtime.ARTIFACT_FILES["profile_snapshot"]).read_text())
    assert snapshot["provider"] == "claude"
    assert snapshot["quota_status"] == "provider_managed_unknown"
    assert snapshot["profiles"][0]["alias"] == "claude-local"


def test_claude_worker_dispatch_updates_real_provider_and_pid(tmp_path, fake_claude, monkeypatch, runtime):
    cfg = claude_config(runtime, tmp_path)
    worktree = tmp_path / "worker-1"
    worktree.mkdir()
    runtime._atomic_write_json(tmp_path / runtime.ARTIFACT_FILES["worker_packets"], {"packets":[{"worker_id":"worker-1", "packet_id":"packet-1", "profile_alias":"claude-local", "prompt":"implement worker packet"}]})
    runtime._atomic_write_json(tmp_path / runtime.ARTIFACT_FILES["worker_registry"], {"workers":[{"worker_id":"worker-1", "worktree":str(worktree), "status":"idle"}]})
    monkeypatch.setattr(runtime, "_resolve_dispatch_script", lambda *_: None)
    monkeypatch.setattr(runtime, "_launch_blackbox_dispatch", lambda *a, **k: pytest.fail("Claude must not launch Blackbox"))
    result = runtime._dispatch_packets(cfg, cycle_number=1)
    assert result["launched"] == 1
    worker = json.loads((tmp_path / runtime.ARTIFACT_FILES["worker_registry"]).read_text())["workers"][0]
    try:
        deadline = time.monotonic() + 5
        invocation = worktree / "invocation.json"
        while time.monotonic() < deadline and not invocation.exists():
            time.sleep(0.01)
        assert json.loads(invocation.read_text())["prompt"] == "implement worker packet"
        assert worker["current_task_provider"] == "claude"
        assert worker["pid"] > 0
        assert worker["thread_id"]
    finally:
        try:
            os.waitpid(worker["pid"], 0)
        except ChildProcessError:
            pass
