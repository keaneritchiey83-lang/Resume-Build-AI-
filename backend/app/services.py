from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.career_sources import ConceptRecord, ESCOClient, ONetClient
from app.connectors import JobRecord
from app.crypto import decrypt_text, encrypt_text
from app.embeddings import embedding_service
from app.models import (
    Application,
    AuditEvent,
    CandidateProfileRecord,
    CareerConcept,
    Job,
    KnowledgeDocument,
    ResumeDocument,
)
from app.telemetry import emit_security_event
from app.schemas import (
    ApplicationCreate,
    ApplicationResponse,
    CandidateProfile,
)


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9+#.\- ]", " ", value.lower())).strip()


def unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()

    for value in values:
        clean = value.strip()
        key = normalize(clean)

        if key and key not in seen:
            seen.add(key)
            result.append(clean)

    return result


async def audit(
    session: AsyncSession,
    event: str,
    actor: str,
    details: dict[str, Any],
) -> None:
    session.add(AuditEvent(event=event, actor=actor, details=details))
    await session.commit()
    emit_security_event(event, actor, details)


async def save_profile(
    session: AsyncSession,
    user_id: str,
    profile: CandidateProfile,
) -> None:
    encrypted = encrypt_text(
        profile.model_dump_json(),
        aad=f"profile:{user_id}",
    )

    existing = await session.get(CandidateProfileRecord, user_id)

    if existing:
        existing.encrypted_payload = encrypted
    else:
        session.add(
            CandidateProfileRecord(
                user_id=user_id,
                encrypted_payload=encrypted,
            )
        )

    await session.commit()


async def load_profile(
    session: AsyncSession,
    user_id: str,
) -> CandidateProfile:
    record = await session.get(CandidateProfileRecord, user_id)

    if record is None:
        raise LookupError("Candidate profile has not been created.")

    payload = decrypt_text(
        record.encrypted_payload,
        aad=f"profile:{user_id}",
    )
    return CandidateProfile.model_validate_json(payload)


