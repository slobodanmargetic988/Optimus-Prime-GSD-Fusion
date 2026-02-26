#!/usr/bin/env python3
"""Configurable sleep helper.

Examples:
  python3 sleep_wait.py --for 30m
  python3 sleep_wait.py --for 1h30m
  python3 sleep_wait.py --until "03:30"
  python3 sleep_wait.py --until "2026-02-21T03:30:00" --tz Europe/Belgrade
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


DURATION_RE = re.compile(r"(\d+)([smhd])")
HHMM_RE = re.compile(r"^\d{2}:\d{2}(:\d{2})?$")


def parse_duration(value: str) -> int:
    """Parse duration strings like 30m, 1h30m, 45s, 2d.

    Returns total seconds.
    """
    value = value.strip().lower()
    if not value:
        raise ValueError("empty duration")

    pos = 0
    total = 0
    for match in DURATION_RE.finditer(value):
        if match.start() != pos:
            raise ValueError(f"invalid duration syntax near '{value[pos:]}'")
        qty = int(match.group(1))
        unit = match.group(2)
        pos = match.end()
        if unit == "s":
            total += qty
        elif unit == "m":
            total += qty * 60
        elif unit == "h":
            total += qty * 3600
        elif unit == "d":
            total += qty * 86400
        else:
            raise ValueError(f"unsupported duration unit '{unit}'")

    if pos != len(value):
        raise ValueError(f"invalid duration syntax near '{value[pos:]}'")
    if total <= 0:
        raise ValueError("duration must be > 0")
    return total


def parse_until(value: str, tz_name: str | None) -> tuple[datetime, datetime]:
    """Parse --until as HH:MM[:SS] or ISO datetime.

    Returns (now, target) in same timezone.
    """
    tz = ZoneInfo(tz_name) if tz_name else datetime.now().astimezone().tzinfo
    now = datetime.now(tz=tz)
    raw = value.strip()

    if HHMM_RE.match(raw):
        parts = [int(p) for p in raw.split(":")]
        if len(parts) == 2:
            hour, minute = parts
            second = 0
        else:
            hour, minute, second = parts
        target = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
        if target <= now:
            target = target + timedelta(days=1)
        return now, target

    normalized = raw.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        target = parsed.replace(tzinfo=tz)
    else:
        target = parsed.astimezone(tz)
    return now, target


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Configurable sleep helper")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--for",
        dest="duration",
        help="duration like 30m, 1h30m, 45s, 2d",
    )
    mode.add_argument(
        "--until",
        dest="until",
        help='target time as "HH:MM", "HH:MM:SS", or ISO datetime',
    )
    parser.add_argument(
        "--tz",
        help="IANA timezone (for --until parsing), e.g. Europe/Belgrade",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="compute and print wait duration without sleeping",
    )
    parser.add_argument(
        "--max-seconds",
        type=int,
        default=0,
        help="optional safety cap; fail if computed wait exceeds this value",
    )
    parser.add_argument(
        "--reason",
        default="",
        help="optional reason label printed in logs",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.duration:
            seconds = parse_duration(args.duration)
            now = datetime.now().astimezone()
            target = now + timedelta(seconds=seconds)
        else:
            now, target = parse_until(args.until, args.tz)
            delta = target - now
            seconds = max(0, int(delta.total_seconds()))
    except Exception as exc:  # noqa: BLE001
        print(f"[sleep] invalid input: {exc}", file=sys.stderr)
        return 2

    if args.max_seconds and seconds > args.max_seconds:
        print(
            f"[sleep] refused: computed wait {seconds}s exceeds max {args.max_seconds}s",
            file=sys.stderr,
        )
        return 2

    reason = f" reason='{args.reason}'" if args.reason else ""
    print(f"[sleep] now={now.isoformat()}{reason}")
    print(f"[sleep] target={target.isoformat()}")
    print(f"[sleep] wait_seconds={seconds}")

    if args.dry_run:
        print("[sleep] dry-run complete")
        return 0

    if seconds > 0:
        time.sleep(seconds)
    print(f"[sleep] done_at={datetime.now().astimezone().isoformat()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

