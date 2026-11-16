from __future__ import annotations


def evaporation_reduction_coefficient(depletion_evaporation_mm: float, readily_evaporable_water_mm: float, total_evaporable_water_mm: float) -> float:
    """Kr FAO-56 para a camada superficial evaporante."""
    if readily_evaporable_water_mm < 0 or total_evaporable_water_mm <= 0 or readily_evaporable_water_mm > total_evaporable_water_mm:
        raise ValueError("Exija 0 <= REW <= TEW e TEW > 0.")
    de = max(0.0, depletion_evaporation_mm)
    if de <= readily_evaporable_water_mm:
        return 1.0
    return max(0.0, min(1.0, (total_evaporable_water_mm - de) / (total_evaporable_water_mm - readily_evaporable_water_mm)))


def maximum_crop_coefficient(u2_m_s: float, rh_min_pct: float, crop_height_m: float, kcb: float) -> float:
    """Kcmax FAO-56 para cálculo dual; entradas locais e unidade métrica."""
    if u2_m_s < 0 or not (0 <= rh_min_pct <= 100) or crop_height_m <= 0:
        raise ValueError("Vento, UR mínima ou altura de cultura inválidos.")
    climate_term = 1.2 + (0.04 * (u2_m_s - 2.0) - 0.004 * (rh_min_pct - 45.0)) * (crop_height_m / 3.0) ** 0.3
    return max(climate_term, kcb + 0.05)


def dual_crop_coefficient_et(
    et0_mm_day: float,
    kcb: float,
    ks: float,
    kr: float,
    kcmax: float,
    few: float,
) -> dict:
    """ETc=(Kcb*Ks + Ke)*ET0; separa transpiração e evaporação do solo.

    `few` é a fração de solo exposta e molhada; sua determinação exige cobertura
    do dossel e geometria/fração molhada por chuva/irrigação.
    """
    if et0_mm_day < 0 or kcb < 0 or not (0 <= ks <= 1) or not (0 <= kr <= 1) or kcmax < kcb or not (0 <= few <= 1):
        raise ValueError("Parâmetros do coeficiente duplo fora dos intervalos válidos.")
    ke = min(kr * (kcmax - kcb), few * kcmax)
    transpiration = kcb * ks * et0_mm_day
    soil_evaporation = ke * et0_mm_day
    return {
        "ke": round(ke, 4),
        "transpiration_mm_day": round(transpiration, 3),
        "soil_evaporation_mm_day": round(soil_evaporation, 3),
        "etc_actual_mm_day": round(transpiration + soil_evaporation, 3),
        "formula": "ETc=(Kcb*Ks+Ke)*ET0",
        "note": "Função de cálculo dual isolada; ainda não substitui o balanço diário Kc simples do endpoint /assessments/field.",
    }
