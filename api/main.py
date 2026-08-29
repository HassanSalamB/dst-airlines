"""FastAPI product interface for Gulf aviation analytics, live observations,
route traversal, and the versioned Saudi/UAE delay-risk model.
"""

import os
import logging
from datetime import date
from typing import Optional

import joblib
import pandas as pd
import numpy as np
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

# ── Config ────────────────────────────────────────────────────────────────
PG_URL = os.getenv("DATABASE_URL")
MONGO_URL = os.getenv("MONGO_URL", "mongodb://mongo:27017/")
NEO4J_URL = os.getenv("NEO4J_URL", "bolt://neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASS")
GULF_MODEL_PATH = os.getenv("GULF_MODEL_PATH", "gulf_delay_model.joblib")

# ═══════════════════════════════════════════════════════════════════════════
# DB Clients (lazy init)
# ═══════════════════════════════════════════════════════════════════════════
class DBClients:
    _pg    = None
    _mongo = None
    _neo4j = None

    @classmethod
    def pg(cls):
        if cls._pg is None:
            if not PG_URL:
                raise RuntimeError("DATABASE_URL is required for PostgreSQL access")
            from sqlalchemy import create_engine
            cls._pg = create_engine(PG_URL)
        return cls._pg

    @classmethod
    def mongo(cls):
        if cls._mongo is None:
            from pymongo import MongoClient
            cls._mongo = MongoClient(MONGO_URL,
                                     serverSelectionTimeoutMS=3000)["airlines_db"]
        return cls._mongo

    @classmethod
    def neo4j(cls):
        if cls._neo4j is None:
            if not NEO4J_PASS:
                raise RuntimeError("NEO4J_PASS is required for Neo4j access")
            from neo4j import GraphDatabase
            cls._neo4j = GraphDatabase.driver(
                NEO4J_URL, auth=(NEO4J_USER, NEO4J_PASS))
        return cls._neo4j


# ═══════════════════════════════════════════════════════════════════════════
# Gulf model loader
# ═══════════════════════════════════════════════════════════════════════════
_gulf_model_bundle = None


def get_gulf_model_bundle():
    global _gulf_model_bundle
    if _gulf_model_bundle is None:
        try:
            _gulf_model_bundle = joblib.load(GULF_MODEL_PATH)
            log.info("Gulf delay model loaded: %s", GULF_MODEL_PATH)
        except Exception as exc:
            log.warning("Gulf model artifact unavailable (%s): %s", GULF_MODEL_PATH, exc)
    return _gulf_model_bundle


def gulf_model_reliability(metadata: dict) -> dict:
    champion = metadata.get("champion", "")
    metrics = metadata.get("metrics", {}).get(champion, {})
    roc_auc = float(metrics.get("roc_auc", 0))
    pr_auc = float(metrics.get("pr_auc", 0))
    brier = float(metrics.get("brier", 1))
    calibration_points = metadata.get("calibration", [])
    calibration_gap = np.mean([
        abs(float(point["predicted"]) - float(point["observed"]))
        for point in calibration_points
        if "predicted" in point and "observed" in point
    ]) if calibration_points else 1
    score = round(100 * (
        0.40 * roc_auc
        + 0.20 * pr_auc
        + 0.20 * max(0, 1 - min(brier, 1))
        + 0.20 * max(0, 1 - min(float(calibration_gap), 1))
    ))
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


# ═══════════════════════════════════════════════════════════════════════════
# Pydantic schema
# ═══════════════════════════════════════════════════════════════════════════
class GulfPredictionInput(BaseModel):
    origin: str
    destination: str
    airline: str
    flight_date: date
    distance: float
    departure_hour: int
    wind_kmh: float
    precipitation_mm: float
    cloud_cover_pct: float


class GulfPredictionResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    delay_probability: float
    risk_band: str
    model_version: str
    algorithm: str
    data_scope: str
    limitations: str


# ═══════════════════════════════════════════════════════════════════════════
# App
# ═══════════════════════════════════════════════════════════════════════════
app = FastAPI(
    title="DST Airlines Gulf Aviation API",
    description=(
        "Saudi/UAE portfolio analytics, live aircraft observations, route "
        "traversal, and transparent delay-risk scenarios."
    ),
    version="3.0.0",
)

Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Health ────────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def health():
    return {
        "status": "ok",
        "version": "3.0.0",
        "databases": ["postgresql", "mongodb", "neo4j"],
    }


