from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_user
from app.career_pathways import (
    build_forecast,
    build_learning_plan,
    mobility_search,
    salary_search,
)
from app.db import get_session
from app.governance import (
    collect_soc2_evidence,
    compliance_dashboard,
    create_review,
    evaluate_policy,
    fairness_analysis,
    run_eval_suite,
    source_hash,
)
from app.models import (
    CareerMonitorPolicy,
    EducationPathway,
    GovernancePolicy,
    HumanReviewItem,
    MobilityMapping,
    ModelEvalSuite,
    SalaryBenchmark,
    User,
)
from app.monitoring import consent_allows
from app.schemas import (
    CareerForecastRequest,
    CareerForecastResponse,
    ComplianceDashboardResponse,
    EducationPathwayIn,
    EvalRunResponse,
    EvalSuiteCreate,
    FairnessAnalysisRequest,
    FairnessAnalysisResponse,
    HumanReviewCreate,
    HumanReviewUpdate,
    LearningPlanRequest,
    LearningPlanResponse,
    MobilityMappingIn,
    SalaryBenchmarkIn,
    SalaryBenchmarkResponse,
)
from app.services import audit
from app.tenancy import require_org_role, require_platform_admin


router = APIRouter()


async def platform_admin_user(
    user: User = Depends(current_user),
) -> User:
    require_platform_admin(user)
    return user


async def _require_career_analysis_consent(
    session: AsyncSession,
    user: User,
) -> None:
    policy = await session.get(CareerMonitorPolicy, user.id)

    if not consent_allows(policy, "ai_career_analysis"):
        raise HTTPException(
            status_code=403,
            detail=(
                "Career-path analysis requires active ai_career_analysis consent "
                "in the monitoring policy."
            ),
        )


