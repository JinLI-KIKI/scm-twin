# Market monitor and memory lens: formulas

Code: `src/market.py`; the switch itself lives in `src/mwd_engine.py` (`memory_market`,
`memory_index`, `price_scale`). Data: `data/market_watch.csv` (readings), `data/memory_prices.csv`
(index), `memory_market` in `data/params.csv` (default). Rules: R48, R49. Page: `docs/market.html`.

## Memory price index

From TrendForce's quarterly contract changes `g_q` (midpoint of each published range):

```
index(Q2 2025) = 1,   index(q) = index(q − 1) × (1 + g_q)
```

DRAM: +12.5%, +47.5%, +95.5%, +60.5%, +15.5%, +12.5% (Q3 2025 → Q4 2026, the last a forecast).
NAND: the 2025 quarters are anchored on one client SSD contract price (4.03× from Q3 2025 to Q3
2026), the 2026 quarters on TrendForce.

## Memory lens

With `memory_market = 1`, for every material `m`:

```
unit_cost(m) = base_cost(m) × index_DRAM(latest)   if m is MEM_*
             = base_cost(m) × index_NAND(latest)   if m is SSD_*
memory delta of a model     Δ = Σ_m (unit_cost − base_cost) × qty, over its BOM
customs value               cv' = cv + Δ                        (ODM passes memory on at cost)
channel price               p'  = p × cv' / cv                  (markup kept)
footprint (P1-14)           customs value and parts shipped to other sites + Δ
```

Everything downstream (board value, freed and MWD value, carrying, tariff, finished-goods
values) follows from these. `src/market.py` runs each module at both levels and reports the
decision each recommends; the studio pages (year run, demand, ramp, footprint, FG simulator)
switch it live.
