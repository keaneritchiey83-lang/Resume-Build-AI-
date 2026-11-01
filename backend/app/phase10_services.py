from __future__ import annotations

import base64
import hashlib
import json
import math
import re
import secrets
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import quote, urlencode

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crypto import decrypt_text, encrypt_text
from app.db import Base
from app.models import (
    Application,
    CandidateProfileRecord,
    CandidateWallet,
    ConsentReceipt,
    CredentialAccessToken,
    CredentialAuthorizationCode,
    CredentialConfiguration,
    CredentialIssuanceOffer,
    CredentialIssuerProfile,
    CredentialTrustAnchor,
    CredentialVerifierProfile,
    CredentialWalletClient,
    CryptographicAuditEntry,
    DataClassificationRule,
    DataDiscoveryFinding,
    DataDiscoveryScan,
    DataSubjectRequest,
    DeletionWorkflow,
    InboundCandidate,
    IssuedCredentialRecord,
    JobRecommendation,
    Membership,
    PresentationRequestRecord,
    PresentationSubmission,
    PrivacyAnalyticsBudget,
    PrivacyAnalyticsRelease,
    ResumeDocument,
    RetentionPolicy,
    SkillsPassport,
    User,
    VerifiedCredential,
)
from app.phase10_schemas import (
    AuditLedgerAppendRequest,
    ClassificationRuleRequest,
    ConsentReceiptRequest,
    CredentialConfigurationRequest,
    CredentialOfferRequest,
    IssuerProfileCreateRequest,
    PrivacyAnalyticsRequest,
    TrustAnchorRequest,
    VerifierProfileCreateRequest,
    WalletClientRegistrationRequest,
)
from app.phase9_services import decrypt_skills_passport
from app.services import load_profile
from app.tenancy import normalized_slug


PRE_AUTH_GRANT = "urn:ietf:params:oauth:grant-type:pre-authorized_code"
SUPPORTED_CREDENTIAL_FORMATS = {"jwt_vc_json", "dc+sd-jwt"}


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64u_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _now() -> datetime:
    return datetime.now(UTC)


def _public_base() -> str:
    return settings.phase10_public_base_url.rstrip("/")


def _issuer_identifier(slug: str) -> str:
    return f"{_public_base()}/oid4vci/{slug}"


def _verifier_response_uri(slug: str) -> str:
    return f"{_public_base()}/oid4vp/{slug}/response"


def _public_jwk(private_key: ec.EllipticCurvePrivateKey) -> dict[str, Any]:
    numbers = private_key.public_key().public_numbers()
    size = 32
    x = _b64u(numbers.x.to_bytes(size, "big"))
    y = _b64u(numbers.y.to_bytes(size, "big"))
    thumbprint_input = _canonical(
        {"crv": "P-256", "kty": "EC", "x": x, "y": y}
    )
    kid = _b64u(hashlib.sha256(thumbprint_input.encode()).digest())
    return {
        "kty": "EC",
        "crv": "P-256",
        "x": x,
        "y": y,
        "use": "sig",
        "alg": "ES256",
        "kid": kid,
    }


def _generate_signing_material() -> tuple[str, dict[str, Any]]:
    private_key = ec.generate_private_key(ec.SECP256R1())
    pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("ascii")
    return pem, _public_jwk(private_key)


def _jwk_key(jwk_value: dict[str, Any]) -> Any:
    return jwt.algorithms.ECAlgorithm.from_jwk(
        json.dumps(jwk_value, separators=(",", ":"))
    )


async def create_issuer_profile(
    session: AsyncSession,
    user_id: str,
    payload: IssuerProfileCreateRequest,
) -> CredentialIssuerProfile:
    slug = normalized_slug(payload.slug)

    if not slug:
        raise ValueError("Issuer slug is invalid.")

    private_pem, public_jwk = _generate_signing_material()
    record = CredentialIssuerProfile(
        organization_id=payload.organization_id,
        slug=slug,
        issuer_identifier=_issuer_identifier(slug),
        display_name=payload.display_name.strip(),
        approval_status="pending",
        signing_alg="ES256",
        public_jwk=public_jwk,
        encrypted_private_key="",
        created_by_user_id=user_id,
    )
    session.add(record)
    await session.flush()
    record.encrypted_private_key = encrypt_text(
        private_pem,
        aad=f"openid4vci-issuer-key:{record.organization_id}:{record.id}",
    )
    await session.commit()
    await session.refresh(record)
    return record


async def approve_issuer_profile(
    session: AsyncSession,
    record: CredentialIssuerProfile,
    approver_user_id: str,
    approved: bool,
) -> CredentialIssuerProfile:
    record.approval_status = "approved" if approved else "rejected"
    record.approved_by_user_id = approver_user_id
    await session.commit()
    await session.refresh(record)
    return record


async def upsert_credential_configuration(
    session: AsyncSession,
    issuer: CredentialIssuerProfile,
    payload: CredentialConfigurationRequest,
) -> CredentialConfiguration:
    if payload.credential_format not in SUPPORTED_CREDENTIAL_FORMATS:
        raise ValueError("Unsupported credential format.")

    if payload.credential_format == "dc+sd-jwt" and not payload.vct:
        raise ValueError("dc+sd-jwt configurations require a vct value.")

    record = await session.scalar(
        select(CredentialConfiguration).where(
            CredentialConfiguration.issuer_profile_id == issuer.id,
            CredentialConfiguration.configuration_id == payload.configuration_id,
        )
    )

    values = {
        "credential_format": payload.credential_format,
        "credential_type": payload.credential_type,
        "vct": payload.vct,
        "scope": payload.scope,
        "claim_names": list(payload.claim_names),
        "selective_claims": list(payload.selective_claims),
        "display_json": dict(payload.display),
        "require_holder_binding": payload.require_holder_binding,
        "active": payload.active,
    }

    if record is None:
        record = CredentialConfiguration(
            issuer_profile_id=issuer.id,
            configuration_id=payload.configuration_id,
            **values,
        )
        session.add(record)
    else:
        for key, value in values.items():
            setattr(record, key, value)

    await session.commit()
    await session.refresh(record)
    return record


async def register_wallet_client(
    session: AsyncSession,
    payload: WalletClientRegistrationRequest,
) -> CredentialWalletClient:
    record = await session.scalar(
        select(CredentialWalletClient).where(
            CredentialWalletClient.client_id == payload.client_id
        )
    )
    values = {
        "display_name": payload.display_name,
        "redirect_uris": [str(item) for item in payload.redirect_uris],
        "approved": True,
        "metadata_json": dict(payload.metadata),
    }

    if record is None:
        record = CredentialWalletClient(
            client_id=payload.client_id,
            **values,
        )
        session.add(record)
    else:
        for key, value in values.items():
            setattr(record, key, value)

    await session.commit()
    await session.refresh(record)
    return record


