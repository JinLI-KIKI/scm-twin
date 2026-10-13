# Assumptions Register

Every rule and number in the model, with where it came from. Status:
**PRACTITIONER** = generalized from hands-on industry practice; sites and numbers are virtualized (no employer-specific data) · **WEB** = sourced online · **PLACEHOLDER** = invented, needs calibration · **OPEN** = question pending.

Last updated: 2026-10-13 (v0.5: virtualized — 16-week window, 36-month tracking, new site in Indonesia)

## Business rules — MWD (Material Without Demand)

| ID | Rule | Status |
|---|---|---|
| R1 | A plan cancelled inside the **16-week** liability window counts as MWD (liability) for the full BOM, whether or not the ODM actually stocked the material. | PRACTITIONER |
| R2 | Same part number used by other plans → MRP netting absorbs it: the factory buys less, stock burns down naturally. Not MWD. | PRACTITIONER |
| R3 | Freed stock is netted by pushing out / cancelling other plans' open POs. Push-out only moves timing; MWD is decided by how much of the order book is **non-cancellable**. Netting offsets demand beyond each material's non-cancellable window. | PRACTITIONER (direction) |
| R10 | Shared ODMs: industry-standard parts (CPU, memory, SSD, panel) are also bought by other brands, so ODM/supplier can redeploy them → short non-cancellable window. Custom parts (battery pack, housing, keyboard) → window = full lead time. | PRACTITIONER (direction); window lengths PLACEHOLDER |
| R4 | Consumption is tracked for **36 months** (adjustable). | PRACTITIONER |
| R5 | Collective EOL and NPI both matter: demand stops at platform EOL; an NPI absorbs old stock only if it reuses the same part number. | PRACTITIONER (mechanics: OPEN) |
| R6 | Non-common but convertible material needs the planner to negotiate with other GEO BUs and own BU, then pay to convert (改料). Locked material → MWD. | PRACTITIONER |
| R7 | Material routing classes (CPU/memory/SSD/panel/battery/adapter/housing = 1; cord/packaging = 2; keyboard/WWAN = 3). | PRACTITIONER |
| R8 | Two ledgers: **claimed** MWD (plan basis) vs **physical** MWD (stock-take). Gap comes from ODM hedging; sometimes ODMs do not report. Settled at fiscal-year end. | PRACTITIONER |
| R9 | Factory transfer cuts off a region's consumption path for its region-locked MWD → drives transfer timing. | PRACTITIONER |
| R11 | Finished-goods disposition order: 1 sell in original region at discount → 2 divert to same-config markets → 3 rework → 4 tear down for service parts → 5 liquidate → 6 scrap. 3 is skipped for low-value lines (e.g. EDU) and done for high-value lines (e.g. gaming). | PRACTITIONER |
| R12 | Rework is quoted case by case by the ODM; cost = parts + labour. Keyboard-only ≈ 2–5% of unit cost; often 30–50%; hard designs (convertible 2-in-1 with touch) 70%+. | PRACTITIONER (ranges illustrative) |
| R14 | Pre-SMT components left at the old factory are routinely shipped to the new factory, because the new location's local supply base is incomplete and China parts flow there anyway. They take the new site's origin once SMT/base-unit assembly happens there. | PRACTITIONER |
| R15 | After transfer, parts still come from China, so lead time to the new factory gets longer (supplier lead time + cross-border transit + import handling). Plans must be committed earlier → longer commitment window, more forecast error inside it, more in-transit and safety stock → **recurring** extra MWD and inventory every year, not a one-time cost. | PRACTITIONER (direction); size OPEN — Q11 |
| R17 | Transfer to a new Southeast Asian site: **+4 weeks lead time** by default. Sales must give a **quarterly plan** to cover the longer horizon. Long-lead parts such as **OLED** panels get an earlier pull-in rhythm. | PRACTITIONER |
| R18 | Longer horizon → forecast vs actual gets worse, but by a limited amount: **~8% worse**. Forecast accuracy was never very good to begin with. | PRACTITIONER |
| R19 | **Risk board hedge (风险打板):** for uncertain models, or models that sold badly in the past, delay/stretch the board-build (SMT) cadence so material stays loose and liquid. Cost: if you keep not loading boards, the ODM cuts the capacity it gives you — needs a strong GSM function to keep capacity stable. | PRACTITIONER |
| R20 | New-site conversion cost (labour + new line) **+5–10%** vs China. | PRACTITIONER |
| R21 | Rushing a transfer → certain material shortage at the new factory (lead time +4 weeks not yet covered). Expediting helps but on-time delivery is not guaranteed; also depends on capacity and worker learning. Duration is hard to predict and depends heavily on GSM strength. | PRACTITIONER |
| R22 | **Tariffs are not in the planner/BU KPI; MWD is.** But tariffs reach the BU through volume: higher tariffs raise consumer prices, which threatens the fiscal-year shipment target. So the BU-level trade-off is MWD (KPI) + shortage risk from rushing (shipment KPI) vs tariff-driven demand loss (shipment KPI). | PRACTITIONER |
| R23 | Finished goods first go into **MGI**, rarely straight to merchants/channel. Both low-end and premium segments are hit by price rises. So a price-driven demand drop does not cut factory shipments at once — it accumulates as excess finished goods in MGI (then ageing, price erosion, disposition per R11). Sell-in can hit target while sell-through misses; the gap sits in MGI. | PRACTITIONER (flow); MGI definition OPEN — Q18 |
| R24 | **MGI = regional distribution warehouse, located after customs clearance.** Ownership differs by company: brand-owned, or space briefly leased through a logistics provider — never the ODM. Known sites in `data/mgi_sites.csv`. | PRACTITIONER · sites ILLUSTRATIVE |
| R25 | **Customs status of MGI stock is a tariff hedge.** Post-customs (the common default): duty is paid on arrival, so diverting excess abroad leaves the duty sunk unless drawback is allowed (the Jan 2026 semiconductor 232 proclamation bars drawback). US FTZ: re-exports pay no duty; goods destroyed under CBP supervision pay no duty; no storage time limit. But 2025-26 actions (Section 301, several 232s, the 60-economy 301 from 24 Jul 2026) force privileged-foreign admission: the rate is locked at admission, irrevocably — you cannot wait in the zone for a lower rate. Bonded warehouse: up to 5 years, rate set at withdrawal (exposed both ways). Sources disagree on whether duty is still deferred under forced PF status. | WEB — [GingerControl](https://gingercontrol.com/blog/foreign-trade-zones-reduce-tariff-exposure), [Cargolinked](https://cargolinked.com/guides/foreign-trade-zones-vs-bonded-warehouses); practitioner: possible, details unknown |
| R16 | New factories ramp slowly — capacity, yield and certification lag — so transfer is a gradual curve, not a switch. The old factory keeps covering the gap (still paying China-origin tariff); yield loss at the new site consumes material without output. | PRACTITIONER (direction); ramp shape OPEN — Q12 |
| R13 | **Origin lock at the motherboard.** US customs mostly judges origin by the motherboard; once the board is built (SMT done) its origin is fixed — final assembly elsewhere does not change it. A built board that cannot be used is scrapped. Only pre-SMT components can be moved to a new factory and change origin. | PRACTITIONER · WEB: CBP NY N305378 (Chinese subassemblies assembled in Taiwan → China origin) |

## Network atlas (map) — added 2026-10-13

| Item | Value | Status |
|---|---|---|
| Company | Anonymous laptop maker; no real brand is modelled | Design choice |
| Factory sites | Kunshan, Jiangsu (current) and Cikarang, West Java, Indonesia (new) — `data/nodes.csv` | ILLUSTRATIVE |
| MGI sites | Inland Empire CA, Venlo NL, Daventry UK, Atsugi JP, Campinas BR — `data/mgi_sites.csv` | ILLUSTRATIVE (typical electronics DC hubs) |
| Ports and airports | Real gateways (UN/LOCODE, IATA codes) | WEB-KNOWN |
| Ocean paths and distances | `searoute` open-source maritime network; Cape option closes Suez, Bab-el-Mandeb and Panama | WEB / open source |
| Red Sea status | Most Asia–Europe services still go around the Cape in 2026 → Cape is the default | WEB (see sources in Q&A log) |
| Ocean speed / port-call allowance | 15 kn + 4 days | PLACEHOLDER (`data/leadtime_params.csv`) |
| Handling days at each step | `data/leadtime_params.csv` | PLACEHOLDER |
| Duty by importing country | `data/tariffs.csv` (US, MX, BR, IN, AE web-sourced; EU/UK/JP zero under WTO ITA, to verify) | WEB / TO VERIFY |

## Ageing while waiting

| Item | Value | Status |
|---|---|---|
| Battery | Store ~50% charge, recharge every 6 months; capacity loss after 12+ months | WEB — [Apple](https://support.apple.com/en-ae/100731) |
| Chips | Industry 2-year date-code convention; distributor-sponsored tests claim most old parts still pass solderability (biased source) | WEB — [Wevolver](https://www.wevolver.com/article/long-term-storage-and-dispelling-myths-about-date-codes) |
| Keyboards, housings, panels | No physical decay; die with EOL | Reasoned |

## Numbers

| Parameter | Value | Status |
|---|---|---|
| Liability window | 16 weeks | PRACTITIONER (virtualized) |
| Tracking window | 156 weeks (36 months) | PRACTITIONER (virtualized) |
| Unit costs (CPU $120, panel $60, keyboard $25, …) | see `data/materials.csv` | PLACEHOLDER |
| Purchase lead times (CPU 16w, panel 12w, memory 8w, …) | see `data/materials.csv` | PLACEHOLDER |
| Non-cancellable window: standard parts 2w; custom parts = lead time | `cancel_window_weeks` in `data/materials.csv` | PLACEHOLDER — Q7 |
| Carrying rate | 20%/yr | PLACEHOLDER |
| Battery recharge cost | $0.50/unit/event | PLACEHOLDER |
| Re-test cost past date code | $1.00/unit | PLACEHOLDER |
| Rework acceptance by other BU | 80% | PLACEHOLDER |
| ODM hedge ratio | 0% | PLACEHOLDER |
| Locale mix (US 40 / DE 12 / UK 8 / FR 7 / JP 15 / BR 18) | `data/locales.csv` | PLACEHOLDER |
| Forecast accuracy 16w / 20w | ~68% / ~60% | PRACTITIONER (virtualized) |
| Week-to-week forecast-error correlation | 0.3–0.9 | PLACEHOLDER |
| New-factory ramp to full volume | strong GSM 8–16 wks; weak GSM 16–30 wks | PLACEHOLDER (direction PRACTITIONER) |
| Expediting cost while lead time not covered | $6 (strong GSM) / $12 (weak) per unit | PLACEHOLDER |
| China conversion cost per unit | $25 | PLACEHOLDER |
| Sales optimism bias | not modelled yet | OPEN |
| Tariff pass-through to US importers | ~96% (exporters absorbed ~4%), measured on import prices, not retail | WEB — Kiel Institute via [Mahomet Daily](https://mahometdaily.com/?p=341079) |
| Laptop retail impact of large tariffs | 10% global + 60% China → +45% laptop price (≈$357 on $793), assumes near-full pass-through | WEB — CTA via [Tom's Hardware](https://www.tomshardware.com/news/trump-tariffs-increase-laptop-electronics-prices) |
| Retail pass-through of tariff cost | ~60–100%+ (Acer +10% list for a 10% China tariff, Feb 2025; Asus +6.7–9% on five models, Mar 2025) | WEB — derived; see [The Register](https://www.theregister.com/2025/02/18/acer_hikes_us_prices/), [Yahoo Tech](https://tech.yahoo.com/computing/articles/5-asus-laptops-now-more-090000444.html) |
| Market-level price elasticity (US PCs) | ≈ −0.7 implied: 2026 units −10.7% (Omdia) with sell-in ASP +12% (2Q26); confounded by memory shortage, Win10 refresh ending, pull-forward | WEB — derived; [Light Reading/Omdia](https://www.lightreading.com/smartphones-devices/us-pc-shipments-grew-1-0-in-2q26-while-full-year-market-forecast-to-decline-10-7-omdia) |
| Segment elasticity | low end far more elastic: 1Q26 sub-$500 units −18.7% vs total −7% with ASP +4%; 2Q26 sub-$699 −6.5%, $1,500+ +36.8% | WEB — [Digital Citizen](https://www.digitalcitizen.life/us-pc-shipments-fall-7-as-higher-memory-costs-push-prices-up/), Omdia — to validate with practitioner (Q17) |
| Boards built ahead of assembly | 2 weeks | PLACEHOLDER |
| New-site lead-time adder (SE Asia) | +4 weeks | PRACTITIONER |
| Relocation transit / cost | 3 weeks / 3% of material value, bonded (no duty) | PLACEHOLDER |
| Customs value per unit (P1-14 / P1-16 / P2-14) | $480 / $560 / $520 | PLACEHOLDER |
| China-origin US tariff on laptops | 0% current; 25% hypothetical scenario | WEB (current) / PLACEHOLDER (scenario) |
| Lifecycle (P1 EOL wk 30, P2 NPI wk 26) | `data/models.csv`, `data/platforms.csv` | PLACEHOLDER |

## Question log

| # | Question | Answer |
|---|---|---|
| Q1 | When is material officially MWD? | Plan cancelled inside the liability window → MWD regardless of actual stocking; physical amount only known at stock-take; annual reconciliation. |
| Q2 | Is common material netted out first? | Yes — same PN is absorbed by other plans; non-common needs cross-BU negotiation and paid conversion. |
| Q3 | Time limit for natural consumption? | Tracked for years (modelled 36 months), adjustable; electronics depend on storage yield. |
| Q4 | BOM routing table | Confirmed; also consider collective EOL and NPI. |
| Q5 | Does freed common stock offset only not-yet-purchased demand (beyond lead time)? | No — factories push out / cancel other plans' POs, because other brands buy the same parts and ODMs are often shared. |
| Q6 | When a shared ODM redeploys our freed standard parts to another brand, does it still claim MWD from us? | PARKED |
| Q6b | Finished-goods disposition order? | 1→6 as listed; 3 vs 4 depends on unit value (gaming reworked, EDU torn down). |
| Q7b | Rework cost? | ODM quotes case by case; 2–5% keyboard-only, 30–50% common, 70%+ for convertibles; plus labour. |
| Q8 | Is rework cost fixed or proportional? | Percentages were examples; labour must be added. Also: rework to re-enter the US depends on US origin rules — customs check the motherboard; once SMT is done the board's origin is locked. |
| Q9 | At transfer, are pre-SMT components moved to the new factory? | Yes — normal, because the new origin's supply base is not complete. |
| Q10 | Model says: with a 25% tariff, cut over immediately — MWD is small money. That contradicts experience. What is missing? | Shipping time: lead time to the new factory gets longer (R15). |
| Q10b | Is slow new-factory ramp (capacity, yield, certification) a real constraint? | Yes, obviously (R16). |
| Q11 | How many weeks longer is the chain, and does the commitment window stretch with it? | New SE Asia site: +4 weeks by default; sales give quarterly plans; OLED pulled in earlier. |
| Q13 | How much more of a 20-week-out plan gets cancelled or changed than a 16-week-out plan? | ~8% worse; risky models get a stretched board-build cadence (hedge); ODM cuts capacity if you under-load; new-site conversion +5–10%. |
| Q14 | What is forecast accuracy at the base window, and is "8% worse" percentage points or relative? | Roughly 8 points worse (modelled as 68% → 60%). Rushing causes shortages; can expedite but delivery not guaranteed; GSM-dependent. |
| Q15 | In a transfer decision, do MWD and tariff land on the same P&L / owner? | No. Tariff is not in the KPI, but it affects whether shipments hit the FY target, because consumers feel the price. |
| Q16 | When tariffs rose, how much did selling prices rise and how much did shipments fall? | Researched from public news → see pass-through / elasticity rows above. |
| Q17 | Does the low-end / EDU segment really react much harder to price than premium / gaming? | Both are affected; goods go into MGI first, rarely directly to merchants. |
| Q18 | What exactly is MGI — full name, who owns the stock, per country or per GEO, where are they? | Regional distribution warehouse after customs; brand-owned or briefly leased via logistics providers; never ODM. Typical hub locations used. |
| Q19 | Is MGI always post-customs, or is stock ever held bonded / in an FTZ so duty is paid only on release? | Possible; FTZ / bonded rules researched from public sources (R25). |
| Q20 | How fast does a finished laptop sitting in MGI lose value per month, and when does discounting start? | OPEN |
| Q12 | From first trial build to full volume, how long does a new factory take; what holds it back most? | OPEN |
| Q7 | How many weeks before delivery does a PO become non-cancellable, standard vs custom parts? | QUEUED |
