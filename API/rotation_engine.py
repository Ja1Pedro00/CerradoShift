"""Deterministic water-balance and rotation comparison engine.

Research MVP, not a calibrated yield model. All climate series and crop coefficients
must be supplied by the caller and carry explicit provenance.
"""
from __future__ import annotations

from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, model_validator
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix='/v1/science', tags=['scientific-simulation'])

class WeatherDay(BaseModel):
    date: date
    precipitation_mm: float = Field(ge=0, le=600)
    et0_mm: float = Field(ge=0, le=35)

class WeatherScenario(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    days: list[WeatherDay] = Field(min_length=1, max_length=1500)
    source: str = Field(min_length=3, max_length=300)
    historical: bool = False

    @model_validator(mode='after')
    def validate_days(self):
        dates = [day.date for day in self.days]
        if dates != sorted(set(dates)):
            raise ValueError('Scenario days must be unique and strictly ordered')
        for a, b in zip(dates, dates[1:]):
            if (b-a).days != 1:
                raise ValueError('Daily time series must be consecutive')
        return self

class CropCycle(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    duration_days: int = Field(ge=1, le=400)
    kc_initial: float = Field(ge=0, le=2.5)
    kc_mid: float = Field(ge=0, le=2.5)
    kc_end: float = Field(ge=0, le=2.5)
    # Proxy for the land surface being covered; NOT an estimate of soil carbon.
    ground_cover: bool = False
    parameter_source: str = Field(min_length=3, max_length=300)

class Rotation(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    cycles: list[CropCycle] = Field(min_length=1, max_length=8)

class ComparisonRequest(BaseModel):
    rotations: list[Rotation] = Field(min_length=2, max_length=20)
    scenarios: list[WeatherScenario] = Field(min_length=1, max_length=20)
    soil_capacity_mm: float = Field(gt=0, le=1000)
    initial_soil_water_mm: float = Field(ge=0, le=1000)
    irrigation_mm_per_day: float = Field(default=0, ge=0, le=40)
    assumption_note: str = Field(min_length=3, max_length=500)

    @model_validator(mode='after')
    def check_horizon(self):
        if self.initial_soil_water_mm > self.soil_capacity_mm:
            raise ValueError('Initial soil water exceeds capacity')
        names = [r.name for r in self.rotations]
        if len(names) != len(set(names)):
            raise ValueError('Rotation names must be unique')
        scenario_names = [s.name for s in self.scenarios]
        if len(scenario_names) != len(set(scenario_names)):
            raise ValueError('Scenario names must be unique')
        lengths = [sum(c.duration_days for c in r.cycles) for r in self.rotations]
        if len(set(lengths)) != 1:
            raise ValueError('Compare rotations with equal total duration')
        for s in self.scenarios:
            if len(s.days) != lengths[0]:
                raise ValueError(f'Scenario {s.name} must provide exactly {lengths[0]} daily values')
        return self

def _kc(crop: CropCycle, day: int) -> float:
    """Clearly documented simplified 20/30/30/20 stage fraction Kc model."""
    fraction = (day + 0.5) / crop.duration_days
    if fraction < .2:
        return crop.kc_initial
    if fraction < .5:
        return crop.kc_initial + (crop.kc_mid - crop.kc_initial) * (fraction - .2) / .3
    if fraction < .8:
        return crop.kc_mid
    return crop.kc_mid + (crop.kc_end - crop.kc_mid) * (fraction - .8) / .2

def _simulate(rotation: Rotation, scenario: WeatherScenario, capacity: float, initial: float, irrigation: float) -> dict:
    water = initial
    offset = 0
    deficit = et_demand = actual_et = overflow = 0.0
    water_stress_days = longest_streak = streak = uncovered_days = 0
    chart = []
    for crop in rotation.cycles:
        for i in range(crop.duration_days):
            day = scenario.days[offset]
            demand = day.et0_mm * _kc(crop, i)
            supply = water + day.precipitation_mm + irrigation
            real_et = min(demand, supply)
            water = max(0, supply - real_et)
            drained = max(0, water - capacity)
            water = min(capacity, water)
            shortfall = demand - real_et
            deficit += shortfall
            actual_et += real_et
            et_demand += demand
            overflow += drained
            is_stressed = demand > 0.01 and real_et / demand < .7
            streak = streak + 1 if is_stressed else 0
            water_stress_days += int(is_stressed)
            longest_streak = max(longest_streak, streak)
            uncovered_days += int(not crop.ground_cover)
            chart.append({'date': day.date.isoformat(), 'crop': crop.name,
                          'water_mm': round(water, 3), 'et_demand_mm': round(demand, 3),
                          'actual_et_mm': round(real_et, 3), 'deficit_mm': round(shortfall, 3)})
            offset += 1
    return {'scenario': scenario.name, 'source': scenario.source, 'historical': scenario.historical,
            'deficit_mm': round(deficit, 3), 'crop_water_demand_mm': round(et_demand, 3),
            'actual_evapotranspiration_mm': round(actual_et, 3), 'drainage_excess_mm': round(overflow, 3),
            'stress_days': water_stress_days, 'longest_stress_streak_days': longest_streak,
            'uncovered_days_proxy': uncovered_days, 'final_soil_water_mm': round(water, 3),
            'daily': chart}

def compare(data: ComparisonRequest) -> dict:
    output = []
    for rotation in data.rotations:
        per_scenario = [_simulate(rotation, s, data.soil_capacity_mm, data.initial_soil_water_mm,
                                  data.irrigation_mm_per_day) for s in data.scenarios]
        output.append({'rotation': rotation.name,
                       'avg_deficit_mm': round(sum(x['deficit_mm'] for x in per_scenario)/len(per_scenario), 3),
                       'worst_deficit_mm': max(x['deficit_mm'] for x in per_scenario),
                       'avg_stress_days': round(sum(x['stress_days'] for x in per_scenario)/len(per_scenario), 2),
                       'uncovered_days_proxy': per_scenario[0]['uncovered_days_proxy'],
                       'scenarios': per_scenario})
    # Non-dominated in two comparable MINIMIZED criteria, no invented weighted score.
    for a in output:
        a['pareto_efficient'] = not any(
            (b['avg_deficit_mm'] <= a['avg_deficit_mm'] and
             b['uncovered_days_proxy'] <= a['uncovered_days_proxy'] and
             (b['avg_deficit_mm'] < a['avg_deficit_mm'] or
              b['uncovered_days_proxy'] < a['uncovered_days_proxy']))
            for b in output if b is not a)
    return {'model': 'daily_bucket_v1', 'status': 'scenario_comparison_not_yield_prediction',
            'assumptions': ['ETc = Kc x ET0', 'No runoff, groundwater, upward flux, rooting-depth changes or water-stress feedback on Kc',
                            'Excess soil water is treated as drainage', 'Ground-cover days are a proxy, not measured soil quality',
                            'Uncalibrated Kc stage proportions 20/30/30/20', data.assumption_note],
            'objectives_minimized': ['avg_deficit_mm', 'uncovered_days_proxy'],
            'results': output}

@router.post('/compare-rotations')
def compare_rotations(payload: ComparisonRequest):
    return compare(payload)
