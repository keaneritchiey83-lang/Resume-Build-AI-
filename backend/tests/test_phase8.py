from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.credential_verification import inspect_credential
from app.governance8 import classify_eu_ai
from app.labor_market import compute_trend
from app.learning_providers import validate_learning_base_url
from app.portfolio import filter_public_portfolio
from app.schemas import AISystemInventoryIn


def test_open_badges_structural_validation_is_not_crypto_verification() -> None:
    payload = {
        "@context": [
            "https://www.w3.org/ns/credentials/v2",
            "https://purl.imsglobal.org/spec/ob/v3p0/context-3.0.3.json",
        ],
        "id": "urn:uuid:example",
        "type": ["VerifiableCredential", "OpenBadgeCredential"],
        "issuer": {
            "id": "https://issuer.example",
            "name": "Example University",
        },
        "validFrom": "2026-01-01T00:00:00Z",
        "credentialSubject": {
            "id": "did:example:learner",
            "achievement": {
                "name": "Cloud Foundations",
                "alignment": [
                    {
                        "targetType": "Skill",
                        "targetName": "Cloud computing",
                    }
                ],
            },
        },
        "proof": {
            "type": "DataIntegrityProof",
            "verificationMethod": "did:example:issuer#key-1",
        },
    }

    result = inspect_credential(payload)

    assert result.credential_format == "open_badges_3"
    assert result.status == "structurally_valid"
    assert result.evidence["proof_present"] is True
    assert result.evidence["cryptographic_proof_checked"] is False
    assert "Cloud computing" in result.skills


def test_expired_credential_is_detected_locally() -> None:
    result = inspect_credential(
        {
            "@context": ["https://www.w3.org/ns/credentials/v2"],
            "type": ["VerifiableCredential"],
            "issuer": "https://issuer.example",
            "validUntil": "2020-01-01T00:00:00Z",
            "credentialSubject": {"id": "did:example:learner"},
        }
    )

    assert result.status == "expired"


def test_labor_trend_increasing() -> None:
    result = compute_trend(
        [
            ("2022", 100.0),
            ("2023", 110.0),
            ("2024", 120.0),
            ("2025", 132.0),
        ]
    )

    assert result["direction"] == "increasing"
    assert result["input_count"] == 4
    assert result["projected_next_value"] > 132.0
    assert 0 < result["confidence"] <= 0.95


def test_public_portfolio_excludes_contact_by_default() -> None:
    payload = {
        "identity": {
            "name": "Candidate",
            "location": "Ohio",
            "email": "candidate@example.com",
            "phone": "555-0100",
        },
        "headline": "Engineer",
        "about": "Profile",
        "skills": ["Python"],
        "experience": [{"title": "Engineer"}],
        "education": [{"credential": "BS"}],
        "verified_credentials": [{"title": "Credential"}],
        "projects": [{"title": "Project"}],
    }

    public = filter_public_portfolio(
        payload,
        {
            "include_contact": False,
            "include_experience": True,
            "include_education": True,
            "include_skills": True,
            "include_credentials": True,
            "include_projects": True,
        },
    )

    assert "email" not in public["identity"]
    assert "phone" not in public["identity"]
    assert public["identity"]["name"] == "Candidate"


def test_employment_profiling_gets_high_risk_candidate_triage() -> None:
    risk_class, basis, applicable_from = classify_eu_ai(
        AISystemInventoryIn(
            system_key="candidate-ranking",
            version="1",
            name="Candidate Ranking",
            intended_purpose="Rank employment candidates for recruiter review.",
            employment_use=True,
            profiles_natural_persons=True,
            materially_influences_decisions=True,
            human_oversight=True,
        )
    )

    assert risk_class == "annex_iii_high_risk_candidate"
    assert applicable_from.isoformat() == "2027-12-02"
    assert basis["assessment_type"] == "triage_only"


def test_learning_provider_allowlist_blocks_unknown_host(monkeypatch) -> None:
    from app.config import settings

    monkeypatch.setattr(
        settings,
        "learning_provider_allowed_hosts",
        "learning.example,localhost",
    )

    # Clear cached property created by pydantic model if present.
    settings.__dict__.pop("learning_provider_allowed_host_set", None)

    assert (
        validate_learning_base_url("https://learning.example")
        == "https://learning.example"
    )

    with pytest.raises(ValueError):
        validate_learning_base_url("https://169.254.169.254")
