from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crypto import decrypt_text, encrypt_text
from app.models import (
    CareerPortfolio,
    CareerPortfolioShare,
    VerifiedCredential,
)
from app.schemas import PortfolioRequest, PortfolioShareRequest
from app.services import load_profile


def _portfolio_aad(user_id: str, portfolio_id: str) -> str:
    return f"career-portfolio:{user_id}:{portfolio_id}"


def _credential_public(record: VerifiedCredential) -> dict[str, Any]:
    return {
        "title": record.title,
        "credential_type": record.credential_type,
        "issuer_name": record.issuer_name,
        "issuer_url": record.issuer_url,
        "verification_level": record.verification_level,
        "verification_status": record.verification_status,
        "skills": record.skills,
        "issued_at": record.issued_at.isoformat() if record.issued_at else None,
        "expires_at": record.expires_at.isoformat() if record.expires_at else None,
    }


async def build_portfolio(
    session: AsyncSession,
    user_id: str,
    request: PortfolioRequest,
) -> tuple[CareerPortfolio, dict[str, Any]]:
    profile = await load_profile(session, user_id)

    credentials: list[dict[str, Any]] = []

    if request.include_verified_credentials:
        credential_rows = (
            await session.scalars(
                select(VerifiedCredential)
                .where(
                    VerifiedCredential.user_id == user_id,
                    VerifiedCredential.verification_status == "verified",
                )
                .order_by(VerifiedCredential.created_at.desc())
            )
        ).all()
        credentials = [_credential_public(item) for item in credential_rows]

    payload: dict[str, Any] = {
        "identity": {
            "name": profile.full_name,
            "location": profile.location,
            "email": profile.email,
            "phone": profile.phone,
        },
        "headline": request.headline,
        "about": request.about or profile.summary,
        "skills": profile.skills,
        "abilities": profile.abilities,
        "core_values": profile.core_values,
        "experience": [
            item.model_dump()
            for item in profile.experience
        ],
        "education": [
            item.model_dump()
            for item in profile.education
        ],
        "certifications_claimed": profile.certifications,
        "publications": profile.publications,
        "verified_credentials": credentials,
        "projects": [
            item.model_dump()
            for item in request.projects
        ],
        "links": request.links,
        "portfolio_notice": (
            "Verified credentials are shown separately from candidate-authored "
            "certification claims."
        ),
    }

    record = await session.scalar(
        select(CareerPortfolio).where(CareerPortfolio.user_id == user_id)
    )

    if record is None:
        record = CareerPortfolio(
            user_id=user_id,
            encrypted_payload="",
        )
        session.add(record)
        await session.flush()
    else:
        record.version += 1

    record.encrypted_payload = encrypt_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        aad=_portfolio_aad(user_id, record.id),
    )

    await session.commit()
    await session.refresh(record)
    return record, payload


def decrypt_portfolio(record: CareerPortfolio) -> dict[str, Any]:
    return json.loads(
        decrypt_text(
            record.encrypted_payload,
            aad=_portfolio_aad(record.user_id, record.id),
        )
    )


def filter_public_portfolio(
    payload: dict[str, Any],
    visibility: dict[str, Any],
) -> dict[str, Any]:
    identity = dict(payload.get("identity", {}))

    if not visibility.get("include_contact", False):
        identity.pop("email", None)
        identity.pop("phone", None)

    output: dict[str, Any] = {
        "identity": identity,
        "headline": payload.get("headline", ""),
        "about": payload.get("about", ""),
        "core_values": payload.get("core_values", []),
        "links": payload.get("links", []),
        "portfolio_notice": payload.get("portfolio_notice", ""),
    }

    if visibility.get("include_skills", True):
        output["skills"] = payload.get("skills", [])
        output["abilities"] = payload.get("abilities", [])

    if visibility.get("include_experience", True):
        output["experience"] = payload.get("experience", [])

    if visibility.get("include_education", True):
        output["education"] = payload.get("education", [])
        output["publications"] = payload.get("publications", [])

    if visibility.get("include_credentials", True):
        output["verified_credentials"] = payload.get("verified_credentials", [])

    if visibility.get("include_projects", True):
        output["projects"] = payload.get("projects", [])

    return output


async def create_share(
    session: AsyncSession,
    portfolio: CareerPortfolio,
    request: PortfolioShareRequest,
) -> tuple[CareerPortfolioShare, str]:
    token = secrets.token_urlsafe(36)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    days = request.expires_in_days or settings.phase8_portfolio_default_share_days

    share = CareerPortfolioShare(
        portfolio_id=portfolio.id,
        token_hash=token_hash,
        visibility_json={
            "include_contact": request.include_contact,
            "include_experience": request.include_experience,
            "include_education": request.include_education,
            "include_skills": request.include_skills,
            "include_credentials": request.include_credentials,
            "include_projects": request.include_projects,
        },
        expires_at=datetime.now(UTC) + timedelta(days=days),
    )
    session.add(share)
    await session.commit()
    await session.refresh(share)
    return share, token


async def public_portfolio(
    session: AsyncSession,
    token: str,
) -> dict[str, Any]:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    share = await session.scalar(
        select(CareerPortfolioShare).where(
            CareerPortfolioShare.token_hash == token_hash
        )
    )

    now = datetime.now(UTC)

    if (
        share is None
        or share.revoked_at is not None
        or share.expires_at <= now
    ):
        raise LookupError("Portfolio share is unavailable or expired.")

    portfolio = await session.get(CareerPortfolio, share.portfolio_id)

    if portfolio is None:
        raise LookupError("Portfolio is unavailable.")

    payload = decrypt_portfolio(portfolio)
    share.last_accessed_at = now
    await session.commit()

    return filter_public_portfolio(
        payload,
        share.visibility_json or {},
    )
