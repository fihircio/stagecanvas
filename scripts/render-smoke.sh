#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/.sanity-logs/render-smoke"
mkdir -p "$LOG_DIR"

ORCH_PORT="${ORCH_PORT:-19010}"
DIAG_FILE="$LOG_DIR/diagnostics.jsonl"
ORCH_LOG="$LOG_DIR/orchestration.log"
NODE_LOG="$LOG_DIR/render-node.log"
REPORT="$LOG_DIR/report.txt"

ORCH_PID=""

cleanup() {
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
    if rg -q "$pattern" "$logfile" 2>/dev/null; then
      return 0
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done
  return 1
}

: > "$REPORT"
: > "$ORCH_LOG"
: > "$NODE_LOG"
rm -f "$DIAG_FILE"

echo "Render-node smoke check" | tee -a "$REPORT"
echo "Root: $ROOT_DIR" | tee -a "$REPORT"
echo "Orchestration port: $ORCH_PORT" | tee -a "$REPORT"

echo "[1/5] Ensure orchestration deps" | tee -a "$REPORT"
(
  cd "$ROOT_DIR/orchestration-server"
  python -m pip install -e . --no-deps --ignore-installed
) >> "$ORCH_LOG" 2>&1

echo "[2/5] Ensure render-node deps" | tee -a "$REPORT"
(
  cd "$ROOT_DIR/render-node"
  python -m pip install -e . --no-deps --ignore-installed
) >> "$NODE_LOG" 2>&1

echo "[3/5] Start orchestration server" | tee -a "$REPORT"
(
  cd "$ROOT_DIR/orchestration-server"
  uvicorn app.main:app --host 127.0.0.1 --port "$ORCH_PORT" --reload
) > "$ORCH_LOG" 2>&1 &
ORCH_PID=$!

if ! wait_for_log "$ORCH_LOG" "Uvicorn running on|Application startup complete" 30; then
  echo "[FAIL] orchestration did not become ready" | tee -a "$REPORT"
  tail -n 80 "$ORCH_LOG" | tee -a "$REPORT"
  exit 1
fi

echo "[4/5] Run bounded render-node session" | tee -a "$REPORT"
(
  cd "$ROOT_DIR/render-node"
  stagecanvas-render-node \
    --base-url "http://127.0.0.1:$ORCH_PORT" \
    --node-id "smoke-node-1" \
    --label "Smoke Node 1" \
    --max-runtime-sec 6 \
    --log-state-every-sec 0.5 \
    --diagnostics-sample-every 2 \
    --diagnostics-file "$DIAG_FILE"
) >> "$NODE_LOG" 2>&1

echo "[5/5] Validate diagnostics output" | tee -a "$REPORT"
if [[ ! -s "$DIAG_FILE" ]]; then
  echo "[FAIL] diagnostics file is empty: $DIAG_FILE" | tee -a "$REPORT"
  tail -n 80 "$NODE_LOG" | tee -a "$REPORT"
  exit 1
fi

if ! rg -q '"node_id":"smoke-node-1"' "$DIAG_FILE"; then
  echo "[FAIL] expected node_id not found in diagnostics" | tee -a "$REPORT"
  tail -n 80 "$DIAG_FILE" | tee -a "$REPORT"
  exit 1
fi

echo "[PASS] render-node smoke check complete" | tee -a "$REPORT"
echo "Logs: $LOG_DIR" | tee -a "$REPORT"
