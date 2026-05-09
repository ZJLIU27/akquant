#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/apps/akquant_platform/backend"
FRONTEND_DIR="$ROOT_DIR/apps/akquant_platform/frontend"

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

missing=0
for tool in uv cargo npm; do
    if ! command_exists "$tool"; then
        echo "ERROR: $tool not found on PATH."
        missing=1
    fi
done

if [ "$missing" -ne 0 ]; then
    cat <<'EOF'

Install prerequisites on macOS, then rerun:
  xcode-select --install
  brew install uv rust node

If you do not use Homebrew, install equivalent uv, Rust, and Node.js toolchains.
EOF
    exit 1
fi

echo "=== AKQuant macOS setup ==="

cd "$ROOT_DIR"
echo "Syncing Python/Rust project dependencies..."
uv sync --extra dev

echo "Installing platform backend dependencies..."
uv pip install -r "$BACKEND_DIR/requirements.txt"

echo "Building local Rust Python extension..."
uv run maturin develop

cd "$FRONTEND_DIR"
echo "Installing frontend dependencies..."
if [ -f "package-lock.json" ]; then
    npm ci
else
    npm install
fi

cat <<'EOF'

macOS setup finished.

Start the local platform with:
  bash scripts/start_dev.sh

Useful checks on the Mac:
  uv run pytest tests/test_update_data.py -q
  uv run python -m pytest apps/akquant_platform/backend/tests -q
  cd apps/akquant_platform/frontend && npm run build
EOF
