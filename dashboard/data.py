"""
data.py — fetches data from FastAPI endpoints instead of direct PostgreSQL.
Falls back to mock data if API is unavailable.
"""
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from math import asin, cos, radians, sin, sqrt
import pandas as pd
import numpy as np
import requests

API_BASE_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
OPENSKY_STATES_URL = "https://opensky-network.org/api/states/all"
ADSBDB_CALLSIGN_URL = "https://api.adsbdb.com/v0/callsign/{callsign}"
GULF_BBOX = {"lamin": 16.0, "lomin": 34.0, "lamax": 33.0, "lomax": 56.5}

AIRLINE_MAP = {
    "RX":"Riyadh Air","SV":"Saudia","XY":"flynas",
    "EK":"Emirates","EY":"Etihad Airways","FZ":"flydubai","G9":"Air Arabia",
}

AIRLINES = sorted(AIRLINE_MAP.values())

AIRPORTS = {
    "RUH":"Riyadh","JED":"Jeddah","DMM":"Dammam","MED":"Medina",
    "DXB":"Dubai","AUH":"Abu Dhabi","SHJ":"Sharjah",
}

# Gulf portfolio market used by the interactive dashboard demo.
GULF_COUNTRIES = {
    "Saudi Arabia": {
        "flag": "🇸🇦",
        "airports": {
            "RUH": "King Khalid International · Riyadh",
            "JED": "King Abdulaziz International · Jeddah",
            "DMM": "King Fahd International · Dammam",
            "MED": "Prince Mohammad bin Abdulaziz · Medina",
        },
        "focus": "Riyadh Air network showcase",
        "airlines": ["Riyadh Air", "Saudia", "flynas"],
    },
    "United Arab Emirates": {
        "flag": "🇦🇪",
        "airports": {
            "DXB": "Dubai International · Dubai",
            "AUH": "Zayed International · Abu Dhabi",
            "SHJ": "Sharjah International · Sharjah",
        },
        "focus": "Emirates network showcase",
        "airlines": ["Emirates", "Etihad Airways", "flydubai", "Air Arabia"],
    },
}

GULF_AIRPORT_COORDS = {
    "RUH": (24.9576, 46.6988), "JED": (21.6702, 39.1528),
    "DMM": (26.4712, 49.7979), "MED": (24.5534, 39.7051),
    "DXB": (25.2532, 55.3657), "AUH": (24.4330, 54.6511),
    "SHJ": (25.3286, 55.5172),
}

GULF_AIRLINES = sorted({
    airline
    for market in GULF_COUNTRIES.values()
    for airline in market["airlines"]
})

GULF_ANALYTICS_YEARS = [2023, 2024, 2025]

GULF_AIRPORTS = {
    code: name
    for market in GULF_COUNTRIES.values()
    for code, name in market["airports"].items()
}

GULF_AIRPORT_COUNTRY = {
    code: country
    for country, market in GULF_COUNTRIES.items()
    for code in market["airports"]
}

GULF_MARKET_POLYGONS = {
    "United Arab Emirates": [
        (51.4, 24.0), (51.7, 25.4), (53.0, 26.1), (56.4, 26.2),
        (56.4, 24.0), (55.0, 22.5), (52.3, 22.6),
    ],
    "Saudi Arabia": [
        (34.5, 28.0), (36.0, 32.2), (39.2, 32.1), (42.0, 28.9),
        (48.0, 29.4), (50.3, 27.0), (50.2, 24.4), (52.0, 22.7),
        (55.5, 21.8), (55.0, 19.0), (52.0, 16.0), (47.0, 16.0),
        (43.0, 17.0), (41.0, 19.0), (38.0, 23.0),
    ],
}

DELAY_CAUSES = [
    "CarrierDelay","WeatherDelay","NASDelay",
    "SecurityDelay","LateAircraftDelay",
]

