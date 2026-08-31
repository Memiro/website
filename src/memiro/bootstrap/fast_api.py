from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI

# The instrumentation package ships no stubs; its one entry point is used as documented.
from opentelemetry.instrumentation.fastapi import (  # pyright: ignore[reportMissingTypeStubs]
    FastAPIInstrumentor,
)

from memiro.bootstrap.config_loader import Config
from memiro.bootstrap.di.container import get_async_container
from memiro.presentation.fast_api.error_handlers import setup_error_handlers
from memiro.presentation.fast_api.routers.health import router as health_router
from memiro.presentation.fast_api.routers.inquiries import router as inquiries_router
from memiro.presentation.fast_api.routers.pricing import router as pricing_router
from memiro_common.observability.logs import setup_logging
from memiro_common.observability.tracing import setup_tracing


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Close the DI container when the process shuts down."""
    yield
    await app.state.dishka_container.close()


def create_app(config: Config) -> FastAPI:
    """Assemble the application in the §11.1 order."""
    setup_logging(level=config.observability.log_level)
    setup_tracing(
        enabled=config.observability.enabled,
        service_name="memiro-api",
        endpoint=config.observability.otlp_endpoint,
    )
    app = FastAPI(title="Memiro API", lifespan=_lifespan)
    # Health probes are excluded from tracing (§10.4).
    FastAPIInstrumentor.instrument_app(app, excluded_urls="/internal/.*")
    container = get_async_container(config)
    setup_dishka(container, app)
    app.include_router(health_router)
    app.include_router(inquiries_router)
    app.include_router(pricing_router)
    setup_error_handlers(app)
    return app


def app_factory() -> FastAPI:
    """Build the app for ``uvicorn --factory``.

    The only place the API process calls ``Config.load()``; other process
    entry points (CLI migrations) load their config in ``cli.py``.
    """
    return create_app(Config.load())


def run_api() -> None:
    """Run the production API server."""
    # Binding all interfaces is deliberate: uvicorn serves inside the
    # container and nginx is the public edge; tuning lives in compose.
    uvicorn.run(
        "memiro.bootstrap.fast_api:app_factory",
        factory=True,
        host="0.0.0.0",  # noqa: S104  # nosec B104
        port=8000,
    )
