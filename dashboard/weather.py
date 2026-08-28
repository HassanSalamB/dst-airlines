"""Current Open-Meteo weather for the Saudi/UAE portfolio gateways."""

import requests


AIRPORT_COORDS = {
    "RUH": (24.9576, 46.6988),
    "JED": (21.6702, 39.1528),
    "DMM": (26.4712, 49.7979),
    "MED": (24.5534, 39.7051),
    "DXB": (25.2532, 55.3657),
    "AUH": (24.4330, 54.6511),
    "SHJ": (25.3286, 55.5172),
}


def get_weather(iata: str) -> dict | None:
    coords = AIRPORT_COORDS.get((iata or "").upper())
    if not coords:
        return None
    latitude, longitude = coords
    try:
        response = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,wind_speed_10m,precipitation,cloud_cover",
                "timezone": "auto",
            },
            timeout=5,
        )
        response.raise_for_status()
        current = response.json().get("current", {})
        return {
            "temp": round(current.get("temperature_2m", 0), 1),
            "wind_speed": round(current.get("wind_speed_10m", 0), 1),
            "precip": round(current.get("precipitation", 0), 1),
            "cloud_cover": round(current.get("cloud_cover", 0) / 100 * 8, 1),
        }
    except (requests.RequestException, TypeError, ValueError):
        return None
