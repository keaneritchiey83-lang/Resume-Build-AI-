"""Authenticated Phase 14A endpoints. No autonomous tool execution through model gateway."""
from __future__ import annotations

from typing import Any, Literal
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.auth import current_user
from app.config import settings
from app.db import get_session
from app.models import User
from app.phase14_runtime import get_phase14_runtime, assert_agent_permissions
from app.tenancy import require_org_role
from phase14 import CapabilityError, AgentStep, ApprovalRequired

router = APIRouter(prefix="/v1/phase14", tags=["phase14"])


def runtime():
    if not settings.phase14_enabled:
        raise HTTPException(status_code=503, detail="Phase 14 is disabled.")
    try:
        return get_phase14_runtime()
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail="Phase 14 security infrastructure unavailable."
        ) from exc


def controlled(operation):
    """Map default-deny errors to HTTP without exposing secrets or raw DB errors."""
    try:
        return operation()
    except (CapabilityError, PermissionError) as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail="Invalid Phase 14 request.") from exc


class Capability(BaseModel):
    action: str = Field(min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9._-]*$")
    resource: str = Field(min_length=1, max_length=256)


class IssueToken(BaseModel):
    organization_id: str = Field(min_length=1, max_length=36)
    workflow_id: str = Field(min_length=1, max_length=128)
    agent_name: str = Field(min_length=1, max_length=128)
    capabilities: list[Capability] = Field(min_length=1, max_length=64)
    lifetime_seconds: int = Field(default=300, ge=1, le=1800)


class RevokeToken(BaseModel):
    organization_id: str
    jti: str = Field(min_length=1, max_length=64)


class MemoryPut(BaseModel):
    organization_id: str
    token: str = Field(max_length=16384)
    key: str = Field(min_length=1, max_length=256)
    value: Any


class MemoryGet(BaseModel):
    organization_id: str
    token: str = Field(max_length=16384)
    key: str = Field(min_length=1, max_length=256)


