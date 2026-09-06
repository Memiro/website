"""The order of a write in the admin: the interactor first, Django's own half after (ADR-0012).

A business refusal comes back to the form with a message and nothing is
stored, because the domain transaction is one and it did not pass. Where a
screen sends more than one command, the refusal says so instead of promising
an untouched database. Anything that fails once a command has committed —
history, banners, the redirect — is a warning: the admin's bookkeeping is a
convenience, not an invariant.
"""

from collections.abc import Callable, Coroutine
from contextvars import ContextVar
from typing import Any

import structlog
from dishka import AsyncContainer
from django.contrib import messages
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect

from memiro.application.common.dispatch_log import DispatchLog
from memiro.presentation.django_admin.bridge import bridge
from memiro.presentation.django_admin.refusals import refusal_text
from memiro_common.errors import AppError
from memiro_common.logger import Logger

_committed: ContextVar[bool] = ContextVar("memiro_admin_committed", default=False)
_dispatched: ContextVar[DispatchLog | None] = ContextVar("memiro_admin_dispatched", default=None)

HISTORY_LOST = "Изменение сохранено, но админка не смогла доделать свою часть: историю и переход на список."
PARTLY_SAVED = "Часть карточки успела сохраниться: откройте её заново и проверьте."
REPRICED = "Цены пересчитаны. Товаров: {count}."
REPRICE_FAILED = "Правка сохранена, но пересчитать цены не удалось: запустите пересчёт со списка товаров."

logger: Logger = structlog.get_logger(__name__)


def _refused(refusal: AppError) -> str:
    """Say the refusal, and own up when an earlier command of the same save did go through."""
    if _committed.get():
        return f"{refusal_text(refusal)} {PARTLY_SAVED}"
    return refusal_text(refusal)


def send[T](command: Callable[[AsyncContainer], Coroutine[Any, Any, T]]) -> T:
    """Send one command across the bridge, remember it reached the domain, and take back what followed it."""
    result, dispatched = bridge().call(lambda scope: _dispatched_with(command, scope))
    _committed.set(True)
    _absorb(dispatched)
    return result


async def _dispatched_with[T](
    command: Callable[[AsyncContainer], Coroutine[Any, Any, T]],
    scope: AsyncContainer,
) -> tuple[T, DispatchLog]:
    """Run one command and read back what its after-commit subscribers did."""
    result = await command(scope)
    return result, await scope.get(DispatchLog)


def _absorb(dispatched: DispatchLog) -> None:
    """Add what one command's subscribers did to the tally of the screen that sent it."""
    running = _dispatched.get()
    if running is not None:
        running.merge(dispatched)


def _announce(request: HttpRequest, dispatched: DispatchLog) -> None:
    """Tell the owner what the after-commit repricing did, when it did anything."""
    if dispatched.failed:
        messages.warning(request, REPRICE_FAILED)
    # A run that moved nothing is still an answer to the owner who asked for
    # it by hand: silence would read as an action that never fired.
    if dispatched.repricing_ran:
        messages.info(request, REPRICED.format(count=dispatched.repriced_products))


def guarded_write(request: HttpRequest, view: Callable[[], HttpResponse]) -> HttpResponse:
    """Run one write view: a refusal returns to the form, a later failure is a warning."""
    token = _committed.set(False)
    dispatched = DispatchLog()
    running = _dispatched.set(dispatched)
    try:
        return view()
    except AppError as refusal:
        logger.warning("The admin refused a write", code=type(refusal).code)
        messages.error(request, _refused(refusal))
        return HttpResponseRedirect(request.get_full_path())
    except Exception as failure:
        if not _committed.get():
            raise
        logger.warning(
            "The admin's own half failed after the domain was committed",
            error=type(failure).__name__,
        )
        messages.warning(request, HISTORY_LOST)
        return HttpResponseRedirect(request.get_full_path())
    finally:
        _announce(request, dispatched)
        _dispatched.reset(running)
        _committed.reset(token)
