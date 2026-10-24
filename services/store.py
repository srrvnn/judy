from datetime import datetime, timezone

from kasa import Device, Module
from sqlmodel import Session, select

from models import Household, Plug, Reading, User


def _energy_fields(device: Device) -> dict:
    energy = device.modules.get(Module.Energy)
    if energy is None:
        return {}
    fields = {}
    for column, attr in [
        ("power_w", "current_consumption"),
        ("voltage_v", "voltage"),
        ("current_a", "current"),
        ("energy_today_kwh", "consumption_today"),
        ("energy_total_kwh", "consumption_total"),
    ]:
        try:
            fields[column] = getattr(energy, attr)
        except Exception:
            pass
    return fields


def _default_household(session: Session) -> Household:
    household = session.exec(select(Household).where(Household.name == "Default household")).first()
    if household is None:
        household = Household(name="Default household")
        session.add(household)
        session.flush()
        session.add(User(household_id=household.id, name="Default user"))
        session.flush()
    return household


def save_plugs(session: Session, devices: list[Device]) -> int:
    """Register every plug we see and record a reading for each named one.

    Plugs we haven't seen before join the shared default household and user,
    which are created the first time they're needed. Plugs get readings only once
    they have been given a name (via the API).
    Returns the number of readings recorded.
    """
    now = datetime.now(timezone.utc)
    saved = 0
    for device in devices:
        plug = session.exec(select(Plug).where(Plug.device_id == device.device_id)).first()
        if plug is None:
            household = _default_household(session)
            plug = Plug(
                household_id=household.id,
                device_id=device.device_id,
                model=device.model,
                host=device.host,
                has_energy=Module.Energy in device.modules,
                first_seen_at=now,
                last_seen_at=now,
            )
            session.add(plug)
            session.flush()
        else:
            plug.model = device.model
            plug.host = device.host
            plug.last_seen_at = now
            session.add(plug)

        if plug.name:
            session.add(Reading(plug_id=plug.id, recorded_at=now, was_on=device.is_on, **_energy_fields(device)))
            saved += 1
    session.commit()
    return saved
