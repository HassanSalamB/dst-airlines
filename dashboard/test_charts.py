from charts import ChartFactory, _aircraft_polygon


def test_aircraft_silhouette_rotates_toward_heading():
    north_facing = _aircraft_polygon(24.7, 46.7, 0)
    east_facing = _aircraft_polygon(24.7, 46.7, 90)

    assert north_facing[0][0] > 24.7
    assert east_facing[0][1] > 46.7


def test_live_map_uses_plane_shapes_and_directional_tracks():
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
        "trail": [
            {"latitude": 24.75, "longitude": 46.55, "time": 100},
            {"latitude": 24.75, "longitude": 46.70, "time": 130},
        ],
    }]

    figure = ChartFactory().live_aircraft_map(rows, "Saudi Arabia", "RUH")

    assert figure.data[0].name == "Observed trail"
    assert figure.data[1].name == "10-min heading guide"
    assert any(trace.fill == "toself" for trace in figure.data)
    assert not any(getattr(trace.marker, "symbol", None) == "arrow-up" for trace in figure.data)
