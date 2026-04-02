#!/usr/bin/env python3
"""Shared LLM-first strategy runner for OP and standalone CLI usage."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from planner.llm_planner import run_codex_exec


DEFAULT_STRATEGY_MANIFEST_REL = Path("strategy") / "STRATEGY_MANIFEST.md"
DEFAULT_STRATEGY_PACKET_REL = Path("strategy") / "current" / "strategy_packet.md"
DEFAULT_STRATEGY_SUMMARY_REL = Path("strategy") / "current" / "STRATEGY_SUMMARY.md"
INLINE_STRATEGY_MANIFEST_LABEL = "<inline strategy manifest>"
STRATEGY_MAX_ATTEMPTS = 3


class StrategyRunnerError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class StrategyManifestSource:
    mode: str
    display: str
    path: Path | None
    text: str | None


@dataclass(frozen=True)
class StrategyRunResult:
    manifest_ref: str
    packet_path: Path
    summary_path: Path
    artifacts: list[str]


def resolve_strategy_manifest_path(repo_root: Path, manifest_file: str | None = None) -> Path:
    base = Path(manifest_file).expanduser() if manifest_file else repo_root / DEFAULT_STRATEGY_MANIFEST_REL
    if not base.is_absolute():
        base = repo_root / base
    return base.resolve()


def resolve_strategy_manifest_source(
    *,
    repo_root: Path,
    manifest: str | None = None,
    manifest_file: str | None = None,
) -> StrategyManifestSource:
    manifest_text = (manifest or "").strip()
    manifest_file_text = (manifest_file or "").strip()
    if manifest_text and manifest_file_text:
        raise StrategyRunnerError(
            "strategy_manifest_conflict",
            "provide either inline strategy manifest text or strategy_manifest_file, not both",
        )
    if manifest_text:
        return StrategyManifestSource(
            mode="inline",
            display=INLINE_STRATEGY_MANIFEST_LABEL,
            path=None,
            text=manifest,
        )

    manifest_path = resolve_strategy_manifest_path(repo_root, manifest_file_text or None)
    if not manifest_path.exists():
        raise StrategyRunnerError("strategy_manifest_missing", f"strategy manifest does not exist: {manifest_path}")
    if not manifest_path.is_file():
        raise StrategyRunnerError("strategy_manifest_invalid", f"strategy manifest must be a file: {manifest_path}")
    return StrategyManifestSource(
        mode="file",
        display=str(manifest_path),
        path=manifest_path,
        text=None,
    )


def build_planner_strategy_note(*, skip_strategy: bool) -> str:
    if skip_strategy:
        return ""
    packet_rel = DEFAULT_STRATEGY_PACKET_REL.as_posix()
    summary_rel = DEFAULT_STRATEGY_SUMMARY_REL.as_posix()
    return "\n".join(
        [
            "",
            "Strategy artifact discovery (optional but important):",
            f"- Check whether `{packet_rel}` exists.",
            f"- Check whether `{summary_rel}` exists.",
            "- If either file exists, open and ingest it fully before planning.",
            "- Treat strategy artifacts as optional planning context that may sharpen priorities, constraints, sequencing, and cross-project awareness.",
            "- If strategy artifacts are absent, continue planning normally without them.",
            "- In `STATE.md`, explicitly record whether strategy artifacts were found and used for this plan.",
        ]
    )


def run_strategy(
    *,
    repo_root: Path,
    manifest: str | None = None,
    manifest_file: str | None = None,
    emit: Callable[[str], None] | None = None,
    codex_home: str | None = None,
) -> StrategyRunResult:
    repo_root = repo_root.resolve()
    manifest_source = resolve_strategy_manifest_source(
        repo_root=repo_root,
        manifest=manifest,
        manifest_file=manifest_file,
    )
    packet_path, summary_path = resolve_strategy_output_paths(repo_root)
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    previous_outputs = _snapshot_existing_outputs(packet_path, summary_path)
    if emit:
        emit(f"strategy manifest source ready: {manifest_source.display}")
    prior_errors: list[dict[str, str]] = []
    last_missing_outputs: list[str] = []
    with tempfile.TemporaryDirectory(prefix="op-strategy-") as tmp_dir:
        temp_root = Path(tmp_dir)
        for attempt in range(1, STRATEGY_MAX_ATTEMPTS + 1):
            last_message_path = temp_root / f"attempt-{attempt}-last_message.txt"
            stdout_path = temp_root / f"attempt-{attempt}-stdout.log"
            stderr_path = temp_root / f"attempt-{attempt}-stderr.log"
            prompt_text = _build_strategy_prompt(
                repo_root=repo_root,
                manifest_source=manifest_source,
                packet_path=packet_path,
                summary_path=summary_path,
                prior_errors=prior_errors,
            )
            if emit:
                emit(f"running strategy generation attempt {attempt}/{STRATEGY_MAX_ATTEMPTS}")
            _clear_strategy_outputs(packet_path, summary_path)
            try:
                run_codex_exec(
                    repo_root=repo_root,
                    prompt_text=prompt_text,
                    output_last_message=last_message_path,
                    stdout_path=stdout_path,
                    stderr_path=stderr_path,
                    codex_home=codex_home,
                )
            except OSError as exc:
                _restore_previous_outputs(previous_outputs)
                raise StrategyRunnerError("strategy_execution_failed", f"unable to invoke codex exec: {exc}") from exc

            last_missing_outputs = _missing_strategy_outputs(packet_path, summary_path)
            if not last_missing_outputs:
                if emit:
                    emit(f"strategy packet written: {_relative_to_repo_or_abs(repo_root, packet_path)}")
                    emit(f"strategy summary written: {_relative_to_repo_or_abs(repo_root, summary_path)}")
                artifacts = [str(path) for path in (manifest_source.path, packet_path, summary_path) if path is not None]
                return StrategyRunResult(
                    manifest_ref=manifest_source.display,
                    packet_path=packet_path,
                    summary_path=summary_path,
                    artifacts=artifacts,
                )

            stderr_text = stderr_path.read_text(encoding="utf-8") if stderr_path.exists() else ""
            last_message_text = last_message_path.read_text(encoding="utf-8") if last_message_path.exists() else ""
            failure_message = (
                "strategy outputs were not written to disk: "
                + ", ".join(last_missing_outputs)
            )
            detail_text = (last_message_text.strip() or stderr_text.strip())
            if detail_text:
                failure_message += f". Last model message: {detail_text}"
            prior_errors = [
                {
                    "code": "strategy_output_missing",
                    "message": failure_message,
                }
            ]
            if emit:
                emit(
                    f"strategy generation attempt {attempt} did not create required files; "
                    + ", ".join(last_missing_outputs)
                )

    _restore_previous_outputs(previous_outputs)
    raise StrategyRunnerError(
        "strategy_output_missing",
        "strategy outputs were not written after "
        f"{STRATEGY_MAX_ATTEMPTS} attempts: {', '.join(last_missing_outputs)}",
    )


def resolve_strategy_output_paths(repo_root: Path) -> tuple[Path, Path]:
    packet_path = (repo_root / DEFAULT_STRATEGY_PACKET_REL).resolve()
    summary_path = (repo_root / DEFAULT_STRATEGY_SUMMARY_REL).resolve()
    return packet_path, summary_path


def _relative_to_repo_or_abs(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _build_strategy_prompt(
    *,
    repo_root: Path,
    manifest_source: StrategyManifestSource,
    packet_path: Path,
    summary_path: Path,
    prior_errors: list[dict[str, str]] | None = None,
) -> str:
    manifest_section_lines = [
        "Strategy manifest source:",
    ]
    if manifest_source.mode == "inline":
        manifest_section_lines.extend(
            [
                f"- manifest_mode: {manifest_source.mode}",
                "- The full manifest was provided inline below.",
                "```md",
                (manifest_source.text or "").rstrip(),
                "```",
            ]
        )
    else:
        manifest_section_lines.extend(
            [
                f"- manifest_mode: {manifest_source.mode}",
                f"- manifest_path: {manifest_source.display}",
                "- Read that manifest file first, then decide what else to inspect.",
            ]
        )

    prompt = "\n".join(
        [
            "You are the strategy engine for an OP planning run.",
            "",
            "Your job is to read the strategy manifest first, decide what information is actually relevant, inspect the needed sources yourself, and then write two markdown artifacts directly into the repository.",
            "",
            "Operating rules:",
            "- Start with the provided strategy manifest source.",
            "- Let the manifest guide what to inspect. You decide which docs, files, directories, sibling projects, notes, contracts, specs, or other materials are relevant.",
            "- Do not rely on the caller to pre-collect context for you.",
            "- Avoid indiscriminate repo-wide slop scanning. Be selective and evidence-driven so you do not waste context on irrelevant material.",
            "- If the manifest points to locations outside the repo, you may inspect them too.",
            "- If useful source material is in formats like markdown, txt, rst, adoc, json, yaml, docx, or pdf, read what you need using available tools.",
            "- Ground every recommendation in material you actually inspected. If something is missing or unreadable, say so instead of guessing.",
            "- Create or overwrite the required output files directly in the repository.",
            f"- Write the planner-facing packet to `{DEFAULT_STRATEGY_PACKET_REL.as_posix()}`.",
            f"- Write the human-facing summary to `{DEFAULT_STRATEGY_SUMMARY_REL.as_posix()}`.",
            "- Do not return file blocks, fenced file dumps, or markdown copies of the full files in your final message.",
            "- After writing the files, respond with a short confirmation that lists the file paths you wrote.",
            "",
            "Required packet sections:",
            "- Strategic Summary",
            "- Recommendations",
            "- Hard Constraints",
            "- Soft Preferences",
            "- Priority / Sequencing Hints",
            "- Cross-Project Considerations",
            "- Evidence / Sources",
            "- Planner Instructions",
            "",
            "Recommendation entry requirements:",
            "- stable recommendation id",
            "- priority",
            "- rationale",
            "- planner implication",
            "- evidence refs",
            "",
            "Summary requirements:",
            "- short, human-facing explanation of what planner should optimize, protect, sequence first, and avoid",
            "",
            f"repo_root: {repo_root}",
            f"packet_output_path: {_relative_to_repo_or_abs(repo_root, packet_path)}",
            f"summary_output_path: {_relative_to_repo_or_abs(repo_root, summary_path)}",
            "",
            *manifest_section_lines,
            "",
            "Write the two markdown files now.",
        ]
    )
    if prior_errors:
        prompt += "\n\nPrevious attempt issues:\n"
        for idx, row in enumerate(prior_errors, start=1):
            prompt += f"{idx}. [{row.get('code', 'unknown')}] {row.get('message', 'attempt failed')}\n"
    return prompt


def _snapshot_existing_outputs(packet_path: Path, summary_path: Path) -> dict[Path, str]:
    snapshots: dict[Path, str] = {}
    for path in (packet_path, summary_path):
        if path.exists():
            if not path.is_file():
                raise StrategyRunnerError("strategy_output_invalid", f"strategy output path must be a file: {path}")
            snapshots[path] = path.read_text(encoding="utf-8")
    return snapshots


def _restore_previous_outputs(snapshots: dict[Path, str]) -> None:
    for path, content in snapshots.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _clear_strategy_outputs(packet_path: Path, summary_path: Path) -> None:
    for path in (packet_path, summary_path):
        if path.exists():
            if not path.is_file():
                raise StrategyRunnerError("strategy_output_invalid", f"strategy output path must be a file: {path}")
            path.unlink()


def _missing_strategy_outputs(packet_path: Path, summary_path: Path) -> list[str]:
    missing: list[str] = []
    if not packet_path.exists():
        missing.append(DEFAULT_STRATEGY_PACKET_REL.as_posix())
    if not summary_path.exists():
        missing.append(DEFAULT_STRATEGY_SUMMARY_REL.as_posix())
    return missing
