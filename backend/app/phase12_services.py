from __future__ import annotations

import base64
import fnmatch
import hashlib
import json
import re
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

import httpx
import jwt
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    CareerMonitorPolicy,
    ConfidentialInferenceAttestation,
    ConfidentialInferencePolicy,
    ContainmentPolicy,
    CredentialNegotiationDecision,
    CredentialNegotiationPolicy,
    FederationEntityRecord,
    FederationTrustAnchor,
    IncidentContainmentAction,
    Membership,
    ProviderCredential,
    RuntimeSecurityEvent,
    WalletAttestationEvidence,
    WalletAttestationTrustAnchor,
    WalletKeyAttestation,
)


ALLOWED_FEDERATION_ALGORITHMS = {"ES256", "RS256", "PS256", "EdDSA"}
SEVERITY_ORDER = {
    "debug": 0,
    "info": 1,
    "notice": 2,
    "warning": 3,
    "error": 4,
    "critical": 5,
}


def now() -> datetime:
    return datetime.now(UTC)


def canonical_digest(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _jwk_candidates(jwks: dict) -> list[dict]:
    keys = jwks.get("keys", [])

    if not isinstance(keys, list):
        raise ValueError("JWKS keys must be an array.")

    return [item for item in keys if isinstance(item, dict)]


def _public_key_from_jwk(jwk_value: dict):
    kty = jwk_value.get("kty")

    if kty == "EC":
        return jwt.algorithms.ECAlgorithm.from_jwk(json.dumps(jwk_value))
    if kty == "RSA":
        return jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk_value))
    if kty == "OKP":
        return jwt.algorithms.OKPAlgorithm.from_jwk(json.dumps(jwk_value))

    raise ValueError(f"Unsupported JWK kty: {kty}")


def verify_signed_jwt(
    token: str,
    jwks: dict,
    *,
    expected_issuer: str | None = None,
    expected_subject: str | None = None,
    expected_audience: str | None = None,
) -> dict:
    header = jwt.get_unverified_header(token)
    algorithm = str(header.get("alg", ""))

    if algorithm not in ALLOWED_FEDERATION_ALGORITHMS:
        raise ValueError("JWT signing algorithm is not allowed.")

    kid = str(header.get("kid", ""))
    candidates = _jwk_candidates(jwks)

    if kid:
        candidates = [item for item in candidates if str(item.get("kid", "")) == kid]

    if not candidates:
        raise ValueError("No matching verification key was found.")

    last_error: Exception | None = None

    for candidate in candidates:
        try:
            options = {
                "verify_aud": bool(expected_audience),
                "require": ["exp", "iat"],
            }
            payload = jwt.decode(
                token,
                _public_key_from_jwk(candidate),
                algorithms=[algorithm],
                audience=expected_audience or None,
                issuer=expected_issuer or None,
                options=options,
                leeway=60,
            )

            if expected_subject and payload.get("sub") != expected_subject:
                raise ValueError("JWT subject does not match the expected entity.")

            return payload
        except Exception as exc:
            last_error = exc

    raise ValueError("JWT signature or registered claims are invalid.") from last_error


def _self_statement_details(record: FederationEntityRecord) -> dict:
    if not record.self_statement_jwt:
        return {"validated": False, "reason": "self_statement_missing"}

    payload = verify_signed_jwt(
        record.self_statement_jwt,
        record.jwks,
        expected_issuer=record.entity_id,
        expected_subject=record.entity_id,
    )

    return {
        "validated": True,
        "exp": payload.get("exp"),
        "metadata_types": sorted((payload.get("metadata") or {}).keys()),
    }


