import logging

from sqlmodel import Session, select

from models import Action, Message, Plug, User
from services.clock import now
from services.events import message_payload
from services.messages import resolve_message
from services.plug_control import PlugController, PlugControlError

logger = logging.getLogger("judy.actions")


class ActionError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail


def choose_action(session: Session, action_id: int, controller: PlugController) -> dict:
    """Run an action the user picked. Returns the message (with its actions) as JSON-ready data.

    On success the action becomes `executed`, the message's other actions `expired`, and the
    message is resolved. On failure the action becomes `failed` and the message stays open to retry.
    """
    action = session.get(Action, action_id)
    if action is None:
        raise ActionError(404, "Action not found")
    message = session.get(Message, action.message_id)
    if message.resolved_at is not None:
        raise ActionError(409, "This message has already been handled")
    if action.status not in ("suggested", "failed"):
        raise ActionError(409, f"Action is already {action.status}")

    user = session.exec(select(User).where(User.household_id == message.household_id).order_by(User.id)).first()
    action.status = "chosen"
    action.chosen_by_user_id = user.id if user else None
    action.chosen_at = now()
    action.result = None
    session.add(action)
    session.commit()
    logger.info("chosen: %s (%s)", action.label, action.type)

    try:
        result = _execute(session, action, controller)
    except (PlugControlError, ValueError) as exc:
        action.status = "failed"
        action.result = str(exc)
        session.add(action)
        session.commit()
        logger.error("action %s failed: %s", action.id, exc)
        return message_payload(session, message)

    action.status = "executed"
    action.executed_at = now()
    action.result = result
    session.add(action)
    for other in session.exec(select(Action).where(Action.message_id == message.id, Action.id != action.id)).all():
        if other.status in ("suggested", "failed"):
            other.status = "expired"
            session.add(other)
    session.commit()
    logger.info("action %s executed: %s", action.id, result)
    resolve_message(session, message.id, by="user")
    session.refresh(message)
    return message_payload(session, message)


def _execute(session: Session, action: Action, controller: PlugController) -> str:
    if action.type == "dismiss":
        return "Dismissed"
    if action.type in ("turn_off", "turn_on"):
        plug = session.get(Plug, action.plug_id) if action.plug_id else None
        if plug is None:
            raise ValueError("this action has no plug to switch")
        result = controller.switch(plug, on=action.type == "turn_on")
        session.add(plug)  # the controller may have updated the plug's address
        return result
    raise ValueError(f"unknown action type: {action.type}")
