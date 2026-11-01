from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto import encrypt_text
from app.models import (
    CareerConcept,
    CareerForecast,
    EducationPathway,
    LearningPlan,
    MobilityMapping,
    SalaryBenchmark,
)
from app.schemas import (
    CareerForecastRequest,
    CareerForecastResponse,
    CareerPathScenario,
    LearningPlanRequest,
    LearningPlanResponse,
    LearningPlanStep,
)
from app.services import load_profile


METHOD_VERSION = "phase7-pathways-v1"


def _normalize(value: str) -> str:
    return " ".join(
        re.sub(r"[^a-z0-9+#.\- ]", " ", value.lower()).split()
    )


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()

    for value in values:
        cleaned = value.strip()
        key = _normalize(cleaned)

        if key and key not in seen:
            seen.add(key)
            result.append(cleaned)

    return result


async def _occupation_skill_catalog(
    session: AsyncSession,
) -> list[dict[str, Any]]:
    skills = (
        await session.scalars(
            select(CareerConcept).where(
                CareerConcept.source == "onet",
                CareerConcept.kind == "skill",
            )
        )
    ).all()

    catalog: dict[str, dict[str, Any]] = {}

    for skill in skills:
        metadata = skill.metadata_json or {}
        code = str(metadata.get("onet_soc_code", "")).strip()
        title = str(metadata.get("occupation_title", "")).strip()

        if not code or not title:
            continue

        item = catalog.setdefault(
            code,
            {
                "occupation_code": code,
                "occupation_title": title,
                "skills": [],
                "sources": {"O*NET"},
            },
        )
        item["skills"].append(skill.title)

    return list(catalog.values())


def _fit_score(
    candidate_skills: list[str],
    required_skills: list[str],
) -> tuple[float, list[str], list[str]]:
    candidate_map = {_normalize(value): value for value in candidate_skills}
    matched: list[str] = []
    missing: list[str] = []

    for required in _unique(required_skills):
        key = _normalize(required)
        match = next(
            (
                original
                for candidate_key, original in candidate_map.items()
                if candidate_key == key
                or key in candidate_key
                or candidate_key in key
            ),
            None,
        )

        if match:
            matched.append(match)
        else:
            missing.append(required)

    if not required_skills:
        return 0.0, [], []

    score = round(100 * len(matched) / len(_unique(required_skills)), 1)
    return score, _unique(matched), _unique(missing)


def _effort(score: float, gaps: int) -> str:
    if score >= 75 and gaps <= 3:
        return "low"
    if score >= 45 and gaps <= 8:
        return "moderate"
    return "high"


async def build_forecast(
    session: AsyncSession,
    user_id: str,
    request: CareerForecastRequest,
) -> CareerForecastResponse:
    profile = await load_profile(session, user_id)
    candidate_skills = _unique(profile.skills + profile.abilities)
    catalog = await _occupation_skill_catalog(session)

    requested_roles = [_normalize(value) for value in request.target_roles if value.strip()]
    scenarios: list[CareerPathScenario] = []

    for item in catalog:
        if requested_roles:
            title_key = _normalize(item["occupation_title"])

            if not any(
                role in title_key or title_key in role
                for role in requested_roles
            ):
                continue

        score, matched, gaps = _fit_score(candidate_skills, item["skills"])
        scenarios.append(
            CareerPathScenario(
                occupation_code=item["occupation_code"],
                occupation_title=item["occupation_title"],
                fit_score=score,
                current_skill_overlap=matched[:20],
                skill_gaps=gaps[:20],
                transition_effort=_effort(score, len(gaps)),
                evidence_sources=sorted(item["sources"]),
                warning=(
                    "Scenario score reflects verified skill overlap only. "
                    "It is not a prediction of promotion, hiring, salary, or success."
                ),
            )
        )

    scenarios.sort(key=lambda value: value.fit_score, reverse=True)
    scenarios = scenarios[: request.max_scenarios]

    latest_taxonomy_update = await session.scalar(
        select(func.max(CareerConcept.updated_at)).where(
            CareerConcept.source == "onet"
        )
    )
    data_version = (
        f"O*NET-cache:{latest_taxonomy_update.isoformat()}"
        if latest_taxonomy_update is not None
        else "O*NET-cache:unknown"
    )

    record = CareerForecast(
        user_id=user_id,
        target_country=request.target_country.upper(),
        method_version=METHOD_VERSION,
        data_version=data_version,
        encrypted_result="",
    )
    session.add(record)
    await session.flush()

    payload = {
        "scenarios": [item.model_dump(mode="json") for item in scenarios],
        "target_country": request.target_country.upper(),
    }
    record.encrypted_result = encrypt_text(
        json.dumps(payload, ensure_ascii=False),
        aad=f"career-forecast:{user_id}:{record.id}",
    )

    await session.commit()

    return CareerForecastResponse(
        forecast_id=record.id,
        method_version=METHOD_VERSION,
        data_version=data_version,
        scenarios=scenarios,
        disclaimer=(
            "Career pathways are evidence-backed scenarios, not forecasts of "
            "employment outcomes. Licensing, immigration, education, and local "
            "regulatory requirements must be verified separately."
        ),
    )


