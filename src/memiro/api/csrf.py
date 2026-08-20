"""CSRF-защита JSON-эндпоинтов.

Контроллеры django-modern-rest по умолчанию освобождены от проверки
CSRF; формы витрины отдаются нашим же SSR, токен у них есть — возвращаем
стандартную защиту Django и отвечаем на отказ JSON, а не HTML-страницей.
"""

from http import HTTPStatus
from typing import TYPE_CHECKING

from django.views.decorators.csrf import csrf_protect
from dmr import ResponseSpec
from dmr.decorators import wrap_middleware
from dmr.errors import ErrorModel, ErrorType, format_error
from dmr.plugins.pydantic import PydanticSerializer
from dmr.response import build_response

if TYPE_CHECKING:
    from django.http import HttpResponse


@wrap_middleware(
    csrf_protect,
    ResponseSpec(
        return_type=ErrorModel,
        status_code=HTTPStatus.FORBIDDEN,
    ),
)
def csrf_protect_json(response: HttpResponse) -> HttpResponse:
    """Отказ CSRF-проверки в том же формате, что и прочие ошибки API."""
    return build_response(
        PydanticSerializer,
        raw_data=format_error(
            "Проверка CSRF не пройдена, обновите страницу.",
            error_type=ErrorType.user_msg,
        ),
        status_code=HTTPStatus(response.status_code),
    )
