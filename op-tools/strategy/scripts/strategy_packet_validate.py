from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.strategy_validators import validate_strategy_packet_files


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate a strategy packet against schema and REQ-055/REQ-061/REQ-067 consumability gates."
    )
    parser.add_argument("--input", required=True, help="Path to the strategy packet JSON file.")
    parser.add_argument("--schema", required=True, help="Path to the strategy packet JSON schema.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    result = validate_strategy_packet_files(args.input, args.schema)
    sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
