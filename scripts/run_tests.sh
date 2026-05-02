#!/usr/bin/env bash
# Run backend tests from repo root (requires: pip install -r requirements-ci.txt -r requirements-dev.txt)
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
exec python3 -m pytest "$@"
