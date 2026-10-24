from datetime import datetime
from pydantic import BaseModel, StringConstraints
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
