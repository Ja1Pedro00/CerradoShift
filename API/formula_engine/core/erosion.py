from __future__ import annotations

from math import sin, atan


def rusle_soil_loss_t_ha_year(
    rainfall_erosivity_r: float,
    soil_erodibility_k: float,
    slope_length_m: float,
    slope_percent: float,
    cover_factor_c: float,
    support_practice_p: float,
    slope_exponent_m: float = 0.5,
) -> dict:
    """RUSLE: perda média anual estimada por erosão laminar e em sulcos.

    R, K, C e P devem ser fornecidos/calibrados com definições e unidades RUSLE
    consistentes para a região. Não derive R automaticamente de chuva diária:
    erosividade depende da intensidade/energia do evento.
    """
    if min(rainfall_erosivity_r, soil_erodibility_k, cover_factor_c, support_practice_p) < 0:
        raise ValueError("Os fatores R, K, C e P não podem ser negativos.")
    if slope_length_m <= 0 or slope_percent < 0 or not (0 <= slope_exponent_m <= 1):
        raise ValueError("Comprimento, declive ou expoente LS inválidos.")
    theta = atan(slope_percent / 100.0)
    sin_theta = sin(theta)
    ls = (slope_length_m / 22.13) ** slope_exponent_m * (65.41 * sin_theta**2 + 4.56 * sin_theta + 0.065)
    soil_loss = rainfall_erosivity_r * soil_erodibility_k * ls * cover_factor_c * support_practice_p
    return {
        "estimated_sheet_rill_soil_loss_t_ha_year": round(soil_loss, 3),
        "factors": {"R": rainfall_erosivity_r, "K": soil_erodibility_k, "LS": round(ls, 5), "C": cover_factor_c, "P": support_practice_p},
        "scope": "estimativa empírica RUSLE de erosão laminar e em sulcos; não calcula ravinas, voçorocas, deposição ou exportação total de sedimentos",
        "quality_note": "Resultado só é defensável quando fatores e unidades foram obtidos por método apropriado e calibrados para região/escala.",
    }
