"""WebSocket Connection Manager for MedFlow live state broadcasts.

Conforms to AGENT.md §17.3, §20.
"""

from __future__ import annotations

import logging
from typing import Any
from fastapi import WebSocket

logger = logging.getLogger("medflow.ws")


class ConnectionManager:
    """Manages active WebSocket connections and broadcasts simulation state."""

    def __init__(self) -> None:
        self.active_connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        """Accept connection and register websocket."""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info("WebSocket client connected. Active: %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        """Unregister websocket."""
        self.active_connections.discard(websocket)
        logger.info("WebSocket client disconnected. Active: %d", len(self.active_connections))

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Broadcast JSON message to all connected clients; cleans up dead sockets."""
        if not self.active_connections:
            return

        dead_connections: list[WebSocket] = []
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)

        for dead in dead_connections:
            self.active_connections.discard(dead)

    async def broadcast_state(self, snapshot: dict[str, Any]) -> None:
        """Convenience method to broadcast full snapshot state envelope."""
        await self.broadcast({"type": "state", "data": snapshot})


manager = ConnectionManager()
