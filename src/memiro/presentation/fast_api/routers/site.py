from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from memiro.application.read_site import ReadSite, SiteModel

router = APIRouter(tags=["site"], route_class=DishkaRoute, prefix="/site")


@router.get("")
async def read_site(interactor: FromDishka[ReadSite]) -> SiteModel:
    """HTTP endpoint for the studio's contacts and the seller's requisites."""
    return await interactor.execute()
