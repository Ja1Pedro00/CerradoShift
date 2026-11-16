"""CerradoShift | Triagem técnica de solo com proveniência.

Não é laudo agronômico; não recomenda doses de insumos.
Depende do módulo existente providers.soil e do app.state.http.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from math import isfinite
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from schemas import SoilOverride

router = APIRouter(prefix="/v1/soil", tags=["soil-diagnostics"])

class SoilDiagnosticRequest(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    root_depth_cm: float = Field(default=30, ge=10, le=300)
    soil_override: SoilOverride | None = None


def _number(data: dict[str, Any], key: str) -> float | None:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if isfinite(value) else None


def _finding(code: str, level: str, title: str, detail: str, basis: list[str], action: str) -> dict[str, Any]:
    return {"code": code, "level": level, "title": title, "detail": detail,
            "basis": basis, "suggested_action": action}


def diagnose(data: dict[str, Any]) -> dict[str, Any]:
    """Parte pura, determinística e testável do diagnóstico."""
    findings: list[dict[str, Any]] = []
    warnings: list[str] = []
    provider = data.get("provider")
    origins = data.get("origins") or {}
    offset = data.get("sample_offset_deg")
    measured = bool(data.get("user_override"))
    confidence = "moderate" if provider and not offset else "low"
    if measured:
        confidence = "mixed"  # amostras e estimativas podem coexistir
    if not provider:
        confidence = "insufficient"
        findings.append(_finding("no_source", "data_gap", "Sem dados automáticos de solo",
            "O provedor não retornou atributos utilizáveis para esta localização.", ["provider"],
            "Informe análise de solo do talhão para melhorar a avaliação."))
    if offset:
        warnings.append("SoloGrids usou pixel vizinho; características podem não representar o talhão.")
    if provider and "USDA" in provider:
        warnings.append("Verifique cobertura do USDA: SSURGO é voltado aos Estados Unidos.")

    clay, sand, silt = (_number(data, k) for k in ("clay_pct", "sand_pct", "silt_pct"))
    texture = data.get("texture_class")
    if all(v is not None for v in (clay, sand, silt)):
        total = clay + sand + silt
        if not (95 <= total <= 105):
            warnings.append(f"Frações texturais somam {total:.1f}% (esperado ~100%); conferir unidades/amostragem.")
    if texture:
        findings.append(_finding("texture", "info", "Textura estimada ou informada",
            f"Classe textural: {texture}. A textura influencia infiltração, retenção e manejo, mas não determina sozinha a aptidão agrícola.",
            ["texture_class", "clay_pct", "sand_pct", "silt_pct"],
            "Confira a textura em análise de solo representativa do talhão."))
    else:
        findings.append(_finding("texture_unknown", "data_gap", "Textura indisponível",
            "Não foi possível caracterizar a textura com os dados atuais.", ["clay_pct", "sand_pct", "silt_pct"],
            "Informe areia, silte e argila (%)."))

    ph = _number(data, "ph_h2o")
    if ph is None:
        findings.append(_finding("ph_unknown", "data_gap", "pH desconhecido",
            "Sem pH em água não é possível avaliar acidez ou alcalinidade.", ["ph_h2o"],
            "Solicite análise química de solo com método explicitado."))
    elif ph < 5.5:
        findings.append(_finding("acid_soil", "attention", "Acidez potencialmente limitante",
            f"pH em água de {ph:.2f}. Pode haver limitação para culturas sensíveis; pH isolado não define necessidade de calagem.",
            ["ph_h2o"], "Avalie saturação por bases, alumínio, CTC e cultura-alvo com agrônomo."))
    elif ph > 7.5:
        findings.append(_finding("alkaline_soil", "attention", "pH elevado",
            f"pH em água de {ph:.2f}; a disponibilidade de alguns micronutrientes pode ser limitada.",
            ["ph_h2o"], "Confirme em laboratório e avalie conforme cultura e análise química completa."))
    else:
        findings.append(_finding("ph_recorded", "info", "pH registrado",
            f"pH em água de {ph:.2f}; isoladamente, não estabelece fertilidade ou aptidão.",
            ["ph_h2o"], "Interprete com cultura, CTC, nutrientes e saturação por bases."))

    om = _number(data, "organic_matter_pct")
    soc = _number(data, "organic_carbon_g_kg_0_30cm")
    if om is None and soc is None:
        findings.append(_finding("organic_unknown", "data_gap", "Matéria orgânica não quantificada",
            "Não há medida direta de matéria orgânica ou carbono orgânico para a profundidade analisada.",
            ["organic_matter_pct", "organic_carbon_g_kg_0_30cm"],
            "Informe carbono orgânico ou matéria orgânica com profundidade de coleta."))
    else:
        title = "Matéria orgânica informada" if om is not None else "Carbono orgânico estimado"
        val = f"{om:.2f}% de matéria orgânica" if om is not None else f"{soc:.2f} g/kg de carbono orgânico (0–30 cm)"
        findings.append(_finding("organic_recorded", "info", title,
            f"Disponível: {val}. Não equivale diretamente a estoque de carbono ou índice de qualidade do solo.",
            ["organic_matter_pct" if om is not None else "organic_carbon_g_kg_0_30cm"],
            "Interprete com tipo de solo, profundidade, histórico de manejo e análises regionais."))

    fc, wp = _number(data, "field_capacity_m3m3"), _number(data, "wilting_point_m3m3")
    awc = _number(data, "awc_mm_rootzone")
    depth = _number(data, "root_depth_cm")
    if fc is not None and wp is not None and fc <= wp:
        warnings.append("Capacidade de campo <= ponto de murcha: entradas inconsistentes; AWC não deve ser usada.")
        awc = None
    if awc is not None and awc < 0:
        warnings.append("Capacidade de água disponível negativa: ignorada.")
        awc = None
    if awc is not None:
        findings.append(_finding("awc", "info", "Água disponível estimada/informada",
            f"AWC: {awc:.1f} mm para a profundidade representada ({depth or 'não informada'} cm). Não é água atualmente armazenada.",
            ["awc_mm_rootzone", "root_depth_cm"],
            "Confirme profundidade radicular efetiva e parâmetros físicos antes de usar no simulador."))
    else:
        findings.append(_finding("awc_unknown", "data_gap", "Reserva hídrica não determinada",
            "Faltam dados físicos confiáveis para estimar água disponível no perfil.",
            ["awc_mm_rootzone", "field_capacity_m3m3", "wilting_point_m3m3"],
            "Obtenha capacidade de campo, ponto de murcha e profundidade efetiva de raízes."))

    nutrients = ["phosphorus_mg_dm3", "potassium_mg_dm3"]
    missing = [k for k in nutrients if _number(data, k) is None]
    if missing:
        findings.append(_finding("nutrient_gap", "data_gap", "Diagnóstico de fertilidade incompleto",
            "Dados de fósforo/potássio insuficientes. Mesmo quando presentes, o extrator e a interpretação regional são necessários.",
            nutrients, "Solicite laudo químico com método analítico, CTC, saturação por bases e níveis de referência locais."))
    else:
        findings.append(_finding("nutrient_partial", "info", "Fósforo e potássio registrados",
            "Valores disponíveis, mas insuficientes para recomendar adubação sem método, cultura e referências regionais.",
            nutrients, "Interpretar análise com agrônomo, extrator e critérios regionais."))

    return {
        "status": "screening_only",
        "confidence": confidence,
        "summary": {"findings": len(findings), "attention": sum(f["level"] == "attention" for f in findings),
                    "data_gaps": sum(f["level"] == "data_gap" for f in findings)},
        "soil": {"provider": provider, "user_override": measured, "texture_class": texture,
                 "clay_pct": clay, "sand_pct": sand, "silt_pct": silt, "ph_h2o": ph,
                 "organic_matter_pct": om, "organic_carbon_g_kg_0_30cm": soc,
                 "awc_mm_rootzone": awc, "root_depth_cm": depth},
        "findings": findings,
        "field_origins": origins,
        "warnings": warnings,
        "method": "Rule-based transparent screening; no crop-specific thresholds, fertilization rates or yield prediction.",
    }


@router.post("/diagnose")
async def soil_diagnose(req: SoilDiagnosticRequest, request: Request) -> dict[str, Any]:
    from providers import soil
    client = getattr(request.app.state, "http", None)
    if client is None:
        raise HTTPException(503, "Cliente HTTP não inicializado no lifespan da API")
    override = req.soil_override.model_dump(exclude_none=True) if req.soil_override else None
    source_warnings = []
    result = None
    # Evita consultas repetidas a servicos remotos quando um laudo ja foi fornecido.
    if override:
        result_data = {
            **override,
            "provider": "Dados informados pelo produtor (sem consulta externa)",
            "user_override": True,
            "root_depth_cm": override.get("root_depth_cm", req.root_depth_cm),
            "origins": {key: "informado pelo produtor" for key in override},
        }
        if all(result_data.get(k) is not None for k in ("clay_pct", "sand_pct", "silt_pct")):
            result_data["texture_class"] = soil.classify_texture(
                result_data["sand_pct"], result_data["silt_pct"], result_data["clay_pct"]
            )
    else:
        try:
            # Timeout total da consulta, incluindo todas as tentativas dos providers.
            result = await asyncio.wait_for(
                soil.context(client, lat=req.lat, lon=req.lon, root_depth_cm=req.root_depth_cm, override=None),
                timeout=15.0,
            )
            result_data = dict(result.data or {})
            source_warnings.extend(result.warnings)
        except asyncio.TimeoutError:
            result_data = {"provider": None, "root_depth_cm": req.root_depth_cm}
            source_warnings.append("Consulta de solo excedeu 15 segundos; diagnostico parcial gerado sem estimativas automaticas.")
        except Exception as exc:
            result_data = {"provider": None, "root_depth_cm": req.root_depth_cm}
            source_warnings.append(f"Consulta indisponivel: {type(exc).__name__}; diagnostico parcial gerado.")
    diagnostic = diagnose(result_data)
    diagnostic["location"] = {"lat": req.lat, "lon": req.lon}
    diagnostic["generated_at"] = datetime.now(timezone.utc).isoformat()
    diagnostic["source_status"] = result.as_source() if result is not None else {"name": "soil", "status": "partial", "cached": False}
    diagnostic["warnings"] = [*source_warnings, *diagnostic["warnings"]]
    diagnostic["disclaimer"] = "Triagem de dados, não laudo nem prescrição de correção/adubação."
    return diagnostic
