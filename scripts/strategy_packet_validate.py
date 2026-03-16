#!/usr/bin/env python3
"""Validate strategy packet JSON against schema and REQ-057 gate checks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from scripts.strategy_validators import validate_strategy_packet_files


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate strategy packet JSON and REQ-057 consumability gate.")
    parser.add_argument("--input", required=True, help="Path to strategy packet JSON.")
    parser.add_argument("--schema", required=True, help="Path to strategy packet JSON schema.")
    parser.add_argument("--json-pretty", action="store_true", help="Pretty-print output JSON.")
    return parser.parse_args(argv)


def _render(payload: dict[str, object], *, pretty: bool) -> str:
    if pretty:
        return json.dumps(payload, indent=2, sort_keys=False)
    return json.dumps(payload, separators=(",", ":"), sort_keys=False)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = validate_strategy_packet_files(input_path=args.input, schema_path=args.schema)
    print(_render(payload, pretty=args.json_pretty))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
