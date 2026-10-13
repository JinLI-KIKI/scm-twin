"""
MWD engine — Module 1 of the supply-chain twin.

Question it answers
-------------------
"A block of plans is cancelled (or a region's production leaves this factory).
 For every material that was planned for it: how much is absorbed by other
 plans, how much is reworked, how much becomes MWD — and what does each cost?"

Business rules encoded (see docs/ASSUMPTIONS.md for status of each)
-------------------------------------------------------------------
R1  Plans cancelled inside the liability window (16 weeks) create a liability
    for the full BOM, whether or not the ODM actually stocked the material.
R2  Same part number used by other plans -> freed stock is netted against their
    future requirements (MRP netting), so the factory simply buys less.
    Not MWD, but it carries holding + ageing cost until consumed.
R3  Freed stock is netted by pushing out / cancelling other plans' open POs.
    Pushing out only moves timing; what decides MWD is how much of the order
    book is NON-CANCELLABLE. So netting offsets demand beyond each material's
    non-cancellable window (cancel_window_weeks).          [practitioner input]
R10 Shared ODMs: industry-standard parts (CPU, memory, SSD, panel) are bought by
    other brands too, so ODM/supplier can redeploy them -> short window.
    Custom parts (battery pack, housing, keyboard) -> window = full lead time.
R4  Consumption is tracked for up to 36 months (tracking window, adjustable);
    in practice demand stops earlier at model EOL / platform collective EOL.
R5  NPI models absorb old material only if their BOM uses the same part number.
R6  Route class 2 (convertible) remainder can be reworked at a cost if another
    BU accepts it; route 1/3 remainder, and unaccepted route 2, become MWD.
R7  Ageing while waiting: battery = physical (recharge every 26 weeks),
    chips = policy (re-test past 2-year date code), others = obsolescence only.
R8  Two ledgers: claimed MWD (plan basis) vs physical MWD (what the ODM really
    holds). Gap = ODM hedging. Settled once per fiscal year.
"""
import csv
import math
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def _read(name):
    with open(os.path.join(DATA, name), newline="") as f:
        return list(csv.DictReader(f))


def load():
    mats = {r["material_id"]: {
        "name": r["name"],
        "route_class": int(r["route_class"]),
        "unit_cost": float(r["unit_cost_usd"]),
        "lead_time": int(r["lead_time_weeks"]),
        "decay": r["decay_type"],
        "rework_cost": float(r["rework_cost_usd"]),
        "industry_standard": int(r["industry_standard"]),
        "cancel_window": int(r["cancel_window_weeks"]),
        "on_board": int(r["on_board"]),
    } for r in _read("materials.csv")}

    platform_eol = {r["platform"]: int(r["collective_eol_week"]) for r in _read("platforms.csv")}

    models = {}
    for r in _read("models.csv"):
        eol = min(int(r["eol_week"]), platform_eol[r["platform"]])  # collective EOL wins
        models[r["model"]] = {
            "platform": r["platform"],
            "npi": int(r["npi_week"]),
            "eol": eol,
            "peak": float(r["peak_weekly_units"]),
            "up": int(r["ramp_up_weeks"]),
            "down": int(r["ramp_down_weeks"]),
            "customs_value": float(r["customs_value_usd"]),
            "board_extra": float(r["board_extra_usd"]),
        }

    locales = {r["locale"]: float(r["share"]) for r in _read("locales.csv")}

    bom = defaultdict(dict)          # sku -> {material: qty}
    used_by = defaultdict(list)      # material -> [sku]
    for r in _read("bom.csv"):
        bom[r["sku"]][r["material_id"]] = float(r["qty_per"])
        used_by[r["material_id"]].append(r["sku"])

    params = {r["key"]: float(r["value"]) for r in _read("params.csv")}
    return mats, models, locales, bom, used_by, params


# --------------------------------------------------------------------------- #
# Demand
# --------------------------------------------------------------------------- #
def model_weekly_demand(m, w):
    """Lifecycle curve: ramp-up after NPI, flat, ramp-down into EOL."""
    if w < m["npi"] or w >= m["eol"]:
        return 0.0
    level = m["peak"]
    if w < m["npi"] + m["up"]:
        level *= (w - m["npi"] + 1) / m["up"]
    if w >= m["eol"] - m["down"]:
        level *= min(1.0, (m["eol"] - w) / m["down"])
    return level


