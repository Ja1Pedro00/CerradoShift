from __future__ import annotations

from typing import Optional


def daily_gdd(tmax_c: float, tmin_c: float, base_c: float, upper_c: Optional[float] = None) -> float:
    """GDD diário pelo método média com limites inferior/superior."""
    tmax = max(base_c, tmax_c)
    tmin = max(base_c, tmin_c)
    if upper_c is not None:
        tmax = min(tmax, upper_c)
        tmin = min(tmin, upper_c)
    return max(0.0, (tmax + tmin) / 2.0 - base_c)


def thermal_stress_day(tmax_c: float, threshold_c: float, duration_hours: Optional[float] = None) -> dict:
    """Triagem simples de exposição acima de um limite definido para cultura/fase."""
    excess = max(0.0, tmax_c - threshold_c)
    return {
        "exceeded": excess > 0,
        "degree_above_threshold_c": round(excess, 2),
        "exposure_hours_above_threshold": duration_hours,
        "warning": "Triagem, não dano fisiológico estimado; limiar depende de cultivar, órgão, fase, umidade e duração do evento.",
    }


def summarize_gdd_and_heat(weather: list[dict], base_c: float, upper_c: Optional[float], heat_threshold_c: Optional[float]) -> dict:
    cumulative = 0.0
    rows = []
    heat_degree_days = 0.0
    heat_days = 0
    for row in weather:
        gdd = daily_gdd(row["tmax_c"], row["tmin_c"], base_c, upper_c)
        cumulative += gdd
        heat_excess = max(0.0, row["tmax_c"] - heat_threshold_c) if heat_threshold_c is not None else 0.0
        if heat_excess > 0:
            heat_days += 1
            heat_degree_days += heat_excess
        rows.append({"day": str(row["day"]), "gdd_c_day": round(gdd, 2), "cumulative_gdd_c_day": round(cumulative, 2), "heat_excess_c": round(heat_excess, 2) if heat_threshold_c is not None else None})
    return {"daily": rows, "total_gdd_c_day": round(cumulative, 2), "heat_days_above_configured_threshold": heat_days if heat_threshold_c is not None else None, "heat_degree_days_above_threshold": round(heat_degree_days, 2) if heat_threshold_c is not None else None, "note": "GDD e limiar térmico precisam ser configurados para cultura, cultivar e fase; temperaturas médias diárias podem não captar duração/picos intradiários."}
