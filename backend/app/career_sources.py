from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import settings


@dataclass(slots=True)
class ConceptRecord:
    source: str
    external_id: str
    kind: str
    title: str
    description: str = ""
    source_url: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class ONetClient:
    base_url = "https://api-v2.onetcenter.org"

    async def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        api_key = settings.onet_api_key.get_secret_value()

        if not api_key:
            raise RuntimeError("ONET_API_KEY is not configured.")

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(20, connect=5),
            follow_redirects=False,
        ) as client:
            response = await client.get(
                f"{self.base_url}{path}",
                params=params,
                headers={
                    "X-API-Key": api_key,
                    "Accept": "application/json",
                },
            )
            response.raise_for_status()
            return response.json()

    async def search_occupations(
        self,
        keyword: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        payload = await self._get(
            "/online/search",
            {
                "keyword": keyword,
                "start": 1,
                "end": min(limit, 20),
            },
        )
        return list(payload.get("occupation", []))

    async def descriptor(
        self,
        occupation_code: str,
        descriptor_type: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        if descriptor_type not in {"skills", "abilities"}:
            raise ValueError("Descriptor type must be skills or abilities.")

        payload = await self._get(
            (
                f"/online/occupations/{occupation_code}/summary/"
                f"{descriptor_type}"
            ),
            {"start": 1, "end": limit},
        )
        return list(payload.get("element", []))


class ESCOClient:
    async def search(
        self,
        text: str,
        concept_type: str,
        limit: int = 20,
    ) -> list[ConceptRecord]:
        if concept_type not in {"occupation", "skill"}:
            raise ValueError("ESCO type must be occupation or skill.")

        params: dict[str, Any] = {
            "text": text,
            "type": concept_type,
            "language": settings.esco_language,
            "limit": limit,
            "offset": 0,
            "full": "true",
        }

        if settings.esco_version:
            params["selectedVersion"] = settings.esco_version

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(20, connect=5),
            follow_redirects=False,
        ) as client:
            response = await client.get(
                f"{settings.esco_base_url.rstrip('/')}/search",
                params=params,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()

        embedded = payload.get("_embedded", {})
        candidates = [
            payload.get("results"),
            payload.get("items"),
            embedded.get("results"),
            embedded.get("concepts"),
        ]
        items = next(
            (value for value in candidates if isinstance(value, list)),
            [],
        )

        records: list[ConceptRecord] = []

        for item in items:
            if not isinstance(item, dict):
                continue

            uri = str(
                item.get("uri")
                or item.get("_links", {}).get("self", {}).get("href", "")
            )
            title = self._label(
                item.get("title")
                or item.get("preferredLabel")
                or item.get("label")
            )
            description = self._label(
                item.get("description")
                or item.get("definition")
                or item.get("scopeNote")
            )

            if uri and title:
                records.append(
                    ConceptRecord(
                        source="esco",
                        external_id=uri,
                        kind=concept_type,
                        title=title,
                        description=description,
                        source_url=uri,
                        metadata={"language": settings.esco_language},
                    )
                )

        return records

    @staticmethod
    def _label(value: Any) -> str:
        if isinstance(value, str):
            return value.strip()

        if isinstance(value, dict):
            preferred = value.get(settings.esco_language)

            if isinstance(preferred, str):
                return preferred.strip()

            return next(
                (
                    item.strip()
                    for item in value.values()
                    if isinstance(item, str) and item.strip()
                ),
                "",
            )

        if isinstance(value, list):
            return " ".join(str(item) for item in value if item).strip()

        return ""
