/* Shared helpers for the report pages: theme-aware ECharts, number formats, slicers. */
const R = (() => {
  const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const theme = () => ({
    ink: css('--ink'), ink2: css('--ink-2'), muted: css('--muted'), rule: css('--rule'),
    panel: css('--panel'), paper: css('--paper'), chip: css('--chip'), hl: css('--hl'),
    c: [1, 2, 3, 4, 5, 6, 7].map((i) => css('--c' + i)),
    sea: css('--sea'), air: css('--air'), inland: css('--inland'),
    d0: css('--d0'), d5: css('--d5'), d16: css('--d16'),
    good: css('--good'), warn: css('--warn'), bad: css('--bad'),
    fBody: css('--f-body'), fMono: css('--f-mono'), fDisp: css('--f-display'),
  });

  // ---------- numbers
  const usd = (v, d) => {
    if (v == null || isNaN(v)) return '–';
    const a = Math.abs(v), s = v < 0 ? '−' : '';
    if (a >= 1e9) return s + '$' + (a / 1e9).toFixed(d ?? 2) + 'B';
    if (a >= 1e6) return s + '$' + (a / 1e6).toFixed(d ?? 2) + 'M';
    if (a >= 1e3) return s + '$' + (a / 1e3).toFixed(d ?? 0) + 'k';
    return s + '$' + a.toFixed(0);
  };
  const num = (v, d = 0) => (v == null || isNaN(v)) ? '–' :
    (v < 0 ? '−' : '') + Math.abs(v).toLocaleString('en-US', { maximumFractionDigits: d, minimumFractionDigits: d });
  const kunits = (v) => Math.abs(v) >= 1e3 ? num(v / 1e3, 1) + 'k' : num(v);
  const pct = (v, d = 0) => (v == null || isNaN(v)) ? '–' : (v * 100).toFixed(d) + '%';
  const axUsd = (v) => usd(v, Math.abs(v) >= 1e6 ? 1 : 0);

  // ---------- charts
  const charts = [];
  const hasLib = () => typeof window.echarts !== 'undefined';
  function base(t) {
    return {
      animationDuration: 280, animationDurationUpdate: 280,
      textStyle: { fontFamily: t.fBody, color: t.ink2, fontSize: 12 },
      tooltip: { trigger: 'axis', confine: true, backgroundColor: t.panel, borderColor: t.rule,
        textStyle: { color: t.ink, fontFamily: t.fBody, fontSize: 12 }, axisPointer: { lineStyle: { color: t.muted }, shadowStyle: { color: t.chip, opacity: .6 } } },
      legend: { top: 0, left: 0, type: 'scroll', icon: 'roundRect', itemWidth: 12, itemHeight: 8, itemGap: 14,
        textStyle: { color: t.ink2, fontSize: 12 }, pageTextStyle: { color: t.ink2 }, pageIconColor: t.ink2, pageIconInactiveColor: t.rule },
      grid: { left: 6, right: 18, top: 34, bottom: 6, containLabel: true },
    };
  }
  function axis(t, o = {}) {
    return Object.assign({
      axisLine: { lineStyle: { color: t.rule } }, axisTick: { show: false },
      axisLabel: { color: t.muted, fontFamily: t.fMono, fontSize: 11, hideOverlap: true },
      splitLine: { lineStyle: { color: t.rule, type: [3, 3] } },
      nameTextStyle: { color: t.muted, fontSize: 11, fontFamily: t.fBody },
    }, o);
  }
  function chart(id, build) {
    const el = document.getElementById(id);
    const c = { el, build, inst: null };
    if (!el) return c;
    if (!hasLib()) {
      el.innerHTML = '<div class="nolib">The chart library did not load. The numbers in the cards and tables are still current.</div>';
      return c;
    }
    c.inst = echarts.init(el, null, { renderer: 'svg' });
    c.inst.setOption(build(theme()), true);
    charts.push(c);
    return c;
  }
  function update(c) { if (c && c.inst) c.inst.setOption(c.build(theme()), true); }
  function refreshAll() { charts.forEach(update); }
  let rt;
  window.addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => charts.forEach((c) => c.inst && c.inst.resize()), 120); });
  try { matchMedia('(prefers-color-scheme: dark)').addEventListener('change', refreshAll); } catch (e) { /* old browsers */ }
  new MutationObserver(refreshAll).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

  // ---------- per-viewer memory for slicers (optional; page works without it)
  const KEY = 'scm-twin:' + location.pathname.split('/').pop();
  const load = () => { try { return JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { return {}; } };
  const save = (state) => { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) { /* storage blocked */ } };

  // ---------- segmented slicer
  function seg(el, options, value, onChange) {
    el.innerHTML = '';
    options.forEach(([v, label]) => {
      const b = document.createElement('button');
      b.type = 'button'; b.textContent = label; b.dataset.v = String(v);
      b.setAttribute('aria-pressed', String(String(v) === String(value)));
      b.addEventListener('click', () => {
        el.querySelectorAll('button').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
        onChange(v);
      });
      el.appendChild(b);
    });
    return { set(v) { el.querySelectorAll('button').forEach((x) => x.setAttribute('aria-pressed', String(x.dataset.v === String(v)))); } };
  }
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s).replace(/[&<>"]/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch]));
  const tip = (t, rows, title) => `<div style="font-weight:600;margin-bottom:4px">${esc(title)}</div>` +
    rows.map(([color, name, val]) => `<div style="display:flex;justify-content:space-between;gap:18px"><span><span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:${color};margin-right:6px"></span>${esc(name)}</span><span style="font-family:${t.fMono}">${val}</span></div>`).join('');
  return { theme, usd, num, kunits, pct, axUsd, base, axis, chart, update, refreshAll, load, save, seg, $, esc, tip, hasLib };
})();
