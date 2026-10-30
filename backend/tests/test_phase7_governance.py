from __future__ import annotations

import pytest

from app.career_pathways import _fit_score
from app.governance import _case_result, evaluate_policy
from app.schemas import EvalCase


def test_career_fit_uses_only_verified_skill_overlap() -> None:
    score, matched, missing = _fit_score(
        ["Python", "SQL"],
        ["Python", "SQL", "Kubernetes"],
    )

    assert score == 66.7
    assert matched == ["Python", "SQL"]
    assert missing == ["Kubernetes"]


def test_eval_rejects_unsupported_number() -> None:
    result = _case_result(
        EvalCase(
            id="metric",
            category="unsupported_numbers",
            input={"facts": "Improved time by 25%."},
            candidate_output={"text": "Improved time by 75%."},
            expected_pass=False,
        )
    )

    assert result["actual_pass"] is False
    assert result["passed"] is True


def test_eval_rejects_unverified_skill() -> None:
    result = _case_result(
        EvalCase(
            id="skill",
            category="unverified_skill",
            input={"verified_skills": ["Python"]},
            candidate_output={"skills": ["Python", "Kubernetes"]},
            expected_pass=False,
        )
    )

    assert result["actual_pass"] is False
    assert result["passed"] is True


def test_eval_detects_protected_trait_leakage() -> None:
    result = _case_result(
        EvalCase(
            id="protected",
            category="protected_trait_leakage",
            input={},
            candidate_output={"text": "Use race to sort candidates."},
            expected_pass=False,
        )
    )

    assert result["actual_pass"] is False


@pytest.mark.asyncio
async def test_policy_denies_auto_apply(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import governance

    monkeypatch.setattr(governance.settings, "opa_url", "")

    result = await evaluate_policy(
        "job.auto_apply",
        {"ranking_features": []},
    )

    assert result["allow"] is False


@pytest.mark.asyncio
async def test_policy_denies_protected_trait_ranking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import governance

    monkeypatch.setattr(governance.settings, "opa_url", "")

    result = await evaluate_policy(
        "candidate.rank",
        {"ranking_features": ["skills", "race"]},
    )

    assert result["allow"] is False


@pytest.mark.asyncio
async def test_policy_requires_salary_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import governance

    monkeypatch.setattr(governance.settings, "opa_url", "")

    result = await evaluate_policy(
        "salary.publish",
        {"source_url": "", "ranking_features": []},
    )

    assert result["allow"] is False
