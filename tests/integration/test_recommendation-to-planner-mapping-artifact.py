import copy
import json
from pathlib import Path

from scripts import strategy_artifacts_handoff as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "recommendation-to-planner-mapping-artifact.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_054_integration_recommendation_processing_is_complete_and_uses_cross_project_context() -> None:
    payload = copy.deepcopy(_read_json(FIXTURE_PATH))
    payload["broad_sweep_context"] = {
        "projects_considered": [
            "earth-core-runtime",
            "earth-shared-observability",
            "earth-ops-pipeline",
        ],
        "earth_sweep_evidence_refs": [
            "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
            "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
            "reports/earth/sweeps/earth-ops-pipeline/planner-packet-gaps-2026-03-15.json",
        ],
        "cross_project_obligations": [
            {
                "obligation_id": "obligation-runtime-canary-alignment",
                "summary": "Coordinate runtime canary windows before widening rollout.",
                "recommendation_ids": ["rec.align-earth-runtime-canary"],
                "project_ids": ["earth-core-runtime"],
                "earth_sweep_evidence_refs": [
                    "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
                ],
            },
            {
                "obligation_id": "obligation-missing-earth-evidence",
                "summary": "Link reuse contract updates to cross-project ownership evidence.",
                "recommendation_ids": ["rec.review-reuse-contracts"],
                "project_ids": ["earth-shared-observability"],
                "earth_sweep_evidence_refs": [],
            },
            {
                "obligation_id": "obligation-unknown-recommendation",
                "summary": "Sync planner packet queue with a recommendation not present in mapping rows.",
                "recommendation_ids": ["rec.unknown"],
                "project_ids": ["earth-ops-pipeline"],
                "earth_sweep_evidence_refs": [
                    "reports/earth/sweeps/earth-ops-pipeline/planner-packet-gaps-2026-03-15.json",
                ],
            },
        ],
        "unresolved_ideas": [
            {
                "idea_id": "idea.reuse-ownership-followup",
                "summary": "Validate shared ownership handoff before adding new cross-project packets.",
                "recommendation_ids": ["rec.review-reuse-contracts"],
                "project_ids": ["earth-shared-observability"],
                "required_earth_sweep_evidence_refs": [
                    "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
                ],
            },
            {
                "idea_id": "idea.unscoped-evidence-gap",
                "summary": "Capture missing Earth sweep references for planner intake risk review.",
                "recommendation_ids": [],
                "project_ids": ["earth-ops-pipeline"],
                "required_earth_sweep_evidence_refs": [],
            },
        ],
    }

    out = module.build_req_054_recommendation_to_planner_mapping_artifact(payload)
    assert module.validate_req_054_recommendation_to_planner_mapping_artifact(out) == []

    processing = out["processing_behavior"]
    recommendation = processing["recommendation"]
    usage = processing["cross_project_context_usage"]

    assert set(recommendation.keys()) == {
        "decision",
        "rationale",
        "evidence_refs",
        "context_project_ids",
        "mapped_recommendation_ids",
        "mapped_task_intent_handles",
        "approved_cross_project_obligations",
        "open_risks",
    }
    assert recommendation["decision"] == "planning_with_open_risks"
    assert recommendation["rationale"] == "mappings=4 obligations=3 approved=1 open_risks=4"
    assert recommendation["mapped_recommendation_ids"] == [
        "rec.align-earth-runtime-canary",
        "rec.harden-telemetry-freshness",
        "rec.review-reuse-contracts",
    ]
    assert recommendation["mapped_task_intent_handles"] == [
        "intent.cross-project-reuse-ownership-clarification",
        "intent.cross-project-runtime-canary-alignment",
        "intent.reuse-contract-review",
        "intent.telemetry-freshness-hardening",
    ]
    assert recommendation["context_project_ids"] == [
        "earth-core-runtime",
        "earth-ops-pipeline",
        "earth-shared-observability",
    ]
    assert "reports/runtime/telemetry/freshness-gap-2026-03-15.json" in recommendation["evidence_refs"]
    assert "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json" in recommendation["evidence_refs"]
    assert "missing:earth-sweep-evidence-ref" in recommendation["evidence_refs"]

    assert recommendation["approved_cross_project_obligations"] == [
        {
            "obligation_id": "obligation-runtime-canary-alignment",
            "summary": "Coordinate runtime canary windows before widening rollout.",
            "project_ids": ["earth-core-runtime"],
            "evidence_refs": [
                "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
            ],
            "linked_recommendation_ids": ["rec.align-earth-runtime-canary"],
            "linked_planner_task_intent_handles": ["intent.cross-project-runtime-canary-alignment"],
        }
    ]

    open_risk_reasons = {row["source_id"]: row["reason_code"] for row in recommendation["open_risks"]}
    assert open_risk_reasons == {
        "idea.reuse-ownership-followup": "unresolved_idea_open_risk",
        "idea.unscoped-evidence-gap": "unresolved_idea_open_risk",
        "obligation-missing-earth-evidence": "missing_earth_sweep_evidence_refs",
        "obligation-unknown-recommendation": "unknown_recommendation_ids",
    }

    assert usage == {
        "cross_project_context_provided": True,
        "cross_project_context_used": True,
        "projects_considered": [
            "earth-core-runtime",
            "earth-ops-pipeline",
            "earth-shared-observability",
        ],
        "earth_sweep_evidence_refs_considered": [
            "reports/earth/sweeps/earth-core-runtime/plan-runtime-014-run-131.json",
            "reports/earth/sweeps/earth-ops-pipeline/planner-packet-gaps-2026-03-15.json",
            "reports/earth/sweeps/shared-observability/signals-2026-03-14.json",
        ],
        "cross_project_obligation_count": 3,
        "unresolved_idea_count": 2,
        "recommendation_ids_with_context": [
            "rec.align-earth-runtime-canary",
            "rec.review-reuse-contracts",
        ],
    }


def test_req_054_integration_without_broad_context_keeps_contract_output_stable() -> None:
    payload = _read_json(FIXTURE_PATH)

    out = module.build_req_054_recommendation_to_planner_mapping_artifact(payload)

    assert "processing_behavior" not in out
    assert module.validate_req_054_recommendation_to_planner_mapping_artifact(out) == []
