"""
Roadmap A4 (first step) — link Module 7 (footprint) to Modules 1-4.

Module 7 prices a footprint per unit and per year. Three of its costs come from the other
modules instead of being typed in:

  chain (Module 3)        a non-China site needs parts committed earlier, so the end-of-life
                          material without demand grows: dollars per unit sold for each extra
                          week of commitment window (business_case: EOL MWD for +lt_adder weeks)
  finished goods (Mod. 4) a longer factory-to-MGI chain leaves more stock in the pipeline when
                          the successor launches: dollars per unit sold for each extra week of
                          transit, from the finished-goods simulation with the launch held fixed
  transition (Mod. 1-2)   moving a market's volume out of China in a hurry (a tariff has arrived)
                          means cutting over at once: holding, relocation and MWD of the cutover
                          (transfer.py, best week at a positive tariff) plus rush expediting while
                          the new site's lead time is not yet covered (Module 3), per unit of
                          weekly volume moved. A move planned at a model change costs nothing extra
                          (the cutover then falls at the end of the liability window).

Writes data/linkage.json, read by src/footprint.py and shown on the report pages.

Run:  python3 src/integrate.py
"""
import json
import os

import business_case as BC
import finished_goods as FG
import transfer as TR

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "linkage.json")


def chain_cost():
    """Module 3: extra EOL MWD per unit sold per week of longer commitment window."""
    p, c = BC.region_profile("US"), BC.CASE
    mid = lambda r: (r[0] + r[1]) / 2
    s_old, s_new = BC._sigma(c["fa_base"]), BC._sigma(c["fa_new"])
    rho = mid(c["rho"])
    eol = (BC._overcommit_weeks(s_new, c["window_new"], rho) - BC._overcommit_weeks(s_old, c["window_old"], rho)) \
        * p["weekly_locked"] * c["eol_events_per_year"]
    units = p["weekly_units"] * 52
    return {"usd_per_unit_week": eol / units / p["lt_adder"], "eol_mwd_per_year": eol, "units_per_year": units,
            "extra_weeks": p["lt_adder"], "window_old": c["window_old"], "window_new": c["window_new"]}


def finished_goods_cost(weeks=(5, 6, 7, 8, 9), runs=300):
    """Module 4: avoidable end-of-life cost per unit for each extra week of transit, launch fixed."""
    base = int(FG.load_fg()[0]["build_to_mgi_weeks"])
    pts = []
    for T in weeks:
        r = FG.simulate("lock", overrides={"build_to_mgi_weeks": T, "launch_lag_weeks": base}, runs=runs, seed=11)
        sm = r["summary"]
        pts.append([T, sm["avoidable_cost_usd"]["mean"] / sm["demand_units"]["mean"]])
    mx = sum(x for x, _ in pts) / len(pts)
    my = sum(y for _, y in pts) / len(pts)
    slope = sum((x - mx) * (y - my) for x, y in pts) / sum((x - mx) ** 2 for x, _ in pts)
    return {"usd_per_unit_week": slope, "points": pts, "strategy": "lock", "runs": runs}


def transition_cost():
    """Modules 1-2 (+3): one-time cost per unit of weekly volume moved out of China in a hurry."""
    wk = BC.region_profile("US")["weekly_units"]
    rows = TR.sweep("US", 0.25, 0.0, True)
    best = min(rows, key=lambda r: r["total"])
    calm = min(TR.sweep("US", 0.0, 0.0, True), key=lambda r: r["total"])
    expedite = BC.region_profile("US")["lt_adder"] * BC.CASE["expedite_cost_per_unit"]["strong"]
    return {"urgent_usd_per_weekly_unit": best["total"] / wk + expedite,
            "cutover_usd_per_weekly_unit": best["total"] / wk, "expedite_usd_per_weekly_unit": expedite,
            "urgent_best_week": best["cutover"], "planned_usd_per_weekly_unit": calm["total"] / wk,
            "planned_best_week": calm["cutover"], "weekly_units": wk,
            "parts": {k: best[k] for k in ("holding", "relocation", "rework", "mwd")}}


def build():
    out = {"chain": chain_cost(), "finished_goods": finished_goods_cost(), "transition": transition_cost()}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    return out


if __name__ == "__main__":
    o = build()
    print(f"Module 3 chain:          ${o['chain']['usd_per_unit_week']:.2f} per unit per extra week of commitment window")
    print(f"Module 4 finished goods: ${o['finished_goods']['usd_per_unit_week']:.2f} per unit per extra week of transit "
          f"(points {[(t, round(v, 2)) for t, v in o['finished_goods']['points']]})")
    t = o["transition"]
    print(f"Modules 1-2 transition:  ${t['urgent_usd_per_weekly_unit']:.0f} per unit of weekly volume moved in a hurry "
          f"(cutover week {t['urgent_best_week']}: ${t['cutover_usd_per_weekly_unit']:.0f} + expediting ${t['expedite_usd_per_weekly_unit']:.0f}); "
          f"planned at a model change ${t['planned_usd_per_weekly_unit']:.0f}")
