from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    # The models live in the use case package, whose ``__init__`` imports the
    # interactor that depends on this port; importing them at runtime would
    # close the circle.
    from memiro.application.read_site.models import ContactsModel, RequisiteModel


class SiteGateway(Protocol):
    """Read storage port for the site's own data."""

    @abstractmethod
    async def read_contacts(self) -> ContactsModel | None:
        """Read the studio's contacts, or nothing while the owner has not filled them."""
        raise NotImplementedError

    @abstractmethod
    async def read_seller_requisites(self) -> list[RequisiteModel]:
        """Read the filled requisites of the seller, in the order they are printed."""
        raise NotImplementedError
