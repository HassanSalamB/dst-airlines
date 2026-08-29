"""
test_api.py — Unit Tests for DST Airlines FastAPI Endpoints
Tests the Gulf portfolio API endpoints.

Run with:
    pytest test_api.py -v
    
Or with Docker:
    docker exec airlines_api pytest test_api.py -v
"""

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


# ═══════════════════════════════════════════════════════════════════════════
# Health Check
# ═══════════════════════════════════════════════════════════════════════════

class TestHealthCheck:
    """Test the health check endpoint."""

    def test_health_returns_200(self):
        response = client.get("/")
        assert response.status_code == 200

    def test_health_returns_ok_status(self):
        response = client.get("/")
        data = response.json()
        assert data["status"] == "ok"

    def test_health_returns_version(self):
        response = client.get("/")
        data = response.json()
        assert "version" in data

    def test_health_lists_databases(self):
        response = client.get("/")
        data = response.json()
        assert "databases" in data
        assert "postgresql" in data["databases"]
        assert "mongodb" in data["databases"]
        assert "neo4j" in data["databases"]


# ═══════════════════════════════════════════════════════════════════════════
# NEW: Dashboard Endpoints Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestDashboardFlights:
    """Test GET /api/flights endpoint."""

    def test_flights_returns_200(self):
        response = client.get("/api/flights?limit=5")
        assert response.status_code == 200

    def test_flights_returns_list(self):
        response = client.get("/api/flights?limit=5")
        data = response.json()
        assert isinstance(data, list)

    def test_flights_respects_limit(self):
        response = client.get("/api/flights?limit=5")
        data = response.json()
        assert len(data) <= 5

    def test_flights_has_required_columns(self):
        response = client.get("/api/flights?limit=1")
        data = response.json()
        if len(data) > 0:
            flight = data[0]
            required = ["flight_id", "flightdate", "airline", "origin", "dest", "distance"]
            for col in required:
                assert col in flight, f"Missing column: {col}"

    def test_flights_filter_by_airline(self):
        response = client.get("/api/flights?airline=SV&limit=5")
        data = response.json()
        if len(data) > 0:
            for flight in data:
                assert flight["airline"] == "SV"

    def test_flights_filter_by_origin(self):
        response = client.get("/api/flights?origin=RUH&limit=5")
        data = response.json()
        if len(data) > 0:
            for flight in data:
                assert flight["origin"] == "RUH"

    def test_flights_filter_by_dest(self):
        response = client.get("/api/flights?dest=DXB&limit=5")
        data = response.json()
        if len(data) > 0:
            for flight in data:
                assert flight["dest"] == "DXB"

    def test_flights_max_limit(self):
        response = client.get("/api/flights?limit=200001")
        assert response.status_code == 422  # Validation error — limit > 200000


class TestDashboardAirlines:
    """Test GET /api/airlines endpoint."""

    def test_airlines_returns_200(self):
        response = client.get("/api/airlines")
        assert response.status_code == 200

    def test_airlines_returns_list(self):
        response = client.get("/api/airlines")
        data = response.json()
        assert isinstance(data, list)

    def test_airlines_not_empty(self):
        response = client.get("/api/airlines")
        data = response.json()
        assert len(data) > 0

    def test_airlines_are_strings(self):
        response = client.get("/api/airlines")
        data = response.json()
        for airline in data:
            assert isinstance(airline, str)

    def test_airlines_are_sorted(self):
        response = client.get("/api/airlines")
        data = response.json()
        assert data == sorted(data)


class TestDashboardOrigins:
    """Test GET /api/origins endpoint."""

    def test_origins_returns_200(self):
        response = client.get("/api/origins")
        assert response.status_code == 200

    def test_origins_returns_list(self):
        response = client.get("/api/origins")
        data = response.json()
        assert isinstance(data, list)

    def test_origins_not_empty(self):
        response = client.get("/api/origins")
        data = response.json()
        assert len(data) > 0

    def test_origins_filter_by_airline(self):
        response = client.get("/api/origins?airline=AA")
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_origins_are_iata_codes(self):
        response = client.get("/api/origins")
        data = response.json()
        for origin in data:
            assert isinstance(origin, str)
            assert len(origin) == 3  # IATA codes are 3 characters


class TestDashboardDestinations:
    """Test GET /api/destinations endpoint."""

    def test_destinations_returns_200(self):
        response = client.get("/api/destinations")
        assert response.status_code == 200

    def test_destinations_returns_list(self):
        response = client.get("/api/destinations")
        data = response.json()
        assert isinstance(data, list)

    def test_destinations_not_empty(self):
        response = client.get("/api/destinations")
        data = response.json()
        assert len(data) > 0

    def test_destinations_filter_by_airline(self):
        response = client.get("/api/destinations?airline=EK")
        data = response.json()
        assert isinstance(data, list)

    def test_destinations_filter_by_origin(self):
        response = client.get("/api/destinations?origin=RUH")
        data = response.json()
        assert isinstance(data, list)

    def test_destinations_filter_by_both(self):
        response = client.get("/api/destinations?airline=SV&origin=JED")
        data = response.json()
        assert isinstance(data, list)