def _mock(n=2000):
    """Generate mock data for fallback."""
    np.random.seed(42)
    origins = np.random.choice(list(AIRPORTS.keys()), n)
    dests   = np.random.choice(list(AIRPORTS.keys()), n)
    dep     = np.round(np.random.exponential(18,n)-5,1)
    df = pd.DataFrame({
        "FlightDate":        pd.date_range("2024-01-01","2024-12-31",periods=n),
        "Operating_Airline": np.random.choice(AIRLINES,n),
        "Origin":            origins,
        "Dest":              dests,
        "OriginCity":        [AIRPORTS[o] for o in origins],
        "DestCity":          [AIRPORTS[d] for d in dests],
        "Distance":          np.random.randint(200,3000,n),
        "DepDelay":          np.clip(dep,-30,300),
        "ArrDelay":          np.clip(dep+np.random.normal(0,5,n),-60,300),
        "Delayed":           (dep>15).astype(int),
        "CarrierDelay":      np.clip(np.random.exponential(5,n),0,120),
        "WeatherDelay":      np.clip(np.random.exponential(3,n),0,90),
        "NASDelay":          np.clip(np.random.exponential(4,n),0,100),
        "SecurityDelay":     np.clip(np.random.exponential(1,n),0,30),
        "LateAircraftDelay": np.clip(np.random.exponential(6,n),0,150),
    })
    df["Month"]     = df["FlightDate"].dt.month
    df["DayOfWeek"] = df["FlightDate"].dt.day_name()
    return df

_MOCK = _mock()


def _distance_miles(origin: str, destination: str) -> int:
    """Return the great-circle distance between two Gulf airports."""
    lat1, lon1 = GULF_AIRPORT_COORDS[origin]
    lat2, lon2 = GULF_AIRPORT_COORDS[destination]
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return int(3959 * 2 * asin(sqrt(a)))


def _gulf_mock(n=6000):
    """Generate deterministic Saudi/UAE portfolio flight operations data."""
    rng = np.random.default_rng(2030)
    airports = list(GULF_AIRPORTS)
    origin_weights = np.array([0.24, 0.18, 0.10, 0.05, 0.23, 0.13, 0.07])
    origins = rng.choice(airports, size=n, p=origin_weights)

    destinations = []
    for origin in origins:
        candidates = [airport for airport in airports if airport != origin]
        # Prefer cross-border routes while retaining domestic network coverage.
        cross_border = [
            airport for airport in candidates
            if GULF_AIRPORT_COUNTRY[airport] != GULF_AIRPORT_COUNTRY[origin]
        ]
        domestic = [airport for airport in candidates if airport not in cross_border]
        pool = cross_border if rng.random() < 0.62 or not domestic else domestic
        destinations.append(rng.choice(pool))

    country_airline_weights = {
        "Saudi Arabia": [0.30, 0.45, 0.25],
        "United Arab Emirates": [0.38, 0.25, 0.22, 0.15],
    }
    airlines = [
        rng.choice(
            GULF_COUNTRIES[GULF_AIRPORT_COUNTRY[origin]]["airlines"],
            p=country_airline_weights[GULF_AIRPORT_COUNTRY[origin]],
        )
        for origin in origins
    ]

    dates = rng.choice(
        pd.date_range(
            f"{GULF_ANALYTICS_YEARS[0]}-01-01",
            f"{GULF_ANALYTICS_YEARS[-1]}-12-31",
            freq="D",
        ),
        size=n,
    )
    airport_delay = {"RUH": 6, "JED": 9, "DMM": 5, "MED": 4, "DXB": 11, "AUH": 7, "SHJ": 8}
    airline_delay = {
        "Riyadh Air": -1.5, "Saudia": 1.0, "flynas": 2.5,
        "Emirates": 0.5, "Etihad Airways": -0.5, "flydubai": 2.0, "Air Arabia": 2.5,
    }
    base_delay = np.array([airport_delay[airport] for airport in origins], dtype=float)
    base_delay += np.array([airline_delay[airline] for airline in airlines])
    disruption = rng.binomial(1, 0.17, n) * rng.exponential(28, n)
    dep_delay = np.round(np.clip(base_delay + rng.normal(0, 10, n) + disruption, -20, 180), 1)
    delayed = (dep_delay > 15).astype(int)
    positive_delay = np.clip(dep_delay, 0, None)

    frame = pd.DataFrame({
        "FlightDate": pd.to_datetime(dates),
        "Operating_Airline": airlines,
        "Origin": origins,
        "Dest": destinations,
        "OriginCity": [GULF_AIRPORTS[airport].split(" · ")[-1] for airport in origins],
        "DestCity": [GULF_AIRPORTS[airport].split(" · ")[-1] for airport in destinations],
        "OriginCountry": [GULF_AIRPORT_COUNTRY[airport] for airport in origins],
        "DestCountry": [GULF_AIRPORT_COUNTRY[airport] for airport in destinations],
        "Distance": [_distance_miles(origin, destination) for origin, destination in zip(origins, destinations)],
        "DepDelay": dep_delay,
        "ArrDelay": np.round(np.clip(dep_delay + rng.normal(-2, 5, n), -30, 190), 1),
        "Delayed": delayed,
        "CarrierDelay": np.round(np.where(delayed, positive_delay * rng.uniform(0.25, 0.45, n), 0), 1),
        "WeatherDelay": np.round(np.where(delayed, positive_delay * rng.uniform(0.08, 0.22, n), 0), 1),
        "NASDelay": np.round(np.where(delayed, positive_delay * rng.uniform(0.12, 0.28, n), 0), 1),
        "SecurityDelay": np.round(np.where(delayed, positive_delay * rng.uniform(0.00, 0.04, n), 0), 1),
        "LateAircraftDelay": np.round(np.where(delayed, positive_delay * rng.uniform(0.18, 0.38, n), 0), 1),
    })
    frame["Month"] = frame["FlightDate"].dt.month
    frame["Year"] = frame["FlightDate"].dt.year
    frame["DayOfWeek"] = frame["FlightDate"].dt.day_name()
    return frame.sort_values("FlightDate").reset_index(drop=True)


