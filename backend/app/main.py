from __future__ import annotations

import base64
import hashlib
import json
import secrets
from pathlib import Path
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any, Literal

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.sessions import SessionMiddleware

from app.auth import (
    begin_mfa_setup,
    confirm_mfa_setup,
    auth_redis,
    create_access_token,
    current_user,
    enforce_auth_rate_limit,
    hash_password,
    normalize_email,
    verify_mfa,
    verify_password,
)
from app.config import settings
from app.connectors import CONNECTOR_REGISTRY, USAJobsConnector
from app.crypto import decrypt_text, encrypt_text, rotate_ciphertext
from app.db import SessionFactory, engine, get_session
from app.files import MAX_UPLOAD_BYTES, extract_resume_text
from app.llm import CareerLLM, build_fact_ledger
from app.models import (
    Application,
    AuditEvent,
    CandidateProfileRecord,
    KnowledgeDocument,
    Membership,
    Organization,
    ProviderCredential,
    ProviderPublication,
    ResumeDocument,
    User,
    WebhookEvent,
    InboundCandidate,
    InboundApplication,
    InboundAttachment,
)
from app.phase6_api import router as phase6_router
from app.phase7_api import router as phase7_router
from app.phase8_api import router as phase8_router
from app.phase9_api import router as phase9_router
from app.phase10_api import router as phase10_router
from app.phase11_api import router as phase11_router
from app.phase12_api import router as phase12_router
from app.phase13_api import router as phase13_router
from app.phase14_api import router as phase14_router
from app.phase15_17_api import router as phase15_17_router
from app.phase14_metrics import router as phase14_metrics_router, metrics_middleware
from app.telemetry import configure_fastapi_telemetry
from app.partner_providers import (
    PROVIDER_CAPABILITIES,
    build_provider_adapter,
)
from app.schemas import (
    AITailorRequest,
    ApplicationCreate,
    ApplicationResponse,
    CandidateProfile,
    CoverLetterResponse,
    Credentials,
    InterviewAnswerEvaluation,
    InterviewAnswerRequest,
    InterviewPlan,
    KnowledgeStageRequest,
    MFAConfirmRequest,
    MembershipInvite,
    OrganizationCreate,
    PartnerJobRequest,
    ProviderCredentialRequest,
    ProviderResult,
    TailoredResumeResponse,
    USAJobsSyncRequest,
    UserResponse,
    WebhookEventResponse,
    InboundCandidateResponse,
    InboundApplicationResponse,
)
from app.services import (
    application_response,
    approved_knowledge_context,
    audit,
    create_application,
    load_profile,
    ranked_jobs,
    save_profile,
    save_resume_text,
    semantic_concepts,
    stage_knowledge,
    sync_esco,
    sync_onet,
    upsert_jobs,
)
from app.tenancy import (
    ensure_personal_organization,
    normalized_slug,
    refresh_platform_admin,
    require_org_role,
    require_platform_admin,
)
from app.tasks import enqueue_webhook_event
from app.webhook_pipeline import (
    linkedin_challenge_response,
    linkedin_client_secret,
    persist_verified_event,
    provider_credentials,
    purge_expired_inbound_data,
    verify_webhook,
)


APP_VERSION = "0.17.0"
oauth = OAuth()


if settings.oidc_issuer_url and settings.oidc_client_id:
    oauth.register(
        name="enterprise",
        client_id=settings.oidc_client_id,
        client_secret=settings.oidc_client_secret.get_secret_value(),
        server_metadata_url=(
            settings.oidc_issuer_url.rstrip("/")
            + "/.well-known/openid-configuration"
        ),
        client_kwargs={"scope": settings.oidc_scopes},
    )


def user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        is_platform_admin=user.is_platform_admin,
        mfa_enabled=user.mfa_enabled,
    )


def set_session_cookie(response: Response, user_id: str) -> None:
    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie(
        key="career_session",
        value=create_access_token(user_id),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        max_age=60 * 60,
        path="/",
    )
    response.set_cookie(
        key="career_csrf",
        value=csrf_token,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="strict",
        max_age=60 * 60,
        path="/",
    )


async def require_profile(
    session: AsyncSession,
    user_id: str,
) -> CandidateProfile:
    try:
        return await load_profile(session, user_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=409,
            detail="Create your profile first.",
        ) from exc


async def platform_admin(
    user: User = Depends(current_user),
) -> User:
    require_platform_admin(user)
    return user


async def scheduled_sync() -> None:
    async with SessionFactory() as session:
        if settings.onet_api_key.get_secret_value():
            for term in settings.career_seeds:
                try:
                    await sync_onet(session, term, limit=5)
                except Exception:
                    continue

        for term in settings.career_seeds:
            try:
                await sync_esco(session, term)
            except Exception:
                continue

        if (
            settings.usajobs_api_key.get_secret_value()
            and settings.usajobs_user_agent
        ):
            connector = USAJobsConnector()

            for term in settings.job_seeds:
                try:
                    await upsert_jobs(
                        session,
                        await connector.search(term, limit=100),
                    )
                except Exception:
                    continue


