"""
Roadmap A4 — one fiscal year, week by week, across Modules 1-7.

A US tariff on China-made laptops starts in week 0 of the fiscal year. The year is replayed
week by week for four strategies on the same inputs:

  stay          keep building the US volume in China
  company pick  the cutover week with the lowest company cost that still makes the target
  BU pick       the cutover week with the lowest MWD + price-point cost for the BU (R43, R45)
  model change  move at the successor launch (week 26), when nothing is cancelled

What each module contributes:

  Module 5   weekly units: the plan meets the price rise (pass-through x tariff x share still
             made in China, from the repricing week) at constant elasticity; second-half
             catch-up discount up to the cap so the fiscal-year target is made (R42, R45);
             the company may end up absorbing the tariff (absorb_prob, R44): every cost is the
             expected value over the negotiated and the absorbed case
  Module 6   the new site's share of the volume after the cutover follows the S-curve ramp
             (median over the Monte Carlo, with the pull-in Module 6 recommends at this tariff
             and GSM), replacing Module 5's straight-line ramp; pull-in cost at the cutover,
             yield scrap while the site learns
  Modules 1-2  MWD, holding, relocation and rework of the cutover week (transfer.py); the
             holding, relocation and rework land at the cutover, the MWD at the year-end
             reconciliation (R8)
  Module 3   parts expediting at the cutover; the longer chain (end-of-life MWD of the longer
             commitment window, pipeline carrying) week by week after it; the new site's
             conversion uplift on every unit it builds
  Module 4   the longer factory-to-MGI transit leaves more finished goods at the old platform's
             end of life (week 30): linkage rate x extra transit weeks x units the new site ships
  Module 7   the extra transit (Indonesia against China to the US MGI, Hormuz closed) and the
             memory market lens (mwd_engine.memory_market)

The picks follow Module 5's rules (src/demand_kpi.py score) with the Module 6 ramp in place of
the straight line. Every option of Module 5 (cutover in weeks 0-16, 20, 26, 39, or none) is
replayed; the page shows the four strategies.

Run:  python3 src/year_run.py
"""
import os

import demand_kpi as DK
import footprint as FP
import mwd_engine as E
import ramp_board as RB

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEW_SITE = "ID"                       # the transfer studied in Modules 1-6: China to Indonesia
CATS = ["tariff", "lost_margin", "promotion", "transfer", "mwd", "ramp", "expedite", "chain", "conversion",
        "fg_eol"]


def inputs(region="US"):
    """Plain data for the year run (also embedded in the page for the browser engine)."""
    fpi = FP.fp_input()
    mgi = next(m["mgi"] for m in fpi["markets"] if m["market"] == region)
    lk = fpi["linkage"] or {"finished_goods": {"usd_per_unit_week": 0.0}}
    return {"dk": DK.dk_input(region), "rb": RB.rb_input(region),
            "extra": {"days_cn": FP.route(fpi, "CN", mgi, "sea", "cape", "closed")["days"],
                      "days_new": FP.route(fpi, NEW_SITE, mgi, "sea", "cape", "closed")["days"],
                      "fg_rate": lk["finished_goods"]["usd_per_unit_week"],
                      "fg_week": E.load()[1]["P1-14"]["eol"]}}       # platform P1's collective end of life


def context(inp, tariff, gsm_strong=1, P5=None, P6=None):
    """Inputs shared by every option at one tariff and GSM. P5 / P6 override Module 5 / 6 inputs."""
    dki, rbi, ex = inp["dk"], inp["rb"], inp["extra"]
    P = dict(P5 or dki["P"], tariff_cn=tariff)
    P6 = dict(P6 or rbi["P"], gsm_strong=gsm_strong, ramp_tariff=tariff)
    rs = RB.ramp_sweep(rbi, P6)
    best = next(r for r in rs["rows"] if r["pull"] == rs["best"])
    rg = rbi["region"]
    scrap = []
    for w in range(rbi["ramp_weeks"]):
        y = RB.yield_at(P6, w)
        scrap.append((1 / y - 1) * rg["bom"] * P6["scrap_share_of_bom"])   # per unit built at the new site
    return {"dk": dki, "P": P, "band": best["band"], "pull": rs["best"], "pull_cost": best["pull_cost"],
            "T50": best["T_p50"], "T90": best["T_p90"], "scrap": scrap, "gsm_strong": gsm_strong,
            "expedite_unit": P["expedite_usd_per_unit"] * (1 if gsm_strong >= 0.5 else P["expedite_weak_mult"]),
            "extra_transit_weeks": (ex["days_new"] - ex["days_cn"]) / 7, "days_cn": ex["days_cn"],
            "days_new": ex["days_new"], "fg_rate": ex["fg_rate"], "fg_week": int(ex["fg_week"]), "tariff": tariff}


def china_share(ctx, w, c):
    """Share of week w's US units still built in China when the cutover is in week c."""
    if c is None or w < c:
        return 1.0
    k = w - c
    band = ctx["band"]
    return 1.0 - (band[k][1] if k < len(band) else 1.0)


