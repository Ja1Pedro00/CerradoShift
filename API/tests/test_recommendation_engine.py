from formula_engine.core.recommendation_engine import generate_recommendations


def base_payload():
    return {
        "current_commercial_crop": "soybean",
        "crop_stage": "vegetative",
        "field": {"irrigation_system": "unknown", "budget_level": "unknown"},
        "soil_test": None,
        "pests": [],
        "preferences": {"priorities": ["water_saving", "soil_cover"], "objective": "balanced", "avoided_transition_crops": [], "risk_tolerance": "medium"},
        "rotation": {"current_crop": "soybean", "next_crop": "cotton", "days_available": 60, "pratylenchus_brachyurus_status": "unknown"},
        "model_results": {},
        "evaluation_date": None,
    }


def test_missing_data_does_not_invent_fertilizer_rates():
    result = generate_recommendations(base_payload())
    assert any(r["id"] == "soil_sampling" for r in result["recommendations"])
    assert all("dose" not in r["recommended_action"].lower() or "não" in r["recommended_action"].lower() for r in result["recommendations"])
    assert result["data_gaps"]


def test_water_stress_recommendation_generated():
    payload = base_payload()
    payload["model_results"]["water_balance"] = {
        "latest_ks": 0.55,
        "latest_depletion_mm": 40,
        "latest_raw_mm": 30,
        "water_stress_days": 5,
    }
    result = generate_recommendations(payload)
    assert any(r["id"] == "water_stress_action" for r in result["recommendations"])


def test_low_irrigation_efficiency_recommends_audit_not_automatic_system_swap():
    payload = base_payload()
    payload["field"].update({"irrigation_system": "center_pivot", "irrigation_efficiency": 0.60})
    result = generate_recommendations(payload)
    rec = next(r for r in result["recommendations"] if r["id"] == "irrigation_efficiency_audit")
    assert "Não recomendar troca automática" in rec["safeguards"][1]


def test_low_ph_and_low_phosphorus_create_review_actions_without_rates():
    payload = base_payload()
    payload["soil_test"] = {"ph_status": "low", "nutrient_status": {"P": "low"}, "organic_matter_status": "unknown"}
    result = generate_recommendations(payload)
    ids = {r["id"] for r in result["recommendations"]}
    assert "soil_acidity_review" in ids
    assert "nutrient_p_review" in ids
    assert all("kg/ha" not in r["recommended_action"] for r in result["recommendations"])


def test_confirmed_pratylenchus_prioritizes_crotalaria_options():
    payload = base_payload()
    payload["rotation"]["pratylenchus_brachyurus_status"] = "present"
    result = generate_recommendations(payload)
    rec = next(r for r in result["recommendations"] if r["id"] == "transition_crop_options")
    ids = [c["crop_id"] for c in rec["candidate_options"]]
    assert ids[:2] == ["crotalaria_spectabilis", "crotalaria_ochroleuca"]


def test_confirmed_pest_generates_scouting_action():
    payload = base_payload()
    payload["pests"] = [{"pest_id": "unlisted_pest", "status": "confirmed", "severity": "high"}]
    result = generate_recommendations(payload)
    ids = {r["id"] for r in result["recommendations"]}
    assert "pest_scout_unlisted_pest" in ids
    assert "unmapped_pest_observation" in ids


def test_ndvi_anomaly_does_not_diagnose_pest():
    payload = base_payload()
    payload["model_results"]["vegetation"] = {"ndvi_mean": 0.2, "anomaly_z": -2.5}
    result = generate_recommendations(payload)
    rec = next(r for r in result["recommendations"] if r["id"] == "vegetation_anomaly_scout")
    assert "não identifica sozinho" in rec["safeguards"][0]


def test_erosion_requires_local_tolerance_threshold():
    payload = base_payload()
    payload["model_results"]["erosion"] = {"soil_loss_t_ha_year": 10}
    result = generate_recommendations(payload)
    assert not any(r["id"] == "erosion_control" for r in result["recommendations"])
    assert any("limite de perda tolerável" in gap for gap in result["data_gaps"])


def test_profitability_preference_requests_cost_and_price_inputs():
    payload = base_payload()
    payload["preferences"]["priorities"] = ["profitability"]
    result = generate_recommendations(payload)
    assert any("custos locais" in gap for gap in result["data_gaps"])


def test_low_risk_tolerance_prioritizes_cautious_rotation_order_when_nematode_unknown():
    payload = base_payload()
    payload["preferences"]["risk_tolerance"] = "low"
    payload["rotation"]["pratylenchus_brachyurus_status"] = "unknown"
    result = generate_recommendations(payload)
    rec = next(r for r in result["recommendations"] if r["id"] == "transition_crop_options")
    ids = [c["crop_id"] for c in rec["candidate_options"]]
    assert ids[:2] == ["crotalaria_spectabilis", "crotalaria_ochroleuca"]


def test_water_saving_preference_requests_efficiency_measurement():
    payload = base_payload()
    payload["field"].update({"irrigation_system": "center_pivot", "irrigation_efficiency": None})
    result = generate_recommendations(payload)
    assert any(r["id"] == "measure_irrigation_efficiency" for r in result["recommendations"])


def test_crop_history_is_used_in_host_rotation_interpretation():
    payload = base_payload()
    payload["crop_history"] = [
        {"crop_id": "maize", "season_label": "Safra 2024/25"},
        {"crop_id": "soybean", "season_label": "Safra 2025/26"},
    ]
    payload["pests"] = [{"pest_id": "fall_armyworm", "status": "confirmed", "severity": "moderate"}]
    result = generate_recommendations(payload)
    rec = next(item for item in result["recommendations"] if item["id"] == "pest_host_rotation_check")
    assert any("hospedeira" in sentence for sentence in rec["why_this_was_recommended"])


def test_crop_history_can_include_transition_crop_and_remains_in_host_sequence():
    payload = base_payload()
    payload["crop_history"] = [
        {"crop_id": "maize", "season_label": "Safra 2024/25"},
        {"crop_id": "crotalaria_spectabilis", "season_label": "Entressafra 2025"},
    ]
    payload["pests"] = [{"pest_id": "fall_armyworm", "status": "confirmed", "severity": "moderate"}]
    result = generate_recommendations(payload)
    rec = next(item for item in result["recommendations"] if item["id"] == "pest_host_rotation_check")
    # O modelo deve manter a cobertura na sequência e classificar a relação como não documentada,
    # em vez de supor que a crotalária é hospedeira ou não hospedeira.
    assert any("relação não permite afirmar" in sentence.lower() for sentence in rec["why_this_was_recommended"])
