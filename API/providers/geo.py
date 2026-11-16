from __future__ import annotations

import os
import shutil
from pathlib import Path

# ---------------------------------------------------------------------------
# IMPORTANTE (Windows + usuário com acento no nome)
# O GDAL usa a CA bundle do certifi; se o caminho tiver caracteres fora do
# cp1252 (ex.: "C:\Users\Ângiló\..."), o schannel falha com
# "invalid path name for CA file". Copiamos o cacert.pem para um caminho ASCII
# e apontamos as variáveis ANTES de importar rasterio.
# ---------------------------------------------------------------------------


def _prepare_ssl() -> None:
    if os.name != "nt":
        return
    try:
        import certifi
    except ImportError:
        return

    source = Path(certifi.where())
    if str(source).isascii():
        return

    for base in (os.getenv("PUBLIC"), r"C:\ProgramData", os.getenv("TEMP")):
        if not base:
            continue
        target = Path(base) / "nasa-agro-ca.pem"
        try:
            shutil.copyfile(source, target)
        except OSError:
            continue
        for key in ("CURL_CA_BUNDLE", "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "GDAL_CURL_CA_BUNDLE"):
            os.environ[key] = str(target)
        return


_prepare_ssl()

import asyncio  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import time  # noqa: E402
from datetime import date  # noqa: E402
from typing import Any  # noqa: E402

import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from rasterio.features import geometry_mask  # noqa: E402
from rasterio.warp import transform_bounds, transform_geom  # noqa: E402
from rasterio.windows import Window, from_bounds  # noqa: E402

from clients import CachedHTTP  # noqa: E402
from config import settings  # noqa: E402
from providers.base import ProviderResult  # noqa: E402

STAC_SEARCH = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
SAS_TOKEN = "https://planetarycomputer.microsoft.com/api/sas/v1/token/{collection}"
COLLECTIONS = ["hls2-s30", "hls2-l30"]

# Fmask (HLS): bit1 nuvem, bit2 adjacente a nuvem, bit3 sombra, bit4 neve/gelo.
FMASK_BAD_BITS = 0b11110

SERIES_TTL = 6 * 3600


def _bounds(geometry: dict[str, Any]) -> tuple[float, float, float, float]:
    coords = geometry.get("coordinates") or []
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

    walk(coords)
    if not points:
        raise ValueError("geometria sem coordenadas")
    lons = [p[0] for p in points]
    lats = [p[1] for p in points]
    return min(lons), min(lats), max(lons), max(lats)


def centroid(geometry: dict[str, Any]) -> tuple[float, float]:
    """Centroide simples (média dos vértices) em lon/lat (WGS84)."""
    left, bottom, right, top = _bounds(geometry)
    return (left + right) / 2, (bottom + top) / 2


def polygon_area_ha(geometry: dict[str, Any]) -> float | None:
    """Área aproximada (ha) reprojetando para a UTM da zona do centroide."""
    try:
        from shapely.geometry import shape
    except ImportError:  # pragma: no cover
        return None

    left, bottom, right, top = _bounds(geometry)
    centre_lon = (left + right) / 2
    zone = int((centre_lon + 180) / 6) + 1
    epsg = 32600 + zone if (bottom + top) / 2 >= 0 else 32700 + zone
    try:
        projected = transform_geom("EPSG:4326", f"EPSG:{epsg}", geometry)
        return round(shape(projected).area / 10_000, 2)
    except Exception:  # noqa: BLE001
        return None


def _cache_path(geometry: dict[str, Any], start: date, end: date, max_scenes: int, evi: bool) -> Path:
    payload = json.dumps(
        {"g": geometry, "s": start.isoformat(), "e": end.isoformat(), "n": max_scenes, "evi": evi},
        sort_keys=True,
    )
    key = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
    directory = settings.cache_dir / "vegetation"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{key}.json"


def _read_cache(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
        if time.time() - envelope["stored_at"] > SERIES_TTL:
            return None
        return envelope["data"]
    except (OSError, ValueError, KeyError):
        return None


def _write_cache(path: Path, data: dict[str, Any]) -> None:
    try:
        path.write_text(
            json.dumps({"stored_at": time.time(), "data": data}, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass


def _read_scene(item: dict[str, Any], token: str, geometry: dict[str, Any], include_evi: bool) -> dict[str, Any]:
    """Abre só a janela do talhão dentro do COG e calcula NDVI (e EVI)."""
    assets = item.get("assets") or {}

    def href(key: str) -> str | None:
        asset = assets.get(key)
        return f"{asset['href']}?{token}" if asset else None

    red_url, nir_url, blue_url, fmask_url = href("B04"), href("B05"), href("B02"), href("Fmask")
    if not (red_url and nir_url):
        raise ValueError("cena sem bandas B04/B05")

    left, bottom, right, top = _bounds(geometry)
    env = rasterio.Env(
        GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
        CPL_VSIL_CURL_USE_HEAD="NO",
        GDAL_HTTP_MULTIPLEX="YES",
        GDAL_HTTP_TIMEOUT="40",
    )

    with env:
        with rasterio.open(red_url) as dataset:
            projected_bounds = transform_bounds("EPSG:4326", dataset.crs, left, bottom, right, top)
            window = from_bounds(*projected_bounds, transform=dataset.transform)
            window = window.round_offsets().round_lengths()
            window = window.intersection(Window(0, 0, dataset.width, dataset.height))
            height, width = int(window.height), int(window.width)
            if height < 2 or width < 2:
                raise ValueError("talhão fora da cena")

            red = dataset.read(1, window=window).astype("float32")
            proj_geom = transform_geom("EPSG:4326", dataset.crs, geometry)
            inside = geometry_mask(
                [proj_geom],
                out_shape=(height, width),
                transform=dataset.window_transform(window),
                invert=True,
            )

        with rasterio.open(nir_url) as dataset:
            nir = dataset.read(1, window=window).astype("float32")

        blue = None
        if include_evi and blue_url:
            with rasterio.open(blue_url) as dataset:
                blue = dataset.read(1, window=window).astype("float32")

        fmask = None
        if fmask_url:
            with rasterio.open(fmask_url) as dataset:
                fmask = dataset.read(1, window=window)

    valid = inside & (red > 0) & (nir > 0)
    if fmask is not None:
        valid &= (fmask & FMASK_BAD_BITS) == 0
    if valid.sum() < 10:
        raise ValueError(f"poucos pixels válidos ({int(valid.sum())})")

    denominator = nir + red
    ndvi = np.full(red.shape, np.nan, dtype="float32")
    np.divide(nir - red, denominator, out=ndvi, where=denominator > 0)
    ndvi_values = ndvi[valid & np.isfinite(ndvi)]
    if ndvi_values.size == 0:
        raise ValueError("NDVI sem valores válidos")

    result: dict[str, Any] = {
        "scene_id": item.get("id"),
        "collection": item.get("collection"),
        "date": (item.get("properties") or {}).get("datetime", "")[:10],
        "platform": (item.get("properties") or {}).get("platform"),
        "cloud_cover_pct": (item.get("properties") or {}).get("eo:cloud_cover"),
        "valid_pixel_pct": round(100 * valid.sum() / inside.sum(), 1) if inside.sum() else None,
        "ndvi_mean": round(float(np.mean(ndvi_values)), 4),
        "ndvi_median": round(float(np.median(ndvi_values)), 4),
    }

    if include_evi and blue is not None:
        red01, nir01, blue01 = red / 10000.0, nir / 10000.0, blue / 10000.0
        evi_den = nir01 + 6.0 * red01 - 7.5 * blue01 + 1.0
        evi = np.full(red.shape, np.nan, dtype="float32")
        np.divide(2.5 * (nir01 - red01), evi_den, out=evi, where=np.abs(evi_den) > 1e-6)
        evi_values = evi[valid & np.isfinite(evi)]
        if evi_values.size:
            clipped = np.clip(evi_values, -1.0, 1.0)
            result["evi_mean"] = round(float(np.mean(clipped)), 4)

    return result


async def vegetation_series(
    client: CachedHTTP,
    *,
    geometry: dict[str, Any],
    start: date,
    end: date,
    max_scenes: int = 8,
    include_evi: bool = True,
) -> ProviderResult:
    """Série de NDVI/EVI por talhão (HLS S30/L30), pronta para o gráfico.

    Lê apenas a janela do polígono em cada COG e mascara nuvem/sombra pelo
    Fmask. Não baixa a cena inteira.
    """
    cache_path = _cache_path(geometry, start, end, max_scenes, include_evi)
    cached_series = _read_cache(cache_path)
    if cached_series is not None:
        return ProviderResult(
            name="HLS NDVI/EVI (STAC + COG)",
            data=cached_series,
            cached=True,
        )

    query = {
        "collections": COLLECTIONS,
        "intersects": geometry,
        "datetime": f"{start.isoformat()}T00:00:00Z/{end.isoformat()}T23:59:59Z",
        "limit": max_scenes,
        "sortby": [{"field": "properties.datetime", "direction": "desc"}],
        "query": {"eo:cloud_cover": {"lt": 90}},
    }
    raw, _ = await client.post_json(STAC_SEARCH, body=query, ttl=3600, timeout=30)
    items = (raw or {}).get("features") or []
    if not items:
        raise ValueError("nenhuma cena HLS encontrada para o período")

    tokens: dict[str, str] = {}
    for collection in {item.get("collection") for item in items if item.get("collection")}:
        data, _ = await client.get_json(SAS_TOKEN.format(collection=collection), ttl=1800, timeout=20)
        token = (data or {}).get("token")
        if token:
            tokens[collection] = token
    if not tokens:
        raise ValueError("não foi possível assinar as cenas (SAS token)")

    tasks = [
        asyncio.to_thread(_read_scene, item, tokens[item["collection"]], geometry, include_evi)
        for item in items
        if item.get("collection") in tokens
    ]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    scenes: list[dict[str, Any]] = []
    errors: list[str] = []
    for outcome in raw_results:
        if isinstance(outcome, Exception):
            errors.append(f"{type(outcome).__name__}: {outcome}"[:200])
        else:
            scenes.append(outcome)

    scenes.sort(key=lambda s: s["date"])
    if not scenes:
        raise ValueError(f"nenhuma cena pôde ser processada. Ex.: {errors[:1]}")

    latest = scenes[-1]
    trend = None
    if len(scenes) >= 3:
        values = [s["ndvi_mean"] for s in scenes]
        slope = float(np.polyfit(range(len(values)), values, 1)[0])
        trend = "subindo" if slope > 0.01 else "caindo" if slope < -0.01 else "estável"

    payload = {
        "source": "HLS v2 (Harmonized Landsat-Sentinel) via Planetary Computer STAC",
        "resolution_m": "30 (HLS)",
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "scenes_requested": len(items),
        "scenes_processed": len(scenes),
        "scenes": scenes,
        "latest": latest,
        "trend": trend,
        "warning": (
            "NDVI/EVI indicam vigor da vegetação, não diagnosticam a causa "
            "(praga, água ou nutriente). Use junto com solo e clima."
        ),
        "attribution": "HLS (NASA/USGS) — processado via Microsoft Planetary Computer",
    }
    _write_cache(cache_path, payload)

    return ProviderResult(
        name="HLS NDVI/EVI (STAC + COG)",
        data=payload,
        cached=False,
        warnings=[f"{len(errors)} cena(s) ignorada(s)"] if errors else [],
    )
