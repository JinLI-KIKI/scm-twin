"""
Module 2 — factory transfer cutover timing.

Decision: one region's production moves from the old factory (China) to a new
factory. At week 0 we decide the CUTOVER WEEK C:
  - plans for weeks < C are still built at the old factory -> China origin -> pay China tariff
  - plans for weeks C..W-1 (inside the W-week liability window, W = 16) are cancelled at the old
    factory -> their material is freed -> MWD exposure
  - plans beyond week W are not committed yet -> simply placed at the new factory

What happens to freed material (rules in docs/ASSUMPTIONS.md):
  R13 boards already built (SMT runs `boards_built_ahead_weeks` ahead) are origin-locked:
      usable only for the old factory's other-region builds of the same model, else scrapped
  R2/R3 loose common parts: netted against the old factory's other plans first
  R14 loose parts the old factory cannot use: relocated to the new factory (its local supply
      base is incomplete, so China parts flow there anyway); they keep the new site's origin
      because SMT and base-unit assembly happen there
  R6  convertible leftovers reworked; everything else -> MWD
"""
import os
from collections import defaultdict

import mwd_engine as E

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _absorb(qty, start, horizon, need_fn, unit_cost, carrying):
    """FIFO-consume qty against weekly need from `start`. Returns absorbed, holding cost."""
    absorbed = holding = 0.0
    for w in range(start, horizon):
        if qty - absorbed <= 1e-9:
            break
        take = min(need_fn(w), qty - absorbed)
        if take > 0:
            absorbed += take
            holding += take * unit_cost * carrying * w / 52
    return absorbed, holding


def run_transfer(region, cutover, tariff_old, tariff_new=0.0, relocate=True,
                 overrides=None, data=None):
    mats, models, locales, bom, used_by, params = data or E.load()
    ov = overrides or {}
    if "platform_eol" in ov:
        models = {k: dict(v) for k, v in models.items()}
        for v in models.values():
            if v["platform"] in ov["platform_eol"]:
                v["eol"] = min(v["eol"], ov["platform_eol"][v["platform"]])
    params = {**params, **ov.get("params", {})}

    window = int(params["liability_window_weeks"])
    horizon = int(params["tracking_window_weeks"])
    ahead = int(params["boards_built_ahead_weeks"])
    reloc_wk = int(params["relocation_weeks"])
    carry = params["carrying_rate_annual"]
    dem = lambda s, w: E.sku_demand(s, w, models, locales)
    model_of = lambda s: s.rsplit("_", 1)[0]

    order = [s for s in bom if s.endswith("_" + region)]   # iterate a list: same sum order on every run
    hit = set(order)                                         # membership tests only

    # ---- tariff inside the liability window (weeks beyond are identical for every C)
    tariff = 0.0
    for s in order:
        v = models[model_of(s)]["customs_value"]
        for w in range(window):
            rate = tariff_old if w < cutover else tariff_new
            tariff += dem(s, w) * v * rate

    # ---- freed material: cancelled plans at the old factory, weeks C..window-1
    freed_loose = defaultdict(float)
    freed_boards = defaultdict(float)          # model -> boards already built
    for s in order:
        for w in range(cutover, window):
            u = dem(s, w)
            built = w < ahead
            if built:
                freed_boards[model_of(s)] += u
            for mat, q in bom[s].items():
                if built and mats[mat]["on_board"]:
                    continue                   # sits on a built board, handled below
                freed_loose[mat] += u * q

    old_need = lambda mat: (lambda w: sum(dem(s, w) * bom[s][mat]
                                          for s in used_by[mat] if s not in hit))
    new_need = lambda mat: (lambda w: sum(dem(s, w) * bom[s][mat]
                                          for s in used_by[mat] if s in hit))

    out = {"cutover": cutover, "tariff": tariff, "holding": 0.0, "relocation": 0.0,
           "rework": 0.0, "mwd_boards": 0.0, "mwd_loose": 0.0,
           "relocated_usd": 0.0, "freed_usd": 0.0}

    # ---- built boards: origin-locked; only other-region builds of the same model can use them
    for model, n in freed_boards.items():
        sku_any = next(s for s in bom if model_of(s) == model)
        board_val = models[model]["board_extra"] + sum(
            mats[m]["unit_cost"] * q for m, q in bom[sku_any].items() if mats[m]["on_board"])
        need = lambda w, model=model: sum(dem(s, w) for s in bom
                                          if model_of(s) == model and s not in hit)
        absorbed, hold = _absorb(n, 0, horizon, need, board_val, carry)
        out["holding"] += hold
        out["mwd_boards"] += (n - absorbed) * board_val
        out["freed_usd"] += n * board_val

    # ---- loose material
    for mat, qty in freed_loose.items():
        info = mats[mat]
        out["freed_usd"] += qty * info["unit_cost"]
        a1, h1 = _absorb(qty, info["cancel_window"], horizon, old_need(mat),
                         info["unit_cost"], carry)
        left = qty - a1
        a2 = h2 = 0.0
        if relocate and left > 0:
            a2, h2 = _absorb(left, max(cutover, reloc_wk), horizon, new_need(mat),
                             info["unit_cost"], carry)
            out["relocation"] += a2 * info["unit_cost"] * params["relocation_cost_rate"]
            out["relocated_usd"] += a2 * info["unit_cost"]
            left -= a2
        out["holding"] += h1 + h2
        if info["route_class"] == 2 and left > 0:
            rw = left * params["rework_accept_rate"]
            out["rework"] += rw * info["rework_cost"]
            left -= rw
        out["mwd_loose"] += left * info["unit_cost"]

    out["mwd"] = out["mwd_boards"] + out["mwd_loose"]
    out["total"] = out["tariff"] + out["holding"] + out["relocation"] + out["rework"] + out["mwd"]
    return out