async def save_resume_text(
    session: AsyncSession,
    user_id: str,
    resume_id: str,
    filename: str,
    sha256: str,
    extracted_text: str,
) -> ResumeDocument:
    existing = await session.scalar(
        select(ResumeDocument).where(
            ResumeDocument.user_id == user_id,
            ResumeDocument.sha256 == sha256,
        )
    )

    if existing:
        return existing

    record = ResumeDocument(
        id=resume_id,
        user_id=user_id,
        filename=filename[:500],
        sha256=sha256,
        encrypted_text=encrypt_text(
            extracted_text,
            aad=f"resume:{user_id}:{resume_id}",
        ),
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def upsert_jobs(
    session: AsyncSession,
    records: list[JobRecord],
) -> int:
    for record in records:
        statement = insert(Job).values(
            id=record.id,
            source=record.source,
            external_id=record.external_id,
            title=record.title,
            organization=record.organization,
            location=record.location,
            description=record.description,
            apply_url=record.apply_url,
            posted_at=record.posted_at,
            expires_at=record.expires_at,
            metadata_json=record.metadata,
            updated_at=datetime.now(UTC),
        )
        statement = statement.on_conflict_do_update(
            index_elements=[Job.source, Job.external_id],
            set_={
                "title": statement.excluded.title,
                "organization": statement.excluded.organization,
                "location": statement.excluded.location,
                "description": statement.excluded.description,
                "apply_url": statement.excluded.apply_url,
                "posted_at": statement.excluded.posted_at,
                "expires_at": statement.excluded.expires_at,
                "metadata_json": statement.excluded.metadata_json,
                "updated_at": datetime.now(UTC),
            },
        )
        await session.execute(statement)

    await session.commit()
    return len(records)


async def upsert_concepts(
    session: AsyncSession,
    records: list[ConceptRecord],
) -> int:
    if not records:
        return 0

    vectors = await embedding_service.encode_many(
        [f"{item.title}. {item.description}".strip() for item in records]
    )

    for record, vector in zip(records, vectors, strict=True):
        statement = insert(CareerConcept).values(
            source=record.source,
            external_id=record.external_id,
            kind=record.kind,
            title=record.title,
            description=record.description,
            source_url=record.source_url,
            metadata_json=record.metadata,
            embedding=vector,
            updated_at=datetime.now(UTC),
        )
        statement = statement.on_conflict_do_update(
            index_elements=[CareerConcept.source, CareerConcept.external_id],
            set_={
                "kind": statement.excluded.kind,
                "title": statement.excluded.title,
                "description": statement.excluded.description,
                "source_url": statement.excluded.source_url,
                "metadata_json": statement.excluded.metadata_json,
                "embedding": statement.excluded.embedding,
                "updated_at": datetime.now(UTC),
            },
        )
        await session.execute(statement)

    await session.commit()
    return len(records)


async def sync_onet(
    session: AsyncSession,
    keyword: str,
    limit: int = 8,
) -> int:
    client = ONetClient()
    records: list[ConceptRecord] = []

    for occupation in await client.search_occupations(keyword, limit):
        code = str(occupation.get("code", ""))
        title = str(occupation.get("title", ""))

        if not code or not title:
            continue

        records.append(
            ConceptRecord(
                source="onet",
                external_id=f"occupation:{code}",
                kind="occupation",
                title=title,
                source_url=f"https://www.onetonline.org/link/summary/{code}",
                metadata={"onet_soc_code": code},
            )
        )

        for descriptor_type in ("skills", "abilities"):
            kind = "skill" if descriptor_type == "skills" else "ability"

            for item in await client.descriptor(code, descriptor_type):
                element_id = str(item.get("id", ""))
                name = str(item.get("name", ""))

                if element_id and name:
                    records.append(
                        ConceptRecord(
                            source="onet",
                            external_id=f"{code}:{kind}:{element_id}",
                            kind=kind,
                            title=name,
                            description=str(item.get("description", "")),
                            metadata={
                                "onet_soc_code": code,
                                "occupation_title": title,
                            },
                        )
                    )

    return await upsert_concepts(session, records)


async def sync_esco(
    session: AsyncSession,
    keyword: str,
) -> int:
    client = ESCOClient()
    occupations = await client.search(keyword, "occupation", 15)
    skills = await client.search(keyword, "skill", 25)
    return await upsert_concepts(session, occupations + skills)


async def semantic_concepts(
    session: AsyncSession,
    query: str,
    kind: str | None = None,
    limit: int = 15,
) -> list[dict[str, Any]]:
    vector = await embedding_service.encode(query)
    similarity = (1 - CareerConcept.embedding.cosine_distance(vector)).label(
        "similarity"
    )

    statement = select(CareerConcept, similarity).where(
        CareerConcept.embedding.is_not(None)
    )

    if kind:
        statement = statement.where(CareerConcept.kind == kind)

    rows = (
        await session.execute(
            statement.order_by(similarity.desc()).limit(limit)
        )
    ).all()

    return [
        {
            "source": concept.source,
            "kind": concept.kind,
            "external_id": concept.external_id,
            "title": concept.title,
            "description": concept.description,
            "similarity": round(float(score), 4),
        }
        for concept, score in rows
    ]


async def stage_knowledge(
    session: AsyncSession,
    source: str,
    title: str,
    content: str,
    source_url: str,
    license_name: str,
) -> KnowledgeDocument:
    checksum = hashlib.sha256(
        f"{source}\n{title}\n{content}\n{source_url}".encode()
    ).hexdigest()

    existing = await session.scalar(
        select(KnowledgeDocument).where(KnowledgeDocument.checksum == checksum)
    )

    if existing:
        return existing

    vector = await embedding_service.encode(f"{title}. {content}")

    document = KnowledgeDocument(
        source=source,
        title=title,
        content=content,
        source_url=source_url,
        license=license_name,
        checksum=checksum,
        status="staged",
        embedding=vector,
    )
    session.add(document)
    await session.commit()
    await session.refresh(document)
    return document


async def approved_knowledge_context(
    session: AsyncSession,
    query: str,
    limit: int = 5,
) -> list[dict[str, str]]:
    vector = await embedding_service.encode(query)
    similarity = (1 - KnowledgeDocument.embedding.cosine_distance(vector)).label(
        "similarity"
    )
    rows = (
        await session.execute(
            select(KnowledgeDocument, similarity)
            .where(
                KnowledgeDocument.status == "approved",
                KnowledgeDocument.embedding.is_not(None),
            )
            .order_by(similarity.desc())
            .limit(limit)
        )
    ).all()

    return [
        {
            "title": document.title,
            "source": document.source,
            "content": document.content[:4000],
            "source_url": document.source_url,
        }
        for document, _ in rows
    ]


def job_match_score(profile: CandidateProfile, job: Job) -> tuple[float, list[str]]:
    skills = unique(profile.skills + profile.abilities)
    haystack = normalize(f"{job.title} {job.description}")
    matched = [skill for skill in skills if normalize(skill) in haystack]

    if not skills:
        return 0.0, []

    return round(100 * len(matched) / len(skills), 1), matched


async def ranked_jobs(
    session: AsyncSession,
    profile: CandidateProfile,
    query: str = "",
    location: str = "",
    limit: int = 30,
) -> list[dict[str, Any]]:
    statement = select(Job)

    if query:
        pattern = f"%{query.strip()}%"
        statement = statement.where(
            or_(
                Job.title.ilike(pattern),
                Job.organization.ilike(pattern),
                Job.description.ilike(pattern),
            )
        )

    if location:
        statement = statement.where(Job.location.ilike(f"%{location.strip()}%"))

    jobs = (await session.scalars(statement.limit(200))).all()
    ranked = []

    for job in jobs:
        score, matched = job_match_score(profile, job)
        ranked.append(
            {
                "id": job.id,
                "source": job.source,
                "title": job.title,
                "organization": job.organization,
                "location": job.location,
                "description": job.description,
                "apply_url": job.apply_url,
                "match_score": score,
                "matched_skills": matched[:12],
            }
        )

    ranked.sort(key=lambda item: item["match_score"], reverse=True)
    return ranked[:limit]


async def create_application(
    session: AsyncSession,
    user_id: str,
    payload: ApplicationCreate,
) -> Application:
    record = Application(
        user_id=user_id,
        job_id=payload.job_id,
        title=payload.title,
        organization=payload.organization,
        status=payload.status,
        encrypted_notes="",
        applied_at=payload.applied_at,
    )
    session.add(record)
    await session.flush()

    if payload.notes:
        record.encrypted_notes = encrypt_text(
            payload.notes,
            aad=f"application:{user_id}:{record.id}",
        )

    await session.commit()
    await session.refresh(record)
    return record


def application_response(record: Application) -> ApplicationResponse:
    notes = ""

    if record.encrypted_notes:
        notes = decrypt_text(
            record.encrypted_notes,
            aad=f"application:{record.user_id}:{record.id}",
        )

    return ApplicationResponse(
        id=record.id,
        job_id=record.job_id,
        title=record.title,
        organization=record.organization,
        status=record.status,
        notes=notes,
        applied_at=record.applied_at,
        created_at=record.created_at,
    )
