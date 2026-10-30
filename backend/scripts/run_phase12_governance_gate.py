
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def require(path: str, needle: str) -> None:
    text = (ROOT / path).read_text(encoding="utf-8")
    if needle not in text:
        raise SystemExit(f"FAIL: {needle!r} missing from {path}")


def forbid(path: str, needle: str) -> None:
    text = (ROOT / path).read_text(encoding="utf-8")
    if needle in text:
        raise SystemExit(f"FAIL: forbidden {needle!r} found in {path}")


def main() -> int:
    checks = [
        ("backend/app/phase12_services.py", "approved_trust_anchor_reached"),
        ("backend/app/phase12_services.py", "verified_wallet_attestation_required"),
        ("backend/app/phase12_signing.py", "phase12_require_hsm_signing"),
        ("backend/app/phase12_signing.py", 'MessageType="DIGEST"'),
        ("backend/app/phase12_api.py", "Only a public JWK may be registered."),
        ("backend/app/phase12_services.py", "REVERSIBLE_AUTO_ACTIONS"),
        ("backend/app/phase12_services.py", "Infrastructure isolation must be performed"),
        ("backend/app/config.py", "phase12_spiffe_endpoint_socket"),
        ("backend/app/main.py", "Phase 12 requires the SPIFFE Workload API socket"),
        ("k8s/base/api.yaml", "spire-sockets"),
        ("backend/tests/test_phase12.py", "request_network_quarantine"),
        ("k8s/phase12/spire-values.yaml", "trustDomain"),
        ("k8s/phase12/falco-values.yaml", "runtime/events"),
        (".github/workflows/phase12-security.yml", "run_phase12_governance_gate.py"),
    ]

    for path, needle in checks:
        require(path, needle)

    forbid("runtime-sensor-gateway/app.py", '"proc.cmdline"')
    print(f"Phase 12 governance gate PASS ({len(checks) + 1} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
