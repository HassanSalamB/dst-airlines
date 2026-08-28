from charts import ChartFactory, _aircraft_polygon


def test_aircraft_silhouette_rotates_toward_heading():
    north_facing = _aircraft_polygon(24.7, 46.7, 0)
    east_facing = _aircraft_polygon(24.7, 46.7, 90)

    assert north_facing[0][0] > 24.7
    assert east_facing[0][1] > 46.7


def test_live_map_uses_large_plane_shapes_and_matched_routes():
    rows = [{
        "icao24": "abc123",
        "callsign": "TEST1",
        "latitude": 24.75,
        "longitude": 46.70,
        "altitude_ft": 18000,
        "speed_kmh": 720,
        "heading": 90,
        "nearest_airport": "RUH",
        "distance_to_airport_km": 15,
        "origin": "CAI · Cairo",
        "origin_latitude": 30.1219,
        "origin_longitude": 31.4056,
        "destination": "DXB · Dubai",
        "destination_latitude": 25.2528,
        "destination_longitude": 55.3644,
    }]

    figure = ChartFactory().live_aircraft_map(rows, "Saudi Arabia", "RUH")

    assert figure.data[0].name == "Matched origin–destination route"
    assert any(trace.fill == "toself" for trace in figure.data)
    assert not any(getattr(trace.marker, "symbol", None) == "arrow-up" for trace in figure.data)


def test_live_map_omits_dotted_route_without_both_airport_coordinates():
    rows = [{
        "icao24": "abc123", "callsign": "TEST1",
        "latitude": 24.75, "longitude": 46.70,
        "altitude_ft": 18000, "speed_kmh": 720, "heading": 90,
        "nearest_airport": "RUH", "distance_to_airport_km": 15,
        "origin_latitude": None, "origin_longitude": None,
        "destination_latitude": None, "destination_longitude": None,
    }]

    figure = ChartFactory().live_aircraft_map(rows, "Saudi Arabia", "RUH")

    assert all(trace.line.dash != "dot" for trace in figure.data)


def test_ml_evaluation_charts_render_model_metadata():
    charts = ChartFactory()
    metrics = {
        "Calibrated CatBoost": {
            "roc_auc": 0.628, "pr_auc": 0.585, "brier": 0.235, "recall": 0.368,
        },
        "Logistic Regression": {
            "roc_auc": 0.618, "pr_auc": 0.588, "brier": 0.238, "recall": 0.549,
        },
    }
    features = [
        {"feature": "PrecipitationMm", "importance": 33.7},
        {"feature": "Operating_Airline", "importance": 20.7},
    ]
    calibration = [
        {"predicted": 0.25, "observed": 0.30},
        {"predicted": 0.65, "observed": 0.70},
    ]

    comparison = charts.ml_metric_comparison(metrics)
    importance = charts.ml_feature_importance(features)
    calibrated = charts.ml_calibration(calibration)

    assert len(comparison.data) == 2
    assert len(importance.data) == 1
    assert len(calibrated.data) == 2
