"""Near-real-time OpenSky ingestion for the Saudi/UAE portfolio view.

OpenSky provides aircraft state vectors, not commercial schedules, gates, or
official delay data.  Records are therefore stored as aircraft observations
and are never presented as airline operational status.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import time
from datetime import datetime, timezone
from typing import Iterable

import requests


LOG = logging.getLogger("gulf-live")
OPENSKY_STATES_URL = "https://opensky-network.org/api/states/all"
OPENSKY_TOKEN_URL = (
    "https://auth.opensky-network.org/auth/realms/opensky-network/"
    "protocol/openid-connect/token"
)
GULF_BBOX = {"lamin": 16.0, "lomin": 34.0, "lamax": 33.0, "lomax": 56.5}

AIRPORTS = {
    "RUH": {"name": "King Khalid International", "country": "Saudi Arabia", "lat": 24.9576, "lon": 46.6988},
    "JED": {"name": "King Abdulaziz International", "country": "Saudi Arabia", "lat": 21.6702, "lon": 39.1528},
    "DMM": {"name": "King Fahd International", "country": "Saudi Arabia", "lat": 26.4712, "lon": 49.7979},
    "MED": {"name": "Prince Mohammad bin Abdulaziz", "country": "Saudi Arabia", "lat": 24.5534, "lon": 39.7051},
    "DXB": {"name": "Dubai International", "country": "United Arab Emirates", "lat": 25.2532, "lon": 55.3657},
    "AUH": {"name": "Zayed International", "country": "United Arab Emirates", "lat": 24.4330, "lon": 54.6511},
    "SHJ": {"name": "Sharjah International", "country": "United Arab Emirates", "lat": 25.3286, "lon": 55.5172},
}

# Lightweight portfolio boundaries used to remove neighboring countries from
# the larger OpenSky request box. They are intentionally not legal airspace
# boundaries; the UI describes them as geographic portfolio boundaries.
MARKET_POLYGONS = {
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

STATE_FIELDS = (
    "icao24", "callsign", "origin_country", "time_position", "last_contact",
    "longitude", "latitude", "baro_altitude", "on_ground", "velocity",
    "true_track", "vertical_rate", "sensors", "geo_altitude", "squawk",
    "spi", "position_source", "category",
)


def utc_iso(timestamp: int | float | None = None) -> str:
    value = timestamp if timestamp is not None else time.time()
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return radius * 2 * math.asin(math.sqrt(a))


def point_in_polygon(latitude: float, longitude: float, polygon: list[tuple[float, float]]) -> bool:
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


def market_for_position(latitude: float, longitude: float) -> str | None:
    for country, polygon in MARKET_POLYGONS.items():
        if point_in_polygon(latitude, longitude, polygon):
            return country
    return None


def nearest_gateway(latitude: float, longitude: float, country: str | None = None) -> tuple[str, dict, float]:
    candidates = {
        code: details for code, details in AIRPORTS.items()
        if country is None or details["country"] == country
    }
    airport, details = min(
        candidates.items(),
        key=lambda item: haversine_km(latitude, longitude, item[1]["lat"], item[1]["lon"]),
    )
    distance = haversine_km(latitude, longitude, details["lat"], details["lon"])
    return airport, details, distance


class OpenSkyGulfClient:
    """Fetch and normalize one Gulf-bounding-box state-vector snapshot."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.client_id = os.getenv("OPENSKY_CLIENT_ID")
        self.client_secret = os.getenv("OPENSKY_CLIENT_SECRET")
        self._token: str | None = None
        self._token_expires_at = 0.0

    def _access_token(self) -> str | None:
        if not self.client_id or not self.client_secret:
            return None
        if self._token and time.time() < self._token_expires_at - 30:
            return self._token
        response = requests.post(
            OPENSKY_TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        self._token = payload["access_token"]
        self._token_expires_at = time.time() + int(payload.get("expires_in", 300))
        return self._token

    def fetch(self) -> list[dict]:
        token = self._access_token()
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        response = requests.get(
            OPENSKY_STATES_URL,
            params=GULF_BBOX,
            headers=headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        snapshot_time = int(payload.get("time") or time.time())
        return list(self.normalize(payload.get("states") or [], snapshot_time))

    @staticmethod
    def normalize(states: Iterable[list], snapshot_time: int) -> Iterable[dict]:
        for raw_state in states:
            values = list(raw_state) + [None] * max(0, len(STATE_FIELDS) - len(raw_state))
            state = dict(zip(STATE_FIELDS, values))
            if state["on_ground"] is not False or state["latitude"] is None or state["longitude"] is None:
                continue

            latitude = float(state["latitude"])
            longitude = float(state["longitude"])
            market_country = market_for_position(latitude, longitude)
            if market_country is None:
                continue
            airport, gateway, distance = nearest_gateway(latitude, longitude, market_country)
            altitude_m = state["geo_altitude"] if state["geo_altitude"] is not None else state["baro_altitude"]
            velocity_ms = state["velocity"]
            collected_at = utc_iso()
            yield {
                "icao24": state["icao24"],
                "callsign": (state["callsign"] or "").strip() or None,
                "registration_country": state["origin_country"],
                "longitude": longitude,
                "latitude": latitude,
                "altitude_m": round(float(altitude_m), 1) if altitude_m is not None else None,
                "altitude_ft": round(float(altitude_m) * 3.28084) if altitude_m is not None else None,
                "speed_kmh": round(float(velocity_ms) * 3.6, 1) if velocity_ms is not None else None,
                "heading": state["true_track"],
                "vertical_rate_ms": state["vertical_rate"],
                "on_ground": False,
                "airborne": True,
                "nearest_airport": airport,
                "nearest_airport_name": gateway["name"],
                "distance_to_airport_km": round(distance, 1),
                "market_country": market_country,
                "snapshot_time": snapshot_time,
                "snapshot_at": utc_iso(snapshot_time),
                "last_contact": state["last_contact"],
                "collected_at": collected_at,
                "data_source": "OpenSky Network",
                "is_live": True,
            }


def write_snapshot_to_mongo(records: list[dict]) -> None:
    from pymongo import MongoClient, UpdateOne

    client = MongoClient(os.getenv("MONGO_URL", "mongodb://mongo:27017/"), serverSelectionTimeoutMS=5000)
    collection = client[os.getenv("MONGO_DB", "airlines")]["live_flights"]
    collection.create_index("icao24", unique=True)
    collection.create_index("collected_at_dt", expireAfterSeconds=int(os.getenv("LIVE_TTL_SECONDS", "900")))
    now = datetime.now(timezone.utc)
    operations = [
        UpdateOne(
            {"icao24": record["icao24"]},
            {"$set": {**record, "collected_at_dt": now}},
            upsert=True,
        )
        for record in records
    ]
    if operations:
        collection.bulk_write(operations, ordered=False)
    client.close()


def run_producer(client: OpenSkyGulfClient, once: bool = False) -> None:
    from kafka import KafkaProducer

    producer = KafkaProducer(
        bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"),
        value_serializer=lambda value: json.dumps(value).encode("utf-8"),
    )
    topic = os.getenv("KAFKA_TOPIC", "gulf.live_flights")
    poll_seconds = max(20, int(os.getenv("OPENSKY_POLL_SECONDS", "60")))
    while True:
        try:
            records = client.fetch()
            for record in records:
                producer.send(topic, record)
            producer.flush()
            LOG.info("Published %d OpenSky aircraft observations", len(records))
        except Exception:
            LOG.exception("OpenSky producer cycle failed")
        if once:
            return
        time.sleep(poll_seconds)


def run_consumer() -> None:
    from kafka import KafkaConsumer

    consumer = KafkaConsumer(
        os.getenv("KAFKA_TOPIC", "gulf.live_flights"),
        bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"),
        group_id="gulf-live-mongodb",
        auto_offset_reset="latest",
        enable_auto_commit=True,
        value_deserializer=lambda value: json.loads(value.decode("utf-8")),
    )
    while True:
        batches = consumer.poll(timeout_ms=2000, max_records=250)
        batch = [message.value for messages in batches.values() for message in messages]
        if batch:
            write_snapshot_to_mongo(batch)
            LOG.info("Upserted %d observations into MongoDB", len(batch))


def run_direct(client: OpenSkyGulfClient, once: bool = False) -> None:
    """Mongo-only fallback for environments where Kafka is intentionally omitted."""
    poll_seconds = max(20, int(os.getenv("OPENSKY_POLL_SECONDS", "60")))
    while True:
        try:
            records = client.fetch()
            write_snapshot_to_mongo(records)
            LOG.info("Upserted %d OpenSky aircraft observations directly", len(records))
        except Exception:
            LOG.exception("OpenSky direct-ingestion cycle failed")
        if once:
            return
        time.sleep(poll_seconds)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("producer", "consumer", "direct"), default="direct")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
    client = OpenSkyGulfClient()
    if args.mode == "producer":
        run_producer(client, args.once)
    elif args.mode == "consumer":
        run_consumer()
    else:
        run_direct(client, args.once)


if __name__ == "__main__":
    main()
