"""The admin's one door into the async context: a thread that owns an event loop (ADR-0012).

The admin is WSGI and synchronous, the interactors are async. This module
holds the loop they run in, and the dishka container that lives in it — both
made once per admin process, so the engine and its pool are an honest
APP-scope and every write opens nothing but a REQUEST scope.
"""

import asyncio
import threading
from collections.abc import Callable, Coroutine
from typing import Any, cast

import structlog
from dishka import AsyncContainer
from django.conf import settings

from memiro_common.logger import Logger

_bridge: "Bridge | None" = None
_bridge_lock = threading.Lock()

# The setting the bootstrap leaves for the presentation: the container is
# assembled from the very ``Config`` the process was started with, and the
# admin package is not allowed to reach into the bootstrap for it.
CONTAINER_FACTORY_SETTING = "MEMIRO_CONTAINER_FACTORY"
THREAD_NAME = "memiro-admin-bridge"

logger: Logger = structlog.get_logger(__name__)


async def _assembled(container_factory: Callable[[], AsyncContainer]) -> AsyncContainer:
    """Make the container in the loop that will own it."""
    return container_factory()


def _container_factory() -> Callable[[], AsyncContainer]:
    """Take the container factory the bootstrap left among the settings."""
    return cast("Callable[[], AsyncContainer]", getattr(settings, CONTAINER_FACTORY_SETTING))


class Bridge:
    """The loop-owning thread every write of the admin is sent across."""

    def __init__(self, container_factory: Callable[[], AsyncContainer]) -> None:
        """Start the loop of this process and assemble the container that lives in it."""
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._serve, name=THREAD_NAME, daemon=True)
        self._thread.start()
        # Assembled inside the loop: the engine and its pool bind to the loop
        # that runs every command, and rebinding them per call would leave the
        # process without an APP scope at all (ADR-0012).
        self._container = self._awaited(_assembled(container_factory))

    def call[T](self, command: Callable[[AsyncContainer], Coroutine[Any, Any, T]]) -> T:
        """Run one command in a REQUEST scope of the process-wide container."""
        return self._awaited(self._within_request(command))

    def _serve(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    async def _within_request[T](self, command: Callable[[AsyncContainer], Coroutine[Any, Any, T]]) -> T:
        async with self._container() as scope:
            return await command(scope)

    def _awaited[T](self, coroutine: Coroutine[Any, Any, T]) -> T:
        return asyncio.run_coroutine_threadsafe(coroutine, self._loop).result()


def bridge() -> Bridge:
    """Hand over the process's one bridge, starting its loop on first use."""
    global _bridge  # noqa: PLW0603  # one loop per process is exactly what the module owns
    with _bridge_lock:
        if _bridge is None:
            logger.debug("Starting the admin bridge")
            _bridge = Bridge(_container_factory())
        return _bridge
