"""
Module 7 — factory footprint under real laptop duties.

Six candidate assembly sites (China, Indonesia, Vietnam, Malaysia, Brazil, UAE) serve nine
regional distribution centres. For every site-market pair the model builds a landed cost per
unit, then chooses where each market buys from (a transport problem with site capacities),
and finally ranks every combination of open sites across tariff scenarios.

Landed cost of one unit, site o to market m:
  factory value  cv = China customs value + China conversion x (conversion index - 1)
                      + parts landed at the site (non-China sites: ocean freight on the parts
                        feed, carrying cost while it sails, import duty on parts)
  freight          ocean: (container base + rate x nm) / units per container + handling + trucking
                   air:   kg x (base + rate x 1,000 km) + handling + trucking
                   same country: trucking only
  duty             rate(market, origin, scenario) x (cv, plus freight where the market values CIF)
  carrying         cv x carrying rate x door-to-MGI days / 365
  planning         non-China sites: a longer chain (feed days / 7 + 1 week) worsens end-of-life
                   forecasts; priced per unit per week from Module 3
  chokepoints      optional premium per unit for each risky passage (Red Sea, Hormuz)

Origin: US customs gives a laptop the origin of the country where its main board (motherboard
PCBA) is made, not where it is put together (CBP rulings N350187, Jul 2025, and N357691, Jan 2026:
boards made in Vietnam, final assembly in China -> Vietnam origin). A non-China site that only
assembles boards made in China therefore pays the China rate. The model blends the two rates,
rate = (1 - w) x own rate + w x China rate, with w = board_origin_weight (1 = the CBP rule) for
sites that import their boards, and w = 0 for sites that make the board on site (extra cost per
unit and a yearly fixed cost) and for sales inside the site's own country.

Allocation: minimum-cost flow from open sites (capacity in units/week) to markets (demand in
units/week) on the ocean landed costs. A new site must run at least its minimum load (a share of
capacity: below it the workforce and the customer qualifications are lost), so a second site
costs its fixed cost plus the landed-cost gap on the volume it has to carry.

Footprints: every set of open sites that can cover demand and whose minimum loads fit inside
it, with the boards either imported from China or made on site, scored per scenario (52 weeks
+ yearly fixed cost of each new site and board line), by expected cost and by worst-case regret.

Build now or wait: a new site takes ramp_months to qualify. Waiting means keeping the footprint
that is cheapest under today's duties and opening the new one only in the scenarios where it
pays, after paying the old cost during the ramp plus a rush premium. Over horizon_years:
  wait(s) = min(H x C_base(s), lag x C_base(s) + (H - lag) x C(s) + rush)
  now(s)  = H x C(s)
The value of building now is the probability-weighted wait cost minus the build-now cost.

Break-even: for each market and site, the duty on China-made units above which the site beats
China (None when the site's units would pay the China rate too).

src/dash/fp_engine.js is the same model for the browser; tests/test_fp_parity.py checks both
give identical numbers.

Run:  python3 src/footprint.py
"""
import csv
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
RISKY = {"suez": "Red Sea", "babalmandab": "Red Sea", "ormuz": "Hormuz"}


def _csv(name):
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def ssum(values):
    t = 0.0
    for x in values:
        t += x
    return t


