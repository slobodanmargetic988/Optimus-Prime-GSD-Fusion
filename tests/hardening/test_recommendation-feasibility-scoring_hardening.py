from scripts import strategy_llm_pipeline as module


def _base_input() -> dict:
    return {
        "target_project_root": "/workspace/projects/optimus-prime",
        "earth_root": "/workspace/projects/Earth",
        "output_root": "/workspace/projects/optimus-prime/strategy/out",
        "revision_identity": "rev-req040-hardening",
        "resource_constraints": {
            "available_parallel_slots": 4,
            "available_daily_tokens": 300000,
            "max_recommendation_cost_tier": "high",
            "constrained_resources": ["integration_capacity"],
            "evidence_refs": ["reports/runtime/budgets/strategy-runtime.json"],
        },
        "dependency_readiness": [
            {
                "dependency_id": "dep.analysis-lane",
                "readiness_status": "ready",
                "blocker_count": 0,
                "evidence_refs": ["reports/strategy/analysis/analysis-lane.json"],
            },
            {
                "dependency_id": "dep.synthesis-lane",
                "readiness_status": "ready",
                "blocker_count": 0,
                "evidence_refs": ["reports/strategy/synthesis/synthesis-lane.json"],
            },
            {
                "dependency_id": "dep.ready-lane",
                "readiness_status": "ready",
                "blocker_count": 0,
                "evidence_refs": ["reports/dependencies/ready-lane.json"],
            },
        ],
        "repo_maturity": {
            "maturity_level": "stable",
            "test_pass_rate": 0.99,
            "open_defect_count": 1,
            "evidence_refs": ["reports/quality/repo-maturity.json"],
        },
    }


def test_req_040_hardening_detects_cross_call_contradiction_between_analysis_and_synthesis_outputs() -> None:
    payload = module.build_req_040_recommendation_feasibility_scoring(
        **_base_input(),
        candidate_recommendations=[
            {
                "recommendation_id": "rec.analysis-synthesis-conflict",
                "summary": "Analysis and synthesis conflict on write-path readiness and contradict each other.",
                "required_dependency_ids": ["dep.analysis-lane", "dep.synthesis-lane"],
                "required_cost_tier": "low",
                "evidence_refs": [
                    "reports/strategy/analysis/write-path-readiness.json",
                    "reports/strategy/synthesis/write-path-readiness.json",
                ],
            }
        ],
        persist_llm_call_trace=False,
    )

    row = payload["feasibility_assessment"]["recommendations"][0]
    risk = payload["risk_policy"]["open_risks"][0]

    assert module.validate_req_040_recommendation_feasibility_scoring(payload) == []
    assert row["reason_codes"] == ["cross_call_analysis_synthesis_contradiction"]
    assert row["risk_policy"] == "defer-until-controls"
    assert row["sequencing_bucket"] == "defer"
    assert "diagnostics/req-040/rec.analysis-synthesis-conflict/analysis-synthesis-contradiction.json" in row[
        "evidence_refs"
    ]
    assert risk["reason_codes"] == ["cross_call_analysis_synthesis_contradiction"]
    assert risk["required_evidence_refs"] == row["evidence_refs"]


def test_req_040_hardening_blocks_uncited_strategic_claim_via_citation_discipline() -> None:
    payload = module.build_req_040_recommendation_feasibility_scoring(
        **_base_input(),
        candidate_recommendations=[
            {
                "recommendation_id": "rec.uncited-claim",
                "summary": "Analysis recommends immediate rollout while synthesis input is pending final review.",
                "required_dependency_ids": ["dep.ready-lane"],
                "required_cost_tier": "low",
                "evidence_refs": ["reports/recommendations/rollout-without-call-citation.json"],
            }
        ],
        persist_llm_call_trace=False,
    )

    row = payload["feasibility_assessment"]["recommendations"][0]
    risk = payload["risk_policy"]["open_risks"][0]

    assert module.validate_req_040_recommendation_feasibility_scoring(payload) == []
    assert row["reason_codes"] == ["uncited_strategic_claim_blocked"]
    assert row["risk_policy"] == "defer-until-controls"
    assert row["sequencing_bucket"] == "defer"
    assert "diagnostics/req-040/rec.uncited-claim/citation-discipline-block.json" in row["evidence_refs"]
    assert risk["reason_codes"] == ["uncited_strategic_claim_blocked"]
    assert risk["required_evidence_refs"] == row["evidence_refs"]


def test_req_040_hardening_replay_keeps_recommendation_ids_and_ordering_stable() -> None:
    input_payload = {
        **_base_input(),
        "candidate_recommendations": [
            {
                "recommendation_id": "rec.uncited-claim",
                "summary": "Analysis says to proceed now while synthesis remains pending formal review.",
                "required_dependency_ids": ["dep.ready-lane"],
                "required_cost_tier": "low",
                "evidence_refs": ["reports/recommendations/uncited-claim.json"],
            },
            {
                "recommendation_id": "rec.ready-path",
                "summary": "Readiness evidence supports standard sequencing for the read path.",
                "required_dependency_ids": ["dep.ready-lane"],
                "required_cost_tier": "low",
                "evidence_refs": ["reports/recommendations/read-path-ready.json"],
            },
            {
                "recommendation_id": "rec.analysis-synthesis-conflict",
                "summary": "Analysis and synthesis disagree and conflict on canary expansion timing.",
                "required_dependency_ids": ["dep.analysis-lane", "dep.synthesis-lane"],
                "required_cost_tier": "low",
                "evidence_refs": [
                    "reports/strategy/analysis/canary-expansion.json",
                    "reports/strategy/synthesis/canary-expansion.json",
                ],
            },
        ],
    }

    first = module.build_req_040_recommendation_feasibility_scoring(
        **input_payload,
        persist_llm_call_trace=False,
    )
    second = module.build_req_040_recommendation_feasibility_scoring(
        **input_payload,
        persist_llm_call_trace=False,
    )

    assert module.validate_req_040_recommendation_feasibility_scoring(first) == []
    assert module.validate_req_040_recommendation_feasibility_scoring(second) == []
    assert first["sequencing_policy"]["ordered_recommendation_ids"] == [
        "rec.ready-path",
        "rec.analysis-synthesis-conflict",
        "rec.uncited-claim",
    ]
    assert first["sequencing_policy"]["ordered_recommendation_ids"] == second["sequencing_policy"][
        "ordered_recommendation_ids"
    ]
    assert [
        action["action_id"] for action in first["processing_behavior"]["recommendation"]["recommended_actions"]
    ] == [
        "sequence-rec.ready-path",
        "sequence-rec.analysis-synthesis-conflict",
        "sequence-rec.uncited-claim",
    ]
    assert first["processing_behavior"]["recommendation"] == second["processing_behavior"]["recommendation"]
    assert first["risk_policy"]["open_risks"] == second["risk_policy"]["open_risks"]
    assert [row["trace_row_id"] for row in first["llm_call_trace"]["rows"]] == [
        row["trace_row_id"] for row in second["llm_call_trace"]["rows"]
    ]