_GULF_MOCK = _gulf_mock()


def get_gulf_flights_df(country=None, airport=None):
    """Return the Gulf portfolio dataset filtered by origin market and gateway."""
    frame = _GULF_MOCK.copy()
    if country and country != "ALL":
        frame = frame[frame["OriginCountry"] == country]
    if airport and airport != "ALL":
        frame = frame[frame["Origin"] == airport]
    return frame.reset_index(drop=True)


# ═══════════════════════════════════════════════════════════════════════════
# NEW: API-based data fetching
# ═══════════════════════════════════════════════════════════════════════════

def get_flights_df(airline=None, origin=None, dest=None, limit=100000):
    """
    Fetch flights from FastAPI instead of direct PostgreSQL.
    Falls back to mock data if API is unavailable.
    """
    try:
        url = f"{API_BASE_URL}/api/flights"
        params = {"limit": limit}
        
        if airline:
            params["airline"] = airline
        if origin:
            params["origin"] = origin
        if dest:
            params["dest"] = dest
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if not data:
                print("API returned empty data, using mock")
                return _MOCK.copy()
            
            df = pd.DataFrame(data)
            
            # Rename columns to match dashboard expectations
            column_mapping = {
                "flightdate": "FlightDate",
                "airline": "Operating_Airline",
                "origin": "Origin",
                "origincityname": "OriginCity",
                "dest": "Dest",
                "destcityname": "DestCity",
                "distance": "Distance",
                "dep_delay": "DepDelay",
                "dep_del15": "Delayed",
                "carrierdelay": "CarrierDelay",
                "weatherdelay": "WeatherDelay",
                "nasdelay": "NASDelay",
                "securitydelay": "SecurityDelay",
                "lateaircraftdelay": "LateAircraftDelay",
            }
            df.rename(columns=column_mapping, inplace=True)
            
            # Process columns
            df["FlightDate"] = pd.to_datetime(df["FlightDate"])
            df["Month"]      = df["FlightDate"].dt.month
            df["DayOfWeek"]  = df["FlightDate"].dt.day_name()
            df["Delayed"]    = df["Delayed"].fillna(0).astype(int)
            
            # Map airline codes to full names
            df["Operating_Airline"] = df["Operating_Airline"].map(AIRLINE_MAP).fillna(df["Operating_Airline"])
            
            # Fill missing delay causes with 0
            for col in ["CarrierDelay", "WeatherDelay", "NASDelay", "SecurityDelay", "LateAircraftDelay"]:
                if col in df.columns:
                    df[col] = df[col].fillna(0)
            
            print(f"✅ Loaded {len(df)} flights from API")
            return df
        else:
            print(f"API error {response.status_code}, using mock data")
            return _MOCK.copy()
            
    except requests.exceptions.RequestException as e:
        print(f"API unavailable ({e}), using mock data")
        return _MOCK.copy()
    except Exception as e:
        print(f"Unexpected error ({e}), using mock data")
        return _MOCK.copy()


