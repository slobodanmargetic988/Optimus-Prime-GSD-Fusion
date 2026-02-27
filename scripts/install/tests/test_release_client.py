import importlib.util
import sys
import tempfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


COMMON = _load(ROOT / "scripts" / "install" / "common.py", "lane_c_common_for_release_client")
RELEASE = _load(ROOT / "scripts" / "install" / "release_client.py", "lane_c_release_client")
BUILDER = _load(ROOT / "scripts" / "release" / "build_lane_c_bundle.py", "lane_c_builder_for_release_client")


def test_auth_resolution_prefers_gh_token(monkeypatch: pytest.MonkeyPatch):
    class Result:
        returncode = 0
        stdout = "gh-token-abc\n"

    monkeypatch.setattr(RELEASE.shutil, "which", lambda _: "/usr/bin/gh")
    monkeypatch.setattr(RELEASE.subprocess, "run", lambda *args, **kwargs: Result())
    monkeypatch.setenv("GH_TOKEN", "env-gh-token")
    token = RELEASE.resolve_auth_token({})
    assert token == "gh-token-abc"


def test_auth_resolution_falls_back_to_environment(monkeypatch: pytest.MonkeyPatch):
    class Result:
        returncode = 1
        stdout = ""

    monkeypatch.setattr(RELEASE.shutil, "which", lambda _: "/usr/bin/gh")
    monkeypatch.setattr(RELEASE.subprocess, "run", lambda *args, **kwargs: Result())
    monkeypatch.setenv("GH_TOKEN", "env-gh-token")
    token = RELEASE.resolve_auth_token({})
    assert token == "env-gh-token"


def test_auth_resolution_errors_without_any_token(monkeypatch: pytest.MonkeyPatch):
    class Result:
        returncode = 1
        stdout = ""

    monkeypatch.setattr(RELEASE.shutil, "which", lambda _: "/usr/bin/gh")
    monkeypatch.setattr(RELEASE.subprocess, "run", lambda *args, **kwargs: Result())
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(Exception) as exc:
        RELEASE.resolve_auth_token({})
    assert getattr(exc.value, "code", None) == "auth_error"


def test_fetch_release_bundle_resolves_version_and_extracts(monkeypatch: pytest.MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp:
        bundle_result = BUILDER.build_bundle(ROOT, Path(tmp), "8.0.0-rc.1")
        bundle_dir = Path(bundle_result["bundle_dir"])
        tar_path = Path(bundle_result["bundle_tar_gz"])
        manifest_path = bundle_dir / "bundle_manifest.json"
        checksums_path = bundle_dir / "SHA256SUMS.json"

        release_payload = [
            {
                "tag_name": "v8.0.0-rc.1",
                "draft": False,
                "prerelease": True,
                "assets": [
                    {"name": tar_path.name, "browser_download_url": "mock://bundle"},
                    {"name": "bundle_manifest.json", "browser_download_url": "mock://manifest"},
                    {"name": "SHA256SUMS.json", "browser_download_url": "mock://checksums"},
                ],
            }
        ]

        def fake_api(url: str, token: str):
            return release_payload

        def fake_download(url: str, token: str, out: Path):
            source_map = {
                "mock://bundle": tar_path,
                "mock://manifest": manifest_path,
                "mock://checksums": checksums_path,
            }
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(source_map[url].read_bytes())

        monkeypatch.setattr(RELEASE, "resolve_auth_token", lambda payload: "tok")
        monkeypatch.setattr(RELEASE, "_github_api_json", fake_api)
        monkeypatch.setattr(RELEASE, "_download_asset", fake_download)

        work = Path(tmp) / "work"
        out = RELEASE.fetch_release_bundle(
            {
                "repo_owner": "owner",
                "repo_name": "repo",
                "channel": "prerelease",
                "version": "8.0.0-rc.1",
            },
            work,
        )
        resolved_bundle = Path(out["bundle_dir"])
        assert resolved_bundle.exists()
        assert (resolved_bundle / "bundle_manifest.json").exists()
        assert out["source"] == "github_release"
        assert out["source_ref"] == "owner/repo@v8.0.0-rc.1"


def test_fetch_release_bundle_errors_when_required_asset_missing(monkeypatch: pytest.MonkeyPatch):
    release_payload = [
        {
            "tag_name": "v1.0.0-rc.1",
            "draft": False,
            "prerelease": True,
            "assets": [
                {"name": "bundle_manifest.json", "browser_download_url": "mock://manifest"},
                {"name": "SHA256SUMS.json", "browser_download_url": "mock://checksums"},
            ],
        }
    ]
    monkeypatch.setattr(RELEASE, "resolve_auth_token", lambda payload: "tok")
    monkeypatch.setattr(RELEASE, "_github_api_json", lambda url, token: release_payload)
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(Exception) as exc:
            RELEASE.fetch_release_bundle(
                {"repo_owner": "owner", "repo_name": "repo", "channel": "prerelease"},
                Path(tmp),
            )
        assert getattr(exc.value, "code", None) == "asset_missing"
