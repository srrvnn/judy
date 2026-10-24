from sqlmodel import Session

from models import Message
from services.clock import now


def resolve_message(session: Session, message_id: int, by: str) -> Message | None:
    """Mark a message as taken care of (severity becomes info). Nothing is sent over the stream.

    `by` is "user" or "judy". Returns None if the message doesn't exist or was already resolved.
    """
    message = session.get(Message, message_id)
    if message is None or message.resolved_at is not None:
        return None
    message.severity = "info"
    message.resolved_at = now()
    message.resolved_by = by
    session.add(message)
    session.commit()
    session.refresh(message)
    return message