async def build_learning_plan(
    session: AsyncSession,
    user_id: str,
    request: LearningPlanRequest,
) -> LearningPlanResponse:
    profile = await load_profile(session, user_id)
    existing = _unique(profile.skills + profile.abilities)
    _, _, gaps = _fit_score(existing, request.required_skills)

    steps: list[LearningPlanStep] = []

    for gap in gaps:
        pattern = f"%{gap}%"
        statement = select(EducationPathway).where(
            EducationPathway.status == "approved",
            or_(
                EducationPathway.title.ilike(pattern),
                EducationPathway.description.ilike(pattern),
            ),
        )

        if request.country_code:
            statement = statement.where(
                or_(
                    EducationPathway.country_code == request.country_code.upper(),
                    EducationPathway.country_code == "",
                )
            )

        pathways = (
            await session.scalars(
                statement.order_by(EducationPathway.updated_at.desc()).limit(5)
            )
        ).all()

        approved = [
            {
                "title": item.title,
                "provider": item.provider,
                "type": item.pathway_type,
                "source": item.source,
                "source_url": item.source_url,
            }
            for item in pathways
            if any(
                _normalize(gap) in _normalize(skill)
                or _normalize(skill) in _normalize(gap)
                for skill in item.skills
            )
            or _normalize(gap) in _normalize(item.title)
            or _normalize(gap) in _normalize(item.description)
        ]

        steps.append(
            LearningPlanStep(
                skill=gap,
                reason=(
                    f"{gap} is listed as a target skill and is not present in "
                    "the verified candidate skill ledger."
                ),
                approved_pathways=approved,
            )
        )

    record = LearningPlan(
        user_id=user_id,
        target_occupation_code=request.occupation_code,
        target_occupation_title=request.occupation_title,
        encrypted_plan="",
        method_version=METHOD_VERSION,
    )
    session.add(record)
    await session.flush()

    result = {
        "existing_skills": existing,
        "gaps": gaps,
        "steps": [item.model_dump(mode="json") for item in steps],
    }
    record.encrypted_plan = encrypt_text(
        json.dumps(result, ensure_ascii=False),
        aad=f"learning-plan:{user_id}:{record.id}",
    )

    await session.commit()

    return LearningPlanResponse(
        plan_id=record.id,
        target_occupation_code=request.occupation_code,
        target_occupation_title=request.occupation_title,
        existing_skills=existing,
        gaps=gaps,
        steps=steps,
        warning=(
            "Education and certification entries are suggestions from approved "
            "source records. Verify accreditation, eligibility, cost, recognition, "
            "and licensing requirements before enrolling."
        ),
    )


async def salary_search(
    session: AsyncSession,
    country_code: str,
    occupation: str,
    region_code: str = "",
    limit: int = 25,
) -> list[SalaryBenchmark]:
    statement = select(SalaryBenchmark).where(
        SalaryBenchmark.country_code == country_code.upper(),
        or_(
            SalaryBenchmark.occupation_code.ilike(f"%{occupation}%"),
            SalaryBenchmark.occupation_title.ilike(f"%{occupation}%"),
        ),
    )

    if region_code:
        statement = statement.where(
            SalaryBenchmark.region_code == region_code
        )

    return list(
        (
            await session.scalars(
                statement.order_by(
                    SalaryBenchmark.data_vintage.desc(),
                    SalaryBenchmark.captured_at.desc(),
                ).limit(limit)
            )
        ).all()
    )


async def mobility_search(
    session: AsyncSession,
    from_country: str,
    to_country: str,
    occupation: str,
    limit: int = 25,
) -> list[MobilityMapping]:
    statement = select(MobilityMapping).where(
        MobilityMapping.from_country == from_country.upper(),
        MobilityMapping.to_country == to_country.upper(),
        or_(
            MobilityMapping.from_occupation_code.ilike(f"%{occupation}%"),
            MobilityMapping.from_title.ilike(f"%{occupation}%"),
        ),
    )

    return list(
        (
            await session.scalars(
                statement.order_by(MobilityMapping.skill_overlap.desc()).limit(limit)
            )
        ).all()
    )
