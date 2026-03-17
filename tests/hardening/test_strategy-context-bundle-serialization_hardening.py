import copy
import json
from pathlib import Path

from scripts import strategy_context_sweep as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "strategy-context-bundle-serialization.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _bundle_from_payload(payload: dict) -> dict:
    return json.loads(payload["strategy_context_bundle_serialization"]["serialized_context_bundle"])


def test_req_024_stale_earth_sweep_source_artifact_emits_deterministic_reason_code_and_evidence_refs():
    fixture = _read_json(FIXTURE_PATH)
    test_input = copy.deepcopy(fixture["input"])
    context_inputs = test_input["strategy_context"]["processing_behavior"]["context_inputs"]
    context_inputs["earth_sweep_source_artifacts"] = [
        {
            "artifact_ref": "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
            "status": "stale",
            "evidence_refs": [
                "reports/optimus-prime/planning/evidence/TASK-077/stale-earth-source-artifact.txt"
            ],
        }
    ]

    payload = module.build_req_024_strategy_context_bundle_serialization(**test_input)
    assert module.validate_req_024_strategy_context_bundle_serialization(payload) == []

    recommendation = _bundle_from_payload(payload)["strategy_context"]["processing_behavior"]["recommendation"]
    assert recommendation["decision"] == "proceed-with-open-risks"
    assert recommendation["open_risks"] == [
        {
            "risk_id": "risk-earth-source-7fdf112ec591",
            "summary": "Earth sweep source artifact is stale: reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
            "reason_code": "stale_earth_sweep_source_artifact",
            "required_evidence_refs": [
                "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
                "reports/optimus-prime/planning/evidence/TASK-077/stale-earth-source-artifact.txt",
            ],
        }
    ]


def test_req_024_missing_mission_scope_and_peer_project_docs_emit_explicit_reason_codes():
    fixture = _read_json(FIXTURE_PATH)
    test_input = copy.deepcopy(fixture["input"])
    context_inputs = test_input["strategy_context"]["processing_behavior"]["context_inputs"]
    context_inputs["required_context_documents"] = [
        {
            "doc_kind": "mission",
            "doc_ref": "strategy/current/mission.md",
            "status": "missing",
            "evidence_refs": ["reports/optimus-prime/planning/evidence/TASK-077/mission-missing.txt"],
        },
        {
            "doc_kind": "scope",
            "doc_ref": "strategy/current/scope.md",
            "status": "missing",
            "evidence_refs": ["reports/optimus-prime/planning/evidence/TASK-077/scope-missing.txt"],
        },
        {
            "doc_kind": "peer-project",
            "project_id": "runtime-orchestrator",
            "doc_ref": "reports/earth/sweeps/2026-03-15/runtime-orchestrator/mission-scope.md",
            "status": "missing",
            "evidence_refs": ["reports/optimus-prime/planning/evidence/TASK-077/peer-doc-missing.txt"],
        },
    ]

    payload = module.build_req_024_strategy_context_bundle_serialization(**test_input)
    assert module.validate_req_024_strategy_context_bundle_serialization(payload) == []

    recommendation = _bundle_from_payload(payload)["strategy_context"]["processing_behavior"]["recommendation"]
    assert recommendation["decision"] == "proceed-with-open-risks"
    assert recommendation["open_risks"] == [
        {
            "risk_id": "risk-context-doc-e97432be2ce0",
            "summary": "Required mission document is missing: strategy/current/mission.md",
            "reason_code": "missing_mission_doc",
            "required_evidence_refs": [
                "reports/optimus-prime/planning/evidence/TASK-077/mission-missing.txt",
                "strategy/current/mission.md",
            ],
        },
        {
            "risk_id": "risk-context-doc-1f60a9f7139b",
            "summary": (
                "Required peer-project document is missing for 'runtime-orchestrator': "
                "reports/earth/sweeps/2026-03-15/runtime-orchestrator/mission-scope.md"
            ),
            "reason_code": "missing_peer_project_doc",
            "required_evidence_refs": [
                "reports/earth/sweeps/2026-03-15/runtime-orchestrator/mission-scope.md",
                "reports/optimus-prime/planning/evidence/TASK-077/peer-doc-missing.txt",
            ],
        },
        {
            "risk_id": "risk-context-doc-82f39f7d256e",
            "summary": "Required scope document is missing: strategy/current/scope.md",
            "reason_code": "missing_scope_doc",
            "required_evidence_refs": [
                "reports/optimus-prime/planning/evidence/TASK-077/scope-missing.txt",
                "strategy/current/scope.md",
            ],
        },
    ]


def test_req_024_context_bundle_serialization_is_replay_stable_across_repeated_runs():
    fixture = _read_json(FIXTURE_PATH)
    first = module.build_req_024_strategy_context_bundle_serialization(**copy.deepcopy(fixture["input"]))
    second = module.build_req_024_strategy_context_bundle_serialization(**copy.deepcopy(fixture["input"]))
    third = module.build_req_024_strategy_context_bundle_serialization(**copy.deepcopy(fixture["input"]))

    assert module.validate_req_024_strategy_context_bundle_serialization(first) == []
    assert module.validate_req_024_strategy_context_bundle_serialization(second) == []
    assert module.validate_req_024_strategy_context_bundle_serialization(third) == []
    assert first == second == third

    first_serialization = first["strategy_context_bundle_serialization"]["serialized_context_bundle"]
    second_serialization = second["strategy_context_bundle_serialization"]["serialized_context_bundle"]
    third_serialization = third["strategy_context_bundle_serialization"]["serialized_context_bundle"]
    assert first_serialization == second_serialization == third_serialization

    first_sha256 = first["strategy_context_bundle_serialization"]["context_bundle_sha256"]
    second_sha256 = second["strategy_context_bundle_serialization"]["context_bundle_sha256"]
    third_sha256 = third["strategy_context_bundle_serialization"]["context_bundle_sha256"]
    assert first_sha256 == second_sha256 == third_sha256

    parsed_bundle = _bundle_from_payload(first)
    canonical = json.dumps(parsed_bundle, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    assert first_serialization == canonical
