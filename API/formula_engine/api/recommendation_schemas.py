from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


CropId = Literal["soybean", "maize", "cotton"]
CropHistoryId = Literal[
    "soybean", "maize", "cotton", "millet", "urochloa_ruziziensis",
    "crotalaria_spectabilis", "crotalaria_ochroleuca",
]
PestStatus = Literal["confirmed", "suspected", "not_detected", "unknown"]
Priority = Literal[
    "water_saving",
    "soil_cover",
    "nutrient_cycling",
    "pest_break",
    "profitability",
    "soil_recovery",
]


class PestObservationInput(BaseModel):
    pest_id: str = Field(min_length=2, max_length=100)
    status: PestStatus = "unknown"
    severity: Literal["low", "moderate", "high", "unknown"] = "unknown"
    observed_date: date | None = None
    notes: str | None = Field(default=None, max_length=1000)


class SoilTestInput(BaseModel):
    sample_date: date | None = None
    laboratory: str | None = Field(default=None, max_length=200)
    ph_value: float | None = Field(default=None, ge=0, le=14)
    ph_method: str | None = Field(default=None, max_length=50)
    # Usar a interpretação do laboratório/localidade; o motor não converte
    # valores brutos de P, K ou pH em dose universal de fertilizante/corretivo.
    ph_status: Literal["low", "adequate", "high", "unknown"] = "unknown"
    nutrient_status: dict[str, Literal["low", "adequate", "high", "unknown"]] = Field(default_factory=dict)
    organic_matter_status: Literal["low", "adequate", "high", "unknown"] = "unknown"
    texture_class: str | None = Field(default=None, max_length=80)
    compaction_status: Literal["suspected", "confirmed", "not_detected", "unknown"] = "unknown"


class FieldContextInput(BaseModel):
    area_ha: float | None = Field(default=None, gt=0)
    slope_percent: float | None = Field(default=None, ge=0, le=300)
    irrigation_system: Literal["rainfed", "center_pivot", "sprinkler", "drip", "furrow", "other", "unknown"] = "unknown"
    irrigation_efficiency: float | None = Field(default=None, gt=0, le=1)
    water_limited: bool = False
    available_machinery: list[str] = Field(default_factory=list)
    budget_level: Literal["low", "medium", "high", "unknown"] = "unknown"
    cotton_years_since_last: int | None = Field(default=None, ge=0, le=30)


class FarmerPreferencesInput(BaseModel):
    priorities: list[Priority] = Field(default_factory=lambda: ["water_saving", "soil_cover", "pest_break"])
    objective: Literal["balanced", "ground_cover", "nitrogen_cycling", "nematode_management"] = "balanced"
    avoided_transition_crops: list[str] = Field(default_factory=list)
    risk_tolerance: Literal["low", "medium", "high"] = "medium"
    notes: str | None = Field(default=None, max_length=1500)


class CropHistoryEntryInput(BaseModel):
    """Uma safra ou cultura de transição concluída, da mais antiga à mais recente."""
    crop_id: CropHistoryId
    season_label: str | None = Field(default=None, max_length=80)
    planting_date: date | None = None
    harvest_date: date | None = None
    notes: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.planting_date and self.harvest_date and self.harvest_date < self.planting_date:
            raise ValueError("A data de colheita não pode ser anterior à data de plantio.")
        return self


class RotationContextInput(BaseModel):
    current_crop: CropId | None = None
    next_crop: CropId | None = None
    days_available: int | None = Field(default=None, ge=0, le=365)
    pratylenchus_brachyurus_status: Literal["present", "not_detected", "unknown"] = "unknown"

    @model_validator(mode="after")
    def paired_crop_validation(self):
        if (self.current_crop is None) != (self.next_crop is None):
            raise ValueError("Informe current_crop e next_crop juntos, ou deixe ambos vazios.")
        if self.current_crop is not None and self.days_available is None:
            raise ValueError("Informe days_available quando informar as culturas comerciais.")
        return self


class RecommendationRequest(BaseModel):
    current_commercial_crop: CropId | None = None
    crop_stage: str | None = Field(default=None, max_length=80)
    field: FieldContextInput = Field(default_factory=FieldContextInput)
    soil_test: SoilTestInput | None = None
    pests: list[PestObservationInput] = Field(default_factory=list)
    # Safras concluídas, da mais antiga para a mais recente; usadas para contextualizar a rotação.
    crop_history: list[CropHistoryEntryInput] = Field(default_factory=list, max_length=6)
    preferences: FarmerPreferencesInput = Field(default_factory=FarmerPreferencesInput)
    rotation: RotationContextInput = Field(default_factory=RotationContextInput)
    # Respostas de outros endpoints: water_balance, vegetation, erosion,
    # phenology_thermal, yield_water_response, etc.
    model_results: dict[str, Any] = Field(default_factory=dict)
    evaluation_date: date | None = None

    @model_validator(mode="after")
    def crop_consistency(self):
        if self.current_commercial_crop and self.rotation.current_crop:
            if self.current_commercial_crop != self.rotation.current_crop:
                raise ValueError("current_commercial_crop deve coincidir com rotation.current_crop.")
        return self
