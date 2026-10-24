"""Server-sent events plumbing: an in-memory broadcaster and the stream generator.

judy.run saves messages on a worker thread while SSE clients live on the event
loop, so publish() hands payloads across threads safely. State is per process.
"""
import asyncio
import json
import os
from collections.abc import AsyncIterator

from sqlmodel import Session, select

from models import Action, Message
from schemas import MessageRead
from services.clock import now

HEARTBEAT_SECONDS = 15
RETRY_MS = 3000
# Off by default. Set SSE_MOCK_ON_CONNECT=1 to send a mock message to every client that
# connects, so a UI can be built without waiting on a real trigger.
MOCK_ON_CONNECT = os.environ.get("SSE_MOCK_ON_CONNECT", "0") == "1"


def mock_message() -> dict:
    """A fake message in the same shape as a real one. Never saved to the database."""
    return {
        "id": 0,
        "household_id": 0,
        "plug_id": None,
        "kind": "mock",
        "severity": "critical",
        "title": "Mock: heater left on",
        "body": "This is a mock message sent when you connected. The heater has been on for 4 hours.",
        "created_at": now().isoformat(),
        "actions": [
            {"id": 0, "label": "Turn off", "description": "Switch the heater off", "type": "turn_off",
             "plug_id": None, "status": "suggested"},
            {"id": 0, "label": "Dismiss", "description": "Ignore this", "type": "dismiss",
             "plug_id": None, "status": "suggested"},
        ],
        "mock": True,
    }


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
        """Call from the event loop. Returns a queue that receives (event, payload) for everything published."""
        self._loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    def publish(self, payload: dict, event: str = "message") -> None:
        """Safe to call from any thread. Does nothing when nobody is listening."""
        if self._loop is None or not self._subscribers:
            return
        try:
            self._loop.call_soon_threadsafe(self._fan_out, event, payload)
        except RuntimeError:
            # the loop that owned these subscribers is gone (e.g. shutdown); drop them
            self._subscribers.clear()

    def _fan_out(self, event: str, payload: dict) -> None:
        for queue in list(self._subscribers):
            queue.put_nowait((event, payload))

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


broadcaster = Broadcaster()


def format_event(payload: dict, with_id: bool = True, event: str = "message") -> str:
    # No id line for mock or update events: an id would become the browser's Last-Event-ID
    # and trigger a bogus replay on reconnect.
    id_line = f"id: {payload['id']}\n" if with_id else ""
    return f"{id_line}event: {event}\ndata: {json.dumps(payload)}\n\n"


async def event_stream(
    queue: asyncio.Queue,
    replay: list[dict],
    heartbeat: float = HEARTBEAT_SECONDS,
    bus: Broadcaster = broadcaster,
    mock: dict | None = None,
) -> AsyncIterator[str]:
    """Yield SSE text: a retry hint, an optional mock message, replayed messages, then live ones with keep-alives."""
    last_id = 0
    try:
        yield f"retry: {RETRY_MS}\n\n"
        if mock is not None:
            yield format_event(mock, with_id=False)
        for payload in replay:
            last_id = max(last_id, payload["id"])
            yield format_event(payload)
        while True:
            try:
                event, payload = await asyncio.wait_for(queue.get(), timeout=heartbeat)
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
                continue
            if event != "message":
                yield format_event(payload, with_id=False, event=event)
                continue
            if payload["id"] <= last_id:
                continue  # already sent during replay
            last_id = payload["id"]
            yield format_event(payload)
    finally:
        bus.unsubscribe(queue)
