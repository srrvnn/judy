import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from db.session import get_session
from models import Plug, Reading

router = APIRouter()

def _rate_per_kwh() -> float:
    try:
        rate = float(os.environ.get("ENERGY_RATE_PER_KWH", "0.30"))
        return rate if rate > 0 else 0.30
    except (TypeError, ValueError):
        return 0.30

def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

@router.get("/dashboard")
def get_dashboard(session: Session = Depends(get_session)):
    """Return the current plug inventory with its most recent saved reading."""
    now = datetime.now(timezone.utc)
    rate = _rate_per_kwh()
    plugs = session.exec(select(Plug).order_by(Plug.id)).all()
    latest_readings: dict[int, Reading] = {}
    for reading in session.exec(select(Reading).order_by(Reading.recorded_at.desc())).all():
        latest_readings.setdefault(reading.plug_id, reading)
    devices = []
    poll_interval = max(1, int(os.environ.get("KASA_POLL_INTERVAL", "5")))
    online_window = max(30, poll_interval * 3)
    for plug in plugs:
        last_seen = _utc(plug.last_seen_at)
        reading = latest_readings.get(plug.id)
        power_w = reading.power_w if reading else None
        devices.append({
            "id": plug.id, "name": plug.name, "model": plug.model,
            "room": plug.room, "has_energy": plug.has_energy,
            "online": (now - last_seen).total_seconds() <= online_window,
            "is_on": reading.was_on if reading else None,
            "power_w": power_w,
            "voltage_v": reading.voltage_v if reading else None,
            "current_a": reading.current_a if reading else None,
            "energy_today_kwh": reading.energy_today_kwh if reading else None,
            "energy_total_kwh": reading.energy_total_kwh if reading else None,
            "hourly_cost": (power_w or 0) * rate / 1000 if power_w is not None else None,
            "last_reading_at": reading.recorded_at if reading else None,
            "last_seen_at": plug.last_seen_at,
        })
    return {"source": "live", "updated_at": now, "rate_per_kwh": rate, "devices": devices}
