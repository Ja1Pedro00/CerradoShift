from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date
from typing import Iterable

from .crop import crop_day_parameters, adjusted_depletion_fraction
from .evapotranspiration import fao56_reference_et0
from .schemas import CropParameters, DailyWeather, FarmerContext, IrrigationEvent, SoilProfile


@dataclass
class DailyBalanceResult:
    day: str
    crop_age_days: int
    crop_stage: str
    root_depth_m: float
    et0_mm: float
    kc: float
    etc_potential_mm: float
    ks: float
    eta_actual_mm: float
    precipitation_mm: float
    runoff_mm: float
    effective_rain_mm: float
    irrigation_gross_mm: float
    irrigation_net_mm: float
    application_loss_mm: float
    deep_percolation_mm: float
    taw_mm: float
    raw_mm: float
    depletion_start_mm: float
    depletion_end_mm: float
    storage_end_mm: float
    gdd_c_day: float | None
    stress_status: str


@dataclass
class AssessmentResult:
    status: str
    latest_ks: float
    latest_depletion_mm: float
    latest_raw_mm: float
    latest_taw_mm: float
    cumulative_potential_etc_mm: float
    cumulative_actual_eta_mm: float
    cumulative_rain_mm: float
    cumulative_irrigation_gross_mm: float
    cumulative_runoff_mm: float
    cumulative_deep_percolation_mm: float
    water_stress_days: int
    longest_dry_spell_days: int
    high_temperature_days: int
    irrigation_recommendation: dict
    action_guidance: list[str]
    warnings: list[str]
    daily: list[DailyBalanceResult]

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "latest_ks": round(self.latest_ks, 3),
            "latest_depletion_mm": round(self.latest_depletion_mm, 2),
            "latest_raw_mm": round(self.latest_raw_mm, 2),
            "latest_taw_mm": round(self.latest_taw_mm, 2),
            "cumulative_potential_etc_mm": round(self.cumulative_potential_etc_mm, 2),
            "cumulative_actual_eta_mm": round(self.cumulative_actual_eta_mm, 2),
            "cumulative_rain_mm": round(self.cumulative_rain_mm, 2),
            "cumulative_irrigation_gross_mm": round(self.cumulative_irrigation_gross_mm, 2),
            "cumulative_runoff_mm": round(self.cumulative_runoff_mm, 2),
            "cumulative_deep_percolation_mm": round(self.cumulative_deep_percolation_mm, 2),
            "water_stress_days": self.water_stress_days,
            "longest_dry_spell_days": self.longest_dry_spell_days,
            "high_temperature_days": self.high_temperature_days,
            "irrigation_recommendation": self.irrigation_recommendation,
            "action_guidance": self.action_guidance,
            "warnings": self.warnings,
            "daily": [asdict(row) for row in self.daily],
        }


def scs_curve_number_runoff(precipitation_mm: float, curve_number: float) -> float:
    """Escoamento diário aproximado pela curva-número NRCS/SCS.

    A aplicação diária é uma aproximação de triagem. Para calibração em talhão,
    separar eventos de chuva e caracterizar grupo hidrológico, uso/cobertura e
    condição antecedente de umidade.
    """
    if precipitation_mm <= 0:
        return 0.0
    if not (0 < curve_number <= 100):
        raise ValueError("Curve Number deve estar entre 0 e 100.")
    storage_potential = 25400.0 / curve_number - 254.0  # S em mm
    initial_abstraction = 0.2 * storage_potential
    if precipitation_mm <= initial_abstraction:
        return 0.0
    runoff = ((precipitation_mm - initial_abstraction) ** 2) / (
        precipitation_mm + 0.8 * storage_potential
    )
    return min(precipitation_mm, max(0.0, runoff))


def total_available_water_mm(
    field_capacity: float, wilting_point: float, root_depth_m: float
) -> float:
    """TAW = 1000 * (theta_FC - theta_WP) * Zr, em mm (FAO-56)."""
    if not (0 <= wilting_point < field_capacity <= 1) or root_depth_m <= 0:
        raise ValueError("Parâmetros de solo/profundidade inválidos para TAW.")
    return 1000.0 * (field_capacity - wilting_point) * root_depth_m


def water_stress_coefficient(depletion_mm: float, taw_mm: float, raw_mm: float) -> float:
    """Ks FAO-56: 1 até RAW; cai linearmente até 0 no ponto de murcha."""
    if taw_mm <= 0 or raw_mm < 0 or raw_mm >= taw_mm:
        raise ValueError("TAW/RAW inválidos.")
    if depletion_mm <= raw_mm:
        return 1.0
    return max(0.0, min(1.0, (taw_mm - depletion_mm) / (taw_mm - raw_mm)))


