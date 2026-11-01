from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request


app = FastAPI(title="Career AI Runtime Sensor Gateway")

CAREER_RUNTIME_ENDPOINT = os.environ.get(
    "CAREER_RUNTIME_ENDPOINT",
    "http://career-api.career-ai.svc.cluster.local:8000/v1/phase12/runtime/events",
)
RUNTIME_SENSOR_TOKEN = os.environ.get("RUNTIME_SENSOR_TOKEN", "")

PRIORITY_MAP = {
    "debug": "debug",
    "informational": "info",
    "info": "info",
    "notice": "notice",
    "warning": "warning",
    "error": "error",
    "critical": "critical",
    "alert": "critical",
    "emergency": "critical",
}


def normalized_event(payload: dict[str, Any]) -> dict[str, Any]:
    output_fields = payload.get("output_fields")

    if not isinstance(output_fields, dict):
        output_fields = {}

    priority = str(payload.get("priority", "warning")).lower()
    namespace = str(
        output_fields.get("k8s.ns.name")
        or output_fields.get("k8s.pod.namespace")
        or ""
    )
    workload = str(
        output_fields.get("k8s.pod.name")
        or output_fields.get("container.name")
        or output_fields.get("proc.name")
        or ""
    )
    organization_id = str(
        output_fields.get("career.organization_id")
        or payload.get("organization_id")
        or ""
    ).strip()

    return {
        "organization_id": organization_id or None,
        "source": "falco",
        "severity": PRIORITY_MAP.get(priority, "warning"),
        "rule": str(payload.get("rule", "Falco runtime event"))[:500],
        "workload": workload[:500],
        "namespace": namespace[:300],
        "details": {
            "time": payload.get("time"),
            "source": payload.get("source"),
            "hostname": payload.get("hostname"),
            "output": str(payload.get("output", ""))[:4000],
            "output_fields": {
                key: output_fields.get(key)
                for key in [
                    "k8s.ns.name",
                    "k8s.pod.name",
                    "container.name",
                    "container.id",
                    "proc.name",
                    "evt.type",
                    "user.name",
                ]
                if key in output_fields
            },
        },
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/falco")
async def falco(request: Request) -> dict[str, str]:
    if not RUNTIME_SENSOR_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="RUNTIME_SENSOR_TOKEN is not configured.",
        )

    payload = await request.json()

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Falco payload must be an object.")

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(5, connect=2),
        follow_redirects=False,
    ) as client:
        response = await client.post(
            CAREER_RUNTIME_ENDPOINT,
            headers={
                "X-Runtime-Sensor-Token": RUNTIME_SENSOR_TOKEN,
                "Content-Type": "application/json",
            },
            json=normalized_event(payload),
        )

    if response.status_code >= 300:
        raise HTTPException(
            status_code=502,
            detail=f"Career runtime endpoint rejected event: {response.status_code}",
        )

    return {"status": "forwarded"}
