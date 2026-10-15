/* Module 4 engine for the browser: a line-by-line port of src/finished_goods.py.
   Same random numbers as src/prng.py, so a given seed gives the same result in both;
   tests/test_fg_parity.py checks it. Keep the two files in step when either changes. */
const FGE = (() => {
  // ---------------------------------------------------------------- random numbers
  function makeRng(seed) {
    let s = seed >>> 0;
    const random = () => {
      s = (s + 0x6D2B79F5) >>> 0;
      let t = s;
      t = Math.imul(t ^ (t >>> 15), t | 1) >>> 0;
      t = ((((t + (Math.imul(t ^ (t >>> 7), t | 61) >>> 0)) >>> 0)) ^ t) >>> 0;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
    return {
      random,
      gauss(mu = 0, sigma = 1) {
        const u1 = 1 - random(), u2 = random();
        return mu + sigma * Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
      },
      randint(a, b) { return a + Math.floor(random() * (b - a + 1)); },
    };
  }
  const sum = (arr, a = 0, b = arr.length) => { let t = 0; for (let i = a; i < Math.min(b, arr.length); i++) t += arr[i]; return t; };
  const PATHS = ['divert', 'rework', 'teardown', 'liquidate', 'scrap'];

  // ---------------------------------------------------------------- disposition
  function pathValues(price, cost, dutyUnit, ftz, P, rw, td, lq) {
    const post = price * (1 - P.launch_drop_pct);
    const refund = ftz ? 0 : P.drawback_share * dutyUnit;
    const dom = ftz ? dutyUnit : 0;
    return {
      divert: [post * P.divert_price_factor - P.divert_cost_usd + refund, P.divert_capacity_share],
      rework: [post * P.rework_price_factor - cost * rw - P.rework_labour_usd + refund, P.rework_capacity_share],
      teardown: [cost * td - dom, 1],
      liquidate: [price * lq - dom, 1],
      scrap: [-P.scrap_cost_usd + refund, 1],
    };
  }
  function disposition(units, price, cost, dutyUnit, ftz, P, rw, td, lq) {
    const mix = { divert: 0, rework: 0, teardown: 0, liquidate: 0, scrap: 0 };
    if (units <= 1e-9) return [0, mix, 0];
    const vals = pathValues(price, cost, dutyUnit, ftz, P, rw, td, lq);
    const landed = cost + (ftz ? 0 : dutyUnit);
    const good = units * (1 - P.aged_failure_rate);
    const failed = units - good;
    let rec = 0, left = good;
    // stable sort by net, best first (same order as Python's sorted on a dict)
    const order = PATHS.map((k, i) => [k, i]).sort((a, b) => (vals[b[0]][0] - vals[a[0]][0]) || (a[1] - b[1]));
    for (const [name] of order) {
      if (left <= 1e-9) break;
      const take = Math.min(left, units * vals[name][1]);
      rec += take * vals[name][0];
      mix[name] += take;
      left -= take;
    }
    rec += failed * vals.teardown[0];
    mix.teardown += failed;
    const carry = units * landed * (P.carrying_rate_annual ?? 0.20) * P.disposition_delay_weeks / 52;
    const loss = units * landed - rec + units * P.reinspect_cost_usd + carry;
    let sunk;
    if (ftz) sunk = (mix.teardown + mix.liquidate) * dutyUnit;
    else sunk = units * dutyUnit - (mix.divert + mix.rework + mix.scrap) * P.drawback_share * dutyUnit;
    return [loss, mix, sunk];
  }

  function marketShape(peak, launch, tail, horizon) {
    const out = new Array(horizon);
    for (let w = 0; w < horizon; w++) out[w] = w < launch ? peak : peak * Math.max(0, 1 - (w - launch + 1) / (tail + 1));
    return out;
  }

  // ---------------------------------------------------------------- one model in one region
  function regionRun(S, A, P, cfg, launch, eol, liability, tLock, traj, runs, lockBias, ibpHedge) {
    const n = S.length, T = Math.trunc(P.build_to_mgi_weeks), L = Math.trunc(liability);
    const C = Math.trunc(P.mgi_wos_weeks + P.channel_wos_weeks);
    const bias = 1 + P.sales_bias;
    const fc = S.map((x) => x * bias);
    let locked = false;
    const f = (i) => (i < n ? fc[i] : 0);
    const fwd = (w, k) => sum(fc, w + 1, w + 1 + k);
    let mgi = P.mgi_wos_weeks * fc[0];
    let chan = P.channel_wos_weeks * fc[0];
    const pipe = new Array(n + T + 1).fill(0);
    for (let i = 0; i < T; i++) pipe[i] = fc[i + C];
    const kit = new Array(n + L).fill(0);
    for (let b = 0; b < Math.min(L, eol); b++) kit[b] = f(b + T + C);
    let bank = 0, plan = null, backlog = 0;
    const c = { lost: 0, sold_pre: 0, sold_post: 0, sell_in_pre: 0, sell_in_post: 0, chan_launch: 0, builds: 0,
      kits: sum(kit, 0, L), final_buy: 0, cut_at_lock: 0, hedge_units: 0 };
    const sellIn = new Array(n).fill(0);
    for (let w = 0; w < n; w++) {
      let r = 1;
      if (w >= 4) {
        let a = 0, s = 0;
        for (let i = Math.max(0, w - 4); i < w; i++) a += A[i];
        for (let i = Math.max(0, w - 4); i < w; i++) s += S[i];
        r = a / Math.max(1e-9, s);
      }
      if (cfg.lock && w === tLock) {
        locked = true;
        let rd = 1;
        if (w > 0) {
          const h0 = Math.max(0, w - Math.trunc(P.lock_window_weeks));
          let a = 0, s = 0;
          for (let i = h0; i < w; i++) a += A[i];
          for (let i = h0; i < w; i++) s += S[i];
          rd = a / Math.max(1e-9, s);
        }
        const mult = rd * (1 + lockBias);
        for (let i = w; i < n; i++) fc[i] = S[i] * mult;
        const inFlight = sum(pipe, w, w + T + 1);
        let need = Math.max(0, sum(fc, w, n) - mgi - chan - inFlight);
        if (cfg.ibp) {
          need *= Math.max(0, 1 + ibpHedge);
          c.hedge_units = need * ibpHedge / Math.max(1e-9, 1 + ibpHedge);
        }
        const weeks = [];
        for (let b = w; b < eol; b++) weeks.push(b);
        if (weeks.length) {
          const wt = [];
          for (let k = 0; k < weeks.length - 1; k++) wt.push(f(weeks[k] + T + C));
          wt.push(sum(fc, Math.min(n, weeks[weeks.length - 1] + T + C), n));
          const totW = sum(wt) || 1;
          plan = {};
          weeks.forEach((b, k) => { plan[b] = need * wt[k] / totW; });
        }
        let ks = 0;
        for (let b = w; b < Math.min(eol, w + L); b++) ks += kit[b];
        const committed = bank + ks;
        const buy = Math.max(0, need - committed);
        let later = weeks.filter((b) => b >= w + L);
        if (!later.length) later = weeks.slice(-1);
        for (const b of later) kit[b] += buy / later.length;
        c.final_buy = buy;
        c.cut_at_lock = Math.max(0, committed - need);
        c.kits += buy;
      } else if (!locked) {
        const mult = bias * (1 + P.sales_chase * Math.max(0, r - 1));
        for (let i = w; i < n; i++) fc[i] = S[i] * mult;
      }
      // 1) material
      const b = w + L;
      if (b < eol && !locked) {
        let ds = 0;
        for (let j = w; j < b; j++) ds += kit[j] - f(j + T + C);
        const proj = bank + ds;
        kit[b] = Math.max(0, f(b + T + C) - Math.max(0, proj));
        c.kits += kit[b];
      }
      // 2) build release
      let build = 0;
      if (w < eol) {
        bank += kit[w];
        const position = mgi + chan + sum(pipe, w, w + T + 1);
        if (plan !== null) {
          backlog += plan[w] || 0;
          build = Math.min(bank, backlog);
          backlog -= build;
        } else {
          build = Math.min(bank, Math.max(0, fwd(w, T + C) - position));
        }
        bank -= build;
        pipe[w + T] += build;
        c.builds += build;
      }
      // 3) arrivals, launch, sales
      mgi += pipe[w];
      if (w === launch) c.chan_launch = chan;
      const s = Math.min(chan, A[w]);
      c.lost += A[w] - s;
      chan -= s;
      if (w < launch) c.sold_pre += s; else c.sold_post += s;
      // 4) channel replenishment
      const near = launch - P.drain_weeks <= w;
      let wos = P.channel_wos_weeks;
      if (near && cfg.cover === 'drain') wos = P.drain_wos_weeks;
      else if (near && w < launch && cfg.cover === 'push') wos = P.push_wos_weeks;
      const whole = Math.trunc(wos);
      const cover = fwd(w, whole) + (wos - whole) * f(w + 1 + whole);
      const ship = Math.min(mgi, Math.max(0, cover - chan));
      mgi -= ship;
      chan += ship;
      sellIn[w] = ship;
      if (w < launch) c.sell_in_pre += ship; else c.sell_in_post += ship;
      if (traj) {
        traj.demand[w] += A[w] / runs; traj.forecast[w] += fc[w] / runs; traj.sold[w] += s / runs;
        traj.lost[w] += (A[w] - s) / runs; traj.builds[w] += build / runs; traj.arrivals[w] += pipe[w] / runs;
        traj.sell_in[w] += ship / runs; traj.mgi[w] += mgi / runs; traj.channel[w] += chan / runs;
        traj.kits[w] += bank / runs;
        traj.transit[w] += sum(pipe, w + 1, w + T + 1) / runs;
      }
    }
    c.rotation_base = sum(sellIn, Math.max(0, n - Math.trunc(P.stock_rotation_window_weeks)), n);
    return [mgi + sum(pipe, n, pipe.length), chan, bank, c];
  }

  // ---------------------------------------------------------------- Monte Carlo
  const TRAJ_KEYS = ['demand', 'forecast', 'sold', 'lost', 'builds', 'arrivals', 'sell_in', 'mgi', 'channel', 'kits', 'transit'];
  const tri = (rng, lo, mode, hi) => {
    if (hi <= lo) return mode;
    const u = rng.random(), fc = (mode - lo) / (hi - lo);
    return u < fc ? lo + Math.sqrt(u * (hi - lo) * (mode - lo)) : hi - Math.sqrt((1 - u) * (hi - lo) * (hi - mode));
  };

  /* input: from finished_goods.engine_input(); P0: parameter values; opts: {strategy, runs, seed,
     ftz, dutyOverride, ranges: {key: [lo, hi]} sampled each run around P0 (triangular), traj} */
  function simulate(input, P0, opts) {
    const cfg = input.strategies[opts.strategy];
    const runs = opts.runs || 200, seed = opts.seed ?? 11, ftz = !!opts.ftz;
    const rng = makeRng(seed);
    const regions = input.regions, L = input.liability;
    const rangeKeys = Object.keys(opts.ranges || {});
    const Tbase = Math.trunc(P0.build_to_mgi_weeks);
    const launch = input.npi_successor + Tbase;
    const horizon = launch + Math.trunc(P0.tail_weeks) + 1;
    const traj = opts.traj === false ? null : Object.fromEntries(TRAJ_KEYS.map((k) => [k, new Array(horizon).fill(0)]));
    const runsOut = [], byRegion = {};
    regions.forEach((g) => { byRegion[g] = {}; });
    for (let run = 0; run < runs; run++) {
      // parameter uncertainty: draw ranged inputs first (only when ranges are switched on)
      let P = P0;
      if (rangeKeys.length) {
        P = { ...P0 };
        for (const k of rangeKeys) P[k] = tri(rng, opts.ranges[k][0], P0[k], opts.ranges[k][1]);
      }
      const sigmaW = P.weekly_error_mape * Math.sqrt(Math.PI / 2);
      const tot = {};
      const add = (k, v) => { tot[k] = (tot[k] || 0) + v; };
      const style = {}, hedge = {};
      for (const g of regions) style[g] = rng.gauss(P.lock_bias, P.lock_bias_sd);
      for (const g of regions) hedge[g] = -P.ibp_learn * (style[g] - 0) + rng.gauss(0, P.ibp_noise_sd);
      for (const m of input.models) {
        const price = m.price, cost = m.cv + P.inbound_freight_usd;
        const drop = price * P.launch_drop_pct;
        const shape = marketShape(m.peak, launch, Math.trunc(P0.tail_weeks), horizon);
        const level = Math.max(0.3, rng.gauss(1, P.level_error_sd));
        for (const g of regions) {
          const sh = input.share[g];
          const duty = (opts.dutyOverride && g in opts.dutyOverride) ? opts.dutyOverride[g] : input.duty[g];
          const dutyUnit = m.cv * duty;
          const sp = Math.trunc(P.lock_region_spread_weeks);
          const spread = rng.randint(-sp, sp);
          const noise = new Array(horizon);
          for (let w = 0; w < horizon; w++) noise[w] = Math.max(0, 1 + rng.gauss(0, sigmaW));
          const S = shape.map((x) => x * sh);
          const A = S.map((x, w) => x * level * noise[w]);
          const tLock = Math.trunc(m.eol - P.lock_lead_weeks + spread);
          const [mgiLeft, chanLeft, kitsLeft, c] = regionRun(S, A, P, cfg, launch, m.eol, L, tLock, traj, runs, style[g], hedge[g]);
          const returned = Math.min(chanLeft, P.stock_rotation_cap * c.rotation_base);
          const kept = chanLeft - returned;
          const dealerLoss = kept * price * (1 - P.launch_drop_pct) * (1 - P.dealer_clearance_recovery);
          const excess = mgiLeft + returned;
          let [loss, mix, sunk] = disposition(excess, price, cost, dutyUnit, ftz, P, m.rw, m.td, m.lq);
          loss += returned * P.return_handling_usd;
          const prot = c.chan_launch * drop;
          const markdown = prot + c.sell_in_post * drop;
          const floor = c.sold_post * drop;
          const mwd = kitsLeft * m.kit_mwd;
          const lostMargin = c.lost * (price - cost) * (1 - P.lost_to_successor_share);
          const row = {
            demand_units: sum(A), sold_units: c.sold_pre + c.sold_post, builds_units: c.builds, kits_ordered: c.kits,
            sell_in_pre_launch_units: c.sell_in_pre, channel_at_launch_units: c.chan_launch,
            excess_units: excess, returned_units: returned, lost_units: c.lost,
            dealer_kept_units: kept, dealer_loss_usd: dealerLoss, mwd_kits: kitsLeft,
            price_protection_usd: prot, launch_markdown_usd: markdown, markdown_floor_usd: floor,
            markdown_above_floor_usd: markdown - floor, excess_loss_usd: loss, mwd_usd: mwd,
            lost_margin_usd: lostMargin, duty_sunk_usd: sunk,
            avoidable_cost_usd: (markdown - floor) + loss + mwd + lostMargin,
            system_cost_usd: (markdown - floor) + loss + mwd + lostMargin + dealerLoss,
            cut_at_lock_kits: c.cut_at_lock, final_buy_kits: c.final_buy,
          };
          for (const pth of PATHS) row['mix_' + pth] = mix[pth] || 0;
          for (const k in row) {
            add(k, row[k]);
            byRegion[g][k] = (byRegion[g][k] || 0) + row[k] / runs;
          }
        }
      }
      runsOut.push(tot);
    }
    const summary = {};
    for (const k of Object.keys(runsOut[0])) {
      const v = runsOut.map((r) => r[k]).sort((a, b) => a - b);
      summary[k] = { mean: sum(v) / v.length, p10: v[Math.trunc(0.1 * (v.length - 1))], p90: v[Math.trunc(0.9 * (v.length - 1))] };
    }
    return { strategy: opts.strategy, summary, traj, byRegion, runs, launch_week: launch, horizon,
      eol_week: input.models[0].eol, lock_week: input.models[0].eol - P0.lock_lead_weeks };
  }
  return { simulate, makeRng, TRAJ_KEYS };
})();
if (typeof module !== 'undefined') module.exports = FGE;
