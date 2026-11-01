from __future__ import annotations

import math
import statistics
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import LaborMarketObservation, LaborTrendSnapshot
from app.schemas import BLSSeriesImportRequest, LaborObservationIn


METHOD_VERSION = "phase8-linear-trend-v1"
BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"


def period_position(period: str) -> float:
    text = period.strip().upper()

    if len(text) == 4 and text.isdigit():
        return float(text)

    if "-M" in text:
        year_text, month_text = text.split("-M", 1)
        year = int(year_text)
        month = int(month_text)

        if month == 13:
            return float(year) + 0.999

        if not 1 <= month <= 12:
            raise ValueError(f"Unsupported month in period {period!r}.")

        return year + (month - 1) / 12

    if "-Q" in text:
        year_text, quarter_text = text.split("-Q", 1)
        year = int(year_text)
        quarter = int(quarter_text)

        if not 1 <= quarter <= 4:
            raise ValueError(f"Unsupported quarter in period {period!r}.")

        return year + (quarter - 1) / 4

    raise ValueError(
        "Period must use YYYY, YYYY-M01..M12, or YYYY-Q1..Q4."
    )


def _linear_slope(points: list[tuple[float, float]]) -> float:
    xs = [item[0] for item in points]
    ys = [item[1] for item in points]
    x_mean = statistics.fmean(xs)
    y_mean = statistics.fmean(ys)
    numerator = sum(
        (x - x_mean) * (y - y_mean)
        for x, y in points
    )
    denominator = sum((x - x_mean) ** 2 for x in xs)

    return numerator / denominator if denominator else 0.0


def _volatility(values: list[float]) -> float:
    changes: list[float] = []

    for previous, current in zip(values, values[1:], strict=False):
        if previous == 0:
            continue

        changes.append((current - previous) / abs(previous))

    if len(changes) < 2:
        return 0.0

    return statistics.pstdev(changes)


def compute_trend(
    periods_and_values: list[tuple[str, float]],
) -> dict[str, Any]:
    if len(periods_and_values) < 2:
        raise ValueError("At least two observations are required.")

    points = sorted(
        (
            (period_position(period), period, float(value))
            for period, value in periods_and_values
        ),
        key=lambda item: item[0],
    )

    unique: dict[float, tuple[str, float]] = {}

    for position, period, value in points:
        unique[position] = (period, value)

    points = [
        (position, period, value)
        for position, (period, value) in sorted(unique.items())
    ]

    if len(points) < 2:
        raise ValueError("At least two unique observation periods are required.")

    regression_points = [(position, value) for position, _, value in points]
    slope = _linear_slope(regression_points)
    start_position, start_period, start_value = points[0]
    end_position, end_period, end_value = points[-1]
    span_years = max(end_position - start_position, 0.0)

    annualized_change: float | None = None

    if span_years > 0 and start_value > 0 and end_value >= 0:
        annualized_change = (end_value / start_value) ** (1 / span_years) - 1

    values = [value for _, _, value in points]
    volatility = _volatility(values)

    baseline = abs(statistics.fmean(values)) or 1.0
    relative_slope = slope / baseline

    if relative_slope > 0.02:
        direction = "increasing"
    elif relative_slope < -0.02:
        direction = "decreasing"
    else:
        direction = "stable"

    coverage = min(1.0, len(points) / 8)
    span_factor = min(1.0, max(span_years, 0.25) / 4)
    stability = max(0.2, 1.0 - min(volatility, 0.8))
    confidence = round(
        min(0.95, max(0.1, (0.45 * coverage) + (0.35 * span_factor) + (0.20 * stability))),
        3,
    )

    projected_next = max(0.0, end_value + slope)

    return {
        "input_count": len(points),
        "start_period": start_period,
        "end_period": end_period,
        "start_value": start_value,
        "end_value": end_value,
        "linear_slope": round(slope, 6),
        "annualized_change": (
            round(annualized_change, 6)
            if annualized_change is not None and math.isfinite(annualized_change)
            else None
        ),
        "volatility": round(volatility, 6),
        "direction": direction,
        "confidence": confidence,
        "projected_next_value": round(projected_next, 6),
    }


async def upsert_observation(
    session: AsyncSession,
    payload: LaborObservationIn,
) -> None:
    period_position(payload.period)

    statement = insert(LaborMarketObservation).values(
        source=payload.source,
        data_vintage=payload.data_vintage,
        country_code=payload.country_code.upper(),
        region_code=payload.region_code,
        occupation_code=payload.occupation_code,
        occupation_title=payload.occupation_title,
        metric=payload.metric,
        period=payload.period,
        value=payload.value,
        unit=payload.unit,
        source_url=payload.source_url,
        license=payload.license,
        metadata_json=payload.metadata,
        captured_at=datetime.now(UTC),
    )
    statement = statement.on_conflict_do_update(
        index_elements=[
            LaborMarketObservation.source,
            LaborMarketObservation.country_code,
            LaborMarketObservation.region_code,
            LaborMarketObservation.occupation_code,
            LaborMarketObservation.metric,
            LaborMarketObservation.period,
        ],
        set_={
            "data_vintage": statement.excluded.data_vintage,
            "occupation_title": statement.excluded.occupation_title,
            "value": statement.excluded.value,
            "unit": statement.excluded.unit,
            "source_url": statement.excluded.source_url,
            "license": statement.excluded.license,
            "metadata_json": statement.excluded.metadata_json,
            "captured_at": statement.excluded.captured_at,
        },
    )
    await session.execute(statement)
    await session.commit()


