#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Start the full stack with Docker Compose (production-like)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "╔══════════════════════════════════════════════════╗"
echo "║   Digital Employee — Full Stack (Docker)         ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── Pre-flight checks ────────────────────────────────────────────────────────
if [ ! -f "backend/.env" ]; then
    echo "❌ backend/.env not found. Run ./scripts/setup.sh first."
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker."
    exit 1
fi

# ── Build & Start ────────────────────────────────────────────────────────────
echo "🐳 Building and starting all services..."
echo "   PostgreSQL + pgvector | Redis | Backend API | Celery Worker | Celery Beat | Frontend"
echo ""

docker compose up --build -d

echo ""
echo "⏳ Waiting for services to become healthy..."
sleep 5

# ── Health check ─────────────────────────────────────────────────────────────
for i in {1..30}; do
    if curl -sf http://localhost:8000/healthz > /dev/null 2>&1; then
        echo ""
        echo "═══════════════════════════════════════════════════"
        echo "✅ All services running!"
        echo ""
        echo "  🌐 Frontend:     http://localhost:3000"
        echo "  📡 Backend API:  http://localhost:8000"
        echo "  📖 API Docs:     http://localhost:8000/docs"
        echo "  ❤️  Health:       http://localhost:8000/healthz"
        echo ""
        echo "  📊 Dashboard:    http://localhost:3000/"
        echo "  📰 Newsletters:  http://localhost:3000/newsletters"
        echo "  💬 Chat:         http://localhost:3000/chat"
        echo "  👥 Leads:        http://localhost:3000/leads"
        echo ""
        echo "  To stop:  docker compose down"
        echo "  Logs:     docker compose logs -f [service]"
        echo "═══════════════════════════════════════════════════"
        exit 0
    fi
    echo -n "."
    sleep 2
done

echo ""
echo "⚠️  Backend not responding after 60s. Check logs:"
echo "   docker compose logs backend"
