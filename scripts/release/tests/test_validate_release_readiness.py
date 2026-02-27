import importlib.util
import json
import sys
import tempfile
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "validate_release_readiness.py"
SPEC = importlib.util.spec_from_file_location("validate_release_readiness", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_validate_passes_for_current_repo_version():
    repo_root = Path(__file__).resolve().parents[3]
    version = (repo_root / "VERSION").read_text(encoding="utf-8").strip()
    out = MODULE.validate(repo_root, version)
    assert out["ok"] is True
    assert out["status"] == "passed"


def test_validate_blocks_when_changelog_missing_version():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "docs" / "release").mkdir(parents=True, exist_ok=True)
        (root / "VERSION").write_text("1.2.3\n", encoding="utf-8")
        (root / "CHANGELOG.md").write_text("# Changelog\n\nNo version.\n", encoding="utf-8")
        (root / "docs" / "release" / "LANE_C_RELEASE_CHECKLIST.md").write_text("ok\n", encoding="utf-8")
        out = MODULE.validate(root, "1.2.3")
        assert out["ok"] is False
        assert out["status"] == "blocked"
        failing_ids = [item["id"] for item in out["checks"] if not item["passed"]]
        assert "changelog_contains_version" in failing_ids
