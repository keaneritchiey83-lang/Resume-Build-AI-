from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crypto import encrypt_text
from app.models import VerifiedCredential


MAX_CREDENTIAL_BYTES = 512_000


@dataclass(slots=True)
class CredentialInspection:
    credential_format: str
    credential_id: str
    credential_type: str
    title: str
    issuer_name: str
    issuer_url: str
    subject_hash: str
    skills: list[str]
    issued_at: datetime | None
    expires_at: datetime | None
    status: str
    evidence: dict[str, Any]


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None

    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None

    if result.tzinfo is None:
        result = result.replace(tzinfo=UTC)

    return result


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]

    if isinstance(value, list):
        return [str(item) for item in value if item is not None]

    return []


def _issuer(payload: dict[str, Any]) -> tuple[str, str]:
    issuer = payload.get("issuer")

    if isinstance(issuer, str):
        return "", issuer

    if isinstance(issuer, dict):
        return (
            str(issuer.get("name") or issuer.get("legalName") or ""),
            str(issuer.get("id") or issuer.get("url") or ""),
        )

    return "", ""


def _subject(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("credentialSubject", {})

    if isinstance(value, list):
        return next((item for item in value if isinstance(item, dict)), {})

    return value if isinstance(value, dict) else {}


def _achievement(subject: dict[str, Any]) -> dict[str, Any]:
    value = subject.get("achievement", {})

    if isinstance(value, list):
        return next((item for item in value if isinstance(item, dict)), {})

    return value if isinstance(value, dict) else {}


def _skills(achievement: dict[str, Any]) -> list[str]:
    values: list[str] = []
    direct = achievement.get("skills")

    if isinstance(direct, list):
        for item in direct:
            if isinstance(item, str):
                values.append(item)
            elif isinstance(item, dict):
                values.append(
                    str(
                        item.get("name")
                        or item.get("targetName")
                        or item.get("targetCode")
                        or ""
                    )
                )

    alignment = achievement.get("alignment")

    if isinstance(alignment, list):
        for item in alignment:
            if not isinstance(item, dict):
                continue

            target_type = str(item.get("targetType", "")).lower()

            if "skill" in target_type or "competenc" in target_type:
                values.append(
                    str(
                        item.get("targetName")
                        or item.get("targetCode")
                        or item.get("targetUrl")
                        or ""
                    )
                )

    output: list[str] = []
    seen: set[str] = set()

    for value in values:
        clean = value.strip()
        key = clean.lower()

        if clean and key not in seen:
            seen.add(key)
            output.append(clean)

    return output


def inspect_credential(payload: dict[str, Any]) -> CredentialInspection:
    """Perform local structural validation without claiming proof verification."""

    encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()

    if len(encoded) > MAX_CREDENTIAL_BYTES:
        raise ValueError("Credential payload exceeds the 512 KB safety limit.")

    types = _strings(payload.get("type"))
    contexts = _strings(payload.get("@context"))
    subject = _subject(payload)
    achievement = _achievement(subject)

    credential_format = "w3c_verifiable_credential"

    if any("OpenBadge" in item or "AchievementCredential" in item for item in types):
        credential_format = "open_badges_3"
    elif any("europass" in item.lower() for item in contexts):
        credential_format = "europass_digital_credential"

    if "VerifiableCredential" not in types and credential_format == "w3c_verifiable_credential":
        raise ValueError(
            "Payload does not identify itself as a W3C Verifiable Credential."
        )

    credential_id = str(payload.get("id") or "").strip()
    issuer_name, issuer_url = _issuer(payload)
    title = str(
        achievement.get("name")
        or subject.get("name")
        or payload.get("name")
        or payload.get("title")
        or "Untitled credential"
    ).strip()
    credential_type = next(
        (
            item
            for item in reversed(types)
            if item not in {"VerifiableCredential", "OpenBadgeCredential"}
        ),
        types[-1] if types else "VerifiableCredential",
    )

    subject_identifier = str(
        subject.get("id")
        or subject.get("identifier")
        or subject.get("email")
        or ""
    )
    subject_hash = (
        hashlib.sha256(subject_identifier.encode()).hexdigest()
        if subject_identifier
        else ""
    )

    issued_at = _parse_datetime(
        payload.get("validFrom")
        or payload.get("issuanceDate")
        or payload.get("issued")
    )
    expires_at = _parse_datetime(
        payload.get("validUntil")
        or payload.get("expirationDate")
        or payload.get("expires")
    )

    now = datetime.now(UTC)
    status = "structurally_valid"

    if expires_at and expires_at <= now:
        status = "expired"

    proof_present = bool(payload.get("proof"))
    status_pointer_present = bool(payload.get("credentialStatus"))

    evidence = {
        "structural_validation": True,
        "proof_present": proof_present,
        "credential_status_pointer_present": status_pointer_present,
        "cryptographic_proof_checked": False,
        "credential_status_checked": False,
        "warning": (
            "Local validation checks structure and expiry only. "
            "Cryptographic proof and revocation/status require a configured verifier."
        ),
    }

    return CredentialInspection(
        credential_format=credential_format,
        credential_id=credential_id,
        credential_type=credential_type,
        title=title,
        issuer_name=issuer_name,
        issuer_url=issuer_url,
        subject_hash=subject_hash,
        skills=_skills(achievement),
        issued_at=issued_at,
        expires_at=expires_at,
        status=status,
        evidence=evidence,
    )


async def remote_verify(payload: dict[str, Any]) -> dict[str, Any]:
    """Call the single administrator-configured verifier endpoint.

    The endpoint is intentionally not supplied by the request, preventing the
    credential feature from becoming an arbitrary URL fetcher.
    """

    endpoint = settings.credential_remote_verifier_url.strip()

    if not endpoint:
        raise RuntimeError("CREDENTIAL_REMOTE_VERIFIER_URL is not configured.")

    if not endpoint.lower().startswith("https://"):
        raise RuntimeError("Credential verifier URL must use HTTPS.")

    headers = {"Accept": "application/json"}

    token = settings.credential_remote_verifier_token.get_secret_value()

    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(20, connect=5),
        follow_redirects=False,
    ) as client:
        response = await client.post(
            endpoint,
            headers=headers,
            json={"credential": payload},
        )
        response.raise_for_status()
        result = response.json()

    if not isinstance(result, dict):
        raise RuntimeError("Credential verifier returned an invalid response.")

    return result


