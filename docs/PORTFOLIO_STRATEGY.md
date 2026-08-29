# Two-Project Portfolio Strategy

The two projects are strongest when they demonstrate different engineering problems instead of presenting two similar dashboards.

## Positioning

| Project | Primary story | Best audience | Evidence to lead with |
|---|---|---|---|
| DST Airlines | Real-time Gulf aviation intelligence and delay-risk scenarios | Airlines, airports, aviation consultancies, operations/data teams | Live aircraft ingestion, Kafka pipeline, operational views, model card, observability |
| Holiday Itinerary | Governed tourism data platform and recommendation product | Travel technology, hospitality, data-platform, recommendation teams | Airflow DAG, bronze/silver/gold lineage, dbt tests, Spark features, Neo4j recommendations |

## DST Airlines: recommended improvements

### Priority 1 — make the evidence operationally credible

1. Add a data-provenance badge to every view: `LIVE OBSERVATION`, `PORTFOLIO SIMULATION`, or `MODEL SCENARIO`.
2. Persist short aircraft histories so live airspace can show track age, observation continuity, and ingestion lag without implying a confirmed route.
3. Add pipeline-health indicators: last OpenSky pull, Kafka consumer lag, MongoDB freshness, API latency, and model version.
4. Add a replay mode that runs a recorded disruption window through the same collector-to-dashboard path. This gives recruiters a stable demonstration when the external live feed is quiet.

### Priority 2 — turn the model into an evaluation story

1. Expose ROC-AUC, PR-AUC, Brier score, calibration plot, class balance, and chronological split in the AI Intelligence view.
2. Add a baseline comparison and a clear “why this prediction changed” explanation for each scenario.
3. Add data-drift checks for airport, airline, weather, and departure-hour distributions.
4. Retrain only when a versioned dataset passes validation; record the data version and model version together.

### Priority 3 — prepare a credible airline proof of concept

1. Define an adapter for an official schedule/status provider or airline feed without changing the dashboard’s domain interface.
2. Add role-specific saved views for network planning, airport operations, and executive monitoring.
3. Add authenticated access and tenant-specific configuration before accepting proprietary data.
4. Validate one measurable decision, such as identifying high-risk departure banks 60–180 minutes ahead.

## Holiday Itinerary: recommended improvements

### Priority 1 — strengthen recommendation quality

1. Replace simple category matching with a scored itinerary objective that balances preference fit, travel time, opening hours, weather, diversity, and daily pace.
2. Show “why this place” explanations and allow users to lock, remove, or reorder stops before recalculation.
3. Add offline evaluation using constraint satisfaction, route efficiency, diversity, and preference coverage rather than presenting recommendations without a quality measure.
4. Create three repeatable evaluation personas: family, culture-focused weekend, and outdoor/weather-sensitive traveller.

### Priority 2 — make the data platform visible in the product

1. Add a lineage panel linking a recommendation back to source snapshot, silver record, feature build, and graph version.
2. Show Airflow run freshness, dbt test status, source-row changes, and failed-record quarantine counts.
3. Add a controlled “pipeline replay” demo using a small dated DATAtourisme sample.
4. Treat Spark as a measured scale path: publish dataset size and runtime comparisons so it is clear when Spark adds value over pandas.

### Priority 3 — improve the live product

1. Add map-based day editing with route durations and day-level totals.
2. Cache weather and geocoding results, with stale-data indicators.
3. Save and share itineraries through a small persistent user/session module.
4. Add accommodation-area recommendations using POI density, transit access, and itinerary travel time without claiming hotel demand or pricing intelligence.

## Shared implementation principles

- Keep one public product URL per project and link to protected engineering evidence from within it.
- Prefer a small number of deep modules: source ingestion, domain transformation, recommendation/prediction, and product delivery.
- Make failure states visible. A dashboard that explains stale or unavailable data is more credible than one that silently substitutes it.
- Keep generated reports, local data, secrets, caches, and environment-specific output out of Git.
- Use ADRs only for durable trade-offs; use the roadmap for reversible features.

## Suggested portfolio narrative

Together, the projects demonstrate two complementary capabilities: building a continuously updated operational product from event data, and building a governed recommendation product from complex batch and graph data. The common thread is turning imperfect external data into transparent, testable decisions.
