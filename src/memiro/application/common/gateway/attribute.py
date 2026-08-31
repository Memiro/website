from abc import abstractmethod
from collections.abc import Sequence
from typing import Protocol

from memiro.entities.catalog.attribute.entity import Attribute


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
