"""
Check that the browser engine (src/dash/fp_engine.js) reproduces src/footprint.py exactly:
landed costs, allocations (with minimum loads), the footprint ranking with board variants and
the build-now value, and the break-even duties. Needs Node.js; skipped if missing.

Run:  python3 tests/test_fp_parity.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import footprint as FP  # noqa: E402

JS = """
const FPE = require(process.argv[2]);
const inp = JSON.parse(require('fs').readFileSync(process.argv[3], 'utf8'));
const out = { landed: [], evals: [], be: [], fps: null };
for (const s of inp.scenarios) {
  const d = FPE.dutyMatrix(inp, s);
  for (const mode of ['sea', 'air']) for (const rs of ['cape', 'suez']) {
    const t = FPE.landedTable(inp, inp.P, inp.sites, mode, rs, d);
    out.landed.push(inp.origins.map((o) => t[o].map((c) => c.total)));
  }
  for (const open of [['CN'], ['CN', 'VN'], inp.origins, ['ID', 'VN', 'MY', 'BR', 'AE']]) {
    for (const board of [false, true]) {
      const sv = FPE.withBoards(inp.sites, open, board);
      const e = FPE.evaluate(inp, inp.P, sv, open, 'cape', d);
      out.evals.push([e.weekly_cost, e.weekly_duty, e.avg_days, e.unmet, e.underload]);
    }
  }
  for (const board of [false, true]) {
    const be = FPE.breakEven(inp, inp.P, FPE.withBoards(inp.sites, inp.origins, board), 'suez', d);
    out.be.push(inp.origins.filter((o) => o !== 'CN').map((o) => be[o].map((v) => v === null ? -1 : v)));
  }
}
const fpRows = (P) => FPE.footprints(inp, P, inp.sites, 'cape').slice(0, 20).map((r) => {
  const tw = FPE.tippingWeight(r, inp.scenarios, 'cn301', P.horizon_years);
  return [r.open.join('+') + (r.board ? '/b' : ''), r.expected, r.regret, r.wait, r.build_now_value, tw === null ? -1 : tw];
});
out.fps = fpRows(inp.P).concat(fpRows({ ...inp.P, board_origin_weight: 0.5, ramp_months: 18 }));
const stress = {};
for (const m of inp.markets) for (const o of inp.origins) stress[`${m.tkey}|${o}`] = [0, inp.ranges[`USA|${o}`][1]];
out.mc = [];
for (const [rg, p, seed] of [[inp.ranges, 0.2, 7], [stress, 0.5, 3]]) {
  const r = FPE.dutyMonteCarlo(inp, { ...inp.P, duty_change_prob: p }, inp.sites, 'cape', rg, 24, seed);
  out.mc.push(r.rows.map((x) => [x.open.join('+') + (x.board ? '/b' : ''), x.mean, x.p10, x.p90, x.win, x.regret_mean, x.regret_p90])
    .concat([Object.values(r.mean_duty)]));
}
process.stdout.write(JSON.stringify(out));
"""


def main(tol=1e-9):
    node = shutil.which("node")
    if not node:
        print("node not found: parity test skipped")
        return 0
    inp = FP.fp_input()
    with tempfile.TemporaryDirectory() as d:
        jf, sf = os.path.join(d, "inp.json"), os.path.join(d, "run.js")
        with open(jf, "w") as f:
            json.dump(inp, f)
        with open(sf, "w") as f:
            f.write(JS)
        js = json.loads(subprocess.run([node, sf, os.path.join(ROOT, "src", "dash", "fp_engine.js"), jf],
                                       capture_output=True, text=True, check=True).stdout)
    py = {"landed": [], "evals": [], "be": [], "fps": None}
    for s in inp["scenarios"]:
        dm = FP.duty_matrix(inp, s)
        for mode in ("sea", "air"):
            for rs in ("cape", "suez"):
                t = FP.landed_table(inp, inp["P"], inp["sites"], mode, rs, dm)
                py["landed"].append([[c["total"] for c in t[o]] for o in inp["origins"]])
        for open_ in (["CN"], ["CN", "VN"], inp["origins"], ["ID", "VN", "MY", "BR", "AE"]):
            for board in (False, True):
                sv = FP.with_boards(inp["sites"], open_, board)
                e = FP.evaluate(inp, inp["P"], sv, open_, "cape", dm)
                py["evals"].append([e["weekly_cost"], e["weekly_duty"], e["avg_days"], e["unmet"], e["underload"]])
        for board in (False, True):
            be = FP.break_even(inp, inp["P"], FP.with_boards(inp["sites"], inp["origins"], board), "suez", dm)
            py["be"].append([[-1 if v is None else v for v in be[o]] for o in inp["origins"] if o != "CN"])

    def fp_rows(P):
        out = []
        for r in FP.footprints(inp, P, inp["sites"], "cape")[:20]:
            tw = FP.tipping_weight(r, inp["scenarios"], "cn301", P["horizon_years"])
            out.append(["+".join(r["open"]) + ("/b" if r["board"] else ""), r["expected"], r["regret"], r["wait"],
                        r["build_now_value"], -1 if tw is None else tw])
        return out
    py["fps"] = fp_rows(inp["P"]) + fp_rows({**inp["P"], "board_origin_weight": 0.5, "ramp_months": 18})
    stress = {f"{m['tkey']}|{o}": [0.0, inp["ranges"][f"USA|{o}"][1]] for m in inp["markets"] for o in inp["origins"]}
    py["mc"] = []
    for rg, p, seed in ((inp["ranges"], 0.2, 7), (stress, 0.5, 3)):
        r = FP.duty_monte_carlo(inp, {**inp["P"], "duty_change_prob": p}, inp["sites"], "cape", rg, 24, seed)
        py["mc"].append([["+".join(x["open"]) + ("/b" if x["board"] else ""), x["mean"], x["p10"], x["p90"], x["win"],
                          x["regret_mean"], x["regret_p90"]] for x in r["rows"]] + [list(r["mean_duty"].values())])
    worst, bad = 0.0, 0

    def cmp(a, b, label):
        nonlocal worst, bad
        if isinstance(a, str) or isinstance(b, str):
            if a != b:
                bad += 1
                print("MISMATCH", label, a, b)
            return
        rel = abs(a - b) / max(1.0, abs(a))
        worst = max(worst, rel)
        if rel > tol:
            bad += 1
            print("MISMATCH", label, a, b)

    for k, (A, B) in enumerate(zip(py["landed"], js["landed"])):
        for i, (ra, rb) in enumerate(zip(A, B)):
            for j, (a, b) in enumerate(zip(ra, rb)):
                cmp(a, b, f"landed[{k}][{i}][{j}]")
    for k, (A, B) in enumerate(zip(py["evals"], js["evals"])):
        for a, b in zip(A, B):
            cmp(a, b, f"eval[{k}]")
    for k, (A, B) in enumerate(zip(py["be"], js["be"])):
        for i, (ra, rb) in enumerate(zip(A, B)):
            for j, (a, b) in enumerate(zip(ra, rb)):
                cmp(a, b, f"break_even[{k}][{i}][{j}]")
    for k, (A, B) in enumerate(zip(py["fps"], js["fps"])):
        for a, b in zip(A, B):
            cmp(a, b, f"footprint[{k}]")
    nmc = 0
    for k, (A, B) in enumerate(zip(py["mc"], js["mc"])):
        if len(A) != len(B):
            bad += 1
            print("MISMATCH mc lengths", k)
        for i, (ra, rb) in enumerate(zip(A, B)):
            for a, b in zip(ra, rb):
                cmp(a, b, f"mc[{k}][{i}]")
                nmc += 1
    if len(py["fps"]) != len(js["fps"]) or len(py["evals"]) != len(js["evals"]):
        bad += 1
        print("MISMATCH lengths")
    n = sum(len(r) * len(r[0]) for r in py["landed"]) + len(py["evals"]) * 5 + len(py["fps"]) * 6 \
        + sum(len(r) * len(r[0]) for r in py["be"]) + nmc
    print(f"{n} numbers compared: worst relative difference {worst:.2e} -> {'OK' if not bad else str(bad) + ' mismatches'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
