import pydantic
from dmr import Controller
from dmr.plugins.pydantic import PydanticSerializer


class PingResponse(pydantic.BaseModel):
    status: str


class PingController(Controller[PydanticSerializer]):
    """Пробный типизированный эндпоинт: живой ли API."""

    def get(self) -> PingResponse:
        return PingResponse(status="ok")
