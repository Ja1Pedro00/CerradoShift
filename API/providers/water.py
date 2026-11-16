from __future__ import annotations

import math
from typing import Any

from clients import CachedHTTP
from providers.base import ProviderResult

USGS_ITEMS_URL = "https://api.waterdata.usgs.gov/ogcapi/v0/collections/monitoring-locations/items"


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return round(2 * radius * math.asin(math.sqrt(a)), 2)


async def context(
    client: CachedHTTP,
    *,
    lat: float,
    lon: float,
    radius_deg: float = 0.25,
) -> ProviderResult:
    """Contexto hidrológico: existem estações de monitoramento por perto?

    Serve para o app saber se dá para validar/calibrar a umidade vinda do
    satélite com medição em campo (NWIS). Série temporal de vazão entra na
    próxima versão (precisa escolher a estação).
    """
    bbox = f"{lon - radius_deg:.4f},{lat - radius_deg:.4f},{lon + radius_deg:.4f},{lat + radius_deg:.4f}"
    raw, cached = await client.get_json(
        USGS_ITEMS_URL,
        params={"bbox": bbox, "limit": 20, "f": "json"},
        ttl=24 * 3600,
        timeout=25,
    )

    features = (raw or {}).get("features") or []
    sites: list[dict[str, Any]] = []
    for feature in features:
        props = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        coords = geometry.get("coordinates") or []
        if len(coords) < 2:
            continue
        site_lon, site_lat = float(coords[0]), float(coords[1])
        sites.append(
            {
                "id": props.get("monitoring_location_number") or props.get("id"),
                "name": props.get("monitoring_location_name"),
                "state": props.get("state_name"),
                "county": props.get("county_name"),
                "distance_km": _haversine_km(lat, lon, site_lat, site_lon),
            }
        )

    sites.sort(key=lambda s: s["distance_km"])
    nearest = sites[:3]

    payload = {
        "source": "USGS Water Data (OGC API / NWIS)",
        "coverage": "Estados Unidos",
        "search_radius_deg": radius_deg,
        "monitoring_locations_nearby": len(sites),
        "nearest": nearest,
        "has_ground_truth_water_data": bool(nearest),
        "attribution": "USGS Water Data — https://waterdata.usgs.gov/",
    }
    return ProviderResult(name="USGS Water Data (NWIS)", data=payload, cached=cached)
