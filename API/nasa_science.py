"""CerradoShift: historical NASA POWER -> rotation comparison.

Pairs POWER daily precipitation (PRECTOTCORR) with Open-Meteo historical daily
FAO-56 reference evapotranspiration (ET0); never substitutes POWER EVPTRNS
(actual ET) for ET0. Data gaps fail closed (no synthetic interpolation).

Scientific scope: transparent screening of water stress, not calibrated yield,
field-level rain measurements or a general agronomic prescription.
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from math import isfinite
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, model_validator

from providers import power
from rotation_engine import ComparisonRequest, Rotation, WeatherDay, WeatherScenario, compare

router = APIRouter(prefix="/v1/science", tags=["scientific-simulation"])
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


class NASAHistoryRequest(BaseModel):
    """Same crop sequences for each historical planting window."""

    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    historical_start_dates: list[date] = Field(min_length=1, max_length=5)
    rotations: list[Rotation] = Field(min_length=2, max_length=12)
    soil_capacity_mm: float = Field(gt=0, le=1000)
    initial_soil_water_mm: float = Field(ge=0, le=1000)
    irrigation_mm_per_day: float = Field(default=0, ge=0, le=40)
    assumption_note: str = Field(min_length=3, max_length=500)
    include_daily: bool = Field(default=False, description="Return per-day charts as well")

    @model_validator(mode="after")
    def check_parameters(self):
        if self.initial_soil_water_mm > self.soil_capacity_mm:
            raise ValueError("Initial soil water cannot exceed soil capacity")
        durations = {sum(c.duration_days for c in r.cycles) for r in self.rotations}
        if len(durations) != 1:
            raise ValueError("Rotations must have equal total duration")
        if len({r.name for r in self.rotations}) != len(self.rotations):
            raise ValueError("Rotation names must be unique")
        starts = self.historical_start_dates
        if len(set(starts)) != len(starts):
            raise ValueError("Historical windows must not repeat")
        if len({(d.month, d.day) for d in starts}) != 1:
            raise ValueError("Compare the same calendar planting window across years")
        horizon = next(iter(durations))
        if horizon > 730:
            raise ValueError("For this endpoint, rotation horizon is limited to 730 days")
        today_cutoff = date.today() - timedelta(days=10)
        for d in starts:
            if d < date(1981, 1, 1) or d + timedelta(days=horizon - 1) > today_cutoff:
                raise ValueError("Window must be historical (1981 onward), ending at least 10 days ago")
        return self


def _valid_mm(value: Any, limit: float, *, source: str, day: date) -> float:
    """Enforce physical and API-sentinel safety; never turn missing into zero."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{source} missing/non-numeric value for {day}")
    value = float(value)
    if not isfinite(value) or not (0 <= value <= limit):
        raise ValueError(f"{source} invalid mm/day value for {day}: {value}")
    return value


