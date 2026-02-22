#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Run all tests (backend + frontend)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FAILED=0

echo "╔══════════════════════════════════════════════════╗"
echo "║   Digital Employee — Test Suite                  ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── Backend Tests ────────────────────────────────────────────────────────────
echo "🐍 Running backend tests (pytest)..."
echo "─────────────────────────────────────────────────"
cd "$ROOT_DIR/backend"
if uv run pytest -v --tb=short 2>&1; then
    echo "   ✅ Backend tests passed."
else
    echo "   ❌ Backend tests failed."
    FAILED=1
fi

echo ""

# ── Frontend Tests ───────────────────────────────────────────────────────────
echo "⚛️  Running frontend tests (vitest)..."
echo "─────────────────────────────────────────────────"
cd "$ROOT_DIR/frontend"
if npm test 2>&1; then
    echo "   ✅ Frontend tests passed."
else
    echo "   ❌ Frontend tests failed."
    FAILED=1
fi

echo ""

# ── Import Check ─────────────────────────────────────────────────────────────
echo "📦 Running backend import check..."
echo "─────────────────────────────────────────────────"
cd "$ROOT_DIR/backend"
if uv run python -c "
from digital_employee.settings import Settings
from digital_employee.models import Base
from digital_employee.services.llm_service import LLMService
from digital_employee.services.email_service import EmailService
from digital_employee.services.rag_service import RAGService
from digital_employee.workflow.graph import build_graph
from digital_employee.api.router import api_router
print(f'   Models: {len(Base.metadata.tables)} tables')
print(f'   API routes: {len(api_router.routes)} endpoints')
print(f'   Graph nodes: {len(build_graph().nodes)} nodes')
" 2>&1; then
    echo "   ✅ All imports valid."
else
    echo "   ❌ Import check failed."
    FAILED=1
fi

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════"
if [ $FAILED -eq 0 ]; then
    echo "✅ All checks passed!"
else
    echo "❌ Some checks failed. See output above."
    exit 1
fi
echo "═══════════════════════════════════════════════════"
