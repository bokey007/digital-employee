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

echo ""
echo "📝 Key settings to configure in backend/.env:"
echo "   OPENAI_API_KEY        — your OpenAI key"
echo "   SMTP_HOST/PORT        — outbound email for notifications"
echo "   EMAIL_ADDRESS         — the Digital Employee's sender address"
echo "   EMAIL_PASSWORD        — SMTP app password"
echo "   PORTAL_BASE_URL       — frontend URL (default: http://localhost:3000)"
echo "   ANUJ_EMAIL / ASHWIN_EMAIL — reviewer email addresses"
echo ""

# ── Backend dependencies ─────────────────────────────────────────────────────
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
echo "     (PORTAL_BASE_URL defaults to http://localhost:3000 — change for production)"
echo "  2. Start the app:"
echo "     ./scripts/start.sh      (Docker full stack — auto-runs DB migrations)"
echo "     ./scripts/dev.sh        (local dev with hot-reload — also auto-runs migrations)"
echo ""
echo "  🔗 Once running, portal links are emailed automatically"
echo "     when you trigger a newsletter cycle from the dashboard."
echo "═══════════════════════════════════════════════════"
