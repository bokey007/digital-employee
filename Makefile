# ─────────────────────────────────────────────────────────────────────────────
# Digital Employee — Makefile
# ─────────────────────────────────────────────────────────────────────────────
.PHONY: setup start stop dev test logs clean help reset-db

help: ## Show this help
	@grep -E '^[a-z]+:.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup: ## First-time setup (install dependencies, create .env)
	@bash scripts/setup.sh

start: ## Start the full stack with Docker Compose
	@bash scripts/start.sh

stop: ## Stop all services
	@bash scripts/stop.sh

dev: ## Start local dev mode (hot-reload, PG+Redis via Docker)
	@bash scripts/dev.sh

test: ## Run all tests (backend + frontend + import check)
	@bash scripts/test.sh

logs: ## Tail Docker Compose logs
	docker compose logs -f

clean: ## Remove containers, volumes, and build artifacts
	docker compose down -v --rmi local 2>/dev/null || true
	rm -rf backend/.venv frontend/node_modules frontend/dist
	@echo "✅ Cleaned."

reset-db: ## Wipe ONLY the database (for clean end-to-end testing)
	@echo "🛑 Stopping services and wiping database..."
	docker compose down -v 2>/dev/null || true
	@echo "✅ Database wiped. Run 'make dev' or './scripts/dev.sh' to start fresh."
