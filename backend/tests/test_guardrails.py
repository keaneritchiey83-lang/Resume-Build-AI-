import base64
import os

import pytest

from app.llm import (
    _assert_evidence_ids,
    _assert_no_missing_skill_claims,
    _assert_no_unsupported_numbers,
    build_fact_ledger,
)
from app.schemas import CandidateProfile, Experience, TargetJob


@pytest.fixture
def profile() -> CandidateProfile:
    return CandidateProfile(
        full_name="Example Candidate",
        summary="Software professional.",
        skills=["Python", "SQL"],
        experience=[
            Experience(
                title="Developer",
                organization="Example Company",
                start_date="2022",
                end_date="2025",
                bullets=[
                    "Reduced processing time by 25% using Python automation."
                ],
            )
        ],
    )


@pytest.fixture
def target() -> TargetJob:
    return TargetJob(
        title="Platform Engineer",
        description="Python, SQL, Kubernetes and cloud systems.",
        required_skills=["Python", "SQL", "Kubernetes"],
    )


def test_fact_ledger_contains_source_bullet(profile: CandidateProfile) -> None:
    ledger = build_fact_ledger(profile)
    assert (
        ledger.facts["exp:0:bullet:0"]
        == "Reduced processing time by 25% using Python automation."
    )


def test_guardrail_accepts_supported_number(profile: CandidateProfile) -> None:
    ledger = build_fact_ledger(profile)
    _assert_no_unsupported_numbers(
        "Reduced processing time by 25%.",
        ledger,
    )


def test_guardrail_rejects_new_metric(profile: CandidateProfile) -> None:
    ledger = build_fact_ledger(profile)

    with pytest.raises(ValueError):
        _assert_no_unsupported_numbers(
            "Reduced processing time by 75%.",
            ledger,
        )


def test_guardrail_rejects_missing_skill(
    profile: CandidateProfile,
    target: TargetJob,
) -> None:
    with pytest.raises(ValueError):
        _assert_no_missing_skill_claims(
            "Experienced with Kubernetes.",
            profile,
            target,
        )


def test_guardrail_rejects_unknown_evidence(profile: CandidateProfile) -> None:
    ledger = build_fact_ledger(profile)

    with pytest.raises(ValueError):
        _assert_evidence_ids(["fake:fact"], ledger)


def test_guardrail_accepts_real_evidence(profile: CandidateProfile) -> None:
    ledger = build_fact_ledger(profile)
    _assert_evidence_ids(["exp:0:bullet:0"], ledger)
