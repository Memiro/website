import logging

import structlog
from opentelemetry import trace
from structlog.typing import EventDict, Processor


def _add_trace_context(
    _logger: logging.Logger,
    _method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Stamp the current OTel trace id onto the log record, if a span is active."""
    span_context = trace.get_current_span().get_span_context()
    if span_context.is_valid:
        event_dict["trace_id"] = format(span_context.trace_id, "032x")
    return event_dict


def _shared_processors() -> list[Processor]:
    return [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _add_trace_context,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]


def setup_logging(*, level: str = "INFO") -> None:
    """Route structlog and foreign stdlib records through one JSON chain.

    The same processor chain is reused as ``foreign_pre_chain``, so logs from
    third-party libraries come out as JSON with a ``trace_id`` too.
    """
    shared = _shared_processors()
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *shared,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
        foreign_pre_chain=shared,
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
