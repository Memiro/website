from types import TracebackType
from typing import Self

import httpx
from fastapi import FastAPI
from pydantic import TypeAdapter

from memiro.application.browse_catalog import CategoryModel, ProductModel
from memiro.application.calculate_price import CalculatedPrice, CalculatePriceForm
from memiro.application.submit_inquiry import CreatedInquiry, SubmitInquiryForm
from memiro.presentation.fast_api.error_handlers import ErrorResponse
from memiro.presentation.fast_api.routers.health import HealthStatus


class ApiResponse[ModelT]:
    """One API response with fluent assertions (§14.5.4)."""

    def __init__(self, response: httpx.Response, response_adapter: TypeAdapter[ModelT]) -> None:
        """Wrap a raw response together with its expected DTO type."""
        self._response = response
        self._response_adapter = response_adapter

    def assert_status(self, expected: int) -> Self:
        """Assert the HTTP status code, failing with the response body."""
        assert self._response.status_code == expected, self._response.text
        return self

    def assert_error(self, expected_status: int, expected_code: str) -> None:
        """Assert a refusal by its status and its machine code — the whole of a negative test."""
        assert self._response.status_code == expected_status, self._response.text
        assert ErrorResponse.model_validate_json(self._response.text).code == expected_code

    def ensure_content(self) -> ModelT:
        """Parse the body into the real production DTO."""
        return self._response_adapter.validate_json(self._response.text)

    @property
    def text(self) -> str:
        """Return the body as it went over the wire — for fences over what must not be in it."""
        return self._response.text


class ApiClient:
    """Typed client over the in-process ASGI app: one method per endpoint."""

    def __init__(self, app: FastAPI) -> None:
        """Build an httpx client over the app's ASGI transport."""
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        self._client = httpx.AsyncClient(transport=transport, base_url="http://test")

    async def __aenter__(self) -> Self:
        """Enter the underlying HTTP client."""
        await self._client.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Close the underlying HTTP client."""
        await self._client.__aexit__(exc_type, exc, tb)

    async def alive(self) -> ApiResponse[HealthStatus]:
        """Call the liveness probe."""
        return ApiResponse(await self._client.get("/internal/alive"), TypeAdapter(HealthStatus))

    async def ready(self) -> ApiResponse[HealthStatus]:
        """Call the readiness probe."""
        return ApiResponse(await self._client.get("/internal/ready"), TypeAdapter(HealthStatus))

    async def calculate(self, data: CalculatePriceForm) -> ApiResponse[CalculatedPrice]:
        """Price one configuration of a product."""
        response = await self._client.post("/calculate", json=data.model_dump(mode="json"))
        return ApiResponse(response, TypeAdapter(CalculatedPrice))

    async def list_categories(self) -> ApiResponse[list[CategoryModel]]:
        """List public catalogue categories."""
        return ApiResponse(await self._client.get("/catalog/categories"), TypeAdapter(list[CategoryModel]))

    async def read_product(self, slug: str) -> ApiResponse[ProductModel]:
        """Read one public product card by its slug."""
        return ApiResponse(await self._client.get(f"/catalog/products/{slug}"), TypeAdapter(ProductModel))

    async def submit_inquiry(self, data: SubmitInquiryForm) -> ApiResponse[CreatedInquiry]:
        """Submit one visitor inquiry."""
        response = await self._client.post("/inquiries", json=data.model_dump(mode="json"))
        return ApiResponse(response, TypeAdapter(CreatedInquiry))
