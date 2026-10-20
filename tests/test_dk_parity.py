"""
Check that the browser engine (src/dash/dk_engine.js) reproduces src/demand_kpi.py exactly:
every option's figures (with the second-half catch-up), both picks and the disagreement grid,
under several parameter sets.
Needs Node.js; skipped if missing.

Run:  python3 tests/test_dk_parity.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import demand_kpi as DK  # noqa: E402

VARIANTS = [{}, {"passthrough": 0.4, "reprice_lag_weeks": 5, "ramp_weeks": 20, "mwd_transferability": 1},
            {"tariff_cn": 0.45, "target_tolerance": 0.93, "exporter_absorb": 0.1, "ramp_weeks": 0},
            {"max_promo_discount": 0.2, "catchup_from_week": 13, "target_tolerance": 1.02},
            {"company_holds_target": 0, "max_promo_discount": 0.0},
            {"bu_funds_support": 0.3, "target_tolerance": 0.99, "max_promo_discount": 0.15},
            {"mwd_transferability": 0.2, "mwd_cost_rate": 0.4, "points_effect": 0.6, "max_promo_discount": 0.25}]
BG = ("mwd_cost_rate", [0.0, 0.5, 1.0, 1.5], "mwd_transferability", [0.0, 0.5, 1.0])
TS, PS = [0.0, 0.15, 0.3, 0.5], [0.0, 0.5, 1.0]

JS = """
const DKE = require(process.argv[2]);
const inp = JSON.parse(require('fs').readFileSync(process.argv[3], 'utf8'));
const V = JSON.parse(process.argv[4]), TS = JSON.parse(process.argv[5]), PS = JSON.parse(process.argv[6]), BG = JSON.parse(process.argv[7]);
const out = V.map((v) => {
  const P = { ...inp.P, ...v };
  const s = DKE.score(inp, P);
  return { rows: s.rows.map((r) => [r.units, r.attainment, r.bu_mwd, r.company_cost, r.parts.absorbed, r.parts.lost_margin,
      r.parts.chain, r.parts.conversion, r.weekly[3], r.weekly[30], r.discount, r.before_catch_up, r.parts.promotion,
      r.quarters[0][1], r.quarters[3][1], r.bu_cost]), picks: [s.bu, s.company], gap: s.gap,
    grid: DKE.grid(inp, P, TS, PS).flat().map((c) => [c.bu, c.company, c.gap]),
    bg: DKE.buGrid(inp, P, BG[0], BG[1], BG[2], BG[3]).flat() };
});
process.stdout.write(JSON.stringify(out));
"""


def main(tol=1e-9):
    node = shutil.which("node")
    if not node:
        print("node not found: parity test skipped")
        return 0
    inp = DK.dk_input()
    with tempfile.TemporaryDirectory() as d:
        jf, sf = os.path.join(d, "inp.json"), os.path.join(d, "run.js")
        with open(jf, "w") as f:
            json.dump(inp, f)
        with open(sf, "w") as f:
            f.write(JS)
        js = json.loads(subprocess.run([node, sf, os.path.join(ROOT, "src", "dash", "dk_engine.js"), jf,
                                        json.dumps(VARIANTS), json.dumps(TS), json.dumps(PS), json.dumps(BG)],
                                       capture_output=True, text=True, check=True).stdout)
    worst, bad, n = 0.0, 0, 0
    for v, J in zip(VARIANTS, js):
        P = {**inp["P"], **v}
        s = DK.score(inp, P)
        py_rows = [[r["units"], r["attainment"], r["bu_mwd"], r["company_cost"], r["parts"]["absorbed"],
                    r["parts"]["lost_margin"], r["parts"]["chain"], r["parts"]["conversion"], r["weekly"][3],
                    r["weekly"][30], r["discount"], r["before_catch_up"], r["parts"]["promotion"],
                    r["quarters"][0][1], r["quarters"][3][1], r["bu_cost"]] for r in s["rows"]]
        py_grid = [[c["bu"], c["company"], c["gap"]] for row in DK.grid(inp, P, TS, PS) for c in row]
        pairs = [(a, b) for ra, rb in zip(py_rows, J["rows"]) for a, b in zip(ra, rb)]
        pairs += list(zip([s["bu"], s["company"], s["gap"]], J["picks"] + [J["gap"]]))
        pairs += [(a, b) for ra, rb in zip(py_grid, J["grid"]) for a, b in zip(ra, rb)]
        pairs += list(zip([c for row in DK.bu_grid(inp, P, *BG) for c in row], J["bg"]))
        for a, b in pairs:
            n += 1
            if isinstance(a, str):
                if a != b:
                    bad += 1
                    print("MISMATCH", v, a, b)
                continue
            rel = abs(a - b) / max(1.0, abs(a))
            worst = max(worst, rel)
            if rel > tol:
                bad += 1
                print("MISMATCH", v, a, b)
    print(f"{n} values compared: worst relative difference {worst:.2e} -> {'OK' if not bad else str(bad) + ' mismatches'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
