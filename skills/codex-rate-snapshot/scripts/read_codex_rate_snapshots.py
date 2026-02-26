#!/usr/bin/env python3
"""Read Codex rate-limit snapshots from session JSONL token_count events."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
RESET_KEYS = ("reset_at", "resets_at", "resetAt", "resetsAt", "reset_time", "resetTime")


@dataclass
class WindowSnapshot:
    used_percent: float | None
    remaining_percent: float | None
    reset_at: str | None
    reset_in_hours: float | None
    gated: bool


@dataclass
class ProfileSnapshot:
    alias: str
    codex_home: str
    account_identity: str | None
    account_source: str | None
    session_file: str | None
    token_count_event_found: bool
    five_hour: WindowSnapshot
    weekly: WindowSnapshot
    recommended_action: str
    soft_concurrency_gated: bool
    wait_until_reset_candidate: bool
    wait_seconds: int | None
    errors: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read Codex session JSONL token_count rate limits for one or more profiles.")
    parser.add_argument(
        "--profile",
        action="append",
        default=[],
        help="profile mapping alias=PATH_OR_DEFAULT (repeatable). PATH_OR_DEFAULT may be 'default'.",
    )
    parser.add_argument("--gate-5h-percent", type=float, default=15.0)
    parser.add_argument("--gate-weekly-percent", type=float, default=10.0)
    parser.add_argument("--soft-gate-5h-percent", type=float, default=40.0)
    parser.add_argument("--soft-gate-weekly-percent", type=float, default=25.0)
    parser.add_argument("--soft-max-active-workers", type=int, default=3)
    parser.add_argument("--wait-max-hours", type=float, default=4.0)
    parser.add_argument("--json-pretty", action="store_true")
    return parser.parse_args()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_profile_map(items: list[str]) -> dict[str, str]:
    if not items:
        return {"codex": "default"}
    result: dict[str, str] = {}
    for raw in items:
        if "=" not in raw:
            raise ValueError(f"invalid --profile value '{raw}' (expected alias=path)")
        alias, value = raw.split("=", 1)
        alias = alias.strip()
        value = value.strip()
        if not alias:
            raise ValueError(f"invalid --profile value '{raw}' (empty alias)")
        if not value:
            raise ValueError(f"invalid --profile value '{raw}' (empty path)")
        result[alias] = value
    return result


def resolve_codex_home(value: str) -> Path:
    if value == "default":
        env_home = os.environ.get("CODEX_HOME")
        if env_home:
            return Path(os.path.expandvars(os.path.expanduser(env_home))).resolve()
        return (Path.home() / ".codex").resolve()
    return Path(os.path.expandvars(os.path.expanduser(value))).resolve()


def newest_session_jsonl(codex_home: Path) -> Path | None:
    sessions_root = codex_home / "sessions"
    if not sessions_root.exists():
        return None
    candidates = [p for p in sessions_root.rglob("*.jsonl") if p.is_file()]
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def _dict_get_path(obj: dict[str, Any], *keys: str) -> Any:
    cur: Any = obj
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


def _find_rate_limits(node: Any) -> dict[str, Any] | None:
    if isinstance(node, dict):
        rl = node.get("rate_limits")
        if isinstance(rl, dict) and isinstance(rl.get("primary"), dict) and isinstance(rl.get("secondary"), dict):
            return rl
        for value in node.values():
            found = _find_rate_limits(value)
            if found:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _find_rate_limits(item)
            if found:
                return found
    return None


def _looks_like_token_count(node: dict[str, Any]) -> bool:
    if node.get("type") == "token_count":
        return True
    payload = node.get("payload")
    if isinstance(payload, dict):
        if payload.get("type") == "token_count":
            return True
        msg = payload.get("msg")
        if isinstance(msg, dict) and msg.get("type") == "token_count":
            return True
        event = payload.get("event")
        if isinstance(event, dict) and event.get("type") == "token_count":
            return True
    return False


def latest_token_count_event(session_file: Path) -> dict[str, Any] | None:
    last_match: dict[str, Any] | None = None
    with session_file.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            rate_limits = _find_rate_limits(obj)
            if not rate_limits:
                continue
            if _looks_like_token_count(obj) or "token_count" in line:
                last_match = obj
    return last_match


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            return datetime.fromisoformat(raw[:-1] + "+00:00")
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def extract_reset_at(window: dict[str, Any]) -> str | None:
    for key in RESET_KEYS:
        value = window.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_window(window_dict: dict[str, Any] | None, gate_percent: float) -> WindowSnapshot:
    if not isinstance(window_dict, dict):
        return WindowSnapshot(None, None, None, None, True)
    used = to_float(window_dict.get("used_percent"))
    remaining = None if used is None else max(0.0, min(100.0, 100.0 - used))
    reset_at = extract_reset_at(window_dict)
    reset_dt = parse_iso_datetime(reset_at)
    hours_until = None
    if reset_dt is not None:
        delta = (reset_dt - now_utc()).total_seconds() / 3600.0
        hours_until = round(delta, 3)
    gated = True if remaining is None else remaining <= gate_percent
    return WindowSnapshot(used, remaining, reset_at, hours_until, gated)


def window_soft_gated(window: WindowSnapshot, soft_gate_percent: float) -> bool:
    if window.remaining_percent is None:
        return True
    return window.remaining_percent <= soft_gate_percent


def maybe_read_auth_identity(codex_home: Path) -> tuple[str | None, str | None]:
    candidates = [codex_home / "auth.json", codex_home / "config" / "auth.json"]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        jwt_email = extract_email_from_auth_tokens(data)
        if jwt_email:
            return jwt_email, f"auth-json-jwt:{path}"
        email = find_email_like(data)
        if email:
            return email, f"auth-json:{path}"
        account = find_account_label(data)
        if account:
            return account, f"auth-json:{path}"
    return None, None


def extract_email_from_auth_tokens(data: Any) -> str | None:
    if not isinstance(data, dict):
        return None
    tokens = data.get("tokens")
    if not isinstance(tokens, dict):
        return None
    for key in ("id_token", "access_token"):
        token = tokens.get(key)
        if not isinstance(token, str) or "." not in token:
            continue
        claims = decode_jwt_claims(token)
        if not claims:
            continue
        for claim_key in ("email", "preferred_username", "upn", "sub"):
            value = claims.get(claim_key)
            if isinstance(value, str) and value.strip():
                if claim_key == "sub":
                    # Keep sub as a last resort identity key when no email-like field exists.
                    return value.strip()
                match = EMAIL_RE.search(value)
                return match.group(0) if match else value.strip()
    return None


def decode_jwt_claims(token: str) -> dict[str, Any] | None:
    parts = token.split(".")
    if len(parts) < 2:
        return None
    payload_b64 = parts[1]
    padding = "=" * (-len(payload_b64) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload_b64 + padding)
        claims = json.loads(decoded.decode("utf-8"))
    except Exception:
        return None
    return claims if isinstance(claims, dict) else None


def find_email_like(node: Any) -> str | None:
    if isinstance(node, str):
        match = EMAIL_RE.search(node)
        return match.group(0) if match else None
    if isinstance(node, dict):
        for key in ("email", "username", "account", "user"):
            if key in node:
                found = find_email_like(node[key])
                if found:
                    return found
        for value in node.values():
            found = find_email_like(value)
            if found:
                return found
    elif isinstance(node, list):
        for item in node:
            found = find_email_like(item)
            if found:
                return found
    return None


def find_account_label(node: Any) -> str | None:
    if isinstance(node, str):
        text = node.strip()
        return text if text else None
    if isinstance(node, dict):
        for key in ("email", "username", "name", "account"):
            if key in node and isinstance(node[key], str) and node[key].strip():
                return node[key].strip()
        for value in node.values():
            found = find_account_label(value)
            if found:
                return found
    elif isinstance(node, list):
        for item in node:
            found = find_account_label(item)
            if found:
                return found
    return None


def build_profile_snapshot(
    alias: str,
    codex_home: Path,
    gate_5h: float,
    gate_weekly: float,
    soft_gate_5h: float,
    soft_gate_weekly: float,
    wait_max_hours: float,
) -> ProfileSnapshot:
    errors: list[str] = []
    session_file = newest_session_jsonl(codex_home)
    account_identity, account_source = maybe_read_auth_identity(codex_home)

    if session_file is None:
        errors.append("no_session_jsonl_found")
        five = WindowSnapshot(None, None, None, None, True)
        weekly = WindowSnapshot(None, None, None, None, True)
        return ProfileSnapshot(
            alias=alias,
            codex_home=str(codex_home),
            account_identity=account_identity,
            account_source=account_source,
            session_file=None,
            token_count_event_found=False,
            five_hour=five,
            weekly=weekly,
            recommended_action="wind_down",
            soft_concurrency_gated=True,
            wait_until_reset_candidate=False,
            wait_seconds=None,
            errors=errors,
        )

    event = None
    try:
        event = latest_token_count_event(session_file)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"session_read_error:{exc}")

    if event is None:
        errors.append("token_count_event_not_found")
        five = WindowSnapshot(None, None, None, None, True)
        weekly = WindowSnapshot(None, None, None, None, True)
        return ProfileSnapshot(
            alias=alias,
            codex_home=str(codex_home),
            account_identity=account_identity,
            account_source=account_source,
            session_file=str(session_file),
            token_count_event_found=False,
            five_hour=five,
            weekly=weekly,
            recommended_action="wind_down",
            soft_concurrency_gated=True,
            wait_until_reset_candidate=False,
            wait_seconds=None,
            errors=errors,
        )

    rate_limits = _find_rate_limits(event) or {}
    five = build_window(rate_limits.get("primary"), gate_5h)
    weekly = build_window(rate_limits.get("secondary"), gate_weekly)

    any_gated = five.gated or weekly.gated
    wait_candidate = False
    wait_seconds = None
    recommended_action = "continue"

    if any_gated:
        reset_candidates: list[float] = []
        if five.gated and five.reset_in_hours is not None and five.reset_in_hours >= 0:
            reset_candidates.append(five.reset_in_hours)
        if weekly.gated and weekly.reset_in_hours is not None and weekly.reset_in_hours >= 0:
            reset_candidates.append(weekly.reset_in_hours)
        if reset_candidates:
            soonest_hours = min(reset_candidates)
            if soonest_hours <= wait_max_hours:
                wait_candidate = True
                wait_seconds = max(0, int(soonest_hours * 3600))
                recommended_action = "wait_until_reset"
            else:
                recommended_action = "wind_down"
        else:
            recommended_action = "wind_down"

    soft_concurrency_gated = window_soft_gated(five, soft_gate_5h) or window_soft_gated(weekly, soft_gate_weekly)

    return ProfileSnapshot(
        alias=alias,
        codex_home=str(codex_home),
        account_identity=account_identity,
        account_source=account_source,
        session_file=str(session_file),
        token_count_event_found=True,
        five_hour=five,
        weekly=weekly,
        recommended_action=recommended_action,
        soft_concurrency_gated=soft_concurrency_gated,
        wait_until_reset_candidate=wait_candidate,
        wait_seconds=wait_seconds,
        errors=errors,
    )


def normalize_account_key(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip().lower()
    return text or None


def derive_profile_running_mode(profiles: list[ProfileSnapshot]) -> str:
    if len(profiles) <= 1:
        return "single-profile"
    identities = {normalize_account_key(p.account_identity) for p in profiles if normalize_account_key(p.account_identity)}
    if not identities:
        return "unknown"
    return "single-user" if len(identities) == 1 else "multiple-users"


def to_json_obj(profile: ProfileSnapshot) -> dict[str, Any]:
    def window_obj(w: WindowSnapshot) -> dict[str, Any]:
        return {
            "used_percent": w.used_percent,
            "remaining_percent": w.remaining_percent,
            "reset_at": w.reset_at,
            "reset_in_hours": w.reset_in_hours,
            "gated": w.gated,
        }

    return {
        "alias": profile.alias,
        "codex_home": profile.codex_home,
        "account_identity": profile.account_identity,
        "account_source": profile.account_source,
        "session_file": profile.session_file,
        "token_count_event_found": profile.token_count_event_found,
        "five_hour": window_obj(profile.five_hour),
        "weekly": window_obj(profile.weekly),
        "recommended_action": profile.recommended_action,
        "soft_concurrency_gated": profile.soft_concurrency_gated,
        "wait_until_reset_candidate": profile.wait_until_reset_candidate,
        "wait_seconds": profile.wait_seconds,
        "eligible_for_new_work": profile.recommended_action == "continue",
        "errors": profile.errors,
    }


def main() -> int:
    args = parse_args()
    try:
        profile_map = parse_profile_map(args.profile)
    except ValueError as exc:
        print(f"[codex-rate-snapshot] error: {exc}", file=sys.stderr)
        return 2

    profiles: list[ProfileSnapshot] = []
    for alias, raw_home in profile_map.items():
        codex_home = resolve_codex_home(raw_home)
        profiles.append(
            build_profile_snapshot(
                alias=alias,
                codex_home=codex_home,
                gate_5h=args.gate_5h_percent,
                gate_weekly=args.gate_weekly_percent,
                soft_gate_5h=args.soft_gate_5h_percent,
                soft_gate_weekly=args.soft_gate_weekly_percent,
                wait_max_hours=args.wait_max_hours,
            )
        )

    mode = derive_profile_running_mode(profiles)
    profiles_obj = {p.alias: to_json_obj(p) for p in profiles}
    eligible_profiles = [p.alias for p in profiles if p.recommended_action == "continue"]
    gated_profiles = [p.alias for p in profiles if p.recommended_action != "continue"]
    soft_concurrency_gated_profiles = [p.alias for p in profiles if p.soft_concurrency_gated]

    output = {
        "generated_at": now_utc().isoformat(),
        "gate_thresholds": {
            "five_hour_percent": args.gate_5h_percent,
            "weekly_percent": args.gate_weekly_percent,
            "wait_max_hours": args.wait_max_hours,
        },
        "soft_concurrency": {
            "five_hour_percent": args.soft_gate_5h_percent,
            "weekly_percent": args.soft_gate_weekly_percent,
            "max_active_workers_when_gated": args.soft_max_active_workers,
        },
        "profile_running_mode": mode,
        "eligible_profiles": eligible_profiles,
        "gated_profiles": gated_profiles,
        "soft_concurrency_gated_profiles": soft_concurrency_gated_profiles,
        "profiles": profiles_obj,
    }

    if args.json_pretty:
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        print(json.dumps(output, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
