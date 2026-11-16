from datetime import date
import math
import pytest

from formula_engine.core.math_formulas import (
    actual_vapour_pressure_kpa,
    adjusted_depletion_fraction,
    atmospheric_pressure_kpa,
    classify_host_transition,
    count_water_stress_days,
    crop_evapotranspiration_potential_mm_day,
    crop_stage_and_kc,
    daily_gdd_c_day,
    daily_heat_excess_c,
    daylight_hours,
    dual_kc_evapotranspiration_mm_day,
    effective_rainfall_mm,
    evaporation_reduction_coefficient_kr,
    extraterrestrial_radiation_mj_m2_day,
    fao56_et0_mm_day,
    fao_water_yield_response,
    irrigation_recommendation_mm,
    irrigation_volume_m3,
    maximum_crop_coefficient_kcmax,
    net_irrigation_mm,
    readily_available_water_mm,
    root_depth_linear_m,
    rusle_ls_factor,
    rusle_soil_loss_t_ha_year,
    saturation_vapour_pressure_kpa,
    scs_curve_number_runoff_mm,
    standardized_anomaly,
    total_available_water_mm,
    vegetation_indices,
    water_stress_coefficient,
    weighted_rotation_score,
    daily_water_balance_step,
)


def test_fao_climate_helpers():
    assert saturation_vapour_pressure_kpa(20) == pytest.approx(2.338, abs=0.01)
    assert actual_vapour_pressure_kpa(2.0, rh_mean_pct=50) == pytest.approx(1.0)
    assert atmospheric_pressure_kpa(0) == pytest.approx(101.3, abs=0.2)
    assert 0 < daylight_hours(-16, 355) < 24
    assert extraterrestrial_radiation_mj_m2_day(-16, 320) > 0


def test_fao56_et0_positive_for_typical_day():
    et0 = fao56_et0_mm_day(
        tmax_c=30, tmin_c=20, rh_mean_pct=65,
        wind_2m_m_s=2, solar_radiation_mj_m2_day=18,
        latitude_deg=-16, elevation_m=800, day_of_year=320,
    )
    assert 0 < et0 < 15


def test_crop_stage_kc_and_root_growth():
    out = crop_stage_and_kc(40, 20, 40, 60, 30, 0.3, 1.2, 0.6)
    assert out["stage"] == "development"
    assert out["kc"] == pytest.approx(0.75)
    assert root_depth_linear_m(50, 0.1, 1.0, 100) == pytest.approx(0.55)
    assert adjusted_depletion_fraction(0.5, 6) == pytest.approx(0.46)


def test_gdd_heat_and_etc():
    assert daily_gdd_c_day(30, 18, 10) == pytest.approx(14)
    assert daily_gdd_c_day(8, 5, 10) == 0
    assert daily_heat_excess_c(38, 35) == 3
    assert crop_evapotranspiration_potential_mm_day(1.2, 5) == 6


def test_water_storage_and_stress():
    taw = total_available_water_mm(0.30, 0.15, 0.60)
    assert taw == pytest.approx(90)
    raw = readily_available_water_mm(0.5, taw)
    assert raw == pytest.approx(45)
    assert water_stress_coefficient(40, taw, raw) == 1
    assert water_stress_coefficient(67.5, taw, raw) == pytest.approx(0.5)


def test_scs_rain_and_irrigation():
    assert 0 <= scs_curve_number_runoff_mm(40, 75) <= 40
    assert effective_rainfall_mm(40, 8) == 32
    assert net_irrigation_mm(20, 0.8) == 16
    assert irrigation_volume_m3(20, 5) == 1000
    assert irrigation_recommendation_mm(60, 40, 0.8)["gross_mm"] > 0
    assert count_water_stress_days([1.0, 0.95, 0.8, 0.7]) == 2


def test_daily_water_balance_conserves_simple_storage():
    result = daily_water_balance_step(
        depletion_start_mm=30, taw_mm=90, raw_mm=45,
        etc_potential_mm=5, precipitation_mm=0,
        irrigation_gross_mm=0, irrigation_efficiency=1,
    )
    assert result["ks"] == 1
    assert result["eta_actual_mm"] == 5
    assert result["storage_end_mm"] == 55
    assert result["depletion_end_mm"] == 35


def test_vegetation_indices():
    result = vegetation_indices(red=0.1, nir=0.6, blue=0.05, green=0.2, swir1=0.3, swir2=0.25)
    assert result["ndvi"] == pytest.approx(0.7142857)
    assert result["evi"] is not None
    assert result["ndmi"] == pytest.approx(0.3333333)
    assert standardized_anomaly(0.3, 0.6, 0.1) == pytest.approx(-3)
    assert standardized_anomaly(0.3, 0.6, 0) is None


def test_rusle():
    ls = rusle_ls_factor(50, 5)
    assert ls > 0
    result = rusle_soil_loss_t_ha_year(500, 0.03, 50, 5, 0.2, 0.5)
    assert result["soil_loss_t_ha_year"] > 0


def test_dual_kc():
    kr = evaporation_reduction_coefficient_kr(20, 10, 30)
    assert kr == pytest.approx(0.5)
    kcmax = maximum_crop_coefficient_kcmax(2, 45, 1.0, 1.0)
    assert kcmax >= 1.05
    result = dual_kc_evapotranspiration_mm_day(5, 1.0, 0.8, 0.2)
    assert result["transpiration_mm_day"] == pytest.approx(4)
    assert result["soil_evaporation_mm_day"] == pytest.approx(1)
    assert result["etc_actual_mm_day"] == pytest.approx(5)


def test_yield_host_and_rotation_score():
    result = fao_water_yield_response(300, 400, 1.2)
    assert result["estimated_relative_yield_loss_percent"] == pytest.approx(30)
    assert classify_host_transition(True, False) == "potential_host_break"
    score = weighted_rotation_score({"water": 0.8, "soil": 0.6}, {"water": 0.5, "soil": 0.5})
    assert score["score_0_to_100"] == pytest.approx(70)
    assert weighted_rotation_score({"water": 1.0}, {"water": 1.0}, hard_blocked=True)["score_0_to_100"] is None
