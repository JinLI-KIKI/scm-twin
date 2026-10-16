# Module 7 — factory footprint: formulas

Code: `src/footprint.py` (Python) and `src/dash/fp_engine.js` (browser), kept identical by
`tests/test_fp_parity.py`. Data: `data/sites.csv`, `data/markets.csv`, `data/tariffs.csv`,
`data/duty_scenarios.csv`, `data/footprint_params.csv`, `data/freight_lanes.csv`,
`data/freight_regions.csv`, `data/linkage.json` (written by `src/integrate.py`), lanes from
`data/network.json` (built by `src/build_map.py`). Rules: R13, R34–R41 in
[`ASSUMPTIONS.md`](../ASSUMPTIONS.md).

## 1. Landed cost of one unit, site `o` to market `m`

**Factory value (the duty base before freight)**

```
cv = customs_value_CN + conversion_CN × (conv_index_o − 1) + parts_o + board_extra (if o makes boards)
parts_o (o ≠ CN) = (FEU(feed lane) + extra) / kits_per_FEU + handling                 parts freight
                 + parts_value × carrying_rate × feed_days_o / 365                      parts in transit
                 + parts_value × parts_duty_o                                           duty on parts
                 + parts_value × cn_parts_premium × parts_o(scenario)                   China parts curbs (R39)
```

`conv_index_o` is the ODM's price for the line against China's (R35); a bought plant uses
`conv_index_o − odm_op_margin × customs_value_CN / conversion_CN` (it keeps the ODM's operating
margin). `parts_o(scenario)` is 1 for every non-China site in the China parts scenario and 0
otherwise.

**Site terms (R35)**

```
                 ODM line (mode odm)                         bought plant (mode buy)
fixed per year   program_cost + NRE / H                      program_cost + overhead + price × (1 / life + capital_rate)
fee per unit     take-or-pay fee                             labour_share × conversion_CN × conv (idle labour)
  below commit
ramp             ramp_months_odm                             ramp_months_buy
NRE   = capex_line × 52 × capacity + qualification          capex_line = $4.2 (Wistron Ha Nam Victory II)
price = capex_plant × 52 × capacity                         capex_plant = $13.3 (Quanta Nam Dinh)
```

**Ocean rate per 40-ft (R37, R38)**

```
lane     = region(from_port) − region(to_port)                  freight_regions.csv
(a, c, b) = pre-war, long-term contract, spot                   benchmark lanes (freight_lanes.csv)
          = (f, f × fallback_contract_factor, f × fallback_now_factor),  f = FEU_base + FEU_per_nm × nm
FEU      = a + x × (c − a)            if x = freight_basis ≤ 1    (default x = 1: contract)
         = c + (x − 1) × (b − c)      if x > 1
extra    = gulf_surcharge (leg starts or ends in the Gulf) + bypass_truck (leg uses Khor Fakkan)
```

With `hormuz_closed = 1` every sea leg that would pass Hormuz uses its Khor Fakkan variant:
the sea leg ends or starts at Khor Fakkan, a truck covers Khor Fakkan–Dubai, and the lead time
adds the trucking and `hormuz_bypass_queue_days`.

**Freight to the market**

```
ocean:          (FEU + extra) / units_per_FEU + handling + trucking
air:            kg × (air_base + air_per_1000km × air_km / 1000) + handling + trucking
same country:   trucking + handling / 2
trucking = truck_per_100km × truck_km / 100
```

**Duty (R13, R34)**

```
own   = duty[m][o]           from tariffs.csv, overridden by the scenario
w     = 0                    if o = CN, o makes its boards, or o sells in its own country
      = board_origin_weight  otherwise (1 = US customs rule: origin follows the main board)
rate  = (1 − w) × own + w × duty[m][CN]
base  = cv + freight         where the market values imports CIF (EU, UK, JP, BR, SG, IN, UAE)
      = cv                   where it values them FOB (US, AU)
duty  = rate × base
```

**The rest**

```
carry = cv × carrying_rate × door-to-MGI days / 365
plan  = chain_cost × (feed_days_o / 7 + 1)           o ≠ CN; chain_cost from Module 3 (R40)
fg    = fg_eol × (days[o][m] − days[CN][m]) / 7      from Module 4 (R40); negative = closer than China
risk  = chokepoint_premium × number of risky passages (Red Sea, Hormuz) on the lane
landed = cv + freight + duty + carry + plan + fg + risk
```

**Linked costs (`src/integrate.py`, R40)**

```
chain_cost = (EOL MWD/yr at the 20-week window − at the 16-week window) / units per year / 4 weeks
           Module 3, US profile: overcommitment weeks × weekly locked value × EOL events per year
fg_eol     = slope of avoidable cost per unit sold against transit weeks T = 5..9
           Module 4 simulation, lock strategy, 300 runs, successor launch held at the base week
urgent     = (Module 2 total at the best cutover week with a 25% tariff) / weekly US units
             + lead-time adder × expediting cost per unit (Module 3, strong GSM)
```

## 2. Allocation

