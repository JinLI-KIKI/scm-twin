# Module 5 — demand and KPI view: formulas

Code: `src/demand_kpi.py` (Python) and `src/dash/dk_engine.js` (browser), kept identical by
`tests/test_dk_parity.py`. Data: `data/demand_params.csv`, `data/demand_models.csv`; demand
curves from Module 1 (`data/models.csv`, US share in `data/locales.csv`); MWD, holding and
relocation per cutover week from Module 2 (`src/transfer.py`); the longer chain from Module 3
(`src/business_case.py`). Rules: R1, R8, R33, R42–R44 in [`ASSUMPTIONS.md`](../ASSUMPTIONS.md).

## 1. One week of one model

A tariff `t` on China-made laptops starts in week 0. Option `C` = the week the US volume
leaves China (or no transfer this year).

```
china(w) = 1                                   w < C, or no transfer
         = max(0, 1 − (w − C) / ramp)          w ≥ C (the new site ramps up linearly)
tariff   = t × customs_value × (1 − exporter_absorb)            per China-made unit
rise(w)  = passthrough × tariff × china(w)     w ≥ reprice_lag;  0 before
q(w)     = q0(w) × (1 + rise(w) / price)^elasticity             q0 = US plan before the tariff
```

## 2. The year, summed over weeks and models

```
units      = Σ q                     attainment = units / Σ q0
paid       = Σ q × tariff × china    recovered  = Σ q × rise      absorbed = paid − recovered
lost       = Σ (q0 − q) × price × gross_margin
frac       = (52 − C) / 52 if the volume moves this year, else 0
eol        = extra end-of-life MWD of the longer window per year (Module 3) × frac
chain      = eol + pipeline carrying per year (Module 3) × frac
expedite   = expedite_per_unit × weekly US units × lead-time adder        if the volume moves
conversion = Σ q × (1 − china) × conversion_CN × conv_uplift
transfer   = physical MWD + holding + relocation + rework at cutover C (Module 2; 0 after week 16)
```

## 3. Catch-up in Q3–Q4 (R45)

The fiscal-year target is `target = target_share × Σ q0` (the plan sits above the target). A
shortfall `gap = target − units` is closed by a discount `d` on every unit from week
`catchup_from_week` (26 = start of Q3), found by bisection:

```
Σ_m H2_m × ((1 − e × d)^elasticity_m − 1) = gap,   0 ≤ d ≤ max_promo_discount
q(w) ← q(w) × (1 − e × d)^elasticity   for w ≥ catchup_from_week
e = points_effect (share of the points that reaches the shelf price)
promotion = Σ_{w ≥ catchup} q × d × price
```

`H2_m` = units of model m in the catch-up weeks before the discount. If the cap is not enough,
`d` = cap and the year ends below target. Paid tariff, recovered tariff and lost margin are summed
on the units after the discount (lost margin turns negative when the year sells above plan).

## 4. Negotiated pass-through (R44)

```
case N (probability 1 − absorb_prob): passthrough = negotiated share
case A (probability absorb_prob):     passthrough = 0 (the company absorbs the tariff)
cost(option)       = (1 − p) × cost_N + p × cost_A          every company part, BU MWD cost, BU points
attainment(option) = min(attainment_N, attainment_A)        the target must be made in both
```

Units, weekly sell-in, quarters and the catch-up discount shown are those of case N.

## 5. Two scorecards

```
company cost = absorbed + lost + promotion + transfer + expedite + chain + conversion
BU MWD       = claimed − transferability × (claimed − physical) + eol
               claimed = plans cancelled in weeks C..15 at full BOM value (R1); physical from Module 2
BU cost      = mwd_cost_rate × BU MWD + bu_funds_support × promotion        MWD against points (R43)
BU pick      = among options with units ≥ target: lowest BU cost (ties: the latest)
               none reaches it: highest units (the target is lowered to that)
company pick = lowest company cost among options with units ≥ target (company_holds_target = 1)
               or among all options (0, and when none reaches the target)
gap          = company cost(BU pick) − company cost(company pick)
```

The map repeats the two picks over tariff 0–50% × pass-through 0–100%.

## What it leaves out

One fiscal year only: the tariff saved after the year is on the business-case page (Module 3).
Sell-in equals demand at the new price (no channel stock, Module 4). The target is not reset when
the price rises; quarter targets are re-phased only through the catch-up. Elasticity is the same
for every model (Q17).
