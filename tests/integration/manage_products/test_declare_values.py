from decimal import Decimal
from uuid import uuid4

import pytest
from dishka import AsyncContainer
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.application.common.input_limits import MAX_QUANTITY, MAX_SELECTIONS
from memiro.application.errors.catalog import AttributeValueNotFoundError, ProductNotFoundError
from memiro.application.manage_products import DeclarationForm, DeclareValues, DeclareValuesForm
from memiro.entities.catalog.attribute.chosen_value import ChosenValue
from memiro.entities.catalog.product.entity import DeclaredValue
from memiro.entities.common.identifiers import AttributeId, AttributeValueId, ProductId
from tests.common.factory.catalog import (
    BLADE,
    CUTOUTS,
    FRAME,
    GRAPHITE,
    NO_FRAME,
    PRODUCT,
    SILVER,
)
from tests.integration.manage_products.arrange import declared_index, load_product
from tests.integration.prime import prime_numeric_catalog

pytestmark = pytest.mark.usefixtures("catalog")


def _form(*declarations: DeclarationForm) -> DeclareValuesForm:
    """Build the set the owner leaves on the card of the product."""
    return DeclareValuesForm(declarations=list(declarations))


def _row(
    attribute_id: AttributeId,
    value_id: AttributeValueId | None = None,
    quantity: Decimal | None = None,
) -> DeclarationForm:
    """Build one declaration as the card of the product submits it."""
    return DeclarationForm(attribute_id=attribute_id, value_id=value_id, quantity=quantity)


async def _declare(container: AsyncContainer, form: DeclareValuesForm, product_id: ProductId = PRODUCT) -> None:
    """Execute one declaration in its own production REQUEST scope."""
    async with container() as request:
        interactor = await request.get(DeclareValues)
        await interactor.execute(product_id, form)


async def test_the_owner_declares_what_the_product_is_made_of(container: AsyncContainer) -> None:
    """The set the owner left on the card is what the product declares."""
    await _declare(container, _form(_row(BLADE, GRAPHITE), _row(FRAME, NO_FRAME)))

    product = await load_product(container, PRODUCT)
    assert product is not None
    assert declared_index(product) == {
        BLADE: ChosenValue(value_id=GRAPHITE, quantity=None),
        FRAME: ChosenValue(value_id=NO_FRAME, quantity=None),
    }


async def test_an_attribute_left_out_of_the_set_is_no_longer_declared(container: AsyncContainer) -> None:
    """The set is replaced whole: what the owner did not name is unfilled again."""
    await _declare(container, _form(_row(BLADE, SILVER)))

    product = await load_product(container, PRODUCT)
    assert product is not None
    assert product.declared(FRAME) is None


async def test_an_empty_set_leaves_the_product_declaring_nothing(container: AsyncContainer) -> None:
    """A card submitted with every field cleared declares nothing at all."""
    await _declare(container, _form())

    product = await load_product(container, PRODUCT)
    assert product is not None
    assert product.declared_values == ()


async def test_a_numeric_attribute_is_declared_by_its_quantity(container: AsyncContainer, engine: AsyncEngine) -> None:
    """A numeric attribute carries a count, not a dictionary row."""
    await prime_numeric_catalog(engine)

    await _declare(container, _form(_row(CUTOUTS, quantity=Decimal("2.5"))))

    product = await load_product(container, PRODUCT)
    assert product is not None
    assert product.declared(CUTOUTS) == DeclaredValue(
        attribute_id=CUTOUTS,
        chosen=ChosenValue(value_id=None, quantity=Decimal("2.5")),
    )


async def test_declaring_values_fails_if_the_product_does_not_exist(container: AsyncContainer) -> None:
    """PRODUCT_NOT_FOUND: a card names a product that exists."""
    with pytest.raises(ProductNotFoundError):
        await _declare(container, _form(_row(BLADE, SILVER)), product_id=uuid4())


async def test_declaring_values_fails_on_a_value_of_another_attribute(container: AsyncContainer) -> None:
    """ATTRIBUTE_VALUE_NOT_FOUND: a value belongs to the attribute it is declared on."""
    with pytest.raises(AttributeValueNotFoundError):
        await _declare(container, _form(_row(BLADE, NO_FRAME)))


async def test_declaring_values_fails_on_an_attribute_nobody_issued(container: AsyncContainer) -> None:
    """ATTRIBUTE_VALUE_NOT_FOUND: a declaration names an attribute of the product's own section."""
    with pytest.raises(AttributeValueNotFoundError):
        await _declare(container, _form(_row(uuid4(), SILVER)))


async def test_declaring_values_fails_on_two_declarations_for_one_attribute() -> None:
    """VALIDATION_ERROR: a product declares one value per attribute of its section."""
    with pytest.raises(ValidationError):
        _form(_row(BLADE, SILVER), _row(BLADE, GRAPHITE))


async def test_declaring_values_fails_on_one_declaration_over_the_limit() -> None:
    """VALIDATION_ERROR: the form refuses more declarations than the production constant allows."""
    with pytest.raises(ValidationError):
        _form(*[_row(uuid4(), uuid4()) for _ in range(MAX_SELECTIONS + 1)])


async def test_declaring_values_fails_on_a_quantity_over_the_limit() -> None:
    """VALIDATION_ERROR: the form refuses a quantity larger than the production constant allows."""
    with pytest.raises(ValidationError):
        _row(CUTOUTS, quantity=MAX_QUANTITY + 1)


async def test_a_refused_declaration_leaves_the_set_as_it_was(container: AsyncContainer) -> None:
    """A refused command stores nothing: the product declares what it declared before."""
    before = await load_product(container, PRODUCT)
    assert before is not None

    with pytest.raises(AttributeValueNotFoundError):
        await _declare(container, _form(_row(BLADE, GRAPHITE), _row(FRAME, SILVER)))

    product = await load_product(container, PRODUCT)
    assert product is not None
    assert declared_index(product) == declared_index(before)
