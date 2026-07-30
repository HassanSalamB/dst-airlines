# Disaster Recovery Plan — DST Airlines

## Overview

This document describes the disaster recovery procedures for the DST Airlines platform. It covers database backups, container failure recovery, infrastructure recreation, and rollback procedures.

---

## 1. Database Backup Strategy

### PostgreSQL

```bash
# Create a backup
docker exec pg_airlines pg_dump -U airlines airlines_db > backup_postgres_$(date +%Y%m%d).sql

# Restore from backup
docker exec -i pg_airlines psql -U airlines airlines_db < backup_postgres_20260731.sql
```

- **Frequency:** Daily
- **Retention:** 7 days
- **Storage:** Store backups outside the container (local or cloud storage)

### MongoDB

```bash
# Create a backup
docker exec mongo_airlines mongodump --out /backup/mongo_$(date +%Y%m%d)

# Restore from backup
docker exec mongo_airlines mongorestore /backup/mongo_20260731
```

- **Frequency:** Daily
- **Retention:** 7 days

### Neo4j

```bash
# Create a backup
docker exec neo4j_airlines neo4j-admin database dump neo4j --to-path=/backup

# Restore from backup
docker exec neo4j_airlines neo4j-admin database load neo4j --from-path=/backup
```

- **Frequency:** Weekly
- **Retention:** 4 weeks

---

## 2. Container Failure Recovery

### What happens if a container fails?

All containers are configured with `restart: always` in both Docker Compose and Kubernetes. This means:

- If a container crashes, Docker or Kubernetes will automatically restart it
- No manual intervention is needed for simple crashes
- Data is preserved in persistent volumes (PVC in Kubernetes, named volumes in Docker)

### Manual recovery steps:

```bash
# Check container status
docker ps -a

# Restart a specific container
docker restart pg_airlines

# Check Kubernetes pod status
kubectl get pods -n dst-airlines

# Restart a Kubernetes deployment
kubectl rollout restart deployment/api -n dst-airlines
```

---

## 3. Kubernetes Node Failure

If a Kubernetes node fails:

1. Kubernetes automatically reschedules pods to healthy nodes
2. Persistent data is preserved in PersistentVolumeClaims (PVC)
3. Services continue to route traffic to healthy pods

```bash
# Check node status
kubectl get nodes

# Check pod rescheduling
kubectl get pods -n dst-airlines -o wide
```

---

## 4. Rollback to Previous Version

### Docker rollback

```bash
# Pull previous image version
docker pull alidoghan/dst-airlines-api:v1.0

# Stop current container and start with old image
docker stop airlines_api
docker run -d --name airlines_api alidoghan/dst-airlines-api:v1.0
```

### Kubernetes rollback

```bash
# Rollback to previous deployment
kubectl rollout undo deployment/api -n dst-airlines
kubectl rollout undo deployment/dashboard -n dst-airlines

# Check rollback status
kubectl rollout status deployment/api -n dst-airlines
```

### CI/CD rollback

Each image is tagged with the Git commit SHA. To rollback:

1. Find the previous commit SHA from GitHub
2. Pull the image with that SHA tag from GHCR
3. Update the Kubernetes deployment with the old image tag

```bash
git log --oneline
# Copy the previous commit SHA
kubectl set image deployment/api api=ghcr.io/kboroz/dst-airlines-api:<previous-sha> -n dst-airlines
```

---

## 5. Infrastructure Recreation from Terraform

If the entire infrastructure needs to be recreated:

```bash
# Navigate to terraform directory
cd terraform

# Initialize Terraform
terraform init

# Review the plan
terraform plan -var-file="terraform.tfvars"

# Apply and recreate everything
terraform apply -var-file="terraform.tfvars"
```

This will recreate:
- Docker network
- All persistent volumes
- All containers (PostgreSQL, MongoDB, Neo4j, API, Dashboard)

---

## 6. Recovery Order

In case of complete system failure, follow this order:

| Step | Action |
|------|--------|
| 1 | Recreate infrastructure with Terraform |
| 2 | Start PostgreSQL and restore database backup |
| 3 | Start MongoDB and restore backup |
| 4 | Start Neo4j and restore backup |
| 5 | Start API container |
| 6 | Start Dashboard container |
| 7 | Verify all services are healthy |

---

## 7. Expected Recovery Time

| Scenario | Expected Time |
|----------|--------------|
| Single container crash | < 30 seconds (auto-restart) |
| Full infrastructure recreation | < 15 minutes |
| Database restore from backup | < 30 minutes |
| Complete system recovery | < 1 hour |