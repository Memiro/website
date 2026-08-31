from decimal import Decimal
from typing import TypedDict, override
from uuid import UUID

from sqlalchemy import Dialect, Integer, Numeric, Uuid
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.types import TypeDecorator

from memiro.entities.catalog.product.entity import ConfiguredValue, DeclaredValue, VariantOverrides
from memiro.entities.common.identifiers import AttributeId
from memiro.entities.common.measure import Area, Dimensions, Millimeters
from memiro.entities.common.money import Money
from memiro.entities.errors.product import InvalidVariantConfigurationError
from memiro.entities.inquiry.entity import ConfigurationValue, InquiryConfiguration

# Money is stored to the kopeck; the area of a mirror to the fourth decimal —
# a square millimetre. Both deserialize through the domain constructor, so a
# corrupted row never loads silently (§8.5).
_MONEY = Numeric(12, 2)
_AREA = Numeric(10, 4)
type VariantOverridePayload = dict[str, str | None]


class InquiryConfigurationValuePayload(TypedDict):
    """Serialized named customer selection in one inquiry snapshot."""

    attribute_name: str
    value_name: str | None
    quantity: str | None


class InquiryConfigurationPayload(TypedDict):
    """Serialized immutable configuration stored in JSONB."""

    width_mm: int
    height_mm: int
    values: list[InquiryConfigurationValuePayload]


class MoneyType(TypeDecorator[Money]):
    """Column type storing ``Money`` as a fixed-point number of roubles."""

    impl = _MONEY
    cache_ok = True

    @override
    def process_bind_param(self, value: Money | None, dialect: Dialect) -> Decimal | None:
        """Flatten the sum into the column."""
        return None if value is None else value.amount

    @override
    def process_result_value(self, value: Decimal | None, dialect: Dialect) -> Money | None:
        """Rebuild the sum through the domain constructor."""
        return None if value is None else Money(amount=value)


class AreaType(TypeDecorator[Area]):
    """Column type storing ``Area`` as a fixed-point number of square metres."""

    impl = _AREA
    cache_ok = True

    @override
    def process_bind_param(self, value: Area | None, dialect: Dialect) -> Decimal | None:
        """Flatten the area into the column."""
        return None if value is None else value.value

    @override
    def process_result_value(self, value: Decimal | None, dialect: Dialect) -> Area | None:
        """Rebuild the area through the domain constructor."""
        return None if value is None else Area(value=value)


class AttributeIdsType(TypeDecorator[tuple[AttributeId, ...]]):
    """Column type storing immutable attribute identifiers as a PostgreSQL UUID array."""

    impl = ARRAY(Uuid())
    cache_ok = True

    @override
    def process_bind_param(self, value: tuple[AttributeId, ...] | None, dialect: Dialect) -> list[UUID] | None:
        """Flatten the immutable domain collection into an array."""
        return None if value is None else list(value)

    @override
    def process_result_value(self, value: list[UUID] | None, dialect: Dialect) -> tuple[AttributeId, ...] | None:
        """Expose an immutable tuple when hydrating the domain entity."""
        return None if value is None else tuple(value)


class MillimetersType(TypeDecorator[Millimeters]):
    """Column type storing ``Millimeters`` as its integer value."""

    impl = Integer
    cache_ok = True

    @override
    def process_bind_param(self, value: Millimeters | None, dialect: Dialect) -> int | None:
        """Flatten the limit into the column."""
        return None if value is None else value.value

    @override
    def process_result_value(self, value: int | None, dialect: Dialect) -> Millimeters | None:
        """Rebuild the limit through the domain constructor."""
        return None if value is None else Millimeters(value=value)


class VariantOverridesType(TypeDecorator[VariantOverrides]):
    """Column type storing a variant's immutable override set as canonical JSONB."""

    impl = JSONB
    cache_ok = True

    @override
    def process_bind_param(
        self,
        value: VariantOverrides | None,
        dialect: Dialect,
    ) -> list[VariantOverridePayload] | None:
        """Flatten and sort overrides so equal sets have one database representation."""
        if value is None:
            return None
        return [
            {
                "attribute_id": str(override.attribute_id),
                "value_id": (str(override.configured.value_id) if override.configured.value_id is not None else None),
                "quantity": (
                    format(override.configured.quantity.normalize(), "f")
                    if override.configured.quantity is not None
                    else None
                ),
            }
            for override in sorted(value, key=lambda item: str(item.attribute_id))
        ]

    @override
    def process_result_value(
        self,
        value: list[VariantOverridePayload] | None,
        dialect: Dialect,
    ) -> VariantOverrides | None:
        """Rebuild every override through its domain constructors."""
        if value is None:
            return None

        try:
            return VariantOverrides(
                DeclaredValue(
                    attribute_id=UUID(payload["attribute_id"] or ""),
                    configured=ConfiguredValue(
                        value_id=UUID(payload["value_id"]) if payload["value_id"] is not None else None,
                        quantity=Decimal(payload["quantity"]) if payload["quantity"] is not None else None,
                    ),
                )
                for payload in value
            )
        except (
            ArithmeticError,
            AttributeError,
            InvalidVariantConfigurationError,
            KeyError,
            TypeError,
            ValueError,
        ) as error:
            message = "Stored product variant has corrupted variant overrides"
            raise RuntimeError(message) from error


class InquiryConfigurationType(TypeDecorator[InquiryConfiguration]):
    """Column type storing an inquiry configuration as its self-contained JSONB snapshot."""

    impl = JSONB
    cache_ok = True

    @override
    def process_bind_param(
        self,
        value: InquiryConfiguration | None,
        dialect: Dialect,
    ) -> InquiryConfigurationPayload | None:
        """Flatten the snapshot without retaining dictionary identifiers."""
        if value is None:
            return None
        return {
            "width_mm": value.dimensions.width.value,
            "height_mm": value.dimensions.height.value,
            "values": [
                {
                    "attribute_name": configured.attribute_name,
                    "value_name": configured.value_name,
                    "quantity": (
                        format(configured.quantity.normalize(), "f") if configured.quantity is not None else None
                    ),
                }
                for configured in value.values
            ],
        }

    @override
    def process_result_value(
        self,
        value: InquiryConfigurationPayload | None,
        dialect: Dialect,
    ) -> InquiryConfiguration | None:
        """Rebuild snapshots through the domain constructors when rows are loaded."""
        if value is None:
            return None
        try:
            return InquiryConfiguration(
                dimensions=Dimensions(
                    width=Millimeters(value["width_mm"]),
                    height=Millimeters(value["height_mm"]),
                ),
                values=tuple(
                    ConfigurationValue(
                        attribute_name=str(configured["attribute_name"]),
                        value_name=configured["value_name"],
                        quantity=Decimal(configured["quantity"]) if configured["quantity"] is not None else None,
                    )
                    for configured in value["values"]
                ),
            )
        except (ArithmeticError, KeyError, TypeError, ValueError) as error:
            message = "Stored inquiry has a corrupted configuration snapshot"
            raise RuntimeError(message) from error