# ----------------------------------------------------------------------------- inputs
def fp_input():
    """Everything the model needs, as plain data (also embedded in the browser page)."""
    with open(os.path.join(DATA, "network.json"), encoding="utf-8") as f:
        net = json.load(f)
    lanes = net["lanes"]
    origins = list(net["origins"])
    markets = []
    for r in _csv("markets.csv"):
        markets.append({"market": r["market"], "mgi": r["mgi"], "tkey": r["tkey"],
                        "weekly_units": float(r["weekly_units"]), "valuation": r["valuation"],
                        "name": net["nodes"][r["mgi"]]["name"], "code": net["nodes"][r["mgi"]]["code"]})
    routes = {}
    for r in net["routes"]:
        truck = ssum(lanes[l]["km"] for l in r["lanes"] if lanes[l]["mode"] == "inland")
        air = ssum(lanes[l]["km"] for l in r["lanes"] if lanes[l]["mode"] == "air")
        key = f"{r['origin']}|{r['mgi']}|{r['mode']}|{r['variant']}"
        routes[key] = {"days": r["days"], "nm": r["nm"], "truck_km": truck, "air_km": air,
                       "passages": r.get("passages", []), "domestic": bool(r.get("domestic"))}
    feeds = {}
    for o, fs in net["feeds"].items():
        sea = fs[0]
        nm = ssum(lanes[l]["nm"] for l in sea["lanes"] if lanes[l]["mode"] == "sea")
        feeds[o] = {"days": sea["days"], "nm": nm, "passages": sea.get("passages", []),
                    "air_days": fs[1]["days"]}
    duties = {}
    for r in _csv("tariffs.csv"):
        duties[r["iso3"]] = {o: float(r[f"duty_{o.lower()}_origin_pct"]) / 100 for o in origins}
    scen, order = {}, []
    for r in _csv("duty_scenarios.csv"):
        sid = r["scenario"]
        if sid not in scen:
            scen[sid] = {"id": sid, "label": r["label"], "probability": float(r["probability"] or 0),
                         "overrides": [], "note": r["note"]}
            order.append(sid)
        if r["market"]:
            scen[sid]["overrides"].append({"tkey": r["market"], "origin": r["origin"],
                                           "duty": float(r["duty_pct"]) / 100})
    sites = {}
    for r in _csv("sites.csv"):
        sites[r["site"]] = {"label": r["label"], "conv_index": float(r["conv_index"]),
                            "parts_duty": float(r["parts_duty_pct"]) / 100,
                            "capacity": float(r["capacity_units_wk"]),
                            "fixed_cost": float(r["fixed_cost_usd_yr"]),
                            "min_load": float(r["min_load_pct"]) / 100,
                            "open": r["open_default"] == "1", "board_local": r["board_local"] == "1",
                            "status": r["status"], "note": r["note"]}
    P = {r["key"]: float(r["value"]) for r in _csv("footprint_params.csv")}
    return {"origins": origins, "markets": markets, "routes": routes, "feeds": feeds,
            "duties": duties, "scenarios": [scen[s] for s in order], "sites": sites, "P": P}


def duty_matrix(inp, scenario):
    d = {k: dict(v) for k, v in inp["duties"].items()}
    for ov in scenario["overrides"]:
        targets = inp["origins"] if ov["origin"] == "*" else [ov["origin"]]
        for o in targets:
            d[ov["tkey"]][o] = ov["duty"]
    return d


def route(inp, o, mgi, mode, red_sea):
    """Ocean routes through the Red Sea have a Cape and a Suez variant; others one ('any')."""
    R = inp["routes"]
    for v in (red_sea, "any"):
        k = f"{o}|{mgi}|{mode}|{v}"
        if k in R:
            return R[k]
    raise KeyError(f"{o}|{mgi}|{mode}")


# ----------------------------------------------------------------------------- landed cost
def landed(inp, P, sites, o, m, mode, red_sea, duties):
    r = route(inp, o, m["mgi"], mode, red_sea)
    s = sites[o]
    parts = plan = 0.0
    if o != "CN":
        f = inp["feeds"][o]
        parts_freight = (P["sea_feu_base_usd"] + P["sea_feu_per_nm_usd"] * f["nm"]) / P["kits_per_feu"] \
            + P["handling_usd_per_unit"]
        parts_carry = P["parts_value_usd"] * P["carrying_rate_annual"] * f["days"] / 365
        parts = parts_freight + parts_carry + P["parts_value_usd"] * s["parts_duty"]
        plan = P["planning_cost_usd_per_unit_week"] * (f["days"] / 7 + 1)
    board = o == "CN" or s["board_local"]
    cv = P["customs_value_cn_usd"] + P["conversion_cost_cn_usd"] * (s["conv_index"] - 1) + parts \
        + (P["board_extra_usd"] if o != "CN" and board else 0.0)
    trucking = P["truck_usd_per_unit_100km"] * r["truck_km"] / 100
    if r["domestic"]:
        freight = trucking + P["handling_usd_per_unit"] * 0.5
    elif mode == "sea":
        freight = (P["sea_feu_base_usd"] + P["sea_feu_per_nm_usd"] * r["nm"]) / P["units_per_feu"] \
            + P["handling_usd_per_unit"] + trucking
    else:
        freight = P["kg_per_unit"] * (P["air_usd_per_kg_base"] + P["air_usd_per_kg_per_1000km"] * r["air_km"] / 1000) \
            + P["handling_usd_per_unit"] + trucking
    own = duties[m["tkey"]][o]
    w = 0.0 if (board or r["domestic"]) else P["board_origin_weight"]
    rate = (1 - w) * own + w * duties[m["tkey"]]["CN"]
    base = cv + (freight if (m["valuation"] == "CIF" and not r["domestic"]) else 0.0)
    duty = rate * base
    carry = cv * P["carrying_rate_annual"] * r["days"] / 365
    risky = sorted({RISKY[p] for p in r["passages"] if p in RISKY})
    risk = P["chokepoint_premium_usd"] * len(risky)
    total = cv + freight + duty + carry + plan + risk
    return {"total": total, "factory": cv, "parts": parts, "freight": freight, "duty": duty,
            "duty_rate": rate, "own_rate": own, "origin_weight": w, "duty_base": base, "board": board,
            "carry": carry, "plan": plan, "risk": risk, "days": r["days"],
            "passages": r["passages"], "risky": risky, "domestic": r["domestic"]}


