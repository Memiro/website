from collections.abc import Sequence
from typing import Protocol


class UoW(Protocol):
    """The four session members an interactor is allowed to touch.

    Honest framing: this is not the Unit of Work pattern but interface
    segregation over ``AsyncSession`` — the session itself is the only
    implementation, registered in DI under both types (§9.5). The protocol
    keeps SQLAlchemy out of the application layer and makes raw SQL from an
    interactor inexpressible.
    """

    def add(self, instance: object) -> None:
        """Schedule a new entity for INSERT on commit."""

    async def delete(self, instance: object) -> None:
        """Schedule a loaded entity for DELETE on commit."""

    async def flush(self, objects: Sequence[object] | None = None) -> None:
        """Push pending changes so generated ids exist before commit."""

    async def commit(self) -> None:
        """Commit the single transaction of the current request."""
