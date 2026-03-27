#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SHA1_RE = re.compile(r"^[0-9a-f]{40}$")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _log(message: str) -> None:
    print(f"[{_stamp()}] {message}", flush=True)


def _fail(message: str) -> int:
    _log(f"FAIL: {message}")
    return 1


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate lane merge evidence for an Optimus merge task.",
    )
    parser.add_argument("--task-id", required=True, help="Task identifier such as TASK-028.")
    parser.add_argument("--lane-id", required=True, help="Lane identifier such as phase-3/lane-a.")
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Earth repo root that contains reports/ and project artifacts. Defaults to the current directory.",
    )
    parser.add_argument(
        "--require-ancestor",
        action="store_true",
        help="Require git ancestry validation that lane-base already contains the run-base tip.",
    )
    return parser.parse_args()


def _discover_repo_root(start: Path) -> Path:
    for candidate in [start.resolve(), *start.resolve().parents]:
        evidence_root = candidate / "reports" / "optimus-prime" / "planning" / "evidence"
        if evidence_root.exists() and (candidate / "DeepMCP").exists():
            return candidate
    raise FileNotFoundError(
        f"could not discover Earth repo root from {start}; pass --repo-root explicitly"
    )


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_merge_evidence(repo_root: Path, task_id: str) -> Path:
    evidence_dir = repo_root / "reports" / "optimus-prime" / "planning" / "evidence" / task_id
    candidates = sorted(evidence_dir.glob("*MERGE_EVIDENCE*.json"))
    if candidates:
        return candidates[-1]

    task_token = task_id.replace("-", "_")
    docs_candidates = sorted((repo_root / "DeepMCP" / "docs").glob(f"*{task_token}*MERGE_EVIDENCE*.json"))
    if docs_candidates:
        return docs_candidates[-1]

    raise FileNotFoundError(
        f"no merge evidence JSON found for {task_id} under {evidence_dir} or DeepMCP/docs"
    )


def _require_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing required string field: {key}")
    return value.strip()


def _require_sha(payload: dict[str, Any], key: str) -> str:
    value = _require_string(payload, key)
    if not SHA1_RE.fullmatch(value):
        raise ValueError(f"{key} must be a 40-character git SHA")
    return value


def _ensure_commit_exists(repo_root: Path, sha: str, label: str) -> None:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", f"{sha}^{{commit}}"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ValueError(f"{label} does not resolve to a commit in this repo: {sha}")


def _validate_review_summary(repo_root: Path, payload: dict[str, Any]) -> None:
    review = payload.get("review_summary")
    if not isinstance(review, dict):
        raise ValueError("missing review_summary object")
    review_path_raw = _require_string(review, "path")
    review_status = _require_string(review, "review_status")
    blocker_status = _require_string(review, "blocker_status")
    if review_status != "pass":
        raise ValueError(f"review_summary.review_status must be pass, got {review_status}")
    if blocker_status != "none":
        raise ValueError(f"review_summary.blocker_status must be none, got {blocker_status}")
    review_path = repo_root / review_path_raw
    if not review_path.exists():
        raise ValueError(f"review summary file does not exist: {review_path_raw}")


def _validate_targeted_test(payload: dict[str, Any]) -> None:
    targeted = payload.get("targeted_test")
    if not isinstance(targeted, dict):
        raise ValueError("missing targeted_test object")
    _require_string(targeted, "command")
    result = _require_string(targeted, "result")
    if result != "pass":
        raise ValueError(f"targeted_test.result must be pass, got {result}")


def _validate_ancestor(
    repo_root: Path,
    lane_base_branch: str,
    run_base_branch: str,
    ancestor_verification: dict[str, Any],
) -> None:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", run_base_branch, lane_base_branch],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ValueError(
            f"git ancestry check failed: run-base {run_base_branch} is not an ancestor of {lane_base_branch}"
        )
    if ancestor_verification.get("result") != "pass":
        raise ValueError("ancestor_verification.result must be pass when --require-ancestor is set")
    if ancestor_verification.get("lane_base_contains_latest_run_base") is not True:
        raise ValueError("ancestor_verification.lane_base_contains_latest_run_base must be true")


def main() -> int:
    args = _parse_args()
    requested_root = Path(args.repo_root)
    repo_root = _discover_repo_root(Path.cwd()) if args.repo_root == "." else requested_root.resolve()
    _log(
        f"Starting merge evidence validation for {args.task_id} on {args.lane_id} from repo root {repo_root}."
    )

    try:
        evidence_path = _find_merge_evidence(repo_root, args.task_id)
        payload = _load_json(evidence_path)

        task_identifier = _require_string(payload, "task_identifier")
        lane_id = _require_string(payload, "lane_id")
        lane_base_branch = _require_string(payload, "lane_base_branch")
        run_base_branch = _require_string(payload, "run_base_branch")
        run_base_before_sha = _require_sha(payload, "run_base_before_sha")
        run_base_after_sha = _require_sha(payload, "run_base_after_sha")

        merge_commit_sha = payload.get("merge_commit_sha")
        squash_rebase_proof = payload.get("squash_rebase_proof")
        if isinstance(merge_commit_sha, str) and merge_commit_sha.strip():
            merge_commit_sha = merge_commit_sha.strip()
            if not SHA1_RE.fullmatch(merge_commit_sha):
                raise ValueError("merge_commit_sha must be a 40-character git SHA when present")
            _ensure_commit_exists(repo_root, merge_commit_sha, "merge_commit_sha")
        elif isinstance(squash_rebase_proof, dict):
            proof_sha = _require_sha(squash_rebase_proof, "head_sha")
            _ensure_commit_exists(repo_root, proof_sha, "squash_rebase_proof.head_sha")
        else:
            raise ValueError("evidence must include merge_commit_sha or squash_rebase_proof")

        if task_identifier != args.task_id:
            raise ValueError(f"task_identifier mismatch: expected {args.task_id}, got {task_identifier}")
        if lane_id != args.lane_id:
            raise ValueError(f"lane_id mismatch: expected {args.lane_id}, got {lane_id}")

        _ensure_commit_exists(repo_root, run_base_before_sha, "run_base_before_sha")
        _ensure_commit_exists(repo_root, run_base_after_sha, "run_base_after_sha")

        ancestor_verification = payload.get("ancestor_verification")
        if not isinstance(ancestor_verification, dict):
            raise ValueError("missing ancestor_verification object")
        _require_string(ancestor_verification, "command")
        _require_sha(ancestor_verification, "lane_base_head_sha")
        _require_sha(ancestor_verification, "run_base_head_sha")

        _validate_targeted_test(payload)
        _validate_review_summary(repo_root, payload)

        if args.require_ancestor:
            _validate_ancestor(repo_root, lane_base_branch, run_base_branch, ancestor_verification)

        _log(f"PASS: merge evidence is valid at {evidence_path.relative_to(repo_root)}.")
        return 0
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        return _fail(str(exc))


if __name__ == "__main__":
    sys.exit(main())
