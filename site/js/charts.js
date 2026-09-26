/* charts.js - small SVG chart library for SF City Monitor. No dependencies.
   Every chart: reads colours from CSS custom properties (light/dark need no re-render),
   hairline solid gridlines, thin marks, 2px surface gaps, >= 24px hit targets, one shared
   tooltip (per mark, or crosshair on line charts), keyboard focus on every mark group,
   and returns {head, rows} for the table twin. */
(function () {
  const M = (window.SFCM = window.SFCM || {});
  const NS = 'http://www.w3.org/2000/svg';
  const fmt = () => M.stats.fmt;

  /** Create an SVG element. Non-finite numeric attributes (NaN from missing data) are dropped rather than
      written, so a bad value never throws a console error or draws garbage; the mark simply collapses. */
  function svgEl(tag, attrs, parent) {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs || {}) { const v = attrs[k]; if (v == null) continue; if (typeof v === 'number' && !isFinite(v)) { e.dataset.bad = k; continue; } if (typeof v === 'string' && /NaN|Infinity/.test(v) && (k === 'd' || k === 'viewBox' || k === 'transform' || k === 'points')) { e.dataset.bad = k; continue; } e.setAttribute(k, v); }
    if (parent) parent.appendChild(e); return e;
  }
  function text(parent, x, y, str, cls, attrs) { const t = svgEl('text', Object.assign({ x, y, class: cls || 'ax-label' }, attrs || {}), parent); t.textContent = str == null ? '' : String(str); return t; }
  const finite = (v) => typeof v === 'number' && isFinite(v);
  function h(tag, cls, parent, txt) { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; if (parent) parent.appendChild(e); return e; }
  function measure(el, fallback) { const w = el.getBoundingClientRect().width; return w > 40 ? w : fallback || 600; }
  function niceTicks(max, count, min) {
    min = min || 0;
    if (!(max - min > 0)) return [min, min + 1];
    const raw = (max - min) / count, mag = Math.pow(10, Math.floor(Math.log10(raw))), norm = raw / mag;
    const step = (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * mag;
    const ticks = []; for (let v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) ticks.push(+v.toFixed(6));
    return ticks;
  }
  const lin = (d0, d1, r0, r1) => { const f = (v) => r0 + ((v - d0) / (d1 - d0 || 1)) * (r1 - r0); f.invert = (p) => d0 + ((p - r0) / (r1 - r0 || 1)) * (d1 - d0); f.domain = [d0, d1]; return f; };
  const logS = (d0, d1, r0, r1) => { const l0 = Math.log10(d0), l1 = Math.log10(d1); const f = (v) => r0 + ((Math.log10(Math.max(v, d0)) - l0) / (l1 - l0 || 1)) * (r1 - r0); f.domain = [d0, d1]; return f; };
  function centerOf(g) { const r = g.getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 }; }

  // ---------------------------------------------------------------- tooltip (single instance)
  let tipEl;
  function tip() { if (!tipEl) { tipEl = h('div', 'tip', document.body); tipEl.setAttribute('role', 'tooltip'); tipEl.hidden = true; } return tipEl; }
  function showTip(evt, title, rows, anchor) {
    const t = tip(); t.innerHTML = '';
    if (title) h('div', 'tip-title', t, title);
    for (const r of rows) { const row = h('div', 'tip-row' + (r.muted ? ' muted' : ''), t); const k = h('span', 'tip-key', row); if (r.key) k.style.background = r.key; else k.style.visibility = 'hidden'; h('span', 'tip-val', row, r.value); h('span', 'tip-label', row, r.label); }
    t.hidden = false;
    const pad = 14; let x = (anchor ? anchor.x : evt.clientX) + pad, y = (anchor ? anchor.y : evt.clientY) + pad;
    const r = t.getBoundingClientRect();
    if (x + r.width > window.innerWidth - 8) x = (anchor ? anchor.x : evt.clientX) - r.width - pad;
    if (y + r.height > window.innerHeight - 8) y = (anchor ? anchor.y : evt.clientY) - r.height - pad;
    t.style.transform = `translate(${Math.max(4, x)}px, ${Math.max(4, y)}px)`;
  }
  function hideTip() { if (tipEl) tipEl.hidden = true; }
  window.addEventListener('scroll', hideTip, { passive: true });
  function hover(g, show) { g.addEventListener('pointermove', show); g.addEventListener('pointerleave', hideTip); g.addEventListener('focus', show); g.addEventListener('blur', hideTip); }
  function clickable(g, onClick) { if (!onClick) return; g.style.cursor = 'pointer'; g.addEventListener('click', onClick); g.addEventListener('keydown', (e) => { if (e.key === 'Enter') onClick(e); }); }

  // ---------------------------------------------------------------- frame + axes
  function frame(el, opts) {
    el.innerHTML = '';
    const width = measure(el, opts.fallbackWidth), height = opts.height || 280;
    const m = Object.assign({ top: 28, right: 24, bottom: 34, left: 48 }, opts.margin || {});
    const svg = svgEl('svg', { viewBox: `0 0 ${width} ${height}`, width, height, class: 'chart', role: 'img' }, el);
    if (opts.aria) { const t = svgEl('title', {}, svg); t.textContent = opts.aria; }
    const g = svgEl('g', { transform: `translate(${m.left},${m.top})` }, svg);
    return { svg, g, width, height, m, iw: width - m.left - m.right, ih: height - m.top - m.bottom };
  }
  function yGrid(f, y, ticks, format) { for (const t of ticks) { const yy = y(t); if (yy < -2 || yy > f.ih + 2) continue; svgEl('line', { x1: 0, x2: f.iw, y1: yy, y2: yy, class: t === 0 ? 'ax-base' : 'gridline' }, f.g); text(f.g, -8, yy + 4, format ? format(t) : t, 'ax-label tnum', { 'text-anchor': 'end' }); } }
  function xGrid(f, x, ticks, format) { for (const t of ticks) { const xx = x(t); if (xx < -1 || xx > f.iw + 1) continue; svgEl('line', { y1: 0, y2: f.ih, x1: xx, x2: xx, class: t === 0 ? 'ax-base' : 'gridline' }, f.g); text(f.g, xx, f.ih + 18, format ? format(t) : t, 'ax-label tnum', { 'text-anchor': 'middle' }); } }
  function axisTitle(f, str, axis) { if (!str) return; if (axis === 'y') text(f.g, -f.m.left + 2, -f.m.top + 14, str, 'ax-title'); else text(f.g, f.iw, f.ih + 32, str, 'ax-title', { 'text-anchor': 'end' }); }
  /** Vertical reference markers on a time axis: [{x (px), label}] drawn as a dotted hairline with a top label. */
  function markers(f, marks) { for (const mk of marks || []) { if (mk.x == null || mk.x < 0 || mk.x > f.iw) continue; svgEl('line', { x1: mk.x, x2: mk.x, y1: -6, y2: f.ih, class: 'ref-line', 'stroke-dasharray': '2 3' }, f.g); if (mk.label) text(f.g, mk.x + 4, -10, mk.label, 'ref-label'); } }
  function callout(f, a) {
    const g = svgEl('g', { class: 'callout' }, f.g); const pl = a.placement || 'top';
    const dx = pl === 'left' ? -46 : pl === 'right' ? 46 : 0, dy = pl === 'top' ? -38 : pl === 'bottom' ? 40 : 0;
    const lx = a.x + dx, ly = a.y + dy, maxW = Math.min(200, f.iw * 0.5);
    const words = a.text.split(' '), lines = []; let cur = '';
    for (const w of words) { if ((cur + ' ' + w).trim().length * 6.3 > maxW && cur) { lines.push(cur); cur = w; } else cur = (cur + ' ' + w).trim(); }
    if (cur) lines.push(cur);
    const bw = Math.max(...lines.map((l) => l.length)) * 6.3 + 16, bh = lines.length * 15 + 10;
    let bx = pl === 'left' ? lx - bw : pl === 'right' ? lx : lx - bw / 2, by = pl === 'top' ? ly - bh : pl === 'bottom' ? ly : ly - bh / 2;
    bx = Math.max(-f.m.left + 4, Math.min(bx, f.iw + f.m.right - bw - 4)); by = Math.max(-f.m.top + 4, Math.min(by, f.ih - bh));
    const ax = pl === 'left' ? bx + bw : pl === 'right' ? bx : Math.max(bx + 6, Math.min(bx + bw - 6, a.x)), ay = pl === 'top' ? by + bh : pl === 'bottom' ? by : by + bh / 2;
    svgEl('line', { x1: a.x, y1: a.y, x2: ax, y2: ay, class: 'callout-leader' }, g); svgEl('circle', { cx: a.x, cy: a.y, r: 3.5, class: 'callout-dot' }, g);
    svgEl('rect', { x: bx, y: by, width: bw, height: bh, rx: 4, class: 'callout-box' }, g);
    lines.forEach((l, i) => text(g, bx + 8, by + 17 + i * 15, l, 'callout-text'));
  }
  function legend(el, series, shape) { const l = h('div', 'legend'); el.insertBefore(l, el.firstChild); for (const s of series) { const it = h('span', 'legend-item', l); const sw = h('span', 'legend-swatch ' + (shape === 'line' ? 'line' : ''), it); sw.style.background = s.color; h('span', '', it, s.label); } return l; }
  function roundedRight(x, y, w, hgt, r) { r = Math.min(r, w, hgt / 2); return `M${x},${y}h${w - r}a${r},${r},0,0,1,${r},${r}v${hgt - 2 * r}a${r},${r},0,0,1,${-r},${r}h${-(w - r)}z`; }
  function roundedTop(x, y, w, hgt, r) { r = Math.min(r, hgt, w / 2); return `M${x},${y + hgt}v${-(hgt - r)}a${r},${r},0,0,1,${r},${-r}h${w - 2 * r}a${r},${r},0,0,1,${r},${r}v${hgt - r}z`; }

  // ---------------------------------------------------------------- bars
  /** rows:[{label,value,color,n,small,sub,onClick,id}]; horizontal by default; o.vertical for columns. */
  function bars(el, o) {
    const rows = o.rows.map((r) => (r.value != null && !finite(r.value) ? Object.assign({}, r, { value: null }) : r)), format = o.format || ((v) => fmt().money(v));
    const table = rows.map((r) => [r.label, r.value == null ? '–' : format(r.value), ...(rows.some((x) => x.n != null) ? [fmt().int(r.n)] : [])]);
    const head = [o.labelHead || 'Group', o.valueHead || 'Value', ...(rows.some((x) => x.n != null) ? [o.nHead || 'n'] : [])];
    if (!rows.length) { el.innerHTML = ''; return { head, rows: [] }; }
    if (!o.vertical) {
      const rowH = o.rowH || 30;
      const hasN = rows.some((r) => r.n != null);
      const f = frame(el, { height: rows.length * rowH + 54, margin: { top: 24, right: o.rightPad || (hasN ? 96 : 70), bottom: 30, left: o.labelWidth || 170 }, aria: o.aria });
      const vals = rows.map((r) => r.value || 0), minV = Math.min(0, ...vals), maxV = Math.max(1e-9, ...vals);
      const maxX = o.maxX || maxV * 1.22, minX = o.minX != null ? o.minX : minV * 1.22;
      const x = lin(minX, maxX, 0, f.iw);
      xGrid(f, x, niceTicks(maxX, Math.max(2, Math.floor(f.iw / 90)), minX), o.tickFormat || ((t) => format(t)));
      axisTitle(f, o.xTitle, 'x');
      if (o.refLine != null) { svgEl('line', { x1: x(o.refLine), x2: x(o.refLine), y1: -4, y2: f.ih, class: 'ref-line' }, f.g); if (o.refLabel) text(f.g, x(o.refLine) + 4, -8, o.refLabel, 'ref-label'); }
      rows.forEach((r, i) => {
        const y = i * rowH + rowH / 2;
        const g = svgEl('g', { class: 'row' + (r.small ? ' small-n' : ''), tabindex: 0 }, f.g);
        text(g, -10, y + 4, truncate(r.label, (f.m.left - 14) / 6.6), 'row-label', { 'text-anchor': 'end' });
        if (r.value != null) {
          const x0 = x(Math.min(0, r.value)), x1 = x(Math.max(0, r.value)), w = Math.max(0, x1 - x0);
          if (r.value >= 0) svgEl('path', { d: roundedRight(x0, y - 10, Math.max(w, 1), 20, 4), class: 'bar', style: `fill:${r.color || 'var(--series-1)'}` }, g);
          else svgEl('rect', { x: x0, y: y - 10, width: Math.max(w, 1), height: 20, rx: 4, class: 'bar', style: `fill:${r.color || 'var(--series-1)'}` }, g);
          const lab = format(r.value), lw = lab.length * 6.8;
          if (r.value >= 0 && x1 + 6 + lw > f.iw + (hasN ? 2 : 40) && w > lw + 14) text(g, x1 - 6, y + 4, lab, 'seg-label tnum', { 'text-anchor': 'end' });
          else text(g, r.value >= 0 ? Math.min(x1 + 6, f.iw + (hasN ? 2 : 40) - lw) : x0 - 6, y + 4, lab, 'val-label tnum', r.value >= 0 ? null : { 'text-anchor': 'end' });
        } else text(g, x(0) + 4, y + 4, r.small ? 'too few records' : 'no data', 'val-label muted');
        if (r.n != null) text(g, f.iw + 10, y + 4, `n = ${fmt().int(r.n)}`, 'n-label tnum');
        svgEl('rect', { x: -f.m.left, y: y - rowH / 2, width: f.width, height: rowH, class: 'hit' }, g);
        hover(g, (e) => showTip(e, r.label, [{ key: r.color || 'var(--series-1)', label: o.valueHead || '', value: r.value != null ? format(r.value) : '–' }, ...(r.n != null ? [{ label: o.nHead || 'records', value: fmt().int(r.n), muted: true }] : []), ...(r.sub ? [{ label: '', value: r.sub, muted: true }] : []), ...(r.onClick ? [{ label: '', value: 'Click to open', muted: true }] : [])], e.clientX == null ? centerOf(g) : null));
        clickable(g, r.onClick);
      });
      return { head, rows: table };
    }
    const f = frame(el, { height: o.height || 240, margin: { top: 34, right: 16, bottom: 40, left: 52 }, aria: o.aria });
    const maxY = o.maxY || Math.max(1e-9, ...rows.map((r) => r.value || 0)) * 1.12;
    const y = lin(0, maxY, f.ih, 0);
    yGrid(f, y, niceTicks(maxY, 4), o.tickFormat || ((t) => format(t)));
    axisTitle(f, o.yTitle, 'y');
    const bw = f.iw / rows.length, barW = Math.min(o.maxBarW || 26, bw * 0.62);
    const every0 = o.labelEvery != null ? o.labelEvery : Math.max(1, Math.ceil((Math.max(...rows.map((r) => String(r.label).length)) * 6.6 + 8) / bw));
    rows.forEach((r, i) => {
      const cx = i * bw + bw / 2;
      const g = svgEl('g', { class: 'col' + (r.small ? ' small-n' : ''), tabindex: 0 }, f.g);
      if (r.value != null) svgEl('path', { d: roundedTop(cx - barW / 2, y(r.value), barW, f.ih - y(r.value), 4), class: 'bar', style: `fill:${r.color || 'var(--series-1)'}` }, g);
      if (i % every0 === 0) text(g, cx, f.ih + 18, r.label, 'ax-label', { 'text-anchor': 'middle' });
      if (o.directLabels && r.value != null) text(g, cx, y(r.value) - 6, format(r.value), 'val-label tnum', { 'text-anchor': 'middle' });
      svgEl('rect', { x: i * bw, y: 0, width: bw, height: f.ih + 20, class: 'hit' }, g);
      hover(g, (e) => showTip(e, r.label, [{ key: r.color || 'var(--series-1)', label: o.valueHead || '', value: r.value != null ? format(r.value) : '–' }, ...(r.n != null ? [{ label: o.nHead || 'records', value: fmt().int(r.n), muted: true }] : []), ...(r.sub ? [{ label: '', value: r.sub, muted: true }] : [])], e.clientX == null ? centerOf(g) : null));
      clickable(g, r.onClick);
    });
    if (o.markers) markers(f, o.markers.map((mk) => ({ x: rows.findIndex((r) => String(r.label) === String(mk.x)) * bw + (mk.frac == null ? 0 : mk.frac * bw), label: mk.label })).filter((mk) => mk.x >= 0));
    if (o.annotations) for (const a of o.annotations) { const i = rows.findIndex((r) => String(r.label) === String(a.x)); if (i >= 0 && rows[i].value != null) callout(f, { x: i * bw + bw / 2, y: y(rows[i].value), text: a.text, placement: a.placement }); }
    return { head, rows: table };
  }
  function truncate(s, n) { s = String(s); return s.length > n ? s.slice(0, Math.max(3, n - 1)) + '…' : s; }

  /** Stacked bars. categories: labels; series:[{id,label,color,values[]}]; percent; horizontal; n[]; small[]; onClick(i). */
  function stackedBars(el, o) {
    const cats = o.categories, series = o.series.map((s) => Object.assign({}, s, { values: s.values.map((v) => (finite(v) ? v : 0)) }));
    const totals = cats.map((_, i) => series.reduce((a, s) => a + (s.values[i] || 0), 0));
    const val = (s, i) => (o.percent ? (totals[i] ? (s.values[i] || 0) / totals[i] : 0) : s.values[i] || 0);
    const format = o.format || (o.percent ? (v) => fmt().pct(v) : (v) => fmt().money(v));
    const rawFormat = o.rawFormat || ((v) => fmt().int(v));
    const table = cats.map((c, i) => [c, ...series.map((s) => (o.percent ? `${format(val(s, i))} (${rawFormat(s.values[i] || 0)})` : format(val(s, i)))), ...(o.n ? [fmt().int(o.n[i])] : [])]);
    const head = [o.labelHead || 'Group', ...series.map((s) => s.label), ...(o.n ? [o.nHead || 'n'] : [])];
    if (!cats.length) { el.innerHTML = ''; return { head, rows: [] }; }
    if (o.horizontal) {
      const rowH = o.rowH || 30;
      const f = frame(el, { height: cats.length * rowH + 54, margin: { top: 22, right: 74, bottom: 30, left: o.labelWidth || 170 }, aria: o.aria });
      legend(el, series);
      const maxX = o.percent ? 1 : Math.max(1e-9, ...totals) * 1.05;
      const x = lin(0, maxX, 0, f.iw);
      xGrid(f, x, niceTicks(maxX, 5), o.percent ? (t) => fmt().pct(t) : (t) => format(t));
      axisTitle(f, o.xTitle, 'x');
      cats.forEach((c, i) => {
        const y = i * rowH + rowH / 2;
        const g = svgEl('g', { class: 'row' + (o.small && o.small[i] ? ' small-n' : ''), tabindex: 0 }, f.g);
        text(g, -10, y + 4, truncate(c, (f.m.left - 14) / 6.6), 'row-label', { 'text-anchor': 'end' });
        let acc = 0;
        series.forEach((s) => { const v = val(s, i); if (!v) return; const x0 = x(acc), x1 = x(acc + v); svgEl('rect', { x: x0 + 1, y: y - 10, width: Math.max(0, x1 - x0 - 2), height: 20, rx: 2, class: 'seg', style: `fill:${s.color}` }, g); if (x1 - x0 > 44 && o.segLabels) text(g, (x0 + x1) / 2, y + 4, format(v), 'seg-label tnum', { 'text-anchor': 'middle' }); acc += v; });
        if (!o.percent) text(g, x(acc) + 6, y + 4, format(acc), 'val-label tnum');
        if (o.n) text(g, f.iw + 10, y + 4, `n = ${fmt().int(o.n[i])}`, 'n-label tnum');
        svgEl('rect', { x: -f.m.left, y: y - rowH / 2, width: f.width, height: rowH, class: 'hit' }, g);
        hover(g, (e) => showTip(e, c, [...series.map((s) => ({ key: s.color, label: s.label, value: o.percent ? `${format(val(s, i))} · ${rawFormat(s.values[i] || 0)}` : format(val(s, i)) })), ...(o.n ? [{ label: o.nHead || 'records', value: fmt().int(o.n[i]), muted: true }] : [])], e.clientX == null ? centerOf(g) : null));
        clickable(g, o.onClick ? () => o.onClick(i) : null);
      });
      return { head, rows: table };
    }
    const f = frame(el, { height: o.height || 260, margin: { top: 30, right: 16, bottom: 40, left: 52 }, aria: o.aria });
    legend(el, series);
    const maxY = o.percent ? 1 : o.maxY || Math.max(1e-9, ...totals) * 1.08;
    const y = lin(0, maxY, f.ih, 0);
    yGrid(f, y, niceTicks(maxY, 4), o.percent ? (t) => fmt().pct(t) : (t) => format(t));
    axisTitle(f, o.yTitle, 'y');
    const bw = f.iw / cats.length, barW = Math.min(o.maxBarW || 28, bw * 0.66);
    const lblLen = Math.max(...cats.map((c) => String(o.catFormat ? o.catFormat(c) : c).length)) * 6.6 + 8;
    const every = o.labelEvery != null ? o.labelEvery : Math.max(1, Math.ceil(lblLen / bw));
    cats.forEach((c, i) => {
      const cx = i * bw + bw / 2;
      const g = svgEl('g', { class: 'col' + (o.small && o.small[i] ? ' small-n' : ''), tabindex: 0 }, f.g);
      let acc = 0;
      series.forEach((s) => { const v = val(s, i); if (!v) return; const y1 = y(acc), y0 = y(acc + v); svgEl('rect', { x: cx - barW / 2, y: y0 + 1, width: barW, height: Math.max(0, y1 - y0 - 2), rx: 2, class: 'seg', style: `fill:${s.color}` }, g); acc += v; });
      if (i % every === 0) text(g, cx, f.ih + 18, o.catFormat ? o.catFormat(c) : c, 'ax-label', { 'text-anchor': 'middle' });
      svgEl('rect', { x: i * bw, y: -10, width: bw, height: f.ih + 30, class: 'hit' }, g);
      hover(g, (e) => showTip(e, o.catFormat ? o.catFormat(c) : c, [...series.map((s) => ({ key: s.color, label: s.label, value: o.percent ? `${format(val(s, i))} · ${rawFormat(s.values[i] || 0)}` : format(val(s, i)) })), { label: 'total', value: o.percent ? rawFormat(totals[i]) : format(totals[i]), muted: true }, ...(o.n ? [{ label: o.nHead || 'records', value: fmt().int(o.n[i]), muted: true }] : [])], e.clientX == null ? centerOf(g) : null));
      clickable(g, o.onClick ? () => o.onClick(i) : null);
    });
    if (o.markers) markers(f, o.markers.map((mk) => ({ x: cats.findIndex((c) => String(c) === String(mk.x)) * bw + (mk.frac == null ? 0 : mk.frac * bw), label: mk.label })).filter((mk) => mk.x >= 0));
    if (o.annotations) for (const a of o.annotations) { const i = cats.findIndex((c) => String(c) === String(a.x)); if (i >= 0) callout(f, { x: i * bw + bw / 2, y: y(o.percent ? 1 : totals[i]), text: a.text, placement: a.placement }); }
    return { head, rows: table };
  }

  /** Multi-series line / step chart. o.x labels; series:[{id,label,color,values[],band:{lo,hi},dash,muted}]; crosshair tooltip. */
  function lines(el, o) {
    const X = o.x || [], format = o.format || ((v) => fmt().money(v));
    const S = o.series.map((s) => Object.assign({}, s, { values: s.values.map((v) => (v != null && finite(v) ? v : null)) }));
    if (!X.length || !S.some((s) => s.values.some((v) => v != null))) { el.innerHTML = ''; h('div', 'empty', el, 'No values to plot for these filters'); return { head: [], rows: [] }; }
    const f = frame(el, { height: o.height || 260, margin: { top: 30, right: o.endLabels === false ? 16 : 110, bottom: 38, left: 56 }, aria: o.aria });
    const xs = X.map((_, i) => (o.xPos ? o.xPos(i) : X.length > 1 ? i / (X.length - 1) : 0.5) * f.iw);
    const allVals = S.flatMap((s) => [...s.values, ...(s.band ? s.band.hi : [])]).filter((v) => v != null);
    const maxY = o.maxY || Math.max(1e-9, ...allVals) * 1.1, minY = o.minY != null ? o.minY : Math.min(0, ...allVals) * 1.1;
    const y = lin(minY, maxY, f.ih, 0);
    yGrid(f, y, niceTicks(maxY, 4, minY), o.tickFormat || ((t) => format(t)));
    axisTitle(f, o.yTitle, 'y');
    const every = o.tickEvery || Math.max(1, Math.ceil(X.length / (f.iw / 70)));
    let lastTick = -1e9; const minGap = 44;
    X.forEach((lab, i) => { const isLast = i === X.length - 1; if (i % every === 0 || (!o.tickEvery && isLast)) { if (isLast && i % every !== 0 && xs[i] - lastTick < minGap) return; text(f.g, xs[i], f.ih + 18, o.xFormat ? o.xFormat(lab) : lab, 'ax-label tnum', { 'text-anchor': 'middle' }); lastTick = xs[i]; } });
    S.forEach((s) => { if (!s.band) return; const pts = []; X.forEach((_, i) => { if (s.band.lo[i] != null && s.band.hi[i] != null) pts.push(i); }); if (!pts.length) return; const d = 'M' + pts.map((i) => `${xs[i]},${y(s.band.hi[i])}`).join('L') + 'L' + pts.slice().reverse().map((i) => `${xs[i]},${y(s.band.lo[i])}`).join('L') + 'z'; svgEl('path', { d, class: 'band', style: `fill:${s.color}` }, f.g); });
    S.forEach((s) => {
      let d = '', prev = null;
      X.forEach((_, i) => { const v = s.values[i]; if (v == null) { prev = null; return; } d += prev == null ? `M${xs[i]},${y(v)}` : o.step ? `H${xs[i]}V${y(v)}` : `L${xs[i]},${y(v)}`; prev = v; });
      if (d) svgEl('path', { d, class: 'line' + (s.muted ? ' muted-line' : ''), style: `stroke:${s.color}` + (s.dash ? ';stroke-dasharray:5 4' : '') }, f.g);
      if (o.markers !== false && X.length <= 20) X.forEach((_, i) => { if (s.values[i] != null) svgEl('circle', { cx: xs[i], cy: y(s.values[i]), r: 3.5, class: 'marker', style: `fill:${s.color}` }, f.g); });
    });
    if (o.endLabels !== false && S.length <= 4) {
      const ends = S.map((s) => { let i = X.length - 1; while (i >= 0 && s.values[i] == null) i--; return i >= 0 ? { s, yy: y(s.values[i]), i } : null; }).filter(Boolean).sort((a, b) => a.yy - b.yy);
      for (let k = 1; k < ends.length; k++) if (ends[k].yy - ends[k - 1].yy < 14) ends[k].yy = ends[k - 1].yy + 14;
      ends.forEach((e) => text(f.g, xs[e.i] + 8, e.yy + 4, truncate(e.s.label, 16), 'end-label'));
    } else if (S.length > 1) legend(el, S, 'line');
    if (o.refY != null) { svgEl('line', { x1: 0, x2: f.iw, y1: y(o.refY), y2: y(o.refY), class: 'ref-line' }, f.g); if (o.refLabel) text(f.g, f.iw, y(o.refY) - 6, o.refLabel, 'ref-label', { 'text-anchor': 'end' }); }
    if (o.vmarkers) markers(f, o.vmarkers.map((mk) => { const i = X.map(String).indexOf(String(mk.x)); return { x: i >= 0 ? xs[i] + (mk.frac ? mk.frac * (xs[1] - xs[0]) : 0) : null, label: mk.label }; }));
    if (o.annotations) for (const a of o.annotations) { const i = X.map(String).indexOf(String(a.x)); if (i < 0) continue; const s = S.find((q) => q.id === a.series) || S[0]; const v = s.values[i]; if (v == null) continue; callout(f, { x: xs[i], y: y(v), text: a.text, placement: a.placement }); }
    const cross = svgEl('line', { y1: 0, y2: f.ih, class: 'crosshair', visibility: 'hidden' }, f.g);
    const hit = svgEl('rect', { x: 0, y: 0, width: f.iw, height: f.ih, class: 'hit', tabindex: 0 }, f.g);
    const showAt = (e, best) => { cross.setAttribute('x1', xs[best]); cross.setAttribute('x2', xs[best]); cross.setAttribute('visibility', 'visible'); showTip(e, o.xFormat ? o.xFormat(X[best]) : X[best], S.map((s) => ({ key: s.color, label: s.label + (o.n && o.n[s.id] ? ` (n = ${fmt().int(o.n[s.id][best])})` : ''), value: s.values[best] != null ? format(s.values[best]) : '–' })), e.clientX == null ? { x: f.svg.getBoundingClientRect().left + f.m.left + xs[best], y: f.svg.getBoundingClientRect().top + f.m.top } : null); };
    hit.addEventListener('pointermove', (e) => { const r = f.svg.getBoundingClientRect(); const px = e.clientX - r.left - f.m.left; let best = 0; for (let i = 1; i < xs.length; i++) if (Math.abs(xs[i] - px) < Math.abs(xs[best] - px)) best = i; showAt(e, best); });
    hit.addEventListener('focus', (e) => showAt(e, X.length - 1));
    hit.addEventListener('pointerleave', () => { cross.setAttribute('visibility', 'hidden'); hideTip(); }); hit.addEventListener('blur', hideTip);
    return { head: [o.xHead || 'x', ...S.map((s) => s.label)], rows: X.map((lab, i) => [o.xFormat ? o.xFormat(lab) : lab, ...S.map((s) => (s.values[i] != null ? format(s.values[i]) : '–'))]) };
  }

  /** Histogram over pre-binned counts. bins: labels; counts; highlight index set; refs:[{i,label}] */
  function histogram(el, o) {
    const counts = o.counts, labels = o.labels;
    const f = frame(el, { height: o.height || 240, margin: { top: 40, right: 16, bottom: 40, left: 46 }, aria: o.aria });
    const maxY = Math.max(1, ...counts) * 1.15, y = lin(0, maxY, f.ih, 0);
    yGrid(f, y, niceTicks(maxY, 4), (t) => fmt().int(t)); axisTitle(f, o.yTitle || (o.unit ? o.unit[0].toUpperCase() + o.unit.slice(1) : 'Records'), 'y');
    const bw = f.iw / counts.length, barW = Math.max(2, Math.min(28, bw - 3));
    const everyH = o.labelEvery != null ? o.labelEvery : Math.max(1, Math.ceil((Math.max(...labels.map((l) => String(l).length)) * 6.4 + 6) / bw));
    const hl = new Set(o.highlight || []);
    counts.forEach((c, i) => {
      const cx = i * bw + bw / 2, g = svgEl('g', { tabindex: 0, class: 'col' }, f.g);
      svgEl('path', { d: roundedTop(cx - barW / 2, y(c), barW, f.ih - y(c), 3), class: 'bar', style: `fill:${hl.has(i) ? 'var(--series-2)' : o.color || 'var(--series-1)'}` }, g);
      if (i % everyH === 0) text(g, cx, f.ih + 18, labels[i], 'ax-label tnum', { 'text-anchor': 'middle' });
      svgEl('rect', { x: i * bw, y: 0, width: bw, height: f.ih + 20, class: 'hit' }, g);
      hover(g, (e) => showTip(e, labels[i], [{ key: hl.has(i) ? 'var(--series-2)' : o.color || 'var(--series-1)', label: o.unit || 'records', value: fmt().int(c) }], e.clientX == null ? centerOf(g) : null));
    });
    (o.refs || []).forEach((r) => { const xx = r.i * bw; svgEl('line', { x1: xx, x2: xx, y1: -4, y2: f.ih, class: 'ref-line' }, f.g); text(f.g, xx + 4, -8, r.label, 'ref-label'); });
    axisTitle(f, o.xTitle, 'x');
    return { head: [o.xTitle || 'Bin', o.unit || 'Records'], rows: counts.map((c, i) => [labels[i], fmt().int(c)]) };
  }

  /** Range bars: rows [{label, q:{p25,p50,p75,p90}, n, color, small}] */
  function rangeBars(el, o) {
    const rows = o.rows.map((r) => (r.q && !['p25', 'p50', 'p75', 'p90'].every((k) => finite(r.q[k])) ? Object.assign({}, r, { q: null }) : r)), rowH = o.rowH || 34, format = o.format || ((v) => fmt().months(v));
    if (!rows.length) { el.innerHTML = ''; return { head: [], rows: [] }; }
    const f = frame(el, { height: rows.length * rowH + 56, margin: { top: 26, right: 96, bottom: 30, left: o.labelWidth || 170 }, aria: o.aria });
    const maxX = o.maxX || Math.max(1, ...rows.map((r) => (r.q ? r.q.p90 : 0))) * 1.25, x = lin(0, maxX, 0, f.iw);
    xGrid(f, x, niceTicks(maxX, Math.max(2, Math.floor(f.iw / 90))), o.tickFormat || ((t) => (t === 0 || Math.abs(t) >= 10 ? fmt().int(t) : format(t)))); axisTitle(f, o.xTitle || 'Months', 'x');
    const table = [];
    rows.forEach((r, i) => {
      const y = i * rowH + rowH / 2, g = svgEl('g', { class: 'row' + (r.small ? ' small-n' : ''), tabindex: 0 }, f.g);
      text(g, -10, y + 4, truncate(r.label, (f.m.left - 14) / 6.6), 'row-label', { 'text-anchor': 'end' });
      if (r.q) {
        svgEl('line', { x1: x(r.q.p25), x2: x(r.q.p90), y1: y, y2: y, class: 'whisker' }, g);
        svgEl('rect', { x: x(r.q.p25), y: y - 9, width: Math.max(2, x(r.q.p75) - x(r.q.p25)), height: 18, rx: 3, class: 'box', style: `fill:${r.color || 'var(--series-1)'}` }, g);
        svgEl('rect', { x: x(r.q.p50) - 1.5, y: y - 12, width: 3, height: 24, class: 'median' }, g);
        svgEl('circle', { cx: x(r.q.p90), cy: y, r: 3, class: 'p90' }, g);
        const lab = format(r.q.p50), lw = lab.length * 6.8; text(g, Math.min(x(r.q.p90) + 8, f.iw - 2 - lw), y + 4, lab, 'val-label tnum');
      } else text(g, 4, y + 4, r.small ? 'too few records' : 'no data', 'val-label muted');
      text(g, f.iw + 10, y + 4, `n = ${fmt().int(r.n)}`, 'n-label tnum');
      svgEl('rect', { x: -f.m.left, y: y - rowH / 2, width: f.width, height: rowH, class: 'hit' }, g);
      hover(g, (e) => showTip(e, r.label, r.q ? [{ key: r.color || 'var(--series-1)', label: 'median', value: format(r.q.p50) }, { label: 'p25 – p75', value: `${format(r.q.p25)} – ${format(r.q.p75)}` }, { label: 'p90', value: format(r.q.p90) }, { label: 'records', value: fmt().int(r.n), muted: true }] : [{ label: 'records', value: fmt().int(r.n) }], e.clientX == null ? centerOf(g) : null));
      table.push([r.label, r.q ? format(r.q.p25) : '–', r.q ? format(r.q.p50) : '–', r.q ? format(r.q.p75) : '–', r.q ? format(r.q.p90) : '–', fmt().int(r.n)]);
    });
    return { head: [o.labelHead || 'Group', 'p25', 'Median', 'p75', 'p90', 'n'], rows: table };
  }

  /** Dumbbell: rows [{label, a, b, n, small, onClick}]; prints b − a at right. */
  function dumbbell(el, o) {
    const rows = o.rows.map((r) => Object.assign({}, r, { a: finite(r.a) ? r.a : null, b: finite(r.b) ? r.b : null })), rowH = 32, format = o.format || ((v) => fmt().money(v));
    if (!rows.length) { el.innerHTML = ''; return { head: [], rows: [] }; }
    const f = frame(el, { height: rows.length * rowH + 56, margin: { top: 26, right: 120, bottom: 30, left: o.labelWidth || 170 }, aria: o.aria });
    legend(el, [{ label: o.aLabel, color: o.aColor || 'var(--neutral-2)' }, { label: o.bLabel, color: o.bColor || 'var(--series-1)' }]);
    const maxX = o.maxX || Math.max(1, ...rows.flatMap((r) => [r.a || 0, r.b || 0])) * 1.12, x = o.log ? logS(o.log, maxX, 0, f.iw) : lin(0, maxX, 0, f.iw);
    if (!o.log) xGrid(f, x, niceTicks(maxX, 5), (t) => format(t)); else { for (let p = Math.ceil(Math.log10(o.log)); p <= Math.log10(maxX); p++) { const t = Math.pow(10, p); svgEl('line', { y1: 0, y2: f.ih, x1: x(t), x2: x(t), class: 'gridline' }, f.g); text(f.g, x(t), f.ih + 18, format(t), 'ax-label tnum', { 'text-anchor': 'middle' }); } }
    axisTitle(f, o.xTitle, 'x');
    rows.forEach((r, i) => {
      const y = i * rowH + rowH / 2, g = svgEl('g', { class: 'row' + (r.small ? ' small-n' : ''), tabindex: 0 }, f.g);
      text(g, -10, y + 4, truncate(r.label, (f.m.left - 14) / 6.6), 'row-label', { 'text-anchor': 'end' });
      if (r.a != null && r.b != null) {
        svgEl('line', { x1: x(r.a), x2: x(r.b), y1: y, y2: y, class: 'db-line' }, g);
        svgEl('circle', { cx: x(r.a), cy: y, r: 6, class: 'db-dot', style: `fill:${o.aColor || 'var(--neutral-2)'}` }, g);
        svgEl('circle', { cx: x(r.b), cy: y, r: 6, class: 'db-dot', style: `fill:${o.bColor || 'var(--series-1)'}` }, g);
        const diff = r.b - r.a, rel = r.a ? diff / r.a : null;
        text(g, f.iw + 10, y + 4, (o.diffFormat || ((d, rl) => `${fmt().signedPct(rl, 1)} (${fmt().money(d)})`))(diff, rel), 'val-label tnum' + (rel != null && Math.abs(rel) > (o.strongAt || 0.05) ? ' strong' : ''));
      } else text(g, 4, y + 4, 'no data', 'val-label muted');
      svgEl('rect', { x: -f.m.left, y: y - rowH / 2, width: f.width, height: rowH, class: 'hit' }, g);
      hover(g, (e) => showTip(e, r.label, [{ key: o.aColor || 'var(--neutral-2)', label: o.aLabel, value: format(r.a) }, { key: o.bColor || 'var(--series-1)', label: o.bLabel, value: format(r.b) }, { label: 'difference', value: r.a != null ? `${fmt().money(r.b - r.a)} (${fmt().signedPct(r.a ? (r.b - r.a) / r.a : null, 1)})` : '–', muted: true }, ...(r.sub ? [{ label: '', value: r.sub, muted: true }] : [])], e.clientX == null ? centerOf(g) : null));
      clickable(g, r.onClick);
    });
    return { head: [o.labelHead || 'Group', o.aLabel, o.bLabel, 'Difference', 'Difference %'], rows: rows.map((r) => [r.label, format(r.a), format(r.b), r.a != null ? fmt().money(r.b - r.a) : '–', r.a ? fmt().signedPct((r.b - r.a) / r.a, 1) : '–']) };
  }

  /** Heatmap. rows, cols, values[][]; n[][] optional (small-n greying); o.diverging => blue/red around o.mid; o.colorFor(v) override. */
  function heatmap(el, o) {
    const R = o.rows, C = o.cols, V = o.values.map((row) => row.map((v) => (v != null && finite(v) ? v : null))), cellH = o.cellH || 32, format = o.format || ((v) => fmt().pct(v));
    if (!R.length) { el.innerHTML = ''; return { head: [], rows: [] }; }
    const f = frame(el, { height: R.length * cellH + 60, margin: { top: 30, right: 16, bottom: 30, left: o.labelWidth || 180 }, aria: o.aria });
    const flat = V.flat().filter((v) => v != null), vmax = o.max != null ? o.max : Math.max(1e-9, ...flat), vmin = o.min != null ? o.min : Math.min(0, ...flat);
    const cw = f.iw / C.length;
    const colLabel = (c) => { const full = o.colFormat ? o.colFormat(c) : String(c); const short = cw < 44 && o.colFormatShort ? o.colFormatShort(c) : full; return truncate(short, Math.max(3, Math.floor((cw - 6) / 6.3))); };
    C.forEach((c, j) => text(f.g, j * cw + cw / 2, -10, colLabel(c), 'ax-label tnum', { 'text-anchor': 'middle' }));
    const stepOf = (v) => {
      if (o.diverging) { const mid = o.mid || 0, span = Math.max(Math.abs(vmax - mid), Math.abs(vmin - mid)) || 1; const t = (v - mid) / span; const k = Math.min(2, Math.ceil(Math.abs(t) * 2 + 1e-9)); return t > 0.02 ? `var(--div-pos-${k})` : t < -0.02 ? `var(--div-neg-${k})` : 'var(--div-mid)'; }
      const s = Math.min(7, Math.max(1, Math.ceil(((v - vmin) / (vmax - vmin || 1)) * 7))); return `var(--seq-${s})`;
    };
    const dark = (v) => { if (o.diverging) { const mid = o.mid || 0, span = Math.max(Math.abs(vmax - mid), Math.abs(vmin - mid)) || 1; return Math.abs((v - mid) / span) > 0.5; } return ((v - vmin) / (vmax - vmin || 1)) * 7 > 4; };
    const table = R.map((r, i) => [r, ...C.map((_, j) => (V[i][j] != null ? format(V[i][j]) + (o.n && o.n[i][j] != null ? ` (n=${o.n[i][j]})` : '') : '–'))]);
    R.forEach((r, i) => {
      text(f.g, -10, i * cellH + cellH / 2 + 4, truncate(r, (f.m.left - 14) / 6.6), 'row-label', { 'text-anchor': 'end' });
      C.forEach((c, j) => {
        const v = V[i][j], n = o.n ? o.n[i][j] : null, small = n != null && n < (o.smallN || 3);
        const g = svgEl('g', { class: small ? 'small-n' : '', tabindex: 0 }, f.g);
        svgEl('rect', { x: j * cw + 1, y: i * cellH + 1, width: cw - 2, height: cellH - 2, rx: 3, class: 'cell', style: v == null ? 'fill:var(--surface-2)' : `fill:${stepOf(v)}` }, g);
        if (v != null && cw > 34) text(g, j * cw + cw / 2, i * cellH + cellH / 2 + 4, small ? `(${format(v)})` : format(v), 'cell-label tnum ' + (dark(v) ? 'on-dark' : 'on-light'), { 'text-anchor': 'middle' });
        hover(g, (e) => showTip(e, `${r} · ${o.colFormat ? o.colFormat(c) : c}`, [{ key: v == null ? null : stepOf(v), label: o.valueLabel || '', value: v != null ? format(v) : 'no data' }, ...(n != null ? [{ label: (o.nLabel || 'records') + (small ? ' (too few to rely on)' : ''), value: fmt().int(n), muted: true }] : []), ...(o.extra ? o.extra(i, j) : [])], e.clientX == null ? centerOf(g) : null));
        clickable(g, o.onClick ? () => o.onClick(i, j) : null);
      });
    });
    const lg = h('div', 'seq-legend', el);
    if (o.diverging) { h('span', 'seq-legend-label', lg, format(vmin)); ['var(--div-neg-2)', 'var(--div-neg-1)', 'var(--div-mid)', 'var(--div-pos-1)', 'var(--div-pos-2)'].forEach((c) => { const sw = h('span', 'seq-swatch', lg); sw.style.background = c; }); h('span', 'seq-legend-label', lg, format(vmax) + (o.valueLabel ? ` ${o.valueLabel}` : '')); }
    else { h('span', 'seq-legend-label', lg, format(vmin)); for (let s = 1; s <= 7; s++) { const sw = h('span', 'seq-swatch', lg); sw.style.background = `var(--seq-${s})`; } h('span', 'seq-legend-label', lg, format(vmax) + (o.valueLabel ? ` ${o.valueLabel}` : '')); }
    return { head: [o.rowHead || '', ...C.map((c) => (o.colFormat ? o.colFormat(c) : c))], rows: table };
  }

  /** Scatter: points [{x,y,label,color,r,sub,onClick}], log x optional, reference lines. */
  function scatter(el, o) {
    const P = o.points.filter((p) => finite(p.x) && finite(p.y)), fx = o.xFormat || ((v) => fmt().money(v)), fy = o.yFormat || ((v) => fmt().pct(v));
    if (!P.length) { el.innerHTML = ''; h('div', 'empty', el, 'No points to plot'); return { head: [], rows: [] }; }
    const f = frame(el, { height: o.height || 300, margin: { top: 26, right: 20, bottom: 44, left: 56 }, aria: o.aria });
    let maxX = o.maxX || Math.max(...P.map((p) => p.x)) * 1.1; const maxY = o.maxY || Math.max(1e-9, ...P.map((p) => p.y)) * 1.1;
    if (o.logX && !(maxX > o.logX * 10)) maxX = o.logX * 10;
    const x = o.logX ? logS(o.logX, maxX, 0, f.iw) : lin(0, maxX, 0, f.iw), y = lin(0, maxY, f.ih, 0);
    yGrid(f, y, niceTicks(maxY, 4), (t) => fy(t));
    if (o.logX) { for (let p = Math.ceil(Math.log10(o.logX)); p <= Math.log10(maxX); p++) { const t = Math.pow(10, p); svgEl('line', { y1: 0, y2: f.ih, x1: x(t), x2: x(t), class: 'gridline' }, f.g); text(f.g, x(t), f.ih + 18, fx(t), 'ax-label tnum', { 'text-anchor': 'middle' }); } } else xGrid(f, x, niceTicks(maxX, Math.max(2, Math.floor(f.iw / 90))), (t) => fx(t));
    axisTitle(f, o.yTitle, 'y'); axisTitle(f, o.xTitle, 'x');
    if (o.legend) legend(el, o.legend);
    if (o.refY != null) { svgEl('line', { x1: 0, x2: f.iw, y1: y(o.refY), y2: y(o.refY), class: 'ref-line' }, f.g); if (o.refLabel) text(f.g, f.iw, y(o.refY) - 6, o.refLabel, 'ref-label', { 'text-anchor': 'end' }); }
    if (o.trend) { const d = 'M' + o.trend.map((p) => `${x(p.x)},${y(p.y)}`).join('L'); svgEl('path', { d, class: 'fit-line' }, f.g); }
    P.forEach((p) => {
      const g = svgEl('g', { tabindex: 0 }, f.g);
      svgEl('circle', { cx: x(p.x), cy: y(Math.min(p.y, maxY)), r: p.r || 4.5, class: 'marker', style: `fill:${p.color || 'var(--series-1)'};fill-opacity:.85` }, g);
      svgEl('circle', { cx: x(p.x), cy: y(Math.min(p.y, maxY)), r: 12, class: 'hit' }, g);
      hover(g, (e) => showTip(e, p.label, [{ key: p.color || 'var(--series-1)', label: o.yTitle, value: fy(p.y) }, { label: o.xTitle, value: fx(p.x) }, ...(p.sub ? [{ label: '', value: p.sub, muted: true }] : []), ...(p.onClick ? [{ label: '', value: 'Click to open profile', muted: true }] : [])], e.clientX == null ? centerOf(g) : null));
      clickable(g, p.onClick);
    });
    if (o.annotations) for (const a of o.annotations) { const p = P.find((q) => q.id === a.x || q.label === a.x); if (p) callout(f, { x: x(p.x), y: y(p.y), text: a.text, placement: a.placement }); }
    return { head: ['Point', o.xTitle, o.yTitle], rows: P.map((p) => [p.label, fx(p.x), fy(p.y)]) };
  }

  /** Dot strip on a relative-time axis: points [{t (days), amount, label, tag, color, sub, onClick}], window:[t0,t1] shaded. */
  function dotStrip(el, o) {
    const P = o.points.filter((p) => finite(p.t));
    if (!P.length) { el.innerHTML = ''; h('div', 'empty', el, 'No records to plot'); return { head: [], rows: [] }; }
    const f = frame(el, { height: o.height || 200, margin: { top: 30, right: 20, bottom: 40, left: 20 }, aria: o.aria });
    const lo = o.min != null ? o.min : Math.min(...P.map((p) => p.t), o.window ? o.window[0] : 0) - 30, hi = o.max != null ? o.max : Math.max(...P.map((p) => p.t), o.window ? o.window[1] : 0) + 30;
    const x = lin(lo, hi, 0, f.iw);
    if (o.window) { svgEl('rect', { x: x(o.window[0]), y: 0, width: x(o.window[1]) - x(o.window[0]), height: f.ih, class: 'window-band' }, f.g); text(f.g, x(o.window[0]) + 6, 14, o.windowLabel || 'window', 'window-label'); }
    xGrid(f, x, niceTicks(hi, 8, lo), (t) => (t === 0 ? o.zeroLabel || '0' : `${t > 0 ? '+' : ''}${Math.round(t / 30)} mo`));
    svgEl('line', { x1: x(0), x2: x(0), y1: 0, y2: f.ih, class: 'ref-line' }, f.g);
    axisTitle(f, o.xTitle, 'x');
    // jitter rows deterministically to avoid overplotting
    const rows = o.rowsCount || 6, rowH = (f.ih - 30) / rows;
    P.forEach((p, i) => {
      const yy = 30 + (M.stats.hash(p.label + i) * rows | 0) * rowH + rowH / 2, r = Math.max(3.5, Math.min(11, Math.sqrt((p.amount || 500) / 100)));
      const g = svgEl('g', { tabindex: 0 }, f.g);
      svgEl('circle', { cx: x(p.t), cy: yy, r, class: 'marker', style: `fill:${p.color || 'var(--series-1)'};fill-opacity:.8` }, g);
      svgEl('circle', { cx: x(p.t), cy: yy, r: Math.max(12, r), class: 'hit' }, g);
      hover(g, (e) => showTip(e, p.label, [{ key: p.color || 'var(--series-1)', label: 'amount', value: fmt().money(p.amount) }, { label: 'days from approval', value: `${p.t > 0 ? '+' : ''}${Math.round(p.t)}` }, ...(p.tag ? [{ label: '', value: p.tag, muted: true }] : []), ...(p.sub ? [{ label: '', value: p.sub, muted: true }] : [])], e.clientX == null ? centerOf(g) : null));
      clickable(g, p.onClick);
    });
    return { head: ['Record', 'Days from approval', 'Amount', 'Status'], rows: P.map((p) => [p.label, Math.round(p.t), fmt().money(p.amount), p.tag || '']) };
  }

  /** Slope chart: rows [{label, a, b, color, onClick}] between two labelled columns. */
  function slope(el, o) {
    const rows = o.rows.filter((r) => finite(r.a) && finite(r.b)), format = o.format || ((v) => fmt().money(v));
    if (!rows.length) { el.innerHTML = ''; h('div', 'empty', el, 'No values to plot'); return { head: [], rows: [] }; }
    const f = frame(el, { height: o.height || Math.max(320, rows.length * 30 + 60), margin: { top: 30, right: 210, bottom: 20, left: 230 }, aria: o.aria });
    const vals = rows.flatMap((r) => [r.a, r.b]).filter((v) => v != null), maxY = Math.max(...vals) * 1.05, minY = 0;
    const y = o.log ? (v) => f.ih - ((Math.log10(Math.max(v, o.log)) - Math.log10(o.log)) / (Math.log10(maxY) - Math.log10(o.log))) * f.ih : lin(minY, maxY, f.ih, 0);
    svgEl('line', { x1: 0, x2: 0, y1: 0, y2: f.ih, class: 'ax-base' }, f.g); svgEl('line', { x1: f.iw, x2: f.iw, y1: 0, y2: f.ih, class: 'ax-base' }, f.g);
    text(f.g, 0, -12, o.aLabel, 'ax-title', { 'text-anchor': 'middle' }); text(f.g, f.iw, -12, o.bLabel, 'ax-title', { 'text-anchor': 'middle' });
    const placed = { l: [], r: [] };
    const nudge = (arr, yy) => { arr.sort((a, b) => a - b); for (const p of arr) if (Math.abs(p - yy) < 14) yy = p + 14; arr.push(yy); return yy; };
    rows.forEach((r) => {
      const g = svgEl('g', { tabindex: 0, class: 'row' }, f.g);
      const ya = y(r.a), yb = y(r.b);
      svgEl('line', { x1: 0, x2: f.iw, y1: ya, y2: yb, class: 'line', style: `stroke:${r.color || 'var(--series-1)'};stroke-width:${r.width || 2}` }, g);
      svgEl('circle', { cx: 0, cy: ya, r: 4, class: 'marker', style: `fill:${r.color || 'var(--series-1)'}` }, g); svgEl('circle', { cx: f.iw, cy: yb, r: 4, class: 'marker', style: `fill:${r.color || 'var(--series-1)'}` }, g);
      const la = nudge(placed.l, ya), lb = nudge(placed.r, yb);
      text(g, -10, la + 4, `${truncate(r.label, 26)} ${format(r.a)}`, 'ax-label', { 'text-anchor': 'end' });
      text(g, f.iw + 10, lb + 4, `${format(r.b)} ${r.sub || ''}`, 'val-label tnum');
      hover(g, (e) => showTip(e, r.label, [{ key: r.color || 'var(--series-1)', label: o.aLabel, value: format(r.a) }, { key: r.color || 'var(--series-1)', label: o.bLabel, value: format(r.b) }, { label: 'change', value: r.a ? fmt().signedPct((r.b - r.a) / r.a) : '–', muted: true }], e.clientX == null ? centerOf(g) : null));
      clickable(g, r.onClick);
    });
    return { head: ['Row', o.aLabel, o.bLabel, 'Change'], rows: rows.map((r) => [r.label, format(r.a), format(r.b), r.a ? fmt().signedPct((r.b - r.a) / r.a) : '–']) };
  }

  /** Sparkline for tiles. */
  function sparkline(el, values, color) { const w = 90, hh = 26; const svg = svgEl('svg', { viewBox: `0 0 ${w} ${hh}`, width: w, height: hh, class: 'spark' }, el); const v = values.filter((x) => x != null); if (v.length < 2) return; const mx = Math.max(...v), mn = Math.min(...v); const pts = v.map((val, i) => `${(i / (v.length - 1)) * w},${hh - 2 - ((val - mn) / (mx - mn || 1)) * (hh - 4)}`); svgEl('path', { d: 'M' + pts.join('L'), class: 'spark-line', style: `stroke:${color || 'var(--text-muted)'}` }, svg); const last = pts[pts.length - 1].split(','); svgEl('circle', { cx: last[0], cy: last[1], r: 3, style: `fill:${color || 'var(--series-1)'}` }, svg); }

  /** Sortable, searchable HTML table. cols:[{key,label,num,format,render}]; rows objects; o.search; o.pageSize. */
  function dataTable(el, o) {
    const sortCol = o.cols.find((c) => c.key === o.sort) || o.cols[0];
    const state = { sort: sortCol.key, dir: o.dir || (sortCol.num ? 'desc' : 'asc'), q: '', limit: o.pageSize || 50 };
    const tools = h('div', 'table-tools', el);
    let input;
    if (o.search !== false) { input = h('input', '', tools); input.type = 'search'; input.placeholder = o.placeholder || 'Filter rows…'; input.setAttribute('aria-label', 'Filter rows'); input.addEventListener('input', () => { state.q = input.value.toLowerCase(); state.limit = o.pageSize || 50; draw(); }); }
    const count = h('span', '', tools);
    const wrap = h('div', 'table-wrap', el);
    function draw() {
      wrap.innerHTML = '';
      let rows = o.rows;
      if (state.q) rows = rows.filter((r) => o.cols.some((c) => String(c.text ? c.text(r) : r[c.key] == null ? '' : r[c.key]).toLowerCase().includes(state.q)));
      const col = o.cols.find((c) => c.key === state.sort);
      const sv = (r) => { const v = col.sortVal ? col.sortVal(r) : r[col.key]; return v == null || (typeof v === 'number' && !isFinite(v)) ? null : Array.isArray(v) ? v.join(', ') : v; };
      rows = rows.slice().sort((a, b) => { const va = sv(a), vb = sv(b); if (va == null && vb == null) return 0; if (va == null) return 1; if (vb == null) return -1; const c = col.num && typeof va === 'number' && typeof vb === 'number' ? va - vb : String(va).localeCompare(String(vb)); return state.dir === 'asc' ? c : -c; });
      count.textContent = `${Math.min(rows.length, state.limit).toLocaleString()} of ${rows.length.toLocaleString()} rows` + (o.totalNote ? ` · ${o.totalNote}` : '');
      const t = h('table', 'data-table', wrap), thead = h('thead', '', t), tr = h('tr', '', thead);
      o.cols.forEach((c, ci) => { const th = h('th', 'sortable' + (c.num ? '' : ' txt'), tr); th.scope = 'col'; const b = h('button', 'th-btn', th, c.label); b.type = 'button'; th.setAttribute('aria-sort', c.key === state.sort ? (state.dir === 'asc' ? 'ascending' : 'descending') : 'none'); b.addEventListener('click', () => { if (state.sort === c.key) state.dir = state.dir === 'asc' ? 'desc' : 'asc'; else { state.sort = c.key; state.dir = c.num ? 'desc' : 'asc'; } draw(); const again = wrap.querySelectorAll('th .th-btn')[ci]; if (again) again.focus(); }); });
      const tb = h('tbody', '', t);
      rows.slice(0, state.limit).forEach((r) => { const row = h('tr', '', tb); o.cols.forEach((c) => { const td = h('td', c.num ? '' : 'txt', row); if (c.render) c.render(td, r); else if (c.text) td.textContent = c.text(r); else td.textContent = c.format ? c.format(r[c.key], r) : r[c.key] == null ? '–' : Array.isArray(r[c.key]) ? r[c.key].join(', ') : r[c.key]; }); });
      if (!rows.length) h('div', 'empty', wrap, state.q ? 'No rows match this text filter.' : 'No rows.');
      if (rows.length > state.limit) { const more = h('button', 'link', wrap, `Show ${Math.min(100, rows.length - state.limit)} more`); more.type = 'button'; more.style.margin = '8px 0'; more.addEventListener('click', () => { state.limit += 100; draw(); }); }
    }
    draw();
    return { head: o.cols.map((c) => c.label), rows: o.rows.map((r) => o.cols.map((c) => (c.text ? c.text(r) : c.format ? c.format(r[c.key], r) : r[c.key]))) };
  }

  M.charts = { bars, stackedBars, lines, histogram, rangeBars, dumbbell, heatmap, scatter, dotStrip, slope, sparkline, dataTable, legend, showTip, hideTip, h, svgEl, text, frame, lin, niceTicks, hover, centerOf, truncate };
})();
