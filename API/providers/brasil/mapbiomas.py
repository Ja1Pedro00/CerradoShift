"""MapBiomas Coleção 11 (30 m) via Google Earth Engine autenticado.

É necessário configurar projeto Earth Engine: ee.Authenticate() e ee.Initialize(project=...).
A classe é um código de legenda, não uma cultura específica ou análise de solo.
"""
import asyncio
import os
from .common import safe_error, status

ASSET = "projects/mapbiomas-public/assets/brazil/lulc/collection11/mapbiomas_brazil_collection11_coverage_v3"


def _consultar(lat: float, lon: float, ano: int):
    import ee
    ee.Initialize(project=os.environ["GEE_PROJECT_ID"])
    pixel = ee.Image(ASSET).select(f"classification_{ano}")
    point = ee.Geometry.Point([lon, lat])
    result = pixel.reduceRegion(reducer=ee.Reducer.first(), geometry=point, scale=30).getInfo()
    return result.get(f"classification_{ano}")


async def consultar_cobertura(lat: float, lon: float, ano: int = 2024):
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return status("MapBiomas", "invalid_request", warning="Coordenadas inválidas")
    if ano < 1985 or ano > 2025:
        return status("MapBiomas", "invalid_request", warning="Ano fora do intervalo configurado (1985–2025)")
    if not os.getenv("GEE_PROJECT_ID"):
        return status("MapBiomas", "not_configured", warning="Configure GEE_PROJECT_ID e autenticação Earth Engine")
    try:
        cls = await asyncio.wait_for(asyncio.to_thread(_consultar, lat, lon, ano), timeout=20)
        if cls is None:
            return status("MapBiomas", "no_data", warning="Sem pixel classificado nessa coordenada")
        return status("MapBiomas", "ok", data={
            "year": ano, "class_code": int(cls), "asset": ASSET,
            "note": "Interpretar código pela legenda da coleção. Pixel 30 m, não laudo do talhão."
        })
    except Exception as exc:
        return safe_error("MapBiomas", exc)
