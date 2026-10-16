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

Each new site is run one of two ways (site_terms). 'odm': a line on an ODM's existing overseas
campus, at a price uplift per unit over the China line (conversion index), a one-time NRE (the
line's share of the campus fit-out plus qualification) spread over the horizon, a yearly program
cost and a volume commitment: units below it pay a take-or-pay fee. 'buy': the brand buys an
electronics plant (price from the capex per unit of capacity of recent ODM campuses), saves the
ODM's operating margin, and pays depreciation and capital on the price, its own overhead and the
idle labour below the planned load.

Allocation: minimum-cost flow from open lines (capacity in units/week) to markets (demand in
units/week) on the ocean landed costs; each line is loaded up to its commitment whenever that
costs less than the fee, and the fee is paid on the rest.

Freight: ocean rates per 40-ft container are published lane benchmarks (Far East to each region):
pre-war (late Feb 2026), long-term contract (Aug 2026) and spot (Oct 2026); freight_basis 0, 1, 2
picks them, with straight lines in between. Lanes without a benchmark use the distance formula. The Strait of Hormuz has been closed to normal
shipping since 28 Feb 2026: with hormuz_closed = 1, Gulf cargo lands at Khor Fakkan and trucks
to and from Dubai.

Supply scenario: China licences parts exports; non-China sites pay cn_parts_premium on the parts
they take from China.

Footprints: every set of open sites that can cover demand, with the boards either imported from
China or made on site, scored per scenario (52 weeks + yearly program, NRE and board-line cost),
by expected cost and by worst-case regret.

Linked costs (src/integrate.py, data/linkage.json): the chain cost per extra week comes from
Module 3, the end-of-life finished-goods cost per extra week of transit from Module 4, and the
cost of moving volume out of China in a hurry from Modules 1-2 (cutover) and 3 (expediting).

Build now or wait: a new site takes ramp_months_odm or ramp_months_buy to qualify (lag). Waiting means keeping the footprint
that is cheapest under today's duties and opening the new one only in the scenarios where it
pays, after paying the old cost during the ramp, a rush premium and an urgent transfer of the
volume that leaves China. Over horizon_years:
  wait(s) = min(H x C_base(s), lag x C_base(s) + (H - lag) x C(s) + rush + urgent x moved(s))
  now(s)  = H x C(s)
The value of building now is the probability-weighted wait cost minus the build-now cost.

Break-even: for each market and site, the duty on China-made units above which the site beats
China (None when the site's units would pay the China rate too).

Duty ranges (Monte Carlo): each duty can move inside a range [low, high]; the default ceiling
for the US is the April 2025 peak (China 145%, Vietnam 46%, Indonesia 32%, Malaysia 24%,
Brazil and UAE 10%). In every run and market, with probability duty_change_prob the market
changes its duties: one strength s ~ U(0, 1) moves every origin to low + s x (high - low);
otherwise today's rate stays. Every feasible footprint is priced in every run: mean, P10,
P90, how often it is the cheapest, and its regret against the cheapest in the same run.

src/dash/fp_engine.js is the same model for the browser; tests/test_fp_parity.py checks both
give identical numbers.

Run:  python3 src/footprint.py
"""
import csv
import json
import os

from prng import PortableRandom

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
    region = {r["port"]: r["region"] for r in _csv("freight_regions.csv")}
    freight = {r["lane"]: [float(r["normal_usd_feu"]), float(r["contract_usd_feu"]), float(r["now_usd_feu"])]
               for r in _csv("freight_lanes.csv")}
    lane_of = lambda a, b: f"{region.get(a, a)}-{region.get(b, b)}"
    routes = {}
    for r in net["routes"]:
        truck = ssum(lanes[l]["km"] for l in r["lanes"] if lanes[l]["mode"] == "inland")
        air = ssum(lanes[l]["km"] for l in r["lanes"] if lanes[l]["mode"] == "air")
        hz = r.get("hormuz", "any")
        key = f"{r['origin']}|{r['mgi']}|{r['mode']}|{r['variant']}|{hz}"
        fp, tp = r.get("from_port"), r.get("to_port")
        routes[key] = {"days": r["days"], "nm": r["nm"], "truck_km": truck, "air_km": air,
                       "passages": r.get("passages", []), "domestic": bool(r.get("domestic")),
                       "lane": lane_of(fp, tp) if fp else "",
                       "gulf": bool(fp) and "GULF" in (region.get(fp), region.get(tp)),
                       "bypass": hz == "closed"}
    feeds = {}
    for o, fs in net["feeds"].items():
        air_days = next(f["days"] for f in fs if f.get("mode") == "air")
        feeds[o] = {}
        for state in ("open", "closed"):
            sea = next(f for f in fs if f.get("mode") == "sea" and f.get("hormuz", "any") in ("any", state))
            nm = ssum(lanes[l]["nm"] for l in sea["lanes"] if lanes[l]["mode"] == "sea")
            feeds[o][state] = {"days": sea["days"], "nm": nm, "passages": sea.get("passages", []),
                               "air_days": air_days, "lane": lane_of(sea["from_port"], sea["to_port"]),
                               "gulf": "GULF" in (region.get(sea["from_port"]), region.get(sea["to_port"])),
                               "bypass": sea.get("hormuz") == "closed"}
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
        if r["market"] == "PARTS":                    # China restricts parts exports to other sites
            scen[sid]["overrides"].append({"tkey": "_parts", "origin": r["origin"], "duty": 1.0})
        elif r["market"]:
            scen[sid]["overrides"].append({"tkey": r["market"], "origin": r["origin"],
                                           "duty": float(r["duty_pct"]) / 100})
    sites = {}
    for r in _csv("sites.csv"):
        sites[r["site"]] = {"label": r["label"], "conv_index": float(r["conv_index"]),
                            "parts_duty": float(r["parts_duty_pct"]) / 100,
                            "capacity": float(r["capacity_units_wk"]),
                            "fixed_cost": float(r["fixed_cost_usd_yr"]), "nre": float(r["nre_usd"] or 0),
                            "mode": r.get("mode") or "odm", "buy_price": float(r.get("buy_price_usd") or 0),
                            "min_load": float(r["min_load_pct"]) / 100,
                            "open": r["open_default"] == "1", "board_local": r["board_local"] == "1",
                            "status": r["status"], "note": r["note"]}
    P = {r["key"]: float(r["value"]) for r in _csv("footprint_params.csv")}
    for o, r in zip(sites, _csv("sites.csv")):        # blank = derived from capex per unit of capacity
        yearly = sites[o]["capacity"] * 52
        if not r["nre_usd"]:
            sites[o]["nre"] = round(P["capex_odm_line_usd_per_annual_unit"] * yearly + P["qualification_usd"], -4)
        if not r.get("buy_price_usd"):
            sites[o]["buy_price"] = round(P["capex_plant_usd_per_annual_unit"] * yearly, -4)
    linkage = None
    lp = os.path.join(DATA, "linkage.json")
    if os.path.exists(lp):                          # Modules 1-4 feed three of Module 7's costs
        with open(lp, encoding="utf-8") as f:
            linkage = json.load(f)
        P["planning_cost_usd_per_unit_week"] = linkage["chain"]["usd_per_unit_week"]
        P["fg_eol_usd_per_unit_week"] = linkage["finished_goods"]["usd_per_unit_week"]
        P["urgent_transition_usd_per_weekly_unit"] = linkage["transition"]["urgent_usd_per_weekly_unit"]
    ranges, peaks = {}, {}
    for r in _csv("duty_ranges.csv"):
        k = f"{r['market']}|{r['origin']}"
        ranges[k] = [float(r["low_pct"]) / 100, float(r["high_pct"]) / 100]
        if r["peak_2025_pct"]:
            peaks[k] = float(r["peak_2025_pct"]) / 100
    duties["_parts"] = {o: 0.0 for o in origins}      # 1 = this site's China parts carry cn_parts_premium
    return {"origins": origins, "markets": markets, "routes": routes, "feeds": feeds, "freight": freight,
            "duties": duties, "scenarios": [scen[s] for s in order], "sites": sites, "P": P,
            "ranges": ranges, "peaks_2025": peaks, "linkage": linkage}


def duty_matrix(inp, scenario):
    d = {k: dict(v) for k, v in inp["duties"].items()}
    for ov in scenario["overrides"]:
        targets = inp["origins"] if ov["origin"] == "*" else [ov["origin"]]
        for o in targets:
            if ov["tkey"] == "_parts" and o == "CN":
                continue
            d[ov["tkey"]][o] = ov["duty"]
    return d


def route(inp, o, mgi, mode, red_sea, hormuz):
    """Ocean routes through the Red Sea have a Cape and a Suez variant; routes through Hormuz an
    open and a closed (Khor Fakkan bypass) variant; all others one ('any')."""
    R = inp["routes"]
    for v in (red_sea, "any"):
        for h in (hormuz, "any"):
            k = f"{o}|{mgi}|{mode}|{v}|{h}"
            if k in R:
                return R[k]
    raise KeyError(f"{o}|{mgi}|{mode}")


def feu_rate(inp, P, lane, nm):
    """Ocean rate per 40-ft container on a lane: freight_basis 0 = pre-war (late Feb 2026),
    1 = long-term contract (Aug 2026), 2 = spot (Oct 2026), straight lines in between. Lanes
    without a benchmark use the distance formula, scaled by the contract and spot factors."""
    if lane in inp["freight"]:
        a, c, b = inp["freight"][lane]
    else:
        a = P["sea_feu_base_usd"] + P["sea_feu_per_nm_usd"] * nm
        c, b = a * P["fallback_contract_factor"], a * P["fallback_now_factor"]
    x = P["freight_basis"]
    return a + x * (c - a) if x <= 1 else c + (x - 1) * (b - c)


def site_terms(P, s):
    """How a site is run (R35): 'odm' = an ODM's line on its existing campus (price index on the
    China line, NRE, yearly program cost, take-or-pay below the commitment); 'buy' = the brand buys
    an electronics plant (saves the ODM's operating margin, pays depreciation and capital on the
    price, its own overhead, and the idle labour below the planned load)."""
    if s.get("mode") == "buy":
        conv = s["conv_index"] - P["odm_op_margin"] * P["customs_value_cn_usd"] / P["conversion_cost_cn_usd"]
        return {"conv": conv, "fee": P["labour_share_conversion"] * P["conversion_cost_cn_usd"] * conv,
                "fixed": s["fixed_cost"] + P["buy_overhead_usd_yr"]
                + s["buy_price"] * (1 / P["plant_life_years"] + P["capital_rate"]),
                "ramp": P["ramp_months_buy"]}
    return {"conv": s["conv_index"], "fee": P["shortfall_fee_usd"],
            "fixed": s["fixed_cost"] + s["nre"] / P["horizon_years"], "ramp": P["ramp_months_odm"]}


def ocean_extra(P, leg):
    """Gulf surcharge and bypass trucking per container."""
    return (P["gulf_surcharge_feu"] if leg["gulf"] else 0.0) + (P["bypass_truck_usd_feu"] if leg["bypass"] else 0.0)


# ----------------------------------------------------------------------------- landed cost
def landed(inp, P, sites, o, m, mode, red_sea, duties):
    hz = "closed" if P["hormuz_closed"] >= 0.5 else "open"
    r = route(inp, o, m["mgi"], mode, red_sea, hz)
    s = sites[o]
    parts = plan = 0.0
    if o != "CN":
        f = inp["feeds"][o][hz]
        parts_freight = (feu_rate(inp, P, f["lane"], f["nm"]) + ocean_extra(P, f)) / P["kits_per_feu"] \
            + P["handling_usd_per_unit"]
        parts_carry = P["parts_value_usd"] * P["carrying_rate_annual"] * f["days"] / 365
        parts = parts_freight + parts_carry + P["parts_value_usd"] * s["parts_duty"] \
            + P["parts_value_usd"] * P["cn_parts_premium"] * duties["_parts"][o]
        plan = P["planning_cost_usd_per_unit_week"] * (f["days"] / 7 + 1)
    board = o == "CN" or s["board_local"]
    cv = P["customs_value_cn_usd"] + P["conversion_cost_cn_usd"] * (site_terms(P, s)["conv"] - 1) + parts \
        + (P["board_extra_usd"] if o != "CN" and board else 0.0)
    trucking = P["truck_usd_per_unit_100km"] * r["truck_km"] / 100
    if r["domestic"]:
        freight = trucking + P["handling_usd_per_unit"] * 0.5
    elif mode == "sea":
        freight = (feu_rate(inp, P, r["lane"], r["nm"]) + ocean_extra(P, r)) / P["units_per_feu"] \
            + P["handling_usd_per_unit"] + trucking
    else:
        freight = P["kg_per_unit"] * (P["air_usd_per_kg_base"] + P["air_usd_per_kg_per_1000km"] * r["air_km"] / 1000) \
            + P["handling_usd_per_unit"] + trucking
    # Module 4: a longer (shorter) chain than China's to the same MGI leaves more (less) stock in the
    # pipeline at the successor launch
    cn_days = r["days"] if o == "CN" else route(inp, "CN", m["mgi"], mode, red_sea, hz)["days"]
    fg = P["fg_eol_usd_per_unit_week"] * (r["days"] - cn_days) / 7
    own = duties[m["tkey"]][o]
    w = 0.0 if (board or r["domestic"]) else P["board_origin_weight"]
    rate = (1 - w) * own + w * duties[m["tkey"]]["CN"]
    base = cv + (freight if (m["valuation"] == "CIF" and not r["domestic"]) else 0.0)
    duty = rate * base
    carry = cv * P["carrying_rate_annual"] * r["days"] / 365
    risky = sorted({RISKY[p] for p in r["passages"] if p in RISKY})
    risk = P["chokepoint_premium_usd"] * len(risky)
    total = cv + freight + duty + carry + plan + fg + risk
    return {"total": total, "factory": cv, "parts": parts, "freight": freight, "duty": duty, "fg": fg,
            "duty_rate": rate, "own_rate": own, "origin_weight": w, "duty_base": base, "board": board,
            "carry": carry, "plan": plan, "risk": risk, "days": r["days"],
            "passages": r["passages"], "risky": risky, "domestic": r["domestic"]}


def landed_table(inp, P, sites, mode, red_sea, duties):
    return {o: [landed(inp, P, sites, o, m, mode, red_sea, duties) for m in inp["markets"]]
            for o in inp["origins"]}


# ----------------------------------------------------------------------------- allocation
def transport(cost, cap, demand, low=None, bonus=0.0):
    """Minimum-cost flow, sites -> markets. cost[i][j] per unit, cap[i], demand[j], low[i] the
    minimum volume commitment of site i. Successive shortest paths with Bellman-Ford; the first
    low[i] units out of site i carry a bonus equal to its fee per unit short (bonus: one number or
    one per site), so a site is loaded up to its commitment whenever that costs less than paying
    the fee. Returns (flow, unmet units)."""
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
    bonus = bonus if isinstance(bonus, list) else [bonus] * ni
    for i in range(ni):
        lo = min(low[i], cap[i])
        if lo > 0:
            add(s, 1 + i, lo, -bonus[i])
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
    fee = [site_terms(P, sites[o])["fee"] for o in org]
    flow, unmet = transport(cost, cap, dem, low, fee)
    under = [max(0.0, low[i] - ssum(flow[i])) for i in range(len(org))]
    underload = ssum(under)
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
    shortfall = ssum(fee[i] * under[i] for i in range(len(org)))   # take-or-pay or idle labour below the load
    return {"weekly_cost": total + shortfall, "weekly_landed": total, "weekly_shortfall": shortfall,
            "weekly_duty": duty, "avg_days": days / served if served else 0.0,
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
    """Yearly cost of one footprint in each duty matrix: 52 weeks of landed cost and shortfall,
    plus each site's fixed terms (site_terms) and board lines."""
    fixed = ssum(site_terms(P, sites[o])["fixed"] for o in open_sites) \
        + P["board_fixed_usd_yr"] * len([o for o in open_sites if o != "CN" and sites[o]["board_local"]])
    costs, moved = [], []
    for d in mats:
        ev = evaluate(inp, P, sites, open_sites, red_sea, d)
        costs.append(52 * ev["weekly_cost"] + fixed + (1e12 if ev["unmet"] > 1e-6 else 0.0))
        moved.append(ssum(q for o, q in ev["load"].items() if o != "CN"))   # weekly units built outside China
    return fixed, costs, moved


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
        if ssum(sites[o]["capacity"] for o in open_sites) < demand - 1e-9:
            continue
        for board in ((False, True) if any(o != "CN" for o in open_sites) else (None,)):
            sv = with_boards(sites, open_sites, board)
            fixed, costs, moved = yearly_costs(inp, P, sv, open_sites, red_sea, mats)
            rows.append({"open": open_sites, "board": bool(board), "fixed": fixed, "costs": costs, "moved": moved})
    best = [min(r["costs"][k] for r in rows) for k in range(len(scen_list))]
    wsum = ssum(s["probability"] for s in scen_list) or 1.0
    for r in rows:
        r["expected"] = ssum(s["probability"] * c for s, c in zip(scen_list, r["costs"])) / wsum
        r["regret"] = max(c - b for c, b in zip(r["costs"], best))
    rows.sort(key=lambda r: (r["expected"], len(r["open"]), r["board"]))
    base = min(rows, key=lambda r: r["costs"][0])
    H = P["horizon_years"]
    for r in rows:
        new = [o for o in r["open"] if o != "CN" and o not in base["open"]]
        lag = min(max([site_terms(P, sites[o])["ramp"] for o in new], default=0.0) / 12, H)
        r["lag"] = lag
        wait = []
        for k, c in enumerate(r["costs"]):
            cb = base["costs"][k]
            # waiting: open late, pay the old cost through the ramp-up, a rush premium, and an
            # urgent transfer of the volume that leaves China (Modules 1-3)
            urgent = P["urgent_transition_usd_per_weekly_unit"] * max(0.0, r["moved"][k] - base["moved"][k])
            rush = P["rush_premium_usd"] if new else 0.0
            wait.append(H * cb if r is base else min(H * cb, lag * cb + (H - lag) * c + rush + urgent))
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


def candidates(inp, sites):
    """Every feasible footprint with its board variant, in the order footprints() enumerates them."""
    orgs = inp["origins"]
    demand = ssum(m["weekly_units"] for m in inp["markets"])
    out = []
    for mask in range(1, 2 ** len(orgs)):
        open_sites = [o for k, o in enumerate(orgs) if mask >> k & 1]
        if ssum(sites[o]["capacity"] for o in open_sites) < demand - 1e-9:
            continue
        for board in ((False, True) if any(o != "CN" for o in open_sites) else (None,)):
            out.append({"open": open_sites, "board": bool(board), "sites": with_boards(sites, open_sites, board)})
    return out


def draw_duties(inp, base, ranges, p_change, rng):
    """One Monte Carlo draw of every market's duties (see the module docstring)."""
    d = {t: dict(v) for t, v in base.items()}
    seen = []
    for m in inp["markets"]:
        t = m["tkey"]
        if t in seen:
            continue
        seen.append(t)
        u, s = rng.random(), rng.random()
        for o in inp["origins"]:
            b = base[t][o]
            lo, hi = ranges.get(f"{t}|{o}", (b, b))
            if lo > hi:
                lo, hi = hi, lo
            d[t][o] = lo + s * (hi - lo) if u < p_change else min(max(b, lo), hi)
    return d


def duty_monte_carlo(inp, P, sites, red_sea, ranges=None, runs=200, seed=7):
    """Price every feasible footprint under random duty draws inside the ranges."""
    ranges = inp["ranges"] if ranges is None else ranges
    base = duty_matrix(inp, inp["scenarios"][0])
    cands = candidates(inp, sites)
    rng = PortableRandom(seed)
    cost = [[0.0] * len(cands) for _ in range(runs)]
    mean_duty = {}
    for k in range(runs):
        d = draw_duties(inp, base, ranges, P["duty_change_prob"], rng)
        for key in ranges:
            t, o = key.split("|")
            mean_duty[key] = mean_duty.get(key, 0.0) + d[t][o] / runs
        for i, c in enumerate(cands):
            cost[k][i] = yearly_costs(inp, P, c["sites"], c["open"], red_sea, [d])[1][0]
    best = [min(row) for row in cost]
    win = [0] * len(cands)
    for row in cost:
        j, b = 0, row[0]
        for i, v in enumerate(row):
            if v < b:
                j, b = i, v
        win[j] += 1
    pick = lambda v, q: v[int(q * (len(v) - 1))]
    rows = []
    for i, c in enumerate(cands):
        col = [cost[k][i] for k in range(runs)]
        reg = [cost[k][i] - best[k] for k in range(runs)]
        sc, sr = sorted(col), sorted(reg)
        rows.append({"open": c["open"], "board": c["board"], "mean": ssum(col) / runs,
                     "p10": pick(sc, .1), "p50": pick(sc, .5), "p90": pick(sc, .9),
                     "win": win[i] / runs, "regret_mean": ssum(reg) / runs, "regret_p90": pick(sr, .9)})
    rows.sort(key=lambda r: (r["mean"], len(r["open"]), r["board"]))
    return {"rows": rows, "runs": runs, "mean_duty": mean_duty}


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


# ----------------------------------------------------------------------------- back-test
def backtest(inp, P, sites, red_sea="cape"):
    """What the model says about what happened: (1) Mar-Nov 2025, China-made laptops paid 20% more
    in the US: where does US volume go with a Vietnam line, boards imported or made there?
    (2) since Feb 2026 the China-specific gap is 0, yet volume stayed in Vietnam: with the Vietnam
    NRE already paid, what weight on a renewed China tariff makes staying the cheaper bet?"""
    us = next(m["weekly_units"] for m in inp["markets"] if m["market"] == "US")
    d = duty_matrix(inp, inp["scenarios"][0])
    d["USA"]["CN"] = 0.20
    shift = {}
    for board in (False, True):
        sv = with_boards(sites, ["CN", "VN"], board)
        ev = evaluate(inp, P, sv, ["CN", "VN"], red_sea, d)
        shift["own_boards" if board else "china_boards"] = ev["alloc"].get("VN|US", 0.0) / us
    sv = with_boards(sites, ["CN", "VN"], True)
    sv["VN"] = dict(sv["VN"], nre=0.0, buy_price=0.0)       # already paid
    mats = [duty_matrix(inp, s) for s in inp["scenarios"]]
    _, c_stay, _ = yearly_costs(inp, P, sv, ["CN", "VN"], red_sea, mats)
    _, c_back, _ = yearly_costs(inp, P, sv, ["CN"], red_sea, mats)
    ids = [s["id"] for s in inp["scenarios"]]
    k = ids.index("cn301")
    w = [s["probability"] for s in inp["scenarios"]]
    rest = ssum(x for i, x in enumerate(w) if i != k) or 1.0
    e = lambda c, p: p * c[k] + (1 - p) * ssum(w[i] * c[i] for i in range(len(c)) if i != k) / rest
    a0, a1, b0, b1 = e(c_stay, 0), e(c_stay, 1), e(c_back, 0), e(c_back, 1)
    den = (a0 - b0) - (a1 - b1)
    implied = None if abs(den) < 1e-9 else max(0.0, min(1.0, (a0 - b0) / den))
    return {"shift_2025": shift, "implied_weight_2026": implied}


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
              f" (ramp-up {P['ramp_months_odm']:.0f} months on an ODM campus, {P['ramp_months_buy']:.0f} for a bought plant)")
    mc = duty_monte_carlo(inp, P, sites, "cape", runs=200)
    print(f"\n== Duty ranges, {mc['runs']} Monte Carlo draws (US up to its April 2025 peak,"
          f" change probability {P['duty_change_prob']:.0%} per market)")
    print(f"  {'open sites':<26}{'mean':>9}{'P10':>9}{'P90':>9}{'cheapest':>10}{'regret':>9}{'P90 reg':>9}")
    for r in mc["rows"][:8]:
        name = "+".join(r["open"]) + (" (boards)" if r["board"] else "")
        print(f"  {name:<26}{r['mean'] / 1e6:>8.2f}M{r['p10'] / 1e6:>8.2f}M{r['p90'] / 1e6:>8.2f}M"
              f"{r['win']:>10.0%}{r['regret_mean'] / 1e6:>8.2f}M{r['regret_p90'] / 1e6:>8.2f}M")
    print("  mean drawn US duty: " + ", ".join(f"{k.split('|')[1]} {v:.1%}" for k, v in mc["mean_duty"].items()))
    bt = backtest(inp, P, sites)
    print("\n== Back-test against US import data (data/us_import_history.csv)")
    print(f"  2025, China-made laptops +20% in the US: share of US volume the model moves to Vietnam = "
          f"{bt['shift_2025']['own_boards']:.0%} with boards made there, {bt['shift_2025']['china_boards']:.0%} with China-made boards"
          f"  (actual: about 60% of US laptop imports from Vietnam in 2025, 68% in May-Jul 2026)")
    print(f"  2026, no China-specific gap, Vietnam NRE already paid: staying beats moving back once the weight on a renewed"
          f" China tariff exceeds {bt['implied_weight_2026']:.0%} (actual: volume stayed; the model's default weight is"
          f" {[s['probability'] for s in inp['scenarios'] if s['id'] == 'cn301'][0] / ssum(s['probability'] for s in inp['scenarios']):.0%})")
    print("\n  weight on 'US 25% on China-made laptops' above which building now beats waiting:")
    for r in rows[:6]:
        if r["is_base"]:
            continue
        tw = tipping_weight(r, inp["scenarios"], "cn301", P["horizon_years"])
        name = "+".join(r["open"]) + (" (boards)" if r["board"] else "")
        print(f"    {name:<24} {'never' if tw is None else f'{tw * 100:.0f}%'}")

if __name__ == "__main__":
    main()
