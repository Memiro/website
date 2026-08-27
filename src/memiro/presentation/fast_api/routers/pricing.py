from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from memiro.application.calculate_price import CalculatedPrice, CalculatePrice, CalculatePriceForm

# nginx serves this router under /api, so the public address of the endpoint
# is /api/calculate; the prefix carries the whole path (§10.1).
router = APIRouter(tags=["pricing"], route_class=DishkaRoute, prefix="/calculate")


@router.post("")
async def calculate_price(
    interactor: FromDishka[CalculatePrice],
    data: CalculatePriceForm,
) -> CalculatedPrice:
    """HTTP endpoint for pricing one configuration of a product."""
    return await interactor.execute(data)
