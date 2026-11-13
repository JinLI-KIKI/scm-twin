"""
Market monitor — the 2026 market the model runs in, and what the memory price surge changes.

Two parts:

  watch         the real-world readings behind the model's inputs (data/market_watch.csv): ocean
                rates, the Strait of Hormuz, US laptop duties, memory contract prices, PC
                shipments and where notebooks are built, each with its date, source and the input
                it feeds.

  memory lens   every module run twice on the same inputs: with memory priced at the 2025 base
                and at the latest quarter of data/memory_prices.csv (Q4 2026 contract: DRAM x6.8,
                NAND x4.7). DRAM parts are MEM_*, NAND parts SSD_*. The ODM passes the memory
                dollars on at cost (customs value rises by the same amount) and channel prices
                keep their markup (mwd_engine.price_scale). The lens reports the decision each
                module recommends under both, so the page shows which decisions the memory market
                moves and which it does not.

Run:  python3 src/market.py
"""
import csv
import os

import business_case as BC
import demand_kpi as DK
import finished_goods as FG
import footprint as FP
import mwd_engine as E
import ramp_board as RB
import scenarios as SC
import transfer as TR

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")


def _csv(name):
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def watch():
    return _csv("market_watch.csv")


def memory_series():
    return [{k: (float(v) if k in ("dram_index", "nand_index") else v) for k, v in r.items()}
            for r in _csv("memory_prices.csv")]


def _bom(mats, bom, sku):
    return sum(mats[x]["unit_cost"] * q for x, q in bom[sku].items())


def lens_one(level, fg_runs=300):
    """One pass of every module with memory at the 2025 base (0) or the latest quarter (1)."""
    with E.memory_market(level):
        mats, models, locales, bom, used_by, params = E.load()
        units = {}
        for k, m in models.items():
            sku = next(s for s in bom if s.rsplit("_", 1)[0] == k)
            mem = sum(mats[x]["unit_cost"] * q for x, q in bom[sku].items() if x.startswith(("MEM_", "SSD_")))
            onb = sum(mats[x]["unit_cost"] * q for x, q in bom[sku].items() if mats[x]["on_board"])
            b = _bom(mats, bom, sku)
            units[k] = {"bom": b, "memory": mem, "memory_share": mem / b, "board": m["board_extra"] + onb,
                        "customs": m["customs_value"], "price_scale": E.price_scale(m)}
        # Module 1: factory transfer of the US region (scenario B)
        data = (mats, models, locales, bom, used_by, params)
        s = E.summarize(E.run_event(SC.SCENARIOS[1], data))
        m1 = {"freed": s["freed_usd"], "mwd": s["mwd_claimed_usd"], "holding": s["holding_usd"]}
        # Module 2: cutover week under a 25% tariff
        rows = TR.sweep("US", 0.25, 0.0, True)
        best = min(rows, key=lambda r: r["total"])
        m2 = {"best_week": best["cutover"], "best_total": best["total"], "week0": rows[0]["total"],
              "tariff_week0": rows[0]["tariff"]}
        # Module 3: transfer-year business case at 25%, strong GSM, midpoints
        p = BC.region_profile("US")
        m3 = {"net_year1": BC.deterministic(0.25), "breakeven": BC.breakeven_tariff("strong"),
              "pipeline": p["weekly_bom"] * p["lt_adder"] * p["carry"], "weekly_customs": p["weekly_customs"]}
        # Module 4: finished goods around the successor launch, sales lock
        r = FG.simulate("lock", runs=fg_runs, seed=11)["summary"]
        m4 = {"avoidable": r["avoidable_cost_usd"]["mean"]}
        # Module 5: the BU's and the company's cutover pick
        dki = DK.dk_input()
        sc = DK.score(dki, dki["P"])
        by = {x["id"]: x for x in sc["rows"]}
        m5 = {"bu": sc["bu"], "company": sc["company"], "gap": sc["gap"],
              "bu_cost": by[sc["bu"]]["bu_cost"], "company_cost": by[sc["company"]]["company_cost"]}
        # Module 6: board cover per model, strong and weak GSM
        rbi = RB.rb_input()
        m6 = {}
        for g in (1, 0):
            for b in RB.boards(rbi, dict(rbi["P"], gsm_strong=g)):
                row = next(x for x in b["rows"] if x["cover"] == b["best"])
                m6[f"{b['model']}|{g}"] = {"cover": b["best"], "expected": row["total"], "p90": row["p90"],
                                           "stranded": row["parts"]["stranded"]}
        ramp = RB.ramp_sweep(rbi, rbi["P"])
        m6["ramp_pull"] = ramp["best"]
        # Module 7: footprint
        fpi = FP.fp_input()
        fr = FP.footprints(fpi, fpi["P"], fpi["sites"], "cape")
        name = lambda x: " + ".join(x["open"]) + (" · own boards" if x["board"] else "")
        rob = min(fr, key=lambda x: x["regret"])
        m7 = {"best": name(fr[0]), "best_expected": fr[0]["expected"], "robust": name(rob),
              "robust_regret": rob["regret"]}
    return {"units": units, "m1": m1, "m2": m2, "m3": m3, "m4": m4, "m5": m5, "m6": m6, "m7": m7}