def get_airlines_list():
    """Get list of all airlines from API."""
    try:
        url = f"{API_BASE_URL}/api/airlines"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            airlines = response.json()
            # Map codes to full names
            return [AIRLINE_MAP.get(code, code) for code in airlines]
        else:
            return AIRLINES
    except Exception as e:
        print(f"Failed to fetch airlines from API: {e}")
        return AIRLINES


def get_origins_list(airline=None):
    """Get list of origin airports from API, optionally filtered by airline."""
    try:
        url = f"{API_BASE_URL}/api/origins"
        params = {}
        if airline:
            # Map full name back to code
            airline_code = {v: k for k, v in AIRLINE_MAP.items()}.get(airline, airline)
            params["airline"] = airline_code
        
        response = requests.get(url, params=params, timeout=5)
        
        if response.status_code == 200:
            return response.json()
        else:
            return list(AIRPORTS.keys())
    except Exception as e:
        print(f"Failed to fetch origins from API: {e}")
        return list(AIRPORTS.keys())


def get_destinations_list(airline=None, origin=None):
    """Get list of destination airports from API, filtered by airline and/or origin."""
    try:
        url = f"{API_BASE_URL}/api/destinations"
        params = {}
        
        if airline:
            # Map full name back to code
            airline_code = {v: k for k, v in AIRLINE_MAP.items()}.get(airline, airline)
            params["airline"] = airline_code
        if origin:
            params["origin"] = origin
        
        response = requests.get(url, params=params, timeout=5)
        
        if response.status_code == 200:
            return response.json()
        else:
            return list(AIRPORTS.keys())
    except Exception as e:
        print(f"Failed to fetch destinations from API: {e}")
        return list(AIRPORTS.keys())


def get_dashboard_stats(airline=None, origin=None, dest=None):
    """Get aggregated statistics from API."""
    try:
        url = f"{API_BASE_URL}/api/dashboard-stats"
        params = {}
        
        if airline:
            airline_code = {v: k for k, v in AIRLINE_MAP.items()}.get(airline, airline)
            params["airline"] = airline_code
        if origin:
            params["origin"] = origin
        if dest:
            params["dest"] = dest
        
        response = requests.get(url, params=params, timeout=5)
        
        if response.status_code == 200:
            return response.json()
        else:
            # Fallback: calculate from mock data
            df = _MOCK.copy()
            return {
                "total_flights": len(df),
                "delay_rate": round(df["Delayed"].mean() * 100, 1),
                "avg_delay_minutes": round(df[df["DepDelay"] > 0]["DepDelay"].mean(), 1),
                "delay_by_day": []
            }
    except Exception as e:
        print(f"Failed to fetch stats from API: {e}")
        df = _MOCK.copy()
        return {
            "total_flights": len(df),
            "delay_rate": round(df["Delayed"].mean() * 100, 1),
            "avg_delay_minutes": round(df[df["DepDelay"] > 0]["DepDelay"].mean(), 1),
            "delay_by_day": []
        }


def get_summary_stats():
    """Legacy function for backward compatibility."""
    df = get_flights_df()
    return {
        "total_flights":   len(df),
        "delayed_flights": int(df["Delayed"].sum()),
        "delay_rate":      round(df["Delayed"].mean()*100,1),
        "avg_dep_delay":   round(df[df["DepDelay"]>0]["DepDelay"].mean(),1),
        "airlines":        df["Operating_Airline"].nunique(),
        "routes":          df.groupby(["Origin","Dest"]).ngroups,
    }


def api_healthy():
    """Check if the FastAPI is responding."""
    try:
        response = requests.get(f"{API_BASE_URL}/", timeout=3)
        return response.status_code == 200
    except:
        return False


