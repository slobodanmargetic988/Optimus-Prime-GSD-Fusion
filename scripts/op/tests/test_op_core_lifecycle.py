import importlib.util
import json
import sys
from pathlib import Path


OP_CORE_PATH = Path(__file__).resolve().parents[1] / "op_core.py"
SPEC = importlib.util.spec_from_file_location("op_core_module", OP_CORE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def make_req(repo_root: Path, **overrides: object):
    payload = {
        "command": "op-initialize",
        "repo_root": repo_root,
        "mission": "Build a playable tetris game.",
        "mission_file": None,
        "scope": "Polish gameplay and finalize UX.",
        "scope_file": None,
        "override_old_plan": False,
        "constraints": [],
        "non_interactive": True,
        "output_mode": "json",
        "max_build_cycles": None,
        "max_parallel_workers": 5,
        "sleep_minutes": 0.0,
        "enable_artifact_fan_in": False,
        "dry_run": True,
        "reset_exhausted_retries": False,
        "run_base_source_branch": "main",
        "boss_model": "gpt-5.3-codex",
        "boss_reasoning_effort": "xhigh",
    }
    payload.update(overrides)
    return MODULE.OpRequest(**payload)


def test_append_app_lifecycle_era_persists_text_and_source_refs(tmp_path: Path) -> None:
    mission_file = tmp_path / "mission.md"
    mission_file.write_text("Mission file body.\n", encoding="utf-8")
    mission_source = {
        "mode": "file",
        "path": str(mission_file),
        "display": f"@file:{mission_file}",
        "value": None,
    }
    scope_source = {
        "mode": "inline",
        "path": None,
        "display": "Inline scope text",
        "value": "Inline scope text",
    }

    era_id, path, warnings = MODULE._append_app_lifecycle_era(
        tmp_path,
        mission_source=mission_source,
        scope_source=scope_source,
        run_base_source_branch="feature/base",
    )

    assert warnings == []
    assert path == (tmp_path / MODULE.APP_LIFECYCLE_JSON).resolve()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.0"
    assert isinstance(payload["app_lifecycle"], list)
    row = payload["app_lifecycle"][-1]
    assert row["era_id"] == era_id
    assert row["status"] == "in_progress"
    assert row["mission"]["text"] == "Mission file body.\n"
    assert row["mission"]["source"]["mode"] == "file"
    assert row["scope"]["text"] == "Inline scope text"
    assert row["scope"]["source"]["mode"] == "inline"
    assert row["run_context"]["run_base_source_branch"] == "feature/base"


def test_command_initialize_creates_lifecycle_entry_and_sets_plan_id(tmp_path: Path, monkeypatch) -> None:
    req = make_req(tmp_path)

    monkeypatch.setattr(MODULE, "_ensure_git_initialized_for_initialize", lambda _req: ([], []))
    monkeypatch.setattr(MODULE, "_ensure_managed_gitignore_block", lambda _repo_root: None)
    monkeypatch.setattr(MODULE, "command_map_codebase", lambda _req: {"warnings": [], "artifacts": []})

    def fake_new_project(_req):
        state_path = MODULE._repo_path(tmp_path, MODULE.STATE_JSON)
        MODULE._atomic_write_json(
            state_path,
            {
                "schema_version": "1.0",
                "initialized_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
                "mission": "Build a playable tetris game.",
                "scope": "Polish gameplay and finalize UX.",
                "mission_source": {"mode": "inline", "value": "Build a playable tetris game.", "path": None, "display": "Build a playable tetris game."},
                "scope_source": {"mode": "inline", "value": "Polish gameplay and finalize UX.", "path": None, "display": "Polish gameplay and finalize UX."},
                "constraints": [],
                "requirements": [],
                "baseline_ready": True,
                "plan_ready": False,
                "build_ready": False,
            },
        )
        return {"warnings": [], "artifacts": [str(state_path)]}

    monkeypatch.setattr(MODULE, "command_new_project", fake_new_project)
    monkeypatch.setattr(MODULE, "_detect_profile_selection_payload", lambda: {"selected_aliases": []})
    monkeypatch.setattr(MODULE, "_seed_rate_registry_if_missing", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        MODULE,
        "command_plan",
        lambda _req: {"warnings": [], "artifacts": [], "data": {"plan_ready": True, "plan_id": "plan-lifecycle-test"}},
    )

    out = MODULE.command_initialize(req)

    assert out["ok"] is True
    lifecycle_path = tmp_path / MODULE.APP_LIFECYCLE_JSON
    assert lifecycle_path.exists()
    payload = json.loads(lifecycle_path.read_text(encoding="utf-8"))
    row = payload["app_lifecycle"][-1]
    assert row["status"] == "in_progress"
    assert row["mission"]["text"] == "Build a playable tetris game."
    assert row["mission"]["source"]["mode"] == "inline"
    assert row["scope"]["text"] == "Polish gameplay and finalize UX."
    assert row["run_context"]["plan_id"] == "plan-lifecycle-test"
