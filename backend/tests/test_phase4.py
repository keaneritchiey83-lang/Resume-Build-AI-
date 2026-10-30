import pytest

from app.partner_providers import (
    IndeedJobSyncAdapter,
    LinkedInApplyConnectAdapter,
    ZipRecruiterPartnerAdapter,
)
from app.tenancy import normalized_slug


def test_normalized_slug() -> None:
    assert normalized_slug("  Global Career AI, Inc.  ") == "global-career-ai-inc"


def test_linkedin_requires_partner_credentials() -> None:
    with pytest.raises(ValueError):
        LinkedInApplyConnectAdapter({})


def test_indeed_requires_partner_credentials() -> None:
    with pytest.raises(ValueError):
        IndeedJobSyncAdapter(
            {
                "client_id": "id",
                "client_secret": "secret",
            }
        )


def test_ziprecruiter_requires_partner_credentials() -> None:
    with pytest.raises(ValueError):
        ZipRecruiterPartnerAdapter({})


def test_provider_adapters_accept_structural_credentials() -> None:
    LinkedInApplyConnectAdapter(
        {
            "access_token": "token",
            "organization_urn": "urn:li:organization:123",
        }
    )
    IndeedJobSyncAdapter(
        {
            "client_id": "id",
            "client_secret": "secret",
            "source_name": "assigned-source",
        }
    )
    ZipRecruiterPartnerAdapter({"api_key": "issued-key"})
