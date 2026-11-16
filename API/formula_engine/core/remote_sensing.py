from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Optional


@dataclass(frozen=True)
class ReflectancePixel:
    """Reflectância de superfície em escala 0–1, após máscara de qualidade."""
    red: float
    nir: float
    blue: Optional[float] = None
    green: Optional[float] = None
    swir1: Optional[float] = None
    swir2: Optional[float] = None
    valid: bool = True


def _ratio(numerator: float, denominator: float) -> Optional[float]:
    if abs(denominator) < 1e-12:
        return None
    return numerator / denominator


def compute_indices(pixel: ReflectancePixel, savi_l: float = 0.5) -> dict[str, Optional[float]]:
    """Calcula índices de reflectância; não busca nem corrige a imagem orbital.

    Entrada: reflectância de superfície (não DN bruto), escala 0–1. Nuvens,
    sombras, neve, água e pixels saturados devem ser excluídos pela máscara QA
    ou explicitamente marcados valid=False antes do cálculo.
    """
    if not pixel.valid:
        return {k: None for k in ("ndvi", "evi", "savi", "msavi2", "ndmi", "ndwi_green_nir", "nbr", "nbr2")}
    values = [pixel.red, pixel.nir] + [v for v in (pixel.blue, pixel.green, pixel.swir1, pixel.swir2) if v is not None]
    if any(v < 0 or v > 1.5 for v in values):
        raise ValueError("Reflectâncias devem estar em escala de superfície plausível (0–1.5); aplique o fator de escala do produto antes.")

    ndvi = _ratio(pixel.nir - pixel.red, pixel.nir + pixel.red)
    savi = _ratio((1.0 + savi_l) * (pixel.nir - pixel.red), pixel.nir + pixel.red + savi_l)
    msavi_term = (2 * pixel.nir + 1) ** 2 - 8 * (pixel.nir - pixel.red)
    msavi2 = (2 * pixel.nir + 1 - sqrt(max(0.0, msavi_term))) / 2.0
    evi = None
    if pixel.blue is not None:
        evi = _ratio(2.5 * (pixel.nir - pixel.red), pixel.nir + 6 * pixel.red - 7.5 * pixel.blue + 1.0)
    ndmi = _ratio(pixel.nir - pixel.swir1, pixel.nir + pixel.swir1) if pixel.swir1 is not None else None
    # Nome explicita a variante McFeeters (água superficial), evitando confusão
    # com o índice de umidade da vegetação que também é chamado NDWI.
    ndwi = _ratio(pixel.green - pixel.nir, pixel.green + pixel.nir) if pixel.green is not None else None
    nbr = _ratio(pixel.nir - pixel.swir2, pixel.nir + pixel.swir2) if pixel.swir2 is not None else None
    nbr2 = _ratio(pixel.swir1 - pixel.swir2, pixel.swir1 + pixel.swir2) if pixel.swir1 is not None and pixel.swir2 is not None else None
    return {"ndvi": ndvi, "evi": evi, "savi": savi, "msavi2": msavi2, "ndmi": ndmi, "ndwi_green_nir": ndwi, "nbr": nbr, "nbr2": nbr2}


def summarize_pixels(pixels: list[ReflectancePixel], savi_l: float = 0.5) -> dict:
    """Resumo simples por talhão; média calculada após índice por pixel."""
    if not pixels:
        raise ValueError("Informe ao menos um pixel.")
    per_pixel = [compute_indices(p, savi_l=savi_l) for p in pixels]
    keys = per_pixel[0].keys()
    summary = {}
    for key in keys:
        vals = [row[key] for row in per_pixel if row[key] is not None]
        summary[key] = round(sum(vals) / len(vals), 4) if vals else None
    valid_count = sum(p.valid for p in pixels)
    return {
        "pixel_count": len(pixels),
        "valid_pixel_count": valid_count,
        "valid_pixel_fraction": round(valid_count / len(pixels), 4),
        "mean_indices": summary,
        "per_pixel": per_pixel,
        "interpretation": "Os índices são sinais espectrais; baixos valores não identificam sozinhos a causa do estresse. Compare com histórico, fase da cultura, nuvens/QA, solo exposto e manejo.",
    }


def standardized_anomaly(current: float, historical_mean: float, historical_std: float) -> Optional[float]:
    """Anomalia padronizada (z-score) em relação ao mesmo local/época do ano."""
    if historical_std <= 0:
        return None
    return (current - historical_mean) / historical_std
