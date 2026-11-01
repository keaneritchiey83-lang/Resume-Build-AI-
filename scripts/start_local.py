#!/usr/bin/env python3
"""Secure local Docker Compose entry point for the complete Phase 14 stack.

Requires Docker Engine + Compose V2 and network access to container/npm/PyPI
registries on the machine running it. Does not enable Phase 14 autonomous agents.
"""
from __future__ import annotations

import argparse
import base64
import json
from urllib.parse import urlsplit, unquote
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops" / "phase14" / "validation"))
from create_ci_env import write_env  # noqa: E402
from live_smoke import verify_database, verify_health  # noqa: E402


def run(args: list[str], *, check: bool = True, timeout: int | None = None):
    return subprocess.run(args, cwd=ROOT, check=check, timeout=timeout)


def preflight() -> list[str]:
    errors = []
    for args, help_text in [
        (["docker", "--version"], "Install Docker Engine or Docker Desktop."),
        (["docker", "compose", "version"], "Install the Docker Compose V2 plugin."),
        (["docker", "info"], "Start Docker Desktop or the Docker daemon."),
    ]:
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=12)
            if result.returncode:
                errors.append(f"{' '.join(args)} failed: {help_text}")
        except (OSError, subprocess.TimeoutExpired):
            errors.append(f"{' '.join(args)} unavailable: {help_text}")
    return errors


def verify_local_config() -> None:
    config = ROOT / ".env"
    if not config.is_file():
        config = write_env(ROOT, mode="local")
        print(f"Created private {config.name} with random local secrets; never commit it.")
    values = {}
    for line in config.read_text(encoding="utf-8").splitlines():
        if line and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value.strip()
    if values.get("PHASE14_ENABLED", "false").lower() != "false":
        raise RuntimeError(
            "Local launcher refuses PHASE14_ENABLED=true. Use managed runtime "
            "and explicit approved manifests for agent execution."
        )
    for name in ("JWT_SECRET", "OIDC_SESSION_SECRET"):
        value = values.get(name, "")
        if len(value) < 32 or value.startswith("replace-"):
            raise RuntimeError(f"Unsafe {name} in .env. Supply a unique >=32-character secret.")
    local_keys = values.get("LOCAL_MASTER_KEYS_JSON", "")
    if not local_keys or "REPLACE_WITH" in local_keys:
        raise RuntimeError("Invalid LOCAL_MASTER_KEYS_JSON: generate 32-byte base64 key.")
    try:
        keys = json.loads(local_keys)
        key_name = values.get("LOCAL_CURRENT_KEY_ID", "")
        key_bytes = base64.b64decode(keys[key_name], validate=True)
        if len(key_bytes) != 32:
            raise ValueError("Expected a 32-byte local master key")
    except (ValueError, KeyError, TypeError) as exc:
        raise RuntimeError("LOCAL_MASTER_KEYS_JSON must contain a valid base64 32-byte key") from exc
    db_password = values.get("POSTGRES_PASSWORD", "")
    if len(db_password) < 24 or db_password.startswith("replace-"):
        raise RuntimeError("POSTGRES_PASSWORD must be a unique strong local password.")
    database_url = urlsplit(values.get("DATABASE_URL", ""))
    if database_url.hostname != "postgres" or database_url.port != 5432 or database_url.path != "/career":
        raise RuntimeError("Local Compose requires DATABASE_URL to connect to postgres:5432/career.")
    if unquote(database_url.password or "") != db_password:
        raise RuntimeError("DATABASE_URL credentials do not match POSTGRES_PASSWORD.")


def smoke(wait: float):
    verify_health("http://127.0.0.1:8000", "http://127.0.0.1:5173", deadline=wait)
    verify_database()
    print("PASS: database migration, pgvector, API, compiled frontend, Phase 14 default-deny.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "check", "smoke", "stop", "logs"],
                        nargs="?", default="start")
    parser.add_argument("--wait-seconds", type=float, default=240)
    args = parser.parse_args()
    try:
        if args.action in {"start", "check"}:
            verify_local_config()
        problems = preflight()
        if problems:
            raise RuntimeError("\n".join(problems))
        if args.action == "check":
            run(["docker", "compose", "config", "--quiet"])
            print("PASS: Docker, Compose, daemon and local environment.")
        elif args.action == "start":
            run(["docker", "compose", "config", "--quiet"])
            run(["docker", "compose", "up", "--build", "-d"],
                timeout=1800)
            smoke(args.wait_seconds)
            print("RUNNING: frontend http://localhost:5173 · API http://localhost:8000/docs")
        elif args.action == "smoke":
            smoke(args.wait_seconds)
        elif args.action == "stop":
            run(["docker", "compose", "down"])  # preserve persistent data volumes
            print("Stopped. PostgreSQL and Redis volumes preserved.")
        else:
            run(["docker", "compose", "logs", "--tail", "150"])
    except (RuntimeError, OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired,
            AssertionError, ValueError) as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        if args.action == "start":
            print("Troubleshoot with: python scripts/start_local.py logs", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
