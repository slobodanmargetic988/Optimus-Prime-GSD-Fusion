import importlib.util
import json
import sys
from pathlib import Path

import pytest


SCRIPT_PATH = Path(
    "/Users/slobodan/Projects/Optimus-Prime-GSD-Fusion/skills/workstation-preparation/scripts/prepare_workstation.py"
)


@pytest.fixture
def mod():
    spec = importlib.util.spec_from_file_location("prepare_workstation", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_hydrate_creates_required_symlink_and_state(mod, tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".env").write_text("SECRET=1\n", encoding="utf-8")

    manifest = repo_root / "reports" / "optimus-prime" / "config" / "WORKSTATION_ASSETS.json"
    write_json(
        manifest,
        {
            "assets": [
                {
                    "id": "env",
                    "source": "${REPO_ROOT}/.env",
                    "target": ".env",
                    "mode": "symlink",
                    "required": True,
                    "roles": ["all"],
                }
            ]
        },
    )

    worktree = tmp_path / "wt-1"
    worktree.mkdir()
    state_path = repo_root / "reports" / "optimus-prime" / "WORKSTATION_ASSET_STATE.json"

    result = mod.hydrate_worktree_assets(
        repo_root=repo_root,
        worktree_name="workstation-1",
        worktree_path=worktree,
        slot_role="developer",
        manifest_path=manifest,
        state_path=state_path,
    )

    assert result.ok is True
    target = worktree / ".env"
    assert target.is_symlink()
    assert target.resolve() == (repo_root / ".env").resolve()

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["slots"]["workstation-1"]["ready"] is True


def test_hydrate_missing_required_fails(mod, tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    manifest = repo_root / "reports" / "optimus-prime" / "config" / "WORKSTATION_ASSETS.json"
    write_json(
        manifest,
        {
            "assets": [
                {
                    "id": "env",
                    "source": "${REPO_ROOT}/.env",
                    "target": ".env",
                    "mode": "symlink",
                    "required": True,
                    "roles": ["all"],
                }
            ]
        },
    )

    worktree = tmp_path / "wt-1"
    worktree.mkdir()
    state_path = repo_root / "reports" / "optimus-prime" / "WORKSTATION_ASSET_STATE.json"

    result = mod.hydrate_worktree_assets(
        repo_root=repo_root,
        worktree_name="workstation-1",
        worktree_path=worktree,
        slot_role="developer",
        manifest_path=manifest,
        state_path=state_path,
    )

    assert result.ok is False
    assert result.missing_required
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["slots"]["workstation-1"]["ready"] is False


def test_hydrate_skips_non_matching_role(mod, tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    auth = repo_root / ".myboard" / "auth-state"
    auth.mkdir(parents=True)

    manifest = repo_root / "reports" / "optimus-prime" / "config" / "WORKSTATION_ASSETS.json"
    write_json(
        manifest,
        {
            "assets": [
                {
                    "id": "auth",
                    "source": "${REPO_ROOT}/.myboard/auth-state",
                    "target": ".myboard/auth-state",
                    "mode": "symlink",
                    "required": True,
                    "roles": ["tester"],
                }
            ]
        },
    )

    worktree = tmp_path / "wt-1"
    worktree.mkdir()
    state_path = repo_root / "reports" / "optimus-prime" / "WORKSTATION_ASSET_STATE.json"

    result = mod.hydrate_worktree_assets(
        repo_root=repo_root,
        worktree_name="workstation-1",
        worktree_path=worktree,
        slot_role="developer",
        manifest_path=manifest,
        state_path=state_path,
    )

    assert result.ok is True
    assert not (worktree / ".myboard" / "auth-state").exists()
    assert any(item["status"] == "skipped_role" for item in result.applied_assets)


def test_hydrate_is_idempotent(mod, tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".env").write_text("SECRET=1\n", encoding="utf-8")

    manifest = repo_root / "reports" / "optimus-prime" / "config" / "WORKSTATION_ASSETS.json"
    write_json(
        manifest,
        {
            "assets": [
                {
                    "id": "env",
                    "source": "${REPO_ROOT}/.env",
                    "target": ".env",
                    "mode": "symlink",
                    "required": True,
                    "roles": ["all"],
                }
            ]
        },
    )

    worktree = tmp_path / "wt-1"
    worktree.mkdir()
    state_path = repo_root / "reports" / "optimus-prime" / "WORKSTATION_ASSET_STATE.json"

    first = mod.hydrate_worktree_assets(
        repo_root=repo_root,
        worktree_name="workstation-1",
        worktree_path=worktree,
        slot_role="developer",
        manifest_path=manifest,
        state_path=state_path,
    )
    second = mod.hydrate_worktree_assets(
        repo_root=repo_root,
        worktree_name="workstation-1",
        worktree_path=worktree,
        slot_role="developer",
        manifest_path=manifest,
        state_path=state_path,
    )

    assert first.ok is True
    assert second.ok is True
    assert any(item["status"] == "already_ok" for item in second.applied_assets)
