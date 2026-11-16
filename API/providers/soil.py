from __future__ import annotations

from typing import Any

from clients import CachedHTTP
from providers.base import ProviderResult

SDA_URL = "https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest"
SOILGRIDS_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"

SDA_QUERY = """
SELECT mu.mukey, mu.muname, c.cokey, c.compname, c.comppct_r,
       c.drainagecl, c.hydgrp, c.slope_r,
       h.hzdept_r, h.hzdepb_r, h.claytotal_r, h.sandtotal_r,
       h.silttotal_r, h.om_r, h.awc_r
FROM mapunit mu
JOIN component c ON c.mukey = mu.mukey
LEFT JOIN chorizon h ON h.cokey = c.cokey
WHERE mu.mukey = (
    SELECT * FROM SDA_Get_Mukey_from_intersection_with_WktWgs84('point({lon} {lat})')
)
ORDER BY c.comppct_r DESC, h.hzdept_r
"""

# Centroides aproximados das 12 classes texturais do USDA (areia, silte, argila).
TEXTURE_CENTROIDS: dict[str, tuple[float, float, float]] = {
    "areia": (92, 5, 3),
    "areia franca": (82, 12, 6),
    "franco-arenosa": (65, 25, 10),
    "franca": (40, 40, 20),
    "franco-siltosa": (20, 65, 15),
    "silte": (8, 85, 7),
    "franco-argilo-arenosa": (60, 13, 27),
    "franco-argilosa": (32, 34, 34),
    "franco-argilo-siltosa": (10, 56, 34),
    "argila-arenosa": (52, 7, 41),
    "argila-siltosa": (8, 47, 45),
    "argila": (20, 20, 60),
}


def classify_texture(sand: float | None, silt: float | None, clay: float | None) -> str | None:
    """Classificação aproximada por vizinho mais próximo no triângulo USDA.

    Serve para dar um rótulo legível ao app; o serviço de fórmulas deve usar
    as percentagens brutas, não este rótulo.
    """
    if sand is None or silt is None or clay is None:
        return None
    best, best_distance = None, float("inf")
    for label, (c_sand, c_silt, c_clay) in TEXTURE_CENTROIDS.items():
        distance = (sand - c_sand) ** 2 + (silt - c_silt) ** 2 + (clay - c_clay) ** 2
        if distance < best_distance:
            best, best_distance = label, distance
    return best


def _weighted_mean(rows: list[dict[str, Any]], key: str, top: float = 0, bottom: float = 100) -> float | None:
    total, weight_sum = 0.0, 0.0
    for row in rows:
        top_cm, bottom_cm = row.get("hzdept_r"), row.get("hzdepb_r")
        value = row.get(key)
        if top_cm is None or bottom_cm is None or value is None:
            continue
        overlap = min(bottom_cm, bottom) - max(top_cm, top)
        if overlap <= 0:
            continue
        total += value * overlap
        weight_sum += overlap
    return round(total / weight_sum, 3) if weight_sum else None


def _awc_mm(rows: list[dict[str, Any]], top: float = 0, bottom: float = 100) -> float | None:
    total, found = 0.0, False
    for row in rows:
        top_cm, bottom_cm, awc = row.get("hzdept_r"), row.get("hzdepb_r"), row.get("awc_r")
        if top_cm is None or bottom_cm is None or awc is None:
            continue
        overlap = min(bottom_cm, bottom) - max(top_cm, top)
        if overlap <= 0:
            continue
        # awc_r está em cm de água por cm de solo -> mm = cm * 10
        total += overlap * awc * 10
        found = True
    return round(total, 1) if found else None


NUMERIC_COLUMNS = {
    "comppct_r",
    "slope_r",
    "hzdept_r",
    "hzdepb_r",
    "claytotal_r",
    "sandtotal_r",
    "silttotal_r",
    "om_r",
    "awc_r",
}


def _parse_sda_table(payload: Any) -> list[dict[str, Any]]:
    table = (payload or {}).get("Table") or []
    if len(table) < 2:
        return []
    header = table[0]
    rows = []
    for values in table[1:]:
        row: dict[str, Any] = {}
        for column, value in zip(header, values, strict=False):
            if column in NUMERIC_COLUMNS and value is not None:
                try:
                    row[column] = float(value)
                except (TypeError, ValueError):
                    row[column] = None
            else:
                row[column] = value
        rows.append(row)
    return rows