def memory_lens(fg_runs=300):
    ix = E.memory_index()
    return {"index": ix, "base": lens_one(0, fg_runs), "now": lens_one(1, fg_runs)}


def main():
    L = memory_lens()
    b, n, ix = L["base"], L["now"], L["index"]
    print(f"== Memory lens: 2025 base vs {ix['quarter']} contract (DRAM x{ix['dram']:.2f}, NAND x{ix['nand']:.2f})")
    for k in b["units"]:
        u0, u1 = b["units"][k], n["units"][k]
        print(f"  {k}: BOM ${u0['bom']:,.0f} -> ${u1['bom']:,.0f} (memory {u0['memory_share']:.0%} -> {u1['memory_share']:.0%})"
              f" · board ${u0['board']:,.0f} -> ${u1['board']:,.0f} · customs ${u0['customs']:,.0f} -> ${u1['customs']:,.0f}")
    print(f"  M1 US transfer: freed ${b['m1']['freed'] / 1e6:.2f}M -> ${n['m1']['freed'] / 1e6:.2f}M, "
          f"MWD ${b['m1']['mwd'] / 1e6:.2f}M -> ${n['m1']['mwd'] / 1e6:.2f}M")
    print(f"  M2 cutover at 25%: week {b['m2']['best_week']} (${b['m2']['best_total'] / 1e6:.2f}M) -> "
          f"week {n['m2']['best_week']} (${n['m2']['best_total'] / 1e6:.2f}M)")
    print(f"  M3 year-1 net at 25%: ${b['m3']['net_year1'] / 1e6:.2f}M -> ${n['m3']['net_year1'] / 1e6:.2f}M; "
          f"break-even tariff {b['m3']['breakeven']:.1%} -> {n['m3']['breakeven']:.1%}")
    print(f"  M4 FG avoidable cost (lock): ${b['m4']['avoidable'] / 1e6:.2f}M -> ${n['m4']['avoidable'] / 1e6:.2f}M")
    print(f"  M5 picks: BU {b['m5']['bu']} / company {b['m5']['company']} -> BU {n['m5']['bu']} / company {n['m5']['company']}")
    for k in b["m6"]:
        if k == "ramp_pull":
            print(f"  M6 ramp pull-in: {b['m6'][k]} -> {n['m6'][k]} weeks")
        else:
            print(f"  M6 {k}: cover {b['m6'][k]['cover']} -> {n['m6'][k]['cover']} weeks")
    print(f"  M7 best: {b['m7']['best']} -> {n['m7']['best']}; robust: {b['m7']['robust']} -> {n['m7']['robust']}")


if __name__ == "__main__":
    main()
