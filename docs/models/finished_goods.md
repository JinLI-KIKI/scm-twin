# Module 4 — finished goods: formulas

Code: `src/finished_goods.py` (Python) and `src/dash/fg_engine.js` (browser), kept identical by
`tests/test_fg_parity.py`. Parameters: `data/fg_params.csv`, `data/fg_models.csv`,
`data/fg_archetypes.csv`. Rules: R26–R33 in [`ASSUMPTIONS.md`](../ASSUMPTIONS.md).

## 1. Timeline

| Symbol | Meaning | Default |
|---|---|---|
| `EOL` | last build week of the old model | week 30 |
| `T` | build release to MGI arrival (`build_to_mgi_weeks`) | 5 weeks |
| `launch` | successor reaches the market = successor NPI + `T` | week 31 |
| `H` | horizon = `launch` + `tail_weeks` + 1 | 40 weeks |
| `L` | liability window: kits are ordered `L` weeks before the build | 16 weeks |
| `t_lock` | sales lock = `EOL` − `lock_lead_weeks` + region spread (−2…+2) | about week 8 |

## 2. Demand

Planned sell-through for one model in one region (share `sh` of the model's peak):

```
S[w] = peak × sh                                   w < launch
S[w] = peak × sh × max(0, 1 − (w − launch + 1) / (tail + 1))   w ≥ launch   (linear fade)
```

Actual sell-through, per Monte Carlo run:

```
A[w] = S[w] × level × noise[w]
level    ~ max(0.3, Normal(1, level_error_sd))       one draw per model and run, all regions
noise[w] ~ max(0, 1 + Normal(0, σw)),  σw = weekly_error_mape × √(π/2)
```

`level` is the surprise nobody knows in advance; `noise` is week-to-week scatter.

## 3. Forecast before the lock

Sales starts optimistic and chases upside, never cutting below plan:

```
r      = ΣA / ΣS over the last 4 weeks
mult   = (1 + sales_bias) × (1 + sales_chase × max(0, r − 1))
fc[i]  = S[i] × mult        for every future week i
```

## 4. Weekly loop (one model, one region)

State: `mgi` (units in the MGI), `chan` (units at dealers), `pipe[i]` (builds arriving in
week `i`), `kit[b]` (kits for build week `b`), `bank` (kits on hand, not yet built).
Cover `C = mgi_wos + channel_wos` (weeks).

1. **Material (MRP), before the lock only.** For build week `b = w + L`:
   ```
   proj   = bank + Σ_{j=w}^{b−1} (kit[j] − fc[j + T + C])
   kit[b] = max(0, fc[b + T + C] − max(0, proj))
   ```
2. **Build release**, while `w < EOL`: `bank += kit[w]`, then
   ```
   before the lock:  build = min(bank, max(0, Σ fc[w+1 … w+T+C] − (mgi + chan + Σ pipe[w … w+T])))
   after the lock:   backlog += plan[w];  build = min(bank, backlog);  backlog −= build
   ```
   `pipe[w + T] += build`.
3. **Arrivals and sales**: `mgi += pipe[w]`; `sold = min(chan, A[w])`; `lost += A[w] − sold`;
   `chan −= sold`. At `w = launch` the channel stock is recorded for price protection.
4. **Sell-in** (MGI → dealers) to a forward cover `wos`:
   ```
   wos = channel_wos                       normally
       = drain_wos   (drain strategies)    from launch − drain_weeks
       = push_wos    (push strategies)     from launch − drain_weeks until launch
   ship = min(mgi, max(0, Σ fc over the next wos weeks − chan))
   ```

## 5. The sales lock (R28, Q25)

At `t_lock` the forecast is reset from the last `lock_window_weeks` of sell-through and the
GEO's own style:

```
r_d   = ΣA / ΣS over the lock window
fc[i] = S[i] × r_d × (1 + bias_GEO)                  i ≥ t_lock
bias_GEO ~ Normal(lock_bias, lock_bias_sd)           one draw per GEO and run (Q24)
need  = max(0, Σ fc[t_lock …] − mgi − chan − units in flight)
```

**IBP hedge (R32)**, strategy `lock_ibp` only: `need ×= max(0, 1 + hedge)` with
`hedge = −ibp_learn × bias_GEO + Normal(0, ibp_noise_sd)`; negative when the GEO locks high.

Locked is locked: the builds still needed are frozen as a plan over weeks `t_lock … EOL−1`
(weighted by the forecast each build would cover), and the final material buy is placed:

```
committed = bank + kits already due in t_lock … t_lock+L−1
final_buy = max(0, need − committed)          spread over build weeks beyond the liability window
cut       = max(0, committed − need)          kits that will never be built: MWD
```

## 6. End of horizon

```
returned     = min(dealer leftovers, stock_rotation_cap × sell-in of the last 13 weeks)   (R30)
dealer kept  = leftovers − returned
dealer loss  = kept × price × (1 − launch_drop) × (1 − dealer_clearance_recovery)
excess       = MGI stock + units in flight + returned
kits left    = unbuilt kits (MWD, valued at the cost of parts that die with the platform)
```

## 7. Disposition of excess (R11, R25, R26)

Net recovery per good unit, best path first, each within its capacity share:

| Path | Net per unit | Capacity |
|---|---|---|
| Other GEO as is | `p_post × divert_price_factor − divert_cost + refund` | `divert_capacity_share` |
| Rework and resell | `p_post × rework_price_factor − cost × rework_pct − rework_labour + refund` | `rework_capacity_share` |
| Tear down | `cost × teardown_pct − domestic duty` | unlimited |
| Liquidate | `price × liquidation_pct − domestic duty` | unlimited |
| Scrap | `−scrap_cost + refund` | unlimited |

`p_post = price × (1 − launch_drop)`. Post-customs: `refund = drawback_share × duty`; FTZ:
`domestic duty = duty` on units that enter domestic commerce. Units failing re-inspection
(`aged_failure_rate`) can only be torn down.

```
loss = excess × landed − recovery + excess × reinspect_cost
       + excess × landed × carrying_rate × disposition_delay / 52 + returned × return_handling
```

## 8. Costs reported

```
price protection   = channel stock at launch × price × launch_drop
markdown           = price protection + sell-in after launch × price × launch_drop
markdown floor     = units sold after launch × price × launch_drop   (unavoidable: they sell at the new price anyway)
lost margin        = lost units × (price − landed) × (1 − lost_to_successor_share)
MWD                = kits left × die-with-platform value per kit
avoidable cost     = (markdown − floor) + excess loss + MWD + lost margin        brand view
system cost        = avoidable cost + dealer loss                               brand + dealers
```

## 9. Monte Carlo

Per run: one `bias_GEO` and one `hedge` per GEO, one `level` per model, one region spread and
one noise series per model and region. Every strategy uses the same seed, so all strategies
see the same demand (common random numbers). The page's range mode also draws each input
with a range from a triangular distribution (low, base, high) once per run. Results: mean,
P10 and P90 over runs.
