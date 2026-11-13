"""
Check that the browser engine (src/dash/yr_engine.js) reproduces src/year_run.py: every cutover
option's company cost, BU cost and attainment, the four strategies' picks, cost by kind, quarters
and cumulative cost, and the Module 6 ramp it uses, at several tariffs, GSMs, input overrides and
both memory price levels. Needs Node.js.

Run:  python3 tests/test_yr_parity.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import mwd_engine as E  # noqa: E402
import year_run as YR  # noqa: E402

VARIANTS = [  # (memory level, tariff, gsm, Module 5 overrides, Module 6 overrides)
    (0, 0.25, 1, {}, {"ramp_runs": 300}),
    (0, 0.10, 0, {"passthrough": 0.5, "absorb_prob": 0.0}, {"ramp_runs": 300}),
    (1, 0.40, 1, {"target_tolerance": 1.0, "max_promo_discount": 0.05}, {"ramp_runs": 300, "ramp_base_weeks": 20}),
    (1, 0.25, 0, {"company_holds_target": 0}, {"ramp_runs": 300, "pull_cost_usd_per_unit": 30}),
]

JS = """
const dir = process.argv[2];
global.DKE = require(dir + '/dk_engine.js'); global.RBE = require(dir + '/rb_engine.js');
const YRE = require(dir + '/yr_engine.js');
const ins = JSON.parse(require('fs').readFileSync(process.argv[3], 'utf8'));
const V = JSON.parse(process.argv[4]);
const out = V.map(([lv, t, g, p5, p6]) => {
  const inp = ins[lv];
  const y = YRE.runYear(inp, t, g, { ...inp.dk.P, ...p5 }, { ...inp.rb.P, ...p6 });
  return [y.pull, y.T50, y.T90].concat(...y.options.map((o) => [o.company_cost, o.bu_cost, o.attainment]),
    ...y.strategies.map((s) => [s.cutover === null ? -1 : s.cutover, s.discount, s.cumulative[25], s.cumulative[51]]
      .concat(YRE.CATS.map((k) => s.totals[k]), ...s.quarters)));
});
process.stdout.write(JSON.stringify(out));
"""


def py_numbers(inp, t, g, p5, p6):
    y = YR.run_year(t, g, inp, {**inp["dk"]["P"], **p5}, {**inp["rb"]["P"], **p6})
    out = [y["pull"], y["T50"], y["T90"]]
    for o in y["options"]:
        out += [o["company_cost"], o["bu_cost"], o["attainment"]]
    for s in y["strategies"]:
        out += [-1 if s["cutover"] is None else s["cutover"], s["discount"], s["cumulative"][25], s["cumulative"][51]]
        out += [s["totals"][k] for k in YR.CATS]
        for q in s["quarters"]:
            out += q
    return out


def main(tol=1e-9):
    node = shutil.which("node")
    if not node:
        print("node not found: parity test skipped")
        return 0
    ins = []
    for lv in (0, 1):
        with E.memory_market(lv):
            ins.append(YR.inputs())
    with tempfile.TemporaryDirectory() as d:
        jf, sf = os.path.join(d, "inp.json"), os.path.join(d, "run.js")
        with open(jf, "w") as f:
            json.dump(ins, f)
        with open(sf, "w") as f:
            f.write(JS)
        js = json.loads(subprocess.run([node, sf, os.path.join(ROOT, "src", "dash"), jf, json.dumps(VARIANTS)],
                                       capture_output=True, text=True, check=True).stdout)
    worst, bad, n = 0.0, 0, 0
    for v, J in zip(VARIANTS, js):
        P = py_numbers(ins[v[0]], *v[1:])
        if len(P) != len(J):
            print("LENGTH MISMATCH", v, len(P), len(J))
            return 1
        for a, b in zip(P, J):
            n += 1
            rel = abs(a - b) / max(1.0, abs(a))
            worst = max(worst, rel)
            if rel > tol:
                bad += 1
                print("MISMATCH", v, a, b)
    print(f"{n} values compared: worst relative difference {worst:.2e} -> {'OK' if not bad else str(bad) + ' mismatches'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