def landed_table(inp, P, sites, mode, red_sea, duties):
    return {o: [landed(inp, P, sites, o, m, mode, red_sea, duties) for m in inp["markets"]]
            for o in inp["origins"]}


# ----------------------------------------------------------------------------- allocation
BIG = 1e6   # cost bonus that makes the solver fill each site's minimum load first


def transport(cost, cap, demand, low=None):
    """Minimum-cost flow, sites -> markets. cost[i][j] per unit, cap[i], demand[j], low[i] the
    minimum load of site i. Successive shortest paths with Bellman-Ford; the first low[i] units
    out of site i carry a large bonus so they are routed first. Returns (flow[i][j], unmet units)."""
    ni, nj = len(cap), len(demand)
    n = ni + nj + 2
    s, t = 0, n - 1
    to, capv, costv = [], [], []
    adj = [[] for _ in range(n)]

    def add(u, v, c, w):
        adj[u].append(len(to)); to.append(v); capv.append(c); costv.append(w)
        adj[v].append(len(to)); to.append(u); capv.append(0.0); costv.append(-w)

    need = ssum(demand)
    low = low or [0.0] * ni
    for i in range(ni):
        lo = min(low[i], cap[i])
        if lo > 0:
            add(s, 1 + i, lo, -BIG)
        add(s, 1 + i, cap[i] - lo, 0.0)
    for i in range(ni):
        for j in range(nj):
            add(1 + i, 1 + ni + j, need, cost[i][j])
    for j in range(nj):
        add(1 + ni + j, t, demand[j], 0.0)
    sent = 0.0
    while sent < need - 1e-9:
        dist = [float("inf")] * n
        prev = [-1] * n
        dist[s] = 0.0
        for _ in range(n - 1):
            changed = False
            for u in range(n):
                if dist[u] == float("inf"):
                    continue
                for e in adj[u]:
                    if capv[e] > 1e-12 and dist[u] + costv[e] < dist[to[e]] - 1e-12:
                        dist[to[e]] = dist[u] + costv[e]
                        prev[to[e]] = e
                        changed = True
            if not changed:
                break
        if dist[t] == float("inf"):
            break
        push, v = need - sent, t
        while v != s:
            e = prev[v]
            push = min(push, capv[e])
            v = to[e ^ 1]
        v = t
        while v != s:
            e = prev[v]
            capv[e] -= push
            capv[e ^ 1] += push
            v = to[e ^ 1]
        sent += push
    flow = [[0.0] * nj for _ in range(ni)]
    for i in range(ni):
        for e in adj[1 + i]:
            j = to[e] - 1 - ni
            if 0 <= j < nj and e % 2 == 0:
                flow[i][j] = need - capv[e]
    return flow, max(0.0, need - sent)


def evaluate(inp, P, sites, open_sites, red_sea, duties):
    """Allocate demand from the open sites on ocean landed costs. Weekly figures."""
    org = [o for o in inp["origins"] if o in open_sites]
    tab = landed_table(inp, P, sites, "sea", red_sea, duties)
    cost = [[tab[o][j]["total"] for j in range(len(inp["markets"]))] for o in org]
    cap = [sites[o]["capacity"] for o in org]
    low = [sites[o]["min_load"] * sites[o]["capacity"] for o in org]
    dem = [m["weekly_units"] for m in inp["markets"]]
    flow, unmet = transport(cost, cap, dem, low)
    underload = ssum(max(0.0, low[i] - ssum(flow[i])) for i in range(len(org)))
    total = duty = days = 0.0
    exposure = {}
    alloc = {}
    for i, o in enumerate(org):
        for j, m in enumerate(inp["markets"]):
            q = flow[i][j]
            if q <= 1e-9:
                continue
            c = tab[o][j]
            alloc[f"{o}|{m['market']}"] = q
            total += q * c["total"]
            duty += q * c["duty"]
            days += q * c["days"]
            for p in c["risky"]:
                exposure[p] = exposure.get(p, 0.0) + q
    served = ssum(dem) - unmet
    return {"weekly_cost": total, "weekly_duty": duty, "avg_days": days / served if served else 0.0,
            "alloc": alloc, "unmet": unmet, "underload": underload, "exposure": exposure, "open": org,
            "load": {o: ssum(flow[i]) for i, o in enumerate(org)}}


