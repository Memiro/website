from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class ObservabilityConfig:
    """Tracing and logging settings for one process."""

    enabled: bool
    # No endpoint keeps the tracer provider real but exporterless — spans are
    # produced and dropped; useful before a collector exists.
    otlp_endpoint: str | None = None
    log_level: str = "INFO"
