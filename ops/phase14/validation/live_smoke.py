#!/usr/bin/env python3
"""Validate a *running* local Phase 14 Docker Compose deployment.

Requires Docker Compose, pgvector Postgres and the backend/frontend services.
Never equate this with a cloud multi-region failover test.
"""
from __future__ import annotations

import argparse
import json
import re
from urllib.parse import urljoin
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


EXPECTED_TABLES = (
    "phase14_tokens",
    "phase14_approvals",
    "phase14_agent_memory",
    "phase14_step_receipts",
)


def fetch(url: str, *, timeout: float = 5.0) -> tuple[int, bytes]:
    with urlopen(url, timeout=timeout) as response:
        return response.status, response.read(1024 * 1024)


def wait_for(url: str, *, deadline: float = 150.0) -> tuple[int, bytes]:
    end = time.monotonic() + deadline
    while True:
        try:
            status, body = fetch(url)
            if status == 200:
                return status, body
        except (HTTPError, URLError, OSError, TimeoutError):
            pass
        if time.monotonic() >= end:
            raise RuntimeError(f"{url} did not become healthy within {deadline:g}s")
        time.sleep(3)


def verify_health(base: str, web: str, *, deadline: float) -> None:
    _, health_body = wait_for(f"{base}/health", deadline=deadline)
    health = json.loads(health_body)
    if health.get("status") != "ok":
        raise AssertionError("API /health did not report healthy")

    _, readiness_body = wait_for(f"{base}/ready", deadline=deadline)
    readiness = json.loads(readiness_body)
    if readiness.get("status") != "ready":
        raise AssertionError("API /ready did not confirm a working database")

    _, phase14_body = wait_for(f"{base}/v1/phase14/readiness", deadline=deadline)
    phase14 = json.loads(phase14_body)
    if phase14.get("phase") != "14A+14B":
        raise AssertionError("Phase 14 readiness endpoint is not available")
    if phase14.get("enabled") is not False:
        raise AssertionError("Local smoke run must keep Phase 14 agent execution disabled")

    _, html = wait_for(web, deadline=deadline)
    if b"Global Career Architecture AI" not in html:
        raise AssertionError("Frontend HTML did not contain the expected application title")
    # An HTML shell alone is not enough: nginx could serve the SPA fallback
    # even when assets are missing. Fetch a compiled Vite JS entry separately.
    assets = re.findall(rb'<script[^>]+src="(/assets/[^"]+\.js)"', html)
    if not assets:
        raise AssertionError("Frontend HTML has no production Vite JavaScript entry")
    url = urljoin(web.rstrip("/") + "/", assets[0].decode("ascii"))
    _, javascript = wait_for(url, deadline=deadline)
    if not javascript or javascript.lstrip().lower().startswith(b"<!doctype html"):
        raise AssertionError("Compiled JS entry is missing (frontend SPA fallback returned)")
    print("PASS: API health, database readiness, Phase 14 default-deny, and compiled web assets")


def postgres_scalar(query: str) -> str:
    command = [
        "docker", "compose", "exec", "-T", "postgres",
        "psql", "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1",
        "-U", "career", "-d", "career", "-c", query,
    ]
    proc = subprocess.run(command, capture_output=True, text=True, timeout=30)
    if proc.returncode:
        raise RuntimeError(
            f"PostgreSQL verification failed (exit={proc.returncode}): "
            f"{proc.stderr.strip()[-700:]}"
        )
    return proc.stdout.strip()


def verify_database() -> None:
    version = postgres_scalar("SELECT version_num FROM alembic_version")
    if version != "0012_phase14":
        raise AssertionError(f"Expected migration 0012_phase14, got {version!r}")
    vector = postgres_scalar(
        "SELECT COUNT(*) FROM pg_extension WHERE extname = 'vector'"
    )
    if vector != "1":
        raise AssertionError("pgvector extension is not installed")
    tables = postgres_scalar(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' "
        "AND table_name LIKE 'phase14_%' ORDER BY table_name"
    ).splitlines()
    missing = set(EXPECTED_TABLES) - set(tables)
    if missing:
        raise AssertionError(f"Phase 14 database tables missing: {sorted(missing)}")
    print("PASS: live PostgreSQL migration 0012_phase14, pgvector and Phase 14 tables")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--web-url", default="http://127.0.0.1:5173")
    parser.add_argument("--wait-seconds", type=float, default=150)
    args = parser.parse_args()
    if args.wait_seconds <= 0:
        parser.error("--wait-seconds must be positive")
    try:
        verify_health(
            args.api_url.rstrip("/"),
            args.web_url.rstrip("/"),
            deadline=args.wait_seconds,
        )
        verify_database()
    except (AssertionError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print("PASS: Phase 14 local database + Docker Compose smoke validation completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
