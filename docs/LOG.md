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

- **Duty ranges up to the April 2025 peak** (`data/duty_ranges.csv`): every duty can be
  stretched by hand into a range (0–150%); by default the US runs from today's rate to its
  April 2025 peak (China 145%, Vietnam 46%, Indonesia 32%, Malaysia 24%, Brazil and UAE 10%).
  A Monte Carlo prices every footprint across the draws (mean, P10–P90, how often it is
  cheapest, regret), in a Web Worker on the page and in Python with the same random numbers.
- **Footprint page redesigned**: a decision summary on top, one card per site with its load
  against capacity and minimum load, then five numbered sections (allocation, one-tariff sweep
  to the ceiling with break-even duties, duty-range Monte Carlo with a fan chart and a duty
  sensitivity chart, named scenarios, duty matrix and chokepoints). Site colours were checked
  for colour-blind separation; dark-mode chart colours were darkened on every page to pass.

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
- With US duties free to move up to the April 2025 peak (20% chance of a change), China +
  Malaysia with boards made on site has the lowest mean cost: a repeat of April 2025 hits every
  Asian site at once, scaled to its own peak, and Malaysia's peak (24%) is the lowest. China
  alone stays the cheapest in about 80% of the draws but has a P90 of about $396M a year
  against $348M.

## Day 4 — 2026-10-16

**Built:**
- **Every value is a slider.** Footprint page: each duty, market by market and origin by
  origin, slides in the selected scenario (inputs panel, with an option to move every origin
  together, and a slider grid in the duty table); duty draws slide from 50 to 1,000. FG
  simulator: range ends are two-thumb sliders, runs slide. Transfer timing: the China tariff
  slides from 0 to 50% in 1% steps (grid recomputed at every step). Finished goods: price drop,
  sales optimism and lock style slide across the computed grid, with the simulator linked for
  values in between.
- **2026 reality in Module 7.** The Strait of Hormuz has been closed since 28 Feb 2026: Gulf
  cargo now lands at Khor Fakkan and is trucked to Dubai (new node, bypass routes in the atlas,
  a Hormuz switch on the atlas, lanes and footprint pages). Ocean rates come from lane
  benchmarks (SCFI, Drewry WCI, Xeneta) for late February and October 2026, blended by a
  freight-basis slider; Far East–Brazil is ×6.6 and Far East–Gulf ×5.8, Far East–Japan flat.
- **ODM structure (R35).** New sites are ODM lines: price index on the China line, one-time
  NRE spread over the horizon, yearly program cost, and a volume commitment with a take-or-pay
  fee instead of a hard minimum load.
- **China parts curbs** as a sixth scenario (R39): non-China sites pay a premium on China
  parts.
- **A4, first link (R40).** `src/integrate.py` prices three Module 7 costs from Modules 2–4 and
  writes `data/linkage.json`: chain $1.29 per unit per extra week (Module 3), end-of-life stock
  $1.71 per unit per extra week of transit (Module 4, launch held fixed), urgent transfer $226
  per unit of weekly volume (Modules 1–3). Each Module 2–4 page shows what it feeds.
- **Back-test (R41)** against US imports by origin (Census, HS 8471): in 2025 the model moves
  the US to Vietnam only with boards made there (100% vs 0%; actual about 60%), and in 2026
  staying in Vietnam is rational once a renewed China tariff has more than 15% weight (the
  model uses 20%). Python and the browser engine agree on 3,404 numbers.

**Results:**
- Cheapest under today's duties: China + Brazil ($329.0M a year). Lowest expected cost over the
  named scenarios: China + Brazil ($339.0M), China + Vietnam with own boards a close second
  ($339.2M). Lowest worst-case regret: China + Malaysia with own boards ($4.9M a year).
- Under the duty ranges China + Malaysia with own boards has the lowest mean ($337.0M).
- At today's duties the Asian hedge lines run below their commitment and pay take-or-pay:
  China is cheaper per unit by more than the $12 fee. Building a hedge now beats waiting once
  the China-tariff weight passes about 42–43%.

**Afternoon — real indices for Q30 and Q31:**
- **Ocean rates (Q30).** Each lane now has three readings: pre-war (late Feb 2026), long-term
  contract (Xeneta, Aug 2026: Far East–US West Coast $2,854, Far East–North Europe $2,690, both
  +41%) and spot (Oct 2026). The plan pays the contract rate by default; the slider runs from
  pre-war (0) through contract (1) to spot (2).
