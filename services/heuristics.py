import logging
import os
from dataclasses import dataclass

from kasa import Device, Module

logger = logging.getLogger("judy.heuristics")

POWER_THRESHOLD_W = float(os.environ.get("POWER_THRESHOLD_W", "1.0"))


@dataclass
class Trigger:
    kind: str
    device_id: str
    host: str
    label: str
    power_w: float


def current_power_w(device: Device) -> float | None:
    """Live power draw in watts, or None if the plug can't meter."""
    energy = device.modules.get(Module.Energy)
    if energy is None:
        return None
    try:
        return energy.current_consumption
    except Exception:
        return None


class PowerAfterOffDetector:
    """Fires when a plug that was not drawing power in the previous poll is drawing power now.

    Keeps the last seen state per plug in memory, so the first poll after a
    restart never fires.
    """

    def __init__(self, threshold_w: float = POWER_THRESHOLD_W):
        self.threshold_w = threshold_w
        self._was_drawing: dict[str, bool] = {}

    def check(self, devices: list[Device]) -> list[Trigger]:
        triggers = []
        for device in devices:
            power = current_power_w(device)
            if power is None:
                continue
            drawing = bool(device.is_on) and power >= self.threshold_w
            previous = self._was_drawing.get(device.device_id)
            self._was_drawing[device.device_id] = drawing
            if drawing and previous is False:
                triggers.append(
                    Trigger(
                        kind="power_after_off",
                        device_id=device.device_id,
                        host=device.host,
                        label=device.alias or device.model,
                        power_w=power,
                    )
                )
        return triggers


def log_triggers(triggers: list[Trigger]) -> None:
    for t in triggers:
        logger.warning("%s (%s) is drawing %.1fW after being off", t.label, t.host, t.power_w)
