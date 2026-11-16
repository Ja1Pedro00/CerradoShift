"""IBGE: contexto de pedologia via WFS configurado e produção municipal via SIDRA.

Não confundir mapas regionais com laudo laboratorial do talhão.
"""
import os
from .common import get_json, safe_error, status


async def consultar_pedologia(lat: float, lon: float):
    url = os.getenv("IBGE_PEDO_WFS_URL", "").strip()
    layer = os.getenv("IBGE_PEDO_LAYER", "").strip()
    if not url or not layer:
        return status("IBGE BDiA pedologia", "not_configured",
                      warning="Escolha camada pedológica e configure IBGE_PEDO_WFS_URL / IBGE_PEDO_LAYER.")
    try:
        delta = 0.005
        raw = await get_json(url, params={
            "service": "WFS", "version": "2.0.0", "request": "GetFeature",
            "typeNames": layer, "outputFormat": "application/json", "srsName": "EPSG:4326",
            "bbox": f"{lon-delta},{lat-delta},{lon+delta},{lat+delta},EPSG:4326",
            "count": 20,
        })
        if raw.get("type") != "FeatureCollection":
            return status("IBGE BDiA pedologia", "unavailable", warning="Resposta não é GeoJSON FeatureCollection")
        return status("IBGE BDiA pedologia", "ok", data={
            "features": raw.get("features", []),
            "note": "Feições regionais candidatas; classe/escala/legenda requerem interpretação."
        }, layer=layer)
    except Exception as exc:
        return safe_error("IBGE BDiA pedologia", exc)


async def consultar_producao_municipal(codigo_ibge: int):
    """SIDRA tabela 1612: dados municipais, NÃO medidas do talhão.

    Retorna linhas brutas; variáveis/culturas devem ser filtradas após verificar metadados.
    """
    code = str(codigo_ibge)
    if len(code) != 7 or not code.isdigit():
        return status("IBGE SIDRA", "invalid_request", warning="Código IBGE municipal deve ter 7 dígitos")
    url = f"https://apisidra.ibge.gov.br/values/t/1612/n6/{code}/p/last%201/v/all"
    try:
        rows = await get_json(url)
        return status("IBGE SIDRA tabela 1612", "ok", data={
            "rows": rows, "note": "Produção agrícola municipal; não caracteriza solo ou produção do talhão."
        })
    except Exception as exc:
        return safe_error("IBGE SIDRA", exc)