async def build_trend_snapshot(
    session: AsyncSession,
    source: str,
    country_code: str,
    region_code: str,
    occupation_code: str,
    metric: str,
) -> LaborTrendSnapshot:
    observations = list(
        (
            await session.scalars(
                select(LaborMarketObservation)
                .where(
                    LaborMarketObservation.source == source,
                    LaborMarketObservation.country_code == country_code.upper(),
                    LaborMarketObservation.region_code == region_code,
                    LaborMarketObservation.occupation_code == occupation_code,
                    LaborMarketObservation.metric == metric,
                )
                .order_by(LaborMarketObservation.period.asc())
            )
        ).all()
    )

    if len(observations) < settings.phase8_labor_min_points:
        raise ValueError(
            f"At least {settings.phase8_labor_min_points} observations are required."
        )

    result = compute_trend(
        [(observation.period, observation.value) for observation in observations]
    )
    vintages = sorted({observation.data_vintage for observation in observations})
    source_urls = sorted(
        {observation.source_url for observation in observations if observation.source_url}
    )
    licenses = sorted(
        {observation.license for observation in observations if observation.license}
    )

    record = LaborTrendSnapshot(
        source=source,
        country_code=country_code.upper(),
        region_code=region_code,
        occupation_code=occupation_code,
        occupation_title=observations[-1].occupation_title,
        metric=metric,
        method_version=METHOD_VERSION,
        input_count=result["input_count"],
        start_period=result["start_period"],
        end_period=result["end_period"],
        start_value=result["start_value"],
        end_value=result["end_value"],
        linear_slope=result["linear_slope"],
        annualized_change=result["annualized_change"],
        volatility=result["volatility"],
        direction=result["direction"],
        confidence=result["confidence"],
        projected_next_value=result["projected_next_value"],
        provenance_json={
            "data_vintages": vintages,
            "source_urls": source_urls,
            "licenses": licenses,
            "method": (
                "Ordinary least-squares trend over the supplied time axis. "
                "The next value is a one-year linear projection."
            ),
            "not_a_probability": True,
        },
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


def _bls_period(year: str, period: str) -> str | None:
    if period == "M13":
        return year

    if period.startswith("M") and period[1:].isdigit():
        month = int(period[1:])

        if 1 <= month <= 12:
            return f"{year}-M{month:02d}"

    if period.startswith("Q") and period[1:].isdigit():
        quarter = int(period[1:])

        if 1 <= quarter <= 4:
            return f"{year}-Q{quarter}"

    return None


async def import_bls_series(
    session: AsyncSession,
    request: BLSSeriesImportRequest,
) -> int:
    if request.end_year < request.start_year:
        raise ValueError("end_year must be greater than or equal to start_year.")

    body: dict[str, Any] = {
        "seriesid": [request.series_id],
        "startyear": str(request.start_year),
        "endyear": str(request.end_year),
        "catalog": True,
        "annualaverage": True,
    }

    key = settings.bls_api_key.get_secret_value()

    if key:
        body["registrationkey"] = key

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(25, connect=5),
        follow_redirects=False,
    ) as client:
        response = await client.post(
            BLS_API_URL,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json=body,
        )
        response.raise_for_status()
        payload = response.json()

    if payload.get("status") != "REQUEST_SUCCEEDED":
        raise RuntimeError(
            "BLS API request failed: "
            + "; ".join(str(item) for item in payload.get("message", []))
        )

    series = payload.get("Results", {}).get("series", [])

    if not series:
        return 0

    records = series[0].get("data", [])
    imported = 0

    for item in records:
        period = _bls_period(str(item.get("year", "")), str(item.get("period", "")))

        if not period:
            continue

        try:
            value = float(item["value"])
        except (KeyError, TypeError, ValueError):
            continue

        observation = LaborObservationIn(
            source="BLS Public Data API v2",
            data_vintage=request.data_vintage,
            country_code=request.country_code,
            region_code=request.region_code,
            occupation_code=request.occupation_code,
            occupation_title=request.occupation_title,
            metric=request.metric if request.metric in {
                "employment",
                "openings",
                "wage_median",
                "annual_mean_wage",
                "unemployment_rate",
                "vacancy_rate",
                "custom",
            } else "custom",
            period=period,
            value=value,
            unit=request.unit,
            source_url=BLS_API_URL,
            license="U.S. government public data; verify dataset-specific notices.",
            metadata={
                "series_id": request.series_id,
                "footnotes": item.get("footnotes", []),
                "period_name": item.get("periodName"),
            },
        )
        await upsert_observation(session, observation)
        imported += 1

    return imported
