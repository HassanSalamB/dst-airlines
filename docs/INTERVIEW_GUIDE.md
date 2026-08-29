# DST Airlines Interview Guide

This guide helps explain the project clearly, defend the architectural choices, and answer difficult questions without overstating the data or deployment maturity.

## The story in one sentence

I transformed a general airline DataOps project into a Gulf-focused aviation intelligence product that combines current Saudi/UAE aircraft observations, a streaming data path, simulated operational analytics, and a deployed, evaluated delay-risk model behind FastAPI and Dash.

## 30-second answer

> DST Airlines is an end-to-end Gulf aviation intelligence portfolio focused on Saudi Arabia and the UAE. A Python collector retrieves current OpenSky aircraft observations, Kafka decouples ingestion from persistence, MongoDB stores recent positions, and FastAPI serves them to a Dash operational dashboard. Separately, a clearly labelled Saudi/UAE simulation supports historical analytics in PostgreSQL, route traversal in Neo4j, and a calibrated CatBoost delay-risk scenario. I also added automated tests, CI/CD, containerization, Kubernetes validation, Terraform, and observability. The key design principle is provenance: live observations, simulated history, and model scenarios are never presented as the same type of evidence.

## Two-minute architecture walkthrough

1. **Live lane:** OpenSky returns aircraft state vectors for Saudi/UAE geographic bounding boxes. The collector normalizes fields such as ICAO24, callsign, position, altitude, speed, heading, and observation time.
2. **Event seam:** The producer publishes normalized records to the Kafka topic `gulf.live_flights`. This allows collection and storage to scale or fail independently and enables future replay.
3. **Recent-state storage:** A consumer validates events and writes observations to MongoDB. FastAPI queries records using freshness, market boundary, and gateway-catchment filters.
4. **Analytical lane:** A deterministic Saudi/UAE portfolio simulation supplies repeatable operational records to PostgreSQL. It supports airline, airport, route, and historical trend views without claiming actual airline performance.
5. **Graph lane:** Neo4j represents airports and route relationships for network/path queries. It is justified only while the product demonstrates traversal that is awkward in ordinary aggregate SQL.
6. **ML lane:** CatBoost is fit on 2023 simulation data, calibrated on 2024, and compared with Logistic Regression on 2025. The versioned artifact and model metadata are served through FastAPI.
7. **Product layer:** Dash consumes the backend interface and enriches the live view with Open-Meteo weather and best-effort ADSBDB callsign route matches.
8. **Operations:** Prometheus scrapes FastAPI metrics, Grafana displays platform health, Docker Compose runs the local stack, and CI validates images in a temporary Kind cluster.

Use [the architecture diagrams](ARCHITECTURE.md) while giving this answer.

## What problem does it solve?

The prototype reduces the effort required to combine several kinds of aviation evidence into one operational view. A user can monitor recently observed aircraft, focus on a country or gateway catchment, compare simulated operational patterns, explore a route graph, and test how route, time, carrier, and weather inputs alter a delay-risk scenario.

For a real airline, the product would become useful only after connecting official schedules, movement messages, delay outcomes, aircraft rotations, and airport operational data. The current portfolio proves the engineering pattern and provides a starting interface for that proof of concept.

## What was my contribution?

Use this answer and adjust it if an interviewer asks for exact ownership:

> The original DataOps repository was collaborative. My documented contributions include the automated test and CI/CD work, followed by the Gulf portfolio redesign: replacing the US-oriented experience with Saudi/UAE views, adding live OpenSky ingestion and filtering, refining the aircraft map, introducing the AI Intelligence view and versioned Gulf model, clarifying provenance, and improving the product and repository documentation. I preserve the original team credits and use Git history to distinguish contributions.

Do not imply that every original database, Terraform, monitoring, or recovery module was solely authored by you.

## Why these technologies?

### Why Kafka?

> Collection and persistence have different failure and scaling behavior. Kafka gives them a durable event seam, lets the consumer recover after downtime, and creates a path to replay and multiple consumers. At the current portfolio volume, a direct write would be simpler, so Kafka is justified primarily by demonstrating the production pattern and enabling replay. If those benefits were not needed, I would remove it.

