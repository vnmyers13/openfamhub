import asyncio
from typing import Any, Callable, Dict, List

Listener = Callable[[str, Dict[str, Any]], Any]


class EventBus:
    def __init__(self) -> None:
        self._listeners: List[Listener] = []
        self._lock = asyncio.Lock()

    def subscribe(self, callback: Listener) -> Callable[[], None]:
        self._listeners.append(callback)

        def unsubscribe() -> None:
            if callback in self._listeners:
                self._listeners.remove(callback)

        return unsubscribe

    async def emit(self, event_type: str, payload: Dict[str, Any]) -> None:
        dead: List[Listener] = []
        async with self._lock:
            for listener in self._listeners:
                try:
                    result = listener(event_type, payload)
                    if result is not None and hasattr(result, "__await__"):
                        await result
                except Exception:
                    dead.append(listener)
            for d in dead:
                self._listeners.remove(d)


event_bus = EventBus()
