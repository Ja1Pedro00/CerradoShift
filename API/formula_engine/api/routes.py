from __future__ import annotations

from fastapi import APIRouter, HTTPException

from formula_engine.api.schemas import AssessmentRequest
from formula_engine.core.schemas import (
    CropParameters, DailyWeather, FarmerContext, IrrigationEvent, SoilProfile,
)
from formula_engine.core.water_balance import simulate_water_balance
from formula_engine.core.crop_catalog import CROP_REFERENCE_CATALOG
from formula_engine.core.evapotranspiration import daylight_hours
from formula_engine.integrations.nasa_power import fetch_nasa_power_daily
from formula_engine.api.global_schemas import (
    VegetationIndexRequest, VegetationAnomalyRequest, ErosionRequest, RotationAssessmentRequest,
    ThermalAssessmentRequest, DualKcRequest, WaterYieldResponseRequest, CerradoMvpRotationRequest,
)
from formula_engine.core.remote_sensing import ReflectancePixel, summarize_pixels, standardized_anomaly
from formula_engine.core.erosion import rusle_soil_loss_t_ha_year
from formula_engine.core.pest_rotation import assess_rotation_sequence
from formula_engine.core.phenology import summarize_gdd_and_heat
from formula_engine.core.dual_kc import dual_crop_coefficient_et
from formula_engine.core.yield_response import fao_water_yield_response
from formula_engine.core.cerrado_mvp import get_cerrado_mvp_catalog, recommend_transition_options
from formula_engine.api.recommendation_schemas import RecommendationRequest
from formula_engine.core.recommendation_engine import generate_recommendations

router = APIRouter(prefix="/api/v1", tags=["CerradoShift"])


@router.get("/crop-catalog")
async def crop_catalog():
    """Retorna perfis bibliográficos para pré-preencher a interface.

    Perfis de referência não substituem cadastro agronômico local; o Front-End
    deve exigir confirmação de cultivar, duração fenológica e parâmetros ausentes.
    """
    return CROP_REFERENCE_CATALOG


@router.get("/data-sources")
async def data_sources():
    """Mostra quais origens estão conectadas e quais ainda exigem integração."""
    return {
        "global_scope": True,
        "sources": [
            {"name": "NASA POWER Daily", "variables": ["temperature", "humidity", "wind", "solar_radiation", "precipitation"], "status": "connected_for_point_daily_weather", "scale_note": "meteorologia em grade global relativamente ampla; não substitui estação de talhão"},
            {"name": "NASA GPM IMERG", "variables": ["precipitation"], "status": "planned_adapter_not_connected", "scale_note": "precipitação global em grade ~0.1° e séries subdiárias; requer pipeline de extração/interpolação"},
            {"name": "NASA/USGS Landsat + ESA Sentinel-2 HLS", "variables": ["surface_reflectance", "NDVI", "EVI", "SAVI", "MSAVI", "NDMI", "NDWI", "NBR", "NBR2"], "status": "index_math_connected_reflectance_input_only", "scale_note": "HLS harmonizado a 30 m; falta conectar busca/recorte de cenas, escala de bandas e QA mask"},
            {"name": "NASA SMAP", "variables": ["near_surface_soil_moisture"], "status": "planned_adapter_not_connected", "scale_note": "mede umidade superficial; não representa diretamente toda a zona de raízes"},
            {"name": "ISRIC SoilGrids", "variables": ["pH", "texture", "SOC", "bulk_density", "CEC", "total_N"], "status": "planned_raster_ingestion_rest_api_temporarily_paused", "scale_note": "mapas preditivos globais de 250 m com intervalos de incerteza; avaliar WCS/WebDAV ou rasters no Google Earth Engine; não substituem análise de laboratório"},
            {"name": "EPPO / IPPC / serviços fitossanitários nacionais", "variables": ["pest_distribution", "host_ranges", "plant_health_alerts"], "status": "starter_records_only", "scale_note": "cobertura regional e qualidade variam; ausência de registro não significa ausência da praga"},
            {"name": "Modelos locais de elevação e solos", "variables": ["slope", "field_boundary", "soil_physical_hydraulic_properties"], "status": "user_or_external_layer_required", "scale_note": "selecionar DEM e cartografia adequados à região e à resolução do talhão"},
        ],
    }


