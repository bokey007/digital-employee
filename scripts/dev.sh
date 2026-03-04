#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Local development mode — hot-reload for backend & frontend
# Starts PostgreSQL + Redis via Docker, everything else natively
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.."
cd "$ROOT_DIR"

echo "╔══════════════════════════════════════════════════╗"
echo "║   Digital Employee — Dev Mode (hot-reload)       ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── Pre-flight ───────────────────────────────────────────────────────────────
if [ ! -f "backend/.env" ]; then
    echo "❌ backend/.env not found. Run ./scripts/setup.sh first."
    exit 1
fi

echo "🧹 Cleaning up old processes..."
    fuser -k 8000/tcp 2>/dev/null || true
    fuser -k 3000/tcp 2>/dev/null || true
pkill -f "uvicorn digital_employee" 2>/dev/null || true
pkill -f "celery.*digital_employee" 2>/dev/null || true
pkill -f "npm run dev" 2>/dev/null || true

# ── Start infra (PostgreSQL + Redis only) ────────────────────────────────────
echo "🐳 Starting PostgreSQL + Redis..."
docker compose up postgresql redis -d --wait 2>/dev/null || docker compose up postgresql redis -d
sleep 3
echo "   ✅ Infrastructure running."
echo ""

# ── Sync Dependencies ────────────────────────────────────────────────────────
echo "📦 Syncing backend dependencies..."
cd "$ROOT_DIR/backend"
uv sync

# ── Run migrations ───────────────────────────────────────────────────────────
echo ""
echo "🗄️  Running database migrations..."
uv run alembic upgrade head
echo "   ✅ Migrations applied (including portal_tokens table)."
echo ""

# ── Cleanup on exit ──────────────────────────────────────────────────────────
cleanup() {
    echo ""
    echo "🛑 Shutting down..."
    kill $(jobs -p) 2>/dev/null || true
    wait 2>/dev/null || true
    echo "   Stopped all processes. PostgreSQL + Redis still running."
    echo "   To stop those: docker compose down"
}
trap cleanup EXIT INT TERM

# ── Backend API (hot-reload) ─────────────────────────────────────────────────
echo "🚀 Starting Backend API (port 8000)..."
uv run uvicorn digital_employee.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
sleep 2

# ── Celery Worker ────────────────────────────────────────────────────────────
echo "⚙️  Starting Celery Worker..."
uv run celery -A digital_employee.tasks.celery_app worker --loglevel=info --concurrency=2 &
WORKER_PID=$!

# ── Celery Beat ──────────────────────────────────────────────────────────────
echo "⏰ Starting Celery Beat (daily reminder scheduler)..."
uv run celery -A digital_employee.tasks.celery_app beat --loglevel=info &
BEAT_PID=$!

# ── Frontend (Vite dev server) ───────────────────────────────────────────────
echo "🌐 Starting Frontend (port 3000)..."
cd "$ROOT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

# ── Ready ────────────────────────────────────────────────────────────────────
sleep 3
echo ""
echo "═══════════════════════════════════════════════════"
echo "✅ Dev environment running! (hot-reload enabled)"
echo ""
echo "  🌐 Frontend:      http://localhost:3000"
echo "  📡 Backend API:   http://localhost:8000"
echo "  📖 API Docs:      http://localhost:8000/docs"
echo ""
echo "  📊 Dashboard:     http://localhost:3000/"
echo "  📰 Newsletters:   http://localhost:3000/newsletters"
echo "  💬 Chat:          http://localhost:3000/chat"
echo "  👥 Leads:         http://localhost:3000/leads"
echo ""
echo "  🔗 Portal Submit: http://localhost:3000/portal/submit?token=<token>"
echo "  🔗 Portal Review: http://localhost:3000/portal/review?token=<token>"
echo "     Tokens are emailed automatically when you trigger a newsletter cycle."
echo ""
echo "  Press Ctrl+C to stop all services."
echo "═══════════════════════════════════════════════════"
echo ""

# Wait for any process to exit
wait -n $BACKEND_PID $WORKER_PID $BEAT_PID $FRONTEND_PID
