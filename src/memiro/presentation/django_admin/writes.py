"""The order of a write in the admin: the interactor first, Django's own half after (ADR-0012).

A business refusal comes back to the form with a message and nothing is
stored, because the domain transaction is one and it did not pass. Where a
screen sends more than one command, the refusal says so instead of promising
an untouched database. Anything that fails once a command has committed —
history, banners, the redirect — is a warning: the admin's bookkeeping is a
convenience, not an invariant.
"""

from collections.abc import Callable
from contextvars import ContextVar

import structlog
from django.contrib import messages
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect

from memiro.presentation.django_admin.refusals import refusal_text
from memiro_common.errors import AppError
from memiro_common.logger import Logger

_committed: ContextVar[bool] = ContextVar("memiro_admin_committed", default=False)

HISTORY_LOST = "Изменение сохранено, но админка не смогла доделать свою часть: историю и переход на список."
PARTLY_SAVED = "Часть карточки успела сохраниться: откройте её заново и проверьте."

logger: Logger = structlog.get_logger(__name__)


def _refused(refusal: AppError) -> str:
    """Say the refusal, and own up when an earlier command of the same save did go through."""
    if _committed.get():
        return f"{refusal_text(refusal)} {PARTLY_SAVED}"
    return refusal_text(refusal)


def record_commit() -> None:
    """Remember that a command of this request has already reached the domain."""
    _committed.set(True)


def guarded_write(request: HttpRequest, view: Callable[[], HttpResponse]) -> HttpResponse:
    """Run one write view: a refusal returns to the form, a later failure is a warning."""
    token = _committed.set(False)
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
        _committed.reset(token)
