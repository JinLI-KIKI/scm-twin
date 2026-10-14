# Supply Chain Twin — tariff-driven factory transfer & MWD

Work in progress, built one module at a time with a practitioner's input.
Pure Python 3.9+, no external packages. Plan: [`docs/ROADMAP.md`](docs/ROADMAP.md) ·
progress: [`docs/LOG.md`](docs/LOG.md).

**Live report:** [jinli-kiki.github.io/scm-twin/docs](https://jinli-kiki.github.io/scm-twin/docs/) —
eight linked pages in the style of a BI report (slicers, KPI cards, cross-filtering charts):
Overview · Network atlas · Lanes & lead time · MWD · Transfer timing · Business case ·
Finished goods · Rules register.

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
ahead; dealers lock volumes 22 weeks before EOL (forecasts can then only fall); units held by
dealers at launch get price protection; leftovers go down the disposition paths (divert, rework,
tear down, liquidate, scrap) by net recovery; post-customs vs FTZ decides whether duty on
re-exported excess is sunk. Compares push sell-in, sales plan, dealer lock, lock + drain.

**Report pages** (`src/build_dashboards.py`, templates in `src/dash/`): runs every module over
a grid of scenarios and writes self-contained pages to `docs/` (data embedded, charts from
ECharts). Slicers filter precomputed results, as in a BI report.

**Network atlas** (`docs/atlas.html`): a world map of the network — two factory sites
(China, Indonesia), real export gateways, five regional distribution centres (MGI), real
ocean lanes (Cape of Good Hope vs Suez), air lanes, the parts feed from China into Indonesia,
door-to-MGI lead-time breakdowns, import duty by country, and major highways (truck lanes
follow them). One complete world, no repeated copies. Open the file in a browser.
Rebuild after editing `data/nodes.csv`, `data/tariffs.csv` or `data/leadtime_params.csv`:
`pip install -r requirements-map.txt && python3 src/build_map.py`.

The company is anonymous and every site is illustrative.

```bash
python3 src/make_sample_data.py   # reset editable sample data in data/
python3 src/scenarios.py          # module 1: scenarios A/B/C0/C/D, per-material detail in output/
python3 src/transfer.py           # module 2: cutover-week sweep under tariff scenarios
python3 src/business_case.py      # module 3: annual business case, Monte Carlo
python3 src/finished_goods.py     # module 4: finished goods around a successor launch
python3 src/build_dashboards.py   # rebuild the report pages in docs/ (about one minute)
```

All rules and numbers, and whether each is practitioner input, web-sourced or a placeholder:
[`docs/ASSUMPTIONS.md`](docs/ASSUMPTIONS.md).

## Disclaimer

This is an independent portfolio project. The company is anonymous and every site is
illustrative. Business rules describe general industry practice, generalized from hands-on
experience; no confidential information of any current or former employer, supplier or
customer is used. All numbers are illustrative defaults or come from the public sources
cited in `docs/ASSUMPTIONS.md`.

