#!/usr/bin/env python3
"""Prepare standardized workstation worktrees for worker handoff."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MAX_WORKSTATIONS = 10
LEGACY_SLOT_RE = re.compile(r"^workstation-(?:[1-9]|10)$")
MANAGER_SLOT_RE = re.compile(r"^workstation-(?:dev|test|review)-[1-3]$")
WORKTREE_NAME_ERROR = (
    "worktree name must be workstation-1 through workstation-10 "
    "or workstation-(dev|test|review)-[1-3]"
)
DEFAULT_ASSETS_MANIFEST_REL = Path("reports/optimus-prime/config/WORKSTATION_ASSETS.json")
DEFAULT_ASSETS_STATE_REL = Path("reports/optimus-prime/WORKSTATION_ASSET_STATE.json")
ROLE_VALUES = {"all", "developer", "tester", "reviewer"}


@dataclass
class WorktreeEntry:
    path: Path
    branch: str | None


@dataclass
class AssetSpec:
    asset_id: str
    source_raw: str
    target_raw: str
    mode: str
    required: bool
    roles: list[str]


@dataclass
class HydrationResult:
    ok: bool
    worktree_name: str
    worktree_path: Path
    role: str
    manifest_path: Path
    state_path: Path
    applied_assets: list[dict[str, Any]]
    missing_required: list[dict[str, Any]]
    missing_optional: list[dict[str, Any]]
    warnings: list[str]

def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=check, text=True, capture_output=True)


def git_root(repo_input: str) -> Path:
    result = run(
        ["git", "-C", repo_input, "rev-parse", "--show-toplevel"],
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "not a git repository")
    return Path(result.stdout.strip()).resolve()


def list_worktrees(repo_root: Path) -> list[WorktreeEntry]:
    result = run(
        ["git", "-C", str(repo_root), "worktree", "list", "--porcelain"],
        check=True,
    )
    entries: list[WorktreeEntry] = []
    current_path: str | None = None
    current_branch: str | None = None

    for line in result.stdout.splitlines():
        if not line:
            if current_path:
                entries.append(WorktreeEntry(path=Path(current_path).resolve(), branch=current_branch))
            current_path = None
            current_branch = None
            continue

        key, _, value = line.partition(" ")
        if key == "worktree":
            current_path = value
        elif key == "branch":
            current_branch = value.removeprefix("refs/heads/")

    if current_path:
        entries.append(WorktreeEntry(path=Path(current_path).resolve(), branch=current_branch))

    return entries


def slot_name_for_path(path: Path) -> str | None:
    name = path.name
    return name if (LEGACY_SLOT_RE.fullmatch(name) or MANAGER_SLOT_RE.fullmatch(name)) else None


def slot_sort_key(slot_name: str) -> tuple[int, str]:
    suffix = slot_name.rsplit("-", 1)[-1]
    try:
        order = int(suffix)
    except ValueError:
        order = 999
    return (order, slot_name)


def default_base_ref(repo_root: Path) -> str:
    result = run(
        ["git", "-C", str(repo_root), "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"],
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return "HEAD"


def default_worktrees_parent(repo_root: Path) -> Path:
    return (repo_root.parent / f".{repo_root.name}-workstations").resolve()


def revlist_count(repo_path: Path, revspec: str, right_only: bool) -> int:
    args = ["git", "-C", str(repo_path), "rev-list", "--count"]
    args.append("--right-only" if right_only else "--left-only")
    args.append(revspec)
    result = run(args, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"unable to evaluate rev-list for {revspec}")
    raw = result.stdout.strip() or "0"
    return int(raw)


def branch_exists(repo_path: Path, branch_name: str) -> bool:
    result = run(
        ["git", "-C", str(repo_path), "show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}"],
        check=False,
    )
    return result.returncode == 0


def branch_divergence(repo_path: Path, base_ref: str, branch_name: str) -> tuple[int, int]:
    ahead = revlist_count(repo_path, f"{base_ref}...{branch_name}", right_only=True)
    behind = revlist_count(repo_path, f"{base_ref}...{branch_name}", right_only=False)
    return ahead, behind


def working_tree_dirty(worktree_path: Path) -> bool:
    result = run(
        ["git", "-C", str(worktree_path), "status", "--porcelain"],
        check=True,
    )
    return bool(result.stdout.strip())


def checked_out_paths(
    all_worktrees: list[WorktreeEntry],
    branch_name: str,
    exclude_path: Path | None = None,
) -> list[Path]:
    conflicts: list[Path] = []
    for entry in all_worktrees:
        if entry.branch != branch_name:
            continue
        if exclude_path is not None and entry.path == exclude_path:
            continue
        conflicts.append(entry.path)
    return conflicts


def resolve_branch_name(
    *,
    requested_branch: str,
    all_worktrees: list[WorktreeEntry],
    repo_root: Path,
    exclude_path: Path | None,
    fallback_suffix: str | None,
    allow_existing_branch_ref: bool,
) -> tuple[str, bool, list[str], str | None]:
    conflicts = checked_out_paths(all_worktrees, requested_branch, exclude_path)
    if not conflicts:
        return requested_branch, False, [], None

    conflict_paths = [str(path) for path in conflicts]
    if not fallback_suffix:
        return requested_branch, False, conflict_paths, None

    suffix = fallback_suffix.strip()
    if not suffix or any(ch.isspace() for ch in suffix):
        return requested_branch, False, conflict_paths, "fallback suffix must be non-empty and contain no whitespace"

    base_candidate = f"{requested_branch}{suffix}"
    for idx in range(0, 100):
        candidate = base_candidate if idx == 0 else f"{base_candidate}-{idx + 1}"
        candidate_conflicts = checked_out_paths(all_worktrees, candidate, exclude_path)
        if candidate_conflicts:
            continue
        if branch_exists(repo_root, candidate) and not allow_existing_branch_ref:
            continue
        return candidate, True, conflict_paths, None

    return requested_branch, False, conflict_paths, "could not resolve unique fallback branch after 100 attempts"


def payload_base(
    *,
    repo_root: Path,
    base_ref: str,
    managed_count: int,
    output_mode: str,
    dry_run: bool,
) -> dict[str, object]:
    return {
        "repo_root": str(repo_root),
        "base_ref": base_ref,
        "managed_slots": managed_count,
        "max_workstations": MAX_WORKSTATIONS,
        "output": output_mode,
        "dry_run": dry_run,
    }


def emit_text(payload: dict[str, object]) -> None:
    if payload.get("ok"):
        print(f"[workstation] repo_root={payload.get('repo_root')}")
        print(f"[workstation] base_ref={payload.get('base_ref')}")
        print(f"[workstation] managed_slots={payload.get('managed_slots')}/{payload.get('max_workstations')}")
        if payload.get("worktree_name"):
            print(f"[workstation] worktree_name={payload.get('worktree_name')}")
        if payload.get("target_path"):
            print(f"[workstation] target_path={payload.get('target_path')}")
        if payload.get("branch_name_resolved"):
            print(f"[workstation] branch_name={payload.get('branch_name_resolved')}")
        if payload.get("branch_fallback_applied"):
            print(
                "[workstation] branch_fallback="
                f"requested={payload.get('branch_name_requested')} resolved={payload.get('branch_name_resolved')}"
            )
        if payload.get("branch_conflict_paths"):
            print(
                "[workstation] branch_conflict_paths=" + ",".join(payload.get("branch_conflict_paths", []))
            )
        if payload.get("repair_results"):
            for item in payload.get("repair_results", []):
                print(
                    "[workstation] repair "
                    f"slot={item.get('worktree_name')} branch={item.get('branch_name_resolved')} "
                    f"status={item.get('status')}"
                )
        if payload.get("message"):
            print(f"[workstation] {payload.get('message')}")
        return

    if payload.get("repo_root"):
        print(f"[workstation] repo_root={payload.get('repo_root')}")
    if payload.get("worktree_name"):
        print(f"[workstation] worktree_name={payload.get('worktree_name')}")
    if payload.get("branch_name_requested"):
        print(f"[workstation] branch_name={payload.get('branch_name_requested')}")
    if payload.get("base_ref"):
        print(f"[workstation] base_ref={payload.get('base_ref')}")
    if payload.get("target_path"):
        print(f"[workstation] target_path={payload.get('target_path')}")
    if payload.get("managed_slots") is not None and payload.get("max_workstations") is not None:
        print(f"[workstation] managed_slots={payload.get('managed_slots')}/{payload.get('max_workstations')}")
    print(f"[workstation] error: {payload.get('error')}", file=sys.stderr)


def emit(payload: dict[str, object], output_mode: str) -> int:
    if output_mode == "json":
        print(json.dumps(payload, sort_keys=True))
    else:
        emit_text(payload)
    return 0 if payload.get("ok") else 2


def fail(message: str, output_mode: str, context: dict[str, object]) -> int:
    payload = dict(context)
    payload.update({"ok": False, "error": message})
    return emit(payload, output_mode)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_load(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise RuntimeError(f"json root must be an object: {path}")
    return data


def _json_load_optional(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return _json_load(path)


def _json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def normalize_role(value: str | None) -> str:
    if not value:
        return "all"
    role = value.strip().lower()
    if role in {"dev", "developer"}:
        return "developer"
    if role in {"test", "tester", "qa"}:
        return "tester"
    if role in {"review", "reviewer"}:
        return "reviewer"
    if role not in ROLE_VALUES:
        return "all"
    return role


def infer_role_from_branch(branch_name: str | None) -> str:
    if not branch_name:
        return "all"
    b = branch_name.lower()
    if "/dev" in b or "-dev" in b:
        return "developer"
    if "/test" in b or "-test" in b or "qa" in b:
        return "tester"
    if "/review" in b or "-review" in b:
        return "reviewer"
    return "all"


def _expand_tokens(text: str, *, repo_root: Path, worktree_path: Path) -> str:
    return (
        text.replace("${REPO_ROOT}", str(repo_root))
        .replace("${WORKTREE_PATH}", str(worktree_path))
        .replace("${HOME}", str(Path.home()))
    )


def _resolve_source_path(source_raw: str, *, repo_root: Path, worktree_path: Path) -> Path:
    expanded = _expand_tokens(source_raw, repo_root=repo_root, worktree_path=worktree_path)
    source_path = Path(expanded).expanduser()
    if not source_path.is_absolute():
        source_path = repo_root / source_path
    return source_path.resolve()


def _resolve_target_path(target_raw: str, *, worktree_path: Path, repo_root: Path) -> Path:
    expanded = _expand_tokens(target_raw, repo_root=repo_root, worktree_path=worktree_path)
    raw_path = Path(expanded).expanduser()
    worktree_root = Path(os.path.abspath(str(worktree_path)))
    candidate = Path(os.path.abspath(str(raw_path if raw_path.is_absolute() else (worktree_root / raw_path))))
    common = Path(os.path.commonpath([str(candidate), str(worktree_root)]))
    if common != worktree_root:
        raise RuntimeError(f"target path escapes worktree root: {candidate}")
    return candidate


def _remove_path(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
        return
    shutil.rmtree(path)


def _copy_path(source: Path, target: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, target)
    else:
        shutil.copy2(source, target)


def _parse_roles(raw: Any) -> list[str]:
    if raw is None:
        return ["all"]
    if isinstance(raw, str):
        role = normalize_role(raw)
        return [role]
    if isinstance(raw, list):
        out: list[str] = []
        for item in raw:
            role = normalize_role(str(item))
            if role not in out:
                out.append(role)
        return out or ["all"]
    return ["all"]


def load_assets_manifest(manifest_path: Path) -> list[AssetSpec]:
    payload = _json_load(manifest_path)
    assets = payload.get("assets")
    if not isinstance(assets, list):
        raise RuntimeError(f"assets manifest must include array key 'assets': {manifest_path}")

    parsed: list[AssetSpec] = []
    seen_ids: set[str] = set()
    for idx, raw in enumerate(assets, start=1):
        if not isinstance(raw, dict):
            raise RuntimeError(f"asset at index {idx} must be object")
        asset_id = str(raw.get("id") or f"asset-{idx}").strip()
        if not asset_id:
            raise RuntimeError(f"asset id empty at index {idx}")
        if asset_id in seen_ids:
            raise RuntimeError(f"duplicate asset id '{asset_id}' in manifest")
        seen_ids.add(asset_id)

        source_raw = str(raw.get("source") or "").strip()
        target_raw = str(raw.get("target") or "").strip()
        if not source_raw:
            raise RuntimeError(f"asset '{asset_id}' missing 'source'")
        if not target_raw:
            raise RuntimeError(f"asset '{asset_id}' missing 'target'")

        mode = str(raw.get("mode") or "symlink").strip().lower()
        if mode not in {"symlink", "copy"}:
            raise RuntimeError(f"asset '{asset_id}' invalid mode '{mode}' (expected symlink|copy)")

        required = bool(raw.get("required", False))
        roles = _parse_roles(raw.get("roles"))
        parsed.append(
            AssetSpec(
                asset_id=asset_id,
                source_raw=source_raw,
                target_raw=target_raw,
                mode=mode,
                required=required,
                roles=roles,
            )
        )
    return parsed


def role_applies(asset_roles: list[str], slot_role: str) -> bool:
    if "all" in asset_roles:
        return True
    return slot_role in asset_roles


def hydrate_worktree_assets(
    *,
    repo_root: Path,
    worktree_name: str,
    worktree_path: Path,
    slot_role: str,
    manifest_path: Path,
    state_path: Path,
) -> HydrationResult:
    slot_role_normalized = normalize_role(slot_role)
    specs = load_assets_manifest(manifest_path)

    applied_assets: list[dict[str, Any]] = []
    missing_required: list[dict[str, Any]] = []
    missing_optional: list[dict[str, Any]] = []
    warnings: list[str] = []

    for spec in specs:
        if not role_applies(spec.roles, slot_role_normalized):
            applied_assets.append(
                {
                    "id": spec.asset_id,
                    "status": "skipped_role",
                    "mode": spec.mode,
                    "roles": spec.roles,
                }
            )
            continue

        source = _resolve_source_path(spec.source_raw, repo_root=repo_root, worktree_path=worktree_path)
        try:
            target = _resolve_target_path(spec.target_raw, worktree_path=worktree_path, repo_root=repo_root)
        except RuntimeError as exc:
            missing_required.append(
                {
                    "id": spec.asset_id,
                    "reason": str(exc),
                    "source": str(source),
                    "target": spec.target_raw,
                }
            )
            continue

        if not source.exists():
            miss = {
                "id": spec.asset_id,
                "source": str(source),
                "target": str(target),
                "mode": spec.mode,
                "required": spec.required,
                "roles": spec.roles,
            }
            if spec.required:
                missing_required.append(miss)
            else:
                missing_optional.append(miss)
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        previous_status = "created"

        if target.is_symlink():
            try:
                link_target = target.resolve()
            except OSError:
                link_target = None
            if spec.mode == "symlink" and link_target == source.resolve():
                applied_assets.append(
                    {
                        "id": spec.asset_id,
                        "status": "already_ok",
                        "mode": spec.mode,
                        "source": str(source),
                        "target": str(target),
                    }
                )
                continue
            _remove_path(target)
            previous_status = "replaced"
        elif target.exists():
            _remove_path(target)
            previous_status = "replaced"

        if spec.mode == "symlink":
            os.symlink(str(source), str(target))
        else:
            _copy_path(source, target)

        applied_assets.append(
            {
                "id": spec.asset_id,
                "status": previous_status,
                "mode": spec.mode,
                "source": str(source),
                "target": str(target),
            }
        )

    ok = len(missing_required) == 0
    state_payload = _json_load_optional(state_path) or {}
    slots = state_payload.get("slots")
    if not isinstance(slots, dict):
        slots = {}
    slots[worktree_name] = {
        "slot": worktree_name,
        "role": slot_role_normalized,
        "worktree_path": str(worktree_path),
        "manifest_path": str(manifest_path),
        "ready": ok,
        "updated_at": utc_now_iso(),
        "applied_assets": applied_assets,
        "missing_required": missing_required,
        "missing_optional": missing_optional,
        "warnings": warnings,
    }
    state_payload["schema_version"] = "1.0"
    state_payload["updated_at"] = utc_now_iso()
    state_payload["slots"] = slots
    _json_write(state_path, state_payload)

    return HydrationResult(
        ok=ok,
        worktree_name=worktree_name,
        worktree_path=worktree_path,
        role=slot_role_normalized,
        manifest_path=manifest_path,
        state_path=state_path,
        applied_assets=applied_assets,
        missing_required=missing_required,
        missing_optional=missing_optional,
        warnings=warnings,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare workstation worktrees with a hard max-10 gate.")
    parser.add_argument(
        "--repo-root",
        default=".",
        help="path inside the target git repository (default: current directory)",
    )
    parser.add_argument(
        "--worktree-name",
        help="slot name; when omitted, first free standardized slot is selected",
    )
    parser.add_argument(
        "--branch-name",
        help="branch to initialize; defaults to resolved worktree slot name",
    )
    parser.add_argument(
        "--worktrees-parent",
        help=(
            "parent directory for new worktrees "
            "(default: <repo-parent>/<repo-name>-workstations)"
        ),
    )
    parser.add_argument(
        "--slot-role",
        choices=["all", "developer", "tester", "reviewer"],
        default="all",
        help="logical role for hydration filters (default: all)",
    )
    parser.add_argument(
        "--assets-manifest-path",
        help=(
            "asset manifest path (json). "
            "Default: <repo-root>/reports/optimus-prime/config/WORKSTATION_ASSETS.json"
        ),
    )
    parser.add_argument(
        "--assets-state-path",
        help=(
            "asset state output path (json). "
            "Default: <repo-root>/reports/optimus-prime/WORKSTATION_ASSET_STATE.json"
        ),
    )
    parser.add_argument(
        "--skip-assets-hydration",
        action="store_true",
        help="skip post-prepare hydration step",
    )
    parser.add_argument(
        "--require-assets-manifest",
        action="store_true",
        help="fail if manifest path does not exist",
    )
    parser.add_argument(
        "--base-ref",
        help="base ref used to initialize/reset the branch (default: origin/HEAD fallback HEAD)",
    )
    parser.add_argument(
        "--force-reset-existing",
        action="store_true",
        help="allow destructive reset for existing dirty/diverged slots",
    )
    parser.add_argument(
        "--branch-in-use-fallback-suffix",
        help=(
            "suffix to append when requested branch is already checked out in another worktree "
            "(for example '-dev' or '-test')"
        ),
    )
    parser.add_argument(
        "--repair-all-existing",
        action="store_true",
        help="reset all managed workstation slots in one run",
    )
    parser.add_argument(
        "--output",
        choices=["text", "json"],
        default="text",
        help="output mode for orchestrator parsing (default: text)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print actions only",
    )
    return parser.parse_args()


def resolve_assets_paths(repo_root: Path, args: argparse.Namespace) -> tuple[Path, Path]:
    manifest_path = (
        Path(args.assets_manifest_path).expanduser().resolve()
        if args.assets_manifest_path
        else (repo_root / DEFAULT_ASSETS_MANIFEST_REL).resolve()
    )
    state_path = (
        Path(args.assets_state_path).expanduser().resolve()
        if args.assets_state_path
        else (repo_root / DEFAULT_ASSETS_STATE_REL).resolve()
    )
    return manifest_path, state_path


def build_assets_context(
    *,
    context: dict[str, object],
    slot_role: str,
    manifest_path: Path,
    state_path: Path,
    skip_hydration: bool,
    require_manifest: bool,
) -> dict[str, object]:
    return {
        **context,
        "slot_role": slot_role,
        "assets_manifest_path": str(manifest_path),
        "assets_state_path": str(state_path),
        "skip_assets_hydration": skip_hydration,
        "require_assets_manifest": require_manifest,
    }


def run_assets_hydration_or_raise(
    *,
    repo_root: Path,
    worktree_name: str,
    target_path: Path,
    slot_role: str,
    manifest_path: Path,
    state_path: Path,
) -> HydrationResult:
    if not manifest_path.exists():
        raise RuntimeError(f"assets manifest not found: {manifest_path}")
    return hydrate_worktree_assets(
        repo_root=repo_root,
        worktree_name=worktree_name,
        worktree_path=target_path,
        slot_role=slot_role,
        manifest_path=manifest_path,
        state_path=state_path,
    )


def main() -> int:
    args = parse_args()

    try:
        repo_root = git_root(args.repo_root)
        all_worktrees = list_worktrees(repo_root)
    except Exception as exc:  # noqa: BLE001
        return emit(
            {
                "ok": False,
                "error": str(exc),
            },
            args.output,
        )

    managed_slots: dict[str, WorktreeEntry] = {}
    for entry in all_worktrees:
        slot = slot_name_for_path(entry.path)
        if not slot:
            continue
        if slot in managed_slots:
            context = payload_base(
                repo_root=repo_root,
                base_ref=args.base_ref or default_base_ref(repo_root),
                managed_count=len(managed_slots),
                output_mode=args.output,
                dry_run=args.dry_run,
            )
            return fail(f"duplicate managed slot detected for {slot}", args.output, context)
        managed_slots[slot] = entry

    base_ref = args.base_ref or default_base_ref(repo_root)
    assets_manifest_path, assets_state_path = resolve_assets_paths(repo_root, args)
    slot_role = normalize_role(args.slot_role)
    context_common = payload_base(
        repo_root=repo_root,
        base_ref=base_ref,
        managed_count=len(managed_slots),
        output_mode=args.output,
        dry_run=args.dry_run,
    )
    context_common = build_assets_context(
        context=context_common,
        slot_role=slot_role,
        manifest_path=assets_manifest_path,
        state_path=assets_state_path,
        skip_hydration=bool(args.skip_assets_hydration),
        require_manifest=bool(args.require_assets_manifest),
    )

    if args.require_assets_manifest and not args.skip_assets_hydration and not assets_manifest_path.exists():
        return fail(
            f"required assets manifest missing: {assets_manifest_path}",
            args.output,
            context_common,
        )

    if args.repair_all_existing:
        if args.worktree_name:
            return fail("--repair-all-existing cannot be combined with --worktree-name", args.output, context_common)
        if args.branch_name:
            return fail("--repair-all-existing cannot be combined with --branch-name", args.output, context_common)
        if not managed_slots:
            return fail("no managed workstation slots found to repair", args.output, context_common)
        if not args.force_reset_existing and not args.dry_run:
            return fail(
                "--repair-all-existing is destructive; pass --force-reset-existing or use --dry-run",
                args.output,
                context_common,
            )

        repair_results: list[dict[str, object]] = []
        for slot in sorted(managed_slots.keys(), key=slot_sort_key):
            entry = managed_slots[slot]
            requested_branch = entry.branch or slot
            resolved_branch, fallback_used, conflict_paths, resolution_error = resolve_branch_name(
                requested_branch=requested_branch,
                all_worktrees=all_worktrees,
                repo_root=repo_root,
                exclude_path=entry.path,
                fallback_suffix=args.branch_in_use_fallback_suffix,
                allow_existing_branch_ref=True,
            )
            if resolution_error:
                return fail(
                    f"slot '{slot}' branch resolution failed: {resolution_error}",
                    args.output,
                    {
                        **context_common,
                        "worktree_name": slot,
                        "target_path": str(entry.path),
                        "branch_name_requested": requested_branch,
                        "branch_conflict_paths": conflict_paths,
                    },
                )
            if conflict_paths and not fallback_used:
                return fail(
                    f"slot '{slot}' branch '{requested_branch}' is checked out elsewhere; "
                    "set --branch-in-use-fallback-suffix to auto-resolve",
                    args.output,
                    {
                        **context_common,
                        "worktree_name": slot,
                        "target_path": str(entry.path),
                        "branch_name_requested": requested_branch,
                        "branch_conflict_paths": conflict_paths,
                    },
                )

            item_result: dict[str, object] = {
                "worktree_name": slot,
                "target_path": str(entry.path),
                "branch_name_requested": requested_branch,
                "branch_name_resolved": resolved_branch,
                "branch_fallback_applied": fallback_used,
                "branch_conflict_paths": conflict_paths,
                "status": "dry_run" if args.dry_run else "prepared",
            }

            item_role = slot_role if slot_role != "all" else infer_role_from_branch(resolved_branch)
            item_result["slot_role"] = item_role

            if not args.dry_run:
                try:
                    run(["git", "-C", str(entry.path), "checkout", "-B", resolved_branch, base_ref], check=True)
                    run(["git", "-C", str(entry.path), "reset", "--hard", base_ref], check=True)
                    run(["git", "-C", str(entry.path), "clean", "-fd"], check=True)
                except subprocess.CalledProcessError as exc:
                    return fail(
                        exc.stderr.strip() or str(exc),
                        args.output,
                        {**context_common, **item_result},
                    )

                if not args.skip_assets_hydration:
                    if not assets_manifest_path.exists():
                        item_result["assets_hydration"] = {
                            "status": "manifest_missing",
                            "ready": False,
                            "manifest_path": str(assets_manifest_path),
                            "state_path": str(assets_state_path),
                        }
                    else:
                        try:
                            hydration = run_assets_hydration_or_raise(
                                repo_root=repo_root,
                                worktree_name=slot,
                                target_path=entry.path,
                                slot_role=item_role,
                                manifest_path=assets_manifest_path,
                                state_path=assets_state_path,
                            )
                        except Exception as exc:  # noqa: BLE001
                            return fail(
                                f"assets hydration failed for slot '{slot}': {exc}",
                                args.output,
                                {**context_common, **item_result},
                            )
                        item_result["assets_hydration"] = {
                            "status": "applied",
                            "ready": hydration.ok,
                            "manifest_path": str(hydration.manifest_path),
                            "state_path": str(hydration.state_path),
                            "missing_required": hydration.missing_required,
                            "missing_optional": hydration.missing_optional,
                        }
                        if not hydration.ok:
                            return fail(
                                f"assets hydration missing required entries for slot '{slot}'",
                                args.output,
                                {**context_common, **item_result},
                            )
            elif not args.skip_assets_hydration:
                item_result["assets_hydration"] = {
                    "status": "dry_run",
                    "ready": None,
                    "manifest_path": str(assets_manifest_path),
                    "state_path": str(assets_state_path),
                }

            repair_results.append(item_result)

        return emit(
            {
                **context_common,
                "ok": True,
                "action": "repair_all_existing",
                "repair_results": repair_results,
                "message": (
                    "dry-run: would reset all managed slots"
                    if args.dry_run
                    else "all managed slots prepared in clean state"
                ),
            },
            args.output,
        )

    if args.worktree_name:
        if not (LEGACY_SLOT_RE.fullmatch(args.worktree_name) or MANAGER_SLOT_RE.fullmatch(args.worktree_name)):
            return fail(WORKTREE_NAME_ERROR, args.output, context_common)
        worktree_name = args.worktree_name
    else:
        worktree_name = ""
        for index in range(1, MAX_WORKSTATIONS + 1):
            candidate = f"workstation-{index}"
            if candidate not in managed_slots:
                worktree_name = candidate
                break
        if not worktree_name:
            return fail("all workstation slots are occupied; max is 10", args.output, context_common)

    branch_name_requested = args.branch_name or worktree_name
    if not branch_name_requested.strip() or any(ch.isspace() for ch in branch_name_requested):
        return fail("branch name must be non-empty and cannot contain whitespace", args.output, context_common)

    existing_slot = managed_slots.get(worktree_name)
    managed_count = len(managed_slots)
    if existing_slot is None and managed_count >= MAX_WORKSTATIONS:
        return fail("max workstation limit reached (10); refusing to create additional worktrees", args.output, context_common)

    parent_dir = Path(args.worktrees_parent).resolve() if args.worktrees_parent else default_worktrees_parent(repo_root)
    target_path = existing_slot.path if existing_slot else (parent_dir / worktree_name).resolve()

    branch_name_resolved, fallback_used, conflict_paths, resolution_error = resolve_branch_name(
        requested_branch=branch_name_requested,
        all_worktrees=all_worktrees,
        repo_root=repo_root,
        exclude_path=target_path if existing_slot else None,
        fallback_suffix=args.branch_in_use_fallback_suffix,
        allow_existing_branch_ref=args.force_reset_existing,
    )
    if resolution_error:
        return fail(
            resolution_error,
            args.output,
            {
                **context_common,
                "worktree_name": worktree_name,
                "target_path": str(target_path),
                "branch_name_requested": branch_name_requested,
                "branch_conflict_paths": conflict_paths,
            },
        )

    if conflict_paths and not fallback_used:
        return fail(
            f"branch '{branch_name_requested}' is checked out in another worktree; "
            "set --branch-in-use-fallback-suffix to auto-resolve",
            args.output,
            {
                **context_common,
                "worktree_name": worktree_name,
                "target_path": str(target_path),
                "branch_name_requested": branch_name_requested,
                "branch_conflict_paths": conflict_paths,
            },
        )

    effective_slot_role = slot_role if slot_role != "all" else infer_role_from_branch(branch_name_resolved)
    context = {
        **context_common,
        "worktree_name": worktree_name,
        "target_path": str(target_path),
        "branch_name_requested": branch_name_requested,
        "branch_name_resolved": branch_name_resolved,
        "branch_fallback_applied": fallback_used,
        "branch_conflict_paths": conflict_paths,
        "effective_slot_role": effective_slot_role,
    }

    if existing_slot:
        try:
            dirty = working_tree_dirty(target_path)
            head_ahead = revlist_count(target_path, f"{base_ref}...HEAD", right_only=True)
            branch_ahead = 0
            if branch_exists(target_path, branch_name_resolved):
                branch_ahead = revlist_count(target_path, f"{base_ref}...{branch_name_resolved}", right_only=True)
        except Exception as exc:  # noqa: BLE001
            return fail(str(exc), args.output, context)

        needs_force = dirty or head_ahead > 0 or branch_ahead > 0
        if needs_force and not args.force_reset_existing:
            details = []
            if dirty:
                details.append("working tree has local changes")
            if head_ahead > 0:
                details.append(f"HEAD is ahead of {base_ref} by {head_ahead} commit(s)")
            if branch_ahead > 0:
                details.append(
                    f"branch '{branch_name_resolved}' is ahead of {base_ref} by {branch_ahead} commit(s)"
                )
            return fail(
                "existing slot requires reset but --force-reset-existing is not set: " + "; ".join(details),
                args.output,
                context,
            )

        if args.dry_run:
            dry_payload: dict[str, object] = {
                **context,
                "ok": True,
                "action": "reset_existing_slot",
                "message": "dry-run: would reset existing slot",
            }
            if not args.skip_assets_hydration:
                dry_payload["assets_hydration"] = {
                    "status": "dry_run",
                    "ready": None,
                    "manifest_path": str(assets_manifest_path),
                    "state_path": str(assets_state_path),
                }
            return emit(
                dry_payload,
                args.output,
            )

        try:
            run(["git", "-C", str(target_path), "checkout", "-B", branch_name_resolved, base_ref], check=True)
            run(["git", "-C", str(target_path), "reset", "--hard", base_ref], check=True)
            run(["git", "-C", str(target_path), "clean", "-fd"], check=True)
        except subprocess.CalledProcessError as exc:
            return fail(exc.stderr.strip() or str(exc), args.output, context)

        assets_payload: dict[str, object] | None = None
        if not args.skip_assets_hydration:
            if not assets_manifest_path.exists():
                assets_payload = {
                    "status": "manifest_missing",
                    "ready": False,
                    "manifest_path": str(assets_manifest_path),
                    "state_path": str(assets_state_path),
                }
            else:
                try:
                    hydration = run_assets_hydration_or_raise(
                        repo_root=repo_root,
                        worktree_name=worktree_name,
                        target_path=target_path,
                        slot_role=effective_slot_role,
                        manifest_path=assets_manifest_path,
                        state_path=assets_state_path,
                    )
                except Exception as exc:  # noqa: BLE001
                    return fail(f"assets hydration failed: {exc}", args.output, context)
                assets_payload = {
                    "status": "applied",
                    "ready": hydration.ok,
                    "manifest_path": str(hydration.manifest_path),
                    "state_path": str(hydration.state_path),
                    "missing_required": hydration.missing_required,
                    "missing_optional": hydration.missing_optional,
                }
                if not hydration.ok:
                    return fail(
                        "assets hydration missing required entries",
                        args.output,
                        {**context, "assets_hydration": assets_payload},
                    )

        return emit(
            {
                **context,
                "ok": True,
                "action": "reset_existing_slot",
                "message": "existing slot prepared in clean state",
                **({"assets_hydration": assets_payload} if assets_payload is not None else {}),
            },
            args.output,
        )

    if target_path.exists():
        return fail(f"target path already exists and is not a managed slot: {target_path}", args.output, context)

    if not parent_dir.exists():
        if args.dry_run:
            pass
        else:
            try:
                parent_dir.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                return fail(f"unable to create worktrees parent directory {parent_dir}: {exc}", args.output, context)
    elif not parent_dir.is_dir():
        return fail(f"worktrees parent path is not a directory: {parent_dir}", args.output, context)

    branch_already_exists = branch_exists(repo_root, branch_name_resolved)
    if branch_already_exists:
        try:
            branch_ahead, branch_behind = branch_divergence(repo_root, base_ref, branch_name_resolved)
        except Exception as exc:  # noqa: BLE001
            return fail(str(exc), args.output, context)
        if not args.force_reset_existing:
            divergence_note = (
                f" (ahead {branch_ahead}, behind {branch_behind} vs {base_ref})"
                if branch_ahead > 0 or branch_behind > 0
                else ""
            )
            return fail(
                f"branch '{branch_name_resolved}' already exists{divergence_note}; "
                "refusing to reset existing branch without --force-reset-existing",
                args.output,
                context,
            )

    if args.dry_run:
        message = (
            "dry-run: would create new slot and force-reset existing branch ref"
            if branch_already_exists
            else "dry-run: would create new slot"
        )
        dry_payload: dict[str, object] = {
            **context,
            "ok": True,
            "action": "create_new_slot",
            "message": message,
        }
        if not args.skip_assets_hydration:
            dry_payload["assets_hydration"] = {
                "status": "dry_run",
                "ready": None,
                "manifest_path": str(assets_manifest_path),
                "state_path": str(assets_state_path),
            }
        return emit(
            dry_payload,
            args.output,
        )

    add_args = [
        "git",
        "-C",
        str(repo_root),
        "worktree",
        "add",
        str(target_path),
    ]
    if branch_already_exists:
        add_args.extend(["-B", branch_name_resolved, base_ref])
    else:
        add_args.extend(["-b", branch_name_resolved, base_ref])

    try:
        run(add_args, check=True)
    except subprocess.CalledProcessError as exc:
        return fail(exc.stderr.strip() or str(exc), args.output, context)

    assets_payload: dict[str, object] | None = None
    if not args.skip_assets_hydration:
        if not assets_manifest_path.exists():
            assets_payload = {
                "status": "manifest_missing",
                "ready": False,
                "manifest_path": str(assets_manifest_path),
                "state_path": str(assets_state_path),
            }
        else:
            try:
                hydration = run_assets_hydration_or_raise(
                    repo_root=repo_root,
                    worktree_name=worktree_name,
                    target_path=target_path,
                    slot_role=effective_slot_role,
                    manifest_path=assets_manifest_path,
                    state_path=assets_state_path,
                )
            except Exception as exc:  # noqa: BLE001
                return fail(f"assets hydration failed: {exc}", args.output, context)
            assets_payload = {
                "status": "applied",
                "ready": hydration.ok,
                "manifest_path": str(hydration.manifest_path),
                "state_path": str(hydration.state_path),
                "missing_required": hydration.missing_required,
                "missing_optional": hydration.missing_optional,
            }
            if not hydration.ok:
                return fail(
                    "assets hydration missing required entries",
                    args.output,
                    {**context, "assets_hydration": assets_payload},
                )

    return emit(
        {
            **context,
            "ok": True,
            "action": "create_new_slot",
            "message": "new slot created",
            **({"assets_hydration": assets_payload} if assets_payload is not None else {}),
        },
        args.output,
    )


if __name__ == "__main__":
    raise SystemExit(main())
