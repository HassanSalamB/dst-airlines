"""
data.py — fetches data from FastAPI endpoints instead of direct PostgreSQL.
Falls back to mock data if API is unavailable.
"""
import os
from math import asin, cos, radians, sin, sqrt
import pandas as pd
import numpy as np
import requests

API_BASE_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

AIRLINE_MAP = {
    "AA":"American Airlines","AS":"Alaska Airlines","B6":"JetBlue Airways",
    "C5":"CommutAir","DL":"Delta Air Lines","F9":"Frontier Airlines",
    "G4":"Allegiant Air","G7":"GoJet Airlines","HA":"Hawaiian Airlines",
    "MQ":"Envoy Air","NK":"Spirit Airlines","OH":"PSA Airlines",
    "OO":"SkyWest Airlines","PT":"Piedmont Airlines","QX":"Horizon Air",
    "UA":"United Airlines","WN":"Southwest Airlines","YV":"Mesa Airlines",
    "YX":"Republic Airways","ZW":"Air Wisconsin","9E":"Endeavor Air",
}

AIRLINES = sorted(AIRLINE_MAP.values())

AIRPORTS = {
    "ATL":"Atlanta","AUS":"Austin","BNA":"Nashville","BOS":"Boston",
    "BUF":"Buffalo","BWI":"Baltimore","CLT":"Charlotte","CMH":"Columbus",
    "CVG":"Cincinnati","DCA":"Washington DC","DEN":"Denver","DFW":"Dallas",
    "DTW":"Detroit","EWR":"Newark","HNL":"Honolulu","IAD":"Dulles",
    "IAH":"Houston","IND":"Indianapolis","JFK":"New York","LAS":"Las Vegas",
    "LAX":"Los Angeles","LGA":"LaGuardia","MCO":"Orlando","MDW":"Midway",
    "MIA":"Miami","MCI":"Kansas City","MKE":"Milwaukee","MSP":"Minneapolis",
    "OAK":"Oakland","OMA":"Omaha","ORD":"Chicago","PHL":"Philadelphia",
    "PHX":"Phoenix","PIT":"Pittsburgh","RDU":"Raleigh","SEA":"Seattle",
    "SFO":"San Francisco","SLC":"Salt Lake City","STL":"St. Louis","TPA":"Tampa",
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

    dates = rng.choice(pd.date_range("2025-01-01", "2025-12-31", freq="D"), size=n)
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


def get_live_flights():
    """Get live flights from MongoDB via API."""
    try:
        url = f"{API_BASE_URL}/live"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            result = response.json()
            return result.get("data", [])
        else:
            return []
    except Exception as e:
        print(f"Failed to fetch live flights: {e}")
        return []
