import json
from pathlib import Path

from scripts import strategy_llm_pipeline as module


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "cross-call-contradiction-detection.json"
TRACE_RELATIVE_PATH = "strategy/current/llm_call_trace.jsonl"
TRACE_PATH = REPO_ROOT / TRACE_RELATIVE_PATH


def _read_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        rows.append(json.loads(text))
    return rows


def test_strategy_llm_pipeline_smoke_emits_replay_stable_llm_call_trace() -> None:
    fixture = _read_fixture()

    first_payload = module.build_req_036_cross_call_contradiction_detection(
        **fixture["input"],
        llm_call_trace_path=TRACE_RELATIVE_PATH,
        persist_llm_call_trace=True,
    )
    second_payload = module.build_req_036_cross_call_contradiction_detection(
        **fixture["input"],
        llm_call_trace_path=TRACE_RELATIVE_PATH,
        persist_llm_call_trace=True,
    )

    assert module.validate_req_036_cross_call_contradiction_detection(first_payload) == []
    assert module.validate_req_036_cross_call_contradiction_detection(second_payload) == []

    assert TRACE_PATH.exists()
    trace_rows = _read_jsonl(TRACE_PATH)
    assert trace_rows == first_payload["llm_call_trace"]["rows"]
    assert trace_rows == second_payload["llm_call_trace"]["rows"]
    assert len(trace_rows) == len(fixture["input"]["call_outputs"])

    for row in trace_rows:
        assert row["call_objective"]
        assert row["input_refs"]
        assert row["output_refs"]
        assert row["handoff_summary"]

    assert first_payload["llm_call_trace"]["sha256"] == second_payload["llm_call_trace"]["sha256"]