def _remote_outcome(
    inspection: CredentialInspection,
    remote: dict[str, Any],
) -> tuple[str, str, str, dict[str, Any]]:
    verified = bool(
        remote.get("verified")
        or remote.get("valid")
        or remote.get("isValid")
    )
    revoked = bool(
        remote.get("revoked")
        or remote.get("isRevoked")
        or str(remote.get("status", "")).lower() == "revoked"
    )

    if revoked:
        status = "revoked"
        level = "cryptographic"
    elif verified and inspection.status != "expired":
        status = "verified"
        level = "cryptographic"
    elif inspection.status == "expired":
        status = "expired"
        level = "cryptographic" if verified else "structural"
    else:
        status = "verification_failed"
        level = "failed"

    method = str(
        remote.get("verificationMethod")
        or remote.get("method")
        or "configured_remote_verifier"
    )

    evidence = dict(inspection.evidence)
    evidence.update(
        {
            "cryptographic_proof_checked": verified or bool(remote.get("proofChecked")),
            "credential_status_checked": bool(
                remote.get("statusChecked")
                or "revoked" in remote
                or "isRevoked" in remote
            ),
            "remote_result": {
                key: value
                for key, value in remote.items()
                if key not in {"credential", "raw", "payload"}
            },
        }
    )

    return level, status, method, evidence


async def store_credential(
    session: AsyncSession,
    user_id: str,
    payload: dict[str, Any],
    use_remote_verifier: bool,
) -> VerifiedCredential:
    inspection = inspect_credential(payload)
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    credential_hash = hashlib.sha256(canonical.encode()).hexdigest()

    existing = await session.scalar(
        select(VerifiedCredential).where(
            VerifiedCredential.user_id == user_id,
            VerifiedCredential.credential_hash == credential_hash,
        )
    )

    if existing is not None:
        if use_remote_verifier:
            remote = await remote_verify(payload)
            level, status, method, evidence = _remote_outcome(inspection, remote)
            existing.verification_level = level
            existing.verification_status = status
            existing.verification_method = method
            existing.evidence_json = evidence
            existing.verified_at = (
                datetime.now(UTC)
                if level == "cryptographic"
                else None
            )
            await session.commit()
            await session.refresh(existing)

        return existing

    level = "structural"
    status = inspection.status
    method = "local_structural_validation"
    evidence = inspection.evidence

    if use_remote_verifier:
        remote = await remote_verify(payload)
        level, status, method, evidence = _remote_outcome(inspection, remote)

    record = VerifiedCredential(
        user_id=user_id,
        credential_hash=credential_hash,
        credential_id=inspection.credential_id,
        credential_format=inspection.credential_format,
        credential_type=inspection.credential_type,
        title=inspection.title,
        issuer_name=inspection.issuer_name,
        issuer_url=inspection.issuer_url,
        subject_hash=inspection.subject_hash,
        verification_level=level,
        verification_method=method,
        verification_status=status,
        skills=inspection.skills,
        issued_at=inspection.issued_at,
        expires_at=inspection.expires_at,
        encrypted_payload=encrypt_text(
            canonical,
            aad=f"credential:{user_id}:{credential_hash}",
        ),
        evidence_json=evidence,
        verified_at=datetime.now(UTC) if level == "cryptographic" else None,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record
