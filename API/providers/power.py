from __future__ import annotations

from datetime import date
from typing import Any

from clients import CachedHTTP
from providers.base import ProviderResult

URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
FILL = -999.0

# Parâmetros da comunidade AG (Agroclimatology) do POWER.
# PRECTOTCORR  = precipitação corrigida (mm/dia)
# T2M_MAX/MIN  = temperatura do ar a 2 m (°C)
# EVPTRNS      = evapotranspiração (mm/dia)
# GWETROOT     = umidade da zona radicular (0-1, fração de saturação)
# GWETTOP      = umidade da camada superficial (0-1)
# RH2M, WS2M    = umidade relativa e vento a 2 m
# ALLSKY_SFC_SW_DWN = radiação de onda curta na superfície (MJ/m²/dia)
PARAMETERS = [
    "PRECTOTCORR",
    "T2M_MAX",
    "T2M_MIN",
    "T2M",
    "EVPTRNS",
    "GWETROOT",
    "GWETTOP",
    "RH2M",
    "WS2M",
    "ALLSKY_SFC_SW_DWN",
]

LABELS = {
    "PRECTOTCORR": "precip_mm",
    "T2M_MAX": "tmax_c",
    "T2M_MIN": "tmin_c",
    "T2M": "tmean_c",
    "EVPTRNS": "et_mm",
    "GWETROOT": "soil_moisture_rootzone",
    "GWETTOP": "soil_moisture_surface",
    "RH2M": "rh_pct",
    "WS2M": "wind_ms",
    "ALLSKY_SFC_SW_DWN": "solar_mj_m2",
}


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if f <= FILL + 1e-6 else f


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 3) if values else None


def _sum(values: list[float]) -> float | None:
    return round(sum(values), 2) if values else None


async def context(
    client: CachedHTTP,
    *,
    lat: float,
    lon: float,
    start: date,
    end: date,
    include_series: bool = False,
) -> ProviderResult:
    params = {
        "parameters": ",".join(PARAMETERS),
        "community": "AG",
        "longitude": f"{lon:.4f}",
        "latitude": f"{lat:.4f}",
        "start": start.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
        "format": "JSON",
        "units": "metric",
    }
    raw, cached = await client.get_json(URL, params=params, ttl=6 * 3600)

    parameter = (raw.get("properties") or {}).get("parameter") or {}
    if not parameter:
        raise ValueError("POWER respondeu sem 'properties.parameter'")

    dates = sorted(parameter.get("PRECTOTCORR", {}).keys())
    daily: list[dict[str, Any]] = []
    for day in dates:
        row: dict[str, Any] = {"date": day}
        for power_key, field_name in LABELS.items():
            row[field_name] = _num(parameter.get(power_key, {}).get(day))
        daily.append(row)

    # O POWER devolve -999 nos últimos dias (dados ainda não consolidados).
    complete = [row for row in daily if row["precip_mm"] is not None]
    if not complete:
        raise ValueError("POWER não retornou nenhum dia consolidado no período")

    precip = [r["precip_mm"] for r in complete]
    tmax = [r["tmax_c"] for r in complete if r["tmax_c"] is not None]
    tmin = [r["tmin_c"] for r in complete if r["tmin_c"] is not None]
    et = [r["et_mm"] for r in complete if r["et_mm"] is not None]
    root = [r["soil_moisture_rootzone"] for r in complete if r["soil_moisture_rootzone"] is not None]
    surface = [r["soil_moisture_surface"] for r in complete if r["soil_moisture_surface"] is not None]
    solar = [r["solar_mj_m2"] for r in complete if r["solar_mj_m2"] is not None]

    longest_dry = current_dry = 0
    for value in precip:
        if value < 1.0:
            current_dry += 1
            longest_dry = max(longest_dry, current_dry)
        else:
            current_dry = 0

    monthly: dict[str, dict[str, Any]] = {}
    for row in complete:
        key = row["date"][:6]
        bucket = monthly.setdefault(key, {"month": key, "precip_mm": 0.0, "et_mm": 0.0, "_tmax": [], "_root": []})
        bucket["precip_mm"] += row["precip_mm"] or 0.0
        bucket["et_mm"] += row["et_mm"] or 0.0
        if row["tmax_c"] is not None:
            bucket["_tmax"].append(row["tmax_c"])
        if row["soil_moisture_rootzone"] is not None:
            bucket["_root"].append(row["soil_moisture_rootzone"])

    months = []
    for key in sorted(monthly):
        bucket = monthly[key]
        months.append(
            {
                "month": f"{key[:4]}-{key[4:]}",
                "precip_mm": round(bucket["precip_mm"], 1),
                "et_mm": round(bucket["et_mm"], 1),
                "tmax_mean_c": _mean(bucket["_tmax"]),
                "soil_moisture_rootzone_mean": _mean(bucket["_root"]),
            }
        )

    trend = "sem_dados"
    if len(root) >= 20:
        half = len(root) // 2
        first, second = _mean(root[:half]) or 0.0, _mean(root[half:]) or 0.0
        delta = second - first
        if delta > 0.02:
            trend = "subindo"
        elif delta < -0.02:
            trend = "caindo"
        else:
            trend = "estavel"
        trend_delta = round(delta, 4)
    else:
        trend_delta = None

    precip_total = _sum(precip)
    et_total = _sum(et)

    payload = {
        "source": "NASA POWER (MERRA-2 / GEOSIT)",
        "community": "AG",
        "native_resolution_km": 50,
        "period": {"start": complete[0]["date"], "end": complete[-1]["date"]},
        "days_with_data": len(complete),
        "precip_mm_total": precip_total,
        "precip_mm_per_day": round(precip_total / len(precip), 2) if precip_total is not None else None,
        "et_mm_total": et_total,
        "net_water_balance_mm": round(precip_total - et_total, 1)
        if precip_total is not None and et_total is not None
        else None,
        "tmax_mean_c": _mean(tmax),
        "tmin_mean_c": _mean(tmin),
        "tmean_mean_c": _mean([r["tmean_c"] for r in complete if r["tmean_c"] is not None]),
        "solar_mj_m2_mean": _mean(solar),
        "frost_days_tmin_le_2c": sum(1 for v in tmin if v <= 2.0),
        "heat_days_tmax_ge_35c": sum(1 for v in tmax if v >= 35.0),
        "rainy_days_precip_ge_1mm": sum(1 for v in precip if v >= 1.0),
        "longest_dry_spell_days": longest_dry,
        "soil_moisture_rootzone": {
            "mean": _mean(root),
            "min": round(min(root), 3) if root else None,
            "latest": round(root[-1], 3) if root else None,
            "trend": trend,
            "trend_delta": trend_delta,
            "unit": "fração de saturação (0-1)",
        },
        "soil_moisture_surface_mean": _mean(surface),
        "monthly": months,
        "attribution": "NASA POWER / LaRC — https://power.larc.nasa.gov/",
    }

    warnings = []
    if complete[-1]["date"] != daily[-1]["date"]:
        warnings.append(
            f"POWER: últimos dias do período ainda não consolidados "
            f"(último dia com dado: {complete[-1]['date']})."
        )

    if include_series:
        payload["daily"] = complete

    return ProviderResult(name="NASA POWER", data=payload, cached=cached, warnings=warnings)
