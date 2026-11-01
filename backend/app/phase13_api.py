from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_user
from app.db import get_session
from app.models import (
    AgentPermissionManifest,
    CrossCloudWorkloadBinding,
    DeploymentRegion,
    ModelGatewayPolicy,
    ModelRelease,
    RegionTrustLink,
    TransparencyLogEntry,
    TrustContinuitySnapshot,
    User,
)
from app.phase13_schemas import (
    AgentActionCheckRequest,
    AgentActionCheckResponse,
    AgentManifestApprovalRequest,
    AgentPermissionManifestRequest,
    CrossCloudWorkloadBindingRequest,
    DeploymentRegionRequest,
    ModelGatewayPolicyRequest,
    ModelGatewayRequest,
    ModelGatewayResponse,
    ModelReleaseApprovalRequest,
    ModelReleaseRequest,
    Phase13ReadinessResponse,
    PromptInjectionScanRequest,
    PromptInjectionScanResponse,
    RegionTrustLinkRequest,
    RestoreApprovalRequest,
    TransparencyAppendRequest,
    TrustContinuitySnapshotRequest,
)
from app.phase13_services import (
    append_transparency_entry,
    create_model_release,
    create_trust_continuity_snapshot,
    digest_object,
    evaluate_agent_action,
    manifest_digest,
    purge_expired_trust_snapshots,
    record_prompt_scan,
    run_model_gateway,
    scan_prompt_injection,
    verify_region_trust_link,
    verify_transparency_log,
    verify_trust_snapshot,
)
from app.tenancy import require_org_role, require_platform_admin


router = APIRouter(prefix="/v1/phase13", tags=["phase13"])


async def _org_admin(
    session: AsyncSession,
    user: User,
    organization_id: str,
) -> None:
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin"},
    )


@router.get("/readiness", response_model=Phase13ReadinessResponse)
async def readiness() -> Phase13ReadinessResponse:
    from app.config import settings

    return Phase13ReadinessResponse(
        phase="13A+13B",
        region_id=settings.phase13_region_id,
        openid_federation_baseline="1.1",
        spiffe_federation=True,
        transparency_log=True,
        external_transparency_configured=bool(
            settings.phase13_transparency_external_url
        ),
        model_gateway=True,
        agent_manifest_required=settings.phase13_agent_manifest_required,
        notes=[
            "Cross-region trust requires explicit region/link registration and pinned trust material.",
            "The model gateway disables tools; action authorization is handled separately by agent permission manifests.",
            "Prompt-injection detection is heuristic and is combined with capability isolation, signed releases, and human approval.",
            "Disaster-recovery snapshots are sealed evidence; restore activation is a separate approved operator procedure.",
        ],
    )


