# ✈ DST Airlines — Flight Delay Analytics Platform

> **DataScientest · LIORA · B2C DataOps Bootcamp · 2026**

![Docker](https://img.shields.io/badge/Docker-2CA5E0?style=flat&logo=docker&logoColor=white)
![Kubernetes](https://img.shields.io/badge/Kubernetes-326CE5?style=flat&logo=kubernetes&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=flat&logo=postgresql&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-4EA94B?style=flat&logo=mongodb&logoColor=white)
![Neo4j](https://img.shields.io/badge/Neo4j-008CC1?style=flat&logo=neo4j&logoColor=white)

---

## 📋 Table of Contents

- [Project Overview](#project-overview)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Docker Setup](#docker-setup)
- [Kubernetes Deployment](#kubernetes-deployment)
- [CI/CD Pipeline](#cicd-pipeline)
- [Infrastructure as Code](#infrastructure-as-code)
- [Monitoring](#monitoring)
- [Security](#security)
- [Disaster Recovery](#disaster-recovery)
- [Team](#team)

---

## 🎯 Project Overview

DST Airlines is a full **data engineering and analytics platform** that collects, stores, analyzes, and visualizes US domestic flight delay data using real flight data covering **560,352 flights from 2018 to 2024**.

### What Does It Do?

| Feature | Description |
|---------|-------------|
| ✈ **Flight Analytics** | Analyze delay patterns by airline, route, airport |
| 🤖 **ML Prediction** | Predict flight delays using Logistic + Linear Regression |
| 📊 **Dashboard** | 7-page interactive Dash dashboard |
| 🌦 **Live Weather** | Real-time weather for 346 US airports |
| 🕸 **Route Graph** | Neo4j shortest path between airports |
| 🗄 **3 Databases** | PostgreSQL + MongoDB + Neo4j |

### Key Numbers

| Metric | Value |
|--------|-------|
| Total flights in database | 560,352 |
| Delayed flights (> 15 min) | ~28% |
| API endpoints | 16 |
| Dashboard pages | 7 |
| Unit tests | 81 (all passing ✅) |
| Docker containers | 7 |
| Airport coordinates | 346 |

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.11 · FastAPI · Uvicorn |
| **Dashboard** | Dash · Plotly · Dash Bootstrap |
| **ML** | scikit-learn (Logistic + Linear Regression) |
| **Databases** | PostgreSQL 16 · MongoDB 7 · Neo4j 5 |
| **Containerization** | Docker · Docker Compose |
| **Orchestration** | Kubernetes (Minikube) |
| **CI/CD** | GitHub Actions |
| **IaC** | Terraform |
| **Monitoring** | Prometheus + Grafana |
| **Security** | Trivy · Kubernetes Secrets |
| **Weather API** | Open-Meteo (free, no key needed) |

---

## 📁 Project Structure

```
dst-airlines-DataOps/
├── api/
│   ├── main.py              # FastAPI — 16 REST endpoints
│   ├── Dockerfile           # Production container
│   ├── Dockerfile.dev       # Development container (with --reload)
│   ├── .dockerignore
│   └── requirements.txt
├── dashboard/
│   ├── app.py               # Main Dash app (OOP — 7 pages)
│   ├── charts.py            # Plotly chart factory
│   ├── data.py              # Data layer (PostgreSQL)
│   ├── weather.py           # Live weather (Open-Meteo)
│   ├── train_models.py      # ML model training
│   ├── Dockerfile
│   └── .dockerignore
├── database/
│   ├── db_setup.py          # PostgreSQL + MongoDB + Neo4j setup
│   └── sql/init.sql         # Schema (Bronze/Silver/Gold layers)
├── k8s/                     # Kubernetes manifests
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── secret.yaml
│   ├── postgres-deployment.yaml
│   ├── mongo-deployment.yaml
│   ├── neo4j-deployment.yaml
│   ├── api-deployment.yaml
│   ├── api-service.yaml
│   ├── dashboard-deployment.yaml
│   └── dashboard-service.yaml
├── docker-compose.yml       # Main compose file
├── docker-compose.dev.yml   # Development environment
├── docker-compose.prod.yml  # Production environment
├── .env.dev                 # Development variables (not in git)
├── .env.prod                # Production variables (not in git)
├── trivy-report-api.json    # Security scan report
├── trivy-report-dashboard.json
├── SECURITY.md              # Security documentation
├── DEPLOYMENT.md            # Deployment guide
└── README.md
```

---

## 🚀 Quick Start

### Prerequisites

- Docker Desktop
- Git
- Python 3.11+

### 1. Clone the Repository

```bash
git clone https://github.com/kboroz/dst-airlines-DataOps.git
cd dst-airlines-DataOps
git checkout dev-ali
```

### 2. Run with Docker Compose

```bash
# Development
docker compose -f docker-compose.dev.yml --env-file .env.dev up -d

# Production
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
```

### 3. Access the Application

| Service | URL | Credentials |
|---------|-----|-------------|
| Dashboard | http://localhost:8050 | — |
| API Docs | http://localhost:8000/docs | — |
| pgAdmin | http://localhost:5050 | admin@airlines.com / see .env |
| Mongo Express | http://localhost:8081 | — |
| Neo4j Browser | http://localhost:7474 | neo4j / see .env |

---

## 🐳 Docker Setup

### Images on Docker Hub

```bash
docker pull alidoghan/dst-airlines-api:v1.0
docker pull alidoghan/dst-airlines-dashboard:v1.0
```

### Build Locally

```bash
# Production
docker build -t dst-airlines-api:v1.0 ./api

# Development
docker build -f api/Dockerfile.dev -t dst-airlines-api:dev ./api
```

### Environment Differences

| Setting | Development | Production |
|---------|-------------|------------|
| API reload | ✅ Enabled | ❌ Disabled |
| Debug mode | true | false |
| Volume mounts | Yes (live code) | No |
| Compose file | docker-compose.dev.yml | docker-compose.prod.yml |

---

## ☸ Kubernetes Deployment

### Prerequisites

```bash
minikube start --driver=docker
```

### Deploy All Resources

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/postgres-deployment.yaml
kubectl apply -f k8s/mongo-deployment.yaml
kubectl apply -f k8s/neo4j-deployment.yaml
kubectl apply -f k8s/api-deployment.yaml
kubectl apply -f k8s/api-service.yaml
kubectl apply -f k8s/dashboard-deployment.yaml
kubectl apply -f k8s/dashboard-service.yaml
```

### Check Status

```bash
kubectl get pods -n dst-airlines
kubectl get services -n dst-airlines
```

### Expected Output

```
NAME                         READY   STATUS    RESTARTS   AGE
api-xxx                      1/1     Running   0          1m
dashboard-xxx                1/1     Running   0          1m
db-xxx                       1/1     Running   0          2m
mongo-xxx                    1/1     Running   0          2m
neo4j-xxx                    1/1     Running   0          2m
```

### Remove Everything

```bash
kubectl delete namespace dst-airlines
```

---

## 🔄 CI/CD Pipeline

> Implemented by Hassan Salam using GitHub Actions

*[To be completed — add pipeline details here]*

---

## 🏗 Infrastructure as Code

> Implemented by Fabian Schilling using Terraform

*[To be completed — add Terraform details here]*

---

## 📊 Monitoring

> Implemented by Kristian Boroz using Prometheus + Grafana

*[To be completed — add monitoring details here]*

---

## 🔒 Security

See [SECURITY.md](./SECURITY.md) for full security documentation.

### Implemented Controls

| Control | Status | Description |
|---------|--------|-------------|
| Container Image Scanning (Trivy) | ✅ Done | Both images scanned, reports saved |
| Secrets Management | ✅ Done | .env files, Kubernetes Secrets |
| No Hard-coded Credentials | ✅ Done | All credentials externalized |

### Quick Scan

```bash
trivy image alidoghan/dst-airlines-api:v1.0
trivy image alidoghan/dst-airlines-dashboard:v1.0
```

---

## 🆘 Disaster Recovery

> Implemented by Fabian Schilling + Hassan Salam

*[To be completed — add backup strategy and recovery procedures here]*

---

## 👥 Team

| Member | Role | GitHub |
|--------|------|--------|
| Ali Doghan | Docker · Kubernetes · Security | [@Ali-Doghan](https://github.com/Ali-Doghan) |
| Hassan Salam | CI/CD Pipeline | — |
| Fabian Schilling | IaC · Terraform · DR | — |
| Kristian Boroz | Testing · Monitoring · Team Lead | [@kboroz](https://github.com/kboroz) |

**Supervisor:** Durrell Gemuh · DataScientest LIORA Program

---

## 📄 License

This project is part of the DataScientest B2C DataOps Bootcamp curriculum.

---

*✈ DST Airlines — Built with ❤ by Group 1 · DataScientest 2026*
