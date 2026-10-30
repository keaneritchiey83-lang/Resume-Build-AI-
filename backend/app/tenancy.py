from __future__ import annotations

import re

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Membership, Organization, User


ALLOWED_ROLES = {"owner", "admin", "recruiter", "member"}


def normalized_slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9-]+", "-", value.strip().lower()).strip("-")
    return re.sub(r"-{2,}", "-", result)


async def ensure_personal_organization(
    session: AsyncSession,
    user: User,
) -> Organization:
    membership = await session.scalar(
        select(Membership).where(Membership.user_id == user.id).limit(1)
    )

    if membership:
        organization = await session.get(Organization, membership.organization_id)

        if organization is not None:
            return organization

    base = normalized_slug(user.email.split("@", 1)[0]) or "user"
    slug = f"{base}-{user.id[:8]}"
    organization = Organization(
        name=f"{user.email} Workspace",
        slug=slug,
        created_by_user_id=user.id,
    )
    session.add(organization)
    await session.flush()
    session.add(
        Membership(
            organization_id=organization.id,
            user_id=user.id,
            role="owner",
        )
    )
    await session.commit()
    await session.refresh(organization)
    return organization


async def require_org_role(
    session: AsyncSession,
    user: User,
    organization_id: str,
    allowed_roles: set[str],
) -> Membership:
    membership = await session.scalar(
        select(Membership).where(
            Membership.organization_id == organization_id,
            Membership.user_id == user.id,
        )
    )

    if membership is None or membership.role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Organization access denied.")

    return membership


def refresh_platform_admin(user: User) -> bool:
    should_be_admin = user.email.lower() in settings.admin_email_set

    if user.is_platform_admin != should_be_admin:
        user.is_platform_admin = should_be_admin
        return True

    return False


def require_platform_admin(user: User) -> None:
    if not user.is_platform_admin:
        raise HTTPException(status_code=403, detail="Platform administrator required.")