### Why PostgreSQL?

> Historical operational records are structured and queried through filters, joins, and aggregates. PostgreSQL gives strong relational semantics and is a natural fit for those analytical queries and deterministic test fixtures.

### Why MongoDB?

> OpenSky observations are time-oriented and may contain optional or evolving fields. MongoDB makes recent observation documents easy to persist and query while the collector schema develops. For a mature high-volume time-series workload, I would benchmark PostgreSQL/TimescaleDB or a dedicated stream store before keeping the extra database.

### Why Neo4j?

> Airport-route relationships support graph traversal and shortest-path questions. Neo4j makes the route model explicit and the query concise. If the deployed product only needs direct-route aggregates, PostgreSQL is sufficient and Neo4j should be removed—the architecture decision deliberately includes that deletion test.

### Why FastAPI?

> FastAPI creates one typed product interface across all stores and the model. The dashboard does not need database-specific credentials or query knowledge, Pydantic validates scenario inputs, and OpenAPI documentation makes the backend inspectable.

### Why Dash instead of Streamlit?

> Dash offers finer callback and component control for a multi-view operational dashboard. Streamlit is excellent for rapid analytical apps, and it is used in the Holiday Itinerary project, but Dash better fits the aviation product’s persistent navigation, map interactions, and filter-driven views.

### Why CatBoost?

> The scenario includes categorical fields such as airline, origin, and destination together with numerical weather, time, and distance features. CatBoost handles mixed features well and reduces encoding complexity. I still compare it with Logistic Regression so the more complex model must earn its place.

### Why probability calibration?

> The interface presents risk, not only a class. A probability should correspond as closely as possible to observed frequency, so I reserve a chronological calibration year and inspect Brier loss and calibration gaps. Ranking metrics alone are not enough when users see a probability.

## Explain the model evaluation

The model is evaluated chronologically to reduce temporal leakage:

- 2023: fit candidate models.
- 2024: calibrate CatBoost probabilities.
- 2025: evaluate both candidates on unseen simulated records.

The simulated 2025 results are:

| Metric | Calibrated CatBoost | Logistic Regression |
|---|---:|---:|
| ROC-AUC | 0.6280 | 0.6177 |
| PR-AUC | 0.5847 | 0.5876 |
| Brier loss | 0.2353 | 0.2382 |
| Recall at 0.50 | 0.3678 | 0.5485 |

Strong answer:

> The result is modest. CatBoost ranks slightly better and has slightly lower probability error, while Logistic Regression has higher recall at the default threshold. I selected calibrated CatBoost because the product displays probability, but I would not call it production-ready. The score mainly proves a sound training, calibration, evaluation, artifact-versioning, and serving workflow. Real operational validation requires real outcomes and a threshold selected around a specific cost function.

## What does the 71/100 model score mean?

> It is a portfolio-facing summary of ROC-AUC, PR-AUC, Brier loss, and calibration gap on the simulated 2025 holdout. It is not conventional accuracy, a confidence value for one prediction, or a certification. The underlying metrics are more important than the combined score, so an operational review should inspect those directly.

## Can it predict a future flight?

> It can score a future-dated what-if scenario using supplied airline, route, departure time, distance, and weather assumptions. It cannot identify or forecast an actual scheduled flight because it currently lacks an official schedule/status feed and future airport weather forecast integration. With Cirium, FlightAware, or airline data, I would create scheduled-flight features, event-time snapshots, and outcome labels, then retrain and backtest at defined lead times such as 60, 120, and 180 minutes.

## Is Live Airspace showing all flights today?

> No. It shows aircraft observations recently returned by OpenSky inside the selected Saudi/UAE geographic filter. Altitude, speed, and heading describe the observed aircraft state. It is neither a list of all flights today nor a complete record of departures and arrivals.

## How do you know origin and destination?

> OpenSky state vectors do not reliably supply commercial origin and destination. The dashboard may enrich a callsign through ADSBDB, and unmatched values remain unavailable. Gateway catchment means geographic proximity, not confirmed arrival or departure. Official routing requires a schedule/status provider or airline feed.

## Why is the historical data simulated?

