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
    """Одна страница ошибки: код, заголовок и объяснение в шаблоне.

    Из этой записи растут и шаблон, и мета, и код ответа — новая
    страница ошибки заводится в одном месте, как статическая
    (`views.STATIC_PAGES`).
    """

    code: int
    heading: str
    description: str

    @property
    def template(self) -> str:
        """Шаблон зовётся по коду: так его ищет и сам Django."""
        return f"{self.code}.html"

    def view(
        self, request: HttpRequest, exception: BaseException | None = None
    ) -> HttpResponse:
        """Представление страницы: подпись Django для handler400, 403, 404.

        `exception` приходит от Django и покупателю не показывается —
        техинформации на странице ошибки быть не должно.
        """
        del exception
        return render(
            request,
            self.template,
            {
                "code": self.code,
                "heading": self.heading,
                # Canonical на странице ошибки указывал бы на адрес,
                # которого нет: `base.html` пустой не печатает
                "canonical": "",
                # Страница ошибки в индексе не нужна: сам код ответа
                # держит её оттуда, но лишним `noindex` не будет
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
    heading="Некорректный запрос",
    description="Сервер не смог разобрать запрос браузера.",
)
FORBIDDEN = ErrorPage(
    code=403,
    heading="Доступ закрыт",
    description="Служебная страница сайта memiro.",
)
NOT_FOUND = ErrorPage(
    code=404,
    heading="Страница не найдена",
    description=(
        "Такого адреса на сайте memiro нет. Зеркала студии собраны в каталоге."
    ),
)
GONE = ErrorPage(
    code=410,
    heading="Страница удалена",
    description=(
        "Страница прежнего сайта memiro удалена насовсем, замены у неё нет."
    ),
)
