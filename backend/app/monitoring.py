from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.career_agents import agent_input_digest, run_career_agent_team
from app.config import settings
from app.crypto import decrypt_text, encrypt_text
from app.models import (
    CareerAgentRun,
    CareerMonitorPolicy,
    ConsentEvent,
    Job,
    JobRecommendation,
)
from app.schemas import (
    CandidateProfile,
    CareerAgentRunResponse,
    JobRecommendationResponse,
    MonitorPolicyRequest,
    MonitorPolicyResponse,
)
from app.services import approved_knowledge_context, load_profile


PURPOSES = {
    "job_monitoring",
    "ai_career_analysis",
    "in_app_notifications",
}


def _normalize(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9+#.\- ]", " ", value.lower()).split())


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in _normalize(value).split()
        if len(token) >= 3
    }


def _preferences_aad(user_id: str) -> str:
    return f"career-monitor:{user_id}"


def _recommendation_aad(user_id: str, recommendation_id: str) -> str:
    return f"job-recommendation:{user_id}:{recommendation_id}"


def _agent_run_aad(user_id: str, run_id: str) -> str:
    return f"career-agent-run:{user_id}:{run_id}"


def monitor_preferences(
    policy: CareerMonitorPolicy,
) -> dict[str, Any]:
    return json.loads(
        decrypt_text(
            policy.encrypted_preferences,
            aad=_preferences_aad(policy.user_id),
        )
    )


def consent_allows(
    policy: CareerMonitorPolicy | None,
    purpose: str,
) -> bool:
    if (
        policy is None
        or not policy.enabled
        or policy.revoked_at is not None
        or purpose not in PURPOSES
    ):
        return False

    preferences = monitor_preferences(policy)
    return purpose in set(preferences.get("purposes", []))


