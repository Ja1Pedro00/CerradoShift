
"""Consulta de granulometria do MapBiomas Solo Coleção 3.

Estimativas de areia, silte e argila, 30 m.
Não representa análise laboratorial do talhão.
"""

import asyncio
import os

from .common import safe_error, status

BASE = "projects/mapbiomas-public/assets/brazil/soil/collection3"

ASSETS = {
    "clay_pct": (
        f"{BASE}/mapbiomas_brazil_collection3_soil_clay_fraction_v1",
        "clay_fraction",
    ),
    "sand_pct": (
        f"{BASE}/mapbiomas_brazil_collection3_soil_sand_fraction_v1",
        "sand_fraction",
    ),
    "silt_pct": (
        f"{BASE}/mapbiomas_brazil_collection3_soil_silt_fraction_v1",
        "silt_fraction",
    ),
}


def _consultar(lat, lon, root_depth_cm):
    import ee

    ee.Initialize(project=os.environ["GEE_PROJECT_ID"])

    if root_depth_cm > 100:
        raise ValueError(
            "MapBiomas Solo fornece granulometria até 100 cm."
        )

    point = ee.Geometry.Point([lon, lat])
    results = {}

    for field, (asset, prefix) in ASSETS.items():
        collection = ee.ImageCollection(asset)

        weighted_sum = 0.0
        total_depth = 0.0

        for top in range(0, 100, 10):
            bottom = top + 10

            overlap = max(
                0.0,
                min(root_depth_cm, bottom) - top,
            )

            if overlap <= 0:
                break

            image_name = (
                f"{prefix}_{top:03d}_{bottom:03d}_v1"
            )

            image = ee.Image(
                collection.filter(
                    ee.Filter.eq("system:index", image_name)
                ).first()
            )

            sample = image.reduceRegion(
                reducer=ee.Reducer.first(),
                geometry=point,
                scale=30,
            ).getInfo()

            values = list(sample.values())

            if not values or values[0] is None:
                raise ValueError(
                    f"Sem dados para {field}, {top}-{bottom} cm"
                )

            weighted_sum += float(values[0]) * overlap
            total_depth += overlap

        results[field] = round(
            weighted_sum / total_depth, 2
        )

    return results


async def consultar_solo(
    lat: float,
    lon: float,
    root_depth_cm: float = 30,
):
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return status(
            "MapBiomas Solo",
            "invalid_request",
            warning="Coordenadas inválidas",
        )

    if not 0 < root_depth_cm <= 100:
        return status(
            "MapBiomas Solo",
            "invalid_request",
            warning="Profundidade fora do intervalo 0–100 cm",
        )

    if not os.getenv("GEE_PROJECT_ID"):
        return status(
            "MapBiomas Solo",
            "not_configured",
            warning="Configure GEE_PROJECT_ID",
        )

    try:
        data = await asyncio.wait_for(
            asyncio.to_thread(
                _consultar,
                lat,
                lon,
                root_depth_cm,
            ),
            timeout=60,
        )

        return status(
            "MapBiomas Solo",
            "ok",
            data={
                **data,
                "root_depth_cm": root_depth_cm,
                "provider": "MapBiomas Solo Coleção 3",
                "resolution_m": 30,
            },
        )

    except Exception as exc:
        return safe_error("MapBiomas Solo", exc)