async def _usda_sda(client: CachedHTTP, lat: float, lon: float, root_depth_cm: float) -> ProviderResult | None:
    query = SDA_QUERY.format(lon=f"{lon:.6f}", lat=f"{lat:.6f}")
    raw, cached = await client.post_json(
        SDA_URL,
        body={"query": query, "format": "JSON+COLUMNNAME"},
        ttl=30 * 24 * 3600,
        timeout=25,
    )
    rows = _parse_sda_table(raw)
    if not rows:
        return None

    dominant_key = max(rows, key=lambda r: (r.get("comppct_r") or 0, r.get("cokey") or 0)).get("cokey")
    horizons = [r for r in rows if r.get("cokey") == dominant_key]
    dominant = horizons[0]

    clay = _weighted_mean(horizons, "claytotal_r", 0, root_depth_cm)
    sand = _weighted_mean(horizons, "sandtotal_r", 0, root_depth_cm)
    silt = _weighted_mean(horizons, "silttotal_r", 0, root_depth_cm)
    om_top = _weighted_mean(horizons, "om_r", 0, 25)
    om_root = _weighted_mean(horizons, "om_r", 0, root_depth_cm)

    payload = {
        "provider": "USDA-NRCS Soil Data Access (SSURGO)",
        "coverage": "Estados Unidos (SSURGO)",
        "map_unit": {
            "mukey": dominant.get("mukey"),
            "name": dominant.get("muname"),
            "dominant_component": dominant.get("compname"),
            "component_pct": dominant.get("comppct_r"),
        },
        "root_depth_cm": root_depth_cm,
        "texture_class": classify_texture(sand, silt, clay),
        "clay_pct": clay,
        "sand_pct": sand,
        "silt_pct": silt,
        "organic_matter_pct_0_25cm": om_top,
        "organic_matter_pct": om_top,
        "organic_matter_pct_rootzone": om_root,
        "awc_mm_rootzone": _awc_mm(horizons, 0, root_depth_cm),
        "drainage_class": dominant.get("drainagecl"),
        "hydrologic_group": dominant.get("hydgrp"),
        "slope_pct": dominant.get("slope_r"),
        "horizons": [
            {
                "top_cm": r.get("hzdept_r"),
                "bottom_cm": r.get("hzdepb_r"),
                "clay_pct": r.get("claytotal_r"),
                "sand_pct": r.get("sandtotal_r"),
                "silt_pct": r.get("silttotal_r"),
                "organic_matter_pct": r.get("om_r"),
                "awc_cm_per_cm": r.get("awc_r"),
            }
            for r in horizons[:8]
        ],
        "attribution": "USDA-NRCS SSURGO via Soil Data Access — https://sdmdataaccess.sc.egov.usda.gov/",
    }
    return ProviderResult(name="USDA Soil Data Access (SSURGO)", data=payload, cached=cached)


async def _query_soilgrids(
    client: CachedHTTP, lat: float, lon: float
) -> tuple[dict[str, Any] | None, bool]:
    """Consulta um ponto exato no SoilGrids. Devolve (payload, veio_do_cache)."""
    raw, cached = await client.get_json(
        SOILGRIDS_URL,
        params=[
            ("lon", f"{lon:.4f}"),
            ("lat", f"{lat:.4f}"),
            ("property", "clay"),
            ("property", "sand"),
            ("property", "silt"),
            ("property", "soc"),
            ("property", "phh2o"),
            ("property", "nitrogen"),
            ("property", "bdod"),
            ("property", "wv0033"),
            ("property", "wv1500"),
            ("depth", "0-5cm"),
            ("depth", "5-15cm"),
            ("depth", "15-30cm"),
            ("value", "mean"),
        ],
        ttl=30 * 24 * 3600,
        timeout=60,
    )
    layers = ((raw or {}).get("properties") or {}).get("layers") or []
    if not layers:
        return None, cached

    # Agrupa por profundidade para poder ponderar por espessura de camada.
    by_depth: dict[tuple[float, float], dict[str, float]] = {}
    for layer in layers:
        name = layer.get("name")
        factor = (layer.get("unit_measure") or {}).get("d_factor") or 1
        for depth in layer.get("depths") or []:
            mean = (depth.get("values") or {}).get("mean")
            top = (depth.get("range") or {}).get("top_depth")
            bottom = (depth.get("range") or {}).get("bottom_depth")
            if mean is None or top is None or bottom is None or bottom <= top:
                continue
            value = mean / factor
            # Umidade volumétrica vem em unidades de 10^-3 cm³/cm³.
            if name in {"wv0033", "wv1500", "wv0010"} and value > 1:
                value /= 100
            by_depth.setdefault((float(top), float(bottom)), {})[name] = value

    if not any(values.get("clay") for values in by_depth.values()):
        return None, cached

    def weighted(name: str, top_limit: float = 0, bottom_limit: float = 30) -> float | None:
        total, weight = 0.0, 0.0
        for (top, bottom), values in by_depth.items():
            value = values.get(name)
            if value is None:
                continue
            overlap = min(bottom, bottom_limit) - max(top, top_limit)
            if overlap <= 0:
                continue
            total += value * overlap
            weight += overlap
        return round(total / weight, 3) if weight else None

    sand, silt, clay = weighted("sand"), weighted("silt"), weighted("clay")
    field_capacity, wilting_point = weighted("wv0033"), weighted("wv1500")
    awc_mm = None
    if field_capacity is not None and wilting_point is not None:
        awc_mm = round((field_capacity - wilting_point) * 30 * 10, 1)

    payload = {
        "provider": "ISRIC SoilGrids 2.0",
        "coverage": "global (250 m, 0-30 cm)",
        "root_depth_cm": 30,
        "texture_class": classify_texture(sand, silt, clay),
        "clay_pct": clay,
        "sand_pct": sand,
        "silt_pct": silt,
        "organic_carbon_g_kg_0_30cm": weighted("soc"),
        "ph_h2o": weighted("phh2o"),
        "nitrogen_g_kg_0_30cm": weighted("nitrogen"),
        "bulk_density_g_cm3": weighted("bdod"),
        "field_capacity_m3m3": field_capacity,
        "wilting_point_m3m3": wilting_point,
        "awc_mm_rootzone": awc_mm,
        "attribution": "ISRIC SoilGrids — https://soilgrids.org/ (CC BY 4.0)",
    }
    return payload, cached


