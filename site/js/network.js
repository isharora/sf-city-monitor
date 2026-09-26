/* network.js - readable-at-scale network graph (SVG, no dependencies).
   Strategy: prune (top-K edges by weight, plus the selected node's neighborhood), cluster
   (deterministic force layout with a gravity well per cluster), search (type to focus).
   Colour = entity type (fixed slots). Individuals appear only as grey aggregate nodes. */
(function () {
  const M = (window.SFCM = window.SFCM || {});
  const { svgEl, text, h, showTip, hideTip, hover, centerOf } = M.charts;
  const fmt = () => M.stats.fmt;

  /** Deterministic force layout. nodes [{id, w, cluster}], edges [{a, b, w}]. Returns positions. */
  function layout(nodes, edges, width, height, clusters) {
    const idx = new Map(nodes.map((n, i) => [n.id, i]));
    const N = nodes.length, px = new Float64Array(N), py = new Float64Array(N), vx = new Float64Array(N), vy = new Float64Array(N);
    const cl = clusters.map((c, i) => ({ id: c, x: width / 2 + Math.cos((i / clusters.length) * Math.PI * 2 - Math.PI / 2) * width * 0.3, y: height / 2 + Math.sin((i / clusters.length) * Math.PI * 2 - Math.PI / 2) * height * 0.3 }));
    nodes.forEach((n, i) => { const c = cl.find((q) => q.id === n.cluster) || { x: width / 2, y: height / 2 }; const r1 = M.stats.hash(n.id), r2 = M.stats.hash(n.id + 'y'); px[i] = c.x + (r1 - 0.5) * 120; py[i] = c.y + (r2 - 0.5) * 120; });
    const E = edges.map((e) => [idx.get(e.a), idx.get(e.b), e.w]).filter((e) => e[0] != null && e[1] != null);
    const rad = nodes.map((n) => n.r);
    const iters = N > 200 ? 160 : 240;
    for (let it = 0; it < iters; it++) {
      const alpha = 1 - it / iters, k = 0.9 * alpha + 0.05;
      for (let i = 0; i < N; i++) for (let j = i + 1; j < N; j++) {
        let dx = px[j] - px[i], dy = py[j] - py[i]; let d2 = dx * dx + dy * dy; if (d2 < 1) { dx = (M.stats.hash(i + ':' + j) - 0.5) || 0.1; dy = 0.1; d2 = dx * dx + dy * dy; }
        const d = Math.sqrt(d2), min = rad[i] + rad[j] + 14;
        let f = (2200 / d2) * k; if (d < min) f += (min - d) * 0.6;
        const fx = (dx / d) * f, fy = (dy / d) * f; vx[i] -= fx; vy[i] -= fy; vx[j] += fx; vy[j] += fy;
      }
      for (const [a, b, w] of E) { const dx = px[b] - px[a], dy = py[b] - py[a], d = Math.sqrt(dx * dx + dy * dy) || 1; const f = (d - 90) * 0.02 * Math.min(1, 0.3 + w) * k; vx[a] += (dx / d) * f; vy[a] += (dy / d) * f; vx[b] -= (dx / d) * f; vy[b] -= (dy / d) * f; }
      for (let i = 0; i < N; i++) { const c = cl.find((q) => q.id === nodes[i].cluster); if (c) { vx[i] += (c.x - px[i]) * 0.02 * k; vy[i] += (c.y - py[i]) * 0.02 * k; } vx[i] += (width / 2 - px[i]) * 0.004 * k; vy[i] += (height / 2 - py[i]) * 0.004 * k; }
      for (let i = 0; i < N; i++) { vx[i] *= 0.6; vy[i] *= 0.6; px[i] = Math.max(rad[i] + 4, Math.min(width - rad[i] - 4, px[i] + vx[i])); py[i] = Math.max(rad[i] + 4, Math.min(height - rad[i] - 4, py[i] + vy[i])); }
    }
    return { px, py, clusters: cl };
  }

  /** Render. o: {entities (Map id->entity), edges:[{from,to,type,amount,count}], selected, onSelect(id), maxEdges, labelTop, clusterLabels{id:label}} */
  function graph(el, o) {
    el.innerHTML = '';
    const width = Math.max(600, el.getBoundingClientRect().width || 900), height = o.height || 620;
    const svg = svgEl('svg', { viewBox: `0 0 ${width} ${height}`, role: 'group', 'aria-label': (o.aria || 'Network graph') + '. Tab to nodes and edges; Enter focuses a node.' }, el);
    const t = svgEl('title', {}, svg); t.textContent = o.aria || 'Network of entities and money flows';
    // aggregate edges by pair (undirected for layout, directed for display)
    const pair = new Map();
    for (const e of o.edges) { const k = e.from + '→' + e.to; const p = pair.get(k) || { a: e.from, b: e.to, amount: 0, count: 0, types: new Set(), n: 0 }; p.amount += e.amount || 0; p.count += e.count || 1; p.types.add(e.type); p.n++; pair.set(k, p); }
    let list = [...pair.values()];
    const weightOf = (p) => (p.amount > 0 ? p.amount : p.count * 500); // contacts have no dollars: weight by count at $500/contact for layout only
    list.forEach((p) => (p.w = weightOf(p)));
    list.sort((a, b) => b.w - a.w);
    const total = list.length;
    const keep = new Set(list.slice(0, o.maxEdges || 80).map((p) => p.a + '→' + p.b));
    if (o.selected) for (const p of list) if (p.a === o.selected || p.b === o.selected) keep.add(p.a + '→' + p.b);
    list = list.filter((p) => keep.has(p.a + '→' + p.b));
    const hidden = total - list.length;
    const nodeW = new Map();
    for (const p of list) { nodeW.set(p.a, (nodeW.get(p.a) || 0) + p.w); nodeW.set(p.b, (nodeW.get(p.b) || 0) + p.w); }
    const maxW = Math.max(1, ...nodeW.values());
    const nodes = [...nodeW.keys()].map((id) => { const e = o.entities.get(id) || { id, name: id, type: 'other', cluster: 'other' }; return { id, e, w: nodeW.get(id), r: 5 + Math.sqrt(nodeW.get(id) / maxW) * 22, cluster: e.cluster || e.type }; });
    const clusters = [...new Set(nodes.map((n) => n.cluster))];
    const maxEdgeW = Math.max(1, ...list.map((p) => p.w));
    const pos = layout(nodes, list.map((p) => ({ a: p.a, b: p.b, w: p.w / maxEdgeW })), width, height, clusters);
    const P = new Map(nodes.map((n, i) => [n.id, { x: pos.px[i], y: pos.py[i] }]));
    // cluster labels
    const gl = svgEl('g', {}, svg);
    pos.clusters.forEach((c) => { const members = nodes.filter((n) => n.cluster === c.id); if (!members.length) return; const cx = members.reduce((a, n) => a + P.get(n.id).x, 0) / members.length; const minY = Math.min(...members.map((n) => P.get(n.id).y - n.r)); text(gl, Math.max(40, Math.min(width - 40, cx)), Math.max(14, minY - 14), (o.clusterLabels && o.clusterLabels[c.id]) || c.id, 'nw-cluster-label', { 'text-anchor': 'middle' }); });
    const neighbors = new Set(); if (o.selected) { neighbors.add(o.selected); for (const p of list) { if (p.a === o.selected) neighbors.add(p.b); if (p.b === o.selected) neighbors.add(p.a); } }
    // edges
    const ge = svgEl('g', {}, svg);
    for (const p of list) {
      const a = P.get(p.a), b = P.get(p.b); if (!a || !b) continue;
      const w = 1 + Math.sqrt(p.w / maxEdgeW) * 9;
      const dim = o.selected && !(p.a === o.selected || p.b === o.selected);
      const dx = b.x - a.x, dy = b.y - a.y, d = Math.sqrt(dx * dx + dy * dy) || 1, curve = 0.12 * d;
      const mx = (a.x + b.x) / 2 - (dy / d) * curve, my = (a.y + b.y) / 2 + (dx / d) * curve;
      const path = svgEl('path', { d: `M${a.x},${a.y}Q${mx},${my} ${b.x},${b.y}`, class: 'nw-edge' + (dim ? ' dim' : ''), 'stroke-width': w, style: `opacity:${dim ? 0.06 : 0.28 + 0.4 * Math.sqrt(p.w / maxEdgeW)}`, tabindex: 0 }, ge);
      const ea = o.entities.get(p.a), eb = o.entities.get(p.b);
      hover(path, (e) => showTip(e, `${ea ? ea.name : p.a} → ${eb ? eb.name : p.b}`, [{ key: 'var(--text-secondary)', label: 'total amount', value: p.amount ? fmt().money(p.amount) : 'no dollar amount' }, { label: 'records / contacts', value: fmt().int(p.count), muted: true }, { label: 'flow types', value: [...p.types].map((x) => o.flowLabel ? o.flowLabel(x) : x).join(', '), muted: true }], e.clientX == null ? centerOf(path) : null));
    }
    // nodes
    const gn = svgEl('g', {}, svg);
    const byW = nodes.slice().sort((a, b) => b.w - a.w);
    const labelSet = new Set(byW.slice(0, o.labelTop || 14).map((n) => n.id)); if (o.selected) neighbors.forEach((id) => labelSet.add(id));
    for (const n of nodes) {
      const p = P.get(n.id);
      const g = svgEl('g', { class: 'nw-node' + (o.selected === n.id ? ' sel' : '') + (o.selected && !neighbors.has(n.id) ? ' dim' : ''), tabindex: 0, role: 'button', 'aria-label': `${n.e.name} (${n.e.type})` }, gn);
      svgEl('circle', { cx: p.x, cy: p.y, r: n.r, style: `fill:var(--c-${n.e.type}, var(--neutral))` }, g);
      if (n.e.type === 'individuals') svgEl('circle', { cx: p.x, cy: p.y, r: Math.max(1, n.r - 3), style: 'fill:none;stroke:var(--surface-1);stroke-width:1.5;stroke-dasharray:3 2' }, g);
      if (labelSet.has(n.id)) text(g, p.x, p.y - n.r - 4, M.charts.truncate(n.e.name, 28), 'nw-label', { 'text-anchor': 'middle' });
      hover(g, (e) => showTip(e, n.e.name, [{ key: `var(--c-${n.e.type}, var(--neutral))`, label: o.typeLabel ? o.typeLabel(n.e.type) : n.e.type, value: '' }, { label: 'connected dollars (shown edges)', value: fmt().money(nodeW.get(n.id)), muted: true }, ...(n.e.count ? [{ label: 'individuals aggregated', value: fmt().int(n.e.count), muted: true }] : []), { label: '', value: 'Click to focus; open profile in the side panel', muted: true }], e.clientX == null ? centerOf(g) : null));
      g.addEventListener('click', () => o.onSelect && o.onSelect(n.id)); g.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); if (o.onSelect) o.onSelect(n.id); } });
    }
    const rows = list.map((p) => [(o.entities.get(p.a) || {}).name || p.a, (o.entities.get(p.b) || {}).name || p.b, [...p.types].join(', '), p.amount ? fmt().money(p.amount) : '–', fmt().int(p.count)]);
    return { table: { head: ['From', 'To', 'Flow types', 'Amount', 'Records'], rows }, nodes: nodes.length, edges: list.length, hidden, total: list.reduce((a, p) => a + p.amount, 0), neighbors };
  }
  M.network = { graph, layout };
})();
