#!/usr/bin/env python3
"""Validate deterministic Lane C release readiness constraints."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def validate(repo_root: Path, version: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    version_path = repo_root / "VERSION"
    changelog_path = repo_root / "CHANGELOG.md"
    checklist_path = repo_root / "docs" / "release" / "LANE_C_RELEASE_CHECKLIST.md"

    checks.append(
        {
            "id": "version_file_exists",
            "passed": version_path.exists(),
            "message": f"{version_path} exists",
        }
    )
    checks.append(
        {
            "id": "changelog_exists",
            "passed": changelog_path.exists(),
            "message": f"{changelog_path} exists",
        }
    )
    checks.append(
        {
            "id": "checklist_exists",
            "passed": checklist_path.exists(),
            "message": f"{checklist_path} exists",
        }
    )

    if version_path.exists():
        file_version = _read_text(version_path).strip()
        checks.append(
            {
                "id": "version_matches_tag",
                "passed": file_version == version,
                "message": f"VERSION matches tag version ({file_version} vs {version})",
            }
        )
    if changelog_path.exists():
        changelog = _read_text(changelog_path)
        checks.append(
            {
                "id": "changelog_contains_version",
                "passed": version in changelog,
                "message": f"CHANGELOG includes {version}",
            }
        )

    passed = all(bool(item["passed"]) for item in checks)
    return {
        "ok": passed,
        "status": "passed" if passed else "blocked",
        "checks": checks,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate release readiness for Lane C tags.")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--json-pretty", action="store_true")
    return parser.parse_args()


def _print(payload: dict[str, Any], pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=False))
    else:
        print(json.dumps(payload, separators=(",", ":"), sort_keys=False))


def main() -> int:
    args = parse_args()
    out = validate(Path(args.repo_root).expanduser().resolve(), args.version.strip())
    _print(out, args.json_pretty)
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