# ══════════════════════════════════════════════════════════════════════════
# NEW: Dashboard Endpoints (to replace direct PostgreSQL access)
# ══════════════════════════════════════════════════════════════════════════

@app.get("/api/flights", tags=["Dashboard"])
def get_flights_for_dashboard(
    airline: Optional[str] = Query(None, description="Filter by airline code"),
    origin:  Optional[str] = Query(None, description="Origin IATA code"),
    dest:    Optional[str] = Query(None, description="Dest IATA code"),
    limit:  int = Query(100000, le=200000, description="Max 200K rows"),
):
    """
    Dashboard endpoint: Get flights with optional filters.
    Returns random sample for balanced data across all months.
    """
    from sqlalchemy import text
    conditions = ["cancelled = FALSE"]
    params: dict = {}

    if airline:
        conditions.append("operating_airline = :airline")
        params["airline"] = airline.upper()
    if origin:
        conditions.append("origin = :origin")
        params["origin"] = origin.upper()
    if dest:
        conditions.append("dest = :dest")
        params["dest"] = dest.upper()

    where = " AND ".join(conditions)
    sql = f"""
        SELECT flight_id, flightdate, operating_airline AS airline,
               origin, origincityname, dest, destcityname,
               depdelay AS dep_delay, depdel15 AS dep_del15,
               distance, carrierdelay, weatherdelay, nasdelay,
               securitydelay, lateaircraftdelay
        FROM bronze.flights
        WHERE {where}
        ORDER BY RANDOM()
        LIMIT :limit
    """
    params["limit"] = limit

    try:
        with DBClients.pg().connect() as conn:
            df = pd.read_sql_query(text(sql), conn, params=params)
        df = df.fillna(0)
        return df.to_dict(orient='records')
    except Exception as e:
        log.error(f"Dashboard flights error: {e}")
        raise HTTPException(500, f"Database error: {e}")


@app.get("/api/airlines", tags=["Dashboard"])
def get_airlines_list():
    """Dashboard endpoint: Get list of all airlines."""
    from sqlalchemy import text
    sql = """
        SELECT DISTINCT operating_airline AS airline
        FROM bronze.flights
        WHERE operating_airline IS NOT NULL
        ORDER BY operating_airline
    """
    try:
        with DBClients.pg().connect() as conn:
            df = pd.read_sql_query(text(sql), conn)
        return df['airline'].tolist()
    except Exception as e:
        log.error(f"Airlines list error: {e}")
        raise HTTPException(500, f"Database error: {e}")


@app.get("/api/origins", tags=["Dashboard"])
def get_origins_list(airline: Optional[str] = Query(None)):
    """Dashboard endpoint: Get list of origin airports, optionally filtered by airline."""
    from sqlalchemy import text
    
    if airline:
        sql = """
            SELECT DISTINCT origin
            FROM bronze.flights
            WHERE operating_airline = :airline
              AND origin IS NOT NULL
            ORDER BY origin
        """
        params = {"airline": airline.upper()}
    else:
        sql = """
            SELECT DISTINCT origin
            FROM bronze.flights
            WHERE origin IS NOT NULL
            ORDER BY origin
        """
        params = {}

    try:
        with DBClients.pg().connect() as conn:
            df = pd.read_sql_query(text(sql), conn, params=params)
        return df['origin'].tolist()
    except Exception as e:
        log.error(f"Origins list error: {e}")
        raise HTTPException(500, f"Database error: {e}")


@app.get("/api/destinations", tags=["Dashboard"])
def get_destinations_list(
    airline: Optional[str] = Query(None),
    origin: Optional[str] = Query(None)
):
    """Dashboard endpoint: Get list of destination airports, filtered by airline and/or origin."""
    from sqlalchemy import text
    
    conditions = ["dest IS NOT NULL"]
    params = {}
    
    if airline:
        conditions.append("operating_airline = :airline")
        params["airline"] = airline.upper()
    if origin:
        conditions.append("origin = :origin")
        params["origin"] = origin.upper()
    
    where = " AND ".join(conditions)
    sql = f"""
        SELECT DISTINCT dest
        FROM bronze.flights
        WHERE {where}
        ORDER BY dest
    """

    try:
        with DBClients.pg().connect() as conn:
            df = pd.read_sql_query(text(sql), conn, params=params)
        return df['dest'].tolist()
    except Exception as e:
        log.error(f"Destinations list error: {e}")
        raise HTTPException(500, f"Database error: {e}")


