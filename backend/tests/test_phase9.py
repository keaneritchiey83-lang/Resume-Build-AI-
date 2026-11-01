from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.phase9_services import (
    RED_TEAM_CASES,
    _did_method,
)
from app.phase9_schemas import PrivacyImpactAssessmentRequest
from app.phase9_services import _privacy_risk_level


def test_supported_did_methods() -> None:
    assert _did_method("did:key:z6MkgExample") == "key"
    assert _did_method("did:web:wallet.example") == "web"
    assert _did_method("did:jwk:eyJrdHkiOiJFQyJ9") == "jwk"


def test_invalid_did_is_rejected() -> None:
    with pytest.raises(ValueError):
        _did_method("https://wallet.example/user/123")


def test_private_key_custody_boundary_is_documented() -> None:
    root = Path(__file__).resolve().parents[2]
    profile = json.loads(
        (
            root
            / "governance"
            / "phase9"
            / "portable_identity_profile.json"
        ).read_text(encoding="utf-8")
    )

    assert (
        profile["trust_boundaries"]["candidate_private_keys"]
        == "never stored by the platform"
    )


def test_red_team_manual_cases_are_not_auto_passed() -> None:
    assert RED_TEAM_CASES["prompt_injection"]["mode"] == "manual"
    assert RED_TEAM_CASES["data_exfiltration"]["mode"] == "manual"
    assert RED_TEAM_CASES["autonomous_apply"]["mode"] == "policy"


def test_privacy_risk_increases_for_high_risk_automated_processing() -> None:
    result = _privacy_risk_level(
        PrivacyImpactAssessmentRequest(
            name="Employment ranking",
            system_or_process="candidate-ranking",
            processing_purposes=["candidate screening support"],
            data_categories=["profile", "resume", "skills"],
            jurisdictions=["US", "EU"],
            lawful_bases=["review_required"],
            automated_decision_support=True,
            high_risk_processing=True,
            international_transfers=True,
        )
    )

    assert result == "high"
