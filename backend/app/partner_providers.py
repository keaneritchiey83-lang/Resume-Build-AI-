from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

import httpx

from app.config import settings
from app.schemas import PartnerJobRequest, ProviderResult


class ProviderAdapter(Protocol):
    async def publish(self, job: PartnerJobRequest) -> ProviderResult: ...


def _raise_provider_error(
    provider: str,
    response: httpx.Response,
    payload: Any,
) -> None:
    if response.is_error:
        raise RuntimeError(
            f"{provider} returned HTTP {response.status_code}: {str(payload)[:1000]}"
        )


class LinkedInApplyConnectAdapter:
    """Authorized LinkedIn Apply Connect / Job Posting API adapter."""

    endpoint = "https://api.linkedin.com/v2/simpleJobPostings"

    def __init__(self, credentials: dict[str, str]) -> None:
        self.access_token = credentials.get("access_token", "")
        self.organization_urn = credentials.get("organization_urn", "")
        self.webhook_url = credentials.get("job_application_webhook_url", "")
        self.version = credentials.get("linkedin_version", settings.linkedin_version)

        if not self.access_token or not self.organization_urn:
            raise ValueError(
                "LinkedIn requires access_token and organization_urn from an "
                "approved Apply Connect/Talent Solutions partnership."
            )

    async def publish(self, job: PartnerJobRequest) -> ProviderResult:
        element: dict[str, Any] = {
            "externalJobPostingId": job.external_job_id,
            "title": job.title,
            "description": job.description,
            "integrationContext": self.organization_urn,
            "listedAt": int(datetime.now(UTC).timestamp() * 1000),
            "jobPostingOperationType": job.operation,
            "location": job.location or job.city_region_postal,
            "availability": "PUBLIC",
        }

        if job.apply_url:
            element["companyApplyUrl"] = job.apply_url

        if job.poster_email:
            element["posterEmail"] = job.poster_email

        if self.webhook_url and job.operation != "CLOSE":
            element["onsiteApplyConfiguration"] = {
                "jobApplicationWebhookUrl": self.webhook_url,
            }

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "X-RestLi-Protocol-Version": "2.0.0",
            "LinkedIn-Version": self.version,
        }

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30, connect=5),
            follow_redirects=False,
        ) as client:
            response = await client.post(
                self.endpoint,
                headers=headers,
                json={"elements": [element]},
            )

        payload = response.json() if response.content else {}
        _raise_provider_error("linkedin", response, payload)
        elements = payload.get("elements", []) if isinstance(payload, dict) else []
        first = elements[0] if elements else {}
        return ProviderResult(
            provider="linkedin",
            status=str(first.get("status", response.status_code)),
            provider_job_id=str(first.get("id", "")),
            response=payload if isinstance(payload, dict) else {"raw": payload},
        )


class IndeedJobSyncAdapter:
    """Authorized Indeed Job Sync GraphQL adapter."""

    token_endpoint = "https://apis.indeed.com/oauth/v2/tokens"
    graphql_endpoint = "https://apis.indeed.com/graphql"

    CREATE_MUTATION = """
    mutation CreateSourcedJobPostings($input: CreateSourcedJobPostingsInput) {
      jobsIngest {
        createSourcedJobPostings(input: $input) {
          results {
            jobPosting {
              sourcedPostingId
              employerJobId
            }
          }
        }
      }
    }
    """

    EXPIRE_MUTATION = """
    mutation ExpireSourcedJobsBySourcedPostingId(
      $input: ExpireSourcedJobsBySourcedPostingIdInput!
    ) {
      jobsIngest {
        expireSourcedJobsBySourcedPostingId(input: $input) {
          results {
            trackingKey
          }
        }
      }
    }
    """

    def __init__(self, credentials: dict[str, str]) -> None:
        self.client_id = credentials.get("client_id", "")
        self.client_secret = credentials.get("client_secret", "")
        self.source_name = credentials.get("source_name", "")
        self.source_type = credentials.get("source_type", "Employer")
        self.employer_id = credentials.get("employer_id", "")

        if not self.client_id or not self.client_secret or not self.source_name:
            raise ValueError(
                "Indeed requires approved partner client_id, client_secret, "
                "and assigned source_name."
            )

    async def _token(self, client: httpx.AsyncClient) -> str:
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials",
            "scope": "employer_access",
        }

        if self.employer_id:
            data["employer"] = self.employer_id

        response = await client.post(
            self.token_endpoint,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data=data,
        )
        payload = response.json()
        _raise_provider_error("indeed-oauth", response, payload)
        token = payload.get("access_token", "")

        if not token:
            raise RuntimeError("Indeed OAuth response omitted access_token.")

        return str(token)

    async def _graphql(
        self,
        client: httpx.AsyncClient,
        token: str,
        query: str,
        variables: dict[str, Any],
    ) -> dict[str, Any]:
        response = await client.post(
            self.graphql_endpoint,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"query": query, "variables": variables},
        )
        payload = response.json()
        _raise_provider_error("indeed", response, payload)

        if payload.get("errors"):
            raise RuntimeError(
                "Indeed GraphQL error: " + str(payload["errors"])[:1500]
            )

        return payload

    async def publish(self, job: PartnerJobRequest) -> ProviderResult:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30, connect=5),
            follow_redirects=False,
        ) as client:
            token = await self._token(client)

            if job.operation == "CLOSE":
                if not job.provider_job_id:
                    raise ValueError(
                        "Indeed CLOSE requires provider_job_id=sourcedPostingId."
                    )

                payload = await self._graphql(
                    client,
                    token,
                    self.EXPIRE_MUTATION,
                    {
                        "input": {
                            "jobs": [
                                {"sourcedPostingId": job.provider_job_id}
                            ]
                        }
                    },
                )
                return ProviderResult(
                    provider="indeed",
                    status="accepted",
                    provider_job_id=job.provider_job_id,
                    response=payload,
                )

            public_job_url = job.public_job_url or job.apply_url

            if not public_job_url:
                raise ValueError(
                    "Indeed Job Sync requires public_job_url for the public "
                    "job description page."
                )

            location_value = job.city_region_postal or job.location

            if not location_value:
                raise ValueError(
                    "Indeed Job Sync requires a job location for this reference adapter."
                )

            body = {
                "title": job.title,
                "description": job.description,
                "descriptionFormatting": (
                    "RICH_FORMATTING"
                    if "<" in job.description and ">" in job.description
                    else "TEXT"
                ),
                "location": {
                    "country": job.country,
                    "cityRegionPostal": location_value,
                },
            }
            metadata = {
                "jobSource": {
                    "companyName": job.employer_name,
                    "sourceName": self.source_name,
                    "sourceType": self.source_type,
                },
                "jobPostingId": job.external_job_id,
                "datePublished": (
                    job.date_published or datetime.now(UTC)
                ).isoformat(),
                "url": public_job_url,
            }

            if job.company_website:
                metadata["jobSource"]["companyWebsite"] = job.company_website

            payload = await self._graphql(
                client,
                token,
                self.CREATE_MUTATION,
                {
                    "input": {
                        "jobPostings": [
                            {
                                "body": body,
                                "metadata": metadata,
                            }
                        ]
                    }
                },
            )
            results = (
                payload.get("data", {})
                .get("jobsIngest", {})
                .get("createSourcedJobPostings", {})
                .get("results", [])
            )
            posting = results[0].get("jobPosting", {}) if results else {}
            return ProviderResult(
                provider="indeed",
                status="accepted",
                provider_job_id=str(posting.get("sourcedPostingId", "")),
                response=payload,
            )


