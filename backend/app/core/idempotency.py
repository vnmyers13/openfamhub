"""Idempotency keys for writes replayed from the offline queue (Phase 9).

A phone that saved a change while offline replays it when it reconnects. If
the first attempt reached the server but the reply was lost, a plain replay
would add the shopping item (or to-do) twice. Writes sent with an
`Idempotency-Key` header are remembered for a day: the same key from the
same sign-in gets the first answer back instead of running again.

In-process memory is enough: the API runs a single worker by design (a
restart forgets keys, which only matters for a reply lost in that moment).
"""
import hashlib
import time
from collections import OrderedDict

from starlette.types import ASGIApp, Message, Receive, Scope, Send

TTL_SECONDS = 24 * 3600
MAX_KEYS = 5000
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class IdempotencyMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.seen: OrderedDict[str, tuple[float, list[Message]]] = OrderedDict()

    def reset(self) -> None:
        self.seen.clear()

    def _key(self, scope: Scope) -> str | None:
        headers = dict(scope.get("headers") or [])
        key = headers.get(b"idempotency-key")
        if not key or len(key) > 128:
            return None
        # Scope the key to the sign-in (cookie) and the request, so keys can't
        # be used to read someone else's answer.
        who = headers.get(b"cookie", b"")
        raw = b"|".join([key, who, scope["method"].encode(), scope["path"].encode()])
        return hashlib.sha256(raw).hexdigest()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in WRITE_METHODS:
            await self.app(scope, receive, send)
            return
        key = self._key(scope)
        if key is None:
            await self.app(scope, receive, send)
            return
        now = time.monotonic()
        for k in [k for k, (t, _) in self.seen.items() if now - t > TTL_SECONDS]:
            del self.seen[k]
        if key in self.seen:
            for message in self.seen[key][1]:
                if message["type"] == "http.response.start":
                    message = {**message, "headers": [*message.get("headers", []), (b"idempotent-replay", b"true")]}
                await send(message)
            return

        messages: list[Message] = []

        async def capture(message: Message) -> None:
            messages.append(message)
            await send(message)

        await self.app(scope, receive, capture)
        start = next((m for m in messages if m["type"] == "http.response.start"), None)
        # Remember answers, not failures: a 5xx should be retried for real.
        if start is not None and start["status"] < 500:
            self.seen[key] = (now, messages)
            while len(self.seen) > MAX_KEYS:
                self.seen.popitem(last=False)


def find(app) -> "IdempotencyMiddleware | None":
    """The installed middleware (for tests that need to reset it)."""
    stack = getattr(app, "middleware_stack", None)
    while stack is not None:
        if isinstance(stack, IdempotencyMiddleware):
            return stack
        stack = getattr(stack, "app", None)
    return None
