from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto import decrypt_text, encrypt_text
from app.models import (
    AIIncident,
    AIRiskAssessment,
    AISystemInventory,
    ComplianceEvidence,
    GovernanceControlMapping,
    HumanReviewItem,
)
from app.schemas import (
    AIIncidentCreate,
    AIIncidentUpdate,
    AIRiskAssessmentIn,
    AISystemInventoryIn,
)


EU_STANDALONE_HIGH_RISK_APPLICABLE = date(2027, 12, 2)

EU_BASELINE_CONTROLS: list[dict[str, Any]] = [
    {
        "ref": "EU-AI-ACT-ART-4",
        "title": "AI literacy",
        "evidence": ["training records", "role competency evidence"],
        "applicability": "general",
    },
    {
        "ref": "EU-AI-ACT-ANNEX-III-4",
        "title": "Employment-use classification assessment",
        "evidence": ["intended purpose", "classification record", "Article 6 assessment"],
        "applicability": "employment",
    },
    {
        "ref": "EU-AI-ACT-ART-9",
        "title": "Lifecycle risk management",
        "evidence": ["risk assessment", "risk treatment", "review history"],
        "applicability": "high_risk",
    },
    {
        "ref": "EU-AI-ACT-ART-10",
        "title": "Data and data-governance controls",
        "evidence": ["data provenance", "quality checks", "bias controls"],
        "applicability": "high_risk",
    },
    {
        "ref": "EU-AI-ACT-ART-11",
        "title": "Technical documentation",
        "evidence": ["system description", "model/version inventory", "evaluation records"],
        "applicability": "high_risk",
    },
    {
        "ref": "EU-AI-ACT-ART-12",
        "title": "Logging and record keeping",
        "evidence": ["audit logs", "trace retention configuration"],
        "applicability": "high_risk",
    },
    {
        "ref": "EU-AI-ACT-ART-13",
        "title": "Transparency and instructions for use",
        "evidence": ["user notices", "limitations", "intended-use documentation"],
        "applicability": "high_risk",
    },
    {
        "ref": "EU-AI-ACT-ART-14",
        "title": "Human oversight",
        "evidence": ["human review workflow", "override controls", "review training"],
        "applicability": "high_risk",
    },
    {
        "ref": "EU-AI-ACT-ART-15",
        "title": "Accuracy, robustness and cybersecurity",
        "evidence": ["evaluation results", "security controls", "resilience tests"],
        "applicability": "high_risk",
    },
    {
        "ref": "EU-AI-ACT-ART-26",
        "title": "Deployer operational obligations",
        "evidence": ["monitoring procedure", "human oversight assignment", "incident process"],
        "applicability": "deployer_high_risk",
    },
    {
        "ref": "EU-AI-ACT-ART-49",
        "title": "Registration applicability review",
        "evidence": ["registration decision", "EU database reference if applicable"],
        "applicability": "conditional",
    },
    {
        "ref": "EU-AI-ACT-ART-27",
        "title": "Fundamental-rights impact assessment applicability review",
        "evidence": ["FRIA applicability decision", "FRIA record if applicable"],
        "applicability": "conditional",
    },
]

ISO42001_BASELINE_CONTROLS: list[dict[str, Any]] = [
    {
        "ref": "ISO42001-AIMS-CONTEXT",
        "title": "AIMS context, scope and interested parties",
        "evidence": ["AIMS scope", "AI inventory", "stakeholder register"],
    },
    {
        "ref": "ISO42001-AIMS-LEADERSHIP",
        "title": "Leadership, policy, accountability and roles",
        "evidence": ["AI policy", "owners", "governance approvals"],
    },
    {
        "ref": "ISO42001-AIMS-PLANNING",
        "title": "AI risks, opportunities, objectives and treatment planning",
        "evidence": ["risk assessments", "treatment plans", "objectives"],
    },
    {
        "ref": "ISO42001-AIMS-SUPPORT",
        "title": "Resources, competence, awareness and documented information",
        "evidence": ["training", "competence records", "controlled documentation"],
    },
    {
        "ref": "ISO42001-AIMS-OPERATION",
        "title": "Operational AI lifecycle and impact controls",
        "evidence": ["lifecycle procedures", "data controls", "supplier controls"],
    },
    {
        "ref": "ISO42001-AIMS-PERFORMANCE",
        "title": "Monitoring, measurement, internal audit and management review",
        "evidence": ["metrics", "evals", "audit records", "management review"],
    },
    {
        "ref": "ISO42001-AIMS-IMPROVEMENT",
        "title": "Nonconformity, corrective action and continual improvement",
        "evidence": ["incidents", "corrective actions", "improvement records"],
    },
]

