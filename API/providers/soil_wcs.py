
"""ISRIC SoilGrids WCS — CerradoShift.

Consulta propriedades estimadas do solo para coordenadas WGS84.
Profundidade suportada: 5 a 30 cm.

Instalação:
    pip install httpx rasterio numpy

Observação:
    São estimativas espaciais, não medições laboratoriais.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import time
from pathlib import Path
from typing import Any

import httpx
import numpy as np
from rasterio.io import MemoryFile
from rasterio.errors import RasterioIOError
from rasterio.warp import transform

from providers.soil import classify_texture


# =====================================================
# CONFIGURAÇÃO
# =====================================================

WCS_ROOT = "https://maps.isric.org/mapserv"

CRS_SUBSET = (
    "http://www.opengis.net/def/crs/EPSG/0/4326"
)

CRS_OUTPUT = (
    "http://www.opengis.net/def/crs/EPSG/0/152160"
)

LAYERS = (
    "clay",
    "sand",
    "silt",
    "phh2o",
    "soc",
    "wv0033",
    "wv1500",
)

DEPTHS = (
    (0, 5),
    (5, 15),
    (15, 30),
)

FACTORS = {
    "clay": 10.0,
    "sand": 10.0,
    "silt": 10.0,
    "phh2o": 10.0,
    "soc": 10.0,
    "wv0033": 1000.0,
    "wv1500": 1000.0,
}

CACHE_DIR = Path(
    os.getenv(
        "SOIL_WCS_CACHE_DIR",
        ".cache/soil_wcs",
    )
)

CACHE_VERSION = "v6_dynamic_coverage"
CACHE_TTL = 30 * 24 * 3600

SEM = asyncio.Semaphore(1)

DEBUG = os.getenv(
    "SOIL_WCS_DEBUG", "false"
).lower() == "true"


def debug(*args):
    if DEBUG:
        print("[SoilGrids]", *args, flush=True)


# =====================================================
# CACHE
# =====================================================

def _cache_path(lat, lon, prop, depth):
    key = hashlib.sha256(
        (
            f"{CACHE_VERSION}|{lat:.5f}|{lon:.5f}|"
            f"{prop}|{depth}"
        ).encode()
    ).hexdigest()

    return CACHE_DIR / f"{key}.json"


def _cached(path):
    try:
        if (
            time.time() - path.stat().st_mtime
            > CACHE_TTL
        ):
            return None

        data = json.loads(
            path.read_text(encoding="utf-8")
        )

        value = data.get("value")

        if value is None:
            return None

        value = float(value)

        if not math.isfinite(value):
            return None

        # Não reutilizar os zeros do cache antigo.
        # O sistema deverá consultar novamente.
        if value == 0:
            return None

        return value

    except (
        OSError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
    ):
        return None


def _save_cache(path, value):
    if value is None or not math.isfinite(value):
        return

    # Não armazenamos zeros até esclarecer
    # a origem dos valores neste serviço.
    if value == 0:
        return

    CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    tmp = path.with_suffix(".tmp")

    tmp.write_text(
        json.dumps({
            "version": CACHE_VERSION,
            "value": value,
        }),
        encoding="utf-8",
    )

    tmp.replace(path)


# =====================================================
# LEITURA DO GEOTIFF
# =====================================================

def _sample_geotiff(
    content: bytes,
    lon: float,
    lat: float,
    layer_name: str,
) -> float:

    if content[:4] not in (
        b"II*\x00",
        b"MM\x00*",
    ):
        raise ValueError(
            f"{layer_name}: resposta não é GeoTIFF"
        )

    try:
        with MemoryFile(content) as mem:
            with mem.open() as ds:

                if ds.crs is None:
                    raise ValueError(
                        f"{layer_name}: raster sem CRS"
                    )

                xs, ys = transform(
                    "EPSG:4326",
                    ds.crs,
                    [lon],
                    [lat],
                )

                row, col = ds.index(
                    xs[0],
                    ys[0],
                )

                if not (
                    0 <= row < ds.height
                    and 0 <= col < ds.width
                ):
                    raise ValueError(
                        f"{layer_name}: ponto fora do raster"
                    )

                raster = ds.read(
                    1,
                    masked=True,
                )


                pixels_validos = raster.compressed()
                pixels_nao_zero = pixels_validos[
                    pixels_validos != 0
                ]

                print("\n===== DIAGNÓSTICO WCS =====")
                print("Camada:", layer_name)
                print("CRS:", ds.crs)
                print("NoData:", ds.nodata)
                print("Bounds:", ds.bounds)
                print("Dimensões:", ds.width, ds.height)
                print("Posição do ponto:", row, col)
                print("Máscara do ponto:", bool(np.ma.getmaskarray(raster)[row, col]))

                print("Pixels válidos:", pixels_validos.size)
                print("Pixels diferentes de zero:",
                      pixels_nao_zero.size)

                if pixels_validos.size:
                    print("Mínimo:", pixels_validos.min())
                    print("Máximo:", pixels_validos.max())

                if pixels_nao_zero.size:
                    print(
                        "Exemplo não zero:",
                        pixels_nao_zero[:10].tolist()
                    )

                print("===========================\n")

                valid_pixels = raster.compressed()

                if valid_pixels.size == 0:
                    raise ValueError(
                        f"{layer_name}: raster sem pixels válidos"
                    )

                pixel = raster[row, col]

                if np.ma.is_masked(pixel):
                    raise ValueError(
                        f"{layer_name}: pixel central NoData"
                    )

                value = float(pixel)

                if not math.isfinite(value):
                    raise ValueError(
                        f"{layer_name}: valor não finito"
                    )

                if value <= -32768:
                    raise ValueError(
                        f"{layer_name}: sentinel NoData"
                    )

                debug(
                    layer_name,
                    "CRS:", ds.crs,
                    "NODATA:", ds.nodata,
                    "dimensões:",
                    (ds.width, ds.height),
                    "posição:",
                    (row, col),
                    "valor bruto:", value,
                    "mínimo:",
                    float(valid_pixels.min()),
                    "máximo:",
                    float(valid_pixels.max()),
                )

                # Neste projeto, zeros de todas
                # as camadas estão sendo investigados.
                # Não utilizar zero como medição
                # até validar sua origem.
                if value == 0:
                    raise ValueError(
                        f"{layer_name}: pixel central zero; "
                        "verificar cobertura e NoData"
                    )

                return value

    except RasterioIOError as exc:
        raise ValueError(
            f"{layer_name}: GeoTIFF ilegível"
        ) from exc


# =====================================================
# CONSULTA WCS
# =====================================================

async def _fetch_one(
    client: httpx.AsyncClient,
    lat: float,
    lon: float,
    prop: str,
    depth: str,
    half_span_deg: float,
):

    path = _cache_path(
        lat,
        lon,
        prop,
        depth,
    )

    cached = _cached(path)

    if cached is not None:
        debug(prop, depth, "CACHE:", cached)

        return prop, depth, cached, None

    # Formato oficial MapServer do SoilGrids.
    url = WCS_ROOT
    layer_name = f"{prop}_{depth}"

    params = [
        ("map", f"/map/{prop}.map"),
        ("SERVICE", "WCS"),
        ("VERSION", "2.0.1"),
        ("REQUEST", "GetCoverage"),
        ("COVERAGEID", f"{prop}_{depth}_mean"),
        ("FORMAT", "GEOTIFF_INT16"),
        ("SUBSETTINGCRS", CRS_SUBSET),
        ("OUTPUTCRS", CRS_OUTPUT),
        (
            "SUBSET",
            f"X({lon-half_span_deg:.6f},"
            f"{lon+half_span_deg:.6f})",
        ),
        (
            "SUBSET",
            f"Y({lat-half_span_deg:.6f},"
            f"{lat+half_span_deg:.6f})",
        ),
    ]

    

    try:
        async with SEM:
            response = await client.get(
                url,
                params=params,
            )
            response.raise_for_status()

        debug("URL:", str(response.request.url))

        if response.content[:4] not in (
            b"II*\x00",
            b"MM\x00*",
        ):
            raise ValueError(
                "Resposta não é GeoTIFF: "
                + response.text[:200]
            )

        value = _sample_geotiff(
            response.content,
            lon,
            lat,
            layer_name,
        )

        _save_cache(path, value)

        return prop, depth, value, None

    except (
        httpx.HTTPError,
        ValueError,
        OSError,
        RasterioIOError,
    ) as exc:
        error = (
            f"{layer_name}: "
            f"{type(exc).__name__}: {exc}"
        )

        debug("ERRO:", error)

        return prop, depth, None, error



# =====================================================
# AGREGAÇÃO POR PROFUNDIDADE
# =====================================================

def _depth_weighted(
    values: dict[str, float],
    root_depth_cm: float,
) -> float | None:

    weighted = 0.0
    total = 0.0

    for top, bottom in DEPTHS:

        depth_name = f"{top}-{bottom}cm"

        overlap = max(
            0.0,
            min(root_depth_cm, bottom) - top,
        )

        if overlap <= 0:
            continue

        if depth_name not in values:
            return None

        weighted += (
            values[depth_name] * overlap
        )

        total += overlap

    if total == 0:
        return None

    return weighted / total


# =====================================================
# VALIDAÇÃO DAS PROPRIEDADES
# =====================================================

def _valid_property(prop, value):
    if value is None:
        return False

    if not math.isfinite(value):
        return False

    if prop in ("clay", "sand", "silt"):
        return 0 <= value <= 100

    if prop == "phh2o":
        return 2 <= value <= 12

    if prop == "soc":
        return 0 < value <= 1000

    if prop in ("wv0033", "wv1500"):
        return 0 <= value <= 1

    return False


# =====================================================
# FUNÇÃO PRINCIPAL
# =====================================================

async def consultar_solo(
    lat: float,
    lon: float,
    root_depth_cm: float = 30,
    *,
    timeout_seconds: float = 55,
) -> dict[str, Any]:

    if not (
        -90 <= lat <= 90
        and -180 <= lon <= 180
    ):
        raise ValueError(
            "Latitude ou longitude inválida"
        )

    if not 5 <= root_depth_cm <= 30:
        raise ValueError(
            "Profundidade suportada: 5 a 30 cm"
        )

    data = {
        "provider": None,
        "user_override": False,
        "root_depth_cm": root_depth_cm,
        "origins": {},
        "warnings": [],
        "attribution": (
            "ISRIC SoilGrids 2.0 (CC BY 4.0)"
        ),
        "coverage": (
            "Estimativas espaciais globais ~250 m"
        ),
    }

    values = {
        prop: {}
        for prop in LAYERS
    }

    errors = []

    jobs = [
        (
            prop,
            f"{top}-{bottom}cm",
        )
        for prop in LAYERS
        for top, bottom in DEPTHS
        if top < root_depth_cm
    ]

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(
            45,
            connect=10,
        ),
        headers={
            "User-Agent": (
                "CerradoShift/1.0 "
                "(academic prototype)"
            )
        },
    ) as client:

        tasks = [
            _fetch_one(
                client,
                lat,
                lon,
                prop,
                depth,
                0.007,
            )
            for prop, depth in jobs
        ]

        try:
            rows = await asyncio.wait_for(
                asyncio.gather(*tasks),
                timeout=timeout_seconds,
            )

        except asyncio.TimeoutError:
            data["warnings"].append(
                "Tempo limite do WCS excedido."
            )
            return data

    for prop, depth, raw, err in rows:

        if err:
            errors.append(err)
            continue

        if raw is None:
            continue

        # Conversão para unidades usuais.
        converted = raw / FACTORS[prop]

        if not _valid_property(
            prop,
            converted,
        ):
            errors.append(
                f"{prop}_{depth}: valor fora da "
                f"faixa física ({converted})"
            )
            continue

        values[prop][depth] = converted

    aggregated = {
        prop: _depth_weighted(
            values[prop],
            root_depth_cm,
        )
        for prop in LAYERS
    }

    mapping = {
        "clay": "clay_pct",
        "sand": "sand_pct",
        "silt": "silt_pct",
        "phh2o": "ph_h2o",
        "soc": "organic_carbon_g_kg_0_30cm",
    }

    for prop, field in mapping.items():

        value = aggregated[prop]

        if value is None:
            continue

        if not _valid_property(
            prop,
            value,
        ):
            continue

        data[field] = round(value, 3)

        data["origins"][field] = (
            "ISRIC SoilGrids WCS, "
            f"média ponderada 0-{root_depth_cm:g} cm"
        )

    # Validação da textura
    sand = data.get("sand_pct")
    silt = data.get("silt_pct")
    clay = data.get("clay_pct")

    if all(
        isinstance(v, (int, float))
        for v in (sand, silt, clay)
    ):
        total = sand + silt + clay

        if 95 <= total <= 105:

            data["texture_class"] = (
                classify_texture(
                    sand,
                    silt,
                    clay,
                )
            )

            data["origins"]["texture_class"] = (
                "Derivada das frações SoilGrids"
            )

        else:
            for field in (
                "sand_pct",
                "silt_pct",
                "clay_pct",
            ):
                data.pop(field, None)
                data["origins"].pop(field, None)

            data["warnings"].append(
                "Textura descartada: "
                f"frações somam {total:.2f}%."
            )

    # Retenção hídrica
    fc = aggregated["wv0033"]
    wp = aggregated["wv1500"]

    if (
        fc is not None
        and wp is not None
        and 0 <= wp < fc <= 1
    ):
        data["field_capacity_m3m3"] = (
            round(fc, 4)
        )

        data["wilting_point_m3m3"] = (
            round(wp, 4)
        )

        data["awc_mm_rootzone"] = round(
            (fc - wp) * root_depth_cm * 10,
            2,
        )

        for field in (
            "field_capacity_m3m3",
            "wilting_point_m3m3",
            "awc_mm_rootzone",
        ):
            data["origins"][field] = (
                "SoilGrids WCS, estimativa "
                "a partir de 33/1500 kPa"
            )

    # Considera o provedor disponível somente
    # quando existirem atributos aproveitáveis.
    valid_fields = (
        "clay_pct",
        "sand_pct",
        "silt_pct",
        "ph_h2o",
        "organic_carbon_g_kg_0_30cm",
        "awc_mm_rootzone",
    )

    if any(
        data.get(field) is not None
        for field in valid_fields
    ):
        data["provider"] = (
            "ISRIC SoilGrids 2.0 WCS "
            "(estimativa global)"
        )
    else:
        data["warnings"].append(
            "Nenhum atributo quantitativo "
            "confiável foi obtido do WCS."
        )

    if errors:
        data["warnings"].append(
            f"{len(errors)}/{len(rows)} "
            "coberturas não foram aproveitadas."
        )

        data["layer_errors"] = errors[:10]

    data["warnings"].append(
        "Estimativas espaciais não substituem "
        "análises laboratoriais do talhão."
    )

    return data
