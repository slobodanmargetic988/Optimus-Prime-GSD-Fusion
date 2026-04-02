import importlib.util
import json
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "strategy_context_sweep.py"
SPEC = importlib.util.spec_from_file_location("strategy_context_sweep", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


FIXTURE_PATH = Path(__file__).resolve().parents[2] / "examples" / "fixtures" / "interface-contract-extraction.json"


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_req012_extracts_relevant_shared_interface_contracts_only():
    payload = _load_fixture()
    out = MODULE.extract_interface_contracts(payload, generated_at="2026-03-15T00:00:00Z")

    assert out["schema_version"] == "REQ-012-interface-contract-extraction.v1"
    assert out["generated_at"] == "2026-03-15T00:00:00Z"
    assert out["current_project_id"] == "optimus-prime-gsd-fusion"
    assert out["summary"]["earth_contract_source_count"] == 3
    assert out["summary"]["relevant_source_count"] == 2
    assert out["summary"]["shared_interface_contract_count"] == 3
    assert out["summary"]["required_obligation_count"] == 3
    assert out["summary"]["optional_obligation_count"] == 3
    assert out["summary"]["total_obligation_count"] == 6

    interfaces = out["shared_interface_contracts"]
    interface_ids = {row["interface_id"] for row in interfaces}
    assert interface_ids == {"planning-packet.v2", "telemetry-handshake.v1", "fusion-evidence.v1"}
    assert "ops-control-channel.v1" not in interface_ids


def test_req012_marks_required_vs_optional_obligations_with_provenance():
    payload = _load_fixture()
    out = MODULE.extract_interface_contracts(payload, generated_at="2026-03-15T00:00:00Z")

    level_map = {
        interface["interface_id"]: {row["obligation_level"] for row in interface["obligations"]}
        for interface in out["shared_interface_contracts"]
    }
    assert level_map["planning-packet.v2"] == {"required", "optional"}
    assert level_map["telemetry-handshake.v1"] == {"required", "optional"}
    assert level_map["fusion-evidence.v1"] == {"required", "optional"}

    for interface in out["shared_interface_contracts"]:
        for obligation in interface["obligations"]:
            assert obligation["obligation_level"] in {"required", "optional"}
            assert isinstance(obligation["statement"], str) and obligation["statement"]
            provenance = obligation["source_provenance"]
            assert isinstance(provenance, list) and provenance
            entry = provenance[0]
            assert isinstance(entry["source_id"], str) and entry["source_id"]
            assert entry["source_path"].startswith("earth/contracts/")
            assert isinstance(entry["line_number"], int) and entry["line_number"] > 0
            assert isinstance(entry["source_sha256"], str) and len(entry["source_sha256"]) == 64
            assert entry["excerpt"] == obligation["statement"]


def test_req012_file_writer_emits_deterministic_surface(tmp_path: Path):
    output_path = tmp_path / "REQ-012.sample.json"
    out = MODULE.extract_interface_contracts_file(
        input_path=FIXTURE_PATH,
        output_path=output_path,
        generated_at="2026-03-15T00:00:00Z",
    )

    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written == out
    assert written["schema_version"] == "REQ-012-interface-contract-extraction.v1"
    assert written["summary"]["total_obligation_count"] == 6
