#!/usr/bin/env python3
"""LLM planner utilities for OP plan generation."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class PlannerError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class BundleArtifact:
    rel_path: Path
    content_type: str
    content: Any
    checksum_sha256: str


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_checksum(content_type: str, content: Any) -> str:
    if content_type == "json":
        payload = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return _sha256_bytes(payload)
    if content_type == "text":
        if not isinstance(content, str):
            raise PlannerError("planner_bundle_schema_error", "text artifact content must be string")
        return _sha256_bytes(content.encode("utf-8"))
    raise PlannerError("planner_bundle_schema_error", f"unsupported content_type: {content_type}")


def _normalize_rel_path(raw: str, planning_root: Path) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute():
        resolved = candidate.resolve()
        try:
            rel = resolved.relative_to(planning_root)
        except ValueError as exc:
            raise PlannerError("planner_bundle_schema_error", f"artifact_path outside planning root: {raw}") from exc
        return rel
    rel = candidate
    resolved = (planning_root / rel).resolve()
    try:
        resolved.relative_to(planning_root)
    except ValueError as exc:
        raise PlannerError("planner_bundle_schema_error", f"artifact_path escapes planning root: {raw}") from exc
    return rel


def parse_bundle_jsonl(bundle_path: Path, planning_root: Path) -> dict[str, BundleArtifact]:
    if not bundle_path.exists():
        raise PlannerError("planner_bundle_missing", f"planner bundle missing: {bundle_path}")
    try:
        lines = bundle_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise PlannerError("planner_bundle_parse_error", f"unable to read planner bundle: {exc}") from exc

    out: dict[str, BundleArtifact] = {}
    if not lines:
        raise PlannerError("planner_bundle_parse_error", "planner bundle is empty")

    for idx, line in enumerate(lines, start=1):
        text = line.strip()
        if not text:
            continue
        try:
            row = json.loads(text)
        except json.JSONDecodeError as exc:
            raise PlannerError("planner_bundle_parse_error", f"line {idx}: invalid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise PlannerError("planner_bundle_schema_error", f"line {idx}: row must be object")

        artifact_path_raw = row.get("artifact_path")
        content_type = row.get("content_type")
        content = row.get("content")
        checksum = row.get("checksum_sha256")

        if not isinstance(artifact_path_raw, str) or not artifact_path_raw.strip():
            raise PlannerError("planner_bundle_schema_error", f"line {idx}: artifact_path must be non-empty string")
        if content_type not in {"json", "text"}:
            raise PlannerError("planner_bundle_schema_error", f"line {idx}: content_type must be json|text")
        if not isinstance(checksum, str) or not checksum.strip():
            raise PlannerError("planner_bundle_schema_error", f"line {idx}: checksum_sha256 must be non-empty string")
        if content_type == "json" and not isinstance(content, (dict, list)):
            raise PlannerError("planner_bundle_schema_error", f"line {idx}: json content must be object or array")
        if content_type == "text" and not isinstance(content, str):
            raise PlannerError("planner_bundle_schema_error", f"line {idx}: text content must be string")

        rel_path = _normalize_rel_path(artifact_path_raw.strip(), planning_root)
        rel_key = str(rel_path.as_posix())
        if rel_key in out:
            raise PlannerError("planner_bundle_schema_error", f"line {idx}: duplicate artifact_path {rel_key}")

        expected_checksum = canonical_checksum(content_type, content)
        if expected_checksum != checksum.strip():
            raise PlannerError(
                "planner_bundle_schema_error",
                f"line {idx}: checksum mismatch for {rel_key}",
            )

        out[rel_key] = BundleArtifact(
            rel_path=rel_path,
            content_type=content_type,
            content=content,
            checksum_sha256=checksum.strip(),
        )

    if not out:
        raise PlannerError("planner_bundle_parse_error", "planner bundle has no artifact rows")
    return out


def materialize_bundle(bundle: dict[str, BundleArtifact], planning_root: Path) -> list[Path]:
    written: list[Path] = []
    for artifact in bundle.values():
        target = (planning_root / artifact.rel_path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        if artifact.content_type == "json":
            payload = json.dumps(artifact.content, indent=2, sort_keys=False, ensure_ascii=False) + "\n"
            target.write_text(payload, encoding="utf-8")
        else:
            text = artifact.content
            if not text.endswith("\n"):
                text += "\n"
            target.write_text(text, encoding="utf-8")
        written.append(target)
    return written


def render_prompt(
    template_text: str,
    *,
    repo_root: Path,
    bundle_path: Path,
    validator_command: str,
    example_root: Path,
    mission_source: str,
    scope_source: str,
    map_path: Path,
    arch_path: Path,
) -> str:
    out = template_text
    replacements = {
        "{{REPO_ROOT}}": str(repo_root),
        "{{BUNDLE_PATH}}": str(bundle_path),
        "{{VALIDATOR_COMMAND}}": validator_command,
        "{{EXAMPLE_ROOT}}": str(example_root),
        "{{MISSION_SOURCE}}": mission_source,
        "{{SCOPE_SOURCE}}": scope_source,
        "{{MAP_PATH}}": str(map_path),
        "{{ARCH_PATH}}": str(arch_path),
    }
    for key, value in replacements.items():
        out = out.replace(key, value)
    return out


def run_codex_exec(
    *,
    repo_root: Path,
    prompt_text: str,
    output_last_message: Path,
    stdout_path: Path,
    stderr_path: Path,
    codex_home: str | None = None,
) -> int:
    output_last_message.parent.mkdir(parents=True, exist_ok=True)
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "codex",
        "exec",
        "--dangerously-bypass-approvals-and-sandbox",
        "-c",
        'model_reasoning_effort="xhigh"',
        "--cd",
        str(repo_root),
        "--output-last-message",
        str(output_last_message),
        "-",
    ]
    env = None
    codex_home_text = (codex_home or "").strip()
    if codex_home_text:
        env = os.environ.copy()
        env["CODEX_HOME"] = codex_home_text

    proc = subprocess.run(
        cmd,
        cwd=str(repo_root),
        input=prompt_text,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    stdout_path.write_text(proc.stdout or "", encoding="utf-8")
    stderr_path.write_text(proc.stderr or "", encoding="utf-8")
    return int(proc.returncode)