- **ODM line or bought plant (Q31).** Each new site is either a line on an ODM's existing campus
  or a bought electronics plant (switch per site). NRE and the plant price follow capex per
  laptop of yearly capacity of real Vietnam campuses ($4.2 Wistron Ha Nam Victory II fit-out,
  $13.3 Quanta Nam Dinh; cross-check Tata–Wistron India $125M for 10,000 workers); a bought plant
  keeps the ODM's 1.4% operating margin (Compal FY2025) and carries its own overhead,
  depreciation, capital and idle labour. Ramp-up depends on the mode (6 months on an existing
  campus, 9 for a bought plant; a campus from scratch took 16–20 months).
- **Results.** Expected cost: China + Brazil $337.9M, China + Malaysia with own boards $338.5M
  (lowest regret, $5.2M). With a 6-month ramp on an existing campus, waiting gets cheaper:
  building a hedge now pays once a China tariff passes about 60% (was 42%). Buying the plants
  instead of ODM lines costs about $1M a year more at half load. Parity: 3,524 numbers.

## Day 5 — 2026-10-20

**Built — Module 5, demand and KPI view (Roadmap A2):**
- `src/demand_kpi.py`: a US tariff on China-made laptops starts at week 0 of the fiscal year;
  part of it goes into the channel price from the repricing week, units follow a constant
  elasticity, and the US volume can leave China in any week (0–16 inside the liability window,
  20, 26, 39) or not at all this year. The new site ramps up linearly; China builds the rest and
  pays the tariff.
- **Two scorecards (R42, R43).** BU: shipment attainment in sell-in units (R33) and claimed MWD
  (every plan cancelled inside the window at full BOM value, R1/R8), plus the extra end-of-life
  MWD of the longer window. Company: tariff absorbed, margin on lost units, physical MWD,
  holding and relocation (Module 2), expediting, longer chain and conversion uplift (Module 3).
  The BU picks the latest option that still ships 98% of the target; the company the cheapest.
- Inputs from public data: 100% pass-through and a 2-week repricing lag (Acer, Feb 2025), 4%
  absorbed by exporters (Kiel Institute), elasticity −0.7 (Omdia 2026).
- `src/dash/dk_engine.js` + `tests/test_dk_parity.py` (747 values, identical); new page
  `docs/demand.html` with sliders for every input, both picks, the cost and BU charts, the
  weekly sell-in, a tariff × pass-through map of the disagreement and the option ledger.

**Results (25% tariff, fully passed on):**
- BU cuts over in week 4 (attainment 98.1%, claimed MWD $13.2M); the company would wait until
  week 16 (attainment 95.5%, cost $3.05M). With the tariff in the price, the shipment target makes
  the BU move earlier than the company needs; the BU's pick costs $0.20M.
- With the tariff absorbed by the company the BU stays in China (no lost units, no MWD) while the
  company moves in week 0: the BU's pick costs $12.3M at 25% and $27.1M at 50%.
- Counted as physical MWD (after relocation) the BU's MWD from a cutover is almost zero, so
  most of the disagreement is the counting rule (R1), not the material.

**Afternoon — the fiscal-year target rule (Q32 answered):**
- The BU must ship 100% of the fiscal-year target and usually beats it, so the pre-tariff plan
  sits above it (modelled 3%, Q33). The annual target is not lowered; the rhythm moves instead:
  Q1 and Q2 come in lower and Q3 or Q4 is raised. Modelled as a channel discount from week 26,
  as large as needed to close the gap (up to 10%), a company cost (R45). The target is lowered
  only when even the cap cannot close it. The company holds the target too and picks the
  cheapest option that reaches it.
- Result at a 25% tariff, fully in the price: the BU waits until week 20 and needs 7% off in
  Q3–Q4 ($3.4M) to make the year; the company would move in week 9 and need no discount. The
  BU's pick costs $2.8M. With the tariff absorbed by the company the BU stays in China and the
  company moves in week 0 ($8.9M).
- Parity: 1,770 values identical, with the catch-up.

## Next — Day 6

- **Jin to judge:** the take-or-pay fee and commitment (Q28), ramp months by mode and rush
  premium (Q29), own-plant overhead and labour share.

- **Formula and algorithm review with Jin**, module by module (spec in `docs/models/`).
- **Jin to judge Module 5:** how far the plan beats the target and the catch-up discount cap
  (Q33), pass-through and the repricing lag, elasticity by model (Q17).
- Then Roadmap A3, Module 6: new-site ramp and risk board hedge.