async def recover_webhook_queue() -> None:
    """Re-enqueue durable inbox events left behind by broker/worker outages."""

    async with SessionFactory() as session:
        events = (
            await session.scalars(
                select(WebhookEvent)
                .where(WebhookEvent.status.in_(["received", "retry"]))
                .order_by(WebhookEvent.received_at.asc())
                .limit(250)
            )
        ).all()

        for event in events:
            try:
                enqueue_webhook_event(event.id)
            except Exception:
                continue


async def scheduled_privacy_cleanup() -> None:
    async with SessionFactory() as session:
        await purge_expired_inbound_data(session)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.phase12_spiffe_required:
        socket_value = settings.phase12_spiffe_endpoint_socket
        socket_path = socket_value.removeprefix("unix://")

        if not Path(socket_path).exists():
            raise RuntimeError(
                "Phase 12 requires the SPIFFE Workload API socket, "
                f"but it is unavailable at {socket_path}."
            )

    if len(settings.jwt_secret.get_secret_value()) < 32:
        raise RuntimeError("JWT_SECRET must contain at least 32 characters.")

    scheduler: AsyncIOScheduler | None = None

    if settings.scheduler_enabled:
        scheduler = AsyncIOScheduler(timezone="UTC")
        scheduler.add_job(
            scheduled_sync,
            "interval",
            hours=settings.sync_interval_hours,
            id="career-sync",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )
        scheduler.add_job(
            recover_webhook_queue,
            "interval",
            minutes=2,
            id="webhook-recovery",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )
        scheduler.add_job(
            scheduled_privacy_cleanup,
            "interval",
            hours=24,
            id="privacy-cleanup",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )
        scheduler.start()

    app.state.scheduler = scheduler
    yield

    if scheduler:
        scheduler.shutdown(wait=False)

    await auth_redis.aclose()
    await engine.dispose()


app = FastAPI(
    title="Global Career Architecture AI",
    version=APP_VERSION,
    lifespan=lifespan,
)

app.include_router(phase6_router)
app.include_router(phase7_router)
app.include_router(phase8_router)
app.include_router(phase9_router)
app.include_router(phase10_router)
app.include_router(phase11_router)
app.include_router(phase12_router)
app.include_router(phase13_router)
app.include_router(phase14_router)
app.include_router(phase15_17_router)
app.include_router(phase14_metrics_router)
app.middleware("http")(metrics_middleware)
configure_fastapi_telemetry(app)

session_secret = (
    settings.oidc_session_secret.get_secret_value()
    or settings.jwt_secret.get_secret_value()
    or "development-only-change-me"
)

app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret,
    same_site="lax",
    https_only=settings.cookie_secure,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next: Any):
    unsafe = request.method in {"POST", "PUT", "PATCH", "DELETE"}
    has_cookie_session = bool(request.cookies.get("career_session"))
    has_bearer = request.headers.get("authorization", "").lower().startswith("bearer ")

    if unsafe and has_cookie_session and not has_bearer:
        cookie_token = request.cookies.get("career_csrf", "")
        header_token = request.headers.get("x-csrf-token", "")

        if not cookie_token or not secrets.compare_digest(cookie_token, header_token):
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF validation failed."},
            )

    content_length = request.headers.get("content-length")

    if content_length:
        try:
            request_limit = (
                settings.webhook_max_body_bytes
                if request.url.path.startswith("/v1/webhooks/")
                else MAX_UPLOAD_BYTES + 500_000
            )

            if int(content_length) > request_limit:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Request exceeds safety size limit."},
                )
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid Content-Length header."},
            )

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'"
    return response


@app.get("/ready")
async def ready(
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    from sqlalchemy import text
    try:
        await session.execute(text("SELECT 1"))
        if settings.phase14_enabled:
            from app.phase14_runtime import get_phase14_runtime
            from starlette.concurrency import run_in_threadpool
            def check_phase14():
                with get_phase14_runtime().sessions() as db:
                    db.execute(text("SELECT 1"))
            await run_in_threadpool(check_phase14)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Required database or Phase 14 runtime unavailable.") from exc
    response_value = {"status": "ready", "version": APP_VERSION,
                      "region": settings.phase14_region_id}
    return response_value


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": APP_VERSION}


# ---------------------------------------------------------------------------
# Authentication, OIDC/SSO and MFA
# ---------------------------------------------------------------------------


@app.post("/v1/auth/register", response_model=UserResponse)
async def register(
    credentials: Credentials,
    session: AsyncSession = Depends(get_session),
):
    email = normalize_email(credentials.email)
    user = User(
        email=email,
        password_hash=hash_password(credentials.password),
        is_platform_admin=email in settings.admin_email_set,
    )
    session.add(user)

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Email is already registered.",
        ) from exc

    await session.refresh(user)
    await ensure_personal_organization(session, user)
    return user_response(user)


