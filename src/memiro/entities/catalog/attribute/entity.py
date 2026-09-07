from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum, auto
from uuid import uuid4

from memiro.entities.catalog.attribute.chosen_value import ChosenValue
from memiro.entities.catalog.attribute.rate import Rate
from memiro.entities.common.entity import Entity
from memiro.entities.common.identifiers import AttributeId, AttributeValueId, CategoryId
from memiro.entities.errors.attribute import InvalidAttributeValueSetError
from memiro_common.clock import Clock


class AttributeKind(StrEnum):
    """How a customer configures an attribute."""

    SELECT = auto()
    NUMBER = auto()


def _ensure_the_kind_fits_the_dictionary(kind: AttributeKind, size: int) -> None:
    """Hold the one rule the kind and the dictionary share: a number is charged by one tariff."""
    if kind is AttributeKind.NUMBER and size != 1:
        raise InvalidAttributeValueSetError(
            message="A numeric attribute needs exactly one tariff row",
        )


@dataclass
class AttributeValue(Entity):
    """A dictionary row of an attribute: "silver", "no frame", "cut-out".

    The row both describes the product and forms its price: the tariff lives
    here and nowhere else (ADR-0007).
    """

    id: AttributeValueId
    name: str
    rate: Rate
    scaled_by_shape: bool
    sort_order: int
    marks_absence: bool = False
    scaled_by_size_surcharge: bool = False

    def is_present(self) -> bool:
        """Tell whether this row names a feature the product actually has."""
        return not self.marks_absence

    def restate(self, data: "AttributeValueData") -> None:
        """Take the owner's new wording, tariff and place for this dictionary row."""
        self.name = data.name
        self.rate = data.rate
        self.scaled_by_shape = data.scaled_by_shape
        self.scaled_by_size_surcharge = data.scaled_by_size_surcharge
        self.marks_absence = data.marks_absence
        self.sort_order = data.sort_order


@dataclass(frozen=True, slots=True)
class AttributeValueData:
    """Owner-controlled fields of one dictionary row."""

    name: str
    rate: Rate
    scaled_by_shape: bool
    scaled_by_size_surcharge: bool
    marks_absence: bool
    sort_order: int


@dataclass(frozen=True, slots=True)
class ReplacementValueData:
    """One row of a replacement set: the dictionary row it keeps, or nothing if it is a new one."""

    # The identifier is what tells an edit from an addition, and it is never
    # invented here: a row the owner names keeps the identifier products
    # declare, a row without one is born inside the aggregate.
    id: AttributeValueId | None
    data: AttributeValueData


@dataclass(frozen=True, slots=True)
class CreateAttributeData:
    """Owner-controlled fields of an attribute being created, dictionary included."""

    category_id: CategoryId
    name: str
    kind: AttributeKind
    parent_ids: tuple[AttributeId, ...]
    is_customer_changeable: bool
    is_filterable: bool
    sort_order: int
    values: tuple[AttributeValueData, ...]


@dataclass(frozen=True, slots=True)
class ChangeAttributeData:
    """Owner-controlled root fields of an attribute being changed."""

    # No category: an attribute does not move between sections of the
    # catalogue, and the dictionary is replaced by its own command.

    name: str
    kind: AttributeKind
    parent_ids: tuple[AttributeId, ...]
    is_customer_changeable: bool
    is_filterable: bool
    sort_order: int


