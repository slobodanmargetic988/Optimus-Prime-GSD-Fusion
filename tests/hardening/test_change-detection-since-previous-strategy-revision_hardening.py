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


def _build_revision_pair(manifest: dict) -> tuple[dict, dict]:
    previous_revision = {
        "revision_id": "strategy-2026-03-14T08:00:00Z",
        "mission_scope": {"primary_objective": "Stabilize planner reliability", "constraints": {"task_floor": 400}},
        "runtime_data": {"runtime_mode": "shared", "queue_backlog": 2, "blocked_cycles": 0},
        "ecosystem_signals": {"upstream_projects": [{"project_id": "prj.tetris", "signal": "stable"}]},
        "recommendations": [
            {
                "recommendation_id": "rec.scope-refresh",
                "summary": "Refresh mission and scope alignment.",
                "anchors": ["mission_scope"],
            },
            {
                "recommendation_id": "rec.runtime-hardening",
                "summary": "Hold runtime lane stable.",
                "anchors": ["runtime_data"],
            },
            {
                "recommendation_id": "rec.ecosystem-signal-response",
                "summary": "Track upstream signal changes.",
                "anchors": ["ecosystem_signals"],
            },
        ],
        "evidence_refs": ["strategy/history/strategy-2026-03-14T08:00:00Z/STRATEGY.json"],
    }
    current_revision = {
        "revision_id": "strategy-2026-03-15T08:00:00Z",
        "mission_scope": {
            "primary_objective": "Stabilize planner reliability",
            "constraints": {"task_floor": 400, "change_budget": "tight"},
        },
        "runtime_data": {"runtime_mode": "isolated", "queue_backlog": 4, "blocked_cycles": 1},
        "ecosystem_signals": {"upstream_projects": [{"project_id": "prj.tetris", "signal": "degraded"}]},
        "recommendations": [
            {
                "recommendation_id": "rec.scope-refresh",
                "summary": "Refresh mission and scope alignment.",
                "anchors": ["mission_scope"],
            },
            {
                "recommendation_id": "rec.runtime-hardening",
                "summary": "Increase runtime isolation after signal changes.",
                "anchors": ["runtime_data"],
            },
            {
                "recommendation_id": "rec.ecosystem-signal-response",
                "summary": "Track upstream signal changes.",
                "anchors": ["ecosystem_signals"],
            },
        ],
        "context_inputs": {
            "broad_sweep_inputs": manifest["broad_sweep_inputs"],
            "cross_project_context": manifest["cross_project_context"],
            "earth_sweep_evidence_refs": manifest["evidence_refs"],
            "evidence_refs": manifest["evidence_refs"],
        },
        "proposed_cross_project_obligations": [
            {
                "obligation_id": "obl.cross-project.runtime-sync",
                "title": "Coordinate runtime behavior across active projects.",
                "project_ids": ["prj.optimus-prime-gsd-fusion", "prj.tetris"],
                "evidence_refs": ["Optimus-Prime-GSD-Fusion/mission.md"],
            }
        ],
        "evidence_refs": [
            "strategy/current/STRATEGY.json",
            "reports/runtime/runtime-status-2026-03-15.json",
        ],
    }
    return previous_revision, current_revision


def test_req010_hardening_detects_stale_source_artifact_from_earth_sweep():
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
        previous_revision, current_revision = _build_revision_pair(manifest)
        payload = sweep.build_change_detection_since_previous_strategy_revision(previous_revision, current_revision)

        assert sweep.validate_change_detection_since_previous_strategy_revision(payload) == []
        tetris_row = next(
            row for row in payload["context_inputs"]["cross_project_context"] if row["project_id"] == "prj.tetris"
        )
        assert "stale_source_artifact_detected" in tetris_row["reason_codes"]
        assert "stale:Tetris/mission.md#stale_source_artifact_detected" in tetris_row["evidence_refs"]

        partial_context_risk = next(
            row
            for row in payload["cross_project_context_usage"]["open_risks"]
            if row["risk_id"] == "risk.req010.cross-project-context-partial"
        )
        assert partial_context_risk["reason_code"] == "missing_peer_project_doc"
        assert "stale:Tetris/mission.md#stale_source_artifact_detected" in partial_context_risk["evidence_refs"]


def test_req010_hardening_emits_missing_doc_and_peer_doc_reason_codes():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        earth_root = tmp_root / "Users" / "slobodan" / "projects" / "Earth"
        earth_root.mkdir(parents=True, exist_ok=True)

        _seed_repo(earth_root, "Optimus-Prime-GSD-Fusion")
        _seed_repo(earth_root, "Tetris", mission=True, scope=False)

        manifest = sweep.build_earth_repository_discovery_manifest(earth_root, owner_username="slobodan")
        previous_revision, current_revision = _build_revision_pair(manifest)
        payload = sweep.build_change_detection_since_previous_strategy_revision(previous_revision, current_revision)

        assert sweep.validate_change_detection_since_previous_strategy_revision(payload) == []
        tetris_row = next(
            row for row in payload["context_inputs"]["cross_project_context"] if row["project_id"] == "prj.tetris"
        )
        assert tetris_row["reason_codes"] == ["missing_scope_doc"]
        assert "missing:Tetris/scope.md#missing_scope_doc" in tetris_row["evidence_refs"]

        partial_context_risk = next(
            row
            for row in payload["cross_project_context_usage"]["open_risks"]
            if row["risk_id"] == "risk.req010.cross-project-context-partial"
        )
        assert partial_context_risk["reason_code"] == "missing_peer_project_doc"
        assert "missing:Tetris/scope.md#missing_scope_doc" in partial_context_risk["evidence_refs"]

        obligations = payload["cross_project_context_usage"]["obligations"]
        assert [row["obligation_id"] for row in obligations] == ["obl.cross-project.runtime-sync"]


def test_req010_hardening_context_bundle_serialization_is_replay_stable():
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

        first_previous, first_current = _build_revision_pair(first_manifest)
        second_previous, second_current = _build_revision_pair(second_manifest)
        first_payload = sweep.build_change_detection_since_previous_strategy_revision(first_previous, first_current)
        second_payload = sweep.build_change_detection_since_previous_strategy_revision(second_previous, second_current)

        assert first_bundle == second_bundle
        assert first_serialized == second_serialized
        assert json.loads(first_serialized) == first_bundle
        assert sweep.validate_change_detection_since_previous_strategy_revision(first_payload) == []
        assert sweep.validate_change_detection_since_previous_strategy_revision(second_payload) == []
        assert first_payload == second_payload
