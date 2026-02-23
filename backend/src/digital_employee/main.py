"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.websockets import WebSocket, WebSocketDisconnect

from digital_employee.api.router import api_router
from digital_employee.database import close_db, init_db
from digital_employee.services.notification import ws_manager
from digital_employee.settings import get_settings
from digital_employee.utils.logging import setup_logging
import os

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle management."""
    settings = get_settings()
    setup_logging(settings.log_level)
    logger.info("starting_up", app=settings.app_name, env=settings.app_env.value)

    # Initialise database tables and pgvector extension
    await init_db()

    yield

    # Shutdown
    await close_db()
    logger.info("shutdown_complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="AI-Powered Digital Employee — Newsletter Automation",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if not settings.is_production else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount API routes
    app.include_router(api_router)

    # Mount static files for avatars
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    os.makedirs(static_dir, exist_ok=True)
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # Health checks
    @app.get("/healthz", tags=["health"])
    async def healthz():
        return {"status": "healthy"}

    @app.get("/readyz", tags=["health"])
    async def readyz():
        from digital_employee.database import engine

        try:
            async with engine.connect() as conn:
                await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
            return {"status": "ready", "database": "connected"}
        except Exception as exc:
            return {"status": "not_ready", "database": str(exc)}

    # WebSocket endpoint for real-time notifications
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await ws_manager.connect(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket)

    return app


# Application instance for uvicorn
app = create_app()
