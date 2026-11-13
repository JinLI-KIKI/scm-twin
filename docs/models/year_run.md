# Roadmap A4 — one fiscal year, week by week: formulas

Code: `src/year_run.py`. It composes Modules 1–7 and adds no new behaviour of its own; every
input comes from the other modules' data files. Rules: R50 (composition of R1–R47) in
[`ASSUMPTIONS.md`](../ASSUMPTIONS.md). Page: `docs/year.html`.

## Setting

A US tariff `t` on China-made laptops starts in week 0 of the fiscal year (52 weeks, US region,
the three models of Module 1). The US volume can move to Indonesia in any week `c` of Module 5's
options (0–16, 20, 26, 39) or stay. Precomputed for t ∈ {10%, 25%, 40%} × GSM strong/weak ×
memory at 2025 or Q4 2026 prices (R48) for the overview; the page recomputes live with
`src/dash/yr_engine.js` (checked by `tests/test_yr_parity.py`).

## Share still built in China

Module 6's ramp Monte Carlo at this tariff and GSM gives the recommended pull-in and, for it,
the median share of the volume at the new site `s50(k)` in week `k` after the first build:

```
china(w) = 1                      before the cutover (w < c) or without a transfer
china(w) = 1 − s50(w − c)         after it (s50 = 1 once the band ends)
```

This replaces Module 5's straight-line ramp.

## Units (Module 5)

For each model `i` with US plan `q0_i(w)`, customs value `cv_i`, price `p_i`, elasticity `ε`:

```
tariff_i     = t × (1 − exporter_absorb) × cv_i
rise_i(w)    = passthrough × tariff_i × china(w)          from the repricing week on
base_i(w)    = q0_i(w) × (1 + rise_i(w) / p_i)^ε
d            = catch-up discount (Module 5 catch_up) closing target × plan − Σ base, capped
q_i(w)       = base_i(w) × (1 − points_effect × d)^ε       from the catch-up week on
```

## Weekly costs (company view)

```
tariff absorbed  Σ_i q_i(w) × (tariff_i × china(w) − rise_i(w))
lost margin      Σ_i (q0_i − q_i) × p_i × gross margin
price points     Σ_i q_i(w) × d × p_i                       from the catch-up week
cutover          holding + relocation + rework of option c (Module 2), in week c
MWD              physical MWD of option c, in week 51 (year-end reconciliation, R8)
ramp             Module 6 pull-in cost in week c; yield scrap on new-site units while it learns
expediting       expedite per unit × weekly units × lead-time adder, in week c (×2 weak GSM)
longer chain     (end-of-life MWD + pipeline carrying per year, Module 3) / 52, every week from c
conversion       new-site units × conversion cost × uplift
end of life      Module 4 rate × extra transit weeks (Indonesia − China to the US MGI, Module 7
                 routes) × units the new site ships before week 30, booked in week 30
```

With `absorb_prob` the company ends up absorbing the tariff (pass-through 0): every cost is
`(1 − absorb_prob) × negotiated + absorb_prob × absorbed` (R44); units and quarters shown are the
negotiated case, attainment the lower of the two.

## Picks (Module 5 rules)

```
hit      = options shipping at least target × plan (both cases)
company  = lowest Σ_w cost among hit (all options if the company does not hold the target)
BU       = lowest mwd_cost_rate × (claimed − migration × (claimed − physical) + EOL MWD)
           + funded share of the price points, among hit (ties: the later week)
```

The page follows four strategies: stay, the company's pick, the BU's pick and a move at the
model change (week 26).