async def validate_federation_chain(
    session: AsyncSession,
    organization_id: str,
    entity_id: str,
) -> dict:
    entity = await session.scalar(
        select(FederationEntityRecord).where(
            FederationEntityRecord.organization_id == organization_id,
            FederationEntityRecord.entity_id == entity_id,
        )
    )

    if entity is None:
        raise ValueError("Federation entity is not registered.")

    path: list[str] = []
    reasons: list[str] = []
    effective_metadata = dict(entity.metadata_json or {})
    current = entity
    visited: set[str] = set()

    for _ in range(settings.phase12_federation_max_chain_depth):
        if current.entity_id in visited:
            reasons.append("federation_cycle_detected")
            break

        visited.add(current.entity_id)
        path.append(current.entity_id)

        try:
            self_details = _self_statement_details(current)
        except Exception as exc:
            reasons.append(f"invalid_self_statement:{current.entity_id}:{type(exc).__name__}")
            break

        parent_id = current.parent_entity_id.strip()

        if not parent_id:
            anchor = await session.scalar(
                select(FederationTrustAnchor).where(
                    FederationTrustAnchor.organization_id == organization_id,
                    FederationTrustAnchor.entity_id == current.entity_id,
                    FederationTrustAnchor.enabled.is_(True),
                )
            )

            if anchor is None:
                reasons.append("chain_does_not_end_at_approved_anchor")
                break

            reasons.append("approved_trust_anchor_reached")
            current.trust_status = "trusted"
            current.validation_details = {
                "path": path,
                "anchor": anchor.entity_id,
                "self_statement": self_details,
            }
            current.last_validated_at = now()
            await session.commit()

            return {
                "trusted": True,
                "anchor_entity_id": anchor.entity_id,
                "path": path,
                "reasons": reasons,
                "effective_metadata": effective_metadata,
            }

        parent_entity = await session.scalar(
            select(FederationEntityRecord).where(
                FederationEntityRecord.organization_id == organization_id,
                FederationEntityRecord.entity_id == parent_id,
            )
        )
        anchor = await session.scalar(
            select(FederationTrustAnchor).where(
                FederationTrustAnchor.organization_id == organization_id,
                FederationTrustAnchor.entity_id == parent_id,
                FederationTrustAnchor.enabled.is_(True),
            )
        )

        parent_jwks: dict

        if parent_entity is not None:
            parent_jwks = parent_entity.jwks
        elif anchor is not None:
            parent_jwks = anchor.jwks
        else:
            reasons.append(f"unregistered_parent:{parent_id}")
            break

        if not current.subordinate_statement_jwt:
            reasons.append(f"subordinate_statement_missing:{current.entity_id}")
            break

        try:
            verify_signed_jwt(
                current.subordinate_statement_jwt,
                parent_jwks,
                expected_issuer=parent_id,
                expected_subject=current.entity_id,
            )
        except Exception as exc:
            reasons.append(
                f"invalid_subordinate_statement:{current.entity_id}:{type(exc).__name__}"
            )
            break

        if parent_entity is not None:
            effective_metadata = {
                **dict(parent_entity.metadata_json or {}),
                **effective_metadata,
            }
            current = parent_entity
            continue

        path.append(parent_id)
        reasons.append("approved_trust_anchor_reached")
        entity.trust_status = "trusted"
        entity.validation_details = {
            "path": path,
            "anchor": anchor.entity_id if anchor else parent_id,
        }
        entity.last_validated_at = now()
        await session.commit()

        return {
            "trusted": True,
            "anchor_entity_id": anchor.entity_id if anchor else parent_id,
            "path": path,
            "reasons": reasons,
            "effective_metadata": effective_metadata,
        }

    entity.trust_status = "untrusted"
    entity.validation_details = {"path": path, "reasons": reasons}
    entity.last_validated_at = now()
    await session.commit()

    return {
        "trusted": False,
        "anchor_entity_id": "",
        "path": path,
        "reasons": reasons or ["maximum_chain_depth_exceeded"],
        "effective_metadata": effective_metadata,
    }


def _verify_certificate_signature(
    certificate: x509.Certificate,
    issuer_certificate: x509.Certificate,
) -> None:
    public_key = issuer_certificate.public_key()

    if isinstance(public_key, rsa.RSAPublicKey):
        public_key.verify(
            certificate.signature,
            certificate.tbs_certificate_bytes,
            padding.PKCS1v15(),
            certificate.signature_hash_algorithm,
        )
    elif isinstance(public_key, ec.EllipticCurvePublicKey):
        public_key.verify(
            certificate.signature,
            certificate.tbs_certificate_bytes,
            ec.ECDSA(certificate.signature_hash_algorithm),
        )
    else:
        raise ValueError("Unsupported certificate public-key type.")


