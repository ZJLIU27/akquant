#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/apps/akquant_platform/backend"
FRONTEND_DIR="$ROOT_DIR/apps/akquant_platform/frontend"

echo "=== AKQuant Platform Dev Mode ==="
echo "  Frontend: http://localhost:3000"
echo "  Backend:  http://localhost:8000"
echo ""

# Start backend in background
cd "$ROOT_DIR"
uv run uvicorn app.main:app --reload --app-dir "$BACKEND_DIR" &
BACKEND_PID=$!

# Start frontend
cd "$FRONTEND_DIR"
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi
npx vite --host &
FRONTEND_PID=$!

cleanup() {
    echo ""
    echo "Shutting down..."
    kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
    wait 2>/dev/null
}
trap cleanup EXIT INT TERM

wait
