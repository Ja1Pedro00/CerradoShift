"""Embrapa GeoInfo: WFS da camada selecionada no catálogo.

É preciso escolher uma camada vetorial de pedologia no portal GeoInfo,
confirmar a URL do WFS e o nome do tipo de feição (typeNames).
"""
import os
from .common import get_json, safe_error, status


async def consultar_solo(lat: float, lon: float):
    url = os.getenv("EMBRAPA_WFS_URL", "").strip()
    layer = os.getenv("EMBRAPA_SOIL_LAYER", "").strip()
    if not url or not layer:
        return status("Embrapa GeoInfo", "not_configured",
                      warning="Defina EMBRAPA_WFS_URL e EMBRAPA_SOIL_LAYER após escolher a camada no GeoInfo.")
    try:
        delta = 0.003  # caixa de busca aproximada; não garante ponto dentro da unidade
        features = await get_json(url, params={
            "service": "WFS", "version": "2.0.0", "request": "GetFeature",
            "typeNames": layer, "outputFormat": "application/json",
            "srsName": "EPSG:4326",
            "bbox": f"{lon-delta},{lat-delta},{lon+delta},{lat+delta},EPSG:4326",
            "count": 20,
        })
        if features.get("type") != "FeatureCollection":
            return status("Embrapa GeoInfo", "unavailable",
                          warning="WFS não retornou FeatureCollection GeoJSON; confirme camada e formato.")
        return status("Embrapa GeoInfo", "ok", data={
            "features": features.get("features", []),
            "note": "Feições candidatas próximas; verificar interseção, escala e legenda antes de inferir classe de solo."
        }, layer=layer)
    except Exception as exc:
        return safe_error("Embrapa GeoInfo", exc)
