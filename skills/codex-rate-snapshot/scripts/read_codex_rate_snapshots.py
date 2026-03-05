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
AUTH_SCAN_TAIL_LINES = 250

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
    rate_limits_source: str | None
    rate_limits_event_at: str | None
    rate_snapshot_age_minutes: float | None
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
    parser.add_argument("--max-session-files", type=int, default=20)
    parser.add_argument("--max-snapshot-age-hours", type=float, default=24.0)
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
    files = recent_session_jsonl(codex_home, max_files=1)
    return files[0] if files else None


def recent_session_jsonl(codex_home: Path, max_files: int) -> list[Path]:
    sessions_root = codex_home / "sessions"
    if not sessions_root.exists():
        return []
    candidates = [p for p in sessions_root.rglob("*.jsonl") if p.is_file()]
    if not candidates:
        return []
    # Select by last edit time (mtime), not creation time.
    def _mtime_key(path: Path) -> tuple[int, int, str]:
        stat = path.stat()
        return int(stat.st_mtime_ns), int(stat.st_size), str(path)

    sorted_candidates = sorted(candidates, key=_mtime_key, reverse=True)
    if max_files <= 0:
        return sorted_candidates
    return sorted_candidates[:max_files]


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
            if _looks_like_token_count(obj) or "token_count" in line:
                last_match = obj
    return last_match


def event_timestamp_utc(event: dict[str, Any]) -> datetime | None:
    raw_ts = event.get("timestamp")
    if isinstance(raw_ts, str):
        return parse_iso_datetime(raw_ts)
    return None


def latest_token_count_event_with_rate_limits(session_file: Path) -> tuple[dict[str, Any] | None, datetime | None]:
    latest_with_limits: dict[str, Any] | None = None
    latest_ts: datetime | None = None
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
            if not (_looks_like_token_count(obj) or "token_count" in line):
                continue
            rate_limits = _find_rate_limits(obj)
            if not isinstance(rate_limits, dict):
                continue
            ts = event_timestamp_utc(obj)
            if latest_with_limits is None:
                latest_with_limits = obj
                latest_ts = ts
                continue
            if ts is None:
                continue
            if latest_ts is None or ts >= latest_ts:
                latest_with_limits = obj
                latest_ts = ts
    return latest_with_limits, latest_ts


def latest_session_auth_state(session_file: Path) -> tuple[str | None, bool]:
    try:
        lines = session_file.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return None, False

    # Hard-gate auth detection is scoped to recent structured event messages.
    # Avoid scanning raw text across tool outputs, which can include copied strings
    # like "refresh_token_reused" without representing an actual auth failure.
    latest_error_code: str | None = None
    latest_error_ts: datetime | None = None
    latest_recovery_ts: datetime | None = None

    for line in reversed(lines[-AUTH_SCAN_TAIL_LINES:]):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        if obj.get("type") != "event_msg":
            continue
        payload = obj.get("payload")
        if not isinstance(payload, dict):
            continue
        event_ts = event_timestamp_utc(obj)

        # Strong auth-recovery signal: successful token_count with usable rate_limits.
        if payload.get("type") == "token_count":
            if _find_rate_limits(obj):
                if event_ts is not None and (latest_recovery_ts is None or event_ts > latest_recovery_ts):
                    latest_recovery_ts = event_ts
            continue

        text_parts: list[str] = []
        for key in ("text", "message", "error"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                text_parts.append(value.strip().lower())
        excerpt = "\n".join(text_parts) if text_parts else ""
        if excerpt:
            if "refresh_token_reused" in excerpt and ("unauthorized" in excerpt or "401" in excerpt):
                latest_error_code = "refresh_token_reused"
                if event_ts is not None and (latest_error_ts is None or event_ts > latest_error_ts):
                    latest_error_ts = event_ts
                continue
            if "invalid_grant" in excerpt:
                latest_error_code = "invalid_grant"
                if event_ts is not None and (latest_error_ts is None or event_ts > latest_error_ts):
                    latest_error_ts = event_ts
                continue

        # Secondary recovery signal: regular assistant/system message emitted after failure.
        # Keep this permissive for resilience in logs where token_count may be sparse.
        if payload.get("type") in {"assistant_message", "system_message"}:
            if event_ts is not None and (latest_recovery_ts is None or event_ts > latest_recovery_ts):
                latest_recovery_ts = event_ts
            continue

    if latest_error_code is None:
        return None, False
    if latest_error_ts is None or latest_recovery_ts is None:
        return latest_error_code, False
    return latest_error_code, latest_recovery_ts > latest_error_ts


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


def _parse_unix_timestamp(raw: int | float) -> datetime | None:
    # Support both seconds and milliseconds epoch values.
    seconds = float(raw)
    if seconds > 10_000_000_000:
        seconds /= 1000.0
    try:
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def normalize_reset_at(value: Any) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        # Accept ISO strings directly.
        dt = parse_iso_datetime(text)
        if dt is not None:
            return dt.astimezone(timezone.utc).isoformat()
        # Accept numeric strings as unix timestamps.
        try:
            numeric = float(text)
        except ValueError:
            return None
        dt = _parse_unix_timestamp(numeric)
        return dt.isoformat() if dt is not None else None
    if isinstance(value, (int, float)):
        dt = _parse_unix_timestamp(value)
        return dt.isoformat() if dt is not None else None
    return None


def extract_reset_at(window: dict[str, Any]) -> str | None:
    for key in RESET_KEYS:
        normalized = normalize_reset_at(window.get(key))
        if normalized is not None:
            return normalized
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
    current = now_utc()
    if reset_dt is not None:
        delta = (reset_dt - current).total_seconds() / 3600.0
        # If the reset moment has passed, treat window usage as refreshed.
        if delta <= 0:
            used = 0.0
            remaining = 100.0
            hours_until = 0.0
        else:
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


def maybe_read_auth_json(codex_home: Path) -> tuple[dict[str, Any] | None, Path | None]:
    candidates = [codex_home / "auth.json", codex_home / "config" / "auth.json"]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict):
            return data, path
    return None, None


