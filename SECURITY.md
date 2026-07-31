# Security and DevSecOps

## Implemented controls

### Runtime secrets

- Real `.env.*` and `terraform/*.tfvars` files are ignored.
- Sanitized example files document every required variable.
- Kubernetes Secrets are created at runtime by `scripts/deploy-k8s.sh`.
- Docker build contexts exclude environment files.
- Python database clients fail clearly when required credentials are absent.

Never commit populated copies of:

```text
.env.dev
.env.prod
.env.k8s
terraform/terraform.tfvars
```

Credentials present in older commits must be rotated. Deleting a file in a new
commit does not remove its previous contents from Git history.

### Container scanning

GitHub Actions scans the published API and dashboard images with Trivy. The
pipeline fails when a fixed critical vulnerability is found.

Local scan:

```bash
trivy image ghcr.io/kboroz/dst-airlines-api:<commit-sha>
trivy image ghcr.io/kboroz/dst-airlines-dashboard:<commit-sha>
```

The checked-in JSON reports are historical evidence only. The CI result is the
current security gate.

### Dependency updates

`.github/dependabot.yml` checks:

- API Python dependencies
- Dashboard Python dependencies
- API and dashboard Docker base images
- GitHub Actions

### Infrastructure transport

Terraform accepts only:

- `unix:///var/run/docker.sock` for local Docker
- `ssh://user@host:22` for a remote Docker guest

Plain Docker TCP endpoints are rejected. Do not expose port `2375`.

### Network exposure

The production Compose and Terraform configurations:

- do not publish PostgreSQL, MongoDB, or Neo4j ports;
- bind web/monitoring ports to `127.0.0.1` by default;
- expect a TLS reverse proxy and host firewall for public access.

## Production requirements

Before a public deployment:

1. Rotate previously exposed credentials.
2. Restrict SSH by source address and key; disable password authentication.
3. Put the API, dashboard, and Grafana behind HTTPS.
4. Store production secrets in protected GitHub Environments or a secret manager.
5. Add Kubernetes NetworkPolicy and least-privilege RBAC if using Kubernetes.
6. Review Trivy and Dependabot findings before promotion.
7. Back up databases off-host and verify restores.

## Incident response

If a credential or image is compromised:

1. Disable the affected account, token, or endpoint.
2. Rotate credentials and update protected runtime configuration.
3. Rebuild images from a reviewed commit.
4. Run tests and Trivy scans.
5. Deploy immutable SHA-tagged images.
6. Review host, registry, and application logs.
7. Document the incident and prevention action.
