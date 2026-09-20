"""WebSocket router for live simulation state broadcast.

Conforms to AGENT.md §18 (Task 5), §20.
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from api.ws import manager
from api.sim_service import sim_service

logger = logging.getLogger("medflow.ws")
router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/simulation")
async def simulation_websocket(websocket: WebSocket):
    """Client WebSocket connection for live tick broadcast.
    
    Immediately sends initial state snapshot on connect, then listens for disconnect.
    """
    await manager.connect(websocket)
    # Send full snapshot immediately on connection so UI doesn't stare at empty screen
    try:
        initial_snapshot = sim_service.get_snapshot()
        await websocket.send_json({"type": "state", "data": initial_snapshot})
    except Exception as e:
        logger.warning("Failed to send initial snapshot to WS client: %s", e)

    try:
        while True:
            # Client can send ping / keepalive if desired
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.warning("WebSocket connection exception: %s", e)
        manager.disconnect(websocket)
