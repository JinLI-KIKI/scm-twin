# Assumptions Register

Every rule and number in the model, with where it came from. Status:
**PRACTITIONER** = generalized from hands-on industry practice; sites and numbers are virtualized (no employer-specific data) · **WEB** = sourced online · **PLACEHOLDER** = invented, needs calibration · **OPEN** = question pending.

Last updated: 2026-10-15 (v0.7: Module 7 footprint — six sites, nine markets, real laptop duties, origin by main board, duty ranges up to the April 2025 peak)

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
| R26 | **Finished-goods value in MGI is flat until the successor model launches**, then drops in a step. Before that, the main ageing risk is quality: units that sit long can develop yield problems and need re-inspection. Prices in third-tier (liquidation / grey) markets do not feed back into the official price. | PRACTITIONER |
| R27 | **The step drop is paid through the channel, not the list price.** Usually price protection: the official price stays, and the brand credits dealers the difference on units they still hold. Alternatively a new agreement with the dealer. So at successor launch the brand pays (units in channel × drop) in credits, and MGI stock still unsold is later sold in at the lower net price. Consequence: stock pushed into the channel just before launch to hit a sell-in target comes back as a price-protection bill. | PRACTITIONER · WEB: price protection as a manufacturer rebate on retailer-held units ([Lee et al., Management Science 2000](https://www.gsb.stanford.edu/faculty-research/publications/price-protection-pc-industry)) |
| R28 | **Sales volume lock.** Well before EOL (modelled 22 weeks, virtualized) the brand's sales team talks with dealers and locks the old model's remaining volume. Locked is locked: the material for the locked volume is ordered at the lock, and the forecast does not move afterwards. A hedge is possible. If the lock is a cut, the cut stands: material already committed beyond the locked need becomes MWD. Lock dates differ a little by region (modelled ±2 weeks). The lock is the brand's internal commitment; dealers are not bound by it. | PRACTITIONER (virtualized) |
| R30 | **Dealer leftovers after the lock.** Units dealers cannot sell are either returned through stock rotation or cleared by the dealer. Once the brand has sold a unit in, most of the damage to the brand is gone; the leftover is mainly the dealer's problem. Modelled: returns capped at 10% of the dealer's last-quarter purchases, against a new order; the rest stays with the dealer. | PRACTITIONER (rule) · cap WEB from an example distribution agreement |
| R31 | **Sales must sell the locked volume.** What sales cannot sell is the brand's problem: the BU either absorbs it, or contacts other GEOs to resell it there (as is, or after rework). Modelled as the disposition paths: resell to another GEO first, within capacity, then the BU tears down, liquidates or scraps. | PRACTITIONER |
| R32 | **IBP hedge at the lock.** IBP sets a hedge on the locked volume from each GEO's sales history. It can be negative: sales are sometimes too optimistic, and IBP buys less than they lock. Modelled: supply (final material buy and frozen builds) = locked need × (1 + hedge); IBP corrects 60% of a GEO's habitual lock bias, with ±3% error of its own. | PRACTITIONER (rule) · PLACEHOLDER (size) |
| R33 | **The BU's fiscal-year shipment target is counted in sell-in units.** Units shipped into the channel count when they are sold in, whether or not they have sold through. | PRACTITIONER |
| R29 | **EOL means the last build week** of a model. Sell-through continues after it, until the successor reaches the market and the old stock fades out. | Design choice — to confirm |
| R16 | New factories ramp slowly — capacity, yield and certification lag — so transfer is a gradual curve, not a switch. The old factory keeps covering the gap (still paying China-origin tariff); yield loss at the new site consumes material without output. | PRACTITIONER (direction); ramp shape OPEN — Q12 |
| R13 | **Origin lock at the motherboard.** US customs mostly judges origin by the motherboard; once the board is built (SMT done) its origin is fixed — final assembly elsewhere does not change it. A built board that cannot be used is scrapped. Only pre-SMT components can be moved to a new factory and change origin. | PRACTITIONER · WEB: CBP NY N305378 (Chinese subassemblies assembled in Taiwan → China origin) |

## Network atlas (map) — added 2026-10-13

| Item | Value | Status |
|---|---|---|
| Company | Anonymous laptop maker; no real brand is modelled | Design choice |
| Factory sites | Kunshan, Jiangsu (current); candidates Cikarang (Indonesia), Bac Ninh (Vietnam), Penang (Malaysia), Jundiai (Brazil), Jebel Ali Free Zone (UAE) — `data/nodes.csv` | ILLUSTRATIVE |
| MGI sites | Inland Empire CA, Venlo NL, Daventry UK, Atsugi JP, Campinas BR, Eastern Creek AU, Loyang SG, Bhiwandi IN, Jebel Ali AE — `data/mgi_sites.csv` | ILLUSTRATIVE (typical electronics DC hubs) |
| Ports and airports | Real gateways (UN/LOCODE, IATA codes) | WEB-KNOWN |
| Map frame | One complete Pacific-centred world, cut in the mid-Atlantic at 28°W; no repeated copies when zooming out | Design choice |
| Country shapes | Natural Earth 1:50m, public domain | WEB / open data |
| Highways and truck lanes | Natural Earth 1:10m major highways shown when zoomed in; truck lanes routed over the Natural Earth road network (straight line × 1.3 where no road route is found) | WEB / open data |
| Ocean paths and distances | `searoute` open-source maritime network; Cape option closes Suez, Bab-el-Mandeb and Panama | WEB / open source |
| Red Sea status | Most Asia–Europe services still go around the Cape in 2026 → Cape is the default | WEB (see sources in Q&A log) |
| Ocean speed / port-call allowance | 15 kn + 4 days | PLACEHOLDER (`data/leadtime_params.csv`) |
| Handling days at each step | `data/leadtime_params.csv` | PLACEHOLDER |
| Duty by importing country and assembly origin | `data/tariffs.csv`, one column per site; see the Module 7 section | WEB / TO VERIFY |
| Same-country lanes | Brazil to Brazil and UAE to UAE go by truck only; the UAE adds 2 days to leave the free zone and clear into the mainland | ILLUSTRATIVE / PLACEHOLDER |

## Footprint and duties (Module 7) — added 2026-10-15

| ID | Rule | Status |
|---|---|---|
| R34 | **Origin follows the main board in the footprint model too (R13).** A site that assembles main boards made in China ships China-origin laptops to the US and pays the China rate. To escape a China tariff a new site must make its own boards (SMT), at an extra cost per unit and a yearly fixed cost for the board line. A weight between 0 and 1 lets other customs authorities, or a looser ruling, be tested. | PRACTITIONER (R13) · WEB: CBP rulings [N350187](https://www.tarifflens.ai/rulings/N350187) (Jul 2025) and [N357691](https://www.tarifflens.ai/rulings/N357691) (Jan 2026): boards made in Vietnam, final assembly in China → Vietnam origin |
| R35 | **A new site needs a minimum load.** Once open it must build at least a share of its capacity, or it loses its workforce and its qualifications. So a hedge site costs its fixed cost plus the landed-cost gap on the volume it has to carry, even when China is cheaper. | Design choice — to confirm (Q28) |
| R36 | **Build now or wait.** Waiting means keeping the footprint that is cheapest under today's duties and opening a new site only once a tariff arrives: the old cost runs through the ramp-up and a rush premium is paid. Building now pays the fixed cost and minimum load every year whatever happens. | Design choice — to confirm (Q29) |

| Item | Value | Status |
|---|---|---|
| Markets and weekly demand | US 4,000 · EU 2,400 · UK 700 · JP 1,300 · BR 1,500 · AU 550 · SEA (Singapore hub) 800 · IN 900 · ME (UAE) 450 units a week — `data/markets.csv`; separate from the Module 1–4 locale mix | PLACEHOLDER |
| US duty on laptops (HTS 8471.30) | 0% from every site: MFN free; laptops (8471.30–.90) are exempt from the 60-economy Section 301 action of 24 Jul 2026 (10% ID/MY, 12.5% VN on other goods); China's 2019 list on laptops stays suspended (one commercial tracker shows 25%: conflicting); IEEPA tariffs struck down 20 Feb 2026; Section 122 expired 24 Jul 2026 | WEB — [TechNode Global](https://technode.global/2026/07/24/u-s-section-301-hits-southeast-asia-10-for-three-12-5-for-singapore-vietnam-technology-escapes/) |
| Section 232 semiconductors, phase 2 | Phase 1 (Jan 2026) covers 8471.50/.80 servers with qualifying chips only; a phase 2 reaching laptops is proposed (25%), not in force as of Oct 2026 | WEB — [TariffLens](https://www.tarifflens.ai/blog/section-232-semiconductor-tariff-july-2026-phase-2-guide) |
| EU and UK duty on laptops | 0% from every origin (WTO Information Technology Agreement) | ITA — TO VERIFY |
| Japan and Australia duty on laptops | 0% (MFN free on 8471.30); Australia values imports FOB | WEB — [Treayo](https://treayo.com/en/compare/847130) |
| Singapore duty on laptops | 0% (not on the dutiable list); GST 9% recoverable | WEB — [Epic Sourcing](https://www.epicsourcing.co/epic-guide/import-duty-gst-from-china-to-singapore-2026) |
| India duty on laptops | 0% basic customs duty (ITA); laptops need an import authorisation (IMS) | WEB — [A2Z Taxcorp](https://a2ztaxcorp.net/government-notifies-procedure-for-import-management-system-for-restricted-it-hardware-for-calendar-year-2026/) |
| Brazil duty on laptops | 16% import duty (NCM 8471.30.12, Mercosur TEC) on CIF from every foreign site; a Brazilian-made laptop pays none, but its imported parts do (modelled 8% average) | WEB — [Buscador NCM](https://buscadorncm.com.br/ncm/84713012); parts rate PLACEHOLDER |
| UAE duty on laptops | 5% GCC tariff on CIF, also on free-zone units entering the mainland unless they qualify as a GCC national product; some sources say computers are free | WEB-CONFLICTING — [Middle East Briefing](https://middleeastbriefing.com/doing-business-guide/uae/taxation-and-accounting/custom-duties-export-import-tax-uae) |
| Duty ceilings (April 2025 peak, US) | China 145% (125% reciprocal + 20% fentanyl, 10 Apr–13 May 2025); Vietnam 46%, Indonesia 32%, Malaysia 24% (announced 2 Apr 2025, paused at 10%); Brazil and UAE 10% (Brazil 50% from 6 Aug 2025). Laptops were exempted from the reciprocal part on 11 Apr 2025, so China-made laptops actually paid 20% — 145% is the ceiling without that exemption. Default ranges: US duties from today's rate up to these peaks; other markets fixed unless stretched on the page (slider scale 0–150%) — `data/duty_ranges.csv` | WEB — [CBS News](https://cbsnews.com/news/us-exempts-smartphones-computers-from-global-trump-tariffs), [Dimerco reciprocal tariff table (10 Apr 2025)](https://lp.dimerco.com/hubfs/Content/USA%20Reciprocal%20Tariff%20Table%20(April%2010).pdf) |
| Chance a market changes its duties | 20% per market and Monte Carlo draw; a change moves every origin to the same point of its range (as in April 2025, when the US hit all Asian sites at once) | PLACEHOLDER |
| Duty scenarios and weights | Current 50% · US 25% on China-made laptops 20% · Section 232 phase 2 at 25% on every origin 15% · Asia Section 301 without the computer exemption 10% · Brazil removes its 16% 5% — `data/duty_scenarios.csv` | PLACEHOLDER (weights); rates WEB |
| Site conversion cost vs China | ID 1.08× · VN 1.06× · MY 1.12× · BR 1.60× · AE 1.35× of China's $25 per unit | PRACTITIONER (+5–10% for a new SE Asia site) / PLACEHOLDER |
| Site capacity and fixed cost per year | CN 14,000/wk · ID and VN 5,000/wk, $1.5M · MY 4,000/wk, $1.8M · BR 2,000/wk, $2.5M · AE 1,500/wk, $2.0M — `data/sites.csv` | PLACEHOLDER |
| Minimum load of a new site | 50% of capacity (China 0%) | PLACEHOLDER (R35) |
| Main board made on site | +$6 per unit; board line $1.2M a year | PLACEHOLDER (R34) |
| Board-origin weight | 1.0 (origin follows the board, as in the CBP rulings) | PRACTITIONER (R13) · WEB |
| Ramp-up to open a site / rush premium / years compared | 12 months / $1.0M / 3 years | PLACEHOLDER (R36) |
| Ocean freight | $900 + $0.20 per nautical mile per 40-ft; 1,800 laptops or 2,600 part kits per container; $1.50 handling per unit | PLACEHOLDER |
| Air freight | 3 kg per laptop × ($2.50 + $0.22 per 1,000 km) per kg | PLACEHOLDER |
| Planning cost of a longer chain | $1.25 per unit per extra week (feed days / 7 + 1) | DERIVED from Module 3 (≈$5 per unit for +4 weeks, US) |
| Chokepoint premium | $0 per risky passage by default (Red Sea, Hormuz) | PLACEHOLDER |
| Straits on each ocean lane | Reported by `searoute` (Malacca, Sunda, Hormuz, Suez, Bab-el-Mandeb, Gibraltar, Cape, Panama, Chile) | WEB / open source |

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
| Sales optimism bias | +8% on the plan; sales add half of any upside surprise and never cut below plan (Module 4) | PLACEHOLDER |
| Finished goods (Module 4): channel cover, drain/push cover, tail, disposition prices and capacities | `data/fg_params.csv` (status per row) | PLACEHOLDER unless marked |
| Gross margin on channel net price | ~25% (P1-14 $650 / P1-16 $760 on $488 / $568 landed) | PLACEHOLDER |
| Weeks of sell-through read at the lock | 13 (one quarter) | PLACEHOLDER |
| IBP hedge | Corrects 60% of each GEO's habitual lock bias, ±3% error; can be negative | PLACEHOLDER (rule PRACTITIONER, R32) |
| Lock bias by GEO | Average 0, spread ±10% (standard deviation) between GEOs, drawn per region and run; page slicer tests an average of −10% / 0 / +10% | PRACTITIONER (no fixed direction) / PLACEHOLDER (size) |
| Stock rotation allowance | Up to 10% of the previous quarter's purchases, dollar-for-dollar against a new order; discontinued products can be excluded after the last order date. Price protection there covers distributor and reseller stock plus units sold in the 30 days before the cut | WEB — example contract: [domestic distribution agreement filed with the SEC (EX-10.25)](https://www.sec.gov/Archives/edgar/data/913949/000119312503008918/dex1025.htm); clause patterns: [Law Insider](https://lawinsider.com/clause/stock-rotation/_1) · PLACEHOLDER for laptops |
| Dealer clearance of leftovers they keep | 60% of their net cost after price protection | PLACEHOLDER |
| Duty drawback on re-export or destruction (US) | Up to 99% for MFN and Section 301 duty; barred for IEEPA (struck down 20 Feb 2026) and for Section 232 steel/aluminium; the Jan 2026 semiconductor 232 proclamation bars it too (R25). Modelled 0% in the 25% stress case | WEB — [GingerControl drawback matrix](https://gingercontrol.com/resources/duty-drawback), [Skadden on the IEEPA ruling](https://www.skadden.com/insights/publications/2026/03/tariff-refund-mechanism-takes-shape) |
| Price drop at successor launch (net, via price protection) | 10–20% | PLACEHOLDER · WEB: retail discounts on previous-generation laptops ~10–25% ([ShopSavvy](https://shopsavvy.com/best-time-to-buy/computers)) |
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
| Q20 | How does a finished laptop in MGI lose value? | Little movement before the successor launches, then a step drop; ageing stock may show yield problems; third-tier market prices do not directly move the price. |
| Q21 | How big is the drop when the successor launches, and is it a list-price cut or price protection paid to the channel? | Usually price protection to the channel (list price unchanged), or a new dealer agreement. Size not given → web retail range for previous-generation laptops ~10–25% used as a placeholder (10–20% modelled). |
| Q22 | How many weeks of stock do dealers hold before a successor launch, and is sell-in deliberately cut beforehand to drain the channel? | About 20 weeks before EOL (modelled 22) sales talks with dealers and locks the remaining volume; after the lock, forecasts can no longer be increased; regions lock at slightly different times. Channel weeks of stock not given → 5 weeks placeholder (R28). |
| Q23 | Is the locked volume binding on the dealer? If sell-through falls short of it, who carries the leftover: the dealer, the brand through stock rotation / returns, or the brand through extra support? | Usually stock rotation back to the brand, or the dealer clears it; once the brand has sold the units in, the damage to the brand is much smaller (R30). |
| Q24 | Compared with what finally sells, is the volume sales locks usually too high, too low or about right, and by roughly how much? | Not known in general: every GEO and every salesperson has their own style, high or low. Modelled as zero on average with a ±10% spread between GEOs. |
| Q25 | When sales locks the volume, is the material for the last builds still unordered, so the lock sets the final material buy? Or is most of it already inside the liability window? | Locked is locked: the material is ordered at the lock. A hedge is possible, but once the lock is a cut, the lower volume is locked (R28). |
| Q26 | When you hedge at the lock, how much extra material do you usually buy over the locked volume (% or weeks), for which parts, and what happens to hedge material that is not used? | The hedge can also be negative. IBP sets it from historical sell-through, because sales are sometimes too optimistic (R32). |
| Q27 | What is the BU's fiscal-year shipment target counted in: sell-in units, sell-in revenue, or something else? | Sell-in units (R33). |
| Q28 | When a second factory is opened as a tariff hedge, does it have to run a minimum share of its capacity? Roughly how much, and what happens below it (staff, ODM contract, customer qualification)? | OPEN — modelled 50% (R35) |
| Q29 | When a US tariff on China-made laptops is announced, how long does it take to open and qualify a new site and its board line, and is it usual to prepare one before the tariff comes? | OPEN — modelled 12 months, $1M rush premium (R36) |
| Q12 | From first trial build to full volume, how long does a new factory take; what holds it back most? | OPEN |
| Q7 | How many weeks before delivery does a PO become non-cancellable, standard vs custom parts? | QUEUED |
