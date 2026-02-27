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

