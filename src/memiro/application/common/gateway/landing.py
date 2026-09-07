from abc import abstractmethod
from collections.abc import Collection, Sequence
from typing import Protocol

from memiro.entities.catalog.landing.entity import Landing
from memiro.entities.common.identifiers import AttributeId, AttributeValueId, LandingId


class LandingGateway(Protocol):
    """Storage port of the ``Landing`` aggregate."""

    @abstractmethod
    async def get(self, landing_id: LandingId, *, for_update: bool = False) -> Landing | None:
        """Load one landing with its narrowing, or ``None`` if there is no such landing.

        Implementations must load the conditions eagerly — the owner's
        commands replace the set whole — and ``for_update`` locks the
        aggregate root until the current transaction ends, raising
        ``LockTimeoutError`` when the lock is refused.
        """
        raise NotImplementedError

    @abstractmethod
    async def slug_owner(self, slug: str) -> LandingId | None:
        """Name the landing holding this public address, or ``None`` if it is free.

        Uniqueness belongs to the transaction, not to the aggregate: a landing
        cannot see the addresses of the others, and the database is the only
        place that knows them all.
        """
        raise NotImplementedError

    @abstractmethod
    async def headings_narrowing_by_values(self, value_ids: Collection[AttributeValueId]) -> Sequence[str]:
        """Name the landings narrowing by any of these dictionary rows, in one stable order.

        The answer is shown to the owner as the reason a row cannot leave the
        dictionary: a page narrowed by a value that is gone would stop being
        the page its address promises.
        """
        raise NotImplementedError

    @abstractmethod
    async def headings_narrowing_by_attribute(self, attribute_id: AttributeId) -> Sequence[str]:
        """Name the landings narrowing by anything of this attribute, in one stable order."""
        raise NotImplementedError
