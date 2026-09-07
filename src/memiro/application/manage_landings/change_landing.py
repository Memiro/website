import structlog

from memiro.application.common.gateway.attribute import AttributeGateway
from memiro.application.common.gateway.landing import LandingGateway
from memiro.application.manage_landings.shared import (
    LandingCopyForm,
    ensure_the_address_is_free,
    loaded_for_update,
    narrowing_of,
)
from memiro.entities.catalog.landing.entity import ChangeLandingData, settled_slug
from memiro.entities.common.identifiers import LandingId
from memiro_common.clock import Clock
from memiro_common.interactor import interactor
from memiro_common.logger import Logger
from memiro_common.uow import UoW

logger: Logger = structlog.get_logger(__name__)


class ChangeLandingForm(LandingCopyForm):
    """Owner-controlled fields of a saved landing: the category it narrows is not among them."""


@interactor
class ChangeLanding:
    """Interactor for restating one landing page and the narrowing it stands for."""

    uow: UoW
    attribute_gateway: AttributeGateway
    landing_gateway: LandingGateway
    clock: Clock

    async def execute(self, landing_id: LandingId, data: ChangeLandingForm) -> None:
        """Restate the copy and the narrowing of one landing in a single transaction."""
        logger.debug("Changing a landing", landing_id=landing_id)
        landing = await loaded_for_update(self.landing_gateway, landing_id, command="change")
        conditions = await narrowing_of(
            self.attribute_gateway,
            data.conditions,
            category_id=landing.category_id,
        )
        await ensure_the_address_is_free(
            self.landing_gateway,
            settled_slug(data.slug, data.heading),
            except_landing=landing_id,
        )
        landing.change(
            ChangeLandingData(
                slug=data.slug,
                title=data.title,
                heading=data.heading,
                description=data.description,
                text=data.text,
                is_published=data.is_published,
                sort_order=data.sort_order,
            ),
            clock=self.clock,
        )
        landing.narrow_by(conditions, clock=self.clock)
        await self.uow.commit()
        logger.info("Landing changed", landing_id=landing_id)