@router.post(
    "/v1/career/forecast",
    response_model=CareerForecastResponse,
)
async def career_forecast(
    payload: CareerForecastRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await _require_career_analysis_consent(session, user)
    decision = await evaluate_policy(
        "career.forecast",
        {"consent": True, "ranking_features": []},
    )

    if not decision["allow"]:
        raise HTTPException(status_code=403, detail=decision["reasons"])

    try:
        result = await build_forecast(session, user.id, payload)
    except LookupError as exc:
        raise HTTPException(
            status_code=409,
            detail="Create a verified candidate profile first.",
        ) from exc

    await audit(
        session,
        "phase7.career_forecast",
        user.id,
        {
            "forecast_id": result.forecast_id,
            "method_version": result.method_version,
        },
    )
    return result


@router.post(
    "/v1/career/learning-plan",
    response_model=LearningPlanResponse,
)
async def learning_plan(
    payload: LearningPlanRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await _require_career_analysis_consent(session, user)

    try:
        result = await build_learning_plan(session, user.id, payload)
    except LookupError as exc:
        raise HTTPException(
            status_code=409,
            detail="Create a verified candidate profile first.",
        ) from exc

    await audit(
        session,
        "phase7.learning_plan",
        user.id,
        {
            "plan_id": result.plan_id,
            "occupation_code": payload.occupation_code,
        },
    )
    return result


@router.get(
    "/v1/career/salary",
    response_model=list[SalaryBenchmarkResponse],
)
async def salary_intelligence(
    country: str = Query(min_length=2, max_length=3),
    occupation: str = Query(min_length=1, max_length=300),
    region: str = Query(default="", max_length=100),
    limit: int = Query(default=25, ge=1, le=100),
    _: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    records = await salary_search(
        session,
        country,
        occupation,
        region,
        limit,
    )

    return [
        SalaryBenchmarkResponse(
            id=record.id,
            source=record.source,
            data_vintage=record.data_vintage,
            country_code=record.country_code,
            region_code=record.region_code,
            occupation_code=record.occupation_code,
            occupation_title=record.occupation_title,
            currency=record.currency,
            wage_p10=record.wage_p10,
            wage_p25=record.wage_p25,
            wage_median=record.wage_median,
            wage_p75=record.wage_p75,
            wage_p90=record.wage_p90,
            annual_mean=record.annual_mean,
            employment=record.employment,
            source_url=record.source_url,
            license=record.license,
            captured_at=record.captured_at,
        )
        for record in records
    ]


@router.get("/v1/career/mobility")
async def mobility(
    from_country: str = Query(min_length=2, max_length=3),
    to_country: str = Query(min_length=2, max_length=3),
    occupation: str = Query(min_length=1, max_length=300),
    limit: int = Query(default=25, ge=1, le=100),
    _: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    records = await mobility_search(
        session,
        from_country,
        to_country,
        occupation,
        limit,
    )

    return [
        {
            "id": item.id,
            "source": item.source,
            "from_country": item.from_country,
            "from_occupation_code": item.from_occupation_code,
            "from_title": item.from_title,
            "to_country": item.to_country,
            "to_occupation_code": item.to_occupation_code,
            "to_title": item.to_title,
            "common_taxonomy": item.common_taxonomy,
            "common_code": item.common_code,
            "skill_overlap": item.skill_overlap,
            "transition_effort": item.transition_effort,
            "evidence": item.evidence,
            "source_url": item.source_url,
            "warning": (
                "Occupation mapping does not establish immigration eligibility, "
                "license recognition, or right to work."
            ),
        }
        for item in records
    ]


@router.post("/v1/admin/phase7/salary-benchmarks")
async def import_salary_benchmark(
    payload: SalaryBenchmarkIn,
    user: User = Depends(platform_admin_user),
    session: AsyncSession = Depends(get_session),
):
    decision = await evaluate_policy(
        "salary.publish",
        {
            "source_url": payload.source_url,
            "ranking_features": [],
        },
    )

    if not decision["allow"]:
        raise HTTPException(status_code=422, detail=decision["reasons"])

    statement = insert(SalaryBenchmark).values(
        **payload.model_dump(),
    )
    statement = statement.on_conflict_do_update(
        constraint="uq_salary_benchmark_source_vintage_geo_occ",
        set_={
            "occupation_title": statement.excluded.occupation_title,
            "currency": statement.excluded.currency,
            "wage_p10": statement.excluded.wage_p10,
            "wage_p25": statement.excluded.wage_p25,
            "wage_median": statement.excluded.wage_median,
            "wage_p75": statement.excluded.wage_p75,
            "wage_p90": statement.excluded.wage_p90,
            "annual_mean": statement.excluded.annual_mean,
            "employment": statement.excluded.employment,
            "source_url": statement.excluded.source_url,
            "license": statement.excluded.license,
            "captured_at": datetime.now(UTC),
        },
    )
    await session.execute(statement)
    await session.commit()
    await audit(
        session,
        "phase7.salary_benchmark.upsert",
        user.id,
        {
            "source": payload.source,
            "occupation_code": payload.occupation_code,
            "country_code": payload.country_code,
        },
    )
    return {"status": "upserted"}


@router.post("/v1/admin/phase7/education-pathways")
async def import_education_pathway(
    payload: EducationPathwayIn,
    user: User = Depends(platform_admin_user),
    session: AsyncSession = Depends(get_session),
):
    statement = insert(EducationPathway).values(
        **payload.model_dump(),
        status="approved",
    )
    statement = statement.on_conflict_do_update(
        constraint="uq_education_pathway_source_external",
        set_={
            "title": statement.excluded.title,
            "provider": statement.excluded.provider,
            "pathway_type": statement.excluded.pathway_type,
            "country_code": statement.excluded.country_code,
            "occupation_code": statement.excluded.occupation_code,
            "skills": statement.excluded.skills,
            "description": statement.excluded.description,
            "source_url": statement.excluded.source_url,
            "license": statement.excluded.license,
            "status": "approved",
            "updated_at": datetime.now(UTC),
        },
    )
    await session.execute(statement)
    await session.commit()
    await audit(
        session,
        "phase7.education_pathway.upsert",
        user.id,
        {
            "source": payload.source,
            "external_id": payload.external_id,
        },
    )
    return {"status": "upserted"}


@router.post("/v1/admin/phase7/mobility-mappings")
async def import_mobility_mapping(
    payload: MobilityMappingIn,
    user: User = Depends(platform_admin_user),
    session: AsyncSession = Depends(get_session),
):
    statement = insert(MobilityMapping).values(**payload.model_dump())
    statement = statement.on_conflict_do_update(
        constraint="uq_mobility_mapping_route",
        set_={
            "from_title": statement.excluded.from_title,
            "to_title": statement.excluded.to_title,
            "common_taxonomy": statement.excluded.common_taxonomy,
            "common_code": statement.excluded.common_code,
            "skill_overlap": statement.excluded.skill_overlap,
            "transition_effort": statement.excluded.transition_effort,
            "evidence": statement.excluded.evidence,
            "source_url": statement.excluded.source_url,
            "updated_at": datetime.now(UTC),
        },
    )
    await session.execute(statement)
    await session.commit()
    await audit(
        session,
        "phase7.mobility_mapping.upsert",
        user.id,
        {
            "from_country": payload.from_country,
            "to_country": payload.to_country,
            "common_code": payload.common_code,
        },
    )
    return {"status": "upserted"}


@router.post(
    "/v1/organizations/{organization_id}/governance/fairness",
    response_model=FairnessAnalysisResponse,
)
async def analyze_fairness(
    organization_id: str,
    payload: FairnessAnalysisRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin"},
    )

    try:
        result = await fairness_analysis(session, organization_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    await audit(
        session,
        "phase7.fairness_analysis",
        user.id,
        {
            "organization_id": organization_id,
            "snapshot_id": result.snapshot_id,
            "requires_review": result.requires_review,
        },
    )
    return result


@router.post(
    "/v1/organizations/{organization_id}/governance/eval-suites",
)
async def create_eval_suite(
    organization_id: str,
    payload: EvalSuiteCreate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin"},
    )

    suite = ModelEvalSuite(
        organization_id=organization_id,
        name=payload.name,
        version=payload.version,
        cases_json=[item.model_dump(mode="json") for item in payload.cases],
    )
    session.add(suite)
    await session.commit()
    await session.refresh(suite)

    return {
        "id": suite.id,
        "name": suite.name,
        "version": suite.version,
        "cases": len(suite.cases_json),
    }


@router.post(
    "/v1/organizations/{organization_id}/governance/eval-suites/{suite_id}/run",
    response_model=EvalRunResponse,
)
async def run_eval(
    organization_id: str,
    suite_id: str,
    model_name: str = Query(default="deterministic-phase7-guardrails", max_length=300),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin"},
    )

    suite = await session.scalar(
        select(ModelEvalSuite).where(
            ModelEvalSuite.id == suite_id,
            ModelEvalSuite.organization_id == organization_id,
        )
    )

    if suite is None:
        raise HTTPException(status_code=404, detail="Evaluation suite not found.")

    result = await run_eval_suite(session, suite, model_name)

    if result.failed:
        await create_review(
            session,
            organization_id=organization_id,
            category="evaluation",
            severity="high",
            subject_type="model_eval_run",
            subject_id=result.id,
            reason=(
                f"Evaluation run failed {result.failed} case(s); "
                "model/workflow release requires human review."
            ),
            context={
                "score": result.score,
                "model_name": result.model_name,
            },
        )

    return result


@router.post("/v1/organizations/{organization_id}/governance/reviews")
async def create_human_review(
    organization_id: str,
    payload: HumanReviewCreate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin"},
    )

    item = await create_review(
        session,
        organization_id=organization_id,
        category=payload.category,
        severity=payload.severity,
        subject_type=payload.subject_type,
        subject_id=payload.subject_id,
        reason=payload.reason,
        context=payload.context,
    )
    return {
        "id": item.id,
        "status": item.status,
        "severity": item.severity,
    }


@router.get("/v1/organizations/{organization_id}/governance/reviews")
async def list_human_reviews(
    organization_id: str,
    status: str = Query(default="", max_length=50),
    limit: int = Query(default=100, ge=1, le=500),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin"},
    )

    statement = select(HumanReviewItem).where(
        HumanReviewItem.organization_id == organization_id
    )

    if status:
        statement = statement.where(HumanReviewItem.status == status)

    records = (
        await session.scalars(
            statement.order_by(HumanReviewItem.created_at.desc()).limit(limit)
        )
    ).all()

    return [
        {
            "id": item.id,
            "category": item.category,
            "severity": item.severity,
            "subject_type": item.subject_type,
            "subject_id": item.subject_id,
            "reason": item.reason,
            "status": item.status,
            "assigned_to_user_id": item.assigned_to_user_id,
            "resolution": item.resolution,
            "created_at": item.created_at,
            "resolved_at": item.resolved_at,
        }
        for item in records
    ]


@router.patch("/v1/organizations/{organization_id}/governance/reviews/{review_id}")
async def update_human_review(
    organization_id: str,
    review_id: str,
    payload: HumanReviewUpdate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin"},
    )

    item = await session.scalar(
        select(HumanReviewItem).where(
            HumanReviewItem.id == review_id,
            HumanReviewItem.organization_id == organization_id,
        )
    )

    if item is None:
        raise HTTPException(status_code=404, detail="Review item not found.")

    item.status = payload.status
    item.resolution = payload.resolution

    if payload.status in {"approved", "rejected", "resolved"}:
        item.resolved_at = datetime.now(UTC)
        item.assigned_to_user_id = user.id

    await session.commit()
    return {"id": item.id, "status": item.status}


@router.post("/v1/organizations/{organization_id}/compliance/evidence/collect")
async def collect_compliance(
    organization_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin"},
    )
    records = await collect_soc2_evidence(session, organization_id)
    return {
        "captured": len(records),
        "note": "Evidence automation does not constitute a SOC 2 audit or report.",
    }


@router.get(
    "/v1/organizations/{organization_id}/compliance/dashboard",
    response_model=ComplianceDashboardResponse,
)
async def compliance(
    organization_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin"},
    )
    return await compliance_dashboard(session, organization_id)


@router.post("/v1/admin/phase7/policies/baseline")
async def register_baseline_policy(
    user: User = Depends(platform_admin_user),
    session: AsyncSession = Depends(get_session),
):
    policy = {
        "deny_autonomous_apply": True,
        "deny_autonomous_employer_message": True,
        "deny_protected_trait_ranking": True,
        "require_salary_provenance": True,
        "require_forecast_consent": True,
        "require_eval_gate_for_model_release": True,
    }
    digest = source_hash(policy)

    existing = await session.scalar(
        select(GovernancePolicy).where(
            GovernancePolicy.organization_id.is_(None),
            GovernancePolicy.policy_key == "baseline-career-ai",
            GovernancePolicy.version == "phase7-governance-v1",
        )
    )

    if existing is None:
        session.add(
            GovernancePolicy(
                organization_id=None,
                policy_key="baseline-career-ai",
                version="phase7-governance-v1",
                enabled=True,
                policy_json=policy,
                source_hash=digest,
            )
        )
        await session.commit()

    return {
        "policy_key": "baseline-career-ai",
        "version": "phase7-governance-v1",
        "source_hash": digest,
    }
