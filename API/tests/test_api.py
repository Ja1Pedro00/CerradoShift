from fastapi.testclient import TestClient
from formula_engine.main import app

client = TestClient(app)


def test_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_assessment_with_supplied_weather():
    payload = {
        "latitude": -18.9,
        "longitude": -48.3,
        "elevation_m": 850,
        "start_date": "2026-01-01",
        "end_date": "2026-01-03",
        "fetch_power": False,
        "weather": [
            {
                "day": f"2026-01-0{i}",
                "tmax_c": 31,
                "tmin_c": 19,
                "rh_mean_pct": 60,
                "wind_2m_m_s": 2,
                "solar_radiation_mj_m2_day": 20,
                "precipitation_mm_day": 4 if i == 2 else 0
            }
            for i in range(1, 4)
        ],
        "crop": {
            "crop_id": "soybean_demo",
            "cultivar": "demo",
            "kc_initial": 0.4,
            "kc_mid": 1.15,
            "kc_end": 0.5,
            "stage_initial_days": 20,
            "stage_development_days": 30,
            "stage_mid_days": 50,
            "stage_late_days": 30,
            "depletion_fraction_p": 0.5,
            "root_depth_initial_m": 0.2,
            "root_depth_max_m": 0.8,
            "root_growth_days": 60,
            "base_temperature_c": 10,
            "heat_threshold_c": 35,
            "parameter_source": "fixture de teste; não usar em produção"
        },
        "soil": {
            "field_capacity_m3_m3": 0.3,
            "wilting_point_m3_m3": 0.15,
            "initial_available_fraction": 0.5,
            "initial_moisture_is_assumed": True,
            "irrigation_efficiency": 0.85
        },
        "farmer": {
            "field_area_ha": 5,
            "planting_date": "2026-01-01",
            "irrigation_frequency_days": 3,
            "irrigation_method": "aspersao",
            "sun_exposure_hours_day": 8,
            "shade_percent": 5,
            "mulch_cover_percent": 20,
            "canopy_cover_percent": 30,
            "current_stage_reported": "initial"
        },
        "irrigation_events": [
            {"day": "2026-01-02", "gross_depth_mm": 12}
        ]
    }
    response = client.post("/api/v1/assessments/field", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["context"]["crop_id"] == "soybean_demo"
    assert len(body["daily"]) == 3
    assert "irrigation_recommendation" in body


def test_crop_catalog():
    response = client.get("/api/v1/crop-catalog")
    assert response.status_code == 200
    catalog = response.json()
    assert catalog["soybean"]["profile_status"] == "reference_values_only"
    assert catalog["brachiaria"]["profile_status"] == "local_profile_required"


def test_recommendations_endpoint_returns_explanations():
    payload = {
        "current_commercial_crop": "soybean",
        "field": {"irrigation_system": "center_pivot", "irrigation_efficiency": 0.62, "budget_level": "medium"},
        "soil_test": None,
        "pests": [{"pest_id": "pratylenchus_brachyurus", "status": "confirmed", "severity": "moderate"}],
        "preferences": {"priorities": ["water_saving", "soil_cover"], "objective": "balanced", "avoided_transition_crops": [], "risk_tolerance": "low"},
        "rotation": {"current_crop": "soybean", "next_crop": "cotton", "days_available": 75, "pratylenchus_brachyurus_status": "unknown"},
        "model_results": {
            "water_balance": {"latest_ks": 0.65, "latest_depletion_mm": 42, "latest_raw_mm": 35, "water_stress_days": 4},
            "vegetation": {"z_score": -2.2, "mean_indices": {"ndvi": 0.4}},
        },
    }
    response = client.post("/api/v1/assessments/recommendations", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["engine_version"] == "0.1.0"
    ids = {item["id"] for item in body["recommendations"]}
    assert "water_stress_action" in ids
    assert "irrigation_efficiency_audit" in ids
    assert "transition_crop_options" in ids
    transition = next(item for item in body["recommendations"] if item["id"] == "transition_crop_options")
    assert transition["candidate_options"][0]["crop_id"] == "crotalaria_spectabilis"
