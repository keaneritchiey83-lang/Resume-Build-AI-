from __future__ import annotations

import sys
from pathlib import Path
import re
import tomllib


ROOT = Path(__file__).resolve().parents[2]


def require(path: str, needle: str) -> None:
    text = (ROOT / path).read_text(encoding="utf-8")
    if needle not in text:
        raise SystemExit(f"FAIL: {needle!r} missing from {path}")


def forbid(path: str, needle: str) -> None:
    text = (ROOT / path).read_text(encoding="utf-8")
    if needle in text:
        raise SystemExit(f"FAIL: forbidden {needle!r} found in {path}")


def verify_application_version(minimum_minor: int) -> None:
    """Allow newer phase releases while requiring the declared build version."""
    source = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    match = re.search(r'^APP_VERSION\s*=\s*"(\d+)\.(\d+)\.(\d+)"\s*$', source, re.M)
    if not match:
        raise SystemExit("FAIL: missing semantic APP_VERSION in backend/app/main.py")
    current = tuple(map(int, match.groups()))
    if current < (0, minimum_minor, 0):
        raise SystemExit(f"FAIL: application version {current} is older than phase {minimum_minor}")
    project = tomllib.loads((ROOT / "backend/pyproject.toml").read_text(encoding="utf-8"))
    if project["project"]["version"] != match.group(0).split('"')[1]:
        raise SystemExit("FAIL: APP_VERSION differs from backend/pyproject.toml")


def main() -> int:
    verify_application_version(13)
    checks = [
        ("backend/app/main.py", "phase13_router"),
        ("backend/app/config.py", "phase13_peer_bundle_allowed_host_set"),
        ("backend/app/phase13_services.py", "validate_peer_bundle"),
        ("backend/app/phase13_security.py", "public keys only"),
        ("backend/app/phase13_services.py", "with_for_update()"),
        ("backend/app/phase13_services.py", "active_permission_manifest_required"),
        ("backend/app/phase13_services.py", "Phase 13 gateway does not expose model tools"),
        ("backend/app/phase13_services.py", "passed evaluation run"),
        ("backend/app/phase13_api.py", "External transparency publication is performed by the signed release pipeline"),
        ("backend/alembic/versions/0011_phase13_trust_ai_security.py", 'revision = "0011_phase13"'),
        ("backend/tests/test_phase13.py", "test_prompt_injection_blocks_instruction_override"),
        ("k8s/base/kustomization.yaml", "phase14"),
        (".github/workflows/phase13-security.yml", "run_phase13_governance_gate.py"),
        (".github/workflows/phase13-release-transparency.yml", "cosign sign"),
    ]

    for path, needle in checks:
        require(path, needle)

    forbid("backend/app/phase13_services.py", "verify=False")
    forbid("backend/app/phase13_api.py", "requests.get(")

    print(f"Phase 13 governance gate PASS ({len(checks) + 2} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
