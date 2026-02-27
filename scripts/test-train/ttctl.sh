#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

RUNTIME_COORD="$REPO_ROOT/skills/runtime-coordinator/scripts/runtime_coordinator.py"
TRAIN_MANAGER="$REPO_ROOT/skills/test-train-manager/scripts/test_train_manager.py"

TT_MODE="${TT_MODE:-final-stage}"
TT_RUNTIME_PROFILE_ID="${TT_RUNTIME_PROFILE_ID:-default-web}"
TT_RUNTIME_ID="${TT_RUNTIME_ID:-rt-shared-$TT_RUNTIME_PROFILE_ID}"
TT_PIPELINE_CONFIG_PATH="${TT_PIPELINE_CONFIG_PATH:-$REPO_ROOT/reports/optimus-prime/config/TEST_TRAIN_PIPELINE.json}"

RUNTIME_HEALTH_PATH="$REPO_ROOT/reports/optimus-prime/runtime/RUNTIME_HEALTH.json"
RUNTIME_ACTION_LOG_PATH="$REPO_ROOT/reports/optimus-prime/runtime/RUNTIME_ACTION_LOG.jsonl"
RUNTIME_REPAIR_TASKS_PATH="$REPO_ROOT/reports/optimus-prime/runtime/RUNTIME_REPAIR_TASKS.json"
RUNTIME_LOCKS_DIR="$REPO_ROOT/reports/optimus-prime/runtime/locks"

run_runtime_action() {
  local action="$1"
  python3 "$RUNTIME_COORD" --input-json - --json-pretty <<JSON
{
  "repo_root": "$REPO_ROOT",
  "action": "$action",
  "test_train_mode": "$TT_MODE",
  "runtime_profile_id": "$TT_RUNTIME_PROFILE_ID",
  "runtime_id": "$TT_RUNTIME_ID",
  "test_train_pipeline_path": "$TT_PIPELINE_CONFIG_PATH",
  "runtime_health_path": "$RUNTIME_HEALTH_PATH",
  "runtime_action_log_path": "$RUNTIME_ACTION_LOG_PATH",
  "runtime_repair_tasks_path": "$RUNTIME_REPAIR_TASKS_PATH",
  "runtime_locks_dir": "$RUNTIME_LOCKS_DIR"
}
JSON
}

run_train_action() {
  local action="$1"
  python3 "$TRAIN_MANAGER" --input-json - --json-pretty <<JSON
{
  "repo_root": "$REPO_ROOT",
  "action": "$action",
  "test_train_mode": "$TT_MODE",
  "test_train_pipeline_path": "$TT_PIPELINE_CONFIG_PATH",
  "runtime_health_path": "$RUNTIME_HEALTH_PATH",
  "runtime_action_log_path": "$RUNTIME_ACTION_LOG_PATH",
  "runtime_repair_tasks_path": "$RUNTIME_REPAIR_TASKS_PATH",
  "runtime_locks_dir": "$RUNTIME_LOCKS_DIR",
  "runtime_profile_id": "$TT_RUNTIME_PROFILE_ID",
  "runtime_id": "$TT_RUNTIME_ID"
}
JSON
}

usage() {
  cat <<USAGE
Usage: $0 <bootstrap|start|health|deploy|stop|repair|start-wave|gate|flow>

Environment overrides:
  TT_MODE                 default: final-stage
  TT_RUNTIME_PROFILE_ID   default: default-web
  TT_RUNTIME_ID           default: rt-shared-<profile-id>
  TT_PIPELINE_CONFIG_PATH default: reports/optimus-prime/config/TEST_TRAIN_PIPELINE.json
USAGE
}

cmd="${1:-}"
case "$cmd" in
  bootstrap)
    run_runtime_action "bootstrap"
    ;;
  start)
    run_runtime_action "start"
    ;;
  health)
    run_runtime_action "health"
    ;;
  deploy)
    run_train_action "deploy_test_branch"
    ;;
  stop)
    run_runtime_action "stop"
    ;;
  repair)
    run_runtime_action "repair"
    ;;
  start-wave)
    run_train_action "start_new_test_wave"
    ;;
  gate)
    run_train_action "evaluate_promotion_gate"
    ;;
  flow)
    run_runtime_action "bootstrap"
    run_runtime_action "start"
    run_runtime_action "health"
    run_runtime_action "health"
    run_train_action "start_new_test_wave"
    run_train_action "deploy_test_branch"
    run_train_action "evaluate_promotion_gate"
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
