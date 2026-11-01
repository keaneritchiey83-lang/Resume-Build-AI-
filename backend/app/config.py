from __future__ import annotations

import json
from functools import cached_property

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    # Phase 14 fail-closed controls: never ship signing keys in source control.
    phase14_enabled: bool = False
    phase14_token_signing_key_pem_b64: SecretStr = SecretStr("")
    phase14_memory_master_key_b64: SecretStr = SecretStr("")
    phase14_agent_trust_edges_json: SecretStr = SecretStr("[]")
    phase14_metrics_bearer_token: SecretStr = SecretStr("")
    phase14_region_id: str = "local-dev"

    database_url: str = (
        "postgresql+asyncpg://career:career@postgres:5432/career"
    )
    redis_url: str = "redis://redis:6379/0"

    jwt_secret: SecretStr = SecretStr("")
    oidc_session_secret: SecretStr = SecretStr("")
    cookie_secure: bool = False
    cors_origins: str = "http://localhost:5173"
    admin_emails: str = ""

    oidc_issuer_url: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: SecretStr = SecretStr("")
    oidc_redirect_uri: str = "http://localhost:8000/v1/auth/oidc/callback"
    oidc_scopes: str = "openid profile email"
    oidc_require_verified_email: bool = True

    key_provider: str = "local"
    legacy_profile_encryption_key: SecretStr = SecretStr("")
    local_current_key_id: str = "local-v1"
    local_master_keys_json: SecretStr = SecretStr("{}")
    aws_kms_key_id: str = ""
    aws_region: str = "us-east-1"
    azure_key_vault_url: str = ""
    azure_key_name: str = ""

    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = "gpt-5.6"

    onet_api_key: SecretStr = SecretStr("")
    esco_base_url: str = "https://ec.europa.eu/esco/api"
    esco_version: str = "1.2.0"
    esco_language: str = "en"

    usajobs_api_key: SecretStr = SecretStr("")
    usajobs_user_agent: str = ""

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimensions: int = 384

    scheduler_enabled: bool = False
    sync_interval_hours: int = 12
    career_seed_terms: str = (
        "software engineer,cybersecurity,data analyst,"
        "project manager,nurse,teacher"
    )
    job_seed_terms: str = (
        "software engineer,cybersecurity,data analyst,project manager"
    )

    linkedin_version: str = "202609"

    webhook_max_body_bytes: int = 32 * 1024 * 1024
    webhook_replay_window_seconds: int = 15
    webhook_event_retention_days: int = 30
    candidate_retention_days: int = 365
    celery_broker_url: str = ""
    celery_result_backend: str = ""

    agent_monitor_enabled: bool = True
    agent_monitor_interval_minutes: int = 15
    agent_auto_analysis_limit: int = 3
    agent_default_match_threshold: float = 65.0
    agent_consent_version: str = "2026-09"
    analytics_retention_days: int = 730

    otel_enabled: bool = False
    otel_service_name: str = "global-career-ai"
    otel_exporter_otlp_endpoint: str = ""
    otel_exporter_otlp_headers: str = ""
    deployment_environment: str = "development"
    security_log_level: str = "INFO"


    opa_url: str = ""
    opa_fail_closed: bool = True
    phase7_fairness_min_group_size: int = 20
    phase7_evidence_interval_hours: int = 24

    credential_remote_verifier_url: str = ""
    credential_remote_verifier_token: SecretStr = SecretStr("")
    learning_provider_allowed_hosts: str = "localhost,127.0.0.1"
    phase8_learning_sync_hours: int = 24
    phase8_evidence_interval_hours: int = 24
    phase8_portfolio_default_share_days: int = 30
    phase8_labor_min_points: int = 4
    bls_api_key: SecretStr = SecretStr("")

    phase9_dsar_due_days: int = 30
    phase9_retention_interval_hours: int = 24
    phase9_continuous_control_interval_hours: int = 6
    phase9_privacy_review_days: int = 365
    phase9_portable_record_issuer: str = "https://global-career.example/issuers/unsigned-export"

    phase10_public_base_url: str = "http://localhost:8000"
    phase10_access_token_seconds: int = 600
    phase10_credential_valid_days: int = 365
    phase10_daily_epsilon_limit: float = 2.0
    phase10_audit_ed25519_private_key: SecretStr = SecretStr("")
    phase10_audit_signing_key_id: str = "phase10-audit-v1"
    phase10_privacy_scan_hours: int = 24
    phase10_audit_verify_hours: int = 6
    phase10_protocol_cleanup_hours: int = 1

    phase11_webauthn_rp_id: str = "localhost"
    phase11_webauthn_rp_name: str = "Global Career Architecture AI"
    phase11_webauthn_origins: str = "http://localhost:5173"
    phase11_webauthn_challenge_seconds: int = 300
    phase11_did_web_allowed_hosts: str = ""
    phase11_mdoc_verifier_url: str = ""
    phase11_mdoc_verifier_token: SecretStr = SecretStr("")


    phase12_federation_remote_allowed_hosts: str = ""
    phase12_federation_max_chain_depth: int = 8
    phase12_wallet_attestation_clock_skew_seconds: int = 60
    phase12_require_hsm_signing: bool = False
    phase12_confidential_inference_url: str = ""
    phase12_confidential_inference_token: SecretStr = SecretStr("")
    phase12_confidential_inference_allowed_hosts: str = ""
    phase12_confidential_attestation_max_age_seconds: int = 300
    phase12_spiffe_trust_domain: str = "career.internal"
    phase12_spiffe_endpoint_socket: str = "unix:///run/spire/sockets/agent.sock"
    phase12_spiffe_required: bool = False
    phase12_runtime_sensor_token: SecretStr = SecretStr("")
    phase12_runtime_event_retention_days: int = 90
    phase13_region_id: str = "local-dev"
    phase13_region_name: str = "Local Development"
    phase13_region_cloud: str = "local"
    phase13_region_jurisdiction: str = ""
    phase13_peer_bundle_allowed_hosts: str = ""
    phase13_transparency_external_url: str = ""
    phase13_transparency_external_allowed_hosts: str = "rekor.sigstore.dev"
    phase13_trust_snapshot_hours: int = 6
    phase13_trust_snapshot_retention_days: int = 180
    phase13_trust_snapshot_ed25519_private_key: SecretStr = SecretStr("")
    phase13_model_gateway_allowed_models: str = "gpt-5.6"
    phase13_model_gateway_max_input_chars: int = 50000
    phase13_model_gateway_max_output_tokens: int = 4000
    phase13_prompt_injection_block_score: int = 70
    phase13_confidential_rag_max_documents: int = 6
    phase13_agent_manifest_required: bool = True
    phase13_release_ed25519_private_key: SecretStr = SecretStr("")
    phase13_release_signing_key_id: str = "phase13-release-v1"

    @cached_property
    def phase13_peer_bundle_allowed_host_set(self) -> set[str]:
        return {
            item.strip().lower()
            for item in self.phase13_peer_bundle_allowed_hosts.split(",")
            if item.strip()
        }

    @cached_property
    def phase13_transparency_external_allowed_host_set(self) -> set[str]:
        return {
            item.strip().lower()
            for item in self.phase13_transparency_external_allowed_hosts.split(",")
            if item.strip()
        }

    @cached_property
    def phase13_model_gateway_allowed_model_set(self) -> set[str]:
        return {
            item.strip()
            for item in self.phase13_model_gateway_allowed_models.split(",")
            if item.strip()
        }

    @cached_property
    def phase12_federation_remote_allowed_host_set(self) -> set[str]:
        return {
            item.strip().lower()
            for item in self.phase12_federation_remote_allowed_hosts.split(",")
            if item.strip()
        }

    @cached_property
    def phase12_confidential_inference_allowed_host_set(self) -> set[str]:
        return {
            item.strip().lower()
            for item in self.phase12_confidential_inference_allowed_hosts.split(",")
            if item.strip()
        }

    @cached_property
    def phase11_webauthn_origin_list(self) -> list[str]:
        return [
            item.strip()
            for item in self.phase11_webauthn_origins.split(",")
            if item.strip()
        ]

    @cached_property
    def phase11_did_web_allowed_host_set(self) -> set[str]:
        return {
            item.strip().lower()
            for item in self.phase11_did_web_allowed_hosts.split(",")
            if item.strip()
        }

    @cached_property
    def learning_provider_allowed_host_set(self) -> set[str]:
        return {
            item.strip().lower()
            for item in self.learning_provider_allowed_hosts.split(",")
            if item.strip()
        }

    @cached_property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @cached_property
    def admin_email_set(self) -> set[str]:
        return {
            item.strip().lower()
            for item in self.admin_emails.split(",")
            if item.strip()
        }

    @cached_property
    def career_seeds(self) -> list[str]:
        return [
            item.strip()
            for item in self.career_seed_terms.split(",")
            if item.strip()
        ]

    @cached_property
    def job_seeds(self) -> list[str]:
        return [
            item.strip()
            for item in self.job_seed_terms.split(",")
            if item.strip()
        ]

    @cached_property
    def local_master_keys(self) -> dict[str, str]:
        try:
            value = json.loads(self.local_master_keys_json.get_secret_value())
        except json.JSONDecodeError as exc:
            raise RuntimeError("LOCAL_MASTER_KEYS_JSON must be valid JSON.") from exc

        if not isinstance(value, dict):
            raise RuntimeError("LOCAL_MASTER_KEYS_JSON must be a JSON object.")

        return {str(key): str(secret) for key, secret in value.items()}


settings = Settings()
