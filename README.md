# ✈ DST Airlines — Flight Delay Analytics Platform

> **Data Engineering Project | DataScientest | Feb 2026 Cohort**

![Python](https://img.shields.io/badge/Python-3.11-blue)
![Dash](https://img.shields.io/badge/Dash-2.17-cyan)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue)
![MongoDB](https://img.shields.io/badge/MongoDB-7-green)
![Neo4j](https://img.shields.io/badge/Neo4j-5-orange)
![Docker](https://img.shields.io/badge/Docker-Compose-blue)
![ML](https://img.shields.io/badge/ML-Scikit--Learn-yellow)
![Weather](https://img.shields.io/badge/Weather-Open--Meteo-lightblue)

---

## What Is This Project?

DST Airlines is a full data engineering platform that collects, stores, analyzes, and visualizes US domestic flight delay data. It uses **real flight data (560,352 flights, 2018–2024)** and connects three different databases to a live interactive dashboard and REST API.

The platform goes beyond basic analytics — it includes a **Machine Learning delay prediction model**, **real-time live weather integration**, an **interactive US airport map**, and a **Neo4j graph-based route finder**.

---

## Quick Start

```bash
git clone https://github.com/DataScientest-Studio/dst-airlines-DataOps
cd dst-airlines-DataOps
docker-compose up -d
```

| Service | URL | Credentials |
|---------|-----|-------------|
| **Dashboard** | http://localhost:8050 | — |
| **API Docs** | http://localhost:8000/docs | — |
| **pgAdmin** | http://localhost:5050 | admin@airlines.com / airlines123 |
| **Mongo Express** | http://localhost:8081 | — |
| **Neo4j Browser** | http://localhost:7474 | neo4j / airlines123 |

---

## Architecture

```
Kaggle CSV (560K real US flights 2018-2024)
        ↓
  [ collector.py ]              ← Step 1: Data Collection + Cleaning
        ↓
┌──────────────────────────────────────────────────────┐
│  PostgreSQL  — Bronze → Silver → Gold (Medallion)    │
│  MongoDB     — Live flights + API responses           │  ← Step 2: Data Modeling
│  Neo4j       — Airport route graph (346 nodes)        │
└──────────────────────────────────────────────────────┘
        ↓
  [ FastAPI :8000 ]             ← Step 3: REST API (11 endpoints)
        ↓
  [ Dash Dashboard :8050 ]      ← Step 3: 7-page Interactive Dashboard
  ├── ML Model (scikit-learn)   ← Logistic + Linear Regression
  ├── Weather API (Open-Meteo)  ← Real-time live weather
  └── Neo4j Graph Queries       ← Shortest path algorithm
        ↓
  [ Docker Compose ]            ← Step 4: 7 containers, one command
```

---

## Project Structure

```
FEB26-BDE-AIRLINES/
├── api/
│   ├── main.py              ← FastAPI — 11 REST endpoints
│   ├── Dockerfile
│   └── requirements.txt
├── collector/
│   └── collector.py         ← Data collection (Kaggle CSV + OpenSky API)
├── dashboard/
│   ├── app.py               ← Main Dash app (OOP — 2 classes, 7 pages)
│   ├── charts.py            ← Plotly chart factory (OOP — 10 chart methods)
│   ├── data.py              ← Data layer (PostgreSQL → mock fallback)
│   ├── weather.py           ← Live weather from Open-Meteo API (346 airports)
│   ├── train_models.py      ← ML model training script
│   ├── Dockerfile
│   └── assets/
│       └── custom.css       ← Professional aviation dark theme
├── database/
│   ├── db_setup.py          ← PostgreSQL + MongoDB + Neo4j setup
│   └── sql/
│       └── init.sql         ← Schema (Bronze/Silver/Gold layers)
├── docker-compose.yml       ← All 7 services
└── README.md
```

---

## Databases

### PostgreSQL — Medallion Architecture
| Layer | Table / View | Description |
|-------|-------------|-------------|
| Bronze | `bronze.flights` | Raw flight data — 560,352 rows exactly as from CSV |
| Bronze | `bronze.weather` | Raw weather data per city |
| Silver | `silver.flights_weather` | Flights joined with weather — ready for analysis |
| Gold | `gold.delay_summary` | Aggregated stats per airline/route — ready for ML |
| Public | `airports`, `airlines` | Reference tables |

### MongoDB — Flexible / Live Data
- `live_flights` — real-time flight positions from OpenSky Network API
- `api_responses` — raw API responses saved for audit
- `delay_predictions` — log of all ML predictions made

### Neo4j — Airport Route Graph
```cypher
(Airport {iata, city})-[:ROUTE {total_flights, avg_delay, delay_rate}]->(Airport)
```
- **346** airport nodes
- **5,167** route relationships
- Supports: shortest path, most connected airports, route delay analysis

---

## Dashboard Pages (7 Pages)

| Page | What It Shows |
|------|--------------|
| **Overview** | 6 KPI cards, monthly trend, day-of-week analysis, delay distribution, top 10 delayed routes |
| **Airlines** | Delay rate per airline, delay causes breakdown (carrier/weather/NAS/security/late aircraft) |
| **Routes** | Heatmap of top 20 busiest airports + busiest routes bubble chart |
| **Trends** | Monthly delay trend + most delayed routes with exact minutes |
| **⚡ Risk Analyzer** | ML prediction + live weather + risk gauge + 4 stats cards |
| **🗺 Airport Map** | Interactive US map — bubble size = flight volume, color = delay rate |
| **🕸 Route Graph** | Neo4j shortest path finder between any two airports |

---

## Machine Learning

- **Algorithm:** Logistic Regression (delay yes/no) + Linear Regression (delay minutes)
- **Training data:** 100,000 real flights from PostgreSQL
- **Features:** Airline, Origin, Destination, Distance
- **Output:** Delay probability % + expected delay in minutes
- **Storage:** `/app/models.pkl` (pickle format)

To retrain the model:
```bash
docker exec airlines_dashboard python3 /app/train_models.py
```

---

## Live Weather Integration

The **Risk Analyzer** page fetches real-time weather automatically using the **Open-Meteo API** (free, no API key needed).

- Coverage: 346 US airports with exact coordinates
- Data: Temperature, wind speed, precipitation, cloud cover
- Updates: Every time you select an airport

---

## API Endpoints

| Method | Endpoint | Database | Description |
|--------|----------|----------|-------------|
| GET | `/` | — | Health check |
| GET | `/flights` | PostgreSQL | Get flights with filters |
| GET | `/flights/stats` | PostgreSQL | Aggregated delay stats |
| GET | `/airports` | PostgreSQL | List all airports |
| GET | `/airports/{iata}` | PostgreSQL | Single airport info |
| GET | `/routes` | PostgreSQL | Routes with delay stats |
| GET | `/routes/graph` | Neo4j | Graph data (nodes + edges) |
| GET | `/routes/path` | Neo4j | Shortest path between airports |
| GET | `/live` | MongoDB | Current live flight positions |
| POST | `/live` | MongoDB | Add new live flight record |
| POST | `/predict` | ML Model | Predict flight delay |

---

## Key Numbers

| Metric | Value |
|--------|-------|
| Total flights in PostgreSQL | 560,352 |
| Delayed flights (> 15 min) | ~28% |
| Airports in Neo4j | 346 |
| Routes in Neo4j | 5,167 |
| Airport coordinates (weather) | 346 |
| API endpoints | 11 |
| Dashboard pages | 7 |
| Docker containers | 7 |
| ML training rows | 100,000 |

---

## Team

| Member | Role |
|--------|------|
| **Ali Doghan** | Dashboard (7 pages, OOP), ML models, Neo4j graph, live weather API, Docker setup, documentation |
| **Adam Bonwitt** | Data collection, database design, weather data collection, bronze layer population |
| **Timo** | Docker Compose, PostgreSQL schema, FastAPI base setup, README |
| **Fabian K** | ML model pipeline (Logistic Regression), prediction endpoint, model evaluation |

**Mentor:** Antoine F
**Program:** Data Engineer — DataScientest
**Cohort:** February 2026
