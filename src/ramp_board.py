"""
Module 6 — new-site ramp and risk board hedge (Roadmap A3).

Part A, ramp. From the first trial build a new site takes about three months to reach full volume
(Q12), and the ramp can be pulled in at a cost. Three gates can slip it: material rhythm (parts on
the new site's longer lead time arrive late or out of step), yield learning and supplier readiness.
Each gate slips with a chance (lower with a strong GSM) by a random number of weeks:

  T          = max(ramp_min, ramp_base - pull) + slip_material + slip_yield + slip_supplier
  share(w)   = smoothstep(w / T) = 3x^2 - 2x^3,  x = min(1, w / T)      share of the region's volume
  leakage    = sum over weeks of (1 - share) x weekly units x customs value x tariff
               (China builds what the new site cannot yet and pays the China tariff, R16)
  yield(w)   = yield_full - (yield_full - yield_start) x exp(-w / tau)
  scrap      = sum of share x units x (1 / yield - 1) x BOM value x scrap_share
  pull cost  = weekly units x pull_cost x sum over pulled weeks i of (1 + growth x (i - 1))

The pull-in that minimises expected leakage + scrap + pull cost is recommended.

Part B, risk board hedge (R19). Each SMT run of a model builds boards for the next `cover`
weeks of forecast demand. A board locks its CPU and memory to the model and to the site's origin
(R13): if demand stops (end of life, or the model is cut early), boards left over are MWD at full
board value, while loose parts would mostly migrate (Module 5: 90%). Short covers keep material
loose but cost setups, and the ODM takes away SMT capacity it is not loaded with (stronger with a
weak GSM). Per model and cover, a Monte Carlo over the year:

  actual     D(w)     = plan(w) x max(0, 1 + noise x z)                0 after an early cut
  forecast   F(w, h)  = D(w) x (1 + bias x sqrt(h/16) + sigma(h) x u),  sigma(h) = MAPE16 x 1.2533 x sqrt(h/16)
                        made h weeks ahead; 0 for weeks at or after the end of life, and after a
                        cut once it is known
  run week d (every `cover` weeks): build = min(need - boards on hand, need x (1 - cut))
                        need = sum of F(d + j, j + 1), cut = kappa x max(0, (std - cover) / std)
  each week  boards used = min(on hand, D); short -> rush boards at a premium from the run's rush
             budget (smt_flex x the plan of the run's weeks), the rest short: lost_share lost at
             gross margin
  cost       = setups + rush + lost margin + carrying + stranded boards x
               (board value - on-board parts x (1 - migration)) x MWD cost rate

The cover with the lowest expected cost is the recommended board-build cover for the model.

src/dash/rb_engine.js is the same model for the browser; tests/test_rb_parity.py checks it.
Run:  python3 src/ramp_board.py
"""
import csv
import math
import os

import business_case as BC
import mwd_engine as E
from prng import PortableRandom

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
COVERS = [1, 2, 3, 4, 6, 8]
WEEKS = 52
RAMP_WEEKS = 40


def _csv(name):
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def rb_input(region="US"):
    mats, models, locales, bom, used_by, params = E.load()
    prof = BC.region_profile(region)
    dm = {r["model"]: r for r in _csv("demand_models.csv")}
    bm = {r["model"]: r for r in _csv("board_models.csv")}
    dp = {r["key"]: float(r["value"]) for r in _csv("demand_params.csv")}
    mods = []
    for k, m in models.items():
        sku = next(s for s in bom if s.rsplit("_", 1)[0] == k)
        onboard = sum(mats[x]["unit_cost"] * q for x, q in bom[sku].items() if mats[x]["on_board"])
        r = bm[k]
        mods.append({"model": k, "risk": r["risk"], "bias": float(r["forecast_bias"]),
                     "sigma_mult": float(r["sigma_mult"]), "cut_prob": float(r["cut_prob"]),
                     "eol": m["eol"] if m["eol"] <= WEEKS else None,
                     "board_value": m["board_extra"] + onboard, "onboard_parts": onboard,
                     "margin": float(dm[k]["channel_net_price_usd"]) * float(dm[k]["gross_margin_pct"]) / 100,
                     "plan": [E.model_weekly_demand(m, w) for w in range(WEEKS)]})
    P = {r["key"]: float(r["value"]) for r in _csv("ramp_params.csv")}
    P.update(carry=params["carrying_rate_annual"], migration=dp["mwd_transferability"],
             mwd_cost_rate=dp["mwd_cost_rate"])
    region_ = {"weekly_units": prof["weekly_units"], "customs": prof["weekly_customs"] / prof["weekly_units"],
               "bom": prof["weekly_bom"] / prof["weekly_units"]}
    return {"models": mods, "region": region_, "P": P, "covers": COVERS, "weeks": WEEKS, "ramp_weeks": RAMP_WEEKS}


