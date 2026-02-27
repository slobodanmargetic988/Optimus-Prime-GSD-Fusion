#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RUNTIME_STATE_DIR="${RUNTIME_STATE_DIR:-$REPO_ROOT/reports/optimus-prime/runtime}"
DEPLOY_STATE_PATH="$RUNTIME_STATE_DIR/DEPLOY_STATE.json"
UNHEALTHY_MARKER_PATH="$RUNTIME_STATE_DIR/FORCE_UNHEALTHY"

mkdir -p "$RUNTIME_STATE_DIR"

if [[ "${SIMULATE_DEPLOY_FAILURE:-0}" == "1" ]]; then
  echo "deploy failure simulated" >&2
  exit 42
fi

"$REPO_ROOT/scripts/runtime/start.sh"
rm -f "$UNHEALTHY_MARKER_PATH"
"$REPO_ROOT/scripts/runtime/health.sh"

branch="$(git -C "$REPO_ROOT" branch --show-current 2>/dev/null || true)"
commit="$(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || true)"
deployed_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

cat > "$DEPLOY_STATE_PATH" <<JSON
{
  "deployed_at": "$deployed_at",
  "branch": "${branch:-unknown}",
  "commit": "${commit:-unknown}",
  "status": "deployed"
}
JSON

if [[ "${SIMULATE_UNHEALTHY_AFTER_DEPLOY:-0}" == "1" ]]; then
  touch "$UNHEALTHY_MARKER_PATH"
fi

echo "deploy complete branch=${branch:-unknown} commit=${commit:-unknown}"
