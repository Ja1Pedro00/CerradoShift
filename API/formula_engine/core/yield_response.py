from __future__ import annotations


def fao_water_yield_response(eta_actual_mm: float, eta_max_mm: float, ky: float) -> dict:
    """Resposta relativa de rendimento à água pela relação FAO Ky.

    1 - Ya/Ym = Ky * (1 - ETa/ETm). Retorna estimativa relativa, não toneladas.
    Ky precisa ser específico da cultura/fase/ambiente e validado.
    """
    if eta_actual_mm < 0 or eta_max_mm <= 0 or ky < 0:
        raise ValueError("ETa deve ser >=0, ETm >0 e Ky >=0.")
    deficit_fraction = max(0.0, 1.0 - min(1.0, eta_actual_mm / eta_max_mm))
    relative_loss = min(1.0, ky * deficit_fraction)
    return {
        "relative_water_deficit_fraction": round(deficit_fraction, 4),
        "estimated_relative_yield_loss_fraction": round(relative_loss, 4),
        "estimated_relative_yield_loss_percent": round(relative_loss * 100, 2),
        "equation": "1 - Ya/Ym = Ky * (1 - ETa/ETm)",
        "status": "screening_only_requires_crop_stage_specific_Ky_and_valid_ET_inputs",
        "warning": "Não estima produtividade absoluta. Efeitos de pragas, nutrientes, salinidade, calor, cultivar e manejo devem ser tratados separadamente; não some perdas sem modelo validado.",
    }
