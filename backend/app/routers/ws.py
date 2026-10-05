"""In-process fan-out of calendar changes to connected wall displays.

The socket endpoint lives in routers/wall.py (/api/wall/ws) so it shares the
wall device cookie and authentication.
"""
from typing import Any, Dict, List

from fastapi import WebSocket

from app.core.events import EventBus, event_bus

class ConnectionManager:
    def __init__(self) -> None:
        self._connections: List[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._connections:
            self._connections.remove(ws)

    async def broadcast(self, message: Dict[str, Any]) -> None:
        dead: List[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for d in dead:
            self._connections.remove(d)


manager = ConnectionManager()


async def _forward_to_manager(event_type: str, payload: Dict[str, Any]) -> None:
    await manager.broadcast({"type": event_type, "data": payload})


event_bus.subscribe(_forward_to_manager)