def longest_dry_spell(weather: Iterable[DailyWeather], threshold_mm: float = 1.0) -> int:
    longest = current = 0
    for item in weather:
        if item.precipitation_mm_day < threshold_mm:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def _stress_label(ks: float) -> str:
    if ks >= 0.90:
        return "sem_estresse_estimado"
    if ks >= 0.70:
        return "atencao"
    if ks >= 0.40:
        return "estresse_moderado"
    return "estresse_severo"


def simulate_water_balance(
    weather: list[DailyWeather],
    latitude_deg: float,
    elevation_m: float,
    crop: CropParameters,
    soil: SoilProfile,
    farmer: FarmerContext,
    irrigation_events: list[IrrigationEvent] | None = None,
) -> AssessmentResult:
    """Simula balanço de água diário na zona radicular.

    Fluxos incluídos: chuva, escoamento (CN ou medido), irrigação líquida,
    evapotranspiração real estimada e drenagem profunda quando armazenamento
    excede TAW. Capilaridade e ascensão de lençol freático não são modeladas.

    O motor usa Kc simples e aplica Ks ao ETc total como aproximação. Para
    agendamento de irrigação de maior precisão, evoluir para Kcb + Ke e um
    balanço separado da camada superficial, conforme FAO-56 capítulo 7.
    """
    if not weather:
        raise ValueError("A simulação precisa de pelo menos um dia de clima.")
    soil.validate()
    crop.validate()
    farmer.validate()
    ordered = sorted(weather, key=lambda x: x.day)
    if len({x.day for x in ordered}) != len(ordered):
        raise ValueError("Há datas climáticas duplicadas.")
    # Não simular uma sequência incompleta como se todos os dias estivessem cobertos.
    for previous, current in zip(ordered, ordered[1:]):
        if (current.day - previous.day).days != 1:
            raise ValueError(f"Série climática incompleta entre {previous.day} e {current.day}; obtenha os dias faltantes antes de calcular o balanço.")
    if ordered[0].day < farmer.planting_date:
        raise ValueError("A data inicial do clima não pode anteceder o plantio.")
    if farmer.emergence_date is not None and ordered[0].day < farmer.emergence_date:
        raise ValueError("Esta versão inicia o cálculo fenológico na emergência; inicie o período na data de emergência ou depois dela.")

    irrigation_by_day: dict[date, float] = {}
    for event in irrigation_events or []:
        if event.gross_depth_mm < 0:
            raise ValueError("Lâmina de irrigação não pode ser negativa.")
        irrigation_by_day[event.day] = irrigation_by_day.get(event.day, 0.0) + event.gross_depth_mm

    warnings: list[str] = []
    if soil.effective_soil_depth_m is not None and soil.effective_soil_depth_m < crop.root_depth_max_m:
        warnings.append("Profundidade efetiva do solo limita a profundidade radicular parametrizada; TAW foi limitado ao solo efetivamente explorável.")
    if soil.curve_number is None and all(x.runoff_mm_day is None for x in ordered):
        warnings.append("Escoamento não modelado: foi assumido zero. Informe Curve Number calibrado ou escoamento observado.")
    if soil.initial_moisture_is_assumed and soil.initial_theta_m3_m3 is None:
        warnings.append("Umidade inicial assumida: foi usado o valor de initial_available_fraction; substitua por sensor ou estimativa local documentada.")
    if soil.irrigation_efficiency_is_assumed:
        warnings.append("Eficiência de irrigação assumida; informe eficiência medida/estimada para o método e estado real do sistema.")
    if crop.root_depth_max_m > crop.root_depth_initial_m:
        warnings.append("Crescimento radicular é linear e a umidade da nova camada explorada foi assumida; calibrar com perfil de solo/raízes ou sensores em profundidade.")
    if not crop.parameter_source or crop.parameter_source.startswith("PREENCHER"):
        warnings.append("Parâmetros agronômicos sem referência validada: Kc, p, fenologia e raízes precisam de validação para a cultivar/região.")
    if farmer.irrigation_frequency_days is not None and not irrigation_events:
        warnings.append("Frequência de irrigação informada sem lâmina/volume por evento; frequência sozinha não permite fechar o balanço hídrico.")
    if farmer.sun_exposure_hours_day is not None:
        warnings.append("Horas de sol foram registradas como contexto de sombreamento; não foram multiplicadas por ET0, pois a radiação meteorológica já participa do cálculo.")

    results: list[DailyBalanceResult] = []
    previous_root_depth: float | None = None
    depletion = 0.0
    total_potential_etc = total_actual_eta = total_rain = 0.0
    total_irrigation_gross = total_runoff = total_deep_percolation = 0.0
    water_stress_days = high_temperature_days = 0

    for day_weather in ordered:
        if day_weather.day < farmer.planting_date:
            continue
        phenology_start = farmer.emergence_date or farmer.planting_date
        crop_day = crop_day_parameters(
            crop, phenology_start, day_weather.day,
            day_weather.tmax_c, day_weather.tmin_c
        )
        root_depth = crop_day.root_depth_m
        if soil.effective_soil_depth_m is not None and root_depth > soil.effective_soil_depth_m:
            root_depth = soil.effective_soil_depth_m
        taw = total_available_water_mm(soil.field_capacity, soil.wilting_point, root_depth)

        # Ao crescer a raiz, o novo solo explorado não é automaticamente
        # considerado úmido: recebe a fração inicial explicitada no perfil.
        if previous_root_depth is None:
            if soil.initial_theta_m3_m3 is not None:
                initial_fraction = (soil.initial_theta_m3_m3 - soil.wilting_point) / (soil.field_capacity - soil.wilting_point)
            else:
                initial_fraction = soil.initial_available_fraction
            depletion = (1.0 - initial_fraction) * taw
        elif root_depth > previous_root_depth:
            added_taw = total_available_water_mm(
                soil.field_capacity, soil.wilting_point,
                root_depth - previous_root_depth
            )
            depletion += (1.0 - soil.new_root_zone_available_fraction) * added_taw
        depletion = max(0.0, min(taw, depletion))
        previous_root_depth = root_depth

        et0 = fao56_reference_et0(day_weather, latitude_deg, elevation_m)
        etc_potential = crop_day.kc * et0
        p_adjusted = adjusted_depletion_fraction(crop.depletion_fraction_p, etc_potential)
        raw = p_adjusted * taw
        ks = water_stress_coefficient(depletion, taw, raw)

        # Kc simples: aproximação de ETc real = Ks * Kc * ET0.
        # Ks atua na transpiração; Kc simples também contém evaporação do solo.
        eta = ks * etc_potential

        runoff = (
            day_weather.runoff_mm_day
            if day_weather.runoff_mm_day is not None
            else scs_curve_number_runoff(day_weather.precipitation_mm_day, soil.curve_number)
            if soil.curve_number is not None
            else 0.0
        )
        runoff = min(day_weather.precipitation_mm_day, max(0.0, runoff))
        effective_rain = day_weather.precipitation_mm_day - runoff

        irrigation_gross = irrigation_by_day.get(day_weather.day, 0.0)
        irrigation_net = irrigation_gross * soil.irrigation_efficiency
        application_loss = irrigation_gross - irrigation_net

        storage_start = taw - depletion
        water_before_et = storage_start + effective_rain + irrigation_net
        deep_percolation = max(0.0, water_before_et - taw)
        storage_before_et = min(taw, water_before_et)
        # ET real não pode retirar mais água do que existe no reservatório.
        eta = min(eta, storage_before_et)
        storage_end = max(0.0, storage_before_et - eta)
        depletion_end = taw - storage_end

        status = _stress_label(ks)
        if ks < 0.90:
            water_stress_days += 1
        stage_heat_limit = crop.heat_thresholds_by_stage.get(
            crop_day.stage, crop.heat_threshold_c
        )
        if stage_heat_limit is not None and day_weather.tmax_c > stage_heat_limit:
            high_temperature_days += 1

        results.append(DailyBalanceResult(
            day=day_weather.day.isoformat(),
            crop_age_days=crop_day.days_after_planting,
            crop_stage=crop_day.stage,
            root_depth_m=round(root_depth, 3),
            et0_mm=round(et0, 3),
            kc=round(crop_day.kc, 3),
            etc_potential_mm=round(etc_potential, 3),
            ks=round(ks, 3),
            eta_actual_mm=round(eta, 3),
            precipitation_mm=round(day_weather.precipitation_mm_day, 3),
            runoff_mm=round(runoff, 3),
            effective_rain_mm=round(effective_rain, 3),
            irrigation_gross_mm=round(irrigation_gross, 3),
            irrigation_net_mm=round(irrigation_net, 3),
            application_loss_mm=round(application_loss, 3),
            deep_percolation_mm=round(deep_percolation, 3),
            taw_mm=round(taw, 3),
            raw_mm=round(raw, 3),
            depletion_start_mm=round(taw - storage_start, 3),
            depletion_end_mm=round(depletion_end, 3),
            storage_end_mm=round(storage_end, 3),
            gdd_c_day=round(crop_day.gdd_c_day, 3) if crop_day.gdd_c_day is not None else None,
            stress_status=status,
        ))

        total_potential_etc += etc_potential
        total_actual_eta += eta
        total_rain += day_weather.precipitation_mm_day
        total_irrigation_gross += irrigation_gross
        total_runoff += runoff
        total_deep_percolation += deep_percolation
        depletion = depletion_end

    if not results:
        raise ValueError("Nenhum dia de clima corresponde ao período após o plantio.")

    last = results[-1]
    final_ks = last.ks
    final_depletion = last.depletion_end_mm
    final_raw = last.raw_mm
    final_taw = last.taw_mm
    final_status = _stress_label(final_ks)

    # Recomendação de lâmina: repor até metade de RAW, sem exceder a depleção.
    # É uma sugestão de triagem, não uma ordem automática de irrigação.
    net_recommendation = max(0.0, final_depletion - 0.5 * final_raw) if final_depletion >= final_raw else 0.0
    gross_recommendation = net_recommendation / soil.irrigation_efficiency
    volume_m3 = gross_recommendation * farmer.field_area_ha * 10.0
    recommendation = {
        "irrigation_attention": bool(final_depletion >= final_raw),
        "suggested_net_depth_mm": round(net_recommendation, 2),
        "suggested_gross_depth_mm": round(gross_recommendation, 2),
        "estimated_gross_volume_m3": round(volume_m3, 2),
        "basis": "Reposição simplificada até 50% de RAW; conferir umidade real, previsão de chuva, capacidade de infiltração e sistema de irrigação antes de aplicar.",
    }

    # Orientações de checagem em linguagem de produto. Elas não substituem
    # a avaliação de um agrônomo nem transformam o valor calculado em ordem.
    action_guidance: list[str] = []
    if final_depletion >= final_raw:
        action_guidance.append("A depleção estimada atingiu o limite RAW configurado. Confirme a umidade na zona radicular e a previsão de chuva antes de decidir irrigar.")
    elif final_ks < 0.90:
        action_guidance.append("Há redução estimada da evapotranspiração por estresse hídrico. Verifique sensores, profundidade molhada e uniformidade da irrigação.")
    else:
        action_guidance.append("O balanço não indica estresse hídrico acima do limite configurado no último dia. Continue monitorando umidade e chuva.")
    if farmer.irrigation_frequency_days is not None and not irrigation_events:
        action_guidance.append("Registre a lâmina ou o volume de cada irrigação; a frequência isolada não informa quanta água entrou no solo.")
    if soil.initial_moisture_is_assumed and soil.initial_theta_m3_m3 is None:
        action_guidance.append("Meça a umidade em mais de uma profundidade representativa da zona radicular para reduzir a incerteza do estado inicial.")
    if high_temperature_days > 0:
        action_guidance.append("Houve dias acima do limite térmico cadastrado. Confira se ocorreram em fase sensível e valide o limite específico do cultivar.")
    if longest_dry_spell(ordered) >= 5:
        action_guidance.append("Foi observada sequência prolongada com pouca chuva; acompanhe a umidade do perfil, não apenas a chuva acumulada.")

    return AssessmentResult(
        status=final_status,
        latest_ks=final_ks,
        latest_depletion_mm=final_depletion,
        latest_raw_mm=final_raw,
        latest_taw_mm=final_taw,
        cumulative_potential_etc_mm=total_potential_etc,
        cumulative_actual_eta_mm=total_actual_eta,
        cumulative_rain_mm=total_rain,
        cumulative_irrigation_gross_mm=total_irrigation_gross,
        cumulative_runoff_mm=total_runoff,
        cumulative_deep_percolation_mm=total_deep_percolation,
        water_stress_days=water_stress_days,
        longest_dry_spell_days=longest_dry_spell(ordered),
        high_temperature_days=high_temperature_days,
        irrigation_recommendation=recommendation,
        action_guidance=action_guidance,
        warnings=warnings,
        daily=results,
    )
