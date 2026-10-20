"""
Check that the browser engine (src/dash/rb_engine.js) reproduces src/ramp_board.py exactly:
the ramp sweep (ramp weeks, costs, the share band) and the board-cover Monte Carlo (costs by
cover, P90, stranded boards, the recommended cover) under several parameter sets. Needs Node.js.

Run:  python3 tests/test_rb_parity.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import ramp_board as RB  # noqa: E402

VARIANTS = [{}, {"gsm_strong": 0, "ramp_tariff": 0.1, "ramp_runs": 300, "board_runs": 150},
            {"pull_cost_usd_per_unit": 40, "slip_supplier_prob": 0.9, "board_cover_std_weeks": 6,
             "smt_flex": 0.05, "ramp_runs": 300, "board_runs": 150}]

JS = """
const RBE = require(process.argv[2]);
const inp = JSON.parse(require('fs').readFileSync(process.argv[3], 'utf8'));
const V = JSON.parse(process.argv[4]);
const out = V.map((v) => {
  const P = { ...inp.P, ...v };
  const r = RBE.rampSweep(inp, P);
  const b = RBE.boards(inp, P);
  return { ramp: r.rows.map((x) => [x.T_mean, x.T_p10, x.T_p50, x.T_p90, x.leakage, x.scrap, x.pull_cost, x.total,
      x.band[5][0], x.band[10][1], x.band[15][2]]).concat([[r.best], r.slip_share, r.slip_mean]),
    boards: b.map((m) => m.rows.map((x) => [x.total, x.p90, x.stranded_boards, x.parts.setups, x.parts.rush,
      x.parts.lost, x.parts.carry, x.parts.stranded]).concat([[m.best]])) };
});
process.stdout.write(JSON.stringify(out));
"""


def main(tol=1e-9):
    node = shutil.which("node")
    if not node:
        print("node not found: parity test skipped")
        return 0
    inp = RB.rb_input()
    with tempfile.TemporaryDirectory() as d:
        jf, sf = os.path.join(d, "inp.json"), os.path.join(d, "run.js")
        with open(jf, "w") as f:
            json.dump(inp, f)
        with open(sf, "w") as f:
            f.write(JS)
        js = json.loads(subprocess.run([node, sf, os.path.join(ROOT, "src", "dash", "rb_engine.js"), jf,
                                        json.dumps(VARIANTS)], capture_output=True, text=True, check=True).stdout)
    worst, bad, n = 0.0, 0, 0
    for v, J in zip(VARIANTS, js):
        P = {**inp["P"], **v}
        r = RB.ramp_sweep(inp, P)
        ramp = [[x["T_mean"], x["T_p10"], x["T_p50"], x["T_p90"], x["leakage"], x["scrap"], x["pull_cost"], x["total"],
                 x["band"][5][0], x["band"][10][1], x["band"][15][2]] for x in r["rows"]] + [[r["best"]], r["slip_share"],
                                                                                         r["slip_mean"]]
        bd = [[[x["total"], x["p90"], x["stranded_boards"], x["parts"]["setups"], x["parts"]["rush"], x["parts"]["lost"],
                x["parts"]["carry"], x["parts"]["stranded"]] for x in m["rows"]] + [[m["best"]]] for m in RB.boards(inp, P)]
        pairs = [(a, b) for ra, rb in zip(ramp, J["ramp"]) for a, b in zip(ra, rb)]
        pairs += [(a, b) for ma, mb in zip(bd, J["boards"]) for ra, rb in zip(ma, mb) for a, b in zip(ra, rb)]
        for a, b in pairs:
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
