from abc import abstractmethod
from collections.abc import Sequence
from typing import Protocol

from memiro.entities.catalog.attribute.entity import Attribute
from memiro.entities.common.identifiers import AttributeId


class AttributeGateway(Protocol):
    """Storage port of the ``Attribute`` aggregate."""

    @abstractmethod
    async def list_with_values(self) -> Sequence[Attribute]:
        """List the whole dictionary with the values of every attribute.

        The dictionary is one screen of the admin — a handful of attributes
        for the whole site — so pricing takes it whole rather than guessing
        which rows a configuration will need. Scoping by category arrives
        with ``Category``.
        """
        raise NotImplementedError

    @abstractmethod
    async def get(self, attribute_id: AttributeId, *, for_update: bool = False) -> Attribute | None:
        """Load one attribute with its dictionary, or ``None`` if there is no such attribute.

        Implementations must load the values eagerly — the owner's commands
        replace the set whole — and ``for_update`` locks the aggregate root
        until the current transaction ends, raising ``LockTimeoutError`` when
        the lock is refused.
        """
        raise NotImplementedError
