# Security Documentation — DST Airlines

## Implemented DevSecOps Controls

### 1. Container Image Scanning (Trivy)
We use Trivy to scan all Docker images for known vulnerabilities.

**Images scanned:**
- `alidoghan/dst-airlines-api:v1.0`
- `alidoghan/dst-airlines-dashboard:v1.0`

**Results:**
- API image: 171 vulnerabilities (4 Critical, 19 High, 54 Medium, 66 Low)
- Dashboard image: scanned and report saved

**Reports location:** 
- `trivy-report-api.json`
- `trivy-report-dashboard.json`

**How to run:**
```bash
trivy image alidoghan/dst-airlines-api:v1.0
trivy image alidoghan/dst-airlines-dashboard:v1.0
```

---

### 2. Secrets Management
All sensitive credentials are stored securely and never hard-coded.

**Implementation:**
- Runtime secrets stored in `.env.dev` and `.env.prod` files
- Both files are listed in `.gitignore` — never pushed to GitHub
- Kubernetes Secrets used for all sensitive values in K8s deployments
- `docker-compose.yml` uses environment variable references (`${VARIABLE}`) instead of plain text values

**Kubernetes Secret:** `dst-airlines-secret` in namespace `dst-airlines`

---

### 3. No Hard-coded Credentials in CI/CD
- All credentials are passed via environment variables
- No passwords or API keys exist in any code file
- `.dockerignore` prevents sensitive files from being included in Docker images

---

## Security Recommendations (Future)
- Update `starlette` to version 1.3.1+ (fixes HIGH vulnerabilities)
- Update `pip` to version 26.1+ (fixes MEDIUM vulnerabilities)
- Add GitHub Dependabot for automated dependency scanning
- Implement HTTPS via ingress + cert-manager