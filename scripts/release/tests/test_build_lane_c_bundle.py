import importlib.util
import json
import sys
import tempfile
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "build_lane_c_bundle.py"
SPEC = importlib.util.spec_from_file_location("build_lane_c_bundle", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_build_bundle_emits_manifest_and_checksums_for_repo():
    repo_root = Path(__file__).resolve().parents[3]
    with tempfile.TemporaryDirectory() as tmp:
        out = MODULE.build_bundle(repo_root, Path(tmp), "9.9.9-test")
        assert out["status"] == "completed"
        bundle_dir = Path(out["bundle_dir"])
        assert (bundle_dir / "bundle_manifest.json").exists()
        assert (bundle_dir / "SHA256SUMS").exists()
        assert (bundle_dir / "SHA256SUMS.json").exists()
        assert Path(out["bundle_tar_gz"]).exists()


def test_bundle_manifest_has_required_contract_fields():
    repo_root = Path(__file__).resolve().parents[3]
    with tempfile.TemporaryDirectory() as tmp:
        out = MODULE.build_bundle(repo_root, Path(tmp), "9.9.10-test")
        manifest = json.loads((Path(out["bundle_dir"]) / "bundle_manifest.json").read_text(encoding="utf-8"))
        for key in [
            "schema_version",
            "product_version",
            "build_timestamp",
            "git_commit",
            "platforms",
            "managed_files",
            "skills_manifest",
            "templates_manifest",
            "checksums",
        ]:
            assert key in manifest
        assert manifest["product_version"] == "9.9.10-test"
        assert isinstance(manifest["managed_files"], list)
        assert manifest["managed_files"]


def test_bundle_manifest_includes_required_runtime_skills():
    repo_root = Path(__file__).resolve().parents[3]
    with tempfile.TemporaryDirectory() as tmp:
        out = MODULE.build_bundle(repo_root, Path(tmp), "9.9.12-test")
        manifest = json.loads((Path(out["bundle_dir"]) / "bundle_manifest.json").read_text(encoding="utf-8"))
        skills_manifest = manifest.get("skills_manifest") or []
        required = sorted(Path(rel).name for rel in MODULE.REQUIRED_RUNTIME_SKILL_DIRS)
        for skill in required:
            assert skill in skills_manifest


def test_build_bundle_excludes_runtime_cache_artifacts():
    repo_root = Path(__file__).resolve().parents[3]
    pycache_dir = repo_root / "scripts" / "op" / "__pycache__"
    pycache_dir.mkdir(parents=True, exist_ok=True)
    probe = pycache_dir / "temporary_probe.cpython-311.pyc"
    probe.write_bytes(b"probe")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            out = MODULE.build_bundle(repo_root, Path(tmp), "9.9.11-test")
            manifest = json.loads((Path(out["bundle_dir"]) / "bundle_manifest.json").read_text(encoding="utf-8"))
            managed = manifest["managed_files"]
            assert all("__pycache__" not in item for item in managed)
            assert all(not item.endswith(".pyc") for item in managed)
    finally:
        if probe.exists():
            probe.unlink()


def test_bundle_manifest_includes_op_simple_runtime_assets():
    repo_root = Path(__file__).resolve().parents[3]
    with tempfile.TemporaryDirectory() as tmp:
        out = MODULE.build_bundle(repo_root, Path(tmp), "9.9.13-test")
        manifest = json.loads((Path(out["bundle_dir"]) / "bundle_manifest.json").read_text(encoding="utf-8"))
        managed = set(manifest["managed_files"])
        required = {
            "scripts/op/op_simple_build.py",
            "scripts/op_simple/prompts/managers/boss.md",
            "scripts/op_simple/prompts/workers/optimus-fullstack-developer/README.md",
            "scripts/op_simple/prompts/workers/optimus-fullstack-tester/README.md",
            "scripts/op_simple/prompts/workers/optimus-reviewer/README.md",
            "agents/optimus-fullstack-developer/README.md",
            "agents/optimus-fullstack-tester/README.md",
            "agents/optimus-reviewer/README.md",
            "skills/dev-check-bundle/SKILL.md",
            "docs/plans/OP_SIMPLE_SCHEMA_CATALOG_V2.md",
        }
        for rel in required:
            assert rel in managed
        templates_manifest = set(manifest.get("templates_manifest") or [])
        assert "agents/optimus-fullstack-developer/README.md" in templates_manifest
        assert "agents/optimus-fullstack-tester/README.md" in templates_manifest
        assert "agents/optimus-reviewer/README.md" in templates_manifest
