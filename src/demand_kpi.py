"""
Module 5 — demand and KPI view (Roadmap A2).

A tariff on China-made laptops starts at week 0 of the fiscal year. The brand decides when the
US volume leaves China (cutover week C, or not at all) while its pricing puts part of the tariff
into the channel price. The same decision is scored twice:

  BU view       the planner / BU KPIs: fiscal-year shipment target in sell-in units (R33) and MWD
                (claimed MWD by default: every plan cancelled inside the liability window counts at
                full BOM value, R1/R8). Tariffs are not a BU KPI; they reach the BU only through
                the price and the units it loses.
  company view  the total cost of the fiscal year against a year with no tariff: tariff the brand
                absorbs, gross margin on the units the price rise loses, physical MWD, holding,
                relocation and rework (Module 2), expediting, the longer chain and the new site's
                conversion uplift (Module 3).

Weekly, for model m (US share of its lifecycle demand q0) and week w:

  china(w)  = 1                                  w < C (or no transfer)
            = max(0, 1 - (w - C) / ramp)         after the cutover: the new site ramps up linearly
  tariff    = t x customs_value x (1 - exporter_absorb)          per China-made unit
  rise(w)   = passthrough x tariff x china(w)    from reprice_lag_weeks on (0 before)
  q(w)      = q0(w) x (1 + rise / price)^elasticity
  paid      = q x tariff x china ;  recovered = q x rise ;  absorbed = paid - recovered
  lost      = (q0 - q) x price x gross_margin                 (negative when the catch-up sells above plan)

Fiscal-year target (R42, R45): 100% of the pre-tariff plan in sell-in units, not lowered. A
shortfall in the first half is re-phased: Q1 and Q2 come in lower and Q3 and Q4 must sell more,
with a channel price discount d on every unit from catchup_from_week on, large enough to close
the gap (capped at max_promo_discount):
  sum over models of H2_units x ((1 - d)^elasticity - 1) = target x plan - units
  promotion = sum of H2 units x d x price
Only when even the cap cannot close it is the target lowered to what can be reached.

Sales negotiate the discount (price points) with the channel and the BU usually funds it, so the
BU trades MWD against points (R43, R45). Neither always wins; it depends on
  what a dollar of MWD costs the BU     mwd_cost_rate
  how much of it migrates               mwd_transferability (claimed -> physical MWD)
  what a point costs and buys           bu_funds_support, points_effect, elasticity
  BU cost = mwd_cost_rate x (claimed - t x (claimed - physical) + eol) + bu_funds_support x promotion

BU pick: among the options that reach the target, the lowest BU MWD + BU-funded price support
(ties: the latest); if none does, the one closest to target. Company pick: the lowest total cost, among the options
that reach the target when the company holds the fiscal-year target too (default), else of all.
Where they differ, the gap is what the BU's KPIs cost the company in the year.

src/dash/dk_engine.js is the same model for the browser; tests/test_dk_parity.py checks it.
Run:  python3 src/demand_kpi.py
"""
import csv
import os

import business_case as BC
import mwd_engine as E
import transfer as TR

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
WEEKS = 52
LATE = (20, 26, 39)            # cutover options after the liability window (nothing cancelled)


def _csv(name):
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def dk_input(region="US"):
    """Everything the model needs, as plain data (also embedded in the page)."""
    mats, models, locales, bom, used_by, params = E.load()
    share = locales[region]
    dm = {r["model"]: r for r in _csv("demand_models.csv")}
    mods = []
    for k, m in models.items():
        r = dm[k]
        mods.append({"model": k, "customs_value": m["customs_value"],
                     "price": float(r["channel_net_price_usd"]), "elasticity": float(r["elasticity"]),
                     "gross_margin": float(r["gross_margin_pct"]) / 100,
                     "demand": [E.model_weekly_demand(m, w) * share for w in range(WEEKS)]})
    window = int(params["liability_window_weeks"])
    rows = {r["cutover"]: r for r in TR.sweep(region, 0.0, 0.0, True)}   # MWD side does not depend on the tariff
    opts = []
    for c in list(range(window + 1)) + list(LATE):
        r = rows[min(c, window)]
        opts.append({"id": f"C{c}", "cutover": c, "claimed_mwd": r["freed_usd"], "mwd": r["mwd"],
                     "holding": r["holding"], "relocation": r["relocation"], "rework": r["rework"]})
    opts.append({"id": "stay", "cutover": None, "claimed_mwd": 0.0, "mwd": 0.0, "holding": 0.0,
                 "relocation": 0.0, "rework": 0.0})
    p = BC.region_profile(region)
    c = BC.CASE
    mid = lambda x: (x[0] + x[1]) / 2
    eol = (BC._overcommit_weeks(BC._sigma(c["fa_new"]), c["window_new"], mid(c["rho"]))
           - BC._overcommit_weeks(BC._sigma(c["fa_base"]), c["window_old"], mid(c["rho"]))) \
        * p["weekly_locked"] * c["eol_events_per_year"]
    P = {r["key"]: float(r["value"]) for r in _csv("demand_params.csv")}
    case = {"eol_mwd_year": eol, "pipeline_year": p["weekly_bom"] * p["lt_adder"] * p["carry"],
            "conv_cost": c["conv_cost_per_unit"], "lt_adder": p["lt_adder"], "weekly_units": p["weekly_units"]}
    return {"weeks": WEEKS, "window": window, "models": mods, "options": opts, "case": case, "P": P}


