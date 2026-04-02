import json
from copy import deepcopy
from pathlib import Path

from scripts.strategy_context_sweep import (
    detect_overlap_and_conflicts,
    serialize_overlap_and_conflict_context_bundle,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "overlap-and-conflict-detection.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _base_payload() -> dict:
    payload = _read_json(FIXTURE_PATH)
    payload["broad_sweep_context"]["earth_sweep_evidence_refs"] = [
        *payload["broad_sweep_context"]["earth_sweep_evidence_refs"],
        "reports/earth/sweeps/earth-core-runtime/runtime-signal-snapshot-2026-03-14.json",
    ]
    return payload


def test_req_017_hardening_detects_stale_source_artifact_during_earth_sweep() -> None:
    payload = _base_payload()
    payload["broad_sweep_context"]["earth_sweep_source_artifacts"] = [
        {
            "artifact_ref": "reports/earth/sweeps/earth-core-runtime/runtime-signal-snapshot-2026-03-14.json",
            "status": "stale",
            "evidence_refs": [
                "reports/earth/sweeps/earth-core-runtime/runtime-signal-snapshot-2026-03-14.audit.json",
            ],
        }
    ]

    output = detect_overlap_and_conflicts(payload, evaluated_at="2026-03-15T04:20:00Z")

    stale_rows = [
        row
        for row in output["recommendation"]["open_risks"]
        if row.get("reason_code") == "stale_earth_sweep_source_artifact"
    ]
    assert len(stale_rows) == 1

    stale = stale_rows[0]
    assert stale["artifact_ref"] == "reports/earth/sweeps/earth-core-runtime/runtime-signal-snapshot-2026-03-14.json"
    assert stale["evidence_refs"] == [
        "reports/earth/sweeps/earth-core-runtime/runtime-signal-snapshot-2026-03-14.audit.json",
        "reports/earth/sweeps/earth-core-runtime/runtime-signal-snapshot-2026-03-14.json",
    ]
    assert stale["out_of_scope_evidence_refs"] == [
        "reports/earth/sweeps/earth-core-runtime/runtime-signal-snapshot-2026-03-14.audit.json",
    ]
    assert output["decision"] == "conflicts_detected"
    assert output["recommendation"]["decision"] == "planning_with_open_risks"


def test_req_017_hardening_emits_explicit_reason_codes_for_missing_docs() -> None:
    payload = _base_payload()
    payload["broad_sweep_context"]["required_context_documents"] = [
        {
            "doc_kind": "mission",
            "doc_ref": "projects/optimus-prime-gsd-fusion/mission.md",
            "status": "missing",
            "evidence_refs": [
                "reports/optimus-prime/planning/evidence/TASK-054/missing-mission.json",
            ],
        },
        {
            "doc_kind": "scope",
            "doc_ref": "projects/optimus-prime-gsd-fusion/scope.md",
            "status": "missing",
            "evidence_refs": [
                "reports/optimus-prime/planning/evidence/TASK-054/missing-scope.json",
            ],
        },
        {
            "doc_kind": "peer-project",
            "project_id": "shared-observability",
            "doc_ref": "projects/shared-observability/scope.md",
            "status": "missing",
            "evidence_refs": [
                "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
            ],
        },
    ]

    output = detect_overlap_and_conflicts(payload, evaluated_at="2026-03-15T04:25:00Z")

    reason_rows = {
        row["reason_code"]: row
        for row in output["recommendation"]["open_risks"]
        if row.get("reason_code") in {"missing_mission_doc", "missing_scope_doc", "missing_peer_project_doc"}
    }
    assert sorted(reason_rows) == [
        "missing_mission_doc",
        "missing_peer_project_doc",
        "missing_scope_doc",
    ]

    assert reason_rows["missing_mission_doc"]["evidence_refs"] == [
        "projects/optimus-prime-gsd-fusion/mission.md",
        "reports/optimus-prime/planning/evidence/TASK-054/missing-mission.json",
    ]
    assert reason_rows["missing_scope_doc"]["evidence_refs"] == [
        "projects/optimus-prime-gsd-fusion/scope.md",
        "reports/optimus-prime/planning/evidence/TASK-054/missing-scope.json",
    ]
    peer_row = reason_rows["missing_peer_project_doc"]
    assert peer_row["project_id"] == "shared-observability"
    assert peer_row["evidence_refs"] == [
        "projects/shared-observability/scope.md",
        "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
    ]


def test_req_017_hardening_context_bundle_serialization_is_replay_stable() -> None:
    first_payload = _base_payload()
    first_payload["broad_sweep_context"]["earth_sweep_source_artifacts"] = [
        {
            "artifact_ref": "reports/earth/sweeps/earth-core-runtime/runtime-signal-snapshot-2026-03-14.json",
            "status": "stale",
            "evidence_refs": [
                "reports/earth/sweeps/earth-core-runtime/runtime-signal-snapshot-2026-03-14.audit.json",
            ],
        },
        {
            "artifact_ref": "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
            "status": "fresh",
            "evidence_refs": [],
        },
    ]
    first_payload["broad_sweep_context"]["required_context_documents"] = [
        {
            "doc_kind": "mission",
            "doc_ref": "projects/optimus-prime-gsd-fusion/mission.md",
            "status": "present",
            "evidence_refs": [],
        },
        {
            "doc_kind": "peer-project",
            "project_id": "shared-observability",
            "doc_ref": "projects/shared-observability/scope.md",
            "status": "missing",
            "evidence_refs": [
                "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
            ],
        },
    ]

    second_payload = deepcopy(first_payload)
    second_payload["related_project_ids"] = [
        "shared-observability",
        "earth-core-runtime",
        "shared-observability",
    ]
    second_payload["broad_sweep_context"]["earth_sweep_evidence_refs"] = [
        "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
        "reports/earth/sweeps/earth-core-runtime/runtime-signal-snapshot-2026-03-14.json",
        "reports/earth/sweeps/earth-core-runtime/roadmap-2026-q2.json",
        "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
    ]
    second_payload["broad_sweep_context"]["project_context"] = list(
        reversed(second_payload["broad_sweep_context"]["project_context"])
    )
    second_payload["broad_sweep_context"]["unresolved_direction_ideas"] = list(
        reversed(second_payload["broad_sweep_context"]["unresolved_direction_ideas"])
    )
    second_payload["broad_sweep_context"]["earth_sweep_source_artifacts"] = list(
        reversed(second_payload["broad_sweep_context"]["earth_sweep_source_artifacts"])
    )
    second_payload["broad_sweep_context"]["required_context_documents"] = list(
        reversed(second_payload["broad_sweep_context"]["required_context_documents"])
    )
    second_payload["initiatives"] = list(reversed(second_payload["initiatives"]))

    first = detect_overlap_and_conflicts(first_payload, evaluated_at="2026-03-15T04:30:00Z")
    second = detect_overlap_and_conflicts(second_payload, evaluated_at="2026-03-15T04:30:00Z")

    assert first == second

    first_bundle = serialize_overlap_and_conflict_context_bundle(first)
    second_bundle = serialize_overlap_and_conflict_context_bundle(second)

    assert first_bundle == second_bundle
    assert first_bundle["checksum_sha256"] == second_bundle["checksum_sha256"]
    assert first_bundle["serialized_payload"] == second_bundle["serialized_payload"]

    parsed = json.loads(first_bundle["serialized_payload"])
    canonical = json.dumps(parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert first_bundle["serialized_payload"] == canonical
