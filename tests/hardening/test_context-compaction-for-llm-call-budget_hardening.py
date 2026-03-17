from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from scripts import strategy_context_sweep as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "context-compaction-for-llm-call-budget.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_023_hardening_stale_earth_sweep_source_artifact_emits_reason_code_and_evidence_refs() -> None:
    fixture = _read_json(FIXTURE_PATH)
    test_input = deepcopy(fixture["input"])
    test_input["required_context_documents"] = []

    payload = module.build_req_023_context_compaction_for_llm_call_budget(**test_input)

    assert module.validate_req_023_context_compaction_for_llm_call_budget(payload) == []

    recommendation = payload["processing_behavior"]["recommendation"]
    open_risks = recommendation["open_risks"]

    assert recommendation["decision"] == "proceed-with-open-risks"
    assert [row["reason_code"] for row in open_risks] == ["stale_earth_sweep_source_artifact"]
    assert open_risks == [
        {
            "risk_id": (
                "risk-earth-source-"
                f"{module._stable_id_fragment('reports/earth/sweeps/2026-03-15/runtime-orchestrator.json')}"
            ),
            "summary": (
                "Earth sweep source artifact is stale: "
                "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json"
            ),
            "reason_code": "stale_earth_sweep_source_artifact",
            "required_evidence_refs": [
                "reports/earth/sweeps/2026-03-15/runtime-orchestrator.audit.json",
                "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
            ],
        }
    ]


def test_req_023_hardening_missing_required_docs_emit_explicit_reason_codes() -> None:
    fixture = _read_json(FIXTURE_PATH)
    test_input = deepcopy(fixture["input"])
    test_input["candidate_recommendations"] = []
    test_input["earth_sweep_source_artifacts"] = []
    test_input["required_context_documents"] = [
        {
            "doc_kind": "mission",
            "doc_ref": "mission.md",
            "status": "missing",
            "evidence_refs": [
                "reports/optimus-prime/planning/evidence/TASK-074/TASK_EVIDENCE.json",
            ],
        },
        {
            "doc_kind": "scope",
            "doc_ref": "scope.md",
            "status": "missing",
            "evidence_refs": [
                "reports/optimus-prime/planning/evidence/TASK-074/TASK_EVIDENCE.json",
            ],
        },
        {
            "doc_kind": "peer-project",
            "project_id": "runtime-orchestrator",
            "doc_ref": "docs/runtime-orchestrator/mission-scope.md",
            "status": "missing",
            "evidence_refs": [
                "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
            ],
        },
    ]

    payload = module.build_req_023_context_compaction_for_llm_call_budget(**test_input)

    assert module.validate_req_023_context_compaction_for_llm_call_budget(payload) == []

    recommendation = payload["processing_behavior"]["recommendation"]
    open_risks = recommendation["open_risks"]
    risks_by_reason_code = {row["reason_code"]: row for row in open_risks}

    assert recommendation["decision"] == "resolve-context-gaps"
    assert sorted(risks_by_reason_code) == [
        "missing_mission_doc",
        "missing_peer_project_doc",
        "missing_scope_doc",
    ]
    assert risks_by_reason_code["missing_mission_doc"] == {
        "risk_id": f"risk-context-doc-{module._stable_id_fragment('mission', '', 'mission.md')}",
        "summary": "Required mission document is missing: mission.md",
        "reason_code": "missing_mission_doc",
        "required_evidence_refs": [
            "mission.md",
            "reports/optimus-prime/planning/evidence/TASK-074/TASK_EVIDENCE.json",
        ],
    }
    assert risks_by_reason_code["missing_scope_doc"] == {
        "risk_id": f"risk-context-doc-{module._stable_id_fragment('scope', '', 'scope.md')}",
        "summary": "Required scope document is missing: scope.md",
        "reason_code": "missing_scope_doc",
        "required_evidence_refs": [
            "reports/optimus-prime/planning/evidence/TASK-074/TASK_EVIDENCE.json",
            "scope.md",
        ],
    }
    assert risks_by_reason_code["missing_peer_project_doc"] == {
        "risk_id": (
            "risk-context-doc-"
            f"{module._stable_id_fragment('peer-project', 'runtime-orchestrator', 'docs/runtime-orchestrator/mission-scope.md')}"
        ),
        "summary": (
            "Required peer-project document is missing for 'runtime-orchestrator': "
            "docs/runtime-orchestrator/mission-scope.md"
        ),
        "reason_code": "missing_peer_project_doc",
        "required_evidence_refs": [
            "docs/runtime-orchestrator/mission-scope.md",
            "reports/earth/sweeps/2026-03-15/runtime-orchestrator.json",
        ],
    }


def test_req_023_hardening_context_bundle_serialization_is_replay_stable() -> None:
    fixture = _read_json(FIXTURE_PATH)
    first_input = deepcopy(fixture["input"])
    second_input = deepcopy(fixture["input"])
    second_input["target_project_evidence_refs"] = [
        "reports/optimus-prime/planning/evidence/TASK-072/TASK_EVIDENCE.json",
        "reports/optimus-prime/planning/evidence/TASK-072/TASK_EVIDENCE.json",
    ]
    second_input["earth_sweep_evidence_refs"] = [
        "reports/earth/sweeps/2026-03-15/portfolio.json",
        "reports/earth/sweeps/2026-03-15/portfolio.json",
    ]
    second_input["cross_project_context"] = list(reversed(second_input["cross_project_context"]))
    second_input["candidate_recommendations"] = list(reversed(second_input["candidate_recommendations"]))
    second_input["earth_sweep_source_artifacts"] = list(reversed(second_input["earth_sweep_source_artifacts"]))
    second_input["required_context_documents"] = list(reversed(second_input["required_context_documents"]))
    second_input["hard_constraints"] = list(reversed(second_input["hard_constraints"]))

    first = module.build_req_023_context_compaction_for_llm_call_budget(**first_input)
    second = module.build_req_023_context_compaction_for_llm_call_budget(**second_input)
    third = module.build_req_023_context_compaction_for_llm_call_budget(**first_input)

    assert module.validate_req_023_context_compaction_for_llm_call_budget(first) == []
    assert module.validate_req_023_context_compaction_for_llm_call_budget(second) == []
    assert module.validate_req_023_context_compaction_for_llm_call_budget(third) == []
    assert first == second == third

    first_bundle = json.dumps(
        first["call_metadata"]["canonical_processing_input"],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    second_bundle = json.dumps(
        second["call_metadata"]["canonical_processing_input"],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    third_bundle = json.dumps(
        third["call_metadata"]["canonical_processing_input"],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    assert first_bundle == second_bundle == third_bundle
    assert first["call_metadata"]["processing_input_sha256"] == second["call_metadata"]["processing_input_sha256"]
    assert second["call_metadata"]["processing_input_sha256"] == third["call_metadata"]["processing_input_sha256"]
    assert first["call_metadata"]["processing_call_id"] == second["call_metadata"]["processing_call_id"]
    assert second["call_metadata"]["processing_call_id"] == third["call_metadata"]["processing_call_id"]
