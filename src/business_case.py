"""
Module 3 — transfer business case under uncertainty (Monte Carlo).

Annual view of moving one region's production (default: US) from China to a new site in Indonesia.

  benefit   tariff saved = units x customs value x (China rate - new-site rate)
  recurring (R15/R18/R20, paid every year after transfer)
            + extra end-of-life MWD from the longer commitment window and worse forecast
            + carrying cost of 4 extra weeks of material in the chain
            + new-site conversion cost uplift (5-10%)
  one-time  (R16 + rush shortage, paid in the transfer year)
            + tariff still paid on volume the new factory cannot yet cover during ramp
            + expediting cost for parts while the +4 week lead time is not yet covered

End-of-life MWD logic (why the window matters):
  plans are committed W weeks ahead. When a platform hits EOL, the last W weeks of
  commitments were made on forecasts; over-forecast there has nowhere to go for parts
  that die with the platform (CPU, battery pack, housing, keyboard ...).
  Forecast error per week: sigma = MAPE * sqrt(pi/2)  (normal errors).
  Cumulative over-commit over W weeks, errors with pairwise correlation rho:
      E[max(0, sum e)] = sigma/sqrt(2 pi) * sqrt(W + rho W (W-1))   weeks of volume
  rho = 0 -> errors cancel out (sqrt W); rho = 1 -> one systematic miss (W).

Every input is listed in docs/ASSUMPTIONS.md with its status.
"""
import math
import os
import random

import mwd_engine as E

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CASE = {
    # practitioner input (generalized)
    "fa_base": 0.68,                # forecast accuracy at the base window (virtualized)
    "fa_new": 0.60,                 # ~8 points worse at base + 4 weeks
    "window_old": 16,
    "window_new": 20,
    "conv_uplift": (0.05, 0.10),    # new-site labour + new line
    # placeholders
    "conv_cost_per_unit": 25.0,     # assembly/test conversion cost, China
    "eol_events_per_year": 1,       # collective platform EOLs per year
    "rho": (0.3, 0.9),              # week-to-week forecast-error correlation range
    "ramp_weeks": {"strong": (8, 16), "weak": (16, 30)},   # GSM-dependent
    "expedite_cost_per_unit": {"strong": 6.0, "weak": 12.0},
}


def _sigma(fa):
    return (1 - fa) * math.sqrt(math.pi / 2)


def _overcommit_weeks(sigma, W, rho):
    return sigma / math.sqrt(2 * math.pi) * math.sqrt(W + rho * W * (W - 1))


def region_profile(region="US", data=None):
    """Steady-state weekly units, customs value, BOM value and EOL-locked value."""
    mats, models, locales, bom, used_by, params = data or E.load()
    hit = [s for s in bom if s.endswith("_" + region)]
    wk = 5
    units = {s: E.sku_demand(s, wk, models, locales) for s in hit}
    units = {s: u for s, u in units.items() if u > 0}
    model_of = lambda s: s.rsplit("_", 1)[0]
    platform_of = lambda s: models[model_of(s)]["platform"]

    def dies_with_platform(mat, platform):
        # a part is locked at EOL if no model on another platform uses it
        return all(platform_of(s) == platform for s in used_by[mat])

    customs = sum(u * models[model_of(s)]["customs_value"] for s, u in units.items())
    bom_val = sum(u * sum(mats[m]["unit_cost"] * q for m, q in bom[s].items())
                  for s, u in units.items())
    locked = sum(u * sum(mats[m]["unit_cost"] * q for m, q in bom[s].items()
                         if dies_with_platform(m, platform_of(s)))
                 for s, u in units.items())
    return {"weekly_units": sum(units.values()), "weekly_customs": customs,
            "weekly_bom": bom_val, "weekly_locked": locked,
            "carry": params["carrying_rate_annual"],
            "lt_adder": params["new_site_lt_adder_weeks"]}


