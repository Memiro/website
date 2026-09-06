"""Publication strictly after the commit: the tariff lands, and only then are prices recalculated (ADR-0014)."""

from decimal import Decimal

import pytest
from dishka import AsyncContainer
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.application.common.dispatch_log import DispatchLog
from memiro.application.common.gateway.attribute import AttributeGateway
from memiro.application.manage_attributes import ReplacementValueForm, ReplaceValues, ReplaceValuesForm
from memiro.application.manage_pricing_settings import ChangePricingSettings, ChangePricingSettingsForm
from memiro.entities.catalog.attribute.rate import Unit
from memiro.entities.common.money import Money
from tests.common.factory.catalog import MOUNT, NO_MOUNT, WITH_MOUNT
from tests.integration.prime import prime_no_pricing_settings
from tests.integration.reprice_products.arrange import arranged_variant, prices_after

pytestmark = pytest.mark.usefixtures("catalog")

SMALL_BEFORE = Money(amount=Decimal(8900))
SMALL_AFTER = Money(amount=Decimal(9900))
RAISED_TO_THE_MINIMUM_ORDER = Money(amount=Decimal(20000))
DEARER_MOUNT = Money(amount=Decimal(1500))

MAX_LONG_SIDE_MM = 3000
MAX_SHORT_SIDE_MM = 2000


def _dearer_mount() -> ReplaceValuesForm:
    """Spell the mount dictionary with the piece priced at 1 500 instead of 500."""
    return ReplaceValuesForm(
        values=[
            ReplacementValueForm(
                id=WITH_MOUNT,
                name="Крепление",
                rate_amount=DEARER_MOUNT.amount,
                rate_unit=Unit.PIECE,
                sort_order=1,
            ),
            ReplacementValueForm(
                id=NO_MOUNT,
                name="Без крепления",
                rate_amount=Decimal(0),
                rate_unit=Unit.PIECE,
                marks_absence=True,
                sort_order=2,
            ),
        ],
    )


def _raised_minimum_order() -> ChangePricingSettingsForm:
    """Spell the calculation parameters with an order minimum above every demo variant."""
    return ChangePricingSettingsForm(
        min_area=Decimal("0.25"),
        min_order_total=RAISED_TO_THE_MINIMUM_ORDER.amount,
        max_long_side_mm=MAX_LONG_SIDE_MM,
        max_short_side_mm=MAX_SHORT_SIDE_MM,
        surcharges=[],
    )


async def _mount_tariff(container: AsyncContainer) -> Money:
    """Read the stored price of one mount back in a fresh transaction."""
    async with container() as request:
        gateway: AttributeGateway = await request.get(AttributeGateway)
        mount = await gateway.get(MOUNT)
    assert mount is not None
    value = mount.value(WITH_MOUNT)
    assert value is not None
    return value.rate.amount


async def test_a_saved_tariff_reprices_the_catalogue_in_the_same_request(container: AsyncContainer) -> None:
    """``TariffChanged`` is published after the commit and its subscriber reprices at once."""
    await arranged_variant(container, width_mm=800, height_mm=600)

    async with container() as request:
        interactor = await request.get(ReplaceValues)
        await interactor.execute(MOUNT, _dearer_mount())

    assert await prices_after(container) == (SMALL_AFTER,)


async def test_saved_calculation_parameters_reprice_the_catalogue_in_the_same_request(
    container: AsyncContainer,
) -> None:
    """``PricingSettingsChanged`` is published after the commit and its subscriber reprices at once."""
    await arranged_variant(container, width_mm=800, height_mm=600)

    async with container() as request:
        interactor = await request.get(ChangePricingSettings)
        await interactor.execute(_raised_minimum_order())

    assert await prices_after(container) == (RAISED_TO_THE_MINIMUM_ORDER,)


async def test_the_publication_reports_how_many_products_it_repriced(container: AsyncContainer) -> None:
    """The screen that saved the tariff is told the number of products behind the banner."""
    await arranged_variant(container, width_mm=800, height_mm=600)

    async with container() as request:
        interactor = await request.get(ReplaceValues)
        await interactor.execute(MOUNT, _dearer_mount())
        log = await request.get(DispatchLog)

    assert log == DispatchLog(repriced_products=1, repricing_ran=True)


async def test_a_failed_reprice_does_not_roll_back_the_tariff_it_followed(
    container: AsyncContainer,
    engine: AsyncEngine,
) -> None:
    """The subscriber ran after the transaction of the change ended: its failure is a warning, not a rollback."""
    await arranged_variant(container, width_mm=800, height_mm=600)
    await prime_no_pricing_settings(engine)

    async with container() as request:
        interactor = await request.get(ReplaceValues)
        await interactor.execute(MOUNT, _dearer_mount())
        log = await request.get(DispatchLog)

    assert log == DispatchLog(repriced_products=0, failed=True)
    assert await _mount_tariff(container) == DEARER_MOUNT
    assert await prices_after(container) == (SMALL_BEFORE,)
