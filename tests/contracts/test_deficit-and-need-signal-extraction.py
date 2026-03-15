import importlib.util
import json
import subprocess
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "strategy_context_sweep.py"
FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "examples"
    / "fixtures"
    / "deficit-and-need-signal-extraction.json"
)
SPEC = importlib.util.spec_from_file_location("strategy_context_sweep", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _load_fixture_payload() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_extracts_high_leverage_need_signals_with_scoring_and_evidence() -> None:
    payload = _load_fixture_payload()

    out = MODULE.run(payload)

    assert out["ok"] is True
    assert out["analysis_type"] == "deficit_and_need_signal_extraction"
    assert out["checked_at_utc"] == "2026-03-14T21:00:00Z"
    assert out["analysis_anchors"] == [
        "unmet_ecosystem_needs",
        "high_leverage_fit",
        "impact",
        "urgency",
    ]
    assert out["totals"] == {
        "deficits": 4,
        "eligible": 2,
        "signals": 2,
        "excluded": 2,
        "evidence_references": 3,
    }

    need_signals = out["need_signals"]
    assert [row["signal_id"] for row in need_signals] == ["NEED-0001", "NEED-0002"]
    assert [row["deficit_id"] for row in need_signals] == ["DEF-001", "DEF-002"]
    assert need_signals[0]["priority_score"] == 72.0
    assert need_signals[0]["leverage_ratio"] == 1.0
    assert need_signals[0]["evidence_refs"] == ["EVD-0001", "EVD-0002"]
    assert need_signals[1]["priority_score"] == 63.0
    assert need_signals[1]["evidence_refs"] == ["EVD-0003"]

    excluded = {row["deficit_id"]: row for row in out["excluded_deficits"]}
    assert excluded["DEF-003"]["reason_code"] == "leverage_below_threshold"
    assert excluded["DEF-003"]["failed_criteria"] == ["leverage_below_threshold"]
    assert excluded["DEF-004"]["reason_code"] == "multiple_threshold_failures"
    assert excluded["DEF-004"]["failed_criteria"] == [
        "impact_below_threshold",
        "urgency_below_threshold",
        "leverage_below_threshold",
    ]

    evidence_rows = out["evidence_references"]
    assert [row["citation_id"] for row in evidence_rows] == ["EVD-0001", "EVD-0002", "EVD-0003"]
    assert evidence_rows[0]["upstream_evidence_ref"] == "OBS-TELEM-001"
    assert evidence_rows[-1]["deficit_id"] == "DEF-002"

    recommendation = out["recommendation"]
    assert recommendation["decision"] == "prioritize_need_signals"
    assert recommendation["top_signal_id"] == "NEED-0001"
    assert recommendation["evidence_refs"] == ["EVD-0001", "EVD-0002", "EVD-0003"]


def test_respects_max_signals_cap() -> None:
    payload = _load_fixture_payload()
    payload["max_signals"] = 1

    out = MODULE.run(payload)

    assert out["ok"] is True
    assert out["totals"] == {
        "deficits": 4,
        "eligible": 2,
        "signals": 1,
        "excluded": 3,
        "evidence_references": 2,
    }

    assert [row["signal_id"] for row in out["need_signals"]] == ["NEED-0001"]
    assert [row["deficit_id"] for row in out["need_signals"]] == ["DEF-001"]

    excluded = {row["deficit_id"]: row for row in out["excluded_deficits"]}
    assert excluded["DEF-002"]["reason_code"] == "max_signals_cap_reached"
    assert excluded["DEF-002"]["failed_criteria"] == ["max_signals_cap_reached"]


def test_cli_contract_returns_zero_on_fixture(tmp_path: Path) -> None:
    payload = _load_fixture_payload()
    input_json = tmp_path / "input.json"
    input_json.write_text(json.dumps(payload), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--input-json", str(input_json)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    assert out["ok"] is True
    assert out["analysis_type"] == "deficit_and_need_signal_extraction"
    assert out["totals"]["signals"] == 2
