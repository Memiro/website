import asyncio

import pytest
from dishka import AsyncContainer
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.application.manage_landings import CreatedLanding
from tests.integration.manage_landings.arrange import create_form, create_landing
from tests.integration.prime import count_landings_directly

pytestmark = pytest.mark.usefixtures("catalog")

# One address, two competitors: the storefront keeps the winner's page alone.
STOREFRONT_AFTER_THE_RACE = 1


async def test_two_landings_racing_for_one_address_leave_one_winner(
    container: AsyncContainer,
    engine: AsyncEngine,
) -> None:
    """The unique column settles the race the check cannot see: the loser is told to retry."""
    form = create_form(slug="zerkala-bliznecy")

    outcomes = await asyncio.gather(
        create_landing(container, form),
        create_landing(container, form),
        return_exceptions=True,
    )

    # Either road ends the race honestly: the loser's check sees the winner's
    # row, or the unique column refuses the loser's insert.
    assert sorted(isinstance(outcome, CreatedLanding) for outcome in outcomes) == [False, True]
    assert await count_landings_directly(engine) == STOREFRONT_AFTER_THE_RACE
