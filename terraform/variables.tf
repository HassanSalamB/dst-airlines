variable "postgres_password" {
  description = "PostgreSQL password"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.postgres_password) >= 16
    error_message = "postgres_password must contain at least 16 characters."
  }
}

variable "neo4j_password" {
  description = "Neo4j password"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.neo4j_password) >= 16
    error_message = "neo4j_password must contain at least 16 characters."
  }
}

variable "docker_host" {
  description = "Docker endpoint. Use unix:///var/run/docker.sock locally or ssh://user@host:22 for a Proxmox Docker guest."
  type        = string
  default     = "unix:///var/run/docker.sock"

  validation {
    condition = (
      startswith(var.docker_host, "unix://") ||
      startswith(var.docker_host, "ssh://")
    )
    error_message = "docker_host must use unix:// or ssh://. Plain TCP Docker endpoints are intentionally rejected."
  }
}

variable "deployment_host" {
  description = "Hostname or IP used only when displaying API and dashboard URLs."
  type        = string
  default     = "localhost"
}

variable "public_bind_address" {
  description = "Host address for API/dashboard published ports. Keep 127.0.0.1 when using a reverse proxy."
  type        = string
  default     = "127.0.0.1"
}

variable "api_image" {
  description = "Immutable API image reference, preferably a GHCR commit-SHA tag."
  type        = string
}

variable "dashboard_image" {
  description = "Immutable dashboard image reference, preferably a GHCR commit-SHA tag."
  type        = string
}
