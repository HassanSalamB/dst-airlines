# Deployment Guide

## Credential setup

```bash
cp .env.dev.example .env.dev
cp .env.prod.example .env.prod
cp .env.k8s.example .env.k8s
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
```

Replace all placeholders. Never commit populated copies.

## Docker development

The committed Gulf model artifact is produced by a chronological training flow:
2023 fit, 2024 probability calibration, and 2025 evaluation. Retrain it before
building the API image whenever the portfolio dataset or feature contract changes:

```bash
cd dashboard
uv run --python 3.11 \
  --with pandas==2.2.2 --with numpy==1.26.4 --with requests==2.32.3 \
  --with scikit-learn==1.4.2 --with catboost==1.2.8 --with joblib==1.4.2 \
  train_gulf_ml.py
cd ..
```

The API image loads `api/gulf_delay_model.joblib` once, serves model metadata at
`GET /model/gulf/status`, and scores scenarios at `POST /predict/gulf`. The
dashboard consumes those endpoints and never deserializes the estimator.

```bash
docker compose --env-file .env.dev -f docker-compose.dev.yml up --build -d
docker compose --env-file .env.dev -f docker-compose.dev.yml ps
docker compose --env-file .env.dev -f docker-compose.dev.yml logs -f api dashboard
```

URLs:

- Dashboard: `http://localhost:8050`
- API: `http://localhost:8000`
- API documentation: `http://localhost:8000/docs`

## Full local stack

```bash
docker compose --env-file .env.dev -f docker-compose.yml up --build -d
```

Additional services:

- pgAdmin: `http://localhost:5050`
- Mongo Express: `http://localhost:8081`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

## Production-oriented Compose

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up --build -d
```

The production file binds web services to `127.0.0.1` by default and does not
publish database ports. Add a TLS reverse proxy and firewall before public
access.

## Minikube

```bash
minikube start --driver=docker
eval "$(minikube docker-env)"
docker build -t dst-airlines-api:ci ./api
docker build -t dst-airlines-dashboard:ci ./dashboard

cp .env.k8s.example .env.k8s
# Replace all credential placeholders.
./scripts/deploy-k8s.sh

minikube service dashboard -n dst-airlines
```

## Proxmox Docker guest

1. Create an Ubuntu or Debian VM/LXC in Proxmox.
2. Install Docker in the guest.
3. Create a non-root deployment user with the required Docker access.
4. Configure SSH keys and `known_hosts`.
5. Restrict SSH with the host and Proxmox firewalls.
6. Do not expose Docker port `2375`.
7. Configure Terraform with `ssh://user@host:22`.

```bash
export TF_VAR_docker_host='ssh://docker-user@proxmox-docker-host:22'
export TF_VAR_deployment_host='proxmox-docker-host'
export TF_VAR_api_image='ghcr.io/kboroz/dst-airlines-api:<commit-sha>'
export TF_VAR_dashboard_image='ghcr.io/kboroz/dst-airlines-dashboard:<commit-sha>'
export TF_VAR_postgres_password='<strong-password>'
export TF_VAR_neo4j_password='<strong-password>'

cd terraform
terraform init
terraform plan
terraform apply
```

For private GHCR packages, authenticate Docker on the target guest with a
package-read token stored outside Git.

## Verification

```bash
curl --fail http://127.0.0.1:8000/
curl --fail http://127.0.0.1:8050/ >/dev/null
curl --fail http://127.0.0.1:9090/-/ready
```

For Kubernetes:

```bash
kubectl get pods,services,persistentvolumeclaims -n dst-airlines
kubectl rollout status deployment/api -n dst-airlines
kubectl rollout status deployment/dashboard -n dst-airlines
```

## Shutdown

```bash
docker compose --env-file .env.dev -f docker-compose.dev.yml down
docker compose --env-file .env.prod -f docker-compose.prod.yml down
minikube stop
```

Add `--volumes` or delete the Kubernetes namespace only when data removal is
intentional.
