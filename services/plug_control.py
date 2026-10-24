import asyncio
import logging
import os

from kasa import Device, Discover

from models import Plug

logger = logging.getLogger("judy.control")

# Log what would happen instead of switching real plugs
DRY_RUN = os.environ.get("KASA_DRY_RUN", "0") == "1"
TIMEOUT_SECONDS = 15


class PlugControlError(Exception):
    pass


async def _find_device(plug: Plug) -> Device:
    """Connect to the plug at its last known IP; if it moved, find it again by device id."""
    try:
        device = await Discover.discover_single(plug.host, discovery_timeout=3)
        if device is not None:
            await device.update()
            if device.device_id == plug.device_id:
                return device
            await device.disconnect()
    except Exception as exc:
        logger.warning("could not reach %s at %s: %r; searching the network", plug.name, plug.host, exc)

    found = await Discover.discover(discovery_timeout=3)
    match = None
    for device in found.values():
        try:
            await device.update()
        except Exception:
            pass
        if device.device_id == plug.device_id:
            match = device
        else:
            await device.disconnect()
    if match is None:
        raise PlugControlError(f"could not find {plug.name or plug.model} on the network")
    return match


async def _set_power(plug: Plug, on: bool) -> tuple[str, str]:
    device = await _find_device(plug)
    try:
        await (device.turn_on() if on else device.turn_off())
        await device.update()
        if bool(device.is_on) != on:
            raise PlugControlError(f"told {plug.name or plug.model} to turn {'on' if on else 'off'} but it is still {'on' if device.is_on else 'off'}")
        return device.host, f"{plug.name or plug.model} turned {'on' if on else 'off'}"
    finally:
        await device.disconnect()


class PlugController:
    """Switches real Kasa plugs. Tests replace this with a fake."""

    def switch(self, plug: Plug, on: bool) -> str:
        """Turn a plug on or off and confirm it took effect. Returns a human-readable result."""
        word = "on" if on else "off"
        label = plug.name or plug.model
        if DRY_RUN:
            logger.info("dry run: would turn %s %s", label, word)
            return f"dry run: would turn {label} {word}"
        try:
            host, result = asyncio.run(asyncio.wait_for(_set_power(plug, on), TIMEOUT_SECONDS))
        except PlugControlError:
            raise
        except asyncio.TimeoutError:
            raise PlugControlError(f"timed out turning {label} {word}")
        except Exception as exc:
            raise PlugControlError(f"could not turn {label} {word}: {exc}")
        if host != plug.host:
            plug.host = host  # the plug moved; remember where it is now
        logger.info("%s", result)
        return result


controller = PlugController()


def get_controller() -> PlugController:
    return controller
