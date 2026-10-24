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
    offset_seconds: float
    simulated: bool
    messages_created: int = 0


class ClockUpdate(BaseModel):
    now: datetime | None = None
    advance_minutes: int | None = None

    @model_validator(mode="after")
    def exactly_one(self):
        if (self.now is None) == (self.advance_minutes is None):
            raise ValueError("provide exactly one of 'now' or 'advance_minutes'")
        return self


class ActionRead(BaseModel):
    id: int
    label: str
    description: str
    type: str
    plug_id: int | None
    status: str


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
