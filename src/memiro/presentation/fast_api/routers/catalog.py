from typing import Annotated

from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter, Query

from memiro.application.browse_catalog import (
    CatalogQuery,
    CategoriesList,
    LandingModel,
    LandingsList,
    ListCategories,
    ListCategoryProducts,
    ListLandings,
    ProductModel,
    ProductsList,
    ReadLanding,
    ReadProduct,
)

router = APIRouter(tags=["catalog"], route_class=DishkaRoute, prefix="/catalog")


@router.get("/categories")
async def list_categories(interactor: FromDishka[ListCategories]) -> CategoriesList:
    """HTTP endpoint for public category listing."""
    return await interactor.execute()


@router.get("/categories/{slug}/products")
async def list_products(
    slug: str,
    interactor: FromDishka[ListCategoryProducts],
    query: Annotated[CatalogQuery, Query()],
) -> ProductsList:
    """HTTP endpoint for one category's products, narrowed and ordered by the visitor."""
    return await interactor.execute(slug, query)


@router.get("/landings")
async def list_landings(interactor: FromDishka[ListLandings]) -> LandingsList:
    """HTTP endpoint for the published landing pages."""
    return await interactor.execute()


@router.get("/landings/{slug}")
async def read_landing(slug: str, interactor: FromDishka[ReadLanding]) -> LandingModel:
    """HTTP endpoint for one landing page."""
    return await interactor.execute(slug)


@router.get("/products/{slug}")
async def read_product(slug: str, interactor: FromDishka[ReadProduct]) -> ProductModel:
    """HTTP endpoint for one public product card."""
    return await interactor.execute(slug)
