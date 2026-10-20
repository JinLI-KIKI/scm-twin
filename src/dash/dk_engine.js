/* Module 5 engine for the browser: a line-by-line port of src/demand_kpi.py.
   tests/test_dk_parity.py checks both give identical numbers. Keep the two files in step. */
const DKE = (() => {
  function chinaShare(w, cutover, ramp) {
    if (cutover === null || w < cutover) return 1;
    return ramp > 0 ? Math.max(0, 1 - (w - cutover) / ramp) : 0;
  }
  function evaluate(inp, P, opt) {
    const C = opt.cutover;
    const tariffRate = P.tariff_cn * (1 - P.exporter_absorb);
    let plan = 0, units = 0, paid = 0, recovered = 0, lost = 0, convUnits = 0;
    const weekly = new Array(inp.weeks).fill(0);
    for (const m of inp.models) {
      const tariff = tariffRate * m.customs_value;
      for (let w = 0; w < inp.weeks; w++) {
        const q0 = m.demand[w];
        if (q0 <= 0) continue;
        const ch = chinaShare(w, C, P.ramp_weeks);
        const rise = w >= P.reprice_lag_weeks ? P.passthrough * tariff * ch : 0;
        const q = q0 * Math.pow(1 + rise / m.price, m.elasticity);
        plan += q0; units += q; weekly[w] += q;
        paid += q * tariff * ch; recovered += q * rise;
        lost += (q0 - q) * m.price * m.gross_margin;
        convUnits += q * (1 - ch);
      }
    }
    const cs = inp.case;
    const moved = C !== null && C < inp.weeks;
    const frac = moved ? (inp.weeks - C) / inp.weeks : 0;
    const eol = cs.eol_mwd_year * frac;
    const chain = eol + cs.pipeline_year * frac;
    const expedite = moved ? P.expedite_usd_per_unit * cs.weekly_units * cs.lt_adder : 0;
    const conv = convUnits * cs.conv_cost * P.conv_uplift;
    const transfer = opt.mwd + opt.holding + opt.relocation + opt.rework;
    const parts = { absorbed: paid - recovered, lost_margin: lost, transfer, expedite, chain, conversion: conv };
    const buMwd = (P.bu_mwd_claimed >= 0.5 ? opt.claimed_mwd : opt.mwd) + eol;
    const companyCost = parts.absorbed + parts.lost_margin + parts.transfer + parts.expedite + parts.chain + parts.conversion;
    return { id: opt.id, cutover: C, plan, units, attainment: plan ? units / plan : 1, lost_units: plan - units,
      tariff_paid: paid, recovered, bu_mwd: buMwd, claimed_mwd: opt.claimed_mwd, physical_mwd: opt.mwd, eol_mwd: eol,
      parts, company_cost: companyCost, weekly };
  }
  function score(inp, P) {
    const rows = inp.options.map((o) => evaluate(inp, P, o));
    const order = (r) => (r.cutover === null ? inp.weeks + 1 : r.cutover);
    const hit = rows.filter((r) => r.attainment >= P.target_tolerance - 1e-12);
    let bu = null;
    if (hit.length) {
      for (const r of hit) if (!bu || r.bu_mwd < bu.bu_mwd || (r.bu_mwd === bu.bu_mwd && -order(r) < -order(bu))) bu = r;
    } else {
      for (const r of rows) if (!bu || r.attainment > bu.attainment || (r.attainment === bu.attainment && -r.bu_mwd > -bu.bu_mwd)) bu = r;
    }
    let co = null;
    for (const r of rows) if (!co || r.company_cost < co.company_cost || (r.company_cost === co.company_cost && order(r) < order(co))) co = r;
    return { rows, bu: bu.id, company: co.id, gap: bu.company_cost - co.company_cost, any_hit: hit.length > 0 };
  }
  function grid(inp, P, tariffs, passthroughs) {
    return tariffs.map((t) => passthroughs.map((pt) => {
      const s = score(inp, { ...P, tariff_cn: t, passthrough: pt });
      return { bu: s.bu, company: s.company, gap: s.gap };
    }));
  }
  return { chinaShare, evaluate, score, grid };
})();
if (typeof module !== 'undefined') module.exports = DKE;
