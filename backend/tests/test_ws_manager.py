"""Live-update fan-out to wall sockets (routers/ws.py)."""
from app.routers.ws import ConnectionManager, _forward_to_manager, manager


class FakeSocket:
    def __init__(self, fail=False):
        self.sent, self.accepted, self.fail = [], False, fail

    async def accept(self):
        self.accepted = True

    async def send_json(self, message):
        if self.fail:
            raise RuntimeError("connection reset")
        self.sent.append(message)


async def test_broadcast_reaches_every_wall_and_drops_dead_ones():
    hub = ConnectionManager()
    alive, dead = FakeSocket(), FakeSocket(fail=True)
    await hub.connect(alive)
    await hub.connect(dead)
    assert alive.accepted and dead.accepted

    await hub.broadcast({"type": "calendar_updated"})
    await hub.broadcast({"type": "calendar_updated"})

    assert alive.sent == [{"type": "calendar_updated"}] * 2
    assert hub._connections == [alive]  # the dead socket was removed after the first failure


async def test_disconnect_is_idempotent():
    hub = ConnectionManager()
    ws = FakeSocket()
    await hub.connect(ws)
    hub.disconnect(ws)
    hub.disconnect(ws)
    assert hub._connections == []


async def test_bus_events_are_forwarded_with_their_type():
    ws = FakeSocket()
    await manager.connect(ws)
    try:
        await _forward_to_manager("calendar_updated", {"source_id": "s1"})
    finally:
        manager.disconnect(ws)
    assert ws.sent == [{"type": "calendar_updated", "data": {"source_id": "s1"}}]