@router.get("/cerrado-mvp/catalog")
async def cerrado_mvp_catalog():
    """Catálogo restrito ao primeiro MVP: soja, milho, algodão e coberturas."""
    return get_cerrado_mvp_catalog()


@router.post("/assessments/cerrado-transition-options")
async def assess_cerrado_transition_options(request: CerradoMvpRotationRequest):
    """Lista opções de culturas de transição com regras agronômicas iniciais."""
    try:
        return recommend_transition_options(**request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/assessments/recommendations")
async def assess_recommendations(request: RecommendationRequest):
    """Interpreta resultados ambientais/agronômicos e preferências do produtor.

    Recebe resultados já calculados pelos demais endpoints em model_results.
    Gera ações explicáveis e lacunas de dados; não prescreve doses nem defensivos.
    """
    try:
        return generate_recommendations(request.model_dump(mode="json"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/assessments/vegetation-indices")
async def assess_vegetation_indices(request: VegetationIndexRequest):
    """Calcula índices a partir de reflectância de superfície já preparada.

    A aquisição das cenas HLS, correção/escala e máscara QA são etapas de
    integração geoespacial separadas e ainda não são executadas por este endpoint.
    """
    try:
        pixels = [ReflectancePixel(**item.model_dump()) for item in request.pixels]
        result = summarize_pixels(pixels, savi_l=request.savi_l)
        result["sensor_product"] = request.sensor_product
        result["reflectance_scale"] = request.reflectance_scale
        result["implementation_status"] = "indices_calculated_from_supplied_surface_reflectance; satellite_download_and_QA_mask_not_connected"
        result["index_notes"] = {
            "ndvi": "verdor/densidade de vegetação; não identifica sozinho a causa do estresse",
            "evi": "ajusta influência atmosférica e do fundo da copa; útil em vegetação densa",
            "savi_msavi2": "ajudam quando há solo exposto ou cobertura esparsa",
            "ndmi": "umidade relativa da vegetação usando NIR e SWIR1",
            "ndwi_green_nir": "variante de água superficial (McFeeters), não confundir com índices de umidade da vegetação",
            "nbr_nbr2": "índices de queima/alteração; não são indicadores agronômicos universais",
        }
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/assessments/vegetation-anomaly")
async def assess_vegetation_anomaly(request: VegetationAnomalyRequest):
    """Compara um índice atual com a média e o desvio-padrão históricos fornecidos."""
    z_score = standardized_anomaly(
        request.current_value,
        request.historical_mean,
        request.historical_std,
    )
    if z_score is None:
        return {
            "index_name": request.index_name,
            "z_score": None,
            "status": "insufficient_baseline_variability",
            "note": "Desvio-padrão histórico zero ou insuficiente; não é possível padronizar a anomalia.",
        }
    if z_score <= -2:
        interpretation = "valor muito abaixo da referência histórica; investigar, sem diagnosticar causa"
    elif z_score <= -1:
        interpretation = "valor abaixo da referência histórica; acompanhar"
    elif z_score >= 2:
        interpretation = "valor muito acima da referência histórica; verificar mudança de cultura/fase ou condição"
    else:
        interpretation = "dentro de uma faixa de variação histórica de triagem"
    return {
        "index_name": request.index_name,
        "current_value": request.current_value,
        "historical_mean": request.historical_mean,
        "historical_std": request.historical_std,
        "baseline_period": request.baseline_period,
        "z_score": round(z_score, 3),
        "interpretation": interpretation,
        "warning": "Comparação só é válida com talhão/área, sensor/processamento e fase fenológica comparáveis. Anomalia espectral não identifica sozinha praga, doença ou deficiência nutricional.",
    }


@router.post("/assessments/erosion")
async def assess_erosion(request: ErosionRequest):
    try:
        result = rusle_soil_loss_t_ha_year(**request.model_dump())
        result["implementation_status"] = "equation_implemented_factors_must_be_supplied_and_locally_calibrated"
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/assessments/rotation")
async def assess_rotation(request: RotationAssessmentRequest):
    try:
        result = assess_rotation_sequence(
            request.crop_sequence,
            request.detected_pests or None,
        )
        result["implementation_status"] = "transparent_host_relation_rules_starter_dataset_not_global_complete"
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/assessments/phenology-thermal")
async def assess_phenology_thermal(request: ThermalAssessmentRequest):
    try:
        return summarize_gdd_and_heat(
            [row.model_dump() for row in request.weather],
            request.base_temperature_c,
            request.upper_temperature_c,
            request.heat_threshold_c,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/assessments/dual-kc")
async def assess_dual_kc(request: DualKcRequest):
    try:
        return dual_crop_coefficient_et(**request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/assessments/yield-water-response")
async def assess_yield_water_response(request: WaterYieldResponseRequest):
    try:
        return fao_water_yield_response(**request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/health")
async def health():
    return {"status": "ok", "service": "cerradoshift-api", "version": "0.5.0"}


@router.post("/assessments/field")
async def assess_field(request: AssessmentRequest):
    """Gera avaliação agro-hídrica do processo atual do produtor.

    O endpoint aceita clima explícito (testes/estação local) ou busca NASA POWER.
    A resposta é diagnóstico de triagem, não prescrição agronômica automática.
    """
    try:
        if request.weather:
            weather = [DailyWeather(**row.model_dump()) for row in request.weather]
        else:
            weather = await fetch_nasa_power_daily(
                latitude=request.latitude,
                longitude=request.longitude,
                start_date=request.start_date,
                end_date=request.end_date,
            )

        weather = sorted(weather, key=lambda row: row.day)
        if weather[0].day != request.start_date or weather[-1].day != request.end_date:
            raise ValueError("Os dados climáticos precisam cobrir exatamente start_date até end_date.")

        crop = CropParameters(**request.crop.model_dump())
        soil = SoilProfile(
            field_capacity=request.soil.field_capacity_m3_m3,
            wilting_point=request.soil.wilting_point_m3_m3,
            initial_available_fraction=request.soil.initial_available_fraction,
            initial_theta_m3_m3=request.soil.initial_theta_m3_m3,
            initial_moisture_is_assumed=request.soil.initial_moisture_is_assumed,
            irrigation_efficiency=request.soil.irrigation_efficiency,
            irrigation_efficiency_is_assumed=request.soil.irrigation_efficiency_is_assumed,
            curve_number=request.soil.curve_number,
            new_root_zone_available_fraction=request.soil.new_root_zone_available_fraction,
            effective_soil_depth_m=request.soil.effective_soil_depth_m,
        )
        farmer = FarmerContext(**request.farmer.model_dump())

        irrigation_events: list[IrrigationEvent] = []
        for event in request.irrigation_events:
            if not (request.start_date <= event.day <= request.end_date):
                raise ValueError(f"Evento de irrigação {event.day} está fora do período analisado.")
            if event.gross_depth_mm is not None:
                gross_depth = event.gross_depth_mm
            elif event.volume_m3 is not None:
                gross_depth = event.volume_m3 / (farmer.field_area_ha * 10.0)
            else:
                volume_m3 = event.flow_rate_m3_h * event.duration_minutes / 60.0
                gross_depth = volume_m3 / (farmer.field_area_ha * 10.0)
            irrigation_events.append(IrrigationEvent(event.day, gross_depth))

        result = simulate_water_balance(
            weather=weather,
            latitude_deg=request.latitude,
            elevation_m=request.elevation_m,
            crop=crop,
            soil=soil,
            farmer=farmer,
            irrigation_events=irrigation_events,
        )
        output = result.to_dict()
        output["status_scope"] = "diagnostico_hidrico_estimado; nao representa saude geral nem produtividade"
        if result.high_temperature_days > 0:
            output["warnings"].append(f"Foram identificados {result.high_temperature_days} dia(s) acima do limite térmico configurado; confira se o limite corresponde ao cultivar e estágio.")

        # Compara estágio relatado com estágio estimado por dias após plantio.
        if farmer.current_stage_reported:
            estimated = output["daily"][-1]["crop_stage"]
            if farmer.current_stage_reported.lower() != estimated.lower():
                output["warnings"].append(
                    f"Estágio informado ({farmer.current_stage_reported}) difere do estágio fenológico estimado ({estimated}); revise duração dos estágios, cultivar e data de plantio."
                )

        # Contexto de manejo é devolvido ao frontend para a explicação do resultado.
        reported_sun = farmer.sun_exposure_hours_day
        daylight_mean = sum(daylight_hours(request.latitude, row.day) for row in weather) / len(weather)
        sun_context = {
            "astronomical_daylight_hours_mean": round(daylight_mean, 2),
            "reported_direct_sun_hours_day": reported_sun,
            "approx_fraction_of_daylight": (round(min(1.0, reported_sun / daylight_mean), 3) if reported_sun is not None and daylight_mean > 0 else None),
            "used_as_et0_multiplier": False,
            "interpretation": "Indicador contextual de exposição/sombra; horas não substituem radiação global nem PAR medidos."
        }
        if reported_sun is not None and reported_sun > daylight_mean + 0.5:
            output["warnings"].append("Horas de sol direto informadas excedem a duração astronômica média do dia; revise o dado.")

        output["context"] = {
            "crop_id": crop.crop_id,
            "cultivar": crop.cultivar,
            "planting_date": farmer.planting_date.isoformat(),
            "emergence_date": farmer.emergence_date.isoformat() if farmer.emergence_date else None,
            "analysis_start": request.start_date.isoformat(),
            "analysis_end": request.end_date.isoformat(),
            "field_area_ha": farmer.field_area_ha,
            "irrigation_frequency_days": farmer.irrigation_frequency_days,
            "irrigation_method": farmer.irrigation_method,
            "sun_exposure_hours_day": farmer.sun_exposure_hours_day,
            "sun_exposure": sun_context,
            "shade_percent": farmer.shade_percent,
            "mulch_cover_percent": farmer.mulch_cover_percent,
            "canopy_cover_percent": farmer.canopy_cover_percent,
            "weather_source": "NASA_POWER" if not request.weather else (request.weather_source_label or "user_supplied"),
            "crop_parameter_source": crop.parameter_source,
            "crop_parameter_version": crop.parameter_version,
        }
        runoff_mode = (
            "observed_or_external" if all(row.runoff_mm_day is not None for row in weather)
            else "scs_curve_number_daily_approximation" if soil.curve_number is not None
            else "zero_runoff_assumption"
        )
        output["data_quality"] = {
            "weather_source": "NASA_POWER" if not request.weather else (request.weather_source_label or "user_supplied"),
            "soil_initial_moisture": "measured_vwc" if soil.initial_theta_m3_m3 is not None else ("estimated_fraction" if not soil.initial_moisture_is_assumed else "assumed_fraction"),
            "runoff_method": runoff_mode,
            "crop_parameter_source": crop.parameter_source,
            "crop_parameter_version": crop.parameter_version,
        }
        output["model_metadata"] = {
            "model_version": "0.1.0",
            "water_balance": "daily_root_zone_single_kc",
            "reference_et": "FAO56_Penman_Monteith",
            "limitations": [
                "Kc simples: Ks é aplicado ao ETc total; para irrigação de alta precisão, implementar Kcb+Ke e balanço da camada superficial.",
                "Não modela capilaridade, lençol freático, salinidade, nutrientes, pragas, doenças, compactação nem interceptação do dossel.",
                "A chuva diária e o Curve Number são aproximações; o cálculo de escoamento requer calibração por evento e condição antecedente.",
                "Não é previsão de produtividade nem recomendação automática de irrigação.",
            ],
        }
        return output
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        # Não exponha stack traces para o cliente; registre exceções no logger
        # da aplicação em produção.
        raise HTTPException(status_code=502, detail=f"Falha ao processar dados: {exc}") from exc
