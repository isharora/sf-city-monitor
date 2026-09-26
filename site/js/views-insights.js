/* views-insights.js - the insights-first front door of each dashboard (design/insights/INSIGHTS_DESIGN.md).
   Ported from design/insights/prototype/js/insights.js; the shell parts (sidebar, top bar, theme, help) are the
   site's own, and this file registers one view per dashboard whose module ships a valid
   <module>/data/site/insights/insights.json (checked by tools/bundle.py): pf-insights today; np-insights,
   au-insights and nw-insights appear by themselves once those files exist. Nothing here is dashboard-specific
   except the noun in the title (NOUN below); themes, departments and counts all come from the file.
   URL state (js/state.js): topic=<theme,...> (insight themes; `theme` is already light/dark), dept=<code,...>,
   verdict=robust|fragile, insight=<id> (current card, evidence open), evidence=all, data=1. */
(function () {
  const M = window.SFCM;
  M.views = M.views || {};
  const C = M.insightsCharts, S = M.state;
  const h = (tag, cls, parent, text) => M.charts.h(tag, cls, parent, text);
  const fmt = () => M.stats.fmt;

  const MODULES = { np: 'nonprofits', pf: 'performance', au: 'audits', nw: 'network' };
  const NOUN = { np: 'nonprofit money', pf: 'budget and outcomes', au: 'audit recommendations', nw: 'the money network' };
  const THEMES = { 'spending-growth': 'Spending growth', outcomes: 'Outcomes', efficiency: 'Efficiency', staffing: 'Staffing', 'budgeting-practice': 'Budgeting practice', measurement: 'Measurement', capital: 'Capital', equity: 'Equity', other: 'Other' };
  const themeLabel = (t) => THEMES[t] || String(t).replace(/-/g, ' ').replace(/^\w/, (c) => c.toUpperCase());
  const FAILED_CHECK = /^(did not|does not|sign flip|fail|not held|reversed)/i;
  const fileOf = (dashId) => `${MODULES[dashId]}/insights/insights.json`;
  const isInsightsView = (id) => !!(M.views[id] && M.views[id].insights);

  // ---------------------------------------------------------------- helpers
  function deptShort(id) { const d = ((M.SITE && M.SITE.departments) || []).find((x) => x.id === id); return d ? d.short || d.name || id : id; }
  function deptFull(id) { const d = ((M.SITE && M.SITE.departments) || []).find((x) => x.id === id); return d ? d.name : id; }
  const knownDept = (id) => ((M.SITE && M.SITE.departments) || []).some((x) => x.id === id);
  function applyFilters(data, st) {
    return data.insights.filter((i) => (!st.topic.length || st.topic.includes(i.theme)) && (!st.dept.length || (i.departments || []).some((d) => st.dept.includes(d))) && (!st.verdict || i.robustness.verdict === st.verdict)).sort((a, b) => a.rank - b.rank);
  }
  /** Files a number cites: every path-like token (a source may name several, with notes in parentheses). */
  const srcFiles = (n) => { const src = String(n.source || ''); const m = src.match(/[\w.\/-]+\.(?:json|csv|parquet|xlsx?|pdf|txt|md)\b/gi); return m && m.length ? [...new Set(m)] : [src.split(/[#(;]/)[0].trim() || src]; };
  function isDark() { return document.documentElement.getAttribute('data-theme') === 'dark'; }
  function exploreUrl(ex) {
    const q = new URLSearchParams(); q.set('view', ex.view);
    Object.keys(ex.params || {}).forEach((k) => q.set(k, ex.params[k]));
    if (isDark()) q.set('theme', 'dark');
    return 'index.html?' + q.toString();
  }
  function exploreTitle(ex) {
    const v = M.views[ex.view], ps = Object.keys(ex.params || {});
    return `Opens ${v ? (v.nav || v.title) : ex.view} (view=${ex.view}) ${ps.length ? 'with ' + ps.map((k) => `${k}=${ex.params[k]}`).join(', ') : 'with no filters'} (o)`;
  }
  function shareUrl(viewId, id) {
    const urlTheme = new URLSearchParams(location.search).get('theme');
    return location.href.split(/[?#]/)[0] + S.serialise(Object.assign({}, S.DEFAULTS, { view: viewId, insight: id, theme: urlTheme ? (isDark() ? 'dark' : 'light') : 'auto' }));
  }
  /** Department codes in a chart's categories or series names read as short names (the chart shows them verbatim). */
  function chartForDisplay(ch) {
    const c = JSON.parse(JSON.stringify(ch));
    const nm = (v) => (typeof v === 'string' && /^[A-Z]{2,4}$/.test(v) && knownDept(v) ? deptShort(v) : v);
    if (c.x && Array.isArray(c.x.values)) c.x.values = c.x.values.map(nm);
    (c.series || []).forEach((s) => { s.name = nm(s.name); if (Array.isArray(s.labels)) s.labels = s.labels.map(nm); });
    if (Array.isArray(c.highlight)) c.highlight = c.highlight.map(nm); else if (c.highlight != null) c.highlight = nm(c.highlight);
    return c;
  }
  function verdictBadge(v, small) {
    const b = h('span', 'verdict v-' + v + (small ? ' small' : '')); h('i', 'vdot v-' + v, b);
    b.appendChild(document.createTextNode(v === 'robust' ? 'Robust' : 'Fragile'));
    b.title = v === 'robust' ? 'Held under every alternative tried' : 'At least one reasonable alternative weakened it; see Evidence';
    return b;
  }
  function copyText(url, btn, okText, restore) {
    const done = () => { btn.textContent = okText; btn.classList.add('ok'); setTimeout(() => { btn.textContent = restore; btn.classList.remove('ok'); }, 1600); };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(done, () => window.prompt('Copy this link', url));
    else window.prompt('Copy this link', url);
  }

  // ---------------------------------------------------------------- page state kept across re-renders
  let pickOpen = false, pickFocus = -1;
  let page = null; // { view, data, shown, twins, byId }

  // ---------------------------------------------------------------- header + summary
  function renderHeader(el, ctx, data) {
    el.innerHTML = '';
    const n = data.insights.length;
    const head = h('header', 'view-head ins-head', el);
    const k = h('div', 'kicker', head); h('span', '', k, `${ctx.dash.num} · ${ctx.dash.short} · Insights`);
    if (data.sample) h('span', 'badge badge-sample', k, 'Sample insights');
    h('h1', 'view-title ins-title', head, `${n} ${n === 1 ? 'thing' : 'things'} the numbers say about ${NOUN[ctx.dash.id] || ctx.dash.short.toLowerCase()}`);
    if (data.intro) h('p', 'view-what ins-intro', head, data.intro);
    const robust = data.insights.filter((i) => i.robustness.verdict === 'robust').length, fragile = n - robust;
    const themes = new Set(data.insights.map((i) => i.theme)), depts = new Set(data.insights.flatMap((i) => i.departments || []));
    const sum = h('div', 'ins-summary', head); sum.setAttribute('aria-label', 'Summary of every insight on this page');
    const item = (b, t, dot, key) => { const s = h('span', 'sum-item', sum); s.dataset.sum = key; if (dot) h('i', 'vdot v-' + dot, s); h('b', 'tnum', s, String(b)); s.appendChild(document.createTextNode(' ' + t)); return s; };
    item(robust, 'robust', 'robust', 'robust'); item(fragile, 'fragile', 'fragile', 'fragile');
    item(themes.size, themes.size === 1 ? 'theme' : 'themes', null, 'themes'); item(depts.size, depts.size === 1 ? 'department named' : 'departments named', null, 'depts');
    const how = h('details', 'howto', head); h('summary', '', how, 'How to read this page');
    h('p', '', how, 'Each card makes one claim, shows the one chart that carries it, and says how sturdy it is. Robust means the finding held under every alternative we tried (other deflators, year ranges, definitions); fragile means at least one reasonable alternative weakened or reversed it, and the card says which. "Evidence" opens the numbers with their sources, the checks run, what could make the claim wrong, and caveats. "Explore in the dashboard" opens the full view with the filters already applied.');
    h('p', '', how, 'Unusual is not improper. A pattern here is a reason to ask a question, not an answer to it.');
  }

  // ---------------------------------------------------------------- filter bar (every filter applies to everything on the page)
  function renderFilters(ctx, data) {
    const st = ctx.state, bar = document.getElementById('filterbar');
    bar.innerHTML = ''; bar.hidden = false;
    const set = (patch) => S.set(Object.assign({ insight: '' }, patch));
    const themes = {}; data.insights.forEach((i) => { themes[i.theme] = (themes[i.theme] || 0) + 1; });
    const f1 = h('div', 'filter', bar); f1.dataset.insFilter = 'topic'; h('span', 'filter-label', f1, 'Theme');
    const chips = h('div', 'chips', f1); chips.setAttribute('role', 'group'); chips.setAttribute('aria-label', 'Theme');
    Object.keys(themes).forEach((t) => { const c = h('button', 'chip', chips); c.type = 'button'; c.dataset.value = t; c.setAttribute('aria-pressed', String(st.topic.includes(t))); c.appendChild(document.createTextNode(themeLabel(t))); h('span', 'chip-n tnum', c, String(themes[t])); c.addEventListener('click', () => set({ topic: st.topic.includes(t) ? st.topic.filter((x) => x !== t) : st.topic.concat(t) })); });
    // department popover (multi-select; stays open while ticking)
    const depts = {}; data.insights.forEach((i) => (i.departments || []).forEach((d) => { depts[d] = (depts[d] || 0) + 1; }));
    const f2 = h('div', 'filter pick', bar); f2.id = 'ins-dept-pick'; f2.dataset.insFilter = 'dept';
    const pb = h('button', 'pick-btn' + (st.dept.length ? ' active' : ''), f2); pb.type = 'button'; pb.setAttribute('aria-haspopup', 'listbox');
    pb.textContent = 'Department · ' + (st.dept.length ? st.dept.map(deptShort).join(', ') : 'All'); h('span', 'caret', pb, ' ▾');
    const pop = h('div', 'pick-pop', f2); pop.hidden = !pickOpen; pb.setAttribute('aria-expanded', String(pickOpen)); pop.setAttribute('role', 'listbox'); pop.setAttribute('aria-label', 'Department'); pop.setAttribute('aria-multiselectable', 'true');
    const tools = h('div', 'tools', pop); const clr = h('button', 'link-btn', tools, 'Clear'); clr.type = 'button'; clr.addEventListener('click', () => { pickOpen = true; set({ dept: [] }); });
    h('span', 'muted', tools, `${Object.keys(depts).length} departments are named in an insight`);
    Object.keys(depts).sort((a, b) => deptShort(a).localeCompare(deptShort(b))).forEach((d, idx) => {
      const row = h('label', 'row', pop); row.title = deptFull(d); const cb = h('input', '', row); cb.type = 'checkbox'; cb.value = d; cb.checked = st.dept.includes(d);
      cb.addEventListener('change', () => { pickOpen = true; pickFocus = idx; set({ dept: cb.checked ? st.dept.concat(d) : st.dept.filter((x) => x !== d) }); });
      row.appendChild(document.createTextNode(`${deptShort(d)} `)); h('span', 'muted tnum', row, String(depts[d]));
    });
    pb.addEventListener('click', () => { pop.hidden = !pop.hidden; pickOpen = !pop.hidden; pb.setAttribute('aria-expanded', String(pickOpen)); if (pickOpen) { const first = pop.querySelector('input'); if (first) first.focus(); } });
    const f3 = h('div', 'filter', bar); f3.dataset.insFilter = 'verdict'; h('span', 'filter-label', f3, 'Verdict');
    const vc = h('div', 'chips', f3); vc.setAttribute('role', 'group'); vc.setAttribute('aria-label', 'Verdict');
    [['robust', 'Robust'], ['fragile', 'Fragile']].forEach(([v, l]) => { const c = h('button', 'chip', vc); c.type = 'button'; c.dataset.value = v; c.setAttribute('aria-pressed', String(st.verdict === v)); h('i', 'vdot v-' + v, c); c.appendChild(document.createTextNode(l)); h('span', 'chip-n tnum', c, String(data.insights.filter((i) => i.robustness.verdict === v).length)); c.addEventListener('click', () => set({ verdict: st.verdict === v ? '' : v })); });
    if (st.topic.length || st.dept.length || st.verdict) { const r = h('button', 'link-btn reset', bar, 'Reset filters'); r.type = 'button'; r.addEventListener('click', () => set({ topic: [], dept: [], verdict: '' })); }
    // Dashboard filters that do not apply here, named with the reason (Principle 1).
    const L = M.app.FILTER_LABELS, absent = ctx.dash.filterKeys.filter((k) => k !== 'dept' && k !== 'topic');
    if (absent.length) {
      const na = h('span', 'filter-na', bar); na.dataset.absent = absent.join(','); na.appendChild(document.createTextNode('Not on this page: '));
      const fixed = absent.filter((k) => k === 'years' || k === 'real'), other = absent.filter((k) => !fixed.includes(k));
      fixed.forEach((k, i) => { h('b', '', na, k === 'years' ? ctx.dash.yearsLabel : L[k]); if (i < fixed.length - 1) na.appendChild(document.createTextNode(', ')); });
      if (fixed.length) na.appendChild(document.createTextNode(` (each insight fixes its own ${fixed.map((k) => (k === 'years' ? 'years' : 'dollar basis')).join(' and ')}; see its chart subtitle)`));
      other.forEach((k, i) => { na.appendChild(document.createTextNode(fixed.length || i ? '; ' : '')); h('b', '', na, L[k]); });
      if (other.length) na.appendChild(document.createTextNode(` (insights are single findings, not filtered records${ctx.dash.filterKeys.includes('dept') ? '; pick departments instead' : ''})`));
    }
    if (pickOpen) { const boxes = pop.querySelectorAll('input'); const f = boxes[pickFocus] || boxes[0]; if (f) setTimeout(() => f.focus({ preventScroll: true }), 0); }
  }
  function filtersText(st) {
    const parts = [];
    if (st.topic.length) parts.push('theme ' + st.topic.map(themeLabel).join(', '));
    if (st.dept.length) parts.push('department ' + st.dept.map(deptShort).join(', '));
    if (st.verdict) parts.push(st.verdict + ' only');
    return parts.length ? 'Filters: ' + parts.join(' · ') : 'No filters: all insights shown.';
  }

  // ---------------------------------------------------------------- data strip (same component as every view; insights counts)
  function renderData(ctx, o) {
    const el = ctx.dataEl, data = page.data, shown = page.shown, total = data.insights.length, F = fmt();
    el.innerHTML = '';
    const entry = M.data.entry(fileOf(ctx.dash.id)) || {};
    const size = F.bytes(entry.bytes || JSON.stringify(data).length);
    const strip = h('div', 'datastrip', el); strip.setAttribute('role', 'region'); strip.setAttribute('aria-label', 'How much data is feeding this page');
    h('span', 'ds-label', strip, 'Data on this page');
    const feed = (key, n, of, label) => { const it = h('span', 'ds-item ds-feed' + (n === 0 ? ' zero' : ''), strip); it.dataset.matched = n; it.dataset.total = of; it.dataset.key = key; h('b', '', it, F.int(n)); it.appendChild(document.createTextNode(of != null && of !== n ? ` of ${F.int(of)} ${label}` : ` ${label}`)); return it; };
    const nums = shown.reduce((a, i) => a + i.numbers.length, 0), files = new Set(shown.flatMap((i) => i.numbers.flatMap(srcFiles)));
    feed('insights', shown.length, total, total === 1 ? 'insight' : 'insights');
    feed('numbers', nums, null, nums === 1 ? 'cited number' : 'cited numbers');
    feed('sources', files.size, null, files.size === 1 ? 'source file' : 'source files');
    const fl = h('span', 'ds-item', strip); h('b', '', fl, '1'); fl.appendChild(document.createTextNode(` file loaded (${size})`));
    if (data.sample) h('span', 'badge badge-sample', strip, 'sample');
    if (data.as_of) { const ao = h('span', 'ds-item', strip); ao.appendChild(document.createTextNode('as of ')); h('b', '', ao, data.as_of); }
    const tog = h('button', 'link ds-toggle', strip, o.open ? 'Hide details' : 'Details'); tog.type = 'button'; tog.setAttribute('aria-expanded', String(!!o.open)); tog.setAttribute('aria-controls', 'datapanel');
    const panel = h('div', 'datapanel', el); panel.id = 'datapanel'; panel.hidden = !o.open;
    tog.addEventListener('click', () => { panel.hidden = !panel.hidden; tog.textContent = panel.hidden ? 'Details' : 'Hide details'; tog.setAttribute('aria-expanded', String(!panel.hidden)); if (o.onToggle) o.onToggle(!panel.hidden); });
    const c1 = h('div', '', panel); h('h3', '', c1, 'Insights for your current filters'); h('p', 'muted', c1, filtersText(ctx.state)).style.margin = '0 0 6px';
    const t1 = h('table', '', c1);
    const byTheme = {}; data.insights.forEach((i) => { byTheme[i.theme] = byTheme[i.theme] || { total: 0, shown: 0 }; byTheme[i.theme].total++; }); shown.forEach((i) => byTheme[i.theme].shown++);
    Object.keys(byTheme).forEach((t) => { const tr = h('tr', '', t1); const td = h('td', '', tr, themeLabel(t)); const bar = h('div', 'bar', td); h('i', '', bar).style.width = (100 * byTheme[t].shown / byTheme[t].total) + '%'; h('td', 'num', tr, `${byTheme[t].shown} / ${byTheme[t].total}`); });
    const c2 = h('div', '', panel); h('h3', '', c2, 'Source files cited by the numbers'); const t2 = h('table', '', c2); const hr = h('tr', '', t2); ['File', 'Numbers'].forEach((x, i) => h('th', i ? 'num' : '', hr, x));
    const counts = {}; shown.forEach((i) => i.numbers.forEach((n) => srcFiles(n).forEach((f) => { counts[f] = (counts[f] || 0) + 1; })));
    if (!shown.length) { const tr = h('tr', '', t2); h('td', 'muted', tr, 'No insights match the current filters.').colSpan = 2; }
    Object.keys(counts).sort((a, b) => counts[b] - counts[a] || a.localeCompare(b)).forEach((f) => { const tr = h('tr', '', t2); const td = h('td', '', tr); h('code', '', td, f); h('td', 'num', tr, String(counts[f])); });
    const c3 = h('div', '', panel); h('h3', '', c3, 'File for this page'); const t3 = h('table', '', c3); const tr = h('tr', '', t3); const td = h('td', '', tr);
    h('code', '', td, `${MODULES[ctx.dash.id]}/data/site/insights/insights.json`); if (data.sample) { td.appendChild(document.createTextNode(' ')); h('span', 'badge badge-sample', td, 'sample'); }
    const inf = M.data.info.get(fileOf(ctx.dash.id));
    h('div', 'muted', td, `${total} insights · contract design/insights/INSIGHTS_CONTRACT.json` + (inf ? (inf.via === 'fetch' ? ' · read from the export' : ' · bundled') : ''));
    h('td', 'num', tr, size);
    h('p', 'muted', c3, 'Every number on this page carries a source path; the module\'s verify script checks each one against the file it names.').style.margin = '8px 0 0';
  }

  // ---------------------------------------------------------------- glance list
  function renderGlance(el, shown, total) {
    if (!shown.length) return;
    const box = h('section', 'glance', el); box.setAttribute('aria-labelledby', 'glance-title');
    const top = h('div', 'glance-top', box); h('h2', 'section-title', top, 'Read in 30 seconds').id = 'glance-title';
    h('span', 'glance-sub', top, shown.length === total ? `All ${total}, in rank order. Click a claim to jump to its chart and evidence.` : `${shown.length} of ${total} match your filters. Click a claim to jump to it.`);
    const ol = h('ol', 'glance-list', box);
    shown.forEach((i) => {
      const li = h('li', 'glance-item', ol); li.dataset.id = i.id;
      const a = h('a', 'glance-link', li); a.href = '#' + i.id; a.addEventListener('click', (e) => { e.preventDefault(); openInsight(i.id, false); });
      h('span', 'glance-rank tnum', a, String(i.rank)); h('span', 'glance-text', a, i.title);
      h('span', 'glance-meta', li).append(verdictBadge(i.robustness.verdict, true), h('span', 'glance-theme', null, themeLabel(i.theme)));
    });
  }

  // ---------------------------------------------------------------- cards
  function card(ctx, i) {
    const art = h('article', 'card ins-card'); art.id = i.id; art.tabIndex = -1; art.dataset.rank = i.rank; art.setAttribute('aria-labelledby', i.id + '-title');
    const head = h('header', 'ins-card-head', art);
    h('span', 'ins-rank tnum', head, String(i.rank));
    const meta = h('div', 'ins-meta', head); h('span', 'tag tag-theme', meta, themeLabel(i.theme)); meta.appendChild(verdictBadge(i.robustness.verdict));
    (i.departments || []).forEach((d) => {
      if (knownDept(d)) { const a = ctx.link(deptShort(d), { view: 'dept', id: d }, 'ins-dept'); a.title = `Open the ${deptFull(d)} scorecard`; meta.appendChild(a); }
      else h('span', 'ins-dept ins-dept-plain', meta, d);
    });
    const share = h('button', 'icon-btn share-btn', head, 'Share'); share.type = 'button'; share.title = 'Copy a link to this insight (c)'; share.addEventListener('click', () => copyText(shareUrl(ctx.view.id, i.id), share, 'Link copied', 'Share'));
    h('h2', 'ins-claim', art, i.title).id = i.id + '-title';
    if (i.dek) h('p', 'ins-dek', art, i.dek);
    const ch = h('figure', 'ins-chart', art);
    const chHead = h('div', 'card-head', ch); const tt = h('div', 'card-titles', chHead); h('h3', 'card-title', tt, i.chart.title); if (i.chart.subtitle) h('p', 'card-sub', tt, i.chart.subtitle);
    const ctl = h('div', 'card-controls', chHead); const tb = h('button', 'tbl-btn', ctl, 'Table'); tb.type = 'button'; tb.setAttribute('aria-pressed', 'false'); tb.title = 'Show the chart as a table (t)';
    const body = h('div', 'card-body ins-plot', ch); body.dataset.chart = i.id;
    const twinEl = h('div', 'ins-twin', ch); twinEl.hidden = true;
    tb.addEventListener('click', () => { const on = twinEl.hidden; twinEl.hidden = !on; body.hidden = on; tb.setAttribute('aria-pressed', String(on)); tb.textContent = on ? 'Chart' : 'Table'; if (on && page.twins[i.id]) C.renderTwin(twinEl, page.twins[i.id]); });
    if (i.chart.note) h('figcaption', 'ins-note', ch, i.chart.note);
    const why = h('div', 'ins-why', art); h('span', 'ins-label', why, 'Why it matters'); h('p', '', why, i.why_it_matters);
    if (i.surprise) { const sp = h('div', 'ins-surprise', art); h('span', 'ins-label', sp, 'The surprise'); h('p', '', sp, i.surprise); }
    const act = h('div', 'ins-actions', art);
    const ev = h('button', 'icon-btn ev-btn', act, 'Evidence'); ev.type = 'button'; ev.setAttribute('aria-expanded', 'false'); ev.setAttribute('aria-controls', i.id + '-evidence'); ev.title = 'Numbers, sources, checks and caveats (e)';
    h('span', 'ev-count tnum', ev, `${i.numbers.length} ${i.numbers.length === 1 ? 'number' : 'numbers'} · ${i.robustness.checks.length} ${i.robustness.checks.length === 1 ? 'check' : 'checks'}`);
    const ex = h('a', 'explore-link', act, (i.explore.label || 'Explore in the dashboard') + ' →'); ex.href = exploreUrl(i.explore); ex.title = exploreTitle(i.explore); ex.dataset.view = i.explore.view;
    const evd = h('section', 'ins-evidence', art); evd.id = i.id + '-evidence'; evd.hidden = true; evd.setAttribute('aria-label', 'Evidence for insight ' + i.rank);
    const g = h('div', 'ev-grid', evd);
    const n = h('div', 'ev-col', g); h('h4', 'ev-title', n, 'The numbers');
    const nl = h('ol', 'ev-numbers', n); i.numbers.forEach((x) => { const li = h('li', 'ev-num', nl); h('span', 'ev-nvalue tnum', li, x.value); h('span', 'ev-nlabel', li, x.label); const src = h('span', 'ev-nsrc', li); src.appendChild(document.createTextNode('Source: ')); h('code', '', src, x.source); });
    const r = h('div', 'ev-col', g); const rt = h('h4', 'ev-title', r, 'Robustness '); rt.appendChild(verdictBadge(i.robustness.verdict, true));
    const ul = h('ul', 'ev-checks', r); i.robustness.checks.forEach((c) => h('li', FAILED_CHECK.test(c) ? 'failed' : 'held', ul, c));
    if (i.robustness.what_could_make_it_wrong) { h('h4', 'ev-title', r, 'What could make it wrong'); h('p', 'ev-wrong', r, i.robustness.what_could_make_it_wrong); }
    if (i.caveats && i.caveats.length) { const cv = h('div', 'ev-col ev-caveats', g); h('h4', 'ev-title', cv, 'Caveats'); const cl = h('ul', '', cv); i.caveats.forEach((c) => h('li', '', cl, c)); }
    const foot = h('div', 'ev-foot', evd); if (i.tags && i.tags.length) h('span', 'ev-tags', foot, 'Tags: ' + i.tags.join(', '));
    const perma = h('a', 'link', foot, 'Link to this insight'); perma.href = shareUrl(ctx.view.id, i.id);
    ev.addEventListener('click', () => toggleEvidence(art, evd.hidden));
    return art;
  }
  function toggleEvidence(art, open) { const evd = art.querySelector('.ins-evidence'), btn = art.querySelector('.ev-btn'); if (!evd) return; evd.hidden = !open; btn.setAttribute('aria-expanded', String(open)); art.classList.toggle('open', open); }
  function renderCharts(root) {
    root.querySelectorAll('.ins-plot').forEach((el) => {
      const i = page.byId[el.dataset.chart]; if (!i) return;
      const tw = C.render(el, chartForDisplay(i.chart), { height: i.chart.type === 'scatter' ? 260 : i.chart.type === 'stacked' ? 230 : 220 });
      if (tw) { page.twins[i.id] = tw; const twinEl = el.parentElement.querySelector('.ins-twin'); if (!twinEl.hidden) C.renderTwin(twinEl, tw); }
      else { const tb = el.parentElement.querySelector('.tbl-btn'); if (tb) tb.hidden = true; M.app.errors.push(`insight ${i.id}: chart failed to render`); }
    });
  }
  function openInsight(id, expand) {
    const art = document.getElementById(id); if (!art || !art.classList.contains('ins-card')) return;
    document.querySelectorAll('.ins-card.current').forEach((c) => c.classList.remove('current'));
    art.classList.add('current');
    if (expand) toggleEvidence(art, true);
    if (new URLSearchParams(location.search).get('shot') === '1') { // QA only: headless Chrome does not paint scrolled content, so show just this card and the next
      document.body.classList.add('shot'); document.querySelectorAll('.ins-card.next').forEach((c) => c.classList.remove('next')); if (art.nextElementSibling) art.nextElementSibling.classList.add('next');
    } else art.scrollIntoView({ block: 'start', behavior: 'auto' });
    art.focus({ preventScroll: true });
    if (S.get().insight !== id) S.set({ insight: id }, { silent: true });
  }

  // ---------------------------------------------------------------- closing note
  function renderFoot(el, data) {
    const box = h('aside', 'caveats ins-foot', el); h('h2', 'section-title', box, 'Reading these insights');
    const ul = h('ul', '', box);
    [['high', 'Robust is not proven. It means the finding survived the alternatives listed under Evidence; a check we did not think of could still move it.'], ['medium', 'Fragile is not wrong. It means a reasonable alternative changed the picture; the card names it so you can judge.'], ['low', `Ranking is editorial: how much a finding should change what a careful reader believes, given how sturdy it is. Rank ${data.insights.length} is still worth a look.`]]
      .forEach(([sev, t]) => { const li = h('li', 'caveat sev-' + sev, ul); h('span', 'sev', li, sev === 'high' ? 'Could move the finding' : sev === 'medium' ? 'Worth knowing' : 'Minor'); li.appendChild(document.createTextNode(' ' + t)); });
    const fair = h('div', 'fair', el); h('b', '', fair, 'Unusual is not improper.'); fair.appendChild(document.createTextNode(' Every pattern on this page is a reason to ask a question, not a finding about anyone\'s conduct. Organizations and officials are named only in public roles; nobody below executive level is named.'));
  }

  // ---------------------------------------------------------------- the view
  function render(ctx) {
    const data = ctx.data.ins, st = ctx.state;
    const shown = applyFilters(data, st);
    page = { view: ctx.view.id, data, shown, twins: {}, byId: {} };
    data.insights.forEach((i) => { page.byId[i.id] = i; });
    document.title = `${ctx.dash.short}: ${data.insights.length} things the numbers say · SF City Monitor`;
    // counts for the shell and the self-test (the strip itself is drawn by renderData below)
    const nums = (list) => list.reduce((a, i) => a + i.numbers.length, 0), files = (list) => new Set(list.flatMap((i) => i.numbers.flatMap(srcFiles))).size;
    ctx.feed('insights', shown.length, data.insights.length); ctx.feed('cited numbers', nums(shown), nums(data.insights)); ctx.feed('source files', files(shown), files(data.insights));
    renderHeader(ctx.headEl, ctx, data);
    renderFilters(ctx, data);
    const wrap = h('div', 'col-12 ins-body', ctx.grid);
    const glance = h('div', '', wrap); glance.id = 'ins-glance'; renderGlance(glance, shown, data.insights.length);
    const cards = h('div', '', wrap); cards.id = 'ins-cards';
    if (!shown.length) {
      const e = h('div', 'card empty ins-empty', cards); h('b', '', e, 'No insights match these filters');
      e.appendChild(document.createTextNode('Pick another theme or department, or '));
      const r = h('button', 'link', e, 'reset the filters'); r.type = 'button'; r.addEventListener('click', () => S.set({ topic: [], dept: [], verdict: '', insight: '' }));
      e.appendChild(document.createTextNode('.'));
    } else {
      const grid = h('div', 'ins-grid', cards);
      shown.forEach((i) => grid.appendChild(card(ctx, i)));
      renderCharts(cards);
    }
    renderFoot(h('div', '', wrap), data);
  }
  function afterRender(ctx) {
    const st = ctx.state;
    if (st.evidence === 'all') document.querySelectorAll('#content .ins-card').forEach((c) => toggleEvidence(c, true));
    if (st.insight && document.getElementById(st.insight)) openInsight(st.insight, true);
    pickFocus = -1;
  }

  // ---------------------------------------------------------------- keyboard (active on insights views only)
  function currentCard() { return document.querySelector('#content .ins-card.current') || (document.activeElement && document.activeElement.closest && document.activeElement.closest('#content .ins-card')) || null; }
  function moveCard(dir) {
    const cards = [...document.querySelectorAll('#content .ins-card')]; if (!cards.length) return;
    const cur = currentCard(); let idx = cur ? cards.indexOf(cur) + dir : (dir > 0 ? 0 : cards.length - 1);
    idx = Math.max(0, Math.min(cards.length - 1, idx)); openInsight(cards[idx].id, false);
  }
  document.addEventListener('keydown', (e) => {
    if (!isInsightsView(S.get().view) || !page) return;
    if (e.target.matches && e.target.matches('input, textarea, select') || e.metaKey || e.ctrlKey || e.altKey) return;
    const help = document.getElementById('help'); if (help && !help.hidden && e.key !== 'Escape') return;
    const cur = currentCard();
    switch (e.key) {
      case 'j': case 'ArrowDown': if (e.key === 'ArrowDown' && !cur) return; e.preventDefault(); moveCard(1); break;
      case 'k': case 'ArrowUp': if (e.key === 'ArrowUp' && !cur) return; e.preventDefault(); moveCard(-1); break;
      case 'e': case 'Enter': if (!cur || (e.key === 'Enter' && e.target !== cur)) return; e.preventDefault(); toggleEvidence(cur, cur.querySelector('.ins-evidence').hidden); break;
      case 'o': if (!cur) return; e.preventDefault(); cur.querySelector('.explore-link').click(); break;
      case 'c': if (!cur) return; e.preventDefault(); cur.querySelector('.share-btn').click(); break;
      case 't': if (!cur) return; e.preventDefault(); { const b = cur.querySelector('.tbl-btn'); if (b && !b.hidden) b.click(); } break;
      case 'Escape': if (cur) { cur.classList.remove('current'); S.set({ insight: '' }, { silent: true }); } break;
      default:
    }
  });
  // department popover: close on an outside click or Escape
  document.addEventListener('click', (e) => { const pick = document.getElementById('ins-dept-pick'); if (!pick || pick.contains(e.target)) return; const pop = pick.querySelector('.pick-pop'); if (pop && !pop.hidden) { pop.hidden = true; pickOpen = false; pick.querySelector('.pick-btn').setAttribute('aria-expanded', 'false'); } });
  document.addEventListener('keydown', (e) => { if (e.key !== 'Escape') return; const pick = document.getElementById('ins-dept-pick'); const pop = pick && pick.querySelector('.pick-pop'); if (pop && !pop.hidden) { pop.hidden = true; pickOpen = false; pick.querySelector('.pick-btn').focus(); } });
  // leaving the view closes the popover; a theme switch updates the Explore links (they carry theme=dark)
  S.subscribe((st, info) => {
    if (info.changedView) { pickOpen = false; pickFocus = -1; if (!isInsightsView(st.view)) document.body.classList.remove('shot'); }
    if (info.patch && 'theme' in info.patch) setTimeout(() => document.querySelectorAll('#content .ins-card').forEach((a) => { const i = page && page.byId[a.id]; const x = a.querySelector('.explore-link'); if (i && x) x.href = exploreUrl(i.explore); }), 0);
  });
  function openAllEvidence() { document.querySelectorAll('#content .ins-card').forEach((c) => toggleEvidence(c, true)); }
  window.addEventListener('beforeprint', () => { if (isInsightsView(S.get().view)) openAllEvidence(); });
  const printBtn = document.getElementById('print-btn');
  if (printBtn) printBtn.addEventListener('click', () => { const v = M.views[S.get().view]; if (v && v.print) v.print(); });

  // ---------------------------------------------------------------- registration: only where the bundle has a valid file
  Object.keys(MODULES).forEach((dashId) => {
    const file = fileOf(dashId), e = M.data.entry(file);
    if (!e || e.status !== 'ok') return;
    const id = `${dashId}-insights`;
    M.views[id] = {
      id, dash: dashId, nav: 'Insights', navNum: '★', title: 'Insights', insights: true,
      what: 'Ranked, tested findings, each with one chart and a link into the dashboard.',
      filters: [], ownFilterBar: true, customHeader: true, headline: false, noStory: true,
      files: { ins: file }, render, renderData, afterRender, print() { openAllEvidence(); setTimeout(() => window.print(), 50); },
    };
    if (M.views.home && M.views.home.files && typeof M.views.home.files === 'object') M.views.home.files['ins_' + dashId] = file; // landing cards show the count and the top three claims
  });
  M.insights = { applyFilters, exploreUrl, shareUrl, fileOf, themeLabel, chartForDisplay, isFailedCheck: (c) => FAILED_CHECK.test(c), NOUN, THEMES, get page() { return page; } };
})();
