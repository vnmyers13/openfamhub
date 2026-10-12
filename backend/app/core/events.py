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


# ---- emit after commit -------------------------------------------------------
# Listeners (wall displays) re-fetch as soon as they hear "calendar_updated".
# Emitting before the transaction commits lets them read the old data, so
# changes are queued on the DB session and published only after commit.

_PENDING = "pending_events"


def queue_event(db: Any, event_type: str, payload: Dict[str, Any]) -> None:
    """Queue an event to publish after *db* commits (see publish_queued)."""
    pending = db.info.setdefault(_PENDING, [])
    if (event_type, payload) not in pending:  # one notice per change is enough
        pending.append((event_type, payload))


async def publish_queued(db: Any) -> None:
    """Publish everything queued on *db*. Call only after a successful commit."""
    for event_type, payload in db.info.pop(_PENDING, []):
        await event_bus.emit(event_type, payload)


def discard_queued(db: Any) -> None:
    """Drop queued events, e.g. after a rollback."""
    db.info.pop(_PENDING, None)
