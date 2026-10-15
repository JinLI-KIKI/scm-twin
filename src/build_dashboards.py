"""
Build the linked report pages in docs/ from the model modules.

  docs/index.html            Overview: headline numbers, how the modules connect, roadmap
  docs/atlas.html            Network atlas (built by src/build_map.py, same top navigation)
  docs/lanes.html            Lanes & lead time: door-to-MGI days by step, duty vs lead time
  docs/mwd.html              Module 1: MWD by scenario and material
  docs/transfer.html         Module 2: cutover week sweep, tariff vs MWD
  docs/business-case.html    Module 3: Monte Carlo, waterfall, tornado, break-even curve
  docs/finished-goods.html   Module 4: sales volume lock, price protection, excess disposition
  docs/fg-live.html          Module 4 simulator: every input as a slider or a range, re-run live
  docs/footprint.html        Module 7: six sites, nine markets, real duties, footprints live
  docs/rules.html            Rules register, numbers and question log from ASSUMPTIONS.md

Each page is one self-contained HTML file: data embedded as JSON, charts drawn with
ECharts from cdnjs. Scenario grids are precomputed here, so slicers on most pages only
filter (as in a BI report). The two studio pages (fg-live, footprint) embed a JavaScript
port of their model and recompute in the browser; tests/ check the ports match Python.

Run:  python3 src/build_dashboards.py            (about two minutes; Module 4 grid dominates)
      PREVIEW_DIR=/some/dir python3 src/build_dashboards.py   also writes the overview as a
      fragment for a hosted preview
"""
import csv
import datetime
import html
import json
import os
import re
from multiprocessing import Pool

import business_case as BC
import finished_goods as FG
import footprint as FP
import mwd_engine as E
import scenarios as SC
import site_chrome as S
import transfer as TR

ROOT = S.ROOT
DATA = os.path.join(ROOT, "data")
DOCS = os.path.join(ROOT, "docs")
TODAY = datetime.date.today().isoformat()


def rnd(x, n=0):
    if x is None:
        return None
    return round(x, n) if n else int(round(x))


def read_csv(name):
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ----------------------------------------------------------------------------- Module 1
SC_TEXT = {
    "A_temporary_cut_BR": ("A", "Temporary cut · Brazil",
                           "Brazil plans for P1-14 cancelled for the whole 16-week window; Brazil demand returns later."),
    "B_transfer_US_eol30": ("B", "US transfer · EOL week 30",
                            "US production leaves the China factory now; platform P1 reaches EOL at week 30."),
    "C0_eol20_old_rule": ("C0", "EOL week 20 · old netting rule",
                          "Same as C, but freed stock only offsets demand beyond the purchase lead time (the v0 assumption)."),
    "C_transfer_US_eol20": ("C", "US transfer · EOL week 20",
                            "P1 EOL pulled in to week 20 and P2 NPI at week 16: less future demand to absorb the freed stock."),
    "D_transfer_US_eol8": ("D", "US transfer · EOL week 8",
                           "US leaves only 8 weeks before P1 EOL (P2 NPI at week 4): almost nothing left to absorb it."),
}


def data_mwd():
    data = E.load()
    names = {r["material_id"]: r["name"] for r in read_csv("materials.csv")}
    out = []
    for sc in SC.SCENARIOS:
        rows = E.run_event(sc, data)
        s = E.summarize(rows)
        code, label, desc = SC_TEXT[sc["name"]]
        out.append({
            "id": sc["name"], "code": code, "label": label, "desc": desc,
            "summary": {k: rnd(v) for k, v in s.items()},
            "rows": [{"material": r["material"], "name": names.get(r["material"], r["material"]),
                      "cls": r["route_class"], "std": r["industry_standard"],
                      "start": r["netting_start_week"], "done": r["absorb_done_week"],
                      "freed_qty": rnd(r["freed_qty"]), "absorbed_qty": rnd(r["absorbed_qty"]),
                      "reworked_qty": rnd(r["reworked_qty"]), "mwd_qty": rnd(r["mwd_qty"]),
                      "freed_usd": rnd(r["freed_usd"]), "holding_usd": rnd(r["holding_usd"]),
                      "ageing_usd": rnd(r["ageing_usd"]), "rework_usd": rnd(r["rework_usd"]),
                      "mwd_usd": rnd(r["mwd_claimed_usd"])} for r in rows],
        })
    params = data[5]
    return {"scenarios": out, "window": int(params["liability_window_weeks"]),
            "tracking": int(params["tracking_window_weeks"])}