class TestDashboardStats:
    """Test GET /api/dashboard-stats endpoint."""

    def test_stats_returns_200(self):
        response = client.get("/api/dashboard-stats")
        assert response.status_code == 200

    def test_stats_has_required_fields(self):
        response = client.get("/api/dashboard-stats")
        data = response.json()
        assert "total_flights" in data
        assert "delay_rate" in data
        assert "avg_delay_minutes" in data
        assert "delay_by_day" in data

    def test_stats_total_flights_positive(self):
        response = client.get("/api/dashboard-stats")
        data = response.json()
        assert data["total_flights"] > 0

    def test_stats_delay_rate_valid(self):
        response = client.get("/api/dashboard-stats")
        data = response.json()
        assert 0 <= data["delay_rate"] <= 100

    def test_stats_filter_by_airline(self):
        response = client.get("/api/dashboard-stats?airline=UA")
        assert response.status_code == 200

    def test_stats_delay_by_day_is_list(self):
        response = client.get("/api/dashboard-stats")
        data = response.json()
        assert isinstance(data["delay_by_day"], list)


# ═══════════════════════════════════════════════════════════════════════════
# Original Endpoints Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestFlights:
    """Test GET /flights endpoint."""

    def test_flights_returns_200(self):
        response = client.get("/flights?limit=5")
        assert response.status_code == 200

    def test_flights_returns_data_and_count(self):
        response = client.get("/flights?limit=5")
        data = response.json()
        assert "data" in data
        assert "count" in data

    def test_flights_respects_limit(self):
        response = client.get("/flights?limit=3")
        data = response.json()
        assert data["count"] <= 3


class TestFlightsStats:
    """Test GET /flights/stats endpoint."""

    def test_stats_returns_200(self):
        response = client.get("/flights/stats")
        assert response.status_code == 200

    def test_stats_returns_data(self):
        response = client.get("/flights/stats")
        data = response.json()
        assert "data" in data


class TestAirports:
    """Test GET /airports endpoint."""

    def test_airports_returns_200(self):
        response = client.get("/airports")
        assert response.status_code == 200

    def test_airports_returns_data(self):
        response = client.get("/airports")
        data = response.json()
        assert "data" in data


class TestAirportByIata:
    """Test GET /airports/{iata} endpoint."""

    def test_airport_returns_200(self):
        response = client.get("/airports/RUH")
        # Could be 200 or 404 depending on data
        assert response.status_code in [200, 404]


class TestRoutes:
    """Test GET /routes endpoint."""

    def test_routes_returns_200(self):
        response = client.get("/routes")
        assert response.status_code == 200

    def test_routes_returns_data(self):
        response = client.get("/routes")
        data = response.json()
        assert "data" in data


class TestGulfPredictionModel:
    """Test the deployed Saudi/UAE portfolio model."""

    def test_model_status_exposes_evaluation_metadata(self):
        response = client.get("/model/gulf/status")
        assert response.status_code == 200
        data = response.json()
        assert data["available"] is True
        assert data["champion"] == "Calibrated CatBoost"
        assert "Logistic Regression" in data["metrics"]
        assert 0 <= data["reliability_score"] <= 100
        assert data["reliability_label"]

    def test_gulf_prediction_returns_calibrated_probability(self):
        response = client.post("/predict/gulf", json={
            "origin": "RUH",
            "destination": "DXB",
            "airline": "Riyadh Air",
            "flight_date": "2026-09-12",
            "distance": 545,
            "departure_hour": 18,
            "wind_kmh": 25,
            "precipitation_mm": 0,
            "cloud_cover_pct": 20,
        })
        assert response.status_code == 200
        data = response.json()
        assert 0 <= data["delay_probability"] <= 1
        assert data["risk_band"] in {"LOW", "MEDIUM", "HIGH"}
        assert data["model_version"] == "gulf-delay-portfolio-v1"


class TestLive:
    """Test GET /live endpoint."""

    def test_live_returns_response(self):
        response = client.get("/live")
        # 200 if MongoDB connected, 500 if not
        assert response.status_code in [200, 500]

    def test_live_returns_data_when_connected(self):
        response = client.get("/live")
        if response.status_code == 200:
            data = response.json()
            assert "data" in data
            assert "count" in data
