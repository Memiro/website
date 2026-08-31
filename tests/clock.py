"""The frozen instant and the clock twin every unit test shares (§14.6.8)."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import override

from memiro_common.clock import Clock

# Non-zero seconds and microseconds: a normalization that silently drops them
# stays invisible against a round instant.
NOW = datetime(2026, 8, 31, 12, 34, 56, 789012, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class FakeClock(Clock):
    """Clock frozen at a known instant for unit tests."""

    instant: datetime

    @override
    def now(self) -> datetime:
        """Return the frozen instant."""
        return self.instant
