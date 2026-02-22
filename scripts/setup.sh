#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# First-time project setup
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "╔══════════════════════════════════════════════════╗"
echo "║   Digital Employee — First-Time Setup            ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── .env file ────────────────────────────────────────────────────────────────
if [ ! -f "$ROOT_DIR/backend/.env" ]; then
    echo "📋 Creating backend/.env from .env.example..."
    cp "$ROOT_DIR/backend/.env.example" "$ROOT_DIR/backend/.env"
    echo "   ✅ Created. Please edit backend/.env with your credentials."
    echo ""
else
    echo "📋 backend/.env already exists — skipping."
fi

# ── Backend dependencies ─────────────────────────────────────────────────────
echo ""
echo "📦 Installing backend dependencies (uv)..."
cd "$ROOT_DIR/backend"
if command -v uv &> /dev/null; then
    uv sync
    echo "   ✅ Backend dependencies installed."
else
    echo "   ⚠️  'uv' not found. Install it: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# ── Frontend dependencies ────────────────────────────────────────────────────
echo ""
echo "📦 Installing frontend dependencies (npm)..."
cd "$ROOT_DIR/frontend"
if command -v npm &> /dev/null; then
    npm install --silent
    echo "   ✅ Frontend dependencies installed."
else
    echo "   ⚠️  'npm' not found. Install Node.js 20+."
    exit 1
fi

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════"
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit backend/.env with your API keys and email credentials"
echo "  2. Run:  ./scripts/start.sh   (Docker full stack)"
echo "     or:   ./scripts/dev.sh     (local dev with hot-reload)"
echo "═══════════════════════════════════════════════════"
