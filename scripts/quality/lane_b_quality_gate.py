#!/usr/bin/env python3
"""Deterministic Lane B quality gate for reliability-first release checks."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
MANIFEST_REL = Path("scripts") / "quality" / "lane_b_required_tests.json"
ARTIFACT_REL = Path("reports") / "optimus-prime" / "planning" / "LANE_B_QUALITY_GATE.json"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_cmd(repo_root: Path, cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(repo_root),
        text=True,
        capture_output=True,
        check=False,
    )


def read_manifest(repo_root: Path) -> dict[str, Any]:
    path = (repo_root / MANIFEST_REL).resolve()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("lane_b_required_tests.json must be a JSON object")
    return payload


def as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    return out


def run_required_risk_tests(repo_root: Path, required_tests: list[str]) -> tuple[bool, list[str]]:
    failed: list[str] = []
    for nodeid in required_tests:
        proc = run_cmd(repo_root, [sys.executable, "-m", "pytest", "-q", nodeid])
        if proc.returncode != 0:
            failed.append(nodeid)
    return len(failed) == 0, sorted(failed)


def run_full_matrix(repo_root: Path, targets: list[str]) -> bool:
    if not targets:
        return False
    proc = run_cmd(repo_root, [sys.executable, "-m", "pytest", *targets])
    return proc.returncode == 0


def parse_coverage_json(path: Path, coverage_targets: list[str]) -> dict[str, float]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    files = payload.get("files") if isinstance(payload, dict) else None
    if not isinstance(files, dict):
        return {}
    module_coverage: dict[str, float] = {}
    for target in coverage_targets:
        target_norm = target.replace("\\", "/")
        percent: float | None = None
        for file_path, details in files.items():
            if not isinstance(file_path, str) or not isinstance(details, dict):
                continue
            file_norm = file_path.replace("\\", "/")
            if not file_norm.endswith(target_norm):
                continue
            summary = details.get("summary") if isinstance(details.get("summary"), dict) else {}
            raw_percent = summary.get("percent_covered")
            if isinstance(raw_percent, (int, float)):
                percent = float(raw_percent)
                break
            display = summary.get("percent_covered_display")
            try:
                percent = float(display) if display is not None else None
            except (TypeError, ValueError):
                percent = None
        if percent is not None:
            module_coverage[target] = round(percent, 2)
    return module_coverage


def run_coverage_snapshot(repo_root: Path, matrix_targets: list[str], coverage_targets: list[str]) -> tuple[bool, dict[str, float]]:
    if not matrix_targets or not coverage_targets:
        return False, {}
    planning_dir = (repo_root / "reports" / "optimus-prime" / "planning").resolve()
    planning_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix="lane_b_cov_",
        suffix=".json",
        dir=str(planning_dir),
        delete=False,
    ) as fh:
        cov_path = Path(fh.name)
    coverage_roots = sorted({target.split("/", 1)[0] for target in coverage_targets if "/" in target} | {"scripts", "skills"})
    cmd = [sys.executable, "-m", "pytest", *matrix_targets, "-q"]
    for root in coverage_roots:
        cmd.append(f"--cov={root}")
    cmd.append(f"--cov-report=json:{cov_path}")
    proc = run_cmd(repo_root, cmd)
    module_coverage = parse_coverage_json(cov_path, coverage_targets)
    try:
        cov_path.unlink()
    except OSError:
        pass
    return proc.returncode == 0 and len(module_coverage) > 0, module_coverage


def write_artifact(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic Lane B quality gate.")
    parser.add_argument("--repo-root", required=True, help="Absolute repo root path")
    args = parser.parse_args()
    repo_root = Path(args.repo_root).expanduser().resolve()

    manifest = read_manifest(repo_root)
    required_tests = as_str_list(manifest.get("required_risk_tests"))
    matrix_targets = as_str_list(manifest.get("full_matrix_targets"))
    coverage_targets = as_str_list(manifest.get("coverage_targets"))

    risk_tests_passed, failed_risk_tests = run_required_risk_tests(repo_root, required_tests)
    matrix_passed = run_full_matrix(repo_root, matrix_targets)
    coverage_collected, module_coverage = run_coverage_snapshot(repo_root, matrix_targets, coverage_targets)

    gate_passed = risk_tests_passed and matrix_passed and coverage_collected
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "matrix_passed": matrix_passed,
        "risk_tests_passed": risk_tests_passed,
        "required_risk_tests": required_tests,
        "failed_risk_tests": failed_risk_tests,
        "module_coverage": module_coverage,
        "status": "passed" if gate_passed else "blocked",
        "next_action": (
            "Lane B quality gate passed. Proceed with release workflow."
            if gate_passed
            else "Run scripts/quality/run_lane_b_quality.sh and fix failing required risk tests or matrix errors."
        ),
    }
    artifact_path = (repo_root / ARTIFACT_REL).resolve()
    write_artifact(artifact_path, artifact)
    print(json.dumps(artifact, indent=2, sort_keys=False))
    return 0 if gate_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
