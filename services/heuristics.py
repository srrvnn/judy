import logging
import os

from kasa import Device, Module

from judy.trigger import Trigger

logger = logging.getLogger("judy.heuristics")

POWER_THRESHOLD_W = float(os.environ.get("POWER_THRESHOLD_W", "1.0"))


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
                label = device.alias or device.model
                triggers.append(
                    Trigger(
                        kind="power_after_off",
                        detail=f"{label} ({device.host}) is drawing {power:.1f}W after being off",
                        device_id=device.device_id,
                        data={"power_w": power, "host": device.host},
                    )
                )
        return triggers


def log_triggers(triggers: list[Trigger]) -> None:
    for t in triggers:
        logger.log(logging.WARNING if t.kind == "power_after_off" else logging.INFO, "%s", t.detail)