class StepRequest(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    recipient: str = Field(min_length=1, max_length=128)
    action: str = Field(min_length=1, max_length=128)
    resource: str = Field(min_length=1, max_length=256)
    payload: dict[str, Any] = Field(default_factory=dict)


class DispatchRequest(BaseModel):
    organization_id: str
    token: str = Field(max_length=16384)
    step: StepRequest
    approval_id: str | None = None


class ReviewRequest(BaseModel):
    organization_id: str
    decision: Literal["approve", "reject"]


async def _authorize_user_and_grant(
    user: User, db: AsyncSession, org: str, token: str, action: str | None = None
):
    await require_org_role(db, user, org, {"owner", "admin"})
    instance = runtime()
    claims = await run_in_threadpool(
        lambda: controlled(lambda: instance.authority.verify(token))
    )
    if claims.tenant != org:
        raise HTTPException(status_code=403, detail="Capability organization mismatch.")
    if action:
        await run_in_threadpool(
            lambda: controlled(lambda: _check_manifest(instance, org, claims.sub, {action}))
        )
    return instance, claims


def _check_manifest(instance, org, agent_name, actions):
    with instance.sessions() as db:
        assert_agent_permissions(db, org, agent_name, actions)


@router.get("/readiness")
async def phase14_readiness():
    if settings.phase14_enabled:
        runtime()  # Fail closed on missing/invalid keys or trust-edge configuration.
    return {
        "phase": "14A+14B",
        "enabled": settings.phase14_enabled,
        "agent_trust": "explicit-default-deny",
        "authorization": "phase13-manifests-required",
        "human_review": "authenticated-org-admin",
    }


@router.post("/capabilities/issue")
async def issue_token(
    payload: IssueToken,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
):
    await require_org_role(db, user, payload.organization_id, {"owner", "admin"})
    instance = runtime()
    actions = {cap.action for cap in payload.capabilities}
    # A root grant is never derived from model text or user-supplied permission
    # manifests. Verify the latest approved/active Phase 13 manifest in DB.
    await run_in_threadpool(
        lambda: controlled(
            lambda: _check_manifest(instance, payload.organization_id, payload.agent_name, actions)
        )
    )
    token = await run_in_threadpool(
        lambda: controlled(
            lambda: instance.authority.issue(
                tenant=payload.organization_id,
                workflow=payload.workflow_id,
                subject=payload.agent_name,
                caps=[cap.model_dump() for cap in payload.capabilities],
                ttl_seconds=payload.lifetime_seconds,
                origin_user_id=user.id,
            )
        )
    )
    claims = await run_in_threadpool(
        lambda: controlled(lambda: instance.authority.verify(token))
    )
    return {"token": token, "jti": claims.jti, "expires_at": claims.expires_at}


@router.post("/capabilities/revoke")
async def revoke_token(
    payload: RevokeToken,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
):
    await require_org_role(db, user, payload.organization_id, {"owner", "admin"})
    instance = runtime()
    def revoke():
        from phase14.storage import TokenRecord
        with instance.sessions() as session:
            record = session.get(TokenRecord, payload.jti)
            if record is None or record.tenant != payload.organization_id:
                raise CapabilityError("unknown organization token")
        instance.authority.revoke(payload.jti)
    await run_in_threadpool(lambda: controlled(revoke))
    return {"revoked": True}


@router.post("/memory/write")
async def memory_write(
    payload: MemoryPut,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
):
    instance, claims = await _authorize_user_and_grant(
        user, db, payload.organization_id, payload.token, "memory.write"
    )
    await run_in_threadpool(
        lambda: controlled(lambda: instance.memory.put(payload.token, payload.key, payload.value))
    )
    return {"stored": True, "agent": claims.sub, "workflow": claims.workflow}


@router.post("/memory/read")
async def memory_read(
    payload: MemoryGet,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
):
    instance, claims = await _authorize_user_and_grant(
        user, db, payload.organization_id, payload.token, "memory.read"
    )
    value = await run_in_threadpool(
        lambda: controlled(lambda: instance.memory.get(payload.token, payload.key))
    )
    return {"value": value, "agent": claims.sub, "workflow": claims.workflow}


@router.post("/orchestration/dispatch")
async def dispatch_step(
    payload: DispatchRequest,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
):
    instance, _claims = await _authorize_user_and_grant(
        user, db, payload.organization_id, payload.token
    )
    step = AgentStep(
        id=payload.step.id, recipient=payload.step.recipient,
        action=payload.step.action, resource=payload.step.resource,
        payload=payload.step.payload
    )
    def dispatch():
        try:
            return controlled(lambda: instance.orchestrator.dispatch(
                payload.token, step, approval_id=payload.approval_id
            ))
        except ApprovalRequired as exc:
            return {"status": "pending_human_approval", "approval_id": exc.approval_id,
                    "step_id": step.id}
    outcome = await run_in_threadpool(dispatch)
    return outcome


@router.get("/approvals/{approval_id}")
async def get_approval_detail(
    approval_id: str,
    organization_id: str,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
):
    await require_org_role(db, user, organization_id, {"owner", "admin"})
    instance = runtime()
    def lookup():
        from phase14.storage import ApprovalRecord
        with instance.sessions() as session:
            record = session.get(ApprovalRecord, approval_id)
            if record is None or record.tenant != organization_id:
                raise HTTPException(status_code=404, detail="Approval not found.")
            return {
                "id": record.id, "organization_id": record.tenant,
                "workflow": record.workflow, "requester_agent": record.requester_agent,
                "recipient_agent": record.recipient_agent, "action": record.action,
                "resource": record.resource, "payload_sha256": record.payload_digest,
                "state": record.state, "expires_at": record.expires_at,
                "reviewed_by": record.reviewed_by,
                "initiated_by_user_id": record.origin_user_id,
            }
    return await run_in_threadpool(lookup)


@router.post("/approvals/{approval_id}/review")
async def review_approval(
    approval_id: str,
    payload: ReviewRequest,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
):
    await require_org_role(db, user, payload.organization_id, {"owner", "admin"})
    instance = runtime()
    def review():
        from phase14.storage import ApprovalRecord
        with instance.sessions() as session:
            record = session.get(ApprovalRecord, approval_id)
            if record is None or record.tenant != payload.organization_id:
                raise CapabilityError("unknown organization approval")
        return controlled(lambda: instance.approvals.review(
            approval_id, reviewer_id=user.id,
            reviewer_tenant=payload.organization_id,
            authenticated_roles=frozenset({"human_approver"}),
            approve=(payload.decision == "approve")
        ))
    await run_in_threadpool(review)
    return {"state": "approved" if payload.decision == "approve" else "rejected"}


