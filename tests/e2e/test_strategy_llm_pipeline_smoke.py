import json
import subprocess
import sys
from pathlib import Path

from scripts import strategy_llm_pipeline as module

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "strategy_llm_pipeline.py"
REQ_025_FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "multi-call-strategy-pipeline-planner.json"
REQ_029_FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "call-4-recommendation-synthesis.json"
TRACE_PATH = REPO_ROOT / module.LLM_CALL_TRACE_RELATIVE_PATH


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _run_cli_fixture(tmp_path: Path, fixture_path: Path) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    input_path.write_text(json.dumps(fixture["input"], indent=2), encoding="utf-8")
    first_run = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--input-json", str(input_path), "--output-json", str(output_path), "--json-pretty"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return first_run, input_path, output_path


def test_strategy_llm_pipeline_cli_writes_replay_stable_trace_file(tmp_path: Path) -> None:
    first_run, input_path, output_path = _run_cli_fixture(tmp_path, REQ_025_FIXTURE_PATH)

    assert first_run.returncode == 0, f"stdout={first_run.stdout}\nstderr={first_run.stderr}"
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert module.validate_req_025_multi_call_strategy_pipeline_planner(payload) == []

    trace_text = TRACE_PATH.read_text(encoding="utf-8")
    trace_rows = _read_jsonl(TRACE_PATH)
    assert trace_rows == payload["call_metadata"]["llm_call_trace_rows"]
    assert len(trace_rows) == payload["multi_call_strategy_pipeline_planner_entrypoint"]["call_depth"]
    assert all(row["call_objective"] for row in trace_rows)
    assert all(row["input_refs"] for row in trace_rows)
    assert all(row["output_refs"] for row in trace_rows)
    assert all(row["handoff_summary"] for row in trace_rows)

    second_output_path = tmp_path / "output-second.json"
    second_run = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--input-json", str(input_path), "--output-json", str(second_output_path), "--json-pretty"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert second_run.returncode == 0, f"stdout={second_run.stdout}\nstderr={second_run.stderr}"
    assert second_output_path.read_text(encoding="utf-8") == output_path.read_text(encoding="utf-8")
    assert TRACE_PATH.read_text(encoding="utf-8") == trace_text


def test_strategy_llm_pipeline_cli_writes_replay_stable_trace_file_for_req_029(tmp_path: Path) -> None:
    first_run, input_path, output_path = _run_cli_fixture(tmp_path, REQ_029_FIXTURE_PATH)

    assert first_run.returncode == 0, f"stdout={first_run.stdout}\nstderr={first_run.stderr}"
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert module.validate_req_029_call_4_recommendation_synthesis(payload) == []

    trace_text = TRACE_PATH.read_text(encoding="utf-8")
    trace_rows = _read_jsonl(TRACE_PATH)
    assert trace_rows == payload["call_metadata"]["llm_call_trace_rows"]
    assert [row["call_id"] for row in trace_rows] == ["call-1", "call-2", "call-3", "call-4"]
    assert all(row["call_objective"] for row in trace_rows)
    assert all(row["input_refs"] for row in trace_rows)
    assert all(row["output_refs"] for row in trace_rows)
    assert all(row["handoff_summary"] for row in trace_rows)

    second_output_path = tmp_path / "output-second.json"
    second_run = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--input-json", str(input_path), "--output-json", str(second_output_path), "--json-pretty"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert second_run.returncode == 0, f"stdout={second_run.stdout}\nstderr={second_run.stderr}"
    assert second_output_path.read_text(encoding="utf-8") == output_path.read_text(encoding="utf-8")
    assert TRACE_PATH.read_text(encoding="utf-8") == trace_text