ISO_DISCLAIMER = (
    "This is an implementation-oriented management-system crosswalk, not the "
    "copyrighted ISO/IEC 42001 standard, a certification checklist, or a claim "
    "of conformity. Use a licensed copy of ISO/IEC 42001 and qualified auditors "
    "for certification work."
)


def classify_eu_ai(payload: AISystemInventoryIn) -> tuple[str, dict[str, Any], date | None]:
    """Create a conservative triage classification, not a legal determination."""

    basis: dict[str, Any] = {
        "regulation": "Regulation (EU) 2024/1689 as amended through 2026-07-27",
        "assessment_type": "triage_only",
        "annex_iii_employment_use": payload.employment_use,
        "education_use_requires_specific_use_case_review": payload.education_use,
        "profiles_natural_persons": payload.profiles_natural_persons,
        "materially_influences_decisions": payload.materially_influences_decisions,
        "article_6_3_exemption_not_determined": False,
        "note": (
            "Classification depends on intended purpose and actual deployment. "
            "Counsel/compliance review remains required."
        ),
    }

    if payload.employment_use:
        if payload.profiles_natural_persons:
            risk_class = "annex_iii_high_risk_candidate"
            basis["reason"] = (
                "Employment use is listed in Annex III and profiling removes "
                "the Article 6(3) exemption route."
            )
        elif payload.materially_influences_decisions:
            risk_class = "annex_iii_high_risk_candidate"
            basis["reason"] = (
                "Employment use that materially influences recruitment, selection "
                "or worker decisions requires high-risk assessment."
            )
        else:
            risk_class = "annex_iii_review_required"
            basis["article_6_3_exemption_not_determined"] = True
            basis["reason"] = (
                "Employment use is Annex III territory, but the application has "
                "declared no material decision influence; document the Article 6(3) "
                "assessment before relying on an exemption."
            )

        return risk_class, basis, EU_STANDALONE_HIGH_RISK_APPLICABLE

    if payload.education_use:
        basis["reason"] = (
            "Certain education and vocational-training uses are listed in Annex III; "
            "the specific intended purpose must be assessed."
        )
        return (
            "annex_iii_review_required",
            basis,
            EU_STANDALONE_HIGH_RISK_APPLICABLE,
        )

    basis["reason"] = (
        "No employment or education Annex III flag was declared; other AI Act "
        "categories and transparency/prohibited-practice rules still require review."
    )
    return "context_assessment_required", basis, None


def risk_level(score: int) -> str:
    if score <= 4:
        return "low"
    if score <= 9:
        return "medium"
    if score <= 16:
        return "high"
    return "critical"


async def create_inventory(
    session: AsyncSession,
    organization_id: str,
    payload: AISystemInventoryIn,
) -> AISystemInventory:
    risk_class, basis, applicable_from = classify_eu_ai(payload)

    record = AISystemInventory(
        organization_id=organization_id,
        system_key=payload.system_key,
        version=payload.version,
        name=payload.name,
        owner=payload.owner,
        intended_purpose=payload.intended_purpose,
        operator_role=payload.operator_role,
        lifecycle_status=payload.lifecycle_status,
        jurisdictions=payload.jurisdictions,
        model_names=payload.model_names,
        data_categories=payload.data_categories,
        employment_use=payload.employment_use,
        education_use=payload.education_use,
        profiles_natural_persons=payload.profiles_natural_persons,
        materially_influences_decisions=payload.materially_influences_decisions,
        human_oversight=payload.human_oversight,
        eu_risk_class=risk_class,
        eu_classification_basis=basis,
        iso42001_in_scope=payload.iso42001_in_scope,
        applicable_from=applicable_from,
        last_reviewed_at=datetime.now(UTC),
    )
    session.add(record)
    await session.flush()
    await seed_control_mappings(session, organization_id, record)
    await session.commit()
    await session.refresh(record)
    return record


