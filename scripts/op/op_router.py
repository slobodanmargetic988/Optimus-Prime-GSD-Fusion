#!/usr/bin/env python3
"""Normalize OP command aliases and route to canonical command names."""

from __future__ import annotations

from dataclasses import dataclass


SUPPORTED_COMMANDS = {
    "op-map-codebase",
    "op-new-project",
    "op-plan",
    "op-initialize",
    "op-build",
    "op-health",
    "op-status",
    "op-resume",
}

ALIASES = {
    "op-map-codebase": "op-map-codebase",
    "map-codebase": "op-map-codebase",
    "op-new-project": "op-new-project",
    "new-project": "op-new-project",
    "op-plan": "op-plan",
    "plan": "op-plan",
    "op-initialize": "op-initialize",
    "initialize": "op-initialize",
    "op-build": "op-build",
    "build": "op-build",
    "op-health": "op-health",
    "health": "op-health",
    "op-status": "op-status",
    "status": "op-status",
    "op-resume": "op-resume",
    "resume": "op-resume",
}


@dataclass(frozen=True)
class NormalizedCommand:
    raw: str
    canonical: str


def normalize_command(raw_command: str) -> NormalizedCommand:
    text = (raw_command or "").strip().lower()
    if not text:
        raise ValueError("command is required")

    # Accept /op-*, $op-*, and bare op-*.
    while text.startswith("/") or text.startswith("$"):
        text = text[1:]

    canonical = ALIASES.get(text)
    if canonical is None:
        raise ValueError(
            "unsupported command; expected one of: "
            + ", ".join(sorted(SUPPORTED_COMMANDS))
        )
    return NormalizedCommand(raw=raw_command, canonical=canonical)