# ----------------------------------------------------------------------------- Module 2
TR_TARIFFS = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.35, 0.50]


def data_transfer():
    sweeps, chain = {}, {}
    for t in TR_TARIFFS:
        for reloc in (True, False):
            rows = TR.sweep("US", t, 0.0, reloc)
            sweeps[f"{t:.2f}|{int(reloc)}"] = [
                {k: rnd(v) for k, v in r.items()} for r in rows]
        c = TR.chain_extension_cost("US", t)
        chain[f"{t:.2f}"] = {k: rnd(v) for k, v in c.items()}
    params = E.load()[5]
    return {"tariffs": TR_TARIFFS, "sweeps": sweeps, "chain": chain,
            "window": int(params["liability_window_weeks"]),
            "boards_ahead": int(params["boards_built_ahead_weeks"]),
            "relocation_weeks": int(params["relocation_weeks"]),
            "relocation_rate": params["relocation_cost_rate"],
            "lt_adder": int(params["new_site_lt_adder_weeks"])}


# ----------------------------------------------------------------------------- Module 3
BC_GRID = [i / 100 for i in range(0, 31)]
BC_KEYS = ["tariff_saved", "eol_mwd", "pipeline", "conv", "ramp_leak", "expedite",
           "net_steady", "net_year1"]


def _bc_cell(args):
    t, g = args
    sims = BC.simulate(t, gsm=g, n=2000)
    col = lambda k: sorted(s[k] for s in sims)
    q = lambda v, p: v[int(p * (len(v) - 1))]
    cell = {}
    for k in BC_KEYS:
        v = col(k)
        cell[k] = [rnd(q(v, .1)), rnd(q(v, .5)), rnd(q(v, .9))]
    net = col("net_year1")
    cell["p_pos"] = round(sum(1 for x in net if x > 0) / len(net), 3)
    lo, hi = net[0], net[-1]
    bins = 24
    width = (hi - lo) / bins if hi > lo else 1.0
    counts = [0] * bins
    for x in net:
        counts[min(bins - 1, int((x - lo) / width))] += 1
    cell["hist"] = {"lo": rnd(lo), "w": rnd(width), "n": counts}
    base, rows = BC.tornado(t, g)
    cell["tornado"] = {"base": rnd(base), "rows": [
        {"d": r["driver"], "lo": rnd(r["net_at_low"]), "hi": rnd(r["net_at_high"])} for r in rows]}
    return f"{t:.2f}|{g}", cell


def data_business(pool):
    cells = dict(pool.map(_bc_cell, [(t, g) for g in ("strong", "weak") for t in BC_GRID]))
    prof = BC.region_profile()
    c = BC.CASE
    return {"grid": BC_GRID, "cells": cells,
            "breakeven": {g: round(BC.breakeven_tariff(g), 4) for g in ("strong", "weak")},
            "profile": {k: rnd(v, 2) for k, v in prof.items()},
            "case": {"fa_base": c["fa_base"], "fa_new": c["fa_new"], "window_old": c["window_old"],
                     "window_new": c["window_new"], "conv_uplift": c["conv_uplift"],
                     "ramp_weeks": c["ramp_weeks"], "expedite": c["expedite_cost_per_unit"],
                     "rho": c["rho"], "conv_cost": c["conv_cost_per_unit"]}}


