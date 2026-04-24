#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
BACKEND_VENV_PYTHON="${BACKEND_VENV_PYTHON:-$HOME/.venvs/localVocalAgent/bin/python}"
OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5:7b}"
EMBEDDING_MODEL="${EMBEDDING_MODEL:-nomic-embed-text}"
AUTO_FIX_OLLAMA="${AUTO_FIX_OLLAMA:-1}"
AUTO_START_OLLAMA="${AUTO_START_OLLAMA:-1}"

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

if ! command -v curl >/dev/null 2>&1; then
  echo "Error: curl is not installed or not in PATH."
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

wait_for_ollama() {
  local retries="${1:-25}"
  local delay_s="${2:-1}"
  local url="${OLLAMA_BASE_URL%/}/api/tags"
  for ((i = 1; i <= retries; i++)); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$delay_s"
  done
  return 1
}

ensure_ollama_running() {
  if wait_for_ollama 1 0; then
    return 0
  fi

  if [[ "$AUTO_START_OLLAMA" != "1" ]]; then
    echo "Error: Ollama is not reachable at $OLLAMA_BASE_URL."
    echo "Start it manually (e.g. \`ollama serve\`) or set AUTO_START_OLLAMA=1."
    exit 1
  fi

  if ! command -v ollama >/dev/null 2>&1; then
    echo "Error: ollama CLI not found, cannot auto-start service."
    exit 1
  fi

  echo "Ollama not reachable. Starting ollama service..."
  ollama serve >/dev/null 2>&1 &
  OLLAMA_SERVE_PID=$!
  if ! wait_for_ollama 25 1; then
    echo "Error: Failed to start Ollama at $OLLAMA_BASE_URL."
    exit 1
  fi
}

ensure_ollama_model() {
  local model="$1"
  local tag_url="${OLLAMA_BASE_URL%/}/api/tags"
  local code
  code="$(curl -sS -o /tmp/ollama-tags.json -w "%{http_code}" "$tag_url" || true)"
  if [[ "$code" != "200" ]]; then
    echo "Error: unable to query Ollama model list at $tag_url (HTTP $code)"
    exit 1
  fi

  if "$PYTHON_BIN" - "$model" <<'PY'
import json
import sys

model = sys.argv[1]
with open("/tmp/ollama-tags.json", "r", encoding="utf-8") as fh:
    payload = json.load(fh)
names = {m.get("name", "") for m in payload.get("models", [])}
base = {name.split(":", 1)[0] for name in names if name}
ok = model in names or model in base
raise SystemExit(0 if ok else 1)
PY
  then
    return 0
  fi

  if [[ "$AUTO_FIX_OLLAMA" != "1" ]]; then
    echo "Error: required model '$model' is missing in Ollama."
    echo "Install it with: ollama pull $model"
    exit 1
  fi

  echo "Model '$model' missing. Pulling..."
  ollama pull "$model"
}

cleanup() {
  local exit_code=$?
  trap - EXIT INT TERM
  if [[ -n "${BACKEND_PID:-}" || -n "${FRONTEND_PID:-}" ]]; then
    echo ""
    echo "Stopping services..."
    [[ -n "${BACKEND_PID:-}" ]] && kill "$BACKEND_PID" 2>/dev/null || true
    [[ -n "${FRONTEND_PID:-}" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
    [[ -n "${OLLAMA_SERVE_PID:-}" ]] && kill "$OLLAMA_SERVE_PID" 2>/dev/null || true
    wait 2>/dev/null || true
  fi
  exit "$exit_code"
}

trap cleanup EXIT INT TERM

kill_port_if_busy "$BACKEND_PORT"
kill_port_if_busy "$FRONTEND_PORT"

ensure_ollama_running
ensure_ollama_model "$EMBEDDING_MODEL"
ensure_ollama_model "$OLLAMA_MODEL"

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
