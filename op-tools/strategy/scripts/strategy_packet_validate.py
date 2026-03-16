#!/usr/bin/env python3
"""CLI wrapper for strategy packet validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from scripts.strategy_validators import validate_strategy_packet
except ModuleNotFoundError:  # pragma: no cover - direct script execution path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.strategy_validators import validate_strategy_packet


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate strategy packet contract and REQ-056 consumability gate.")
    parser.add_argument("--input", required=True, help="Path to strategy packet JSON")
    parser.add_argument("--schema", required=True, help="Path to strategy packet schema JSON")
    parser.add_argument("--context", help="Optional path to strategy packet context JSON")
    parser.add_argument(
        "--stability-contract",
        help="Optional path to recommendation id stability contract JSON",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    result = validate_strategy_packet(
        packet_path=Path(args.input),
        schema_path=Path(args.schema),
        context_path=Path(args.context).resolve() if args.context else None,
        stability_contract_path=Path(args.stability_contract).resolve() if args.stability_contract else None,
    )
    json.dump(result, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
