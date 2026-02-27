#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RUNTIME_STATE_DIR="${RUNTIME_STATE_DIR:-$REPO_ROOT/reports/optimus-prime/runtime}"
UNHEALTHY_MARKER_PATH="$RUNTIME_STATE_DIR/FORCE_UNHEALTHY"

if [[ "${SIMULATE_HEAL_FAILURE:-0}" == "1" ]]; then
  echo "heal failure simulated" >&2
  exit 43
fi

mkdir -p "$RUNTIME_STATE_DIR"
rm -f "$UNHEALTHY_MARKER_PATH"

"$REPO_ROOT/scripts/runtime/start.sh"
if "$REPO_ROOT/scripts/runtime/health.sh"; then
  echo "runtime heal completed"
  exit 0
fi

"$REPO_ROOT/scripts/runtime/stop.sh"
"$REPO_ROOT/scripts/runtime/start.sh"
"$REPO_ROOT/scripts/runtime/health.sh"

echo "runtime heal completed after restart"
