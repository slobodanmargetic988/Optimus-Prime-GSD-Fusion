#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

TTCTL="$REPO_ROOT/scripts/test-train/ttctl.sh"
RUNTIME_DIR="$REPO_ROOT/reports/optimus-prime/runtime"

HEALTH_PATH="$RUNTIME_DIR/RUNTIME_HEALTH.json"
RUNTIME_ACTION_LOG_PATH="$RUNTIME_DIR/RUNTIME_ACTION_LOG.jsonl"
REPAIR_TASKS_PATH="$RUNTIME_DIR/RUNTIME_REPAIR_TASKS.json"
RUNTIME_REGISTRY_PATH="$REPO_ROOT/reports/optimus-prime/RUNTIME_REGISTRY.json"

STATE_PATH="$REPO_ROOT/reports/optimus-prime/TEST_TRAIN_STATE.json"
ATTEMPTS_PATH="$REPO_ROOT/reports/optimus-prime/TEST_TASK_ATTEMPTS.json"
WAVE_LOG_PATH="$REPO_ROOT/reports/optimus-prime/TEST_WAVE_LOG.jsonl"

BLOCKERS_PATH="$REPO_ROOT/reports/optimus-prime/BLOCKERS.jsonl"
BLOCKER_INDEX_PATH="$REPO_ROOT/reports/optimus-prime/BLOCKER_INDEX.json"
BLOCKER_ADAPTATION_PATH="$REPO_ROOT/reports/optimus-prime/BLOCKER_ADAPTATION_CANDIDATES.md"

DEPLOY_STATE_PATH="$RUNTIME_DIR/DEPLOY_STATE.json"
BOOT_STATE_PATH="$RUNTIME_DIR/RUNTIME_BOOTSTRAP.json"
RUNTIME_LOG_PATH="$RUNTIME_DIR/runtime.log"
RUNTIME_PID_PATH="$RUNTIME_DIR/runtime.pid"

ARCHIVE_DIR="$RUNTIME_DIR/drills/latest"
REPORT_PATH="$RUNTIME_DIR/DRILL_REPORT.md"
BACKUP_DIR="$(mktemp -d "$RUNTIME_DIR/.drill-backup.XXXXXX")"

mkdir -p "$RUNTIME_DIR"

FILES_TO_BACKUP=(
  "$HEALTH_PATH"
  "$RUNTIME_ACTION_LOG_PATH"
  "$REPAIR_TASKS_PATH"
  "$RUNTIME_REGISTRY_PATH"
  "$STATE_PATH"
  "$ATTEMPTS_PATH"
  "$WAVE_LOG_PATH"
  "$BLOCKERS_PATH"
  "$BLOCKER_INDEX_PATH"
  "$BLOCKER_ADAPTATION_PATH"
  "$DEPLOY_STATE_PATH"
  "$BOOT_STATE_PATH"
  "$RUNTIME_LOG_PATH"
  "$RUNTIME_PID_PATH"
)

timestamp() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

backup_key() {
  python3 - "$1" <<'PY'
import sys
print(sys.argv[1].replace("/", "__"))
PY
}

backup_file() {
  local path="$1"
  local key
  key="$(backup_key "$path")"
  if [[ -f "$path" ]]; then
    cp "$path" "$BACKUP_DIR/$key"
    echo "present" > "$BACKUP_DIR/$key.state"
  else
    echo "missing" > "$BACKUP_DIR/$key.state"
  fi
}

restore_file() {
  local path="$1"
  local key
  key="$(backup_key "$path")"
  local state
  state="$(cat "$BACKUP_DIR/$key.state")"
  if [[ "$state" == "present" ]]; then
    cp "$BACKUP_DIR/$key" "$path"
  else
    rm -f "$path"
  fi
}

restore_workspace() {
  set +e
  for path in "${FILES_TO_BACKUP[@]}"; do
    restore_file "$path"
  done
  rm -rf "$BACKUP_DIR"
}
trap restore_workspace EXIT

for path in "${FILES_TO_BACKUP[@]}"; do
  backup_file "$path"
