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

**Evening — price points against MWD (Q33):**
- Planners do not know the points: sales planning asks sales, sales negotiate them with the
  channel, and the BU may have to fund them. So the BU now weighs the MWD it avoids by moving
  later against the points it pays to catch up (R43, R45). Not a one-way rule: it depends on the
  price of MWD (what $1 of MWD finally costs the BU), the price of the points (share the BU funds,
  share that reaches the shelf, elasticity) and how much of the claimed MWD migrates.
- New page section "What moves the BU's pick": the BU's cutover week across the MWD price and
  one of migration share / BU share of points / points reaching the shelf; and "The BU's
  balance": claimed, migrated, MWD cost, points and the total per key option.
- At the defaults (25% tariff in the price, 50% migrates, $1 per $): the BU waits until week 16,
  the company moves in week 9; the BU's pick costs the company $1.7M. With 80% or more
  migrating, or MWD at $0.50 per $ or less, the BU picks the company's week.
- Parity: 2,709 values identical.

**Late — migration share and MWD price from public data (Q34):**
- No public source gives a migration share. Bounded by part type instead: industry-standard
  parts (CPU + DRAM + SSD: 45% of a mainstream notebook BOM in 1Q25, 68% in 3Q26, TrendForce)
  are the supplier's to re-use; customized, single-customer, EOL and MOQ parts are NCNR. Excess
  components resell at 5–15% of cost.
- Transfers move one region while the same models stay in China for other regions (Q34), so only
  region-specific parts stay: default 90% migrates (range 45–95%), $0.90 per $1 of MWD that
  stays. A "transfer pattern" switch sets one region (90%) or a whole model/platform (55%).
- Result: at a 25% tariff in the price the BU and the company now both pick week 9; the BU's pick
  flips back to week 16 below about 70% migration. They still disagree when the company absorbs
  the tariff (BU stays, company moves in week 0).

**Last — negotiated pass-through (Q35):**
- Pass-through is negotiated; the company absorbing the tariff is possible but unlikely. Each
  option is now scored on expected costs over two cases: 85% of the tariff in the price (90%)
  and absorbed by the company (10%). Units, weeks and the catch-up are those of the negotiated
  case; the target must be made in both.
- Result at a 25% tariff: the BU picks week 11, the company week 0 (the 10% absorb chance makes
  every China week dearer for the company); the BU's pick costs $0.45M in expectation.
- Parity: 3,483 values identical.

- Q36 answered: the new price lands in about 2 weeks, as Acer's in Feb 2025 (kept).

**Module 6 — new-site ramp and risk board hedge (Roadmap A3):**
- Q12 answered: about three months from the first trial build to full volume, and it can be
  pulled in; material rhythm, yield and supplier readiness are all problems (R46).
- `src/ramp_board.py`, Part A: an S-curve ramp over 13 weeks less the weeks pulled in, plus a
  random slip from each of the three gates (chances lower with a strong GSM). China builds the
  gap and pays the tariff; failed units consume material; pulling in costs more for every
  further week. At a 25% tariff the median ramp is 14.7 weeks; pulling in 7 weeks (the most the
  line allows) brings it to 7.7 and saves $0.9M (leakage $2.86M → $1.63M).
- Part B (R47): boards per SMT run of 1–8 weeks of forecast. Boards strand at full value when a
  model ends or is cut, loose parts migrate; short runs cost setups and the SMT capacity the ODM
  keeps back. First run with a 4-week standard: P1-14 4 weeks, P1-16 (sold below plan) 3, P2-14
  (new) 3; with a weak GSM no model is stretched.
- `src/dash/rb_engine.js` + `tests/test_rb_parity.py` (726 values identical); new page
  `docs/ramp.html` with every input as a slider, per-model risk sliders, the ramp band, cost
  by pull-in, the gates, cost by cover per model and the board ledger.

