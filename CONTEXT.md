# Gulf Aviation Intelligence

This context defines the language used by the Saudi Arabia and UAE aviation portfolio so that live observations, analytical simulations, and model outputs are not confused with official airline operations data.

## Language

**Aircraft Observation**:
A time-stamped position and motion report for an aircraft currently detected by the live data source. It is not a scheduled flight or a complete flight record.
_Avoid_: Live flight, today’s flight

**Market Boundary**:
The portfolio’s geographic selection for Saudi Arabia, the United Arab Emirates, or both. It is an analytical filter rather than an official airspace classification.
_Avoid_: National airspace

**Gateway Catchment**:
A configurable area around a supported airport used to group nearby aircraft observations. It does not prove that an aircraft departed from or will arrive at that airport.
_Avoid_: Airport traffic, airport destination

**Route Match**:
A best-effort origin and destination association inferred from a callsign by a community data source.
_Avoid_: Confirmed route, official schedule

**Portfolio Simulation**:
A synthetic but internally consistent history used to demonstrate operational analytics when official airline movement data is unavailable.
_Avoid_: Historical operations, airline records

**Operational View**:
A decision-oriented perspective over one part of the Gulf aviation market, such as live airspace, airports, airlines, routes, or historical performance.
_Avoid_: Tab, page

**Delay Event**:
A simulated departure outcome at least 15 minutes later than its reference departure time.
_Avoid_: Disruption

**Delay-Risk Scenario**:
A what-if estimate of the probability of a Delay Event for supplied route, time, carrier, and weather conditions. It is not an official forecast for a scheduled flight.
_Avoid_: Flight prediction, delay forecast

**Model Score**:
A portfolio-facing reliability indicator derived from held-out discrimination, probability calibration, and data provenance. It is not an airline safety or regulatory certification.
_Avoid_: Accuracy, confidence score
