from __future__ import annotations

import json
import logging
import os
from typing import Any

from app.config import settings


_security_logger = logging.getLogger("career.security")
_configured = False


def configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.security_log_level.upper(), logging.INFO),
        format="%(message)s",
    )


def emit_security_event(
    event: str,
    actor: str,
    details: dict[str, Any],
) -> None:
    """Emit SIEM-friendly JSON without embedding secret values."""

    payload = {
        "event_type": "security_audit",
        "event": event,
        "actor": actor,
        "environment": settings.deployment_environment,
        "service": settings.otel_service_name,
        "details": details,
    }
    _security_logger.info(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    )


def configure_fastapi_telemetry(app: Any) -> None:
    global _configured

    configure_logging()

    if _configured or not settings.otel_enabled:
        return

    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
        OTLPMetricExporter,
    )
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.metrics import set_meter_provider
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "deployment.environment.name": settings.deployment_environment,
        }
    )
    endpoint = settings.otel_exporter_otlp_endpoint or None
    headers = _parse_headers(settings.otel_exporter_otlp_headers)

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(
                endpoint=endpoint,
                headers=headers or None,
            )
        )
    )
    trace.set_tracer_provider(tracer_provider)

    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(
            endpoint=endpoint,
            headers=headers or None,
        )
    )
    set_meter_provider(
        MeterProvider(
            resource=resource,
            metric_readers=[metric_reader],
        )
    )
    FastAPIInstrumentor.instrument_app(app)
    _configured = True


def configure_celery_telemetry() -> None:
    configure_logging()

    if not settings.otel_enabled:
        return

    from opentelemetry.instrumentation.celery import CeleryInstrumentor

    CeleryInstrumentor().instrument()


def _parse_headers(value: str) -> dict[str, str]:
    result: dict[str, str] = {}

    for item in value.split(","):
        key, separator, header_value = item.partition("=")

        if separator and key.strip():
            result[key.strip()] = header_value.strip()

    return result
