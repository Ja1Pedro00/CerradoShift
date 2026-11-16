from __future__ import annotations

from datetime import date
import math

from .schemas import DailyWeather


def saturation_vapour_pressure_kpa(temp_c: float) -> float:
    """Pressão de vapor de saturação, FAO-56, em kPa."""
    return 0.6108 * math.exp((17.27 * temp_c) / (temp_c + 237.3))


def slope_vapour_pressure_curve_kpa_c(temp_c: float) -> float:
    """Inclinação da curva de pressão de vapor, em kPa/°C."""
    es = saturation_vapour_pressure_kpa(temp_c)
    return 4098.0 * es / ((temp_c + 237.3) ** 2)


def extraterrestrial_radiation_mj_m2_day(latitude_deg: float, day: date) -> float:
    """Radiação extraterrestre diária (Ra), equações de geometria solar FAO-56."""
    if not -90 <= latitude_deg <= 90:
        raise ValueError("Latitude deve estar entre -90 e 90 graus.")
    lat = math.radians(latitude_deg)
    j = day.timetuple().tm_yday
    dr = 1.0 + 0.033 * math.cos(2.0 * math.pi * j / 365.0)
    solar_declination = 0.409 * math.sin(2.0 * math.pi * j / 365.0 - 1.39)
    argument = -math.tan(lat) * math.tan(solar_declination)
    ws = math.acos(max(-1.0, min(1.0, argument)))
    gsc = 0.0820  # constante solar, MJ m-2 min-1
    ra = (24.0 * 60.0 / math.pi) * gsc * dr * (
        ws * math.sin(lat) * math.sin(solar_declination)
        + math.cos(lat) * math.cos(solar_declination) * math.sin(ws)
    )
    return max(0.0, ra)


def daylight_hours(latitude_deg: float, day: date) -> float:
    """Duração astronômica do dia em horas; não mede radiação recebida no dossel."""
    lat = math.radians(latitude_deg)
    j = day.timetuple().tm_yday
    declination = 0.409 * math.sin(2.0 * math.pi * j / 365.0 - 1.39)
    argument = max(-1.0, min(1.0, -math.tan(lat) * math.tan(declination)))
    sunset_hour_angle = math.acos(argument)
    return 24.0 * sunset_hour_angle / math.pi


def wind_10m_to_2m(wind_10m_m_s: float) -> float:
    """Converte vento de 10 m para 2 m no perfil padrão FAO-56."""
    if wind_10m_m_s < 0:
        raise ValueError("Velocidade do vento não pode ser negativa.")
    return wind_10m_m_s * 4.87 / math.log(67.8 * 10.0 - 5.42)


def fao56_reference_et0(
    weather: DailyWeather,
    latitude_deg: float,
    elevation_m: float,
    wind_is_10m: bool = False,
) -> float:
    """Calcula ET0 diária (mm/dia) pelo FAO Penman-Monteith-56.

    Requer Tmax, Tmin, RH média (ou ponto de orvalho), vento, radiação solar
    e altitude. O fluxo de calor no solo G é aproximado por zero no passo diário.

    Quando só há RH média, ea é aproximada por RHmed * es_média. Se houver
    ponto de orvalho, usa-se ea = es(Tdew), normalmente preferível.
    """
    w = weather
    if w.tmax_c < w.tmin_c:
        raise ValueError(f"{w.day}: Tmax menor que Tmin.")
    if not (0 <= w.rh_mean_pct <= 100):
        raise ValueError(f"{w.day}: RH deve estar entre 0 e 100%.")
    if w.solar_radiation_mj_m2_day < 0 or w.precipitation_mm_day < 0:
        raise ValueError(f"{w.day}: radiação e precipitação não podem ser negativas.")
    if elevation_m < -500 or elevation_m > 9000:
        raise ValueError("Altitude fora da faixa plausível em metros.")

    tmean = (w.tmax_c + w.tmin_c) / 2.0
    es_tmax = saturation_vapour_pressure_kpa(w.tmax_c)
    es_tmin = saturation_vapour_pressure_kpa(w.tmin_c)
    es = (es_tmax + es_tmin) / 2.0
    ea = (
        saturation_vapour_pressure_kpa(w.dew_point_c)
        if w.dew_point_c is not None
        else (w.rh_mean_pct / 100.0) * es
    )
    ea = max(0.0, min(ea, es))
    delta = slope_vapour_pressure_curve_kpa_c(tmean)

    # Pressão atmosférica aproximada pela altitude; em operação pode ser
    # substituída pela pressão medida/fornecida pelo provedor meteorológico.
    pressure = 101.3 * (((293.0 - 0.0065 * elevation_m) / 293.0) ** 5.26)
    gamma = 0.000665 * pressure

    u2 = wind_10m_to_2m(w.wind_2m_m_s) if wind_is_10m else w.wind_2m_m_s
    ra = extraterrestrial_radiation_mj_m2_day(latitude_deg, w.day)
    rso = (0.75 + 2e-5 * elevation_m) * ra
    rs = w.solar_radiation_mj_m2_day

    # Balanço de radiação FAO-56. Rs/Rso é limitado a 1 para evitar
    # radiação de onda longa irrealisticamente baixa em dados ruidosos.
    rns = 0.77 * rs
    if rso <= 0:
        rnl = 0.0
    else:
        # Rs/Rso não deve exceder 1. O piso 0.3 representa a condição de céu
        # totalmente encoberto usada na referência FAO-56/ASCE para a correção diária.
        cloudiness = max(0.3, min(rs / rso, 1.0))
        sigma = 4.903e-9  # MJ K-4 m-2 dia-1
        tmax_k = w.tmax_c + 273.16
        tmin_k = w.tmin_c + 273.16
        rnl = sigma * ((tmax_k**4 + tmin_k**4) / 2.0) * (
            0.34 - 0.14 * math.sqrt(ea)
        ) * (1.35 * cloudiness - 0.35)
    rn = rns - rnl
    g = 0.0  # aproximação para intervalo diário

    numerator = (
        0.408 * delta * (rn - g)
        + gamma * (900.0 / (tmean + 273.0)) * u2 * (es - ea)
    )
    denominator = delta + gamma * (1.0 + 0.34 * u2)
    et0 = numerator / denominator
    # ET0 negativa não representa evapotranspiração diária útil para esse modelo.
    return max(0.0, et0)
