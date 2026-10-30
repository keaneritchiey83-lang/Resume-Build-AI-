from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

import boto3
import jwt
from anyio import to_thread
from azure.identity import DefaultAzureCredential
from azure.keyvault.keys.crypto import CryptographyClient, SignatureAlgorithm
from cryptography.hazmat.primitives.asymmetric import utils
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import CredentialIssuerProfile, HsmSigningKey


def _b64u(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _compact_json(value: dict[str, Any]) -> str:
    return json.dumps(
        value,
        separators=(",", ":"),
        sort_keys=True,
        ensure_ascii=False,
    )


def _normalize_es256_signature(signature: bytes) -> bytes:
    if len(signature) == 64:
        return signature

    r, s = utils.decode_dss_signature(signature)
    return r.to_bytes(32, "big") + s.to_bytes(32, "big")


async def active_hsm_key(
    session: AsyncSession,
    issuer: CredentialIssuerProfile,
) -> HsmSigningKey | None:
    return await session.scalar(
        select(HsmSigningKey)
        .where(
            HsmSigningKey.issuer_profile_id == issuer.id,
            HsmSigningKey.active.is_(True),
            HsmSigningKey.approval_status == "approved",
        )
        .order_by(HsmSigningKey.created_at.desc())
        .limit(1)
    )


def _sign_aws_kms(key_reference: str, signing_input: bytes) -> bytes:
    client = boto3.client("kms", region_name=settings.aws_region)
    response = client.sign(
        KeyId=key_reference,
        Message=hashlib.sha256(signing_input).digest(),
        MessageType="DIGEST",
        SigningAlgorithm="ECDSA_SHA_256",
    )
    return _normalize_es256_signature(bytes(response["Signature"]))


def _sign_azure_hsm(key_reference: str, signing_input: bytes) -> bytes:
    credential = DefaultAzureCredential()
    client = CryptographyClient(
        key_id=key_reference,
        credential=credential,
    )
    digest = hashlib.sha256(signing_input).digest()
    response = client.sign(SignatureAlgorithm.es256, digest)
    return _normalize_es256_signature(bytes(response.signature))


def _local_issuer_sign(
    issuer: CredentialIssuerProfile,
    payload: dict[str, Any],
    headers: dict[str, Any],
) -> str:
    from app.phase10_services import _issuer_private_pem

    return jwt.encode(
        payload,
        _issuer_private_pem(issuer),
        algorithm="ES256",
        headers=headers,
    )


async def sign_credential_jws(
    session: AsyncSession,
    issuer: CredentialIssuerProfile,
    payload: dict[str, Any],
    headers: dict[str, Any],
) -> str:
    key = await active_hsm_key(session, issuer)

    if key is None:
        if settings.phase12_require_hsm_signing:
            raise ValueError(
                "Credential issuance requires an approved active HSM signing key."
            )

        return _local_issuer_sign(issuer, payload, headers)

    if key.algorithm != "ES256":
        raise ValueError("Only ES256 HSM credential signing is implemented.")

    protected = {
        **headers,
        "alg": "ES256",
        "kid": str(key.public_jwk.get("kid", headers.get("kid", ""))),
    }
    encoded_header = _b64u(_compact_json(protected).encode("utf-8"))
    encoded_payload = _b64u(_compact_json(payload).encode("utf-8"))
    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")

    if key.provider == "aws_kms":
        signature = await to_thread.run_sync(
            _sign_aws_kms,
            key.key_reference,
            signing_input,
        )
    elif key.provider == "azure_hsm":
        signature = await to_thread.run_sync(
            _sign_azure_hsm,
            key.key_reference,
            signing_input,
        )
    else:
        raise ValueError("Unsupported HSM signing provider.")

    return f"{encoded_header}.{encoded_payload}.{_b64u(signature)}"
