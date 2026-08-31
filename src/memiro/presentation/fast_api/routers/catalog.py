from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from memiro.application.browse_catalog import (
    CategoryModel,
    ListCategories,
    ListCategoryProducts,
    ProductModel,
    ProductSummary,
    ReadProduct,
)

router = APIRouter(tags=["catalog"], route_class=DishkaRoute, prefix="/catalog")


@router.get("/categories")
async def list_categories(interactor: FromDishka[ListCategories]) -> list[CategoryModel]:
    """HTTP endpoint for public category listing."""
    return list(await interactor.execute())


@router.get("/categories/{slug}/products")
async def list_products(slug: str, interactor: FromDishka[ListCategoryProducts]) -> list[ProductSummary]:
    """HTTP endpoint for one category's products."""
    return list(await interactor.execute(slug))


@router.get("/products/{slug}")
async def read_product(slug: str, interactor: FromDishka[ReadProduct]) -> ProductModel:
    """HTTP endpoint for one public product card."""
    return await interactor.execute(slug)
