from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlmodel import Session

from db.session import get_session
from judy.run import run as judy_run
from judy.trigger import Trigger
from schemas import ClockRead, ClockUpdate
from services.clock import clock

router = APIRouter()


def _state(messages_created: int = 0) -> ClockRead:
    return ClockRead(
        now=clock.now(),
        real_now=datetime.now(timezone.utc),
        offset_seconds=clock.offset.total_seconds(),
        simulated=clock.offset != timedelta(0),
        messages_created=messages_created,
    )


def _time_changed(session: Session, before: datetime) -> ClockRead:
    after = clock.now()
    trigger = Trigger(
        kind="time_changed",
        detail=f"time changed from {before.isoformat()} to {after.isoformat()}",
        data={"from": before.isoformat(), "to": after.isoformat()},
    )
    return _state(len(judy_run(session, trigger)))


@router.get("/clock", response_model=ClockRead)
def get_clock():
    return _state()


@router.put("/clock", response_model=ClockRead)
def update_clock(body: ClockUpdate, session: Session = Depends(get_session)):
    before = clock.now()
    if body.now is not None:
        clock.set(body.now)
    else:
        clock.advance(timedelta(minutes=body.advance_minutes))
    return _time_changed(session, before)


@router.post("/clock/reset", response_model=ClockRead)
def reset_clock(session: Session = Depends(get_session)):
    before = clock.now()
    clock.reset()
    return _time_changed(session, before)