def replay(ctx, opt, passthrough):
    """One case (negotiated or absorbed): weekly units and costs for one option."""
    dki, P = ctx["dk"], dict(ctx["P"], passthrough=passthrough)
    W, C = dki["weeks"], opt["cutover"]
    rate = P["tariff_cn"] * (1 - P["exporter_absorb"])
    ch = [china_share(ctx, w, C) for w in range(W)]
    base, plan = [], [0.0] * W
    for m in dki["models"]:
        tariff = rate * m["customs_value"]
        row = []
        for w in range(W):
            q0 = m["demand"][w]
            plan[w] += q0
            rise = P["passthrough"] * tariff * ch[w] if w >= P["reprice_lag_weeks"] else 0.0
            row.append(q0 * (1 + rise / m["price"]) ** m["elasticity"] if q0 > 0 else 0.0)
        base.append(row)
    total_plan = sum(plan)
    disc = DK.catch_up(dki, P, base, P["target_tolerance"] * total_plan - sum(map(sum, base)))
    cw = int(P["catchup_from_week"])
    cost = {k: [0.0] * W for k in CATS}
    units, cn_units, rise_avg = [0.0] * W, [0.0] * W, [0.0] * W
    for i, m in enumerate(dki["models"]):
        tariff = rate * m["customs_value"]
        lift = (1 - P["points_effect"] * disc) ** m["elasticity"] if disc > 0 else 1.0
        for w in range(W):
            q0 = m["demand"][w]
            if q0 <= 0:
                continue
            rise = P["passthrough"] * tariff * ch[w] if w >= P["reprice_lag_weeks"] else 0.0
            q = base[i][w] * (lift if w >= cw else 1.0)
            units[w] += q
            cn_units[w] += q * ch[w]
            rise_avg[w] += q * rise
            cost["tariff"][w] += q * (tariff * ch[w] - rise)
            cost["lost_margin"][w] += (q0 - q) * m["price"] * m["gross_margin"]
            if w >= cw:
                cost["promotion"][w] += q * disc * m["price"]
    cs = dki["case"]
    moved = C is not None and C < W
    new_units = [u - c for u, c in zip(units, cn_units)]
    if moved:
        cost["transfer"][C] += opt["holding"] + opt["relocation"] + opt["rework"]
        cost["mwd"][W - 1] += opt["mwd"]                      # settled at the year-end reconciliation (R8)
        cost["ramp"][C] += ctx["pull_cost"]
        cost["expedite"][C] += ctx["expedite_unit"] * cs["weekly_units"] * cs["lt_adder"]
        for w in range(C, W):
            cost["chain"][w] += (cs["eol_mwd_year"] + cs["pipeline_year"]) / W
            cost["conversion"][w] += new_units[w] * cs["conv_cost"] * P["conv_uplift"] * DK.uplift_left(P, w, C)
            k = w - C
            if k < len(ctx["scrap"]):
                cost["ramp"][w] += new_units[w] * ctx["scrap"][k]
        fw = ctx["fg_week"]
        if C < fw:
            shipped = sum(new_units[C:fw])
            cost["fg_eol"][fw] += ctx["fg_rate"] * max(0.0, ctx["extra_transit_weeks"]) * shipped
    quarters = [[sum(plan[q * 13:(q + 1) * 13]), sum(units[q * 13:(q + 1) * 13])] for q in range(4)]
    frac = (W - C) / W if moved else 0.0
    eol = cs["eol_mwd_year"] * frac
    promo = sum(cost["promotion"])
    bu_std, bu_custom = DK.bu_mwd_parts(opt, P, eol) if moved else (0.0, 0.0)
    bu_mwd = bu_std + bu_custom
    return {"units": units, "cn_units": cn_units, "plan": plan, "cost": cost, "discount": disc,
            "rise": [r / u if u else 0.0 for r, u in zip(rise_avg, units)], "quarters": quarters,
            "attainment": sum(units) / total_plan, "bu_cost": P["mwd_cost_rate_std"] * bu_std + P["mwd_cost_rate"] * bu_custom + P["bu_funds_support"] * promo,
            "bu_mwd": bu_mwd, "share_cn": ch}


