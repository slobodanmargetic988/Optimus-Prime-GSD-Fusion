#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

RUNTIME_STATE_DIR="${RUNTIME_STATE_DIR:-$REPO_ROOT/reports/optimus-prime/runtime}"
PID_FILE="$RUNTIME_STATE_DIR/runtime.pid"
MARKER_FILE="$RUNTIME_STATE_DIR/FORCE_UNHEALTHY"

mkdir -p "$RUNTIME_STATE_DIR"

killed=0
if [[ -f "$PID_FILE" ]]; then
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    for _ in $(seq 1 20); do
      if ! kill -0 "$pid" 2>/dev/null; then
        break
      fi
      sleep 0.25
    done
    if kill -0 "$pid" 2>/dev/null; then
      kill -9 "$pid" 2>/dev/null || true
    fi
    killed=1
  fi
fi

rm -f "$PID_FILE" "$MARKER_FILE"

if [[ "$killed" == "1" ]]; then
  echo "runtime stopped"
else
  echo "runtime already stopped"
fi