# ----------------------------------------------------------------------------- Part A: ramp
def smoothstep(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def ramp_slips(inp, P, seed=11):
    """Slip weeks per run and gate, drawn once so every pull-in is compared on the same runs."""
    rng = PortableRandom(seed)
    mult = P["gsm_mult_strong"] if P["gsm_strong"] >= 0.5 else P["gsm_mult_weak"]
    out = []
    for _ in range(int(P["ramp_runs"])):
        row = []
        for g in ("material", "yield", "supplier"):
            u1, u2 = rng.random(), rng.random()
            p = min(1.0, P[f"slip_{g}_prob"] * mult)
            lo, hi = P[f"slip_{g}_lo"], P[f"slip_{g}_hi"]
            row.append(lo + (hi - lo) * u2 if u1 < p else 0.0)
        out.append(row)
    return out


def ramp_run(inp, P, pull, slips):
    """One run: ramp weeks, the share curve and the three costs."""
    rg = inp["region"]
    T = max(P["ramp_min_weeks"], P["ramp_base_weeks"] - pull) + sum(slips)
    share = [smoothstep(w / T) if T > 0 else 1.0 for w in range(inp["ramp_weeks"])]
    leak = scrap = 0.0
    for w, s in enumerate(share):
        leak += (1 - s) * rg["weekly_units"] * rg["customs"] * P["ramp_tariff"]
        y = P["yield_full"] - (P["yield_full"] - P["yield_start"]) * math.exp(-w / P["yield_tau_weeks"])
        scrap += s * rg["weekly_units"] * (1 / y - 1) * rg["bom"] * P["scrap_share_of_bom"]
    k = int(pull)
    pc = rg["weekly_units"] * P["pull_cost_usd_per_unit"] * sum(1 + P["pull_cost_growth"] * i for i in range(k))
    return {"T": T, "share": share, "leakage": leak, "scrap": scrap, "pull": pc, "total": leak + scrap + pc}


def pct(vals, q):
    v = sorted(vals)
    return v[int(q * (len(v) - 1))]


def ramp_sweep(inp, P, seed=11):
    """Expected cost of every pull-in from 0 to the most the ramp allows."""
    slips = ramp_slips(inp, P, seed)
    top = int(max(0.0, P["ramp_base_weeks"] - P["ramp_min_weeks"]))
    rows = []
    for pull in range(top + 1):
        runs = [ramp_run(inp, P, pull, s) for s in slips]
        n = len(runs)
        rows.append({"pull": pull, "T_mean": sum(r["T"] for r in runs) / n,
                     "T_p10": pct([r["T"] for r in runs], 0.1), "T_p50": pct([r["T"] for r in runs], 0.5),
                     "T_p90": pct([r["T"] for r in runs], 0.9),
                     "leakage": sum(r["leakage"] for r in runs) / n, "scrap": sum(r["scrap"] for r in runs) / n,
                     "pull_cost": runs[0]["pull"], "total": sum(r["total"] for r in runs) / n,
                     "band": [[pct([r["share"][w] for r in runs], q) for q in (0.1, 0.5, 0.9)]
                              for w in range(inp["ramp_weeks"])]})
    best = min(rows, key=lambda r: (r["total"], r["pull"]))
    gates = [sum(1 for s in slips if s[g] > 0) / len(slips) for g in range(3)]
    return {"rows": rows, "best": best["pull"], "slip_share": gates,
            "slip_mean": [sum(s[g] for s in slips) / len(slips) for g in range(3)]}


# ----------------------------------------------------------------------------- Part B: board cover
def board_draws(inp, P, m, seed):
    """Per run: weekly demand noise z, forecast noise u, and the early-cut week (None if none)."""
    rng = PortableRandom(seed)
    runs = []
    for _ in range(int(P["board_runs"])):
        z = [rng.gauss() for _ in range(inp["weeks"])]
        u = [rng.gauss() for _ in range(inp["weeks"])]
        c1, c2 = rng.random(), rng.random()
        live = [w for w in range(inp["weeks"]) if m["plan"][w] > 0]
        cut = None
        if c1 < m["cut_prob"] and len(live) > 8:
            cut = live[0] + 4 + int(c2 * (len(live) - 4))
        runs.append((z, u, cut))
    return runs


def board_run(inp, P, m, cover, draw):
    z, u, cut = draw
    W = inp["weeks"]
    s16 = P["forecast_mape_16w"] * math.sqrt(math.pi / 2) * m["sigma_mult"]
    D = [0.0 if (cut is not None and w >= cut) else m["plan"][w] * max(0.0, 1 + P["demand_noise"] * z[w])
         for w in range(W)]
    kappa = P["capacity_cut_strong"] if P["gsm_strong"] >= 0.5 else P["capacity_cut_weak"]
    cutcap = kappa * max(0.0, (P["board_cover_std_weeks"] - cover) / P["board_cover_std_weeks"])
    inv = setups = rush = lost = carry = 0.0
    budget = 0.0                                          # rush boards the ODM can still add in this run

    def forecast(w, h, d):
        if m["eol"] is not None and w >= m["eol"]:
            return 0.0
        if cut is not None and d >= cut:
            return 0.0                                   # the cut is known at decision week d
        base = m["plan"][w] * max(0.0, 1 + P["demand_noise"] * z[w])
        g = math.sqrt(h / 16)
        return base * max(0.0, 1 + m["bias"] * g + s16 * g * u[w])

    for w in range(W):
        if w % cover == 0:
            need = sum(forecast(w + j, j + 1, w) for j in range(cover) if w + j < W)
            build = min(max(0.0, need - inv), need * (1 - cutcap))
            if build > 1e-9:
                inv += build
                setups += P["setup_usd_per_run"]
            budget = P["smt_flex"] * sum(m["plan"][w + j] for j in range(cover) if w + j < W)
        use = min(inv, D[w])
        inv -= use
        short = D[w] - use
        if short > 1e-9:
            r = min(short, budget)
            budget -= r
            rush += r * P["rush_premium_usd"]
            lost += (short - r) * P["lost_share"] * m["margin"]
        carry += inv * m["board_value"] * P["carry"] / 52
    ended = cut is not None or m["eol"] is not None
    stranded = inv if ended else 0.0
    lock = (m["board_value"] - m["onboard_parts"] * (1 - P["migration"])) * P["mwd_cost_rate"]
    parts = {"setups": setups, "rush": rush, "lost": lost, "carry": carry, "stranded": stranded * lock}
    return {"parts": parts, "total": sum(parts.values()), "stranded_boards": stranded}


def board_eval(inp, P, m, seed):
    draws = board_draws(inp, P, m, seed)
    rows = []
    for cover in inp["covers"]:
        runs = [board_run(inp, P, m, cover, d) for d in draws]
        n = len(runs)
        parts = {k: sum(r["parts"][k] for r in runs) / n for k in runs[0]["parts"]}
        tot = [r["total"] for r in runs]
        rows.append({"cover": cover, "parts": parts, "total": sum(tot) / n, "p90": pct(tot, 0.9),
                     "stranded_boards": sum(r["stranded_boards"] for r in runs) / n})
    best = min(rows, key=lambda r: (r["total"], -r["cover"]))
    return {"model": m["model"], "risk": m["risk"], "rows": rows, "best": best["cover"]}


def boards(inp, P):
    return [board_eval(inp, P, m, 101 + i) for i, m in enumerate(inp["models"])]


# ----------------------------------------------------------------------------- report
def main():
    inp = rb_input()
    P = inp["P"]
    rs = ramp_sweep(inp, P)
    print(f"== Part A, new-site ramp: base {P['ramp_base_weeks']:.0f} weeks, {P['ramp_tariff']:.0%} tariff on what "
          f"China still builds, {'strong' if P['gsm_strong'] >= 0.5 else 'weak'} GSM, {int(P['ramp_runs'])} runs")
    print("  slip chance: " + ", ".join(f"{g} {s:.0%} (mean {m:.1f} wk)" for g, s, m in
                                         zip(("material", "yield", "supplier"), rs["slip_share"], rs["slip_mean"])))
    print(f"  {'pull':>4}{'T mean':>8}{'P10':>6}{'P50':>6}{'P90':>6}{'leakage':>11}{'scrap':>9}{'pull $':>9}{'total':>11}")
    for r in rs["rows"]:
        mark = "  <- best" if r["pull"] == rs["best"] else ""
        print(f"  {r['pull']:>4}{r['T_mean']:>8.1f}{r['T_p10']:>6.1f}{r['T_p50']:>6.1f}{r['T_p90']:>6.1f}"
              f"{r['leakage'] / 1e6:>10.2f}M{r['scrap'] / 1e6:>8.2f}M{r['pull_cost'] / 1e6:>8.2f}M{r['total'] / 1e6:>10.2f}M{mark}")
    print(f"\n== Part B, board-build cover per SMT run (standard {P['board_cover_std_weeks']:.0f} weeks), "
          f"{int(P['board_runs'])} runs")
    for b in boards(inp, P):
        print(f"  {b['model']} ({b['risk']}): recommended cover {b['best']} week{'s' if b['best'] > 1 else ''}")
        for r in b["rows"]:
            p = r["parts"]
            print(f"    cover {r['cover']}: expected ${r['total'] / 1e3:,.0f}k (P90 ${r['p90'] / 1e3:,.0f}k) · setups "
                  f"{p['setups'] / 1e3:,.0f}k · rush {p['rush'] / 1e3:,.0f}k · lost {p['lost'] / 1e3:,.0f}k · carry "
                  f"{p['carry'] / 1e3:,.0f}k · stranded {p['stranded'] / 1e3:,.0f}k ({r['stranded_boards']:,.0f} boards)")


if __name__ == "__main__":
    main()