def run_option(ctx, opt):
    """Expected weekly costs over the negotiated and the absorbed case (R44)."""
    P = ctx["P"]
    neg = replay(ctx, opt, P["passthrough"])
    p = P["absorb_prob"]
    if p > 0:
        ab = replay(ctx, opt, 0.0)
        cost = {k: [(1 - p) * a + p * b for a, b in zip(neg["cost"][k], ab["cost"][k])] for k in CATS}
        bu_cost = (1 - p) * neg["bu_cost"] + p * ab["bu_cost"]
        att = min(neg["attainment"], ab["attainment"])
    else:
        cost, bu_cost, att = neg["cost"], neg["bu_cost"], neg["attainment"]
    weekly = [sum(cost[k][w] for k in CATS) for w in range(len(neg["units"]))]
    cum, acc = [], 0.0
    for x in weekly:
        acc += x
        cum.append(acc)
    return {"id": opt["id"], "cutover": opt["cutover"], "units": neg["units"], "cn_units": neg["cn_units"],
            "plan": neg["plan"], "rise": neg["rise"], "share_cn": neg["share_cn"], "quarters": neg["quarters"],
            "discount": neg["discount"], "cost": cost, "totals": {k: sum(cost[k]) for k in CATS},
            "company_cost": acc, "cumulative": cum, "bu_cost": bu_cost, "attainment": att,
            "bu_mwd": neg["bu_mwd"], "claimed_mwd": opt["claimed_mwd"]}


def run_year(tariff=0.25, gsm_strong=1, inp=None, P5=None, P6=None):
    ctx = context(inp or inputs(), tariff, gsm_strong, P5, P6)
    P, dki = ctx["P"], ctx["dk"]
    rows = [run_option(ctx, o) for o in dki["options"]]
    order = lambda r: dki["weeks"] + 1 if r["cutover"] is None else r["cutover"]
    hit = [r for r in rows if r["attainment"] >= P["target_tolerance"] - 1e-9]
    bu = min(hit, key=lambda r: (r["bu_cost"], -order(r))) if hit else max(rows, key=lambda r: r["attainment"])
    pool = hit if (hit and P["company_holds_target"] >= 0.5) else rows
    co = min(pool, key=lambda r: (r["company_cost"], order(r)))
    by = {r["id"]: r for r in rows}
    strategies = [("stay", "Stay in China", by["stay"]), ("company", "Company's pick", co),
                  ("bu", "BU's pick", bu), ("model_change", "Move at the model change", by["C26"])]
    return {"tariff": tariff, "gsm_strong": gsm_strong, "pull": ctx["pull"], "T50": ctx["T50"], "T90": ctx["T90"],
            "extra_transit_days": ctx["days_new"] - ctx["days_cn"], "target": P["target_tolerance"],
            "reprice_lag": P["reprice_lag_weeks"], "catchup_from": P["catchup_from_week"],
            "strategies": [{"key": k, "label": l, **s} for k, l, s in strategies],
            "options": [{"id": r["id"], "cutover": r["cutover"], "company_cost": r["company_cost"],
                         "bu_cost": r["bu_cost"], "attainment": r["attainment"]} for r in rows],
            "events": events(ctx, co, bu)}


def events(ctx, co, bu):
    P = ctx["P"]
    ev = [[0, f"US tariff of {ctx['tariff']:.0%} on China-made laptops starts"],
          [int(P["reprice_lag_weeks"]), "The new channel price is in place (pass-through negotiated)"]]
    for r, who in ((co, "company"), (bu, "BU")):
        if r["cutover"] is not None:
            ev.append([r["cutover"], f"Cutover, the {who}'s pick: plans inside the 16-week window are cancelled; "
                                     f"the new site's first build"])
            ev.append([min(51, r["cutover"] + round(ctx["T50"])), f"New site at full volume (median, {who}'s pick)"])
    ev += [[26, "Successor P2-14 launches; second-half catch-up discount runs from here"],
           [ctx["fg_week"], "Platform P1 end of life: finished goods left in the pipeline"],
           [51, "Fiscal year-end: shipments against the target; MWD reconciled"]]
    return sorted(ev, key=lambda e: e[0])


def grid(tariffs=(0.10, 0.25, 0.40), gsms=(1, 0), memories=(0, 1)):
    out = {}
    for mem in memories:
        with E.memory_market(mem):
            inp = inputs()
            for t in tariffs:
                for g in gsms:
                    out[f"{t:.2f}|{g}|{mem}"] = run_year(t, g, inp)
    return out


def main():
    y = run_year()
    print(f"== Year run, US region, tariff {y['tariff']:.0%}, {'strong' if y['gsm_strong'] else 'weak'} GSM; "
          f"Module 6 ramp: pull in {y['pull']} weeks, median {y['T50']:.1f}, P90 {y['T90']:.1f} weeks; "
          f"extra transit {y['extra_transit_days']:.1f} days")
    for s in y["strategies"]:
        tot = s["totals"]
        print(f"  {s['label']:<26} cutover {str(s['cutover']):>4} · company ${s['company_cost'] / 1e6:6.2f}M · "
              f"BU ${s['bu_cost'] / 1e6:5.2f}M · attainment {s['attainment']:.1%} · "
              + " · ".join(f"{k} {v / 1e6:.2f}" for k, v in tot.items() if abs(v) > 1))
        print("      quarters: " + "  ".join(f"Q{i + 1} {q[1] / q[0]:.1%}" for i, q in enumerate(s["quarters"]) if q[0]))
    for w, e in y["events"]:
        print(f"  W{w:<3} {e}")


if __name__ == "__main__":
    main()
