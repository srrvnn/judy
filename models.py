from datetime import datetime, timezone
from sqlalchemy import JSON, Index
from sqlmodel import SQLModel, Field, Column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Household(SQLModel, table=True):
    __tablename__ = "households"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    created_at: datetime = Field(default_factory=utcnow)


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    household_id: int = Field(foreign_key="households.id", index=True)
    name: str
    email: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow)


class Plug(SQLModel, table=True):
    __tablename__ = "plugs"

    id: int | None = Field(default=None, primary_key=True)
    household_id: int = Field(foreign_key="households.id", index=True)
    device_id: str = Field(unique=True, index=True, description="Kasa hardware ID")
    name: str | None = Field(default=None, description="Name given in Judy; readings are only recorded once set")
    model: str
    host: str = Field(description="Last seen IP address")
    room: str | None = Field(default=None)
    has_energy: bool = Field(default=False, description="Whether the plug can meter energy")
    first_seen_at: datetime = Field(default_factory=utcnow)
    last_seen_at: datetime = Field(default_factory=utcnow)


class Reading(SQLModel, table=True):
    __tablename__ = "readings"
    __table_args__ = (Index("ix_readings_plug_id_recorded_at", "plug_id", "recorded_at"),)

    id: int | None = Field(default=None, primary_key=True)
    plug_id: int = Field(foreign_key="plugs.id")
    recorded_at: datetime = Field(default_factory=utcnow)
    was_on: bool
    power_w: float | None = Field(default=None)
    voltage_v: float | None = Field(default=None)
    current_a: float | None = Field(default=None)
    energy_today_kwh: float | None = Field(default=None)
    energy_total_kwh: float | None = Field(default=None)


class Message(SQLModel, table=True):
    __tablename__ = "messages"

    id: int | None = Field(default=None, primary_key=True)
    household_id: int = Field(foreign_key="households.id", index=True)
    plug_id: int | None = Field(default=None, foreign_key="plugs.id")
    kind: str = Field(index=True, description="e.g. high_usage, left_on")
    title: str
    body: str
    created_at: datetime = Field(default_factory=utcnow)
    read_at: datetime | None = Field(default=None)
    expires_at: datetime | None = Field(default=None)


class Action(SQLModel, table=True):
    __tablename__ = "actions"

    id: int | None = Field(default=None, primary_key=True)
    message_id: int = Field(foreign_key="messages.id", index=True)
    label: str = Field(description="Short button text, e.g. 'Turn off'")
    description: str = Field(description="Longer explanation of the suggested action")
    type: str = Field(description="e.g. turn_off, turn_on, dismiss")
    plug_id: int | None = Field(default=None, foreign_key="plugs.id")
    params: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    status: str = Field(default="suggested", description="suggested, chosen, executed, failed, expired")
    chosen_by_user_id: int | None = Field(default=None, foreign_key="users.id")
    chosen_at: datetime | None = Field(default=None)
    executed_at: datetime | None = Field(default=None)
    result: str | None = Field(default=None)
