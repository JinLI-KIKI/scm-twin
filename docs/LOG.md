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

## Day 3 — 2026-10-15

**Built:**
- **Finished-goods simulator** (`docs/fg-live.html`, Roadmap F1 pulled forward): every Module 4
  input is a slider, or a low–high range sampled per run (triangular), and the model re-runs in
  the browser in a Web Worker (6 strategies × 200 runs in about 0.4 s). The JavaScript engine
  (`src/dash/fg_engine.js`) is a line-by-line port of `src/finished_goods.py` with the same
  portable random-number generator; `tests/test_fg_parity.py` checks both agree to 1e-15.
  A week-by-week state view (kits → in transit → MGI → dealers → customers) plays the run.
- **Six candidate sites and nine markets.** Vietnam (Bac Ninh), Malaysia (Penang), Brazil
  (Jundiai) and the UAE (Jebel Ali Free Zone) join China and Indonesia; Australia, Singapore,
  India and the UAE join the US, EU, UK, Japan and Brazil as MGIs. The atlas and the lanes
  page cover every pair, with the straits each ocean lane passes (`searoute`) and a parts feed
  from China into every new site. Same-country lanes go by truck.
- **Real laptop duties, October 2026** (`data/tariffs.csv`, one column per site): zero in the
  US, EU, UK, Japan, Australia, Singapore and India from every site; Brazil 16% (0% for
  Brazil-made); the UAE 5%, free-zone units included. Four scenarios: a 25% US tariff on
  China-made laptops, Section 232 phase 2 on every origin, the July 2026 Asia Section 301 rates
  without the computer exemption, and Brazil dropping its 16%.
- **Module 7 — factory footprint** (`src/footprint.py`, `docs/footprint.html`): landed cost per
  site and market; a minimum-cost flow that allocates demand within site capacity and minimum
  loads; every feasible footprint scored in every scenario (expected cost, worst-case regret);
  break-even China duty per site and market; build now or wait, with the scenario weight at
  which building now wins. **Origin follows the main board** (R13, R34; CBP rulings N350187 and
  N357691): a site assembling China-made boards pays the China rate, so footprints come in two
  variants, boards imported or made on site. The page recomputes all of it live
  (`src/dash/fp_engine.js`, exact parity in `tests/test_fp_parity.py`).

**Key findings (placeholder costs, real duties):**
- Under today's duties China is the cheapest source for every market except Brazil, where a
  local site saves the 16%. A UAE free-zone site saves nothing on the UAE's 5%.
- A second Asian site is no hedge against a US tariff on China-made laptops unless it makes its
  own main boards: assembling China-made boards, it pays the China rate too. Making boards on
  site, Vietnam beats China in the US once that tariff passes about 4%.
- China alone has the lowest expected cost; China + Malaysia or China + Vietnam with boards made
  on site costs about $0.3M a year more in expectation but cuts the worst-case regret from
  $18.4M to $4.9M a year.
- With a 12-month ramp-up and a 20% weight on the China tariff, waiting beats building now.
  Building the hedge now wins once that weight passes about 43%.

## Next — Day 4

- **Practitioner check of Module 7**: minimum load of a hedge site (Q28), time to open and
  qualify a site and its board line (Q29), conversion cost by site.
- **Formula and algorithm review with Jin**, module by module (spec in `docs/models/`).
- Then Roadmap A2, Module 5: demand and KPI view. Q27 answered: the BU's FY shipment target is
  counted in sell-in units (R33).
