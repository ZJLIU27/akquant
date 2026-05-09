#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/apps/akquant_platform/backend"
FRONTEND_DIR="$ROOT_DIR/apps/akquant_platform/frontend"

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

if ! command_exists uv; then
    echo "ERROR: uv not found. Install uv first, then run scripts/setup_macos.sh."
    exit 1
fi

if ! command_exists npm; then
    echo "ERROR: npm not found. Install Node.js first, then rerun this script."
    exit 1
fi

echo "=== AKQuant Platform Dev Mode ==="
echo "  Frontend: http://localhost:3000"
echo "  Backend:  http://localhost:8000"
echo ""

# Start backend in background
cd "$ROOT_DIR"
uv run python -m uvicorn app.main:app --reload --app-dir "$BACKEND_DIR" --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

# Start frontend
cd "$FRONTEND_DIR"
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    if [ -f "package-lock.json" ]; then
        npm ci
    else
        npm install
    fi
fi
npm run dev -- --host 0.0.0.0 &
FRONTEND_PID=$!

cleanup() {
    echo ""
    echo "Shutting down..."
    kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
    wait 2>/dev/null
}
trap cleanup EXIT INT TERM

wait
