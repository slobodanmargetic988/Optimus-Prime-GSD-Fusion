#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_op_core_is_importable_as_package() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, "-c", "import scripts.op.op_core; print('PACKAGE_IMPORT_OK')"],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "PACKAGE_IMPORT_OK"
