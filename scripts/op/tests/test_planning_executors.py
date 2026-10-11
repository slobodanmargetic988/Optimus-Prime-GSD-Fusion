"""Selected providers must also own planning, without hidden subscription dependencies."""

from types import SimpleNamespace

import pytest

from scripts.op import op_core as core


def _paths(root):
    return dict(prompt_text="Plan this", output_last_message=root / "last.txt", stdout_path=root / "out.log", stderr_path=root / "err.log")


def test_claude_planning_routes_without_codex(monkeypatch, tmp_path):
    import claude_executor
    captured = {}
    def run(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(claude_executor, "run_claude_exec", run)
    monkeypatch.setattr(core, "run_codex_exec", lambda **_: pytest.fail("Codex must not run"))
    req = core.parse_request({"command": "/op-plan", "repo_root": str(tmp_path), "executor_provider": "claude", "executor_model": "sonnet"})
    assert core._run_planning_executor(req, codex_home="/unused", **_paths(tmp_path)) == 0
    assert captured["model"] == "sonnet"
    assert "codex_home" not in captured


@pytest.mark.parametrize("provider", ["codex", "openrouter"])
def test_api_planner_honors_profile_model_and_isolated_home(monkeypatch, tmp_path, provider):
    captured = {}
    def run(**kwargs):
        captured.update(kwargs)
        return 0
    monkeypatch.setattr(core, "run_codex_exec", run)
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "provider config"))
    req = core.parse_request({"command": "/op-plan", "repo_root": str(tmp_path), "executor_provider": provider, "profile": "optimus-desktop", "executor_model": "chosen-model"})
    assert core._run_planning_executor(req, codex_home="/unrelated-subscription", **_paths(tmp_path)) == 0
    assert captured["codex_home"] == str(tmp_path / "provider config")
    assert captured["codex_profile"] == "optimus-desktop"
    assert captured["model"] == "chosen-model"


@pytest.mark.parametrize("settings", [{"executor_provider": "claude"}, {"executor_provider": "codex", "profile": "optimus-desktop"}])
def test_initialize_plans_without_scanning_codex_accounts(monkeypatch, tmp_path, settings):
    monkeypatch.setattr(core, "_detect_profile_selection_payload", lambda: pytest.fail("Subscription discovery must not run"))
    monkeypatch.setattr(core, "_seed_rate_registry_if_missing", lambda *a, **k: pytest.fail("Subscription rate probing must not run"))
    monkeypatch.setattr(core, "_ensure_git_initialized_for_initialize", lambda req: ([], []))
    monkeypatch.setattr(core, "_run_llm_plan_generation", lambda req, **kw: ({"plan_packets": {"plan_id": "small-plan", "tasks": [{"task_id": "one"}], "phases": [], "requirements": []}, "recomputed_plan_check": {"passed": True}}, [], []))
    req = core.parse_request({"command": "/op-initialize", "repo_root": str(tmp_path), "mission": "Small local project", "scope": "One feature", "max_plan_tasks": 1, "skip_strategy": True, **settings})
    result = core.command_initialize(req)
    assert result["ok"]
    assert result["data"]["plan_ready"]
    assert not (tmp_path / ".op-simple").exists()
    state = core._read_json(tmp_path / core.STATE_JSON)
    assert state["max_plan_tasks"] == 1
    selected = core._load_profile_selection_required(tmp_path, stage="test")
    assert selected["selected_aliases"] == []


def test_free_blackbox_not_used_for_high_effort_planning(tmp_path):
    req = core.parse_request({"command": "/op-plan", "repo_root": str(tmp_path), "executor_provider": "blackbox"})
    with pytest.raises(OSError, match="API-key lane"):
        core._run_planning_executor(req, **_paths(tmp_path))


def test_validator_command_quotes_space_in_project_path(tmp_path):
    project = tmp_path / "my project"
    project.mkdir()
    req = core.parse_request({"command": "/op-plan", "repo_root": str(project), "max_plan_tasks": 4})
    prompt = core._planner_prompt_text(req=req, bundle_path=project / "bundle.jsonl", mission_source={}, scope_source={}, prior_errors=[])
    import shlex
    command = next(line for line in prompt.splitlines() if "--bundle-path" in line and "validate_plan_bundle.py" in line)
    args = shlex.split(command)
    assert args[args.index("--repo-root") + 1] == str(project)
    assert args[args.index("--max-plan-tasks") + 1] == "4"
