from typing import Literal

from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["internal"], route_class=DishkaRoute, prefix="/internal")


class HealthStatus(BaseModel):
    """Health probe response."""

    status: Literal["ok"]


@router.get("/alive")
async def alive() -> HealthStatus:
    """Report that the process is up and serving requests."""
    return HealthStatus(status="ok")


@router.get("/ready")
async def ready(session: FromDishka[AsyncSession]) -> HealthStatus:
    """Report readiness by taking a session from DI and touching the database."""
    # Deliberate §10.2 deviation: readiness is infrastructure, not a use case —
    # an interactor here would put probe SQL into the application layer for no
    # domain rule. Domain routes stay one-line interactor calls.
    await session.execute(text("SELECT 1"))
    return HealthStatus(status="ok")
