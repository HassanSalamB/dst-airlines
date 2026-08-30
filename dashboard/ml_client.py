"""Dashboard-side access to Gulf delay model metadata and predictions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests


MODEL_METADATA_PATHS = [
    Path(__file__).resolve().parents[1] / "api" / "gulf_delay_model.metadata.json",
    Path(__file__).resolve().parent / "assets" / "gulf_delay_model.metadata.json",
]


def gulf_model_reliability(metadata: dict[str, Any]) -> dict[str, Any]:
    champion = metadata.get("champion", "")
    metrics = metadata.get("metrics", {}).get(champion, {})
    roc_auc = float(metrics.get("roc_auc", 0))
    pr_auc = float(metrics.get("pr_auc", 0))
    brier = float(metrics.get("brier", 1))
    calibration_points = metadata.get("calibration", [])
    calibration_gap = (
        np.mean(
            [
                abs(float(point["predicted"]) - float(point["observed"]))
                for point in calibration_points
                if "predicted" in point and "observed" in point
            ]
        )
        if calibration_points
        else 1
    )
    score = round(
        100
        * (
            0.40 * roc_auc
            + 0.20 * pr_auc
            + 0.20 * max(0, 1 - min(brier, 1))
            + 0.20 * max(0, 1 - min(float(calibration_gap), 1))
        )
    )
    if score >= 80:
        label = "strong portfolio signal"
    elif score >= 65:
        label = "moderate portfolio signal"
    else:
        label = "experimental portfolio signal"
    return {
        "reliability_score": int(score),
        "reliability_label": label,
        "calibration_gap": round(float(calibration_gap), 4),
        "reliability_note": (
            "Score combines ROC-AUC, PR-AUC, Brier probability error and "
            "calibration gap on the 2025 simulation test set."
        ),
    }


def _local_metadata() -> dict[str, Any] | None:
    metadata = None
    for metadata_path in MODEL_METADATA_PATHS:
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            break
        except (OSError, json.JSONDecodeError):
            continue
    if metadata is None:
        return None

    metadata.update(gulf_model_reliability(metadata))
    metadata.update(
        {
            "available": True,
            "api_available": False,
            "inference_available": False,
            "serving_mode": "metadata-fallback",
            "serving_note": (
                "Model metadata loaded from the repository. The FastAPI inference "
                "service is not reachable from this dashboard instance."
            ),
        }
    )
    return metadata


def get_ml_status(api_base_url: str) -> dict[str, Any]:
    try:
        response = requests.get(f"{api_base_url}/model/gulf/status", timeout=5)
        response.raise_for_status()
        status = response.json()
        status.update(
            {
                "api_available": True,
                "inference_available": bool(status.get("available")),
                "serving_mode": "fastapi",
                "serving_note": "FastAPI inference service is reachable.",
            }
        )
        return status
    except requests.RequestException as exc:
        metadata = _local_metadata()
        if metadata is not None:
            metadata["reason"] = f"FastAPI inference is offline: {exc}"
            return metadata
        return {"available": False, "reason": f"Prediction API unavailable: {exc}"}


def _clamp_probability(value: float) -> float:
    return max(0.05, min(0.85, float(value)))


def _mean_or_none(frame: pd.DataFrame, column: str = "Delayed") -> float | None:
    if frame.empty or column not in frame.columns:
        return None
    return float(frame[column].mean())


def _historical_baseline_prediction(payload: dict[str, Any], frame: pd.DataFrame, reason: str) -> dict[str, Any]:
    origin = str(payload["origin"])
    destination = str(payload["destination"])
    airline = str(payload["airline"])
    flight_date = pd.Timestamp(payload["flight_date"])

    route = frame[(frame["Origin"] == origin) & (frame["Dest"] == destination)]
    airline_rows = frame[frame["Operating_Airline"] == airline]
    origin_rows = frame[frame["Origin"] == origin]
    day_rows = frame[frame["DayOfWeek"] == flight_date.strftime("%A")]

    overall_rate = _mean_or_none(frame) or 0.35
    components = [
        (0.40, _mean_or_none(route)),
        (0.25, _mean_or_none(airline_rows)),
        (0.15, _mean_or_none(origin_rows)),
        (0.10, _mean_or_none(day_rows)),
        (0.10, overall_rate),
    ]
    weighted = [(weight, value) for weight, value in components if value is not None]
    probability = sum(weight * value for weight, value in weighted) / sum(weight for weight, _ in weighted)

    hour = int(payload.get("departure_hour", 12))
    wind = float(payload.get("wind_kmh", 0))
    precipitation = float(payload.get("precipitation_mm", 0))
    cloud = float(payload.get("cloud_cover_pct", 0))
    weather_adjustment = min(0.18, precipitation * 0.035 + max(0, wind - 28) * 0.004 + max(0, cloud - 70) * 0.0015)
    peak_adjustment = 0.04 if hour in {6, 7, 8, 17, 18, 19, 20} else 0
    probability = _clamp_probability(probability + weather_adjustment + peak_adjustment)
    risk_band = "LOW" if probability < 0.30 else "MEDIUM" if probability < 0.60 else "HIGH"

    return {
        "delay_probability": probability,
        "risk_band": risk_band,
        "model_version": "portfolio-baseline",
        "algorithm": "Historical portfolio baseline",
        "data_scope": "Saudi Arabia and UAE portfolio simulation",
        "limitations": (
            "FastAPI model inference is offline, so this is a transparent "
            "historical baseline, not the trained CatBoost model output."
        ),
        "fallback_reason": reason,
    }


def predict_gulf_delay(api_base_url: str, payload: dict[str, Any], frame: pd.DataFrame) -> dict[str, Any]:
    try:
        response = requests.post(f"{api_base_url}/predict/gulf", json=payload, timeout=12)
        response.raise_for_status()
        prediction = response.json()
        prediction["serving_mode"] = "fastapi"
        return prediction
    except requests.RequestException as exc:
        return _historical_baseline_prediction(payload, frame, str(exc))
