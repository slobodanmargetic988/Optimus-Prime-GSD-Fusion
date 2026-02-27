#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [[ -n "${TT_DB_RESET_MIGRATE_SEED_CMD:-}" ]]; then
  bash -lc "$TT_DB_RESET_MIGRATE_SEED_CMD"
  exit 0
fi

reset_cmd="$REPO_ROOT/scripts/db/reset.sh"
migrate_cmd="$REPO_ROOT/scripts/db/migrate.sh"
seed_cmd="$REPO_ROOT/scripts/db/seed.sh"

if [[ ! -x "$reset_cmd" || ! -x "$migrate_cmd" || ! -x "$seed_cmd" ]]; then
  echo "db reset/migrate/seed no-op: canonical scripts missing (scripts/db/{reset,migrate,seed}.sh)"
  exit 0
fi

"$reset_cmd"
"$migrate_cmd"
"$seed_cmd"

echo "db reset/migrate/seed completed"
