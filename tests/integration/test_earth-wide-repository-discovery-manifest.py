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


def test_req002_integration_enforces_evidence_backed_reasoning_fields():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        earth_root = tmp_root / "Users" / "slobodan" / "projects" / "Earth"
        earth_root.mkdir(parents=True, exist_ok=True)

        _seed_repo(earth_root, "Optimus-Prime-GSD-Fusion")
        _seed_repo(earth_root, "Tetris", mission=True, scope=False)
        _seed_repo(earth_root, "archives")
        (earth_root / "ScratchFolder").mkdir(parents=True, exist_ok=True)

        outside_repo = _seed_repo(tmp_root / "outside", "ForeignRepo")
        link_path = earth_root / "foreign-link"
        try:
            link_path.symlink_to(outside_repo, target_is_directory=True)
        except OSError as exc:
            pytest.skip(f"symlink unavailable in environment: {exc}")

        manifest = sweep.build_earth_repository_discovery_manifest(earth_root, owner_username="slobodan")
        assert sweep.validate_earth_repository_discovery_manifest(manifest) == []

        evidence_refs = manifest["evidence_refs"]
        assert evidence_refs == sorted(set(evidence_refs))
        assert "Optimus-Prime-GSD-Fusion/mission.md" in evidence_refs
        assert "excluded:foreign-link#exclude_non_owner_path" in evidence_refs

        recommendation = manifest["recommendation"]
        assert recommendation["decision"] == "needs_evidence_backfill"
        assert recommendation["rationale"]
        assert recommendation["evidence_refs"]
        assert recommendation["action_items"]
        assert recommendation["proposed_cross_project_obligations"] == []

        cross_project_context = {row["project_id"]: row for row in manifest["cross_project_context"]}
        assert cross_project_context["prj.optimus-prime-gsd-fusion"]["context_status"] == "complete"
        assert cross_project_context["prj.tetris"]["context_status"] == "partial"
        for row in cross_project_context.values():
            assert row["evidence_refs"]

        open_risks = manifest["open_risks"]
        risk_ids = {row["risk_id"] for row in open_risks}
        assert "risk.cross-project-obligation-evidence-gap" in risk_ids
        assert "risk.missing-source-refs.prj.tetris" in risk_ids
        for row in open_risks:
            assert row["evidence_refs"]


def test_req002_integration_cross_project_obligations_require_evidence_refs():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        earth_root = tmp_root / "Users" / "slobodan" / "projects" / "Earth"
        earth_root.mkdir(parents=True, exist_ok=True)

        _seed_repo(earth_root, "Optimus-Prime-GSD-Fusion")
        _seed_repo(earth_root, "Tetris")

        manifest = sweep.build_earth_repository_discovery_manifest(earth_root, owner_username="slobodan")
        assert sweep.validate_earth_repository_discovery_manifest(manifest) == []

        recommendation = manifest["recommendation"]
        assert recommendation["decision"] == "ready_for_cross_project_planning"
        obligations = recommendation["proposed_cross_project_obligations"]
        assert obligations
        for obligation in obligations:
            assert obligation["evidence_refs"]
            for ref in obligation["evidence_refs"]:
                assert ref in manifest["evidence_refs"]
