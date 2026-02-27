#!/usr/bin/env python3
"""Private GitHub release resolver/downloader for Lane C install/update."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tarfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from scripts.install.common import InstallError, as_str, sha256_file


def resolve_auth_token(payload: dict[str, Any]) -> str:
    explicit = as_str(payload.get("github_token"))
    if explicit:
        return explicit

    if shutil.which("gh"):
        run = subprocess.run(
            ["gh", "auth", "token"],
            text=True,
            capture_output=True,
            check=False,
        )
        if run.returncode == 0:
            token = as_str(run.stdout)
            if token:
                return token

    env_gh = as_str(os.environ.get("GH_TOKEN"))
    if env_gh:
        return env_gh
    env_github = as_str(os.environ.get("GITHUB_TOKEN"))
    if env_github:
        return env_github
    raise InstallError(
        "auth_error",
        "missing GitHub auth token; authenticate with `gh auth login` or set GH_TOKEN/GITHUB_TOKEN",
        stage="auth",
    )


def _github_api_json(url: str, token: str) -> Any:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "optimus-prime-lane-c",
        },
    )
    try:
        with urllib.request.urlopen(req) as response:  # noqa: S310
            raw = response.read().decode("utf-8")
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403}:
            raise InstallError("auth_error", f"github API auth failed ({exc.code})", stage="download") from exc
        raise InstallError(
            "download_error",
            f"github API request failed ({exc.code}) for {url}",
            stage="download",
        ) from exc
    except urllib.error.URLError as exc:
        raise InstallError("download_error", f"github API network error: {exc}", stage="download") from exc
    except json.JSONDecodeError as exc:
        raise InstallError("download_error", "github API returned invalid JSON", stage="download") from exc


def _download_asset(asset_url: str, token: str, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(
        asset_url,
        headers={
            "Accept": "application/octet-stream",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "optimus-prime-lane-c",
        },
    )
    try:
        with urllib.request.urlopen(req) as response, out_path.open("wb") as fh:  # noqa: S310
            fh.write(response.read())
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403}:
            raise InstallError("auth_error", f"asset download auth failed ({exc.code})", stage="download") from exc
        raise InstallError(
            "download_error",
            f"asset download failed ({exc.code}) for {asset_url}",
            stage="download",
        ) from exc
    except urllib.error.URLError as exc:
        raise InstallError("download_error", f"asset download network error: {exc}", stage="download") from exc
    except OSError as exc:
        raise InstallError("download_error", f"failed to write downloaded asset: {exc}", stage="download") from exc


def _normalize_version_targets(version: str | None) -> set[str]:
    if not version:
        return set()
    clean = version.strip()
    if not clean:
        return set()
    if clean.startswith("v"):
        return {clean, clean[1:]}
    return {clean, f"v{clean}"}


def _release_matches_channel(item: dict[str, Any], channel: str) -> bool:
    if bool(item.get("draft")):
        return False
    is_pre = bool(item.get("prerelease"))
    if channel == "prerelease":
        return is_pre
    if channel == "stable":
        return not is_pre
    return False


def _resolve_release(
    releases: list[dict[str, Any]],
    *,
    channel: str,
    version: str | None,
) -> dict[str, Any]:
    version_targets = _normalize_version_targets(version)
    candidates = [item for item in releases if _release_matches_channel(item, channel)]
    if version_targets:
        for item in candidates:
            tag = as_str(item.get("tag_name")) or ""
            if tag in version_targets:
                return item
        raise InstallError(
            "release_not_found",
            f"no {channel} release found for version {version}",
            stage="resolve_release",
        )
    if not candidates:
        raise InstallError("release_not_found", f"no {channel} releases found", stage="resolve_release")
    return candidates[0]


def _safe_extract_tar(tar_path: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, "r:gz") as tar:
        for member in tar.getmembers():
            target = (out_dir / member.name).resolve()
            if not str(target).startswith(str(out_dir.resolve())):
                raise InstallError("download_error", "tar extraction blocked due to unsafe path", stage="extract")
        tar.extractall(out_dir)  # noqa: S202


def _find_bundle_dir(extract_root: Path) -> Path:
    for path in sorted(extract_root.rglob("bundle_manifest.json")):
        parent = path.parent
        if (parent / "SHA256SUMS.json").exists() and (parent / "payload").is_dir():
            return parent
    raise InstallError("asset_missing", "downloaded bundle archive missing expected bundle structure", stage="extract")


def _required_assets(release_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    assets = release_payload.get("assets")
    if not isinstance(assets, list):
        raise InstallError("asset_missing", "release assets list missing", stage="resolve_release")
    required: dict[str, dict[str, Any]] = {}
    for item in assets:
        if not isinstance(item, dict):
            continue
        name = as_str(item.get("name"))
        if not name:
            continue
        if name.endswith(".tar.gz"):
            required["bundle"] = item
        elif name == "bundle_manifest.json":
            required["manifest"] = item
        elif name == "SHA256SUMS.json":
            required["checksums"] = item
    if "bundle" not in required:
        raise InstallError("asset_missing", "missing release bundle tar.gz asset", stage="resolve_release")
    if "manifest" not in required:
        raise InstallError("asset_missing", "missing release bundle_manifest.json asset", stage="resolve_release")
    if "checksums" not in required:
        raise InstallError("asset_missing", "missing release SHA256SUMS.json asset", stage="resolve_release")
    return required


def _asset_url(item: dict[str, Any]) -> str:
    for key in ("browser_download_url", "url"):
        value = as_str(item.get(key))
        if value:
            return value
    raise InstallError("asset_missing", "release asset URL missing", stage="resolve_release")


def fetch_release_bundle(payload: dict[str, Any], temp_root: Path) -> dict[str, str]:
    owner = as_str(payload.get("repo_owner"))
    repo = as_str(payload.get("repo_name"))
    if not owner or not repo:
        raise InstallError("input_error", "repo_owner and repo_name are required for github release source", stage="input")
    channel = (as_str(payload.get("channel")) or "prerelease").lower()
    if channel not in {"prerelease", "stable"}:
        raise InstallError("input_error", "channel must be prerelease or stable", stage="input")
    version = as_str(payload.get("version"))

    token = resolve_auth_token(payload)
    releases_url = f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=100"
    releases = _github_api_json(releases_url, token)
    if not isinstance(releases, list):
        raise InstallError("download_error", "invalid github releases response shape", stage="download")
    release = _resolve_release(releases, channel=channel, version=version)
    assets = _required_assets(release)

    download_root = temp_root / "download"
    bundle_tar = download_root / str(as_str(assets["bundle"].get("name")) or "bundle.tar.gz")
    manifest_asset = download_root / "bundle_manifest.json"
    checksums_asset = download_root / "SHA256SUMS.json"
    _download_asset(_asset_url(assets["bundle"]), token, bundle_tar)
    _download_asset(_asset_url(assets["manifest"]), token, manifest_asset)
    _download_asset(_asset_url(assets["checksums"]), token, checksums_asset)

    extract_root = temp_root / "extract"
    _safe_extract_tar(bundle_tar, extract_root)
    bundle_dir = _find_bundle_dir(extract_root)

    # Ensure sidecar assets in release match extracted bundle metadata.
    extracted_manifest = bundle_dir / "bundle_manifest.json"
    extracted_checksums = bundle_dir / "SHA256SUMS.json"
    if sha256_file(extracted_manifest) != sha256_file(manifest_asset):
        raise InstallError("checksum_mismatch", "release manifest asset does not match bundle manifest", stage="validate")
    if sha256_file(extracted_checksums) != sha256_file(checksums_asset):
        raise InstallError("checksum_mismatch", "release checksum asset does not match bundle checksum file", stage="validate")

    tag_name = as_str(release.get("tag_name")) or "unknown-tag"
    return {
        "bundle_dir": str(bundle_dir),
        "source": "github_release",
        "source_ref": f"{owner}/{repo}@{tag_name}",
    }