def _parse_x5c(value: list[str]) -> list[x509.Certificate]:
    certificates: list[x509.Certificate] = []

    for encoded in value:
        certificates.append(
            x509.load_der_x509_certificate(base64.b64decode(encoded))
        )

    return certificates


def _certificate_is_current(certificate: x509.Certificate) -> bool:
    current = now()
    not_before = certificate.not_valid_before_utc
    not_after = certificate.not_valid_after_utc
    return not_before <= current <= not_after


def _subject_matches(value: str, allowed_patterns: list[str]) -> bool:
    if not allowed_patterns:
        return True

    return any(fnmatch.fnmatchcase(value, pattern) for pattern in allowed_patterns)


async def verify_wallet_attestation(
    session: AsyncSession,
    *,
    organization_id: str,
    user_id: str | None,
    attestation_jwt: str,
    expected_audience: str,
) -> WalletAttestationEvidence:
    header = jwt.get_unverified_header(attestation_jwt)
    x5c_value = header.get("x5c")

    if not isinstance(x5c_value, list) or not x5c_value:
        raise ValueError("Wallet attestation must include an x5c certificate chain.")

    certificates = _parse_x5c([str(item) for item in x5c_value])

    for certificate in certificates:
        if not _certificate_is_current(certificate):
            raise ValueError("Wallet attestation certificate is not currently valid.")

    for child, issuer in zip(certificates, certificates[1:], strict=False):
        _verify_certificate_signature(child, issuer)

    roots = list(
        (
            await session.scalars(
                select(WalletAttestationTrustAnchor).where(
                    WalletAttestationTrustAnchor.organization_id == organization_id,
                    WalletAttestationTrustAnchor.enabled.is_(True),
                )
            )
        ).all()
    )

    matched_anchor: WalletAttestationTrustAnchor | None = None
    final_certificate = certificates[-1]

    for root in roots:
        try:
            root_certificate = x509.load_pem_x509_certificate(
                root.root_certificate_pem.encode("utf-8")
            )

            if (
                final_certificate.fingerprint(hashes.SHA256())
                == root_certificate.fingerprint(hashes.SHA256())
            ):
                matched_anchor = root
                break

            _verify_certificate_signature(final_certificate, root_certificate)
            matched_anchor = root
            break
        except Exception:
            continue

    if matched_anchor is None:
        raise ValueError("Wallet attestation did not chain to an approved trust anchor.")

    algorithm = str(header.get("alg", ""))

    if algorithm not in {"ES256", "RS256", "PS256"}:
        raise ValueError("Wallet attestation signing algorithm is not allowed.")

    options = {
        "verify_aud": bool(expected_audience),
        "require": ["iat", "exp", "iss", "sub"],
    }
    claims = jwt.decode(
        attestation_jwt,
        certificates[0].public_key(),
        algorithms=[algorithm],
        audience=expected_audience or None,
        options=options,
        leeway=settings.phase12_wallet_attestation_clock_skew_seconds,
    )
    subject = str(claims.get("sub", ""))

    if not _subject_matches(subject, matched_anchor.allowed_subjects):
        raise ValueError("Wallet attestation subject is not approved by this trust anchor.")

    digest = hashlib.sha256(attestation_jwt.encode("utf-8")).hexdigest()
    existing = await session.scalar(
        select(WalletAttestationEvidence).where(
            WalletAttestationEvidence.attestation_digest == digest
        )
    )

    if existing is not None:
        return existing

    expires_at = datetime.fromtimestamp(int(claims["exp"]), tz=UTC)
    evidence = WalletAttestationEvidence(
        organization_id=organization_id,
        user_id=user_id,
        trust_anchor_id=matched_anchor.id,
        subject=subject,
        issuer=str(claims.get("iss", "")),
        attestation_digest=digest,
        claims_json={
            key: value
            for key, value in claims.items()
            if key not in {"nonce", "jti"}
        },
        verification_status="verified",
        expires_at=expires_at,
    )
    session.add(evidence)
    await session.commit()
    await session.refresh(evidence)
    return evidence


ASSURANCE_LEVELS = {
    "": 0,
    "low": 1,
    "substantial": 2,
    "high": 3,
}


