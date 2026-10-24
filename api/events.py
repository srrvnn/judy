from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from db.session import get_session
from models import Message
from services.events import broadcaster, event_stream, message_payload

router = APIRouter()


@router.get("/events")
async def events(
    after: int | None = Query(default=None, description="Replay messages with an id greater than this"),
    last_event_id: int | None = Header(default=None, alias="Last-Event-ID"),
    session: Session = Depends(get_session),
):
    """Stream new messages as server-sent events.

    A reconnecting browser sends Last-Event-ID automatically; anything newer is replayed first.
    """
    queue = broadcaster.subscribe()  # subscribe before replaying so nothing slips between the two
    since = last_event_id if last_event_id is not None else after
    replay = []
    if since is not None:
        messages = session.exec(select(Message).where(Message.id > since).order_by(Message.id)).all()
        replay = [message_payload(session, m) for m in messages]
    return StreamingResponse(
        event_stream(queue, replay),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
