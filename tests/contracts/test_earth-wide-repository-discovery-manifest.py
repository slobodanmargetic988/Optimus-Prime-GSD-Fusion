import json
import tempfile
from pathlib import Path

import pytest

from scripts import strategy_context_sweep as sweep


def _seed_repo(parent: Path, name: str, *, mission: bool = True, scope: bool = True) -> Path:
    repo = parent / name
    repo.mkdir(parents=True, exist_ok=True)
    (repo / ".git").mkdir(parents=True, exist_ok=True)
    if mission:
        (repo / "mission.md").write_text(f"# Mission for {name}\n", encoding="utf-8")
    if scope:
        (repo / "scope.md").write_text(f"# Scope for {name}\n", encoding="utf-8")
    return repo


def test_req002_manifest_discovery_contract_and_stability():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        earth_root = tmp_root / "Users" / "slobodan" / "projects" / "Earth"
        earth_root.mkdir(parents=True, exist_ok=True)

        _seed_repo(earth_root, "Tetris")
        _seed_repo(earth_root, "Optimus-Prime-GSD-Fusion")
        _seed_repo(earth_root, "archives")

        (earth_root / "ScratchFolder").mkdir(parents=True, exist_ok=True)

        hidden = earth_root / ".hidden-repo"
        hidden.mkdir(parents=True, exist_ok=True)
        (hidden / ".git").mkdir(parents=True, exist_ok=True)

        outside_repo = _seed_repo(tmp_root / "outside", "ForeignRepo")
        link_path = earth_root / "foreign-link"
        try:
            link_path.symlink_to(outside_repo, target_is_directory=True)
        except OSError as exc:
            pytest.skip(f"symlink unavailable in environment: {exc}")

        first = sweep.build_earth_repository_discovery_manifest(earth_root, owner_username="slobodan")
        second = sweep.build_earth_repository_discovery_manifest(earth_root, owner_username="slobodan")

        assert first == second

        errors = sweep.validate_earth_repository_discovery_manifest(first)
        assert errors == []

        project_ids = [row["project_id"] for row in first["projects"]]
        assert project_ids == ["prj.optimus-prime-gsd-fusion", "prj.tetris"]

        source_refs = {row["project_id"]: row["source_refs"] for row in first["projects"]}
        assert source_refs["prj.optimus-prime-gsd-fusion"] == {"mission": "mission.md", "scope": "scope.md"}
        assert source_refs["prj.tetris"] == {"mission": "mission.md", "scope": "scope.md"}

        assert first["broad_sweep_inputs"]["discovered_project_ids"] == [
            "prj.optimus-prime-gsd-fusion",
            "prj.tetris",
        ]
        assert first["broad_sweep_inputs"]["source_ref_coverage"] == {
            "project_count": 2,
            "complete_project_count": 2,
            "partial_project_count": 0,
            "mission_ref_count": 2,
            "scope_ref_count": 2,
        }

        exclusion_map = {(row["path"], row["reason_code"]) for row in first["excluded_paths"]}
        assert ("archives", "exclude_archived_path") in exclusion_map
        assert ("ScratchFolder", "exclude_non_repository_path") in exclusion_map
        assert (".hidden-repo", "exclude_hidden_path") in exclusion_map
        assert ("foreign-link", "exclude_non_owner_path") in exclusion_map

        assert first["evidence_refs"] == sorted(set(first["evidence_refs"]))
        cross_project_context = {row["project_id"]: row for row in first["cross_project_context"]}
        assert sorted(cross_project_context.keys()) == ["prj.optimus-prime-gsd-fusion", "prj.tetris"]
        assert cross_project_context["prj.optimus-prime-gsd-fusion"]["context_status"] == "complete"
        assert cross_project_context["prj.tetris"]["context_status"] == "complete"

        recommendation = first["recommendation"]
        assert recommendation["decision"] == "ready_for_cross_project_planning"
        assert recommendation["context_project_ids"] == ["prj.optimus-prime-gsd-fusion", "prj.tetris"]
        assert recommendation["evidence_refs"]
        assert recommendation["action_items"]
        obligations = recommendation["proposed_cross_project_obligations"]
        assert len(obligations) == 1
        assert obligations[0]["evidence_refs"]
        assert first["open_risks"] == []

        assert first["stats"] == {"project_count": 2, "excluded_path_count": len(first["excluded_paths"])}


def test_req002_fixture_and_sample_validate_against_contract():
    repo_root = Path(__file__).resolve().parents[2]
    fixture_path = repo_root / "examples" / "fixtures" / "earth-wide-repository-discovery-manifest.json"
    sample_path = repo_root / "strategy" / "current" / "samples" / "REQ-002_earth-wide-repository-discovery-manifest.sample.json"

    fixture_payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    sample_payload = json.loads(sample_path.read_text(encoding="utf-8"))

    assert sweep.validate_earth_repository_discovery_manifest(fixture_payload) == []
    assert sweep.validate_earth_repository_discovery_manifest(sample_payload) == []

    assert set(fixture_payload.keys()) == set(sample_payload.keys())


def test_req002_contract_doc_references_sample_structure():
    repo_root = Path(__file__).resolve().parents[2]
    contract_path = repo_root / "contracts" / "req" / "REQ-002_earth-wide-repository-discovery-manifest.md"
    contract_text = contract_path.read_text(encoding="utf-8")

    assert "strategy/current/samples/REQ-002_earth-wide-repository-discovery-manifest.sample.json" in contract_text