Minimum-cost flow on ocean landed costs, open sites → markets, with ODM take-or-pay (R35):

```
minimise   Σ_o Σ_m x[o][m] × landed[o][m] + Σ_o fee_o × max(0, commit_o − Σ_m x[o][m])
subject to Σ_o x[o][m] = demand_m                     every market
           Σ_m x[o][m] ≤ cap_o                        every open site
commit_o = min_load_o × cap_o
```

Solved by successive shortest paths (Bellman-Ford). The first `commit_o` units out of each site
get a cost bonus of `−fee_o` (filling the commitment avoids the fee), so a site fills its
commitment only where its landed cost is within the fee of the alternative; the remaining
shortfall pays the fee.

## 3. Footprints across scenarios

For every set `F` of open sites with `Σ cap ≥ demand`, and for each board variant (all
non-China sites import their boards, or all make them):

```
C(F, s)   = 52 × weekly cost of the allocation in scenario s (landed + take-or-pay)
            + Σ fixed_o (site terms) + board_fixed × (number of non-China sites making boards)
E(F)      = Σ_s p_s × C(F, s) / Σ_s p_s                         expected yearly cost
regret(F) = max_s [ C(F, s) − min_F' C(F', s) ]                 worst-case regret
```

## 4. Build now or wait (R36)

`B` is the footprint with the lowest cost under today's duties (scenario 1). Over `H`
years, where a new site takes its ramp-up (`ramp_months_odm` or `ramp_months_buy`) to qualify:

```
now(F, s)  = H × C(F, s)
wait(F, s) = min( H × C(B, s),  lag_F × C(B, s) + (H − lag_F) × C(F, s) + rush_F
                                 + urgent × max(0, moved(F, s) − moved(B, s)) )
lag_F  = max ramp (months / 12) over the sites F opens beyond B; rush_F = rush_premium if F opens any
moved(F, s) = weekly units built outside China in footprint F, scenario s
value(F)   = Σ_s p_s × wait(F, s) / Σ p − Σ_s p_s × now(F, s) / Σ p      > 0: build now
```

**Tipping weight** on scenario `k` (the others keep their relative weights):

```
d_s    = wait(F, s) − now(F, s)
d_rest = Σ_{s≠k} p_s × d_s / Σ_{s≠k} p_s
weight* = −d_rest / (d_k − d_rest)        if d_rest < 0 < d_k;  0 if d_rest ≥ 0;  never if d_k ≤ 0
```

## 5. Break-even China duty

For site `o` in market `m`, write both landed costs as lines in the China duty `r`:

```
L_CN(r) = L_CN0 + r × base_CN
L_o(r)  = L_o0 + (1 − w) × own × base_o + w × r × base_o
r*      = (L_o0 + (1 − w) × own × base_o − L_CN0) / (base_CN − w × base_o)
```

`L_CN0` and `L_o0` are the landed costs without duty. If `base_CN − w × base_o ≤ 0` the site
never wins (a China tariff raises its cost as fast as China's); `r* ≤ 0` means it already wins.
Per-unit only: fixed costs of a site are not in the break-even.

## 6. Duty ranges (Monte Carlo)

Every duty `d[m][o]` has a range `[low, high]` (default: US from today's rate to its April 2025
peak; every other market fixed). For each draw and each market `m`:

```
u, s ~ U(0, 1)
d[m][o] = low + s × (high − low)        if u < duty_change_prob   (the market changes its duties)
        = today's rate (kept inside the range)   otherwise
```

One `s` per market moves all of that market's origins together, as the US did in April 2025.
Each feasible footprint `F` is priced in every draw `k` (`C(F, k)`, yearly), then

```
mean, P10, P50, P90 of C(F, ·)
cheapest in  = share of draws where F has the lowest cost (first in order on ties)
regret(F, k) = C(F, k) − min_F' C(F', k)          reported as mean and P90
```

The page draws with the same generator as Python (mulberry32, seed 7), so a given range set and
number of draws gives the same numbers in both.

**Which duty moves the cost** (page only): for one footprint, each stretched duty is set to the
low and to the high end of its range with every other duty at today's rate; the bars are the
change in yearly cost.

## 7. Back-test (R41)

Run on today's sites and parameters, with CN and VN open:

```
2025:  duty[US][CN] = 20%, every other duty as today
       share_b = x[VN][US] / demand_US        for boards imported (b = 0) and made in Vietnam (b = 1)
       w*      = highest board-origin weight at which the imported-board line still takes the US
2026:  Vietnam NRE set to 0 (already paid); C_stay(s) = C({CN, VN}, s), C_back(s) = C({CN}, s)
       E_x(p)  = p × C_x(cn301) + (1 − p) × Σ_{s ≠ cn301} p_s × C_x(s) / Σ_{s ≠ cn301} p_s
       p*      = weight on cn301 at which E_stay(p*) = E_back(p*)
```

Compared with US imports by origin (`data/us_import_history.csv`) and the China-only tariff
gap by date (`data/us_laptop_tariff_history.csv`). The model moves a market whole, so it can
only say whether a shift pays, not how big it is.
