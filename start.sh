#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
BACKEND_VENV_PYTHON="${BACKEND_VENV_PYTHON:-$HOME/.venvs/localVocalAgent/bin/python}"

if [[ ! -d "$FRONTEND_DIR" ]]; then
  echo "Error: frontend directory not found at $FRONTEND_DIR"
  exit 1
fi

if [[ -x "$BACKEND_VENV_PYTHON" ]]; then
  PYTHON_BIN="$BACKEND_VENV_PYTHON"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Error: Python binary not found ($PYTHON_BIN)"
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "Error: npm is not installed or not in PATH."
  exit 1
fi

is_port_busy() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"$port" -sTCP:LISTEN -n -P >/dev/null 2>&1
  else
    "$PYTHON_BIN" - "$port" <<'PY'
import socket
import sys
port = int(sys.argv[1])
s = socket.socket()
s.settimeout(0.2)
busy = s.connect_ex(("127.0.0.1", port)) == 0
s.close()
sys.exit(0 if busy else 1)
PY
  fi
}

kill_port_if_busy() {
  local port="$1"
  if ! is_port_busy "$port"; then
    return 0
  fi
  echo "Port $port is in use. Stopping existing process..."
  if command -v lsof >/dev/null 2>&1; then
    local pids
    pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN -n -P || true)"
    if [[ -n "$pids" ]]; then
      # shellcheck disable=SC2086
      kill $pids 2>/dev/null || true
    fi
  else
    echo "Warning: lsof not found; cannot auto-stop process on port $port"
  fi
}

cleanup() {
  local exit_code=$?
  trap - EXIT INT TERM
  if [[ -n "${BACKEND_PID:-}" || -n "${FRONTEND_PID:-}" ]]; then
    echo ""
    echo "Stopping services..."
    [[ -n "${BACKEND_PID:-}" ]] && kill "$BACKEND_PID" 2>/dev/null || true
    [[ -n "${FRONTEND_PID:-}" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
    wait 2>/dev/null || true
  fi
  exit "$exit_code"
}

trap cleanup EXIT INT TERM

kill_port_if_busy "$BACKEND_PORT"
kill_port_if_busy "$FRONTEND_PORT"

echo "Starting backend on http://$BACKEND_HOST:$BACKEND_PORT ..."
"$PYTHON_BIN" -m uvicorn app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" &
BACKEND_PID=$!

echo "Starting frontend on http://$FRONTEND_HOST:$FRONTEND_PORT ..."
(
  cd "$FRONTEND_DIR"
  npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" --strictPort
) &
FRONTEND_PID=$!

echo ""
echo "Services ready:"
echo "  Backend : http://$BACKEND_HOST:$BACKEND_PORT"
echo "  Frontend: http://$FRONTEND_HOST:$FRONTEND_PORT"
echo "Press Ctrl+C to stop both."

if [[ -n "${BACKEND_PID:-}" && -n "${FRONTEND_PID:-}" ]]; then
  wait -n "$BACKEND_PID" "$FRONTEND_PID"
elif [[ -n "${BACKEND_PID:-}" ]]; then
  wait "$BACKEND_PID"
elif [[ -n "${FRONTEND_PID:-}" ]]; then
  wait "$FRONTEND_PID"
fi
