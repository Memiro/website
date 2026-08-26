import re
from dataclasses import dataclass
from functools import wraps
from typing import Any, dataclass_transform

from opentelemetry import trace

_tracer = trace.get_tracer(__name__)
_camel_to_snake = re.compile(r"(?<!^)(?=[A-Z])")


@dataclass_transform(kw_only_default=True, frozen_default=True)
def interactor[T](cls: type[T]) -> type[T]:
    """Make the class a frozen slots kw-only dataclass and trace ``execute``.

    One decorator carries three cross-cutting policies for every interactor:
    a DI-ready ``__init__`` synthesized from annotated fields, immutability
    (the only way to obtain a dependency is DI), and an OTel span named after
    the class.
    """
    cls = dataclass(frozen=True, slots=True, kw_only=True)(cls)
    original = cls.execute  # type: ignore[attr-defined]
    span_name = f"interactor.{_camel_to_snake.sub('_', cls.__name__).lower()}"

    @wraps(original)  # pyright: ignore[reportUnknownArgumentType]
    async def execute(self: Any, *args: Any, **kwargs: Any) -> Any:
        with _tracer.start_as_current_span(span_name):
            return await original(self, *args, **kwargs)  # pyright: ignore[reportUnknownVariableType]

    cls.execute = execute  # type: ignore[attr-defined]
    return cls
