#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/.sanity-logs"
mkdir -p "$LOG_DIR"

ORCH_PORT="${ORCH_PORT:-18010}"
UI_PORT="${UI_PORT:-13000}"

ORCH_LOG="$LOG_DIR/orchestration-dev.log"
UI_LOG="$LOG_DIR/control-ui-dev.log"
REPORT="$LOG_DIR/report.txt"

ORCH_PID=""
UI_PID=""

cleanup() {
  if [[ -n "$UI_PID" ]] && kill -0 "$UI_PID" 2>/dev/null; then
    kill "$UI_PID" 2>/dev/null || true
    wait "$UI_PID" 2>/dev/null || true
  fi
  if [[ -n "$ORCH_PID" ]] && kill -0 "$ORCH_PID" 2>/dev/null; then
    kill "$ORCH_PID" 2>/dev/null || true
    wait "$ORCH_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

wait_for_log() {
  local logfile="$1"
  local pattern="$2"
  local timeout_sec="$3"
  local elapsed=0

  while (( elapsed < timeout_sec )); do
    if grep -qE "$pattern" "$logfile" 2>/dev/null; then
      return 0
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done
  return 1
}

fail_with_logs() {
  local title="$1"
  local logfile="$2"
  {
    echo "[FAIL] $title"
    echo "Log: $logfile"
    echo "--- tail ---"
    tail -n 80 "$logfile" 2>/dev/null || true
    echo "------------"
  } | tee -a "$REPORT"
  exit 1
}

: > "$REPORT"
echo "StageCanvas dev sanity check" | tee -a "$REPORT"
echo "Root: $ROOT_DIR" | tee -a "$REPORT"
echo "Ports: orchestration=$ORCH_PORT ui=$UI_PORT" | tee -a "$REPORT"

run_step() {
  local step_label="$1"
  local logfile="$2"
  shift 2
  if ! "$@" >> "$logfile" 2>&1; then
    fail_with_logs "$step_label failed" "$logfile"
  fi
}

echo "[1/4] Ensure orchestration deps" | tee -a "$REPORT"
run_step "orchestration dependency install" "$ORCH_LOG" \
  bash -lc "cd \"$ROOT_DIR/orchestration-server\" && python -m pip install -e ."

echo "[2/4] Ensure control-ui deps" | tee -a "$REPORT"
run_step "control-ui dependency install" "$UI_LOG" \
  bash -lc "cd \"$ROOT_DIR/control-ui\" && npm install"

echo "[3/4] Start orchestration-server dev" | tee -a "$REPORT"
(
  cd "$ROOT_DIR/orchestration-server"
  uvicorn app.main:app --host 127.0.0.1 --port "$ORCH_PORT" --reload
) > "$ORCH_LOG" 2>&1 &
ORCH_PID=$!

if ! wait_for_log "$ORCH_LOG" "Uvicorn running on|Application startup complete" 25; then
  if ! kill -0 "$ORCH_PID" 2>/dev/null; then
    fail_with_logs "orchestration-server crashed during startup" "$ORCH_LOG"
  fi
  fail_with_logs "orchestration-server did not become ready within timeout" "$ORCH_LOG"
fi
echo "[PASS] orchestration-server ready" | tee -a "$REPORT"

echo "[4/4] Start control-ui dev" | tee -a "$REPORT"
(
  cd "$ROOT_DIR/control-ui"
  NEXT_PUBLIC_ORCHESTRATION_HTTP="http://127.0.0.1:$ORCH_PORT" \
  NEXT_PUBLIC_ORCHESTRATION_WS="ws://127.0.0.1:$ORCH_PORT/ws/operators" \
  npm run dev -- -p "$UI_PORT"
) > "$UI_LOG" 2>&1 &
UI_PID=$!

if ! wait_for_log "$UI_LOG" "Ready in|ready - started server|Local:" 35; then
  if ! kill -0 "$UI_PID" 2>/dev/null; then
    fail_with_logs "control-ui crashed during startup" "$UI_LOG"
  fi
  fail_with_logs "control-ui did not become ready within timeout" "$UI_LOG"
fi
echo "[PASS] control-ui ready" | tee -a "$REPORT"

echo "[PASS] dev sanity complete" | tee -a "$REPORT"
echo "Logs: $LOG_DIR" | tee -a "$REPORT"