async def seed_control_mappings(
    session: AsyncSession,
    organization_id: str,
    inventory: AISystemInventory,
) -> int:
    controls: list[tuple[str, dict[str, Any]]] = []

    for item in EU_BASELINE_CONTROLS:
        controls.append(("EU_AI_ACT", item))

    if inventory.iso42001_in_scope:
        for item in ISO42001_BASELINE_CONTROLS:
            controls.append(("ISO_IEC_42001", item))

    created = 0

    for framework, item in controls:
        existing = await session.scalar(
            select(GovernanceControlMapping.id).where(
                GovernanceControlMapping.organization_id == organization_id,
                GovernanceControlMapping.inventory_id == inventory.id,
                GovernanceControlMapping.framework == framework,
                GovernanceControlMapping.control_ref == item["ref"],
            )
        )

        if existing:
            continue

        notes = ""

        if framework == "ISO_IEC_42001":
            notes = ISO_DISCLAIMER

        session.add(
            GovernanceControlMapping(
                organization_id=organization_id,
                inventory_id=inventory.id,
                framework=framework,
                control_ref=item["ref"],
                title=item["title"],
                evidence_requirements=item.get("evidence", []),
                notes=notes,
            )
        )
        created += 1

    await session.flush()
    return created


async def create_risk_assessment(
    session: AsyncSession,
    inventory: AISystemInventory,
    payload: AIRiskAssessmentIn,
    approver_user_id: str | None,
) -> AIRiskAssessment:
    inherent = payload.likelihood * payload.impact

    if payload.residual_score > inherent:
        raise ValueError(
            "Residual risk cannot exceed inherent risk in this assessment model."
        )

    if (
        inventory.employment_use
        and inventory.materially_influences_decisions
        and not inventory.human_oversight
        and payload.status == "approved"
    ):
        raise ValueError(
            "Employment decision systems cannot be approved without human oversight."
        )

    record = AIRiskAssessment(
        inventory_id=inventory.id,
        assessment_version=payload.assessment_version,
        likelihood=payload.likelihood,
        impact=payload.impact,
        inherent_score=inherent,
        residual_score=payload.residual_score,
        risk_level=risk_level(payload.residual_score),
        hazards_json=payload.hazards,
        controls_json=payload.controls,
        status=payload.status,
        approved_by_user_id=approver_user_id if payload.status == "approved" else None,
        approved_at=datetime.now(UTC) if payload.status == "approved" else None,
    )
    session.add(record)
    await session.flush()

    if payload.residual_score >= 17:
        session.add(
            HumanReviewItem(
                organization_id=inventory.organization_id,
                category="policy",
                severity="critical",
                subject_type="ai_risk_assessment",
                subject_id=record.id,
                reason=(
                    "Critical residual AI risk requires explicit human governance review."
                ),
                encrypted_context="",
            )
        )

    await session.commit()
    await session.refresh(record)
    return record


def _incident_aad(organization_id: str, incident_id: str) -> str:
    return f"ai-incident:{organization_id}:{incident_id}"


async def create_incident(
    session: AsyncSession,
    organization_id: str,
    user_id: str,
    payload: AIIncidentCreate,
) -> AIIncident:
    if payload.inventory_id:
        inventory = await session.get(AISystemInventory, payload.inventory_id)

        if inventory is None or inventory.organization_id != organization_id:
            raise ValueError("AI inventory item does not belong to this organization.")

    record = AIIncident(
        organization_id=organization_id,
        inventory_id=payload.inventory_id,
        severity=payload.severity,
        category=payload.category,
        serious_incident_candidate=payload.serious_incident_candidate,
        encrypted_details="",
        detected_at=payload.detected_at,
        created_by_user_id=user_id,
    )
    session.add(record)
    await session.flush()
    record.encrypted_details = encrypt_text(
        json.dumps(payload.details, ensure_ascii=False, separators=(",", ":")),
        aad=_incident_aad(organization_id, record.id),
    )

    if payload.severity == "critical" or payload.serious_incident_candidate:
        session.add(
            HumanReviewItem(
                organization_id=organization_id,
                category="security" if payload.category == "security" else "policy",
                severity="critical" if payload.severity == "critical" else "high",
                subject_type="ai_incident",
                subject_id=record.id,
                reason=(
                    "AI incident requires human triage. The serious-incident flag is "
                    "a candidate classification only; determine legal reporting duties "
                    "using the actual incident facts and jurisdiction."
                ),
                encrypted_context="",
            )
        )

    await session.commit()
    await session.refresh(record)
    return record