> Reliable commercial Saudi/UAE movement and delay data is not freely available at the required detail. Simulation lets me build and test the product architecture without misrepresenting scraped or invented records as airline truth. The interface explicitly labels simulation, and the future official-data adapter is an architectural seam rather than a hidden substitution.

## How would you productionize it for an airline?

1. Agree on one operational decision and measurable success criterion.
2. Connect official schedule, movement, weather, rotation, and outcome feeds through authenticated adapters.
3. Introduce a canonical flight-leg identity and event-time model.
4. Add schema contracts, dead-letter handling, idempotency, replay, and data-quality service-level indicators.
5. Train on real outcomes with time-aware cross-validation and lead-time-specific backtests.
6. Choose thresholds using the operational cost of false alarms and missed disruptions.
7. Add authentication, authorization, audit logs, encryption, retention policies, and tenant isolation.
8. Deploy stateful infrastructure with managed backups and measured recovery objectives.
9. Run shadow predictions before allowing the output to influence operations.
10. Monitor freshness, drift, calibration, latency, and user action/outcome feedback.

## How would you scale it?

> I would first measure the bottleneck. For ingestion, partition Kafka by stable aircraft or market key and run multiple consumers. Store a latest-state collection separately from append-only observation history. For PostgreSQL, add date/route indexes and partition large fact tables. Cache slow reference lookups. Run stateless FastAPI and Dash replicas behind a load balancer. The public edge and private data platform remain separate so stateful scaling is not coupled to portfolio web traffic.

## How do you handle failures?

> External fetches use timeouts and the product reports freshness rather than silently presenting stale data as live. Kafka decouples the producer from the consumer, and a production version would add retry topics and a dead-letter path. Database clients initialize lazily so one unavailable dependency does not prevent every interface from starting. Health should ultimately be split into liveness and dependency readiness. Backups and recovery targets are documented, but they are not claimed as proven until a restore exercise measures them.

## What would you monitor?

- OpenSky request success rate and duration.
- Time since the last accepted aircraft observation.
- Kafka producer errors, consumer lag, and dead-letter count.
- MongoDB write/query latency and observation age.
- PostgreSQL query latency and data freshness.
- FastAPI latency, error rate, and saturation by route.
- Dashboard callback failures.
- Model input drift, prediction distribution, calibration, and outcome delay.
- Backup completion and restore-test age.

## Security answer

> Secrets are supplied at runtime and example files are committed without real credentials. Container build contexts exclude environment files, CI performs dependency and image scanning, and public production interfaces should sit behind TLS. Before proprietary airline data, I would add identity, role-based authorization, audit logging, network isolation, managed secrets, encryption, data-retention rules, and a threat model. The current portfolio controls are a foundation, not airline-grade certification.

## CI/CD answer

> Pull requests and selected branch changes run application tests and Terraform validation, build the API and dashboard images, and use immutable commit tags. Non-PR runs publish images, scan them with Trivy, deploy them to a temporary Kind cluster, and smoke-test the interfaces. Kind proves the manifests deploy; it is not a persistent environment. A production pipeline still needs an approved target, environment protection, migration strategy, rollback evidence, and post-deployment monitoring.

## Render and Proxmox answer

> Render is appropriate for the accessible Dash/FastAPI portfolio edge. The continuously running Kafka, databases, observability, backups, and optional Airflow scheduler are better placed on the private Proxmox environment for this project. Protected links can expose selected engineering evidence, but infrastructure dashboards should not be left anonymous on the public internet.

## Difficult questions

### “Is this overengineered?”

> For the current traffic, yes, a single Python process and PostgreSQL could deliver the dashboard. The repository intentionally demonstrates multiple DataOps patterns. I still apply a deletion test: Kafka must enable replay or decoupled consumers, MongoDB must serve live observations naturally, and Neo4j must demonstrate route traversal. If a module does not produce visible leverage, I remove it rather than keeping it as a logo.

### “Why not use one database?”

> One database would be the default for a small production product because it lowers operational cost. Here the stores demonstrate different access patterns behind FastAPI. I would validate the expected query and scale before retaining polyglot persistence in an airline deployment.

### “Why isn’t the model stronger?”

