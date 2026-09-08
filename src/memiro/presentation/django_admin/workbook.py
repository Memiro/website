"""What the owner downloads from the card and from the list of sections: the book his prices are in."""

from uuid import UUID

import structlog
from dishka import AsyncContainer
from django.contrib import messages
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect

from memiro.application.export_pricing_workbook import (
    ExportPricingWorkbook,
    ExportPricingWorkbookForm,
    PricingWorkbookFile,
)
from memiro.presentation.django_admin.bridge import bridge
from memiro.presentation.django_admin.refusals import refusal_text
from memiro_common.errors import AppError
from memiro_common.logger import Logger

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
ONE_AT_A_TIME = "Книга собирается по одному разделу: отметьте один и повторите."

logger: Logger = structlog.get_logger(__name__)


def workbook_response(
    request: HttpRequest,
    *,
    product_id: UUID | None = None,
    category_id: UUID | None = None,
) -> HttpResponse:
    """Answer with the workbook as a file, and with a message where the domain refuses to build one."""
    form = ExportPricingWorkbookForm(product_id=product_id, category_id=category_id)
    try:
        exported = bridge().call(lambda scope: _exported(scope, form))
    except AppError as refusal:
        logger.warning("The admin was refused the workbook", code=type(refusal).code)
        messages.error(request, refusal_text(refusal))
        return HttpResponseRedirect(_back_to(request))
    response = HttpResponse(exported.content, content_type=XLSX)
    response["Content-Disposition"] = f'attachment; filename="{exported.name}"'
    return response


async def _exported(scope: AsyncContainer, form: ExportPricingWorkbookForm) -> PricingWorkbookFile:
    """Collect the book in one REQUEST scope of the admin's own container."""
    interactor = await scope.get(ExportPricingWorkbook)
    return await interactor.execute(form)


def _back_to(request: HttpRequest) -> str:
    """Send a refused download back to the screen it was asked from."""
    referer = request.META.get("HTTP_REFERER")
    return referer or "/admin/"
