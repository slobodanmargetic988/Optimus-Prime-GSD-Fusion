#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [[ -n "${TT_DB_RESET_MIGRATE_SEED_CMD:-}" ]]; then
  bash -lc "$TT_DB_RESET_MIGRATE_SEED_CMD"
  exit 0
fi

steps=()
for candidate in \
  "$REPO_ROOT/scripts/db/reset.sh" \
  "$REPO_ROOT/scripts/db/migrate.sh" \
  "$REPO_ROOT/scripts/db/seed.sh" \
  "$REPO_ROOT/scripts/db-reset.sh" \
  "$REPO_ROOT/scripts/db-migrate.sh" \
  "$REPO_ROOT/scripts/db-seed.sh"
do
  if [[ -x "$candidate" ]]; then
    steps+=("$candidate")
  fi
done

if (( ${#steps[@]} == 0 )); then
  echo "db reset/migrate/seed no-op: no known db scripts found"
  exit 0
fi

for step in "${steps[@]}"; do
  "$step"
done

echo "db reset/migrate/seed completed"
