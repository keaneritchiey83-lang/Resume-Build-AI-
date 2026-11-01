"""Bounded-cardinality Prometheus metrics; bearer-gated /metrics endpoint."""
import secrets
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from app.config import settings

router = APIRouter(tags=["observability"])
REQUESTS = Counter("career_phase14_http_requests_total", "HTTP requests", ["method", "route", "status"])
DURATION = Histogram("career_phase14_http_duration_seconds", "Request latency seconds",
                     ["method", "route"], buckets=(.025, .05, .1, .25, .5, 1, 2.5, 5, 10))


async def metrics_middleware(request: Request, call_next):
    started = time.perf_counter()
    status = "500"
    try:
        response = await call_next(request)
        status = str(response.status_code)
        return response
    finally:
        # The registered route template is stable: never label raw user paths.
        route = request.scope.get("route")
        path = getattr(route, "path", "unmatched")
        REQUESTS.labels(request.method, path, status).inc()
        DURATION.labels(request.method, path).observe(time.perf_counter() - started)


@router.get("/metrics", include_in_schema=False)
async def metrics(request: Request):
    shared_secret = settings.phase14_metrics_bearer_token.get_secret_value()
    provided = request.headers.get("authorization", "")
    if not shared_secret:
        raise HTTPException(status_code=404, detail="Not found")
    if not secrets.compare_digest(provided, "Bearer " + shared_secret):
        raise HTTPException(status_code=403, detail="Forbidden")
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
