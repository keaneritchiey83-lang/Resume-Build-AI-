from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crypto import decrypt_text, encrypt_text
from app.models import LearningCatalogItem, LearningProviderConnection


SUPPORTED_PROVIDERS = {
    "open_edx",
    "udemy_business",
    "coursera_enterprise",
    "generic_authorized_catalog",
}


def validate_learning_base_url(value: str) -> str:
    parsed = urlparse(value.strip())

    if not parsed.hostname:
        raise ValueError("Learning provider base URL requires a hostname.")

    hostname = parsed.hostname.lower()
    allowed = settings.learning_provider_allowed_host_set

    if hostname not in allowed and not any(
        hostname.endswith(f".{allowed_host}") for allowed_host in allowed
    ):
        raise ValueError(
            "Learning provider hostname is not in LEARNING_PROVIDER_ALLOWED_HOSTS."
        )

    is_local = hostname in {"localhost", "127.0.0.1"}

    if parsed.scheme != "https" and not (is_local and parsed.scheme == "http"):
        raise ValueError("Learning provider endpoints must use HTTPS.")

    return value.rstrip("/")


def _connection_aad(connection_id: str) -> str:
    return f"learning-provider:{connection_id}"


def _credentials(connection: LearningProviderConnection) -> dict[str, Any]:
    if not connection.encrypted_credentials:
        return {}

    value = decrypt_text(
        connection.encrypted_credentials,
        aad=_connection_aad(connection.id),
    )
    result = json.loads(value)

    if not isinstance(result, dict):
        raise ValueError("Stored learning-provider credentials are invalid.")

    return result


def _headers(credentials: dict[str, Any]) -> dict[str, str]:
    result = {"Accept": "application/json"}
    auth_type = str(credentials.get("auth_type", "")).lower()

    if auth_type == "bearer":
        token = str(credentials.get("token", ""))

        if not token:
            raise ValueError("Bearer authentication requires token.")

        result["Authorization"] = f"Bearer {token}"

    elif auth_type == "basic":
        import base64

        username = str(credentials.get("username", ""))
        password = str(credentials.get("password", ""))

        if not username or not password:
            raise ValueError("Basic authentication requires username and password.")

        encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
        result["Authorization"] = f"Basic {encoded}"

    elif auth_type == "api_key":
        header_name = str(credentials.get("header_name", "")).strip()
        api_key = str(credentials.get("api_key", ""))

        if not header_name or not api_key:
            raise ValueError("API-key authentication requires header_name and api_key.")

        if header_name.lower() in {"host", "content-length", "transfer-encoding"}:
            raise ValueError("Unsafe API-key header name.")

        result[header_name] = api_key

    elif auth_type not in {"", "none"}:
        raise ValueError("Unsupported learning-provider authentication type.")

    return result


async def create_or_update_connection(
    session: AsyncSession,
    organization_id: str,
    provider: str,
    base_url: str,
    credentials: dict[str, Any],
    enabled: bool,
    metadata: dict[str, Any],
) -> LearningProviderConnection:
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError("Unsupported learning-provider connector.")

    safe_url = validate_learning_base_url(base_url)

    connection = await session.scalar(
        select(LearningProviderConnection).where(
            LearningProviderConnection.organization_id == organization_id,
            LearningProviderConnection.provider == provider,
            LearningProviderConnection.base_url == safe_url,
        )
    )

    if connection is None:
        connection = LearningProviderConnection(
            organization_id=organization_id,
            provider=provider,
            base_url=safe_url,
            enabled=enabled,
            metadata_json=metadata,
        )
        session.add(connection)
        await session.flush()
    else:
        connection.enabled = enabled
        connection.metadata_json = metadata

    if credentials:
        connection.encrypted_credentials = encrypt_text(
            json.dumps(credentials, separators=(",", ":")),
            aad=_connection_aad(connection.id),
        )

    await session.commit()
    await session.refresh(connection)
    return connection