> The simulated feature set lacks important operational causes such as aircraft rotation, inbound delay, maintenance, crew, gate, traffic management, and real schedule pressure. A modest result is expected. The important point is that the evaluation exposes this instead of presenting a misleading accuracy number.

### “Why not deep learning?”

> The dataset is small, tabular, and mixed-type. CatBoost and a linear baseline are easier to evaluate and explain. Deep learning would add complexity without evidence of better generalization. I would revisit sequence or graph models only after obtaining high-volume aircraft rotation and event-history data.

### “Would you sell this product?”

> I would sell a tailored proof of concept, not the current prototype as finished operational software. The first engagement would connect the customer’s own data and validate one decision with measurable value. The portfolio is strongest today as evidence that I can build that product with an airline or airport team.

### “What would you do differently?”

> I would define the canonical Gulf flight-leg domain model earlier, separate backend routers and data adapters sooner, add contract and browser tests, record short live tracks for replay, and design the deployment around measured recovery and freshness objectives. I would also challenge every infrastructure module with a user-visible query before adding it.

## STAR examples

### Reframing the market

- **Situation:** The project was oriented around US historical data and did not support the Saudi/UAE employers I wanted to approach.
- **Task:** Reposition it for Gulf aviation without pretending that official regional operations data was freely available.
- **Action:** I removed US-facing product behavior, added Saudi/UAE market and gateway filters, integrated current OpenSky observations, created a separate Gulf simulation, and labelled every evidence class.
- **Result:** The product now tells a coherent Gulf aviation story while remaining transparent about its limitations.

### Making ML defensible

- **Situation:** A prediction page without evaluation evidence would be visually impressive but technically weak.
- **Task:** Build an inspectable model workflow suitable for an interview discussion.
- **Action:** I trained CatBoost and Logistic Regression candidates, used chronological fit/calibration/evaluation periods, versioned the artifact and metadata, exposed metrics and limitations, and added focused API tests.
- **Result:** The dashboard can explain both the selected model and why its modest performance is not production validation.

### Strengthening delivery evidence

- **Situation:** Local application behavior alone did not prove that the platform could be packaged and deployed consistently.
- **Task:** Build repeatable validation across tests, images, infrastructure, and Kubernetes.
- **Action:** I implemented CI stages for tests, Terraform validation, image builds, immutable registry tags, Trivy scanning, temporary Kind deployment, and smoke tests.
- **Result:** The repository provides reproducible delivery evidence while clearly distinguishing CI deployment from a live production environment.

## Five-minute demo script

1. Open **Live Airspace** and state: “These are current observations, not today’s schedule.” Show country, gateway, and airline filters plus freshness.
2. Open **Market Overview** and state: “This view is a repeatable simulation used to demonstrate product analytics.” Select year 2026 and compare Saudi Arabia with the UAE.
3. Open **Airlines**, **Airports**, and **Routes** to show the role-based operational views and route graph.
4. Open **AI Intelligence**. Explain the 2023/2024/2025 split, compare CatBoost with Logistic Regression, and show the model limitation.
5. Run one low-risk and one higher-risk scenario. Describe the result as a change in modeled probability, not a real flight forecast.
6. Open the FastAPI documentation or architecture image and trace one live event from OpenSky to the dashboard.
7. Finish with the production path: official data adapter, shadow evaluation, authenticated Proxmox platform, and measurable airline decision.

## Questions to ask the interviewer

- Which operational decisions does your data team support today?
- What are the most difficult aviation data sources to reconcile?
- How do you measure data freshness and trust for operational dashboards?
- Does the team own model deployment and monitoring, or hand models to another platform team?
- Which delay or disruption lead times are most valuable to your users?
- How do engineering, network planning, airport operations, and data science collaborate?

## Final rules for presenting the project

1. Say **aircraft observation**, not “all live flights.”
2. Say **portfolio simulation**, not “historical airline data.”
3. Say **delay-risk scenario**, not “prediction for this actual flight.”
4. Show the underlying metrics instead of defending the 71/100 score as accuracy.
5. Distinguish your contribution from the original collaborative work.
6. Describe Render and Proxmox as live only after their URLs and health checks are verified.
7. Lead with the decision the product supports; use the technology stack as evidence, not as the story itself.
