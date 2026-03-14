#!/usr/bin/env python3
"""Build a minimal multi-profile rate snapshot from ChatGPT usage endpoint."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib import error, request

USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"
USAGE_TIMEOUT_SECONDS = 20
USAGE_RETRY_COUNT = 2
LOG_FILE_NAME = "minimal-rate-snapshot.log"
LOG_CHECK_STATE_NAME = ".minimal-rate-snapshot-log-check.json"
LOG_SIZE_LIMIT_BYTES = 3 * 1024 * 1024 * 1024
LOG_CHECK_INTERVAL_SECONDS = 6 * 60 * 60


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read usage-based rate snapshots for discovered local Codex profiles.")
    parser.add_argument("--minimal", action="store_true", help="Emit only alias, codex_home, and gated fields.")
    parser.add_argument("--table", action="store_true", help="Emit a human-readable table with remaining percentages and email.")
    parser.add_argument("--json-pretty", action="store_true", help="Pretty-print JSON output.")
    parser.add_argument(
        "--log-dir",
        default=str((Path.home() / "projects" / "LOGS").resolve()),
        help="Directory for human-facing logs (default: ~/projects/LOGS).",
    )
    return parser.parse_args()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_timestamp_label() -> str:
    return now_utc().strftime("%Y-%m-%d %H:%M:%S UTC")


def coerce_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


class HumanLogger:
    def __init__(self, log_dir: Path) -> None:
        self.log_dir = log_dir
        self.log_file = self.log_dir / LOG_FILE_NAME
        self.state_file = self.log_dir / LOG_CHECK_STATE_NAME
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._truncate_large_logs_if_due()

    def _truncate_large_logs_if_due(self) -> None:
        now_epoch = int(time.time())
        last_check = self._read_last_check_epoch()
        if last_check is not None and (now_epoch - last_check) < LOG_CHECK_INTERVAL_SECONDS:
            return

        for candidate in self.log_dir.glob("*.log"):
            if not candidate.is_file():
                continue
            try:
                size_bytes = candidate.stat().st_size
            except OSError:
                continue
            if size_bytes <= LOG_SIZE_LIMIT_BYTES:
                continue
            try:
                candidate.write_text("", encoding="utf-8")
                self.log(f"Truncated oversized log file at '{candidate}'.")
            except OSError as exc:
                self.log(f"Failed truncating oversized log '{candidate}': {exc}")

        self._write_last_check_epoch(now_epoch)

    def _read_last_check_epoch(self) -> int | None:
        if not self.state_file.is_file():
            return None
        try:
            payload = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        raw = payload.get("last_checked_epoch")
        if isinstance(raw, int):
            return raw
        return None

    def _write_last_check_epoch(self, value: int) -> None:
        payload = {"last_checked_epoch": value}
        try:
            self.state_file.write_text(json.dumps(payload), encoding="utf-8")
        except OSError:
            return

    def log(self, message: str) -> None:
        line = f"{now_timestamp_label()} | {message}"
        try:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            with self.log_file.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError:
            pass
        sys.stderr.write(line + "\n")
        sys.stderr.flush()


def resolve_default_codex_home() -> Path:
    env_home = os.environ.get("CODEX_HOME")
    if env_home:
        return Path(os.path.expanduser(os.path.expandvars(env_home))).resolve()
    return (Path.home() / ".codex").resolve()


def discover_profile_paths(default_codex_home: Path, home_dir: Path) -> list[Path]:
    candidates: dict[str, Path] = {}

    roots: list[Path] = []
    for root in (home_dir, default_codex_home.parent):
        resolved = root.expanduser().resolve()
        if resolved not in roots:
            roots.append(resolved)

    for root in roots:
        if not root.is_dir():
            continue
        for child in root.iterdir():
            if not child.is_dir():
                continue
            name = child.name
            if name == ".codex" or name.startswith(".codex-"):
                resolved_child = child.resolve()
                candidates[str(resolved_child)] = resolved_child

    if default_codex_home.is_dir():
        candidates[str(default_codex_home.resolve())] = default_codex_home.resolve()

    resolved_default = default_codex_home.resolve()
    paths = sorted(candidates.values(), key=lambda item: str(item).lower())

    if len(paths) > 1:
        paths = [item for item in paths if item.resolve() != resolved_default]

    if not paths and default_codex_home.is_dir():
        paths = [resolved_default]

    return paths


def alias_from_codex_home(codex_home: Path, default_codex_home: Path) -> str:
    resolved = codex_home.resolve()
    if resolved == default_codex_home.resolve():
        return "codex"

    name = codex_home.name
    if name == ".codex":
        return "codex"
    if name.startswith(".codex-") and len(name) > len(".codex-"):
        return name[len(".codex-") :]
    if name.startswith(".codex"):
        suffix = name[len(".codex") :].lstrip("-_")
        if suffix:
            return suffix
    fallback = name.lstrip(".")
    return fallback if fallback else "codex"


def map_aliases(profile_paths: list[Path], default_codex_home: Path) -> list[tuple[str, Path]]:
    alias_counts: dict[str, int] = {}
    mapped: list[tuple[str, Path]] = []
    for codex_home in profile_paths:
        base_alias = alias_from_codex_home(codex_home, default_codex_home)
        seen = alias_counts.get(base_alias, 0)
        alias_counts[base_alias] = seen + 1
        alias = base_alias if seen == 0 else f"{base_alias}-{seen + 1}"
        mapped.append((alias, codex_home))
    return mapped


def auth_json_candidates(codex_home: Path) -> list[Path]:
    return [codex_home / "auth.json", codex_home / "config" / "auth.json"]


def has_profile_auth_json(codex_home: Path) -> bool:
    return (codex_home / "auth.json").is_file()


def read_access_token(codex_home: Path) -> tuple[str | None, Path | None]:
    for candidate in auth_json_candidates(codex_home):
        if not candidate.is_file():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        tokens = payload.get("tokens")
        if not isinstance(tokens, dict):
            continue
        raw = tokens.get("access_token")
        if isinstance(raw, str) and raw.strip():
            return raw.strip(), candidate
    return None, None


def fetch_usage_payload(access_token: str) -> dict[str, Any]:
    req = request.Request(
        USAGE_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        },
        method="GET",
    )
    with request.urlopen(req, timeout=USAGE_TIMEOUT_SECONDS) as response:
        body = response.read().decode("utf-8")
    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise ValueError("usage response is not a JSON object")
    return payload


def fetch_usage_with_retries(
    *,
    alias: str,
    access_token: str,
    logger: HumanLogger,
    retries: int = USAGE_RETRY_COUNT,
    fetcher: Callable[[str], dict[str, Any]] = fetch_usage_payload,
) -> tuple[dict[str, Any] | None, str | None]:
    max_attempts = retries + 1
    last_error: str | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            payload = fetcher(access_token)
            logger.log(f"[{alias}] Usage endpoint succeeded on attempt {attempt}/{max_attempts}.")
            return payload, None
        except (error.URLError, error.HTTPError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            last_error = str(exc)
            logger.log(f"[{alias}] Usage call failed on attempt {attempt}/{max_attempts}: {exc}")
            if attempt < max_attempts:
                time.sleep(attempt)
            continue
    return None, last_error


def normalize_window(raw_window: Any) -> dict[str, Any]:
    if not isinstance(raw_window, dict):
        return {"used_percent": None, "reset_at": None}
    return {
        "used_percent": coerce_float(raw_window.get("used_percent")),
        "reset_at": raw_window.get("reset_at"),
    }


def classify_gate(primary_used: float | None, secondary_used: float | None) -> bool | str:
    if primary_used is None:
        return "hard-gated"
    secondary = secondary_used if secondary_used is not None else 0.0

    if primary_used > 92.0 or secondary > 96.0:
        return "hard-gated"
    if (60.0 <= primary_used <= 92.0) or (80.0 <= secondary <= 96.0):
        return "soft-gated"
    if primary_used < 60.0 and secondary < 80.0:
        return False
    return "soft-gated"


def build_profile_snapshot(
    *,
    alias: str,
    codex_home: Path,
    payload: dict[str, Any] | None,
    unavailable: bool,
) -> dict[str, Any]:
    if unavailable or not isinstance(payload, dict):
        return {
            "email": None,
            "primary_window": {"used_percent": None, "reset_at": None},
            "secondary_window": {"used_percent": None, "reset_at": None},
            "alias": alias,
            "codex_home": str(codex_home),
            "gated": "not-available",
        }

    rate_limit = payload.get("rate_limit")
    if not isinstance(rate_limit, dict):
        rate_limit = {}
    primary_window = normalize_window(rate_limit.get("primary_window"))
    secondary_window = normalize_window(rate_limit.get("secondary_window"))
    gated = classify_gate(primary_window["used_percent"], secondary_window["used_percent"])
    email = payload.get("email")
    if not isinstance(email, str):
        email = None

    return {
        "email": email,
        "primary_window": primary_window,
        "secondary_window": secondary_window,
        "alias": alias,
        "codex_home": str(codex_home),
        "gated": gated,
    }


def build_auth_missing_snapshot(alias: str, codex_home: Path) -> dict[str, Any]:
    return {
        "email": None,
        "primary_window": {"used_percent": None, "reset_at": None},
        "secondary_window": {"used_percent": None, "reset_at": None},
        "alias": alias,
        "codex_home": str(codex_home),
        "gated": "hard-gated",
    }


def reduce_minimal(snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"alias": item.get("alias"), "codex_home": item.get("codex_home"), "gated": item.get("gated")} for item in snapshots]


def remaining_percent(used_percent: float | None) -> float | None:
    if used_percent is None:
        return None
    remaining = 100.0 - used_percent
    if remaining < 0.0:
        return 0.0
    if remaining > 100.0:
        return 100.0
    return round(remaining, 2)


def _render_percent_cell(value: float | None) -> str:
    if value is None:
        return "n/a"
    if value.is_integer():
        return f"{int(value)}%"
    return f"{value:.2f}%"


def render_table(snapshots: list[dict[str, Any]]) -> str:
    headers = ["alias", "remaining 5h", "remaining weekly", "email"]
    rows: list[list[str]] = []
    for item in snapshots:
        primary_window = item.get("primary_window")
        secondary_window = item.get("secondary_window")
        primary_used = None
        secondary_used = None
        if isinstance(primary_window, dict):
            primary_used = coerce_float(primary_window.get("used_percent"))
        if isinstance(secondary_window, dict):
            secondary_used = coerce_float(secondary_window.get("used_percent"))
        rows.append(
            [
                str(item.get("alias") or ""),
                _render_percent_cell(remaining_percent(primary_used)),
                _render_percent_cell(remaining_percent(secondary_used)),
                str(item.get("email") or "n/a"),
            ]
        )

    widths = [len(header) for header in headers]
    for row in rows:
        for idx, value in enumerate(row):
            widths[idx] = max(widths[idx], len(value))

    def _format_row(values: list[str]) -> str:
        return " | ".join(values[idx].ljust(widths[idx]) for idx in range(len(values)))

    separator = "-|-".join("-" * widths[idx] for idx in range(len(widths)))
    lines = [_format_row(headers), separator]
    lines.extend(_format_row(row) for row in rows)
    return "\n".join(lines)


def emit_json(payload: Any, pretty: bool) -> None:
    if pretty:
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=False) + "\n")
        return
    sys.stdout.write(json.dumps(payload, separators=(",", ":"), sort_keys=False) + "\n")


def main() -> int:
    args = parse_args()
    logger = HumanLogger(log_dir=Path(args.log_dir).expanduser().resolve())
    logger.log("Starting minimal-rate-snapshot profile scan.")

    default_codex_home = resolve_default_codex_home()
    profile_paths = discover_profile_paths(default_codex_home, Path.home())
    mapped_profiles = map_aliases(profile_paths, default_codex_home)
    logger.log(f"Discovered {len(mapped_profiles)} profile(s) to process.")

    snapshots: list[dict[str, Any]] = []
    for alias, codex_home in mapped_profiles:
        logger.log(f"[{alias}] Processing profile at '{codex_home}'.")
        if not has_profile_auth_json(codex_home):
            logger.log(f"[{alias}] Skipping profile because '/auth.json' is missing.")
            continue
        access_token, auth_path = read_access_token(codex_home)
        if not access_token:
            logger.log(f"[{alias}] Missing readable access token in auth.json; marking as hard-gated.")
            snapshots.append(build_auth_missing_snapshot(alias, codex_home))
            continue

        logger.log(f"[{alias}] Access token loaded from '{auth_path}'.")
        payload, fetch_error = fetch_usage_with_retries(alias=alias, access_token=access_token, logger=logger)
        if payload is None:
            logger.log(f"[{alias}] Usage unavailable after retries; marking as not-available. Last error: {fetch_error}")
            snapshots.append(
                build_profile_snapshot(
                    alias=alias,
                    codex_home=codex_home,
                    payload=None,
                    unavailable=True,
                )
            )
            continue

        snapshots.append(
            build_profile_snapshot(
                alias=alias,
                codex_home=codex_home,
                payload=payload,
                unavailable=False,
            )
        )

    if args.table:
        sys.stdout.write(render_table(snapshots) + "\n")
    else:
        output = reduce_minimal(snapshots) if args.minimal else snapshots
        emit_json(output, pretty=bool(args.json_pretty))
    logger.log("Completed minimal-rate-snapshot profile scan.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
