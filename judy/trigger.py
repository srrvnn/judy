from dataclasses import dataclass, field


@dataclass
class Trigger:
    """Something noticed by a heuristic (or the clock) that judy.run should decide about."""

    kind: str
    detail: str
    device_id: str | None = None
    data: dict = field(default_factory=dict)
