from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx

from app.config import settings


@dataclass(slots=True)
class JobRecord:
    id: str
    source: str
    external_id: str
    title: str
    organization: str = ""
    location: str = ""
    description: str = ""
    apply_url: str = ""
    posted_at: datetime | None = None
    expires_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class JobConnector(Protocol):
    async def search(
        self,
        keyword: str,
        location: str = "",
        limit: int = 100,
    ) -> list[JobRecord]: ...


def make_job_id(source: str, external_id: str) -> str:
    return hashlib.sha256(f"{source}:{external_id}".encode()).hexdigest()


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None

    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))

        if result.tzinfo is None:
            result = result.replace(tzinfo=UTC)

        return result
    except ValueError:
        return None


class USAJobsConnector:
    base_url = "https://data.usajobs.gov/api/search"

    async def search(
        self,
        keyword: str,
        location: str = "",
        limit: int = 100,
    ) -> list[JobRecord]:
        api_key = settings.usajobs_api_key.get_secret_value()

        if not api_key or not settings.usajobs_user_agent:
            raise RuntimeError(
                "USAJOBS_API_KEY and USAJOBS_USER_AGENT are not configured."
            )

        params: dict[str, Any] = {
            "Keyword": keyword,
            "ResultsPerPage": min(limit, 500),
        }

        if location:
            params["LocationName"] = location

        headers = {
            "Host": "data.usajobs.gov",
            "User-Agent": settings.usajobs_user_agent,
            "Authorization-Key": api_key,
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(25, connect=5),
            follow_redirects=False,
        ) as client:
            response = await client.get(
                self.base_url,
                params=params,
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()

        records: list[JobRecord] = []

        for item in payload.get("SearchResult", {}).get("SearchResultItems", []):
            descriptor = item.get("MatchedObjectDescriptor", {})
            details = descriptor.get("UserArea", {}).get("Details", {})
            external_id = str(
                item.get("MatchedObjectId")
                or descriptor.get("PositionID")
                or descriptor.get("PositionURI")
                or ""
            )

            if not external_id:
                continue

            records.append(
                JobRecord(
                    id=make_job_id("usajobs", external_id),
                    source="usajobs",
                    external_id=external_id,
                    title=str(descriptor.get("PositionTitle", "Untitled")),
                    organization=str(descriptor.get("OrganizationName", "")),
                    location=str(descriptor.get("PositionLocationDisplay", "")),
                    description=str(
                        details.get("JobSummary")
                        or descriptor.get("QualificationSummary", "")
                    ),
                    apply_url=str(descriptor.get("PositionURI", "")),
                    posted_at=parse_datetime(descriptor.get("PublicationStartDate")),
                    expires_at=parse_datetime(descriptor.get("ApplicationCloseDate")),
                    metadata={"position_id": descriptor.get("PositionID")},
                )
            )

        return records


class AuthorizedPartnerConnector:
    """Boundary for partner-only sources. It intentionally does not scrape."""

    def __init__(self, source: str) -> None:
        self.source = source

    async def search(
        self,
        keyword: str,
        location: str = "",
        limit: int = 100,
    ) -> list[JobRecord]:
        raise RuntimeError(
            f"{self.source} connector requires approved API/feed credentials "
            "and a provider-specific implementation."
        )


CONNECTOR_REGISTRY = {
    "usajobs": {
        "status": "implemented",
        "mode": "official_api",
    },
    "linkedin": {
        "status": "authorization_required",
        "mode": "partner_api",
    },
    "indeed": {
        "status": "authorization_required",
        "mode": "partner_api",
    },
    "ziprecruiter": {
        "status": "authorization_required",
        "mode": "partner_api_or_feed",
    },
    "careerbuilder": {
        "status": "authorization_required",
        "mode": "authorized_api_or_feed",
    },
    "clearancejobs": {
        "status": "authorization_required",
        "mode": "authorized_api_or_feed",
    },
    "monster": {
        "status": "authorization_required",
        "mode": "authorized_api_or_feed",
    },
}