@app.get("/api/dashboard-stats", tags=["Dashboard"])
def get_dashboard_stats(
    airline: Optional[str] = Query(None),
    origin: Optional[str] = Query(None),
    dest: Optional[str] = Query(None)
):
    """
    Dashboard endpoint: Get aggregated statistics.
    Returns: total flights, delay rate, avg delay, delay by day, etc.
    """
    from sqlalchemy import text
    
    conditions = ["cancelled = FALSE"]
    params = {}
    
    if airline:
        conditions.append("operating_airline = :airline")
        params["airline"] = airline.upper()
    if origin:
        conditions.append("origin = :origin")
        params["origin"] = origin.upper()
    if dest:
        conditions.append("dest = :dest")
        params["dest"] = dest.upper()
    
    where = " AND ".join(conditions)
    
    # General stats
    sql_general = f"""
        SELECT 
            COUNT(*) as total_flights,
            AVG(CASE WHEN depdel15 = TRUE THEN 1 ELSE 0 END) * 100 as delay_rate,
            AVG(depdelay) as avg_delay_minutes
        FROM bronze.flights
        WHERE {where}
    """
    
    # Delay by day of week
    sql_by_day = f"""
        SELECT 
            EXTRACT(DOW FROM flightdate) as day_of_week,
            COUNT(*) as flights,
            AVG(CASE WHEN depdel15 = TRUE THEN 1 ELSE 0 END) * 100 as delay_rate
        FROM bronze.flights
        WHERE {where}
        GROUP BY EXTRACT(DOW FROM flightdate)
        ORDER BY day_of_week
    """
    
    try:
        with DBClients.pg().connect() as conn:
            general = pd.read_sql_query(text(sql_general), conn, params=params).to_dict(orient='records')[0]
            by_day = pd.read_sql_query(text(sql_by_day), conn, params=params).to_dict(orient='records')
        
        return {
            "total_flights": int(general['total_flights']),
            "delay_rate": float(general['delay_rate'] or 0),
            "avg_delay_minutes": float(general['avg_delay_minutes'] or 0),
            "delay_by_day": by_day
        }
    except Exception as e:
        log.error(f"Dashboard stats error: {e}")
        raise HTTPException(500, f"Database error: {e}")


# ══════════════════════════════════════════════════════════════════════════
# EXISTING ENDPOINTS (no changes)
# ══════════════════════════════════════════════════════════════════════════

# ── Flights (PostgreSQL) ──────────────────────────────────────────────────
@app.get("/flights", tags=["Flights"])
def get_flights(
    airline: Optional[str] = Query(None, description="Filter by airline code"),
    origin:  Optional[str] = Query(None, description="Origin IATA code"),
    dest:    Optional[str] = Query(None, description="Dest IATA code"),
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_to:   Optional[str] = Query(None, description="YYYY-MM-DD"),
    delayed_only: bool = Query(False, description="Only delayed flights"),
    limit:  int = Query(100, le=5000),
    offset: int = Query(0),
):
    from sqlalchemy import text
    conditions = ["cancelled = FALSE"]
    params: dict = {}

    if airline:
        conditions.append("operating_airline = :airline")
        params["airline"] = airline.upper()
    if origin:
        conditions.append("origin = :origin")
        params["origin"] = origin.upper()
    if dest:
        conditions.append("dest = :dest")
        params["dest"] = dest.upper()
    if date_from:
        conditions.append("flightdate >= :date_from")
        params["date_from"] = date_from
    if date_to:
        conditions.append("flightdate <= :date_to")
        params["date_to"] = date_to
    if delayed_only:
        conditions.append("depdel15 = TRUE")

    where = " AND ".join(conditions)
    sql = f"""
        SELECT flight_id, flightdate, operating_airline,
               origin, origincityname, dest, destcityname,
               depdelay, depdel15, distance
        FROM bronze.flights
        WHERE {where}
        ORDER BY flightdate DESC
        LIMIT :limit OFFSET :offset
    """
    params["limit"]  = limit
    params["offset"] = offset

    try:
        with DBClients.pg().connect() as conn:
            rows = conn.execute(text(sql), params).mappings().all()
        return {"data": [dict(r) for r in rows], "count": len(rows)}
    except Exception as e:
        raise HTTPException(500, f"PostgreSQL error: {e}")