def chain_extension_cost(region="US", tariff_old=0.25, tariff_new=0.0, data=None):
    """
    R15 recurring cost of the longer chain (the part we can price today):
    extra in-transit / committed material = lead-time adder x weekly BOM value,
    carried all year. Compared with the tariff saved per year at full transfer.
    The forecast-error MWD part of R15 is NOT priced yet (needs Q13).
    """
    mats, models, locales, bom, used_by, params = data or E.load()
    adder = params["new_site_lt_adder_weeks"]
    carry = params["carrying_rate_annual"]
    hit = [s for s in bom if s.endswith("_" + region)]
    wk = 5  # a representative steady-state week (before ramp-down)
    units = {s: E.sku_demand(s, wk, models, locales) for s in hit}
    bom_val = sum(u * sum(mats[m]["unit_cost"] * q for m, q in bom[s].items())
                  for s, u in units.items())
    cust_val = sum(u * models[s.rsplit("_", 1)[0]]["customs_value"] for s, u in units.items())
    return {
        "weekly_units": sum(units.values()),
        "extra_pipeline_usd": bom_val * adder,
        "pipeline_carry_per_year": bom_val * adder * carry,
        "tariff_saved_per_year": cust_val * 52 * (tariff_old - tariff_new),
    }


def sweep(region="US", tariff_old=0.25, tariff_new=0.0, relocate=True, overrides=None):
    data = E.load()
    return [run_transfer(region, c, tariff_old, tariff_new, relocate, overrides, data)
            for c in range(0, int(data[5]['liability_window_weeks']) + 1)]


def print_sweep(title, rows):
    print(f"\n== {title}")
    print(f"{'C':>3}{'tariff $':>13}{'MWD boards':>12}{'MWD loose':>12}{'relocate $':>12}"
          f"{'hold+rework':>13}{'TOTAL $':>13}")
    best = min(rows, key=lambda r: r["total"])
    for r in rows:
        mark = "  <- best" if r is best else ""
        print(f"{r['cutover']:>3}{r['tariff']:>13,.0f}{r['mwd_boards']:>12,.0f}{r['mwd_loose']:>12,.0f}"
              f"{r['relocation']:>12,.0f}{r['holding'] + r['rework']:>13,.0f}{r['total']:>13,.0f}{mark}")


if __name__ == "__main__":
    print_sweep("China tariff 0% (current US rate on laptops), relocation ON",
                sweep(tariff_old=0.0))
    print_sweep("China tariff 25% (hypothetical), relocation ON",
                sweep(tariff_old=0.25))
    print_sweep("China tariff 25% (hypothetical), relocation OFF",
                sweep(tariff_old=0.25, relocate=False))
    for t in (0.10, 0.25):
        c = chain_extension_cost(tariff_old=t)
        print(f"\n== Longer chain (+lead time) vs tariff saved, China tariff {t:.0%}")
        print(f"  US weekly units           {c['weekly_units']:>14,.0f}")
        print(f"  extra pipeline inventory  {c['extra_pipeline_usd']:>14,.0f}")
        print(f"  its carrying cost / year  {c['pipeline_carry_per_year']:>14,.0f}")
        print(f"  tariff saved / year       {c['tariff_saved_per_year']:>14,.0f}")
