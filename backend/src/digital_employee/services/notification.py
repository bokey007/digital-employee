"""WebSocket push notification service for real-time UI updates."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import structlog
from starlette.websockets import WebSocket, WebSocketDisconnect

logger = structlog.get_logger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for real-time notifications."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.append(websocket)
        logger.info("ws_connected", total=len(self._connections))

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self._connections:
            self._connections.remove(websocket)
        logger.info("ws_disconnected", total=len(self._connections))

    async def broadcast(self, event: str, data: dict[str, Any]) -> None:
        """Broadcast an event to all connected clients."""
        message = json.dumps(
            {
                "event": event,
                "data": data,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        disconnected = []
        for ws in self._connections:
            try:
                await ws.send_text(message)
            except (WebSocketDisconnect, RuntimeError):
                disconnected.append(ws)

        for ws in disconnected:
            self.disconnect(ws)


# Singleton instance
ws_manager = ConnectionManager()
