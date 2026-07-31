terraform {
  required_version = ">= 1.6.0"

  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.9"
    }
  }
}

provider "docker" {
  # Use the local socket or SSH to a Docker host. Never expose unauthenticated
  # Docker TCP port 2375 to a network.
  host = var.docker_host
}
