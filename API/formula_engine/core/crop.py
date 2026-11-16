from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .schemas import CropParameters


@dataclass(frozen=True)
class CropDayParameters:
    days_after_planting: int
    stage: str
    kc: float
    root_depth_m: float
    gdd_c_day: float | None


def crop_stage_and_kc(params: CropParameters, days_after_planting: int) -> tuple[str, float]:
    """Obtém estágio e Kc por interpolação linear entre estágios FAO.

    Kc inicial: constante; desenvolvimento: Kc_ini -> Kc_mid; meio: constante;
    final: Kc_mid -> Kc_end. É uma curva por estágios simplificada. Os dias de
    estágio precisam ser calibrados para cultivar, época e manejo locais.
    """
    d = max(0, days_after_planting)
    initial_end = params.stage_initial_days
    dev_end = initial_end + params.stage_development_days
    mid_end = dev_end + params.stage_mid_days
    late_end = mid_end + params.stage_late_days

    if d < initial_end:
        return "initial", params.kc_initial
    if d < dev_end:
        span = max(1, params.stage_development_days)
        fraction = (d - initial_end) / span
        kc = params.kc_initial + fraction * (params.kc_mid - params.kc_initial)
        return "development", kc
    if d < mid_end:
        return "mid", params.kc_mid
    if d < late_end:
        span = max(1, params.stage_late_days)
        fraction = min(1.0, (d - mid_end) / span)
        kc = params.kc_mid + fraction * (params.kc_end - params.kc_mid)
        return "late", kc
    return "completed", params.kc_end


def root_depth_for_day(params: CropParameters, days_after_planting: int) -> float:
    """Crescimento radicular linear simplificado até a profundidade máxima."""
    fraction = min(1.0, max(0, days_after_planting) / params.root_growth_days)
    return params.root_depth_initial_m + fraction * (
        params.root_depth_max_m - params.root_depth_initial_m
    )


def adjusted_depletion_fraction(p_table: float, etc_mm_day: float) -> float:
    """Ajuste FAO-56 de p para ETc diferente de 5 mm/dia; limitado a 0.1–0.8."""
    return min(0.8, max(0.1, p_table + 0.04 * (5.0 - etc_mm_day)))


def crop_day_parameters(
    params: CropParameters,
    planting_date: date,
    day: date,
    tmax_c: float,
    tmin_c: float,
) -> CropDayParameters:
    age = (day - planting_date).days
    stage, kc = crop_stage_and_kc(params, age)
    root_depth = root_depth_for_day(params, age)

    gdd = None
    if params.base_temperature_c is not None:
        # GDD simplificado. Um teto térmico pode ser definido por cultura.
        tmax = tmax_c
        if params.upper_temperature_c is not None:
            tmax = min(tmax, params.upper_temperature_c)
        tmax = max(tmax, params.base_temperature_c)
        tmin = max(tmin_c, params.base_temperature_c)
        if params.upper_temperature_c is not None:
            tmin = min(tmin, params.upper_temperature_c)
        gdd = max(0.0, (tmax + tmin) / 2.0 - params.base_temperature_c)

    return CropDayParameters(age, stage, kc, root_depth, gdd)