@app.get("/flights/stats", tags=["Flights"])
def get_stats(
    airline: Optional[str] = Query(None),
    origin:  Optional[str] = Query(None),
):
    from sqlalchemy import text
    conditions = []
    params: dict = {}

    if airline:
        conditions.append("operating_airline = :airline")
        params["airline"] = airline.upper()
    if origin:
        conditions.append("origin = :origin")
        params["origin"] = origin.upper()

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    sql = f"""
        SELECT operating_airline, origin, dest,
               total_flights, avg_dep_delay, delayed_count, delay_rate_pct,
               avg_carrier_delay, avg_weather_delay
        FROM gold.delay_summary
        {where}
        ORDER BY delay_rate_pct DESC
        LIMIT 200
    """
    try:
        with DBClients.pg().connect() as conn:
            rows = conn.execute(text(sql), params).mappings().all()
        return {"data": [dict(r) for r in rows]}
    except Exception as e:
        raise HTTPException(500, f"Stats error: {e}")


# ── Airports (PostgreSQL) ─────────────────────────────────────────────────
@app.get("/airports", tags=["Airports"])
def get_airports():
    from sqlalchemy import text
    try:
        with DBClients.pg().connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM public.airports ORDER BY iata")
            ).mappings().all()
        return {"data": [dict(r) for r in rows]}
    except Exception as e:
        raise HTTPException(500, f"Airports error: {e}")


@app.get("/airports/{iata}", tags=["Airports"])
def get_airport(iata: str):
    from sqlalchemy import text
    try:
        with DBClients.pg().connect() as conn:
            row = conn.execute(
                text("SELECT * FROM public.airports WHERE iata = :iata"),
                {"iata": iata.upper()}
            ).mappings().first()
        if not row:
            raise HTTPException(404, f"Airport {iata} not found")
        return dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Routes (PostgreSQL) ───────────────────────────────────────────────────
@app.get("/routes", tags=["Routes"])
def get_routes(
    min_flights: int = Query(10, description="Min flights on route"),
    max_delay:   Optional[float] = Query(None, description="Max avg delay"),
):
    from sqlalchemy import text
    conditions = [f"total_flights >= {min_flights}"]
    if max_delay:
        conditions.append(f"avg_dep_delay <= {max_delay}")
    where = "WHERE " + " AND ".join(conditions)
    sql = f"""
        SELECT origin, dest, total_flights, avg_dep_delay,
               delay_rate_pct, avg_distance
        FROM gold.delay_summary
        {where}
        ORDER BY total_flights DESC
        LIMIT 500
    """
    try:
        with DBClients.pg().connect() as conn:
            rows = conn.execute(text(sql)).mappings().all()
        return {"data": [dict(r) for r in rows]}
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Graph Routes (Neo4j) ──────────────────────────────────────────────────
@app.get("/routes/graph", tags=["Graph"])
def get_graph(limit: int = Query(100, le=500)):
    """Return nodes + edges for network visualization."""
    cypher = """
        MATCH (a:Airport)-[r:ROUTE]->(b:Airport)
        RETURN a.iata AS source, a.city AS source_city,
               b.iata AS target, b.city AS target_city,
               r.total_flights AS flights,
               r.avg_delay AS avg_delay,
               r.delay_rate AS delay_rate
        ORDER BY r.total_flights DESC
        LIMIT $limit
    """
    try:
        with DBClients.neo4j().session() as session:
            result = session.run(cypher, limit=limit)
            records = [dict(r) for r in result]

        nodes_map = {}
        edges = []
        for r in records:
            for key, city_key in [("source", "source_city"),
                                   ("target", "target_city")]:
                iata = r[key]
                if iata not in nodes_map:
                    nodes_map[iata] = {"id": iata, "city": r[city_key]}
            edges.append({
                "source":     r["source"],
                "target":     r["target"],
                "flights":    r["flights"],
                "avg_delay":  r["avg_delay"],
                "delay_rate": r["delay_rate"],
            })

        return {"nodes": list(nodes_map.values()), "edges": edges}
    except Exception as e:
        raise HTTPException(500, f"Neo4j error: {e}")


