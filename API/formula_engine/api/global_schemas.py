from __future__ import annotations
from datetime import date
from typing import Optional
from pydantic import BaseModel, Field, model_validator


class ReflectancePixelInput(BaseModel):
    red: float = Field(ge=0, le=1.5)
    nir: float = Field(ge=0, le=1.5)
    blue: Optional[float] = Field(default=None, ge=0, le=1.5)
    green: Optional[float] = Field(default=None, ge=0, le=1.5)
    swir1: Optional[float] = Field(default=None, ge=0, le=1.5)
    swir2: Optional[float] = Field(default=None, ge=0, le=1.5)
    valid: bool = True


class VegetationIndexRequest(BaseModel):
    sensor_product: str = "HLS_or_other_surface_reflectance"
    reflectance_scale: str = "surface_reflectance_0_to_1"
    savi_l: float = Field(default=0.5, ge=0, le=1)
    pixels: list[ReflectancePixelInput] = Field(min_length=1, max_length=100000)


class VegetationAnomalyRequest(BaseModel):
    index_name: str = Field(default="ndvi", min_length=2, max_length=20)
    current_value: float = Field(ge=-1.5, le=1.5)
    historical_mean: float = Field(ge=-1.5, le=1.5)
    historical_std: float = Field(ge=0)
    baseline_period: str = Field(description="Período de referência, idealmente mesma janela fenológica/época do ano")


class ErosionRequest(BaseModel):
    rainfall_erosivity_r: float = Field(ge=0, description="Fator R no sistema de unidades RUSLE da fonte escolhida")
    soil_erodibility_k: float = Field(ge=0, description="Fator K compatível com a unidade de R")
    slope_length_m: float = Field(gt=0)
    slope_percent: float = Field(ge=0, le=300)
    cover_factor_c: float = Field(ge=0, le=1)
    support_practice_p: float = Field(ge=0, le=1)
    slope_exponent_m: float = Field(default=0.5, ge=0, le=1)


class RotationAssessmentRequest(BaseModel):
    crop_sequence: list[str] = Field(min_length=2, max_length=20)
    detected_pests: list[str] = Field(default_factory=list, max_length=100)


class ThermalDayInput(BaseModel):
    day: date
    tmax_c: float
    tmin_c: float


class ThermalAssessmentRequest(BaseModel):
    weather: list[ThermalDayInput] = Field(min_length=1, max_length=5000)
    base_temperature_c: float
    upper_temperature_c: Optional[float] = None
    heat_threshold_c: Optional[float] = None

    @model_validator(mode="after")
    def validate_temperature_limits(self):
        if self.upper_temperature_c is not None and self.upper_temperature_c <= self.base_temperature_c:
            raise ValueError("upper_temperature_c deve ser maior que base_temperature_c")
        return self

class DualKcRequest(BaseModel):
    et0_mm_day: float = Field(ge=0)
    kcb: float = Field(ge=0)
    ks: float = Field(ge=0, le=1)
    kr: float = Field(ge=0, le=1)
    kcmax: float = Field(ge=0)
    few: float = Field(ge=0, le=1)


class WaterYieldResponseRequest(BaseModel):
    eta_actual_mm: float = Field(ge=0)
    eta_max_mm: float = Field(gt=0)
    ky: float = Field(ge=0)


class CerradoMvpRotationRequest(BaseModel):
    current_crop: str = Field(description="soybean, maize ou cotton")
    next_crop: str = Field(description="soybean, maize ou cotton")
    days_available: int = Field(ge=0, le=365, description="Dias previstos para estabelecer a cultura de transição")
    pratylenchus_brachyurus_status: str = Field(default="unknown", description="present, not_detected ou unknown")
    objective: str = Field(default="balanced", description="balanced, ground_cover, nitrogen_cycling ou nematode_management")
    cotton_years_since_last: Optional[int] = Field(default=None, ge=0, le=20)
