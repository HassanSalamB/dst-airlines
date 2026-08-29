---
status: accepted
---

# Separate the public portfolio edge from the full data platform

The lightweight Dash and FastAPI experience may be hosted publicly on Render, while the continuously running Kafka, databases, monitoring stack, and future scheduler run on the private Proxmox environment. This keeps the public demonstration accessible without paying to keep every stateful portfolio module on a platform designed primarily for web workloads.

## Consequences

Public pages must degrade gracefully when the private environment is unavailable, private observability interfaces require authentication, and recorded evidence must be identified as recorded rather than live.