@app.get("/routes/path", tags=["Graph"])
def shortest_path(
    origin: str = Query(..., description="Origin IATA"),
    dest:   str = Query(..., description="Dest IATA"),
):
    """Find shortest path between two airports in the route graph."""
    cypher = """
        MATCH path = shortestPath(
            (a:Airport {iata: $origin})-[:ROUTE*..10]->(b:Airport {iata: $dest})
        )
        RETURN [n in nodes(path) | n.iata]  AS airports,
               [r in relationships(path) | r.avg_delay] AS delays,
               length(path) AS hops
    """
    try:
        with DBClients.neo4j().session() as session:
            result = session.run(cypher,
                                 origin=origin.upper(),
                                 dest=dest.upper())
            record = result.single()
        if not record:
            raise HTTPException(404,
                f"No path found between {origin} and {dest}")
        return {
            "airports":   record["airports"],
            "delays":     record["delays"],
            "hops":       record["hops"],
            "total_delay": sum(d or 0 for d in record["delays"]),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Neo4j error: {e}")


# ── Live Flights (MongoDB) ────────────────────────────────────────────────
@app.get("/live", tags=["Live"])
def get_live_flights(
    country: Optional[str] = Query(None),
    airport: Optional[str] = Query(None, min_length=3, max_length=3),
    max_age_seconds: int = Query(180, ge=30, le=1800),
    limit:   int = Query(200, le=500),
):
    """Latest OpenSky aircraft observations persisted in MongoDB.

    ``market_country`` is assigned by the collector's Saudi/UAE portfolio
    boundary, while ``nearest_airport`` is a proximity label. Neither field
    is an official airspace or flight-status classification.
    """
    try:
        from datetime import datetime, timedelta, timezone

        query = {
            "collected_at_dt": {
                "$gte": datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)
            }
        }
        if country:
            query["market_country"] = country
        if airport:
            query["nearest_airport"] = airport.upper()
        docs = list(
            DBClients.mongo()["live_flights"]
            .find(query, {"_id": 0, "collected_at_dt": 0})
            .sort("snapshot_time", -1)
            .limit(limit)
        )
        latest = max((doc.get("snapshot_at") for doc in docs), default=None)
        return {
            "data": docs,
            "count": len(docs),
            "last_updated": latest,
            "source": "OpenSky Network",
            "is_live": bool(docs),
            "scope_note": "Country uses a portfolio boundary; airport is the nearest supported gateway.",
        }
    except Exception as e:
        raise HTTPException(500, f"MongoDB error: {e}")


@app.post("/live", tags=["Live"])
def insert_live_flight(flight: dict):
    """Insert a new live flight record into MongoDB."""
    try:
        from datetime import datetime
        flight["inserted_at"] = datetime.utcnow().isoformat()
        result = DBClients.mongo()["live_flights"].insert_one(flight)
        return {"inserted_id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(500, f"MongoDB insert error: {e}")


# ── ML Prediction ─────────────────────────────────────────────────────────
@app.get("/model/gulf/status", tags=["ML"])
def gulf_model_status():
    """Return model-card metadata without exposing the serialized estimator."""
    bundle = get_gulf_model_bundle()
    if bundle is None:
        return {
            "available": False,
            "version": None,
            "reason": "Model artifact is not available",
        }
    metadata = dict(bundle["metadata"])
    metadata.update(gulf_model_reliability(metadata))
    return metadata


@app.post("/predict/gulf", response_model=GulfPredictionResponse, tags=["ML"])
def predict_gulf_delay(payload: GulfPredictionInput):
    """Score one transparent Saudi/UAE portfolio delay scenario."""
    bundle = get_gulf_model_bundle()
    if bundle is None:
        raise HTTPException(503, "Gulf delay model not loaded")
    if payload.origin == payload.destination:
        raise HTTPException(422, "Origin and destination must differ")
    if not 0 <= payload.departure_hour <= 23:
        raise HTTPException(422, "Departure hour must be between 0 and 23")

    features = pd.DataFrame([{
        "Operating_Airline": payload.airline,
        "Origin": payload.origin.upper(),
        "Dest": payload.destination.upper(),
        "DayOfWeek": payload.flight_date.strftime("%A"),
        "Distance": payload.distance,
        "Month": payload.flight_date.month,
        "DepartureHour": payload.departure_hour,
        "WindKmh": max(0, payload.wind_kmh),
        "PrecipitationMm": max(0, payload.precipitation_mm),
        "CloudCoverPct": min(100, max(0, payload.cloud_cover_pct)),
    }])[bundle["features"]]
    probability = float(bundle["model"].predict_proba(features)[0, 1])
    risk_band = "LOW" if probability < 0.30 else "MEDIUM" if probability < 0.60 else "HIGH"
    metadata = bundle["metadata"]
    return GulfPredictionResponse(
        delay_probability=probability,
        risk_band=risk_band,
        model_version=metadata["version"],
        algorithm=metadata["algorithm"],
        data_scope=metadata["data_scope"],
        limitations=metadata["limitations"],
    )
