#!/usr/bin/env bash
set -Eeuo pipefail

IRODORI_API_URL="${IRODORI_API_URL:-http://127.0.0.1:8880}"
IRODORI_READY_TIMEOUT="${IRODORI_READY_TIMEOUT:-600}"
IRODORI_PID=""
WORKER_PID=""

cleanup() {
  local exit_code=$?
  trap - EXIT INT TERM
  if [[ -n "${WORKER_PID}" ]]; then
    kill "${WORKER_PID}" 2>/dev/null || true
  fi
  if [[ -n "${IRODORI_PID}" ]]; then
    kill "${IRODORI_PID}" 2>/dev/null || true
  fi
  wait 2>/dev/null || true
  exit "${exit_code}"
}

trap cleanup EXIT INT TERM

echo "[INFO] Starting Irodori TTS API"
python /app/server.py &
IRODORI_PID=$!

echo "[INFO] Waiting for Irodori TTS API"
started_at=$SECONDS
until curl --fail --silent --show-error "${IRODORI_API_URL}/v1/models" >/dev/null; do
  if ! kill -0 "${IRODORI_PID}" 2>/dev/null; then
    echo "[ERROR] Irodori TTS API exited before becoming ready" >&2
    wait "${IRODORI_PID}"
  fi
  if (( SECONDS - started_at >= IRODORI_READY_TIMEOUT )); then
    echo "[ERROR] Irodori TTS API did not become ready within ${IRODORI_READY_TIMEOUT}s" >&2
    exit 1
  fi
  sleep 2
done

echo "[INFO] Starting RunPod worker"
python /app/handler.py &
WORKER_PID=$!
wait "${WORKER_PID}"