def issuer_metadata(
    issuer: CredentialIssuerProfile,
    configurations: list[CredentialConfiguration],
) -> dict[str, Any]:
    supported: dict[str, Any] = {}

    for config in configurations:
        if not config.active:
            continue

        common = {
            "format": config.credential_format,
            "cryptographic_binding_methods_supported": (
                ["jwk"] if config.require_holder_binding else []
            ),
            "credential_signing_alg_values_supported": ["ES256"],
            "proof_types_supported": (
                {
                    "jwt": {
                        "proof_signing_alg_values_supported": ["ES256"],
                    }
                }
                if config.require_holder_binding
                else {}
            ),
            "credential_metadata": {
                "display": [config.display_json] if config.display_json else [],
                "claims": [
                    {
                        "path": (
                            ["credentialSubject", claim]
                            if config.credential_format == "jwt_vc_json"
                            else [claim]
                        )
                    }
                    for claim in config.claim_names
                ],
            },
        }

        if config.scope:
            common["scope"] = config.scope

        if config.credential_format == "jwt_vc_json":
            common["credential_definition"] = {
                "type": ["VerifiableCredential", config.credential_type]
            }
        else:
            common["vct"] = config.vct

        supported[config.configuration_id] = common

    return {
        "credential_issuer": issuer.issuer_identifier,
        "authorization_servers": [issuer.issuer_identifier],
        "credential_endpoint": f"{issuer.issuer_identifier}/credential",
        "nonce_endpoint": f"{issuer.issuer_identifier}/nonce",
        "credential_configurations_supported": supported,
    }


def authorization_server_metadata(
    issuer: CredentialIssuerProfile,
) -> dict[str, Any]:
    return {
        "issuer": issuer.issuer_identifier,
        "authorization_endpoint": f"{issuer.issuer_identifier}/authorize",
        "token_endpoint": f"{issuer.issuer_identifier}/token",
        "grant_types_supported": ["authorization_code", PRE_AUTH_GRANT],
        "response_types_supported": ["code"],
        "token_endpoint_auth_methods_supported": ["none"],
        "code_challenge_methods_supported": ["S256"],
        "pre-authorized_grant_anonymous_access_supported": True,
    }


async def create_credential_offer(
    session: AsyncSession,
    issuer: CredentialIssuerProfile,
    user_id: str,
    payload: CredentialOfferRequest,
) -> tuple[CredentialIssuanceOffer, dict[str, Any], str | None]:
    if issuer.approval_status != "approved":
        raise ValueError("Credential issuer is not approved.")

    config = await session.scalar(
        select(CredentialConfiguration).where(
            CredentialConfiguration.issuer_profile_id == issuer.id,
            CredentialConfiguration.configuration_id == payload.configuration_id,
            CredentialConfiguration.active.is_(True),
        )
    )

    if config is None:
        raise ValueError("Credential configuration is unavailable.")

    pre_authorized_code = secrets.token_urlsafe(32)
    tx_code = f"{secrets.randbelow(1_000_000):06d}" if payload.transaction_code_required else None
    expires_at = _now() + timedelta(seconds=payload.expires_in_seconds)

    offer = CredentialIssuanceOffer(
        issuer_profile_id=issuer.id,
        user_id=user_id,
        credential_configuration_id=config.id,
        pre_authorized_code_hash=_sha256_text(pre_authorized_code),
        transaction_code_hash=_sha256_text(tx_code) if tx_code else "",
        transaction_code_required=payload.transaction_code_required,
        expires_at=expires_at,
    )
    session.add(offer)
    await session.commit()
    await session.refresh(offer)

    grant: dict[str, Any] = {
        PRE_AUTH_GRANT: {
            "pre-authorized_code": pre_authorized_code,
        }
    }

    if tx_code:
        grant[PRE_AUTH_GRANT]["tx_code"] = {
            "input_mode": "numeric",
            "length": 6,
            "description": "Enter the one-time code shown by Global Career Architecture AI.",
        }

    credential_offer = {
        "credential_issuer": issuer.issuer_identifier,
        "credential_configuration_ids": [config.configuration_id],
        "grants": grant,
    }
    return offer, credential_offer, tx_code


async def get_credential_offer(
    session: AsyncSession,
    offer_id: str,
) -> tuple[CredentialIssuanceOffer, CredentialIssuerProfile, CredentialConfiguration]:
    offer = await session.get(CredentialIssuanceOffer, offer_id)

    if offer is None or offer.expires_at <= _now():
        raise LookupError("Credential offer not found or expired.")

    issuer = await session.get(CredentialIssuerProfile, offer.issuer_profile_id)
    config = await session.get(
        CredentialConfiguration,
        offer.credential_configuration_id,
    )

    if issuer is None or config is None:
        raise LookupError("Credential offer configuration is unavailable.")

    return offer, issuer, config


async def authorize_wallet(
    session: AsyncSession,
    issuer: CredentialIssuerProfile,
    user_id: str,
    *,
    client_id: str,
    redirect_uri: str,
    code_challenge: str,
    code_challenge_method: str,
    scope: str,
) -> str:
    if issuer.approval_status != "approved":
        raise ValueError("Credential issuer is not approved.")

    client = await session.scalar(
        select(CredentialWalletClient).where(
            CredentialWalletClient.client_id == client_id,
            CredentialWalletClient.approved.is_(True),
        )
    )

    if client is None or redirect_uri not in client.redirect_uris:
        raise ValueError("Wallet client or redirect URI is not approved.")

    if code_challenge_method != "S256" or not code_challenge:
        raise ValueError("PKCE S256 is required.")

    config = await session.scalar(
        select(CredentialConfiguration).where(
            CredentialConfiguration.issuer_profile_id == issuer.id,
            CredentialConfiguration.scope == scope,
            CredentialConfiguration.active.is_(True),
        )
    )

    if config is None:
        raise ValueError("Requested credential scope is unavailable.")

    code = secrets.token_urlsafe(32)
    record = CredentialAuthorizationCode(
        issuer_profile_id=issuer.id,
        user_id=user_id,
        client_id=client_id,
        credential_configuration_id=config.id,
        code_hash=_sha256_text(code),
        code_challenge=code_challenge,
        redirect_uri=redirect_uri,
        expires_at=_now() + timedelta(minutes=5),
    )
    session.add(record)
    await session.commit()
    return code


