"""What the list of products sends by hand: the very handler the domain events run (ADR-0014)."""

from dishka import AsyncContainer

from memiro.application.common.event import DispatchLog
from memiro.application.reprice_products import RepriceProducts
from memiro.presentation.django_admin.writes import send


def reprice_catalogue() -> None:
    """Reprice the whole catalogue at the owner's own command, banner included."""
    send(_repriced)


async def _repriced(scope: AsyncContainer) -> None:
    """Run the handler and leave its tally where the banner of the screen reads it."""
    interactor = await scope.get(RepriceProducts)
    dispatch_log = await scope.get(DispatchLog)
    dispatch_log.record(await interactor.execute())