def _item_from_open_edx(
    item: dict[str, Any],
    base_url: str,
) -> dict[str, Any] | None:
    external_id = str(item.get("id") or item.get("course_id") or "").strip()
    title = str(item.get("name") or "").strip()

    if not external_id or not title:
        return None

    media = item.get("media", {})
    course_image = (
        media.get("course_image", {})
        if isinstance(media, dict)
        else {}
    )

    return {
        "external_id": external_id,
        "title": title,
        "description": str(item.get("overview") or item.get("description") or ""),
        "learning_type": "course",
        "skills": [],
        "level": "",
        "language": str(item.get("language") or ""),
        "duration_hours": None,
        "credential_offered": False,
        "source_url": urljoin(base_url + "/", f"courses/{external_id}"),
        "provenance": {
            "source_api": "/api/courses/v1/courses/",
            "org": item.get("org"),
            "number": item.get("number"),
            "start": item.get("start"),
            "end": item.get("end"),
            "course_image": course_image.get("uri") if isinstance(course_image, dict) else None,
        },
    }


def _mapping_value(item: dict[str, Any], path: str) -> Any:
    value: Any = item

    for segment in path.split("."):
        if not isinstance(value, dict):
            return None

        value = value.get(segment)

    return value


def _item_from_configured_mapping(
    item: dict[str, Any],
    mapping: dict[str, str],
    base_url: str,
) -> dict[str, Any] | None:
    external_id = str(
        _mapping_value(item, mapping.get("id", "id")) or ""
    ).strip()
    title = str(
        _mapping_value(item, mapping.get("title", "title")) or ""
    ).strip()

    if not external_id or not title:
        return None

    skills_value = _mapping_value(item, mapping.get("skills", "skills"))
    skills = (
        [str(value) for value in skills_value if str(value).strip()]
        if isinstance(skills_value, list)
        else []
    )

    url_value = str(
        _mapping_value(item, mapping.get("url", "url")) or ""
    ).strip()

    return {
        "external_id": external_id,
        "title": title,
        "description": str(
            _mapping_value(item, mapping.get("description", "description")) or ""
        ),
        "learning_type": str(
            _mapping_value(item, mapping.get("learning_type", "learning_type"))
            or "course"
        ),
        "skills": skills,
        "level": str(_mapping_value(item, mapping.get("level", "level")) or ""),
        "language": str(
            _mapping_value(item, mapping.get("language", "language")) or ""
        ),
        "duration_hours": None,
        "credential_offered": bool(
            _mapping_value(
                item,
                mapping.get("credential_offered", "credential_offered"),
            )
        ),
        "source_url": urljoin(base_url + "/", url_value) if url_value else base_url,
        "provenance": {"configured_mapping": mapping},
    }


