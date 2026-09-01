"""The frozen instant and the clock twin every unit test shares (§14.6.8)."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import override

from memiro_common.clock import Clock

# Non-zero seconds and microseconds: a normalization that silently drops them
# stays invisible against a round instant.
NOW = datetime(2026, 8, 31, 12, 34, 56, 789012, tzinfo=UTC)

# Where a command moves an aggregate to: far enough from NOW that a forgotten
# `updated_at` cannot pass a monotonicity assertion by accident.
LATER = NOW + timedelta(minutes=5)


@dataclass(frozen=True, slots=True)
class FakeClock(Clock):
    """Clock frozen at a known instant for unit tests."""

    instant: datetime

    @override
    def now(self) -> datetime:
        """Return the frozen instant."""
        return self.instant


# The two twins every unit test arranges with: one for the instant an aggregate
# is born at, one for the instant a command moves it to.
CLOCK = FakeClock(instant=NOW)
LATER_CLOCK = FakeClock(instant=LATER)
