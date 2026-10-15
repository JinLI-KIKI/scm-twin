"""
Module 4 — finished goods at MGI and in the channel, around a successor launch.

Flow:  factory -> MGI (regional DC after customs) -> dealer channel -> end customer.

  plan        Builds follow the sales forecast, which runs optimistic (sales_bias) and does
              not see the demand-level surprise of this model (level_error_sd).
  lock (R28)  About 22 weeks before EOL (virtualized) the brand's sales team, after talking
              with dealers, locks the old model's remaining volume. The number reads recent
              sell-through, so it carries the true demand level, plus each GEO's own bias:
              some sales teams lock high, some low (Q24; drawn per region and run). Locked is
              locked (Q25): the builds still needed are frozen, their material is ordered at
              once (final buy), and nothing moves afterwards, up or down. Kits already
              committed beyond the locked need become MWD. The lock is the brand's
              commitment, not the dealers': sales must sell it (R31).
  channel     The MGI replenishes dealers to a forward cover (weeks of forecast). Two
              variants before launch: drain (low cover) and push (high cover, to hit a
              sell-in target).
  launch      The successor launches; the old model's net price steps down (R26). Units the
              dealers hold get price protection (R27); MGI units sold in afterwards are
              invoiced at the lower price. The old model keeps selling until EOL, tapering.
  end         Dealer leftovers come back through stock rotation, capped at a share of the
              dealer's last-quarter purchases; the rest the dealer clears itself (R30). Once
              sold in, most of the risk has left the brand. What sales could not sell stays
              with the BU: it either absorbs the loss or resells through other GEOs (R31).
              Excess is re-inspected (R26) and sent down paths 2-6 of R11 by net recovery per
              unit, within capacity: resell to another GEO as is, rework and resell, tear down,
              liquidate, scrap.
  customs     Post-customs MGI: duty was paid on entry; exported or destroyed units get back
              only drawback_share of it. FTZ: duty is paid only on units that enter domestic
              commerce (R25).

Strategies:  sales lock · lock + drain · lock + push (sales locks, then pushes stock into the
channel before launch) · lock + IBP hedge (supply follows the locked volume times 1 + hedge,
where IBP sets the hedge from each GEO's sales history, often negative; R32). Two no-lock benchmarks (push, plan) keep adjusting material and builds
to the end; in practice component end-of-life forces a final buy, so they show what full
flexibility would be worth rather than a real option. Common random numbers: every
strategy sees the same demand draws, so differences come from the decision, not the dice.

Run:  python3 src/finished_goods.py
"""
import csv
import math
import os
import random
from collections import defaultdict

import mwd_engine as E
from prng import PortableRandom

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
MGI_OF = {"US": "US", "UK": "UK", "FR": "EU", "DE": "EU", "JP": "JP", "BR": "BR"}
DUTY_COUNTRY = {"US": "USA", "EU": "EU", "UK": "GBR", "JP": "JPN", "BR": "BRA"}
STRATEGIES = {
    "push": dict(lock=False, cover="push", label="Push sell-in, no lock (benchmark)"),
    "plan": dict(lock=False, cover="normal", label="Sales plan, no lock (benchmark)"),
    "lock": dict(lock=True, cover="normal", label="Sales volume lock (R28)"),
    "lock_drain": dict(lock=True, cover="drain", label="Sales lock + drain channel"),
    "lock_push": dict(lock=True, cover="push", label="Sales lock + push into channel"),
    "lock_ibp": dict(lock=True, cover="normal", ibp=True, label="Sales lock + IBP hedge (R32)"),
}
PATHS = ["divert", "rework", "teardown", "liquidate", "scrap"]


def _csv(name):
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_fg():
    P = {r["key"]: float(r["value"]) for r in _csv("fg_params.csv")}
    models = {r["model"]: r for r in _csv("fg_models.csv")}
    arche = {r["product_line"]: r for r in _csv("fg_archetypes.csv")}
    duty_cn = {r["iso3"]: float(r["duty_cn_origin_pct"]) / 100 for r in _csv("tariffs.csv")}
    return P, models, arche, duty_cn


def unit_cost(model, mats, bom, P):
    sku = next(s for s in bom if s.startswith(model + "_"))
    return sum(mats[m]["unit_cost"] * q for m, q in bom[sku].items()) + P["conversion_cost_usd"]