async def fetch_catalog(
    connection: LearningProviderConnection,
    query: str = "",
    limit: int = 100,
) -> list[dict[str, Any]]:
    base_url = validate_learning_base_url(connection.base_url)
    credentials = _credentials(connection)
    headers = _headers(credentials)
    metadata = connection.metadata_json or {}

    if connection.provider == "open_edx":
        path = "/api/courses/v1/courses/"
        params: dict[str, Any] = {
            "page_size": min(limit, 100),
            "active_only": "true",
        }

        if query:
            params["search_term"] = query

        mapping = None
    else:
        path = str(metadata.get("catalog_path", "")).strip()

        if not path.startswith("/"):
            raise ValueError(
                "Enterprise/generic learning providers require metadata.catalog_path."
            )

        params = {
            str(metadata.get("query_parameter", "search")): query,
            str(metadata.get("limit_parameter", "limit")): min(limit, 100),
        }
        mapping = metadata.get("field_mapping")

        if not isinstance(mapping, dict):
            raise ValueError(
                "Enterprise/generic learning providers require metadata.field_mapping."
            )

    url = urljoin(base_url + "/", path.lstrip("/"))

    # urljoin can change the host if path is malformed; revalidate the resolved URL.
    validate_learning_base_url(
        f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    )

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(20, connect=5),
        follow_redirects=False,
    ) as client:
        response = await client.get(
            url,
            headers=headers,
            params=params,
        )
        response.raise_for_status()
        payload = response.json()

    if connection.provider == "open_edx":
        if isinstance(payload, dict):
            items = payload.get("results", payload.get("courses", []))
        else:
            items = payload
    else:
        items_path = str(metadata.get("items_path", "results"))
        items = _mapping_value(payload, items_path) if isinstance(payload, dict) else payload

    if not isinstance(items, list):
        raise ValueError("Learning provider catalog response does not contain a list.")

    result: list[dict[str, Any]] = []

    for raw in items[:limit]:
        if not isinstance(raw, dict):
            continue

        normalized = (
            _item_from_open_edx(raw, base_url)
            if connection.provider == "open_edx"
            else _item_from_configured_mapping(raw, mapping or {}, base_url)
        )

        if normalized:
            result.append(normalized)

    return result


async def sync_connection(
    session: AsyncSession,
    connection: LearningProviderConnection,
    query: str = "",
) -> int:
    if not connection.enabled:
        return 0

    records = await fetch_catalog(connection, query=query)

    for record in records:
        statement = insert(LearningCatalogItem).values(
            organization_id=connection.organization_id,
            connection_id=connection.id,
            provider=connection.provider,
            external_id=record["external_id"],
            title=record["title"],
            description=record["description"],
            learning_type=record["learning_type"],
            skills=record["skills"],
            level=record["level"],
            language=record["language"],
            duration_hours=record["duration_hours"],
            credential_offered=record["credential_offered"],
            source_url=record["source_url"],
            provenance_json={
                **record["provenance"],
                "connection_id": connection.id,
                "synced_at": datetime.now(UTC).isoformat(),
            },
            updated_at=datetime.now(UTC),
        )
        statement = statement.on_conflict_do_update(
            index_elements=[
                LearningCatalogItem.organization_id,
                LearningCatalogItem.provider,
                LearningCatalogItem.external_id,
            ],
            set_={
                "connection_id": statement.excluded.connection_id,
                "title": statement.excluded.title,
                "description": statement.excluded.description,
                "learning_type": statement.excluded.learning_type,
                "skills": statement.excluded.skills,
                "level": statement.excluded.level,
                "language": statement.excluded.language,
                "duration_hours": statement.excluded.duration_hours,
                "credential_offered": statement.excluded.credential_offered,
                "source_url": statement.excluded.source_url,
                "provenance_json": statement.excluded.provenance_json,
                "updated_at": statement.excluded.updated_at,
            },
        )
        await session.execute(statement)

    connection.last_sync_at = datetime.now(UTC)
    await session.commit()
    return len(records)


async def search_learning_catalog(
    session: AsyncSession,
    organization_id: str,
    query: str,
    skills: list[str],
    limit: int,
) -> list[LearningCatalogItem]:
    statement = select(LearningCatalogItem).where(
        LearningCatalogItem.organization_id == organization_id
    )

    if query:
        pattern = f"%{query.strip()}%"
        statement = statement.where(
            or_(
                LearningCatalogItem.title.ilike(pattern),
                LearningCatalogItem.description.ilike(pattern),
            )
        )

    candidates = list(
        (
            await session.scalars(
                statement.order_by(LearningCatalogItem.updated_at.desc()).limit(
                    max(limit * 5, 100)
                )
            )
        ).all()
    )

    wanted = {value.strip().lower() for value in skills if value.strip()}

    if wanted:
        candidates = [
            item
            for item in candidates
            if wanted.intersection(
                {skill.strip().lower() for skill in item.skills}
            )
        ]

    return candidates[:limit]
