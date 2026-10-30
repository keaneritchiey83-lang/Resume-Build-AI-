from __future__ import annotations

import base64
import gzip
import hashlib
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import unquote

import cbor2
import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from webauthn import (
    base64url_to_bytes,
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import bytes_to_base64url
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.config import settings
from app.crypto import encrypt_text
from app.models import (
    BitstringStatusListRecord,
    CredentialIssuerProfile,
    CredentialStatusAssignment,
    CredentialVerifierProfile,
    DidTrustRegistryEntry,
    IssuedCredentialRecord,
    PasskeyCredential,
    User,
    WalletKeyAttestation,
    WebAuthnChallenge,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _challenge_expiry() -> datetime:
    return _now() + timedelta(seconds=settings.phase11_webauthn_challenge_seconds)


async def begin_passkey_registration(
    session: AsyncSession,
    user: User,
) -> tuple[str, dict]:
    credentials = (
        await session.scalars(
            select(PasskeyCredential).where(PasskeyCredential.user_id == user.id)
        )
    ).all()

    options = generate_registration_options(
        rp_id=settings.phase11_webauthn_rp_id,
        rp_name=settings.phase11_webauthn_rp_name,
        user_id=user.id.encode("utf-8"),
        user_name=user.email,
        user_display_name=user.email,
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(item.credential_id_b64))
            for item in credentials
        ],
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
        ),
    )

    challenge = WebAuthnChallenge(
        user_id=user.id,
        purpose="registration",
        challenge_b64=bytes_to_base64url(options.challenge),
        expires_at=_challenge_expiry(),
    )
    session.add(challenge)
    await session.commit()
    await session.refresh(challenge)
    return challenge.id, json.loads(options_to_json(options))


