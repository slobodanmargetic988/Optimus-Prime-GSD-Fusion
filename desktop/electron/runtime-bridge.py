#!/usr/bin/env python3
"""Local desktop bridge: typed JSON on stdin, never shell execution or model calls of its own."""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time


def tagged_processes(run_id: str) -> list[int]:
    marker = f"OP_DESKTOP_RUN_ID={run_id}"
    found = []
    if sys.platform.startswith("linux"):
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            try:
                if marker.encode() in (entry / "environ").read_bytes().split(b"\0"):
                    found.append(int(entry.name))
            except (OSError, PermissionError):
                continue
    else:
        # ps output remains private in this process and is never returned or logged.
        result = subprocess.run(["ps", "eww", "-axo", "pid=,command="], capture_output=True, text=True, timeout=10)
        for line in result.stdout.splitlines():
            values = line.strip().split(None, 1)
            if len(values) == 2 and values[0].isdigit() and marker in values[1].split():
                found.append(int(values[0]))
    return [pid for pid in found if pid != os.getpid()]


def stop_run(run_id: str, hard: bool = False) -> None:
    if len(run_id) != 36 or any(c not in "0123456789abcdef-" for c in run_id):
        raise ValueError("Invalid run identifier")
    for pid in tagged_processes(run_id):
        try:
            os.kill(pid, signal.SIGKILL if hard else signal.SIGTERM)
        except ProcessLookupError:
            pass


def main() -> int:
    os.environ["PATH"] = os.pathsep.join([str(Path.home() / ".local" / "bin"), str(Path.home() / ".cargo" / "bin"), "/usr/local/bin", "/opt/homebrew/bin", os.environ.get("PATH", "")])
    mode = sys.argv[1]
    data = json.load(sys.stdin)
    if mode == "probe":
        print(json.dumps({"python": sys.version.split()[0], "git": shutil.which("git"), "codex": shutil.which("codex"), "claude": shutil.which("claude"), "blackbox": shutil.which("blackbox"), "platform": sys.platform}))
        return 0
    if mode == "stop":
        stop_run(data["runId"], bool(data.get("hard")))
        return 0
    if mode != "run":
        raise ValueError("Unknown bridge operation")
    run_id = data["runId"]
    os.environ["OP_DESKTOP_RUN_ID"] = run_id
    environment = os.environ.copy()
    # Never accidentally charge an ambient API key when the user selected a subscription.
    for secret_name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY", "BLACKBOX_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        environment.pop(secret_name, None)
    for key, value in data.get("environment", {}).items():
        if key in {"OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY", "BLACKBOX_API_KEY", "OP_EXECUTOR_LOG_ROOT", "OP_THREAD_DISPATCH_SCRIPT", "OP_WORKSTATION_PREPARE_SCRIPT", "OP_PLANNER_PROVIDER", "OP_PLANNER_MODEL", "CODEX_HOME"} and isinstance(value, str):
            environment[key] = value
    process = subprocess.Popen([sys.executable, "-u", data["entrypoint"], "--input-json", "-"], cwd=data["payload"]["repo_root"], env=environment, stdin=subprocess.PIPE, text=True)
    def cancel(signum, frame):
        stop_run(run_id)
    signal.signal(signal.SIGTERM, cancel)
    signal.signal(signal.SIGINT, cancel)
    process.communicate(json.dumps(data["payload"]))
    # Detached workers must never outlive the desktop-owned run.
    stop_run(run_id)
    time.sleep(0.2)
    stop_run(run_id, hard=True)
    return process.returncode


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(json.dumps({"desktopError": str(exc)}), file=sys.stderr)
        sys.exit(1)
