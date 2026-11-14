/* Roadmap A4 engine for the browser: a line-by-line port of src/year_run.py.
   Uses the Module 5 engine (DKE) for the catch-up and the Module 6 engine (RBE) for the ramp;
   tests/test_yr_parity.py checks Python and JavaScript give the same numbers. */
const YRE = (() => {
  const DK = typeof DKE !== 'undefined' ? DKE : require('./dk_engine.js');
  const RB = typeof RBE !== 'undefined' ? RBE : require('./rb_engine.js');
  const CATS = ['tariff', 'lost_margin', 'promotion', 'transfer', 'mwd', 'ramp', 'expedite', 'chain', 'conversion', 'fg_eol'];
  const sum = (a, i = 0, j = a.length) => { let t = 0; for (let k = i; k < j; k++) t += a[k]; return t; };

  function context(inp, tariff, gsm, P5, P6) {
    const dki = inp.dk, rbi = inp.rb, ex = inp.extra;
    const P = { ...(P5 || dki.P), tariff_cn: tariff };
    const Q6 = { ...(P6 || rbi.P), gsm_strong: gsm, ramp_tariff: tariff };
    const rs = RB.rampSweep(rbi, Q6);
    const best = rs.rows.find((r) => r.pull === rs.best);
    const rg = rbi.region, scrap = [];
    for (let w = 0; w < rbi.ramp_weeks; w++) {
      const y = RB.yieldAt(Q6, w);
      scrap.push((1 / y - 1) * rg.bom * Q6.scrap_share_of_bom);
    }
    return { dk: dki, P, band: best.band, pull: rs.best, pull_cost: best.pull_cost, T50: best.T_p50, T90: best.T_p90, scrap,
      gsm_strong: gsm, expedite_unit: P.expedite_usd_per_unit * (gsm >= 0.5 ? 1 : P.expedite_weak_mult),
      extra_transit_weeks: (ex.days_new - ex.days_cn) / 7, days_cn: ex.days_cn, days_new: ex.days_new,
      fg_rate: ex.fg_rate, fg_week: Math.trunc(ex.fg_week), tariff };
  }
  function chinaShare(ctx, w, c) {
    if (c === null || w < c) return 1;
    const k = w - c;
    return 1 - (k < ctx.band.length ? ctx.band[k][1] : 1);
  }
  function replay(ctx, opt, passthrough) {
    const dki = ctx.dk, P = { ...ctx.P, passthrough };
    const W = dki.weeks, C = opt.cutover;
    const rate = P.tariff_cn * (1 - P.exporter_absorb);
    const ch = []; for (let w = 0; w < W; w++) ch.push(chinaShare(ctx, w, C));
    const base = [], plan = new Array(W).fill(0);
    for (const m of dki.models) {
      const tariff = rate * m.customs_value, row = [];
      for (let w = 0; w < W; w++) {
        const q0 = m.demand[w];
        plan[w] += q0;
        const rise = w >= P.reprice_lag_weeks ? P.passthrough * tariff * ch[w] : 0;
        row.push(q0 > 0 ? q0 * (1 + rise / m.price) ** m.elasticity : 0);
      }
      base.push(row);
    }
    const totalPlan = sum(plan);
    let before = 0; for (const row of base) before += sum(row);
    const disc = DK.catchUp(dki, P, base, P.target_tolerance * totalPlan - before);
    const cw = Math.trunc(P.catchup_from_week);
    const cost = Object.fromEntries(CATS.map((k) => [k, new Array(W).fill(0)]));
    const units = new Array(W).fill(0), cnUnits = new Array(W).fill(0), riseAvg = new Array(W).fill(0);
    dki.models.forEach((m, i) => {
      const tariff = rate * m.customs_value;
      const lift = disc > 0 ? (1 - P.points_effect * disc) ** m.elasticity : 1;
      for (let w = 0; w < W; w++) {
        const q0 = m.demand[w];
        if (q0 <= 0) continue;
        const rise = w >= P.reprice_lag_weeks ? P.passthrough * tariff * ch[w] : 0;
        const q = base[i][w] * (w >= cw ? lift : 1);
        units[w] += q; cnUnits[w] += q * ch[w]; riseAvg[w] += q * rise;
        cost.tariff[w] += q * (tariff * ch[w] - rise);
        cost.lost_margin[w] += (q0 - q) * m.price * m.gross_margin;
        if (w >= cw) cost.promotion[w] += q * disc * m.price;
      }
    });
    const cs = dki.case, moved = C !== null && C < W;
    const newUnits = units.map((u, w) => u - cnUnits[w]);
    if (moved) {
      cost.transfer[C] += opt.holding + opt.relocation + opt.rework;
      cost.mwd[W - 1] += opt.mwd;                                  // settled at the year-end reconciliation (R8)
      cost.ramp[C] += ctx.pull_cost;
      cost.expedite[C] += ctx.expedite_unit * cs.weekly_units * cs.lt_adder;
      for (let w = C; w < W; w++) {
        cost.chain[w] += (cs.eol_mwd_year + cs.pipeline_year) / W;
        cost.conversion[w] += newUnits[w] * cs.conv_cost * P.conv_uplift * DK.upliftLeft(P, w, C);
        const k = w - C;
        if (k < ctx.scrap.length) cost.ramp[w] += newUnits[w] * ctx.scrap[k];
      }
      const fw = ctx.fg_week;
      if (C < fw) cost.fg_eol[fw] += ctx.fg_rate * Math.max(0, ctx.extra_transit_weeks) * sum(newUnits, C, fw);
    }
    const quarters = [0, 1, 2, 3].map((q) => [sum(plan, q * 13, (q + 1) * 13), sum(units, q * 13, (q + 1) * 13)]);
    const frac = moved ? (W - C) / W : 0;
    const eol = cs.eol_mwd_year * frac, promo = sum(cost.promotion);
    const [buStd, buCus] = moved ? DK.buMwdParts(opt, P, eol) : [0, 0];
    const buMwd = buStd + buCus;
    return { units, cn_units: cnUnits, plan, cost, discount: disc, rise: riseAvg.map((r, w) => (units[w] ? r / units[w] : 0)),
      quarters, attainment: sum(units) / totalPlan, bu_cost: P.mwd_cost_rate_std * buStd + P.mwd_cost_rate * buCus + P.bu_funds_support * promo, bu_mwd: buMwd, share_cn: ch };
  }
  function runOption(ctx, opt) {
    const P = ctx.P, neg = replay(ctx, opt, P.passthrough), p = P.absorb_prob;
    let cost = neg.cost, buCost = neg.bu_cost, att = neg.attainment;
    if (p > 0) {
      const ab = replay(ctx, opt, 0);
      cost = Object.fromEntries(CATS.map((k) => [k, neg.cost[k].map((a, w) => (1 - p) * a + p * ab.cost[k][w])]));
      buCost = (1 - p) * neg.bu_cost + p * ab.bu_cost;
      att = Math.min(neg.attainment, ab.attainment);
    }
    const W = neg.units.length, cum = [];
    let acc = 0;
    for (let w = 0; w < W; w++) { let x = 0; for (const k of CATS) x += cost[k][w]; acc += x; cum.push(acc); }
    return { id: opt.id, cutover: opt.cutover, units: neg.units, cn_units: neg.cn_units, plan: neg.plan, rise: neg.rise,
      share_cn: neg.share_cn, quarters: neg.quarters, discount: neg.discount, cost,
      totals: Object.fromEntries(CATS.map((k) => [k, sum(cost[k])])), company_cost: acc, cumulative: cum,
      bu_cost: buCost, attainment: att, bu_mwd: neg.bu_mwd, claimed_mwd: opt.claimed_mwd };
  }
  function events(ctx, co, bu) {
    const P = ctx.P, pct = (v) => Math.round(v * 100) + '%';
    const ev = [[0, `US tariff of ${pct(ctx.tariff)} on China-made laptops starts`],
      [Math.trunc(P.reprice_lag_weeks), 'The new channel price is in place (pass-through negotiated)']];
    for (const [r, who] of [[co, 'company'], [bu, 'BU']]) {
      if (r.cutover !== null) {
        ev.push([r.cutover, `Cutover, the ${who}'s pick: plans inside the 16-week window are cancelled; the new site's first build`]);
        ev.push([Math.min(51, r.cutover + Math.round(ctx.T50)), `New site at full volume (median, ${who}'s pick)`]);
      }
    }
    ev.push([26, 'Successor P2-14 launches; second-half catch-up discount runs from here'],
      [ctx.fg_week, 'Platform P1 end of life: finished goods left in the pipeline'],
      [51, 'Fiscal year-end: shipments against the target; MWD reconciled']);
    return ev.map((e, i) => [e[0], e[1], i]).sort((a, b) => a[0] - b[0] || a[2] - b[2]).map((e) => [e[0], e[1]]);
  }
  function runYear(inp, tariff, gsm, P5, P6) {
    const ctx = context(inp, tariff, gsm, P5, P6), P = ctx.P, dki = ctx.dk;
    const rows = dki.options.map((o) => runOption(ctx, o));
    const order = (r) => (r.cutover === null ? dki.weeks + 1 : r.cutover);
    const hit = rows.filter((r) => r.attainment >= P.target_tolerance - 1e-9);
    let bu;
    if (hit.length) { bu = hit[0]; for (const r of hit) if (r.bu_cost < bu.bu_cost || (r.bu_cost === bu.bu_cost && -order(r) < -order(bu))) bu = r; }
    else { bu = rows[0]; for (const r of rows) if (r.attainment > bu.attainment) bu = r; }
    const pool = hit.length && P.company_holds_target >= 0.5 ? hit : rows;
    let co = pool[0];
    for (const r of pool) if (r.company_cost < co.company_cost || (r.company_cost === co.company_cost && order(r) < order(co))) co = r;
    const by = Object.fromEntries(rows.map((r) => [r.id, r]));
    const strategies = [['stay', 'Stay in China', by.stay], ['company', "Company's pick", co], ['bu', "BU's pick", bu], ['model_change', 'Move at the model change', by.C26]];
    return { tariff, gsm_strong: gsm, pull: ctx.pull, T50: ctx.T50, T90: ctx.T90, extra_transit_days: ctx.days_new - ctx.days_cn,
      target: P.target_tolerance, reprice_lag: P.reprice_lag_weeks, catchup_from: P.catchup_from_week,
      strategies: strategies.map(([key, label, s]) => ({ key, label, ...s })),
      options: rows.map((r) => ({ id: r.id, cutover: r.cutover, company_cost: r.company_cost, bu_cost: r.bu_cost, attainment: r.attainment })),
      events: events(ctx, co, bu) };
  }
  return { CATS, context, replay, runOption, runYear };
})();
if (typeof module !== 'undefined') module.exports = YRE;
