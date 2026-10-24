"""Server-sent events plumbing: an in-memory broadcaster and the stream generator.

judy.run saves messages on a worker thread while SSE clients live on the event
loop, so publish() hands payloads across threads safely. State is per process.
"""
import asyncio
import json
from collections.abc import AsyncIterator

from sqlmodel import Session, select

from models import Action, Message
from schemas import MessageRead

HEARTBEAT_SECONDS = 15
RETRY_MS = 3000


def message_payload(session: Session, message: Message) -> dict:
    """A message with its actions, as JSON-ready data (same shape as GET /v1/messages)."""
    actions = session.exec(select(Action).where(Action.message_id == message.id).order_by(Action.id)).all()
    read = MessageRead(**message.model_dump(), actions=[a.model_dump() for a in actions])
    return read.model_dump(mode="json")


class Broadcaster:
    def __init__(self):
        self._subscribers: set[asyncio.Queue] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def subscribe(self) -> asyncio.Queue:
        """Call from the event loop. Returns a queue that receives every published payload."""
        self._loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    def publish(self, payload: dict) -> None:
        """Safe to call from any thread. Does nothing when nobody is listening."""
        if self._loop is None or not self._subscribers:
            return
        try:
            self._loop.call_soon_threadsafe(self._fan_out, payload)
        except RuntimeError:
            # the loop that owned these subscribers is gone (e.g. shutdown); drop them
            self._subscribers.clear()

    def _fan_out(self, payload: dict) -> None:
        for queue in list(self._subscribers):
            queue.put_nowait(payload)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


broadcaster = Broadcaster()


def format_event(payload: dict) -> str:
    return f"id: {payload['id']}\nevent: message\ndata: {json.dumps(payload)}\n\n"


async def event_stream(
    queue: asyncio.Queue,
    replay: list[dict],
    heartbeat: float = HEARTBEAT_SECONDS,
    bus: Broadcaster = broadcaster,
) -> AsyncIterator[str]:
    """Yield SSE text: a retry hint, replayed messages, then live messages with keep-alives."""
    last_id = 0
    try:
        yield f"retry: {RETRY_MS}\n\n"
        for payload in replay:
            last_id = max(last_id, payload["id"])
            yield format_event(payload)
        while True:
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=heartbeat)
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
                continue
            if payload["id"] <= last_id:
                continue  # already sent during replay
            last_id = payload["id"]
            yield format_event(payload)
    finally:
        bus.unsubscribe(queue)
