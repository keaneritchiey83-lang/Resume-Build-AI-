from __future__ import annotations

import pytest

from app.career_agents import validate_agent_outputs
from app.models import Job
from app.monitoring import evaluate_job_fit
from app.schemas import (
    AgentEvidenceStrength,
    CandidateProfile,
    Experience,
    FitAgentOutput,
    InterviewCoachOutput,
    ResumeStrategyOutput,
)


def candidate() -> CandidateProfile:
    return CandidateProfile(
        full_name="Example Candidate",
        summary="Software professional.",
        skills=["Python", "SQL", "FastAPI"],
        abilities=["Technical Writing"],
        experience=[
            Experience(
                title="Software Developer",
                organization="Example Company",
                start_date="2023",
                end_date="2026",
                bullets=[
                    "Built Python APIs for internal workflow automation.",
                    "Documented technical systems for engineering teams.",
                ],
            )
        ],
    )


def test_job_monitor_uses_verified_profile_overlap() -> None:
    profile = candidate()
    job = Job(
        id="job-1",
        source="test",
        external_id="1",
        title="Senior Python API Engineer",
        organization="Example Employer",
        location="Columbus, OH",
        description=(
            "Build Python and FastAPI services. SQL experience preferred. "
            "This position is hybrid."
        ),
        apply_url="https://example.invalid/apply",
    )

    result = evaluate_job_fit(
        profile,
        job,
        {
            "target_roles": ["Python Engineer"],
            "target_locations": ["Columbus"],
            "remote_preference": "hybrid",
        },
    )

    assert result["score"] >= 65
    assert "Python" in result["matched_skills"]
    assert "FastAPI" in result["matched_skills"]
    assert result["method"] == "deterministic_profile_preference_overlap_v1"


def test_agent_output_rejects_unverified_skill() -> None:
    profile = candidate()

    fit = FitAgentOutput(
        assessment="Good alignment.",
        strengths=[
            AgentEvidenceStrength(
                statement="Verified Python experience.",
                evidence_ids=["skill:0"],
            )
        ],
        gaps=["Kubernetes is not verified."],
        warnings=[],
    )
    resume = ResumeStrategyOutput(
        headline_direction="Python API developer",
        summary_focus=["API experience"],
        experience_focus=[
            AgentEvidenceStrength(
                statement="Emphasize API work.",
                evidence_ids=["exp:0:bullet:0"],
            )
        ],
        skills_to_emphasize=["Python", "Kubernetes"],
        warnings=[],
    )
    interview = InterviewCoachOutput(
        questions=["Describe an API you built."],
        evidence_ids_to_practice=["exp:0:bullet:0"],
        preparation_actions=["Practice a STAR response."],
        warnings=[],
    )

    with pytest.raises(ValueError, match="unverified skills"):
        validate_agent_outputs(profile, fit, resume, interview)


def test_agent_output_rejects_fake_evidence_id() -> None:
    profile = candidate()

    fit = FitAgentOutput(
        assessment="Assessment",
        strengths=[
            AgentEvidenceStrength(
                statement="Unsupported claim.",
                evidence_ids=["fake:fact"],
            )
        ],
        gaps=[],
        warnings=[],
    )
    resume = ResumeStrategyOutput(
        headline_direction="Developer",
        summary_focus=[],
        experience_focus=[],
        skills_to_emphasize=["Python"],
        warnings=[],
    )
    interview = InterviewCoachOutput(
        questions=[],
        evidence_ids_to_practice=[],
        preparation_actions=[],
        warnings=[],
    )

    with pytest.raises(ValueError, match="unknown candidate facts"):
        validate_agent_outputs(profile, fit, resume, interview)


def test_agent_output_rejects_new_numeric_claim() -> None:
    profile = candidate()

    fit = FitAgentOutput(
        assessment="Assessment",
        strengths=[
            AgentEvidenceStrength(
                statement="Delivered 99% improvement with Python.",
                evidence_ids=["skill:0"],
            )
        ],
        gaps=[],
        warnings=[],
    )
    resume = ResumeStrategyOutput(
        headline_direction="Python developer",
        summary_focus=[],
        experience_focus=[],
        skills_to_emphasize=["Python"],
        warnings=[],
    )
    interview = InterviewCoachOutput(
        questions=[],
        evidence_ids_to_practice=[],
        preparation_actions=[],
        warnings=[],
    )

    with pytest.raises(ValueError, match="numeric claims"):
        validate_agent_outputs(profile, fit, resume, interview)
