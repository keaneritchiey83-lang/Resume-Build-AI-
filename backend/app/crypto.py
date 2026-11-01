from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

try:
    import boto3
except ImportError:  # Optional until AWS KMS is selected.
    boto3 = None

try:
    from azure.identity import DefaultAzureCredential
    from azure.keyvault.keys import KeyClient
    from azure.keyvault.keys.crypto import CryptographyClient, KeyWrapAlgorithm
except ImportError:  # Optional until Azure Key Vault is selected.
    DefaultAzureCredential = None
    KeyClient = None
    CryptographyClient = None
    KeyWrapAlgorithm = None

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings


class EncryptionConfigurationError(RuntimeError):
    pass


@dataclass(slots=True)
class DataKey:
    plaintext: bytes
    wrapped: bytes
    key_id: str
    provider: str


class KeyProvider(Protocol):
    name: str

    def generate_data_key(self) -> DataKey: ...

    def decrypt_data_key(self, wrapped: bytes, key_id: str) -> bytes: ...


def _b64decode(value: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(value.encode("ascii"))
    except Exception as exc:
        raise EncryptionConfigurationError("Invalid base64 key material.") from exc


class LocalKeyProvider:
    name = "local"

    def _master_key(self, key_id: str) -> bytes:
        encoded = settings.local_master_keys.get(key_id)

        if not encoded:
            raise EncryptionConfigurationError(
                f"Local master key {key_id!r} is unavailable."
            )

        key = _b64decode(encoded)

        if len(key) != 32:
            raise EncryptionConfigurationError(
                f"Local master key {key_id!r} must decode to 32 bytes."
            )

        return key

    def generate_data_key(self) -> DataKey:
        key_id = settings.local_current_key_id
        master = self._master_key(key_id)
        data_key = os.urandom(32)
        nonce = os.urandom(12)
        wrapped = nonce + AESGCM(master).encrypt(
            nonce,
            data_key,
            f"career-envelope:{key_id}".encode(),
        )
        return DataKey(
            plaintext=data_key,
            wrapped=wrapped,
            key_id=key_id,
            provider=self.name,
        )

    def decrypt_data_key(self, wrapped: bytes, key_id: str) -> bytes:
        master = self._master_key(key_id)
        nonce, ciphertext = wrapped[:12], wrapped[12:]
        return AESGCM(master).decrypt(
            nonce,
            ciphertext,
            f"career-envelope:{key_id}".encode(),
        )


class AwsKmsProvider:
    name = "aws_kms"

    def __init__(self) -> None:
        if boto3 is None:
            raise EncryptionConfigurationError(
                "Install boto3 before selecting KEY_PROVIDER=aws_kms."
            )

        if not settings.aws_kms_key_id:
            raise EncryptionConfigurationError(
                "AWS_KMS_KEY_ID is required for KEY_PROVIDER=aws_kms."
            )

        self.client = boto3.client("kms", region_name=settings.aws_region)

    def generate_data_key(self) -> DataKey:
        response = self.client.generate_data_key(
            KeyId=settings.aws_kms_key_id,
            KeySpec="AES_256",
        )
        return DataKey(
            plaintext=bytes(response["Plaintext"]),
            wrapped=bytes(response["CiphertextBlob"]),
            key_id=str(response["KeyId"]),
            provider=self.name,
        )

    def decrypt_data_key(self, wrapped: bytes, key_id: str) -> bytes:
        response = self.client.decrypt(
            CiphertextBlob=wrapped,
            KeyId=key_id,
        )
        return bytes(response["Plaintext"])


class AzureKeyVaultProvider:
    """Envelope-key provider backed by an RSA key in Azure Key Vault."""

    name = "azure_key_vault"

    def __init__(self) -> None:
        if (
            DefaultAzureCredential is None
            or KeyClient is None
            or CryptographyClient is None
            or KeyWrapAlgorithm is None
        ):
            raise EncryptionConfigurationError(
                "Install Azure identity/key-vault dependencies before selecting "
                "KEY_PROVIDER=azure_key_vault."
            )

        if not settings.azure_key_vault_url or not settings.azure_key_name:
            raise EncryptionConfigurationError(
                "AZURE_KEY_VAULT_URL and AZURE_KEY_NAME are required for "
                "KEY_PROVIDER=azure_key_vault."
            )

        self.credential = DefaultAzureCredential()
        self.key_client = KeyClient(
            vault_url=settings.azure_key_vault_url,
            credential=self.credential,
        )

    def generate_data_key(self) -> DataKey:
        key = self.key_client.get_key(settings.azure_key_name)
        key_id = str(key.id)
        data_key = os.urandom(32)
        crypto = CryptographyClient(
            key,
            credential=self.credential,
        )
        wrapped = crypto.wrap_key(
            KeyWrapAlgorithm.rsa_oaep_256,
            data_key,
        ).encrypted_key

        return DataKey(
            plaintext=data_key,
            wrapped=bytes(wrapped),
            key_id=key_id,
            provider=self.name,
        )

    def decrypt_data_key(self, wrapped: bytes, key_id: str) -> bytes:
        crypto = CryptographyClient(
            key_id,
            credential=self.credential,
        )
        result = crypto.unwrap_key(
            KeyWrapAlgorithm.rsa_oaep_256,
            wrapped,
        )
        return bytes(result.key)


@lru_cache
def _current_provider() -> KeyProvider:
    if settings.key_provider == "local":
        return LocalKeyProvider()

    if settings.key_provider == "aws_kms":
        return AwsKmsProvider()

    if settings.key_provider == "azure_key_vault":
        return AzureKeyVaultProvider()

    raise EncryptionConfigurationError(
        "KEY_PROVIDER must be 'local', 'aws_kms', or 'azure_key_vault'."
    )


def _provider_for_name(name: str) -> KeyProvider:
    if name == "local":
        return LocalKeyProvider()

    if name == "aws_kms":
        return AwsKmsProvider()

    if name == "azure_key_vault":
        return AzureKeyVaultProvider()

    raise EncryptionConfigurationError(f"Unknown envelope provider: {name}")


def encrypt_text(value: str, aad: str) -> str:
    data_key = _current_provider().generate_data_key()
    nonce = os.urandom(12)
    ciphertext = AESGCM(data_key.plaintext).encrypt(
        nonce,
        value.encode("utf-8"),
        aad.encode("utf-8"),
    )
    envelope = {
        "v": 1,
        "provider": data_key.provider,
        "key_id": data_key.key_id,
        "wrapped_key": base64.urlsafe_b64encode(data_key.wrapped).decode("ascii"),
        "nonce": base64.urlsafe_b64encode(nonce).decode("ascii"),
        "ciphertext": base64.urlsafe_b64encode(ciphertext).decode("ascii"),
    }
    return base64.urlsafe_b64encode(
        json.dumps(envelope, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")


def _decrypt_legacy_phase3(value: str, aad: str) -> str:
    encoded_key = settings.legacy_profile_encryption_key.get_secret_value()

    if not encoded_key:
        raise ValueError("Legacy Phase-3 encryption key is not configured.")

    key = _b64decode(encoded_key)

    if len(key) != 32:
        raise EncryptionConfigurationError(
            "LEGACY_PROFILE_ENCRYPTION_KEY must decode to 32 bytes."
        )

    raw = base64.urlsafe_b64decode(value.encode("ascii"))
    nonce, ciphertext = raw[:12], raw[12:]
    return AESGCM(key).decrypt(
        nonce,
        ciphertext,
        aad.encode("utf-8"),
    ).decode("utf-8")


def decrypt_text(value: str, aad: str) -> str:
    try:
        decoded = base64.urlsafe_b64decode(value.encode("ascii"))
        envelope = json.loads(decoded.decode("utf-8"))

        if not isinstance(envelope, dict) or envelope.get("v") != 1:
            raise ValueError("Not a Phase-4 envelope.")

        provider = _provider_for_name(str(envelope["provider"]))
        data_key = provider.decrypt_data_key(
            base64.urlsafe_b64decode(envelope["wrapped_key"]),
            str(envelope["key_id"]),
        )
        plaintext = AESGCM(data_key).decrypt(
            base64.urlsafe_b64decode(envelope["nonce"]),
            base64.urlsafe_b64decode(envelope["ciphertext"]),
            aad.encode("utf-8"),
        )
        return plaintext.decode("utf-8")
    except EncryptionConfigurationError:
        raise
    except Exception as envelope_error:
        try:
            return _decrypt_legacy_phase3(value, aad)
        except Exception as legacy_error:
            raise ValueError(
                "Encrypted value could not be authenticated with Phase-4 "
                "or configured Phase-3 keys."
            ) from legacy_error


def rotate_ciphertext(value: str, aad: str) -> str:
    return encrypt_text(decrypt_text(value, aad), aad)
