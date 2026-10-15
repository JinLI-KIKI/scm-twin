"""
Check that the browser engine (src/dash/fg_engine.js) reproduces the Python model
(src/finished_goods.py) for the same seed. Needs Node.js; skipped if `node` is missing.

Run:  python3 tests/test_fg_parity.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import finished_goods as FG  # noqa: E402

KEYS = ["avoidable_cost_usd", "system_cost_usd", "excess_units", "lost_units", "mwd_usd",
        "price_protection_usd", "dealer_kept_units", "duty_sunk_usd", "sell_in_pre_launch_units"]
CASES = [(s, {}) for s in FG.STRATEGIES] + [
    ("lock", {"duty_override": {"US": 0.25}}),
    ("lock_push", {"duty_override": {"US": 0.25}, "ftz": True}),
]
JS = """
const FGE = require(process.argv[2]);
const job = JSON.parse(require('fs').readFileSync(process.argv[3], 'utf8'));
const out = job.cases.map((c) => FGE.simulate(job.input, job.input.P,
  { strategy: c.strategy, runs: job.runs, seed: job.seed, ftz: !!c.ftz, dutyOverride: c.duty_override }).summary);
process.stdout.write(JSON.stringify(out));
"""


def main(runs=40, seed=11, tol=1e-9):
    node = shutil.which("node")
    if not node:
        print("node not found: parity test skipped")
        return 0
    inp = FG.engine_input()
    job = {"input": inp, "runs": runs, "seed": seed,
           "cases": [{"strategy": s, **kw} for s, kw in CASES]}
    with tempfile.TemporaryDirectory() as d:
        jf, sf = os.path.join(d, "job.json"), os.path.join(d, "run.js")
        with open(jf, "w") as f:
            json.dump(job, f)
        with open(sf, "w") as f:
            f.write(JS)
        res = subprocess.run([node, sf, os.path.join(ROOT, "src", "dash", "fg_engine.js"), jf],
                             capture_output=True, text=True, check=True)
    js = json.loads(res.stdout)
    worst, fails = 0.0, 0
    for (s, kw), jsum in zip(CASES, js):
        py = FG.simulate(s, runs=runs, seed=seed, **kw)["summary"]
        for k in KEYS:
            for stat in ("mean", "p10", "p90"):
                a, b = py[k][stat], jsum[k][stat]
                rel = abs(a - b) / max(1.0, abs(a))
                worst = max(worst, rel)
                if rel > tol:
                    fails += 1
                    print(f"MISMATCH {s} {kw} {k}.{stat}: python {a:.6f} js {b:.6f}")
    print(f"{len(CASES)} cases x {len(KEYS)} metrics: worst relative difference {worst:.2e}"
          f" -> {'OK' if not fails else str(fails) + ' mismatches'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
