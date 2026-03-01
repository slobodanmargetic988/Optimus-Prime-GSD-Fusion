#!/usr/bin/env python3
"""Build deterministic Lane C release bundle for GitHub-first distribution."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SCRIPTS_ROOT.parent
for candidate in (REPO_ROOT, SCRIPTS_ROOT, SCRIPT_DIR):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from scripts.install.common import SCHEMA_VERSION, parse_git_commit, sha256_file, utc_now_iso

PLATFORMS = ["darwin", "linux"]
PAYLOAD_PATHS = [
    "scripts/op",
    "scripts/install",
    "scripts/test-train",
    "scripts/runtime-heal.sh",
    "scripts/runtime/start.sh",
    "scripts/runtime/health.sh",
    "scripts/runtime/stop.sh",
    "scripts/deploy-test.sh",
    "scripts/db-impact-detector.sh",
    "scripts/db-reset-migrate-seed.sh",
    "skills/codex-rate-snapshot",
    "skills/dispatch-worker-packet",
    "skills/optimus-cycle-controller",
    "skills/runtime-coordinator",
    "skills/test-train-manager",
    "skills/thread-dispatch",
    "skills/workstation-preparation",
    "agents/optimus-prime",
    "README.md",
    "VERSION",
]

# Runtime skills that /op-* execution depends on.
REQUIRED_RUNTIME_SKILL_DIRS = [
    "skills/codex-rate-snapshot",
    "skills/dispatch-worker-packet",
    "skills/optimus-cycle-controller",
    "skills/runtime-coordinator",
    "skills/test-train-manager",
    "skills/thread-dispatch",
    "skills/workstation-preparation",
]


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _atomic_write_json(path: Path, payload: Any) -> None:
    _ensure_parent(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def _copy_file(src: Path, dst: Path) -> None:
    _ensure_parent(dst)
    dst.write_bytes(src.read_bytes())


def _collect_payload_files(repo_root: Path) -> list[str]:
    run = subprocess.run(
        ["git", "ls-files", "-z", "--", *PAYLOAD_PATHS],
        cwd=str(repo_root),
        text=False,
        capture_output=True,
        check=False,
    )
    if run.returncode == 0:
        tracked = [item.decode("utf-8") for item in run.stdout.split(b"\x00") if item]
        out = [item for item in tracked if (repo_root / item).is_file()]
        return sorted(set(out))

    out: list[str] = []
    for rel in PAYLOAD_PATHS:
        path = (repo_root / rel).resolve()
        if not path.exists():
            continue
        if path.is_file():
            if path.suffix in {".pyc", ".pyo"}:
                continue
            out.append(rel)
            continue
        for child in sorted(path.rglob("*")):
            if not child.is_file():
                continue
            rel_child = child.relative_to(repo_root)
            if "__pycache__" in rel_child.parts:
                continue
            if child.suffix in {".pyc", ".pyo"}:
                continue
            out.append(str(child.relative_to(repo_root)))
    return sorted(set(out))


def _validate_required_runtime_skills(repo_root: Path, managed_files: list[str]) -> None:
    missing_paths = [rel for rel in REQUIRED_RUNTIME_SKILL_DIRS if not (repo_root / rel).is_dir()]
    if missing_paths:
        raise RuntimeError(f"missing required runtime skill directories: {', '.join(missing_paths)}")
    managed_skill_names = _skills_manifest(managed_files)
    required_skill_names = sorted(Path(rel).name for rel in REQUIRED_RUNTIME_SKILL_DIRS)
    missing_skills = [name for name in required_skill_names if name not in managed_skill_names]
    if missing_skills:
        raise RuntimeError(
            "bundle missing required runtime skills: " + ", ".join(missing_skills)
        )


def _copy_payload(repo_root: Path, bundle_dir: Path, managed_files: list[str]) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for rel in managed_files:
        src = repo_root / rel
        dst = bundle_dir / "payload" / rel
        _copy_file(src, dst)
        checksums[f"payload/{rel}"] = sha256_file(dst)
    return checksums


def _skills_manifest(managed_files: list[str]) -> list[str]:
    names = {
        Path(rel).parts[1]
        for rel in managed_files
        if rel.startswith("skills/") and len(Path(rel).parts) >= 2
    }
    return sorted(names)


def _templates_manifest(managed_files: list[str]) -> list[str]:
    templates: set[str] = set()
    for rel in managed_files:
        if rel.startswith("agents/optimus-prime/"):
            templates.add(rel)
    return sorted(templates)


def _write_checksum_files(bundle_dir: Path, checksums: dict[str, str]) -> None:
    _atomic_write_json(bundle_dir / "SHA256SUMS.json", checksums)
    lines = [f"{checksums[key]}  {key}" for key in sorted(checksums.keys())]
    (bundle_dir / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _deterministic_tar_gz(bundle_dir: Path, out_path: Path) -> None:
    _ensure_parent(out_path)
    with tarfile.open(out_path, "w:gz", compresslevel=9) as tar:
        for child in sorted(bundle_dir.rglob("*")):
            arcname = str(child.relative_to(bundle_dir.parent))
            info = tar.gettarinfo(str(child), arcname=arcname)
            info.uid = 0
            info.gid = 0
            info.uname = "root"
            info.gname = "root"
            info.mtime = 0
            if child.is_file():
                with child.open("rb") as fh:
                    tar.addfile(info, fh)
            else:
                tar.addfile(info)


def build_bundle(repo_root: Path, out_dir: Path, version: str) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    out_dir = out_dir.resolve()
    bundle_name = f"optimus-prime-{version}"
    bundle_dir = out_dir / bundle_name
    if bundle_dir.exists():
        for child in sorted(bundle_dir.rglob("*"), reverse=True):
            if child.is_file():
                child.unlink()
        for child in sorted(bundle_dir.rglob("*"), reverse=True):
            if child.is_dir():
                child.rmdir()
        if bundle_dir.exists():
            bundle_dir.rmdir()
    bundle_dir.mkdir(parents=True, exist_ok=True)

    managed_files = _collect_payload_files(repo_root)
    _validate_required_runtime_skills(repo_root, managed_files)
    checksums = _copy_payload(repo_root, bundle_dir, managed_files)
    _write_checksum_files(bundle_dir, checksums)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "product_version": version,
        "build_timestamp": utc_now_iso(),
        "git_commit": parse_git_commit(repo_root),
        "platforms": PLATFORMS,
        "managed_files": managed_files,
        "skills_manifest": _skills_manifest(managed_files),
        "templates_manifest": _templates_manifest(managed_files),
        "checksums": checksums,
    }
    _atomic_write_json(bundle_dir / "bundle_manifest.json", manifest)
    tar_path = out_dir / f"{bundle_name}.tar.gz"
    _deterministic_tar_gz(bundle_dir, tar_path)
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "status": "completed",
        "summary": "Lane C release bundle created.",
        "bundle_dir": str(bundle_dir),
        "bundle_tar_gz": str(tar_path),
        "manifest_path": str(bundle_dir / "bundle_manifest.json"),
        "checksum_json_path": str(bundle_dir / "SHA256SUMS.json"),
        "checksum_txt_path": str(bundle_dir / "SHA256SUMS"),
        "version": version,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build deterministic Lane C release bundle.")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--version", default=None)
    parser.add_argument("--json-pretty", action="store_true")
    return parser.parse_args()


def _resolve_version(repo_root: Path, override: str | None) -> str:
    if override and override.strip():
        return override.strip()
    version_path = repo_root / "VERSION"
    if not version_path.exists():
        return "0.0.0"
    return version_path.read_text(encoding="utf-8").strip() or "0.0.0"


def _print(payload: dict[str, Any], pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=False))
    else:
        print(json.dumps(payload, separators=(",", ":"), sort_keys=False))


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    try:
        version = _resolve_version(repo_root, args.version)
        result = build_bundle(repo_root, out_dir, version)
        _print(result, args.json_pretty)
        return 0
    except Exception as exc:  # noqa: BLE001
        out = {
            "schema_version": SCHEMA_VERSION,
            "ok": False,
            "status": "failed",
            "summary": "Failed to build Lane C release bundle.",
            "errors": [
                {
                    "code": "bundle_build_failed",
                    "message": str(exc),
                    "stage": "build_bundle",
                }
            ],
        }
        _print(out, args.json_pretty)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
