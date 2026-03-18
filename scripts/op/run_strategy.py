#!/usr/bin/env python3
"""Standalone CLI wrapper for the shared strategy runner."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from strategy_runner import StrategyRunnerError, run_strategy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the LLM-first strategy generator.")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--strategy-manifest")
    parser.add_argument("--strategy-manifest-file")
    parser.add_argument("--json-pretty", action="store_true")
    return parser.parse_args()


def _print_json(payload: dict[str, object], pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=False))
    else:
        print(json.dumps(payload, separators=(",", ":"), sort_keys=False))


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).expanduser().resolve()
    try:
        result = run_strategy(
            repo_root=repo_root,
            manifest=args.strategy_manifest,
            manifest_file=args.strategy_manifest_file,
        )
    except StrategyRunnerError as exc:
        _print_json(
            {
                "ok": False,
                "status": "failed",
                "summary": "Strategy generation failed.",
                "errors": [{"code": exc.code, "message": exc.message, "stage": "strategy"}],
                "warnings": [],
                "artifacts": [],
            },
            args.json_pretty,
        )
        return 1

    _print_json(
        {
            "ok": True,
            "status": "completed",
            "summary": "Strategy artifacts generated.",
            "errors": [],
            "warnings": [],
            "artifacts": result.artifacts,
            "data": {
                "manifest_ref": result.manifest_ref,
                "packet_path": str(result.packet_path),
                "summary_path": str(result.summary_path),
            },
        },
        args.json_pretty,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
