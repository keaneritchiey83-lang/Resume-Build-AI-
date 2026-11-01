from __future__ import annotations

import hashlib
import json
import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.governance import evaluate_policy
from app.phase10_services import (
    _b64u,
    _b64u_decode,
    _public_jwk,
    _sd_disclosure,
    _sha256_text,
    authorization_server_metadata,
    verify_holder_proof,
)


def test_rfc9901_disclosure_digest_commits_to_encoded_disclosure() -> None:
    encoded, digest = _sd_disclosure("skills", ["Python", "SQL"])
    decoded = json.loads(_b64u_decode(encoded))

    assert len(decoded) == 3
    assert decoded[1] == "skills"
    assert decoded[2] == ["Python", "SQL"]
    assert digest == _b64u(hashlib.sha256(encoded.encode("ascii")).digest())


def test_authorization_metadata_requires_pkce_s256() -> None:
    issuer = SimpleNamespace(
        issuer_identifier="https://career.example/oid4vci/example"
    )
    metadata = authorization_server_metadata(issuer)

    assert metadata["code_challenge_methods_supported"] == ["S256"]
    assert "authorization_code" in metadata["grant_types_supported"]
    assert (
        "urn:ietf:params:oauth:grant-type:pre-authorized_code"
        in metadata["grant_types_supported"]
    )


def test_holder_proof_is_nonce_and_audience_bound() -> None:
    private = ec.generate_private_key(ec.SECP256R1())
    public_jwk = _public_jwk(private)
    private_pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )

    nonce = "nonce-for-test"
    issuer = SimpleNamespace(
        issuer_identifier="https://career.example/oid4vci/example"
    )
    token = SimpleNamespace(
        nonce_hash=_sha256_text(nonce)
    )
    proof = jwt.encode(
        {
            "aud": issuer.issuer_identifier,
            "nonce": nonce,
            "iat": int(time.time()),
        },
        private_pem,
        algorithm="ES256",
        headers={
            "typ": "openid4vci-proof+jwt",
            "jwk": public_jwk,
        },
    )

    resolved = verify_holder_proof(issuer, token, proof)

    assert resolved["kty"] == "EC"
    assert resolved["crv"] == "P-256"


def test_holder_proof_rejects_wrong_nonce() -> None:
    private = ec.generate_private_key(ec.SECP256R1())
    private_pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    issuer = SimpleNamespace(
        issuer_identifier="https://career.example/oid4vci/example"
    )
    token = SimpleNamespace(
        nonce_hash=_sha256_text("expected")
    )
    proof = jwt.encode(
        {
            "aud": issuer.issuer_identifier,
            "nonce": "wrong",
            "iat": int(time.time()),
        },
        private_pem,
        algorithm="ES256",
        headers={
            "typ": "openid4vci-proof+jwt",
            "jwk": _public_jwk(private),
        },
    )

    with pytest.raises(ValueError, match="nonce"):
        verify_holder_proof(issuer, token, proof)


@pytest.mark.asyncio
async def test_policy_blocks_issuer_private_key_export() -> None:
    result = await evaluate_policy(
        "credential.issuer_private_key.export",
        {},
    )
    assert result["allow"] is False


@pytest.mark.asyncio
async def test_policy_blocks_dynamic_trust_anchor_fetching() -> None:
    result = await evaluate_policy(
        "credential.trust_anchor.dynamic_fetch",
        {},
    )
    assert result["allow"] is False


@pytest.mark.asyncio
async def test_privacy_analytics_policy_requires_both_controls() -> None:
    denied = await evaluate_policy(
        "privacy.analytics.release",
        {
            "minimum_group_met": False,
            "epsilon_budget_available": True,
        },
    )
    allowed = await evaluate_policy(
        "privacy.analytics.release",
        {
            "minimum_group_met": True,
            "epsilon_budget_available": True,
        },
    )

    assert denied["allow"] is False
    assert allowed["allow"] is True
