from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse

from clients import CachedHTTP
from config import settings
from providers import geo, meteo, power, soil, vegetation, water
from providers.base import ProviderResult, guard
from formula_engine.api.routes import router as formula_router
from formula_engine.core.cerrado_mvp import recommend_transition_options

# Rotas já existentes no CerradoShift integrado.
from nasa_science import router as nasa_science_router
from soil_diagnostic import router as soil_diagnostic_router
from rotation_engine import router as science_router
from brazil_routes import router as brazil_router
from region_soil import (
    router as region_router,
    RegionalSoilRequest,
    regional_soil_diagnose,
)

from schemas import (
    FieldContextRequest,
    FieldContextResponse,
    PlanResponse,
    RotationOptionsRequest,
    VegetationSeriesRequest,
)

APP_VERSION = "0.1.0"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("nasa-agro-api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = CachedHTTP(
        timeout=settings.http_timeout_seconds,
        cache_dir=settings.cache_dir,
        ttl=settings.cache_ttl_seconds,
        retries=settings.http_retries,
    )
    logger.info("cache local em %s", settings.cache_dir)
    if not settings.formulas_base_url:
        logger.info("Motor matemático local disponível em /api/v1; FORMULAS_BASE_URL externo não configurado para rotas legadas /v1/plan e /v1/rotation-options")
    try:
        yield
    finally:
        await app.state.http.aclose()