def sku_demand(sku, w, models, locales):
    model, loc = sku.rsplit("_", 1)
    return model_weekly_demand(models[model], w) * locales[loc]


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #
def run_event(event, data=None):
    """
    event = {
      "name": str,
      "cancel": callable(sku) -> bool   # which SKUs lose their plans
      "cancel_weeks": int               # weeks 0..n-1 cancelled (<= liability window)
      "future_gone": bool               # True if these SKUs never come back here (factory transfer)
      "overrides": {...}                # optional: {"platform_eol": {"P1": 20}, "params": {...}}
    }
    """
    mats, models, locales, bom, used_by, params = data or load()

    # optional what-if overrides (do not touch the CSVs)
    ov = event.get("overrides", {})
    if "platform_eol" in ov:
        models = {k: dict(v) for k, v in models.items()}
        for k, v in models.items():
            if v["platform"] in ov["platform_eol"]:
                v["eol"] = min(v["eol"], ov["platform_eol"][v["platform"]])
    if "npi_week" in ov:
        for k, wk in ov["npi_week"].items():
            models[k]["npi"] = wk
    params = {**params, **ov.get("params", {})}

    window = int(params["liability_window_weeks"])
    horizon = int(params["tracking_window_weeks"])
    n_cancel = min(int(event["cancel_weeks"]), window)
    hit = [s for s in bom if event["cancel"](s)]

    # 1) Explode cancelled plans into freed material
    freed = defaultdict(float)
    for s in hit:
        units = sum(sku_demand(s, w, models, locales) for w in range(n_cancel))
        for mat, q in bom[s].items():
            freed[mat] += units * q

    def available_demand(sku, w):
        if sku in hit and (event["future_gone"] or w < n_cancel):
            return 0.0
        return sku_demand(sku, w, models, locales)

    rows = []
    for mat, qty in sorted(freed.items()):
        info = mats[mat]
        # R3/R10: offset only demand beyond the non-cancellable window.
        # event "netting_rule": "cancel_window" (practitioner rule) | "lead_time" (old v0 assumption)
        rule = event.get("netting_rule", "cancel_window")
        start = info["cancel_window"] if rule == "cancel_window" else info["lead_time"]
        remaining = qty
        absorbed, holding, ageing = 0.0, 0.0, 0.0
        last_week = None
        for w in range(start, horizon):
            if remaining <= 1e-9:
                break
            need = sum(available_demand(s, w) * bom[s][mat] for s in used_by[mat])
            take = min(need, remaining)
            if take <= 0:
                continue
            remaining -= take
            absorbed += take
            last_week = w
            holding += take * info["unit_cost"] * params["carrying_rate_annual"] * w / 52
            if info["decay"] == "physical":
                ageing += take * params["battery_recharge_cost_usd"] * \
                    math.floor(w / params["battery_recharge_interval_weeks"])
            elif info["decay"] == "policy" and w > params["date_code_limit_weeks"]:
                ageing += take * params["retest_cost_usd"]

        reworked = rework_cost = 0.0
        if info["route_class"] == 2 and remaining > 0:
            reworked = remaining * params["rework_accept_rate"]
            rework_cost = reworked * info["rework_cost"]
            remaining -= reworked

        mwd_qty = remaining
        mwd_claimed = mwd_qty * info["unit_cost"]
        rows.append({
            "material": mat,
            "route_class": info["route_class"],
            "industry_standard": info["industry_standard"],
            "netting_start_week": start,
            "freed_qty": qty,
            "absorbed_qty": absorbed,
            "absorb_done_week": last_week,
            "reworked_qty": reworked,
            "mwd_qty": mwd_qty,
            "freed_usd": qty * info["unit_cost"],
            "holding_usd": holding,
            "ageing_usd": ageing,
            "rework_usd": rework_cost,
            "mwd_claimed_usd": mwd_claimed,
            "mwd_physical_usd": mwd_claimed * (1 - params["odm_hedge_ratio"]),
        })
        # conservation check: every freed unit ends up somewhere
        assert abs(qty - absorbed - reworked - mwd_qty) < 1e-6, mat
    return rows


def summarize(rows):
    keys = ["freed_usd", "holding_usd", "ageing_usd", "rework_usd",
            "mwd_claimed_usd", "mwd_physical_usd"]
    out = {k: sum(r[k] for r in rows) for k in keys}
    for rc in (1, 2, 3):
        out[f"mwd_class{rc}_usd"] = sum(r["mwd_claimed_usd"] for r in rows if r["route_class"] == rc)
    out["total_cost_usd"] = (out["holding_usd"] + out["ageing_usd"] +
                             out["rework_usd"] + out["mwd_claimed_usd"])
    return out


def write_rows(rows, path):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items()})
