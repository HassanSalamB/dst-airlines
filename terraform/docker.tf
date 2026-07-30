# ─── NETWORK ────────────────────────────────────────────
resource "docker_network" "dst_network" {
  name = "dst_airlines_network"
}

# ─── VOLUMES ────────────────────────────────────────────
resource "docker_volume" "pg_data" {
  name = "pg_data"
}

resource "docker_volume" "mongo_data" {
  name = "mongo_data"
}

resource "docker_volume" "neo4j_data" {
  name = "neo4j_data"
}

# ─── POSTGRESQL ─────────────────────────────────────────
resource "docker_container" "postgres" {
  name  = "pg_airlines"
  image = "postgres:16-alpine"

  env = [
    "POSTGRES_USER=airlines",
    "POSTGRES_PASSWORD=${var.postgres_password}",
    "POSTGRES_DB=airlines_db"
  ]

  ports {
    internal = 5432
    external = 5432
  }

  volumes {
    volume_name    = docker_volume.pg_data.name
    container_path = "/var/lib/postgresql/data"
  }

  networks_advanced {
    name = docker_network.dst_network.name
  }

  restart = "always"
}

# ─── MONGODB ────────────────────────────────────────────
resource "docker_container" "mongo" {
  name  = "mongo_airlines"
  image = "mongo:7"

  ports {
    internal = 27017
    external = 27017
  }

  volumes {
    volume_name    = docker_volume.mongo_data.name
    container_path = "/data/db"
  }

  networks_advanced {
    name = docker_network.dst_network.name
  }

  restart = "always"
}

# ─── NEO4J ──────────────────────────────────────────────
resource "docker_container" "neo4j" {
  name  = "neo4j_airlines"
  image = "neo4j:5"

  env = [
    "NEO4J_AUTH=neo4j/${var.neo4j_password}",
    "NEO4J_PLUGINS=[\"apoc\"]",
    "NEO4J_server_config_strict__validation_enabled=false"
  ]

  ports {
    internal = 7474
    external = 7474
  }

  ports {
    internal = 7687
    external = 7687
  }

  volumes {
    volume_name    = docker_volume.neo4j_data.name
    container_path = "/data"
  }

  networks_advanced {
    name = docker_network.dst_network.name
  }

  restart = "always"
}

# ─── API ────────────────────────────────────────────────
resource "docker_container" "api" {
  name  = "airlines_api"
  image = "alidoghan/dst-airlines-api:v1.0"

  env = [
    "DATABASE_URL=postgresql+psycopg2://airlines:${var.postgres_password}@pg_airlines:5432/airlines_db",
    "MONGO_URL=mongodb://mongo_airlines:27017/",
    "NEO4J_URL=bolt://neo4j_airlines:7687",
    "NEO4J_USER=neo4j",
    "NEO4J_PASS=${var.neo4j_password}",
    "MODEL_PATH=/app/logistic_regression.pkl"
  ]

  ports {
    internal = 8000
    external = 8000
  }

  networks_advanced {
    name = docker_network.dst_network.name
  }

  restart = "always"

  depends_on = [
    docker_container.postgres,
    docker_container.mongo
  ]
}

# ─── DASHBOARD ──────────────────────────────────────────
resource "docker_container" "dashboard" {
  name  = "airlines_dashboard"
  image = "alidoghan/dst-airlines-dashboard:v1.0"

  env = [
    "API_URL=http://airlines_api:8000",
    "DATABASE_URL=postgresql+psycopg2://airlines:${var.postgres_password}@pg_airlines:5432/airlines_db"
  ]

  ports {
    internal = 8050
    external = 8050
  }

  networks_advanced {
    name = docker_network.dst_network.name
  }

  restart = "always"

  depends_on = [
    docker_container.api
  ]
}