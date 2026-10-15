/* Module 7 engine for the browser: a line-by-line port of src/footprint.py.
   tests/test_fp_parity.py checks both give identical numbers. Keep the two files in step. */
const FPE = (() => {
  const RISKY = { suez: 'Red Sea', babalmandab: 'Red Sea', ormuz: 'Hormuz' };
  const ssum = (a) => { let t = 0; for (const x of a) t += x; return t; };

  function dutyMatrix(inp, scenario) {
    const d = {};
    for (const k of Object.keys(inp.duties)) d[k] = { ...inp.duties[k] };
    for (const ov of scenario.overrides) {
      const targets = ov.origin === '*' ? inp.origins : [ov.origin];
      for (const o of targets) d[ov.tkey][o] = ov.duty;
    }
    return d;
  }
  function route(inp, o, mgi, mode, redSea) {
    for (const v of [redSea, 'any']) {
      const k = `${o}|${mgi}|${mode}|${v}`;
      if (k in inp.routes) return inp.routes[k];
    }
    throw new Error(`${o}|${mgi}|${mode}`);
  }
  function landed(inp, P, sites, o, m, mode, redSea, duties) {
    const r = route(inp, o, m.mgi, mode, redSea), s = sites[o];
    let parts = 0, plan = 0;
    if (o !== 'CN') {
      const f = inp.feeds[o];
      const partsFreight = (P.sea_feu_base_usd + P.sea_feu_per_nm_usd * f.nm) / P.kits_per_feu + P.handling_usd_per_unit;
      const partsCarry = P.parts_value_usd * P.carrying_rate_annual * f.days / 365;
      parts = partsFreight + partsCarry + P.parts_value_usd * s.parts_duty;
      plan = P.planning_cost_usd_per_unit_week * (f.days / 7 + 1);
    }
    const board = o === 'CN' || s.board_local;
    const cv = P.customs_value_cn_usd + P.conversion_cost_cn_usd * (s.conv_index - 1) + parts
      + (o !== 'CN' && board ? P.board_extra_usd : 0);
    const trucking = P.truck_usd_per_unit_100km * r.truck_km / 100;
    let freight;
    if (r.domestic) freight = trucking + P.handling_usd_per_unit * 0.5;
    else if (mode === 'sea') freight = (P.sea_feu_base_usd + P.sea_feu_per_nm_usd * r.nm) / P.units_per_feu + P.handling_usd_per_unit + trucking;
    else freight = P.kg_per_unit * (P.air_usd_per_kg_base + P.air_usd_per_kg_per_1000km * r.air_km / 1000) + P.handling_usd_per_unit + trucking;
    const own = duties[m.tkey][o];
    const w = (board || r.domestic) ? 0 : P.board_origin_weight;
    const rate = (1 - w) * own + w * duties[m.tkey].CN;
    const base = cv + ((m.valuation === 'CIF' && !r.domestic) ? freight : 0);
    const duty = rate * base;
    const carry = cv * P.carrying_rate_annual * r.days / 365;
    const risky = [...new Set(r.passages.filter((p) => p in RISKY).map((p) => RISKY[p]))].sort();
    const risk = P.chokepoint_premium_usd * risky.length;
    const total = cv + freight + duty + carry + plan + risk;
    return { total, factory: cv, parts, freight, duty, duty_rate: rate, own_rate: own, origin_weight: w, duty_base: base, board,
      carry, plan, risk, days: r.days,
      passages: r.passages, risky, domestic: r.domestic };
  }
  function landedTable(inp, P, sites, mode, redSea, duties) {
    const out = {};
    for (const o of inp.origins) out[o] = inp.markets.map((m) => landed(inp, P, sites, o, m, mode, redSea, duties));
    return out;
  }

  // ---------------------------------------------------------------- minimum-cost flow
  const BIG = 1e6;   // cost bonus that makes the solver fill each site's minimum load first
  function transport(cost, cap, demand, low) {
    const ni = cap.length, nj = demand.length, n = ni + nj + 2, s = 0, t = n - 1;
    const to = [], capv = [], costv = [], adj = Array.from({ length: n }, () => []);
    const add = (u, v, c, w) => {
      adj[u].push(to.length); to.push(v); capv.push(c); costv.push(w);
      adj[v].push(to.length); to.push(u); capv.push(0); costv.push(-w);
    };
    const need = ssum(demand);
    low = low || new Array(ni).fill(0);
    for (let i = 0; i < ni; i++) {
      const lo = Math.min(low[i], cap[i]);
      if (lo > 0) add(s, 1 + i, lo, -BIG);
      add(s, 1 + i, cap[i] - lo, 0);
    }
    for (let i = 0; i < ni; i++) for (let j = 0; j < nj; j++) add(1 + i, 1 + ni + j, need, cost[i][j]);
    for (let j = 0; j < nj; j++) add(1 + ni + j, t, demand[j], 0);
    let sent = 0;
    while (sent < need - 1e-9) {
      const dist = new Array(n).fill(Infinity), prev = new Array(n).fill(-1);
      dist[s] = 0;
      for (let it = 0; it < n - 1; it++) {
        let changed = false;
        for (let u = 0; u < n; u++) {
          if (dist[u] === Infinity) continue;
          for (const e of adj[u]) {
            if (capv[e] > 1e-12 && dist[u] + costv[e] < dist[to[e]] - 1e-12) {
              dist[to[e]] = dist[u] + costv[e]; prev[to[e]] = e; changed = true;
            }
          }
        }
        if (!changed) break;
      }
      if (dist[t] === Infinity) break;
      let push = need - sent, v = t;
      while (v !== s) { const e = prev[v]; push = Math.min(push, capv[e]); v = to[e ^ 1]; }
      v = t;
      while (v !== s) { const e = prev[v]; capv[e] -= push; capv[e ^ 1] += push; v = to[e ^ 1]; }
      sent += push;
    }
    const flow = Array.from({ length: ni }, () => new Array(nj).fill(0));
    for (let i = 0; i < ni; i++) {
      for (const e of adj[1 + i]) {
        const j = to[e] - 1 - ni;
        if (j >= 0 && j < nj && e % 2 === 0) flow[i][j] = need - capv[e];
      }
    }
    return [flow, Math.max(0, need - sent)];
  }

  function evaluate(inp, P, sites, openSites, redSea, duties) {
    const org = inp.origins.filter((o) => openSites.includes(o));
    const tab = landedTable(inp, P, sites, 'sea', redSea, duties);
    const cost = org.map((o) => inp.markets.map((_, j) => tab[o][j].total));
    const cap = org.map((o) => sites[o].capacity);
    const low = org.map((o) => sites[o].min_load * sites[o].capacity);
    const dem = inp.markets.map((m) => m.weekly_units);
    const [flow, unmet] = transport(cost, cap, dem, low);
    const underload = ssum(org.map((_, i) => Math.max(0, low[i] - ssum(flow[i]))));
    let total = 0, duty = 0, days = 0;
    const exposure = {}, alloc = {};
    org.forEach((o, i) => inp.markets.forEach((m, j) => {
      const q = flow[i][j];
      if (q <= 1e-9) return;
      const c = tab[o][j];
      alloc[`${o}|${m.market}`] = q;
      total += q * c.total; duty += q * c.duty; days += q * c.days;
      for (const p of c.risky) exposure[p] = (exposure[p] || 0) + q;
    }));
    const served = ssum(dem) - unmet;
    const load = {};
    org.forEach((o, i) => { load[o] = ssum(flow[i]); });
    return { weekly_cost: total, weekly_duty: duty, avg_days: served ? days / served : 0, alloc, unmet, underload, exposure, open: org, load, table: tab };
  }

  function withBoards(sites, openSites, board) {
    const out = {};
    for (const o of Object.keys(sites)) {
      const c = { ...sites[o] };
      if (o !== 'CN' && openSites.includes(o) && board !== null) c.board_local = board;
      out[o] = c;
    }
    return out;
  }
  function yearlyCosts(inp, P, sites, openSites, redSea, mats) {
    const fixed = ssum(openSites.map((o) => sites[o].fixed_cost))
      + P.board_fixed_usd_yr * openSites.filter((o) => o !== 'CN' && sites[o].board_local).length;
    const costs = mats.map((d) => {
      const ev = evaluate(inp, P, sites, openSites, redSea, d);
      return 52 * ev.weekly_cost + fixed + ((ev.unmet > 1e-6 || ev.underload > 1e-6) ? 1e12 : 0);
    });
    return [fixed, costs];
  }
  function footprints(inp, P, sites, redSea, scenList) {
    const scen = scenList || inp.scenarios, orgs = inp.origins;
    const demand = ssum(inp.markets.map((m) => m.weekly_units));
    const mats = scen.map((s) => dutyMatrix(inp, s));
    const rows = [];
    for (let mask = 1; mask < (1 << orgs.length); mask++) {
      const open = orgs.filter((_, k) => (mask >> k) & 1);
      if (ssum(open.map((o) => sites[o].capacity)) < demand - 1e-9
        || ssum(open.map((o) => sites[o].min_load * sites[o].capacity)) > demand + 1e-9) continue;
      for (const board of (open.some((o) => o !== 'CN') ? [false, true] : [null])) {
        const sv = withBoards(sites, open, board);
        const [fixed, costs] = yearlyCosts(inp, P, sv, open, redSea, mats);
        rows.push({ open, board: !!board, fixed, costs });
      }
    }
    const best = scen.map((_, k) => Math.min(...rows.map((r) => r.costs[k])));
    const wsum = ssum(scen.map((s) => s.probability)) || 1;
    for (const r of rows) {
      r.expected = ssum(scen.map((s, k) => s.probability * r.costs[k])) / wsum;
      r.regret = Math.max(...r.costs.map((c, k) => c - best[k]));
    }
    rows.sort((a, b) => (a.expected - b.expected) || (a.open.length - b.open.length) || (a.board - b.board));
    const base = rows.reduce((a, r) => (r.costs[0] < a.costs[0] ? r : a), rows[0]);
    const H = P.horizon_years, lag = Math.min(P.ramp_months / 12, H);
    for (const r of rows) {
      const wait = r.costs.map((c, k) => {
        const cb = base.costs[k];
        return r === base ? H * cb : Math.min(H * cb, lag * cb + (H - lag) * c + P.rush_premium_usd);
      });
      r.wait_by = wait;
      r.wait = ssum(scen.map((s, k) => s.probability * wait[k])) / wsum;
      r.build_now_value = r.wait - H * r.expected;
      r.is_base = r === base;
    }
    return rows;
  }
  function tippingWeight(row, scenList, sid, H) {
    const k0 = scenList.findIndex((s) => s.id === sid);
    const d = row.wait_by.map((w, k) => w - H * row.costs[k]);
    const rest = ssum(scenList.filter((_, k) => k !== k0).map((s) => s.probability));
    const dO = rest > 0 ? ssum(scenList.map((s, k) => (k !== k0 ? s.probability * d[k] : 0)).filter((_, k) => k !== k0)) / rest : 0;
    const dC = d[k0];
    if (dO >= 0) return 0;
    if (dC <= 0) return null;
    return -dO / (dC - dO);
  }
  // ---------------------------------------------------------------- duty ranges (Monte Carlo)
  function makeRng(seed) {                     // mulberry32, identical to src/prng.py
    let s = seed >>> 0;
    return { random() {
      s = (s + 0x6D2B79F5) >>> 0;
      let t = s;
      t = Math.imul(t ^ (t >>> 15), t | 1) >>> 0;
      t = ((((t + (Math.imul(t ^ (t >>> 7), t | 61) >>> 0)) >>> 0)) ^ t) >>> 0;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    } };
  }
  function candidates(inp, sites) {
    const orgs = inp.origins, demand = ssum(inp.markets.map((m) => m.weekly_units)), out = [];
    for (let mask = 1; mask < (1 << orgs.length); mask++) {
      const open = orgs.filter((_, k) => (mask >> k) & 1);
      if (ssum(open.map((o) => sites[o].capacity)) < demand - 1e-9
        || ssum(open.map((o) => sites[o].min_load * sites[o].capacity)) > demand + 1e-9) continue;
      for (const board of (open.some((o) => o !== 'CN') ? [false, true] : [null])) {
        out.push({ open, board: !!board, sites: withBoards(sites, open, board) });
      }
    }
    return out;
  }
  function drawDuties(inp, base, ranges, pChange, rng) {
    const d = {}, seen = [];
    for (const k of Object.keys(base)) d[k] = { ...base[k] };
    for (const m of inp.markets) {
      const t = m.tkey;
      if (seen.includes(t)) continue;
      seen.push(t);
      const u = rng.random(), s = rng.random();
      for (const o of inp.origins) {
        const b = base[t][o];
        let [lo, hi] = ranges[`${t}|${o}`] || [b, b];
        if (lo > hi) [lo, hi] = [hi, lo];
        d[t][o] = u < pChange ? lo + s * (hi - lo) : Math.min(Math.max(b, lo), hi);
      }
    }
    return d;
  }
  function dutyMonteCarlo(inp, P, sites, redSea, ranges, runs, seed, onProgress) {
    ranges = ranges || inp.ranges; runs = runs || 200; seed = seed === undefined ? 7 : seed;
    const base = dutyMatrix(inp, inp.scenarios[0]);
    const cands = candidates(inp, sites), rng = makeRng(seed);
    const cost = [], meanDuty = {};
    for (let k = 0; k < runs; k++) {
      const d = drawDuties(inp, base, ranges, P.duty_change_prob, rng);
      for (const key of Object.keys(ranges)) {
        const [t, o] = key.split('|');
        meanDuty[key] = (meanDuty[key] || 0) + d[t][o] / runs;
      }
      cost.push(cands.map((c) => yearlyCosts(inp, P, c.sites, c.open, redSea, [d])[1][0]));
      if (onProgress && k % 10 === 9) onProgress((k + 1) / runs);
    }
    const best = cost.map((row) => Math.min(...row));
    const win = new Array(cands.length).fill(0);
    for (const row of cost) {
      let j = 0, b = row[0];
      row.forEach((v, i) => { if (v < b) { j = i; b = v; } });
      win[j] += 1;
    }
    const pick = (v, q) => v[Math.floor(q * (v.length - 1))];
    const rows = cands.map((c, i) => {
      const col = cost.map((row) => row[i]), reg = cost.map((row, k) => row[i] - best[k]);
      const sc = col.slice().sort((a, b) => a - b), sr = reg.slice().sort((a, b) => a - b);
      return { open: c.open, board: c.board, mean: ssum(col) / runs, p10: pick(sc, 0.1), p50: pick(sc, 0.5), p90: pick(sc, 0.9),
        win: win[i] / runs, regret_mean: ssum(reg) / runs, regret_p90: pick(sr, 0.9) };
    });
    rows.sort((a, b) => (a.mean - b.mean) || (a.open.length - b.open.length) || (a.board - b.board));
    return { rows, runs, mean_duty: meanDuty };
  }
  function breakEven(inp, P, sites, redSea, duties) {
    const tab = landedTable(inp, P, sites, 'sea', redSea, duties), out = {};
    for (const o of inp.origins) {
      if (o === 'CN') continue;
      out[o] = inp.markets.map((_, j) => {
        const c = tab.CN[j], x = tab[o][j];
        const cn0 = c.total - c.duty;
        const own0 = x.total - x.duty + (1 - x.origin_weight) * x.own_rate * x.duty_base;
        const den = c.duty_base - x.origin_weight * x.duty_base;
        if (den <= 1e-9) return own0 <= cn0 ? 0 : null;
        return Math.max(0, (own0 - cn0) / den);
      });
    }
    return out;
  }
  return { dutyMatrix, landed, landedTable, transport, evaluate, withBoards, yearlyCosts, footprints, tippingWeight, breakEven, makeRng, candidates, drawDuties, dutyMonteCarlo };
})();
if (typeof module !== 'undefined') module.exports = FPE;
