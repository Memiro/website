from django.apps import AppConfig


class LegalConfig(AppConfig):
    """Приложение без моделей: нужно ради регистрации проверок."""

    name = "memiro.legal"
    verbose_name = "юридическое соответствие"

    def ready(self) -> None:
        # Импорт внутри ready — контракт Django: раньше приложения
        # ещё не загружены
        from . import checks  # noqa: F401, PLC0415