async def negotiate_credential_policy(
    session: AsyncSession,
    *,
    policy: CredentialNegotiationPolicy,
    user_id: str | None,
    capabilities: dict,
) -> CredentialNegotiationDecision:
    reasons: list[str] = []
    requested_formats = [str(item) for item in capabilities.get("formats", [])]
    requested_types = [str(item) for item in capabilities.get("credential_types", [])]
    requested_claims = {str(item) for item in capabilities.get("claims", [])}
    requested_algs = [str(item) for item in capabilities.get("proof_algorithms", [])]

    negotiated_formats = sorted(set(requested_formats) & set(policy.accepted_formats))
    negotiated_types = (
        sorted(set(requested_types) & set(policy.accepted_credential_types))
        if policy.accepted_credential_types
        else sorted(set(requested_types))
    )
    negotiated_algs = sorted(
        set(requested_algs) & set(policy.accepted_proof_algorithms)
    )

    if not negotiated_formats:
        reasons.append("no_accepted_credential_format")
    if policy.accepted_credential_types and not negotiated_types:
        reasons.append("no_accepted_credential_type")
    if policy.accepted_proof_algorithms and not negotiated_algs:
        reasons.append("no_accepted_proof_algorithm")

    missing_claims = sorted(set(policy.required_claims) - requested_claims)

    if missing_claims:
        reasons.append("missing_required_claims:" + ",".join(missing_claims))

    assurance = str(capabilities.get("assurance_level", "")).lower()
    minimum = policy.minimum_assurance_level.lower()

    if ASSURANCE_LEVELS.get(assurance, -1) < ASSURANCE_LEVELS.get(minimum, 0):
        reasons.append("assurance_level_below_policy")

    wallet_evidence: WalletAttestationEvidence | None = None
    wallet_evidence_id = capabilities.get("wallet_attestation_evidence_id")

    if wallet_evidence_id:
        wallet_evidence = await session.get(
            WalletAttestationEvidence,
            str(wallet_evidence_id),
        )

    if policy.require_wallet_attestation:
        if (
            wallet_evidence is None
            or wallet_evidence.organization_id != policy.organization_id
            or wallet_evidence.verification_status != "verified"
            or (
                wallet_evidence.expires_at is not None
                and wallet_evidence.expires_at <= now()
            )
        ):
            reasons.append("verified_wallet_attestation_required")

    if policy.require_hardware_backed_key:
        key_id = capabilities.get("wallet_key_attestation_id")
        key_record = await session.get(WalletKeyAttestation, str(key_id)) if key_id else None

        if (
            key_record is None
            or key_record.verification_status != "verified"
            or not key_record.hardware_backed_claim
            or (user_id and key_record.user_id != user_id)
        ):
            reasons.append("verified_hardware_backed_key_required")

    required_frameworks = set(policy.required_trust_frameworks)

    if required_frameworks:
        entity_id = str(capabilities.get("federation_entity_id", ""))
        entity = await session.scalar(
            select(FederationEntityRecord).where(
                FederationEntityRecord.organization_id == policy.organization_id,
                FederationEntityRecord.entity_id == entity_id,
                FederationEntityRecord.trust_status == "trusted",
            )
        )

        if entity is None:
            reasons.append("trusted_federation_entity_required")
        else:
            entity_frameworks = set(
                str(item)
                for item in (entity.metadata_json or {}).get("trust_frameworks", [])
            )
            entity_frameworks.update(
                str(mark.get("id", ""))
                for mark in (entity.trust_marks or [])
                if isinstance(mark, dict)
            )

            missing_frameworks = sorted(required_frameworks - entity_frameworks)

            if missing_frameworks:
                reasons.append(
                    "missing_trust_frameworks:" + ",".join(missing_frameworks)
                )

    decision = "allow" if not reasons else "deny"
    negotiated = {
        "formats": negotiated_formats,
        "credential_types": negotiated_types,
        "proof_algorithms": negotiated_algs,
    }
    digest = canonical_digest(capabilities)
    record = CredentialNegotiationDecision(
        organization_id=policy.organization_id,
        policy_id=policy.id,
        user_id=user_id,
        decision=decision,
        reasons=reasons,
        negotiated_json=negotiated,
        input_digest=digest,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


def _validate_fixed_https_endpoint(url: str) -> str:
    parsed = urlparse(url)

    if parsed.scheme not in {"https", "http"}:
        raise ValueError("Inference endpoint must use HTTP(S).")

    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1"}:
        raise ValueError("Non-local confidential inference requires HTTPS.")

    host = (parsed.hostname or "").lower()
    allowed = settings.phase12_confidential_inference_allowed_host_set

    if allowed and host not in allowed:
        raise ValueError("Inference endpoint host is not allowlisted.")

    if not host:
        raise ValueError("Inference endpoint host is missing.")

    return url


async def authorize_confidential_inference(
    session: AsyncSession,
    policy: ConfidentialInferencePolicy,
    data_categories: list[str],
) -> ConfidentialInferenceAttestation | None:
    if not policy.enabled:
        raise ValueError("Confidential inference policy is disabled.")

    requested_categories = set(data_categories)
    allowed_categories = set(policy.allowed_data_categories)

    if allowed_categories and not requested_categories.issubset(allowed_categories):
        raise ValueError("Requested data categories are outside the policy.")

    if not policy.require_attestation:
        return None

    attestation = await session.scalar(
        select(ConfidentialInferenceAttestation)
        .where(
            ConfidentialInferenceAttestation.policy_id == policy.id,
            ConfidentialInferenceAttestation.verified.is_(True),
            ConfidentialInferenceAttestation.expires_at > now(),
        )
        .order_by(ConfidentialInferenceAttestation.verified_at.desc())
        .limit(1)
    )

    if attestation is None:
        raise ValueError("No current verified confidential-compute attestation exists.")

    if (
        policy.allowed_measurements
        and attestation.measurement not in set(policy.allowed_measurements)
    ):
        raise ValueError("Confidential workload measurement is not approved.")

    return attestation


async def invoke_confidential_inference(
    session: AsyncSession,
    policy: ConfidentialInferencePolicy,
    *,
    task: str,
    input_text: str,
    data_categories: list[str],
) -> dict:
    await authorize_confidential_inference(
        session,
        policy,
        data_categories,
    )

    endpoint = _validate_fixed_https_endpoint(
        settings.phase12_confidential_inference_url
    )
    token = settings.phase12_confidential_inference_token.get_secret_value()
    headers = {"Accept": "application/json", "Content-Type": "application/json"}

    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(30, connect=5),
        follow_redirects=False,
    ) as client:
        response = await client.post(
            endpoint,
            headers=headers,
            json={
                "task": task,
                "input": input_text,
                "data_categories": data_categories,
                "policy_id": policy.id,
            },
        )
        response.raise_for_status()
        payload = response.json()

    if not isinstance(payload, dict):
        raise ValueError("Confidential inference gateway returned an invalid response.")

    return payload


