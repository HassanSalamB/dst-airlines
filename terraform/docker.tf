# Images are managed explicitly so Terraform pulls immutable versions before
# creating containers on either a local or SSH-connected Docker host.
resource "docker_image" "postgres" {
  name         = "postgres:16-alpine"
  keep_locally = true
}

resource "docker_image" "mongo" {
  name         = "mongo:7"
  keep_locally = true
}

resource "docker_image" "neo4j" {
  name         = "neo4j:5"
  keep_locally = true
}

resource "docker_image" "api" {
  name         = var.api_image
  keep_locally = true
}

resource "docker_image" "dashboard" {
  name         = var.dashboard_image
  keep_locally = true
}

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
  image = docker_image.postgres.image_id

  env = [
    "POSTGRES_USER=airlines",
    "POSTGRES_PASSWORD=${var.postgres_password}",
    "POSTGRES_DB=airlines_db"
  ]

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
  image = docker_image.mongo.image_id

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
  image = docker_image.neo4j.image_id

  env = [
    "NEO4J_AUTH=neo4j/${var.neo4j_password}",
    "NEO4J_PLUGINS=[\"apoc\"]",
    "NEO4J_server_config_strict__validation_enabled=false"
  ]

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
  image = docker_image.api.image_id

  env = [
    "DATABASE_URL=postgresql+psycopg2://airlines:${var.postgres_password}@pg_airlines:5432/airlines_db",
    "MONGO_URL=mongodb://mongo_airlines:27017/",
    "NEO4J_URL=bolt://neo4j_airlines:7687",
    "NEO4J_USER=neo4j",
    "NEO4J_PASS=${var.neo4j_password}",
    "GULF_MODEL_PATH=/app/gulf_delay_model.joblib"
  ]

  ports {
    internal = 8000
    external = 8000
    ip       = var.public_bind_address
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
  image = docker_image.dashboard.image_id

  env = [
    "API_URL=http://airlines_api:8000",
    "DATABASE_URL=postgresql+psycopg2://airlines:${var.postgres_password}@pg_airlines:5432/airlines_db"
  ]

  ports {
    internal = 8050
    external = 8050
    ip       = var.public_bind_address
  }

  networks_advanced {
    name = docker_network.dst_network.name
  }

  restart = "always"

  depends_on = [
    docker_container.api
  ]
}