def ssum(values):
    """Plain left-to-right sum, so results match the JavaScript port to the last digits."""
    t = 0.0
    for x in values:
        t += x
    return t


# ----------------------------------------------------------------------------- disposition
def path_values(price, cost, duty_unit, ftz, P, rework_pct, teardown_pct, liquidation_pct):
    """Net recovery per good unit on each path, after re-inspection is paid.
    Post-customs: duty already paid; exports and destruction get drawback_share back.
    FTZ: no duty paid yet; units that enter domestic commerce pay it on exit."""
    post = price * (1 - P["launch_drop_pct"])
    refund = 0.0 if ftz else P["drawback_share"] * duty_unit
    dom_duty = duty_unit if ftz else 0.0
    return {
        "divert": (post * P["divert_price_factor"] - P["divert_cost_usd"] + refund,
                   P["divert_capacity_share"]),
        "rework": (post * P["rework_price_factor"] - cost * rework_pct - P["rework_labour_usd"] + refund,
                   P["rework_capacity_share"]),
        "teardown": (cost * teardown_pct - dom_duty, 1.0),
        "liquidate": (price * liquidation_pct - dom_duty, 1.0),
        "scrap": (-P["scrap_cost_usd"] + refund, 1.0),
    }


def disposition(units, price, cost, duty_unit, ftz, P, rework_pct, teardown_pct, liquidation_pct):
    """Send excess units down the paths, best net recovery first, within capacity.
    Returns (loss $, mix {path: units}, duty sunk $). Loss is against landed cost."""
    if units <= 1e-9:
        return 0.0, {}, 0.0
    vals = path_values(price, cost, duty_unit, ftz, P, rework_pct, teardown_pct, liquidation_pct)
    landed = cost + (0.0 if ftz else duty_unit)
    good = units * (1 - P["aged_failure_rate"])
    failed = units - good                                  # fail re-inspection -> teardown only
    rec, mix, left = 0.0, defaultdict(float), good
    for name, (net, cap) in sorted(vals.items(), key=lambda kv: -kv[1][0]):
        if left <= 1e-9:
            break
        take = min(left, units * cap)
        rec += take * net
        mix[name] += take
        left -= take
    rec += failed * vals["teardown"][0]
    mix["teardown"] += failed
    carry = units * landed * P.get("carrying_rate_annual", 0.20) * P["disposition_delay_weeks"] / 52
    loss = units * landed - rec + units * P["reinspect_cost_usd"] + carry
    if ftz:
        sunk = (mix["teardown"] + mix["liquidate"]) * duty_unit
    else:
        refunded = (mix["divert"] + mix["rework"] + mix["scrap"]) * P["drawback_share"] * duty_unit
        sunk = units * duty_unit - refunded
    return loss, dict(mix), sunk


# ----------------------------------------------------------------------------- simulation
def market_shape(m, launch, tail_weeks, horizon):
    """Planned weekly sell-through of the old model: flat until the successor reaches the
    market, then a linear fade over tail_weeks."""
    base = m["peak"]
    out = []
    for w in range(horizon):
        if w < launch:
            out.append(base)
        else:
            out.append(base * max(0.0, 1 - (w - launch + 1) / (tail_weeks + 1)))
    return out