async def update_monitor_policy(
    session: AsyncSession,
    user_id: str,
    payload: MonitorPolicyRequest,
) -> CareerMonitorPolicy:
    if payload.enabled:
        if not payload.acknowledged:
            raise ValueError("Enabling monitoring requires explicit acknowledgement.")
        if "job_monitoring" not in payload.purposes:
            raise ValueError("job_monitoring consent is required to enable monitoring.")

    purposes = sorted(set(payload.purposes) & PURPOSES)
    preferences = {
        "purposes": purposes,
        "target_roles": [value.strip() for value in payload.target_roles if value.strip()],
        "target_locations": [
            value.strip() for value in payload.target_locations if value.strip()
        ],
        "remote_preference": payload.remote_preference,
        "max_alerts_per_scan": payload.max_alerts_per_scan,
    }
    now = datetime.now(UTC)
    evidence_source = json.dumps(
        {
            "enabled": payload.enabled,
            "purposes": purposes,
            "consent_version": settings.agent_consent_version,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    evidence_hash = hashlib.sha256(evidence_source.encode("utf-8")).hexdigest()

    existing = await session.get(CareerMonitorPolicy, user_id)
    previous_purposes: set[str] = set()
    previous_enabled = False
    previous_revoked = True

    if existing is not None:
        previous_purposes = set(
            monitor_preferences(existing).get("purposes", [])
        )
        previous_enabled = existing.enabled
        previous_revoked = existing.revoked_at is not None

    if existing is None:
        existing = CareerMonitorPolicy(
            user_id=user_id,
            enabled=payload.enabled,
            encrypted_preferences="",
            minimum_match_score=payload.minimum_match_score,
            cadence=payload.cadence,
            allow_ai_analysis="ai_career_analysis" in purposes,
            allow_notifications="in_app_notifications" in purposes,
            consent_version=settings.agent_consent_version,
        )
        session.add(existing)

    existing.enabled = payload.enabled
    existing.encrypted_preferences = encrypt_text(
        json.dumps(preferences, separators=(",", ":")),
        aad=_preferences_aad(user_id),
    )
    existing.minimum_match_score = payload.minimum_match_score
    existing.cadence = payload.cadence
    existing.allow_ai_analysis = "ai_career_analysis" in purposes
    existing.allow_notifications = "in_app_notifications" in purposes
    existing.consent_version = settings.agent_consent_version
    existing.consented_at = now if payload.enabled else existing.consented_at
    existing.revoked_at = None if payload.enabled else now

    all_purposes = previous_purposes | set(purposes)

    for purpose in sorted(all_purposes):
        was_allowed = (
            previous_enabled
            and not previous_revoked
            and purpose in previous_purposes
        )
        is_allowed = payload.enabled and purpose in purposes

        if was_allowed == is_allowed:
            continue

        session.add(
            ConsentEvent(
                user_id=user_id,
                purpose=purpose,
                action="granted" if is_allowed else "revoked",
                consent_version=settings.agent_consent_version,
                source="user_settings",
                evidence_hash=evidence_hash,
            )
        )

    await session.commit()
    await session.refresh(existing)
    return existing


def policy_response(
    policy: CareerMonitorPolicy,
) -> MonitorPolicyResponse:
    preferences = monitor_preferences(policy)
    return MonitorPolicyResponse(
        enabled=policy.enabled,
        purposes=list(preferences.get("purposes", [])),
        target_roles=list(preferences.get("target_roles", [])),
        target_locations=list(preferences.get("target_locations", [])),
        remote_preference=str(preferences.get("remote_preference", "any")),
        minimum_match_score=policy.minimum_match_score,
        cadence=policy.cadence,
        max_alerts_per_scan=int(preferences.get("max_alerts_per_scan", 20)),
        consent_version=policy.consent_version,
        consented_at=policy.consented_at,
        revoked_at=policy.revoked_at,
        last_scanned_at=policy.last_scanned_at,
    )


def policy_is_due(
    policy: CareerMonitorPolicy,
    now: datetime | None = None,
) -> bool:
    if not consent_allows(policy, "job_monitoring"):
        return False

    if policy.last_scanned_at is None:
        return True

    current = now or datetime.now(UTC)
    minimum_age = {
        "realtime": timedelta(minutes=15),
        "daily": timedelta(hours=20),
        "weekly": timedelta(days=6),
    }.get(policy.cadence, timedelta(days=1))

    return current - policy.last_scanned_at >= minimum_age


def evaluate_job_fit(
    profile: CandidateProfile,
    job: Job,
    preferences: dict[str, Any],
) -> dict[str, Any]:
    candidate_skills = [
        value.strip()
        for value in profile.skills + profile.abilities
        if value.strip()
    ]
    job_text = _normalize(
        f"{job.title} {job.organization} {job.location} {job.description}"
    )

    matched_skills = [
        skill for skill in candidate_skills if _normalize(skill) in job_text
    ]

    skill_denominator = max(min(len(candidate_skills), 12), 1)
    skill_score = 65.0 * min(len(matched_skills) / skill_denominator, 1.0)

    target_roles = [
        value for value in preferences.get("target_roles", []) if value.strip()
    ]
    role_score = 0.0

    if target_roles:
        job_title_tokens = _tokens(job.title)
        best_overlap = 0.0

        for target in target_roles:
            target_tokens = _tokens(target)
            if not target_tokens:
                continue
            overlap = len(job_title_tokens & target_tokens) / len(target_tokens)
            best_overlap = max(best_overlap, overlap)

        role_score = 20.0 * min(best_overlap, 1.0)
    else:
        role_score = 10.0

    target_locations = [
        _normalize(value)
        for value in preferences.get("target_locations", [])
        if value.strip()
    ]
    location_score = 0.0
    job_location = _normalize(job.location)

    if not target_locations:
        location_score = 5.0
    elif any(location in job_location for location in target_locations):
        location_score = 10.0

    remote_preference = str(preferences.get("remote_preference", "any"))
    remote_score = 5.0

    if remote_preference != "any":
        remote_terms = {
            "remote": {"remote", "telework", "telecommute"},
            "hybrid": {"hybrid"},
            "on_site": {"on-site", "onsite", "on site"},
        }[remote_preference]
        remote_score = (
            5.0
            if any(term in job_text for term in remote_terms)
            else 0.0
        )

    score = round(
        min(100.0, skill_score + role_score + location_score + remote_score),
        1,
    )

    reasons: list[str] = []

    if matched_skills:
        reasons.append(
            "Verified profile skills found in the posting: "
            + ", ".join(matched_skills[:8])
        )
    if role_score >= 10:
        reasons.append("Job title overlaps with a target role.")
    if location_score >= 10:
        reasons.append("Job location matches a saved location preference.")
    if remote_score >= 5 and remote_preference != "any":
        reasons.append(f"Posting matches the {remote_preference} work preference.")

    return {
        "score": score,
        "matched_skills": matched_skills[:20],
        "reasons": reasons,
        "method": "deterministic_profile_preference_overlap_v1",
    }


async def evaluate_user_monitor(
    session: AsyncSession,
    user_id: str,
) -> list[str]:
    policy = await session.get(CareerMonitorPolicy, user_id)

    if policy is None or not consent_allows(policy, "job_monitoring"):
        return []

    profile = await load_profile(session, user_id)
    preferences = monitor_preferences(policy)
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=45)

    jobs = (
        await session.scalars(
            select(Job)
            .where(
                Job.updated_at >= cutoff,
                (Job.expires_at.is_(None)) | (Job.expires_at >= now),
            )
            .order_by(Job.updated_at.desc())
            .limit(600)
        )
    ).all()

    qualifying: list[tuple[str, float]] = []

    for job in jobs:
        analysis = evaluate_job_fit(profile, job, preferences)

        if analysis["score"] < policy.minimum_match_score:
            continue

        existing = await session.scalar(
            select(JobRecommendation).where(
                JobRecommendation.user_id == user_id,
                JobRecommendation.job_id == job.id,
            )
        )

        if existing is None:
            recommendation = JobRecommendation(
                user_id=user_id,
                job_id=job.id,
                score=analysis["score"],
                encrypted_analysis="",
                state="new",
                notified_at=(
                    now if consent_allows(policy, "in_app_notifications") else None
                ),
            )
            session.add(recommendation)
            await session.flush()
        else:
            recommendation = existing
            recommendation.score = analysis["score"]
            recommendation.evaluated_at = now

        recommendation.encrypted_analysis = encrypt_text(
            json.dumps(analysis, separators=(",", ":")),
            aad=_recommendation_aad(user_id, recommendation.id),
        )

        if (
            consent_allows(policy, "in_app_notifications")
            and recommendation.notified_at is None
            and recommendation.state not in {"dismissed", "applied"}
        ):
            recommendation.notified_at = now

        if (
            recommendation.state not in {"dismissed", "applied"}
            and recommendation.agent_analyzed_at is None
        ):
            qualifying.append((recommendation.id, recommendation.score))

    policy.last_scanned_at = now
    await session.commit()

    max_alerts = int(preferences.get("max_alerts_per_scan", 20))
    qualifying.sort(key=lambda item: item[1], reverse=True)
    return [item[0] for item in qualifying[:max_alerts]]


async def recommendation_response(
    session: AsyncSession,
    recommendation: JobRecommendation,
) -> JobRecommendationResponse:
    job = await session.get(Job, recommendation.job_id)

    if job is None:
        raise LookupError("Recommended job is no longer available.")

    analysis = json.loads(
        decrypt_text(
            recommendation.encrypted_analysis,
            aad=_recommendation_aad(
                recommendation.user_id,
                recommendation.id,
            ),
        )
    )

    return JobRecommendationResponse(
        id=recommendation.id,
        job_id=job.id,
        title=job.title,
        organization=job.organization,
        location=job.location,
        apply_url=job.apply_url,
        score=recommendation.score,
        state=recommendation.state,
        matched_skills=list(analysis.get("matched_skills", [])),
        reasons=list(analysis.get("reasons", [])),
        evaluated_at=recommendation.evaluated_at,
        notified_at=recommendation.notified_at,
        agent_analyzed_at=recommendation.agent_analyzed_at,
    )


async def list_recommendations(
    session: AsyncSession,
    user_id: str,
    *,
    limit: int = 50,
) -> list[JobRecommendationResponse]:
    records = (
        await session.scalars(
            select(JobRecommendation)
            .where(JobRecommendation.user_id == user_id)
            .order_by(
                JobRecommendation.score.desc(),
                JobRecommendation.evaluated_at.desc(),
            )
            .limit(limit)
        )
    ).all()

    return [
        await recommendation_response(session, record)
        for record in records
    ]


async def run_agent_for_recommendation(
    session: AsyncSession,
    user_id: str,
    recommendation_id: str,
    *,
    trigger: str = "manual",
) -> CareerAgentRunResponse:
    policy = await session.get(CareerMonitorPolicy, user_id)

    if policy is None or not consent_allows(policy, "ai_career_analysis"):
        raise PermissionError(
            "AI career analysis requires active ai_career_analysis consent."
        )

    recommendation = await session.scalar(
        select(JobRecommendation).where(
            JobRecommendation.id == recommendation_id,
            JobRecommendation.user_id == user_id,
        )
    )

    if recommendation is None:
        raise LookupError("Job recommendation not found.")

    job = await session.get(Job, recommendation.job_id)

    if job is None:
        raise LookupError("Recommended job is no longer available.")

    profile = await load_profile(session, user_id)
    run = CareerAgentRun(
        user_id=user_id,
        job_id=job.id,
        agent_type="career_agent_team_v1",
        trigger=trigger,
        status="running",
        input_digest=agent_input_digest(profile, job),
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    try:
        knowledge = await approved_knowledge_context(
            session,
            f"{job.title} {job.description[:8000]}",
            limit=5,
        )
        report, total_tokens = await run_career_agent_team(
            profile,
            job,
            knowledge,
        )
        run.encrypted_result = encrypt_text(
            report.model_dump_json(),
            aad=_agent_run_aad(user_id, run.id),
        )
        run.total_tokens = total_tokens
        run.status = "completed"
        run.finished_at = datetime.now(UTC)
        recommendation.agent_analyzed_at = run.finished_at
        await session.commit()

        return CareerAgentRunResponse(
            run_id=run.id,
            status=run.status,
            total_tokens=run.total_tokens,
            report=report,
        )

    except Exception as exc:
        run.status = "failed"
        run.error = f"{type(exc).__name__}: {str(exc)[:1800]}"
        run.finished_at = datetime.now(UTC)
        await session.commit()
        raise


async def get_agent_run(
    session: AsyncSession,
    user_id: str,
    run_id: str,
) -> CareerAgentRunResponse:
    run = await session.scalar(
        select(CareerAgentRun).where(
            CareerAgentRun.id == run_id,
            CareerAgentRun.user_id == user_id,
        )
    )

    if run is None:
        raise LookupError("Agent run not found.")
    if run.status != "completed" or not run.encrypted_result:
        raise RuntimeError(f"Agent run is {run.status}.")

    from app.schemas import CareerAgentReport

    report = CareerAgentReport.model_validate_json(
        decrypt_text(
            run.encrypted_result,
            aad=_agent_run_aad(user_id, run.id),
        )
    )
    return CareerAgentRunResponse(
        run_id=run.id,
        status=run.status,
        total_tokens=run.total_tokens,
        report=report,
    )
