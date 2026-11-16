from fastapi.testclient import TestClient
from formula_engine.main import app
from formula_engine.core.remote_sensing import ReflectancePixel, compute_indices
from formula_engine.core.erosion import rusle_soil_loss_t_ha_year
from formula_engine.core.pest_rotation import assess_rotation_sequence
from formula_engine.core.dual_kc import dual_crop_coefficient_et

client = TestClient(app)


def test_ndvi_formula():
    result = compute_indices(ReflectancePixel(red=0.2, nir=0.6, blue=0.1, green=0.3, swir1=0.25, swir2=0.2))
    assert round(result["ndvi"], 4) == 0.5
    assert result["evi"] is not None
    assert result["ndmi"] is not None


def test_ndvi_masks_invalid_pixel():
    result = compute_indices(ReflectancePixel(red=0.2, nir=0.6, valid=False))
    assert result["ndvi"] is None


def test_rusle_positive():
    result = rusle_soil_loss_t_ha_year(1000, 0.03, 50, 5, 0.2, 0.5)
    assert result["estimated_sheet_rill_soil_loss_t_ha_year"] > 0
    assert result["factors"]["LS"] > 0


def test_fall_armyworm_continuity_maize_sorghum():
    result = assess_rotation_sequence(["maize", "sorghum"], ["fall_armyworm"])
    assert result["transitions"][0]["pests"][0]["status"] == "host_to_host"


def test_scn_potential_break_soybean_corn():
    result = assess_rotation_sequence(["soybean", "maize"], ["soybean_cyst_nematode"])
    assert result["transitions"][0]["pests"][0]["status"] == "potential_host_break"


def test_dual_kc_component():
    result = dual_crop_coefficient_et(5.0, 0.9, 0.8, 0.5, 1.2, 0.4)
    assert result["etc_actual_mm_day"] > 0
    assert result["ke"] >= 0


def test_cerrado_mvp_routes_and_sources():
    catalog = client.get("/api/v1/cerrado-mvp/catalog")
    assert catalog.status_code == 200
    assert set(catalog.json()["commercial_crops"]) == {"soybean", "maize", "cotton"}
    assert client.get("/api/v1/data-sources").status_code == 200


def test_vegetation_indices_endpoint():
    response = client.post("/api/v1/assessments/vegetation-indices", json={
        "pixels": [{"red": 0.2, "nir": 0.6, "blue": 0.1, "green": 0.3, "swir1": 0.25, "swir2": 0.2}]
    })
    assert response.status_code == 200, response.text
    assert response.json()["mean_indices"]["ndvi"] == 0.5


def test_thermal_endpoint():
    response = client.post("/api/v1/assessments/phenology-thermal", json={
        "weather": [{"day": "2026-01-01", "tmax_c": 30, "tmin_c": 20}],
        "base_temperature_c": 10,
        "upper_temperature_c": 30,
        "heat_threshold_c": 35
    })
    assert response.status_code == 200, response.text
    assert response.json()["total_gdd_c_day"] == 15


def test_vegetation_anomaly_endpoint():
    response = client.post("/api/v1/assessments/vegetation-anomaly", json={
        "index_name": "ndvi",
        "current_value": 0.30,
        "historical_mean": 0.60,
        "historical_std": 0.10,
        "baseline_period": "same seasonal window, previous 5 years"
    })
    assert response.status_code == 200, response.text
    assert response.json()["z_score"] == -3.0


def test_cerrado_mvp_catalog_only_has_three_commercial_crops():
    catalog = client.get("/api/v1/cerrado-mvp/catalog")
    assert catalog.status_code == 200
    data = catalog.json()
    assert set(data["commercial_crops"]) == {"soybean", "maize", "cotton"}
    assert "millet" in data["transition_crops"]
    assert "urochloa_ruziziensis" in data["transition_crops"]
    assert "crotalaria_spectabilis" in data["transition_crops"]


def test_cerrado_transition_flags_millet_and_urochloa_when_p_brachyurus_present():
    response = client.post("/api/v1/assessments/cerrado-transition-options", json={
        "current_crop": "soybean",
        "next_crop": "cotton",
        "days_available": 80,
        "pratylenchus_brachyurus_status": "present",
        "objective": "nematode_management",
        "cotton_years_since_last": 3,
    })
    assert response.status_code == 200, response.text
    data = response.json()
    by_id = {item["crop_id"]: item for item in data["candidates"]}
    assert by_id["millet"]["suitability"] == "avoid_as_default_when_P_brachyurus_confirmed"
    assert by_id["urochloa_ruziziensis"]["suitability"] == "avoid_as_default_when_P_brachyurus_confirmed"
    assert by_id["crotalaria_spectabilis"]["suitability"] == "priority_candidate_with_technical_validation"
    assert data["candidates"][0]["crop_id"] == "crotalaria_spectabilis"


def test_cerrado_transition_warns_on_short_cotton_return_interval():
    response = client.post("/api/v1/assessments/cerrado-transition-options", json={
        "current_crop": "maize",
        "next_crop": "cotton",
        "days_available": 0,
        "pratylenchus_brachyurus_status": "unknown",
        "objective": "balanced",
        "cotton_years_since_last": 1,
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["cotton_return_warning"] is not None
    assert all(item["suitability"] == "not_applicable_no_sowing_window" for item in data["candidates"])


def test_cerrado_transition_rejects_non_mvp_crop():
    response = client.post("/api/v1/assessments/cerrado-transition-options", json={
        "current_crop": "soybean",
        "next_crop": "sorghum",
        "days_available": 60,
    })
    assert response.status_code == 422