_LIVE_CACHE = {"fetched_at": 0.0, "payload": None}
_ROUTE_CACHE = {}


def _point_in_polygon(latitude, longitude, polygon):
    inside = False
    previous = polygon[-1]
    for current in polygon:
        x1, y1 = previous
        x2, y2 = current
        if (y1 > latitude) != (y2 > latitude):
            boundary_lon = (x2 - x1) * (latitude - y1) / (y2 - y1) + x1
            if longitude < boundary_lon:
                inside = not inside
        previous = current
    return inside


def _market_for_position(latitude, longitude):
    for country, polygon in GULF_MARKET_POLYGONS.items():
        if _point_in_polygon(latitude, longitude, polygon):
            return country
    return None


def _nearest_gulf_gateway(latitude: float, longitude: float, country: str):
    candidates = [
        code for code in GULF_AIRPORT_COORDS if GULF_AIRPORT_COUNTRY[code] == country
    ]
    nearest = min(
        candidates,
        key=lambda code: _distance_between_coords(
            latitude, longitude, *GULF_AIRPORT_COORDS[code]
        ),
    )
    distance = _distance_between_coords(
        latitude, longitude, *GULF_AIRPORT_COORDS[nearest]
    )
    return nearest, distance


def _distance_between_coords(lat1, lon1, lat2, lon2):
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 6371 * 2 * asin(sqrt(a))


def _direct_opensky_payload():
    """Fetch one cached Gulf snapshot when the FastAPI/Mongo stack is absent."""
    cache_seconds = max(30, int(os.getenv("OPENSKY_CACHE_SECONDS", "60")))
    if _LIVE_CACHE["payload"] and time.monotonic() - _LIVE_CACHE["fetched_at"] < cache_seconds:
        return _LIVE_CACHE["payload"]

    response = requests.get(OPENSKY_STATES_URL, params=GULF_BBOX, timeout=20)
    response.raise_for_status()
    raw = response.json()
    snapshot_time = int(raw.get("time") or time.time())
    rows = []
    for state in raw.get("states") or []:
        values = list(state) + [None] * max(0, 18 - len(state))
        (
            icao24, callsign, registration_country, _time_position, last_contact,
            longitude, latitude, baro_altitude, on_ground, velocity, heading,
            vertical_rate, _sensors, geo_altitude, _squawk, _spi,
            _position_source, _category,
        ) = values[:18]
        if on_ground is not False or latitude is None or longitude is None:
            continue
        market_country = _market_for_position(float(latitude), float(longitude))
        if market_country is None:
            continue
        nearest, distance = _nearest_gulf_gateway(float(latitude), float(longitude), market_country)
        altitude_m = geo_altitude if geo_altitude is not None else baro_altitude
        rows.append({
            "icao24": icao24,
            "callsign": (callsign or "").strip() or None,
            "registration_country": registration_country,
            "longitude": float(longitude),
            "latitude": float(latitude),
            "altitude_m": round(float(altitude_m), 1) if altitude_m is not None else None,
            "altitude_ft": round(float(altitude_m) * 3.28084) if altitude_m is not None else None,
            "speed_kmh": round(float(velocity) * 3.6, 1) if velocity is not None else None,
            "heading": heading,
            "vertical_rate_ms": vertical_rate,
            "on_ground": False,
            "airborne": True,
            "nearest_airport": nearest,
            "distance_to_airport_km": round(distance, 1),
            "market_country": market_country,
            "snapshot_time": snapshot_time,
            "snapshot_at": datetime.fromtimestamp(snapshot_time, tz=timezone.utc).isoformat(),
            "last_contact": last_contact,
            "data_source": "OpenSky Network",
            "is_live": True,
        })
    payload = {
        "data": rows,
        "count": len(rows),
        "last_updated": datetime.fromtimestamp(snapshot_time, tz=timezone.utc).isoformat(),
        "source": "OpenSky Network (direct fallback)",
        "is_live": True,
        "scope_note": "Country uses a portfolio boundary; airport is the nearest supported gateway.",
    }
    _LIVE_CACHE.update({"fetched_at": time.monotonic(), "payload": payload})
    return payload