async def finish_passkey_registration(
    session: AsyncSession,
    user: User,
    *,
    challenge_id: str,
    credential: dict,
    nickname: str,
) -> PasskeyCredential:
    challenge = await session.get(WebAuthnChallenge, challenge_id)

    if (
        challenge is None
        or challenge.user_id != user.id
        or challenge.purpose != "registration"
        or challenge.consumed_at is not None
        or challenge.expires_at <= _now()
    ):
        raise HTTPException(status_code=400, detail="Registration challenge is invalid or expired.")

    try:
        verified = verify_registration_response(
            credential=credential,
            expected_challenge=base64url_to_bytes(challenge.challenge_b64),
            expected_rp_id=settings.phase11_webauthn_rp_id,
            expected_origin=settings.phase11_webauthn_origin_list,
            require_user_verification=True,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Passkey registration verification failed.") from exc

    credential_id = bytes_to_base64url(verified.credential_id)
    existing = await session.scalar(
        select(PasskeyCredential).where(
            PasskeyCredential.credential_id_b64 == credential_id
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Passkey is already registered.")

    record = PasskeyCredential(
        user_id=user.id,
        credential_id_b64=credential_id,
        public_key_b64=bytes_to_base64url(verified.credential_public_key),
        sign_count=verified.sign_count,
        device_type=str(verified.credential_device_type),
        backed_up=verified.credential_backed_up,
        transports=list(credential.get("response", {}).get("transports", [])),
        nickname=nickname.strip(),
    )
    challenge.consumed_at = _now()
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def begin_passkey_authentication(
    session: AsyncSession,
    user: User,
) -> tuple[str, dict]:
    credentials = (
        await session.scalars(
            select(PasskeyCredential).where(PasskeyCredential.user_id == user.id)
        )
    ).all()
    if not credentials:
        raise HTTPException(status_code=404, detail="No passkeys are registered for this account.")

    options = generate_authentication_options(
        rp_id=settings.phase11_webauthn_rp_id,
        allow_credentials=[
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(item.credential_id_b64))
            for item in credentials
        ],
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    challenge = WebAuthnChallenge(
        user_id=user.id,
        purpose="authentication",
        challenge_b64=bytes_to_base64url(options.challenge),
        expires_at=_challenge_expiry(),
    )
    session.add(challenge)
    await session.commit()
    await session.refresh(challenge)
    return challenge.id, json.loads(options_to_json(options))


async def finish_passkey_authentication(
    session: AsyncSession,
    *,
    challenge_id: str,
    credential: dict,
) -> User:
    challenge = await session.get(WebAuthnChallenge, challenge_id)

    if (
        challenge is None
        or challenge.purpose != "authentication"
        or challenge.consumed_at is not None
        or challenge.expires_at <= _now()
    ):
        raise HTTPException(status_code=400, detail="Authentication challenge is invalid or expired.")

    credential_id = str(credential.get("id", ""))
    passkey = await session.scalar(
        select(PasskeyCredential).where(
            PasskeyCredential.user_id == challenge.user_id,
            PasskeyCredential.credential_id_b64 == credential_id,
        )
    )
    if passkey is None:
        raise HTTPException(status_code=401, detail="Unknown passkey.")

    try:
        verified = verify_authentication_response(
            credential=credential,
            expected_challenge=base64url_to_bytes(challenge.challenge_b64),
            expected_rp_id=settings.phase11_webauthn_rp_id,
            expected_origin=settings.phase11_webauthn_origin_list,
            credential_public_key=base64url_to_bytes(passkey.public_key_b64),
            credential_current_sign_count=passkey.sign_count,
            require_user_verification=True,
        )
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Passkey authentication failed.") from exc

    passkey.sign_count = verified.new_sign_count
    passkey.last_used_at = _now()
    challenge.consumed_at = _now()
    user = await session.get(User, challenge.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User account is unavailable.")
    await session.commit()
    return user


def validate_did_document(did: str, document: dict) -> None:
    if document.get("id") != did:
        raise HTTPException(status_code=400, detail="DID document id must match the requested DID.")
    verification_methods = document.get("verificationMethod", [])
    if verification_methods is not None and not isinstance(verification_methods, list):
        raise HTTPException(status_code=400, detail="verificationMethod must be an array.")


def _did_web_url(did: str) -> tuple[str, str]:
    if not did.startswith("did:web:"):
        raise HTTPException(status_code=400, detail="Only did:web supports remote resolution in this deployment.")
    method_specific = did[len("did:web:") :]
    parts = method_specific.split(":")
    host = unquote(parts[0]).lower()
    if host not in settings.phase11_did_web_allowed_host_set:
        raise HTTPException(status_code=403, detail="did:web host is not allowlisted.")
    path = "/".join(unquote(part) for part in parts[1:])
    if path:
        return host, f"https://{host}/{path}/did.json"
    return host, f"https://{host}/.well-known/did.json"


async def resolve_did(
    session: AsyncSession,
    organization_id: str,
    did: str,
) -> tuple[dict, str, str]:
    entry = await session.scalar(
        select(DidTrustRegistryEntry).where(
            DidTrustRegistryEntry.organization_id == organization_id,
            DidTrustRegistryEntry.did == did,
        )
    )
    if entry is not None:
        validate_did_document(did, entry.did_document)
        return entry.did_document, "trust_registry", entry.trust_status

    _, url = _did_web_url(did)
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(10, connect=3),
        follow_redirects=False,
    ) as client:
        response = await client.get(url, headers={"Accept": "application/did+ld+json, application/json"})
        response.raise_for_status()
        if int(response.headers.get("content-length", "0") or 0) > 1_000_000:
            raise HTTPException(status_code=400, detail="DID document exceeds safety limit.")
        document = response.json()

    if not isinstance(document, dict):
        raise HTTPException(status_code=400, detail="DID document must be a JSON object.")
    validate_did_document(did, document)
    return document, "did:web", "untrusted_remote"


def _empty_bitstring(capacity_bits: int) -> bytearray:
    return bytearray(capacity_bits // 8)


def _decode_raw_bitstring(value: str, capacity_bits: int) -> bytearray:
    if not value:
        return _empty_bitstring(capacity_bits)
    data = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    if len(data) * 8 != capacity_bits:
        raise ValueError("Stored bitstring length does not match configured capacity.")
    return bytearray(data)


def _encode_raw_bitstring(value: bytearray) -> str:
    return base64.urlsafe_b64encode(bytes(value)).rstrip(b"=").decode("ascii")


def status_bit_get(value: bytearray, index: int) -> bool:
    byte_index = index // 8
    bit_index = index % 8
    return bool((value[byte_index] >> bit_index) & 1)


def status_bit_set(value: bytearray, index: int, state: bool) -> None:
    byte_index = index // 8
    bit_index = index % 8
    if state:
        value[byte_index] |= 1 << bit_index
    else:
        value[byte_index] &= ~(1 << bit_index)


def compressed_status_list(raw: bytearray) -> str:
    compressed = gzip.compress(bytes(raw), mtime=0)
    # W3C Bitstring Status List uses multibase base64url-no-pad; prefix 'u'.
    return "u" + base64.urlsafe_b64encode(compressed).rstrip(b"=").decode("ascii")


async def create_status_list(
    session: AsyncSession,
    issuer: CredentialIssuerProfile,
    purpose: str,
    capacity_bits: int,
) -> BitstringStatusListRecord:
    if capacity_bits % 8:
        raise HTTPException(status_code=400, detail="Status-list capacity must be divisible by 8.")
    existing = (
        await session.scalars(
            select(BitstringStatusListRecord).where(
                BitstringStatusListRecord.issuer_profile_id == issuer.id,
                BitstringStatusListRecord.purpose == purpose,
            )
        )
    ).all()
    sequence = max((item.sequence for item in existing), default=0) + 1
    status_url = (
        f"{settings.phase10_public_base_url.rstrip('/')}/v1/phase11/status-lists/"
        f"{issuer.slug}-{purpose}-{sequence}"
    )
    record = BitstringStatusListRecord(
        issuer_profile_id=issuer.id,
        purpose=purpose,
        sequence=sequence,
        capacity_bits=capacity_bits,
        bitstring_b64=_encode_raw_bitstring(_empty_bitstring(capacity_bits)),
        status_list_url=status_url,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def assign_status_slot(
    session: AsyncSession,
    credential: IssuedCredentialRecord,
    issuer: CredentialIssuerProfile,
    purpose: str,
) -> CredentialStatusAssignment:
    existing = await session.scalar(
        select(CredentialStatusAssignment).where(
            CredentialStatusAssignment.issued_credential_id == credential.id,
            CredentialStatusAssignment.purpose == purpose,
        )
    )
    if existing is not None:
        return existing

    status_list = await session.scalar(
        select(BitstringStatusListRecord)
        .where(
            BitstringStatusListRecord.issuer_profile_id == issuer.id,
            BitstringStatusListRecord.purpose == purpose,
            BitstringStatusListRecord.next_index < BitstringStatusListRecord.capacity_bits,
        )
        .order_by(BitstringStatusListRecord.sequence.asc())
        .limit(1)
    )
    if status_list is None:
        status_list = await create_status_list(session, issuer, purpose, 131072)

    index = status_list.next_index
    status_list.next_index += 1
    assignment = CredentialStatusAssignment(
        issued_credential_id=credential.id,
        status_list_id=status_list.id,
        purpose=purpose,
        status_index=index,
    )
    session.add(assignment)
    await session.commit()
    await session.refresh(assignment)
    return assignment


async def set_credential_status(
    session: AsyncSession,
    assignment: CredentialStatusAssignment,
    value: bool,
) -> None:
    record = await session.get(BitstringStatusListRecord, assignment.status_list_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Status list not found.")
    raw = _decode_raw_bitstring(record.bitstring_b64, record.capacity_bits)
    status_bit_set(raw, assignment.status_index, value)
    record.bitstring_b64 = _encode_raw_bitstring(raw)
    record.updated_at = _now()
    await session.commit()


def status_list_credential(
    record: BitstringStatusListRecord,
    issuer_identifier: str,
) -> dict:
    raw = _decode_raw_bitstring(record.bitstring_b64, record.capacity_bits)
    return {
        "@context": ["https://www.w3.org/ns/credentials/v2"],
        "id": record.status_list_url,
        "type": ["VerifiableCredential", "BitstringStatusListCredential"],
        "issuer": issuer_identifier,
        "validFrom": record.updated_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "credentialSubject": {
            "id": f"{record.status_list_url}#list",
            "type": "BitstringStatusList",
            "statusPurpose": record.purpose,
            "encodedList": compressed_status_list(raw),
        },
        "_security_notice": (
            "This endpoint returns the status-list credential data model. "
            "Production deployments must secure it with the same proof mechanism "
            "used by the associated credentials."
        ),
    }


def structural_mdoc_inspection(device_response_b64: str, expected_doc_type: str) -> dict:
    try:
        raw = base64.urlsafe_b64decode(device_response_b64 + "=" * (-len(device_response_b64) % 4))
        decoded = cbor2.loads(raw)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid CBOR mdoc DeviceResponse.") from exc

    doc_types: list[str] = []
    if isinstance(decoded, dict):
        documents = decoded.get("documents") or decoded.get("Documents") or []
        if isinstance(documents, list):
            for item in documents:
                if isinstance(item, dict):
                    doc_type = item.get("docType") or item.get("DocType")
                    if isinstance(doc_type, str):
                        doc_types.append(doc_type)

    if expected_doc_type and expected_doc_type not in doc_types:
        return {
            "verification_status": "failed_structural_check",
            "doc_types": doc_types,
            "reason": "Expected docType was not present.",
        }

    return {
        "verification_status": "manual_required",
        "doc_types": doc_types,
        "reason": (
            "CBOR structure was parsed, but ISO mdoc cryptographic/device-authentication "
            "verification requires the configured remote verifier or a certified mdoc stack."
        ),
    }


async def verify_mdoc(device_response_b64: str, expected_doc_type: str) -> dict:
    if not settings.phase11_mdoc_verifier_url:
        return structural_mdoc_inspection(device_response_b64, expected_doc_type)

    headers = {"Content-Type": "application/json"}
    token = settings.phase11_mdoc_verifier_token.get_secret_value()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(15, connect=5),
        follow_redirects=False,
    ) as client:
        response = await client.post(
            settings.phase11_mdoc_verifier_url,
            headers=headers,
            json={
                "device_response_b64": device_response_b64,
                "expected_doc_type": expected_doc_type,
            },
        )
        response.raise_for_status()
        result = response.json()

    if not isinstance(result, dict) or result.get("verification_status") not in {
        "verified", "failed"
    }:
        raise HTTPException(status_code=502, detail="Remote mdoc verifier returned an invalid result.")
    return result


def haip_assessment(
    issuer: CredentialIssuerProfile | None,
    verifier: CredentialVerifierProfile | None,
) -> dict:
    checks: list[dict] = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append({"check": name, "passed": passed, "detail": detail})

    if issuer is not None:
        add("issuer_approved", issuer.approval_status == "approved", "Issuer must be platform-approved.")
        add("authorization_code_supported", True, "Phase 10 implements authorization-code + PKCE.")
        add(
            "credential_format_profile",
            True,
            "Phase 11 can profile dc+sd-jwt and mso_mdoc; full ecosystem conformance still requires interoperability testing.",
        )
        add(
            "wallet_key_attestation",
            True,
            "Key-attestation metadata is supported; ecosystem trust/certificate policy remains deployment-specific.",
        )

    if verifier is not None:
        formats = verifier.vp_formats_supported or {}
        serialized = json.dumps(formats)
        add("verifier_approved", verifier.approval_status == "approved", "Verifier must be platform-approved.")
        add(
            "haip_format_support",
            ("mso_mdoc" in serialized) or ("dc+sd-jwt" in serialized),
            "HAIP requires at least one profiled credential format.",
        )
        add(
            "dcql",
            True,
            "Phase 10 presentation requests use DCQL.",
        )

    return {
        "profile": "OpenID4VC HAIP 1.0 Final",
        "conformance_claim": False,
        "checks": checks,
        "passed_static_checks": bool(checks) and all(item["passed"] for item in checks),
        "notice": (
            "This is a static readiness assessment, not OpenID certification or a claim "
            "of HAIP conformance. Run official conformance/interoperability tests."
        ),
    }


PQC_STANDARDS = ("FIPS 203 / ML-KEM", "FIPS 204 / ML-DSA", "FIPS 205 / SLH-DSA")


def quantum_risk_for_algorithm(algorithm: str) -> tuple[str, str]:
    value = algorithm.upper().replace("_", "-")
    if any(token in value for token in ("RSA", "ECDSA", "ECDH", "ED25519", "EDDSA")):
        return "high", "Plan migration/hybridization using NIST-approved PQC where the protocol ecosystem supports it."
    if any(token in value for token in ("AES-256", "SHA-384", "SHA-512")):
        return "lower", "Symmetric/hash primitive; maintain adequate key/hash sizes and track NIST guidance."
    if any(token in value for token in ("ML-KEM", "ML-DSA", "SLH-DSA")):
        return "pqc", "NIST post-quantum standard family."
    return "unknown", "Review cryptographic purpose and migration dependencies."
