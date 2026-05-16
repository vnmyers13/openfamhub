from typing import Any, Dict, List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.events import EventBus, event_bus

router = APIRouter()


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


@router.websocket("/wall")
async def wall_websocket(ws: WebSocket) -> None:
    try:
        await manager.connect(ws)
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(ws)
