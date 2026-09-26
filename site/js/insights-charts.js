/* insights-charts.js - one focused SVG chart per insight (the insights views, js/views-insights.js). No dependencies.
   Ported from design/insights/prototype/js/insights-charts.js; site changes: the tooltip element is shared with
   js/charts.js (one .tip in the page), and every chart SVG gets a <title> and an aria-label.
   Nine forms from INSIGHTS_CONTRACT.json: line, bar, hbar, dumbbell, slope, stacked, smallmultiples, scatter, waterfall.
   Rules (INSIGHTS_DESIGN.md §5): one idea per chart; the highlighted series/category is series-1 blue and everything
   else is neutral grey; direct labels on the highlighted mark and the extremes only; hairline solid gridlines; 2px lines;
   bars <= 24px with a 4px rounded data end; every mark focusable with the shared tooltip; a table twin for every chart.
   Colours are CSS classes (mk-hi, mk-lo, mk-s1..7, mk-pos, mk-neg, mk-total) so light/dark need no re-render. */
(function () {
  const M = (window.SFCM = window.SFCM || {});
  const NS = 'http://www.w3.org/2000/svg';

  // ---------------------------------------------------------------- helpers
  function svgEl(tag, attrs, parent) {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs || {}) { const v = attrs[k]; if (v == null) continue; if (typeof v === 'number' && !isFinite(v)) continue; e.setAttribute(k, v); }
    if (parent) parent.appendChild(e); return e;
  }
  function txt(parent, x, y, str, cls, attrs) { const t = svgEl('text', Object.assign({ x, y, class: cls || 'ax-label' }, attrs || {}), parent); t.textContent = str == null ? '' : String(str); return t; }
  function h(tag, cls, parent, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; if (parent) parent.appendChild(e); return e; }
  const finite = (v) => typeof v === 'number' && isFinite(v);
  const textW = (s, size) => String(s == null ? '' : s).length * (size || 12) * 0.56; // system-ui average advance
  function niceTicks(min, max, count) {
    if (!(max - min > 0)) return [min, min + 1];
    const raw = (max - min) / count, mag = Math.pow(10, Math.floor(Math.log10(raw))), norm = raw / mag;
    const step = (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * mag;
    const t = []; for (let v = Math.floor(min / step + 1e-9) * step; v <= max + 1e-9; v += step) t.push(+v.toFixed(8));
    return t;
  }
  const lin = (d0, d1, r0, r1) => { const f = (v) => r0 + ((v - d0) / (d1 - d0 || 1)) * (r1 - r0); f.domain = [d0, d1]; return f; };
  const logS = (d0, d1, r0, r1) => { const l0 = Math.log10(d0), l1 = Math.log10(d1); const f = (v) => r0 + ((Math.log10(Math.max(v, d0 / 10)) - l0) / (l1 - l0 || 1)) * (r1 - r0); f.domain = [d0, d1]; return f; };
  function measure(el, fallback) { const w = el.getBoundingClientRect().width; return w > 80 ? w : fallback || 560; }

  /** Value formatting by unit (contract: index | $ | $M | $B | % | min | count | ratio). */
  function fmtVal(v, unit, opts) {
    if (!finite(v)) return '–';
    const o = opts || {}; const sign = o.signed && v > 0 ? '+' : '';
    if (v === 0 && (unit === '$' || unit === '$M' || unit === '$B')) return '$0';
    const dec = (n, d) => n.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
    switch (unit) {
      case '$': return sign + (Math.abs(v) >= 1e9 ? '$' + dec(v / 1e9, 2) + 'B' : Math.abs(v) >= 1e6 ? '$' + dec(v / 1e6, Math.abs(v) >= 1e8 ? 0 : 1) + 'M' : '$' + dec(v, 0)).replace('$-', '-$');
      case '$M': return (v < 0 ? '-' : sign) + (Math.abs(v) >= 1000 ? '$' + dec(Math.abs(v) / 1000, 2) + 'B' : '$' + dec(Math.abs(v), Math.abs(v) < 10 ? 1 : 0) + 'M');
      case '$B': return (v < 0 ? '-' : sign) + '$' + dec(Math.abs(v), 2) + 'B';
      case '%': return sign + dec(v, Math.abs(v) < 10 && v % 1 !== 0 ? 1 : 0) + '%';
      case 'min': { const m = Math.floor(v), s = Math.round((v - m) * 60); return `${m}:${String(s).padStart(2, '0')}`; }
      case 'ratio': return sign + dec(v, 2) + '×';
      case 'index': return sign + (Math.abs(v) < 2 ? v.toLocaleString('en-US', { maximumFractionDigits: 2 }) : dec(v, 0));
      case 'count': default: return sign + dec(v, Math.abs(v) < 10 && v % 1 !== 0 ? 1 : 0);
    }
  }
  const tickFmt = (v, unit) => unit === 'min' ? fmtVal(v, 'min') : unit === '$' ? (Math.abs(v) >= 1e6 ? fmtVal(v, '$') : '$' + v.toLocaleString('en-US')) : fmtVal(v, unit);
  // Years are prefixed FY only when the x axis says it is a fiscal year (calendar-year series such as surveys stay plain).
  let FY = true;
  const isYear = (v) => typeof v === 'number' && v > 1900 && v < 2100;
  const xLabel = (v) => isYear(v) ? (FY ? 'FY' + String(v).slice(2) : String(v)) : String(v);
  const xLabelLong = (v) => isYear(v) ? (FY ? 'FY' + v : String(v)) : String(v);

  // ---------------------------------------------------------------- tooltip (single, shared with the site's .tip styles)
  let tipEl;
  function tip() { if (!tipEl || !tipEl.isConnected) { tipEl = document.querySelector('body > .tip') || h('div', 'tip', document.body); tipEl.setAttribute('role', 'tooltip'); tipEl.hidden = true; } return tipEl; }
  function showTip(evt, title, rows, anchor) {
    const t = tip(); t.innerHTML = '';
    if (title) h('div', 'tip-title', t, title);
    for (const r of rows) { const row = h('div', 'tip-row' + (r.muted ? ' muted' : ''), t); const k = h('span', 'tip-key', row); if (r.key) k.className += ' ' + r.key; else k.style.visibility = 'hidden'; h('span', 'tip-val', row, r.value); h('span', 'tip-label', row, r.label); }
    t.hidden = false;
    const pad = 14; let x = (anchor ? anchor.x : evt.clientX) + pad, y = (anchor ? anchor.y : evt.clientY) + pad;
    const r = t.getBoundingClientRect();
    if (x + r.width > window.innerWidth - 8) x = (anchor ? anchor.x : evt.clientX) - r.width - pad;
    if (y + r.height > window.innerHeight - 8) y = (anchor ? anchor.y : evt.clientY) - r.height - pad;
    t.style.transform = `translate(${Math.max(4, x)}px, ${Math.max(4, y)}px)`;
  }
  function hideTip() { if (tipEl) tipEl.hidden = true; }
  window.addEventListener('scroll', hideTip, { passive: true });
  function centerOf(g) { const r = g.getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 }; }
  function hover(g, title, rows) {
    g.setAttribute('tabindex', '0'); g.setAttribute('role', 'img');
    const show = (e) => showTip(e, title, rows, e.type === 'focus' ? centerOf(g) : null);
    g.addEventListener('pointermove', show); g.addEventListener('pointerleave', hideTip);
    g.addEventListener('focus', (e) => { show(e); g.setAttribute('aria-label', [title].concat(rows.map((r) => `${r.value} ${r.label}`)).join('; ')); });
    g.addEventListener('blur', hideTip);
  }

  // ---------------------------------------------------------------- frame
  /** Standard frame: svg with role=img and <title>, y gridlines + ticks, returns scales and the plot group. */
  const annRows = (ch) => Math.max(0, ((ch && ch.annotations) || []).length - 1);
  function frame(el, o) {
    const W = o.width, H = o.height, p = o.pad;
    const svg = svgEl('svg', { viewBox: `0 0 ${W} ${H}`, width: '100%', height: H, role: 'img', class: 'ich' }, el);
    svgEl('title', {}, svg).textContent = o.title || '';
    const g = svgEl('g', {}, svg);
    return { svg, g, W, H, p, x0: p.l, x1: W - p.r, y0: p.t, y1: H - p.b };
  }
  function yGrid(f, y, ticks, unit, o) {
    const grid = svgEl('g', { class: 'grid' }, f.g);
    ticks.forEach((t) => { const yy = y(t); if (yy < f.y0 - 1) return; svgEl('line', { x1: f.x0, x2: f.x1, y1: yy, y2: yy, class: t === 0 ? 'baseline' : 'gridline' }, grid); txt(grid, f.x0 - 8, yy + 4, tickFmt(t, unit), 'ax-label tnum', { 'text-anchor': 'end' }); });
    if (o && o.axisLabel) txt(f.g, f.x0 - 8, f.y0 - 10, o.axisLabel, 'ax-title', { 'text-anchor': 'start', x: f.x0 - 8 + 0 });
  }
  function xTicksTime(f, xs, x, o) {
    const n = xs.length, maxLabels = Math.max(2, Math.floor((f.x1 - f.x0) / 52));
    const every = Math.ceil(n / maxLabels);
    xs.forEach((v, i) => { if (i % every !== 0 && i !== n - 1) return; if (i === n - 1 && n > 1 && (n - 1) % every !== 0 && (x(v) - x(xs[n - 1 - ((n - 1) % every)])) < 44) return; txt(f.g, x(v), f.y1 + 17, xLabel(v), 'ax-label tnum', { 'text-anchor': 'middle' }); });
  }
  /** Vertical annotation: hairline at x with a boxed label clamped inside the plot. */
  function annotateX(f, ann, x, unit) {
    const boxes = [];
    (ann || []).forEach((a) => {
      const xx = x(a.x); if (!finite(xx)) return;
      const w = textW(a.label, 11.5) + 12; let lx = xx + 6; if (lx + w > f.x1) lx = xx - w - 6;
      let ly = f.y0 - 12; while (boxes.some((b) => lx < b.x + b.w + 4 && lx + w + 4 > b.x && Math.abs(b.y - ly) < 18)) ly -= 20; // stagger overlapping boxes upward into the headroom the frame reserved
      boxes.push({ x: lx, y: ly, w });
      svgEl('line', { x1: xx, x2: xx, y1: ly + 9, y2: f.y1, class: 'ann-line' }, f.g);
      const bg = svgEl('rect', { x: lx, y: ly, width: w, height: 18, rx: 4, class: 'ann-box' }, f.g);
      txt(f.g, lx + 6, ly + 13, a.label, 'ann-label');
      bg.setAttribute('aria-hidden', 'true');
    });
  }
  /** Optional reference line y.ref = {value, label} (e.g. 100% = adopted budget). */
  function refLine(f, ch, scale, horizontal) {
    const r = ch.y && ch.y.ref; if (!r || !finite(r.value)) return;
    if (horizontal) { svgEl('line', { x1: scale(r.value), x2: scale(r.value), y1: f.y0, y2: f.y1, class: 'ref-line' }, f.g); if (r.label) txt(f.g, scale(r.value) + 4, f.y0 + 4, r.label, 'ann-label'); }
    else { svgEl('line', { x1: f.x0, x2: f.x1, y1: scale(r.value), y2: scale(r.value), class: 'ref-line' }, f.g); if (r.label) txt(f.g, f.x1, scale(r.value) - 4, r.label, 'ann-label', { 'text-anchor': 'end' }); }
  }
  const isHi = (hl, name) => hl == null ? false : Array.isArray(hl) ? hl.some((x) => String(x) === String(name)) : String(hl) === String(name);
  function legend(el, items) {
    const lg = h('div', 'ich-legend', el);
    items.forEach((it) => { const sp = h('span', 'lg-item' + (it.muted ? ' muted' : ''), lg); h('i', 'lg-key ' + it.cls, sp); sp.appendChild(document.createTextNode(it.name)); });
    return lg;
  }
  const seriesCls = (ch, name, i) => (ch.highlight != null ? (isHi(ch.highlight, name) ? 'mk-hi' : 'mk-lo') : ch.series.length === 1 ? 'mk-hi' : 'mk-s' + (Math.min(i, 6) + 1));

  // ---------------------------------------------------------------- line
  function line(el, ch, o) {
    const W = measure(el, 560), unit = ch.y.unit, xs = ch.x.values, ser = ch.series;
    // End labels ("151 Calls") for up to four series; a name too long for the label column (at most 30% of the width) wraps onto a second line.
    const lastOf = (s) => { for (let j = s.values.length - 1; j >= 0; j--) if (finite(s.values[j])) return s.values[j]; return null; };
    const endLabels = ser.length <= 4;
    const need = endLabels ? Math.max(...ser.map((s) => textW(s.name, 12) + textW(fmtVal(lastOf(s), unit), 12) + 12)) : 0;
    const labelW = endLabels ? Math.min(Math.max(150, W * 0.3), need) : 0;
    const endLines = (name, v) => { const room = Math.floor((labelW - 10) / (12 * 0.56)), lead = fmtVal(v, unit).length + 1; if (lead + name.length <= room) return [name]; const words = name.split(' '); const l1 = []; while (words.length && (lead + [...l1, words[0]].join(' ').length <= room || !l1.length)) l1.push(words.shift()); return words.length ? [l1.join(' '), words.join(' ')] : [l1.join(' ')]; };
    const f = frame(el, { width: W, height: (o.height || 220) + 20 * annRows(ch), pad: { l: 52, r: 16 + labelW, t: 22 + 20 * annRows(ch), b: 26 }, title: ch.title });
    const all = ser.flatMap((s) => s.values).filter(finite);
    let lo = Math.min(0, ...all), hi = Math.max(...all);
    if (unit === 'index') { lo = Math.min(...all, 100) * 0.9; }
    const ticks = niceTicks(lo, hi, 4); lo = ticks[0]; hi = Math.max(hi, ticks[ticks.length - 1]) + (hi - lo) * 0.12; // 12% headroom keeps annotation labels off the line
    const x = lin(0, xs.length - 1, f.x0, f.x1), y = lin(lo, hi, f.y1, f.y0);
    yGrid(f, y, ticks, unit); xTicksTime(f, xs, (v) => x(xs.indexOf(v))); refLine(f, ch, y, false);
    if (unit === 'index') svgEl('line', { x1: f.x0, x2: f.x1, y1: y(100), y2: y(100), class: 'baseline' }, f.g);
    annotateX(f, ch.annotations, (v) => x(xs.indexOf(v)));
    const order = ser.map((s, i) => i).sort((a, b) => (isHi(ch.highlight, ser[a].name) ? 1 : 0) - (isHi(ch.highlight, ser[b].name) ? 1 : 0));
    const ends = [];
    order.forEach((i) => {
      const s = ser[i], cls = seriesCls(ch, s.name, i);
      const pts = s.values.map((v, j) => (finite(v) ? [x(j), y(v)] : null));
      let d = '', pen = false; pts.forEach((p) => { if (!p) { pen = false; return; } d += (pen ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1); pen = true; });
      const g = svgEl('g', { class: 'series ' + cls }, f.g);
      svgEl('path', { d, class: 'ln' }, g);
      if (xs.length <= 20) pts.forEach((p) => p && svgEl('circle', { cx: p[0], cy: p[1], r: 3.2, class: 'dot' }, g));
      // hit bands per x, one tooltip per point (crosshair-like)
      pts.forEach((p, j) => { if (!p) return; const hit = svgEl('rect', { x: x(j) - (f.x1 - f.x0) / (xs.length * 2), y: f.y0, width: (f.x1 - f.x0) / xs.length, height: f.y1 - f.y0, class: 'hit' }, g); hover(hit, xLabelLong(xs[j]), ser.map((t, k) => ({ key: seriesCls(ch, t.name, k), value: fmtVal(t.values[j], unit), label: t.name }))); });
      const last = pts.map((p, j) => [p, j]).filter((q) => q[0]).pop();
      if (last) ends.push({ y: last[0][1], name: s.name, v: s.values[last[1]], cls });
    });
    if (endLabels) {
      ends.forEach((e) => { e.lines = endLines(String(e.name), e.v); });
      ends.sort((a, b) => a.y - b.y);
      for (let i = 1; i < ends.length; i++) { const gap = 14 + 13 * (ends[i - 1].lines.length - 1); if (ends[i].y - ends[i - 1].y < gap) ends[i].y = ends[i - 1].y + gap; }
      const over = ends.length ? ends[ends.length - 1].y + 13 * (ends[ends.length - 1].lines.length - 1) - (f.y1 + 4) : 0; // push the stack back inside the plot
      if (over > 0) ends.forEach((e) => { e.y -= over; });
      ends.forEach((e) => { const t = txt(f.g, f.x1 + 8, e.y + 4, '', 'end-label ' + (e.cls === 'mk-lo' ? 'muted' : 'strong')); const b = svgEl('tspan', { class: 'tnum' }, t); b.textContent = fmtVal(e.v, unit); const n = svgEl('tspan', {}, t); n.textContent = ' ' + e.lines[0]; e.lines.slice(1).forEach((l) => { const c = svgEl('tspan', { x: f.x1 + 8, dy: 13 }, t); c.textContent = l; }); });
    } else legend(el, ser.map((s, i) => ({ name: s.name, cls: seriesCls(ch, s.name, i) })));
    return twin(ch, xLabelLong);
  }

  // ---------------------------------------------------------------- bar (columns)
  function bar(el, ch, o) {
    if (ch.series.length > 1) return groupedBar(el, ch, o);
    const W = measure(el, 560), unit = ch.y.unit, cats = ch.x.values, s = ch.series[0], vals = s.values;
    const f = frame(el, { width: W, height: (o.height || 220) + 20 * annRows(ch), pad: { l: 52, r: 12, t: 26 + 20 * annRows(ch), b: cats.some((c) => typeof c === 'string' && c.length > 9) ? 40 : 26 }, title: ch.title });
    const hi = Math.max(...vals.filter(finite)), lo = Math.min(0, ...vals.filter(finite));
    const ticks = niceTicks(lo, hi, 4); const y = lin(ticks[0], Math.max(hi, ticks[ticks.length - 1]), f.y1, f.y0);
    yGrid(f, y, ticks, unit);
    const n = cats.length, band = (f.x1 - f.x0) / n, bw = Math.min(24, band * 0.62);
    const xOf = (i) => f.x0 + band * (i + 0.5);
    const maxV = Math.max(...vals.filter(finite));
    cats.forEach((c, i) => {
      const v = vals[i]; if (!finite(v)) return;
      const hl = ch.highlight != null ? isHi(ch.highlight, c) : true;
      const g = svgEl('g', { class: 'mark ' + (hl ? 'mk-hi' : 'mk-lo') }, f.g);
      const top = Math.min(y(v), y(0)), hgt = Math.abs(y(v) - y(0));
      svgEl('path', { d: roundedTop(xOf(i) - bw / 2, top, bw, Math.max(hgt, 1), v >= 0 ? 4 : 0, v < 0 ? 4 : 0), class: 'bar' }, g);
      const hit = svgEl('rect', { x: f.x0 + band * i, y: f.y0, width: band, height: f.y1 - f.y0, class: 'hit' }, g);
      const rows = [{ key: hl ? 'mk-hi' : 'mk-lo', value: fmtVal(v, unit), label: s.name }]; if (s.n) rows.push({ muted: true, value: 'n = ' + s.n[i].toLocaleString('en-US'), label: '' });
      hover(hit, typeof c === 'string' ? c : xLabelLong(c), rows);
      // direct labels: highlighted + max + first/last when few
      if (hl || v === maxV || n <= 6) txt(f.g, xOf(i), top - 5, fmtVal(v, unit), 'val-label tnum' + (hl ? ' strong' : ''), { 'text-anchor': 'middle' });
    });
    // x labels: wrap long category names to two lines
    const every = Math.max(1, Math.ceil(n / Math.max(2, Math.floor((f.x1 - f.x0) / 48)))), lastReg = Math.floor((n - 1) / every) * every;
    cats.forEach((c, i) => {
      if (typeof c === 'number') { if (i % every === 0 || (i === n - 1 && (n - 1 - lastReg) * band >= 44)) txt(f.g, xOf(i), f.y1 + 17, xLabel(c), 'ax-label tnum', { 'text-anchor': 'middle' }); return; }
      const lines = wrap(String(c), Math.max(6, Math.floor(band / 6.3)), 2);
      lines.forEach((l, k) => txt(f.g, xOf(i), f.y1 + 17 + k * 13, l, 'ax-label', { 'text-anchor': 'middle' }));
    });
    annotateX(f, ch.annotations, (v) => { const i = cats.indexOf(v); return i < 0 ? NaN : xOf(i) - band / 2; });
    return twin(ch, (c) => typeof c === 'string' ? c : xLabelLong(c));
  }
  /** Grouped columns: one cluster per category, one column per series; highlight names a series. Legend always. */
  function groupedBar(el, ch, o) {
    const W = measure(el, 560), unit = ch.y.unit, cats = ch.x.values, ser = ch.series, k = ser.length;
    const f = frame(el, { width: W, height: o.height || 220, pad: { l: 52, r: 12, t: 26, b: cats.some((c) => typeof c === 'string' && c.length > 9) ? 40 : 26 }, title: ch.title });
    const all = ser.flatMap((s) => s.values).filter(finite), hi = Math.max(...all), lo = Math.min(0, ...all);
    const ticks = niceTicks(lo, hi, 4); const y = lin(ticks[0], Math.max(hi, ticks[ticks.length - 1]), f.y1, f.y0);
    yGrid(f, y, ticks, unit);
    const n = cats.length, band = (f.x1 - f.x0) / n, bw = Math.min(24, (band * 0.7) / k), gap = 3, cluster = k * bw + (k - 1) * gap;
    cats.forEach((c, j) => {
      const cx = f.x0 + band * (j + 0.5);
      ser.forEach((s, i) => {
        const v = s.values[j]; if (!finite(v)) return;
        const cls = seriesCls(ch, s.name, i), hl = ch.highlight == null || isHi(ch.highlight, s.name);
        const x0 = cx - cluster / 2 + i * (bw + gap), top = Math.min(y(v), y(0)), hgt = Math.abs(y(v) - y(0));
        const g = svgEl('g', { class: 'mark ' + cls }, f.g);
        svgEl('path', { d: roundedTop(x0, top, bw, Math.max(hgt, 1), v >= 0 ? 4 : 0, v < 0 ? 4 : 0), class: 'bar' }, g);
        const hit = svgEl('rect', { x: x0 - gap / 2, y: f.y0, width: bw + gap, height: f.y1 - f.y0, class: 'hit' }, g);
        hover(hit, typeof c === 'string' ? c : xLabelLong(c), ser.map((t, m) => ({ key: seriesCls(ch, t.name, m), value: fmtVal(t.values[j], unit), label: t.name })));
        if (hl || n * k <= 8) txt(f.g, x0 + bw / 2, top - 5, fmtVal(v, unit), 'val-label tnum' + (hl && ch.highlight != null ? ' strong' : ''), { 'text-anchor': 'middle' });
      });
      if (typeof c === 'number') txt(f.g, cx, f.y1 + 17, xLabel(c), 'ax-label tnum', { 'text-anchor': 'middle' });
      else wrap(String(c), Math.max(6, Math.floor(band / 6.3)), 2).forEach((l, m) => txt(f.g, cx, f.y1 + 17 + m * 13, l, 'ax-label', { 'text-anchor': 'middle' }));
    });
    annotateX(f, ch.annotations, (v) => { const i = cats.indexOf(v); return i < 0 ? NaN : f.x0 + band * i; });
    legend(el, ser.map((s, i) => ({ name: s.name, cls: seriesCls(ch, s.name, i) })));
    return twin(ch, (c) => typeof c === 'string' ? c : xLabelLong(c));
  }
  function roundedTop(x, y, w, hgt, rTop, rBot) {
    const r = Math.min(rTop, w / 2, hgt), rb = Math.min(rBot, w / 2, hgt);
    return `M${x} ${y + r} q0 -${r} ${r} -${r} h${w - 2 * r} q${r} 0 ${r} ${r} v${hgt - r - rb} q0 ${rb} -${rb} ${rb} h-${w - 2 * rb} q-${rb} 0 -${rb} -${rb} z`;
  }
  function roundedRight(x, y, w, hgt, r) { r = Math.min(r, hgt / 2, Math.abs(w)); if (w >= 0) return `M${x} ${y} h${w - r} q${r} 0 ${r} ${r} v${hgt - 2 * r} q0 ${r} -${r} ${r} h-${w - r} z`; w = -w; return `M${x} ${y} h-${w - r} q-${r} 0 -${r} ${r} v${hgt - 2 * r} q0 ${r} ${r} ${r} h${w - r} z`; }
  function wrap(s, maxChars, maxLines) {
    const words = s.replace(/-/g, '-\u200b').split(/ |\u200b/), lines = []; let cur = '';
    const join = (a, b) => a.endsWith('-') ? a + b : (a + ' ' + b).trim();
    words.forEach((w) => { if (join(cur, w).length > maxChars && cur) { lines.push(cur); cur = w; } else cur = join(cur, w); });
    if (cur) lines.push(cur);
    if (lines.length > maxLines) { const keep = lines.slice(0, maxLines); keep[maxLines - 1] = keep[maxLines - 1].replace(/\s+\S*$/, '') + '…'; return keep; }
    return lines;
  }

  // ---------------------------------------------------------------- hbar (rows; diverging when any value < 0)
  function hbar(el, ch, o) {
    const W = measure(el, 560), unit = ch.y.unit, cats = ch.x.values, s = ch.series[0], vals = s.values;
    const diverging = vals.some((v) => v < 0);
    const longLabels = cats.some((c) => String(c).length > 26);
    const labW = Math.min(longLabels ? 180 : 190, Math.max(...cats.map((c) => textW(longLabels ? String(c).slice(0, 26) : c, 12.5))) + 8);
    const nW = s.n ? 64 : 0, valW = Math.max(...vals.map((v) => textW(fmtVal(v, unit, { signed: diverging }), 12))) + 12;
    const rowH = longLabels ? 34 : 26, f = frame(el, { width: W, height: cats.length * rowH + 20, pad: { l: labW + 8, r: nW + valW, t: 6, b: 14 }, title: ch.title });
    const mx = Math.max(...vals.map(Math.abs).filter(finite));
    const x = diverging ? lin(-mx, mx, f.x0, f.x1) : lin(0, mx, f.x0, f.x1);
    svgEl('line', { x1: x(0), x2: x(0), y1: f.y0, y2: f.y1, class: 'baseline' }, f.g);
    refLine(f, ch, x, true);
    cats.forEach((c, i) => {
      const v = vals[i], yy = f.y0 + i * rowH, bh = Math.min(20, rowH - 12);
      const hl = ch.highlight != null ? isHi(ch.highlight, c) : true;
      const cls = diverging ? (v >= 0 ? 'mk-pos' : 'mk-neg') + (ch.highlight != null && !hl ? ' dim' : '') : hl ? 'mk-hi' : 'mk-lo';
      const g = svgEl('g', { class: 'mark ' + cls }, f.g);
      if (finite(v)) svgEl('path', { d: roundedRight(x(0), yy + (rowH - bh) / 2, x(v) - x(0), bh, 4), class: 'bar' }, g);
      const hit = svgEl('rect', { x: 0, y: yy, width: W, height: rowH, class: 'hit' }, g);
      const rows = [{ key: cls.split(' ')[0], value: fmtVal(v, unit, { signed: diverging }), label: s.name }]; if (s.n) rows.push({ muted: true, value: 'n = ' + s.n[i].toLocaleString('en-US'), label: '' });
      hover(hit, String(c), rows);
      const lines = longLabels ? wrap(String(c), 26, 2) : [String(c)];
      lines.forEach((l, k) => txt(f.g, f.x0 - 8, yy + rowH / 2 + 4 + (k - (lines.length - 1) / 2) * 13, l, 'row-label' + (hl && ch.highlight != null ? ' strong' : ''), { 'text-anchor': 'end' }));
      const lab = fmtVal(v, unit, { signed: diverging }), lw = textW(lab, 12);
      const inside = v < 0 && (x(0) - x(v)) > lw + 14; // a long negative bar would put its tip label on the row names
      const lx = inside ? x(v) + 6 : v >= 0 ? x(v) + 6 : x(v) - 6;
      txt(f.g, lx, yy + rowH / 2 + 4, lab, (inside ? 'in-label onhi tnum' : 'val-label tnum') + (hl && ch.highlight != null && !inside ? ' strong' : ''), { 'text-anchor': inside || v >= 0 ? 'start' : 'end' });
      if (s.n) txt(f.g, W - 4, yy + rowH / 2 + 4, 'n ' + s.n[i].toLocaleString('en-US'), 'n-label tnum', { 'text-anchor': 'end' });
    });
    if (diverging) legend(el, [{ name: 'over budget', cls: 'mk-pos' }, { name: 'under budget', cls: 'mk-neg' }]);
    return twin(ch, String);
  }

  // ---------------------------------------------------------------- dumbbell
  function dumbbell(el, ch, o) {
    const W = measure(el, 560), unit = ch.y.unit, cats = ch.x.values, a = ch.series[0], b = ch.series[1];
    const longLabels = cats.some((c) => c.length > 30);
    const labW = Math.min(longLabels ? 200 : 230, Math.max(...cats.map((c) => textW(longLabels ? c.slice(0, 30) : c, 12.5))) + 8);
    const rowH = longLabels ? 36 : 30, f = frame(el, { width: W, height: cats.length * rowH + 28, pad: { l: labW + 8, r: 72, t: 8, b: 22 }, title: ch.title });
    const all = a.values.concat(b.values).filter(finite);
    const ticks = niceTicks(0, Math.max(...all), 4); const x = lin(0, Math.max(ticks[ticks.length - 1], Math.max(...all)), f.x0, f.x1);
    ticks.forEach((t) => { svgEl('line', { x1: x(t), x2: x(t), y1: f.y0, y2: f.y1, class: t === 0 ? 'baseline' : 'gridline' }, f.g); txt(f.g, x(t), f.y1 + 15, tickFmt(t, unit), 'ax-label tnum', { 'text-anchor': 'middle' }); });
    cats.forEach((c, i) => {
      const v0 = a.values[i], v1 = b.values[i], yy = f.y0 + i * rowH + rowH / 2;
      const hl = ch.highlight != null ? isHi(ch.highlight, c) : true;
      const g = svgEl('g', { class: 'mark ' + (hl ? 'mk-hi' : 'mk-lo') }, f.g);
      svgEl('line', { x1: x(v0), x2: x(v1), y1: yy, y2: yy, class: 'db-link' }, g);
      svgEl('circle', { cx: x(v0), cy: yy, r: 5.5, class: 'db-a' }, g);
      svgEl('circle', { cx: x(v1), cy: yy, r: 5.5, class: 'db-b' }, g);
      const hit = svgEl('rect', { x: 0, y: yy - rowH / 2, width: W, height: rowH, class: 'hit' }, g);
      const chg = v0 ? (v1 / v0 - 1) * 100 : NaN;
      hover(hit, String(c), [{ key: 'mk-lo', value: fmtVal(v0, unit), label: a.name }, { key: hl ? 'mk-hi' : 'mk-lo', value: fmtVal(v1, unit), label: b.name }, { muted: true, value: fmtVal(chg, '%', { signed: true }), label: 'change' }]);
      const lines = longLabels ? wrap(c, 30, 2) : [c];
      lines.forEach((l, k) => txt(f.g, f.x0 - 8, yy + 4 + (k - (lines.length - 1) / 2) * 13, l, 'row-label' + (hl && ch.highlight != null ? ' strong' : ''), { 'text-anchor': 'end' }));
      txt(f.g, f.x1 + 10, yy + 4, fmtVal(chg, '%', { signed: true }), 'val-label tnum' + (hl && ch.highlight != null ? ' strong' : ''), { 'text-anchor': 'start' });
    });
    legend(el, [{ name: a.name, cls: 'mk-lo db' }, { name: b.name, cls: 'mk-hi db' }, { name: 'change at right', cls: 'none' }]);
    return twin(ch, String);
  }

  // ---------------------------------------------------------------- slope
  function slope(el, ch, o) {
    const W = measure(el, 560), unit = ch.y.unit, ser = ch.series, [p0, p1] = ch.x.values;
    const labW = Math.min(170, Math.max(...ser.map((s) => textW(s.name, 12) + textW(fmtVal(Math.max(...s.values), unit), 12) + 10)));
    const f = frame(el, { width: W, height: Math.max(240, ser.length * 27), pad: { l: labW + 16, r: labW + 16, t: 22, b: 24 }, title: ch.title });
    const all = ser.flatMap((s) => s.values).filter(finite);
    const log = ch.y.scale === 'log';
    const y = log ? logS(Math.min(...all) * 0.85, Math.max(...all) * 1.12, f.y1, f.y0) : lin(0, Math.max(...all) * 1.05, f.y1, f.y0);
    [f.x0, f.x1].forEach((xx, k) => { svgEl('line', { x1: xx, x2: xx, y1: f.y0, y2: f.y1, class: 'axisline' }, f.g); txt(f.g, xx, f.y1 + 17, xLabelLong(k ? p1 : p0), 'ax-label tnum', { 'text-anchor': 'middle' }); });
    const left = [], right = [];
    const order = ser.map((s, i) => i).sort((a, b) => (isHi(ch.highlight, ser[a].name) ? 1 : 0) - (isHi(ch.highlight, ser[b].name) ? 1 : 0));
    order.forEach((i) => {
      const s = ser[i], hl = ch.highlight != null ? isHi(ch.highlight, s.name) : true, cls = hl ? 'mk-hi' : 'mk-lo';
      const g = svgEl('g', { class: 'series ' + cls }, f.g);
      svgEl('line', { x1: f.x0, x2: f.x1, y1: y(s.values[0]), y2: y(s.values[1]), class: 'ln' }, g);
      svgEl('circle', { cx: f.x0, cy: y(s.values[0]), r: 3.5, class: 'dot' }, g); svgEl('circle', { cx: f.x1, cy: y(s.values[1]), r: 3.5, class: 'dot' }, g);
      const hit = svgEl('polygon', { points: `${f.x0},${y(s.values[0]) - 6} ${f.x1},${y(s.values[1]) - 6} ${f.x1},${y(s.values[1]) + 6} ${f.x0},${y(s.values[0]) + 6}`, class: 'hit' }, g);
      hover(hit, s.name, [{ key: 'mk-lo', value: fmtVal(s.values[0], unit), label: xLabelLong(p0) }, { key: cls, value: fmtVal(s.values[1], unit), label: xLabelLong(p1) }, { muted: true, value: (s.values[1] / s.values[0]).toFixed(2) + '×', label: 'ratio' }]);
      left.push({ y: y(s.values[0]), text: `${s.name} ${fmtVal(s.values[0], unit)}`, hl }); right.push({ y: y(s.values[1]), text: `${fmtVal(s.values[1], unit)} ${s.name}`, hl });
    });
    [left, right].forEach((arr, side) => {
      arr.sort((a, b) => a.y - b.y); for (let i = 1; i < arr.length; i++) if (arr[i].y - arr[i - 1].y < 13) arr[i].y = arr[i - 1].y + 13;
      const over = arr.length ? arr[arr.length - 1].y - (f.y1 + 4) : 0; if (over > 0) { arr[arr.length - 1].y -= over; for (let i = arr.length - 2; i >= 0; i--) if (arr[i + 1].y - arr[i].y < 13) arr[i].y = arr[i + 1].y - 13; }
      arr.forEach((l) => txt(f.g, side ? f.x1 + 9 : f.x0 - 9, l.y + 4, l.text, 'end-label tnum ' + (l.hl ? 'strong' : 'muted'), { 'text-anchor': side ? 'start' : 'end' }));
    });
    if (log) txt(f.g, f.W / 2, f.y0 - 8, 'log scale', 'ax-title', { 'text-anchor': 'middle' });
    return twin(ch, xLabelLong);
  }

  // ---------------------------------------------------------------- stacked (100% or absolute columns)
  function stacked(el, ch, o) {
    const W = measure(el, 560), unit = ch.y.unit, cats = ch.x.values, ser = ch.series;
    // room at the right for the highlighted segment's value beside the last column (so it never sits on the column before)
    const hiSer = ch.highlight != null ? ser.find((s) => isHi(ch.highlight, s.name)) : null, hiLast = hiSer ? hiSer.values[hiSer.values.length - 1] : null;
    const padR = cats.length > 3 && finite(hiLast) ? 16 + textW(fmtVal(hiLast, unit), 12) : 12;
    const f = frame(el, { width: W, height: (o.height || 240) + 20 * annRows(ch), pad: { l: 44, r: padR, t: ((ch.annotations || []).length ? 26 : 12) + 20 * annRows(ch), b: 26 }, title: ch.title });
    const totals = cats.map((c, j) => ser.reduce((a, s) => a + (finite(s.values[j]) ? s.values[j] : 0), 0));
    const pct = unit === '%' && totals.every((t) => Math.abs(t - 100) < 1.5);
    const top = pct ? 100 : Math.max(...totals) * ((ch.annotations || []).length ? 1.1 : 1.02);
    const ticks = niceTicks(0, top, 4), y = lin(0, pct ? 100 : Math.max(top, ticks[ticks.length - 1]), f.y1, f.y0);
    yGrid(f, y, ticks, unit);
    const n = cats.length, band = (f.x1 - f.x0) / n, bw = Math.min(n <= 3 ? 64 : 36, band * 0.7);
    cats.forEach((c, j) => {
      let acc = 0; const cx = f.x0 + band * (j + 0.5);
      ser.forEach((s, i) => {
        const v = s.values[j]; if (!finite(v) || v <= 0) return;
        const hl = ch.highlight != null ? isHi(ch.highlight, s.name) : true;
        const cls = ch.highlight != null ? (hl ? 'mk-hi' : 'mk-lo l' + (i % 3)) : 'mk-s' + (Math.min(i, 6) + 1);
        const y1 = y(acc), y0 = y(acc + v); acc += v;
        const g = svgEl('g', { class: 'mark ' + cls }, f.g);
        svgEl('rect', { x: cx - bw / 2, y: y0 + 1, width: bw, height: Math.max(0, y1 - y0 - 2), class: 'seg' }, g);
        hover(g, typeof c === 'string' ? c : xLabelLong(c), [{ key: cls.split(' ')[0], value: fmtVal(v, unit), label: s.name }]);
        // label inside the segment when it fits (highlighted or tall)
        const fits = y1 - y0 > 14 && textW(fmtVal(v, unit), 11.5) < bw - 6;
        if (fits && ((hl && ch.highlight != null) || (y1 - y0 > 26 && bw >= 40))) txt(f.g, cx, (y0 + y1) / 2 + 4, fmtVal(v, unit), 'in-label tnum' + (hl && ch.highlight != null ? ' onhi' : ''), { 'text-anchor': 'middle' });
        else if (hl && ch.highlight != null && (n <= 3 || j === n - 1)) { const lab = n <= 3 ? fmtVal(v, unit) + ' ' + s.name : fmtVal(v, unit); const fitsRight = n <= 3 || cx + bw / 2 + 8 + textW(lab, 12) <= W; txt(f.g, fitsRight ? cx + bw / 2 + 6 : cx - bw / 2 - 6, (y0 + y1) / 2 + 4, lab, 'val-label tnum strong', { 'text-anchor': fitsRight ? 'start' : 'end' }); }
      });
      const every = Math.max(1, Math.ceil(n / Math.max(2, Math.floor((f.x1 - f.x0) / 48)))), lastReg = Math.floor((n - 1) / every) * every;
      if (typeof c === 'string' || j % every === 0 || (j === n - 1 && (n - 1 - lastReg) * band >= 44)) txt(f.g, cx, f.y1 + 17, typeof c === 'string' ? c : xLabel(c), 'ax-label tnum', { 'text-anchor': 'middle' });
    });
    annotateX(f, ch.annotations, (v) => { const i = cats.indexOf(v); return i < 0 ? NaN : f.x0 + band * i; });
    legend(el, ser.map((s, i) => ({ name: s.name, cls: ch.highlight != null ? (isHi(ch.highlight, s.name) ? 'mk-hi' : 'mk-lo l' + (i % 3)) : 'mk-s' + (Math.min(i, 6) + 1) })));
    return twin(ch, (c) => typeof c === 'string' ? c : xLabelLong(c));
  }

  // ---------------------------------------------------------------- small multiples (shared x and y)
  function smallmultiples(el, ch, o) {
    const W = measure(el, 560), unit = ch.y.unit, xs = ch.x.values, ser = ch.series;
    const cols = W >= 520 ? 3 : 2, rows = Math.ceil(ser.length / cols), pw = W / cols, ph = 128, shared = ch.y.shared !== false;
    const all = ser.flatMap((s) => s.values).filter(finite);
    const ticks = niceTicks(Math.min(...all, unit === 'index' ? 100 : 0) * (unit === 'index' ? 0.9 : 1), Math.max(...all), 3);
    const lo = ticks[0], hi = Math.max(...all, ticks[ticks.length - 1]);
    const svg = svgEl('svg', { viewBox: `0 0 ${W} ${rows * ph}`, width: '100%', height: rows * ph, role: 'img', class: 'ich' }, el);
    svgEl('title', {}, svg).textContent = ch.title;
    ser.forEach((s, i) => {
      const c = i % cols, r = Math.floor(i / cols), ox = c * pw, oy = r * ph;
      const g = svgEl('g', { transform: `translate(${ox} ${oy})` }, svg);
      const hl = ch.highlight != null ? isHi(ch.highlight, s.name) : true, cls = hl ? 'mk-hi' : 'mk-lo';
      const p = { l: 10, r: 46, t: 24, b: 18 }, x0 = p.l, x1 = pw - p.r, y0 = p.t, y1 = ph - p.b;
      if (hl && ch.highlight != null) svgEl('rect', { x: 2, y: 2, width: pw - 4, height: ph - 4, rx: 6, class: 'sm-hi' }, g);
      let plo = lo, phi = hi;
      if (!shared) { const own = s.values.filter(finite); const t = niceTicks(Math.min(...own, unit === 'index' ? 100 : 0) * (unit === 'index' ? 0.9 : 1), Math.max(...own), 3); plo = t[0]; phi = Math.max(...own, t[t.length - 1]); }
      const x = lin(0, xs.length - 1, x0, x1), y = lin(plo, phi, y1, y0);
      if (unit === 'index') svgEl('line', { x1: x0, x2: x1, y1: y(100), y2: y(100), class: 'baseline' }, g); else svgEl('line', { x1: x0, x2: x1, y1: y(plo), y2: y(plo), class: 'baseline' }, g);
      txt(g, x0, 14, s.name.length > Math.floor((pw - 16) / 6.5) ? s.name.slice(0, Math.floor((pw - 16) / 6.5) - 1) + '…' : s.name, 'sm-title' + (hl && ch.highlight != null ? ' strong' : ''));
      const pts = s.values.map((v, j) => finite(v) ? [x(j), y(v)] : null);
      const sg = svgEl('g', { class: 'series ' + cls }, g);
      svgEl('path', { d: pts.filter(Boolean).map((q, k) => (k ? 'L' : 'M') + q[0].toFixed(1) + ' ' + q[1].toFixed(1)).join(''), class: 'ln' }, sg);
      const last = pts.filter(Boolean).pop(); if (last) svgEl('circle', { cx: last[0], cy: last[1], r: 3.2, class: 'dot' }, sg);
      if (last) { const t = txt(g, x1 + 6, Math.min(Math.max(last[1] + 4, y0 + 8), y1), fmtVal(s.values[s.values.length - 1], unit), 'val-label tnum' + (hl && ch.highlight != null ? ' strong' : '')); void t; }
      if (!(ch.annotations || []).length || i !== 0) { txt(g, x0, ph - 4, xLabel(xs[0]), 'ax-label tnum'); txt(g, x1, ph - 4, xLabel(xs[xs.length - 1]), 'ax-label tnum', { 'text-anchor': 'end' }); }
      (ch.annotations || []).forEach((a) => { const j = xs.indexOf(a.x); if (j < 0) return; svgEl('line', { x1: x(j), x2: x(j), y1: y0 - 4, y2: y1, class: 'ann-line' }, g); if (i === 0) txt(g, x(j) + (x(j) > pw / 2 ? -3 : 3), ph - 4, a.label, 'ann-label', { 'text-anchor': x(j) > pw / 2 ? 'end' : 'start' }); });
      const hit = svgEl('rect', { x: 0, y: 0, width: pw, height: ph, class: 'hit' }, g);
      hover(hit, s.name, [{ key: cls, value: fmtVal(s.values[0], unit), label: xLabelLong(xs[0]) }, { key: cls, value: fmtVal(s.values[s.values.length - 1], unit), label: xLabelLong(xs[xs.length - 1]) }, { muted: true, value: fmtVal(Math.max(...s.values.filter(finite)), unit), label: 'peak' }]);
    });
    return twin(ch, xLabelLong);
  }

  // ---------------------------------------------------------------- scatter (x.values, series[0].values, series[0].labels)
  function scatter(el, ch, o) {
    const W = measure(el, 560), s = ch.series[0], xs = ch.x.values, ys = s.values, labels = s.labels || [];
    const xu = ch.x.unit || 'count', yu = ch.y.unit;
    const f = frame(el, { width: W, height: o.height || 260, pad: { l: 52, r: 24, t: 26, b: 40 }, title: ch.title });
    const xt = niceTicks(Math.min(0, ...xs), Math.max(...xs), 5), yt = niceTicks(Math.min(0, ...ys), Math.max(...ys), 4);
    const x = lin(xt[0], Math.max(xt[xt.length - 1], Math.max(...xs)), f.x0, f.x1), y = lin(yt[0], Math.max(yt[yt.length - 1], Math.max(...ys)), f.y1, f.y0);
    yt.forEach((t) => { svgEl('line', { x1: f.x0, x2: f.x1, y1: y(t), y2: y(t), class: t === 0 ? 'baseline' : 'gridline' }, f.g); txt(f.g, f.x0 - 8, y(t) + 4, tickFmt(t, yu), 'ax-label tnum', { 'text-anchor': 'end' }); });
    xt.forEach((t) => { svgEl('line', { x1: x(t), x2: x(t), y1: f.y0, y2: f.y1, class: t === 0 ? 'baseline' : 'gridline' }, f.g); txt(f.g, x(t), f.y1 + 16, tickFmt(t, xu), 'ax-label tnum', { 'text-anchor': 'middle' }); });
    txt(f.g, f.x1, f.y1 + 32, ch.x.label + ' →', 'ax-title', { 'text-anchor': 'end' });
    txt(f.g, f.x0 - 8, f.y0 - 12, ch.y.label + ' ↑', 'ax-title', { 'text-anchor': 'start' });
    const placed = [];
    const order = xs.map((v, i) => i).sort((a, b) => (isHi(ch.highlight, labels[a]) ? 1 : 0) - (isHi(ch.highlight, labels[b]) ? 1 : 0));
    order.forEach((i) => {
      const hl = ch.highlight != null ? isHi(ch.highlight, labels[i]) : true, cls = hl ? 'mk-hi' : 'mk-lo';
      const g = svgEl('g', { class: 'mark ' + cls }, f.g);
      svgEl('circle', { cx: x(xs[i]), cy: y(ys[i]), r: 5, class: 'pt' }, g);
      const hit = svgEl('circle', { cx: x(xs[i]), cy: y(ys[i]), r: 12, class: 'hit' }, g);
      hover(hit, labels[i] || s.name, [{ key: cls, value: fmtVal(xs[i], xu, { signed: xu === '%' }), label: ch.x.label }, { key: cls, value: fmtVal(ys[i], yu), label: ch.y.label }]);
      const extreme = xs[i] === Math.max(...xs) || xs[i] === Math.min(...xs) || ys[i] === Math.max(...ys) || ys[i] === Math.min(...ys);
      if ((hl && ch.highlight != null) || extreme) {
        let lx = x(xs[i]) + 8, ly = y(ys[i]) + 4, anchor = 'start'; const w = textW(labels[i], 11.5);
        if (lx + w > f.x1) { lx = x(xs[i]) - 8; anchor = 'end'; }
        ly = Math.max(f.y0 + 10, Math.min(f.y1 - 8, ly)); if (ly < y(ys[i]) - 2) ly = y(ys[i]) - 9;
        while (placed.some((p) => Math.abs(p.y - ly) < 12 && Math.abs(p.x - lx) < w)) ly -= 12;
        placed.push({ x: lx, y: ly });
        txt(f.g, lx, ly, labels[i], 'pt-label' + (hl && ch.highlight != null ? ' strong' : ''), { 'text-anchor': anchor });
      }
    });
    return { head: [s.name, ch.x.label, ch.y.label], rows: xs.map((v, i) => [labels[i] || String(i + 1), fmtVal(v, xu, { signed: xu === '%' }), fmtVal(ys[i], yu)]) };
  }

  // ---------------------------------------------------------------- waterfall (first and last are totals)
  function waterfall(el, ch, o) {
    const W = measure(el, 560), unit = ch.y.unit, cats = ch.x.values, vals = ch.series[0].values, n = cats.length;
    const f = frame(el, { width: W, height: (o.height || 240) + 20 * annRows(ch), pad: { l: 52, r: 12, t: 30 + 20 * annRows(ch), b: 52 }, title: ch.title });
    const totals = new Set(ch.totals || [0, n - 1]);
    let run = 0; const bars = cats.map((c, i) => { const v = vals[i]; if (totals.has(i)) { run = v; return { c, y0: 0, y1: v, v, total: true }; } const b = { c, y0: run, y1: run + v, v, total: false }; run += v; return b; });
    const hi = Math.max(...bars.map((b) => Math.max(b.y0, b.y1)));
    const ticks = niceTicks(0, hi, 4), y = lin(0, Math.max(hi, ticks[ticks.length - 1]), f.y1, f.y0);
    yGrid(f, y, ticks, unit);
    const band = (f.x1 - f.x0) / n, bw = Math.min(40, band * 0.66), labels = [];
    bars.forEach((b, i) => {
      const cx = f.x0 + band * (i + 0.5), top = y(Math.max(b.y0, b.y1)), bot = y(Math.min(b.y0, b.y1));
      const hl = ch.highlight != null && isHi(ch.highlight, b.c);
      const cls = b.total ? 'mk-total' : b.v >= 0 ? 'mk-pos' : 'mk-neg';
      const g = svgEl('g', { class: 'mark ' + cls + (hl ? ' hl' : '') + (ch.highlight != null && !hl && !b.total ? ' dim' : '') }, f.g);
      svgEl('path', { d: roundedTop(cx - bw / 2, top, bw, Math.max(bot - top, 1.5), 3, 3), class: 'bar' }, g);
      if (i < n - 1) svgEl('line', { x1: cx + bw / 2, x2: cx + band - bw / 2, y1: y(b.y1), y2: y(b.y1), class: 'wf-connector' }, f.g);
      const hit = svgEl('rect', { x: f.x0 + band * i, y: f.y0, width: band, height: f.y1 - f.y0, class: 'hit' }, g);
      hover(hit, b.c, [{ key: cls, value: fmtVal(b.v, unit, { signed: !b.total }), label: b.total ? 'total' : 'change' }].concat(b.total ? [] : [{ muted: true, value: fmtVal(b.y1, unit), label: 'running total' }]));
      const lab = fmtVal(b.v, unit, { signed: !b.total }); let ly = top - 5; const lw = textW(lab, 12);
      while (labels.some((p) => Math.abs(p.x - cx) < (lw + p.w) / 2 + 4 && Math.abs(p.y - ly) < 13)) ly -= 13; labels.push({ x: cx, y: ly, w: lw });
      txt(f.g, cx, ly, lab, 'val-label tnum' + (hl || b.total ? ' strong' : ''), { 'text-anchor': 'middle' });
      wrap(String(b.c), Math.max(6, Math.floor(band / 6.3)), 3).forEach((l, k) => txt(f.g, cx, f.y1 + 17 + k * 13, l, 'ax-label' + (hl ? ' strong' : ''), { 'text-anchor': 'middle' }));
    });
    legend(el, [{ name: 'total', cls: 'mk-total' }, { name: 'added', cls: 'mk-pos' }, { name: 'reduced', cls: 'mk-neg' }]);
    return { head: ['Step', ch.series[0].name], rows: bars.map((b) => [b.c, fmtVal(b.v, unit, { signed: !b.total })]) };
  }

  // ---------------------------------------------------------------- table twin
  function twin(ch, catFmt) {
    const unit = ch.y.unit;
    if (ch.type === 'slope' || ch.type === 'smallmultiples' || (ch.type === 'line' && ch.series.length > 1 && ch.x.values.length === 2)) {
      return { head: ['Series'].concat(ch.x.values.map(catFmt)), rows: ch.series.map((s) => [s.name].concat(s.values.map((v) => fmtVal(v, unit)))) };
    }
    return { head: [ch.x.label].concat(ch.series.map((s) => s.name)).concat(ch.series[0].n ? ['n'] : []), rows: ch.x.values.map((c, j) => [catFmt(c)].concat(ch.series.map((s) => fmtVal(s.values[j], unit))).concat(ch.series[0].n ? [ch.series[0].n[j].toLocaleString('en-US')] : [])) };
  }
  function renderTwin(el, tw) {
    el.innerHTML = '';
    const t = h('table', 'data-table', el), thead = h('thead', '', t), tr = h('tr', '', thead);
    tw.head.forEach((x, i) => h('th', i ? '' : 'txt', tr, x));
    const tb = h('tbody', '', t);
    tw.rows.forEach((r) => { const row = h('tr', '', tb); r.forEach((c, i) => h('td', i ? '' : 'txt', row, c)); });
  }

  const forms = { line, bar, hbar, dumbbell, slope, stacked, smallmultiples, scatter, waterfall };
  /** Render a contract chart into el. Returns the table twin {head, rows}, or null and an error message in the card. */
  function render(el, ch, opts) {
    el.innerHTML = '';
    const fn = forms[ch.type];
    FY = !/calendar|survey|year$/i.test(ch.x.label || '') || /fiscal/i.test(ch.x.label || '');
    if (ch.highlight === '' || (Array.isArray(ch.highlight) && !ch.highlight.length)) ch.highlight = null;
    if (ch.highlight != null && (ch.type === 'hbar' || ch.type === 'dumbbell') && !ch.x.values.some((c) => isHi(ch.highlight, c))) ch.highlight = null; // names a series, not a row: nothing to single out
    if (!fn) { h('div', 'empty', el, `Unknown chart type "${ch.type}"`); return null; }
    try {
      const tw = fn(el, ch, opts || {});
      el.querySelectorAll('svg.ich').forEach((svg) => { svg.setAttribute('aria-label', ch.title || ch.type); if (!svg.querySelector(':scope > title')) { const t = svgEl('title', {}); t.textContent = [ch.title, ch.subtitle].filter(Boolean).join('. '); svg.insertBefore(t, svg.firstChild); } });
      return tw;
    } catch (e) { console.error('[insights] chart failed', ch.title, e); el.innerHTML = ''; h('div', 'empty', el, 'Chart failed to render'); return null; }
  }
  M.insightsCharts = { render, renderTwin, fmtVal, types: Object.keys(forms) };
})();
