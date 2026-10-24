from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from db.session import get_session
from schemas import MessageRead
from services.actions import ActionError, choose_action
from services.plug_control import PlugController, get_controller

router = APIRouter()


@router.post("/actions/{action_id}/choose", response_model=MessageRead)
def choose(action_id: int, session: Session = Depends(get_session), controller: PlugController = Depends(get_controller)):
    """Run the action the user picked. Returns the updated message; a failed action comes back with status 'failed'."""
    try:
        return choose_action(session, action_id, controller)
    except ActionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
