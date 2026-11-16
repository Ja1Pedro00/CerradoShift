from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from clients import CachedHTTP
from providers.base import ProviderResult

STAC_SEARCH_URL = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
COLLECTIONS = ["sentinel-2-l2a", "landsat-c2-l2"]


def _centroid(geometry: dict[str, Any]) -> tuple[float, float]:
    """Centroide simples (média dos vértices) do polígono, em lon/lat."""
    points: list[tuple[float, float]] = []

    def walk(node: Any) -> None:
        if (
            isinstance(node, (list, tuple))
            and len(node) == 2
            and all(isinstance(v, (int, float)) for v in node)
        ):
            points.append((float(node[0]), float(node[1])))
            return
        if isinstance(node, (list, tuple)):
            for child in node:
                walk(child)

    walk(geometry.get("coordinates") or [])
    if not points:
        raise ValueError("geometria sem coordenadas")
    return (
        sum(p[0] for p in points) / len(points),
        sum(p[1] for p in points) / len(points),
    )


async def context(
    client: CachedHTTP,
    *,
    lat: float | None = None,
    lon: float | None = None,
    geometry: dict[str, Any] | None = None,
    start: date,
    end: date,
    limit: int = 12,
) -> ProviderResult:
    """Disponibilidade de imagens (Sentinel-2 / Landsat) para o talhão.

    Aqui respondemos "existe imagem limpa para calcular NDVI?". O cálculo em si
    está em ``providers.geo`` (HLS por polígono).
    """
    if geometry is not None:
        intersects: dict[str, Any] = geometry
        if lat is None or lon is None:
            lon, lat = _centroid(geometry)
    elif lat is not None and lon is not None:
        intersects = {"type": "Point", "coordinates": [lon, lat]}
    else:
        raise ValueError("informe 'geometry' ou 'lat'/'lon'")

    body = {
        "collections": COLLECTIONS,
        "intersects": intersects,
        "datetime": f"{start.isoformat()}T00:00:00Z/{end.isoformat()}T23:59:59Z",
        "limit": limit,
        "sortby": [{"field": "properties.datetime", "direction": "desc"}],
    }
    raw, cached = await client.post_json(STAC_SEARCH_URL, body=body, ttl=3600, timeout=30)

    scenes: list[dict[str, Any]] = []
    for feature in (raw or {}).get("features") or []:
        props = feature.get("properties") or {}
        assets = feature.get("assets") or {}
        scenes.append(
            {
                "id": feature.get("id"),
                "collection": feature.get("collection"),
                "datetime": props.get("datetime"),
                "cloud_cover_pct": props.get("eo:cloud_cover"),
                "platform": props.get("platform"),
                "assets": sorted(assets.keys())[:8],
            }
        )

    clear_window = date.today() - timedelta(days=60)
    recent_clear = [
        s
        for s in scenes
        if s["datetime"]
        and s["datetime"][:10] >= clear_window.isoformat()
        and (s["cloud_cover_pct"] is None or s["cloud_cover_pct"] <= 20)
    ]

    payload = {
        "source": "Microsoft Planetary Computer STAC",
        "collections": COLLECTIONS,
        "scenes_found": len(scenes),
        "scenes": scenes,
        "recent_clear_scenes_60d": len(recent_clear),
        "best_recent_scene": recent_clear[0] if recent_clear else None,
        "note": "NDVI/EVI por talhão: use POST /v1/vegetation-series (HLS via Planetary Computer).",
        "attribution": "Planetary Computer (Microsoft) — contém Sentinel-2 (ESA) e Landsat (USGS/NASA)",
    }
    warnings = []
    if not scenes:
        warnings.append("Nenhuma cena encontrada para o período — aumente a janela.")
    elif not recent_clear:
        warnings.append("Nenhuma cena com pouca nuvem nos últimos 60 dias.")

    return ProviderResult(
        name="STAC Sentinel-2 / Landsat",
        data=payload,
        cached=cached,
        warnings=warnings,
    )
