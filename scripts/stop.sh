#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Stop all running services
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "🛑 Stopping Digital Employee services..."

docker compose down 2>/dev/null && echo "   ✅ Docker services stopped." || true

# Kill any lingering local processes
pkill -f "uvicorn digital_employee" 2>/dev/null && echo "   ✅ Backend stopped." || true
pkill -f "celery.*digital_employee" 2>/dev/null && echo "   ✅ Celery stopped." || true
pkill -f "vite.*digital_employee\|npm run dev" 2>/dev/null && echo "   ✅ Frontend stopped." || true

echo ""
echo "✅ All services stopped."