@router.post("/regions")
async def create_region(
    payload: DeploymentRegionRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await _org_admin(session, user, payload.organization_id)
    record = DeploymentRegion(
        organization_id=payload.organization_id,
        region_key=payload.region_key.strip(),
        display_name=payload.display_name.strip(),
        cloud_provider=payload.cloud_provider,
        jurisdiction=payload.jurisdiction.strip(),
        spiffe_trust_domain=payload.spiffe_trust_domain.strip(),
        federation_entity_id=payload.federation_entity_id.strip(),
        metadata_json=payload.metadata_json,
        created_by_user_id=user.id,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return {
        "id": record.id,
        "region_key": record.region_key,
        "display_name": record.display_name,
        "cloud_provider": record.cloud_provider,
        "spiffe_trust_domain": record.spiffe_trust_domain,
        "active": record.active,
    }


@router.get("/regions")
async def list_regions(
    organization_id: str = Query(...),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin", "recruiter", "member"},
    )
    rows = list(
        (
            await session.scalars(
                select(DeploymentRegion)
                .where(DeploymentRegion.organization_id == organization_id)
                .order_by(DeploymentRegion.created_at.asc())
            )
        ).all()
    )
    return [
        {
            "id": row.id,
            "region_key": row.region_key,
            "display_name": row.display_name,
            "cloud_provider": row.cloud_provider,
            "jurisdiction": row.jurisdiction,
            "spiffe_trust_domain": row.spiffe_trust_domain,
            "federation_entity_id": row.federation_entity_id,
            "active": row.active,
        }
        for row in rows
    ]


@router.post("/trust-links")
async def create_trust_link(
    payload: RegionTrustLinkRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await _org_admin(session, user, payload.organization_id)
    bundle_digest = digest_object(payload.peer_bundle_json)
    record = RegionTrustLink(
        organization_id=payload.organization_id,
        source_region_id=payload.source_region_id,
        peer_region_id=payload.peer_region_id,
        peer_bundle_endpoint=str(payload.peer_bundle_endpoint or ""),
        peer_bundle_digest=bundle_digest,
        peer_bundle_json=payload.peer_bundle_json,
        federation_anchor_entity_id=payload.federation_anchor_entity_id.strip(),
        status="pending",
        created_by_user_id=user.id,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return {
        "id": record.id,
        "status": record.status,
        "peer_bundle_digest": record.peer_bundle_digest,
    }


@router.post("/trust-links/{link_id}/verify")
async def verify_trust_link_endpoint(
    link_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    link = await session.get(RegionTrustLink, link_id)

    if link is None:
        raise HTTPException(status_code=404, detail="Trust link not found.")

    await _org_admin(session, user, link.organization_id)

    try:
        details = await verify_region_trust_link(session, link)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    link.approved_by_user_id = user.id
    await session.commit()
    return {"id": link.id, "status": link.status, "details": details}


@router.post("/workload-bindings")
async def create_workload_binding(
    payload: CrossCloudWorkloadBindingRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await _org_admin(session, user, payload.organization_id)

    if not payload.aws_role_arn and not payload.azure_client_id:
        raise HTTPException(
            status_code=422,
            detail="At least one AWS or Azure workload identity binding is required.",
        )

    if not payload.spiffe_id.startswith("spiffe://"):
        raise HTTPException(status_code=422, detail="spiffe_id must use the spiffe:// scheme.")

    record = CrossCloudWorkloadBinding(
        organization_id=payload.organization_id,
        name=payload.name.strip(),
        spiffe_id=payload.spiffe_id.strip(),
        aws_role_arn=payload.aws_role_arn.strip(),
        azure_client_id=payload.azure_client_id.strip(),
        azure_tenant_id=payload.azure_tenant_id.strip(),
        audience=payload.audience.strip(),
        allowed_regions=payload.allowed_regions,
        created_by_user_id=user.id,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return {
        "id": record.id,
        "name": record.name,
        "spiffe_id": record.spiffe_id,
        "enabled": record.enabled,
    }


@router.post("/transparency/append")
async def append_transparency(
    payload: TransparencyAppendRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await _org_admin(session, user, payload.organization_id)

    if payload.publish_external:
        raise HTTPException(
            status_code=409,
            detail=(
                "External transparency publication is performed by the signed release pipeline. "
                "This API records external log references but does not send arbitrary payloads "
                "to external transparency services."
            ),
        )

    record = await append_transparency_entry(
        session,
        organization_id=payload.organization_id,
        log_name=payload.log_name,
        entry_type=payload.entry_type,
        subject_id=payload.subject_id,
        payload=payload.payload,
    )
    return {
        "id": record.id,
        "sequence": record.sequence,
        "entry_hash": record.entry_hash,
        "previous_entry_hash": record.previous_entry_hash,
    }


@router.get("/transparency/verify")
async def verify_transparency(
    organization_id: str = Query(...),
    log_name: str = Query(default="career-trust"),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin", "recruiter", "member"},
    )
    return await verify_transparency_log(session, organization_id, log_name)


@router.post("/trust-snapshots")
async def create_snapshot(
    payload: TrustContinuitySnapshotRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await _org_admin(session, user, payload.organization_id)

    try:
        record = await create_trust_continuity_snapshot(
            session,
            organization_id=payload.organization_id,
            region_id=payload.region_id,
            snapshot_version=payload.snapshot_version,
            actor_user_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "id": record.id,
        "snapshot_digest": record.snapshot_digest,
        "signature_present": bool(record.signature),
        "status": record.status,
        "expires_at": record.expires_at,
    }


@router.get("/trust-snapshots/{snapshot_id}/verify")
async def verify_snapshot(
    snapshot_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    record = await session.get(TrustContinuitySnapshot, snapshot_id)

    if record is None:
        raise HTTPException(status_code=404, detail="Snapshot not found.")

    await require_org_role(
        session,
        user,
        record.organization_id,
        {"owner", "admin"},
    )
    return await verify_trust_snapshot(session, record)


@router.post("/trust-snapshots/{snapshot_id}/restore-approval")
async def approve_snapshot_restore(
    snapshot_id: str,
    payload: RestoreApprovalRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    record = await session.get(TrustContinuitySnapshot, snapshot_id)

    if record is None:
        raise HTTPException(status_code=404, detail="Snapshot not found.")

    await _org_admin(session, user, record.organization_id)
    verification = await verify_trust_snapshot(session, record)

    if payload.approved and not verification["valid"]:
        raise HTTPException(
            status_code=409,
            detail="Invalid snapshot cannot be approved for restore.",
        )

    record.status = "approved_for_restore" if payload.approved else "sealed"
    record.approved_for_restore_by_user_id = user.id if payload.approved else None
    await session.commit()
    return {
        "id": record.id,
        "status": record.status,
        "note": (
            "Approval does not automatically restore trust configuration. "
            "A separate disaster-recovery controller must perform the restore."
        ),
    }


@router.post("/prompt-injection/scan", response_model=PromptInjectionScanResponse)
async def prompt_injection_scan(
    payload: PromptInjectionScanRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    if payload.organization_id:
        await require_org_role(
            session,
            user,
            payload.organization_id,
            {"owner", "admin", "recruiter", "member"},
        )

    event = await record_prompt_scan(
        session,
        organization_id=payload.organization_id,
        source_type=payload.source_type,
        source_id=payload.source_id,
        content=payload.content,
    )
    return PromptInjectionScanResponse(
        score=event.score,
        decision=event.decision,
        indicators=event.indicators,
        content_digest=event.content_digest,
    )


@router.post("/model-gateway/policies")
async def create_gateway_policy(
    payload: ModelGatewayPolicyRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await _org_admin(session, user, payload.organization_id)
    record = ModelGatewayPolicy(
        organization_id=payload.organization_id,
        name=payload.name.strip(),
        allowed_models=payload.allowed_models,
        allowed_tasks=payload.allowed_tasks,
        allowed_data_categories=payload.allowed_data_categories,
        tools_allowed=payload.tools_allowed,
        require_signed_release=payload.require_signed_release,
        require_confidential_rag=payload.require_confidential_rag,
        block_injection_score=payload.block_injection_score,
        max_input_chars=payload.max_input_chars,
        max_output_tokens=payload.max_output_tokens,
        created_by_user_id=user.id,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return {"id": record.id, "name": record.name, "enabled": record.enabled}


@router.post("/model-releases")
async def create_release(
    payload: ModelReleaseRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await _org_admin(session, user, payload.organization_id)

    try:
        record = await create_model_release(
            session,
            organization_id=payload.organization_id,
            release_name=payload.release_name,
            version=payload.version,
            model_name=payload.model_name,
            model_snapshot=payload.model_snapshot,
            prompt_version=payload.prompt_version,
            eval_run_id=payload.eval_run_id,
            policy_digest=payload.policy_digest,
            actor_user_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "id": record.id,
        "manifest_digest": record.manifest_digest,
        "signature_present": bool(record.signature),
        "status": record.release_status,
    }


@router.post("/model-releases/{release_id}/approval")
async def approve_release(
    release_id: str,
    payload: ModelReleaseApprovalRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    require_platform_admin(user)
    release = await session.get(ModelRelease, release_id)

    if release is None:
        raise HTTPException(status_code=404, detail="Model release not found.")

    if payload.approved and not release.signature:
        raise HTTPException(
            status_code=409,
            detail="Production model release requires a release signature.",
        )

    release.release_status = "approved" if payload.approved else "rejected"
    release.approved_by_user_id = user.id if payload.approved else None
    await session.commit()

    if payload.approved and payload.publish_transparency:
        entry = await append_transparency_entry(
            session,
            organization_id=release.organization_id,
            log_name="model-releases",
            entry_type="model_release",
            subject_id=release.id,
            payload={
                "manifest_digest": release.manifest_digest,
                "model_name": release.model_name,
                "model_snapshot": release.model_snapshot,
                "prompt_version": release.prompt_version,
                "eval_run_id": release.eval_run_id,
                "signing_key_id": release.signing_key_id,
            },
        )
        release.transparency_entry_id = entry.id
        await session.commit()

    return {"id": release.id, "status": release.release_status}


@router.post("/agent-manifests")
async def create_agent_manifest(
    payload: AgentPermissionManifestRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await _org_admin(session, user, payload.organization_id)
    material = payload.model_dump()
    digest = manifest_digest(material)
    record = AgentPermissionManifest(
        organization_id=payload.organization_id,
        agent_name=payload.agent_name.strip(),
        version=payload.version.strip(),
        allowed_actions=payload.allowed_actions,
        denied_actions=payload.denied_actions,
        allowed_data_categories=payload.allowed_data_categories,
        allowed_destination_hosts=[
            item.strip().lower() for item in payload.allowed_destination_hosts if item.strip()
        ],
        max_external_calls=payload.max_external_calls,
        require_human_approval_actions=payload.require_human_approval_actions,
        active=False,
        manifest_digest=digest,
        created_by_user_id=user.id,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return {"id": record.id, "manifest_digest": record.manifest_digest, "active": record.active}


@router.post("/agent-manifests/{manifest_id}/approval")
async def approve_agent_manifest(
    manifest_id: str,
    payload: AgentManifestApprovalRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    record = await session.get(AgentPermissionManifest, manifest_id)

    if record is None:
        raise HTTPException(status_code=404, detail="Agent manifest not found.")

    await _org_admin(session, user, record.organization_id)

    if payload.activate and not payload.approved:
        raise HTTPException(status_code=422, detail="Rejected manifest cannot be activated.")

    if payload.activate:
        existing = list(
            (
                await session.scalars(
                    select(AgentPermissionManifest).where(
                        AgentPermissionManifest.organization_id == record.organization_id,
                        AgentPermissionManifest.agent_name == record.agent_name,
                        AgentPermissionManifest.active.is_(True),
                    )
                )
            ).all()
        )

        for item in existing:
            item.active = False

    record.active = payload.approved and payload.activate
    record.approved_by_user_id = user.id if payload.approved else None
    await session.commit()
    return {
        "id": record.id,
        "approved": bool(record.approved_by_user_id),
        "active": record.active,
    }


@router.post("/agent-actions/check", response_model=AgentActionCheckResponse)
async def check_agent_action(
    payload: AgentActionCheckRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        payload.organization_id,
        {"owner", "admin", "recruiter", "member"},
    )
    record = await evaluate_agent_action(
        session,
        organization_id=payload.organization_id,
        agent_name=payload.agent_name,
        action=payload.action,
        destination_host=payload.destination_host,
        data_categories=payload.data_categories,
        external_calls_used=payload.external_calls_used,
    )
    return AgentActionCheckResponse(
        decision=record.decision,
        reasons=record.reasons,
        requires_human_approval=record.requires_human_approval,
        manifest_id=record.manifest_id,
    )


@router.post("/model-gateway/infer", response_model=ModelGatewayResponse)
async def model_gateway_infer(
    payload: ModelGatewayRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        payload.organization_id,
        {"owner", "admin", "recruiter", "member"},
    )
    policy = await session.get(ModelGatewayPolicy, payload.policy_id)

    if policy is None or policy.organization_id != payload.organization_id:
        raise HTTPException(status_code=404, detail="Model gateway policy not found.")

    try:
        result = await run_model_gateway(
            session,
            user_id=user.id,
            organization_id=payload.organization_id,
            policy=policy,
            task=payload.task,
            model=payload.model,
            prompt=payload.prompt,
            data_categories=payload.data_categories,
            rag_query=payload.rag_query,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return ModelGatewayResponse(**result)


@router.delete("/maintenance/expired-trust-snapshots")
async def cleanup_expired_snapshots(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    require_platform_admin(user)
    return {"deleted": await purge_expired_trust_snapshots(session)}