# ----------------------------------------------------------------------------- Module 4
FG_DROPS = [0.10, 0.15, 0.20]
FG_BIAS = [0.0, 0.08, 0.15]
FG_CUSTOMS = {
    "base": {},
    "us25_post": {"duty_override": {"US": 0.25}},
    "us25_ftz": {"duty_override": {"US": 0.25}, "ftz": True},
}
FG_SUMMARY = ["demand_units", "sold_units", "builds_units", "kits_ordered", "sell_in_pre_launch_units",
              "channel_at_launch_units", "excess_units", "returned_units", "lost_units", "mwd_kits",
              "price_protection_usd", "launch_markdown_usd", "markdown_floor_usd",
              "markdown_above_floor_usd", "excess_loss_usd", "mwd_usd", "lost_margin_usd",
              "duty_sunk_usd", "avoidable_cost_usd", "dealer_kept_units", "dealer_loss_usd",
              "system_cost_usd"] + ["mix_" + p for p in FG.PATHS]
FG_REGION = ["excess_units", "lost_units", "price_protection_usd", "excess_loss_usd", "mwd_usd",
             "lost_margin_usd", "duty_sunk_usd", "avoidable_cost_usd", "demand_units",
             "dealer_kept_units", "dealer_loss_usd", "system_cost_usd"]
FG_TRAJ = ["demand", "forecast", "sold", "lost", "builds", "sell_in", "mgi", "channel", "kits"]


FG_LOCKSTYLE = {"low": -0.10, "even": 0.0, "high": 0.10}
FG_CURVE = [round(-0.25 + 0.05 * i, 2) for i in range(11)]


def _fg_cell(args):
    s, d, b, ck, ls = args
    res = FG.simulate(s, overrides={"launch_drop_pct": d, "sales_bias": b,
                                    "lock_bias": FG_LOCKSTYLE[ls]}, runs=200, **FG_CUSTOMS[ck])
    cell = {
        "s": {k: [rnd(v["mean"]), rnd(v["p10"]), rnd(v["p90"])] for k, v in res["summary"].items()
              if k in FG_SUMMARY},
        "r": {r: {k: rnd(v.get(k, 0)) for k in FG_REGION} for r, v in res["by_region"].items()},
    }
    meta = {k: res[k] for k in ("launch_week", "eol_week", "lock_week", "horizon",
                                "liability_weeks", "landed_cost", "kit_mwd_value")}
    # flows do not depend on the price drop or customs status: keep one trajectory per
    # strategy, sales optimism and lock style
    traj = ({k: [rnd(x) for x in res["traj"][k]] for k in FG_TRAJ}
            if abs(d - 0.15) < 1e-9 and ck == "base" else None)
    return f"{s}|{d:.2f}|{b:.2f}|{ck}|{ls}", cell, meta, (f"{s}|{b:.2f}|{ls}", traj)


def _fg_curve(args):
    s, lb = args
    res = FG.simulate(s, overrides={"lock_bias": lb, "lock_bias_sd": 0.0}, runs=300)
    sm = res["summary"]
    return s, lb, {k: rnd(sm[k]["mean"]) for k in ("avoidable_cost_usd", "system_cost_usd",
                                                  "excess_units", "lost_units", "mwd_usd")}


