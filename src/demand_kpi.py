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
  lost      = (q0 - q) x price x gross_margin

BU pick: the latest option that still reaches target_tolerance of the shipment target, with the
lowest BU MWD among those (latest = least MWD); if none reaches it, the one closest to target.
Company pick: the lowest total cost. Where they differ, the gap is what the BU's KPIs cost the
company in the year.

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


def evaluate(inp, P, opt):
    """Fiscal-year figures for one option."""
    C = opt["cutover"]
    tariff_rate = P["tariff_cn"] * (1 - P["exporter_absorb"])
    plan = units = paid = recovered = lost = conv_units = 0.0
    weekly = [0.0] * inp["weeks"]
    for m in inp["models"]:
        tariff = tariff_rate * m["customs_value"]
        for w in range(inp["weeks"]):
            q0 = m["demand"][w]
            if q0 <= 0:
                continue
            ch = china_share(w, C, P["ramp_weeks"])
            rise = P["passthrough"] * tariff * ch if w >= P["reprice_lag_weeks"] else 0.0
            q = q0 * (1 + rise / m["price"]) ** m["elasticity"]
            plan += q0
            units += q
            weekly[w] += q
            paid += q * tariff * ch
            recovered += q * rise
            lost += (q0 - q) * m["price"] * m["gross_margin"]
            conv_units += q * (1 - ch)
    cs = inp["case"]
    moved = C is not None and C < inp["weeks"]
    frac = (inp["weeks"] - C) / inp["weeks"] if moved else 0.0
    eol = cs["eol_mwd_year"] * frac
    chain = eol + cs["pipeline_year"] * frac
    expedite = P["expedite_usd_per_unit"] * cs["weekly_units"] * cs["lt_adder"] if moved else 0.0
    conv = conv_units * cs["conv_cost"] * P["conv_uplift"]
    transfer = opt["mwd"] + opt["holding"] + opt["relocation"] + opt["rework"]
    parts = {"absorbed": paid - recovered, "lost_margin": lost, "transfer": transfer, "expedite": expedite,
             "chain": chain, "conversion": conv}
    bu_mwd = (opt["claimed_mwd"] if P["bu_mwd_claimed"] >= 0.5 else opt["mwd"]) + eol
    return {"id": opt["id"], "cutover": C, "plan": plan, "units": units, "attainment": units / plan if plan else 1.0,
            "lost_units": plan - units, "tariff_paid": paid, "recovered": recovered, "bu_mwd": bu_mwd,
            "claimed_mwd": opt["claimed_mwd"], "physical_mwd": opt["mwd"], "eol_mwd": eol,
            "parts": parts, "company_cost": sum(parts.values()), "weekly": weekly}


def score(inp, P):
    rows = [evaluate(inp, P, o) for o in inp["options"]]
    order = lambda r: inp["weeks"] + 1 if r["cutover"] is None else r["cutover"]
    hit = [r for r in rows if r["attainment"] >= P["target_tolerance"] - 1e-12]
    if hit:
        bu = min(hit, key=lambda r: (r["bu_mwd"], -order(r)))
    else:
        bu = max(rows, key=lambda r: (r["attainment"], -r["bu_mwd"]))
    co = min(rows, key=lambda r: (r["company_cost"], order(r)))
    return {"rows": rows, "bu": bu["id"], "company": co["id"], "gap": bu["company_cost"] - co["company_cost"],
            "any_hit": bool(hit)}


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
          f"{P['passthrough']:.0%} passed into the price from week {P['reprice_lag_weeks']:.0f}")
    print(f"  {'option':<8}{'units':>9}{'attain':>8}{'BU MWD':>10}{'claimed':>10}{'absorbed':>10}"
          f"{'lost mgn':>10}{'transfer':>10}{'chain+':>10}{'company':>10}")
    for r in s["rows"]:
        p = r["parts"]
        mark = (" <- BU" if r["id"] == s["bu"] else "") + (" <- company" if r["id"] == s["company"] else "")
        print(f"  {r['id']:<8}{r['units']:>9,.0f}{r['attainment']:>8.1%}{r['bu_mwd'] / 1e6:>9.2f}M"
              f"{r['claimed_mwd'] / 1e6:>9.2f}M{p['absorbed'] / 1e6:>9.2f}M{p['lost_margin'] / 1e6:>9.2f}M"
              f"{p['transfer'] / 1e6:>9.2f}M{(p['chain'] + p['expedite'] + p['conversion']) / 1e6:>9.2f}M"
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
