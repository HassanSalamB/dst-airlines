"""
test_data.py — Unit Tests for Dashboard Data Layer
Tests the API client functions in data.py

Run with:
    pytest test_data.py -v

Or with Docker:
    docker exec airlines_dashboard pytest test_data.py -v
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from data import (
    get_flights_df,
    get_airlines_list,
    get_origins_list,
    get_destinations_list,
    get_dashboard_stats,
    get_summary_stats,
    api_healthy,
    get_live_flights,
    AIRLINE_MAP,
    AIRLINES,
    AIRPORTS,
    GULF_AIRLINES,
    GULF_ANALYTICS_END_DATE,
    GULF_ANALYTICS_YEARS,
    GULF_COUNTRIES,
    _LIVE_CACHE,
    _direct_opensky_payload,
    _enrich_live_routes,
    _normalize_adsblol_aircraft,
    _mock,
    _market_for_position,
    get_gulf_flights_df,
)


# ═══════════════════════════════════════════════════════════════════════════
# Mock Data Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestMockData:
    """Test the mock data fallback."""

    def test_mock_returns_dataframe(self):
        df = _mock()
        assert isinstance(df, pd.DataFrame)

    def test_mock_has_2000_rows(self):
        df = _mock()
        assert len(df) == 2000

    def test_mock_has_required_columns(self):
        df = _mock()
        required = ["FlightDate", "Operating_Airline", "Origin", "Dest",
                     "Distance", "DepDelay", "Delayed"]
        for col in required:
            assert col in df.columns, f"Missing column: {col}"

    def test_mock_has_month_column(self):
        df = _mock()
        assert "Month" in df.columns

    def test_mock_has_day_of_week_column(self):
        df = _mock()
        assert "DayOfWeek" in df.columns

    def test_mock_delayed_is_binary(self):
        df = _mock()
        assert set(df["Delayed"].unique()).issubset({0, 1})


# ═══════════════════════════════════════════════════════════════════════════
# Constants Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestConstants:
    """Test constant values."""

    def test_airline_map_not_empty(self):
        assert len(AIRLINE_MAP) > 0

    def test_airline_map_has_gulf_airlines(self):
        assert AIRLINE_MAP["SV"] == "Saudia"
        assert AIRLINE_MAP["EK"] == "Emirates"
        assert AIRLINE_MAP["EY"] == "Etihad Airways"

    def test_airlines_sorted(self):
        assert AIRLINES == sorted(AIRLINES)

    def test_airports_not_empty(self):
        assert len(AIRPORTS) > 0

    def test_airports_only_cover_the_gulf_portfolio(self):
        assert set(AIRPORTS) == {"RUH", "JED", "DMM", "MED", "DXB", "AUH", "SHJ"}


class TestGulfPortfolioData:
    """Validate the Saudi Arabia and UAE dashboard dataset."""

    def test_only_requested_gulf_markets_are_available(self):
        assert set(GULF_COUNTRIES) == {"Saudi Arabia", "United Arab Emirates"}

    def test_gulf_dataset_has_operational_rows(self):
        frame = get_gulf_flights_df()
        assert len(frame) == 6000
        assert set(frame["OriginCountry"]) == set(GULF_COUNTRIES)
        assert set(frame["Operating_Airline"]).issubset(set(GULF_AIRLINES))

    def test_gulf_dataset_exposes_historical_years_through_2026_ytd(self):
        frame = get_gulf_flights_df()
        assert sorted(frame["Year"].unique()) == GULF_ANALYTICS_YEARS
        assert GULF_ANALYTICS_YEARS[-1] == 2026
        assert frame["FlightDate"].max().year == GULF_ANALYTICS_YEARS[-1]
        assert frame["FlightDate"].max() <= GULF_ANALYTICS_END_DATE

    def test_gulf_dataset_contains_model_weather_and_time_features(self):
        frame = get_gulf_flights_df()
        required = {
            "DepartureHour", "WindKmh", "PrecipitationMm", "CloudCoverPct",
        }
        assert required.issubset(frame.columns)
        assert frame["DepartureHour"].between(0, 23).all()
        assert frame["CloudCoverPct"].between(0, 100).all()

    def test_country_and_gateway_filters_drive_the_data(self):
        frame = get_gulf_flights_df("Saudi Arabia", "RUH")
        assert not frame.empty
        assert set(frame["OriginCountry"]) == {"Saudi Arabia"}
        assert set(frame["Origin"]) == {"RUH"}

    def test_gulf_routes_never_connect_an_airport_to_itself(self):
        frame = get_gulf_flights_df()
        assert not (frame["Origin"] == frame["Dest"]).any()

    def test_live_market_boundaries_exclude_neighboring_country(self):
        assert _market_for_position(24.71, 46.68) == "Saudi Arabia"
        assert _market_for_position(25.20, 55.27) == "United Arab Emirates"
        assert _market_for_position(32.08, 34.78) is None

    @patch("data._route_for_callsign")
    def test_live_route_includes_real_airport_coordinates(self, route_lookup):
        route_lookup.return_value = {
            "origin": {
                "iata_code": "CAI", "municipality": "Cairo",
                "latitude": 30.1219, "longitude": 31.4056,
            },
            "destination": {
                "iata_code": "DXB", "municipality": "Dubai",
                "latitude": 25.2528, "longitude": 55.3644,
            },
        }
        row = _enrich_live_routes([{
            "icao24": "abc123", "callsign": "UAE71J",
            "latitude": 25.1, "longitude": 54.9,
        }])[0]

        assert row["origin_latitude"] == 30.1219
        assert row["origin_longitude"] == 31.4056
        assert row["destination_latitude"] == 25.2528
        assert row["destination_longitude"] == 55.3644
        assert row["airline"] == "Emirates"


# ═══════════════════════════════════════════════════════════════════════════
# API Client Tests (with mocked requests)
# ═══════════════════════════════════════════════════════════════════════════

class TestGetFlightsDf:
    """Test get_flights_df() function."""

    @patch('data.requests.get')
    def test_returns_dataframe_on_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "flight_id": 1,
                "flightdate": "2024-01-01",
                "airline": "SV",
                "origin": "RUH",
                "origincityname": "Riyadh",
                "dest": "DXB",
                "destcityname": "Dubai",
                "dep_delay": 10.0,
                "dep_del15": False,
                "distance": 2475.0,
                "carrierdelay": 0,
                "weatherdelay": 0,
                "nasdelay": 0,
                "securitydelay": 0,
                "lateaircraftdelay": 0,
            }
        ]
        mock_get.return_value = mock_response

        df = get_flights_df()
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    @patch('data.requests.get')
    def test_maps_airline_codes_to_names(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "flight_id": 1,
                "flightdate": "2024-01-01",
                "airline": "SV",
                "origin": "RUH",
                "origincityname": "Riyadh",
                "dest": "DXB",
                "destcityname": "Dubai",
                "dep_delay": 10.0,
                "dep_del15": False,
                "distance": 2475.0,
                "carrierdelay": 0,
                "weatherdelay": 0,
                "nasdelay": 0,
                "securitydelay": 0,
                "lateaircraftdelay": 0,
            }
        ]
        mock_get.return_value = mock_response

        df = get_flights_df()
        assert df["Operating_Airline"].iloc[0] == "Saudia"

    @patch('data.requests.get')
    def test_adds_month_column(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "flight_id": 1,
                "flightdate": "2024-03-15",
                "airline": "EK",
                "origin": "DXB",
                "origincityname": "Dubai",
                "dest": "JED",
                "destcityname": "Jeddah",
                "dep_delay": 5.0,
                "dep_del15": False,
                "distance": 1946.0,
                "carrierdelay": 0,
                "weatherdelay": 0,
                "nasdelay": 0,
                "securitydelay": 0,
                "lateaircraftdelay": 0,
            }
        ]
        mock_get.return_value = mock_response

        df = get_flights_df()
        assert "Month" in df.columns
        assert df["Month"].iloc[0] == 3

    @patch('data.requests.get')
    def test_adds_day_of_week_column(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "flight_id": 1,
                "flightdate": "2024-03-15",
                "airline": "EK",
                "origin": "DXB",
                "origincityname": "Dubai",
                "dest": "JED",
                "destcityname": "Jeddah",
                "dep_delay": 5.0,
                "dep_del15": False,
                "distance": 1946.0,
                "carrierdelay": 0,
                "weatherdelay": 0,
                "nasdelay": 0,
                "securitydelay": 0,
                "lateaircraftdelay": 0,
            }
        ]
        mock_get.return_value = mock_response

        df = get_flights_df()
        assert "DayOfWeek" in df.columns

    @patch('data.requests.get')
    def test_fallback_on_api_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        df = get_flights_df()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2000  # Mock data

    @patch('data.requests.get')
    def test_fallback_on_connection_error(self, mock_get):
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError("API down")

        df = get_flights_df()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2000  # Mock data

    @patch('data.requests.get')
    def test_fallback_on_timeout(self, mock_get):
        import requests
        mock_get.side_effect = requests.exceptions.Timeout("Timeout")

        df = get_flights_df()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2000  # Mock data


class TestGetAirlinesList:
    """Test get_airlines_list() function."""

    @patch('data.requests.get')
    def test_returns_list_on_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = ["SV", "EK", "EY"]
        mock_get.return_value = mock_response

        result = get_airlines_list()
        assert isinstance(result, list)
        assert len(result) == 3

    @patch('data.requests.get')
    def test_maps_codes_to_names(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = ["SV"]
        mock_get.return_value = mock_response

        result = get_airlines_list()
        assert "Saudia" in result

    @patch('data.requests.get')
    def test_fallback_on_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        result = get_airlines_list()
        assert isinstance(result, list)
        assert len(result) > 0  # Returns AIRLINES constant


class TestGetOriginsList:
    """Test get_origins_list() function."""

    @patch('data.requests.get')
    def test_returns_list(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = ["RUH", "JED", "DXB"]
        mock_get.return_value = mock_response

        result = get_origins_list()
        assert isinstance(result, list)

    @patch('data.requests.get')
    def test_fallback_on_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        result = get_origins_list()
        assert isinstance(result, list)
        assert len(result) > 0


class TestGetDestinationsList:
    """Test get_destinations_list() function."""

    @patch('data.requests.get')
    def test_returns_list(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = ["DXB", "AUH", "SHJ"]
        mock_get.return_value = mock_response

        result = get_destinations_list()
        assert isinstance(result, list)

    @patch('data.requests.get')
    def test_fallback_on_error(self, mock_get):
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError()

        result = get_destinations_list()
        assert isinstance(result, list)


class TestGetDashboardStats:
    """Test get_dashboard_stats() function."""

    @patch('data.requests.get')
    def test_returns_dict_on_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "total_flights": 560352,
            "delay_rate": 28.1,
            "avg_delay_minutes": 12.5,
            "delay_by_day": []
        }
        mock_get.return_value = mock_response

        result = get_dashboard_stats()
        assert isinstance(result, dict)
        assert result["total_flights"] == 560352

    @patch('data.requests.get')
    def test_fallback_on_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        result = get_dashboard_stats()
        assert isinstance(result, dict)
        assert "total_flights" in result


# ═══════════════════════════════════════════════════════════════════════════
# API Health Check Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestApiHealthy:
    """Test api_healthy() function."""

    @patch('data.requests.get')
    def test_returns_true_when_api_up(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        assert api_healthy() == True

    @patch('data.requests.get')
    def test_returns_false_when_api_down(self, mock_get):
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError()

        assert api_healthy() == False


# ═══════════════════════════════════════════════════════════════════════════
# Summary Stats Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestGetSummaryStats:
    """Test get_summary_stats() function."""

    @patch('data.get_flights_df')
    def test_returns_dict(self, mock_get_flights):
        mock_get_flights.return_value = _mock()

        result = get_summary_stats()
        assert isinstance(result, dict)

    @patch('data.get_flights_df')
    def test_has_required_keys(self, mock_get_flights):
        mock_get_flights.return_value = _mock()

        result = get_summary_stats()
        required = ["total_flights", "delayed_flights", "delay_rate",
                     "avg_dep_delay", "airlines", "routes"]
        for key in required:
            assert key in result, f"Missing key: {key}"

    @patch('data.get_flights_df')
    def test_total_flights_correct(self, mock_get_flights):
        mock_get_flights.return_value = _mock()

        result = get_summary_stats()
        assert result["total_flights"] == 2000


# ═══════════════════════════════════════════════════════════════════════════
# Live Flights Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestGetLiveFlights:
    """Test get_live_flights() function."""

    @patch('data.requests.get')
    def test_returns_payload_on_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"callsign": "TEST123"}]}
        mock_get.return_value = mock_response

        result = get_live_flights()
        assert result["data"][0]["callsign"] == "TEST123"
        assert result["data"][0]["origin"] == "Not available"
        assert result["data"][0]["destination"] == "Not available"

    @patch('data.requests.get')
    def test_returns_unavailable_payload_on_error(self, mock_get):
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError()

        result = get_live_flights()
        assert result["data"] == []
        assert result["is_live"] is False

    @patch('data.requests.get')
    def test_all_countries_omits_country_api_filter(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{"icao24": "abc123", "callsign": None}]
        }
        mock_get.return_value = mock_response

        get_live_flights("ALL", "ALL")

        assert "country" not in mock_get.call_args.kwargs["params"]

    @patch('data._direct_opensky_payload')
    @patch('data.requests.get')
    def test_gateway_catchment_does_not_discard_distant_nearest_aircraft(
        self, mock_get, direct_payload
    ):
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError()
        direct_payload.return_value = {
            "data": [{
                "icao24": "abc123", "callsign": None,
                "market_country": "Saudi Arabia", "nearest_airport": "RUH",
                "distance_to_airport_km": 298.0,
                "latitude": 26.0, "longitude": 44.0,
            }],
            "count": 1, "last_updated": "2026-08-28T12:00:00Z",
            "source": "OpenSky Network", "is_live": True,
        }

        result = get_live_flights("Saudi Arabia", "RUH")

        assert result["count"] == 1
        assert result["data"][0]["nearest_airport"] == "RUH"

    def test_normalizes_adsblol_observation_without_claiming_schedule_data(self):
        result = _normalize_adsblol_aircraft({
            "hex": "896123",
            "flight": "UAE12 ",
            "lat": 25.2532,
            "lon": 55.3657,
            "alt_baro": 12000,
            "gs": 250,
            "track": 92.5,
            "baro_rate": 600,
            "seen": 2.5,
        }, 1_788_000_000)

        assert result["callsign"] == "UAE12"
        assert result["market_country"] == "United Arab Emirates"
        assert result["nearest_airport"] in {"DXB", "AUH", "SHJ"}
        assert result["speed_kmh"] == 463.0
        assert result["data_source"] == "ADSB.lol"
        assert "origin" not in result
        assert "destination" not in result

    def test_discards_adsblol_ground_and_out_of_scope_observations(self):
        ground = _normalize_adsblol_aircraft({
            "hex": "896123", "lat": 25.25, "lon": 55.36, "alt_baro": "ground",
        }, 1_788_000_000)
        outside = _normalize_adsblol_aircraft({
            "hex": "abc123", "lat": 51.5, "lon": -0.1, "alt_baro": 30000,
        }, 1_788_000_000)

        assert ground is None
        assert outside is None

    @patch('data._fetch_adsblol_payload')
    @patch('data._fetch_opensky_payload')
    def test_uses_adsblol_when_opensky_is_unreachable(self, opensky, adsblol):
        import requests
        opensky.side_effect = requests.exceptions.Timeout()
        adsblol.return_value = {
            "data": [{"icao24": "896123", "data_source": "ADSB.lol"}],
            "count": 1,
            "last_updated": "2026-08-30T10:00:00Z",
            "source": "ADSB.lol community feed (OpenSky fallback)",
            "is_live": True,
        }
        with patch.dict(_LIVE_CACHE, {"fetched_at": 0.0, "payload": None}):
            result = _direct_opensky_payload()

        assert result["count"] == 1
        assert result["source"].startswith("ADSB.lol")
        adsblol.assert_called_once_with()
