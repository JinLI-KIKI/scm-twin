# Work Log

## Day 1 — 2026-10-13

**Covered (Q1–Q19, see `ASSUMPTIONS.md`):** what MWD is and when it is counted; the 16-week
liability window and the claimed vs physical ledgers; which materials are common, convertible
or locked; 36-month tracking; collective EOL and NPI; netting via push-out/cancel at shared
ODMs; finished-goods disposition order; rework cost; origin lock at the motherboard;
relocating pre-SMT parts; +4 weeks lead time at a new SE Asia site; forecast ~8 points worse; risk board
hedge vs ODM capacity; new-site conversion +5–10%; slow ramp and rush shortages; tariffs not in
KPI but hitting the FY shipment target; MGI = post-customs regional DC; FTZ / bonded options.

**Built:**
- Module 1 `src/mwd_engine.py` + `src/scenarios.py` — MWD routing for cancelled plans
- Module 2 `src/transfer.py` — cutover-week sweep for a factory transfer
- Module 3 `src/business_case.py` — annual transfer business case, Monte Carlo
- `data/mgi_sites.csv` — researched regional distribution sites

**Key findings so far (all on placeholder costs):**
- A temporary cut creates little MWD if the region's demand returns early enough before EOL;
  a full-window cut close to EOL strands some region-locked parts.
- A transfer's unavoidable MWD is region-locked parts; transferring close to a collective EOL
  turns custom parts (battery pack, housing) into MWD too.
- Company-wide, MWD rarely decides *whether* to transfer (break-even China tariff ≈ 3%);
  it decides *when*. At BU level it bites harder: MWD is in the KPI, tariffs are not.

**Also built on day 1 (evening):**
- Network atlas `docs/index.html` (`src/build_map.py`, `src/map_template.html`): Natural Earth
  countries, real `searoute` ocean lanes with a Cape / Suez switch, China vs Indonesia origin,
  door-to-MGI lead-time breakdown, parts feed into Indonesia, import-duty layer.
- Project made anonymous: no real brand, illustrative sites, all English.
- Map fixed to one complete world (no repeated copies); highways drawn from Natural Earth and
  truck lanes routed along them; 1:50m country shapes.
- Practitioner numbers virtualized: 16-week liability window, 36-month tracking, new site in Indonesia.

## Day 2 — 2026-10-14

- Wrote [`ROADMAP.md`](ROADMAP.md): phases A–G, about 40–45 working days to a complete version.
- Q20–Q22 answered: value flat until the successor launches, then a step drop (R26); the drop is
  paid as price protection to dealers (R27); sales locks the remaining volume well before EOL,
  after which forecasts can only fall (R28, virtualized to 22 weeks).
- Q23: dealer leftovers go back through stock rotation or the dealer clears them; once sold in,
  the brand is mostly safe (R30). The lock is the brand's own: sales must sell it, otherwise the
  BU absorbs it or resells through other GEOs (R31).
- Q24: lock accuracy varies by GEO and salesperson, high or low → modelled as a ±10% spread
  between GEOs; new chart of cost against lock accuracy.
- Q25: locked is locked — material is ordered at the lock, nothing moves afterwards, a cut at the
  lock stands. The lock is now a frozen build plan with a final material buy; the no-lock
  strategies became benchmarks.
- Q26: the hedge at the lock is set by IBP from sales history and can be negative (R32) → new
  strategy "lock + IBP hedge".
- **Module 4 `src/finished_goods.py`** (Roadmap A1): weekly Monte Carlo of two old models in five
  MGI regions — order-up-to builds limited by material ordered 16 weeks ahead, dealer cover,
  sales volume lock, price protection at launch, excess disposition by net recovery, post-customs vs
  FTZ with drawback rules from public sources. Five strategies compared, from the brand's
  view and from the brand + dealer view.
- **Report pages**: eight linked BI-style pages in `docs/` (`src/build_dashboards.py`,
  `src/dash/`); the atlas moved to `docs/atlas.html` and shares the top navigation.

**Key findings (placeholder costs):**
- Pushing sell-in before launch raises the price-protection bill, but most of it is a shift:
  those units would otherwise be invoiced after launch at the lower price. It is the cheapest
  strategy for the brand, because dealers keep most leftovers beyond the stock-rotation cap (R30).
  Counted with the dealers' loss, the plain sales plan wins.
- A frozen lock costs more than a plan that keeps adjusting to the end: GEOs that lock high keep
  excess units, GEOs that lock low lose sales, and nothing is rebalanced until the end. The
  no-lock plan is only a benchmark (component end-of-life forces a final buy); the gap is what
  better lock accuracy or a hedge could recover.
- Lean high, not low: a low lock strands material already ordered and loses sales; a high lock
  leaves finished units that other GEOs can still take.
- An IBP hedge learned from sales history recovers part of the lock's cost, mostly by trimming
  GEOs that habitually lock high.
- Rework pays for gaming and consumer lines and not for education or convertibles, matching R11.

## Next
- Q27: what is the BU's FY shipment target counted in? (opens Module 5, demand and KPI view)
- Roadmap A2, Module 5: demand and KPI view (tariff → price → units → FY shipment gap; BU vs
  company view).
