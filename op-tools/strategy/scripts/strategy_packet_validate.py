#!/usr/bin/env python3
"""Validate strategy packets for schema compliance and REQ-059/REQ-065 consumability."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from strategy_validators import validate_strategy_packet_file


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _print_status(message: str) -> None:
    print(f"[{_timestamp()}] {message}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate strategy packets with schema and REQ-059/REQ-065 consumability checks."
    )
    parser.add_argument("--input", required=True, help="Path to the strategy packet JSON file.")
    parser.add_argument("--schema", required=True, help="Path to the strategy packet schema JSON file.")
    args = parser.parse_args(argv)

    _print_status(f"Loading strategy packet from {args.input}.")
    _print_status(f"Loading strategy packet schema from {args.schema}.")
    result = validate_strategy_packet_file(args.input, args.schema)
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")

    if result["ok"]:
        _print_status("Strategy packet passed schema and REQ-059/REQ-065 consumability validation.")
        return 0

    _print_status(
        "Strategy packet failed validation with "
        f"{result['summary']['error_count']} error(s); packet is not consumable."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