class ZipRecruiterPartnerAdapter:
    """Authorized ZipRecruiter Partner Jobs API adapter."""

    endpoint = "https://api.ziprecruiter.com/partner/v0/job"

    def __init__(self, credentials: dict[str, str]) -> None:
        self.api_key = credentials.get("api_key", "")
        self.employer_id = credentials.get("employer_id", "")

        if not self.api_key:
            raise ValueError(
                "ZipRecruiter requires the Jobs API key issued during partner onboarding."
            )

    async def publish(self, job: PartnerJobRequest) -> ProviderResult:
        headers = {
            "Authorization": f"Basic {self.api_key}",
            "Content-Type": "application/json",
        }
        endpoint = f"{self.endpoint}/{job.external_job_id}"

        if job.operation == "CLOSE":
            method = "DELETE"
            body = None
        else:
            method = "POST" if job.operation == "CREATE" else "PUT"
            endpoint = self.endpoint if method == "POST" else endpoint
            body = {
                "job_id": job.external_job_id,
                "title": job.title,
                "description": job.description,
                "employer_name": job.employer_name,
                "job_type": job.job_type,
            }

            if self.employer_id:
                body["employer_id"] = self.employer_id

            if job.city_region_postal:
                body["city"] = job.city_region_postal

            if job.apply_url:
                body["apply_url"] = job.apply_url

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30, connect=5),
            follow_redirects=False,
        ) as client:
            response = await client.request(
                method,
                endpoint,
                headers=headers,
                json=body,
            )

        payload = response.json() if response.content else {}
        _raise_provider_error("ziprecruiter", response, payload)
        provider_job_id = ""

        if isinstance(payload, dict):
            provider_job_id = str(
                payload.get("job", {}).get("job_id", job.external_job_id)
            )

        return ProviderResult(
            provider="ziprecruiter",
            status="accepted",
            provider_job_id=provider_job_id,
            response=payload if isinstance(payload, dict) else {"raw": payload},
        )


def build_provider_adapter(
    provider: str,
    credentials: dict[str, str],
) -> ProviderAdapter:
    if provider == "linkedin":
        return LinkedInApplyConnectAdapter(credentials)

    if provider == "indeed":
        return IndeedJobSyncAdapter(credentials)

    if provider == "ziprecruiter":
        return ZipRecruiterPartnerAdapter(credentials)

    raise ValueError(
        "Supported Phase-4 partner providers are linkedin, indeed, and ziprecruiter."
    )


PROVIDER_CAPABILITIES = {
    "linkedin": {
        "integration": "Apply Connect / Job Posting API",
        "capabilities": ["publish_jobs", "update_jobs", "close_jobs"],
        "general_job_search_feed": False,
        "application_webhook_adapter_implemented": True,
        "approval_required": True,
    },
    "indeed": {
        "integration": "Job Sync API",
        "capabilities": ["publish_jobs", "upsert_jobs", "expire_jobs"],
        "general_job_search_feed": False,
        "application_webhook_adapter_implemented": True,
        "approval_required": True,
    },
    "ziprecruiter": {
        "integration": "Partner Jobs API",
        "capabilities": ["publish_jobs", "update_jobs", "close_jobs"],
        "general_job_search_feed": False,
        "application_webhook_adapter_implemented": True,
        "approval_required": True,
    },
}