def data_fg(pool):
    args = [(s, d, b, ck, ls) for s in FG.STRATEGIES for d in FG_DROPS for b in FG_BIAS
            for ck in FG_CUSTOMS for ls in FG_LOCKSTYLE]
    cells, meta, trajs = {}, None, {}
    for key, cell, m, (tkey, traj) in pool.map(_fg_cell, args):
        cells[key] = cell
        meta = m
        if traj is not None:
            trajs[tkey] = traj
    curve = {}
    for s, lb, v in pool.map(_fg_curve, [(s, lb) for s in FG.STRATEGIES for lb in
                                          (FG_CURVE if FG.STRATEGIES[s]["lock"] else [0.0])]):
        curve.setdefault(s, {})[f"{lb:.2f}"] = v
    P, models, arche, _ = FG.load_fg()
    return {"strategies": {k: v["label"] for k, v in FG.STRATEGIES.items()},
            "drops": FG_DROPS, "biases": FG_BIAS, "customs": list(FG_CUSTOMS),
            "lockstyles": FG_LOCKSTYLE, "curve": curve, "curve_x": FG_CURVE,
            "lock_bias_sd": P["lock_bias_sd"], "cells": cells, "traj": trajs, "meta": meta,
            "archetypes": [{**r, "nets": {k: rnd(v) for k, v in r["nets"].items()}}
                           for r in FG.archetype_table()],
            "models": [{"model": m, **{k: v for k, v in r.items() if k != "model"}}
                       for m, r in models.items()],
            "params": read_csv("fg_params.csv")}


# ----------------------------------------------------------------------------- lanes
def data_lanes():
    with open(os.path.join(DATA, "network.json"), encoding="utf-8") as f:
        net = json.load(f)
    origins = list(net["origins"])
    weekly = {r["mgi"]: float(r["weekly_units"]) for r in read_csv("markets.csv")}
    tot = sum(weekly.values()) or 1.0
    mgis = {}
    for m, v in net["mgis"].items():
        n = net["nodes"][m]
        t = net["tariffs"][v["tkey"]]
        mgis[m] = {"code": n["code"], "name": n["name"], "tkey": v["tkey"], "country": t["country"],
                   "duty": {o: float(t[f"duty_{o.lower()}_origin_pct"]) for o in origins},
                   "barrier": t.get("other_barrier") or "", "note": t.get("note") or "",
                   "share": round(weekly.get(m, 0) / tot, 4), "port": net["nodes"][v["port"]]["name"],
                   "airport": net["nodes"][v["airport"]]["code"]}
    routes = [{k: r[k] for k in ("origin", "mgi", "mode", "variant", "km", "nm", "steps", "days", "passages", "domestic")
               if k in r} for r in net["routes"]]
    feeds = {o: [{k: f[k] for k in ("name", "steps", "days", "passages") if k in f} for f in fs]
             for o, fs in net["feeds"].items()}
    return {"mgis": mgis, "routes": routes, "feeds": feeds,
            "origins": {k: v["label"] for k, v in net["origins"].items()},
            "params": read_csv("leadtime_params.csv")}


# ----------------------------------------------------------------------------- rules
LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")


def md_inline(s):
    out, last = [], 0
    for m in LINK.finditer(s):
        out.append(html.escape(s[last:m.start()]))
        out.append(f'<a href="{html.escape(m.group(2))}">{html.escape(m.group(1))}</a>')
        last = m.end()
    out.append(html.escape(s[last:]))
    t = "".join(out)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    return t


def status_kind(s):
    u = s.upper()
    for k in ("OPEN", "QUEUED", "PARKED"):
        if u.startswith(k):
            return "open"
    for k, v in (("PRACTITIONER", "prac"), ("WEB", "web"), ("PLACEHOLDER", "ph"), ("ILLUSTRATIVE", "ill")):
        if u.startswith(k):
            return v
    if "OPEN" in u:
        return "open"
    return "design"


