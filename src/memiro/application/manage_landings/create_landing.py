import structlog
from pydantic import BaseModel

from memiro.application.common.gateway.attribute import AttributeGateway
from memiro.application.common.gateway.category import CategoryGateway
from memiro.application.common.gateway.landing import LandingGateway
from memiro.application.errors.catalog import CategoryNotFoundError
from memiro.application.manage_landings.shared import (
    LandingCopyForm,
    ensure_the_address_is_free,
    narrowing_of,
)
from memiro.entities.catalog.landing.entity import CreateLandingData, landing_factory, settled_slug
from memiro.entities.common.identifiers import CategoryId, LandingId
from memiro_common.clock import Clock
from memiro_common.interactor import interactor
from memiro_common.logger import Logger
from memiro_common.uow import UoW

logger: Logger = structlog.get_logger(__name__)


class CreateLandingForm(LandingCopyForm):
    """Owner-controlled fields of the landing being created, its narrowing included."""

    category_id: CategoryId


class CreatedLanding(BaseModel):
    """Identifier of a newly created landing."""

    id: LandingId


@interactor
class CreateLanding:
    """Interactor for entering one indexable landing page into the storefront."""

    uow: UoW
    category_gateway: CategoryGateway
    attribute_gateway: AttributeGateway
    landing_gateway: LandingGateway
    clock: Clock

    async def execute(self, data: CreateLandingForm) -> CreatedLanding:
        """Create one landing with the narrowing it stands for and commit both in one transaction."""
        logger.debug("Creating a landing", category_id=data.category_id)
        if not await self.category_gateway.exists(data.category_id):
            logger.warning("A landing was created in an unknown category", category_id=data.category_id)
            raise CategoryNotFoundError
        conditions = await narrowing_of(self.attribute_gateway, data.conditions, category_id=data.category_id)
        await ensure_the_address_is_free(
            self.landing_gateway,
            settled_slug(data.slug, data.heading),
            except_landing=None,
        )
        landing = landing_factory(
            CreateLandingData(
                category_id=data.category_id,
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
        self.uow.add(landing)
        await self.uow.commit()
        logger.info("Landing created", landing_id=landing.id)
        return CreatedLanding(id=landing.id)
