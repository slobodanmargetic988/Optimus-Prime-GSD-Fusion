#!/usr/bin/env python3
"""Shared helpers for Lane C install/update/uninstall/doctor commands."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
DEFAULT_VERSION = "0.0.0"
INSTALL_STATE_GLOBAL_REL = Path(".optimus-prime") / "install" / "INSTALL_STATE.json"
INSTALL_STATE_LOCAL_REL = Path(".optimus-prime") / "install" / "INSTALL_STATE.json"
GLOBAL_INSTALL_ROOT_REL = Path(".optimus-prime") / "install" / "current"
GLOBAL_BACKUP_ROOT_REL = Path(".optimus-prime") / "install" / "backups"
GLOBAL_BIN_REL = Path(".local") / "bin"


class InstallError(Exception):
    def __init__(self, code: str, message: str, stage: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.stage = stage


@dataclass
class InstallContext:
    mode: str
    repo_root: Path | None
    home: Path
    codex_home: Path
    config_dir: Path
    state_path: Path
    install_root: Path
    backup_root: Path
    bin_dir: Path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def atomic_write_json(path: Path, payload: Any) -> None:
    _ensure_parent(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise InstallError("state_read_error", f"invalid JSON in {path}: {exc}", stage="state_read") from exc
    except OSError as exc:
        raise InstallError("state_read_error", f"unable to read {path}: {exc}", stage="state_read") from exc


def as_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        out = value.strip()
        return out or None
    out = str(value).strip()
    return out or None


def as_bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "y", "on"}:
            return True
        if text in {"0", "false", "no", "n", "off"}:
            return False
    return default


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def _home_path(payload: dict[str, Any]) -> Path:
    override = as_str(payload.get("home_override"))
    if override:
        return Path(override).expanduser().resolve()
    return Path.home().resolve()


def _config_dir(home: Path) -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg).expanduser().resolve() / "optimus-prime"
    return home / ".optimus-prime" / "config"


def _global_state_path(home: Path) -> Path:
    return home / INSTALL_STATE_GLOBAL_REL


def _global_install_root(home: Path) -> Path:
    return home / GLOBAL_INSTALL_ROOT_REL


def _global_backup_root(home: Path) -> Path:
    return home / GLOBAL_BACKUP_ROOT_REL


def _global_bin_dir(home: Path) -> Path:
    return home / GLOBAL_BIN_REL


def _local_repo(payload: dict[str, Any]) -> Path:
    repo_root = as_str(payload.get("repo_root"))
    if not repo_root:
        raise InstallError("input_error", "repo_root is required for local mode", stage="input")
    return Path(repo_root).expanduser().resolve()


def resolve_context(payload: dict[str, Any]) -> InstallContext:
    mode = (as_str(payload.get("mode")) or "global").lower()
    if mode not in {"global", "local"}:
        raise InstallError("input_error", "mode must be global or local", stage="input")
    home = _home_path(payload)
    codex_home_raw = as_str(payload.get("codex_home")) or os.environ.get("CODEX_HOME")
    codex_home = Path(codex_home_raw).expanduser().resolve() if codex_home_raw else (home / ".codex")
    if mode == "global":
        config_dir = _config_dir(home)
        state_path = _global_state_path(home)
        install_root = _global_install_root(home)
        backup_root = _global_backup_root(home)
        bin_dir = Path(as_str(payload.get("bin_dir")) or str(_global_bin_dir(home))).expanduser().resolve()
        return InstallContext(
            mode=mode,
            repo_root=None,
            home=home,
            codex_home=codex_home,
            config_dir=config_dir,
            state_path=state_path,
            install_root=install_root,
            backup_root=backup_root,
            bin_dir=bin_dir,
        )

    repo_root = _local_repo(payload)
    local_root = repo_root / ".optimus-prime"
    config_dir = local_root / "config"
    state_path = repo_root / INSTALL_STATE_LOCAL_REL
    install_root = local_root / "install" / "current"
    backup_root = local_root / "install" / "backups"
    bin_dir = Path(as_str(payload.get("bin_dir")) or str(local_root / "bin")).expanduser().resolve()
    return InstallContext(
        mode=mode,
        repo_root=repo_root,
        home=home,
        codex_home=codex_home,
        config_dir=config_dir,
        state_path=state_path,
        install_root=install_root,
        backup_root=backup_root,
        bin_dir=bin_dir,
    )


def ensure_launcher(path: Path, target: Path) -> None:
    _ensure_parent(path)
    script = (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f"exec python3 \"{target}\" \"$@\"\n"
    )
    path.write_text(script, encoding="utf-8")
    path.chmod(0o755)


def load_install_state(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        raise InstallError("state_missing", f"install state not found: {state_path}", stage="state_read")
    payload = read_json(state_path)
    if not isinstance(payload, dict):
        raise InstallError("state_read_error", f"install state must be object: {state_path}", stage="state_read")
    return payload


def normalize_managed_paths(payload: dict[str, Any]) -> list[str]:
    raw = payload.get("managed_paths")
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        text = as_str(item)
        if text:
            out.append(text)
    return sorted(set(out))


def build_state_payload(
    *,
    ctx: InstallContext,
    installed_version: str,
    managed_paths: list[str],
    recovery: dict[str, Any] | None = None,
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = utc_now_iso()
    install_id = as_str((previous or {}).get("install_id")) or f"install-{uuid.uuid4().hex[:10]}"
    return {
        "schema_version": SCHEMA_VERSION,
        "install_id": install_id,
        "install_mode": ctx.mode,
        "installed_version": installed_version,
        "installed_at": as_str((previous or {}).get("installed_at")) or now,
        "managed_paths": sorted(set(managed_paths)),
        "codex_home": str(ctx.codex_home),
        "last_update_at": now,
        "last_doctor_at": as_str((previous or {}).get("last_doctor_at")),
        "recovery": recovery or {
            "last_backup_path": None,
            "last_recovery_reason": None,
        },
    }


def load_bundle(bundle_dir: Path) -> tuple[dict[str, Any], dict[str, str]]:
    if not bundle_dir.exists():
        raise InstallError("input_error", f"bundle directory not found: {bundle_dir}", stage="input")
    manifest_path = bundle_dir / "bundle_manifest.json"
    checksum_path = bundle_dir / "SHA256SUMS.json"
    payload = read_json(manifest_path)
    if not isinstance(payload, dict):
        raise InstallError("validation_error", "bundle_manifest.json must be object", stage="validate")
    checksums = read_json(checksum_path)
    if not isinstance(checksums, dict):
        raise InstallError("validation_error", "SHA256SUMS.json must be object", stage="validate")
    checksum_map: dict[str, str] = {}
    for key, value in checksums.items():
        path_key = as_str(key)
        digest = as_str(value)
        if path_key and digest:
            checksum_map[path_key] = digest
    return payload, checksum_map


def verify_bundle_integrity(bundle_dir: Path, manifest: dict[str, Any], checksums: dict[str, str]) -> None:
    required_fields = [
        "schema_version",
        "product_version",
        "build_timestamp",
        "git_commit",
        "platforms",
        "managed_files",
        "skills_manifest",
        "templates_manifest",
        "checksums",
    ]
    missing = [field for field in required_fields if field not in manifest]
    if missing:
        raise InstallError("validation_error", f"bundle_manifest missing fields: {', '.join(missing)}", stage="validate")
    managed_files = manifest.get("managed_files")
    if not isinstance(managed_files, list) or not managed_files:
        raise InstallError("validation_error", "bundle_manifest managed_files must be non-empty list", stage="validate")
    for rel in managed_files:
        rel_path = as_str(rel)
        if not rel_path:
            raise InstallError("validation_error", "managed_files entries must be non-empty strings", stage="validate")
        payload_file = bundle_dir / "payload" / rel_path
        if not payload_file.exists():
            raise InstallError("validation_error", f"managed file missing from payload: {rel_path}", stage="validate")
        expected = checksums.get(f"payload/{rel_path}") or checksums.get(rel_path)
        if not expected:
            raise InstallError("validation_error", f"checksum missing for payload/{rel_path}", stage="validate")
        actual = sha256_file(payload_file)
        if actual != expected:
            raise InstallError("checksum_mismatch", f"checksum mismatch for payload/{rel_path}", stage="validate")


def copy_tree_replace(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def copy_file_replace(src: Path, dst: Path) -> None:
    _ensure_parent(dst)
    shutil.copy2(src, dst)


def copy_codex_assets(bundle_dir: Path, codex_home: Path) -> list[str]:
    managed: list[str] = []
    skills_src = bundle_dir / "payload" / "skills"
    agents_src = bundle_dir / "payload" / "agents" / "optimus-prime"
    if skills_src.exists():
        target_skills = codex_home / "skills"
        target_skills.mkdir(parents=True, exist_ok=True)
        for child in sorted(skills_src.iterdir()):
            if not child.is_dir():
                continue
            dst = target_skills / child.name
            copy_tree_replace(child, dst)
            managed.append(str(dst))
    if agents_src.exists():
        target_agents = codex_home / "agents" / "optimus-prime"
        target_agents.parent.mkdir(parents=True, exist_ok=True)
        copy_tree_replace(agents_src, target_agents)
        managed.append(str(target_agents))
    return sorted(set(managed))


def parse_git_commit(repo_root: Path) -> str:
    run = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repo_root),
        text=True,
        capture_output=True,
        check=False,
    )
    if run.returncode != 0:
        return "unknown"
    return run.stdout.strip() or "unknown"


def standard_response(
    *,
    ok: bool,
    status: str,
    summary: str,
    data: dict[str, Any] | None = None,
    warnings: list[dict[str, Any]] | None = None,
    errors: list[dict[str, Any]] | None = None,
    next_action: str | None = None,
) -> dict[str, Any]:
    out = {
        "schema_version": SCHEMA_VERSION,
        "ok": bool(ok),
        "status": status,
        "summary": summary,
        "warnings": warnings or [],
        "errors": errors or [],
        "next_action": next_action,
    }
    if data:
        out["data"] = data
    return out

