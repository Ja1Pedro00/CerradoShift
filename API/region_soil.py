"""Diagnóstico regional de solo para o CerradoShift.

Brasil: MapBiomas Solo (granulometria), Embrapa/IBGE (pedologia) e,
opcionalmente, SoilGrids WCS (atributos complementares).
Outros países: provedor global legado. Dados manuais têm prioridade.
Dados geoespaciais são estimativas; não substituem laudos do talhão.
"""
from __future__ import annotations

import asyncio
import importlib
import logging
import math
import os
from datetime import datetime, timezone
from typing import Any, Literal

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from schemas import SoilOverride
from soil_diagnostic import diagnose
from providers.soil import classify_texture
from providers import soil_wcs
from providers.brasil import embrapa, ibge_solos

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/region", tags=["Diagnóstico regional"])

TEXTURE_FIELDS = ("sand_pct", "silt_pct", "clay_pct")
SOIL_FIELDS = (
    "clay_pct", "sand_pct", "silt_pct", "texture_class", "ph_h2o",
    "organic_matter_pct", "organic_carbon_g_kg_0_30cm", "awc_mm_rootzone",
    "field_capacity_m3m3", "wilting_point_m3m3",
)


class RegionalSoilRequest(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    root_depth_cm: float = Field(default=30, ge=10, le=300)
    country_code: Literal["BR"] | None = None
    soil_override: SoilOverride | None = None


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _enabled(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"true", "1", "yes", "on"}


def _clear(data: dict, fields: tuple[str, ...], warnings: list[str], message: str) -> None:
    warnings.append(message)
    for key in fields:
        data[key] = None
        (data.get("origins") or {}).pop(key, None)


def validate_soil(soil_data: dict, warnings: list[str]) -> dict:
    """Descarta valores incompatíveis, sem preencher ausências com estimativas fictícias."""
    data = dict(soil_data)
    data["origins"] = dict(data.get("origins") or {})
    portions = [data.get(field) for field in TEXTURE_FIELDS]
    if all(_is_number(v) for v in portions):
        if any(v < 0 or v > 100 for v in portions) or not 95 <= sum(portions) <= 105:
            _clear(data, (*TEXTURE_FIELDS, "texture_class"), warnings,
                   "Textura inválida: areia, silte e argila devem somar aproximadamente 100%.")
        else:
            data["texture_class"] = classify_texture(
                data["sand_pct"], data["silt_pct"], data["clay_pct"]
            )
            data["origins"].setdefault("texture_class", "calculada a partir das frações texturais")
    else:
        # O diagnóstico só pode classificar textura com três frações válidas.
        if any(v is not None for v in portions):
            warnings.append("Textura incompleta: é necessário obter as três frações.")
        for field in (*TEXTURE_FIELDS, "texture_class"):
            data[field] = None
            data["origins"].pop(field, None)

    ph = data.get("ph_h2o")
    if ph is not None and (not _is_number(ph) or not 2 <= ph <= 12):
        _clear(data, ("ph_h2o",), warnings, "pH fora do intervalo de validação (2 a 12).")

    for field in ("organic_matter_pct", "organic_carbon_g_kg_0_30cm"):
        val = data.get(field)
        if val is not None and (not _is_number(val) or val < 0 or
                                (field == "organic_matter_pct" and val > 100)):
            _clear(data, (field,), warnings, f"Atributo inválido: {field}.")

    fc = data.get("field_capacity_m3m3")
    wp = data.get("wilting_point_m3m3")
    if fc is not None or wp is not None:
        if not (_is_number(fc) and _is_number(wp) and 0 <= wp < fc <= 1):
            _clear(data, ("field_capacity_m3m3", "wilting_point_m3m3", "awc_mm_rootzone"),
                   warnings, "Capacidade de campo e ponto de murcha inconsistentes ou incompletos.")

    awc = data.get("awc_mm_rootzone")
    depth = data.get("root_depth_cm")
    if awc is not None and (not _is_number(awc) or not _is_number(depth)
                             or not 0 <= awc <= depth * 10):
        _clear(data, ("awc_mm_rootzone",), warnings, "Água disponível fora dos limites físicos.")
    return data


def manual_soil(req: RegionalSoilRequest) -> dict:
    data = req.soil_override.model_dump(exclude_none=True) if req.soil_override else {}
    depth = data.get("root_depth_cm", req.root_depth_cm)
    data.update({
        "root_depth_cm": depth,
        "provider": "Dados informados pelo produtor",
        "user_override": True,
        "origins": {k: "informado pelo produtor" for k in data},
    })
    fc, wp = data.get("field_capacity_m3m3"), data.get("wilting_point_m3m3")
    if data.get("awc_mm_rootzone") is None and _is_number(fc) and _is_number(wp) and 0 <= wp < fc <= 1:
        data["awc_mm_rootzone"] = round((fc - wp) * depth * 10, 2)
        data["origins"]["awc_mm_rootzone"] = "calculada a partir de CC/PMP e profundidade informadas"
    return data


async def identify_country(lat: float, lon: float) -> str:
    async with httpx.AsyncClient(timeout=7, headers={
        "User-Agent": "CerradoShift/1.0 (academic research project)"
    }) as client:
        response = await client.get("https://nominatim.openstreetmap.org/reverse", params={
            "lat": lat, "lon": lon, "zoom": 3, "format": "jsonv2", "addressdetails": 1
        })
        response.raise_for_status()
        code = ((response.json().get("address") or {}).get("country_code") or "").upper()
        if not code:
            raise ValueError("País não encontrado")
        return code


async def _safe_provider(name: str, fn, lat: float, lon: float, timeout: float = 13) -> dict:
    try:
        result = await asyncio.wait_for(fn(lat, lon), timeout=timeout)
        if not isinstance(result, dict):
            return {"source": name, "status": "invalid_response", "data": None}
        return result
    except asyncio.TimeoutError:
        return {"source": name, "status": "timeout", "data": None}
    except Exception as exc:
        logger.warning("Provedor %s falhou: %s", name, exc)
        return {"source": name, "status": "error", "data": None,
                "detail": f"{type(exc).__name__}: {str(exc)[:200]}"}


def _regional_features(sources: dict) -> list[dict]:
    features = []
    for key in ("embrapa", "ibge_pedologia"):
        result = sources.get(key) or {}
        if result.get("status") != "ok":
            continue
        for feature in ((result.get("data") or {}).get("features") or []):
            if isinstance(feature, dict):
                features.append({"source": key, "properties": feature.get("properties") or {}})
    return features


def _merge_estimates(data: dict, estimates: dict, label: str, fields: tuple[str, ...],
                     warnings: list[str]) -> list[str]:
    """Mescla propriedades validáveis, preservando prioridades e procedência."""
    candidate = {"root_depth_cm": data["root_depth_cm"], "origins": {}}
    for field in fields:
        if estimates.get(field) is not None:
            candidate[field] = estimates[field]
    candidate = validate_soil(candidate, warnings)
    accepted = []
    for field in fields:
        value = candidate.get(field)
        if value is not None and data.get(field) is None:
            data[field] = value
            data.setdefault("origins", {})[field] = label
            accepted.append(field)
    return accepted


async def _mapbiomas_solo(lat: float, lon: float, root_depth_cm: float) -> dict:
    """Importação adiada: GEE não é dependência obrigatória do servidor."""
    try:
        module = importlib.import_module("providers.brasil.mapbiomas_solo")
    except (ModuleNotFoundError, ImportError) as exc:
        return {"source": "MapBiomas Solo", "status": "not_configured", "data": None,
                "detail": f"Módulo indisponível: {type(exc).__name__}: {str(exc)[:140]}"}
    if root_depth_cm > 100:
        return {"source": "MapBiomas Solo", "status": "unsupported_depth", "data": None,
                "detail": "Granulometria MapBiomas limitada a até 100 cm."}
    fn = getattr(module, "consultar_solo", None)
    if not callable(fn):
        return {"source": "MapBiomas Solo", "status": "not_configured", "data": None,
                "detail": "Função consultar_solo ausente."}
    try:
        result = await asyncio.wait_for(fn(lat=lat, lon=lon, root_depth_cm=root_depth_cm), timeout=70)
        return result if isinstance(result, dict) else {
            "source": "MapBiomas Solo", "status": "invalid_response", "data": None
        }
    except asyncio.TimeoutError:
        return {"source": "MapBiomas Solo", "status": "timeout", "data": None}
    except Exception as exc:
        return {"source": "MapBiomas Solo", "status": "error", "data": None,
                "detail": f"{type(exc).__name__}: {str(exc)[:200]}"}


async def _soilgrids(lat: float, lon: float, root_depth_cm: float) -> dict:
    if root_depth_cm > 30:
        return {"source": "SoilGrids WCS", "status": "unsupported_depth", "data": None,
                "detail": "A implementação atual utiliza somente as profundidades até 30 cm."}
    try:
        result = await asyncio.wait_for(
            soil_wcs.consultar_solo(lat=lat, lon=lon, root_depth_cm=root_depth_cm),
            timeout=float(os.getenv("SOIL_WCS_TOTAL_TIMEOUT", "35")),
        )
        return result if isinstance(result, dict) else {"status": "invalid_response"}
    except asyncio.TimeoutError:
        return {"status": "timeout", "warnings": ["Tempo limite do SoilGrids WCS excedido."]}
    except Exception as exc:
        return {"status": "error", "warnings": [f"SoilGrids WCS: {type(exc).__name__}: {str(exc)[:160]}"]}


@router.post("/soil-diagnose")
async def regional_soil_diagnose(req: RegionalSoilRequest, request: Request) -> dict:
    warnings: list[str] = []
    source_results: dict[str, dict] = {}
    regional_soil: list[dict] = []

    if req.country_code:
        country, country_method = req.country_code, "informado pelo frontend"
    else:
        try:
            country = await identify_country(req.lat, req.lon)
            country_method = "geocodificação reversa"
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(status_code=503, detail=(
                "Não foi possível identificar o país. Informe country_code='BR' "
                "somente quando o ponto estiver no Brasil."
            )) from exc

    if req.soil_override is not None:
        soil_data = manual_soil(req)
        origin, data_policy = "manual", "manual"

    elif country == "BR":
        soil_data = {"provider": None, "root_depth_cm": req.root_depth_cm,
                     "user_override": False, "origins": {}}
        origin, data_policy = "regional_br", "brazilian_only"

        # Uma chamada remota que falha não invalida as outras.
        e, i, m = await asyncio.gather(
            _safe_provider("Embrapa", embrapa.consultar_solo, req.lat, req.lon),
            _safe_provider("IBGE", ibge_solos.consultar_pedologia, req.lat, req.lon),
            _mapbiomas_solo(req.lat, req.lon, req.root_depth_cm),
        )
        source_results.update({"embrapa": e, "ibge_pedologia": i, "mapbiomas_solo": m})
        regional_soil = _regional_features(source_results)
        if regional_soil:
            warnings.append("Feições pedológicas regionais encontradas; não são medidas físico-químicas.")

        if m.get("status") == "ok":
            raw = m.get("data") or {}
            accepted = _merge_estimates(soil_data, raw, "MapBiomas Solo - estimativa",
                                        TEXTURE_FIELDS, warnings)
            if accepted:
                source_results["mapbiomas_solo"]["accepted_fields"] = accepted
                origin = "regional_br_with_mapbiomas"
                data_policy = "brazilian_estimates"
                soil_data["provider"] = "MapBiomas Solo (granulometria estimada)"

        if _enabled("SOIL_ALLOW_GLOBAL_FALLBACK"):
            estimates = await _soilgrids(req.lat, req.lon, req.root_depth_cm)
            warnings.extend(estimates.get("warnings") or [])
            if estimates.get("status") in ("timeout", "error", "unsupported_depth", "invalid_response"):
                source_results["soilgrids_wcs"] = {
                    "status": estimates.get("status"),
                    "detail": estimates.get("detail"),
                }
            else:
                accepted = _merge_estimates(soil_data, estimates, "ISRIC SoilGrids WCS - estimativa",
                                             SOIL_FIELDS, warnings)
                if accepted:
                    source_results["soilgrids_wcs"] = {
                        "status": "ok", "accepted_fields": accepted,
                        "provider": estimates.get("provider"),
                    }
                    if soil_data.get("provider") is None:
                        soil_data["provider"] = "ISRIC SoilGrids WCS (estimativas globais)"
                    origin = "regional_br_with_global_estimates" if origin == "regional_br" else origin
                    data_policy = "brazilian_with_global_fallback"
                else:
                    source_results["soilgrids_wcs"] = {"status": "invalid_or_no_data"}
                    warnings.append("SoilGrids WCS não retornou atributos quantitativos válidos.")
        else:
            source_results["soilgrids_wcs"] = {"status": "disabled"}

        if not regional_soil and not soil_data.get("provider"):
            warnings.append("Nenhuma fonte brasileira configurada retornou atributos de solo válidos.")

    else:
        from providers import soil
        client = getattr(request.app.state, "http", None)
        if client is None:
            raise HTTPException(status_code=503, detail="Cliente HTTP não inicializado.")
        origin, data_policy = "global", "global"
        try:
            response = await asyncio.wait_for(
                soil.context(client, lat=req.lat, lon=req.lon,
                             root_depth_cm=req.root_depth_cm), timeout=20
            )
            soil_data = dict(response.data or {})
            source_results["soil"] = response.as_source()
            warnings.extend(response.warnings or [])
        except asyncio.TimeoutError:
            soil_data = {"provider": None, "root_depth_cm": req.root_depth_cm}
            source_results["soil"] = {"status": "timeout"}
            warnings.append("Consulta global excedeu 20 segundos.")
        except Exception as exc:
            soil_data = {"provider": None, "root_depth_cm": req.root_depth_cm}
            source_results["soil"] = {"status": "error", "detail": type(exc).__name__}
            warnings.append(f"Consulta global falhou: {type(exc).__name__}.")

    soil_data = validate_soil(soil_data, warnings)
    # Não declarar fonte quantitativa quando não restou um único atributo utilizável.
    useful = any(soil_data.get(field) is not None for field in SOIL_FIELDS)
    if not useful:
        soil_data["provider"] = None

    diagnostic = diagnose(soil_data)
    diagnostic.update({
        "location": {"lat": req.lat, "lon": req.lon, "country_code": country},
        "country_detection": country_method,
        "data_policy": data_policy,
        "regional_sources": source_results,
        "regional_soil": regional_soil,
        "soil_data_mode": origin,
        "field_origins": soil_data.get("origins") or {},
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "disclaimer": (
            "Triagem baseada em estimativas espaciais ou informações fornecidas; "
            "não substitui análise laboratorial representativa do talhão."
        ),
    })
    diagnostic["warnings"] = warnings + (diagnostic.get("warnings") or [])
    return diagnostic