def _region_run(S, A, P, cfg, launch, eol, liability, t_lock, traj, runs, lock_bias=0.0,
                ibp_hedge=0.0):
    """Weekly loop for one model in one MGI region.
    S planned sell-through, A actual sell-through. Builds stop at EOL (last build week)."""
    n = len(S)
    T = int(P["build_to_mgi_weeks"])
    L = int(liability)
    C = int(P["mgi_wos_weeks"] + P["channel_wos_weeks"])        # planner's position cover
    bias = 1 + P["sales_bias"]
    fc = [x * bias for x in S]                  # forecast in use
    locked = False

    def f(i):
        return fc[i] if i < n else 0.0

    def fwd(w, weeks):                          # forecast for weeks w+1 .. w+weeks
        return ssum(fc[w + 1:w + 1 + weeks])

    mgi = P["mgi_wos_weeks"] * fc[0]
    chan = P["channel_wos_weeks"] * fc[0]
    pipe = [0.0] * (n + T + 1)                  # builds arriving at week i
    for i in range(T):
        pipe[i] = fc[i + C]                     # already in flight at the start
    kit = [0.0] * (n + L)                       # material kits arriving for build week b
    for b in range(min(L, eol)):
        kit[b] = f(b + T + C)                   # ordered before the start (inside liability)
    bank = 0.0
    plan = None                                 # frozen build plan after the lock
    backlog = 0.0
    c = dict(lost=0.0, sold_pre=0.0, sold_post=0.0, sell_in_pre=0.0, sell_in_post=0.0,
             chan_launch=0.0, builds=0.0, kits=ssum(kit[:L]), fc_peak=bias, final_buy=0.0,
             cut_at_lock=0.0, hedge_units=0.0)
    sell_in = [0.0] * n
    for w in range(n):
        seen = range(max(0, w - 4), w)
        r = ssum(A[i] for i in seen) / max(1e-9, ssum(S[i] for i in seen)) if w >= 4 else 1.0
        if cfg["lock"] and w == t_lock:         # R28: sales locks from recent sell-through
            locked = True
            hist = range(max(0, w - int(P["lock_window_weeks"])), w)
            r_d = ssum(A[i] for i in hist) / max(1e-9, ssum(S[i] for i in hist)) if w > 0 else 1.0
            mult = r_d * (1 + lock_bias)              # each GEO's sales style (Q24)
            for i in range(w, n):
                fc[i] = S[i] * mult
            # Q25: locked is locked. Builds still needed to deliver the locked volume are
            # frozen, and all their material is ordered now (final buy). Kits already
            # committed beyond that need stay unused: a cut at the lock becomes MWD.
            in_flight = ssum(pipe[w:w + T + 1])
            need = max(0.0, ssum(fc[w:]) - mgi - chan - in_flight)
            if cfg.get("ibp"):                  # R32: IBP sizes supply off sales history
                need *= max(0.0, 1 + ibp_hedge)
                c["hedge_units"] = need * ibp_hedge / max(1e-9, 1 + ibp_hedge)
            weeks = list(range(w, eol))
            if weeks:
                wt = [f(b + T + C) for b in weeks[:-1]]
                wt.append(ssum(fc[min(n, weeks[-1] + T + C):]))   # last build covers the rest
                tot_w = ssum(wt) or 1.0
                plan = {b: need * x / tot_w for b, x in zip(weeks, wt)}
            committed = bank + ssum(kit[b] for b in range(w, min(eol, w + L)))
            buy = max(0.0, need - committed)
            later = [b for b in weeks if b >= w + L] or weeks[-1:]
            for b in later:
                kit[b] += buy / len(later)
            c["final_buy"] = buy
            c["cut_at_lock"] = max(0.0, committed - need)
            c["kits"] += buy
        elif not locked:                        # sales chases upside, never cuts below plan
            mult = bias * (1 + P["sales_chase"] * max(0.0, r - 1))
            c["fc_peak"] = max(c["fc_peak"], mult)
            for i in range(w, n):
                fc[i] = S[i] * mult
        # 1) material: order kits for build week w+L, netting projected surplus (MRP)
        b = w + L
        if b < eol and not locked:
            proj = bank + ssum(kit[j] - f(j + T + C) for j in range(w, b))
            kit[b] = max(0.0, f(b + T + C) - max(0.0, proj))
            c["kits"] += kit[b]
        # 2) build release: order-up-to on total position, limited by kits on hand
        build = 0.0
        if w < eol:
            bank += kit[w]
            position = mgi + chan + ssum(pipe[w:w + T + 1])
            if plan is not None:                # after the lock builds follow the frozen plan;
                backlog += plan.get(w, 0.0)     # anything short of kits is built later
                build = min(bank, backlog)
                backlog -= build
            else:
                build = min(bank, max(0.0, fwd(w, T + C) - position))
            bank -= build
            pipe[w + T] += build
            c["builds"] += build
        # 3) arrivals, successor launch, sales
        mgi += pipe[w]
        if w == launch:
            c["chan_launch"] = chan
        s = min(chan, A[w])
        c["lost"] += A[w] - s
        chan -= s
        c["sold_pre" if w < launch else "sold_post"] += s
        # 4) replenish the channel to its forward cover
        near = launch - P["drain_weeks"] <= w
        wos = P["channel_wos_weeks"]
        if near and cfg["cover"] == "drain":
            wos = P["drain_wos_weeks"]
        elif near and w < launch and cfg["cover"] == "push":
            wos = P["push_wos_weeks"]
        whole = int(wos)
        cover = fwd(w, whole) + (wos - whole) * f(w + 1 + whole)
        ship = min(mgi, max(0.0, cover - chan))
        mgi -= ship
        chan += ship
        sell_in[w] = ship
        c["sell_in_pre" if w < launch else "sell_in_post"] += ship
        for key, val in (("demand", A[w]), ("forecast", fc[w]), ("sold", s), ("lost", A[w] - s),
                         ("builds", build), ("arrivals", pipe[w]), ("sell_in", ship),
                         ("mgi", mgi), ("channel", chan), ("kits", bank)):
            traj[key][w] += val / runs
    c["rotation_base"] = ssum(sell_in[max(0, n - int(P["stock_rotation_window_weeks"])):])
    return mgi + ssum(pipe[n:]), chan, bank, c


