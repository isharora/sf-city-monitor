/* stats.js - pooling, deflation and formatting helpers shared by every dashboard.
   These are the algorithms the production build should use (see the DATA_CONTRACT files). */
(function () {
  const M = (window.SFCM = window.SFCM || {});

  /** Sum a numeric field over rows. */
  /** Sum a numeric field (or accessor) over rows; null, NaN and non-numbers count as 0. */
  const sum = (rows, f) => rows.reduce((a, r) => { const v = typeof f === 'function' ? f(r) : r[f]; return a + (typeof v === 'number' && isFinite(v) ? v : 0); }, 0);
  /** Group rows by key -> Map(key -> rows). */
  function group(rows, keyFn) { const m = new Map(); for (const r of rows) { const k = keyFn(r); if (!m.has(k)) m.set(k, []); m.get(k).push(r); } return m; }
  /** Quantiles of a numeric array (linear interpolation). */
  function quantiles(vals, ps) {
    const v = vals.filter((x) => x != null && !isNaN(x)).sort((a, b) => a - b);
    if (!v.length) return null;
    const q = (p) => { const i = (v.length - 1) * p, lo = Math.floor(i), hi = Math.ceil(i); return v[lo] + (v[hi] - v[lo]) * (i - lo); };
    const out = {}; (ps || [0.25, 0.5, 0.75, 0.9]).forEach((p) => (out['p' + Math.round(p * 100)] = q(p))); return out;
  }
  const median = (vals) => { const q = quantiles(vals, [0.5]); return q ? q.p50 : null; };
  /** Histogram of values into fixed-width bins (last bin is overflow). */
  function hist(vals, width, bins) { const h = new Array(bins).fill(0); for (const v of vals) { if (v == null) continue; h[Math.min(bins - 1, Math.floor(v / width))]++; } return h; }
  /** Cumulative incidence with right-censoring: events[] (months, or null if not yet), followup[] (months observed). */
  function incidence(events, followup, stepMonths, intervals) {
    let atRisk = events.length, F = 0, S = 1; const out = [];
    for (let k = 0; k < intervals; k++) {
      const t0 = k * stepMonths, t1 = t0 + stepMonths;
      let d = 0, c = 0;
      for (let i = 0; i < events.length; i++) {
        const e = events[i], f = followup[i];
        if (e != null && e >= t0 && e < t1) d++;
        else if (e == null && f >= t0 && f < t1) c++;
      }
      if (atRisk > 0) { F += (S * d) / atRisk; S *= 1 - d / atRisk; }
      atRisk -= d + c;
      out.push(F);
    }
    return out;
  }
  /** Deflate nominal dollars of fiscal year fy to base-year dollars. */
  function real(amount, fy, deflator) { if (amount == null) return null; const idx = deflator && deflator.index && deflator.index[String(fy)]; return idx ? amount / idx : amount; }
  /** Simple string hash (deterministic layouts). */
  function hash(s) { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return (h >>> 0) / 4294967295; }

  const ok = (x) => typeof x === 'number' && isFinite(x);
  const fmt = {
    int(n) { return !ok(n) ? '–' : Math.round(n).toLocaleString('en-US'); },
    pct(x, d = 0) { return !ok(x) ? '–' : `${(x * 100).toFixed(d)}%`; },
    signedPct(x, d = 0) { if (!ok(x)) return '–'; const s = (Math.abs(x) * 100).toFixed(d); return (+s === 0 ? '' : x > 0 ? '+' : '−') + `${s}%`; },
    signed(x, d = 1) { return !ok(x) ? '–' : (x > 0 ? '+' : x < 0 ? '−' : '') + Math.abs(x).toFixed(d); },
    money(n, d) {
      if (!ok(n)) return '–';
      const a = Math.abs(n), s = n < 0 ? '−' : '';
      if (a >= 1e9) return `${s}$${(a / 1e9).toFixed(d == null ? 2 : d)}B`;
      if (a >= 1e6) return `${s}$${(a / 1e6).toFixed(d == null ? (a >= 1e8 ? 0 : 1) : d)}M`;
      if (a >= 1e3) return `${s}$${(a / 1e3).toFixed(d == null ? (a >= 1e5 ? 0 : 1) : d)}k`;
      return `${s}$${Math.round(a)}`;
    },
    moneyLong(n) { return !ok(n) ? '–' : (n < 0 ? '−' : '') + '$' + Math.round(Math.abs(n)).toLocaleString('en-US'); },
    months(m) { if (!ok(m)) return '–'; return m < 10 ? m.toFixed(1) : String(Math.round(m)); },
    num(x, d = 1) { return !ok(+x) || x == null || x === '' ? '–' : (+x).toLocaleString('en-US', { maximumFractionDigits: d, minimumFractionDigits: 0 }); },
    fy(y) { return `FY${y}`; },
    range(a, b, pre) { pre = pre || ''; return a === b ? `${pre}${a}` : `${pre}${a}–${pre}${b}`; },
    date(s) { if (!s || typeof s !== 'string') return '–'; const [y, m, d] = s.split('-'); const mo = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][+m - 1]; if (!mo) return s; return d ? `${mo} ${+d}, ${y}` : `${mo} ${y}`; },
    monthYear(s) { if (!s) return '–'; const [y, m] = s.split('-'); const mo = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][+m - 1]; return mo ? `${mo} ${y}` : s; },
    bytes(b) { if (!ok(b)) return '–'; return b >= 1e6 ? `${(b / 1e6).toFixed(2)} MB` : `${Math.max(1, Math.round(b / 1e3))} KB`; },
    list(items, max = 3) { if (!items.length) return ''; if (items.length <= max) return items.length === 1 ? items[0] : items.slice(0, -1).join(', ') + ' and ' + items[items.length - 1]; return items.slice(0, max).join(', ') + ` and ${items.length - max} more`; },
    ratio(x) { return !ok(x) ? '–' : `${x.toFixed(x < 10 ? 1 : 0)}×`; },
  };
  M.stats = { sum, group, quantiles, median, hist, incidence, real, hash, fmt };
})();
