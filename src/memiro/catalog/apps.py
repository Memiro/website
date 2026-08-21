from django.apps import AppConfig


class CatalogConfig(AppConfig):
    name = "memiro.catalog"
    label = "catalog"
    verbose_name = "Каталог"

    def ready(self) -> None:
        # Импорт отложен до готовности приложений: `repricing` тянет
        # модели, а на уровне модуля их ещё нет
        from . import repricing  # noqa: PLC0415

        repricing.connect()
