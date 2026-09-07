"""What the product card sends: the owner's form as the commands of the aggregate (ADR-0012)."""

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from dishka import AsyncContainer

from memiro.application.manage_products import (
    ChangeProduct,
    ChangeProductForm,
    CreatedProduct,
    CreateProduct,
    CreateProductForm,
    DeclarationForm,
    DeclareValues,
    DeclareValuesForm,
    ListPricingGaps,
    PricingGapsModel,
    RemoveProduct,
)
from memiro.entities.common.identifiers import AttributeValueId, ProductId
from memiro.presentation.django_admin.bridge import bridge
from memiro.presentation.django_admin.forms import DECLARED_PREFIX, declared_attribute_id
from memiro.presentation.django_admin.writes import send


def create_product(card: Mapping[str, Any]) -> ProductId:
    """Send the card of a new product as the command that enters it into its section."""
    form = CreateProductForm(**_root_fields(card))
    created: CreatedProduct = send(lambda scope: _create(scope, form))
    return created.id


def restate_product(product_id: ProductId, card: Mapping[str, Any]) -> None:
    """Send the card of a saved product: the root first, the declared set after.

    The halves are two commands of one aggregate, and the root goes first on
    purpose — what a product may declare is decided by its section, and the
    section must already be the one the owner chose.
    """
    send(lambda scope: _change(scope, product_id, ChangeProductForm(**_root_fields(card))))
    declared = DeclareValuesForm(declarations=_declarations(card))
    send(lambda scope: _declare(scope, product_id, declared))


def remove_product(product_id: ProductId) -> None:
    """Send one product to the command that removes it with everything that belongs to it."""
    send(lambda scope: _remove(scope, product_id))


def pricing_gaps_of(product_ids: Sequence[ProductId]) -> dict[ProductId, PricingGapsModel]:
    """Ask what the products of one page still lack before the calculator prices them."""
    return bridge().call(lambda scope: _gaps(scope, product_ids))


def _root_fields(card: Mapping[str, Any]) -> dict[str, Any]:
    """Read the root half of the card in the words of the application form."""
    return {
        "category_id": card["category"].id,
        "name": card["name"],
        "slug": card["slug"],
        "description": card["description"],
        "is_published": card["is_published"],
        "hides_calculated_price": card["hides_calculated_price"],
    }


def _declarations(card: Mapping[str, Any]) -> list[DeclarationForm]:
    """Read the declared half of the card: one field per attribute, an empty one meaning "not filled in"."""
    declared: list[DeclarationForm] = []
    for field, chosen in card.items():
        if not field.startswith(DECLARED_PREFIX) or chosen is None:
            continue
        attribute_id = declared_attribute_id(field)
        if isinstance(chosen, Decimal):
            declared.append(DeclarationForm(attribute_id=attribute_id, quantity=chosen))
            continue
        value_id: AttributeValueId = chosen.pk
        declared.append(DeclarationForm(attribute_id=attribute_id, value_id=value_id))
    return declared


async def _create(scope: AsyncContainer, form: CreateProductForm) -> CreatedProduct:
    interactor = await scope.get(CreateProduct)
    return await interactor.execute(form)


async def _change(scope: AsyncContainer, product_id: ProductId, form: ChangeProductForm) -> None:
    interactor = await scope.get(ChangeProduct)
    await interactor.execute(product_id, form)


async def _declare(scope: AsyncContainer, product_id: ProductId, form: DeclareValuesForm) -> None:
    interactor = await scope.get(DeclareValues)
    await interactor.execute(product_id, form)


async def _remove(scope: AsyncContainer, product_id: ProductId) -> None:
    interactor = await scope.get(RemoveProduct)
    await interactor.execute(product_id)


async def _gaps(scope: AsyncContainer, product_ids: Sequence[ProductId]) -> dict[ProductId, PricingGapsModel]:
    interactor = await scope.get(ListPricingGaps)
    return await interactor.execute(product_ids)
