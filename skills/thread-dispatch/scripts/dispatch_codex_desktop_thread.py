#!/usr/bin/env python3
"""Create a visible Codex Desktop thread by UI scripting (macOS)."""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path


APPLESCRIPT = r'''
on run argv
  if (count of argv) is less than 1 then
    error "missing_prompt_argument"
  end if
  set promptText to item 1 of argv
  set openDelayMs to item 2 of argv
  set pasteDelayMs to item 3 of argv
  set sendDelayMs to item 4 of argv
  set shouldSend to item 5 of argv

  tell application "Codex" to activate
  delay ((openDelayMs as integer) / 1000.0)

  tell application "System Events"
    if not (exists process "Codex") then
      error "codex_process_not_found"
    end if
    tell process "Codex"
      keystroke "n" using {command down}
      delay ((pasteDelayMs as integer) / 1000.0)
      set the clipboard to promptText
      keystroke "v" using {command down}
      if shouldSend is "1" then
        delay ((sendDelayMs as integer) / 1000.0)
        key code 36
      end if
    end tell
  end tell
end run
'''


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Open a visible Codex Desktop thread, paste prompt, and optionally send it."
        )
    )
    parser.add_argument("--prompt", help="Prompt text.")
    parser.add_argument("--prompt-file", help="Path to UTF-8 prompt file.")
    parser.add_argument(
        "--no-send",
        action="store_true",
        help="Paste prompt but do not press Enter.",
    )
    parser.add_argument(
        "--open-delay",
        type=float,
        default=0.45,
        help="Seconds to wait after activating Codex app.",
    )
    parser.add_argument(
        "--paste-delay",
        type=float,
        default=0.25,
        help="Seconds to wait after Cmd+N before paste.",
    )
    parser.add_argument(
        "--send-delay",
        type=float,
        default=0.10,
        help="Seconds to wait between paste and Enter.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned osascript command and exit.",
    )
    return parser.parse_args()


def load_prompt(args: argparse.Namespace) -> str:
    if bool(args.prompt) == bool(args.prompt_file):
        raise ValueError("provide exactly one of --prompt or --prompt-file")
    if args.prompt:
        return args.prompt.strip()
    path = Path(args.prompt_file).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"prompt_file_not_found:{path}")
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise ValueError("prompt_file_empty")
    return value


def main() -> int:
    args = parse_args()
    try:
        prompt = load_prompt(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    send_flag = "0" if args.no_send else "1"
    open_delay_ms = max(0, int(round(args.open_delay * 1000)))
    paste_delay_ms = max(0, int(round(args.paste_delay * 1000)))
    send_delay_ms = max(0, int(round(args.send_delay * 1000)))
    cmd = [
        "osascript",
        "-e",
        APPLESCRIPT,
        prompt,
        str(open_delay_ms),
        str(paste_delay_ms),
        str(send_delay_ms),
        send_flag,
    ]

    if args.dry_run:
        print(" ".join(shlex.quote(x) for x in cmd))
        return 0

    try:
        completed = subprocess.run(cmd, check=False)  # noqa: S603
    except FileNotFoundError:
        print("error: osascript_not_found (macOS required)", file=sys.stderr)
        return 2
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