done

json_get() {
  local path="$1"
  local key="$2"
  python3 - "$path" "$key" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
value = payload
for part in [p for p in sys.argv[2].split(".") if p]:
    if isinstance(value, dict):
        value = value.get(part)
    else:
        value = None
        break

if isinstance(value, (dict, list)):
    print(json.dumps(value, sort_keys=True))
elif value is None:
    print("")
else:
    print(value)
PY
}

set_planned_flow_pass() {
  python3 - "$STATE_PATH" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.exists():
    raise SystemExit(1)
payload = json.loads(path.read_text(encoding="utf-8"))
active = payload.get("active_wave")
if not isinstance(active, dict):
    active = {}
    payload["active_wave"] = active
active["planned_flow_pass_completed"] = True
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

complete_latest_repair_task() {
  python3 - "$REPAIR_TASKS_PATH" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.exists():
    raise SystemExit(0)
payload = json.loads(path.read_text(encoding="utf-8"))
tasks = payload.get("tasks")
if not isinstance(tasks, list) or not tasks:
    raise SystemExit(0)
tasks[-1]["status"] = "completed"
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

resolve_runtime_blockers() {
  python3 - "$BLOCKERS_PATH" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.exists():
    raise SystemExit(0)

rows = []
for line in path.read_text(encoding="utf-8").splitlines():
    text = line.strip()
    if not text:
        continue
    try:
        row = json.loads(text)
    except json.JSONDecodeError:
        continue
    if not isinstance(row, dict):
        continue
    category = str(row.get("category") or "").lower()
    code = str(row.get("blocker_code") or "").lower()
    if category in {"runtime", "test-train", "env", "infra"} or code == "runtime_repair_required":
        row["status"] = "resolved"
    rows.append(row)

path.write_text("".join(json.dumps(r, sort_keys=True) + "\\n" for r in rows), encoding="utf-8")
PY
}

reset_drill_state() {
  rm -f \
    "$RUNTIME_ACTION_LOG_PATH" \
    "$HEALTH_PATH" \
    "$REPAIR_TASKS_PATH" \
    "$RUNTIME_DIR/FORCE_UNHEALTHY" \
    "$BLOCKERS_PATH" \
    "$BLOCKER_INDEX_PATH" \
    "$BLOCKER_ADAPTATION_PATH" \
    "$STATE_PATH" \
    "$ATTEMPTS_PATH" \
    "$WAVE_LOG_PATH" \
    "$DEPLOY_STATE_PATH" \
    "$BOOT_STATE_PATH" \
    "$RUNTIME_LOG_PATH" \
    "$RUNTIME_PID_PATH"
}

assert_equals() {
  local actual="$1"
  local expected="$2"
  local label="$3"
  if [[ "$actual" != "$expected" ]]; then
    echo "assertion failed: $label (actual='$actual' expected='$expected')" >&2
    exit 1
  fi
}

assert_ge() {
  local actual="$1"
  local expected="$2"
  local label="$3"
  if (( actual < expected )); then
    echo "assertion failed: $label (actual=$actual expected>=$expected)" >&2
    exit 1
  fi
}

{
  echo "# Runtime Gate Drill Report"
  echo
  echo "Generated: $(timestamp)"
  echo
  echo "## Scenario 1: Healthy path (bootstrap -> start -> health x2 -> gate)"
} > "$REPORT_PATH"

reset_drill_state
"$TTCTL" stop >/dev/null || true

"$TTCTL" bootstrap >/dev/null
"$TTCTL" start >/dev/null
"$TTCTL" health >/dev/null
first_gate="$(json_get "$HEALTH_PATH" "gate_state")"
"$TTCTL" health >/dev/null
second_gate="$(json_get "$HEALTH_PATH" "gate_state")"
assert_equals "$first_gate" "degraded" "first health gate state"
assert_equals "$second_gate" "healthy" "second health gate state"

"$TTCTL" start-wave >/dev/null
set_planned_flow_pass
"$TTCTL" gate >/dev/null
eligible_after_healthy="$(json_get "$STATE_PATH" "promotion_eligibility.eligible")"
assert_equals "$eligible_after_healthy" "True" "promotion gate in healthy scenario"

{
  echo "- health pass #1 gate_state: $first_gate"
  echo "- health pass #2 gate_state: $second_gate"
  echo "- promotion eligible after healthy runtime: $eligible_after_healthy"
  echo
  echo "## Scenario 2: Unhealthy path (deploy fail -> heal fail -> repair delegated -> gate blocked)"
} >> "$REPORT_PATH"

"$TTCTL" stop >/dev/null || true

if SIMULATE_DEPLOY_FAILURE=1 SIMULATE_HEAL_FAILURE=1 "$TTCTL" deploy >/dev/null 2>&1; then
  echo "expected deploy failure scenario to fail" >&2
  exit 1
fi

repair_count="$(python3 - "$REPAIR_TASKS_PATH" <<'PY'
import json
import sys
from pathlib import Path
path = Path(sys.argv[1])
if not path.exists():
    print(0)
    raise SystemExit(0)
payload = json.loads(path.read_text(encoding="utf-8"))
tasks = payload.get("tasks")
print(len(tasks) if isinstance(tasks, list) else 0)
PY
)"
assert_ge "$repair_count" 1 "repair task count"

"$TTCTL" start-wave >/dev/null
set_planned_flow_pass
"$TTCTL" gate >/dev/null
blocked_gate="$(json_get "$STATE_PATH" "promotion_eligibility.eligible")"
blocked_state="$(json_get "$HEALTH_PATH" "gate_state")"
assert_equals "$blocked_gate" "False" "promotion gate in unhealthy scenario"

{
  echo "- repair tasks queued: $repair_count"
  echo "- runtime gate_state after failed deploy/heal: $blocked_state"
  echo "- promotion eligible after failed deploy/heal: $blocked_gate"
  echo
  echo "## Scenario 3: Recovery path (manual heal -> health x2 -> gate unblocked)"
} >> "$REPORT_PATH"

"$REPO_ROOT/scripts/runtime-heal.sh" >/dev/null
"$TTCTL" start >/dev/null
"$TTCTL" health >/dev/null
recover_pass1="$(json_get "$HEALTH_PATH" "gate_state")"
"$TTCTL" health >/dev/null
recover_pass2="$(json_get "$HEALTH_PATH" "gate_state")"
assert_equals "$recover_pass1" "degraded" "recovery health pass #1"
assert_equals "$recover_pass2" "healthy" "recovery health pass #2"

complete_latest_repair_task
resolve_runtime_blockers
"$TTCTL" start-wave >/dev/null
set_planned_flow_pass
"$TTCTL" gate >/dev/null
unblocked_gate="$(json_get "$STATE_PATH" "promotion_eligibility.eligible")"
assert_equals "$unblocked_gate" "True" "promotion gate in recovery scenario"

mkdir -p "$ARCHIVE_DIR"
cp "$HEALTH_PATH" "$ARCHIVE_DIR/RUNTIME_HEALTH.json"
cp "$RUNTIME_ACTION_LOG_PATH" "$ARCHIVE_DIR/RUNTIME_ACTION_LOG.jsonl"
cp "$REPAIR_TASKS_PATH" "$ARCHIVE_DIR/RUNTIME_REPAIR_TASKS.json"

{
  echo "- recovery health pass #1 gate_state: $recover_pass1"
  echo "- recovery health pass #2 gate_state: $recover_pass2"
  echo "- promotion eligible after recovery: $unblocked_gate"
  echo
  echo "## Artifacts"
  echo "- $ARCHIVE_DIR/RUNTIME_HEALTH.json"
  echo "- $ARCHIVE_DIR/RUNTIME_ACTION_LOG.jsonl"
  echo "- $ARCHIVE_DIR/RUNTIME_REPAIR_TASKS.json"
} >> "$REPORT_PATH"

echo "gate drills completed; report: $REPORT_PATH"
