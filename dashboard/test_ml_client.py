from unittest.mock import Mock, patch

import pandas as pd
import requests

from ml_client import get_ml_status, predict_gulf_delay


def test_get_ml_status_uses_local_metadata_when_api_is_offline():
    with patch("ml_client.requests.get", side_effect=requests.ConnectionError("offline")):
        status = get_ml_status("http://127.0.0.1:8000")

    assert status["available"] is True
    assert status["api_available"] is False
    assert status["inference_available"] is False
    assert status["version"] == "gulf-delay-portfolio-v1"
    assert "reliability_score" in status


def test_get_ml_status_uses_api_when_available():
    response = Mock()
    response.json.return_value = {"available": True, "version": "api-version"}
    response.raise_for_status.return_value = None

    with patch("ml_client.requests.get", return_value=response):
        status = get_ml_status("https://api.example.test")

    assert status["api_available"] is True
    assert status["inference_available"] is True
    assert status["serving_mode"] == "fastapi"
    assert status["version"] == "api-version"


def test_predict_gulf_delay_falls_back_to_historical_baseline_when_api_is_offline():
    frame = pd.DataFrame(
        [
            {
                "Origin": "RUH",
                "Dest": "DXB",
                "Operating_Airline": "Riyadh Air",
                "DayOfWeek": "Monday",
                "Delayed": 1,
            },
            {
                "Origin": "RUH",
                "Dest": "DXB",
                "Operating_Airline": "Riyadh Air",
                "DayOfWeek": "Monday",
                "Delayed": 0,
            },
        ]
    )
    payload = {
        "origin": "RUH",
        "destination": "DXB",
        "airline": "Riyadh Air",
        "flight_date": "2026-09-07",
        "departure_hour": 18,
        "wind_kmh": 20,
        "precipitation_mm": 0,
        "cloud_cover_pct": 20,
    }

    with patch("ml_client.requests.post", side_effect=requests.ConnectionError("offline")):
        prediction = predict_gulf_delay("http://127.0.0.1:8000", payload, frame)

    assert 0 <= prediction["delay_probability"] <= 1
    assert prediction["risk_band"] in {"LOW", "MEDIUM", "HIGH"}
    assert prediction["model_version"] == "portfolio-baseline"
    assert "not the trained CatBoost model" in prediction["limitations"]
