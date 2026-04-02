import json
from pathlib import Path

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "cross-call-contradiction-detection.json"
SAMPLE_PATH = (
    REPO_ROOT
    / "strategy"
    / "current"
    / "samples"
    / "REQ-036_cross-call-contradiction-detection.sample.json"
)
CONTRACT_PATH = REPO_ROOT / "contracts" / "req" / "REQ-036_cross-call-contradiction-detection.md"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_req_036_builder_matches_expected_contract_anchors() -> None:
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_036_cross_call_contradiction_detection(
        **fixture["input"],
        persist_llm_call_trace=False,
    )
    anchors = fixture["expected_contract_anchors"]

    assert module.validate_req_036_cross_call_contradiction_detection(payload) == []
    assert payload["schema_version"] == anchors["schema_version"]
    assert payload["requirement_id"] == anchors["requirement_id"]
    assert payload["processing_behavior"]["strategy"] == anchors["strategy"]
    assert payload["processing_behavior"]["contradiction_handling_policy"] == anchors["handling_policy"]
    assert payload["processing_behavior"]["recommendation"]["decision"] == anchors["decision"]

    report = payload["contradiction_report"]
    assert report["contradiction_count"] == anchors["contradiction_count"]
    assert report["resolved_contradictions"] == anchors["resolved_contradictions"]
    assert report["unresolved_contradictions"] == anchors["unresolved_contradictions"]

    unresolved_claim_ids = sorted(
        row["claim_id"]
        for row in report["contradictions"]
        if row["resolution_status"] == "unresolved"
    )
    assert unresolved_claim_ids == anchors["unresolved_claim_ids"]


def test_req_036_policy_requires_resolution_or_unresolved_risk_marking() -> None:
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_036_cross_call_contradiction_detection(
        **fixture["input"],
        persist_llm_call_trace=False,
    )

    for row in payload["contradiction_report"]["contradictions"]:
        if row["resolution_status"] == "resolved":
            assert row["resolution"] is not None
            assert row["unresolved_risk"] is None
            continue

        assert row["resolution_status"] == "unresolved"
        assert row["unresolved_risk"] is not None
        assert row["unresolved_risk"]["reason_code"] == "cross_call_contradiction"


def test_req_036_call_metadata_reproducibility_behavior() -> None:
    fixture = _read_json(FIXTURE_PATH)

    first = module.build_req_036_cross_call_contradiction_detection(
        **fixture["input"],
        persist_llm_call_trace=False,
    )
    second = module.build_req_036_cross_call_contradiction_detection(
        **fixture["input"],
        persist_llm_call_trace=False,
    )
    assert first["call_metadata"] == second["call_metadata"]

    changed_input = dict(fixture["input"])
    changed_input["contradiction_resolutions"] = [
        *fixture["input"]["contradiction_resolutions"],
        fixture["determinism_probe"]["append_resolution"],
    ]
    changed = module.build_req_036_cross_call_contradiction_detection(
        **changed_input,
        persist_llm_call_trace=False,
    )

    assert changed["call_metadata"]["canonical_input_sha256"] == first["call_metadata"]["canonical_input_sha256"]
    assert changed["call_metadata"]["reproducible_call_id"] == first["call_metadata"]["reproducible_call_id"]
    assert changed["call_metadata"]["processing_input_sha256"] != first["call_metadata"]["processing_input_sha256"]


def test_req_036_sample_payload_and_contract_doc_are_aligned() -> None:
    sample = _read_json(SAMPLE_PATH)
    assert module.validate_req_036_cross_call_contradiction_detection(sample) == []

    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")
    assert "strategy/current/samples/REQ-036_cross-call-contradiction-detection.sample.json" in contract_text
    for key in [
        "schema_version",
        "requirement_id",
        "cross_call_contradiction_detection",
        "processing_behavior",
        "contradiction_report",
        "context_bundle",
        "llm_call_trace",
        "call_metadata",
    ]:
        assert f"`{key}`" in contract_text


def test_req_036_llm_call_trace_rows_are_one_per_call() -> None:
    fixture = _read_json(FIXTURE_PATH)
    payload = module.build_req_036_cross_call_contradiction_detection(
        **fixture["input"],
        persist_llm_call_trace=False,
    )
    llm_call_trace = payload["llm_call_trace"]

    assert llm_call_trace["row_count"] == len(fixture["input"]["call_outputs"])
    assert [row["call_id"] for row in llm_call_trace["rows"]] == ["call-1", "call-2", "call-3"]
    for row in llm_call_trace["rows"]:
        assert set(row.keys()) == {
            "schema_version",
            "trace_row_id",
            "call_id",
            "call_requirement_id",
            "call_objective",
            "input_refs",
            "output_refs",
            "handoff_summary",
        }
        assert row["schema_version"] == "req-036.llm-call-trace-row.v1"
        assert row["call_objective"]
        assert row["input_refs"]
        assert row["output_refs"]
        assert set(row["handoff_summary"].keys()) == {
            "decision",
            "emitted_claim_count",
            "emitted_claim_ids",
            "emitted_claim_stances",
            "contradiction_claim_ids",
            "resolved_contradiction_claim_ids",
            "unresolved_contradiction_claim_ids",
            "evidence_refs",
        }
