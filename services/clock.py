from datetime import datetime, timedelta, timezone


class Clock:
    """Global clock: real time plus an adjustable offset, so time can be moved from the control panel."""

    def __init__(self):
        self._offset = timedelta(0)

    def now(self) -> datetime:
        return datetime.now(timezone.utc) + self._offset

    @property
    def offset(self) -> timedelta:
        return self._offset

    def set(self, target: datetime) -> None:
        if target.tzinfo is None:
            target = target.replace(tzinfo=timezone.utc)
        self._offset = target - datetime.now(timezone.utc)

    def advance(self, delta: timedelta) -> None:
        self._offset += delta

    def reset(self) -> None:
        self._offset = timedelta(0)


clock = Clock()


def now() -> datetime:
    return clock.now()
