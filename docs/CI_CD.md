# CI/CD Pipeline

The GitHub Actions workflow in `.github/workflows/ci-cd.yml` implements the
baseline pipeline required by project requirement 5.

## Triggers

- Pull requests to `dev-ali`, `dev`, or `main`: test and build both images.
- Pushes to `dev-ali`, `dev`, or `main`: test, build, publish, and deploy to Kind.
- Manual runs: test, build, publish, and deploy to Kind.

## Pipeline stages

1. Start a temporary PostgreSQL 16 service.
2. Create the database schema and load deterministic test fixtures.
3. Run FastAPI and dashboard tests.
4. Check Terraform formatting and validate its configuration.
5. Build the API and dashboard Docker images.
6. Push commit-tagged images to GitHub Container Registry.
7. Scan both images with Trivy and fail on fixed critical vulnerabilities.
8. Create a temporary Kind Kubernetes cluster.
9. Mirror the application images into Kind's local registry.
10. Deploy through `scripts/deploy-k8s.sh`, which creates runtime configuration.
11. Wait for all Kubernetes rollouts and smoke test the API and dashboard.

Images use the Git commit SHA as an immutable tag:

```text
ghcr.io/<owner>/dst-airlines-api:<commit-sha>
ghcr.io/<owner>/dst-airlines-dashboard:<commit-sha>
```

The workflow uses the repository-provided `GITHUB_TOKEN`; no registry password
needs to be added manually. Repository Actions settings must allow workflows to
read and write packages.

## Security

`k8s/secret.example.yaml` documents required keys but contains no runtime
credentials. The CI workflow creates an ephemeral Secret directly in Kind.
Persistent development or production clusters must obtain values from GitHub
Environment secrets or an external secret manager.

Credentials that were previously committed must be rotated because removing a
file from the latest revision does not remove it from Git history.

Trivy scans both published images before deployment. Dependabot checks Python,
Docker, and GitHub Actions dependencies weekly.

## Current deployment scope

Kind proves that the application images and Kubernetes manifests deploy
successfully. Its cluster is temporary and is deleted with the GitHub-hosted
runner.

A persistent deployment still requires one of:

- A managed Kubernetes cluster and a `KUBECONFIG` stored as a GitHub
  Environment secret.
- A self-hosted GitHub Actions runner connected to a Minikube or k3s cluster.

For the production approval bonus, create a GitHub Environment named
`production`, configure required reviewers, and add a production deployment job
that targets the persistent cluster.

## Branch strategy

The workflow currently supports the existing `dev-ali` branch as well as the
recommended `dev` and `main` branches. The team should merge feature work into
`dev`, verify the automatic development deployment, and promote approved changes
to `main`.
