#!/usr/bin/env bash
# Starts the SaaS backend (FastAPI/uvicorn on :8000) and frontend (Vite on
# :5173) together, and stops both on Ctrl-C. Run from anywhere:
#   saas/dev.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

command -v uv >/dev/null || { echo "uv is required (https://docs.astral.sh/uv/) — install it first." >&2; exit 1; }
command -v npm >/dev/null || { echo "npm is required — install Node.js first." >&2; exit 1; }

echo "==> Syncing backend dependencies"
(cd "$BACKEND_DIR" && uv sync)

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "==> Installing frontend dependencies (first run)"
  (cd "$FRONTEND_DIR" && npm install)
fi

if [ ! -f "$BACKEND_DIR/strix_saas.db" ]; then
  echo "==> Seeding demo data"
  (cd "$BACKEND_DIR" && uv run python -m app.seed)
fi

PIDS=()
cleanup() {
  echo ""
  echo "==> Stopping..."
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "==> Starting backend  → http://127.0.0.1:8000"
(cd "$BACKEND_DIR" && uv run uvicorn app.main:app --reload --port 8000) &
PIDS+=($!)

echo "==> Starting frontend → http://localhost:5173"
(cd "$FRONTEND_DIR" && npm run dev) &
PIDS+=($!)

echo ""
echo "Both are starting. Open http://localhost:5173 (use 'localhost', not 127.0.0.1)."
echo "Press Ctrl-C to stop both."
echo ""

wait