def simulate(tariff_old, tariff_new=0.0, gsm="strong", n=5000, region="US", seed=7):
    rng = random.Random(seed)
    p = region_profile(region)
    c = CASE
    s_old, s_new = _sigma(c["fa_base"]), _sigma(c["fa_new"])
    units_yr = p["weekly_units"] * 52
    tariff_saved = p["weekly_customs"] * 52 * (tariff_old - tariff_new)
    pipeline = p["weekly_bom"] * p["lt_adder"] * p["carry"]

    out = []
    for _ in range(n):
        rho = rng.uniform(*c["rho"])
        uplift = rng.uniform(*c["conv_uplift"])
        ramp = rng.uniform(*c["ramp_weeks"][gsm])
        eol_mwd = (_overcommit_weeks(s_new, c["window_new"], rho) -
                   _overcommit_weeks(s_old, c["window_old"], rho)) * p["weekly_locked"] \
            * c["eol_events_per_year"]
        conv = units_yr * c["conv_cost_per_unit"] * uplift
        recurring = eol_mwd + pipeline + conv
        ramp_leak = 0.5 * ramp * p["weekly_customs"] * (tariff_old - tariff_new)
        expedite = p["weekly_units"] * p["lt_adder"] * c["expedite_cost_per_unit"][gsm]
        one_time = ramp_leak + expedite
        out.append({"tariff_saved": tariff_saved, "eol_mwd": eol_mwd, "pipeline": pipeline,
                    "conv": conv, "recurring": recurring, "ramp_leak": ramp_leak,
                    "expedite": expedite, "one_time": one_time,
                    "net_steady": tariff_saved - recurring,
                    "net_year1": tariff_saved - recurring - one_time})
    return out


def pct(vals, q):
    v = sorted(vals)
    return v[int(q * (len(v) - 1))]


def report(tariff_old, gsm):
    sims = simulate(tariff_old, gsm=gsm)
    col = lambda k: [s[k] for s in sims]
    mid = lambda k: pct(col(k), 0.5)
    print(f"\n== China tariff {tariff_old:.0%} -> Indonesia 0%, GSM {gsm}  (median, P10–P90 for net)")
    print(f"  tariff saved / yr        {mid('tariff_saved'):>13,.0f}")
    print(f"  - extra EOL MWD / yr     {mid('eol_mwd'):>13,.0f}")
    print(f"  - pipeline carry / yr    {mid('pipeline'):>13,.0f}")
    print(f"  - new-site conv. / yr    {mid('conv'):>13,.0f}")
    print(f"  = net, steady state      {mid('net_steady'):>13,.0f}   "
          f"[{pct(col('net_steady'), .1):,.0f} .. {pct(col('net_steady'), .9):,.0f}]")
    print(f"  - ramp tariff leakage    {mid('ramp_leak'):>13,.0f}")
    print(f"  - rush expediting        {mid('expedite'):>13,.0f}")
    print(f"  = net, transfer year     {mid('net_year1'):>13,.0f}   "
          f"[{pct(col('net_year1'), .1):,.0f} .. {pct(col('net_year1'), .9):,.0f}]")


def breakeven_tariff(gsm="strong"):
    """Lowest China tariff at which the median transfer-year net turns positive."""
    lo, hi = 0.0, 0.5
    for _ in range(30):
        mid = (lo + hi) / 2
        net = pct([s["net_year1"] for s in simulate(mid, gsm=gsm, n=1500)], 0.5)
        lo, hi = (mid, hi) if net < 0 else (lo, mid)
    return hi


if __name__ == "__main__":
    p = region_profile()
    print(f"US weekly units {p['weekly_units']:,.0f} | weekly BOM ${p['weekly_bom']:,.0f} | "
          f"weekly value locked at EOL ${p['weekly_locked']:,.0f}")
    for t in (0.10, 0.25):
        for g in ("strong", "weak"):
            report(t, g)
    for g in ("strong", "weak"):
        print(f"\nBreak-even China tariff (transfer year, median), GSM {g}: {breakeven_tariff(g):.1%}")
