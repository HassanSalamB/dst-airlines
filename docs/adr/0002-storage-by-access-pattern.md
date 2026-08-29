---
status: accepted
---

# Use storage systems according to access pattern

PostgreSQL owns structured historical analytics, MongoDB owns recent schema-flexible aircraft observations, and Neo4j owns traversable airport-route relationships. A single database would reduce operational complexity, but it would hide the portfolio’s intended demonstration of choosing storage around query shape; FastAPI provides the shared interface so the dashboard does not need database-specific knowledge.

## Consequences

Each database must justify a user-visible query and have independent health, backup, and failure handling. Neo4j should be removed if route traversal is not demonstrated in the deployed product.
