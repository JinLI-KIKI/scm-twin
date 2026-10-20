/* Module 5 engine for the browser: a line-by-line port of src/demand_kpi.py.
   tests/test_dk_parity.py checks both give identical numbers. Keep the two files in step. */
const DKE = (() => {
  function chinaShare(w, cutover, ramp) {
    if (cutover === null || w < cutover) return 1;
    return ramp > 0 ? Math.max(0, 1 - (w - cutover) / ramp) : 0;
  }
  const ssum = (a) => { let t = 0; for (const x of a) t += x; return t; };
  function catchUp(inp, P, base, gap) {        // R45: discount from catchup_from_week that closes the gap
    const cw = Math.trunc(P.catchup_from_week);
    const h2 = base.map((row) => ssum(row.slice(cw)));
    const eff = P.points_effect;
    const extra = (d) => { let t = 0; inp.models.forEach((m, i) => { t += h2[i] * (Math.pow(1 - eff * d, m.elasticity) - 1); }); return t; };
    if (gap <= 1e-9 || ssum(h2) <= 0) return 0;
    let hi = P.max_promo_discount;
    if (extra(hi) <= gap) return hi;
    let lo = 0;
    for (let k = 0; k < 50; k++) { const mid = (lo + hi) / 2; if (extra(mid) < gap) lo = mid; else hi = mid; }
    return hi;
  }
  function evaluate(inp, P, opt) {
    const C = opt.cutover;
    const tariffRate = P.tariff_cn * (1 - P.exporter_absorb);
    const base = []; let plan = 0, before = 0;
    for (const m of inp.models) {
      const tariff = tariffRate * m.customs_value, row = [];
      for (let w = 0; w < inp.weeks; w++) {
        const q0 = m.demand[w];
        const ch = chinaShare(w, C, P.ramp_weeks);
        const rise = w >= P.reprice_lag_weeks ? P.passthrough * tariff * ch : 0;
        row.push(q0 > 0 ? q0 * Math.pow(1 + rise / m.price, m.elasticity) : 0);
        plan += q0;
      }
      base.push(row); before += ssum(row);
    }
    const disc = catchUp(inp, P, base, P.target_tolerance * plan - before);
    const cw = Math.trunc(P.catchup_from_week);
    let units = 0, paid = 0, recovered = 0, lost = 0, convUnits = 0, promo = 0;
    const weekly = new Array(inp.weeks).fill(0);
    const quarters = [[0, 0], [0, 0], [0, 0], [0, 0]];
    inp.models.forEach((m, i) => {
      const tariff = tariffRate * m.customs_value;
      const lift = disc > 0 ? Math.pow(1 - P.points_effect * disc, m.elasticity) : 1;
      for (let w = 0; w < inp.weeks; w++) {
        const q0 = m.demand[w];
        if (q0 <= 0) continue;
        const ch = chinaShare(w, C, P.ramp_weeks);
        const rise = w >= P.reprice_lag_weeks ? P.passthrough * tariff * ch : 0;
        const q = base[i][w] * (w >= cw ? lift : 1);
        units += q; weekly[w] += q;
        const k = Math.min(3, Math.floor(w / 13));
        quarters[k][0] += q0; quarters[k][1] += q;
        paid += q * tariff * ch; recovered += q * rise;
        lost += (q0 - q) * m.price * m.gross_margin;
        convUnits += q * (1 - ch);
        if (w >= cw) promo += q * disc * m.price;
      }
    });
    const cs = inp.case;
    const moved = C !== null && C < inp.weeks;
    const frac = moved ? (inp.weeks - C) / inp.weeks : 0;
    const eol = cs.eol_mwd_year * frac;
    const chain = eol + cs.pipeline_year * frac;
    const expedite = moved ? P.expedite_usd_per_unit * cs.weekly_units * cs.lt_adder : 0;
    const conv = convUnits * cs.conv_cost * P.conv_uplift;
    const transfer = opt.mwd + opt.holding + opt.relocation + opt.rework;
    const parts = { absorbed: paid - recovered, lost_margin: lost, promotion: promo, transfer, expedite, chain, conversion: conv };
    const tr = P.mwd_transferability;                     // R43: claimed -> physical as material migrates
    const buMwd = opt.claimed_mwd - tr * (opt.claimed_mwd - opt.mwd) + eol;
    const buMwdCost = P.mwd_cost_rate * buMwd;
    const buSupport = P.bu_funds_support * promo;
    const companyCost = parts.absorbed + parts.lost_margin + parts.promotion + parts.transfer + parts.expedite + parts.chain + parts.conversion;
    return { id: opt.id, cutover: C, plan, units, attainment: plan ? units / plan : 1, before_catch_up: plan ? before / plan : 1, discount: disc, quarters,
      lost_units: plan - units,
      tariff_paid: paid, recovered, bu_mwd: buMwd, bu_mwd_cost: buMwdCost, bu_support: buSupport, bu_cost: buMwdCost + buSupport, claimed_mwd: opt.claimed_mwd, physical_mwd: opt.mwd, eol_mwd: eol,
      parts, company_cost: companyCost, weekly };
  }
  function evaluateMix(inp, P, opt) {          // R44: negotiated pass-through, small chance of absorbing
    const neg = evaluate(inp, P, opt), p = P.absorb_prob;
    if (p <= 0) return { ...neg, cases: null };
    const ab = evaluate(inp, { ...P, passthrough: 0 }, opt);
    const parts = {};
    for (const k of Object.keys(neg.parts)) parts[k] = (1 - p) * neg.parts[k] + p * ab.parts[k];
    const mix = (k) => (1 - p) * neg[k] + p * ab[k];
    let companyCost = 0;
    for (const k of Object.keys(parts)) companyCost += parts[k];
    return { ...neg, parts, company_cost: companyCost, bu_mwd_cost: mix('bu_mwd_cost'), bu_support: mix('bu_support'), bu_cost: mix('bu_cost'),
      tariff_paid: mix('tariff_paid'), recovered: mix('recovered'), attainment: Math.min(neg.attainment, ab.attainment),
      cases: { negotiated: { company_cost: neg.company_cost, bu_cost: neg.bu_cost }, absorbed: { company_cost: ab.company_cost, bu_cost: ab.bu_cost } } };
  }
  function score(inp, P) {
    const rows = inp.options.map((o) => evaluateMix(inp, P, o));
    const order = (r) => (r.cutover === null ? inp.weeks + 1 : r.cutover);
    const hit = rows.filter((r) => r.attainment >= P.target_tolerance - 1e-9);
    let bu = null;
    if (hit.length) {
      for (const r of hit) if (!bu || r.bu_cost < bu.bu_cost || (r.bu_cost === bu.bu_cost && -order(r) < -order(bu))) bu = r;
    } else {
      for (const r of rows) if (!bu || r.attainment > bu.attainment || (r.attainment === bu.attainment && -r.bu_mwd > -bu.bu_mwd)) bu = r;
    }
    const pool = hit.length && P.company_holds_target >= 0.5 ? hit : rows;
    let co = null;
    for (const r of pool) if (!co || r.company_cost < co.company_cost || (r.company_cost === co.company_cost && order(r) < order(co))) co = r;
    return { rows, bu: bu.id, company: co.id, gap: bu.company_cost - co.company_cost, any_hit: hit.length > 0 };
  }
  function buGrid(inp, P, rowKey, rowVals, colKey, colVals) {
    return rowVals.map((a) => colVals.map((b) => score(inp, { ...P, [rowKey]: a, [colKey]: b }).bu));
  }
  function grid(inp, P, tariffs, passthroughs) {
    return tariffs.map((t) => passthroughs.map((pt) => {
      const s = score(inp, { ...P, tariff_cn: t, passthrough: pt });
      return { bu: s.bu, company: s.company, gap: s.gap };
    }));
  }
  return { chinaShare, evaluate, evaluateMix, score, grid, buGrid };
})();
if (typeof module !== 'undefined') module.exports = DKE;
