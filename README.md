# DST Airlines DataOps Platform

A production-ready data pipeline and analytics dashboard for airline flight data.

## 🎯 MVP Features

- **PostgreSQL Bronze Layer**: 560K+ flights from 22 origins to 196 destinations
- **FastAPI REST API**: 4 operational endpoints with real-time data aggregation
- **Dash Analytics Dashboard**: Interactive charts, filters, airline/route analytics
- **Weather Integration**: OpenMeteo API for real-time weather correlation
- **Multi-Database**: PostgreSQL (bronze), MongoDB (staging), Neo4j (graph analytics)
- **Containerized**: Docker Compose with 7 microservices

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose (v2+)
- Python 3.11+ (for local dev only)
- Git

### Run Everything
```bash
<<<<<<< HEAD
git clone https://github.com/kboroz/dst-airlines-DataOps
cd dst-airlines-DataOps
docker compose up -d
```
=======
git clone https://github.com/<your-username>/dst-airlines-DataOps.git
cd dst-airlines-DataOps/dst-airlines-DataOps
docker compose up -d
>>>>>>> 0d0143b9 (Initial MVP commit: FastAPI backend, Dash dashboard, Docker Compose orchestration, PostgreSQL bronze layer)

┌─────────────────────────────────────────────────────────────────┐
│                      Dash Frontend (8050)                       │
│              Interactive Charts & Filters (Python)              │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                 FastAPI Backend (8000)                          │
│    /api/airlines  /api/origins  /api/destinations               │
│    /api/dashboard-stats  /api/flights  /api/weather             │
└──────────────────────────┬──────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
    ┌───▼──┐          ┌───▼──┐          ┌───▼──┐
    │ PG   │          │Mongo │          │Neo4j │
    │8432  │          │27017 │          │7687  │
    └──────┘          └──────┘          └──────┘
    Bronze Layer      Staging           Graph
    560K flights      Raw Data          Relationships
dst-airlines-DataOps/
├── api/
│   ├── main.py                 # FastAPI app (228 lines of endpoints)
│   ├── requirements.txt         # Dependencies: FastAPI, SQLAlchemy, Pydantic
│   ├── Dockerfile
│   └── db_init.sql            # PostgreSQL schema + initial data
│
├── dashboard/
│   ├── app.py                 # Dash application (interactive UI)
│   ├── data.py                # API client + data transformations
│   ├── charts.py              # Plotly chart definitions
│   ├── weather.py             # Weather data handler
│   ├── train_models.py        # ML model training (optional)
│   ├── assets/                # Custom CSS/JS
│   └── Dockerfile
│
├── docker-compose.yml          # All 7 services orchestration
├── .env.example               # Environment variables template
└── README.md                  # This file
-- Loaded from flight_data.parquet (manual ingestion)
SELECT COUNT(*) FROM flights;  -- 560,234 rows
SELECT COUNT(DISTINCT airline) FROM flights;  -- 22 airlines
SELECT COUNT(DISTINCT destination) FROM flights;  -- 196 destinations
// For future: raw event ingestion, schema flexibility
db.flights.insertOne({airline, origin, destination, delay_minutes, delay_reason, timestamp})
// For future: route network analysis, airline relationships
CREATE (a:Airline {name}) -[:OPERATES]-> (r:Route {origin, destination})
curl http://localhost:8000/api/airlines
# Response: ["Southwest", "Delta", "United", ...]
curl "http://localhost:8000/api/origins?airline=Delta"
curl "http://localhost:8000/api/destinations?origin=LAX&airline=United"
curl "http://localhost:8000/api/dashboard-stats?airline=Southwest&origin=DEN"
# Run all tests
cd api/
python -m pytest --collect-only

# Run specific test
python -m pytest tests/test_api.py::test_airlines_returns_list -v
# .env
DATABASE_URL=postgresql://airlines:airlines_password@db:5432/airlines_db
MONGO_URL=mongodb://mongo_airlines:27017
NEO4J_URL=bolt://neo4j_airlines:7687
API_URL=http://api:8000  # For dashboard
DEBUG=false
docker compose ps
# STATUS column shows: "Up X hours (healthy)" ✅
docker compose logs -f api          # API logs
docker compose logs -f dashboard    # Dashboard logs
docker compose logs -f db           # PostgreSQL logs

---

### Step 1.2: Create `.env.example` for reproducibility

```bash
cat > .env.example << 'EOF'
# PostgreSQL Configuration
POSTGRES_USER=airlines
POSTGRES_PASSWORD=airlines_password
POSTGRES_DB=airlines_db
DATABASE_URL=postgresql://airlines:airlines_password@db:5432/airlines_db

# MongoDB
MONGO_INITDB_ROOT_USERNAME=root
MONGO_INITDB_ROOT_PASSWORD=root_password
MONGO_URL=mongodb://mongo_airlines:27017

# Neo4j
NEO4J_AUTH=neo4j/password
NEO4J_URL=bolt://neo4j_airlines:7687

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_URL=http://api:8000

# Dashboard
DASHBOARD_PORT=8050

# PgAdmin
PGADMIN_DEFAULT_EMAIL=admin@admin.com
PGADMIN_DEFAULT_PASSWORD=admin

# Debug Mode
DEBUG=false
LOG_LEVEL=info