def simulate(strategy="lock", overrides=None, duty_override=None, ftz=False, runs=600, seed=11,
             rng_kind="portable"):
    """Monte Carlo of one strategy. Returns mean / P10 / P90 of each metric, mean weekly
    trajectories, and means by region and by model."""
    cfg = STRATEGIES[strategy]
    mats, models, locales, bom, used_by, params = E.load()
    P, fgm, _, duty_cn = load_fg()
    P["carrying_rate_annual"] = params["carrying_rate_annual"]
    if overrides:
        P.update(overrides)
    liability = params["liability_window_weeks"]
    T = int(P["build_to_mgi_weeks"])
    rng = PortableRandom(seed) if rng_kind == "portable" else random.Random(seed)
    sigma_w = P["weekly_error_mape"] * math.sqrt(math.pi / 2)
    share = defaultdict(float)
    for loc, s in locales.items():
        share[MGI_OF[loc]] += s
    regions = sorted(share)
    first = next(iter(fgm))
    launch = models[fgm[first]["successor"]]["npi"] + T      # successor reaches the market
    eol = models[first]["eol"]                               # last build week of the old model
    horizon = launch + int(P["tail_weeks"]) + 1
    traj = {k: [0.0] * horizon for k in ["demand", "forecast", "sold", "lost", "builds",
                                         "arrivals", "sell_in", "mgi", "channel", "kits"]}
    runs_out = []
    by_region = defaultdict(lambda: defaultdict(float))
    by_model = defaultdict(lambda: defaultdict(float))
    info_m = {}
    for m, info in fgm.items():
        sku = next(s for s in bom if s.startswith(m + "_"))
        plat = models[m]["platform"]
        dies = ssum(mats[x]["unit_cost"] * q for x, q in bom[sku].items()
                   if all(models[s.split("_")[0]]["platform"] == plat for s in used_by[x]))
        info_m[m] = dict(price=float(info["channel_net_price_usd"]),
                         cost=models[m]["customs_value"] + P["inbound_freight_usd"],
                         cv=models[m]["customs_value"], kit_mwd=dies, eol=models[m]["eol"],
                         shape=market_shape(models[m], launch, P["tail_weeks"], horizon),
                         rw=float(info["rework_cost_pct"]), td=float(info["teardown_recovery_pct"]),
                         lq=float(info["liquidation_recovery_pct"]))
    for _ in range(runs):
        tot = defaultdict(float)
        # Q24: every GEO's sales team locks high or low in its own way
        style = {g: rng.gauss(P["lock_bias"], P["lock_bias_sd"]) for g in regions}
        # R32: IBP learns part of each GEO's habit from past models and hedges against it
        hedge = {g: -P["ibp_learn"] * (style[g] - 0.0) + rng.gauss(0, P["ibp_noise_sd"]) for g in regions}
        for m, im in info_m.items():
            price, cost = im["price"], im["cost"]
            drop = price * P["launch_drop_pct"]
            level = max(0.3, rng.gauss(1.0, P["level_error_sd"]))    # same for every region
            for region in regions:
                sh = share[region]
                duty = (duty_override or {}).get(region, duty_cn[DUTY_COUNTRY[region]])
                duty_unit = im["cv"] * duty
                spread = rng.randint(-int(P["lock_region_spread_weeks"]), int(P["lock_region_spread_weeks"]))
                noise = [max(0.0, 1 + rng.gauss(0, sigma_w)) for _ in range(horizon)]
                S = [x * sh for x in im["shape"]]
                A = [S[w] * level * noise[w] for w in range(horizon)]
                t_lock = int(im["eol"] - P["lock_lead_weeks"] + spread)
                mgi_left, chan_left, kits_left, c = _region_run(
                    S, A, P, cfg, launch, im["eol"], liability, t_lock, traj, runs, style[region],
                    hedge[region])
                # R30: dealer leftovers come back through stock rotation (capped by the
                # dealer's recent purchases); the rest the dealer clears on its own
                returned = min(chan_left, P["stock_rotation_cap"] * c["rotation_base"])
                kept = chan_left - returned
                dealer_loss = kept * price * (1 - P["launch_drop_pct"]) * (1 - P["dealer_clearance_recovery"])
                excess = mgi_left + returned
                loss, mix, sunk = disposition(excess, price, cost, duty_unit, ftz, P,
                                              im["rw"], im["td"], im["lq"])
                loss += returned * P["return_handling_usd"]
                prot = c["chan_launch"] * drop
                markdown = prot + c["sell_in_post"] * drop
                floor = c["sold_post"] * drop
                mwd = kits_left * im["kit_mwd"]
                lost_margin = c["lost"] * (price - cost) * (1 - P["lost_to_successor_share"])
                row = {
                    "demand_units": ssum(A), "sold_units": c["sold_pre"] + c["sold_post"],
                    "builds_units": c["builds"], "kits_ordered": c["kits"],
                    "sell_in_pre_launch_units": c["sell_in_pre"],
                    "channel_at_launch_units": c["chan_launch"],
                    "excess_units": excess, "returned_units": returned, "lost_units": c["lost"],
                    "dealer_kept_units": kept, "dealer_loss_usd": dealer_loss,
                    "mwd_kits": kits_left,
                    "price_protection_usd": prot, "launch_markdown_usd": markdown,
                    "markdown_floor_usd": floor, "markdown_above_floor_usd": markdown - floor,
                    "excess_loss_usd": loss, "mwd_usd": mwd,
                    "lost_margin_usd": lost_margin, "duty_sunk_usd": sunk,
                    "avoidable_cost_usd": (markdown - floor) + loss + mwd + lost_margin,
                    "system_cost_usd": (markdown - floor) + loss + mwd + lost_margin + dealer_loss,
                }
                for p_ in PATHS:
                    row["mix_" + p_] = mix.get(p_, 0.0)
                for kk, vv in row.items():
                    tot[kk] += vv
                    by_region[region][kk] += vv / runs
                    by_model[m][kk] += vv / runs
        runs_out.append(dict(tot))

    def stat(key):
        v = sorted(r[key] for r in runs_out)
        return {"mean": ssum(v) / len(v), "p10": v[int(.1 * (len(v) - 1))],
                "p90": v[int(.9 * (len(v) - 1))]}

    return {"strategy": strategy, "label": cfg["label"], "ftz": ftz, "duty_override": duty_override,
            "summary": {kk: stat(kk) for kk in runs_out[0]}, "traj": traj,
            "by_region": {r: dict(v) for r, v in by_region.items()},
            "by_model": {m: dict(v) for m, v in by_model.items()},
            "runs": runs, "launch_week": launch, "eol_week": eol, "horizon": horizon,
            "lock_week": eol - P["lock_lead_weeks"], "liability_weeks": liability,
            "landed_cost": {m: im["cost"] for m, im in info_m.items()},
            "kit_mwd_value": {m: im["kit_mwd"] for m, im in info_m.items()}}


