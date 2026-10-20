#!/usr/bin/env sh
set -eu
PORT="${PORT:-8080}"
export PYTHONPATH="${PYTHONPATH:-/app}"
exec python -m uvicorn finance_ops.serving:app --host 0.0.0.0 --port "${PORT}"