async def _new_access_token(
    session: AsyncSession,
    *,
    issuer_profile_id: str,
    user_id: str,
    credential_configuration_id: str,
) -> tuple[str, CredentialAccessToken]:
    raw = secrets.token_urlsafe(40)
    record = CredentialAccessToken(
        issuer_profile_id=issuer_profile_id,
        user_id=user_id,
        credential_configuration_id=credential_configuration_id,
        token_hash=_sha256_text(raw),
        expires_at=_now() + timedelta(
            seconds=settings.phase10_access_token_seconds
        ),
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return raw, record


async def redeem_pre_authorized_code(
    session: AsyncSession,
    issuer: CredentialIssuerProfile,
    pre_authorized_code: str,
    tx_code: str,
) -> tuple[str, CredentialAccessToken]:
    offer = await session.scalar(
        select(CredentialIssuanceOffer).where(
            CredentialIssuanceOffer.issuer_profile_id == issuer.id,
            CredentialIssuanceOffer.pre_authorized_code_hash
            == _sha256_text(pre_authorized_code),
        )
    )

    if (
        offer is None
        or offer.redeemed_at is not None
        or offer.expires_at <= _now()
    ):
        raise ValueError("Invalid or expired pre-authorized code.")

    if offer.transaction_code_required:
        if not tx_code or not secrets.compare_digest(
            offer.transaction_code_hash,
            _sha256_text(tx_code),
        ):
            raise ValueError("Invalid transaction code.")

    offer.redeemed_at = _now()
    token, record = await _new_access_token(
        session,
        issuer_profile_id=offer.issuer_profile_id,
        user_id=offer.user_id,
        credential_configuration_id=offer.credential_configuration_id,
    )
    return token, record


async def redeem_authorization_code(
    session: AsyncSession,
    issuer: CredentialIssuerProfile,
    *,
    code: str,
    client_id: str,
    redirect_uri: str,
    code_verifier: str,
) -> tuple[str, CredentialAccessToken]:
    record = await session.scalar(
        select(CredentialAuthorizationCode).where(
            CredentialAuthorizationCode.issuer_profile_id == issuer.id,
            CredentialAuthorizationCode.code_hash == _sha256_text(code),
        )
    )

    if (
        record is None
        or record.redeemed_at is not None
        or record.expires_at <= _now()
    ):
        raise ValueError("Invalid or expired authorization code.")

    if record.client_id != client_id or record.redirect_uri != redirect_uri:
        raise ValueError("Authorization code client binding failed.")

    challenge = _b64u(hashlib.sha256(code_verifier.encode()).digest())

    if not secrets.compare_digest(challenge, record.code_challenge):
        raise ValueError("PKCE verification failed.")

    record.redeemed_at = _now()
    token, token_record = await _new_access_token(
        session,
        issuer_profile_id=record.issuer_profile_id,
        user_id=record.user_id,
        credential_configuration_id=record.credential_configuration_id,
    )
    return token, token_record


async def access_token_record(
    session: AsyncSession,
    issuer: CredentialIssuerProfile,
    raw_token: str,
) -> CredentialAccessToken:
    record = await session.scalar(
        select(CredentialAccessToken).where(
            CredentialAccessToken.issuer_profile_id == issuer.id,
            CredentialAccessToken.token_hash == _sha256_text(raw_token),
        )
    )

    if (
        record is None
        or record.revoked_at is not None
        or record.expires_at <= _now()
    ):
        raise ValueError("Invalid or expired access token.")

    return record


async def issue_nonce(
    session: AsyncSession,
    token: CredentialAccessToken,
) -> str:
    raw = secrets.token_urlsafe(24)
    token.nonce_hash = _sha256_text(raw)
    await session.commit()
    return raw


def verify_holder_proof(
    issuer: CredentialIssuerProfile,
    token: CredentialAccessToken,
    proof_jwt: str,
) -> dict[str, Any]:
    if not token.nonce_hash:
        raise ValueError("Obtain a c_nonce from the nonce endpoint first.")

    header = jwt.get_unverified_header(proof_jwt)
    jwk_value = header.get("jwk")

    if not isinstance(jwk_value, dict):
        raise ValueError("Holder proof JWT must contain a public jwk header.")

    if header.get("typ") not in {
        "openid4vci-proof+jwt",
        "application/openid4vci-proof+jwt",
    }:
        raise ValueError("Holder proof JWT typ is invalid.")

    payload = jwt.decode(
        proof_jwt,
        _jwk_key(jwk_value),
        algorithms=["ES256"],
        audience=issuer.issuer_identifier,
        options={"require": ["iat", "nonce", "aud"]},
        leeway=30,
    )

    if not secrets.compare_digest(
        _sha256_text(str(payload["nonce"])),
        token.nonce_hash,
    ):
        raise ValueError("Holder proof nonce does not match.")

    issued_at = int(payload["iat"])
    now_ts = int(_now().timestamp())

    if abs(now_ts - issued_at) > 300:
        raise ValueError("Holder proof is outside the accepted time window.")

    return jwk_value


async def _credential_claims(
    session: AsyncSession,
    user_id: str,
    config: CredentialConfiguration,
) -> dict[str, Any]:
    profile = await load_profile(session, user_id)
    passport_record = await session.scalar(
        select(SkillsPassport).where(SkillsPassport.user_id == user_id)
    )
    verified_credentials = list(
        (
            await session.scalars(
                select(VerifiedCredential).where(
                    VerifiedCredential.user_id == user_id,
                    VerifiedCredential.verification_status == "verified",
                )
            )
        ).all()
    )

    requested = set(config.claim_names)
    claims: dict[str, Any] = {}

    if "full_name" in requested:
        claims["full_name"] = profile.full_name
    if "summary" in requested:
        claims["summary"] = profile.summary
    if "skills" in requested:
        claims["skills"] = list(profile.skills)
    if "abilities" in requested:
        claims["abilities"] = list(profile.abilities)
    if "core_values" in requested:
        claims["core_values"] = list(profile.core_values)
    if "education" in requested:
        claims["education"] = [
            item.model_dump(mode="json")
            for item in profile.education
        ]
    if "certifications" in requested:
        claims["certifications"] = list(profile.certifications)
    if "verified_credentials" in requested:
        claims["verified_credentials"] = [
            {
                "title": record.title,
                "issuer": record.issuer_name or record.issuer_url,
                "skills": list(record.skills),
                "credential_type": record.credential_type,
                "credential_hash": record.credential_hash,
            }
            for record in verified_credentials
        ]
    if "skills_passport" in requested:
        if passport_record is None:
            raise ValueError(
                "This credential configuration requires a generated skills passport."
            )
        claims["skills_passport"] = decrypt_skills_passport(passport_record)

    return {
        key: value
        for key, value in claims.items()
        if value not in ("", [], {}, None)
    }


def _issuer_private_pem(issuer: CredentialIssuerProfile) -> str:
    return decrypt_text(
        issuer.encrypted_private_key,
        aad=f"openid4vci-issuer-key:{issuer.organization_id}:{issuer.id}",
    )


async def _jwt_vc(
    session: AsyncSession,
    issuer: CredentialIssuerProfile,
    config: CredentialConfiguration,
    subject_id: str,
    claims: dict[str, Any],
    holder_jwk: dict[str, Any],
    jti: str,
    expires_at: datetime,
) -> str:
    now = _now()
    vc = {
        "@context": ["https://www.w3.org/ns/credentials/v2"],
        "type": ["VerifiableCredential", config.credential_type],
        "issuer": issuer.issuer_identifier,
        "validFrom": now.isoformat(),
        "validUntil": expires_at.isoformat(),
        "credentialSubject": {
            "id": subject_id,
            **claims,
        },
        "credentialStatus": {
            "id": f"{issuer.issuer_identifier}/status/{jti}",
            "type": "PlatformCredentialStatus2026",
        },
    }
    payload: dict[str, Any] = {
        "iss": issuer.issuer_identifier,
        "sub": subject_id,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": jti,
        "vc": vc,
    }

    if holder_jwk:
        payload["cnf"] = {"jwk": holder_jwk}

    from app.phase12_signing import sign_credential_jws

    return await sign_credential_jws(
        session,
        issuer,
        payload,
        headers={
            "kid": str(issuer.public_jwk.get("kid", "")),
            "typ": "JWT",
        },
    )


def _sd_disclosure(name: str, value: Any) -> tuple[str, str]:
    salt = _b64u(secrets.token_bytes(16))
    encoded = _b64u(
        json.dumps(
            [salt, name, value],
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    )
    digest = _b64u(hashlib.sha256(encoded.encode("ascii")).digest())
    return encoded, digest


async def _sd_jwt(
    session: AsyncSession,
    issuer: CredentialIssuerProfile,
    config: CredentialConfiguration,
    subject_id: str,
    claims: dict[str, Any],
    holder_jwk: dict[str, Any],
    jti: str,
    expires_at: datetime,
) -> str:
    now = _now()
    payload: dict[str, Any] = {
        "iss": issuer.issuer_identifier,
        "sub": subject_id,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": jti,
        "vct": config.vct,
        "_sd_alg": "sha-256",
    }

    if holder_jwk:
        payload["cnf"] = {"jwk": holder_jwk}

    selective = set(config.selective_claims)
    disclosures: list[str] = []
    digests: list[str] = []

    for name, value in claims.items():
        if name in selective:
            disclosure, digest = _sd_disclosure(name, value)
            disclosures.append(disclosure)
            digests.append(digest)
        else:
            payload[name] = value

    if digests:
        payload["_sd"] = sorted(digests)

    from app.phase12_signing import sign_credential_jws

    issuer_jwt = await sign_credential_jws(
        session,
        issuer,
        payload,
        headers={
            "kid": str(issuer.public_jwk.get("kid", "")),
            "typ": "dc+sd-jwt",
        },
    )
    return issuer_jwt + "~" + "~".join(disclosures) + "~"


async def issue_credential(
    session: AsyncSession,
    issuer: CredentialIssuerProfile,
    token: CredentialAccessToken,
    configuration_id: str,
    proof_jwt: str | None,
) -> tuple[str, IssuedCredentialRecord]:
    config = await session.get(
        CredentialConfiguration,
        token.credential_configuration_id,
    )

    if config is None or config.configuration_id != configuration_id:
        raise ValueError("Access token does not authorize this credential.")

    holder_jwk: dict[str, Any] = dict(token.holder_jwk or {})

    if config.require_holder_binding:
        if not proof_jwt:
            raise ValueError("A holder-binding proof JWT is required.")

        holder_jwk = verify_holder_proof(
            issuer,
            token,
            proof_jwt,
        )
        token.holder_jwk = holder_jwk
        # The nonce is one-use so replaying the same proof cannot mint another credential.
        token.nonce_hash = ""

    wallet = await session.scalar(
        select(CandidateWallet)
        .where(CandidateWallet.user_id == token.user_id)
        .order_by(CandidateWallet.created_at.asc())
        .limit(1)
    )
    subject_id = (
        wallet.holder_did
        if wallet is not None
        else f"urn:uuid:{token.user_id}"
    )
    claims = await _credential_claims(
        session,
        token.user_id,
        config,
    )
    jti = secrets.token_urlsafe(18)
    expires_at = _now() + timedelta(
        days=settings.phase10_credential_valid_days
    )

    if config.credential_format == "jwt_vc_json":
        credential = await _jwt_vc(
            session,
            issuer,
            config,
            subject_id,
            claims,
            holder_jwk,
            jti,
            expires_at,
        )
    elif config.credential_format == "dc+sd-jwt":
        credential = await _sd_jwt(
            session,
            issuer,
            config,
            subject_id,
            claims,
            holder_jwk,
            jti,
            expires_at,
        )
    else:
        raise ValueError("Credential format is not implemented.")

    digest = _sha256_text(credential)
    record = IssuedCredentialRecord(
        issuer_profile_id=issuer.id,
        user_id=token.user_id,
        credential_configuration_id=config.id,
        credential_format=config.credential_format,
        jti=jti,
        credential_hash=digest,
        encrypted_credential=encrypt_text(
            credential,
            aad=f"issued-credential:{issuer.id}:{jti}",
        ),
        subject_id=subject_id,
        status="active",
        expires_at=expires_at,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return credential, record


async def revoke_issued_credential(
    session: AsyncSession,
    record: IssuedCredentialRecord,
) -> None:
    record.status = "revoked"
    record.revoked_at = _now()
    await session.commit()


async def create_verifier_profile(
    session: AsyncSession,
    user_id: str,
    payload: VerifierProfileCreateRequest,
) -> CredentialVerifierProfile:
    slug = normalized_slug(payload.slug)

    if not slug:
        raise ValueError("Verifier slug is invalid.")

    response_uri = _verifier_response_uri(slug)
    record = CredentialVerifierProfile(
        organization_id=payload.organization_id,
        slug=slug,
        display_name=payload.display_name.strip(),
        client_id=f"redirect_uri:{response_uri}",
        response_uri=response_uri,
        approval_status="pending",
        vp_formats_supported={
            "jwt_vc_json": {"alg_values": ["ES256"]},
            "dc+sd-jwt": {
                "sd-jwt_alg_values": ["ES256"],
                "kb-jwt_alg_values": ["ES256"],
            },
        },
        created_by_user_id=user_id,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def approve_verifier_profile(
    session: AsyncSession,
    record: CredentialVerifierProfile,
    approver_user_id: str,
    approved: bool,
) -> CredentialVerifierProfile:
    record.approval_status = "approved" if approved else "rejected"
    record.approved_by_user_id = approver_user_id
    await session.commit()
    await session.refresh(record)
    return record


async def upsert_trust_anchor(
    session: AsyncSession,
    organization_id: str,
    payload: TrustAnchorRequest,
) -> CredentialTrustAnchor:
    if payload.public_jwk.get("kty") != "EC":
        raise ValueError("This reference verifier supports EC trust-anchor keys.")

    record = await session.scalar(
        select(CredentialTrustAnchor).where(
            CredentialTrustAnchor.organization_id == organization_id,
            CredentialTrustAnchor.issuer_identifier == payload.issuer_identifier,
        )
    )

    values = {
        "public_jwk": dict(payload.public_jwk),
        "allowed_formats": list(payload.allowed_formats),
        "active": True,
        "metadata_json": dict(payload.metadata),
    }

    if record is None:
        record = CredentialTrustAnchor(
            organization_id=organization_id,
            issuer_identifier=payload.issuer_identifier,
            **values,
        )
        session.add(record)
    else:
        for key, value in values.items():
            setattr(record, key, value)

    await session.commit()
    await session.refresh(record)
    return record


async def create_presentation_request(
    session: AsyncSession,
    verifier: CredentialVerifierProfile,
    user_id: str,
    dcql_query: dict[str, Any],
    expires_in_seconds: int,
) -> tuple[PresentationRequestRecord, str, dict[str, Any], str]:
    if verifier.approval_status != "approved":
        raise ValueError("Verifier profile is not approved.")

    if not isinstance(dcql_query.get("credentials"), list):
        raise ValueError("DCQL query must contain a credentials array.")

    nonce = secrets.token_urlsafe(24)
    state = secrets.token_urlsafe(24)
    record = PresentationRequestRecord(
        verifier_profile_id=verifier.id,
        created_by_user_id=user_id,
        nonce=nonce,
        state=state,
        state_hash=_sha256_text(state),
        dcql_query=dcql_query,
        expires_at=_now() + timedelta(seconds=expires_in_seconds),
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)

    request_uri = f"{_public_base()}/oid4vp/requests/{record.id}"
    request = {
        "client_id": verifier.client_id,
        "response_uri": verifier.response_uri,
        "response_type": "vp_token",
        "response_mode": "direct_post",
        "nonce": nonce,
        "state": state,
        "dcql_query": dcql_query,
        "client_metadata": {
            "client_name": verifier.display_name,
            "vp_formats_supported": verifier.vp_formats_supported,
        },
    }
    wallet_invocation = (
        "openid4vp://authorize?"
        + urlencode(
            {
                "client_id": verifier.client_id,
                "request_uri": request_uri,
            }
        )
    )
    return record, state, request, wallet_invocation


async def presentation_request_object(
    session: AsyncSession,
    request_id: str,
) -> tuple[PresentationRequestRecord, CredentialVerifierProfile, dict[str, Any]]:
    record = await session.get(PresentationRequestRecord, request_id)

    if record is None or record.expires_at <= _now():
        raise LookupError("Presentation request not found or expired.")

    verifier = await session.get(
        CredentialVerifierProfile,
        record.verifier_profile_id,
    )

    if verifier is None or verifier.approval_status != "approved":
        raise LookupError("Verifier is unavailable.")

    # The redirect_uri Client Identifier Prefix explicitly uses an unsigned request.
    request = {
        "client_id": verifier.client_id,
        "response_uri": verifier.response_uri,
        "response_type": "vp_token",
        "response_mode": "direct_post",
        "nonce": record.nonce,
        "state": record.state,
        "dcql_query": record.dcql_query,
        "client_metadata": {
            "client_name": verifier.display_name,
            "vp_formats_supported": verifier.vp_formats_supported,
        },
    }
    return record, verifier, request


async def _trusted_key(
    session: AsyncSession,
    organization_id: str,
    issuer_identifier: str,
    credential_format: str,
) -> dict[str, Any]:
    local_issuer = await session.scalar(
        select(CredentialIssuerProfile).where(
            CredentialIssuerProfile.issuer_identifier == issuer_identifier,
            CredentialIssuerProfile.approval_status == "approved",
        )
    )

    if local_issuer is not None:
        return dict(local_issuer.public_jwk)

    anchor = await session.scalar(
        select(CredentialTrustAnchor).where(
            CredentialTrustAnchor.organization_id == organization_id,
            CredentialTrustAnchor.issuer_identifier == issuer_identifier,
            CredentialTrustAnchor.active.is_(True),
        )
    )

    if anchor is None or credential_format not in anchor.allowed_formats:
        raise ValueError(f"Untrusted credential issuer: {issuer_identifier}")

    return dict(anchor.public_jwk)


async def _verify_local_status(
    session: AsyncSession,
    issuer_identifier: str,
    jti: str,
) -> None:
    issuer = await session.scalar(
        select(CredentialIssuerProfile).where(
            CredentialIssuerProfile.issuer_identifier == issuer_identifier
        )
    )

    if issuer is None:
        return

    record = await session.scalar(
        select(IssuedCredentialRecord).where(
            IssuedCredentialRecord.issuer_profile_id == issuer.id,
            IssuedCredentialRecord.jti == jti,
        )
    )

    if record is not None and record.status != "active":
        raise ValueError("Presented credential is not active.")


async def _verify_jwt_vc(
    session: AsyncSession,
    organization_id: str,
    encoded: str,
) -> tuple[str, str, dict[str, Any]]:
    unverified = jwt.decode(
        encoded,
        options={"verify_signature": False},
        algorithms=["ES256"],
    )
    issuer_identifier = str(unverified.get("iss", ""))

    if not issuer_identifier:
        raise ValueError("Credential issuer is missing.")

    jwk_value = await _trusted_key(
        session,
        organization_id,
        issuer_identifier,
        "jwt_vc_json",
    )
    payload = jwt.decode(
        encoded,
        _jwk_key(jwk_value),
        algorithms=["ES256"],
        issuer=issuer_identifier,
        options={"require": ["iss", "iat", "exp", "jti"]},
        leeway=30,
    )
    await _verify_local_status(
        session,
        issuer_identifier,
        str(payload["jti"]),
    )
    vc = payload.get("vc", {})
    subject = vc.get("credentialSubject", {}) if isinstance(vc, dict) else {}
    holder = str(subject.get("id") or payload.get("sub") or "")
    disclosed = (
        dict(subject)
        if isinstance(subject, dict)
        else {"credentialSubject": subject}
    )
    return issuer_identifier, holder, disclosed


def _parse_sd_jwt(value: str) -> tuple[str, list[str], str | None]:
    pieces = value.split("~")

    if len(pieces) < 2:
        raise ValueError("Invalid SD-JWT presentation.")

    issuer_jwt = pieces[0]
    remaining = [item for item in pieces[1:] if item]
    kb_jwt = None

    if remaining and remaining[-1].count(".") == 2:
        kb_jwt = remaining.pop()

    return issuer_jwt, remaining, kb_jwt


async def _verify_sd_jwt(
    session: AsyncSession,
    organization_id: str,
    encoded: str,
    verifier: CredentialVerifierProfile,
    request: PresentationRequestRecord,
) -> tuple[str, str, dict[str, Any]]:
    issuer_jwt, disclosures, kb_jwt = _parse_sd_jwt(encoded)
    unverified = jwt.decode(
        issuer_jwt,
        options={"verify_signature": False},
        algorithms=["ES256"],
    )
    issuer_identifier = str(unverified.get("iss", ""))

    if not issuer_identifier:
        raise ValueError("SD-JWT issuer is missing.")

    jwk_value = await _trusted_key(
        session,
        organization_id,
        issuer_identifier,
        "dc+sd-jwt",
    )
    payload = jwt.decode(
        issuer_jwt,
        _jwk_key(jwk_value),
        algorithms=["ES256"],
        issuer=issuer_identifier,
        options={"require": ["iss", "iat", "exp", "jti"]},
        leeway=30,
    )
    await _verify_local_status(
        session,
        issuer_identifier,
        str(payload["jti"]),
    )

    embedded = {
        str(value)
        for value in payload.get("_sd", [])
        if isinstance(value, str)
    }
    disclosed: dict[str, Any] = {}

    for disclosure in disclosures:
        digest = _b64u(
            hashlib.sha256(disclosure.encode("ascii")).digest()
        )

        if digest not in embedded:
            raise ValueError("SD-JWT disclosure is not committed by the issuer.")

        decoded = json.loads(_b64u_decode(disclosure))

        if (
            not isinstance(decoded, list)
            or len(decoded) != 3
            or not isinstance(decoded[1], str)
        ):
            raise ValueError("Unsupported SD-JWT disclosure structure.")

        disclosed[decoded[1]] = decoded[2]

    for key, value in payload.items():
        if key not in {
            "iss",
            "sub",
            "iat",
            "exp",
            "jti",
            "vct",
            "_sd_alg",
            "_sd",
            "cnf",
        }:
            disclosed[key] = value

    holder = str(payload.get("sub", ""))
    cnf = payload.get("cnf", {})
    holder_jwk = cnf.get("jwk") if isinstance(cnf, dict) else None

    if isinstance(holder_jwk, dict):
        if not kb_jwt:
            raise ValueError("Key-bound SD-JWT requires a KB-JWT.")

        presentation_without_kb = issuer_jwt + "~"

        if disclosures:
            presentation_without_kb = (
                issuer_jwt + "~" + "~".join(disclosures) + "~"
            )

        expected_hash = _b64u(
            hashlib.sha256(
                presentation_without_kb.encode("ascii")
            ).digest()
        )
        kb_payload = jwt.decode(
            kb_jwt,
            _jwk_key(holder_jwk),
            algorithms=["ES256"],
            audience=verifier.client_id,
            options={"require": ["aud", "nonce", "sd_hash", "iat"]},
            leeway=30,
        )

        if str(kb_payload["nonce"]) != request.nonce:
            raise ValueError("KB-JWT nonce does not match the request.")

        if not secrets.compare_digest(
            str(kb_payload["sd_hash"]),
            expected_hash,
        ):
            raise ValueError("KB-JWT sd_hash does not match the presentation.")

    return issuer_identifier, holder, disclosed


def _requested_query_ids(dcql_query: dict[str, Any]) -> set[str]:
    values = dcql_query.get("credentials", [])

    if not isinstance(values, list):
        return set()

    return {
        str(item.get("id"))
        for item in values
        if isinstance(item, dict) and item.get("id")
    }


async def verify_presentation_response(
    session: AsyncSession,
    verifier: CredentialVerifierProfile,
    request: PresentationRequestRecord,
    state: str,
    vp_token: str,
) -> PresentationSubmission:
    if request.status != "pending" or request.expires_at <= _now():
        raise ValueError("Presentation request is no longer active.")

    if not secrets.compare_digest(
        request.state_hash,
        _sha256_text(state),
    ):
        raise ValueError("Presentation state does not match.")

    try:
        token_object = json.loads(vp_token)
    except json.JSONDecodeError as exc:
        raise ValueError("vp_token must be a JSON object.") from exc

    if not isinstance(token_object, dict):
        raise ValueError("vp_token must be a JSON object.")

    requested_ids = _requested_query_ids(request.dcql_query)

    if not set(token_object).issubset(requested_ids):
        raise ValueError("vp_token includes an unrequested credential query id.")

    results: dict[str, Any] = {}
    issuers: list[str] = []
    holder = ""

    for query_id, presentations in token_object.items():
        if not isinstance(presentations, list) or not presentations:
            raise ValueError("Each vp_token entry must contain a presentation array.")

        verified_items = []

        for presentation in presentations:
            if not isinstance(presentation, str):
                raise ValueError("This reference verifier accepts string presentations.")

            if "~" in presentation:
                issuer_id, current_holder, claims = await _verify_sd_jwt(
                    session,
                    verifier.organization_id,
                    presentation,
                    verifier,
                    request,
                )
                fmt = "dc+sd-jwt"
            else:
                issuer_id, current_holder, claims = await _verify_jwt_vc(
                    session,
                    verifier.organization_id,
                    presentation,
                )
                fmt = "jwt_vc_json"

            issuers.append(issuer_id)
            holder = holder or current_holder
            verified_items.append(
                {
                    "format": fmt,
                    "issuer": issuer_id,
                    "claims": claims,
                }
            )

        results[query_id] = verified_items

    raw_hash = _sha256_text(vp_token)
    submission = PresentationSubmission(
        request_id=request.id,
        holder_identifier=holder,
        verification_status="verified",
        issuer_identifiers=sorted(set(issuers)),
        encrypted_result="",
        raw_hash=raw_hash,
    )
    session.add(submission)
    await session.flush()
    submission.encrypted_result = encrypt_text(
        _canonical(results),
        aad=f"openid4vp-result:{request.id}:{submission.id}",
    )
    request.status = "completed"
    request.completed_at = _now()
    await session.commit()
    await session.refresh(submission)
    return submission


def presentation_result(
    submission: PresentationSubmission,
) -> dict[str, Any]:
    raw = decrypt_text(
        submission.encrypted_result,
        aad=f"openid4vp-result:{submission.request_id}:{submission.id}",
    )
    return json.loads(raw)


async def record_consent_receipt(
    session: AsyncSession,
    user_id: str,
    payload: ConsentReceiptRequest,
) -> ConsentReceipt:
    previous = await session.scalar(
        select(ConsentReceipt)
        .where(
            ConsentReceipt.user_id == user_id,
            ConsentReceipt.purpose == payload.purpose,
        )
        .order_by(ConsentReceipt.occurred_at.desc())
        .limit(1)
    )
    previous_hash = previous.receipt_hash if previous else ""
    occurred_at = _now()
    canonical = {
        "user_id": user_id,
        "organization_id": payload.organization_id,
        "purpose": payload.purpose,
        "action": payload.action,
        "policy_version": payload.policy_version,
        "lawful_basis": payload.lawful_basis,
        "processing_purposes": sorted(payload.processing_purposes),
        "data_categories": sorted(payload.data_categories),
        "previous_receipt_hash": previous_hash,
        "occurred_at": occurred_at.isoformat(),
    }
    receipt_hash = _sha256_text(_canonical(canonical))
    record = ConsentReceipt(
        user_id=user_id,
        organization_id=payload.organization_id,
        purpose=payload.purpose,
        action=payload.action,
        policy_version=payload.policy_version,
        lawful_basis=payload.lawful_basis,
        processing_purposes=list(payload.processing_purposes),
        data_categories=list(payload.data_categories),
        receipt_hash=receipt_hash,
        previous_receipt_hash=previous_hash,
        occurred_at=occurred_at,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


DEFAULT_CLASSIFICATION_RULES = [
    ("email", r"(^|_)email($|_)", "contact", "confidential"),
    ("phone", r"(^|_)phone($|_)", "contact", "confidential"),
    ("password", r"password|secret|private_key|access_token|token_hash", "security_secret", "restricted"),
    ("credential", r"credential|wallet|holder_did|issuer", "credential", "confidential"),
    ("profile", r"profile|resume|skills|education|experience", "career_profile", "confidential"),
    ("auth", r"mfa|oidc|password_hash", "authentication", "restricted"),
    ("location", r"location|address|region", "location", "confidential"),
    ("financial", r"salary|wage|compensation", "financial", "confidential"),
    ("audit", r"audit|event|incident|evidence", "audit", "internal"),
]


async def upsert_classification_rule(
    session: AsyncSession,
    organization_id: str,
    payload: ClassificationRuleRequest,
) -> DataClassificationRule:
    try:
        re.compile(payload.field_pattern)
    except re.error as exc:
        raise ValueError("Classification rule contains an invalid regular expression.") from exc

    record = await session.scalar(
        select(DataClassificationRule).where(
            DataClassificationRule.organization_id == organization_id,
            DataClassificationRule.rule_key == payload.rule_key,
        )
    )

    values = {
        "field_pattern": payload.field_pattern,
        "classification": payload.classification,
        "sensitivity": payload.sensitivity,
        "enabled": payload.enabled,
    }

    if record is None:
        record = DataClassificationRule(
            organization_id=organization_id,
            rule_key=payload.rule_key,
            **values,
        )
        session.add(record)
    else:
        for key, value in values.items():
            setattr(record, key, value)

    await session.commit()
    await session.refresh(record)
    return record


async def run_data_discovery(
    session: AsyncSession,
    organization_id: str,
) -> DataDiscoveryScan:
    custom = list(
        (
            await session.scalars(
                select(DataClassificationRule).where(
                    DataClassificationRule.organization_id == organization_id,
                    DataClassificationRule.enabled.is_(True),
                )
            )
        ).all()
    )
    rules = [
        (
            item.rule_key,
            re.compile(item.field_pattern, re.IGNORECASE),
            item.classification,
            item.sensitivity,
        )
        for item in custom
    ]

    for key, pattern, classification, sensitivity in DEFAULT_CLASSIFICATION_RULES:
        rules.append(
            (
                key,
                re.compile(pattern, re.IGNORECASE),
                classification,
                sensitivity,
            )
        )

    scan = DataDiscoveryScan(
        organization_id=organization_id,
        status="running",
    )
    session.add(scan)
    await session.flush()
    count = 0

    for table in sorted(Base.metadata.tables.values(), key=lambda item: item.name):
        for column in table.columns:
            field_key = f"{table.name}.{column.name}"
            matches = []

            for rule_key, pattern, classification, sensitivity in rules:
                if pattern.search(field_key):
                    matches.append((rule_key, classification, sensitivity))

            if not matches:
                continue

            # Restricted wins over confidential, internal, public.
            order = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}
            matches.sort(key=lambda item: order.get(item[2], 0), reverse=True)
            rule_key, classification, sensitivity = matches[0]
            session.add(
                DataDiscoveryFinding(
                    scan_id=scan.id,
                    table_name=table.name,
                    field_name=column.name,
                    classification=classification,
                    sensitivity=sensitivity,
                    confidence=1.0,
                    evidence=f"metadata-rule:{rule_key}",
                )
            )
            count += 1

    scan.status = "completed"
    scan.finding_count = count
    scan.completed_at = _now()
    await session.commit()
    await session.refresh(scan)
    return scan


async def discovery_findings(
    session: AsyncSession,
    scan_id: str,
) -> list[DataDiscoveryFinding]:
    return list(
        (
            await session.scalars(
                select(DataDiscoveryFinding)
                .where(DataDiscoveryFinding.scan_id == scan_id)
                .order_by(
                    DataDiscoveryFinding.table_name,
                    DataDiscoveryFinding.field_name,
                )
            )
        ).all()
    )


async def _user_organization_ids(
    session: AsyncSession,
    user_id: str,
) -> list[str]:
    return list(
        (
            await session.scalars(
                select(Membership.organization_id).where(
                    Membership.user_id == user_id
                )
            )
        ).all()
    )


async def _legal_hold_for_user(
    session: AsyncSession,
    user_id: str,
) -> bool:
    organization_ids = await _user_organization_ids(session, user_id)

    if not organization_ids:
        return False

    count = int(
        await session.scalar(
            select(func.count())
            .select_from(RetentionPolicy)
            .where(
                RetentionPolicy.organization_id.in_(organization_ids),
                RetentionPolicy.legal_hold.is_(True),
                RetentionPolicy.enabled.is_(True),
            )
        )
        or 0
    )
    return count > 0


async def plan_deletion(
    session: AsyncSession,
    user_id: str,
    dsar_id: str | None,
    dry_run: bool,
) -> DeletionWorkflow:
    if dsar_id:
        dsar = await session.get(DataSubjectRequest, dsar_id)

        if (
            dsar is None
            or dsar.user_id != user_id
            or dsar.request_type != "erasure"
            or not dsar.identity_verified
        ):
            raise ValueError(
                "Deletion orchestration requires an identity-verified erasure request."
            )

    legal_hold = await _legal_hold_for_user(session, user_id)
    count_specs = [
        ("candidate_profile", CandidateProfileRecord, CandidateProfileRecord.user_id),
        ("resumes", ResumeDocument, ResumeDocument.user_id),
        ("applications", Application, Application.user_id),
        ("verified_credentials", VerifiedCredential, VerifiedCredential.user_id),
        ("wallets", CandidateWallet, CandidateWallet.user_id),
        ("skills_passport", SkillsPassport, SkillsPassport.user_id),
        ("job_recommendations", JobRecommendation, JobRecommendation.user_id),
        ("issued_credentials", IssuedCredentialRecord, IssuedCredentialRecord.user_id),
        ("issuance_offers", CredentialIssuanceOffer, CredentialIssuanceOffer.user_id),
        ("authorization_codes", CredentialAuthorizationCode, CredentialAuthorizationCode.user_id),
        ("access_tokens", CredentialAccessToken, CredentialAccessToken.user_id),
        ("consent_receipts", ConsentReceipt, ConsentReceipt.user_id),
    ]
    steps = []

    for label, model, column in count_specs:
        count = int(
            await session.scalar(
                select(func.count()).select_from(model).where(column == user_id)
            )
            or 0
        )
        steps.append(
            {
                "resource": label,
                "records": count,
                "action": "delete",
            }
        )

    steps.append(
        {
            "resource": "user_account",
            "records": 1,
            "action": "pseudonymize_and_disable",
        }
    )

    record = DeletionWorkflow(
        user_id=user_id,
        dsar_id=dsar_id,
        status="blocked" if legal_hold else "planned",
        dry_run=dry_run,
        legal_hold_blocked=legal_hold,
        steps_json=steps,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def execute_deletion(
    session: AsyncSession,
    workflow: DeletionWorkflow,
) -> DeletionWorkflow:
    if workflow.legal_hold_blocked:
        raise ValueError("Deletion is blocked by an active legal hold.")

    if workflow.dry_run:
        raise ValueError("Dry-run deletion plans cannot be executed.")

    if workflow.status not in {"planned", "failed"}:
        raise ValueError("Deletion workflow is not executable.")

    user_id = workflow.user_id
    workflow.status = "running"
    await session.flush()

    delete_specs = [
        (ResumeDocument, ResumeDocument.user_id),
        (Application, Application.user_id),
        (VerifiedCredential, VerifiedCredential.user_id),
        (CandidateWallet, CandidateWallet.user_id),
        (SkillsPassport, SkillsPassport.user_id),
        (JobRecommendation, JobRecommendation.user_id),
        (IssuedCredentialRecord, IssuedCredentialRecord.user_id),
        (CredentialIssuanceOffer, CredentialIssuanceOffer.user_id),
        (CredentialAuthorizationCode, CredentialAuthorizationCode.user_id),
        (CredentialAccessToken, CredentialAccessToken.user_id),
        (ConsentReceipt, ConsentReceipt.user_id),
        (CandidateProfileRecord, CandidateProfileRecord.user_id),
    ]

    for model, column in delete_specs:
        await session.execute(delete(model).where(column == user_id))

    user = await session.get(User, user_id)

    if user is not None:
        user.email = f"deleted-{user.id}@invalid.local"
        user.password_hash = ""
        user.oidc_subject = None
        user.mfa_enabled = False
        user.mfa_secret_encrypted = ""
        user.mfa_pending_secret_encrypted = ""
        user.is_active = False

    workflow.status = "completed"
    workflow.completed_at = _now()
    await session.commit()
    await session.refresh(workflow)
    return workflow


async def _member_user_ids(
    session: AsyncSession,
    organization_id: str,
) -> list[str]:
    return list(
        (
            await session.scalars(
                select(Membership.user_id).where(
                    Membership.organization_id == organization_id
                )
            )
        ).all()
    )


async def _fixed_metric_count(
    session: AsyncSession,
    organization_id: str,
    metric: str,
    target_day: date,
) -> int:
    user_ids = await _member_user_ids(session, organization_id)

    if not user_ids:
        return 0

    day_start = datetime.combine(target_day, datetime.min.time(), tzinfo=UTC)
    day_end = day_start + timedelta(days=1)

    if metric == "applications_total":
        model = Application
        column = Application.created_at
        user_column = Application.user_id
    elif metric == "job_recommendations_total":
        model = JobRecommendation
        column = JobRecommendation.evaluated_at
        user_column = JobRecommendation.user_id
    elif metric == "inbound_candidates_total":
        # Inbound candidates are already organization-scoped and not member-owned.
        return int(
            await session.scalar(
                select(func.count())
                .select_from(InboundCandidate)
                .where(
                    InboundCandidate.organization_id == organization_id,
                    InboundCandidate.created_at >= day_start,
                    InboundCandidate.created_at < day_end,
                )
            )
            or 0
        )
    else:
        raise ValueError("Unsupported privacy analytics metric.")

    return int(
        await session.scalar(
            select(func.count())
            .select_from(model)
            .where(
                user_column.in_(user_ids),
                column >= day_start,
                column < day_end,
            )
        )
        or 0
    )


def _laplace_noise(scale: float) -> float:
    # SystemRandom avoids deterministic PRNG state shared between analytics calls.
    u = secrets.SystemRandom().random() - 0.5

    if u == 0:
        return 0.0

    return -scale * math.copysign(math.log(1 - 2 * abs(u)), u)


async def privacy_preserving_release(
    session: AsyncSession,
    organization_id: str,
    request: PrivacyAnalyticsRequest,
) -> tuple[PrivacyAnalyticsRelease, float]:
    budget = await session.scalar(
        select(PrivacyAnalyticsBudget).where(
            PrivacyAnalyticsBudget.organization_id == organization_id,
            PrivacyAnalyticsBudget.day == request.day,
        )
    )

    if budget is None:
        budget = PrivacyAnalyticsBudget(
            organization_id=organization_id,
            day=request.day,
            epsilon_limit=settings.phase10_daily_epsilon_limit,
            epsilon_used=0.0,
        )
        session.add(budget)
        await session.flush()

    query_hash = _sha256_text(
        _canonical(
            {
                "organization_id": organization_id,
                "metric": request.metric,
                "day": request.day.isoformat(),
                "epsilon": request.epsilon,
                "minimum_group_size": request.minimum_group_size,
            }
        )
    )
    existing = await session.scalar(
        select(PrivacyAnalyticsRelease).where(
            PrivacyAnalyticsRelease.organization_id == organization_id,
            PrivacyAnalyticsRelease.query_hash == query_hash,
        )
    )

    if existing is not None:
        remaining = max(0.0, budget.epsilon_limit - budget.epsilon_used)
        return existing, remaining

    if budget.epsilon_used + request.epsilon > budget.epsilon_limit + 1e-9:
        raise ValueError("Daily differential-privacy budget would be exceeded.")

    true_count = await _fixed_metric_count(
        session,
        organization_id,
        request.metric,
        request.day,
    )
    suppressed = true_count < request.minimum_group_size
    noisy_value = None

    if not suppressed:
        noisy_value = max(
            0.0,
            round(
                true_count + _laplace_noise(1.0 / request.epsilon),
                2,
            ),
        )

    release = PrivacyAnalyticsRelease(
        organization_id=organization_id,
        metric=request.metric,
        day=request.day,
        epsilon=request.epsilon,
        minimum_group_size=request.minimum_group_size,
        source_count=true_count,
        noisy_value=noisy_value,
        suppressed=suppressed,
        query_hash=query_hash,
    )
    budget.epsilon_used += request.epsilon
    session.add(release)
    await session.commit()
    await session.refresh(release)
    remaining = max(0.0, budget.epsilon_limit - budget.epsilon_used)
    return release, remaining


def _audit_signing_key() -> ed25519.Ed25519PrivateKey | None:
    encoded = settings.phase10_audit_ed25519_private_key.get_secret_value().strip()

    if not encoded:
        return None

    raw = _b64u_decode(encoded)

    if len(raw) != 32:
        raise ValueError(
            "PHASE10_AUDIT_ED25519_PRIVATE_KEY must be a base64url-encoded 32-byte seed."
        )

    return ed25519.Ed25519PrivateKey.from_private_bytes(raw)


def audit_public_key_jwk() -> dict[str, Any] | None:
    private = _audit_signing_key()

    if private is None:
        return None

    public = private.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    return {
        "kty": "OKP",
        "crv": "Ed25519",
        "x": _b64u(public),
        "kid": settings.phase10_audit_signing_key_id,
        "use": "sig",
        "alg": "EdDSA",
    }


async def append_crypto_audit(
    session: AsyncSession,
    actor: str,
    request: AuditLedgerAppendRequest,
) -> CryptographicAuditEntry:
    statement = (
        select(CryptographicAuditEntry)
        .where(
            CryptographicAuditEntry.organization_id
            == request.organization_id
        )
        .order_by(CryptographicAuditEntry.sequence.desc())
        .limit(1)
        .with_for_update()
    )
    previous = await session.scalar(statement)
    sequence = 1 if previous is None else previous.sequence + 1
    previous_hash = "" if previous is None else previous.entry_hash
    payload_digest = _sha256_text(_canonical(request.payload))
    created_at = _now()
    envelope = {
        "organization_id": request.organization_id,
        "sequence": sequence,
        "event_type": request.event_type,
        "actor": actor,
        "subject_type": request.subject_type,
        "subject_id": request.subject_id,
        "payload_digest": payload_digest,
        "previous_hash": previous_hash,
        "created_at": created_at.isoformat(),
    }
    entry_hash = _sha256_text(_canonical(envelope))
    private = _audit_signing_key()
    signature = ""
    key_id = ""

    if private is not None:
        signature = _b64u(private.sign(entry_hash.encode("ascii")))
        key_id = settings.phase10_audit_signing_key_id

    record = CryptographicAuditEntry(
        organization_id=request.organization_id,
        sequence=sequence,
        event_type=request.event_type,
        actor=actor,
        subject_type=request.subject_type,
        subject_id=request.subject_id,
        payload_digest=payload_digest,
        previous_hash=previous_hash,
        entry_hash=entry_hash,
        signature=signature,
        signing_key_id=key_id,
        created_at=created_at,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def verify_crypto_audit_chain(
    session: AsyncSession,
    organization_id: str | None,
) -> dict[str, Any]:
    rows = list(
        (
            await session.scalars(
                select(CryptographicAuditEntry)
                .where(
                    CryptographicAuditEntry.organization_id
                    == organization_id
                )
                .order_by(CryptographicAuditEntry.sequence.asc())
            )
        ).all()
    )
    previous_hash = ""
    signed = 0
    unsigned = 0
    first_invalid = None
    public_jwk = audit_public_key_jwk()

    public_key = None

    if public_jwk is not None:
        public_key = ed25519.Ed25519PublicKey.from_public_bytes(
            _b64u_decode(public_jwk["x"])
        )

    for row in rows:
        envelope = {
            "organization_id": row.organization_id,
            "sequence": row.sequence,
            "event_type": row.event_type,
            "actor": row.actor,
            "subject_type": row.subject_type,
            "subject_id": row.subject_id,
            "payload_digest": row.payload_digest,
            "previous_hash": row.previous_hash,
            "created_at": row.created_at.isoformat(),
        }
        expected_hash = _sha256_text(_canonical(envelope))
        valid = (
            row.previous_hash == previous_hash
            and secrets.compare_digest(expected_hash, row.entry_hash)
        )

        if row.signature:
            signed += 1

            if public_key is None:
                valid = False
            else:
                try:
                    public_key.verify(
                        _b64u_decode(row.signature),
                        row.entry_hash.encode("ascii"),
                    )
                except Exception:
                    valid = False
        else:
            unsigned += 1

        if not valid and first_invalid is None:
            first_invalid = row.sequence
            break

        previous_hash = row.entry_hash

    return {
        "organization_id": organization_id,
        "valid": first_invalid is None,
        "entries_checked": len(rows) if first_invalid is None else first_invalid,
        "first_invalid_sequence": first_invalid,
        "signed_entries": signed,
        "unsigned_entries": unsigned,
    }

async def cleanup_expired_protocol_state(
    session: AsyncSession,
) -> dict[str, int]:
    """Minimize expired OAuth/OpenID transaction state while preserving audit records."""

    now = _now()
    offer_result = await session.execute(
        delete(CredentialIssuanceOffer).where(
            CredentialIssuanceOffer.expires_at < now - timedelta(days=1)
        )
    )
    code_result = await session.execute(
        delete(CredentialAuthorizationCode).where(
            CredentialAuthorizationCode.expires_at < now - timedelta(days=1)
        )
    )
    token_result = await session.execute(
        delete(CredentialAccessToken).where(
            CredentialAccessToken.expires_at < now - timedelta(days=1)
        )
    )

    pending_requests = list(
        (
            await session.scalars(
                select(PresentationRequestRecord).where(
                    PresentationRequestRecord.status == "pending",
                    PresentationRequestRecord.expires_at < now,
                )
            )
        ).all()
    )

    for request in pending_requests:
        request.status = "expired"

    await session.commit()

    return {
        "offers_deleted": int(offer_result.rowcount or 0),
        "authorization_codes_deleted": int(code_result.rowcount or 0),
        "access_tokens_deleted": int(token_result.rowcount or 0),
        "presentation_requests_expired": len(pending_requests),
    }

