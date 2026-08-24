"""Ответы об ошибках, общие для эндпоинтов витрины.

Форму запроса отвергает разбор — это 400, и пишет его dmr. Здесь
живёт второй случай: форма верна, а того, на что она ссылается, в
каталоге нет. Отказ у него всегда один и тот же — 422 с сообщением,
которое не стыдно показать посетителю; различается только текст.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, NoReturn

from dmr import APIError, ResponseSpec
from dmr.errors import ErrorModel, ErrorType

if TYPE_CHECKING:
    from dmr import Controller
    from dmr.serializer import BaseSerializer

UNPROCESSABLE = ResponseSpec(
    return_type=ErrorModel,
    status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
)


def reject(controller: Controller[BaseSerializer], message: str) -> NoReturn:
    """Отказ по существу запроса — словами, обращёнными к посетителю."""
    raise APIError(
        controller.format_error(message, error_type=ErrorType.user_msg),
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
    )