- Q37 answered: the ODM builds about 8 weeks of boards per SMT run, and board builds can be
  pushed later. With the 8-week standard (covers 1–8 weeks): strong GSM → P1-14 6 weeks,
  P1-16 and P2-14 5 weeks; weak GSM → P1-14 and P2-14 7, P1-16 6. The capacity the ODM takes
  back stays a placeholder (Q38).

## Day 6 — 2026-11-13

**Module 6 — Q38 answered: the GSM makes a large difference.** When board builds are pushed
back, the ODM gives the capacity to other customers and capacity may drop; that is the risk.
- Two effects, both far larger with a weak GSM: line time given away in every pushed run (as
  before, 35% / 80% × push), and a new risk event: each week the model sells, with chance
  hazard × push (0.5% / 3% a week at a full push) the ODM moves the model's line to another
  customer, and builds and rush capacity drop 25% / 50% for 13 weeks.
- The cover is picked on 75% expected cost + 25% P90, so the bad years count (`risk_weight`).
- Result: strong GSM P1-14 6 weeks, P1-16 6, P2-14 5 (the line moves in 4–5% of years at those
  covers); weak GSM 7, 7, 8 (9–11% of years at 7 weeks; at 5 weeks it would be 26–28%).
- Page: chance the line moves by cover (strong against weak), a strong-vs-weak table, P90 lines
  on the cost chart, the chance in the ledger, sliders for every new input. Parity 1,448 values.

**Market monitor (Roadmap E2, first half) — new page `docs/market.html`, `src/market.py`.**
- 22 dated readings with source and the input each feeds (`data/market_watch.csv`): Drewry WCI
  12 Nov (Shanghai–Los Angeles $7,416, –Rotterdam $3,504), SCFI 30 Oct (Gulf, Australia,
  Singapore, Japan), Xeneta's 2027 outlook (long-term −5%, spot −30%), Hormuz day 257 (3 transits
  a day against 85), US laptop duties (still 0% for every origin; Section 232 phase 2 confirmed
  in Sep with laptops named as a possible target, no rate), TrendForce memory contract prices,
  IDC Q3 PC shipments (−20.1%), notebook output outside China (24% → 21%).
- Spot ocean rates moved to November 2026 on every lane with a print; fallback factor 2.8.

**Memory lens (R48).** DRAM ×6.8 and NAND ×4.7 since Q2 2025 (`data/memory_prices.csv`).
- One switch in the shared loader (`memory_market`, default 0 = 2025 base): memory parts take the
  index, customs values rise by the same dollars, channel prices keep their markup.
- P1-14 BOM $367 → $728 (memory 20% → 60%), board $195 → $426, customs value $480 → $841.
- What moves: the risky P1-16's board run 6 → 3 weeks (strong GSM), the lowest-cost footprint
  CN + BR → CN + MY + BR with own boards; transfer-year net at 25% $14.3M → $25.1M, break-even
  tariff 3.0% → 2.4%. What does not: the cutover picks (BU week 11, company week 0), the physical
  MWD, the weak-GSM board runs.
- Switch on the Year run, Demand, Ramp, Footprint and FG simulator pages; the Market page runs
  every module both ways.

**Roadmap A4 — the year run. New page `docs/year.html`, `src/year_run.py`.**
- One fiscal year week by week across Modules 1–7: Module 5's units, catch-up and absorb chance;
  Module 6's S-curve ramp instead of the straight line; Modules 1–2 cutover costs, MWD at the
  year-end reconciliation; Module 3 expediting and the longer chain; Module 4 end-of-life stock
  from the longer transit (6.3 days Indonesia vs China to the US MGI).
- At 25%, strong GSM: staying costs $9.64M and ships 94.3% of plan (misses the 97% target even
  with a 10% catch-up); the company moves in week 0 ($4.10M; cheaper than staying from week 19);
  the BU waits to week 13 ($4.58M); the model change (week 26) $7.98M.
- Live studio: `src/dash/yr_engine.js` ports `src/year_run.py` on top of the Module 5 and 6
  engines; the tariff, GSM, memory prices and 13 price, target and ramp inputs are sliders
  (about 0.2 s a run). `tests/test_yr_parity.py`: 616 values identical.