app = FastAPI(
    title="NASA Agro Rotation API",
    version=APP_VERSION,
    summary="Contexto solo-água-clima para recomendação de rotação de culturas",
    description=(
        "Agrega dados abertos de solo, clima, água e satélite para um talhão e "
        "entrega um payload normalizado para o serviço de fórmulas. "
        "As fontes abertas (POWER, USDA-SDA, Open-Meteo, STAC, USGS) não exigem chave."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if "*" in settings.cors_origins else settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(formula_router)
app.include_router(science_router)
app.include_router(nasa_science_router)
app.include_router(soil_diagnostic_router)
app.include_router(brazil_router)
app.include_router(region_router)


# --------------------------------------------------------------------- fontes

# Matriz real testada a partir desta máquina (14/11/2026).
# "open" = funciona sem cadastro; "key" = precisa de conta/chave gratuita.
SOURCE_MATRIX: list[dict[str, Any]] = [
    {
        "group": "NASA",
        "name": "NASA POWER",
        "access": "open",
        "endpoint": "https://power.larc.nasa.gov/api/temporal/daily/point",
        "used_for": "chuva, temperatura, ET, radiação e umidade do solo (MERRA-2)",
        "in_api": True,
    },
    {
        "group": "NASA",
        "name": "SMAP L4 (umidade do solo)",
        "access": "key",
        "credential": "Earthdata Login",
        "endpoint": "https://n5eil01u.ecs.nsidc.org/SMAP/SPL4SMGP.008/",
        "used_for": "umidade da superfície e zona radicular a cada 2-3 dias",
        "in_api": False,
        "alternative": "proxy atual: GWETTOP/GWETROOT do POWER",
    },
    {
        "group": "NASA",
        "name": "GPM IMERG (precipitação)",
        "access": "key",
        "credential": "Earthdata Login",
        "endpoint": "https://gpm1.gesdisc.eosdis.nasa.gov/data/GPM_L3/",
        "used_for": "precipitação global e eventos extremos",
        "in_api": False,
        "alternative": "precipitação diária do POWER já cobre a janela histórica",
    },
    {
        "group": "NASA",
        "name": "ECOSTRESS (LST/ET)",
        "access": "key",
        "credential": "Earthdata Login",
        "endpoint": "https://e4ftl01.cr.usgs.gov/ECOSTRESS/",
        "used_for": "estresse térmico e demanda de água em alta resolução",
        "in_api": False,
    },
    {
        "group": "NASA",
        "name": "GEDI (estrutura da vegetação)",
        "access": "key",
        "credential": "Earthdata Login",
        "endpoint": "https://daac.ornl.gov/GEDI/",
        "used_for": "biomassa e dossel no entorno agrícola",
        "in_api": False,
    },
    {
        "group": "NASA",
        "name": "AppEEARS",
        "access": "key",
        "credential": "Earthdata Login",
        "endpoint": "https://appeears.earthdatacloud.nasa.gov/api/",
        "used_for": "série temporal de pontos (MODIS, VIIRS, SMAP) em uma única API",
        "in_api": False,
        "alternative": "NDVI/EVI por polígono já resolvido via HLS + Planetary Computer",
    },
    {
        "group": "NASA",
        "name": "CMR (catálogo)",
        "access": "open",
        "endpoint": "https://cmr.earthdata.nasa.gov/search/",
        "used_for": "metadados de SMAP/GPM/GEDI/ECOSTRESS",
        "in_api": False,
    },
    {
        "group": "USDA",
        "name": "Soil Data Access (SSURGO/STATSGO2)",
        "access": "open",
        "endpoint": "https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest",
        "used_for": "textura, matéria orgânica, AWC, drenagem, grupo hidrológico",
        "in_api": True,
    },
    {
        "group": "USDA",
        "name": "NASS QuickStats",
        "access": "key",
        "credential": "NASS_API_KEY (gratuita)",
        "endpoint": "https://quickstats.nass.usda.gov/api/api_GET/",
        "used_for": "rendimento e área plantada por condado",
        "in_api": False,
    },
    {
        "group": "USDA",
        "name": "AMS Market News",
        "access": "key",
        "credential": "AMS_API_KEY (gratuita)",
        "endpoint": "https://marsapi.ams.usda.gov/services/v1.2/",
        "used_for": "preço e demanda de commodities",
        "in_api": False,
    },
    {
        "group": "USDA",
        "name": "Ag Data Commons",
        "access": "open",
        "endpoint": "https://data.nal.usda.gov/",
        "used_for": "datasets agrícolas complementares",
        "in_api": False,
    },
    {
        "group": "Outros",
        "name": "ISRIC SoilGrids",
        "access": "open",
        "endpoint": "https://rest.isric.org/soilgrids/v2.0/properties/query",
        "used_for": "solo global 250 m (fallback fora dos EUA)",
        "in_api": True,
        "note": "resposta instável hoje (valores nulos); funciona como fallback opcional",
    },
    {
        "group": "Outros",
        "name": "Open-Meteo",
        "access": "open",
        "endpoint": "https://archive-api.open-meteo.com/v1/archive",
        "used_for": "ET0 FAO-56, previsão de 14 dias e umidade volumétrica do solo",
        "in_api": True,
    },
    {
        "group": "Outros",
        "name": "Planetary Computer STAC",
        "access": "open",
        "endpoint": "https://planetarycomputer.microsoft.com/api/stac/v1/search",
        "used_for": "disponibilidade de Sentinel-2 e Landsat para o talhão",
        "in_api": True,
    },
    {
        "group": "NASA",
        "name": "HLS v2 (Harmonized Landsat-Sentinel)",
        "access": "open",
        "endpoint": "https://planetarycomputer.microsoft.com/api/stac/v1/collections/hls2-s30",
        "used_for": "NDVI e EVI por polígono do talhão (30 m, ~2-3 dias)",
        "in_api": True,
        "note": "S30 (Sentinel-2) + L30 (Landsat 8/9); leitura direta do COG com SAS token",
    },
    {
        "group": "Outros",
        "name": "USGS Water Data (NWIS)",
        "access": "open",
        "endpoint": "https://api.waterdata.usgs.gov/ogcapi/v0/",
        "used_for": "cotações fluviométricas próximas ao talhão",
        "in_api": True,
    },
    {
        "group": "Outros",
        "name": "CoCoRaHS",
        "access": "open",
        "endpoint": "https://data.cocorahs.org/cocorahs/export/exportreports.aspx",
        "used_for": "validação local de chuva (América do Norte)",
        "in_api": False,
    },
    {
        "group": "Outros",
        "name": "PRISM",
        "access": "open",
        "endpoint": "https://prism.oregonstate.edu/",
        "used_for": "normais climáticas de alta resolução (EUA)",
        "in_api": False,
        "note": "serviço antigo descontinuado; usar o novo endpoint de dados do PRISM",
    },
    {
        "group": "Parceiros",
        "name": "Copernicus Sentinel-2",
        "access": "key",
        "credential": "Copernicus Data Space (OAuth)",
        "endpoint": "https://catalogue.dataspace.copernicus.eu/odata/v1/",
        "used_for": "NDVI/EVI 10 m (catálogo aberto, download com token)",
        "in_api": False,
        "alternative": "já cobrimos Sentinel-2/Landsat via STAC aberto",
    },
    {
        "group": "Parceiros",
        "name": "ERA5 (Copernicus CDS)",
        "access": "key",
        "credential": "CDS API key",
        "endpoint": "https://cds.climate.copernicus.eu/api",
        "used_for": "reanálise horária global",
        "in_api": False,
        "alternative": "Open-Meteo entrega ERA5-Land já processado, sem chave",
    },
]

BLOCKED_FROM_THIS_NETWORK = ["https://www.mrlc.gov/", "https://www.landfire.gov/"]


# ------------------------------------------------------------------ auxiliares


def _aridity_label(index: float) -> str:
    if index < 0.03:
        return "hiperárido"
    if index < 0.2:
        return "árido"
    if index < 0.5:
        return "semárido"
    if index < 0.65:
        return "subúmido seco"
    return "úmido"


def _slope_label(slope_pct: float | None) -> str | None:
    if slope_pct is None:
        return None
    if slope_pct < 2:
        return "plano"
    if slope_pct < 5:
        return "suave"
    if slope_pct < 10:
        return "moderado"
    return "declivoso"


def _derive_indicators(
    climate: dict[str, Any],
    meteo_data: dict[str, Any],
    soil_data: dict[str, Any],
    veg_data: dict[str, Any],
) -> dict[str, Any]:
    """Indicadores heurísticos para o app e para o serviço de fórmulas.

    IMPORTANTE: isto não substitui o serviço de fórmulas. São sinais
    explicáveis (e citáveis na apresentação), não uma recomendação agronômica.
    """
    indicators: dict[str, Any] = {}
    precip = climate.get("precip_mm_total")
    et0 = climate.get("et0_mm_total")
    actual_et = climate.get("et_mm_total")

    if isinstance(precip, (int, float)) and isinstance(et0, (int, float)) and et0 > 0:
        index = precip / et0
        indicators["aridity_index_unep"] = round(index, 3)
        indicators["climate_class"] = _aridity_label(index)
        indicators["water_deficit_mm"] = round(max(0.0, et0 - precip), 1)

    if isinstance(precip, (int, float)) and isinstance(actual_et, (int, float)):
        indicators["net_water_balance_mm"] = round(precip - actual_et, 1)

    trend = (climate.get("soil_moisture_rootzone") or {}).get("trend")
    if trend:
        indicators["rootzone_moisture_trend"] = trend

    score, basis = 0, []
    aridity = indicators.get("aridity_index_unep")
    if isinstance(aridity, (int, float)) and aridity < 0.5:
        score += 1
        basis.append("índice de aridez abaixo de 0,50 (semárido ou mais seco)")
    dry_spell = climate.get("longest_dry_spell_days")
    if isinstance(dry_spell, (int, float)) and dry_spell >= 20:
        score += 1
        basis.append(f"maior veranico de {int(dry_spell)} dias")
    if trend == "caindo":
        score += 1
        basis.append("umidade da zona radicular em queda na janela")
    deficit = indicators.get("water_deficit_mm")
    if isinstance(deficit, (int, float)) and deficit > 300:
        score += 1
        basis.append("déficit hídrico acumulado acima de 300 mm")

    indicators["drought_risk"] = "alto" if score >= 3 else "moderado" if score >= 2 else "baixo"
    indicators["drought_risk_basis"] = basis

    slope = soil_data.get("slope_pct")
    if isinstance(slope, (int, float)):
        indicators["slope_pct"] = slope
        indicators["slope_class"] = _slope_label(slope)

    awc = soil_data.get("awc_mm_rootzone")
    if isinstance(awc, (int, float)):
        indicators["soil_water_storage_mm"] = awc

    indicators["satellite_scenes_found"] = veg_data.get("scenes_found")
    indicators["forecast_precip_mm_14d"] = (meteo_data.get("forecast") or {}).get("precip_mm_total")
    indicators["forecast_et0_mm_14d"] = (meteo_data.get("forecast") or {}).get("et0_mm_total")
    return indicators


def _br(value: float, digits: int = 1) -> str:
    """Número no padrão brasileiro (vírgula decimal) para textos de alerta."""
    return f"{value:.{digits}f}".replace(".", ",")


def _alert(
    severity: str,
    code: str,
    title: str,
    detail: str,
    action: str,
    basis: list[str],
) -> dict[str, Any]:
    return {
        "severity": severity,  # "critico" | "atencao" | "info"
        "code": code,
        "title": title,
        "detail": detail,
        "action": action,
        "basis": basis,
    }


def _derive_alerts(
    climate: dict[str, Any],
    meteo_data: dict[str, Any],
    soil_data: dict[str, Any],
    water_data: dict[str, Any],
    veg_data: dict[str, Any],
    indicators: dict[str, Any],
    req: FieldContextRequest,
    target_crop: str | None = None,
    target_crop_known: bool = True,
) -> list[dict[str, Any]]:
    """Alertas e prevenções explicáveis ("triagem"), derivados dos dados.

    NÃO é recomendação agronômica nem laudo: é um resumo do que os dados
    mostram, com o campo exato (``basis``) que gerou cada alerta. A decisão
    final continua com o CerradoShift / agrônomo.
    """
    alerts: list[dict[str, Any]] = []
    rainfed = (req.irrigation or "rainfed") == "rainfed"

    # ------------------------------------------------------------- clima/água
    risk = indicators.get("drought_risk")
    if risk in ("alto", "moderado"):
        basis = indicators.get("drought_risk_basis") or []
        action = (
            "Cultivo de sequeiro: priorize ciclo curto ou preveja irrigação "
            "suplementar nos meses críticos."
            if rainfed
            else "Mantenha o plano de irrigação e acompanhe a umidade da zona radicular."
        )
        alerts.append(
            _alert(
                "critico" if risk == "alto" else "atencao",
                "drought_risk",
                f"Risco de seca {risk}",
                "; ".join(basis) if basis else "Sinais de estresse hídrico na janela analisada.",
                action,
                ["indicators.drought_risk", "climate"],
            )
        )

    frost = climate.get("frost_days_tmin_le_2c")
    if isinstance(frost, (int, float)) and frost > 0:
        alerts.append(
            _alert(
                "atencao",
                "frost",
                f"{int(frost)} dia(s) com risco de geada",
                "Temperatura mínima ≤ 2 °C na janela analisada.",
                "Evite cultivares sensíveis em safrinha/inverno e confira a previsão antes do plantio.",
                ["climate.frost_days_tmin_le_2c"],
            )
        )

    heat = climate.get("heat_days_tmax_ge_35c")
    if isinstance(heat, (int, float)) and heat >= 20:
        alerts.append(
            _alert(
                "atencao",
                "heat",
                f"{int(heat)} dia(s) com calor extremo",
                "Temperatura máxima ≥ 35 °C na janela analisada.",
                "Prefira janelas de plantio que evitem floração nos meses mais quentes.",
                ["climate.heat_days_tmax_ge_35c"],
            )
        )

    forecast = meteo_data.get("forecast") or {}
    forecast_precip = forecast.get("precip_mm_total")
    forecast_et0 = forecast.get("et0_mm_total")
    if isinstance(forecast_precip, (int, float)) and forecast_precip > 150:
        alerts.append(
            _alert(
                "atencao",
                "heavy_rain_forecast",
                f"Chuva intensa prevista (~{forecast_precip:.0f} mm)",
                "Acumulado previsto para os próximos dias.",
                "Avalie a janela de plantio/colheita e o risco de erosão; evite tráfego com solo saturado.",
                ["climate.forecast.precip_mm_total"],
            )
        )
    elif (
        isinstance(forecast_precip, (int, float))
        and isinstance(forecast_et0, (int, float))
        and forecast_precip < 5
        and forecast_et0 > 40
    ):
        alerts.append(
            _alert(
                "info",
                "dry_forecast",
                "Previsão seca à frente",
                f"~{forecast_precip:.0f} mm de chuva e ET₀ ~{forecast_et0:.0f} mm previstos.",
                "Se houver plantio recente, verifique a necessidade de irrigação.",
                ["climate.forecast"],
            )
        )

    # -------------------------------------------------------------- solo (físico)
    ph = soil_data.get("ph_h2o")
    if isinstance(ph, (int, float)) and ph < 5.5:
        alerts.append(
            _alert(
                "atencao",
                "soil_acidity",
                f"Solo ácido (pH {_br(ph)})",
                "pH abaixo de 5,5 reduz a disponibilidade de nutrientes.",
                "Solicite análise de laboratório e avalie calagem conforme recomendação agronômica.",
                ["soil.ph_h2o"],
            )
        )
    elif isinstance(ph, (int, float)) and ph > 7.5:
        alerts.append(
            _alert(
                "info",
                "soil_alkalinity",
                f"Solo alcalino (pH {_br(ph)})",
                "pH acima de 7,5 pode reduzir a disponibilidade de micronutrientes.",
                "Confirme com análise de laboratório antes de corrigir.",
                ["soil.ph_h2o"],
            )
        )

    organic_carbon = soil_data.get("organic_carbon_g_kg_0_30cm")
    organic_matter = soil_data.get("organic_matter_pct")
    low_om = (
        isinstance(organic_carbon, (int, float)) and organic_carbon < 10
    ) or (isinstance(organic_matter, (int, float)) and organic_matter < 2)
    if low_om:
        alerts.append(
            _alert(
                "atencao",
                "low_organic_matter",
                "Matéria orgânica baixa",
                "Indicador de pouca reserva de carbono/nutrientes no solo.",
                "Rotação com culturas de cobertura e adubação verde ajuda a recuperar o solo.",
                ["soil.organic_carbon_g_kg_0_30cm", "soil.organic_matter_pct"],
            )
        )

    awc = soil_data.get("awc_mm_rootzone")
    if isinstance(awc, (int, float)) and awc < 60:
        alerts.append(
            _alert(
                "atencao",
                "low_awc",
                f"Baixa reserva de água no solo ({awc:.0f} mm)",
                "O solo armazena pouca água disponível para as raízes.",
                "Cobertura do solo (palhada) e irrigação reduzem o risco em veranicos.",
                ["soil.awc_mm_rootzone"],
            )
        )

    clay = soil_data.get("clay_pct")
    if isinstance(clay, (int, float)):
        if clay > 60:
            alerts.append(
                _alert(
                    "atencao",
                    "heavy_clay",
                    f"Solo muito argiloso ({clay:.0f}% de argila)",
                    "Maior risco de compactação e drenagem lenta.",
                    "Evite tráfego de máquinas com solo úmido e planeje drenagem.",
                    ["soil.clay_pct"],
                )
            )
        elif clay < 15:
            alerts.append(
                _alert(
                    "atencao",
                    "sandy_soil",
                    f"Solo arenoso ({clay:.0f}% de argila)",
                    "Baixa retenção de nutrientes e maior risco de erosão.",
                    "Use cobertura do solo e parcelamento de adubação.",
                    ["soil.clay_pct"],
                )
            )

    drainage = (soil_data.get("drainage_class") or "").lower()
    if any(term in drainage for term in ("poor", "mal", "imperfeito", "imped")):
        alerts.append(
            _alert(
                "atencao",
                "poor_drainage",
                "Drenagem deficiente",
                f"Classe de drenagem informada: {soil_data.get('drainage_class')}.",
                "Avalie drenagem antes do plantio para evitar encharcamento.",
                ["soil.drainage_class"],
            )
        )

    slope = soil_data.get("slope_pct")
    if isinstance(slope, (int, float)) and slope > 5:
        alerts.append(
            _alert(
                "critico" if slope > 10 else "atencao",
                "slope_erosion",
                f"Declive de {slope:.0f}%",
                "Declividade aumenta o risco de erosão hídrica.",
                "Considere curvas de nível, terraceamento e manutenção de cobertura.",
                ["soil.slope_pct"],
            )
        )

    salinity = soil_data.get("electrical_conductivity_ds_m")
    if isinstance(salinity, (int, float)) and salinity > 4:
        alerts.append(
            _alert(
                "critico",
                "salinity",
                f"Salinidade elevada (CE {_br(salinity)} dS/m)",
                "Condutividade elétrica acima de 4 dS/m pode limitar culturas sensíveis.",
                "Confirme com análise de laboratório e avalie lavagem/drenagem.",
                ["soil.electrical_conductivity_ds_m"],
            )
        )

    phosphorus = soil_data.get("phosphorus_mg_dm3")
    if isinstance(phosphorus, (int, float)) and phosphorus < 10:
        alerts.append(
            _alert(
                "atencao",
                "low_phosphorus",
                f"Fósforo baixo (P {phosphorus:.0f} mg/dm³)",
                "Valor informado no laudo abaixo do usual para culturas de grãos.",
                "Ajuste a adubação conforme a recomendação agronômica para a cultura.",
                ["soil.phosphorus_mg_dm3"],
            )
        )

    potassium = soil_data.get("potassium_mg_dm3")
    if isinstance(potassium, (int, float)) and potassium < 50:
        alerts.append(
            _alert(
                "atencao",
                "low_potassium",
                f"Potássio baixo (K {potassium:.0f} mg/dm³)",
                "Valor informado no laudo abaixo do usual para culturas de grãos.",
                "Ajuste a adubação conforme a recomendação agronômica para a cultura.",
                ["soil.potassium_mg_dm3"],
            )
        )

    # -------------------------------------------------------------- água/satélite
    if "monitoring_locations_nearby" in water_data and not water_data.get(
        "monitoring_locations_nearby"
    ):
        alerts.append(
            _alert(
                "info",
                "no_stream_gauge",
                "Sem estação fluviométrica próxima",
                "A rede USGS cobre os EUA; no Brasil normalmente não há estação no raio buscado.",
                "Use a chuva, a ET₀ e a umidade do solo desta API como referência hídrica.",
                ["water.monitoring_locations_nearby"],
            )
        )

    if "recent_clear_scenes_60d" in veg_data and veg_data.get("recent_clear_scenes_60d") == 0:
        alerts.append(
            _alert(
                "atencao",
                "no_clear_satellite",
                "Sem imagem de satélite limpa nos últimos 60 dias",
                "Nuvens impediram cenas utilizáveis para NDVI recente.",
                "Use a série HLS em /v1/vegetation-series com janela maior.",
                ["vegetation.recent_clear_scenes_60d"],
            )
        )

    # ------------------------------------------------------------ qualidade do dado
    if not soil_data.get("provider"):
        alerts.append(
            _alert(
                "atencao",
                "no_automatic_soil",
                "Solo sem fonte automática neste ponto",
                "O SoilGrids não retornou valores para a área.",
                "Peça ao produtor o laudo de solo (soil_override) para o cálculo ficar confiável.",
                ["soil.provider"],
            )
        )
    elif soil_data.get("sample_offset_deg"):
        alerts.append(
            _alert(
                "info",
                "soil_neighbor_pixel",
                "Solo estimado em pixel vizinho (~1 km)",
                "O ponto exato do talhão não tinha dado; foi usado o pixel mais próximo com informação.",
                "Para precisão, envie a análise de laboratório do talhão.",
                ["soil.sample_offset_deg"],
            )
        )
    if soil_data.get("user_override"):
        alerts.append(
            _alert(
                "info",
                "soil_lab_used",
                "Laudo do produtor aplicado",
                "Os valores medidos têm prioridade sobre a estimativa de satélite.",
                "Mantenha o laudo atualizado a cada safra.",
                ["soil.user_override"],
            )
        )

    # ------------------------------------------------------------ cultura desejada
    if target_crop and not target_crop_known:
        alerts.append(
            _alert(
                "atencao",
                "unknown_target_crop",
                f"Cultura fora do catálogo MVP: “{target_crop}”",
                "O CerradoShift pode não ter parâmetros para esta cultura.",
                "Use soja, milho ou algodão (ou uma das coberturas: milheto, braquiária, crotalária).",
                ["location.target_crop"],
            )
        )

    order = {"critico": 0, "atencao": 1, "info": 2}
    alerts.sort(key=lambda item: order.get(item["severity"], 3))
    return alerts


# ------------------------------------------------------------- catálogo de nomes
# Só tradução de nome (soja -> soybean). NÃO é catálogo agronômico: parâmetros,
# Kc, ciclos e regras por cultura são do CerradoShift.
_CROP_ALIASES: dict[str, str] = {
    "soja": "soybean",
    "soy": "soybean",
    "soybean": "soybean",
    "milho": "corn",
    "maize": "corn",
    "corn": "corn",
    "algodao": "cotton",
    "algodão": "cotton",
    "cotton": "cotton",
    "milheto": "millet",
    "millet": "millet",
    "braquiaria": "urochloa_ruziziensis",
    "braquiária": "urochloa_ruziziensis",
    "ruziziensis": "urochloa_ruziziensis",
    "urochloa": "urochloa_ruziziensis",
    "urochloa_ruziziensis": "urochloa_ruziziensis",
    "crotalaria": "crotalaria_spectabilis",
    "crotalária": "crotalaria_spectabilis",
    "crotalaria_spectabilis": "crotalaria_spectabilis",
    "crotalaria_ochroleuca": "crotalaria_ochroleuca",
}

MVP_COMMERCIAL_CROPS = ("soybean", "corn", "cotton")
MVP_COVER_CROPS = (
    "millet",
    "urochloa_ruziziensis",
    "crotalaria_spectabilis",
    "crotalaria_ochroleuca",
)


def _normalize_crop(name: str | None) -> tuple[str | None, bool]:
    """Traduz "Milho ", "algodão" etc. para o nome canônico usado pelas fórmulas.

    Devolve ``(canonico, reconhecido)``. Se não reconhecer, devolve o texto
    normalizado (minúsculo) e ``False`` — a API não bloqueia, só avisa.
    """
    if not name:
        return None, False
    raw = name.strip().lower()
    if raw in _CROP_ALIASES:
        return _CROP_ALIASES[raw], True
    cleaned = (
        raw.replace(" ", "_").replace("-", "_").replace("ç", "c").replace("á", "a")
    )
    if cleaned in _CROP_ALIASES:
        return _CROP_ALIASES[cleaned], True
    return cleaned, False


async def _regional_soil_context(
    request: Request,
    *,
    lat: float,
    lon: float,
    root_depth_cm: float,
    soil_override,
) -> ProviderResult:
    """Adapta o diagnóstico regional ao contrato usado em build_context.

    Mantém um único fluxo de aquisição para a página de solo e o contexto
    agrícola. Não usa valores ausentes ou zeros inválidos como estimativas.
    """
    # O WCS implementado suporta no máximo 30 cm; manter a profundidade
    # solicitada no retorno e sinalizar a limitação caso não haja laudo.
    consult_depth = min(float(root_depth_cm), 30.0)
    if soil_override is not None and soil_override.root_depth_cm is not None:
        consult_depth = min(float(soil_override.root_depth_cm), 30.0)
    consult_depth = max(10.0, consult_depth)

    req = RegionalSoilRequest(
        lat=lat,
        lon=lon,
        root_depth_cm=consult_depth,
        soil_override=soil_override,
    )
    result = await regional_soil_diagnose(req, request)
    soil_data = dict(result.get("soil") or {})
    soil_data["regional_sources"] = result.get("regional_sources", {})
    soil_data["regional_soil"] = result.get("regional_soil", [])
    soil_data["soil_data_mode"] = result.get("soil_data_mode")
    soil_data["data_policy"] = result.get("data_policy")
    soil_data["country_code"] = (result.get("location") or {}).get("country_code")
    soil_data["confidence"] = result.get("confidence")
    soil_data["status"] = result.get("status")
    soil_data["origins"] = result.get("field_origins"or result.get("field_origins")or {})

    warnings = list(result.get("warnings") or [])
    if root_depth_cm > 30 and soil_override is None:
        warnings.append(
            "O provedor regional automático foi consultado para 0–30 cm; "
            "não representa toda a profundidade radicular solicitada."
        )

    has_data = any(
        soil_data.get(field) is not None
        for field in (
            "clay_pct", "sand_pct", "silt_pct", "ph_h2o",
            "organic_carbon_g_kg_0_30cm", "organic_matter_pct",
            "awc_mm_rootzone", "texture_class",
        )
    )
    if not has_data:
        warnings.append("Nenhum atributo quantitativo válido de solo disponível no ponto.")

    return ProviderResult(
        name="Solo regional",
        ok=has_data,
        data=soil_data,
        warnings=warnings,
        detail=None if has_data else "Fontes de solo sem atributos válidos neste ponto",
    )


async def build_context(client: CachedHTTP, req: FieldContextRequest, request: Request) -> dict[str, Any]:
    today = date.today()
    end = today - timedelta(days=1)
    if req.planting_date and req.planting_date - timedelta(days=1) < end:
        end = req.planting_date - timedelta(days=1)
    start = end - timedelta(days=req.window_days)

    geometry = req.geometry.model_dump() if req.geometry else None
    if geometry is not None:
        lon, lat = geo.centroid(geometry)
        area_ha = req.area_ha if req.area_ha is not None else geo.polygon_area_ha(geometry)
    else:
        lat, lon = req.lat, req.lon
        area_ha = req.area_ha

    root_depth = (
        req.soil_override.root_depth_cm if req.soil_override and req.soil_override.root_depth_cm else 100
    )

    # Qual cultura o agricultor quer plantar (o "select" do app).
    if req.target_crop:
        crop_source = "target_crop"
        crop_input = req.target_crop
    elif req.rotation_candidates:
        crop_source = "rotation_candidates[0]"
        crop_input = req.rotation_candidates[0]
    elif req.current_crop:
        crop_source = "current_crop"
        crop_input = req.current_crop
    else:
        crop_source = None
        crop_input = None
    target_crop, target_crop_known = _normalize_crop(crop_input)

    power_res, meteo_res, soil_res, water_res, veg_res = await asyncio.gather(
        guard(
            "NASA POWER",
            lambda: power.context(
                client,
                lat=lat,
                lon=lon,
                start=start,
                end=end,
                include_series=req.include_daily_series,
            ),
        ),
        guard(
            "Open-Meteo",
            lambda: meteo.context(
                client,
                lat=lat,
                lon=lon,
                start=start,
                end=end,
                forecast_days=req.forecast_days,
            ),
        ),
        guard(
            "Solo",
            lambda: _regional_soil_context(
                request,
                lat=lat,
                lon=lon,
                root_depth_cm=root_depth,
                soil_override=req.soil_override,
            ),
        ),
        guard("USGS", lambda: water.context(client, lat=lat, lon=lon)),
        guard(
            "STAC",
            lambda: vegetation.context(
                client,
                lat=lat,
                lon=lon,
                geometry=geometry,
                start=today - timedelta(days=120),
                end=today,
            ),
        ),
    )

    results = [power_res, meteo_res, soil_res, water_res, veg_res]
    climate: dict[str, Any] = (
        dict(power_res.data) if power_res.ok and power_res.data else {"error": power_res.detail}
    )
    meteo_data = meteo_res.data if meteo_res.ok and meteo_res.data else {}
    soil_data = soil_res.data if soil_res.data else {}
    water_data = water_res.data if water_res.ok and water_res.data else {}
    veg_data = veg_res.data if veg_res.ok and veg_res.data else {}

    if meteo_data:
        climate["et0_mm_total"] = meteo_data.get("et0_mm_total")
        climate["et0_mm_per_day"] = meteo_data.get("et0_mm_per_day")
        climate["et0_source"] = "Open-Meteo (FAO-56 Penman-Monteith)"
        climate["soil_moisture_volumetric"] = meteo_data.get("soil_moisture")
        climate["forecast"] = meteo_data.get("forecast")

    warnings: list[str] = []
    for result in results:
        warnings.extend(result.warnings)
        if not result.ok:
            warnings.append(f"{result.name} falhou: {result.detail}")

    sources = [r.as_source() for r in results]
    ok_count = sum(1 for r in results if r.ok)

    indicators = _derive_indicators(climate, meteo_data, soil_data, veg_data)
    indicators["data_completeness"] = round(ok_count / len(results), 2)

    alerts = _derive_alerts(
        climate,
        meteo_data,
        soil_data,
        water_data,
        veg_data,
        indicators,
        req,
        target_crop=target_crop,
        target_crop_known=target_crop_known,
    )
    alerts_summary = {
        level: sum(1 for item in alerts if item["severity"] == level)
        for level in ("critico", "atencao", "info")
    }

    return {
        "request_id": str(uuid.uuid4()),
        "generated_at": datetime.now(timezone.utc),
        "location": {
            "lat": round(lat, 6) if lat is not None else None,
            "lon": round(lon, 6) if lon is not None else None,
            "geometry": geometry,
            "field_id": req.field_id,
            "area_ha": area_ha,
            "current_crop": req.current_crop,
            "target_crop": target_crop,
            "target_crop_raw": crop_input,
            "target_crop_known": target_crop_known,
            "target_crop_source": crop_source,
            "irrigation": req.irrigation,
            "rotation_candidates": req.rotation_candidates,
        },
        "window": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "days": req.window_days,
            "planting_date": req.planting_date.isoformat() if req.planting_date else None,
        },
        "climate": climate,
        "soil": soil_data,
        "water": water_data,
        "vegetation": veg_data,
        "indicators": indicators,
        "alerts": alerts,
        "alerts_summary": alerts_summary,
        "warnings": warnings,
        "sources": sources,
    }


# ---------------------------------------------------------------------- rotas


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse("/docs")


@app.get("/teste", include_in_schema=False)
async def test_page() -> FileResponse:
    """Página de teste com botões — para demonstrar sem ler JSON."""
    return FileResponse(Path(__file__).resolve().parent / "teste.html")


@app.get("/health", tags=["meta"])
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": APP_VERSION,
        "formulas_configured": True,
        "formula_engine_embedded": True,
        "external_formulas_configured": bool(settings.formulas_base_url),
        "earthdata_configured": settings.earthdata_configured,
        "nass_key_configured": bool(settings.nass_api_key),
        "cache_dir": str(settings.cache_dir),
    }


