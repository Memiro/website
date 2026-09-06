"""What the attribute card sends: the owner's form as the commands of the aggregate (ADR-0012)."""

from collections.abc import Callable, Coroutine, Mapping, Sequence
from typing import Any

from dishka import AsyncContainer

from memiro.application.manage_attributes import (
    AttributeValueForm,
    ChangeAttribute,
    ChangeAttributeForm,
    CreateAttribute,
    CreateAttributeForm,
    CreatedAttribute,
    RemoveAttribute,
    ReplacementValueForm,
    ReplaceValues,
    ReplaceValuesForm,
)
from memiro.entities.catalog.attribute.entity import AttributeKind
from memiro.entities.catalog.attribute.rate import Unit
from memiro.entities.common.identifiers import AttributeId, AttributeValueId
from memiro.presentation.django_admin.bridge import bridge
from memiro.presentation.django_admin.writes import record_commit


def create_attribute(root: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> AttributeId:
    """Send the card of a new attribute as the one command that creates it with its dictionary."""
    form = CreateAttributeForm(
        category_id=root["category"].id,
        values=[AttributeValueForm(**_row_fields(row)) for row in rows],
        **_root_fields(root),
    )
    created: CreatedAttribute = _sent(lambda scope: _create(scope, form))
    return created.id


def restate_attribute(
    attribute_id: AttributeId,
    root: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> None:
    """Send the card of a saved attribute: the dictionary first, the root after.

    The halves are two commands of one aggregate, and the dictionary goes
    first on purpose — a set the domain refuses leaves the card exactly as the
    owner found it, root included.
    """
    values = ReplaceValuesForm(
        values=[ReplacementValueForm(id=_kept_row(row), **_row_fields(row)) for row in rows],
    )
    _sent(lambda scope: _replace(scope, attribute_id, values))
    _sent(lambda scope: _change(scope, attribute_id, ChangeAttributeForm(**_root_fields(root))))


def remove_attribute(attribute_id: AttributeId) -> None:
    """Send one attribute to the command that removes it together with its dictionary."""
    _sent(lambda scope: _remove(scope, attribute_id))


def _root_fields(root: Mapping[str, Any]) -> dict[str, Any]:
    """Read the root half of the card in the words of the application form."""
    return {
        "name": root["name"],
        # The mirror stores the member name of the domain enum and offers it as
        # a choice; the application form speaks the enum itself.
        "kind": AttributeKind[root["kind"]],
        "parent_ids": [parent.id for parent in root["parents"]],
        "is_customer_changeable": root["is_customer_changeable"],
        "is_filterable": root["is_filterable"],
        "sort_order": root["sort_order"],
    }


def _row_fields(row: Mapping[str, Any]) -> dict[str, Any]:
    """Read one inline row of the card in the words of the application form."""
    return {
        "name": row["name"],
        "rate_amount": row["rate_amount"],
        "rate_unit": Unit[row["rate_unit"]],
        "scaled_by_shape": row["scaled_by_shape"],
        "scaled_by_size_surcharge": row["scaled_by_size_surcharge"],
        "marks_absence": row["marks_absence"],
        "sort_order": row["sort_order"],
    }


def _kept_row(row: Mapping[str, Any]) -> AttributeValueId | None:
    """Name the dictionary row this one keeps, or nothing if the owner typed it fresh."""
    kept = row.get("id")
    return None if kept is None else kept.id


async def _create(scope: AsyncContainer, form: CreateAttributeForm) -> CreatedAttribute:
    interactor = await scope.get(CreateAttribute)
    return await interactor.execute(form)


async def _change(scope: AsyncContainer, attribute_id: AttributeId, form: ChangeAttributeForm) -> None:
    interactor = await scope.get(ChangeAttribute)
    await interactor.execute(attribute_id, form)


async def _replace(scope: AsyncContainer, attribute_id: AttributeId, form: ReplaceValuesForm) -> None:
    interactor = await scope.get(ReplaceValues)
    await interactor.execute(attribute_id, form)


async def _remove(scope: AsyncContainer, attribute_id: AttributeId) -> None:
    interactor = await scope.get(RemoveAttribute)
    await interactor.execute(attribute_id)


def _sent[T](command: Callable[[AsyncContainer], Coroutine[Any, Any, T]]) -> T:
    """Send one command across the bridge and remember that it reached the domain."""
    result = bridge().call(command)
    record_commit()
    return result