@dataclass
class Attribute(Entity):
    """A characteristic of a product, kept in the admin dictionary.

    Aggregate root; the dictionary rows are its children, and the set is
    replaced whole by ``replace_values`` rather than edited row by row.
    """

    id: AttributeId
    category_id: CategoryId
    name: str
    sort_order: int
    values: list[AttributeValue] = field(default_factory=list[AttributeValue])
    kind: AttributeKind = AttributeKind.SELECT
    parent_ids: tuple[AttributeId, ...] = ()
    is_customer_changeable: bool = True
    # A filter narrows the catalogue by what tells products apart. The blade
    # is not such a thing: any mirror is made of any blade, and a "silver /
    # graphite" group would hide products that do fit. Separate from
    # customer-changeability: the mount and the heating are changed by the
    # customer too, and narrowing by them makes sense.
    is_filterable: bool = True
    created_at: datetime = field(kw_only=True)
    updated_at: datetime = field(kw_only=True)

    def __post_init__(self) -> None:
        """Hold dictionary shape invariants and detach parent identifiers."""
        if self.kind is AttributeKind.NUMBER and len(self.values) != 1:
            msg = f"Numeric attribute {self.id} needs exactly one tariff row"
            raise RuntimeError(msg)
        self.parent_ids = tuple(self.parent_ids)

    def change(self, data: ChangeAttributeData, *, clock: Clock) -> None:
        """Replace the root fields of the attribute, holding the shape its dictionary must keep."""
        _ensure_the_kind_fits_the_dictionary(data.kind, len(self.values))
        self.name = data.name
        self.kind = data.kind
        self.parent_ids = tuple(data.parent_ids)
        self.is_customer_changeable = data.is_customer_changeable
        self.is_filterable = data.is_filterable
        self.sort_order = data.sort_order
        self.updated_at = clock.now()

    def replace_values(self, values: Sequence[ReplacementValueData], *, clock: Clock) -> None:
        """Replace the whole dictionary of the attribute with the set the owner submitted."""
        self._ensure_the_set_describes_this_attribute(values)
        rows = {value.id: value for value in self.values}
        replacement: list[AttributeValue] = []
        for value in values:
            row = rows.get(value.id) if value.id is not None else None
            if row is None:
                row = attribute_value_factory(value.data)
            else:
                row.restate(value.data)
            replacement.append(row)
        # The collection is edited in place, not rebound: the ORM watches this
        # very list to learn which rows left the dictionary and must be deleted.
        self.values[:] = replacement
        self.updated_at = clock.now()

    def values_absent_from(self, replacement: Sequence[ReplacementValueData]) -> tuple[AttributeValueId, ...]:
        """Tell which dictionary rows a replacement set would remove, refusing a set that is not ours."""
        # Asked before storage is asked who uses the rows, so the refusal for
        # an impossible set comes out ahead of the one for a row still declared.
        self._ensure_the_set_describes_this_attribute(replacement)
        kept = {value.id for value in replacement if value.id is not None}
        return tuple(value.id for value in self.values if value.id not in kept)

    def _ensure_the_set_describes_this_attribute(self, values: Sequence[ReplacementValueData]) -> None:
        """Refuse a set naming a row twice, a row of somebody else, or the wrong number of rows."""
        _ensure_the_kind_fits_the_dictionary(self.kind, len(values))
        named = [value.id for value in values if value.id is not None]
        if len(set(named)) != len(named):
            raise InvalidAttributeValueSetError(
                message="A replacement set cannot name one dictionary row twice",
            )
        if not set(named) <= {value.id for value in self.values}:
            raise InvalidAttributeValueSetError(
                message="A replacement set can only keep rows of this attribute",
            )

    def value(self, value_id: AttributeValueId) -> AttributeValue | None:
        """Find a dictionary row of this attribute, or report that it is not one."""
        return next((value for value in self.values if value.id == value_id), None)

    def row_of(self, chosen: ChosenValue) -> AttributeValue | None:
        """Return the dictionary row a chosen value is charged by, or nothing if it is not one."""
        if self.kind is AttributeKind.NUMBER:
            # The constructor holds the single-row invariant, but the ORM
            # hydrates an aggregate without running it (§12.3).
            if len(self.values) != 1:
                msg = f"Numeric attribute {self.id} needs exactly one tariff row"
                raise RuntimeError(msg)
            if chosen.value_id is not None or chosen.quantity is None:
                return None
            return self.values[0]
        if chosen.value_id is None or chosen.quantity is not None:
            return None
        return self.value(chosen.value_id)

    def configure(self, value_id: AttributeValueId | None, quantity: Decimal | None) -> ChosenValue | None:
        """Turn one row of a form into a value of this attribute, or refuse a choice that is not one."""
        if value_id is not None and quantity is not None:
            return None
        chosen = ChosenValue(value_id=value_id, quantity=quantity)
        return chosen if self.row_of(chosen) is not None else None


def attribute_value_factory(data: AttributeValueData) -> AttributeValue:
    """Create one dictionary row under an identifier nobody outside could forge."""
    return AttributeValue(
        id=uuid4(),
        name=data.name,
        rate=data.rate,
        scaled_by_shape=data.scaled_by_shape,
        sort_order=data.sort_order,
        marks_absence=data.marks_absence,
        scaled_by_size_surcharge=data.scaled_by_size_surcharge,
    )


def attribute_factory(data: CreateAttributeData, *, clock: Clock) -> Attribute:
    """Create an attribute with its dictionary; both dates come from one reading of the clock."""
    _ensure_the_kind_fits_the_dictionary(data.kind, len(data.values))
    now = clock.now()
    return Attribute(
        id=uuid4(),
        category_id=data.category_id,
        name=data.name,
        sort_order=data.sort_order,
        values=[attribute_value_factory(value) for value in data.values],
        kind=data.kind,
        parent_ids=tuple(data.parent_ids),
        is_customer_changeable=data.is_customer_changeable,
        is_filterable=data.is_filterable,
        created_at=now,
        updated_at=now,
    )