@app.get("/v1/sources", tags=["meta"])
async def sources() -> dict[str, Any]:
    """Matriz de fontes: o que já está plugado, o que é aberto e o que precisa de chave."""
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": SOURCE_MATRIX,
        "blocked_from_this_network": BLOCKED_FROM_THIS_NETWORK,
        "note": (
            "mrlc.gov e landfire.gov recusam conexão nesta rede; o equivalente "
            "pode ser obtido por STAC/ArcGIS."
        ),
    }


@app.post("/v1/field-context", response_model=FieldContextResponse, tags=["contexto"])
async def field_context(req: FieldContextRequest, request: Request) -> dict[str, Any]:
    """Monta o contexto solo-água-clima de um talhão.

    É a entrada do serviço de fórmulas: devolve clima (POWER + Open-Meteo),
    solo (SSURGO/SoilGrids), contexto hídrico (USGS) e disponibilidade de
    imagem de satélite (STAC).
    """
    return await build_context(request.app.state.http, req, request)


@app.post("/v1/vegetation-series", tags=["satélite"])
async def vegetation_series(req: VegetationSeriesRequest, request: Request) -> dict[str, Any]:
    """Série de NDVI/EVI por talhão (HLS v2 via Planetary Computer).

    Lê apenas a janela do polígono em cada cena e mascara nuvem/sombra pelo
    Fmask. Retorna as cenas, a mais recente e a tendência.
    """
    end = req.end or date.today()
    start = req.start or (end - timedelta(days=120))
    if start > end:
        raise HTTPException(status_code=422, detail="'start' deve ser anterior a 'end'")

    try:
        result = await geo.vegetation_series(
            request.app.state.http,
            geometry=req.geometry.model_dump(),
            start=start,
            end=end,
            max_scenes=req.max_scenes,
            include_evi=req.include_evi,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"STAC/Planetary Computer falhou: {type(exc).__name__}: {exc}",
        ) from exc

    response: dict[str, Any] = {
        "request_id": str(uuid.uuid4()),
        "generated_at": datetime.now(timezone.utc),
        "area_ha": geo.polygon_area_ha(req.geometry.model_dump()),
        **(result.data or {}),
    }
    if result.warnings:
        response["warnings"] = result.warnings
    return response


