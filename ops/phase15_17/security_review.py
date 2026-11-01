#!/usr/bin/env python3
"""Dependency-free, conservative release configuration checks.

This is a static configuration control review, not penetration testing,
software composition analysis, a complete code review, or release approval.
"""
from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]


def require(path: str, requirement: str, ok: bool) -> None:
    if not ok:
        raise AssertionError(f"{path}: {requirement}")
    print(f"PASS {path}: {requirement}")


def main() -> int:
    gitignore = (ROOT / '.gitignore').read_text()
    compose = (ROOT / 'docker-compose.yml').read_text()
    failover = (ROOT / '.github/workflows/phase14-staging-failover.yml').read_text()
    live = (ROOT / '.github/workflows/phase14-live-validation.yml').read_text()
    env_source = (ROOT / 'ops/phase14/validation/create_ci_env.py').read_text()
    nginx = (ROOT / 'frontend/nginx.conf').read_text()
    require('.gitignore', 'private .env files excluded',
            re.search(r'^\.env$', gitignore, re.M) is not None)
    require('docker-compose.yml', 'PostgreSQL password required from environment',
            'POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?' in compose)
    for port in ('8000:8000', '5173:8080', '8088:8080'):
        require('docker-compose.yml', f'local {port} bound to loopback',
                f'"127.0.0.1:{port}"' in compose)
    require('create_ci_env.py', 'ephemeral secrets, agents disabled',
            all(x in env_source for x in ('secrets.token_urlsafe', '"PHASE14_ENABLED": "false"',
                                         'os.O_EXCL', '0o600')))
    require('frontend/nginx.conf', 'same-origin API proxy',
            'location ^~ /v1/' in nginx and 'proxy_pass http://api:8000;' in nginx)
    require('phase14-live-validation.yml', 'isolated CI accounts explicitly acknowledged',
            '--ack-isolated-stack' in live and 'create_ci_env.py' in live)
    require('phase14-staging-failover.yml', 'manual dispatch with explicit impact confirmation',
            all(x in failover for x in ('workflow_dispatch:', 'FAILOVER STAGING',
                                        'environment: staging', 'confirm_staging_impact',
                                        '--ack-impact')) and '--allow-production' not in failover)
    require('phase14-staging-failover.yml', 'no automatic push-triggered staging drill',
            not re.search(r'^\s*push:', failover, re.M))
    print('Static configuration review PASS; external security approval still required.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (AssertionError, OSError) as exc:
        print(f'Static configuration review FAIL: {exc}', file=sys.stderr)
        raise SystemExit(1)
