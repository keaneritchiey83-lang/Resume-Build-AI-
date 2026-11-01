from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import time

import jwt
import pyotp
from fastapi import Depends, HTTPException, Request
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crypto import decrypt_text, encrypt_text
from app.db import get_session
from app.models import User
from app.tenancy import ensure_personal_organization, refresh_platform_admin


password_hash = PasswordHash.recommended()
ACCESS_TOKEN_MINUTES = 60
auth_redis = Redis.from_url(settings.redis_url, decode_responses=True)



async def enforce_auth_rate_limit(
    identity: str,
    *,
    maximum: int = 10,
    window_seconds: int = 900,
) -> None:
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    bucket = int(time.time() // window_seconds)
    key = f"auth-rate:{digest}:{bucket}"

    try:
        count = await auth_redis.incr(key)

        if count == 1:
            await auth_redis.expire(key, window_seconds + 30)
    except RedisError as exc:
        raise HTTPException(
            status_code=503,
            detail="Authentication protection service unavailable.",
        ) from exc

    if count > maximum:
        raise HTTPException(
            status_code=429,
            detail="Too many authentication attempts. Try again later.",
        )

def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    return bool(encoded) and password_hash.verify(password, encoded)


def create_access_token(user_id: str) -> str:
    secret = settings.jwt_secret.get_secret_value()

    if len(secret) < 32:
        raise RuntimeError("JWT_SECRET must contain at least 32 characters.")

    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": user_id,
            "iat": now,
            "exp": now + timedelta(minutes=ACCESS_TOKEN_MINUTES),
            "aud": "career-api",
        },
        secret,
        algorithm="HS256",
    )


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=["HS256"],
            audience="career-api",
        )
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid session.") from exc

    subject = payload.get("sub")

    if not isinstance(subject, str) or not subject:
        raise HTTPException(status_code=401, detail="Invalid session subject.")

    return subject


def verify_mfa(user: User, code: str) -> bool:
    if not user.mfa_enabled:
        return True

    if not code or not user.mfa_secret_encrypted:
        return False

    secret = decrypt_text(
        user.mfa_secret_encrypted,
        aad=f"mfa:{user.id}",
    )
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def begin_mfa_setup(user: User) -> tuple[str, str]:
    secret = pyotp.random_base32()
    user.mfa_pending_secret_encrypted = encrypt_text(
        secret,
        aad=f"mfa-pending:{user.id}",
    )
    uri = pyotp.TOTP(secret).provisioning_uri(
        name=user.email,
        issuer_name="Global Career Architecture AI",
    )
    return secret, uri


def confirm_mfa_setup(user: User, code: str) -> bool:
    if not user.mfa_pending_secret_encrypted:
        return False

    secret = decrypt_text(
        user.mfa_pending_secret_encrypted,
        aad=f"mfa-pending:{user.id}",
    )

    if not pyotp.TOTP(secret).verify(code, valid_window=1):
        return False

    user.mfa_secret_encrypted = encrypt_text(
        secret,
        aad=f"mfa:{user.id}",
    )
    user.mfa_pending_secret_encrypted = ""
    user.mfa_enabled = True
    return True


async def current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User:
    token = request.cookies.get("career_session")

    if not token:
        authorization = request.headers.get("authorization", "")
        scheme, _, value = authorization.partition(" ")

        if scheme.lower() == "bearer":
            token = value.strip()

    if not token:
        raise HTTPException(status_code=401, detail="Authentication required.")

    user_id = decode_access_token(token)
    user = await session.get(User, user_id)

    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User is unavailable.")

    dirty = refresh_platform_admin(user)
    await ensure_personal_organization(session, user)

    if dirty:
        await session.commit()

    return user
