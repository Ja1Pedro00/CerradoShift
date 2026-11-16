from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class WeatherInput(BaseModel):
    day: date
    tmax_c: float
    tmin_c: float
    rh_mean_pct: float = Field(ge=0, le=100)
    wind_2m_m_s: float = Field(ge=0)
    solar_radiation_mj_m2_day: float = Field(ge=0)
    precipitation_mm_day: float = Field(ge=0)
    dew_point_c: Optional[float] = None
    runoff_mm_day: Optional[float] = Field(default=None, ge=0)


class SoilInput(BaseModel):
    field_capacity_m3_m3: float = Field(gt=0, le=1)
    wilting_point_m3_m3: float = Field(ge=0, lt=1)
    # Preferir theta medida por sensor representativo da zona radicular.
    initial_theta_m3_m3: Optional[float] = None
    # Se não houver sensor, o usuário pode informar/aceitar fração estimada.
    initial_available_fraction: float = Field(default=0.50, ge=0, le=1)
    initial_moisture_is_assumed: bool = True
    irrigation_efficiency: float = Field(default=0.85, gt=0, le=1)
    irrigation_efficiency_is_assumed: bool = True
    curve_number: Optional[float] = Field(default=None, ge=30, le=98)
    new_root_zone_available_fraction: float = Field(default=0.50, ge=0, le=1)
    effective_soil_depth_m: Optional[float] = Field(default=None, gt=0)

    @model_validator(mode="after")
    def check_soil_range(self):
        if self.wilting_point_m3_m3 >= self.field_capacity_m3_m3:
            raise ValueError("Ponto de murcha deve ser menor que capacidade de campo.")
        if self.initial_theta_m3_m3 is not None and not (
            self.wilting_point_m3_m3 <= self.initial_theta_m3_m3 <= self.field_capacity_m3_m3
        ):
            raise ValueError("Umidade inicial deve ficar entre ponto de murcha e capacidade de campo.")
        return self


class CropInput(BaseModel):
    crop_id: str
    cultivar: str
    # Curva Kc single-coefficient. Valores devem vir da ficha agronômica validada.
    kc_initial: float = Field(ge=0)
    kc_mid: float = Field(ge=0)
    kc_end: float = Field(ge=0)
    stage_initial_days: int = Field(ge=0)
    stage_development_days: int = Field(ge=0)
    stage_mid_days: int = Field(ge=0)
    stage_late_days: int = Field(ge=0)
    depletion_fraction_p: float = Field(gt=0.05, lt=0.95)
    root_depth_initial_m: float = Field(gt=0)
    root_depth_max_m: float = Field(gt=0)
    root_growth_days: int = Field(gt=0)
    base_temperature_c: Optional[float] = None
    upper_temperature_c: Optional[float] = None
    heat_threshold_c: Optional[float] = None
    heat_thresholds_by_stage: dict[str, float] = Field(default_factory=dict)
    parameter_source: str = "PREENCHER: referência agronômica e cultivar"
    parameter_version: str = "0.1"

    @model_validator(mode="after")
    def check_crop(self):
        if self.stage_initial_days + self.stage_development_days + self.stage_mid_days + self.stage_late_days <= 0:
            raise ValueError("A soma das durações fenológicas deve ser positiva.")
        if self.root_depth_max_m < self.root_depth_initial_m:
            raise ValueError("Profundidade radicular máxima não pode ser menor que a inicial.")
        return self


class IrrigationEventInput(BaseModel):
    day: date
    gross_depth_mm: Optional[float] = Field(default=None, ge=0)
    # volume_m3 deve ser o volume total destinado a toda a área (não por emissor).
    volume_m3: Optional[float] = Field(default=None, gt=0)
    # Alternativa: duração + vazão total do setor/talhão, em m³/h.
    duration_minutes: Optional[float] = Field(default=None, gt=0)
    flow_rate_m3_h: Optional[float] = Field(default=None, gt=0)

    @model_validator(mode="after")
    def exactly_one_measurement_form(self):
        direct = self.gross_depth_mm is not None
        volume = self.volume_m3 is not None
        timed = self.duration_minutes is not None or self.flow_rate_m3_h is not None
        if direct and (volume or timed):
            raise ValueError("Informe lâmina, volume ou duração+vazão; não misture formatos.")
        if volume and timed:
            raise ValueError("Informe volume diretamente ou duração+vazão, não ambos.")
        if timed and (self.duration_minutes is None or self.flow_rate_m3_h is None):
            raise ValueError("Para calcular volume, informe duração e vazão total do talhão.")
        if not (direct or volume or timed):
            raise ValueError("Cada evento precisa de lâmina, volume ou duração+vazão.")
        return self


class FarmerInput(BaseModel):
    field_area_ha: float = Field(gt=0)
    planting_date: date
    emergence_date: Optional[date] = None
    irrigation_frequency_days: Optional[int] = Field(default=None, gt=0)
    irrigation_method: Optional[str] = None
    # Horas relatadas pelo produtor; são diagnóstico de sombra, não fator de ET0.
    sun_exposure_hours_day: Optional[float] = Field(default=None, ge=0, le=24)
    shade_percent: Optional[float] = Field(default=None, ge=0, le=100)
    mulch_cover_percent: Optional[float] = Field(default=None, ge=0, le=100)
    canopy_cover_percent: Optional[float] = Field(default=None, ge=0, le=100)
    current_stage_reported: Optional[str] = None


class AssessmentRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    elevation_m: float = Field(ge=-500, le=9000)
    start_date: date
    end_date: date
    fetch_power: bool = True
    weather_source_label: Optional[str] = None
    weather: Optional[list[WeatherInput]] = None
    crop: CropInput
    soil: SoilInput
    farmer: FarmerInput
    irrigation_events: list[IrrigationEventInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_dates_and_weather(self):
        if self.farmer.emergence_date is not None and self.farmer.emergence_date < self.farmer.planting_date:
            raise ValueError("emergence_date não pode anteceder planting_date.")
        if self.start_date > self.end_date:
            raise ValueError("start_date deve ser anterior ou igual a end_date.")
        if self.start_date < self.farmer.planting_date:
            raise ValueError("start_date não pode anteceder planting_date.")
        if not self.fetch_power and not self.weather:
            raise ValueError("Informe weather ou habilite fetch_power.")
        return self