def engine_input(duty_override=None):
    """Everything the browser engine (src/dash/fg_engine.js) needs to run the same simulation."""
    mats, models, locales, bom, used_by, params = E.load()
    P, fgm, _, duty_cn = load_fg()
    P["carrying_rate_annual"] = params["carrying_rate_annual"]
    share = defaultdict(float)
    for loc, s in locales.items():
        share[MGI_OF[loc]] += s
    regions = sorted(share)
    out_models = []
    for m, info in fgm.items():
        sku = next(s for s in bom if s.startswith(m + "_"))
        plat = models[m]["platform"]
        dies = ssum(mats[x]["unit_cost"] * q for x, q in bom[sku].items()
                    if all(models[s.split("_")[0]]["platform"] == plat for s in used_by[x]))
        out_models.append({"name": m, "price": float(info["channel_net_price_usd"]),
                           "cv": models[m]["customs_value"], "kit_mwd": dies, "eol": models[m]["eol"],
                           "peak": models[m]["peak"], "rw": float(info["rework_cost_pct"]),
                           "td": float(info["teardown_recovery_pct"]),
                           "lq": float(info["liquidation_recovery_pct"])})
    first = next(iter(fgm))
    return {"P": P, "liability": params["liability_window_weeks"],
            "npi_successor": models[fgm[first]["successor"]]["npi"],
            "regions": regions, "share": {g: share[g] for g in regions},
            "duty": {g: (duty_override or {}).get(g, duty_cn[DUTY_COUNTRY[g]]) for g in regions},
            "models": out_models, "paths": PATHS,
            "strategies": {k: {kk: vv for kk, vv in v.items()} for k, v in STRATEGIES.items()}}