def incident_details(record: AIIncident) -> dict[str, Any]:
    return json.loads(
        decrypt_text(
            record.encrypted_details,
            aad=_incident_aad(record.organization_id, record.id),
        )
    )


async def update_incident(
    session: AsyncSession,
    record: AIIncident,
    payload: AIIncidentUpdate,
) -> AIIncident:
    record.status = payload.status

    if payload.serious_incident_candidate is not None:
        record.serious_incident_candidate = payload.serious_incident_candidate

    record.contained_at = payload.contained_at
    record.closed_at = payload.closed_at
    record.external_reported_at = payload.external_reported_at

    if payload.details is not None:
        record.encrypted_details = encrypt_text(
            json.dumps(payload.details, ensure_ascii=False, separators=(",", ":")),
            aad=_incident_aad(record.organization_id, record.id),
        )

    await session.commit()
    await session.refresh(record)
    return record


def _artifact_hash(value: dict[str, Any]) -> str:
    canonical = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


async def _add_evidence(
    session: AsyncSession,
    organization_id: str,
    framework: str,
    control_id: str,
    evidence_type: str,
    source: str,
    payload: dict[str, Any],
) -> ComplianceEvidence | None:
    artifact_hash = _artifact_hash(payload)
    existing = await session.scalar(
        select(ComplianceEvidence.id).where(
            ComplianceEvidence.organization_id == organization_id,
            ComplianceEvidence.framework == framework,
            ComplianceEvidence.control_id == control_id,
            ComplianceEvidence.artifact_hash == artifact_hash,
        )
    )

    if existing:
        return None

    record = ComplianceEvidence(
        organization_id=organization_id,
        framework=framework,
        control_id=control_id,
        evidence_type=evidence_type,
        source=source,
        artifact_hash=artifact_hash,
        evidence_json=payload,
    )
    session.add(record)
    return record


async def collect_phase8_evidence(
    session: AsyncSession,
    organization_id: str,
) -> int:
    inventories = list(
        (
            await session.scalars(
                select(AISystemInventory).where(
                    AISystemInventory.organization_id == organization_id
                )
            )
        ).all()
    )
    controls = list(
        (
            await session.scalars(
                select(GovernanceControlMapping).where(
                    GovernanceControlMapping.organization_id == organization_id
                )
            )
        ).all()
    )
    incidents = list(
        (
            await session.scalars(
                select(AIIncident).where(
                    AIIncident.organization_id == organization_id
                )
            )
        ).all()
    )

    created = 0

    for inventory in inventories:
        payload = {
            "system_id": inventory.id,
            "system_key": inventory.system_key,
            "version": inventory.version,
            "lifecycle_status": inventory.lifecycle_status,
            "eu_risk_class": inventory.eu_risk_class,
            "employment_use": inventory.employment_use,
            "human_oversight": inventory.human_oversight,
            "last_reviewed_at": inventory.last_reviewed_at,
        }

        record = await _add_evidence(
            session,
            organization_id,
            "EU_AI_ACT",
            "AI-INVENTORY",
            "inventory_snapshot",
            "phase8.ai_system_inventory",
            payload,
        )
        created += int(record is not None)

        if inventory.iso42001_in_scope:
            record = await _add_evidence(
                session,
                organization_id,
                "ISO_IEC_42001",
                "AIMS-INVENTORY",
                "inventory_snapshot",
                "phase8.ai_system_inventory",
                payload,
            )
            created += int(record is not None)

    control_payload = {
        "total": len(controls),
        "by_framework": {
            framework: sum(1 for item in controls if item.framework == framework)
            for framework in sorted({item.framework for item in controls})
        },
        "by_status": {
            status: sum(1 for item in controls if item.implementation_status == status)
            for status in sorted({item.implementation_status for item in controls})
        },
    }

    for framework in ("EU_AI_ACT", "ISO_IEC_42001"):
        record = await _add_evidence(
            session,
            organization_id,
            framework,
            "CONTROL-IMPLEMENTATION",
            "control_status_snapshot",
            "phase8.governance_control_mappings",
            control_payload,
        )
        created += int(record is not None)

    incident_payload = {
        "open_incidents": sum(1 for item in incidents if item.status != "closed"),
        "serious_incident_candidates": sum(
            1 for item in incidents if item.serious_incident_candidate
        ),
        "critical_open": sum(
            1
            for item in incidents
            if item.severity == "critical" and item.status != "closed"
        ),
    }

    for framework in ("EU_AI_ACT", "ISO_IEC_42001"):
        record = await _add_evidence(
            session,
            organization_id,
            framework,
            "INCIDENT-MANAGEMENT",
            "incident_metric_snapshot",
            "phase8.ai_incidents",
            incident_payload,
        )
        created += int(record is not None)

    await session.commit()
    return created


