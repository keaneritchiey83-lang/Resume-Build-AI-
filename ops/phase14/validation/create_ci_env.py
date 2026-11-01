#!/usr/bin/env python3
"""Prepare short-lived *local CI only* credentials for the Docker Compose smoke test.

This intentionally does not overwrite an existing .env. Never use these local
keys in production, regional trust federation, or recovery exercises.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import secrets
import sys


def write_env(project_root: Path, *, mode: str = "ci") -> Path:
    if mode not in {"ci", "local"}:
        raise ValueError("Unsupported environment mode")
    source = project_root / ".env.example"
    destination = project_root / ".env"
    if destination.exists():
        raise FileExistsError(".env already exists; refusing to overwrite it")
    if not source.is_file():
        raise FileNotFoundError(source)

    database_password = secrets.token_urlsafe(32)
    settings = {
        "POSTGRES_PASSWORD": database_password,
        "DATABASE_URL": f"postgresql+asyncpg://career:{database_password}@postgres:5432/career",
        "JWT_SECRET": secrets.token_urlsafe(48),
        "OIDC_SESSION_SECRET": secrets.token_urlsafe(48),
        "LOCAL_CURRENT_KEY_ID": "ci-local-v1" if mode == "ci" else "local-v1",
        "LOCAL_MASTER_KEYS_JSON": json.dumps(
            {"ci-local-v1" if mode == "ci" else "local-v1": base64.b64encode(secrets.token_bytes(32)).decode()}
        ),
        "SCHEDULER_ENABLED": "false",
        "AGENT_MONITOR_ENABLED": "false",
        "PHASE14_ENABLED": "false",
        "ADMIN_EMAILS": "",
        "PHASE12_SPIFFE_REQUIRED": "false",
        "OPENAI_API_KEY": "",
        "DEPLOYMENT_ENVIRONMENT": mode,
    }
    lines = []
    seen = set()
    for line in source.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#") and "=" in line:
            name = line.split("=", 1)[0]
            if name in settings:
                line = f"{name}={settings[name]}"
                seen.add(name)
        lines.append(line)
    if missing := set(settings) - seen:
        raise RuntimeError(f".env.example is missing required settings: {sorted(missing)}")
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write("\n".join(lines) + "\n")
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return destination


def main() -> int:
    project_root = Path(__file__).resolve().parents[3]
    try:
        path = write_env(project_root)
    except (OSError, RuntimeError) as exc:
        print(f"Cannot prepare CI .env: {exc}", file=sys.stderr)
        return 1
    print(f"Created {path.name} for local Docker Compose smoke validation (not production).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
