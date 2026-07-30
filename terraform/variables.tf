variable "postgres_password" {
  description = "PostgreSQL password"
  type        = string
  sensitive   = true
}

variable "neo4j_password" {
  description = "Neo4j password"
  type        = string
  sensitive   = true
}

variable "pgadmin_password" {
  description = "pgAdmin password"
  type        = string
  sensitive   = true
}

variable "proxmox_host" {
  description = "Proxmox server IP"
  type        = string
  default     = "51.158.200.169"
}