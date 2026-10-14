# Roadmap

Target: a complete supply-chain twin for an anonymous electronics maker producing in Asia and
selling worldwide, built around tariff-driven factory transfer, MWD and lead time.

Effort is counted in **working days** of one long session each. Plan: about 40–45 days,
roughly two months of daily work; allow two and a half to three months with interruptions.

Last updated: 2026-10-14

## Working rules

- One module at a time. When a phase starts, its scope is frozen; new ideas go to the
  backlog at the bottom, not into the running phase.
- A module is finished when its **done when** line is met, not when it feels polished.
- Every rule and number is traced in [`ASSUMPTIONS.md`](ASSUMPTIONS.md) as PRACTITIONER, WEB,
  PLACEHOLDER or OPEN.
- Practitioner input is generalized and virtualized before it enters the repository. The
  company is anonymous and every site is illustrative.
- Each phase ends with a tagged release and a short entry in [`LOG.md`](LOG.md).

## Status

| | Item | State |
|---|---|---|
| ✓ | Module 1 — MWD engine (`src/mwd_engine.py`) | done |
| ✓ | Module 2 — transfer cutover timing (`src/transfer.py`) | done |
| ✓ | Module 3 — transfer business case, Monte Carlo (`src/business_case.py`) | done |
| ✓ | Network atlas v1 — one-world map, sea/air/truck lanes, duty layer, highways | done |
| ✓ | Module 4 — finished goods at MGI and in the channel (`src/finished_goods.py`) | done |
| ✓ | Report pages — eight linked BI-style pages (`src/build_dashboards.py`) | done |
| → | Phase A — core loop closure | **next: Q24, then A2 demand and KPI view** |

## Phase A — core loop closure · 5 days → release v1

| Step | Scope | Done when |
|---|---|---|
| A1 ✓ | **Module 4 — finished goods at MGI.** Sell-in vs sell-through, excess build-up, step price drop at successor launch paid as price protection (R26, R27), sales volume lock (R28, R31), dealer leftovers and stock rotation (R30), disposition paths 1–6 (R11), post-customs vs FTZ (R25). | An excess-stock scenario returns the cost of each path and the cheapest path per product line. |
| A2 | **Module 5 — demand and KPI view.** Tariff → retail price (pass-through) → units (elasticity by segment) → fiscal-year shipment gap. Score decisions twice: BU view (MWD + shipment target) and company view (total cost). | The same transfer decision is scored both ways and the page shows where the two views disagree. |
| A3 | **Module 6 — new-site ramp and risk board hedge.** Capacity, yield and certification ramp curves; board-build timing vs the ODM's capacity response; GSM strength as a parameter. | The model returns a recommended board-build lead per model under demand uncertainty. |
| A4 | **Integrated simulation.** Chain modules 1–6 week by week. | One command runs a full transfer scenario end to end and writes a summary report. |

## Phase B — breadth · 7 days

| Step | Scope | Done when |
|---|---|---|
| B1 | **Second product line: AI servers.** GPU/HBM allocation, direct Section 232 exposure, high unit value, build-to-order, air-heavy. | Modules 1–6 run for servers as well as laptops. |
| B2 | **More origins and markets.** Mexico (USMCA), India (import licence), Middle East (Gulf routing), Thailand and Malaysia as alternative Southeast Asian sites. | Every origin–market pair has duty, lanes and lead time. |
| B3 | **More modes.** China–Europe rail, sea-air via a hub, cross-border trucking. | Every origin–market pair has at least an ocean and an air option, plus rail where it exists. |

## Phase C — decision engine · 7–8 days → release v2

| Step | Scope | Done when |
|---|---|---|
| C1 | **Network optimisation (MILP).** Which site supplies which market, and when to switch, under tariff scenarios; MWD, ramp and capacity as constraints. | The optimiser returns a footprint and a cutover plan for each tariff scenario. |
| C2 | **Inventory policy.** Safety stock per node from lead-time and demand variability. | A service-level vs inventory-cost frontier per region. |
| C3 | **Demand and forecast.** Seasonality, NPI/EOL curves, forecast error growing with horizon, sales optimism bias. | Forecast error used by modules 1–6 comes from this module, not a constant. |

## Phase D — risk and cost · 5 days

| Step | Scope | Done when |
|---|---|---|
| D1 | **Disruption Monte Carlo.** Chokepoints (Red Sea, Hormuz, Panama), port congestion, tariff shocks, each with a probability and duration. | Cost and service distributions per network design, with resilience metrics. |
| D2 | **Carbon per lane.** Emission factors by mode (GLEC-style). | Every lane shows CO2e per unit; cost vs carbon trade-off available. |
| D3 | **Landed cost.** Benchmark freight (container and air indices), duty, VAT, handling, inventory carrying. | Landed cost per unit for every origin–market–mode route. |

## Phase E — calibration and live data · 4 days

| Step | Scope | Done when |
|---|---|---|
| E1 | **Calibration.** Replace placeholders with public data and virtualized practitioner input. | No PLACEHOLDER left on any number that changes a decision. |
| E2 | **Automated refresh.** Scheduled check of tariff and freight news; GitHub Actions rebuilds the site. | The live map rebuilds itself when data files change. |

## Phase F — product · 5–6 days → release v3

| Step | Scope | Done when |
|---|---|---|
| F1 | **Scenario explorer (atlas v2).** Sliders for tariff, routing, GSM strength and cutover week; module results drawn on the map. | A visitor can rerun the key trade-offs in the browser. |
| F2 | **BI exports.** Tidy tables ready for Power BI. | One folder of CSVs reproduces the main charts in Power BI. |
| F3 | **Tests and CI.** Unit tests for each module, data validation. | Every push runs the tests automatically. |

## Phase G — packaging · 3 days

| Step | Scope | Done when |
|---|---|---|
| G1 | Two or three case studies, a methodology note, a LinkedIn series. | Each case study stands alone and links to the live map. |

Buffer for rework and new practitioner input: about 5 days.

## Milestones

| Release | After | Rough timing |
|---|---|---|
| v1 — core loop closed | Phase A | end of week 1 |
| v2 — decision engine | Phases B and C | around week 4 |
| v3 — complete | Phases D, E and F | around week 8 |

## Backlog (not scheduled)

- Natural-language what-if layer on top of the simulation.
- More product lines (tablets, monitors).
- Supplier-side tiers (memory, panel, battery makers).
