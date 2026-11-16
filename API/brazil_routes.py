"""Rotas opcionais para testar os provedores brasileiros."""
from fastapi import APIRouter, Query
from providers.brasil import embrapa, ibge_solos, inmet, ana, mapbiomas

router = APIRouter(prefix="/v1/brazil", tags=["Fontes brasileiras"])


@router.get("/soil-context")
async def soil_context(lat: float = Query(ge=-90, le=90), lon: float = Query(ge=-180, le=180)):
    import asyncio
    e, i = await asyncio.gather(embrapa.consultar_solo(lat, lon), ibge_solos.consultar_pedologia(lat, lon))
    return {"embrapa": e, "ibge_pedologia": i,
            "warning": "Classes regionais não substituem pH, nutrientes ou análise laboratorial do talhão."}


@router.get("/ibge/production/{codigo_ibge}")
async def ibge_production(codigo_ibge: int):
    return await ibge_solos.consultar_producao_municipal(codigo_ibge)


@router.get("/mapbiomas")
async def coverage(lat: float = Query(ge=-90, le=90), lon: float = Query(ge=-180, le=180), ano: int = 2024):
    return await mapbiomas.consultar_cobertura(lat, lon, ano)


@router.get("/inmet/{station}")
async def inmet_station(station: str):
    return await inmet.consultar_estacao(station)


@router.get("/ana/{station}")
async def ana_series(station: str, inicio: str, fim: str):
    return await ana.consultar_serie(station, inicio, fim)