@app.post("/v1/rotation-options", tags=["recomendação"])
async def rotation_options(req: RotationOptionsRequest, request: Request) -> dict[str, Any]:
    """Compatibilidade com o contrato antigo, executando as regras localmente."""
    status_map = {"present": "present", "absent": "not_detected", "unknown": "unknown"}
    try:
        options = recommend_transition_options(
            current_crop=req.current_crop,
            next_crop=req.next_crop,
            days_available=req.days_available,
            pratylenchus_brachyurus_status=status_map[req.pratylenchus_brachyurus_status],
            objective=req.objective,
            cotton_years_since_last=req.cotton_years_since_last,
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "request_id": str(uuid.uuid4()),
        "generated_at": datetime.now(timezone.utc),
        "sent": req.model_dump(exclude={"lat", "lon", "geometry", "include_vegetation_series"}),
        "options": options,
        "formula_engine": "local",
    }


@app.post("/v1/plan", response_model=PlanResponse, tags=["recomendação"])
async def plan(req: FieldContextRequest, request: Request) -> dict[str, Any]:
    """Retorna contexto real do talhão; não inventa plano sem parâmetros agronômicos completos.

    Os cálculos detalhados devem ser solicitados aos endpoints locais
    /api/v1/assessments/*, com os parâmetros medidos/informados necessários.
    """
    context = await build_context(request.app.state.http, req, request)
    return {
        "request_id": context["request_id"],
        "generated_at": context["generated_at"],
        "context": context,
        "plan": {
            "status": "awaiting_agronomic_inputs",
            "calculation_performed": False,
            "message": (
                "Contexto ambiental obtido. Para calcular balanço hídrico e "
                "resposta da cultura, informe os parâmetros de cultura, solo e manejo "
                "no endpoint /api/v1/assessments/field."
            ),
        },
    }
