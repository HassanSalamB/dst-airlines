# Deployment & Operations Guide

## Local Development

### Start All Services
```bash
docker compose up -d
docker compose ps  # Verify all healthy
# All services
docker compose logs -f

# Specific service
docker compose logs -f api
docker compose logs -f dashboard
docker compose logs -f db
docker compose restart api
docker compose restart dashboard
# Find process using port 8000
lsof -i :8000

# Kill it
kill -9 <PID>

# Or use different port in docker-compose.yml
docker exec pg_airlines pg_dump -U airlines airlines_db > backup.sql
docker exec -i pg_airlines psql -U airlines airlines_db < backup.sql
# Count records
docker exec pg_airlines psql -U airlines -d airlines_db -c "SELECT COUNT(*) FROM flights;"

# List airlines
docker exec pg_airlines psql -U airlines -d airlines_db -c "SELECT DISTINCT airline FROM flights LIMIT 10;"
docker exec pg_airlines psql -U airlines -d airlines_db << 'SQL'
CREATE INDEX idx_flights_airline ON flights(airline);
CREATE INDEX idx_flights_origin ON flights(origin);
CREATE INDEX idx_flights_destination ON flights(destination);
CREATE INDEX idx_flights_date ON flights(date);
SQL
docker compose ps
# All should show: "Up X hours (healthy)"
docker system df
docker image prune -a --filter "until=240h"

---

## **PHASE 2: Initialize Git & Push** (5 mins)

### Step 2.1: Set up Git (if not already)

```bash
cd ~/dst-airlines-DataOps/dst-airlines-DataOps

# Check if git is initialized
git status

# If not, initialize
git init

# Configure git (use your info)
git config user.name "Your Name"
git config user.email "your.email@example.com"
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
venv/
env/
ENV/

# IDEs
.vscode/
.idea/
*.swp
*.swo
*~
.DS_Store

# Environment
.env
.env.local
.env.*.local

# Docker
.dockerignore

# Logs
*.log
logs/

# Cache
.pytest_cache/
.mypy_cache/
.coverage

# Data (optional - keep parquet files?)
# *.parquet
# *.csv

# Secrets
secrets.json
*.pem
*.key