def with_boards(sites, open_sites, board):
    """Copy of the sites with every open non-China site making (True) or importing (False) its boards."""
    out = {}
    for o, v in sites.items():
        c = dict(v)
        if o != "CN" and o in open_sites and board is not None:
            c["board_local"] = board
        out[o] = c
    return out


def yearly_costs(inp, P, sites, open_sites, red_sea, mats):
    """Yearly cost of one footprint in each duty matrix: 52 weeks + fixed cost of sites and board lines."""
    fixed = ssum(sites[o]["fixed_cost"] for o in open_sites) \
        + P["board_fixed_usd_yr"] * len([o for o in open_sites if o != "CN" and sites[o]["board_local"]])
    costs = []
    for d in mats:
        ev = evaluate(inp, P, sites, open_sites, red_sea, d)
        costs.append(52 * ev["weekly_cost"] + fixed + (1e12 if ev["unmet"] > 1e-6 or ev["underload"] > 1e-6 else 0.0))
    return fixed, costs


def footprints(inp, P, sites, red_sea, scen_list=None):
    """Score every set of open sites that can cover demand, boards imported or made on site,
    in every scenario; add the build-now-or-wait comparison."""
    scen_list = scen_list or inp["scenarios"]
    orgs = inp["origins"]
    demand = ssum(m["weekly_units"] for m in inp["markets"])
    mats = [duty_matrix(inp, s) for s in scen_list]
    rows = []
    for mask in range(1, 2 ** len(orgs)):
        open_sites = [o for k, o in enumerate(orgs) if mask >> k & 1]
        if ssum(sites[o]["capacity"] for o in open_sites) < demand - 1e-9 \
                or ssum(sites[o]["min_load"] * sites[o]["capacity"] for o in open_sites) > demand + 1e-9:
            continue
        for board in ((False, True) if any(o != "CN" for o in open_sites) else (None,)):
            sv = with_boards(sites, open_sites, board)
            fixed, costs = yearly_costs(inp, P, sv, open_sites, red_sea, mats)
            rows.append({"open": open_sites, "board": bool(board), "fixed": fixed, "costs": costs})
    best = [min(r["costs"][k] for r in rows) for k in range(len(scen_list))]
    wsum = ssum(s["probability"] for s in scen_list) or 1.0
    for r in rows:
        r["expected"] = ssum(s["probability"] * c for s, c in zip(scen_list, r["costs"])) / wsum
        r["regret"] = max(c - b for c, b in zip(r["costs"], best))
    rows.sort(key=lambda r: (r["expected"], len(r["open"]), r["board"]))
    base = min(rows, key=lambda r: r["costs"][0])
    H = P["horizon_years"]
    lag = min(P["ramp_months"] / 12, H)
    for r in rows:
        wait = []
        for k, c in enumerate(r["costs"]):
            cb = base["costs"][k]
            wait.append(H * cb if r is base else min(H * cb, lag * cb + (H - lag) * c + P["rush_premium_usd"]))
        r["wait_by"] = wait
        r["wait"] = ssum(s["probability"] * w for s, w in zip(scen_list, wait)) / wsum
        r["build_now_value"] = r["wait"] - H * r["expected"]
        r["is_base"] = r is base
    return rows


def tipping_weight(row, scen_list, sid, H):
    """Weight on scenario sid (others keep their relative weights) above which building this
    footprint now beats waiting. None if never, 0 if it already does at any weight."""
    k0 = [s["id"] for s in scen_list].index(sid)
    d = [w - H * c for w, c in zip(row["wait_by"], row["costs"])]
    rest = ssum(s["probability"] for k, s in enumerate(scen_list) if k != k0)
    d_o = ssum(s["probability"] * d[k] for k, s in enumerate(scen_list) if k != k0) / rest if rest > 0 else 0.0
    d_c = d[k0]
    if d_o >= 0:
        return 0.0
    if d_c <= 0:
        return None
    return -d_o / (d_c - d_o)


def break_even(inp, P, sites, red_sea, duties):
    """Duty on China-made units (share of the duty base) above which each site beats China,
    per market; 0 = already cheaper, None = never (its units pay the China rate as well)."""
    tab = landed_table(inp, P, sites, "sea", red_sea, duties)
    out = {}
    for o in inp["origins"]:
        if o == "CN":
            continue
        row = []
        for j in range(len(inp["markets"])):
            c, x = tab["CN"][j], tab[o][j]
            cn0 = c["total"] - c["duty"]
            own0 = x["total"] - x["duty"] + (1 - x["origin_weight"]) * x["own_rate"] * x["duty_base"]
            den = c["duty_base"] - x["origin_weight"] * x["duty_base"]
            if den <= 1e-9:
                row.append(0.0 if own0 <= cn0 else None)
            else:
                row.append(max(0.0, (own0 - cn0) / den))
        out[o] = row
    return out


