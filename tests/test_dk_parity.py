"""
Check that the browser engine (src/dash/dk_engine.js) reproduces src/demand_kpi.py exactly:
every option's figures, both picks and the disagreement grid, under several parameter sets.
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

VARIANTS = [{}, {"passthrough": 0.4, "reprice_lag_weeks": 5, "ramp_weeks": 20, "bu_mwd_claimed": 0},
            {"tariff_cn": 0.45, "target_tolerance": 0.93, "exporter_absorb": 0.1, "ramp_weeks": 0}]
TS, PS = [0.0, 0.15, 0.3, 0.5], [0.0, 0.5, 1.0]

JS = """
const DKE = require(process.argv[2]);
const inp = JSON.parse(require('fs').readFileSync(process.argv[3], 'utf8'));
const V = JSON.parse(process.argv[4]), TS = JSON.parse(process.argv[5]), PS = JSON.parse(process.argv[6]);
const out = V.map((v) => {
  const P = { ...inp.P, ...v };
  const s = DKE.score(inp, P);
  return { rows: s.rows.map((r) => [r.units, r.attainment, r.bu_mwd, r.company_cost, r.parts.absorbed, r.parts.lost_margin,
      r.parts.chain, r.parts.conversion, r.weekly[3], r.weekly[30]]), picks: [s.bu, s.company], gap: s.gap,
    grid: DKE.grid(inp, P, TS, PS).flat().map((c) => [c.bu, c.company, c.gap]) };
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
                                        json.dumps(VARIANTS), json.dumps(TS), json.dumps(PS)],
                                       capture_output=True, text=True, check=True).stdout)
    worst, bad, n = 0.0, 0, 0
    for v, J in zip(VARIANTS, js):
        P = {**inp["P"], **v}
        s = DK.score(inp, P)
        py_rows = [[r["units"], r["attainment"], r["bu_mwd"], r["company_cost"], r["parts"]["absorbed"],
                    r["parts"]["lost_margin"], r["parts"]["chain"], r["parts"]["conversion"], r["weekly"][3],
                    r["weekly"][30]] for r in s["rows"]]
        py_grid = [[c["bu"], c["company"], c["gap"]] for row in DK.grid(inp, P, TS, PS) for c in row]
        pairs = [(a, b) for ra, rb in zip(py_rows, J["rows"]) for a, b in zip(ra, rb)]
        pairs += list(zip([s["bu"], s["company"], s["gap"]], J["picks"] + [J["gap"]]))
        pairs += [(a, b) for ra, rb in zip(py_grid, J["grid"]) for a, b in zip(ra, rb)]
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