async def phase8_dashboard(
    session: AsyncSession,
    organization_id: str,
) -> dict[str, Any]:
    ai_systems = await session.scalar(
        select(func.count(AISystemInventory.id)).where(
            AISystemInventory.organization_id == organization_id
        )
    ) or 0
    employment_systems = await session.scalar(
        select(func.count(AISystemInventory.id)).where(
            AISystemInventory.organization_id == organization_id,
            AISystemInventory.employment_use.is_(True),
        )
    ) or 0
    eu_review_required = await session.scalar(
        select(func.count(AISystemInventory.id)).where(
            AISystemInventory.organization_id == organization_id,
            AISystemInventory.eu_risk_class.in_(
                ["annex_iii_high_risk_candidate", "annex_iii_review_required"]
            ),
        )
    ) or 0
    risk_assessments_open = await session.scalar(
        select(func.count(AIRiskAssessment.id))
        .join(
            AISystemInventory,
            AISystemInventory.id == AIRiskAssessment.inventory_id,
        )
        .where(
            AISystemInventory.organization_id == organization_id,
            AIRiskAssessment.status != "approved",
        )
    ) or 0
    high_residual_risks = await session.scalar(
        select(func.count(AIRiskAssessment.id))
        .join(
            AISystemInventory,
            AISystemInventory.id == AIRiskAssessment.inventory_id,
        )
        .where(
            AISystemInventory.organization_id == organization_id,
            AIRiskAssessment.residual_score >= 10,
        )
    ) or 0
    open_incidents = await session.scalar(
        select(func.count(AIIncident.id)).where(
            AIIncident.organization_id == organization_id,
            AIIncident.status != "closed",
        )
    ) or 0
    serious_incident_candidates = await session.scalar(
        select(func.count(AIIncident.id)).where(
            AIIncident.organization_id == organization_id,
            AIIncident.serious_incident_candidate.is_(True),
            AIIncident.status != "closed",
        )
    ) or 0

    rows = (
        await session.execute(
            select(
                GovernanceControlMapping.implementation_status,
                func.count(GovernanceControlMapping.id),
            )
            .where(
                GovernanceControlMapping.organization_id == organization_id
            )
            .group_by(GovernanceControlMapping.implementation_status)
        )
    ).all()
    controls_by_status = {str(status): int(count) for status, count in rows}

    since = datetime.now(UTC) - timedelta(days=30)
    evidence_records = await session.scalar(
        select(func.count(ComplianceEvidence.id)).where(
            ComplianceEvidence.organization_id == organization_id,
            ComplianceEvidence.framework.in_(["EU_AI_ACT", "ISO_IEC_42001"]),
            ComplianceEvidence.captured_at >= since,
        )
    ) or 0

    return {
        "organization_id": organization_id,
        "ai_systems": int(ai_systems),
        "employment_systems": int(employment_systems),
        "eu_review_required": int(eu_review_required),
        "risk_assessments_open": int(risk_assessments_open),
        "high_residual_risks": int(high_residual_risks),
        "open_incidents": int(open_incidents),
        "serious_incident_candidates": int(serious_incident_candidates),
        "controls_by_status": controls_by_status,
        "evidence_records_last_30_days": int(evidence_records),
        "note": (
            "Dashboard statuses support governance operations. They are not legal "
            "opinions, ISO certification results, or regulator determinations."
        ),
    }
