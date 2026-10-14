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
  paid as price protection to dealers (R27); dealers lock volumes well before EOL, after which
  forecasts can only fall (R28, virtualized to 22 weeks).
- **Module 4 `src/finished_goods.py`** (Roadmap A1): weekly Monte Carlo of two old models in five
  MGI regions — order-up-to builds limited by material ordered 16 weeks ahead, dealer cover,
  dealer lock, price protection at launch, excess disposition by net recovery, post-customs vs
  FTZ with drawback rules from public sources. Four strategies compared.
- **Report pages**: eight linked BI-style pages in `docs/` (`src/build_dashboards.py`,
  `src/dash/`); the atlas moved to `docs/atlas.html` and shares the top navigation.

**Key findings (placeholder costs):**
- Pushing sell-in before launch raises the price-protection bill, but most of it is a shift:
  those units would otherwise be invoiced after launch at the lower price. The real extra cost is
  dealer leftovers that come back.
- A dealer lock that is information only cuts excess finished goods by about three quarters but
  turns part of it into EOL MWD (the material is already ordered) and raises lost sales. Its value
  depends on whether the locked volume binds the dealer (Q23).
- Rework pays for gaming and consumer lines and not for education or convertibles, matching R11.

## Next
- Q23: is the locked volume binding on the dealer, and who carries the leftover?
- Roadmap A2, Module 5: demand and KPI view (tariff → price → units → FY shipment gap; BU vs
  company view).
