from datetime import UTC, datetime
from typing import Protocol, override


class Clock(Protocol):
    """Source of the current time for domain rules."""

    def now(self) -> datetime:
        """Return the current moment as an aware UTC datetime."""
        raise NotImplementedError


class SystemClock(Clock):
    """Clock backed by the system time."""

    @override
    def now(self) -> datetime:
        """Return the current system time in UTC."""
        return datetime.now(tz=UTC)
