from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class DailyWeather:
    """Clima diário já convertido para unidades SI esperadas pelo motor."""
    day: date
    tmax_c: float
    tmin_c: float
    rh_mean_pct: float
    wind_2m_m_s: float
    solar_radiation_mj_m2_day: float
    precipitation_mm_day: float
    dew_point_c: Optional[float] = None
    # Opcional: se houver uma estimativa independente validada de escoamento.
    runoff_mm_day: Optional[float] = None


@dataclass(frozen=True)
class IrrigationEvent:
    """Lâmina bruta aplicada na data (antes da eficiência do sistema)."""
    day: date
    gross_depth_mm: float


@dataclass(frozen=True)
class SoilProfile:
    """Parâmetros hidráulicos da zona radicular.

    field_capacity e wilting_point são conteúdos volumétricos (m³/m³).
    initial_available_fraction é a fração da água disponível ainda presente
    no início da simulação: 1 = capacidade de campo; 0 = ponto de murcha.
    """
    field_capacity: float
    wilting_point: float
    initial_available_fraction: float = 0.50
    initial_theta_m3_m3: Optional[float] = None
    initial_moisture_is_assumed: bool = True
    irrigation_efficiency: float = 0.85
    irrigation_efficiency_is_assumed: bool = True
    curve_number: Optional[float] = None
    # Fração do novo volume de solo explorado que se supõe disponível quando
    # a raiz cresce. É uma hipótese inicial, substituível por perfil medido.
    new_root_zone_available_fraction: float = 0.50
    effective_soil_depth_m: Optional[float] = None

    def validate(self) -> None:
        if not (0.0 <= self.wilting_point < self.field_capacity <= 1.0):
            raise ValueError("Exija 0 <= ponto de murcha < capacidade de campo <= 1.")
        if not (0.0 <= self.initial_available_fraction <= 1.0):
            raise ValueError("initial_available_fraction deve estar entre 0 e 1.")
        if self.initial_theta_m3_m3 is not None and not (self.wilting_point <= self.initial_theta_m3_m3 <= self.field_capacity):
            raise ValueError("A umidade inicial medida deve estar entre ponto de murcha e capacidade de campo.")
        if not (0.0 < self.irrigation_efficiency <= 1.0):
            raise ValueError("irrigation_efficiency deve estar em (0, 1].")
        if not (0.0 <= self.new_root_zone_available_fraction <= 1.0):
            raise ValueError("new_root_zone_available_fraction deve estar entre 0 e 1.")
        if self.curve_number is not None and not (30.0 <= self.curve_number <= 98.0):
            raise ValueError("curve_number deve estar entre 30 e 98.")
        if self.effective_soil_depth_m is not None and self.effective_soil_depth_m <= 0:
            raise ValueError("effective_soil_depth_m deve ser positivo.")


@dataclass(frozen=True)
class CropParameters:
    """Parâmetros agronômicos versionáveis por cultura/cultivar.

    Os Kc e durações devem vir de bibliografia/validação regional. Não são
    inferidos do nome da cultura, pois variam com cultivar, clima e manejo.
    """
    crop_id: str
    cultivar: str
    kc_initial: float
    kc_mid: float
    kc_end: float
    stage_initial_days: int
    stage_development_days: int
    stage_mid_days: int
    stage_late_days: int
    depletion_fraction_p: float
    root_depth_initial_m: float
    root_depth_max_m: float
    root_growth_days: int
    base_temperature_c: Optional[float] = None
    upper_temperature_c: Optional[float] = None
    heat_threshold_c: Optional[float] = None
    heat_thresholds_by_stage: dict[str, float] = field(default_factory=dict)
    parameter_source: str = "PREENCHER: referência agronômica e cultivar"
    parameter_version: str = "0.1"

    def validate(self) -> None:
        if min(self.kc_initial, self.kc_mid, self.kc_end) < 0:
            raise ValueError("Os coeficientes Kc não podem ser negativos.")
        if min(self.stage_initial_days, self.stage_development_days,
               self.stage_mid_days, self.stage_late_days) < 0:
            raise ValueError("Duração dos estágios não pode ser negativa.")
        if self.stage_initial_days + self.stage_development_days + self.stage_mid_days + self.stage_late_days <= 0:
            raise ValueError("A duração total do ciclo deve ser positiva.")
        if not (0.05 <= self.depletion_fraction_p <= 0.95):
            raise ValueError("p deve estar entre 0.05 e 0.95.")
        if self.root_depth_initial_m <= 0 or self.root_depth_max_m < self.root_depth_initial_m:
            raise ValueError("Profundidades radiculares inválidas.")
        if self.root_growth_days <= 0:
            raise ValueError("root_growth_days deve ser positivo.")


@dataclass(frozen=True)
class FarmerContext:
    """Informações operacionais fornecidas pelo produtor.

    sun_exposure_hours é apenas contexto de sombreamento; não multiplica ET0.
    irrigation_frequency_days é informação de rotina, não substitui a lâmina
    aplicada em cada evento.
    """
    field_area_ha: float
    planting_date: date
    emergence_date: Optional[date] = None
    irrigation_frequency_days: Optional[int] = None
    irrigation_method: Optional[str] = None
    sun_exposure_hours_day: Optional[float] = None
    shade_percent: Optional[float] = None
    mulch_cover_percent: Optional[float] = None
    canopy_cover_percent: Optional[float] = None
    current_stage_reported: Optional[str] = None
    soil_moisture_observation_fraction: Optional[float] = None

    def validate(self) -> None:
        if self.field_area_ha <= 0:
            raise ValueError("field_area_ha deve ser positivo.")
        if self.irrigation_frequency_days is not None and self.irrigation_frequency_days <= 0:
            raise ValueError("irrigation_frequency_days deve ser positivo.")
        if self.sun_exposure_hours_day is not None and not (0 <= self.sun_exposure_hours_day <= 24):
            raise ValueError("sun_exposure_hours_day deve estar entre 0 e 24.")
        for name in ("shade_percent", "mulch_cover_percent", "canopy_cover_percent"):
            value = getattr(self, name)
            if value is not None and not (0 <= value <= 100):
                raise ValueError(f"{name} deve estar entre 0 e 100.")
        if self.soil_moisture_observation_fraction is not None and not (
            0 <= self.soil_moisture_observation_fraction <= 1
        ):
            raise ValueError("soil_moisture_observation_fraction deve estar entre 0 e 1.")