# ----------------------------------------------------------------------------- product lines
def archetype_table(overrides=None):
    """Net recovery per excess unit on each path, by product line (domestic, no duty)."""
    P, _, arche, _ = load_fg()
    if overrides:
        P.update(overrides)
    rows = []
    for line, a in arche.items():
        price, cost = float(a["channel_net_price_usd"]), float(a["unit_cost_usd"])
        vals = path_values(price, cost, 0.0, False, P, float(a["rework_cost_pct"]),
                           float(a["teardown_recovery_pct"]), float(a["liquidation_recovery_pct"]))
        nets = {k: v[0] - P["reinspect_cost_usd"] for k, v in vals.items()}
        order = [k for k, _ in sorted(nets.items(), key=lambda kv: -kv[1])]
        rework_pays = nets["rework"] > max(nets["teardown"], nets["liquidate"])
        rows.append({"line": line, "price": price, "cost": cost, "rework_pct": float(a["rework_cost_pct"]),
                     "nets": nets, "order": order, "rework_pays": rework_pays})
    return rows


def main():
    show = ["demand_units", "kits_ordered", "builds_units", "sell_in_pre_launch_units", "channel_at_launch_units",
            "excess_units", "returned_units", "dealer_kept_units", "mwd_kits", "lost_units",
            "price_protection_usd", "markdown_above_floor_usd", "excess_loss_usd", "mwd_usd",
            "lost_margin_usd", "duty_sunk_usd", "avoidable_cost_usd", "dealer_loss_usd", "system_cost_usd"]
    cases = [(s, {}) for s in STRATEGIES] + [
        ("lock", dict(duty_override={"US": 0.25})),
        ("lock", dict(duty_override={"US": 0.25}, ftz=True)),
    ]
    for s, kw in cases:
        res = simulate(s, **kw)
        tag = STRATEGIES[s]["label"]
        if kw:
            tag += " · US duty 25% " + ("FTZ MGI" if kw.get("ftz") else "post-customs MGI")
        print(f"\n== {tag}   (mean [P10 .. P90], {res['runs']} runs)")
        for k in show:
            st = res["summary"][k]
            print(f"  {k:<28}{st['mean']:>13,.0f}   [{st['p10']:,.0f} .. {st['p90']:,.0f}]")
    print("\n== Excess disposition by product line (net recovery per unit, $; R11 check)")
    print(f"  {'line':<12}{'price':>7}{'cost':>7}" + "".join(f"{p:>11}" for p in PATHS) + "   rework?")
    for r in archetype_table():
        print(f"  {r['line']:<12}{r['price']:>7.0f}{r['cost']:>7.0f}"
              + "".join(f"{r['nets'][p]:>11.0f}" for p in PATHS)
              + f"   {'rework' if r['rework_pays'] else 'skip rework'}")


if __name__ == "__main__":
    main()
