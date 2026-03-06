import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


COMMON = _load(ROOT / "scripts" / "install" / "common.py", "lane_c_common")
CONFIG = _load(ROOT / "scripts" / "install" / "config.py", "lane_c_config")


def test_config_precedence_cli_over_project_over_global_over_defaults():
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp) / "home"
        repo = Path(tmp) / "repo"
        xdg = Path(tmp) / "xdg_config"
        home.mkdir(parents=True, exist_ok=True)
        repo.mkdir(parents=True, exist_ok=True)
        xdg.mkdir(parents=True, exist_ok=True)
        old_xdg = os.environ.get("XDG_CONFIG_HOME")
        os.environ["XDG_CONFIG_HOME"] = str(xdg)
        try:
            global_cfg = xdg / "optimus-prime" / "config.json"
            global_cfg.parent.mkdir(parents=True, exist_ok=True)
            global_cfg.write_text(
                json.dumps(
                    {
                        "profile": "budget",
                        "workflow": {"max_build_cycles": 7, "strict_validation": False, "sleep_minutes": 3},
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            project_cfg = repo / ".optimus-prime" / "config.json"
            project_cfg.parent.mkdir(parents=True, exist_ok=True)
            project_cfg.write_text(
                json.dumps(
                    {
                        "profile": "quality",
                        "workflow": {"max_build_cycles": 33},
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            payload = {
                "mode": "local",
                "repo_root": str(repo),
                "home_override": str(home),
                "profile": "balanced",
                "max_build_cycles": 99,
            }
            ctx = COMMON.resolve_context(payload)
            resolved = CONFIG.resolve_effective_config(payload, ctx)
            effective = resolved["effective_config"]
            assert resolved["errors"] == []
            assert effective["profile"] == "balanced"
            assert effective["workflow"]["max_build_cycles"] == 99
            # strict_validation from profile defaults after merges.
            assert effective["workflow"]["strict_validation"] is True
            assert effective["workflow"]["sleep_minutes"] == 2.0
            assert effective["workflow"]["enable_artifact_fan_in"] is False
            assert effective["workflow"]["max_parallel_workers"] == 8
        finally:
            if old_xdg is None:
                os.environ.pop("XDG_CONFIG_HOME", None)
            else:
                os.environ["XDG_CONFIG_HOME"] = old_xdg


def test_config_validation_reports_fix_guidance():
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp) / "home"
        home.mkdir(parents=True, exist_ok=True)
        payload = {
            "mode": "global",
            "home_override": str(home),
                "config": {
                    "profile": "invalid-profile",
                    "workflow": {
                        "max_build_cycles": -1,
                        "strict_validation": "bad",
                        "sleep_minutes": 0,
                        "enable_artifact_fan_in": "bad",
                    },
                    "rate_gate": {"max_wait_hours": 0},
                },
            }
        ctx = COMMON.resolve_context(payload)
        resolved = CONFIG.resolve_effective_config(payload, ctx)
        assert resolved["errors"]
        fields = {item["field"] for item in resolved["errors"]}
        assert "profile" in fields
        assert "workflow.max_build_cycles" in fields
        assert "workflow.strict_validation" in fields
        assert "workflow.sleep_minutes" in fields
        assert "workflow.enable_artifact_fan_in" in fields
        assert "rate_gate.max_wait_hours" in fields
        assert all("fix" in item for item in resolved["errors"])


def test_cli_sleep_minutes_override_wins():
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp) / "home"
        home.mkdir(parents=True, exist_ok=True)
        payload = {
            "mode": "global",
            "home_override": str(home),
            "sleep_minutes": 0.25,
        }
        ctx = COMMON.resolve_context(payload)
        resolved = CONFIG.resolve_effective_config(payload, ctx)
        assert resolved["errors"] == []
        assert resolved["effective_config"]["workflow"]["sleep_minutes"] == 0.25


def test_cli_enable_artifact_fan_in_override_wins():
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp) / "home"
        home.mkdir(parents=True, exist_ok=True)
        payload = {
            "mode": "global",
            "home_override": str(home),
            "enable_artifact_fan_in": True,
        }
        ctx = COMMON.resolve_context(payload)
        resolved = CONFIG.resolve_effective_config(payload, ctx)
        assert resolved["errors"] == []
        assert resolved["effective_config"]["workflow"]["enable_artifact_fan_in"] is True


def test_cli_max_parallel_workers_override_wins():
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp) / "home"
        home.mkdir(parents=True, exist_ok=True)
        payload = {
            "mode": "global",
            "home_override": str(home),
            "max_parallel_workers": 12,
        }
        ctx = COMMON.resolve_context(payload)
        resolved = CONFIG.resolve_effective_config(payload, ctx)
        assert resolved["errors"] == []
        assert resolved["effective_config"]["workflow"]["max_parallel_workers"] == 12
