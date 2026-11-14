/* Module 6 engine for the browser: a line-by-line port of src/ramp_board.py.
   Same random numbers as src/prng.py; tests/test_rb_parity.py checks both give identical numbers. */
const RBE = (() => {
  function makeRng(seed) {
    let s = seed >>> 0;
    const random = () => {
      s = (s + 0x6D2B79F5) >>> 0;
      let t = s;
      t = Math.imul(t ^ (t >>> 15), t | 1) >>> 0;
      t = ((((t + (Math.imul(t ^ (t >>> 7), t | 61) >>> 0)) >>> 0)) ^ t) >>> 0;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
    return { random, gauss(mu = 0, sigma = 1) { const u1 = 1 - random(), u2 = random(); return mu + sigma * Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2); } };
  }
  const pct = (vals, q) => { const v = vals.slice().sort((a, b) => a - b); return v[Math.floor(q * (v.length - 1))]; };
  const smoothstep = (x) => { x = Math.min(1, Math.max(0, x)); return x * x * (3 - 2 * x); };

  // ---------------------------------------------------------------- Part A: ramp
  function rampSlips(inp, P, seed = 11) {
    const rng = makeRng(seed), mult = P.gsm_strong >= 0.5 ? P.gsm_mult_strong : P.gsm_mult_weak, out = [];
    for (let r = 0; r < Math.trunc(P.ramp_runs); r++) {
      const row = [];
      for (const g of ['material', 'yield', 'supplier']) {
        const u1 = rng.random(), u2 = rng.random();
        const base = g === 'supplier' && P.site_campus >= 0.5 ? P.slip_supplier_prob_campus : P[`slip_${g}_prob`];
        const p = Math.min(1, base * mult), lo = P[`slip_${g}_lo`], hi = P[`slip_${g}_hi`];
        row.push(u1 < p ? lo + (hi - lo) * u2 : 0);
      }
      out.push(row);
    }
    return out;
  }
  const YIELD_SHAPE = [0, 6 / 13, 10 / 13, 12 / 13, 1];   // 85 -> 91 -> 95 -> 97 -> 98% at quarter points (Q48)
  function yieldAt(P, w) {
    const x = P.yield_weeks_to_full > 0 ? Math.max(0, w / P.yield_weeks_to_full) * 4 : 4;
    let f;
    if (x >= 4) f = 1; else { const i = Math.trunc(x); f = YIELD_SHAPE[i] + (YIELD_SHAPE[i + 1] - YIELD_SHAPE[i]) * (x - i); }
    return P.yield_start + (P.yield_full - P.yield_start) * f;
  }
  const plannedT = (P, pull) => Math.max(P.ramp_min_weeks, P.ramp_base_weeks - pull);
  function pullCost(inp, P, pull) {             // Q48: only the volume brought forward is paid for
    const rg = inp.region, W = inp.ramp_weeks;
    const curve = (T) => { const c = []; for (let w = 0; w < W; w++) c.push(T > 0 ? smoothstep(w / T) : 1); return c; };
    let cost = 0, prev = curve(plannedT(P, 0));
    for (let i = 1; i <= Math.trunc(pull); i++) {
      const cur = curve(plannedT(P, i));
      let d = 0; for (let w = 0; w < W; w++) d += cur[w] - prev[w];
      cost += P.pull_cost_usd_per_unit * (1 + P.pull_cost_growth) ** (i - 1) * rg.weekly_units * d;
      prev = cur;
    }
    return cost;
  }
  function rampRun(inp, P, pull, slips, pcIn) {
    const rg = inp.region;
    let sl = 0; for (const x of slips) sl += x;
    const T = plannedT(P, pull) + Math.min(P.slip_cap_weeks, sl);
    const share = [];
    for (let w = 0; w < inp.ramp_weeks; w++) share.push(T > 0 ? smoothstep(w / T) : 1);
    let leak = 0, scrap = 0;
    share.forEach((s, w) => {
      leak += (1 - s) * rg.weekly_units * rg.customs * P.ramp_tariff;
      const y = yieldAt(P, w);
      scrap += s * rg.weekly_units * (1 / y - 1) * rg.bom * P.scrap_share_of_bom;
    });
    const pc = pcIn === undefined ? pullCost(inp, P, pull) : pcIn;
    return { T, share, leakage: leak, scrap, pull: pc, total: leak + scrap + pc };
  }
  function rampSweep(inp, P, seed = 11) {
    const slips = rampSlips(inp, P, seed);
    const top = Math.trunc(Math.max(0, P.ramp_base_weeks - P.ramp_min_weeks));
    const rows = [];
    for (let pull = 0; pull <= top; pull++) {
      const pc = pullCost(inp, P, pull);
      const runs = slips.map((s) => rampRun(inp, P, pull, s, pc)), n = runs.length;
      const mean = (k) => { let t = 0; for (const r of runs) t += r[k]; return t / n; };
      const Ts = runs.map((r) => r.T);
      const band = [];
      for (let w = 0; w < inp.ramp_weeks; w++) { const col = runs.map((r) => r.share[w]); band.push([pct(col, 0.1), pct(col, 0.5), pct(col, 0.9)]); }
      rows.push({ pull, T_mean: mean('T'), T_p10: pct(Ts, 0.1), T_p50: pct(Ts, 0.5), T_p90: pct(Ts, 0.9),
        leakage: mean('leakage'), scrap: mean('scrap'), pull_cost: runs[0].pull, total: mean('total'), band });
    }
    let best = rows[0];
    for (const r of rows) if (r.total < best.total || (r.total === best.total && r.pull < best.pull)) best = r;
    const share = [0, 1, 2].map((g) => slips.filter((s) => s[g] > 0).length / slips.length);
    const smean = [0, 1, 2].map((g) => { let t = 0; for (const s of slips) t += s[g]; return t / slips.length; });
    return { rows, best: best.pull, slip_share: share, slip_mean: smean };
  }

  // ---------------------------------------------------------------- Part B: board cover
  function boardDraws(inp, P, m, seed) {
    const rng = makeRng(seed), rngCap = makeRng(seed + 5000), runs = [];
    for (let r = 0; r < Math.trunc(P.board_runs); r++) {
      const z = [], u = [];
      for (let w = 0; w < inp.weeks; w++) z.push(rng.gauss());
      for (let w = 0; w < inp.weeks; w++) u.push(rng.gauss());
      const c1 = rng.random(), c2 = rng.random();
      const live = []; for (let w = 0; w < inp.weeks; w++) if (m.plan[w] > 0) live.push(w);
      let cut = null;
      if (c1 < m.cut_prob && live.length > 8) cut = live[0] + 4 + Math.trunc(c2 * (live.length - 4));
      const v = []; for (let w = 0; w < inp.weeks; w++) v.push(rngCap.random());
      runs.push([z, u, cut, v]);
    }
    return runs;
  }
  const rushPremium = (P, m) => Math.min(P.rush_premium_max, Math.max(P.rush_premium_min, P.rush_premium_share * m.board_extra));   // Q49
  function boardRun(inp, P, m, cover, draw) {
    const [z, u, cut, v] = draw, W = inp.weeks;
    const s16 = P.forecast_mape_16w * Math.sqrt(Math.PI / 2) * m.sigma_mult;
    const D = [];
    for (let w = 0; w < W; w++) D.push(cut !== null && w >= cut ? 0 : m.plan[w] * Math.max(0, 1 + P.demand_noise * z[w]));
    const strong = P.gsm_strong >= 0.5;
    const push = Math.max(0, (P.board_cover_std_weeks - cover) / P.board_cover_std_weeks);
    const cutcap = (strong ? P.capacity_cut_strong : P.capacity_cut_weak) * push;
    const hazard = (strong ? P.capacity_loss_hazard_strong : P.capacity_loss_hazard_weak) * push;
    const drop = strong ? P.capacity_loss_strong : P.capacity_loss_weak, span = Math.trunc(P.capacity_loss_weeks);
    let inv = 0, setups = 0, rush = 0, lost = 0, carry = 0, budget = 0;
    let until = -1, events = 0, downWeeks = 0;   // last week of a capacity loss under way
    const premium = rushPremium(P, m);
    const forecast = (w, h, d) => {
      if (m.eol !== null && w >= m.eol) return 0;
      if (cut !== null && d >= cut) return 0;
      const base = m.plan[w] * Math.max(0, 1 + P.demand_noise * z[w]);
      const g = Math.sqrt(h / 16);
      return base * Math.max(0, 1 + m.bias * g + s16 * g * u[w]);
    };
    for (let w = 0; w < W; w++) {
      const live = m.plan[w] > 0 && !(cut !== null && w >= cut);
      if (live && w > until && v[w] < hazard) { until = w + span - 1; events += 1; budget *= 1 - drop; }  // the line goes to another customer
      const down = w <= until ? drop : 0;
      if (down > 0 && live) downWeeks += 1;
      if (w % cover === 0) {
        let need = 0;
        for (let j = 0; j < cover; j++) if (w + j < W) need += forecast(w + j, j + 1, w);
        const build = Math.min(Math.max(0, need - inv), need * (1 - cutcap) * (1 - down));
        if (build > 1e-9) { inv += build; setups += P.setup_usd_per_run; }
        let pl = 0; for (let j = 0; j < cover; j++) if (w + j < W) pl += m.plan[w + j];
        budget = P.smt_flex * pl * (1 - down);
      }
      const use = Math.min(inv, D[w]);
      inv -= use;
      const short = D[w] - use;
      if (short > 1e-9) {
        const r = Math.min(short, budget);
        budget -= r;
        rush += r * premium;
        lost += (short - r) * P.lost_share * m.margin;
      }
      carry += inv * m.board_value * P.carry / 52;
    }
    const ended = cut !== null || m.eol !== null;
    const stranded = ended ? inv : 0;
    const lock = (m.board_value - m.onboard_parts * (1 - P.migration)) * P.mwd_cost_rate;
    const parts = { setups, rush, lost, carry, stranded: stranded * lock };
    return { parts, total: parts.setups + parts.rush + parts.lost + parts.carry + parts.stranded, stranded_boards: stranded, events, down_weeks: downWeeks };
  }
  function boardEval(inp, P, m, seed) {
    const draws = boardDraws(inp, P, m, seed), rows = [];
    for (const cover of inp.covers) {
      const runs = draws.map((d) => boardRun(inp, P, m, cover, d)), n = runs.length;
      const parts = {};
      for (const k of Object.keys(runs[0].parts)) { let t = 0; for (const r of runs) t += r.parts[k]; parts[k] = t / n; }
      const tot = runs.map((r) => r.total);
      let st = 0; for (const r of runs) st += r.stranded_boards;
      let tt = 0; for (const x of tot) tt += x;
      let lc = 0, dw = 0; for (const r of runs) { if (r.events > 0) lc += 1; dw += r.down_weeks; }
      const mean = tt / n, p90 = pct(tot, 0.9);
      rows.push({ cover, parts, total: mean, p90, score: (1 - P.risk_weight) * mean + P.risk_weight * p90,
        stranded_boards: st / n, loss_chance: lc / n, down_weeks: dw / n });
    }
    let best = rows[0];
    for (const r of rows) if (r.score < best.score || (r.score === best.score && -r.cover < -best.cover)) best = r;
    return { model: m.model, risk: m.risk, rows, best: best.cover };
  }
  const boards = (inp, P) => inp.models.map((m, i) => boardEval(inp, P, m, 101 + i));
  return { makeRng, smoothstep, yieldAt, plannedT, pullCost, rampSlips, rampRun, rampSweep, rushPremium, boardDraws, boardRun, boardEval, boards };
})();
if (typeof module !== 'undefined') module.exports = RBE;
