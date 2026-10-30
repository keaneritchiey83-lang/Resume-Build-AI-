from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crypto import decrypt_text, encrypt_text
from app.models import (
    AuditEvent,
    InboundApplication,
    InboundAttachment,
    InboundCandidate,
    ProviderCredential,
    WebhookEvent,
)
from app.files import MAX_UPLOAD_BYTES, extract_resume_text


@dataclass(slots=True)
class VerifiedWebhook:
    provider: str
    event_id: str
    event_type: str
    payload: dict[str, Any]
    body_sha256: str


def _constant_time_equal(left: str, right: str) -> bool:
    return bool(left and right) and hmac.compare_digest(
        left.encode("utf-8"),
        right.encode("utf-8"),
    )


def verify_linkedin_signature(
    raw_body: bytes,
    supplied_signature: str,
    client_secret: str,
) -> bool:
    """Verify LinkedIn X-LI-Signature using the raw body."""

    if not client_secret:
        return False

    message = b"hmacsha256=" + raw_body
    expected = hmac.new(
        client_secret.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()

    supplied = supplied_signature.strip()

    # Current shared webhook docs show the header as the hex digest. Some
    # historical Apply Connect examples describe a prefixed comparison.
    if supplied.lower().startswith("hmacsha256="):
        supplied = supplied.split("=", 1)[1]

    return _constant_time_equal(expected.lower(), supplied.lower())


def linkedin_challenge_response(
    challenge_code: str,
    client_secret: str,
) -> str:
    return hmac.new(
        client_secret.encode("utf-8"),
        challenge_code.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_indeed_signature(
    raw_body: bytes,
    supplied_signature: str,
    apply_secret: str,
) -> bool:
    """Verify Indeed Apply X-Indeed-Signature over the unaltered body."""

    if not apply_secret:
        return False

    expected = base64.b64encode(
        hmac.new(
            apply_secret.encode("utf-8"),
            raw_body,
            hashlib.sha1,
        ).digest()
    ).decode("ascii")

    return _constant_time_equal(expected, supplied_signature.strip())


def _parse_rfc3339(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)

    return parsed.astimezone(UTC)


def verify_ziprecruiter_signature(
    raw_body: bytes,
    supplied_signature: str,
    timestamp: str,
    version: str,
    webhook_secret: str,
    *,
    now: datetime | None = None,
    replay_window_seconds: int | None = None,
) -> bool:
    """Verify ZipRecruiter v1 timestamp.body HMAC-SHA256 signature."""

    if not webhook_secret or not timestamp or not supplied_signature:
        return False

    version_token = version.split(";", 1)[0].strip().lower()

    if version_token != "v1":
        return False

    try:
        sent_at = _parse_rfc3339(timestamp)
    except ValueError:
        return False

    current = now or datetime.now(UTC)
    window = replay_window_seconds or settings.webhook_replay_window_seconds

    if abs((current - sent_at).total_seconds()) > window:
        return False

    message = timestamp.encode("ascii") + b"." + raw_body
    expected = base64.b64encode(
        hmac.new(
            webhook_secret.encode("ascii"),
            message,
            hashlib.sha256,
        ).digest()
    ).decode("ascii")

    return _constant_time_equal(expected, supplied_signature.strip())


async def provider_credentials(
    session: AsyncSession,
    organization_id: str,
    provider: str,
) -> dict[str, Any]:
    record = await session.scalar(
        select(ProviderCredential).where(
            ProviderCredential.organization_id == organization_id,
            ProviderCredential.provider == provider,
            ProviderCredential.enabled.is_(True),
        )
    )

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="Webhook integration is not enabled for this organization.",
        )

    try:
        value = json.loads(
            decrypt_text(
                record.encrypted_payload,
                aad=f"provider:{organization_id}:{provider}",
            )
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Provider credentials could not be decrypted.",
        ) from exc

    if not isinstance(value, dict):
        raise HTTPException(
            status_code=503,
            detail="Provider credential payload is invalid.",
        )

    return value


def linkedin_client_secret(
    credentials: dict[str, Any],
    application_id: str | None,
) -> str:
    if application_id:
        child_secrets = credentials.get("application_secrets", {})

        if isinstance(child_secrets, dict):
            child_secret = child_secrets.get(application_id)

            if isinstance(child_secret, str) and child_secret:
                return child_secret

        configured_application_id = str(
            credentials.get("application_id", "")
        )

        if configured_application_id == application_id:
            return str(credentials.get("client_secret", ""))

        raise HTTPException(
            status_code=401,
            detail="No secret is configured for the LinkedIn child application.",
        )

    return str(credentials.get("client_secret", ""))


def _json_payload(raw_body: bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Webhook body must be UTF-8 JSON.") from exc

    if not isinstance(value, dict):
        raise HTTPException(status_code=400, detail="Webhook payload must be an object.")

    return value


def _event_identity(
    provider: str,
    payload: dict[str, Any],
    body_sha256: str,
) -> tuple[str, str]:
    if provider == "linkedin":
        event_id = str(
            payload.get("notificationId")
            or payload.get("jobApplicationId")
            or body_sha256
        )
        event_type = str(payload.get("type") or "EXPORT_JOB_APPLICATION")
        return event_id, event_type

    if provider == "indeed":
        event_id = str(
            payload.get("id")
            or payload.get("indeedApplyId")
            or body_sha256
        )
        return event_id, "INDEED_APPLY_APPLICATION"

    if provider == "ziprecruiter":
        event_id = str(
            payload.get("zr_application_id")
            or payload.get("response_id")
            or body_sha256
        )
        event_type = (
            "ZIPRECRUITER_RDB"
            if payload.get("source") == "ZipRecruiter RDB"
            else "ZIPRECRUITER_APPLY"
        )
        return event_id, event_type

    raise HTTPException(status_code=404, detail="Unsupported webhook provider.")


async def verify_webhook(
    session: AsyncSession,
    organization_id: str,
    provider: str,
    raw_body: bytes,
    headers: dict[str, str],
) -> VerifiedWebhook:
    if len(raw_body) > settings.webhook_max_body_bytes:
        raise HTTPException(status_code=413, detail="Webhook body exceeds configured limit.")

    credentials = await provider_credentials(session, organization_id, provider)

    if provider == "linkedin":
        secret = linkedin_client_secret(
            credentials,
            headers.get("x-linkedin-application-id"),
        )
        signature = headers.get("x-li-signature", "")

        if not verify_linkedin_signature(raw_body, signature, secret):
            raise HTTPException(status_code=401, detail="LinkedIn signature mismatch.")

    elif provider == "indeed":
        signature = headers.get("x-indeed-signature", "")
        secret = str(
            credentials.get("indeed_apply_secret")
            or credentials.get("apply_secret")
            or ""
        )

        if not verify_indeed_signature(raw_body, signature, secret):
            raise HTTPException(status_code=401, detail="Indeed signature mismatch.")

    elif provider == "ziprecruiter":
        signature = headers.get("x-ziprecruiter-signature", "")
        timestamp = headers.get("x-ziprecruiter-signature-timestamp", "")
        version = headers.get("x-ziprecruiter-signature-version", "")
        secret = str(credentials.get("webhook_secret", ""))

        if not verify_ziprecruiter_signature(
            raw_body,
            signature,
            timestamp,
            version,
            secret,
        ):
            raise HTTPException(
                status_code=401,
                detail="ZipRecruiter signature or timestamp mismatch.",
            )

    else:
        raise HTTPException(status_code=404, detail="Unsupported webhook provider.")

    payload = _json_payload(raw_body)
    body_sha256 = hashlib.sha256(raw_body).hexdigest()
    event_id, event_type = _event_identity(provider, payload, body_sha256)

    return VerifiedWebhook(
        provider=provider,
        event_id=event_id,
        event_type=event_type,
        payload=payload,
        body_sha256=body_sha256,
    )


async def persist_verified_event(
    session: AsyncSession,
    organization_id: str,
    verified: VerifiedWebhook,
    raw_body: bytes,
) -> tuple[WebhookEvent, bool]:
    event_uuid = str(uuid.uuid4())
    now = datetime.now(UTC)
    event = WebhookEvent(
        id=event_uuid,
        organization_id=organization_id,
        provider=verified.provider,
        event_id=verified.event_id[:1000],
        event_type=verified.event_type[:200],
        body_sha256=verified.body_sha256,
        encrypted_payload=encrypt_text(
            raw_body.decode("utf-8"),
            aad=f"webhook:{organization_id}:{verified.provider}:{event_uuid}",
        ),
        status="received",
        attempts=0,
        retention_until=now + timedelta(days=settings.webhook_event_retention_days),
    )
    session.add(event)

    try:
        await session.commit()
        await session.refresh(event)
        return event, False
    except IntegrityError:
        await session.rollback()

    existing = await session.scalar(
        select(WebhookEvent).where(
            WebhookEvent.organization_id == organization_id,
            WebhookEvent.provider == verified.provider,
            WebhookEvent.event_id == verified.event_id[:1000],
        )
    )

    if existing is None:
        raise RuntimeError("Webhook event conflict could not be resolved.")

    if existing.body_sha256 != verified.body_sha256:
        session.add(
            AuditEvent(
                event="webhook.event_id_conflict",
                actor=f"provider:{verified.provider}",
                details={
                    "organization_id": organization_id,
                    "provider": verified.provider,
                    "event_id": verified.event_id[:1000],
                },
            )
        )
        await session.commit()
        raise HTTPException(
            status_code=409,
            detail="Webhook event ID was previously received with different content.",
        )

    return existing, True


def _text_answer(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()

    if isinstance(value, dict):
        direct = value.get("value")

        if isinstance(direct, str):
            return direct.strip()

    return ""


def _phone_answer(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()

    if isinstance(value, dict):
        country = str(value.get("countryCode", "")).strip()
        national = str(value.get("nationalNumber", "")).strip()
        extension = str(value.get("extension", "")).strip()
        result = f"+{country} {national}".strip() if country else national

        if extension:
            result += f" ext {extension}"

        return result.strip()

    return ""


def _email_hash(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


def _linked_in_normalized(payload: dict[str, Any]) -> dict[str, Any]:
    responses = payload.get("questionResponses", {})

    if not isinstance(responses, dict):
        responses = {}

    contact = responses.get("contactInformationQuestionResponses", {})

    if not isinstance(contact, dict):
        contact = {}

    first = _text_answer(contact.get("firstNameAnswer"))
    last = _text_answer(contact.get("lastNameAnswer"))
    email = _text_answer(contact.get("emailAnswer"))
    phone = _phone_answer(contact.get("cellphoneNumberQuestionAnswer"))

    skills = []

    for skill in payload.get("applicantSkills") or []:
        if isinstance(skill, dict) and isinstance(skill.get("skillName"), str):
            skills.append(skill["skillName"])

    safe_responses = {
        key: value
        for key, value in responses.items()
        if key != "voluntarySelfIdentificationQuestionResponses"
    }

    candidate_id = str(payload.get("jobApplicant") or f"email:{_email_hash(email)}")
    application_id = str(payload.get("jobApplicationId") or "")

    return {
        "candidate": {
            "provider_candidate_id": candidate_id,
            "full_name": " ".join(part for part in [first, last] if part).strip(),
            "email": email,
            "phone": phone,
            "skills": skills,
            "source": "LinkedIn Apply",
        },
        "application": {
            "provider_application_id": application_id,
            "external_job_id": str(payload.get("externalJobId") or ""),
            "source_attribution": "LinkedIn Apply",
            "status": "received",
            "applied_at": payload.get("appliedAt"),
            "question_responses": safe_responses,
            "sensitive_voluntary_identification_discarded": True,
        },
    }


def _indeed_normalized(payload: dict[str, Any]) -> dict[str, Any]:
    applicant = payload.get("applicant", {})

    if not isinstance(applicant, dict):
        applicant = {}

    email = str(applicant.get("email") or payload.get("email") or "").strip()
    name = str(
        applicant.get("fullName")
        or applicant.get("name")
        or payload.get("name")
        or ""
    ).strip()
    phone = str(
        applicant.get("phoneNumber")
        or applicant.get("phone")
        or payload.get("phone")
        or ""
    ).strip()

    job = payload.get("job", {})

    if not isinstance(job, dict):
        job = {}

    application_id = str(
        payload.get("id")
        or payload.get("indeedApplyId")
        or ""
    )
    external_job_id = str(
        job.get("jobId")
        or job.get("id")
        or payload.get("jobId")
        or ""
    )
    candidate_id = f"email:{_email_hash(email)}" if email else f"application:{application_id}"

    safe_application = {
        key: value
        for key, value in payload.items()
        if key not in {"applicant"}
    }

    # Keep common application fields while avoiding duplicating the full resume file
    # in normalized storage. The short-lived encrypted webhook inbox remains the
    # durable source payload until retention cleanup.
    safe_applicant = {
        key: value
        for key, value in applicant.items()
        if key not in {"resume", "file"}
    }
    safe_application["applicant"] = safe_applicant
    safe_application = _scrub_sensitive_keys(safe_application)

    return {
        "candidate": {
            "provider_candidate_id": candidate_id,
            "full_name": name,
            "email": email,
            "phone": phone,
            "source": "Indeed Apply",
        },
        "application": {
            "provider_application_id": application_id,
            "external_job_id": external_job_id,
            "source_attribution": "Indeed Apply",
            "status": "received",
            "payload": safe_application,
        },
    }


def _ziprecruiter_normalized(payload: dict[str, Any]) -> dict[str, Any]:
    email = str(payload.get("email") or "").strip()
    name = str(payload.get("name") or "").strip()
    phone = str(payload.get("phone") or "").strip()
    application_id = str(
        payload.get("zr_application_id")
        or payload.get("response_id")
        or ""
    )
    source = str(payload.get("source") or "ZipRecruiter Apply")
    candidate_id = (
        str(payload.get("candidate_id") or "")
        or (f"email:{_email_hash(email)}" if email else f"application:{application_id}")
    )

    profile = payload.get("profile")

    if not isinstance(profile, dict):
        profile = {}

    candidate_profile = {
        key: value
        for key, value in profile.items()
        if key not in {"text_resume"}
    }

    return {
        "candidate": {
            "provider_candidate_id": candidate_id,
            "full_name": name,
            "email": email,
            "phone": phone,
            "source": source,
            "profile": candidate_profile,
        },
        "application": {
            "provider_application_id": application_id,
            "external_job_id": str(payload.get("job_id") or ""),
            "source_attribution": source,
            "status": "received",
            "answers": payload.get("answers") or [],
            "attributes": payload.get("attributes") or {},
        },
    }



def _decode_attachment(
    encoded: str,
    *,
    filename: str,
    content_type: str,
) -> dict[str, Any] | None:
    if not encoded:
        return None

    try:
        data = base64.b64decode(encoded, validate=True)
    except Exception:
        return None

    if not data or len(data) > MAX_UPLOAD_BYTES:
        return None

    extracted_text = ""

    try:
        extracted_text = extract_resume_text(filename, data)
    except Exception:
        extracted_text = ""

    return {
        "filename": filename[:500],
        "content_type": content_type[:200],
        "data": data,
        "sha256": hashlib.sha256(data).hexdigest(),
        "resume_text": extracted_text,
    }


async def extract_resume_attachment(
    provider: str,
    payload: dict[str, Any],
    credentials: dict[str, Any],
) -> dict[str, Any] | None:
    """Extract an authorized resume attachment without arbitrary URL fetching."""

    if provider == "indeed":
        applicant = payload.get("applicant", {})

        if not isinstance(applicant, dict):
            return None

        resume = applicant.get("resume", {})

        if not isinstance(resume, dict):
            return None

        file_value = resume.get("file", {})

        if not isinstance(file_value, dict):
            return None

        return _decode_attachment(
            str(file_value.get("data") or ""),
            filename=str(file_value.get("fileName") or "indeed-resume.bin"),
            content_type=str(
                file_value.get("contentType") or "application/octet-stream"
            ),
        )

    if provider == "ziprecruiter":
        return _decode_attachment(
            str(payload.get("resume") or ""),
            filename="ziprecruiter-resume.pdf",
            content_type="application/pdf",
        )

    if provider != "linkedin":
        return None

    responses = payload.get("questionResponses", {})

    if not isinstance(responses, dict):
        return None

    resume_responses = responses.get("resumeQuestionResponses", {})

    if not isinstance(resume_responses, dict):
        return None

    answer = resume_responses.get("resumeQuestionAnswer", {})

    if not isinstance(answer, dict):
        return None

    media_url = str(answer.get("mediaUrl") or "")

    if not media_url:
        return None

    parsed = urlparse(media_url)

    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"www.linkedin.com", "linkedin.com"}
        or not parsed.path.startswith("/ambry/")
    ):
        raise ValueError("LinkedIn media URL failed the provider allowlist.")

    access_token = str(credentials.get("access_token") or "")

    if not access_token:
        raise ValueError("LinkedIn media retrieval requires access_token.")

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(20, connect=5),
        follow_redirects=False,
    ) as client:
        response = await client.get(
            media_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if response.status_code != 200:
        raise RuntimeError(
            f"LinkedIn media retrieval returned HTTP {response.status_code}."
        )

    if len(response.content) > MAX_UPLOAD_BYTES:
        raise ValueError("LinkedIn resume exceeds the configured file limit.")

    content_type = response.headers.get(
        "content-type",
        "application/octet-stream",
    ).split(";", 1)[0].strip().lower()
    suffix_by_type = {
        "application/pdf": ".pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "text/plain": ".txt",
    }
    suffix = suffix_by_type.get(content_type, ".bin")
    filename = f"linkedin-resume{suffix}"
    extracted_text = ""

    if suffix != ".bin":
        try:
            extracted_text = extract_resume_text(filename, response.content)
        except Exception:
            extracted_text = ""

    return {
        "filename": filename,
        "content_type": content_type,
        "data": response.content,
        "sha256": hashlib.sha256(response.content).hexdigest(),
        "resume_text": extracted_text,
    }


def _scrub_sensitive_keys(value: Any) -> Any:
    """Remove protected-class/voluntary-identification fields from normalized data."""

    blocked_fragments = {
        "race",
        "ethnicity",
        "gender",
        "disability",
        "veteran",
        "dateofbirth",
        "date_of_birth",
        "religion",
        "sexualorientation",
        "sexual_orientation",
    }

    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}

        for key, item in value.items():
            normalized_key = str(key).lower().replace("-", "").replace(" ", "")

            if any(fragment in normalized_key for fragment in blocked_fragments):
                continue

            cleaned[str(key)] = _scrub_sensitive_keys(item)

        return cleaned

    if isinstance(value, list):
        return [_scrub_sensitive_keys(item) for item in value]

    return value


def normalize_application_event(
    provider: str,
    payload: dict[str, Any],
    credentials: dict[str, Any],
) -> dict[str, Any]:
    if provider == "linkedin":
        return _linked_in_normalized(payload)

    if provider == "indeed":
        return _indeed_normalized(payload)

    if provider == "ziprecruiter":
        normalized = _ziprecruiter_normalized(payload)

        if (
            normalized["candidate"]["source"] == "ZipRecruiter RDB"
            and str(credentials.get("allow_sourced_candidates", "")).lower()
            not in {"true", "1", "yes"}
        ):
            raise PermissionError(
                "ZipRecruiter RDB ingestion is disabled for this organization."
            )

        return normalized

    raise ValueError("Unsupported webhook provider.")


async def process_event_in_session(
    session: AsyncSession,
    event_id: str,
) -> None:
    event = await session.scalar(
        select(WebhookEvent)
        .where(WebhookEvent.id == event_id)
        .with_for_update()
    )

    if event is None:
        raise LookupError("Webhook event not found.")

    if event.status == "processed":
        return

    event.status = "processing"
    event.attempts += 1
    event.last_error = ""
    await session.commit()

    try:
        raw_text = decrypt_text(
            event.encrypted_payload,
            aad=(
                f"webhook:{event.organization_id}:"
                f"{event.provider}:{event.id}"
            ),
        )
        payload = json.loads(raw_text)
        credentials = await provider_credentials(
            session,
            event.organization_id,
            event.provider,
        )

        if str(credentials.get("ingest_applications", "true")).lower() not in {
            "true",
            "1",
            "yes",
        }:
            event.status = "ignored"
            event.processed_at = datetime.now(UTC)
            await session.commit()
            return

        normalized = normalize_application_event(
            event.provider,
            payload,
            credentials,
        )
        candidate_data = normalized["candidate"]
        application_data = normalized["application"]
        attachment = await extract_resume_attachment(
            event.provider,
            payload,
            credentials,
        )

        if attachment and attachment.get("resume_text"):
            candidate_data["resume_text"] = attachment["resume_text"]
        provider_candidate_id = str(candidate_data["provider_candidate_id"])

        if not provider_candidate_id:
            raise ValueError("Provider candidate identifier is unavailable.")

        provider_application_id = str(application_data["provider_application_id"])

        if not provider_application_id:
            provider_application_id = event.event_id

        candidate = await session.scalar(
            select(InboundCandidate).where(
                InboundCandidate.organization_id == event.organization_id,
                InboundCandidate.provider == event.provider,
                InboundCandidate.provider_candidate_id == provider_candidate_id,
            )
        )

        now = datetime.now(UTC)
        retention_days = int(
            credentials.get("candidate_retention_days")
            or settings.candidate_retention_days
        )
        retention_until = now + timedelta(days=max(1, min(retention_days, 3650)))
        privacy_notice_version = str(
            credentials.get("privacy_notice_version", "")
        )
        processing_basis = str(
            credentials.get("processing_basis", "job_application")
        )

        if candidate is None:
            candidate_uuid = str(uuid.uuid4())
            candidate = InboundCandidate(
                id=candidate_uuid,
                organization_id=event.organization_id,
                provider=event.provider,
                provider_candidate_id=provider_candidate_id[:1000],
                email_hash=_email_hash(str(candidate_data.get("email", "")))
                if candidate_data.get("email")
                else "",
                encrypted_payload=encrypt_text(
                    json.dumps(candidate_data, separators=(",", ":")),
                    aad=(
                        f"inbound-candidate:{event.organization_id}:"
                        f"{candidate_uuid}"
                    ),
                ),
                source=str(candidate_data.get("source", event.provider))[:200],
                processing_basis=processing_basis[:200],
                privacy_notice_version=privacy_notice_version[:100],
                retention_until=retention_until,
            )
            session.add(candidate)
            await session.flush()
        else:
            candidate.encrypted_payload = encrypt_text(
                json.dumps(candidate_data, separators=(",", ":")),
                aad=(
                    f"inbound-candidate:{event.organization_id}:"
                    f"{candidate.id}"
                ),
            )
            candidate.email_hash = (
                _email_hash(str(candidate_data.get("email", "")))
                if candidate_data.get("email")
                else candidate.email_hash
            )
            candidate.retention_until = max(candidate.retention_until, retention_until)

        if event.provider == "indeed" and application_data.get("external_job_id"):
            duplicate_cutoff = now - timedelta(days=120)
            indeed_duplicate = await session.scalar(
                select(InboundApplication).where(
                    InboundApplication.organization_id == event.organization_id,
                    InboundApplication.provider == "indeed",
                    InboundApplication.candidate_id == candidate.id,
                    InboundApplication.external_job_id
                    == str(application_data.get("external_job_id", ""))[:500],
                    InboundApplication.received_at >= duplicate_cutoff,
                )
            )

            if indeed_duplicate is not None:
                event.status = "processed"
                event.processed_at = datetime.now(UTC)
                event.last_error = ""
                session.add(
                    AuditEvent(
                        event="webhook.application.duplicate",
                        actor="provider:indeed",
                        details={
                            "organization_id": event.organization_id,
                            "webhook_event_id": event.id,
                            "existing_application_id": indeed_duplicate.id,
                        },
                    )
                )
                await session.commit()
                return

        existing_application = await session.scalar(
            select(InboundApplication).where(
                InboundApplication.organization_id == event.organization_id,
                InboundApplication.provider == event.provider,
                InboundApplication.provider_application_id
                == provider_application_id[:1000],
            )
        )

        if existing_application is None:
            application_uuid = str(uuid.uuid4())
            existing_application = InboundApplication(
                id=application_uuid,
                organization_id=event.organization_id,
                provider=event.provider,
                provider_application_id=provider_application_id[:1000],
                external_job_id=str(
                    application_data.get("external_job_id", "")
                )[:500],
                candidate_id=candidate.id,
                source_attribution=str(
                    application_data.get("source_attribution", event.provider)
                )[:200],
                status=str(application_data.get("status", "received"))[:100],
                encrypted_payload=encrypt_text(
                    json.dumps(application_data, separators=(",", ":")),
                    aad=(
                        f"inbound-application:{event.organization_id}:"
                        f"{application_uuid}"
                    ),
                ),
            )
            session.add(existing_application)
            await session.flush()

        if attachment:
            existing_attachment = await session.scalar(
                select(InboundAttachment).where(
                    InboundAttachment.organization_id == event.organization_id,
                    InboundAttachment.candidate_id == candidate.id,
                    InboundAttachment.sha256 == attachment["sha256"],
                )
            )

            if existing_attachment is None:
                attachment_uuid = str(uuid.uuid4())
                session.add(
                    InboundAttachment(
                        id=attachment_uuid,
                        organization_id=event.organization_id,
                        candidate_id=candidate.id,
                        application_id=existing_application.id,
                        provider=event.provider,
                        filename=str(attachment["filename"])[:500],
                        content_type=str(attachment["content_type"])[:200],
                        sha256=str(attachment["sha256"]),
                        encrypted_base64=encrypt_text(
                            base64.b64encode(attachment["data"]).decode("ascii"),
                            aad=(
                                f"inbound-attachment:{event.organization_id}:"
                                f"{attachment_uuid}"
                            ),
                        ),
                        retention_until=retention_until,
                    )
                )

        event.status = "processed"
        event.processed_at = datetime.now(UTC)
        event.last_error = ""
        session.add(
            AuditEvent(
                event="webhook.application.processed",
                actor=f"provider:{event.provider}",
                details={
                    "organization_id": event.organization_id,
                    "provider": event.provider,
                    "webhook_event_id": event.id,
                    "source_attribution": str(
                        application_data.get("source_attribution", event.provider)
                    )[:200],
                },
            )
        )
        await session.commit()

    except Exception as exc:
        await session.rollback()
        event = await session.get(WebhookEvent, event_id)

        if event is not None:
            event.status = "retry"
            event.last_error = f"{type(exc).__name__}: {str(exc)[:1500]}"
            await session.commit()

        raise


async def mark_dead_letter(event_id: str, error: str) -> None:
    from app.db import SessionFactory

    async with SessionFactory() as session:
        event = await session.get(WebhookEvent, event_id)

        if event is None or event.status == "processed":
            return

        event.status = "dead_letter"
        event.last_error = error[:2000]
        await session.commit()


async def purge_expired_inbound_data(session: AsyncSession) -> dict[str, int]:
    now = datetime.now(UTC)
    expired_events = await session.execute(
        delete(WebhookEvent).where(WebhookEvent.retention_until < now)
    )
    expired_candidates = await session.execute(
        delete(InboundCandidate).where(InboundCandidate.retention_until < now)
    )
    await session.commit()

    return {
        "webhook_events": int(expired_events.rowcount or 0),
        "candidates": int(expired_candidates.rowcount or 0),
    }
