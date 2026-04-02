#!/usr/bin/env python3
"""Shared BOSS model/reasoning normalization helpers."""

from __future__ import annotations

from typing import Any

DEFAULT_BOSS_MODEL = "gpt-5.3-codex"
DEFAULT_BOSS_REASONING_EFFORT = "xhigh"

KNOWN_GOOD_BOSS_MODELS = {
    "gpt-5.3-codex",
    "gpt-5.4",
    "gpt-5.4-mini",
    "gpt-5.4-codex",
    "gpt-5.4-codex-exp",
    "gpt-5.4-codex-experimental",
}

KNOWN_GOOD_BOSS_REASONING_EFFORTS = {
    "low",
    "medium",
    "high",
    "xhigh",
}


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def sanitize_boss_model(value: Any, *, default: str | None = DEFAULT_BOSS_MODEL) -> str | None:
    text = _as_text(value)
    if not text:
        return default
    normalized = text.lower()
    if normalized in KNOWN_GOOD_BOSS_MODELS:
        return normalized
    return default


def sanitize_boss_reasoning_effort(
    value: Any,
    *,
    default: str | None = DEFAULT_BOSS_REASONING_EFFORT,
) -> str | None:
    text = _as_text(value)
    if not text:
        return default
    normalized = text.lower()
    if normalized in KNOWN_GOOD_BOSS_REASONING_EFFORTS:
        return normalized
    return default
