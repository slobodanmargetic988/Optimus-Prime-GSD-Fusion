#!/usr/bin/env python3
"""Validate git bootstrap state for OP initialize."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


def _run(repo_root: Path, *args: str) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        text=True,
        capture_output=True,
        check=False,
    )
    return int(proc.returncode), proc.stdout or "", proc.stderr or ""


def _is_git_repo(repo_root: Path) -> bool:
    code, out, _ = _run(repo_root, "rev-parse", "--is-inside-work-tree")
    return code == 0 and out.strip().lower() == "true"


def validate_git_bootstrap(
    *,
    repo_root: Path,
    required_branch: str,
    require_readme: bool,
    required_primary_branch: str | None = None,
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    facts: dict[str, Any] = {}

    if not _is_git_repo(repo_root):
        errors.append(
            {
                "code": "git_not_initialized",
                "message": "repository is not initialized as a git work tree",
            }
        )
        return {"ok": False, "errors": errors, "warnings": warnings, "facts": facts}

    head_code, head_out, _ = _run(repo_root, "rev-parse", "HEAD")
    head = head_out.strip()
    if head_code != 0 or not head:
        errors.append(
            {
                "code": "git_head_missing",
                "message": "unable to resolve HEAD commit; first commit is missing",
            }
        )
    else:
        facts["head"] = head

    branch_code, _, _ = _run(repo_root, "show-ref", "--verify", f"refs/heads/{required_branch}")
    if branch_code != 0:
        errors.append(
            {
                "code": "git_required_branch_missing",
                "message": f"required branch missing: {required_branch}",
                "branch": required_branch,
            }
        )

    if required_primary_branch:
        primary_code, _, _ = _run(repo_root, "show-ref", "--verify", f"refs/heads/{required_primary_branch}")
        if primary_code != 0:
            errors.append(
                {
                    "code": "git_primary_branch_missing",
                    "message": f"required primary branch missing: {required_primary_branch}",
                    "branch": required_primary_branch,
                }
            )

    if require_readme:
        readme = repo_root / "README.md"
        if not readme.exists():
            errors.append(
                {
                    "code": "git_readme_missing",
                    "message": "README.md is required for bootstrap but was not found",
                }
            )
        else:
            text = readme.read_text(encoding="utf-8", errors="replace").strip()
            if not text:
                errors.append(
                    {
                        "code": "git_readme_empty",
                        "message": "README.md exists but is empty",
                    }
                )

    remote_code, remote_out, _ = _run(repo_root, "remote", "get-url", "origin")
    origin = remote_out.strip()
    if remote_code != 0 or not origin:
        warnings.append(
            {
                "code": "git_origin_missing",
                "message": "origin remote is not configured; remote branch check skipped",
            }
        )
    else:
        facts["origin"] = origin
        ls_code, ls_out, ls_err = _run(repo_root, "ls-remote", "--heads", "origin", required_branch)
        if ls_code != 0:
            warnings.append(
                {
                    "code": "git_remote_check_failed",
                    "message": "unable to verify remote branch on origin",
                    "branch": required_branch,
                    "details": (ls_err.strip() or ls_out.strip()),
                }
            )
        elif required_branch not in ls_out:
            warnings.append(
                {
                    "code": "git_remote_branch_missing",
                    "message": f"origin does not advertise branch {required_branch}",
                    "branch": required_branch,
                }
            )

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "facts": facts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate OP git bootstrap state")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--required-branch", default="RAB-BASE")
    parser.add_argument("--required-primary-branch")
    parser.add_argument("--require-readme", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).expanduser().resolve()
    result = validate_git_bootstrap(
        repo_root=repo_root,
        required_branch=args.required_branch,
        require_readme=bool(args.require_readme),
        required_primary_branch=args.required_primary_branch,
    )
    print(json.dumps(result, indent=2, sort_keys=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