**Site.** Navigation grouped (Start · Network · Transfer · End of life · Sources) with the two
new pages. Overview: a strip of six market readings, the year-run hero with the cost-to-date
chart, the module cards in the order a tariff decision runs, eight KPI cards in two rows.

**Questions for Jin, sent together:** Q7, Q28, Q29, Q33 (still open) and Q39–Q52 (new: capacity
recovery, risk appetite, memory pass-through and default, memory configs, region vs model
moves, decision lag, scenario chances, and six sets of placeholder sizes).

## Day 6, continued — 2026-11-13: practitioner answers Q7, Q28, Q29, Q33, Q47–Q52

**Confirmed as modelled:** Q7 (standard parts non-cancellable 2 weeks before delivery, custom
parts their whole lead time), Q28 (50% minimum load, fee = max(0, 50% − utilization) × rated
capacity × $12), Q29 (6 months on an existing ODM campus with the board line, 9 months to buy and
refit a plant, counted from the formal project start; preparation is done beforehand but no heavy
spending on rumours), Q33 (plan 3% above target, catch-up price points up to 10%).

**Module 6 — ramp (Q47, Q48):**
- Supplier readiness slips with 37.5% on an existing ODM campus (35–40%) and 50% at a new plant
  (new switch on the page); the total slip is capped at 7 weeks because slips overlap (6–8).
- Yield follows 85% → 91% → 95% → 97% → 98% over 4 weeks for a mature product moving lines,
  6–8 weeks for a new product or new suppliers (slider).
- Pull-in is paid only on the volume brought forward: $6, $9, $13.50, $20.25 per unit for the
  first four weeks pulled (compounding ×1.5).
- Result: median ramp without pull-in 14.2 weeks (was 14.7); pulling in 7 weeks still pays.

**Module 6 — boards (Q49):** rush boards cost 25% of the board's own price (without CPU and
memory), between $3 and $10; 30% of the units still short are lost (half is now the stress case).
Strong GSM covers P1-14 6, P1-16 3, P2-14 5 weeks (P1-16 was 6: shortages cost less); weak GSM 7,
7, 8.

**Module 7 — site cost (Q50):** each site's index is a steady-state cost against China = 1.00 with
a range (ID 1.00–1.10, VN 0.98–1.08, MY 1.08–1.20, BR 1.45–1.75, AE 1.25–1.50); the duty Monte
Carlo now draws every site inside its range (`site_cost_draw`). Context from JETRO's Aug 2025
survey: worker base pay China $629, Malaysia $549, Thailand $490, Indonesia $385, Vietnam $302
a month.

**Modules 3, 5 and the year run — temporary uplift (Q51):** the 7.5% conversion uplift is paid
only while the new line ramps, falling to 0 over 26 weeks, so it is no longer a yearly cost in the
business case (break-even tariff 3.0% → 2.6% with a strong GSM, 3.5% → 3.1% weak). Expediting
with a weak GSM is 1.5× the strong rate ($9), 2× is the stress case.

**Modules 5 and the year run — MWD price by part (Q52):** MWD that stays costs the BU $0.60 per
dollar of standard parts (CPU, memory, SSD, panel) and $0.90 of custom or model-locked parts;
`src/transfer.py` now splits freed material and MWD by class. Carrying 20% a year kept (APQC's
realized median is about 10%; planning models use 20–25%).
- Year run at 25%, strong GSM: stay $9.64M; company week 0 $3.80M (was $4.10M); BU week 14
  $4.46M; model change $7.77M.

**Parity:** Module 5 3,483, Module 6 1,810 (a new variant for the campus switch, slip cap, yield
weeks and rush premium), footprint 3,524, year run 616 values identical.

## Next — Day 7

- Jin's answers to the rest of the batch (Q39–Q46: capacity recovery, risk appetite, memory
  pass-through and default, memory configurations, region vs model moves, decision lag, scenario
  chances).
- Then Phase B (Mexico and Thailand, AI servers) or Phase C (inventory policy), Jin to choose.