def _sanitize_runtime_details(details: dict) -> dict:
    sensitive_keys = {
        "password",
        "token",
        "authorization",
        "cookie",
        "secret",
        "private_key",
        "api_key",
    }

    def clean(value):
        if isinstance(value, dict):
            return {
                str(key): (
                    "[REDACTED]"
                    if str(key).lower() in sensitive_keys
                    else clean(item)
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [clean(item) for item in value[:100]]
        if isinstance(value, str):
            return value[:4000]
        return value

    return clean(details)


def _policy_matches(policy: ContainmentPolicy, event: RuntimeSecurityEvent) -> bool:
    if not policy.enabled:
        return False

    if SEVERITY_ORDER.get(event.severity, -1) < SEVERITY_ORDER.get(
        policy.minimum_severity,
        5,
    ):
        return False

    if not policy.rule_patterns:
        return True

    return any(
        fnmatch.fnmatchcase(event.rule.lower(), pattern.lower())
        for pattern in policy.rule_patterns
    )


REVERSIBLE_AUTO_ACTIONS = {
    "disable_provider_integrations",
    "pause_career_agents",
}


async def execute_containment_action(
    session: AsyncSession,
    action: IncidentContainmentAction,
) -> IncidentContainmentAction:
    event = await session.get(RuntimeSecurityEvent, action.event_id)

    if event is None:
        raise ValueError("Runtime security event no longer exists.")

    if action.action == "disable_provider_integrations":
        if event.organization_id is None:
            raise ValueError("Provider containment requires an organization.")

        records = list(
            (
                await session.scalars(
                    select(ProviderCredential).where(
                        ProviderCredential.organization_id == event.organization_id,
                        ProviderCredential.enabled.is_(True),
                    )
                )
            ).all()
        )

        for record in records:
            record.enabled = False

        action.status = "executed"
        action.result_json = {"disabled_provider_credentials": len(records)}

    elif action.action == "pause_career_agents":
        if event.organization_id is None:
            raise ValueError("Agent containment requires an organization.")

        user_ids = list(
            (
                await session.scalars(
                    select(Membership.user_id).where(
                        Membership.organization_id == event.organization_id
                    )
                )
            ).all()
        )
        policies = list(
            (
                await session.scalars(
                    select(CareerMonitorPolicy).where(
                        CareerMonitorPolicy.user_id.in_(user_ids)
                    )
                )
            ).all()
        )

        for policy in policies:
            policy.enabled = False

        action.status = "executed"
        action.result_json = {"paused_monitor_policies": len(policies)}

    elif action.action in {
        "request_network_quarantine",
        "request_workload_isolation",
    }:
        action.status = "awaiting_external_controller"
        action.result_json = {
            "reason": (
                "Infrastructure isolation must be performed by an authorized "
                "cluster/security controller using workload identity."
            )
        }

    else:
        raise ValueError("Unsupported containment action.")

    action.executed_at = now()
    await session.commit()
    await session.refresh(action)
    return action


async def ingest_runtime_event(
    session: AsyncSession,
    event_data: dict,
) -> RuntimeSecurityEvent:
    details = _sanitize_runtime_details(dict(event_data.get("details") or {}))
    digest = canonical_digest(
        {
            "organization_id": event_data.get("organization_id"),
            "source": event_data.get("source"),
            "severity": event_data.get("severity"),
            "rule": event_data.get("rule"),
            "workload": event_data.get("workload"),
            "namespace": event_data.get("namespace"),
            "details": details,
        }
    )
    existing = await session.scalar(
        select(RuntimeSecurityEvent).where(
            RuntimeSecurityEvent.event_digest == digest
        )
    )

    if existing is not None:
        return existing

    record = RuntimeSecurityEvent(
        organization_id=event_data.get("organization_id"),
        source=str(event_data.get("source", "other")),
        severity=str(event_data.get("severity", "warning")),
        rule=str(event_data.get("rule", "")),
        workload=str(event_data.get("workload", "")),
        namespace=str(event_data.get("namespace", "")),
        event_digest=digest,
        details_json=details,
    )
    session.add(record)
    await session.flush()

    if record.organization_id:
        policies = list(
            (
                await session.scalars(
                    select(ContainmentPolicy).where(
                        ContainmentPolicy.organization_id == record.organization_id,
                        ContainmentPolicy.enabled.is_(True),
                    )
                )
            ).all()
        )

        for policy in policies:
            if not _policy_matches(policy, record):
                continue

            for action_name in policy.actions:
                reversible = action_name in REVERSIBLE_AUTO_ACTIONS
                auto_execute = reversible and policy.auto_execute_reversible
                action = IncidentContainmentAction(
                    event_id=record.id,
                    policy_id=policy.id,
                    action=action_name,
                    reversible=reversible,
                    requires_human_approval=not auto_execute,
                    status="pending",
                )
                session.add(action)
                await session.flush()

                if auto_execute:
                    await execute_containment_action(session, action)

    await session.commit()
    await session.refresh(record)
    return record


async def purge_runtime_security_events(session: AsyncSession) -> int:
    cutoff = now() - timedelta(days=settings.phase12_runtime_event_retention_days)
    rows = list(
        (
            await session.scalars(
                select(RuntimeSecurityEvent).where(
                    RuntimeSecurityEvent.detected_at < cutoff,
                    RuntimeSecurityEvent.status.in_(["resolved", "closed"]),
                )
            )
        ).all()
    )

    for row in rows:
        await session.delete(row)

    await session.commit()
    return len(rows)
