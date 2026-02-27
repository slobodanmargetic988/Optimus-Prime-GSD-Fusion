#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

from_commit="${TT_DB_FROM_COMMIT:-}"
to_commit="${TT_DB_TO_COMMIT:-}"

if [[ -z "$to_commit" ]]; then
  echo "TT_DB_TO_COMMIT is required" >&2
  exit 2
fi

requires_reset_seed=false
reason="no_db_impact_paths_changed"
confidence="medium"
signals=()

if [[ -z "$from_commit" ]]; then
  requires_reset_seed=true
  reason="from_commit_missing_conservative_reset_seed"
  confidence="high"
  signals+=("from_commit_missing")
else
  if ! git -C "$REPO_ROOT" rev-parse --verify "$from_commit" >/dev/null 2>&1; then
    requires_reset_seed=true
    reason="from_commit_unresolvable_conservative_reset_seed"
    confidence="high"
    signals+=("from_commit_unresolvable")
  else
    mapfile -t changed_paths < <(git -C "$REPO_ROOT" diff --name-only "$from_commit" "$to_commit")
    for path in "${changed_paths[@]}"; do
      case "$path" in
        *migrations/*|*migration*|*schema.prisma|*schema.sql|*seed*|*fixture*|*fixtures/*|*alembic/*|*prisma/migrations/*)
          signals+=("$path")
          ;;
      esac
    done
    if (( ${#signals[@]} > 0 )); then
      requires_reset_seed=true
      reason="db_impact_paths_changed"
      confidence="high"
    fi
  fi
fi

python3 - "$from_commit" "$to_commit" "$requires_reset_seed" "$reason" "$confidence" "${signals[@]}" <<'PY'
import json
import sys

from_commit = sys.argv[1] if sys.argv[1] else None
to_commit = sys.argv[2]
requires = sys.argv[3].lower() == "true"
reason = sys.argv[4]
confidence = sys.argv[5]
signals = sys.argv[6:]

payload = {
    "schema_version": "1.0",
    "requires_reset_seed": requires,
    "reason": reason,
    "from_commit": from_commit,
    "to_commit": to_commit,
    "signals": signals,
    "confidence": confidence,
}
print(json.dumps(payload, sort_keys=True))
PY
