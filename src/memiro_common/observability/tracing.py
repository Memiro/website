import os
import uuid

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_INSTANCE_ID, SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import NoOpTracerProvider


def setup_tracing(
    *,
    enabled: bool,
    service_name: str,
    endpoint: str | None = None,
) -> None:
    """Install a tracer provider: a real one, or a no-op when disabled.

    With ``enabled=False`` span-bearing code (``@interactor``) runs unchanged
    against no-op providers — tests never pay for tracing.
    """
    if not enabled:
        trace.set_tracer_provider(NoOpTracerProvider())
        return
    instance_id = f"{service_name}-{os.getpid()}-{uuid.uuid4()}"
    resource = Resource.create(
        {SERVICE_NAME: service_name, SERVICE_INSTANCE_ID: instance_id},
    )
    provider = TracerProvider(resource=resource)
    if endpoint is not None:
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    trace.set_tracer_provider(provider)
