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

## 3. Two scorecards

```
company cost = absorbed + lost + transfer + expedite + chain + conversion
BU MWD       = claimed MWD (plans cancelled in weeks C..15 at full BOM value) + eol     default
             = physical MWD + eol                                                     switch
BU pick      = among options with attainment ≥ target_tolerance: lowest BU MWD (the latest one)
               none reaches it: highest attainment
company pick = lowest company cost
gap          = company cost(BU pick) − company cost(company pick)
```

The map repeats the two picks over tariff 0–50% × pass-through 0–100%.

## What it leaves out

One fiscal year only: the tariff saved after the year is on the business-case page (Module 3).
Sell-in equals demand at the new price (no channel stock, Module 4). The target is not reset when
the price rises. Elasticity is the same for every model.
