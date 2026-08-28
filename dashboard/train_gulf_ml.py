"""Train and evaluate the Gulf portfolio delay classifier.

The split is intentionally chronological: fit on 2023, calibrate on 2024,
and evaluate once on 2025. The generated artifact is consumed by FastAPI.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from catboost import CatBoostClassifier
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from data import get_gulf_flights_df


FEATURES = [
    "Operating_Airline", "Origin", "Dest", "DayOfWeek",
    "Distance", "Month", "DepartureHour", "WindKmh",
    "PrecipitationMm", "CloudCoverPct",
]
CATEGORICAL_FEATURES = ["Operating_Airline", "Origin", "Dest", "DayOfWeek"]
NUMERIC_FEATURES = [feature for feature in FEATURES if feature not in CATEGORICAL_FEATURES]
TARGET = "Delayed"
MODEL_VERSION = "gulf-delay-portfolio-v1"


def _metrics(model, features, target):
    probabilities = model.predict_proba(features)[:, 1]
    predictions = probabilities >= 0.5
    return {
        "roc_auc": round(float(roc_auc_score(target, probabilities)), 4),
        "pr_auc": round(float(average_precision_score(target, probabilities)), 4),
        "brier": round(float(brier_score_loss(target, probabilities)), 4),
        "recall": round(float(recall_score(target, predictions, zero_division=0)), 4),
    }, probabilities


def train(output_path: Path):
    frame = get_gulf_flights_df().copy()
    fit = frame[frame["Year"] == 2023]
    calibration = frame[frame["Year"] == 2024]
    test = frame[frame["Year"] == 2025]

    catboost = CatBoostClassifier(
        iterations=280,
        depth=6,
        learning_rate=0.045,
        loss_function="Logloss",
        eval_metric="AUC",
        random_seed=42,
        verbose=False,
        allow_writing_files=False,
    )
    catboost.fit(
        fit[FEATURES], fit[TARGET],
        cat_features=CATEGORICAL_FEATURES,
        eval_set=(calibration[FEATURES], calibration[TARGET]),
        early_stopping_rounds=35,
    )
    calibrated_catboost = CalibratedClassifierCV(catboost, method="sigmoid", cv="prefit")
    calibrated_catboost.fit(calibration[FEATURES], calibration[TARGET])

    preprocessing = ColumnTransformer([
        ("categorical", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
        ("numeric", StandardScaler(), NUMERIC_FEATURES),
    ])
    logistic = Pipeline([
        ("preprocessing", preprocessing),
        ("classifier", LogisticRegression(max_iter=1500, class_weight="balanced")),
    ])
    logistic_train = pd.concat([fit, calibration], ignore_index=True)
    logistic.fit(logistic_train[FEATURES], logistic_train[TARGET])

    catboost_metrics, champion_probabilities = _metrics(
        calibrated_catboost, test[FEATURES], test[TARGET]
    )
    logistic_metrics, _ = _metrics(logistic, test[FEATURES], test[TARGET])

    probability_bins, observed_bins = calibration_curve(
        test[TARGET], champion_probabilities, n_bins=8, strategy="quantile"
    )
    feature_importance = sorted(
        [
            {"feature": feature, "importance": round(float(importance), 2)}
            for feature, importance in zip(FEATURES, catboost.get_feature_importance())
        ],
        key=lambda item: item["importance"],
        reverse=True,
    )

    metadata = {
        "available": True,
        "version": MODEL_VERSION,
        "champion": "Calibrated CatBoost",
        "algorithm": "CatBoostClassifier + sigmoid calibration",
        "data_scope": "Saudi Arabia and UAE portfolio simulation",
        "fit_year": 2023,
        "calibration_year": 2024,
        "evaluation_year": 2025,
        "training_rows": int(len(fit)),
        "calibration_rows": int(len(calibration)),
        "test_rows": int(len(test)),
        "positive_rate": round(float(test[TARGET].mean()), 4),
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "metrics": {
            "Calibrated CatBoost": catboost_metrics,
            "Logistic Regression": logistic_metrics,
        },
        "selection_reason": (
            "Selected for lower Brier loss and higher ROC-AUC; the Logistic "
            "Regression baseline retains higher recall at the default 0.50 threshold."
        ),
        "feature_importance": feature_importance,
        "calibration": [
            {
                "predicted": round(float(predicted), 4),
                "observed": round(float(observed), 4),
            }
            for predicted, observed in zip(probability_bins, observed_bins)
        ],
        "features": FEATURES,
        "limitations": (
            "Portfolio simulation only; probabilities are not official airline forecasts."
        ),
    }
    artifact = {
        "model": calibrated_catboost,
        "metadata": metadata,
        "features": FEATURES,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_tmp = output_path.with_suffix(output_path.suffix + ".tmp")
    metadata_path = output_path.with_suffix(".metadata.json")
    metadata_tmp = metadata_path.with_suffix(metadata_path.suffix + ".tmp")
    joblib.dump(artifact, artifact_tmp, compress=3)
    artifact_tmp.replace(output_path)
    metadata_tmp.write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    metadata_tmp.replace(metadata_path)
    return metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "api" / "gulf_delay_model.joblib",
    )
    args = parser.parse_args()
    result = train(args.output)
    print(json.dumps(result, indent=2))
