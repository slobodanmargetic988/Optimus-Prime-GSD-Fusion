#!/usr/bin/env python3
"""Check staged runtime startup without user configuration or third-party packages."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main() -> None:
    if sys.version_info < (3, 11):
        raise SystemExit("Python 3.11+ is required for the bundled Codex profile parser.")
    root = Path(__file__).resolve().parents[1] / ".runtime"
    required = (
        "scripts/op/opctl.py",
        "scripts/op/claude_executor.py",
        "scripts/op/planner/plan_limits.py",
        "scripts/op/planner/prompts/llm_plan_prompt.md",
        "scripts/op_simple/prompts/managers/boss.md",
        "docs/plans/OP_SIMPLE_SCHEMA_CATALOG_V2.md",
        "skills/thread-dispatch/scripts/dispatch_codex_run.py",
        "skills/workstation-preparation/scripts/prepare_workstation.py",
        "desktop/electron/runtime-bridge.py",
    )
    missing = [name for name in required if not (root / name).is_file()]
    if missing:
        raise SystemExit("Staged runtime is incomplete: " + ", ".join(missing))
    # Retain only OS process essentials; no provider credentials, Codex homes,
    # telemetry settings, Python site packages or developer configuration.
    environment = {
        name: value for name, value in os.environ.items()
        if name in {"PATH", "SystemRoot", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "TMP", "TEMP"}
    }
    with tempfile.TemporaryDirectory(prefix="optimus-runtime-check-") as temporary:
        environment.update(HOME=temporary, USERPROFILE=temporary, PYTHONDONTWRITEBYTECODE="1")
        commands = (
            (["--help"], None),
            (["--input-json", "-"], json.dumps({"command": "/op-status", "repo_root": temporary})),
        )
        for arguments, payload in commands:
            result = subprocess.run(
                [sys.executable, "-S", str(root / "scripts/op/opctl.py"), *arguments],
                cwd=temporary, env=environment, input=payload, text=True,
                capture_output=True, timeout=30, check=False,
            )
            if result.returncode:
                raise SystemExit(f"Runtime startup failed: {result.stderr or result.stdout}")
            if payload is not None:
                response = json.loads(result.stdout)
                if response.get("ok") is not True or response.get("command") != "op-status":
                    raise SystemExit("Runtime status check returned an unexpected result.")
    print("Staged runtime starts with a clean home and Python standard library only. No model calls made.")


if __name__ == "__main__":
    main()