def token_expiry_from_auth(codex_home: Path) -> tuple[datetime | None, str | None]:
    data, path = maybe_read_auth_json(codex_home)
    if not isinstance(data, dict):
        return None, None
    tokens = data.get("tokens")
    if not isinstance(tokens, dict):
        return None, None
    token = tokens.get("access_token")
    if not isinstance(token, str) or "." not in token:
        return None, None
    claims = decode_jwt_claims(token)
    if not isinstance(claims, dict):
        return None, None
    exp = claims.get("exp")
    if not isinstance(exp, (int, float)):
        return None, None
    dt = _parse_unix_timestamp(exp)
    if dt is None:
        return None, None
    return dt, (str(path) if path is not None else None)


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
    max_session_files: int = 20,
    max_snapshot_age_hours: float = 24.0,
) -> ProfileSnapshot:
    errors: list[str] = []
    session_file = newest_session_jsonl(codex_home)
    session_files = recent_session_jsonl(codex_home, max_session_files)
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
            rate_limits_source=None,
            rate_limits_event_at=None,
            rate_snapshot_age_minutes=None,
            token_count_event_found=False,
            five_hour=five,
            weekly=weekly,
            recommended_action="wind_down",
            soft_concurrency_gated=True,
            wait_until_reset_candidate=False,
            wait_seconds=None,
            errors=errors,
        )

    auth_error, auth_error_resolved = latest_session_auth_state(session_file)
    if auth_error:
        if auth_error_resolved:
            errors.append(f"{auth_error}_resolved")
        else:
            errors.append(auth_error)
    event = None
    event_with_rate_limits = None
    rate_limits_source_file: Path | None = None
    rate_limits_event_dt: datetime | None = None
    try:
        event = latest_token_count_event(session_file)
        for candidate in session_files:
            found_event, found_ts = latest_token_count_event_with_rate_limits(candidate)
            if found_event is None:
                continue
            if event_with_rate_limits is None:
                event_with_rate_limits = found_event
                rate_limits_source_file = candidate
                rate_limits_event_dt = found_ts
                continue
            current_ts = rate_limits_event_dt
            if current_ts is None:
                event_with_rate_limits = found_event
                rate_limits_source_file = candidate
                rate_limits_event_dt = found_ts
                continue
            if found_ts is not None and found_ts >= current_ts:
                event_with_rate_limits = found_event
                rate_limits_source_file = candidate
                rate_limits_event_dt = found_ts
    except Exception as exc:  # noqa: BLE001
        errors.append(f"session_read_error:{exc}")

    if auth_error and not auth_error_resolved:
        five = WindowSnapshot(None, None, None, None, True)
        weekly = WindowSnapshot(None, None, None, None, True)
        return ProfileSnapshot(
            alias=alias,
            codex_home=str(codex_home),
            account_identity=account_identity,
            account_source=account_source,
            session_file=str(session_file),
            rate_limits_source=None,
            rate_limits_event_at=None,
            rate_snapshot_age_minutes=None,
            token_count_event_found=event is not None,
            five_hour=five,
            weekly=weekly,
            recommended_action="wind_down",
            soft_concurrency_gated=True,
            wait_until_reset_candidate=False,
            wait_seconds=None,
            errors=errors,
        )

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
            rate_limits_source=None,
            rate_limits_event_at=None,
            rate_snapshot_age_minutes=None,
            token_count_event_found=False,
            five_hour=five,
            weekly=weekly,
            recommended_action="continue",
            soft_concurrency_gated=False,
            wait_until_reset_candidate=False,
            wait_seconds=None,
            errors=errors,
        )

    access_expiry_dt, access_expiry_source = token_expiry_from_auth(codex_home)
    if access_expiry_dt is not None and access_expiry_dt <= now_utc():
        # If newest run has no usable rate-limits and access token is already expired,
        # treat profile auth as unhealthy for dispatch.
        if _find_rate_limits(event) is None:
            errors.append("auth_access_token_expired")
            if access_expiry_source:
                errors.append(f"auth_access_token_source:{access_expiry_source}")
            five = WindowSnapshot(None, None, None, None, True)
            weekly = WindowSnapshot(None, None, None, None, True)
            return ProfileSnapshot(
                alias=alias,
                codex_home=str(codex_home),
                account_identity=account_identity,
                account_source=account_source,
                session_file=str(session_file),
                rate_limits_source=None,
                rate_limits_event_at=None,
                rate_snapshot_age_minutes=None,
                token_count_event_found=True,
                five_hour=five,
                weekly=weekly,
                recommended_action="wind_down",
                soft_concurrency_gated=True,
                wait_until_reset_candidate=False,
                wait_seconds=None,
                errors=errors,
            )

    snapshot_event = event_with_rate_limits if event_with_rate_limits is not None else event
    if event_with_rate_limits is None:
        errors.append("rate_limits_not_found_in_recent_sessions")
    elif rate_limits_source_file is not None and rate_limits_source_file != session_file:
        errors.append("rate_limits_fallback_session_used")

    rate_limits = _find_rate_limits(snapshot_event) or {}
    five = build_window(rate_limits.get("primary"), gate_5h)
    weekly = build_window(rate_limits.get("secondary"), gate_weekly)
    event_ts = rate_limits_event_dt or event_timestamp_utc(snapshot_event)
    snapshot_age_minutes = None
    if event_ts is not None:
        snapshot_age_minutes = round((now_utc() - event_ts).total_seconds() / 60.0, 2)

    if five.remaining_percent is None or weekly.remaining_percent is None:
        errors.append("rate_limits_missing")
        return ProfileSnapshot(
            alias=alias,
            codex_home=str(codex_home),
            account_identity=account_identity,
            account_source=account_source,
            session_file=str(rate_limits_source_file or session_file),
            rate_limits_source="token_count_event",
            rate_limits_event_at=event_ts.isoformat() if event_ts is not None else None,
            rate_snapshot_age_minutes=snapshot_age_minutes,
            token_count_event_found=True,
            five_hour=five,
            weekly=weekly,
            recommended_action="continue",
            soft_concurrency_gated=False,
            wait_until_reset_candidate=False,
            wait_seconds=None,
            errors=errors,
        )

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
    if snapshot_age_minutes is not None and snapshot_age_minutes > max_snapshot_age_hours * 60.0:
        errors.append("rate_limits_snapshot_stale")
        recommended_action = "wind_down"

    soft_concurrency_gated = window_soft_gated(five, soft_gate_5h) or window_soft_gated(weekly, soft_gate_weekly)

    return ProfileSnapshot(
        alias=alias,
        codex_home=str(codex_home),
        account_identity=account_identity,
        account_source=account_source,
        session_file=str(rate_limits_source_file or session_file),
        rate_limits_source="token_count_event",
        rate_limits_event_at=event_ts.isoformat() if event_ts is not None else None,
        rate_snapshot_age_minutes=snapshot_age_minutes,
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
        "rate_limits_source": profile.rate_limits_source,
        "rate_limits_event_at": profile.rate_limits_event_at,
        "rate_snapshot_age_minutes": profile.rate_snapshot_age_minutes,
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
                max_session_files=args.max_session_files,
                max_snapshot_age_hours=args.max_snapshot_age_hours,
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
            "max_session_files": args.max_session_files,
            "max_snapshot_age_hours": args.max_snapshot_age_hours,
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
