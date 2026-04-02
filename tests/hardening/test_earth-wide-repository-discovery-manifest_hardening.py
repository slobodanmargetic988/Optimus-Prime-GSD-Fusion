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


def test_req002_hardening_detects_stale_source_artifact_reason_code():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        earth_root = tmp_root / "Users" / "slobodan" / "projects" / "Earth"
        earth_root.mkdir(parents=True, exist_ok=True)

        _seed_repo(earth_root, "Optimus-Prime-GSD-Fusion")
        stale_repo = _seed_repo(earth_root, "Tetris")
        (stale_repo / "mission.md").unlink()
        try:
            (stale_repo / "mission.md").symlink_to("missing-mission-source.md")
        except OSError as exc:
            pytest.skip(f"symlink unavailable in environment: {exc}")

        manifest = sweep.build_earth_repository_discovery_manifest(earth_root, owner_username="slobodan")
        assert sweep.validate_earth_repository_discovery_manifest(manifest) == []

        row = next(item for item in manifest["cross_project_context"] if item["project_id"] == "prj.tetris")
        assert "stale_source_artifact_detected" in row["reason_codes"]
        assert "stale:Tetris/mission.md#stale_source_artifact_detected" in row["evidence_refs"]

        risk = next(item for item in manifest["open_risks"] if item["risk_id"] == "risk.missing-source-refs.prj.tetris")
        assert risk["reason_code"] == "stale_source_artifact_detected"
        for ref in risk["evidence_refs"]:
            assert ref in manifest["evidence_refs"]


def test_req002_hardening_emits_reason_codes_for_missing_docs_and_peer_context():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        earth_root = tmp_root / "Users" / "slobodan" / "projects" / "Earth"
        earth_root.mkdir(parents=True, exist_ok=True)

        _seed_repo(earth_root, "Optimus-Prime-GSD-Fusion")
        _seed_repo(earth_root, "Tetris", mission=True, scope=False)

        manifest = sweep.build_earth_repository_discovery_manifest(earth_root, owner_username="slobodan")
        assert sweep.validate_earth_repository_discovery_manifest(manifest) == []

        missing_risk = next(
            item for item in manifest["open_risks"] if item["risk_id"] == "risk.missing-source-refs.prj.tetris"
        )
        assert missing_risk["reason_code"] == "missing_scope_doc"
        assert missing_risk["missing_source_refs"] == ["scope.md"]

        peer_risk = next(
            item for item in manifest["open_risks"] if item["risk_id"] == "risk.cross-project-obligation-evidence-gap"
        )
        assert peer_risk["reason_code"] == "missing_peer_project_doc"
        for ref in peer_risk["evidence_refs"]:
            assert ref in manifest["evidence_refs"]


def test_req002_hardening_context_bundle_serialization_is_replay_stable():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        earth_root = tmp_root / "Users" / "slobodan" / "projects" / "Earth"
        earth_root.mkdir(parents=True, exist_ok=True)

        _seed_repo(earth_root, "Optimus-Prime-GSD-Fusion")
        _seed_repo(earth_root, "Tetris")

        first_manifest = sweep.build_earth_repository_discovery_manifest(earth_root, owner_username="slobodan")
        second_manifest = sweep.build_earth_repository_discovery_manifest(earth_root, owner_username="slobodan")

        first_bundle = sweep.build_earth_repository_discovery_context_bundle(first_manifest)
        second_bundle = sweep.build_earth_repository_discovery_context_bundle(second_manifest)
        first_serialized = sweep.serialize_earth_repository_discovery_context_bundle(first_bundle)
        second_serialized = sweep.serialize_earth_repository_discovery_context_bundle(second_bundle)

        assert first_bundle == second_bundle
        assert first_serialized == second_serialized
        assert json.loads(first_serialized) == first_bundle
