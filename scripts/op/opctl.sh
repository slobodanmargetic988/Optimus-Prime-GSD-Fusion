#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <op-map-codebase|op-new-project|op-plan|op-initialize|op-build> [extra args]" >&2
  exit 2
fi

COMMAND="$1"
shift

python3 "$SCRIPT_DIR/opctl.py" \
  --command "$COMMAND" \
  --repo-root "$REPO_ROOT" \
  "$@"
