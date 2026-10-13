# Work Log

## Day 1 — 2026-10-13

**Covered (Q1–Q19, see `ASSUMPTIONS.md`):** what MWD is and when it is counted; the 16-week
liability window and the claimed vs physical ledgers; which materials are common, convertible
or locked; 48-month tracking; collective EOL and NPI; netting via push-out/cancel at shared
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
- Practitioner numbers virtualized: 16-week liability window, 36-month tracking, new site in Indonesia.

## Next — Day 2
- Q20: how fast does a finished laptop in MGI lose value, when does discounting start?
- Module 4: finished goods at MGI — sell-in vs sell-through, excess build-up, disposition
  paths 1–6, post-customs vs FTZ.