def china_share(w, cutover, ramp):
    if cutover is None or w < cutover:
        return 1.0
    return max(0.0, 1.0 - (w - cutover) / ramp) if ramp > 0 else 0.0


def catch_up(inp, P, base, gap):
    """Discount d on every unit from catchup_from_week on that sells `gap` extra units in the year,
    capped at max_promo_discount (R45). base[i][w] = units of model i before the discount."""
    cw = int(P["catchup_from_week"])
    h2 = [sum(base[i][cw:]) for i in range(len(inp["models"]))]
    eff = P["points_effect"]                      # share of the points that reaches the shelf price
    extra = lambda d: sum(h * ((1 - eff * d) ** m["elasticity"] - 1) for h, m in zip(h2, inp["models"]))
    if gap <= 1e-9 or sum(h2) <= 0:
        return 0.0
    hi = P["max_promo_discount"]
    if extra(hi) <= gap:
        return hi
    lo = 0.0
    for _ in range(50):
        mid = (lo + hi) / 2
        if extra(mid) < gap:
            lo = mid
        else:
            hi = mid
    return hi


def evaluate(inp, P, opt):
    """Fiscal-year figures for one option, including the second-half catch-up (R45)."""
    C = opt["cutover"]
    tariff_rate = P["tariff_cn"] * (1 - P["exporter_absorb"])
    base, plan, before = [], 0.0, 0.0
    for m in inp["models"]:
        tariff = tariff_rate * m["customs_value"]
        row = []
        for w in range(inp["weeks"]):
            q0 = m["demand"][w]
            ch = china_share(w, C, P["ramp_weeks"])
            rise = P["passthrough"] * tariff * ch if w >= P["reprice_lag_weeks"] else 0.0
            row.append(q0 * (1 + rise / m["price"]) ** m["elasticity"] if q0 > 0 else 0.0)
            plan += q0
        base.append(row)
        before += sum(row)
    disc = catch_up(inp, P, base, P["target_tolerance"] * plan - before)
    cw = int(P["catchup_from_week"])
    units = paid = recovered = lost = conv_units = promo = 0.0
    weekly = [0.0] * inp["weeks"]
    quarters = [[0.0, 0.0] for _ in range(4)]          # [plan, sell-in] per quarter of 13 weeks
    for i, m in enumerate(inp["models"]):
        tariff = tariff_rate * m["customs_value"]
        lift = (1 - P["points_effect"] * disc) ** m["elasticity"] if disc > 0 else 1.0
        for w in range(inp["weeks"]):
            q0 = m["demand"][w]
            if q0 <= 0:
                continue
            ch = china_share(w, C, P["ramp_weeks"])
            rise = P["passthrough"] * tariff * ch if w >= P["reprice_lag_weeks"] else 0.0
            q = base[i][w] * (lift if w >= cw else 1.0)
            units += q
            weekly[w] += q
            k = min(3, w // 13)
            quarters[k][0] += q0
            quarters[k][1] += q
            paid += q * tariff * ch
            recovered += q * rise
            lost += (q0 - q) * m["price"] * m["gross_margin"]
            conv_units += q * (1 - ch)
            if w >= cw:
                promo += q * disc * m["price"]
    cs = inp["case"]
    moved = C is not None and C < inp["weeks"]
    frac = (inp["weeks"] - C) / inp["weeks"] if moved else 0.0
    eol = cs["eol_mwd_year"] * frac
    chain = eol + cs["pipeline_year"] * frac
    expedite = P["expedite_usd_per_unit"] * cs["weekly_units"] * cs["lt_adder"] if moved else 0.0
    conv = conv_units * cs["conv_cost"] * P["conv_uplift"]
    transfer = opt["mwd"] + opt["holding"] + opt["relocation"] + opt["rework"]
    parts = {"absorbed": paid - recovered, "lost_margin": lost, "promotion": promo, "transfer": transfer,
             "expedite": expedite, "chain": chain, "conversion": conv}
    # MWD as the BU weighs it (R43): claimed MWD less the share that migrates to other plans or
    # the new site (transferability, down to the physical MWD), plus the longer window's EOL MWD,
    # at what each dollar of MWD really costs the BU (mwd_cost_rate)
    t = P["mwd_transferability"]
    bu_mwd = opt["claimed_mwd"] - t * (opt["claimed_mwd"] - opt["mwd"]) + eol
    bu_mwd_cost = P["mwd_cost_rate"] * bu_mwd
    bu_support = P["bu_funds_support"] * promo          # the price points the BU funds (R45)
    return {"id": opt["id"], "cutover": C, "plan": plan, "units": units, "attainment": units / plan if plan else 1.0,
            "before_catch_up": before / plan if plan else 1.0, "discount": disc, "quarters": quarters,
            "lost_units": plan - units, "tariff_paid": paid, "recovered": recovered, "bu_mwd": bu_mwd,
            "bu_mwd_cost": bu_mwd_cost, "bu_support": bu_support, "bu_cost": bu_mwd_cost + bu_support,
            "claimed_mwd": opt["claimed_mwd"], "physical_mwd": opt["mwd"], "eol_mwd": eol,
            "parts": parts, "company_cost": sum(parts.values()), "weekly": weekly}


def score(inp, P):
    """BU: among the options that reach the target after the catch-up, the lowest MWD plus the
    price support the BU funds (ties: the latest); none does -> the target is lowered to the best
    reachable. Company: lowest cost, among the
    options that reach the target when it holds the fiscal-year target too (R42)."""
    rows = [evaluate(inp, P, o) for o in inp["options"]]
    order = lambda r: inp["weeks"] + 1 if r["cutover"] is None else r["cutover"]
    hit = [r for r in rows if r["attainment"] >= P["target_tolerance"] - 1e-9]
    if hit:
        bu = min(hit, key=lambda r: (r["bu_cost"], -order(r)))
    else:
        bu = max(rows, key=lambda r: (r["attainment"], -r["bu_mwd"]))
    pool = hit if (hit and P["company_holds_target"] >= 0.5) else rows
    co = min(pool, key=lambda r: (r["company_cost"], order(r)))
    return {"rows": rows, "bu": bu["id"], "company": co["id"], "gap": bu["company_cost"] - co["company_cost"],
            "any_hit": bool(hit)}


def bu_grid(inp, P, row_key, row_vals, col_key, col_vals):
    """The BU's pick over two of its trade-off inputs (MWD price, transferability, points)."""
    return [[score(inp, {**P, row_key: a, col_key: b})["bu"] for b in col_vals] for a in row_vals]


def grid(inp, P, tariffs, passthroughs):
    """Gap between the two picks over tariff x pass-through."""
    out = []
    for t in tariffs:
        row = []
        for pt in passthroughs:
            s = score(inp, {**P, "tariff_cn": t, "passthrough": pt})
            row.append({"bu": s["bu"], "company": s["company"], "gap": s["gap"]})
        out.append(row)
    return out


def label(r):
    return "No transfer this year" if r["cutover"] is None else f"Cut over in week {r['cutover']}"


def main():
    inp = dk_input()
    P = inp["P"]
    s = score(inp, P)
    print(f"== Fiscal year with a {P['tariff_cn']:.0%} US tariff on China-made laptops, "
          f"{P['passthrough']:.0%} passed into the price from week {P['reprice_lag_weeks']:.0f}; target "
          f"{P['target_tolerance']:.0%}, catch-up from week {P['catchup_from_week']:.0f} with up to "
          f"{P['max_promo_discount']:.0%} off")
    print(f"  {'option':<8}{'units':>9}{'before':>8}{'disc':>6}{'attain':>8}{'BU MWD':>10}{'absorbed':>10}"
          f"{'lost mgn':>10}{'promo':>9}{'transfer':>10}{'chain+':>10}{'company':>10}")
    for r in s["rows"]:
        p = r["parts"]
        mark = (" <- BU" if r["id"] == s["bu"] else "") + (" <- company" if r["id"] == s["company"] else "")
        print(f"  {r['id']:<8}{r['units']:>9,.0f}{r['before_catch_up']:>8.1%}{r['discount']:>6.1%}{r['attainment']:>8.1%}"
              f"{r['bu_mwd'] / 1e6:>9.2f}M{p['absorbed'] / 1e6:>9.2f}M{p['lost_margin'] / 1e6:>9.2f}M"
              f"{p['promotion'] / 1e6:>8.2f}M{p['transfer'] / 1e6:>9.2f}M{(p['chain'] + p['expedite'] + p['conversion']) / 1e6:>9.2f}M"
              f"{r['company_cost'] / 1e6:>9.2f}M{mark}")
    by = {r["id"]: r for r in s["rows"]}
    print(f"\n  BU pick: {label(by[s['bu']])} · company pick: {label(by[s['company']])} · "
          f"the BU's choice costs the company ${s['gap'] / 1e6:.2f}M in the year")
    ts = [0.0, 0.1, 0.2, 0.25, 0.3, 0.4, 0.5]
    ps = [0.0, 0.25, 0.5, 0.75, 1.0]
    g = grid(inp, P, ts, ps)
    print("\n== Where the views disagree: BU pick / company pick, gap $M (rows: tariff, columns: pass-through)")
    print("  tariff " + "".join(f"{p:>20.0%}" for p in ps))
    for t, row in zip(ts, g):
        print(f"  {t:>6.0%} " + "".join(f"{c['bu'] + '/' + c['company'] + ' ' + format(c['gap'] / 1e6, '.2f'):>20}" for c in row))


if __name__ == "__main__":
    main()