def data_rules():
    with open(os.path.join(DOCS, "ASSUMPTIONS.md"), encoding="utf-8") as f:
        lines = f.read().splitlines()
    section, tables = None, []
    for ln in lines:
        if ln.startswith("## "):
            section = ln[3:].strip()
            continue
        if not ln.startswith("|") or ln.startswith("|---") or section is None:
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if cells[0] in ("ID", "Item", "Parameter", "#"):
            continue
        tables.append({"section": section, "cells": cells})
    rules, numbers, questions = [], [], []
    for t in tables:
        c = t["cells"]
        if t["section"] == "Question log":
            ans = c[2] if len(c) > 2 else ""
            kind = "open" if ans.upper().startswith(("OPEN", "QUEUED", "PARKED")) else "answered"
            questions.append({"id": c[0], "q": md_inline(c[1]), "a": md_inline(ans), "kind": kind})
        elif re.match(r"^R\d+$", c[0]):
            rules.append({"id": c[0], "text": md_inline(c[1]), "status": md_inline(c[2]),
                          "kind": status_kind(c[2]), "section": t["section"]})
        else:
            numbers.append({"item": md_inline(c[0]), "value": md_inline(c[1]),
                            "status": md_inline(c[2] if len(c) > 2 else ""),
                            "kind": status_kind(c[2] if len(c) > 2 else ""), "section": t["section"]})
    rules.sort(key=lambda r: int(r["id"][1:]))
    return {"rules": rules, "numbers": numbers, "questions": questions}


# ----------------------------------------------------------------------------- overview
ROADMAP = [
    ("Modules 1–4 + atlas", "MWD, transfer timing, business case, finished goods, network map", "done"),
    ("Module 7 · Footprint", "Six sites, nine markets, real duties, origin by main board, build now or wait", "done"),
    ("A · Core loop", "A2 demand & KPI · A3 ramp & risk board · A4 integrated run", "active"),
    ("B · Breadth", "AI servers, rail and sea-air (more origins and markets done)", "next"),
    ("C · Decision engine", "Inventory policy, forecast module (footprint optimiser done)", "next"),
    ("D · Risk and cost", "Disruption Monte Carlo, carbon per lane (landed cost done)", "next"),
    ("E · Calibration", "Replace placeholders, scheduled data refresh", "next"),
    ("F · Product", "Two live studios done · BI exports, CI", "active"),
    ("G · Packaging", "Case studies, methodology note", "next"),
]


def data_fp_summary():
    inp = FP.fp_input()
    rows = FP.footprints(inp, inp["P"], inp["sites"], "cape")
    name = lambda r: " + ".join(r["open"]) + (" · own boards" if r["board"] else "")
    rob = min(rows, key=lambda r: r["regret"])
    hedge = min((r for r in rows if not r["is_base"] and FP.tipping_weight(r, inp["scenarios"], "cn301", inp["P"]["horizon_years"])),
                key=lambda r: FP.tipping_weight(r, inp["scenarios"], "cn301", inp["P"]["horizon_years"]))
    return {"best": name(rows[0]), "best_expected": rows[0]["expected"], "robust": name(rob),
            "robust_regret": rob["regret"], "hedge": name(hedge),
            "hedge_weight": FP.tipping_weight(hedge, inp["scenarios"], "cn301", inp["P"]["horizon_years"]),
            "n": len(rows)}


def data_overview(mwd, tr, bc, fg, lanes, rules, fp):
    sc = {s["code"]: s["summary"] for s in mwd["scenarios"]}
    route = lambda o, m, v="any": next(r for r in lanes["routes"] if r["origin"] == o and r["mgi"] == m
                                       and r["mode"] == "sea" and r["variant"] in (v, "any"))
    best25 = min(tr["sweeps"]["0.25|1"], key=lambda r: r["total"])
    now25 = tr["sweeps"]["0.25|1"][0]
    fgk = lambda s: fg["cells"][f"{s}|0.15|0.08|base|even"]["s"]
    counts = {}
    for r in rules["rules"] + rules["numbers"]:
        counts[r["kind"]] = counts.get(r["kind"], 0) + 1
    rank = lambda q: (0 if re.sub("<[^>]+>", "", q["a"]).upper().startswith("OPEN") else
                      1 if re.sub("<[^>]+>", "", q["a"]).upper().startswith("QUEUED") else 2,
                      -int(re.sub(r"\D", "", q["id"]) or 0))
    open_q = sorted([q for q in rules["questions"] if q["kind"] == "open"], key=rank)
    return {
        "mwd": {k: {"total": v["total_cost_usd"], "mwd": v["mwd_claimed_usd"]} for k, v in sc.items()},
        "transfer": {"best_week": best25["cutover"], "best_total": best25["total"],
                     "now_total": now25["total"]},
        "breakeven": bc["breakeven"],
        "lead": {"cn_us": route("CN", "M_US")["days"], "id_us": route("ID", "M_US")["days"],
                 "cn_eu_cape": route("CN", "M_EU", "cape")["days"],
                 "cn_eu_suez": route("CN", "M_EU", "suez")["days"]},
        "fg": {s: {"avoidable": fgk(s)["avoidable_cost_usd"][0], "protection": fgk(s)["price_protection_usd"][0],
                   "excess": fgk(s)["excess_units"][0], "lost": fgk(s)["lost_units"][0],
                   "mwd": fgk(s)["mwd_usd"][0]} for s in fg["strategies"]},
        "fp": fp,
        "status_counts": counts, "open_questions": open_q[:3],
        "roadmap": [{"name": a, "scope": b, "state": c} for a, b, c in ROADMAP],
    }


