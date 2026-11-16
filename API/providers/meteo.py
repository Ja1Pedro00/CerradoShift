from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from clients import CachedHTTP
from providers.base import ProviderResult

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

DAILY_VARS = ",".join(
    [
        "precipitation_sum",
        "et0_fao_evapotranspiration",
        "temperature_2m_max",
        "temperature_2m_min",
        "shortwave_radiation_sum",
    ]
)

HOURLY_VARS = "soil_moisture_0_to_7cm,soil_moisture_7_to_28cm"


def _sum(series: list[Any]) -> float | None:
    values = [v for v in series if isinstance(v, (int, float))]
    return round(sum(values), 2) if values else None


def _last(series: list[Any]) -> float | None:
    for value in reversed(series):
        if isinstance(value, (int, float)):
            return round(float(value), 4)
    return None


async def context(
    client: CachedHTTP,
    *,
    lat: float,
    lon: float,
    start: date,
    end: date,
    forecast_days: int = 14,
) -> ProviderResult:
    """ET0 de referência (FAO-56) e previsão de curto prazo.

    O POWER não entrega ET0; o Open-Meteo entrega (ERA5-Land / modelos) sem
    chave e com cobertura global — por isso ele complementa o POWER aqui.
    """
    warnings: list[str] = []
    cached_any = False

    # A API de arquivo tem latência de ~5 dias em relação a hoje.
    archive_end = min(end, date.today() - timedelta(days=5))
    archive: dict[str, Any] = {}
    if archive_end > start:
        try:
            archive, cached = await client.get_json(
                ARCHIVE_URL,
                params={
                    "latitude": f"{lat:.4f}",
                    "longitude": f"{lon:.4f}",
                    "start_date": start.isoformat(),
                    "end_date": archive_end.isoformat(),
                    "daily": DAILY_VARS,
                    "timezone": "auto",
                },
                ttl=24 * 3600,
                timeout=20,
            )
            cached_any = cached_any or cached
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Open-Meteo arquivo indisponível: {type(exc).__name__}")

    daily = archive.get("daily") or {}
    et0_values = daily.get("et0_fao_evapotranspiration") or []
    precip_values = daily.get("precipitation_sum") or []

    try:
        forecast, cached = await client.get_json(
            FORECAST_URL,
            params={
                "latitude": f"{lat:.4f}",
                "longitude": f"{lon:.4f}",
                "daily": DAILY_VARS,
                "hourly": HOURLY_VARS,
                "past_days": 7,
                "forecast_days": forecast_days,
                "timezone": "auto",
            },
            ttl=3 * 3600,
            timeout=20,
        )
        cached_any = cached_any or cached
    except Exception as exc:  # noqa: BLE001
        forecast = {}
        warnings.append(f"Open-Meteo previsão indisponível: {type(exc).__name__}")

    forecast_daily = forecast.get("daily") or {}
    forecast_rows = []
    for index, day in enumerate(forecast_daily.get("time") or []):
        forecast_rows.append(
            {
                "date": day,
                "precip_mm": (forecast_daily.get("precipitation_sum") or [None] * 99)[index],
                "et0_mm": (forecast_daily.get("et0_fao_evapotranspiration") or [None] * 99)[index],
                "tmax_c": (forecast_daily.get("temperature_2m_max") or [None] * 99)[index],
                "tmin_c": (forecast_daily.get("temperature_2m_min") or [None] * 99)[index],
            }
        )

    hourly = forecast.get("hourly") or {}
    soil_moisture = {
        "surface_0_7cm_latest_m3m3": _last(hourly.get("soil_moisture_0_to_7cm") or []),
        "rootzone_7_28cm_latest_m3m3": _last(hourly.get("soil_moisture_7_to_28cm") or []),
        "unit": "m³/m³ (fração volumétrica)",
    }

    et0_total = _sum(et0_values)
    payload = {
        "source": "Open-Meteo (ERA5-Land + modelos numéricos)",
        "period": {"start": start.isoformat(), "end": archive_end.isoformat()} if et0_total else None,
        "et0_mm_total": et0_total,
        "et0_mm_per_day": round(et0_total / len(et0_values), 2) if et0_total and et0_values else None,
        "precip_mm_total": _sum(precip_values),
        "et0_reference": "FAO-56 Penman-Monteith",
        "soil_moisture": soil_moisture,
        "forecast": {
            "days": forecast_rows,
            "precip_mm_total": _sum([r["precip_mm"] for r in forecast_rows]),
            "et0_mm_total": _sum([r["et0_mm"] for r in forecast_rows]),
        },
        "attribution": "Open-Meteo — https://open-meteo.com/ (CC BY 4.0)",
    }

    if not forecast_rows and not et0_total:
        raise ValueError("Open-Meteo não retornou dados")

    return ProviderResult(
        name="Open-Meteo (ET0/previsão)",
        data=payload,
        cached=cached_any,
        warnings=warnings,
    )
