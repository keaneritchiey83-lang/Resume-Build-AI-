from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def require(path: str, needle: str) -> None:
    text = (ROOT / path).read_text(encoding="utf-8")
    if needle not in text:
        raise SystemExit(f"FAIL: {needle!r} missing from {path}")


def main() -> int:
    checks = [
        ("backend/app/phase11_api.py", "Private key parameters are forbidden."),
        ("backend/app/phase11_services.py", "phase11_did_web_allowed_host_set"),
        ("backend/app/phase11_services.py", "manual_required"),
        ("backend/app/phase11_services.py", "conformance_claim"),
        ("backend/app/phase11_services.py", "FIPS 203"),
        ("backend/tests/test_phase11_security.py", "131072"),
        (".github/workflows/phase11-supply-chain.yml", "actions/attest@v4"),
        (".github/workflows/phase11-security.yml", "zaproxy/action-baseline"),
    ]
    for path, needle in checks:
        require(path, needle)
    print(f"Phase 11 governance gate PASS ({len(checks)} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
