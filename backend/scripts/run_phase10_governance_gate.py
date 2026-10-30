from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    governance = ROOT / "governance" / "phase10"

    for name in (
        "openid_credential_interop.json",
        "privacy_engineering_profile.json",
        "selective_disclosure_profile.json",
    ):
        require((governance / name).exists(), f"Missing Phase 10 artifact: {name}")

    interop = json.loads(
        (governance / "openid_credential_interop.json").read_text(encoding="utf-8")
    )
    privacy = json.loads(
        (governance / "privacy_engineering_profile.json").read_text(encoding="utf-8")
    )
    disclosure = json.loads(
        (governance / "selective_disclosure_profile.json").read_text(encoding="utf-8")
    )

    require(
        interop["openid4vci"]["status"] == "OpenID Final Specification",
        "OpenID4VCI status is stale.",
    )
    require(
        interop["openid4vp"]["status"] == "OpenID Final Specification",
        "OpenID4VP status is stale.",
    )
    require(
        interop["selective_disclosure"]["credential_profile"]["never_describe_as_final_rfc"]
        is True,
        "SD-JWT VC draft-status warning is missing.",
    )
    require(
        interop["trust_boundaries"]["arbitrary_key_url_fetching"] is False,
        "Dynamic issuer-key URL fetching must remain prohibited.",
    )
    require(
        privacy["data_discovery"]["samples_plaintext_values"] is False,
        "Data discovery must remain metadata-only.",
    )
    require(
        privacy["deletion_orchestration"]["legal_hold_blocks_deletion"] is True,
        "Deletion legal-hold boundary is missing.",
    )
    require(
        privacy["privacy_analytics"]["daily_epsilon_budget"] is True,
        "Differential-privacy budget control is missing.",
    )
    require(
        disclosure["rfc9901"]["key_binding"].startswith("KB-JWT"),
        "RFC 9901 key-binding profile is missing.",
    )

    policy = (ROOT / "governance" / "policies" / "career.rego").read_text(
        encoding="utf-8"
    )

    for action in (
        "credential.issuer.activate",
        "credential.verifier.activate",
        "credential.issuer_private_key.export",
        "credential.trust_anchor.dynamic_fetch",
        "privacy.analytics.release",
        "audit.delete",
    ):
        require(action in policy, f"Policy gate missing action: {action}")

    migration = (
        ROOT
        / "backend"
        / "alembic"
        / "versions"
        / "0008_phase10_credentials_privacy.py"
    )
    require(migration.exists(), "Phase 10 migration is missing.")

    api = (ROOT / "backend" / "app" / "phase10_api.py").read_text(
        encoding="utf-8"
    )
    for endpoint in (
        "/.well-known/openid-credential-issuer/oid4vci/{slug}",
        "/oid4vci/{slug}/credential",
        "/oid4vp/{slug}/response",
        "/v1/phase10/privacy/deletion/plan",
        "/v1/phase10/audit/verify",
    ):
        require(endpoint in api, f"Phase 10 endpoint missing: {endpoint}")

    services = (ROOT / "backend" / "app" / "phase10_services.py").read_text(
        encoding="utf-8"
    )
    require(
        "follow_redirects=False" not in services
        or "httpx" not in services,
        "Phase 10 credential verification must not fetch arbitrary trust material.",
    )
    require(
        "secrets.SystemRandom()" in services,
        "Privacy analytics must use a CSPRNG-backed noise source.",
    )

    print("Phase 10 governance gate: PASS")


if __name__ == "__main__":
    main()