def _route_for_callsign(callsign):
    callsign = (callsign or "").strip().upper()
    if not callsign:
        return None
    cached = _ROUTE_CACHE.get(callsign)
    if cached and cached["expires_at"] > time.time():
        return cached["route"]

    route = None
    try:
        response = requests.get(ADSBDB_CALLSIGN_URL.format(callsign=callsign), timeout=5)
        if response.status_code == 200:
            route = response.json().get("response", {}).get("flightroute")
    except (requests.RequestException, TypeError, ValueError):
        pass
    ttl = 21600 if route else 3600
    _ROUTE_CACHE[callsign] = {"route": route, "expires_at": time.time() + ttl}
    return route


def _airport_label(airport):
    if not airport:
        return "Not available"
    code = airport.get("iata_code") or airport.get("icao_code") or "Unknown"
    city = airport.get("municipality") or airport.get("name") or airport.get("country_name")
    return f"{code} · {city}" if city else code


def _airport_coordinate(airport, field):
    if not airport or airport.get(field) is None:
        return None
    try:
        return float(airport[field])
    except (TypeError, ValueError):
        return None


def _enrich_live_routes(rows):
    """Add best-effort community route matches without fabricating unknowns."""
    limit = max(0, min(50, int(os.getenv("ROUTE_LOOKUP_LIMIT", "30"))))
    candidates = [row for row in rows if row.get("callsign")][:limit]
    callsigns = sorted({row["callsign"].strip().upper() for row in candidates})
    routes = {}
    if callsigns:
        with ThreadPoolExecutor(max_workers=min(8, len(callsigns))) as executor:
            futures = {executor.submit(_route_for_callsign, callsign): callsign for callsign in callsigns}
            for future in as_completed(futures):
                try:
                    routes[futures[future]] = future.result()
                except Exception:
                    routes[futures[future]] = None

    for row in rows:
        callsign = (row.get("callsign") or "").strip().upper()
        route = routes.get(callsign) or (_ROUTE_CACHE.get(callsign) or {}).get("route")
        origin = route.get("origin") if route else None
        destination = route.get("destination") if route else None
        row["origin"] = _airport_label(origin) if origin else "Not available"
        row["destination"] = _airport_label(destination) if destination else "Not available"
        row["origin_latitude"] = _airport_coordinate(origin, "latitude")
        row["origin_longitude"] = _airport_coordinate(origin, "longitude")
        row["destination_latitude"] = _airport_coordinate(destination, "latitude")
        row["destination_longitude"] = _airport_coordinate(destination, "longitude")
        row["route_source"] = "ADSBDB community match" if route else "No route match"
        row["current_area"] = row.get("market_country") or "Saudi/UAE focus area"
        latitude = row.get("latitude")
        longitude = row.get("longitude")
        row["current_position"] = (
            f"{float(latitude):.3f}, {float(longitude):.3f}"
            if latitude is not None and longitude is not None else "Not available"
        )
    return rows


def get_live_flights(country=None, airport=None):
    """Get live OpenSky aircraft via FastAPI, with a direct read-only fallback."""
    params = {"limit": 500}
    if country and country != "ALL":
        params["country"] = country
    if airport and airport != "ALL":
        params["airport"] = airport
    try:
        url = f"{API_BASE_URL}/live"
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            result = response.json()
            if result.get("data"):
                result["data"] = _enrich_live_routes(result["data"])
                return result
    except Exception:
        pass

    try:
        result = _direct_opensky_payload().copy()
        rows = result["data"]
        if country and country != "ALL":
            rows = [row for row in rows if row.get("market_country") == country]
        if airport and airport != "ALL":
            rows = [
                row for row in rows
                if row.get("nearest_airport") == airport
            ]
        result["data"] = rows
        result["count"] = len(rows)
        result["scope_note"] = (
            "Gateway selection uses the nearest supported gateway catchment; "
            "it is not a fixed-radius airport boundary."
        )
        result["data"] = _enrich_live_routes(result["data"])
        return result
    except Exception as exc:
        return {
            "data": [], "count": 0, "last_updated": None,
            "source": "OpenSky unavailable", "is_live": False,
            "error": str(exc),
        }
