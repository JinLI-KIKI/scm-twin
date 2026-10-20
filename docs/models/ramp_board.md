# Module 6 — new-site ramp and risk board hedge: formulas

Code: `src/ramp_board.py` (Python) and `src/dash/rb_engine.js` (browser), kept identical by
`tests/test_rb_parity.py`. Data: `data/ramp_params.csv`, `data/board_models.csv`; demand curves
and board contents from Module 1 (`data/models.csv`, `data/bom.csv`, `data/materials.csv`); the
US region profile from Module 3; margins from `data/demand_models.csv`; migration and MWD price
from `data/demand_params.csv` (Module 5). Rules: R13, R16, R19, R21, R46, R47 in
[`ASSUMPTIONS.md`](../ASSUMPTIONS.md).

## Part A — ramp (R46)

Per Monte Carlo run, each gate g (material rhythm, yield, supplier readiness) slips with chance
`p_g × GSM factor` by `lo_g + (hi_g − lo_g) × u` weeks. For `pull` weeks pulled in:

```
T(w)     = max(ramp_min, ramp_base − pull) + Σ_g slip_g
share(w) = smoothstep(min(1, w / T)) = 3x² − 2x³                 share of the region's volume
leakage  = Σ_w (1 − share) × weekly units × customs value × tariff
yield(w) = yield_full − (yield_full − yield_start) × e^(−w / τ)
scrap    = Σ_w share × weekly units × (1 / yield − 1) × BOM value × scrap_share
pull     = weekly units × pull_cost × Σ_{i=0}^{pull−1} (1 + growth × i)
```

Every pull-in is priced on the same draws; the one with the lowest mean of leakage + scrap +
pull is recommended. The band is P10, P50 and P90 of `share(w)` over the runs.

## Part B — board-build cover (R47)

Per model and run: weekly noise `z`, forecast noise `u`, and an early-cut week with chance
`cut_prob` (after the first four live weeks). Actual and forecast demand:

```
D(w)    = plan(w) × max(0, 1 + noise × z_w)               0 from the cut week on
F(w, h) = D(w) × max(0, 1 + bias × √(h/16) + σ16 × √(h/16) × u_w)     made h weeks ahead
          σ16 = MAPE16 × √(π/2) × sigma_mult; 0 at or after end of life, and after a known cut
```

Every `cover` weeks a run builds boards for the next `cover` weeks:

```
need   = Σ_{j<cover} F(d + j, j + 1)
cut    = κ_GSM × max(0, (std − cover) / std)              SMT capacity the ODM keeps back
build  = min(need − on hand, need × (1 − cut))             + one setup
budget = smt_flex × Σ_{j<cover} plan(d + j)                rush boards available in the run
```

Each week boards on hand serve `D(w)`; a shortfall takes rush boards from the budget at a
premium, and `lost_share` of what is still short is lost at gross margin. Boards on hand carry
at the carrying rate. When the model ends (end of life or cut), boards left over are stranded:

```
stranded cost = boards × (board value − on-board parts × (1 − migration)) × MWD cost rate
```

The cover with the lowest mean cost (setups + rush + lost + carrying + stranded) is
recommended; ties go to the longer cover.
