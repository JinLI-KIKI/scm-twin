# Module 7 — factory footprint: formulas

Code: `src/footprint.py` (Python) and `src/dash/fp_engine.js` (browser), kept identical by
`tests/test_fp_parity.py`. Data: `data/sites.csv`, `data/markets.csv`, `data/tariffs.csv`,
`data/duty_scenarios.csv`, `data/footprint_params.csv`, lanes from `data/network.json`
(built by `src/build_map.py`). Rules: R13, R34–R36 in [`ASSUMPTIONS.md`](../ASSUMPTIONS.md).

## 1. Landed cost of one unit, site `o` to market `m`

**Factory value (the duty base before freight)**

```
cv = customs_value_CN + conversion_CN × (conv_index_o − 1) + parts_o + board_extra (if o makes boards)
parts_o (o ≠ CN) = (FEU_base + FEU_per_nm × feed_nm_o) / kits_per_FEU + handling     parts freight
                 + parts_value × carrying_rate × feed_days_o / 365                      parts in transit
                 + parts_value × parts_duty_o                                           duty on parts
```

**Freight to the market**

```
ocean:          (FEU_base + FEU_per_nm × nm) / units_per_FEU + handling + trucking
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
plan  = planning_cost × (feed_days_o / 7 + 1)        o ≠ CN; from Module 3 (+4 weeks ≈ $5/unit)
risk  = chokepoint_premium × number of risky passages (Red Sea, Hormuz) on the lane
landed = cv + freight + duty + carry + plan + risk
```

## 2. Allocation

Minimum-cost flow on ocean landed costs, open sites → markets:

```
minimise   Σ_o Σ_m x[o][m] × landed[o][m]
subject to Σ_o x[o][m] = demand_m                     every market
           min_load_o × cap_o ≤ Σ_m x[o][m] ≤ cap_o   every open site (R35)
```

Solved by successive shortest paths (Bellman-Ford). Minimum loads are met by giving the first
`min_load × cap` units out of each site a large cost bonus, so they are routed first.

## 3. Footprints across scenarios

For every set `F` of open sites with `Σ cap ≥ demand` and `Σ min_load × cap ≤ demand`, and
for each board variant (all non-China sites import their boards, or all make them):

```
C(F, s)   = 52 × weekly cost of the allocation in scenario s
            + Σ fixed_cost_o + board_fixed × (number of non-China sites making boards)
E(F)      = Σ_s p_s × C(F, s) / Σ_s p_s                         expected yearly cost
regret(F) = max_s [ C(F, s) − min_F' C(F', s) ]                 worst-case regret
```

## 4. Build now or wait (R36)

`B` is the footprint with the lowest cost under today's duties (scenario 1). Over `H`
years with a ramp-up of `lag = ramp_months / 12` years:

```
now(F, s)  = H × C(F, s)
wait(F, s) = min( H × C(B, s),  lag × C(B, s) + (H − lag) × C(F, s) + rush_premium )
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
