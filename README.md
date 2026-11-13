# Supply Chain Twin — tariff-driven factory transfer & MWD

Work in progress, built one module at a time with a practitioner's input.
Pure Python 3.9+, no external packages (the map build and the parity tests need extras, below). Plan: [`docs/ROADMAP.md`](docs/ROADMAP.md) ·
progress: [`docs/LOG.md`](docs/LOG.md).

**Live report:** [jinli-kiki.github.io/scm-twin/docs](https://jinli-kiki.github.io/scm-twin/docs/) —
fourteen linked pages in the style of a BI report (slicers, KPI cards, cross-filtering charts):
Overview · Year run · Market · Atlas · Lanes · Footprint · MWD · Transfer · Business case ·
Demand & KPI · Ramp & boards · Finished goods · FG simulator · Rules. Four studio pages (FG
simulator, Demand & KPI, Ramp & boards, Footprint) carry a JavaScript copy of their model and
recompute live as inputs move; the Year run page does too.

**Runs on 2026 as it is** (readings to 13 November 2026, each dated and sourced on the Market
page): the Strait of Hormuz closed since February, ocean rates by lane from Drewry, SCFI and
Xeneta, US laptop duties after the Supreme Court ruling and the July Section 301 action, and the
memory price surge (DRAM contract ×6.8, NAND ×4.7 since mid-2025, TrendForce) as a switch every
module respects.

**Module 1 — MWD engine** (`src/mwd_engine.py`): when plans are cancelled or a region's
production leaves a factory, route every freed material to one of three fates —
absorbed by other plans (same part number), converted at a cost, or MWD — and price
the holding, ageing, rework and write-off cost. Platform collective EOL and NPI
part-number reuse decide how long common material can be absorbed.

**Module 2 — transfer cutover** (`src/transfer.py`): one region's production moves to a
new factory. For each possible cutover week inside the 16-week liability window, price the
China-origin tariff still paid on units built before cutover against the MWD, relocation,
holding and rework cost of plans cancelled after it. Built motherboards are origin-locked;
pre-SMT parts can be shipped to the new factory.

**Module 3 — transfer business case** (`src/business_case.py`): Monte Carlo of the annual
economics — tariff saved vs recurring costs of the longer chain (end-of-life MWD from a
longer commitment window and worse forecast, pipeline carrying, new-site conversion uplift)
and one-time costs (tariff leakage during ramp, rush expediting), by GSM strength.

**Module 4 — finished goods** (`src/finished_goods.py`): an old model's finished laptops as its
successor launches. Builds follow an optimistic sales forecast and need material ordered 16 weeks
ahead; sales locks the remaining volume 22 weeks before EOL and the final material is bought then; units held by
dealers at launch get price protection; leftovers go down the disposition paths (divert, rework,
tear down, liquidate, scrap) by net recovery; post-customs vs FTZ decides whether duty on
re-exported excess is sunk. Dealer leftovers return through stock rotation up to a cap; what
sales cannot sell the BU absorbs or resells through other GEOs. Compares push sell-in, sales plan,
sales lock, lock + drain, lock + push and lock + IBP hedge (no-lock strategies kept as benchmarks),
for the brand alone and for brand + dealers.

**Module 5 — demand and KPI view** (`src/demand_kpi.py`): a US tariff on China-made laptops
starts in week 0 of the fiscal year; part of it goes into the channel price, the price costs
units (constant elasticity), and the US volume can leave China in any week. Each option is scored
twice: by the BU's KPIs (shipment target in sell-in units, claimed MWD) and by the company's total
cost (tariff absorbed, margin on lost units, MWD, holding, relocation, longer chain). The page
maps where the two picks differ across tariff and pass-through.

**Module 6 — new-site ramp and risk board hedge** (`src/ramp_board.py`): a new site ramps over
about three months on an S-curve, slipped at random by material rhythm, yield and supplier
readiness, and can be pulled in at a rising cost; China pays the tariff on the gap. On the board
side, each SMT run builds boards for N weeks of forecast: boards strand at full value when a
model ends, loose parts migrate, and pushing builds back gives line time away and risks the ODM
moving the line to another customer, a risk far larger with a weak GSM. The model returns the
pull-in worth paying for and the board-build cover per model, picked on the expected cost and
the bad case (P90).

**Module 7 — factory footprint** (`src/footprint.py`): China and five candidate ODM sites
(Indonesia, Vietnam, Malaysia, Brazil, UAE) and nine regional distribution centres (US, EU, UK,
Japan, Brazil, Australia, Singapore, India, UAE). Landed cost per site and market from 2026
ocean rates by lane (pre-war, long-term contract or spot; with the Strait of Hormuz closed, Gulf cargo goes via Khor Fakkan), laptop
duties in force in November 2026, carrying, and three costs priced by Modules 2–4: the longer
chain, end-of-life stock and an urgent transfer. Each new site is a line on an ODM's existing
campus (price index, NRE, program cost, volume commitment with take-or-pay) or a bought
electronics plant, with NRE and plant price from the capex of real Vietnam campuses; a minimum-cost flow allocates demand within
capacity; every footprint is scored in every tariff scenario (including China curbing parts
exports) by expected cost and worst-case regret, with break-even duties and a
build-now-or-wait comparison. A back-test runs the model on the 2025 and 2026 China-only tariff
gaps against US imports by origin. Each duty can
also be stretched into a range, up to the April 2025 US peak by default, and a Monte Carlo
prices every footprint across the draws. Origin follows the
main board (US customs rulings), so a site that assembles China-made boards does not escape a
China tariff.

**Roadmap A4 — the year run** (`src/year_run.py`): a US tariff starts in week 0 and one fiscal
year is replayed week by week across Modules 1–7 for every cutover option: Module 5's price,
units and second-half catch-up, Module 6's S-curve ramp, Modules 1–2's cutover costs with MWD
settled at year-end, Module 3's expediting and longer chain, Module 4's end-of-life stock from
the longer transit. The page follows four strategies (stay, the company's pick, the BU's pick,
the model change) through the year, live in the browser (`src/dash/yr_engine.js`).

**Market monitor and memory lens** (`src/market.py`): the dated readings behind the inputs
(`data/market_watch.csv`), and every module run twice, with memory at 2025 prices and at Q4 2026
contract prices, to show which decisions the memory market moves.

**Report pages** (`src/build_dashboards.py`, templates in `src/dash/`): runs every module over
a grid of scenarios and writes self-contained pages to `docs/` (data embedded, charts from
ECharts). Slicers filter precomputed results, as in a BI report; the two studio pages
recompute in the browser with ports of the Python models (`src/dash/fg_engine.js`,
`src/dash/fp_engine.js`), and `tests/` checks the ports give the same numbers (needs Node.js).

**Network atlas** (`docs/atlas.html`): a world map of the network — six factory sites, real
export gateways, nine regional distribution centres (MGI), real ocean lanes (Cape of Good Hope
vs Suez, Hormuz open or bypassed via Khor Fakkan) with the straits they pass, air lanes, the parts feed from China into each new site,
door-to-MGI lead-time breakdowns, import duty by market and assembly site, and major highways
(truck lanes follow them). One complete world, no repeated copies. Open the file in a browser.
Rebuild after editing `data/nodes.csv`, `data/tariffs.csv` or `data/leadtime_params.csv`:
`pip install -r requirements-map.txt && python3 src/build_map.py`.

The company is anonymous and every site is illustrative.

```bash
python3 src/make_sample_data.py   # reset editable sample data in data/
python3 src/scenarios.py          # module 1: scenarios A/B/C0/C/D, per-material detail in output/
python3 src/transfer.py           # module 2: cutover-week sweep under tariff scenarios
python3 src/business_case.py      # module 3: annual business case, Monte Carlo
python3 src/finished_goods.py     # module 4: finished goods around a successor launch
python3 src/demand_kpi.py         # module 5: BU scorecard vs company cost for each transfer week
python3 src/ramp_board.py         # module 6: ramp pull-in and board-build cover per model
python3 src/integrate.py          # A4: price Module 7's chain, EOL-stock and transfer costs from modules 2-4
python3 src/footprint.py          # module 7: landed cost, allocation, footprints across tariff scenarios
python3 src/year_run.py           # A4: one fiscal year week by week across modules 1-7
python3 src/market.py             # market monitor: every module at 2025 and Q4 2026 memory prices
python3 src/build_dashboards.py   # rebuild the report pages in docs/ (about two minutes)
python3 tests/test_fg_parity.py   # browser engines match Python (needs Node.js)
python3 tests/test_fp_parity.py
python3 tests/test_dk_parity.py
python3 tests/test_rb_parity.py
python3 tests/test_yr_parity.py
```

All rules and numbers, and whether each is practitioner input, web-sourced or a placeholder:
[`docs/ASSUMPTIONS.md`](docs/ASSUMPTIONS.md).

## Disclaimer

This is an independent portfolio project. The company is anonymous and every site is
illustrative. Business rules describe general industry practice, generalized from hands-on
experience; no confidential information of any current or former employer, supplier or
customer is used. All numbers are illustrative defaults or come from the public sources
cited in `docs/ASSUMPTIONS.md`.

