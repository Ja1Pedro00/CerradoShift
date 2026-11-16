from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Geometry(BaseModel):
    """Polígono do talhão em GeoJSON (WGS84)."""

    type: Literal["Polygon", "MultiPolygon"]
    coordinates: list[Any]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-47.930, -15.780],
                        [-47.920, -15.780],
                        [-47.920, -15.790],
                        [-47.930, -15.790],
                        [-47.930, -15.780],
                    ]
                ],
            }
        }
    )


class SoilOverride(BaseModel):
    """Solo medido (análise de laboratório) ou informado pelo agricultor.

    Campos físicos e químicos do laudo têm prioridade sobre estimativas de
    satélite. Tudo que não for informado fica como estimativa e é sinalizado.
    """

    # Físicos
    clay_pct: float | None = Field(None, ge=0, le=100, description="Argila (%)")
    sand_pct: float | None = Field(None, ge=0, le=100, description="Areia (%)")
    silt_pct: float | None = Field(None, ge=0, le=100, description="Silte (%)")
    organic_matter_pct: float | None = Field(None, ge=0, le=100, description="Matéria orgânica (%)")
    field_capacity_m3m3: float | None = Field(
        None, ge=0, le=1, description="Capacidade de campo (m³/m³)"
    )
    wilting_point_m3m3: float | None = Field(
        None, ge=0, le=1, description="Ponto de murcha permanente (m³/m³)"
    )
    bulk_density_g_cm3: float | None = Field(None, ge=0, le=3)
    awc_mm_rootzone: float | None = Field(None, ge=0, description="Água disponível (mm)")
    root_depth_cm: float | None = Field(
        None, ge=10, le=300, description="Profundidade efetiva (cm). Padrão: 100"
    )
    drainage_class: str | None = Field(None, description="Ex.: 'bem drenado', 'mal drenado'")
    hydrologic_group: str | None = Field(None, description="Grupo hidrológico A-D")

    # Químicos (laudo)
    ph_h2o: float | None = Field(None, ge=0, le=14)
    phosphorus_mg_dm3: float | None = Field(None, ge=0)
    potassium_mg_dm3: float | None = Field(None, ge=0)
    nitrogen_mg_dm3: float | None = Field(None, ge=0)
    electrical_conductivity_ds_m: float | None = Field(None, ge=0)


class FieldContextRequest(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "lat": -15.78,
                "lon": -47.93,
                "field_id": "talhao-01",
                "area_ha": 12.5,
                "planting_date": "2026-11-20",
                "target_crop": "corn",
                "current_crop": "soybean",
                "rotation_candidates": ["corn", "cotton", "crotalaria"],
                "irrigation": "rainfed",
                "window_days": 365,
                "forecast_days": 14,
                "soil_override": {
                    "clay_pct": 35,
                    "sand_pct": 50,
                    "silt_pct": 15,
                    "ph_h2o": 5.8,
                    "phosphorus_mg_dm3": 12,
                    "potassium_mg_dm3": 80,
                },
            }
        },
    )

    lat: float | None = Field(None, ge=-90, le=90, description="Latitude (WGS84)")
    lon: float | None = Field(None, ge=-180, le=180, description="Longitude (WGS84)")
    geometry: Geometry | None = Field(None, description="Polígono do talhão (preferido)")
    field_id: str | None = Field(None, max_length=80)
    area_ha: float | None = Field(None, gt=0)
    planting_date: date | None = None
    target_crop: str | None = Field(
        None,
        max_length=80,
        description=(
            "Cultura que o agricultor QUER plantar (o 'select' do app): "
            "soja/milho/algodão. Aceita PT ou EN; é normalizado para soybean/corn/cotton."
        ),
    )
    current_crop: str | None = Field(None, max_length=80)
    rotation_candidates: list[str] = Field(default_factory=list, max_length=20)
    irrigation: Literal["rainfed", "irrigated", "mixed"] | None = None
    window_days: int = Field(365, ge=30, le=1825, description="Janela histórica analisada")
    forecast_days: int = Field(14, ge=3, le=16)
    include_daily_series: bool = Field(False, description="Inclui a série diária do POWER (resposta maior)")
    soil_override: SoilOverride | None = None
    notes: str | None = Field(None, max_length=1000)

    @model_validator(mode="after")
    def _check_location(self) -> "FieldContextRequest":
        if self.geometry is None and (self.lat is None or self.lon is None):
            raise ValueError("informe 'geometry' (polígono) ou o par 'lat'/'lon'")
        return self


class VegetationSeriesRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [-47.930, -15.780],
                            [-47.920, -15.780],
                            [-47.920, -15.790],
                            [-47.930, -15.790],
                            [-47.930, -15.780],
                        ]
                    ],
                },
                "start": "2026-06-01",
                "end": "2026-11-14",
                "max_scenes": 8,
                "include_evi": True,
            }
        }
    )

    geometry: Geometry
    start: date | None = Field(None, description="Padrão: 120 dias antes de 'end'")
    end: date | None = Field(None, description="Padrão: hoje")
    max_scenes: int = Field(8, ge=1, le=20)
    include_evi: bool = True


class RotationOptionsRequest(BaseModel):
    """Espelha o contrato do CerradoShift (0.3.0) e acrescenta o contexto espacial."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "current_crop": "soybean",
                "next_crop": "cotton",
                "days_available": 75,
                "pratylenchus_brachyurus_status": "unknown",
                "objective": "balanced",
                "cotton_years_since_last": 3,
                "lat": -15.78,
                "lon": -47.93,
            }
        }
    )

    current_crop: str
    next_crop: str
    days_available: int = Field(..., ge=0, le=365)
    pratylenchus_brachyurus_status: Literal["present", "absent", "unknown"] = "unknown"
    objective: str = "balanced"
    cotton_years_since_last: int | None = Field(None, ge=0)
    lat: float | None = Field(None, ge=-90, le=90)
    lon: float | None = Field(None, ge=-180, le=180)
    geometry: Geometry | None = None
    include_vegetation_series: bool = False


class SourceStatus(BaseModel):
    name: str
    status: Literal["ok", "error"]
    cached: bool = False
    latency_ms: int = 0
    detail: str | None = None


class FieldContextResponse(BaseModel):
    request_id: str
    generated_at: datetime
    location: dict[str, Any]
    window: dict[str, Any]
    climate: dict[str, Any]
    soil: dict[str, Any]
    water: dict[str, Any]
    vegetation: dict[str, Any]
    indicators: dict[str, Any]
    alerts: list[dict[str, Any]] = []
    alerts_summary: dict[str, int] = {}
    warnings: list[str]
    sources: list[SourceStatus]


class PlanResponse(BaseModel):
    request_id: str
    generated_at: datetime
    context: dict[str, Any]
    plan: dict[str, Any]
