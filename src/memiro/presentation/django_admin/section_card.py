"""What the section card fills in itself, having no interactor to fill it (ADR-0012, решение 3)."""

from datetime import datetime

from dishka import AsyncContainer

from memiro.presentation.django_admin.bridge import bridge
from memiro_common.clock import Clock


def stamped_now() -> datetime:
    """Take the moment a section is written from the one clock the process runs on."""
    return bridge().call(_now)


async def _now(scope: AsyncContainer) -> datetime:
    clock: Clock = await scope.get(Clock)
    return clock.now()