@app.post("/v1/auth/login", response_model=UserResponse)
async def login(
    credentials: Credentials,
    response: Response,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    email = normalize_email(credentials.email)
    client_host = request.client.host if request.client else "unknown"
    await enforce_auth_rate_limit(f"{client_host}:{email}")
    user = await session.scalar(select(User).where(User.email == email))

    if (
        user is None
        or not user.password_hash
        or not verify_password(credentials.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password.",
        )

    if not verify_mfa(user, credentials.mfa_code):
        raise HTTPException(
            status_code=401,
            detail="A valid MFA code is required.",
        )

    if refresh_platform_admin(user):
        await session.commit()

    await ensure_personal_organization(session, user)
    set_session_cookie(response, user.id)
    return user_response(user)


@app.get("/v1/auth/oidc/login")
async def oidc_login(request: Request):
    if not settings.oidc_issuer_url or not settings.oidc_client_id:
        raise HTTPException(
            status_code=503,
            detail="Enterprise OIDC is not configured.",
        )

    client = oauth.create_client("enterprise")

    if client is None:
        raise HTTPException(status_code=503, detail="OIDC client unavailable.")

    return await client.authorize_redirect(
        request,
        settings.oidc_redirect_uri,
    )


@app.get("/v1/auth/oidc/callback")
async def oidc_callback(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    client = oauth.create_client("enterprise")

    if client is None:
        raise HTTPException(status_code=503, detail="OIDC client unavailable.")

    try:
        token = await client.authorize_access_token(request)
    except OAuthError as exc:
        raise HTTPException(
            status_code=401,
            detail="OIDC sign-in failed.",
        ) from exc

    userinfo = token.get("userinfo") or {}
    subject = str(userinfo.get("sub", "")).strip()
    email = normalize_email(str(userinfo.get("email", "")))
    verified = userinfo.get("email_verified", False)

    if not subject or not email:
        raise HTTPException(
            status_code=401,
            detail="OIDC provider did not supply subject and email claims.",
        )

    if settings.oidc_require_verified_email and verified is not True:
        raise HTTPException(
            status_code=401,
            detail="OIDC email address must be verified.",
        )

    oidc_subject = f"{settings.oidc_issuer_url.rstrip('/')}|{subject}"
    user = await session.scalar(
        select(User).where(User.oidc_subject == oidc_subject)
    )

    if user is None:
        user = await session.scalar(select(User).where(User.email == email))

        if user is None:
            user = User(
                email=email,
                oidc_subject=oidc_subject,
                password_hash="",
                is_platform_admin=email in settings.admin_email_set,
            )
            session.add(user)
        else:
            user.oidc_subject = oidc_subject

        await session.commit()
        await session.refresh(user)

    if refresh_platform_admin(user):
        await session.commit()

    await ensure_personal_organization(session, user)
    response = RedirectResponse(
        url=settings.cors_origin_list[0] if settings.cors_origin_list else "/"
    )
    set_session_cookie(response, user.id)
    return response


@app.post("/v1/auth/logout")
async def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie("career_session", path="/")
    response.delete_cookie("career_csrf", path="/")
    return {"ok": True}


@app.get("/v1/auth/me", response_model=UserResponse)
async def me(user: User = Depends(current_user)):
    return user_response(user)


@app.post("/v1/auth/mfa/setup")
async def mfa_setup(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    secret, provisioning_uri = begin_mfa_setup(user)
    await session.commit()
    return {
        "secret": secret,
        "provisioning_uri": provisioning_uri,
        "message": "Store this secret securely and confirm one TOTP code.",
    }


@app.post("/v1/auth/mfa/confirm")
async def mfa_confirm(
    payload: MFAConfirmRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    if not confirm_mfa_setup(user, payload.code):
        raise HTTPException(status_code=400, detail="Invalid MFA code.")

    await session.commit()
    return {"mfa_enabled": True}


@app.post("/v1/auth/mfa/disable")
async def mfa_disable(
    payload: MFAConfirmRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    if not verify_mfa(user, payload.code):
        raise HTTPException(status_code=400, detail="Invalid MFA code.")

    user.mfa_enabled = False
    user.mfa_secret_encrypted = ""
    user.mfa_pending_secret_encrypted = ""
    await session.commit()
    return {"mfa_enabled": False}


# ---------------------------------------------------------------------------
# Organizations / tenants
# ---------------------------------------------------------------------------


@app.get("/v1/organizations")
async def list_organizations(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    rows = (
        await session.execute(
            select(Organization, Membership.role)
            .join(Membership, Membership.organization_id == Organization.id)
            .where(Membership.user_id == user.id)
            .order_by(Organization.name)
        )
    ).all()

    return [
        {
            "id": organization.id,
            "name": organization.name,
            "slug": organization.slug,
            "role": role,
        }
        for organization, role in rows
    ]


@app.post("/v1/organizations")
async def create_organization(
    payload: OrganizationCreate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    slug = normalized_slug(payload.slug)

    if len(slug) < 2:
        raise HTTPException(status_code=422, detail="Invalid organization slug.")

    organization = Organization(
        name=payload.name.strip(),
        slug=slug,
        created_by_user_id=user.id,
    )
    session.add(organization)

    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Organization slug is already in use.",
        ) from exc

    session.add(
        Membership(
            organization_id=organization.id,
            user_id=user.id,
            role="owner",
        )
    )
    await session.commit()
    await session.refresh(organization)
    return {
        "id": organization.id,
        "name": organization.name,
        "slug": organization.slug,
        "role": "owner",
    }


@app.post("/v1/organizations/{organization_id}/members")
async def add_member(
    organization_id: str,
    payload: MembershipInvite,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin"},
    )
    member_user = await session.scalar(
        select(User).where(User.email == normalize_email(payload.email))
    )

    if member_user is None:
        raise HTTPException(
            status_code=404,
            detail="User must register before being added to an organization.",
        )

    existing = await session.scalar(
        select(Membership).where(
            Membership.organization_id == organization_id,
            Membership.user_id == member_user.id,
        )
    )

    if existing:
        if existing.role == "owner":
            raise HTTPException(
                status_code=409,
                detail="Organization owners cannot be demoted through this endpoint.",
            )
        existing.role = payload.role
    else:
        session.add(
            Membership(
                organization_id=organization_id,
                user_id=member_user.id,
                role=payload.role,
            )
        )

    await session.commit()
    return {"email": member_user.email, "role": payload.role}


@app.get("/v1/organizations/{organization_id}/overview")
async def organization_overview(
    organization_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    membership = await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin", "recruiter", "member"},
    )
    member_count = await session.scalar(
        select(func.count(Membership.id)).where(
            Membership.organization_id == organization_id
        )
    )
    provider_count = await session.scalar(
        select(func.count(ProviderCredential.id)).where(
            ProviderCredential.organization_id == organization_id,
            ProviderCredential.enabled.is_(True),
        )
    )
    publication_count = await session.scalar(
        select(func.count(ProviderPublication.id)).where(
            ProviderPublication.organization_id == organization_id
        )
    )
    return {
        "role": membership.role,
        "members": member_count or 0,
        "enabled_providers": provider_count or 0,
        "provider_publications": publication_count or 0,
    }


# ---------------------------------------------------------------------------
# Encrypted provider configuration and authorized ATS/provider adapters
# ---------------------------------------------------------------------------


@app.get("/v1/providers/capabilities")
async def provider_capabilities(_: User = Depends(current_user)):
    return PROVIDER_CAPABILITIES


@app.put("/v1/organizations/{organization_id}/providers/{provider}/credentials")
async def put_provider_credentials(
    organization_id: str,
    provider: Literal["linkedin", "indeed", "ziprecruiter"],
    payload: ProviderCredentialRequest,
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
        build_provider_adapter(provider, payload.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    encrypted = encrypt_text(
        json.dumps(payload.credentials, separators=(",", ":")),
        aad=f"provider:{organization_id}:{provider}",
    )
    record = await session.scalar(
        select(ProviderCredential).where(
            ProviderCredential.organization_id == organization_id,
            ProviderCredential.provider == provider,
        )
    )

    if record is None:
        record = ProviderCredential(
            organization_id=organization_id,
            provider=provider,
            encrypted_payload=encrypted,
            enabled=payload.enabled,
        )
        session.add(record)
    else:
        record.encrypted_payload = encrypted
        record.enabled = payload.enabled

    await session.commit()
    await audit(
        session,
        "provider.credentials.update",
        user.id,
        {"organization_id": organization_id, "provider": provider},
    )
    return {
        "provider": provider,
        "enabled": payload.enabled,
        "credentials_returned": False,
    }


@app.get("/v1/organizations/{organization_id}/providers")
async def list_provider_credentials(
    organization_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin", "recruiter", "member"},
    )
    records = (
        await session.scalars(
            select(ProviderCredential).where(
                ProviderCredential.organization_id == organization_id
            )
        )
    ).all()
    return [
        {
            "provider": record.provider,
            "enabled": record.enabled,
            "updated_at": record.updated_at,
        }
        for record in records
    ]


@app.post(
    "/v1/organizations/{organization_id}/providers/{provider}/jobs",
    response_model=ProviderResult,
)
async def publish_partner_job(
    organization_id: str,
    provider: Literal["linkedin", "indeed", "ziprecruiter"],
    payload: PartnerJobRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin"},
    )
    credential = await session.scalar(
        select(ProviderCredential).where(
            ProviderCredential.organization_id == organization_id,
            ProviderCredential.provider == provider,
            ProviderCredential.enabled.is_(True),
        )
    )

    if credential is None:
        raise HTTPException(
            status_code=409,
            detail=f"{provider} credentials are not enabled for this organization.",
        )

    credentials = json.loads(
        decrypt_text(
            credential.encrypted_payload,
            aad=f"provider:{organization_id}:{provider}",
        )
    )
    existing = await session.scalar(
        select(ProviderPublication).where(
            ProviderPublication.organization_id == organization_id,
            ProviderPublication.provider == provider,
            ProviderPublication.external_job_id == payload.external_job_id,
        )
    )

    if (
        provider == "indeed"
        and payload.operation == "CLOSE"
        and not payload.provider_job_id
        and existing
    ):
        payload = payload.model_copy(
            update={"provider_job_id": existing.provider_job_id}
        )

    try:
        result = await build_provider_adapter(provider, credentials).publish(payload)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if existing is None:
        existing = ProviderPublication(
            organization_id=organization_id,
            provider=provider,
            external_job_id=payload.external_job_id,
            provider_job_id=result.provider_job_id,
            operation=payload.operation,
            status=result.status,
            response_json=result.response,
        )
        session.add(existing)
    else:
        existing.provider_job_id = result.provider_job_id or existing.provider_job_id
        existing.operation = payload.operation
        existing.status = result.status
        existing.response_json = result.response

    await session.commit()
    await audit(
        session,
        "provider.job.publish",
        user.id,
        {
            "organization_id": organization_id,
            "provider": provider,
            "external_job_id": payload.external_job_id,
            "operation": payload.operation,
        },
    )
    return result



# ---------------------------------------------------------------------------
# Phase 5 verified application webhooks and durable candidate ingestion
# ---------------------------------------------------------------------------


@app.get("/v1/webhooks/{organization_id}/linkedin")
async def linkedin_webhook_validation(
    organization_id: str,
    challenge_code: str = Query(alias="challengeCode", min_length=1, max_length=500),
    application_id: str | None = Query(
        default=None,
        alias="applicationId",
        max_length=500,
    ),
    session: AsyncSession = Depends(get_session),
):
    credentials = await provider_credentials(
        session,
        organization_id,
        "linkedin",
    )
    secret = linkedin_client_secret(credentials, application_id)

    if not secret:
        raise HTTPException(
            status_code=503,
            detail="LinkedIn client secret is not configured.",
        )

    return {
        "challengeCode": challenge_code,
        "challengeResponse": linkedin_challenge_response(
            challenge_code,
            secret,
        ),
    }


@app.post("/v1/webhooks/{organization_id}/{provider}")
async def receive_provider_webhook(
    organization_id: str,
    provider: Literal["linkedin", "indeed", "ziprecruiter"],
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    raw_body = await request.body()
    headers = {
        key.lower(): value
        for key, value in request.headers.items()
    }

    verified = await verify_webhook(
        session,
        organization_id,
        provider,
        raw_body,
        headers,
    )
    event, duplicate = await persist_verified_event(
        session,
        organization_id,
        verified,
        raw_body,
    )

    queue_dispatched = False

    if event.status not in {"processed", "ignored"}:
        try:
            enqueue_webhook_event(event.id)
            queue_dispatched = True
        except Exception:
            # The database inbox is the durability boundary. The scheduler will
            # recover received/retry events when the queue becomes available.
            queue_dispatched = False

    return {
        "received": True,
        "duplicate": duplicate,
        "event_id": event.id,
        "provider_event_id": event.event_id,
        "queue_dispatched": queue_dispatched,
    }


@app.get(
    "/v1/organizations/{organization_id}/webhooks/events",
    response_model=list[WebhookEventResponse],
)
async def list_webhook_events(
    organization_id: str,
    status: str = Query(default="", max_length=50),
    limit: int = Query(default=100, ge=1, le=250),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin", "recruiter"},
    )
    statement = select(WebhookEvent).where(
        WebhookEvent.organization_id == organization_id
    )

    if status:
        statement = statement.where(WebhookEvent.status == status)

    records = (
        await session.scalars(
            statement.order_by(WebhookEvent.received_at.desc()).limit(limit)
        )
    ).all()

    return [
        WebhookEventResponse(
            id=record.id,
            provider=record.provider,
            event_id=record.event_id,
            event_type=record.event_type,
            status=record.status,
            attempts=record.attempts,
            received_at=record.received_at,
            processed_at=record.processed_at,
            last_error=record.last_error,
        )
        for record in records
    ]


@app.post("/v1/organizations/{organization_id}/webhooks/{event_id}/requeue")
async def requeue_webhook_event(
    organization_id: str,
    event_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin"},
    )
    event = await session.get(WebhookEvent, event_id)

    if event is None or event.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Webhook event not found.")

    if event.status == "processed":
        return {"queued": False, "status": "processed"}

    event.status = "received"
    event.last_error = ""
    await session.commit()

    try:
        enqueue_webhook_event(event.id)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Event persisted but the worker queue is unavailable.",
        ) from exc

    await audit(
        session,
        "webhook.event.requeue",
        user.id,
        {
            "organization_id": organization_id,
            "event_id": event.id,
            "provider": event.provider,
        },
    )
    return {"queued": True, "status": event.status}


@app.get(
    "/v1/organizations/{organization_id}/inbound-candidates",
    response_model=list[InboundCandidateResponse],
)
async def list_inbound_candidates(
    organization_id: str,
    limit: int = Query(default=100, ge=1, le=250),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin", "recruiter"},
    )
    records = (
        await session.scalars(
            select(InboundCandidate)
            .where(InboundCandidate.organization_id == organization_id)
            .order_by(InboundCandidate.received_at.desc())
            .limit(limit)
        )
    ).all()
    output: list[InboundCandidateResponse] = []

    for record in records:
        payload = json.loads(
            decrypt_text(
                record.encrypted_payload,
                aad=f"inbound-candidate:{organization_id}:{record.id}",
            )
        )
        output.append(
            InboundCandidateResponse(
                id=record.id,
                provider=record.provider,
                provider_candidate_id=record.provider_candidate_id,
                full_name=str(payload.get("full_name", "")),
                email=str(payload.get("email", "")),
                phone=str(payload.get("phone", "")),
                source=record.source,
                received_at=record.received_at,
                retention_until=record.retention_until,
            )
        )

    return output


@app.get(
    "/v1/organizations/{organization_id}/inbound-applications",
    response_model=list[InboundApplicationResponse],
)
async def list_inbound_applications(
    organization_id: str,
    limit: int = Query(default=100, ge=1, le=250),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin", "recruiter"},
    )
    records = (
        await session.scalars(
            select(InboundApplication)
            .where(InboundApplication.organization_id == organization_id)
            .order_by(InboundApplication.received_at.desc())
            .limit(limit)
        )
    ).all()

    return [
        InboundApplicationResponse(
            id=record.id,
            provider=record.provider,
            provider_application_id=record.provider_application_id,
            external_job_id=record.external_job_id,
            candidate_id=record.candidate_id,
            source_attribution=record.source_attribution,
            status=record.status,
            received_at=record.received_at,
        )
        for record in records
    ]



@app.get("/v1/organizations/{organization_id}/inbound-attachments")
async def list_inbound_attachments(
    organization_id: str,
    candidate_id: str = Query(default="", max_length=36),
    application_id: str = Query(default="", max_length=36),
    limit: int = Query(default=100, ge=1, le=250),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin", "recruiter"},
    )
    statement = select(InboundAttachment).where(
        InboundAttachment.organization_id == organization_id
    )

    if candidate_id:
        statement = statement.where(InboundAttachment.candidate_id == candidate_id)

    if application_id:
        statement = statement.where(
            InboundAttachment.application_id == application_id
        )

    records = (
        await session.scalars(
            statement.order_by(InboundAttachment.created_at.desc()).limit(limit)
        )
    ).all()

    return [
        {
            "id": record.id,
            "candidate_id": record.candidate_id,
            "application_id": record.application_id,
            "provider": record.provider,
            "filename": record.filename,
            "content_type": record.content_type,
            "sha256": record.sha256,
            "created_at": record.created_at,
            "retention_until": record.retention_until,
        }
        for record in records
    ]


@app.get(
    "/v1/organizations/{organization_id}/inbound-attachments/{attachment_id}/download"
)
async def download_inbound_attachment(
    organization_id: str,
    attachment_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin", "recruiter"},
    )
    record = await session.get(InboundAttachment, attachment_id)

    if record is None or record.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Attachment not found.")

    encoded = decrypt_text(
        record.encrypted_base64,
        aad=f"inbound-attachment:{organization_id}:{record.id}",
    )

    try:
        content = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Attachment could not be decrypted safely.",
        ) from exc

    safe_filename = (
        record.filename.replace("\r", "_")
        .replace("\n", "_")
        .replace('"', "_")
    )

    await audit(
        session,
        "candidate.attachment.download",
        user.id,
        {
            "organization_id": organization_id,
            "attachment_id": record.id,
            "candidate_id": record.candidate_id,
        },
    )

    return Response(
        content=content,
        media_type=record.content_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.delete(
    "/v1/organizations/{organization_id}/inbound-candidates/{candidate_id}"
)
async def delete_inbound_candidate(
    organization_id: str,
    candidate_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await require_org_role(
        session,
        user,
        organization_id,
        {"owner", "admin"},
    )
    candidate = await session.get(InboundCandidate, candidate_id)

    if candidate is None or candidate.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    provider = candidate.provider
    await session.delete(candidate)
    await session.commit()
    await audit(
        session,
        "candidate.delete",
        user.id,
        {
            "organization_id": organization_id,
            "candidate_id": candidate_id,
            "provider": provider,
        },
    )
    return {"deleted": True}


@app.post("/v1/admin/privacy/purge-expired")
async def purge_expired_candidate_data(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    require_platform_admin(user)
    result = await purge_expired_inbound_data(session)
    await audit(
        session,
        "privacy.retention.purge",
        user.id,
        result,
    )
    return result


# ---------------------------------------------------------------------------
# Candidate profile / resume / AI / job matching
# ---------------------------------------------------------------------------


@app.put("/v1/profile", response_model=CandidateProfile)
async def put_profile(
    payload: CandidateProfile,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await save_profile(session, user.id, payload)
    await audit(session, "profile.update", user.id, {"fields": len(payload.model_fields)})
    return payload


@app.get("/v1/profile", response_model=CandidateProfile)
async def get_profile(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await load_profile(session, user.id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/v1/resumes/upload")
async def upload_resume(
    resume: UploadFile = File(...),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    data = await resume.read(MAX_UPLOAD_BYTES + 1)

    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Résumé exceeds 5 MB.")

    filename = (resume.filename or "resume.txt")[:500]
    extracted = extract_resume_text(filename, data)
    digest = hashlib.sha256(data).hexdigest()
    resume_id = str(uuid.uuid4())
    record = await save_resume_text(
        session,
        user.id,
        resume_id,
        filename,
        digest,
        extracted,
    )
    await audit(
        session,
        "resume.upload",
        user.id,
        {"resume_id": record.id, "filename": record.filename},
    )
    return {
        "id": record.id,
        "filename": record.filename,
        "characters_extracted": len(extracted),
        "raw_file_retained": False,
    }


@app.get("/v1/resumes")
async def resumes(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    records = (
        await session.scalars(
            select(ResumeDocument)
            .where(ResumeDocument.user_id == user.id)
            .order_by(ResumeDocument.created_at.desc())
        )
    ).all()
    return [
        {"id": item.id, "filename": item.filename, "created_at": item.created_at}
        for item in records
    ]


@app.get("/v1/sources")
async def sources(_: User = Depends(current_user)):
    return {
        "candidate_discovery_sources": CONNECTOR_REGISTRY,
        "partner_ats_sources": PROVIDER_CAPABILITIES,
        "policy": (
            "Provider partner APIs are used only for capabilities authorized by "
            "the provider agreement. They are not treated as unrestricted job-search feeds."
        ),
    }


@app.get("/v1/career/search")
async def career_search(
    q: str = Query(min_length=2, max_length=2000),
    kind: Literal["occupation", "skill", "ability"] | None = None,
    limit: int = Query(default=15, ge=1, le=50),
    _: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    return await semantic_concepts(session, q, kind, limit)


@app.get("/v1/jobs/matches")
async def job_matches(
    q: str = Query(default="", max_length=300),
    location: str = Query(default="", max_length=300),
    limit: int = Query(default=30, ge=1, le=100),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    profile = await require_profile(session, user.id)
    return await ranked_jobs(session, profile, q, location, limit)


@app.post("/v1/ai/resume", response_model=TailoredResumeResponse)
async def ai_resume(
    payload: AITailorRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    profile = await require_profile(session, user.id)
    knowledge = await approved_knowledge_context(
        session,
        f"{payload.target.title} {payload.target.description}",
    )

    try:
        result = await CareerLLM().tailor_resume(
            profile,
            payload.target,
            payload.style,
            knowledge,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Generated résumé failed fact guardrails: {exc}",
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return TailoredResumeResponse(
        resume=result,
        fact_count=len(build_fact_ledger(profile).facts),
        guardrails_passed=True,
    )


@app.post("/v1/ai/cover-letter", response_model=CoverLetterResponse)
async def ai_cover_letter(
    payload: AITailorRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    profile = await require_profile(session, user.id)
    knowledge = await approved_knowledge_context(
        session,
        f"{payload.target.title} {payload.target.description}",
    )

    try:
        result = await CareerLLM().cover_letter(
            profile,
            payload.target,
            knowledge,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Generated cover letter failed fact guardrails: {exc}",
        ) from exc

    return CoverLetterResponse(
        cover_letter=result,
        guardrails_passed=True,
    )


@app.post("/v1/ai/interview-plan", response_model=InterviewPlan)
async def ai_interview_plan(
    payload: AITailorRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    profile = await require_profile(session, user.id)
    return await CareerLLM().interview_plan(profile, payload.target)


@app.post(
    "/v1/ai/interview-evaluate",
    response_model=InterviewAnswerEvaluation,
)
async def ai_interview_evaluate(
    payload: InterviewAnswerRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    profile = await require_profile(session, user.id)
    return await CareerLLM().evaluate_interview_answer(
        profile,
        payload.target,
        payload.question,
        payload.answer,
    )


@app.post("/v1/applications", response_model=ApplicationResponse)
async def add_application(
    payload: ApplicationCreate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    record = await create_application(session, user.id, payload)
    await audit(
        session,
        "application.create",
        user.id,
        {"application_id": record.id},
    )
    return application_response(record)


@app.get("/v1/applications", response_model=list[ApplicationResponse])
async def list_applications(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    records = (
        await session.scalars(
            select(Application)
            .where(Application.user_id == user.id)
            .order_by(Application.created_at.desc())
        )
    ).all()
    return [application_response(record) for record in records]


@app.patch("/v1/applications/{application_id}", response_model=ApplicationResponse)
async def update_application(
    application_id: str,
    payload: ApplicationCreate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    record = await session.get(Application, application_id)

    if record is None or record.user_id != user.id:
        raise HTTPException(status_code=404, detail="Application not found.")

    record.job_id = payload.job_id
    record.title = payload.title
    record.organization = payload.organization
    record.status = payload.status
    record.applied_at = payload.applied_at
    record.encrypted_notes = (
        encrypt_text(
            payload.notes,
            aad=f"application:{user.id}:{record.id}",
        )
        if payload.notes
        else ""
    )
    await session.commit()
    await session.refresh(record)
    return application_response(record)


@app.delete("/v1/applications/{application_id}")
async def delete_application(
    application_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    record = await session.get(Application, application_id)

    if record is None or record.user_id != user.id:
        raise HTTPException(status_code=404, detail="Application not found.")

    await session.delete(record)
    await session.commit()
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Key rotation
# ---------------------------------------------------------------------------


@app.post("/v1/security/rotate-data-keys")
async def rotate_user_data_keys(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    rotated = 0
    profile = await session.get(CandidateProfileRecord, user.id)

    if profile:
        profile.encrypted_payload = rotate_ciphertext(
            profile.encrypted_payload,
            aad=f"profile:{user.id}",
        )
        rotated += 1

    resume_records = (
        await session.scalars(
            select(ResumeDocument).where(ResumeDocument.user_id == user.id)
        )
    ).all()

    for resume in resume_records:
        resume.encrypted_text = rotate_ciphertext(
            resume.encrypted_text,
            aad=f"resume:{user.id}:{resume.id}",
        )
        rotated += 1

    application_records = (
        await session.scalars(
            select(Application).where(Application.user_id == user.id)
        )
    ).all()

    for application in application_records:
        if application.encrypted_notes:
            application.encrypted_notes = rotate_ciphertext(
                application.encrypted_notes,
                aad=f"application:{user.id}:{application.id}",
            )
            rotated += 1

    await session.commit()
    await audit(
        session,
        "security.user_data_keys.rotate",
        user.id,
        {"records": rotated},
    )
    return {"rotated_records": rotated}


@app.post("/v1/organizations/{organization_id}/security/rotate-provider-keys")
async def rotate_provider_keys(
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
    records = (
        await session.scalars(
            select(ProviderCredential).where(
                ProviderCredential.organization_id == organization_id
            )
        )
    ).all()

    for record in records:
        record.encrypted_payload = rotate_ciphertext(
            record.encrypted_payload,
            aad=f"provider:{organization_id}:{record.provider}",
        )

    await session.commit()
    return {"rotated_provider_credentials": len(records)}


# ---------------------------------------------------------------------------
# Platform administration and controlled intelligence updates
# ---------------------------------------------------------------------------


@app.get("/v1/admin/overview")
async def admin_overview(
    _: User = Depends(platform_admin),
    session: AsyncSession = Depends(get_session),
):
    counts = {}

    for name, model in [
        ("users", User),
        ("organizations", Organization),
        ("memberships", Membership),
        ("applications", Application),
        ("provider_credentials", ProviderCredential),
        ("provider_publications", ProviderPublication),
        ("knowledge_documents", KnowledgeDocument),
    ]:
        counts[name] = int(
            await session.scalar(select(func.count()).select_from(model)) or 0
        )

    audits = (
        await session.scalars(
            select(AuditEvent)
            .order_by(AuditEvent.created_at.desc())
            .limit(25)
        )
    ).all()
    return {
        "counts": counts,
        "recent_audit_events": [
            {
                "event": item.event,
                "actor": item.actor,
                "details": item.details,
                "created_at": item.created_at,
            }
            for item in audits
        ],
    }


@app.post("/v1/admin/sync/usajobs")
async def sync_usajobs_endpoint(
    payload: USAJobsSyncRequest,
    user: User = Depends(platform_admin),
    session: AsyncSession = Depends(get_session),
):
    connector = USAJobsConnector()

    try:
        records = await connector.search(
            payload.keyword,
            payload.location,
            payload.limit,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"USAJOBS synchronization failed: {type(exc).__name__}",
        ) from exc

    count = await upsert_jobs(session, records)
    await audit(session, "sync.usajobs", user.id, {"records": count})
    return {"source": "usajobs", "records": count}


@app.post("/v1/admin/sync/onet")
async def sync_onet_endpoint(
    keyword: str = Query(min_length=1, max_length=300),
    user: User = Depends(platform_admin),
    session: AsyncSession = Depends(get_session),
):
    try:
        count = await sync_onet(session, keyword)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"O*NET synchronization failed: {type(exc).__name__}",
        ) from exc

    await audit(session, "sync.onet", user.id, {"keyword": keyword, "records": count})
    return {"source": "onet", "records": count}


@app.post("/v1/admin/sync/esco")
async def sync_esco_endpoint(
    keyword: str = Query(min_length=1, max_length=300),
    user: User = Depends(platform_admin),
    session: AsyncSession = Depends(get_session),
):
    try:
        count = await sync_esco(session, keyword)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"ESCO synchronization failed: {type(exc).__name__}",
        ) from exc

    await audit(session, "sync.esco", user.id, {"keyword": keyword, "records": count})
    return {"source": "esco", "records": count}


@app.post("/v1/admin/knowledge/stage")
async def stage_knowledge_endpoint(
    payload: KnowledgeStageRequest,
    user: User = Depends(platform_admin),
    session: AsyncSession = Depends(get_session),
):
    document = await stage_knowledge(
        session,
        source=payload.source,
        title=payload.title,
        content=payload.content,
        source_url=str(payload.source_url or ""),
        license_name=payload.license,
    )
    await audit(
        session,
        "knowledge.stage",
        user.id,
        {"document_id": document.id},
    )
    return {"id": document.id, "status": document.status}


@app.post("/v1/admin/knowledge/{document_id}/{decision}")
async def review_knowledge(
    document_id: str,
    decision: Literal["approve", "reject"],
    user: User = Depends(platform_admin),
    session: AsyncSession = Depends(get_session),
):
    document = await session.get(KnowledgeDocument, document_id)

    if document is None:
        raise HTTPException(status_code=404, detail="Knowledge document not found.")

    document.status = "approved" if decision == "approve" else "rejected"
    document.reviewed_at = datetime.now(UTC)
    await session.commit()
    await audit(
        session,
        f"knowledge.{decision}",
        user.id,
        {"document_id": document_id},
    )
    return {"id": document_id, "status": document.status}
