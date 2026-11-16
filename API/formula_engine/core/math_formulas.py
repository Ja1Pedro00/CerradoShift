"""Funções matemáticas do CerradoShift — MVP Cerrado.

Este módulo reúne, em funções pequenas e documentadas, as equações discutidas
para o projeto. Não baixa dados da NASA, não lê imagens e não substitui o
catálogo agronômico: recebe números já preparados e devolve resultados.

Unidades principais:
- temperatura: graus Celsius (°C), salvo quando indicado;
- água e evapotranspiração: milímetros (mm) ou mm/dia;
- profundidade: metros (m);
- reflectância: escala de superfície 0–1 (não DN bruto);
- latitude: graus decimais;
- radiação: MJ m-2 dia-1;
- pressão de vapor: kPa.

Status de implementação:
- As funções são disponibilizadas neste módulo para reutilização.
- Isso não significa que todas estejam ligadas ao endpoint de balanço hídrico.
- As funções de NDVI, RUSLE, Kc dual, produtividade e pontuação de rotação
  continuam módulos independentes/experimentais no MVP atual.

Referências metodológicas principais: FAO Irrigation and Drainage Paper 56
(Penman–Monteith, Kc, TAW/RAW/Ks e método dual), SCS/NRCS Curve Number,
RUSLE, e relação FAO Ky de resposta da produtividade à água.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math
from statistics import mean, median
from typing import Iterable, Mapping, Optional, Sequence


# ---------------------------------------------------------------------------
# 0. Validação e utilitários
# ---------------------------------------------------------------------------

def _finite(name: str, value: float) -> float:
    """Converte para float e rejeita NaN/infinito."""
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} deve ser um número finito.")
    return value


def _non_negative(name: str, value: float) -> float:
    value = _finite(name, value)
    if value < 0:
        raise ValueError(f"{name} não pode ser negativo.")
    return value


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


# ---------------------------------------------------------------------------
# 1. Meteorologia e evapotranspiração de referência — FAO-56
# ---------------------------------------------------------------------------

def mean_air_temperature_c(tmax_c: float, tmin_c: float) -> float:
    """Temperatura média diária: (Tmax + Tmin) / 2."""
    tmax_c, tmin_c = _finite("Tmax", tmax_c), _finite("Tmin", tmin_c)
    if tmax_c < tmin_c:
        raise ValueError("Tmax não pode ser menor que Tmin.")
    return (tmax_c + tmin_c) / 2.0


def saturation_vapour_pressure_kpa(temp_c: float) -> float:
    """Pressão de vapor de saturação e°(T), em kPa (FAO-56)."""
    temp_c = _finite("temperatura", temp_c)
    denominator = temp_c + 237.3
    if abs(denominator) < 1e-12:
        raise ValueError("Temperatura produz denominador inválido.")
    return 0.6108 * math.exp((17.27 * temp_c) / denominator)


def mean_saturation_vapour_pressure_kpa(tmax_c: float, tmin_c: float) -> float:
    """es = [e°(Tmax) + e°(Tmin)] / 2, em kPa."""
    return (
        saturation_vapour_pressure_kpa(tmax_c)
        + saturation_vapour_pressure_kpa(tmin_c)
    ) / 2.0


def actual_vapour_pressure_kpa(
    es_kpa: float,
    rh_mean_pct: Optional[float] = None,
    dew_point_c: Optional[float] = None,
) -> float:
    """Pressão real ea.

    Preferência: ponto de orvalho, ea = e°(Tdew). Alternativa aproximada:
    ea = (URmed/100) * es. Para dados completos, FAO-56 pode usar UR máxima e
    mínima em vez desta aproximação com UR média.
    """
    es_kpa = _non_negative("es", es_kpa)
    if dew_point_c is not None:
        ea = saturation_vapour_pressure_kpa(dew_point_c)
    elif rh_mean_pct is not None:
        rh_mean_pct = _finite("UR média", rh_mean_pct)
        if not 0 <= rh_mean_pct <= 100:
            raise ValueError("UR média deve estar entre 0 e 100%.")
        ea = (rh_mean_pct / 100.0) * es_kpa
    else:
        raise ValueError("Informe ponto de orvalho ou umidade relativa média.")
    return _clamp(ea, 0.0, es_kpa)


def vapour_pressure_deficit_kpa(es_kpa: float, ea_kpa: float) -> float:
    """Déficit de pressão de vapor: VPD = es - ea, em kPa."""
    es_kpa, ea_kpa = _non_negative("es", es_kpa), _non_negative("ea", ea_kpa)
    if ea_kpa > es_kpa:
        raise ValueError("ea não deve ser maior que es.")
    return es_kpa - ea_kpa


def slope_vapour_pressure_curve_kpa_c(temp_c: float) -> float:
    """Inclinação Δ da curva de pressão de vapor, em kPa/°C."""
    es = saturation_vapour_pressure_kpa(temp_c)
    return 4098.0 * es / ((temp_c + 237.3) ** 2)


def atmospheric_pressure_kpa(elevation_m: float) -> float:
    """Pressão atmosférica aproximada pela altitude, em kPa (FAO-56)."""
    elevation_m = _finite("altitude", elevation_m)
    base = (293.0 - 0.0065 * elevation_m) / 293.0
    if base <= 0:
        raise ValueError("Altitude fora do domínio da fórmula de pressão.")
    return 101.3 * (base ** 5.26)


def psychrometric_constant_kpa_c(pressure_kpa: float) -> float:
    """Constante psicrométrica γ = 0,000665 * pressão, em kPa/°C."""
    pressure_kpa = _non_negative("pressão atmosférica", pressure_kpa)
    return 0.000665 * pressure_kpa


def extraterrestrial_radiation_mj_m2_day(latitude_deg: float, day_of_year: int) -> float:
    """Radiação extraterrestre diária Ra pela geometria solar FAO-56."""
    latitude_deg = _finite("latitude", latitude_deg)
    if not -90 <= latitude_deg <= 90:
        raise ValueError("Latitude deve estar entre -90 e 90 graus.")
    if not 1 <= int(day_of_year) <= 366:
        raise ValueError("day_of_year deve estar entre 1 e 366.")
    lat = math.radians(latitude_deg)
    j = int(day_of_year)
    dr = 1.0 + 0.033 * math.cos(2.0 * math.pi * j / 365.0)
    declination = 0.409 * math.sin(2.0 * math.pi * j / 365.0 - 1.39)
    arg = _clamp(-math.tan(lat) * math.tan(declination), -1.0, 1.0)
    sunset_angle = math.acos(arg)
    solar_constant = 0.0820  # MJ m-2 min-1
    ra = (24.0 * 60.0 / math.pi) * solar_constant * dr * (
        sunset_angle * math.sin(lat) * math.sin(declination)
        + math.cos(lat) * math.cos(declination) * math.sin(sunset_angle)
    )
    return max(0.0, ra)


def daylight_hours(latitude_deg: float, day_of_year: int) -> float:
    """Duração astronômica do dia em horas (não equivale a horas de sol medido)."""
    latitude_deg = _finite("latitude", latitude_deg)
    if not -90 <= latitude_deg <= 90:
        raise ValueError("Latitude deve estar entre -90 e 90 graus.")
    if not 1 <= int(day_of_year) <= 366:
        raise ValueError("day_of_year deve estar entre 1 e 366.")
    lat = math.radians(latitude_deg)
    declination = 0.409 * math.sin(2.0 * math.pi * int(day_of_year) / 365.0 - 1.39)
    arg = _clamp(-math.tan(lat) * math.tan(declination), -1.0, 1.0)
    sunset_angle = math.acos(arg)
    return 24.0 * sunset_angle / math.pi


def wind_10m_to_2m(wind_10m_m_s: float) -> float:
    """Converte vento medido a 10 m para 2 m conforme FAO-56."""
    wind_10m_m_s = _non_negative("vento a 10 m", wind_10m_m_s)
    return wind_10m_m_s * 4.87 / math.log(67.8 * 10.0 - 5.42)


def net_radiation_fao56_mj_m2_day(
    solar_radiation_mj_m2_day: float,
    extraterrestrial_radiation_mj_m2_day_value: float,
    elevation_m: float,
    tmax_c: float,
    tmin_c: float,
    actual_vapour_pressure_kpa_value: float,
) -> dict[str, float]:
    """Calcula Rns, Rnl, Rso e Rn pelo procedimento diário FAO-56.

    G é tratado como zero posteriormente no cálculo diário de ET0.
    """
    rs = _non_negative("radiação solar Rs", solar_radiation_mj_m2_day)
    ra = _non_negative("radiação extraterrestre Ra", extraterrestrial_radiation_mj_m2_day_value)
    ea = _non_negative("pressão real ea", actual_vapour_pressure_kpa_value)
    if tmax_c < tmin_c:
        raise ValueError("Tmax não pode ser menor que Tmin.")
    rso = (0.75 + 2e-5 * elevation_m) * ra
    rns = 0.77 * rs
    if rso <= 0:
        rnl = 0.0
    else:
        cloudiness = max(0.3, min(rs / rso, 1.0))
        sigma = 4.903e-9  # MJ K-4 m-2 dia-1
        tmax_k = tmax_c + 273.16
        tmin_k = tmin_c + 273.16
        rnl = sigma * ((tmax_k**4 + tmin_k**4) / 2.0) * (
            0.34 - 0.14 * math.sqrt(ea)
        ) * (1.35 * cloudiness - 0.35)
    return {"rso_mj_m2_day": rso, "rns_mj_m2_day": rns, "rnl_mj_m2_day": rnl, "rn_mj_m2_day": rns - rnl}


def fao56_et0_mm_day(
    *,
    tmax_c: float,
    tmin_c: float,
    rh_mean_pct: Optional[float],
    wind_2m_m_s: float,
    solar_radiation_mj_m2_day: float,
    latitude_deg: float,
    elevation_m: float,
    day_of_year: int,
    dew_point_c: Optional[float] = None,
    wind_is_10m: bool = False,
) -> float:
    """ET0 diária pela equação FAO-56 Penman–Monteith, em mm/dia.

    Entradas meteorológicas devem representar o mesmo local e dia. Se rh_mean
    for None, dew_point_c é obrigatório. Se wind_is_10m=True, converte o vento.
    O fluxo de calor no solo G é aproximado por zero no passo diário.
    """
    tmax_c, tmin_c = _finite("Tmax", tmax_c), _finite("Tmin", tmin_c)
    if tmax_c < tmin_c:
        raise ValueError("Tmax não pode ser menor que Tmin.")
    rs = _non_negative("radiação solar", solar_radiation_mj_m2_day)
    wind = _non_negative("vento", wind_2m_m_s)
    tmean = mean_air_temperature_c(tmax_c, tmin_c)
    es = mean_saturation_vapour_pressure_kpa(tmax_c, tmin_c)
    ea = actual_vapour_pressure_kpa(es, rh_mean_pct, dew_point_c)
    delta = slope_vapour_pressure_curve_kpa_c(tmean)
    pressure = atmospheric_pressure_kpa(elevation_m)
    gamma = psychrometric_constant_kpa_c(pressure)
    u2 = wind_10m_to_2m(wind) if wind_is_10m else wind
    ra = extraterrestrial_radiation_mj_m2_day(latitude_deg, day_of_year)
    radiation = net_radiation_fao56_mj_m2_day(rs, ra, elevation_m, tmax_c, tmin_c, ea)
    rn = radiation["rn_mj_m2_day"]
    g = 0.0
    numerator = 0.408 * delta * (rn - g) + gamma * (900.0 / (tmean + 273.0)) * u2 * (es - ea)
    denominator = delta + gamma * (1.0 + 0.34 * u2)
    if denominator <= 0:
        raise ValueError("Denominador inválido no cálculo de ET0.")
    return max(0.0, numerator / denominator)


# ---------------------------------------------------------------------------
# 2. Cultura: estágios, Kc, raízes, GDD e fração p
# ---------------------------------------------------------------------------

def crop_stage_and_kc(
    days_after_planting: int,
    stage_initial_days: int,
    stage_development_days: int,
    stage_mid_days: int,
    stage_late_days: int,
    kc_initial: float,
    kc_mid: float,
    kc_end: float,
) -> dict[str, float | str]:
    """Retorna estágio e Kc por curva FAO de quatro estágios simplificada."""
    durations = [stage_initial_days, stage_development_days, stage_mid_days, stage_late_days]
    if any(int(x) < 0 for x in durations) or sum(durations) <= 0:
        raise ValueError("Durações dos estágios devem ser não negativas e ter soma positiva.")
    if stage_development_days == 0 or stage_late_days == 0:
        # Estágio de duração zero é permitido; não haverá interpolação nesse trecho.
        pass
    if min(kc_initial, kc_mid, kc_end) < 0:
        raise ValueError("Coeficientes Kc não podem ser negativos.")
    d = max(0, int(days_after_planting))
    initial_end = stage_initial_days
    dev_end = initial_end + stage_development_days
    mid_end = dev_end + stage_mid_days
    late_end = mid_end + stage_late_days
    if d < initial_end:
        return {"stage": "initial", "kc": float(kc_initial)}
    if d < dev_end and stage_development_days > 0:
        fraction = (d - initial_end) / stage_development_days
        kc = kc_initial + fraction * (kc_mid - kc_initial)
        return {"stage": "development", "kc": kc}
    if d < mid_end:
        return {"stage": "mid", "kc": float(kc_mid)}
    if d < late_end and stage_late_days > 0:
        fraction = (d - mid_end) / stage_late_days
        kc = kc_mid + fraction * (kc_end - kc_mid)
        return {"stage": "late", "kc": kc}
    return {"stage": "completed", "kc": float(kc_end)}


def root_depth_linear_m(
    days_after_planting: int,
    root_depth_initial_m: float,
    root_depth_max_m: float,
    root_growth_days: int,
) -> float:
    """Crescimento linear simplificado da profundidade radicular até Zr máximo."""
    if root_depth_initial_m <= 0 or root_depth_max_m < root_depth_initial_m or root_growth_days <= 0:
        raise ValueError("Parâmetros de profundidade/crescimento radicular inválidos.")
    fraction = _clamp(max(0, int(days_after_planting)) / root_growth_days, 0.0, 1.0)
    return root_depth_initial_m + fraction * (root_depth_max_m - root_depth_initial_m)


def adjusted_depletion_fraction(p_table: float, etc_mm_day: float) -> float:
    """Ajusta p conforme ETc: p_adj = p_tab + 0,04(5 - ETc), limitado 0,1–0,8."""
    if not 0 <= p_table <= 1:
        raise ValueError("p_table deve estar entre 0 e 1.")
    etc_mm_day = _non_negative("ETc", etc_mm_day)
    return _clamp(p_table + 0.04 * (5.0 - etc_mm_day), 0.1, 0.8)


def daily_gdd_c_day(tmax_c: float, tmin_c: float, base_c: float, upper_c: Optional[float] = None) -> float:
    """Graus-dia diário pelo método média, com limites térmicos inferior/superior."""
    if upper_c is not None and upper_c <= base_c:
        raise ValueError("Temperatura superior deve ser maior que a temperatura-base.")
    tmax = max(base_c, _finite("Tmax", tmax_c))
    tmin = max(base_c, _finite("Tmin", tmin_c))
    if upper_c is not None:
        tmax = min(tmax, upper_c)
        tmin = min(tmin, upper_c)
    return max(0.0, (tmax + tmin) / 2.0 - base_c)


def cumulative_gdd_c_day(weather: Sequence[Mapping[str, float]], base_c: float, upper_c: Optional[float] = None) -> float:
    """Soma GDD diário de registros com tmax_c e tmin_c."""
    return sum(daily_gdd_c_day(row["tmax_c"], row["tmin_c"], base_c, upper_c) for row in weather)


def daily_heat_excess_c(tmax_c: float, threshold_c: float) -> float:
    """Excesso diário simples acima de um limiar: max(0, Tmax - limite)."""
    return max(0.0, _finite("Tmax", tmax_c) - _finite("limite térmico", threshold_c))


def summarize_heat_exposure(tmax_values_c: Sequence[float], threshold_c: float) -> dict[str, float | int]:
    """Conta dias e soma graus acima do limiar; não estima dano fisiológico."""
    excesses = [daily_heat_excess_c(t, threshold_c) for t in tmax_values_c]
    return {"heat_days": sum(x > 0 for x in excesses), "heat_excess_degree_days_c": sum(excesses)}


# ---------------------------------------------------------------------------
# 3. Água no solo, escoamento, irrigação e balanço diário simplificado
# ---------------------------------------------------------------------------

def total_available_water_mm(field_capacity: float, wilting_point: float, root_depth_m: float) -> float:
    """TAW = 1000(θFC - θWP)Zr; umidade em m³/m³, Zr em m, saída em mm."""
    fc, wp = _finite("capacidade de campo", field_capacity), _finite("ponto de murcha", wilting_point)
    z = _non_negative("profundidade radicular", root_depth_m)
    if not 0 <= wp < fc <= 1 or z <= 0:
        raise ValueError("Exija 0 <= ponto de murcha < capacidade de campo <= 1 e Zr > 0.")
    return 1000.0 * (fc - wp) * z


def readily_available_water_mm(p_fraction: float, taw_mm: float) -> float:
    """RAW = p * TAW."""
    if not 0 <= p_fraction <= 1 or taw_mm <= 0:
        raise ValueError("p deve estar em [0,1] e TAW deve ser positivo.")
    return p_fraction * taw_mm


def water_stress_coefficient(depletion_mm: float, taw_mm: float, raw_mm: float) -> float:
    """Ks FAO-56: 1 até RAW; depois cai linearmente até 0 em TAW."""
    if taw_mm <= 0 or not 0 <= raw_mm < taw_mm:
        raise ValueError("Exija TAW > RAW >= 0.")
    d = max(0.0, depletion_mm)
    if d <= raw_mm:
        return 1.0
    return _clamp((taw_mm - d) / (taw_mm - raw_mm), 0.0, 1.0)


def scs_curve_number_runoff_mm(precipitation_mm: float, curve_number: float) -> float:
    """Escoamento pelo SCS/NRCS Curve Number (aproximação por evento)."""
    p = _non_negative("precipitação", precipitation_mm)
    cn = _finite("Curve Number", curve_number)
    if not 0 < cn <= 100:
        raise ValueError("Curve Number deve estar no intervalo (0,100].")
    if p == 0:
        return 0.0
    s = 25400.0 / cn - 254.0
    initial_abstraction = 0.2 * s
    if p <= initial_abstraction:
        return 0.0
    runoff = ((p - initial_abstraction) ** 2) / (p + 0.8 * s)
    return _clamp(runoff, 0.0, p)


def effective_rainfall_mm(precipitation_mm: float, runoff_mm: float) -> float:
    """Chuva efetiva simplificada = precipitação - escoamento superficial."""
    p = _non_negative("precipitação", precipitation_mm)
    q = _clamp(_non_negative("escoamento", runoff_mm), 0.0, p)
    return p - q


def net_irrigation_mm(gross_irrigation_mm: float, application_efficiency: float) -> float:
    """Lâmina líquida = lâmina bruta × eficiência de aplicação."""
    gross = _non_negative("irrigação bruta", gross_irrigation_mm)
    if not 0 < application_efficiency <= 1:
        raise ValueError("Eficiência deve estar em (0,1].")
    return gross * application_efficiency


def irrigation_application_loss_mm(gross_irrigation_mm: float, application_efficiency: float) -> float:
    """Perda de aplicação = lâmina bruta - lâmina líquida."""
    gross = _non_negative("irrigação bruta", gross_irrigation_mm)
    return gross - net_irrigation_mm(gross, application_efficiency)


def irrigation_volume_m3(irrigation_depth_mm: float, area_ha: float) -> float:
    """Volume em m³: 1 mm aplicado em 1 ha equivale a 10 m³."""
    depth = _non_negative("lâmina de irrigação", irrigation_depth_mm)
    area = _non_negative("área", area_ha)
    return depth * area * 10.0


def initial_depletion_mm(
    initial_theta: Optional[float],
    field_capacity: float,
    wilting_point: float,
    taw_mm: float,
    assumed_available_fraction: Optional[float] = None,
) -> float:
    """Calcula depleção inicial a partir da umidade medida ou fração assumida."""
    fc, wp = field_capacity, wilting_point
    if not 0 <= wp < fc <= 1 or taw_mm <= 0:
        raise ValueError("Parâmetros de solo/TAW inválidos.")
    if initial_theta is not None:
        theta = _finite("umidade inicial", initial_theta)
        fraction = _clamp((theta - wp) / (fc - wp), 0.0, 1.0)
    elif assumed_available_fraction is not None:
        if not 0 <= assumed_available_fraction <= 1:
            raise ValueError("Fração disponível assumida deve estar entre 0 e 1.")
        fraction = assumed_available_fraction
    else:
        raise ValueError("Informe umidade inicial medida ou fração disponível assumida.")
    return (1.0 - fraction) * taw_mm


def expand_root_zone_depletion_mm(
    previous_depletion_mm: float,
    field_capacity: float,
    wilting_point: float,
    added_root_depth_m: float,
    new_zone_available_fraction: float,
) -> float:
    """Atualiza depleção quando raízes alcançam nova camada de solo."""
    if not 0 <= new_zone_available_fraction <= 1:
        raise ValueError("Fração de água disponível na nova camada deve estar em [0,1].")
    added_taw = total_available_water_mm(field_capacity, wilting_point, added_root_depth_m)
    return max(0.0, previous_depletion_mm) + (1.0 - new_zone_available_fraction) * added_taw


def daily_water_balance_step(
    *,
    depletion_start_mm: float,
    taw_mm: float,
    raw_mm: float,
    etc_potential_mm: float,
    precipitation_mm: float,
    curve_number: Optional[float] = None,
    observed_runoff_mm: Optional[float] = None,
    irrigation_gross_mm: float = 0.0,
    irrigation_efficiency: float = 1.0,
) -> dict[str, float]:
    """Executa um passo diário do balanço hídrico simplificado do MVP.

    O Ks é calculado a partir da depleção no início do dia (como no motor atual).
    Fluxos: chuva efetiva + irrigação líquida - ET real - drenagem profunda.
    Não modela ascensão capilar, redistribuição entre camadas nem camada de
    evaporação separada. Para uso operacional, evoluir para balanço multicamada.
    """
    if taw_mm <= 0 or not 0 <= raw_mm < taw_mm:
        raise ValueError("Exija TAW > RAW >= 0.")
    etc_pot = _non_negative("ETc potencial", etc_potential_mm)
    p = _non_negative("precipitação", precipitation_mm)
    depletion = _clamp(_non_negative("depleção inicial", depletion_start_mm), 0.0, taw_mm)
    ks = water_stress_coefficient(depletion, taw_mm, raw_mm)
    eta_target = ks * etc_pot

    if observed_runoff_mm is not None:
        runoff = _clamp(_non_negative("escoamento observado", observed_runoff_mm), 0.0, p)
    elif curve_number is not None:
        runoff = scs_curve_number_runoff_mm(p, curve_number)
    else:
        runoff = 0.0
    peff = p - runoff
    inet = net_irrigation_mm(irrigation_gross_mm, irrigation_efficiency)
    iloss = irrigation_application_loss_mm(irrigation_gross_mm, irrigation_efficiency)

    storage_start = taw_mm - depletion
    water_before_et = storage_start + peff + inet
    deep_percolation = max(0.0, water_before_et - taw_mm)
    storage_before_et = min(taw_mm, water_before_et)
    eta = min(eta_target, storage_before_et)
    storage_end = max(0.0, storage_before_et - eta)
    depletion_end = taw_mm - storage_end
    return {
        "ks": ks,
        "runoff_mm": runoff,
        "effective_rain_mm": peff,
        "irrigation_net_mm": inet,
        "application_loss_mm": iloss,
        "etc_potential_mm": etc_pot,
        "eta_actual_mm": eta,
        "deep_percolation_mm": deep_percolation,
        "storage_start_mm": storage_start,
        "storage_end_mm": storage_end,
        "depletion_start_mm": depletion,
        "depletion_end_mm": depletion_end,
        "taw_mm": taw_mm,
        "raw_mm": raw_mm,
    }


def irrigation_recommendation_mm(depletion_mm: float, raw_mm: float, efficiency: float = 1.0) -> dict[str, float]:
    """Regra simples do MVP: quando D>=RAW, repõe até 50% do RAW."""
    d = _non_negative("depleção", depletion_mm)
    raw = _non_negative("RAW", raw_mm)
    if not 0 < efficiency <= 1:
        raise ValueError("Eficiência deve estar em (0,1].")
    net = max(0.0, d - 0.5 * raw) if d >= raw else 0.0
    gross = net / efficiency
    return {"net_mm": net, "gross_mm": gross}


def longest_dry_spell_days(precipitation_values_mm: Sequence[float], threshold_mm: float = 1.0) -> int:
    """Maior sequência de dias com precipitação abaixo do limiar informado."""
    threshold = _non_negative("limiar de chuva", threshold_mm)
    current = longest = 0
    for p in precipitation_values_mm:
        if _non_negative("precipitação diária", p) < threshold:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def count_water_stress_days(ks_values: Sequence[float], threshold: float = 0.90) -> int:
    """Conta dias em que Ks fica abaixo do limiar operacional informado."""
    if not 0 <= threshold <= 1:
        raise ValueError("Limiar de Ks deve estar entre 0 e 1.")
    if any(not 0 <= _finite("Ks", value) <= 1 for value in ks_values):
        raise ValueError("Todos os valores de Ks devem estar entre 0 e 1.")
    return sum(value < threshold for value in ks_values)


# ---------------------------------------------------------------------------
# 4. Sensoriamento remoto: índices espectrais e anomalia
# ---------------------------------------------------------------------------

def _safe_ratio(numerator: float, denominator: float) -> Optional[float]:
    return None if abs(denominator) < 1e-12 else numerator / denominator


def vegetation_indices(
    *,
    red: float,
    nir: float,
    blue: Optional[float] = None,
    green: Optional[float] = None,
    swir1: Optional[float] = None,
    swir2: Optional[float] = None,
    savi_l: float = 0.5,
) -> dict[str, Optional[float]]:
    """Calcula NDVI, EVI, SAVI, MSAVI2, NDMI, NDWI Green-NIR, NBR e NBR2.

    As bandas devem ser reflectância de superfície escalada para valores
    plausíveis (normalmente 0–1), após máscara de nuvens/sombras e QA.
    """
    bands = {"red": red, "nir": nir, "blue": blue, "green": green, "swir1": swir1, "swir2": swir2}
    for name, value in bands.items():
        if value is not None and not 0 <= _finite(name, value) <= 1.5:
            raise ValueError(f"Reflectância {name} deve estar em escala plausível 0–1.5.")
    if savi_l < 0:
        raise ValueError("SAVI L não pode ser negativo.")
    ndvi = _safe_ratio(nir - red, nir + red)
    savi = _safe_ratio((1 + savi_l) * (nir - red), nir + red + savi_l)
    msavi_term = (2 * nir + 1) ** 2 - 8 * (nir - red)
    msavi2 = (2 * nir + 1 - math.sqrt(max(0.0, msavi_term))) / 2.0
    evi = _safe_ratio(2.5 * (nir - red), nir + 6 * red - 7.5 * blue + 1) if blue is not None else None
    ndmi = _safe_ratio(nir - swir1, nir + swir1) if swir1 is not None else None
    ndwi = _safe_ratio(green - nir, green + nir) if green is not None else None
    nbr = _safe_ratio(nir - swir2, nir + swir2) if swir2 is not None else None
    nbr2 = _safe_ratio(swir1 - swir2, swir1 + swir2) if swir1 is not None and swir2 is not None else None
    return {"ndvi": ndvi, "evi": evi, "savi": savi, "msavi2": msavi2, "ndmi": ndmi, "ndwi_green_nir": ndwi, "nbr": nbr, "nbr2": nbr2}


def summarize_vegetation_pixels(pixels: Sequence[Mapping[str, Optional[float]]]) -> dict:
    """Resume índices já calculados por pixel: médias e fração válida.

    Cada dict deve conter, por exemplo, red/nir e opcionalmente blue/green/swir1/swir2.
    Pixels marcados valid=False são ignorados.
    """
    if not pixels:
        raise ValueError("Informe pelo menos um pixel.")
    valid_pixels = [p for p in pixels if p.get("valid", True)]
    indices = []
    for p in valid_pixels:
        indices.append(vegetation_indices(
            red=float(p["red"]), nir=float(p["nir"]),
            blue=p.get("blue"), green=p.get("green"), swir1=p.get("swir1"), swir2=p.get("swir2")
        ))
    keys = ["ndvi", "evi", "savi", "msavi2", "ndmi", "ndwi_green_nir", "nbr", "nbr2"]
    averages = {}
    medians = {}
    for key in keys:
        values = [row[key] for row in indices if row[key] is not None]
        averages[key] = mean(values) if values else None
        medians[key] = median(values) if values else None
    return {
        "pixel_count": len(pixels),
        "valid_pixel_count": len(valid_pixels),
        "valid_pixel_fraction": len(valid_pixels) / len(pixels),
        "mean_indices": averages,
        "median_indices": medians,
        "note": "Resumo de pixels válidos; máscara QA, recorte do talhão e escala de reflectância devem ser feitos antes.",
    }


def standardized_anomaly(current: float, historical_mean: float, historical_std: float) -> Optional[float]:
    """Z-score = (valor atual - média histórica) / desvio-padrão histórico."""
    std = _non_negative("desvio padrão histórico", historical_std)
    if std == 0:
        return None
    return (_finite("valor atual", current) - _finite("média histórica", historical_mean)) / std


# ---------------------------------------------------------------------------
# 5. Erosão — RUSLE
# ---------------------------------------------------------------------------

def rusle_ls_factor(slope_length_m: float, slope_percent: float, exponent_m: float = 0.5) -> float:
    """Fator topográfico LS simplificado da RUSLE."""
    length = _finite("comprimento da encosta", slope_length_m)
    slope = _non_negative("declividade", slope_percent)
    if length <= 0 or not 0 <= exponent_m <= 1:
        raise ValueError("Comprimento deve ser >0 e expoente m entre 0 e 1.")
    theta = math.atan(slope / 100.0)
    sin_theta = math.sin(theta)
    return (length / 22.13) ** exponent_m * (65.41 * sin_theta**2 + 4.56 * sin_theta + 0.065)


def rusle_soil_loss_t_ha_year(
    rainfall_erosivity_r: float,
    soil_erodibility_k: float,
    slope_length_m: float,
    slope_percent: float,
    cover_factor_c: float,
    support_practice_p: float,
    slope_exponent_m: float = 0.5,
) -> dict[str, float | str]:
    """RUSLE: A = R*K*LS*C*P; exige fatores/unidades compatíveis e calibrados."""
    r = _non_negative("fator R", rainfall_erosivity_r)
    k = _non_negative("fator K", soil_erodibility_k)
    c = _non_negative("fator C", cover_factor_c)
    p = _non_negative("fator P", support_practice_p)
    ls = rusle_ls_factor(slope_length_m, slope_percent, slope_exponent_m)
    loss = r * k * ls * c * p
    return {"soil_loss_t_ha_year": loss, "R": r, "K": k, "LS": ls, "C": c, "P": p,
            "scope": "erosão laminar e em sulcos; não calcula voçorocas, deposição ou erosão eólica"}


# ---------------------------------------------------------------------------
# 6. Método dual de Kc — evaporação do solo e transpiração
# ---------------------------------------------------------------------------

def evaporation_reduction_coefficient_kr(
    depletion_evaporation_mm: float,
    readily_evaporable_water_mm: float,
    total_evaporable_water_mm: float,
) -> float:
    """Kr: reduz evaporação do solo conforme seca a camada superficial."""
    rew = _non_negative("REW", readily_evaporable_water_mm)
    tew = _non_negative("TEW", total_evaporable_water_mm)
    de = _non_negative("depleção evaporativa", depletion_evaporation_mm)
    if tew <= 0 or rew > tew:
        raise ValueError("Exija TEW > 0 e 0 <= REW <= TEW.")
    if de <= rew:
        return 1.0
    if tew == rew:
        return 0.0
    return _clamp((tew - de) / (tew - rew), 0.0, 1.0)


def maximum_crop_coefficient_kcmax(u2_m_s: float, rh_min_pct: float, crop_height_m: float, kcb: float) -> float:
    """Kcmax FAO-56 para método dual, com vento a 2 m, UR mínima e altura."""
    u2 = _non_negative("vento a 2 m", u2_m_s)
    rh = _finite("UR mínima", rh_min_pct)
    height = _finite("altura da cultura", crop_height_m)
    if not 0 <= rh <= 100 or height <= 0 or kcb < 0:
        raise ValueError("UR, altura ou Kcb inválidos.")
    climate_term = 1.2 + (0.04 * (u2 - 2.0) - 0.004 * (rh - 45.0)) * (height / 3.0) ** 0.3
    return max(climate_term, kcb + 0.05)


def soil_evaporation_coefficient_ke(kr: float, kcmax: float, kcb: float, few: float) -> float:
    """Ke = min[Kr(Kcmax-Kcb), few*Kcmax]."""
    if not 0 <= kr <= 1 or not 0 <= few <= 1 or kcmax < kcb or kcb < 0:
        raise ValueError("Parâmetros Kr, few, Kcmax e Kcb inválidos.")
    return max(0.0, min(kr * (kcmax - kcb), few * kcmax))


def dual_kc_evapotranspiration_mm_day(et0_mm_day: float, kcb: float, ks: float, ke: float) -> dict[str, float]:
    """ETc real dual = (Kcb*Ks + Ke)*ET0; separa T e E."""
    et0 = _non_negative("ET0", et0_mm_day)
    if kcb < 0 or ke < 0 or not 0 <= ks <= 1:
        raise ValueError("Kcb/Ke devem ser não negativos e Ks entre 0 e 1.")
    transpiration = kcb * ks * et0
    soil_evaporation = ke * et0
    return {"transpiration_mm_day": transpiration,
            "soil_evaporation_mm_day": soil_evaporation,
            "etc_actual_mm_day": transpiration + soil_evaporation}


# ---------------------------------------------------------------------------
# 7. Resposta da produtividade à água — FAO Ky
# ---------------------------------------------------------------------------

def fao_water_yield_response(eta_actual_mm: float, eta_max_mm: float, ky: float) -> dict[str, float | str]:
    """1 - Ya/Ym = Ky * (1 - ETa/ETm); retorna perda relativa estimada."""
    eta_a = _non_negative("ETa", eta_actual_mm)
    eta_m = _finite("ETm", eta_max_mm)
    ky = _non_negative("Ky", ky)
    if eta_m <= 0:
        raise ValueError("ETm deve ser maior que zero.")
    deficit = max(0.0, 1.0 - min(1.0, eta_a / eta_m))
    loss = _clamp(ky * deficit, 0.0, 1.0)
    return {"water_deficit_fraction": deficit,
            "estimated_relative_yield_loss_fraction": loss,
            "estimated_relative_yield_loss_percent": loss * 100.0,
            "status": "triagem; Ky precisa ser específico da cultura e fase"}


# ---------------------------------------------------------------------------
# 8. Regras fitossanitárias e pontuação preliminar de rotação
# ---------------------------------------------------------------------------

def classify_host_transition(previous_is_host: Optional[bool], next_is_host: Optional[bool]) -> str:
    """Classificação lógica da transição para um organismo fitossanitário.

    Não estima população ou probabilidade de infestação. True/False devem vir
    de fonte agronômica validada para espécie do organismo, cultura e região.
    """
    if previous_is_host is None or next_is_host is None:
        return "unknown_relationship"
    if previous_is_host and next_is_host:
        return "host_continuity"
    if previous_is_host and not next_is_host:
        return "potential_host_break"
    if not previous_is_host and next_is_host:
        return "host_introduction"
    return "no_known_host_in_sequence"


def weighted_rotation_score(
    indicators_0_to_1: Mapping[str, float],
    weights: Mapping[str, float],
    hard_blocked: bool = False,
) -> dict[str, float | str | None]:
    """Modelo experimental: soma ponderada de indicadores normalizados 0–1.

    Use somente quando os indicadores e os pesos tiverem sido definidos e
    validados com agrônomos. Critérios impeditivos (ex.: regra fitossanitária)
    devem ser tratados separadamente via hard_blocked=True, não compensados
    por uma pontuação alta em outro indicador.
    """
    if hard_blocked:
        return {"score_0_to_100": None, "status": "blocked_by_hard_constraint"}
    if not indicators_0_to_1 or set(indicators_0_to_1) != set(weights):
        raise ValueError("Indicadores e pesos devem conter exatamente as mesmas chaves.")
    if any(not 0 <= v <= 1 for v in indicators_0_to_1.values()):
        raise ValueError("Todos os indicadores devem estar normalizados entre 0 e 1.")
    if any(v < 0 for v in weights.values()):
        raise ValueError("Pesos não podem ser negativos.")
    total_weight = sum(weights.values())
    if not math.isclose(total_weight, 1.0, rel_tol=1e-6, abs_tol=1e-6):
        raise ValueError("A soma dos pesos deve ser 1.0.")
    score = sum(indicators_0_to_1[key] * weights[key] for key in weights) * 100.0
    return {"score_0_to_100": score, "status": "experimental_not_field_validated"}


# ---------------------------------------------------------------------------
# 9. Fórmula-resumo: ETc simples e balanço de indicadores
# ---------------------------------------------------------------------------

def crop_evapotranspiration_potential_mm_day(kc: float, et0_mm_day: float) -> float:
    """ETc potencial pelo método Kc simples: ETc = Kc * ET0."""
    if kc < 0:
        raise ValueError("Kc não pode ser negativo.")
    return kc * _non_negative("ET0", et0_mm_day)


if __name__ == "__main__":
    # Exemplo rápido: números fictícios, apenas para demonstrar o uso das funções.
    et0 = fao56_et0_mm_day(
        tmax_c=30.0, tmin_c=20.0, rh_mean_pct=65.0,
        wind_2m_m_s=2.0, solar_radiation_mj_m2_day=18.0,
        latitude_deg=-16.0, elevation_m=800.0, day_of_year=320,
    )
    kc = 1.1
    etc = crop_evapotranspiration_potential_mm_day(kc, et0)
    taw = total_available_water_mm(0.30, 0.15, 0.60)
    raw = readily_available_water_mm(0.5, taw)
    ks = water_stress_coefficient(35.0, taw, raw)
    print({"et0_mm_day": round(et0, 3), "etc_potential_mm_day": round(etc, 3),
           "taw_mm": round(taw, 2), "raw_mm": round(raw, 2), "ks": round(ks, 3)})
