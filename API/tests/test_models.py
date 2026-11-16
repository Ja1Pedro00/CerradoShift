from datetime import date, timedelta

import pytest

from formula_engine.core.evapotranspiration import fao56_reference_et0, wind_10m_to_2m
from formula_engine.core.schemas import DailyWeather, SoilProfile, CropParameters, FarmerContext, IrrigationEvent
from formula_engine.core.water_balance import (
    total_available_water_mm, water_stress_coefficient,
    scs_curve_number_runoff, simulate_water_balance,
)


def sample_weather(day: date, rain: float = 0.0) -> DailyWeather:
    return DailyWeather(
        day=day,
        tmax_c=31.0,
        tmin_c=19.0,
        rh_mean_pct=60.0,
        wind_2m_m_s=2.0,
        solar_radiation_mj_m2_day=20.0,
        precipitation_mm_day=rain,
    )


def sample_crop() -> CropParameters:
    return CropParameters(
        crop_id="soybean_demo",
        cultivar="demo-not-for-recommendation",
        kc_initial=0.4,
        kc_mid=1.15,
        kc_end=0.5,
        stage_initial_days=20,
        stage_development_days=30,
        stage_mid_days=50,
        stage_late_days=30,
        depletion_fraction_p=0.5,
        root_depth_initial_m=0.2,
        root_depth_max_m=0.8,
        root_growth_days=60,
        base_temperature_c=10.0,
        heat_threshold_c=35.0,
        parameter_source="Teste sintético; não utilizar em campo",
    )


def test_taw_and_ks():
    taw = total_available_water_mm(0.30, 0.15, 0.8)
    assert taw == pytest.approx(120.0)
    assert water_stress_coefficient(50, 120, 60) == 1.0
    assert water_stress_coefficient(90, 120, 60) == pytest.approx(0.5)


def test_et0_is_nonnegative_and_plausible():
    et0 = fao56_reference_et0(sample_weather(date(2026, 1, 15)), -18.9, 850)
    assert 0 < et0 < 12


def test_wind_conversion():
    assert wind_10m_to_2m(2.0) == pytest.approx(1.496, rel=0.02)


def test_curve_number_runoff():
    assert scs_curve_number_runoff(1.0, 75.0) == 0.0
    assert 0 < scs_curve_number_runoff(50.0, 75.0) < 50.0


def test_irrigation_increases_storage_relative_to_no_irrigation():
    start = date(2026, 1, 1)
    weather = [sample_weather(start + timedelta(days=i), rain=0.0) for i in range(5)]
    soil = SoilProfile(0.30, 0.15, initial_available_fraction=0.9,
                       initial_moisture_is_assumed=False, irrigation_efficiency=0.9)
    farmer = FarmerContext(field_area_ha=5, planting_date=start)

    without = simulate_water_balance(weather, -18.9, 850, sample_crop(), soil, farmer)
    with_irrigation = simulate_water_balance(
        weather, -18.9, 850, sample_crop(), soil, farmer,
        [IrrigationEvent(start + timedelta(days=2), 25.0)],
    )
    assert with_irrigation.daily[-1].storage_end_mm > without.daily[-1].storage_end_mm


def test_rainfall_reduces_depletion_when_storage_not_full():
    start = date(2026, 1, 1)
    weather = [sample_weather(start, rain=30.0)]
    soil = SoilProfile(0.30, 0.15, initial_available_fraction=0.4,
                       initial_moisture_is_assumed=False, irrigation_efficiency=0.9)
    farmer = FarmerContext(field_area_ha=2, planting_date=start)
    result = simulate_water_balance(weather, -18.9, 850, sample_crop(), soil, farmer)
    assert result.daily[0].effective_rain_mm == pytest.approx(30.0)
    assert result.daily[0].storage_end_mm > 0


def test_invalid_soil_is_rejected():
    with pytest.raises(ValueError):
        SoilProfile(0.15, 0.30).validate()


def test_mass_balance_closes_for_fixed_root_depth():
    start = date(2026, 1, 1)
    weather = [sample_weather(start, rain=20.0)]
    crop = CropParameters(
        crop_id="test", cultivar="test", kc_initial=0.5, kc_mid=0.5, kc_end=0.5,
        stage_initial_days=10, stage_development_days=0, stage_mid_days=0, stage_late_days=0,
        depletion_fraction_p=0.5, root_depth_initial_m=0.5, root_depth_max_m=0.5,
        root_growth_days=10, parameter_source="test"
    )
    soil = SoilProfile(0.30, 0.15, initial_available_fraction=0.5,
                       initial_moisture_is_assumed=False, irrigation_efficiency=0.8)
    farmer = FarmerContext(field_area_ha=1, planting_date=start)
    result = simulate_water_balance(weather, -18.9, 850, crop, soil, farmer)
    row = result.daily[0]
    start_storage = row.taw_mm - row.depletion_start_mm
    expected_end = min(row.taw_mm, start_storage + row.effective_rain_mm) - row.eta_actual_mm
    expected_end = max(0.0, expected_end)
    assert row.storage_end_mm == pytest.approx(expected_end, abs=0.01)


def test_missing_weather_day_is_rejected():
    start = date(2026, 1, 1)
    weather = [sample_weather(start), sample_weather(start + timedelta(days=2))]
    soil = SoilProfile(0.30, 0.15, initial_available_fraction=0.5)
    farmer = FarmerContext(field_area_ha=1, planting_date=start)
    with pytest.raises(ValueError, match="incompleta"):
        simulate_water_balance(weather, -18.9, 850, sample_crop(), soil, farmer)
