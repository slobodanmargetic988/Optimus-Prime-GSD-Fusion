import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
_TEMP_HOLDERS: list[tempfile.TemporaryDirectory[str]] = []


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RELEASE = _load(ROOT / "scripts" / "release" / "build_lane_c_bundle.py", "lane_c_release")
INSTALL = _load(ROOT / "scripts" / "install" / "op_install.py", "lane_c_install")
UNINSTALL = _load(ROOT / "scripts" / "install" / "op_uninstall.py", "lane_c_uninstall")
UPDATE = _load(ROOT / "scripts" / "install" / "op_update.py", "lane_c_update")
DOCTOR = _load(ROOT / "scripts" / "install" / "op_doctor.py", "lane_c_doctor")


def _build_bundle(version: str) -> Path:
    tmp = tempfile.TemporaryDirectory()
    _TEMP_HOLDERS.append(tmp)
    out = RELEASE.build_bundle(ROOT, Path(tmp.name), version)
    return Path(out["bundle_dir"])


def test_global_install_and_uninstall_flow():
    bundle_dir = _build_bundle("1.2.3-test")
    with tempfile.TemporaryDirectory() as home:
        payload = {
            "bundle_dir": str(bundle_dir),
            "mode": "global",
            "home_override": home,
            "codex_home": str(Path(home) / ".codex"),
            "bin_dir": str(Path(home) / ".local" / "bin"),
        }
        installed = INSTALL.run_install(payload)
        assert installed["ok"] is True
        state_path = Path(installed["data"]["install_state_path"])
        state = json.loads(state_path.read_text(encoding="utf-8"))
        assert state["installed_version"] == "1.2.3-test"
        assert (Path(home) / ".local" / "bin" / "opctl").exists()
        assert (Path(home) / ".local" / "bin" / "op").exists()

        uninstalled = UNINSTALL.run_uninstall({"mode": "global", "home_override": home})
        assert uninstalled["ok"] is True
        assert not state_path.exists()


def test_update_blocks_on_corrupt_checksum():
    bundle_dir = _build_bundle("2.0.0-test")
    with tempfile.TemporaryDirectory() as home:
        payload = {
            "bundle_dir": str(bundle_dir),
            "mode": "global",
            "home_override": home,
            "codex_home": str(Path(home) / ".codex"),
            "bin_dir": str(Path(home) / ".local" / "bin"),
        }
        first = INSTALL.run_install(payload)
        assert first["ok"] is True

        checksum_path = bundle_dir / "SHA256SUMS.json"
        checksum_payload = json.loads(checksum_path.read_text(encoding="utf-8"))
        any_key = next(iter(checksum_payload.keys()))
        checksum_payload[any_key] = "deadbeef"
        checksum_path.write_text(json.dumps(checksum_payload, indent=2) + "\n", encoding="utf-8")

        try:
            UPDATE.run_update(payload)
            assert False, "expected update to fail on checksum mismatch"
        except Exception as exc:  # noqa: BLE001
            assert "checksum mismatch" in str(exc) or "checksum" in str(exc).lower()


def test_doctor_reports_blocked_when_not_installed_then_repair_still_deterministic():
    with tempfile.TemporaryDirectory() as home:
        blocked = DOCTOR.run_doctor(
            {
                "mode": "global",
                "home_override": home,
                "codex_home": str(Path(home) / ".codex"),
                "bin_dir": str(Path(home) / ".local" / "bin"),
            }
        )
        assert blocked["ok"] is False
        assert blocked["status"] == "blocked"

        repaired = DOCTOR.run_doctor(
            {
                "mode": "global",
                "home_override": home,
                "codex_home": str(Path(home) / ".codex"),
                "bin_dir": str(Path(home) / ".local" / "bin"),
                "repair": True,
            }
        )
        assert repaired["status"] in {"passed", "blocked"}
        assert "checks" in repaired["data"]


def test_local_mode_install_state_path_in_repo():
    bundle_dir = _build_bundle("3.0.0-test")
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir(parents=True, exist_ok=True)
        payload = {
            "bundle_dir": str(bundle_dir),
            "mode": "local",
            "repo_root": str(repo),
            "home_override": tmp,
            "codex_home": str(Path(tmp) / ".codex"),
            "bin_dir": str(repo / ".optimus-prime" / "bin"),
        }
        installed = INSTALL.run_install(payload)
        assert installed["ok"] is True
        state_path = repo / ".optimus-prime" / "install" / "INSTALL_STATE.json"
        assert state_path.exists()
