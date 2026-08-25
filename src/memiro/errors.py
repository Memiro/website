"""Страницы ошибок витрины: своё представление на каждый код.

Django отдал бы их представлениями `django.views.defaults`, а те рисуют
шаблон без `PageMeta`: страница ошибки уехала бы с заголовком и OG
главной и без `noindex`. Мету на витрине даёт представление
(`seo/meta.py`), поэтому у ошибок оно тоже своё — как у корзины.

Пятой, 500-й, здесь нет и быть не может: она рисуется без `request`,
значит без контекст-процессоров и без базы (см. `templates/500.html`),
и остаётся за штатным `django.views.defaults.server_error`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.shortcuts import render

from memiro.seo.meta import NOINDEX, PageMeta
from memiro.seo.meta import title as meta_title

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse


@dataclass(frozen=True)
class ErrorPage:
    """Одна страница ошибки: код, шаблон, заголовок и мета.

    Из этой записи растут и код ответа, и заголовок, и описание — новая
    страница ошибки заводится в одном месте, как статическая
    (`views.STATIC_PAGES`). Объяснение человеческим языком остаётся
    в шаблоне: там ему и место.
    """

    code: int
    template: str
    heading: str
    description: str

    def view(
        self,
        request: HttpRequest,
        exception: BaseException | None = None,  # noqa: ARG002
    ) -> HttpResponse:
        """Представление страницы: подпись Django для handler400, 403, 404.

        `exception` приходит от Django и покупателю не показывается:
        техинформации на странице ошибки быть не должно.
        """
        return render(
            request,
            self.template,
            {
                "code": self.code,
                "heading": self.heading,
                # Canonical на странице ошибки указывал бы на адрес,
                # которого нет: `base.html` пустой не печатает
                "canonical": "",
                # Страницу ошибки держит вне индекса сам код ответа,
                # но `noindex` вторым рядом не помешает
                "meta": PageMeta(
                    title=meta_title(self.heading),
                    description=self.description,
                    robots=NOINDEX,
                ),
            },
            status=self.code,
        )


BAD_REQUEST = ErrorPage(
    code=400,
    template="400.html",
    heading="Некорректный запрос",
    description="Сервер не смог разобрать запрос браузера.",
)
FORBIDDEN = ErrorPage(
    code=403,
    template="403.html",
    heading="Доступ закрыт",
    description="Служебная страница сайта memiro.",
)
NOT_FOUND = ErrorPage(
    code=404,
    template="404.html",
    heading="Страница не найдена",
    description=(
        "Такого адреса на сайте memiro нет. Зеркала студии собраны в каталоге."
    ),
)
GONE = ErrorPage(
    code=410,
    template="410.html",
    heading="Страница удалена",
    description=(
        "Страница прежнего сайта memiro удалена насовсем, замены у неё нет."
    ),
)
# Тот же 403, но человеку надо сказать другое: не «сюда нельзя»,
# а «страница устарела, обновите и повторите»
CSRF_FAILURE = ErrorPage(
    code=403,
    template="403_csrf.html",
    heading="Страница устарела",
    description="Обновите страницу сайта memiro и повторите отправку.",
)


def csrf_failure(
    request: HttpRequest,
    reason: str = "",  # noqa: ARG001
) -> HttpResponse:
    """Провалившаяся проверка CSRF: подпись `CSRF_FAILURE_VIEW`.

    Мимо `handler403` этот случай проходит стороной — Django зовёт
    отдельное представление и рисует свою английскую страницу
    с техническими подсказками — а её видит кто угодно, кто отправил
    обычный POST. Форма заявки сюда не приходит: она уходит в API,
    и там провал CSRF возвращается сообщением в JSON.

    Причина отказа (`reason`) остаётся в логах: на странице она
    и есть та самая техинформация.
    """
    return CSRF_FAILURE.view(request)
