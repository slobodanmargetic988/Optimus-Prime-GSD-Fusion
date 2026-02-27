#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

RUNTIME_HOST="${RUNTIME_HOST:-127.0.0.1}"
RUNTIME_PORT="${RUNTIME_PORT:-43173}"
RUNTIME_STATE_DIR="${RUNTIME_STATE_DIR:-$REPO_ROOT/reports/optimus-prime/runtime}"

PID_FILE="$RUNTIME_STATE_DIR/runtime.pid"
LOG_FILE="$RUNTIME_STATE_DIR/runtime.log"
BOOT_FILE="$RUNTIME_STATE_DIR/RUNTIME_BOOTSTRAP.json"

mkdir -p "$RUNTIME_STATE_DIR"

is_running() {
  local pid="$1"
  kill -0 "$pid" 2>/dev/null
}

if [[ -f "$PID_FILE" ]]; then
  existing_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "$existing_pid" ]] && is_running "$existing_pid"; then
    echo "runtime already running pid=$existing_pid"
    exit 0
  fi
  rm -f "$PID_FILE"
fi

RUNTIME_HOST="$RUNTIME_HOST" RUNTIME_PORT="$RUNTIME_PORT" RUNTIME_STATE_DIR="$RUNTIME_STATE_DIR" \
  python3 "$REPO_ROOT/scripts/runtime/mock_runtime_server.py" >>"$LOG_FILE" 2>&1 &
pid="$!"
echo "$pid" > "$PID_FILE"

for _ in $(seq 1 60); do
  if ! is_running "$pid"; then
    break
  fi
  if curl -fsS --max-time 2 "http://$RUNTIME_HOST:$RUNTIME_PORT/health" >/dev/null 2>&1; then
    started_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    cat > "$BOOT_FILE" <<JSON
{
  "started_at": "$started_at",
  "pid": $pid,
  "base_url": "http://$RUNTIME_HOST:$RUNTIME_PORT"
}
JSON
    echo "runtime started pid=$pid base_url=http://$RUNTIME_HOST:$RUNTIME_PORT"
    exit 0
  fi
  sleep 0.25
done

if is_running "$pid"; then
  kill "$pid" 2>/dev/null || true
  sleep 1
  kill -9 "$pid" 2>/dev/null || true
fi
rm -f "$PID_FILE"
echo "runtime failed to become healthy" >&2
exit 1