async def load_historical_window(
    client: Any, lat: float, lon: float, start: date, end: date
) -> tuple[WeatherScenario, dict[str, Any]]:
    """Collect and align the 2 data products on explicit calendar dates."""
    power_result, (meteo_json, meteo_cached) = await asyncio.gather(
        power.context(client, lat=lat, lon=lon, start=start, end=end, include_series=True),
        client.get_json(
            ARCHIVE_URL,
            params={
                "latitude": f"{lat:.4f}",
                "longitude": f"{lon:.4f}",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "daily": "et0_fao_evapotranspiration",
                "timezone": "auto",
            },
            ttl=24 * 3600,
            timeout=30,
        ),
    )

    if not power_result.ok or not isinstance(power_result.data, dict):
        raise ValueError("NASA POWER unavailable for this window")
    power_daily = power_result.data.get("daily") or []
    precip_by_day: dict[date, float] = {}
    for entry in power_daily:
        key = str(entry.get("date", ""))
        try:
            day = datetime.strptime(key, "%Y%m%d").date()
        except ValueError:
            raise ValueError(f"Malformed NASA date: {key}") from None
        if day in precip_by_day:
            raise ValueError(f"Duplicate NASA date {day}")
        precip_by_day[day] = _valid_mm(
            entry.get("precip_mm"), 600, source="NASA POWER precipitation", day=day
        )

    daily = (meteo_json or {}).get("daily") or {}
    days = daily.get("time") or []
    values = daily.get("et0_fao_evapotranspiration") or []
    if len(days) != len(values):
        raise ValueError("Open-Meteo returned unequal daily dates and ET0 values")
    et0_by_day: dict[date, float] = {}
    for raw_day, value in zip(days, values, strict=True):
        try:
            day = date.fromisoformat(str(raw_day))
        except ValueError:
            raise ValueError(f"Malformed Open-Meteo date: {raw_day}") from None
        if day in et0_by_day:
            raise ValueError(f"Duplicate Open-Meteo date {day}")
        et0_by_day[day] = _valid_mm(value, 35, source="Open-Meteo ET0", day=day)

    history = []
    current = start
    while current <= end:
        if current not in precip_by_day or current not in et0_by_day:
            missing = []
            if current not in precip_by_day:
                missing.append("NASA precipitation")
            if current not in et0_by_day:
                missing.append("Open-Meteo ET0")
            raise ValueError(f"Incomplete historical data for {current}: {', '.join(missing)}")
        history.append(
            WeatherDay(
                date=current,
                precipitation_mm=precip_by_day[current],
                et0_mm=et0_by_day[current],
            )
        )
        current += timedelta(days=1)

    source = "NASA POWER PRECTOTCORR (rain) + Open-Meteo archive ET0 FAO-56"
    scenario = WeatherScenario(
        name=f"safra-{start.isoformat()}",
        days=history,
        source=source,
        historical=True,
    )
    provenance = {
        "scenario": scenario.name,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "days": len(history),
        "precipitation_mm_total": round(sum(x.precipitation_mm for x in history), 2),
        "et0_mm_total": round(sum(x.et0_mm for x in history), 2),
        "precipitation_source": {
            "dataset": "NASA POWER",
            "parameter": "PRECTOTCORR",
            "reference": "https://power.larc.nasa.gov/",
            "cached": bool(power_result.cached),
            "temporal_basis": "Local Solar Time (NASA POWER daily default)",
        },
        "et0_source": {
            "dataset": "Open-Meteo historical archive",
            "parameter": "et0_fao_evapotranspiration",
            "reference": "https://open-meteo.com/en/docs/historical-weather-api",
            "cached": bool(meteo_cached),
            "temporal_basis": "Local civil timezone (auto)",
        },
    }
    return scenario, provenance


async def calculate_historical_comparison(
    client: Any, payload: NASAHistoryRequest
) -> dict[str, Any]:
    horizon = sum(x.duration_days for x in payload.rotations[0].cycles)
    windows = [
        (d, d + timedelta(days=horizon - 1))
        for d in sorted(payload.historical_start_dates)
    ]
    # Independent windows share cached HTTP client but all must succeed.
    observations = await asyncio.gather(
        *[load_historical_window(client, payload.lat, payload.lon, start, end)
          for start, end in windows]
    )
    scenarios = [pair[0] for pair in observations]
    provenance = [pair[1] for pair in observations]
    comparison = ComparisonRequest(
        rotations=payload.rotations,
        scenarios=scenarios,
        soil_capacity_mm=payload.soil_capacity_mm,
        initial_soil_water_mm=payload.initial_soil_water_mm,
        irrigation_mm_per_day=payload.irrigation_mm_per_day,
        assumption_note=payload.assumption_note,
    )
    report = compare(comparison)
    if not payload.include_daily:
        for rotation in report["results"]:
            for scenario in rotation["scenarios"]:
                scenario.pop("daily", None)
    report.update({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "location": {"lat": payload.lat, "lon": payload.lon},
        "historical_windows": provenance,
        "data_validity": "complete historical daily series; any missing day is rejected",
        "warnings": [
            "POWER and Open-Meteo represent different model grids; not local station observations.",
            "NASA POWER daily data are in solar time; Open-Meteo auto uses local civil days; daily aggregation is approximately aligned, not exact.",
            "Crop Kc, dates, root-zone water capacity and initial water are caller assumptions, not inferred from satellites.",
            "Uncovered-days proxy is not validated soil conservation or carbon.",
            "Screening model, not calibrated crop yield or prescription.",
        ],
    })
    return report


@router.post("/compare-nasa-history")
async def compare_nasa_history(payload: NASAHistoryRequest, request: Request):
    try:
        return await calculate_historical_comparison(request.app.state.http, payload)
    except (ValueError, KeyError, TypeError) as exc:
        # Data quality failure should not be silently converted into a scenario.
        raise HTTPException(status_code=502, detail=f"Incomplete upstream data: {exc}") from exc
    except Exception as exc:
        # No raw internals: provider errors may include private URLs/tokens.
        raise HTTPException(status_code=502, detail=f"Data providers unavailable ({type(exc).__name__})") from exc
