"""
db_setup.py — DST Airlines Database Setup
Step 2: Creates and populates SQL (PostgreSQL) + MongoDB + Neo4j

Usage:
    python db_setup.py --db all          # setup all 3 databases
    python db_setup.py --db sql          # PostgreSQL only
    python db_setup.py --db mongo        # MongoDB only
    python db_setup.py --db neo4j        # Neo4j only
    python db_setup.py --db all --seed   # also insert sample data
"""

import os
import json
import logging
import argparse
import pandas as pd
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

# ── Connection config (secrets must be provided through environment variables) ─
PG_URL   = os.getenv("DATABASE_URL")
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017/")
NEO4J_URL = os.getenv("NEO4J_URL", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASS")

DATA_DIR = Path("collected_data")


# ═══════════════════════════════════════════════════════════════════════════
# PostgreSQL (SQL) — Fixed / reference data
# ═══════════════════════════════════════════════════════════════════════════
class PostgreSQLSetup:
    """
    Manages the PostgreSQL schema (Medallion architecture).
    Bronze → Silver → Gold layers.
    Fixed data: airports, airlines.
    Variable data: flights (bronze layer).
    """

    def __init__(self, url: str = PG_URL):
        if not url:
            raise ValueError("DATABASE_URL is required for PostgreSQL setup")
        try:
            from sqlalchemy import create_engine, text
            self.engine = create_engine(url)
            self.text   = text
            log.info("✅ PostgreSQL connection OK")
        except Exception as e:
            log.error(f"PostgreSQL connection failed: {e}")
            self.engine = None

    def create_schema(self):
        """Create all tables with medallion architecture."""
        if not self.engine:
            log.warning("Skipping PostgreSQL — no connection")
            return

        ddl = """
        -- ── Schemas ─────────────────────────────────────────────────
        CREATE SCHEMA IF NOT EXISTS bronze;
        CREATE SCHEMA IF NOT EXISTS silver;
        CREATE SCHEMA IF NOT EXISTS gold;

        -- ── Bronze: raw ingestion ────────────────────────────────────
        DROP TABLE IF EXISTS bronze.flights CASCADE;
        CREATE TABLE bronze.flights (
            flight_id                       SERIAL PRIMARY KEY,
            FlightDate                      DATE NOT NULL,
            Operating_Airline               VARCHAR(20) NOT NULL,
            Tail_Number                     VARCHAR(20),
            Flight_Number_Operating_Airline INT,
            OriginAirportID                 INT,
            Origin                          VARCHAR(10) NOT NULL,
            OriginCityName                  VARCHAR(100),
            DestAirportID                   INT,
            Dest                            VARCHAR(10) NOT NULL,
            DestCityName                    VARCHAR(100),
            DepDelay                        FLOAT,
            DepDel15                        BOOLEAN,
            ArrDelay                        FLOAT,
            ArrDel15                        BOOLEAN,
            Cancelled                       BOOLEAN DEFAULT FALSE,
            Diverted                        BOOLEAN DEFAULT FALSE,
            Distance                        FLOAT,
            DistanceGroup                   INT,
            CarrierDelay                    FLOAT,
            WeatherDelay                    FLOAT,
            NASDelay                        FLOAT,
            SecurityDelay                   FLOAT,
            LateAircraftDelay               FLOAT,
            ingested_at                     TIMESTAMP DEFAULT NOW()
        );

        DROP TABLE IF EXISTS bronze.weather CASCADE;
        CREATE TABLE bronze.weather (
            weather_id       SERIAL PRIMARY KEY,
            location_name    VARCHAR(100) NOT NULL,
            weather_date     DATE NOT NULL,
            temp             FLOAT,
            temp_min_c       FLOAT,
            temp_max_c       FLOAT,
            relative_humidity FLOAT,
            precipitation_mm  FLOAT,
            snow_mm           FLOAT,
            wind_speed_kmh    FLOAT,
            pressure_hpa      FLOAT,
            cloud_cover       FLOAT,
            ingested_at       TIMESTAMP DEFAULT NOW()
        );

        -- ── Reference tables (fixed data) ───────────────────────────
        DROP TABLE IF EXISTS public.airports CASCADE;
        CREATE TABLE public.airports (
            iata        VARCHAR(10) PRIMARY KEY,
            airport_id  INT,
            city        VARCHAR(100),
            country     VARCHAR(100) NOT NULL
        );

        DROP TABLE IF EXISTS public.airlines CASCADE;
        CREATE TABLE public.airlines (
            code  VARCHAR(20) PRIMARY KEY,
            name  VARCHAR(100)
        );

        -- ── Silver: joined & cleaned ─────────────────────────────────
        DROP VIEW IF EXISTS silver.flights_weather;
        CREATE VIEW silver.flights_weather AS
        SELECT
            f.flight_id,
            f.FlightDate,
            f.Operating_Airline,
            f.Origin,
            f.OriginCityName,
            f.Dest,
            f.DestCityName,
            f.Distance,
            f.DistanceGroup,
            f.DepDelay,
            f.DepDel15,
            f.Diverted,
            wo.temp             AS temp_origin,
            wo.wind_speed_kmh   AS wind_origin,
            wo.precipitation_mm AS precip_origin,
            wo.cloud_cover      AS cloud_origin,
            wd.temp             AS temp_dest,
            wd.wind_speed_kmh   AS wind_dest,
            wd.precipitation_mm AS precip_dest
        FROM bronze.flights f
        LEFT JOIN bronze.weather wo
            ON f.FlightDate = wo.weather_date
            AND f.OriginCityName = wo.location_name
        LEFT JOIN bronze.weather wd
            ON f.FlightDate = wd.weather_date
            AND f.DestCityName = wd.location_name;

        -- ── Gold: ML-ready aggregates ────────────────────────────────
        DROP VIEW IF EXISTS gold.delay_summary;
        CREATE VIEW gold.delay_summary AS
        SELECT
            Operating_Airline,
            Origin,
            Dest,
            COUNT(*)                                    AS total_flights,
            AVG(DepDelay)                               AS avg_dep_delay,
            SUM(CASE WHEN DepDel15 THEN 1 ELSE 0 END)  AS delayed_count,
            ROUND(AVG(CASE WHEN DepDel15 THEN 1.0 ELSE 0.0 END) * 100, 2) AS delay_rate_pct,
            AVG(CarrierDelay)                           AS avg_carrier_delay,
            AVG(WeatherDelay)                           AS avg_weather_delay,
            AVG(NASDelay)                               AS avg_nas_delay
        FROM bronze.flights
        WHERE Cancelled = FALSE
        GROUP BY Operating_Airline, Origin, Dest;
        """

        with self.engine.connect() as conn:
            for stmt in ddl.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(self.text(s))
            conn.commit()
        log.info("✅ PostgreSQL schema created (Bronze + Silver + Gold)")

    def seed_airports(self, csv_path: Path = DATA_DIR / "airports_iata.csv"):
        """Insert airport reference data."""
        if not self.engine or not csv_path.exists():
            log.warning(f"Airports CSV not found: {csv_path}")
            return
        df = pd.read_csv(csv_path)
        df.to_sql("airports", self.engine, if_exists="replace",
                  index=False, schema="public")
        log.info(f"✅ Airports seeded: {len(df)} rows")

    def seed_flights(self, csv_path: Path = DATA_DIR / "flights_clean.csv",
                     limit: int = 10000):
        """Insert flight data into bronze layer."""
        if not self.engine or not csv_path.exists():
            log.warning(f"Flights CSV not found: {csv_path}")
            return
        df = pd.read_csv(csv_path, nrows=limit)
        # Match column names to bronze table
        df.columns = [c.strip() for c in df.columns]
        df.to_sql("flights", self.engine, if_exists="append",
                  index=False, schema="bronze", chunksize=500)
        log.info(f"✅ Flights seeded: {len(df):,} rows → bronze.flights")

    def test_query(self):
        """Run a test query to verify everything works."""
        if not self.engine:
            return
        with self.engine.connect() as conn:
            result = conn.execute(
                self.text("SELECT COUNT(*) FROM bronze.flights")
            ).fetchone()
            log.info(f"   bronze.flights count: {result[0]:,}")


# ═══════════════════════════════════════════════════════════════════════════
# MongoDB — Variable / flexible data (live flights, API responses)
# ═══════════════════════════════════════════════════════════════════════════
class MongoDBSetup:
    """
    MongoDB stores variable/flexible data:
    - live_flights: real-time flight positions (from OpenSky)
    - api_responses: raw API JSON responses (audit trail)
    - delay_predictions: ML prediction logs
    """

    def __init__(self, url: str = MONGO_URL):
        try:
            from pymongo import MongoClient, ASCENDING, DESCENDING
            self.client = MongoClient(url, serverSelectionTimeoutMS=5000)
            self.client.server_info()  # test connection
            self.db = self.client["airlines_db"]
            self.ASCENDING  = ASCENDING
            self.DESCENDING = DESCENDING
            log.info("✅ MongoDB connection OK")
        except Exception as e:
            log.error(f"MongoDB connection failed: {e}")
            self.client = None

    def create_collections(self):
        """Create collections with indexes."""
        if not self.client:
            log.warning("Skipping MongoDB — no connection")
            return

        # ── live_flights ─────────────────────────────────────────────
        lf = self.db["live_flights"]
        lf.create_index([("callsign", self.ASCENDING)])
        lf.create_index([("collected_at", self.DESCENDING)])
        lf.create_index([("icao24", self.ASCENDING)])

        # ── api_responses ────────────────────────────────────────────
        ar = self.db["api_responses"]
        ar.create_index([("endpoint", self.ASCENDING)])
        ar.create_index([("fetched_at", self.DESCENDING)])

        # ── delay_predictions ────────────────────────────────────────
        dp = self.db["delay_predictions"]
        dp.create_index([("flight_date", self.DESCENDING)])
        dp.create_index([("origin", self.ASCENDING), ("dest", self.ASCENDING)])

        log.info("✅ MongoDB collections + indexes created")

    def seed_live_flights(self,
                          csv_path: Path = DATA_DIR / "live_flights.csv"):
        """Insert live flight data into MongoDB."""
        if not self.client or not csv_path.exists():
            # Insert a sample document so the collection isn't empty
            sample = {
                "icao24": "abc123", "callsign": "DLH001",
                "origin_country": "Germany",
                "latitude": 50.03, "longitude": 8.56,
                "baro_altitude": 10600, "velocity": 240.0,
                "on_ground": False,
                "collected_at": datetime.utcnow().isoformat(),
                "source": "sample",
            }
            self.db["live_flights"].insert_one(sample)
            log.info("✅ MongoDB seeded with sample live flight")
            return

        df = pd.read_csv(csv_path)
        docs = df.to_dict("records")
        self.db["live_flights"].insert_many(docs)
        log.info(f"✅ MongoDB live_flights: {len(docs)} documents inserted")

    def test_query(self):
        """Test MongoDB query."""
        if not self.client:
            return
        count = self.db["live_flights"].count_documents({})
        log.info(f"   MongoDB live_flights count: {count}")


# ═══════════════════════════════════════════════════════════════════════════
# Neo4j — Graph database for airport routes
# ═══════════════════════════════════════════════════════════════════════════
class Neo4jSetup:
    """
    Neo4j stores flight routes as a graph:
    (Airport)-[:ROUTE {flights, avg_delay, distance}]->(Airport)
    This lets us query things like:
    - "Shortest path from RUH to DXB"
    - "Which airports have the most delays?"
    - "Find all connecting airports between A and B"
    """

    def __init__(self, url: str = NEO4J_URL,
                 user: str = NEO4J_USER, password: str = NEO4J_PASS):
        if not password:
            raise ValueError("NEO4J_PASS is required for Neo4j setup")
        try:
            from neo4j import GraphDatabase
            self.driver = GraphDatabase.driver(url, auth=(user, password))
            self.driver.verify_connectivity()
            log.info("✅ Neo4j connection OK")
        except Exception as e:
            log.error(f"Neo4j connection failed: {e}")
            self.driver = None

    def create_schema(self):
        """Create constraints and indexes."""
        if not self.driver:
            log.warning("Skipping Neo4j — no connection")
            return

        queries = [
            "CREATE CONSTRAINT airport_iata IF NOT EXISTS FOR (a:Airport) REQUIRE a.iata IS UNIQUE",
            "CREATE INDEX route_delay IF NOT EXISTS FOR ()-[r:ROUTE]-() ON (r.avg_delay)",
        ]
        with self.driver.session() as session:
            for q in queries:
                try:
                    session.run(q)
                except Exception as e:
                    log.warning(f"Constraint warning (ok if exists): {e}")
        log.info("✅ Neo4j constraints + indexes created")

    def seed_routes(self, csv_path: Path = DATA_DIR / "flights_clean.csv",
                    limit: int = 50000):
        """Build airport graph from flight data."""
        if not self.driver:
            return

        if csv_path.exists():
            df = pd.read_csv(csv_path, nrows=limit)
            df.columns = [c.strip() for c in df.columns]
        else:
            # Sample data if CSV not available
            df = pd.DataFrame({
                "Origin": ["RUH", "DXB", "JED", "AUH", "DMM"],
                "Dest":   ["DXB", "RUH", "AUH", "JED", "SHJ"],
                "OriginCityName": ["Riyadh", "Dubai", "Jeddah", "Abu Dhabi", "Dammam"],
                "DestCityName":   ["Dubai", "Riyadh", "Abu Dhabi", "Jeddah", "Sharjah"],
                "Distance": [545, 545, 1000, 1000, 530],
                "DepDelay": [12.5, 8.3, 15.2, 9.1, 11.7],
                "DepDel15": [True, False, True, False, True],
            })

        # Aggregate by route
        route_cols = ["Origin", "Dest", "OriginCityName", "DestCityName"]
        agg_cols = {}
        if "Distance" in df.columns:
            agg_cols["Distance"] = "mean"
        if "DepDelay" in df.columns:
            agg_cols["DepDelay"] = "mean"
        if "DepDel15" in df.columns:
            agg_cols["DepDel15"] = ["count", "sum"]

        routes = df.groupby(route_cols).agg(agg_cols).reset_index()
        routes.columns = ["_".join(c).strip("_") for c in routes.columns]

        cypher_airport = """
        MERGE (a:Airport {iata: $iata})
        SET a.city = $city
        RETURN a
        """
        cypher_route = """
        MATCH (o:Airport {iata: $origin})
        MATCH (d:Airport {iata: $dest})
        MERGE (o)-[r:ROUTE]->(d)
        SET r.total_flights = $flights,
            r.avg_delay     = $avg_delay,
            r.avg_distance  = $distance,
            r.delay_rate    = $delay_rate
        """

        with self.driver.session() as session:
            # Create airport nodes
            airports_done = set()
            for _, row in routes.iterrows():
                for iata_col, city_col in [("Origin", "OriginCityName"),
                                            ("Dest", "DestCityName")]:
                    iata = row.get(iata_col, "")
                    city = row.get(city_col, "")
                    if iata and iata not in airports_done:
                        session.run(cypher_airport,
                                    iata=str(iata), city=str(city))
                        airports_done.add(iata)

            # Create route relationships
            count = 0
            for _, row in routes.iterrows():
                flights = int(row.get("DepDel15_count", 1))
                delayed = int(row.get("DepDel15_sum", 0))
                avg_delay = float(row.get("DepDelay_mean", 0) or 0)
                distance  = float(row.get("Distance_mean", 0) or 0)
                delay_rate = round(delayed / flights * 100, 2) if flights else 0

                session.run(cypher_route,
                            origin=str(row["Origin"]),
                            dest=str(row["Dest"]),
                            flights=flights,
                            avg_delay=avg_delay,
                            distance=distance,
                            delay_rate=delay_rate)
                count += 1

        log.info(f"✅ Neo4j: {len(airports_done)} airports, {count} routes created")

    def test_query(self):
        """Run a sample graph query."""
        if not self.driver:
            return
        with self.driver.session() as session:
            result = session.run("""
                MATCH (a:Airport)-[r:ROUTE]->(b:Airport)
                RETURN a.iata, b.iata, r.avg_delay
                ORDER BY r.avg_delay DESC LIMIT 5
            """)
            log.info("   Top 5 delayed routes (Neo4j):")
            for rec in result:
                log.info(f"   {rec['a.iata']} → {rec['b.iata']} | "
                         f"avg delay: {rec['r.avg_delay']:.1f} min")

    def close(self):
        if self.driver:
            self.driver.close()


# ═══════════════════════════════════════════════════════════════════════════
# Main orchestrator
# ═══════════════════════════════════════════════════════════════════════════
class DatabaseOrchestrator:

    def __init__(self, target: str, seed: bool = False):
        self.target = target
        self.seed   = seed

    def run(self):
        log.info("=" * 60)
        log.info("DST Airlines — Database Setup")
        log.info(f"Target: {self.target} | Seed: {self.seed}")
        log.info("=" * 60)

        # ── PostgreSQL ───────────────────────────────────────────────
        if self.target in ("sql", "all"):
            pg = PostgreSQLSetup()
            pg.create_schema()
            if self.seed:
                pg.seed_airports()
                pg.seed_flights()
                pg.test_query()

        # ── MongoDB ──────────────────────────────────────────────────
        if self.target in ("mongo", "all"):
            mg = MongoDBSetup()
            mg.create_collections()
            if self.seed:
                mg.seed_live_flights()
                mg.test_query()

        # ── Neo4j ────────────────────────────────────────────────────
        if self.target in ("neo4j", "all"):
            n4 = Neo4jSetup()
            n4.create_schema()
            if self.seed:
                n4.seed_routes()
                n4.test_query()
            n4.close()

        log.info("=" * 60)
        log.info("Database setup complete ✅")


# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DST Airlines DB Setup")
    parser.add_argument("--db",   choices=["sql", "mongo", "neo4j", "all"],
                        default="all")
    parser.add_argument("--seed", action="store_true",
                        help="Also insert sample/collected data")
    args = parser.parse_args()

    orchestrator = DatabaseOrchestrator(target=args.db, seed=args.seed)
    orchestrator.run()
