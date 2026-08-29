# Disaster Recovery Plan

## Scope

This plan covers PostgreSQL, MongoDB, Neo4j, application containers, Kubernetes
rollbacks, and Terraform-managed Docker infrastructure.

Recovery-time and recovery-point values are targets until a restore exercise
measures them.

## Backup policy

| Data | Frequency | Retention | Required storage |
|---|---|---|---|
| PostgreSQL | Daily | 7 daily copies | Encrypted off-host storage |
| MongoDB | Daily | 7 daily copies | Encrypted off-host storage |
| Neo4j | Daily or after graph refresh | 7 copies | Encrypted off-host storage |
| Terraform state | After every apply | Versioned protected backend | Encrypted remote state |

Run the backup script on the Docker host:

```bash
BACKUP_ROOT=/secure/off-host/path \
BACKUP_RETENTION_DAYS=7 \
./scripts/backup_databases.sh
```

The script:

1. creates a timestamped directory;
2. writes a custom-format PostgreSQL dump;
3. writes a compressed MongoDB archive;
4. briefly stops Neo4j and creates an offline database dump;
5. writes SHA-256 checksums;
6. restarts Neo4j even if the dump fails;
7. prunes expired timestamped backup directories.

Copy backups away from the Docker host and monitor backup failures.

## Restore validation

Before using a backup:

```bash
cd /secure/off-host/path/<timestamp>
shasum -a 256 -c SHA256SUMS
```

Restore into an isolated environment first.

### PostgreSQL

```bash
docker exec -i pg_airlines \
  pg_restore --username=airlines --dbname=airlines_db \
  --clean --if-exists < postgresql.dump
```

### MongoDB

```bash
docker exec -i mongo_airlines \
  mongorestore --archive --gzip --drop < mongodb.archive.gz
```

### Neo4j

Neo4j Community dump/load requires the database to be offline:

```bash
docker stop neo4j_airlines
docker run --rm \
  --volumes-from neo4j_airlines \
  --volume "$PWD:/backups:ro" \
  --entrypoint neo4j-admin \
  neo4j:5 \
  database load neo4j --from-path=/backups --overwrite-destination=true
docker start neo4j_airlines
```

After each restore, verify record counts, representative API queries, dashboard
loading, and Neo4j path queries.

## Container and pod recovery

Docker Compose uses restart policies. Kubernetes Deployments recreate failed
containers and pods.

```bash
docker compose ps
docker compose restart api dashboard

kubectl get pods -n dst-airlines
kubectl rollout restart deployment/api -n dst-airlines
kubectl rollout status deployment/api -n dst-airlines
```

Kind and default Minikube are single-node clusters. If that node fails, there is
no healthy node to receive a rescheduled pod. Node-failure recovery requires a
multi-node cluster and storage that remains available to replacement nodes.

## Image rollback

Every CI-published image uses the Git commit SHA.

```bash
kubectl -n dst-airlines set image \
  deployment/api \
  api=ghcr.io/kboroz/dst-airlines-api:<previous-sha>

kubectl -n dst-airlines set image \
  deployment/dashboard \
  dashboard=ghcr.io/kboroz/dst-airlines-dashboard:<previous-sha>

kubectl -n dst-airlines rollout status deployment/api
kubectl -n dst-airlines rollout status deployment/dashboard
```

If Kubernetes deployment history is available:

```bash
kubectl rollout undo deployment/api -n dst-airlines
kubectl rollout undo deployment/dashboard -n dst-airlines
```

## Infrastructure recreation

For a local or Proxmox Docker guest:

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

Terraform recreates the Docker network, volumes, and containers. Restoring
database content is a separate step.

## Recovery order

1. Secure and verify the host.
2. Recreate infrastructure with Terraform.
3. Restore PostgreSQL and verify SQL data.
4. Restore MongoDB and verify collections.
5. Restore Neo4j and verify graph queries.
6. Start API and verify health and representative endpoints.
7. Start dashboard and monitoring.
8. Record actual recovery time and any data loss.

## Recovery exercise

At least once before submission or production use:

1. create a full backup;
2. deploy an isolated empty environment;
3. restore all three databases;
4. run API and dashboard smoke tests;
5. record measured RTO and RPO;
6. update this plan with the result.