# ----------------------------------------------------------------------------- render
def render(page_file, key, title_tag, data, extra_head=""):
    tpl = S.read(f"page_{key}.html")
    body = (tpl.replace("<!--__HEAD__-->", S.read("head.html") + extra_head)
            .replace("/*__CSS__*/", S.read("report.css") + "\n" + S.read("chrome.css"))
            .replace("<!--__NAV__-->", S.nav_html(key))
            .replace("/*__JS__*/", S.read("report.js"))
            .replace("/*__SIMCSS__*/", S.read("sim.css"))
            .replace("/*__ENGINE__*/", S.read("fg_engine.js"))
            .replace("/*__FPENGINE__*/", S.read("fp_engine.js"))
            .replace("/*__DATA__*/null", json.dumps(data, separators=(",", ":"), ensure_ascii=False)
                     .replace("</", "<\\/"))
            .replace("__TODAY__", TODAY))
    with open(os.path.join(DOCS, page_file), "w", encoding="utf-8") as f:
        f.write(S.document(body))
    prev = os.environ.get("PREVIEW_DIR")
    if prev:
        os.makedirs(prev, exist_ok=True)
        if page_file == "index.html":
            with open(os.path.join(prev, "overview_fragment.html"), "w", encoding="utf-8") as f:
                f.write(body)
    return len(body)


def main():
    cache = os.environ.get("DASH_CACHE")          # optional: reuse the slow grids while editing pages
    if cache and os.path.exists(cache):
        with open(cache, encoding="utf-8") as f:
            fg, bc = json.load(f)
    else:
        with Pool() as pool:
            print("Module 4 grid ...")
            fg = data_fg(pool)
            print("Module 3 grid ...")
            bc = data_business(pool)
        if cache:
            with open(cache, "w", encoding="utf-8") as f:
                json.dump([fg, bc], f)
    mwd, tr, lanes, rules = data_mwd(), data_transfer(), data_lanes(), data_rules()
    ov = data_overview(mwd, tr, bc, fg, lanes, rules, data_fp_summary())
    for page_file, key, data in [
        ("index.html", "overview", ov), ("lanes.html", "lanes", lanes), ("mwd.html", "mwd", mwd),
        ("transfer.html", "transfer", tr), ("business-case.html", "business", bc),
        ("finished-goods.html", "fg", fg), ("rules.html", "rules", rules),
        ("fg-live.html", "fglive", {"input": FG.engine_input(), "ranges": read_csv("fg_ranges.csv"),
                                    "params": read_csv("fg_params.csv")}),
        ("footprint.html", "footprint", {"input": FP.fp_input()}),
    ]:
        n = render(page_file, key, None, data)
        print(f"  docs/{page_file:<22}{n / 1e3:>8.0f} kB")


if __name__ == "__main__":
    main()
