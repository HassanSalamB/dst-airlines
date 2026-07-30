output "api_url" {
  description = "DST Airlines API URL"
  value       = "http://${var.proxmox_host}:8000"
}

output "dashboard_url" {
  description = "DST Airlines Dashboard URL"
  value       = "http://${var.proxmox_host}:8050"
}

output "postgres_container" {
  description = "PostgreSQL container name"
  value       = docker_container.postgres.name
}

output "mongo_container" {
  description = "MongoDB container name"
  value       = docker_container.mongo.name
}

output "neo4j_container" {
  description = "Neo4j container name"
  value       = docker_container.neo4j.name
}