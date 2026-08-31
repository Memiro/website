from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import uuid4

from memiro.entities.common.entity import Entity
from memiro.entities.common.identifiers import InquiryId, InquiryItemId, ProductId
from memiro.entities.common.measure import Dimensions
from memiro.entities.common.money import Money
from memiro.entities.errors.inquiry import (
    ConsentRequiredError,
    EmptyInquiryError,
    InquirySourceNotAcceptedError,
    InvalidInquiryContentsError,
)
from memiro.entities.pricing.quotation import PricingVerdict
from memiro_common.clock import Clock


class InquirySource(StrEnum):
    """The visitor flow that produced an inquiry."""

    SELECTION = "SELECTION"
    FREE_FORM = "FREE_FORM"
    PRODUCT_CARD = "PRODUCT_CARD"


@dataclass(frozen=True, slots=True)
class ConfigurationValue:
    """One named customer choice retained without a dictionary reference."""

    attribute_name: str
    value_name: str | None
    quantity: Decimal | None

    def __post_init__(self) -> None:
        """Keep the two forms of customer selection mutually exclusive."""
        if (self.value_name is None) is (self.quantity is None):
            msg = "A configuration value needs exactly one representation"
            raise RuntimeError(msg)


@dataclass(frozen=True, slots=True)
class InquiryConfiguration:
    """The immutable customer configuration recorded in one inquiry item."""

    dimensions: Dimensions
    values: tuple[ConfigurationValue, ...]


@dataclass
class InquiryItem(Entity):
    """One product snapshot belonging exclusively to an inquiry."""

    id: InquiryItemId
    product_id: ProductId
    product_name: str
    price_from: Money | None
    configuration: InquiryConfiguration | None
    calculated_price: Money | None
    verdict: PricingVerdict
    wish: str


@dataclass
class Inquiry(Entity):
    """A visitor's immutable request for the manager, with its item snapshots."""

    id: InquiryId
    source: InquirySource
    name: str
    phone: str
    email: str | None
    comment: str
    consent: bool
    consent_version: str
    _items: list[InquiryItem]
    created_at: datetime

    def __post_init__(self) -> None:
        """Hold source-specific shape invariants on new and hydrated entities."""
        if self.source is InquirySource.SELECTION and not self._items:
            raise EmptyInquiryError
        if self.source is InquirySource.FREE_FORM and self._items:
            raise InvalidInquiryContentsError(message="A free-form inquiry cannot have items")
        if self.source is InquirySource.SELECTION and self.comment:
            raise InvalidInquiryContentsError(message="A selection inquiry cannot have a comment")
        self._items = list(self._items)

    @property
    def items(self) -> tuple[InquiryItem, ...]:
        """Return the item snapshots without exposing the aggregate collection."""
        return tuple(self._items)


@dataclass(frozen=True, slots=True)
class InquiryItemData:
    """A fully server-derived item snapshot ready to enter the aggregate."""

    product_id: ProductId
    product_name: str
    price_from: Money | None
    configuration: InquiryConfiguration | None
    calculated_price: Money | None
    verdict: PricingVerdict
    wish: str


@dataclass(frozen=True, slots=True)
class InquiryData:
    """Visitor-owned data for creating an inquiry."""

    source: InquirySource
    name: str
    phone: str
    email: str | None
    comment: str
    consent: bool
    consent_version: str
    items: tuple[InquiryItemData, ...]


def inquiry_factory(data: InquiryData, clock: Clock) -> Inquiry:
    """Create one inquiry and all of its private item snapshots at one instant."""
    ensure_new_inquiry_is_accepted(data.source, len(data.items), data.comment, consent=data.consent)

    now = clock.now()
    return Inquiry(
        id=uuid4(),
        source=data.source,
        name=data.name,
        phone=data.phone,
        email=data.email,
        comment=data.comment,
        consent=True,
        consent_version=data.consent_version,
        _items=[
            InquiryItem(
                id=uuid4(),
                product_id=item.product_id,
                product_name=item.product_name,
                price_from=item.price_from,
                configuration=item.configuration,
                calculated_price=item.calculated_price,
                verdict=item.verdict,
                wish=item.wish,
            )
            for item in data.items
        ],
        created_at=now,
    )


def ensure_new_inquiry_shape(source: InquirySource, item_count: int, comment: str) -> None:
    """Refuse source-specific input before an interactor reads other aggregates."""
    if source is InquirySource.PRODUCT_CARD:
        raise InquirySourceNotAcceptedError
    if source is InquirySource.SELECTION and item_count == 0:
        raise EmptyInquiryError
    if source is InquirySource.FREE_FORM and item_count > 0:
        raise InvalidInquiryContentsError(message="A free-form inquiry cannot have items")
    if source is InquirySource.SELECTION and comment:
        raise InvalidInquiryContentsError(message="A selection inquiry cannot have a comment")


def ensure_new_inquiry_is_accepted(
    source: InquirySource,
    item_count: int,
    comment: str,
    *,
    consent: bool,
) -> None:
    """Apply the new-inquiry rules in their observable refusal order."""
    if not consent:
        raise ConsentRequiredError
    ensure_new_inquiry_shape(source, item_count, comment)
