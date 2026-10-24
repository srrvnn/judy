import asyncio
import os

from kasa import Device, DeviceType, Discover, Module
from sqlmodel import Session

from db.session import engine
from services.store import save_plugs

PLUG_TYPES = {DeviceType.Plug, DeviceType.Strip, DeviceType.StripSocket}
POLL_INTERVAL_SECONDS = int(os.environ.get("KASA_POLL_INTERVAL", "5"))


async def discover_plugs() -> list[Device]:
    """Broadcast discovery on the local network and return plugs/strips."""
    found = await Discover.discover(discovery_timeout=2)
    for device in found.values():
        try:
            await device.update()
        except Exception as exc:
            print(f"[kasa] could not update {device.host}: {exc!r}", flush=True)
    plugs = [d for d in found.values() if d.device_type in PLUG_TYPES]
    for device in found.values():
        await device.disconnect()
    return sorted(plugs, key=lambda d: d.host)


def describe_energy(device: Device) -> str:
    energy = device.modules.get(Module.Energy)
    if energy is None:
        return " | no metering"
    parts = []
    for label, attr, unit in [
        ("power", "current_consumption", "W"),
        ("voltage", "voltage", "V"),
        ("current", "current", "A"),
        ("today", "consumption_today", "kWh"),
    ]:
        value = getattr(energy, attr, None)
        if value is not None:
            parts.append(f"{label} {value:.2f}{unit}")
    return " | " + ", ".join(parts)


def _save(plugs: list[Device]) -> None:
    with Session(engine) as session:
        save_plugs(session, plugs)


async def poll_forever(interval: float = POLL_INTERVAL_SECONDS) -> None:
    while True:
        try:
            plugs = await discover_plugs()
            await asyncio.to_thread(_save, plugs)
            for p in plugs:
                state = "on" if p.is_on else "off"
                print(f"INFO: [kasa] {p.alias or 'no name'} ({p.model}) @ {p.host} - {state}{describe_energy(p)}", flush=True)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"[kasa] discovery failed: {exc!r}", flush=True)
        await asyncio.sleep(interval)