async def _soilgrids(client: CachedHTTP, lat: float, lon: float) -> ProviderResult | None:
    """Fallback global (250 m) para pontos fora dos EUA.

    O pixel exato pode cair em estrada, água ou área sem dado (a API devolve
    nulo). Nesse caso tentamos pixels vizinhos (~1 km) antes de desistir — é
    melhor um solo aproximado e rotulado do que nenhum solo.
    """
    offsets = [
        (0.0, 0.0),
        (0.01, 0.0),
        (-0.01, 0.0),
        (0.0, 0.01),
        (0.0, -0.01),
        (0.02, 0.02),
        (-0.02, -0.02),
    ]
    for index, (delta_lat, delta_lon) in enumerate(offsets):
        try:
            payload, cached = await _query_soilgrids(
                client, lat + delta_lat, lon + delta_lon
            )
        except Exception:  # noqa: BLE001
            payload, cached = None, False
        if payload:
            if index > 0:
                payload["sample_offset_deg"] = [delta_lat, delta_lon]
                payload["note"] = (
                    "pixel exato sem dado; amostrado em pixel vizinho (~1 km)"
                )
            return ProviderResult(name="ISRIC SoilGrids", data=payload, cached=cached)
    return None


async def context(
    client: CachedHTTP,
    *,
    lat: float,
    lon: float,
    root_depth_cm: float = 100,
    override: dict[str, Any] | None = None,
) -> ProviderResult:
    warnings: list[str] = []

    try:
        result = await _usda_sda(client, lat, lon, root_depth_cm)
    except Exception as exc:  # noqa: BLE001
        result = None
        warnings.append(f"SDA indisponível: {type(exc).__name__}")

    if result is None:
        try:
            result = await _soilgrids(client, lat, lon)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"SoilGrids indisponível: {type(exc).__name__}")

    if result is None:
        result = ProviderResult(
            name="Solo (sem cobertura automática)",
            ok=True,
            data={"provider": None, "root_depth_cm": root_depth_cm},
            detail="Ponto fora da cobertura SSURGO e SoilGrids sem valores",
        )
        warnings.append(
            "Sem dados de solo automáticos para este ponto: envie 'soil_override' "
            "(texto do solo pelo agricultor) para o cálculo ficar confiável."
        )

    data = dict(result.data or {})
    origin_source = data.get("provider") or "sem fonte automática"
    meta_keys = {
        "provider",
        "coverage",
        "attribution",
        "horizons",
        "component",
        "user_override",
        "origins",
        "note",
        "sample_offset_deg",
    }

    origins: dict[str, str] = {}
    for key, value in data.items():
        if value is not None and key not in meta_keys:
            origins[key] = origin_source

    if override:
        applied = {k: v for k, v in override.items() if v is not None}
        data.update(applied)
        for key in applied:
            origins[key] = "medido/informado pelo produtor"
        if applied.get("organic_matter_pct") is not None:
            data["organic_matter_pct_0_25cm"] = applied["organic_matter_pct"]
        if any(applied.get(k) is not None for k in ("clay_pct", "sand_pct", "silt_pct")):
            data["texture_class"] = classify_texture(
                data.get("sand_pct"), data.get("silt_pct"), data.get("clay_pct")
            )
            origins["texture_class"] = "calculado a partir do solo informado"
        data["provider"] = f"{origin_source} + ajuste do agricultor"
        data["user_override"] = True

    # Água disponível na zona radicular: prioriza valor medido; senão deriva de
    # capacidade de campo - ponto de murcha multiplicado pela profundidade.
    root_depth_cm_effective = float(data.get("root_depth_cm") or root_depth_cm or 100)
    field_capacity = data.get("field_capacity_m3m3")
    wilting_point = data.get("wilting_point_m3m3")
    awc_measured = bool(override and override.get("awc_mm_rootzone") is not None)
    recompute_awc = bool(
        override
        and (
            override.get("field_capacity_m3m3") is not None
            or override.get("wilting_point_m3m3") is not None
        )
    )
    if (
        field_capacity is not None
        and wilting_point is not None
        and not awc_measured
        and (data.get("awc_mm_rootzone") is None or recompute_awc)
    ):
        data["awc_mm_rootzone"] = round(
            (field_capacity - wilting_point) * root_depth_cm_effective * 10, 1
        )
        origins["awc_mm_rootzone"] = "calculado (FC - PWP) x profundidade efetiva"

    data["origins"] = origins
    result.data = data
    result.warnings.extend(warnings)
    return result
