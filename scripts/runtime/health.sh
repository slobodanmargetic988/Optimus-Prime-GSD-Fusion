#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

RUNTIME_HOST="${RUNTIME_HOST:-127.0.0.1}"
RUNTIME_PORT="${RUNTIME_PORT:-43173}"
RUNTIME_STATE_DIR="${RUNTIME_STATE_DIR:-$REPO_ROOT/reports/optimus-prime/runtime}"
PID_FILE="$RUNTIME_STATE_DIR/runtime.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo "runtime pid file missing: $PID_FILE" >&2
  exit 1
fi

pid="$(cat "$PID_FILE" 2>/dev/null || true)"
if [[ -z "$pid" ]] || ! kill -0 "$pid" 2>/dev/null; then
  echo "runtime process is not running" >&2
  exit 1
fi

status_code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 "http://$RUNTIME_HOST:$RUNTIME_PORT/health" || true)"
if [[ "$status_code" != "200" ]]; then
  echo "runtime health endpoint failed status=$status_code" >&2
  exit 1
fi

echo "runtime healthy pid=$pid status=$status_code"
