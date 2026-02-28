#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ARTIFACT_PATH="$REPO_ROOT/reports/optimus-prime/planning/LANE_B_QUALITY_GATE.json"
CANARY_ROOT="${1:-${OP_CANARY_PROJECT_ROOT:-}}"

if [[ -z "$CANARY_ROOT" ]]; then
  echo "error: set OP_CANARY_PROJECT_ROOT or pass canary project root as first argument" >&2
  exit 1
fi

python3 -m scripts.quality.lane_b_quality_gate --repo-root "$REPO_ROOT" --canary-project-root "$CANARY_ROOT"
echo "lane_b_quality_gate_artifact=$ARTIFACT_PATH"
