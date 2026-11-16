import pytest
from pydantic import ValidationError

from formula_engine.api.recommendation_schemas import RecommendationRequest


def test_recommendation_request_accepts_crop_history():
    request = RecommendationRequest.model_validate({
        "current_commercial_crop": "soybean",
        "crop_history": [
            {"crop_id": "maize", "season_label": "Safra 2024/25", "planting_date": "2024-10-20", "harvest_date": "2025-03-10"},
            {"crop_id": "crotalaria_spectabilis", "season_label": "Cobertura 2025"},
            {"crop_id": "soybean", "season_label": "Safra 2025/26"},
        ],
        "rotation": {"current_crop": "soybean", "next_crop": "cotton", "days_available": 60},
    })
    assert len(request.crop_history) == 3
    assert request.crop_history[0].crop_id == "maize"
    assert request.crop_history[1].crop_id == "crotalaria_spectabilis"


def test_crop_history_rejects_harvest_before_planting():
    with pytest.raises(ValidationError):
        RecommendationRequest.model_validate({
            "crop_history": [
                {"crop_id": "soybean", "planting_date": "2025-03-10", "harvest_date": "2025-02-10"}
            ]
        })


def test_crop_history_accepts_transition_crops():
    request = RecommendationRequest.model_validate({
        "crop_history": [
            {"crop_id": "crotalaria_spectabilis", "season_label": "Entressafra 2025"},
            {"crop_id": "millet", "season_label": "Cobertura 2025/26"},
        ]
    })
    assert [entry.crop_id for entry in request.crop_history] == [
        "crotalaria_spectabilis", "millet"
    ]