# ----------------------------------------------------------------------------- report
def main():
    inp = fp_input()
    P, sites = inp["P"], inp["sites"]
    now = duty_matrix(inp, inp["scenarios"][0])
    tab = landed_table(inp, P, sites, "sea", "cape", now)
    mk = [m["market"] for m in inp["markets"]]
    print("== Landed cost per unit by ocean, current duties, Red Sea avoided ($)")
    print(f"  {'site':<6}" + "".join(f"{m:>8}" for m in mk))
    for o in inp["origins"]:
        print(f"  {o:<6}" + "".join(f"{c['total']:>8.1f}" for c in tab[o]))
    print("  cheapest:", ", ".join(f"{m}={min(inp['origins'], key=lambda o: tab[o][j]['total'])}"
                                   for j, m in enumerate(mk)))
    for s in inp["scenarios"]:
        d = duty_matrix(inp, s)
        ev = evaluate(inp, P, sites, inp["origins"], "cape", d)
        cn = evaluate(inp, P, sites, ["CN"], "cape", d)
        print(f"\n== {s['label']} (p={s['probability']:.2f}) · all six sites open")
        print(f"  weekly cost ${ev['weekly_cost']:,.0f} vs China only ${cn['weekly_cost']:,.0f}"
              f"  · duty ${ev['weekly_duty']:,.0f}/wk · avg {ev['avg_days']:.1f} days")
        print("  ", {k: round(v) for k, v in ev["alloc"].items()})
    print("\n== Duty on China-made units above which a site beats China (current duties, boards as in sites.csv)")
    be = break_even(inp, P, sites, "cape", now)
    print(f"  {'site':<6}" + "".join(f"{m:>8}" for m in mk))
    for o, row in be.items():
        print(f"  {o:<6}" + "".join(f"{'never':>8}" if v is None else f"{v * 100:>7.1f}%" for v in row))
    sb = with_boards(sites, inp["origins"], True)
    be = break_even(inp, P, sb, "cape", now)
    print("  same, every site making its own boards:")
    for o, row in be.items():
        print(f"  {o:<6}" + "".join(f"{'never':>8}" if v is None else f"{v * 100:>7.1f}%" for v in row))
    rows = footprints(inp, P, sites, "cape")
    print("\n== Footprints ranked by expected yearly cost (fixed cost of new sites and board lines included)")
    print(f"  {'open sites':<26}{'expected':>10}{'regret':>9}  " + "".join(f"{s['id']:>9}" for s in inp["scenarios"])
          + f"{'build now':>11}")
    for r in rows[:12]:
        name = "+".join(r["open"]) + (" (boards)" if r["board"] else "")
        print(f"  {name:<26}{r['expected'] / 1e6:>9.2f}M{r['regret'] / 1e6:>8.2f}M  "
              + "".join(f"{c / 1e6:>9.2f}" for c in r["costs"]) + f"{r['build_now_value'] / 1e6:>10.2f}M")
    rob = min(rows, key=lambda r: r["regret"])
    print(f"  lowest worst-case regret: {'+'.join(rob['open'])}{' (boards)' if rob['board'] else ''} (${rob['regret'] / 1e6:.2f}M)")
    best_now = max(rows, key=lambda r: r["build_now_value"])
    if best_now["build_now_value"] > 5e4:
        print(f"  most worth building now: {'+'.join(best_now['open'])}{' (boards)' if best_now['board'] else ''}"
              f" (${best_now['build_now_value'] / 1e6:.2f}M over {P['horizon_years']:.0f} years vs waiting)")
    else:
        print(f"  waiting beats building now for every footprint over {P['horizon_years']:.0f} years"
              f" (ramp-up {P['ramp_months']:.0f} months)")
    print("  weight on 'US 25% on China-made laptops' above which building now beats waiting:")
    for r in rows[:6]:
        if r["is_base"]:
            continue
        tw = tipping_weight(r, inp["scenarios"], "cn301", P["horizon_years"])
        name = "+".join(r["open"]) + (" (boards)" if r["board"] else "")
        print(f"    {name:<24} {'never' if tw is None else f'{tw * 100:.0f}%'}")

if __name__ == "__main__":
    main()
