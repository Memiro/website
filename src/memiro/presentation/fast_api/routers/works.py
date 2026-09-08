from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from memiro.application.browse_catalog import ListWorks, WorksList

router = APIRouter(tags=["works"], route_class=DishkaRoute, prefix="/works")


@router.get("")
async def list_works(interactor: FromDishka[ListWorks]) -> WorksList:
    """HTTP endpoint for the gallery of photographed installations."""
    return await interactor.execute()
