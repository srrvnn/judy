from datetime import datetime
from pydantic import BaseModel, StringConstraints, model_validator
from typing import Annotated


class PlugRead(BaseModel):
    id: int
    household_id: int
    device_id: str
    name: str | None
    model: str
    host: str
    room: str | None
    has_energy: bool
    first_seen_at: datetime
    last_seen_at: datetime


class PlugUpdate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ClockRead(BaseModel):
    now: datetime
    real_now: datetime
    now_local: str  # the clock's time as the server's local wall clock, ISO with offset
    real_now_local: str  # the real time, same format
    timezone: str
    offset_seconds: float
    simulated: bool
    messages_created: int = 0


class ClockUpdate(BaseModel):
    now: datetime | None = None
    advance_minutes: int | None = None
    next_at: str | None = None  # "HH:MM" server-local time: move to its next occurrence in the future

    @model_validator(mode="after")
    def exactly_one(self):
        if sum(v is not None for v in (self.now, self.advance_minutes, self.next_at)) != 1:
            raise ValueError("provide exactly one of 'now', 'advance_minutes' or 'next_at'")
        if self.next_at is not None:
            try:
                datetime.strptime(self.next_at, "%H:%M")
            except ValueError:
                raise ValueError("'next_at' must look like 16:00")
        return self


class ActionRead(BaseModel):
    id: int
    label: str
    description: str
    type: str
    plug_id: int | None
    status: str
    result: str | None = None


class MessageRead(BaseModel):
    id: int
    household_id: int
    plug_id: int | None
    kind: str
    severity: str
    title: str
    body: str
    created_at: datetime
    resolved_at: datetime | None
    resolved_by: str | None
    actions: list[ActionRead]
