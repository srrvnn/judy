from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from db.session import get_session
from models import Message
from schemas import MessageRead
from services.events import message_payload

router = APIRouter()


@router.get("/messages", response_model=list[MessageRead])
def list_messages(session: Session = Depends(get_session)):
    messages = session.exec(select(Message).order_by(Message.created_at.desc(), Message.id.desc())).all()
    return [message_payload(session, m) for m in messages]
