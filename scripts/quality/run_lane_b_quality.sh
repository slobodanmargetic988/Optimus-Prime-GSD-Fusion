#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ARTIFACT_PATH="$REPO_ROOT/reports/optimus-prime/planning/LANE_B_QUALITY_GATE.json"

python3 -m scripts.quality.lane_b_quality_gate --repo-root "$REPO_ROOT"
echo "lane_b_quality_gate_artifact=$ARTIFACT_PATH"

