/* insights.js - the insights-first front door of a dashboard. Renders one insights.json (INSIGHTS_CONTRACT.json).
   Reusable across the four dashboards: everything dashboard-specific comes from DASHBOARDS[data.dashboard] and the file.
   URL state: ?topic=<theme,...>&dept=<code,...>&verdict=robust|fragile&insight=<id>&evidence=all&data=1&theme=dark
   ('topic' is the insight theme filter; 'theme' is already the light/dark parameter across the site). */
(function () {
  const M = (window.SFCM = window.SFCM || {});
  const C = M.insightsCharts;
  const $ = (s, r) => (r || document).querySelector(s);
  function h(tag, cls, parent, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; if (parent) parent.appendChild(e); return e; }
  const int = (n) => (n == null ? '–' : Number(n).toLocaleString('en-US'));

  // ---------------------------------------------------------------- dashboard registry (shell + copy per dashboard)
  const DASHBOARDS = {
    performance: { num: 2, title: 'Budget vs outcomes', noun: 'budget and outcomes', views: [['pf-overview', 'Overview'], ['pf-spending', 'What departments spend'], ['pf-staffing', 'Headcount and overtime'], ['pf-outcomes', 'Measures vs targets'], ['pf-cost', 'Cost per outcome'], ['pf-integrity', 'Dropped measures, lowered targets'], ['pf-gaps', 'Budget vs actual'], ['pf-depts', 'Departments']] },
    nonprofits: { num: 1, title: 'Nonprofit money', noun: 'nonprofit money', views: [['np-overview', 'Overview'], ['np-flows', 'Who gets paid'], ['np-dependency', 'Dependency'], ['np-pay', 'Pay and reserves'], ['np-growth', 'Contract growth'], ['np-reviews', 'Monitoring results'], ['np-orgs', 'Organizations']] },
    audits: { num: 3, title: 'Audit tracker', noun: 'audit recommendations', views: [['au-overview', 'Overview'], ['au-status', 'Status'], ['au-time', 'Time to implement'], ['au-agreement', 'Agreement'], ['au-repeat', 'Repeats'], ['au-open', 'Open'], ['au-reports', 'Reports']] },
    network: { num: 4, title: 'Money network', noun: 'the money network', views: [['nw-overview', 'Overview'], ['nw-graph', 'Graph'], ['nw-ban', 'Contractor contributions'], ['nw-behested', 'Behested payments'], ['nw-lobby', 'Lobbying'], ['nw-concentration', 'Concentration'], ['nw-loop', 'Closed loops'], ['nw-entities', 'Entities']] }
  };
  const THEMES = { 'spending-growth': 'Spending growth', outcomes: 'Outcomes', efficiency: 'Efficiency', staffing: 'Staffing', 'budgeting-practice': 'Budgeting practice', measurement: 'Measurement', capital: 'Capital', equity: 'Equity', other: 'Other' };
  const themeLabel = (t) => THEMES[t] || String(t).replace(/-/g, ' ').replace(/^\w/, (c) => c.toUpperCase());
  // Department short names (performance/meta.json › dimensions.dept); the site should read these from site.json.
  const DEPTS = { AAM: 'Asian Art Museum', ADM: 'City Admin', ADP: 'Adult Probation', AIR: 'Airport', ART: 'Arts Commission', ASR: 'Assessor-Recorder', BOS: 'Board of Supervisors', CAT: 'City Attorney', CFC: 'First 5', CHF: 'DCYF', CII: 'Community Investment', CON: 'Controller', CPC: 'Planning', CRT: 'Superior Court', CSS: 'Child Support', DAT: 'District Attorney', DBI: 'Building Inspection', DEC: 'Early Childhood', DEM: 'DEM', DPA: 'Police Accountability', DPH: 'Public Health', DPW: 'Public Works', ECN: 'Economic and Workforce', ENV: 'Environment', ETH: 'Ethics', FAM: 'Fine Arts Museums', FIR: 'Fire', HOM: 'HSH', HRC: 'Human Rights', HRD: 'Human Resources', HSA: 'HSA', HSS: 'Health Service System', JUV: 'Juvenile Probation', LIB: 'Library', MTA: 'SFMTA', MYR: 'Mayor/MOHCD', PDR: 'Public Defender', POL: 'Police', PRT: 'Port', PUC: 'SFPUC', REC: 'Rec and Park', REG: 'Elections', RET: 'Retirement', RNT: 'Rent Board', SCI: 'Academy of Sciences', SHF: 'Sheriff', TIS: 'Technology', TTX: 'Treasurer-Tax Collector', WAR: 'War Memorial', WOM: 'Status of Women' };
  const deptName = (d) => DEPTS[d] || d;
  const EXPLORE_BASE = (document.body.dataset.exploreBase || '../../prototype/index.html');

  // ---------------------------------------------------------------- URL state
  const LIST = ['topic', 'dept'];
  function readState() {
    const q = new URLSearchParams(location.search), s = {};
    LIST.forEach((k) => { s[k] = (q.get(k) || '').split(',').filter(Boolean); });
    s.verdict = q.get('verdict') || ''; s.insight = q.get('insight') || ''; s.evidence = q.get('evidence') || ''; s.data = q.get('data') === '1';
    return s;
  }
  function writeState(s) {
    const q = new URLSearchParams(location.search);
    LIST.forEach((k) => { if (s[k] && s[k].length) q.set(k, s[k].join(',')); else q.delete(k); });
    ['verdict', 'insight', 'evidence'].forEach((k) => { if (s[k]) q.set(k, s[k]); else q.delete(k); });
    if (s.data) q.set('data', '1'); else q.delete('data');
    const qs = q.toString(); history.replaceState(null, '', location.pathname + (qs ? '?' + qs : '') + location.hash);
  }
  function shareUrl(id) { const q = new URLSearchParams(); const t = document.documentElement.getAttribute('data-theme'); if (new URLSearchParams(location.search).get('theme')) q.set('theme', t); q.set('insight', id); return location.origin + location.pathname + '?' + q.toString(); }
  function exploreUrl(ex) { const q = new URLSearchParams(); q.set('view', ex.view); Object.keys(ex.params || {}).forEach((k) => q.set(k, ex.params[k])); const t = document.documentElement.getAttribute('data-theme'); if (t === 'dark') q.set('theme', 'dark'); return EXPLORE_BASE + '?' + q.toString(); }

  // ---------------------------------------------------------------- filtering (every filter applies to everything on the page)
  function applyFilters(data, s) {
    return data.insights.filter((i) => (!s.topic.length || s.topic.includes(i.theme)) && (!s.dept.length || (i.departments || []).some((d) => s.dept.includes(d))) && (!s.verdict || i.robustness.verdict === s.verdict)).sort((a, b) => a.rank - b.rank);
  }

  // ---------------------------------------------------------------- shell
  function renderShell(data) {
    const dash = DASHBOARDS[data.dashboard] || { num: '·', title: data.dashboard, noun: data.dashboard, views: [] };
    const sw = $('#dash-switch'); sw.innerHTML = '';
    [['home', 'Home', '⌂'], ['nonprofits', 'Nonprofit money', 1], ['performance', 'Budget vs outcomes', 2], ['audits', 'Audit tracker', 3], ['network', 'Money network', 4]].forEach(([id, label, num]) => { const b = h('button', 'dash-btn', sw); b.type = 'button'; if (id === data.dashboard) b.setAttribute('aria-current', 'true'); h('span', 'num', b, String(num)); h('span', '', b, label); });
    const nav = $('#nav'); nav.innerHTML = '';
    h('div', 'nav-group-title', nav, dash.title);
    const first = h('a', 'nav-item', nav); first.href = location.pathname; first.setAttribute('aria-current', 'page'); h('span', 'nav-num', first, '★'); h('span', '', first, 'Insights');
    dash.views.forEach(([id, label], i) => { const a = h('a', 'nav-item', nav); a.href = EXPLORE_BASE + '?view=' + id; h('span', 'nav-num', a, String(i + 1)); h('span', '', a, label); });
    $('#asof').textContent = 'Insights as of ' + data.as_of + (data.sample ? ' · sample' : '');
    document.title = `${dash.title}: ${data.insights.length} things the numbers say · SF City Monitor`;
    return dash;
  }

  // ---------------------------------------------------------------- header + summary
  function renderHeader(el, data, dash, shown) {
    el.innerHTML = '';
    const head = h('div', 'view-head ins-head', el);
    const k = h('div', 'kicker', head, `${dash.num} · ${dash.title} · Insights`); if (data.sample) h('span', 'badge badge-sample', k, 'Sample insights');
    h('h1', 'view-title ins-title', head, `${data.insights.length} things the numbers say about ${dash.noun}`);
    h('p', 'view-what ins-intro', head, data.intro);
    const robust = data.insights.filter((i) => i.robustness.verdict === 'robust').length, fragile = data.insights.length - robust;
    const themes = new Set(data.insights.map((i) => i.theme)), depts = new Set(data.insights.flatMap((i) => i.departments || []));
    const sum = h('div', 'ins-summary', head);
    const item = (b, t) => { const s = h('span', 'sum-item', sum); h('b', 'tnum', s, b); s.appendChild(document.createTextNode(' ' + t)); return s; };
    const r = item(String(robust), 'robust'); h('i', 'vdot v-robust', r); r.insertBefore(r.lastChild, r.firstChild);
    const fr = item(String(fragile), 'fragile'); h('i', 'vdot v-fragile', fr); fr.insertBefore(fr.lastChild, fr.firstChild);
    item(String(themes.size), 'themes'); item(String(depts.size), 'departments named');
    const how = h('details', 'howto', head); h('summary', '', how, 'How to read this page'); h('p', '', how, 'Each card makes one claim, shows the one chart that carries it, and says how sturdy it is. Robust means the finding held under every alternative we tried (other deflators, year ranges, definitions); fragile means at least one reasonable alternative weakened or reversed it, and the card says which. "Evidence" opens the numbers with their sources, the checks run, what could make the claim wrong, and caveats. "Explore in the dashboard" opens the full view with the filters already applied.');
    h('p', '', how, 'Unusual is not improper. A pattern here is a reason to ask a question, not an answer to it.');
    void shown;
  }

  // ---------------------------------------------------------------- data strip (kept from every page)
  function renderData(el, data, shown, s, filtersText) {
    el.innerHTML = '';
    const strip = h('div', 'datastrip', el); strip.setAttribute('role', 'region'); strip.setAttribute('aria-label', 'How much data is feeding this page');
    h('span', 'ds-label', strip, 'Data on this page');
    const it1 = h('span', 'ds-item' + (shown.length === 0 ? ' zero' : ''), strip); h('b', '', it1, String(shown.length)); it1.appendChild(document.createTextNode(shown.length === data.insights.length ? ' insights' : ` of ${data.insights.length} insights`));
    const nums = shown.reduce((a, i) => a + i.numbers.length, 0), srcFiles = new Set(shown.flatMap((i) => i.numbers.map((n) => n.source.split('#')[0])));
    const it2 = h('span', 'ds-item', strip); h('b', '', it2, String(nums)); it2.appendChild(document.createTextNode(' cited numbers'));
    const it3 = h('span', 'ds-item', strip); h('b', '', it3, String(srcFiles.size)); it3.appendChild(document.createTextNode(' source files'));
    const it4 = h('span', 'ds-item', strip); h('b', '', it4, '1'); it4.appendChild(document.createTextNode(` file loaded (${(JSON.stringify(data).length / 1024).toFixed(0)} KB)`));
    if (data.sample) h('span', 'badge badge-sample', strip, 'sample');
    const ao = h('span', 'ds-item', strip); ao.appendChild(document.createTextNode('as of ')); h('b', '', ao, data.as_of);
    const tog = h('button', 'link ds-toggle', strip, s.data ? 'Hide details' : 'Details'); tog.type = 'button'; tog.setAttribute('aria-expanded', String(!!s.data)); tog.setAttribute('aria-controls', 'datapanel');
    const panel = h('div', 'datapanel', el); panel.id = 'datapanel'; panel.hidden = !s.data;
    tog.addEventListener('click', () => { s.data = panel.hidden; panel.hidden = !panel.hidden; tog.textContent = panel.hidden ? 'Details' : 'Hide details'; tog.setAttribute('aria-expanded', String(!panel.hidden)); writeState(s); });
    const c1 = h('div', '', panel); h('h3', '', c1, 'Insights for your current filters'); if (filtersText) h('p', 'muted', c1, filtersText).style.margin = '0 0 6px';
    const t1 = h('table', '', c1);
    const byTheme = {}; data.insights.forEach((i) => { byTheme[i.theme] = byTheme[i.theme] || { total: 0, shown: 0 }; byTheme[i.theme].total++; }); shown.forEach((i) => byTheme[i.theme].shown++);
    Object.keys(byTheme).forEach((t) => { const tr = h('tr', '', t1); const td = h('td', '', tr, themeLabel(t)); const bar = h('div', 'bar', td); h('i', '', bar).style.width = (100 * byTheme[t].shown / byTheme[t].total) + '%'; h('td', 'num', tr, `${byTheme[t].shown} / ${byTheme[t].total}`); });
    const c2 = h('div', '', panel); h('h3', '', c2, 'Source files cited by the numbers'); const t2 = h('table', '', c2); const hr = h('tr', '', t2); ['File', 'Numbers'].forEach((x, i) => h('th', i ? 'num' : '', hr, x));
    const counts = {}; shown.forEach((i) => i.numbers.forEach((n) => { const f = n.source.split('#')[0]; counts[f] = (counts[f] || 0) + 1; }));
    Object.keys(counts).sort((a, b) => counts[b] - counts[a]).forEach((f) => { const tr = h('tr', '', t2); const td = h('td', '', tr); h('code', '', td, f); h('td', 'num', tr, String(counts[f])); });
    const c3 = h('div', '', panel); h('h3', '', c3, 'File for this page'); const t3 = h('table', '', c3); const tr = h('tr', '', t3); const td = h('td', '', tr); h('code', '', td, `${data.dashboard}/data/site/insights/insights.json`); if (data.sample) { td.appendChild(document.createTextNode(' ')); h('span', 'badge badge-sample', td, 'sample'); } h('div', 'muted', td, `${data.insights.length} insights · contract design/insights/INSIGHTS_CONTRACT.json`); h('td', 'num', tr, (JSON.stringify(data).length / 1024).toFixed(0) + ' KB');
    h('p', 'muted', c3, 'Every number on this page carries a source path; the module\'s verify script checks each one against the file it names.').style.margin = '8px 0 0';
  }

  // ---------------------------------------------------------------- filter bar
  function renderFilters(el, data, s, onChange) {
    el.innerHTML = '';
    const themes = {}; data.insights.forEach((i) => { themes[i.theme] = (themes[i.theme] || 0) + 1; });
    const f1 = h('div', 'filter', el); h('span', 'filter-label', f1, 'Theme'); const chips = h('div', 'chips', f1);
    Object.keys(themes).forEach((t) => { const c = h('button', 'chip', chips); c.type = 'button'; c.setAttribute('aria-pressed', String(s.topic.includes(t))); c.appendChild(document.createTextNode(themeLabel(t))); h('span', 'chip-n tnum', c, String(themes[t])); c.addEventListener('click', () => { s.topic = s.topic.includes(t) ? s.topic.filter((x) => x !== t) : s.topic.concat(t); onChange(); }); });
    // department popover (multi-select)
    const depts = {}; data.insights.forEach((i) => (i.departments || []).forEach((d) => { depts[d] = (depts[d] || 0) + 1; }));
    const f2 = h('div', 'filter pick', el); const pb = h('button', 'pick-btn' + (s.dept.length ? ' active' : ''), f2); pb.type = 'button'; pb.setAttribute('aria-haspopup', 'listbox'); pb.setAttribute('aria-expanded', 'false');
    pb.textContent = 'Department · ' + (s.dept.length ? s.dept.map(deptName).join(', ') : 'All'); h('span', 'caret', pb, ' ▾');
    const pop = h('div', 'pick-pop', f2); pop.hidden = !s._pickOpen; pb.setAttribute('aria-expanded', String(!!s._pickOpen)); pop.setAttribute('role', 'listbox'); f2.id = 'dept-pick';
    const tools = h('div', 'tools', pop); const clr = h('button', 'link-btn', tools, 'Clear'); clr.type = 'button'; clr.addEventListener('click', () => { s.dept = []; onChange(); });
    h('span', 'muted', tools, `${Object.keys(depts).length} departments are named in an insight`);
    Object.keys(depts).sort((a, b) => deptName(a).localeCompare(deptName(b))).forEach((d) => { const row = h('label', 'row', pop); const cb = h('input', '', row); cb.type = 'checkbox'; cb.checked = s.dept.includes(d); cb.addEventListener('change', () => { s.dept = cb.checked ? s.dept.concat(d) : s.dept.filter((x) => x !== d); s._pickOpen = true; onChange(); const again = document.querySelector('#dept-pick input[type=checkbox]:nth-of-type(1)'); void again; }); row.appendChild(document.createTextNode(`${deptName(d)} `)); h('span', 'muted tnum', row, `${depts[d]}`); });
    pb.addEventListener('click', () => { pop.hidden = !pop.hidden; s._pickOpen = !pop.hidden; pb.setAttribute('aria-expanded', String(!pop.hidden)); });
    const f3 = h('div', 'filter', el); h('span', 'filter-label', f3, 'Verdict'); const vc = h('div', 'chips', f3);
    [['robust', 'Robust'], ['fragile', 'Fragile']].forEach(([v, l]) => { const c = h('button', 'chip', vc); c.type = 'button'; c.setAttribute('aria-pressed', String(s.verdict === v)); h('i', 'vdot v-' + v, c); c.appendChild(document.createTextNode(l)); h('span', 'chip-n tnum', c, String(data.insights.filter((i) => i.robustness.verdict === v).length)); c.addEventListener('click', () => { s.verdict = s.verdict === v ? '' : v; onChange(); }); });
    if (s.topic.length || s.dept.length || s.verdict) { const r = h('button', 'link-btn reset', el, 'Reset filters'); r.type = 'button'; r.addEventListener('click', () => { s.topic = []; s.dept = []; s.verdict = ''; onChange(); }); }
    const na = h('span', 'filter-na', el); na.innerHTML = 'Not on this page: <b>Fiscal years</b>, <b>Dollars</b> (each insight fixes its own years and dollar basis; see its chart subtitle)';
  }
  function filtersText(s) { const parts = []; if (s.topic.length) parts.push('theme ' + s.topic.map(themeLabel).join(', ')); if (s.dept.length) parts.push('department ' + s.dept.map(deptName).join(', ')); if (s.verdict) parts.push(s.verdict + ' only'); return parts.length ? 'Filters: ' + parts.join(' · ') : 'No filters: all insights shown.'; }

  // ---------------------------------------------------------------- glance list
  function renderGlance(el, shown, total) {
    el.innerHTML = '';
    if (!shown.length) return;
    const box = h('section', 'glance', el); box.setAttribute('aria-labelledby', 'glance-title');
    const top = h('div', 'glance-top', box); h('h2', 'section-title', top, 'Read in 30 seconds').id = 'glance-title'; h('span', 'glance-sub', top, shown.length === total ? `All ${total}, in rank order. Click a claim to jump to its chart and evidence.` : `${shown.length} of ${total} match your filters. Click a claim to jump to it.`);
    const ol = h('ol', 'glance-list', box);
    shown.forEach((i) => { const li = h('li', 'glance-item', ol); const a = h('a', 'glance-link', li); a.href = '#' + i.id; a.addEventListener('click', (e) => { e.preventDefault(); openInsight(i.id, false); }); h('span', 'glance-rank tnum', a, String(i.rank)); const t = h('span', 'glance-text', a, i.title); h('span', 'glance-meta', li).append(verdictBadge(i.robustness.verdict, true), h('span', 'glance-theme', null, themeLabel(i.theme))); void t; });
  }
  function verdictBadge(v, small) { const b = h('span', 'verdict v-' + v + (small ? ' small' : '')); h('i', 'vdot v-' + v, b); b.appendChild(document.createTextNode(v === 'robust' ? 'Robust' : 'Fragile')); b.title = v === 'robust' ? 'Held under every alternative tried' : 'At least one reasonable alternative weakened it; see Evidence'; return b; }

  // ---------------------------------------------------------------- cards
  let twins = {};
  function renderCards(el, shown, s) {
    el.innerHTML = ''; twins = {};
    if (!shown.length) { const e = h('div', 'card empty ins-empty', el); h('b', '', e, 'No insights match these filters'); e.appendChild(document.createTextNode('Pick another theme or department, or ')); const r = h('button', 'link', e, 'reset the filters'); r.type = 'button'; r.addEventListener('click', () => { s.topic = []; s.dept = []; s.verdict = ''; update(); }); e.appendChild(document.createTextNode('.')); return; }
    const grid = h('div', 'ins-grid', el);
    shown.forEach((i) => grid.appendChild(card(i, s)));
  }
  function card(i, s) {
    const art = h('article', 'card ins-card'); art.id = i.id; art.tabIndex = -1; art.dataset.rank = i.rank; art.setAttribute('aria-labelledby', i.id + '-title');
    const head = h('header', 'ins-card-head', art);
    h('span', 'ins-rank tnum', head, String(i.rank));
    const meta = h('div', 'ins-meta', head); h('span', 'tag tag-theme', meta, themeLabel(i.theme)); meta.appendChild(verdictBadge(i.robustness.verdict));
    (i.departments || []).forEach((d) => { const a = h('a', 'ins-dept', meta, deptName(d)); a.href = EXPLORE_BASE + '?view=dept&id=' + d; a.title = 'Open the ' + deptName(d) + ' scorecard'; });
    const share = h('button', 'icon-btn share-btn', head, 'Share'); share.type = 'button'; share.title = 'Copy a link to this insight (c)'; share.addEventListener('click', () => copyShare(i.id, share));
    h('h2', 'ins-claim', art, i.title).id = i.id + '-title';
    h('p', 'ins-dek', art, i.dek);
    // chart
    const ch = h('figure', 'ins-chart', art);
    const chHead = h('div', 'card-head', ch); const tt = h('div', 'card-titles', chHead); h('h3', 'card-title', tt, i.chart.title); h('p', 'card-sub', tt, i.chart.subtitle);
    const ctl = h('div', 'card-controls', chHead); const tb = h('button', 'tbl-btn', ctl, 'Table'); tb.type = 'button'; tb.setAttribute('aria-pressed', 'false'); tb.title = 'Show the chart as a table (t)';
    const body = h('div', 'card-body ins-plot', ch); body.dataset.chart = i.id;
    const twinEl = h('div', 'ins-twin', ch); twinEl.hidden = true;
    tb.addEventListener('click', () => { const on = twinEl.hidden; twinEl.hidden = !on; body.hidden = on; tb.setAttribute('aria-pressed', String(on)); if (on && twins[i.id]) C.renderTwin(twinEl, twins[i.id]); });
    if (i.chart.note) h('figcaption', 'ins-note', ch, i.chart.note);
    // why + surprise
    const why = h('div', 'ins-why', art); h('span', 'ins-label', why, 'Why it matters'); h('p', '', why, i.why_it_matters);
    if (i.surprise) { const sp = h('div', 'ins-surprise', art); h('span', 'ins-label', sp, 'The surprise'); h('p', '', sp, i.surprise); }
    // actions
    const act = h('div', 'ins-actions', art);
    const ev = h('button', 'icon-btn ev-btn', act, 'Evidence'); ev.type = 'button'; ev.setAttribute('aria-expanded', 'false'); ev.setAttribute('aria-controls', i.id + '-evidence'); ev.title = 'Numbers, sources, checks and caveats (e)';
    const cnt = h('span', 'ev-count tnum', ev, `${i.numbers.length} numbers · ${i.robustness.checks.length} checks`);
    void cnt;
    const ex = h('a', 'explore-link', act, (i.explore.label || 'Explore in the dashboard') + ' →'); ex.href = exploreUrl(i.explore); ex.title = `Opens ${i.explore.view} with ${Object.keys(i.explore.params || {}).length ? 'filters ' + JSON.stringify(i.explore.params) : 'no filters'} (o)`;
    // evidence
    const evd = h('section', 'ins-evidence', art); evd.id = i.id + '-evidence'; evd.hidden = true; evd.setAttribute('aria-label', 'Evidence');
    const g = h('div', 'ev-grid', evd);
    const n = h('div', 'ev-col', g); h('h4', 'ev-title', n, 'The numbers');
    const nl = h('ol', 'ev-numbers', n); i.numbers.forEach((x) => { const li = h('li', 'ev-num', nl); h('span', 'ev-nvalue tnum', li, x.value); h('span', 'ev-nlabel', li, x.label); const src = h('span', 'ev-nsrc', li); src.appendChild(document.createTextNode('Source: ')); h('code', '', src, x.source); });
    const r = h('div', 'ev-col', g); const rt = h('h4', 'ev-title', r, 'Robustness '); rt.appendChild(verdictBadge(i.robustness.verdict, true));
    const ul = h('ul', 'ev-checks', r); i.robustness.checks.forEach((c) => { const li = h('li', /^(did not|does not|sign flip|fail|not held|reversed)/i.test(c) ? 'failed' : 'held', ul, c); void li; });
    h('h4', 'ev-title', r, 'What could make it wrong'); h('p', 'ev-wrong', r, i.robustness.what_could_make_it_wrong);
    if (i.caveats && i.caveats.length) { const cv = h('div', 'ev-col ev-caveats', g); h('h4', 'ev-title', cv, 'Caveats'); const cl = h('ul', '', cv); i.caveats.forEach((c) => h('li', '', cl, c)); }
    const foot = h('div', 'ev-foot', evd); if (i.tags && i.tags.length) { h('span', 'ev-tags', foot, 'Tags: ' + i.tags.join(', ')); } const perma = h('a', 'link', foot, 'Link to this insight'); perma.href = shareUrl(i.id);
    ev.addEventListener('click', () => toggleEvidence(art, evd.hidden));
    return art;
  }
  function toggleEvidence(art, open) { const evd = $('.ins-evidence', art), btn = $('.ev-btn', art); evd.hidden = !open; btn.setAttribute('aria-expanded', String(open)); art.classList.toggle('open', open); }
  function copyShare(id, btn) {
    const url = shareUrl(id); const done = () => { const t = btn.textContent; btn.textContent = 'Link copied'; btn.classList.add('ok'); setTimeout(() => { btn.textContent = t; btn.classList.remove('ok'); }, 1600); };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(done, () => window.prompt('Copy this link', url)); else window.prompt('Copy this link', url);
  }
  function renderCharts(root) {
    root.querySelectorAll('.ins-plot').forEach((el) => { const i = byId[el.dataset.chart]; if (!i) return; const tw = C.render(el, i.chart, { height: i.chart.type === 'scatter' ? 260 : i.chart.type === 'stacked' ? 230 : 220 }); if (tw) { twins[i.id] = tw; const twinEl = el.parentElement.querySelector('.ins-twin'); if (!twinEl.hidden) C.renderTwin(twinEl, tw); } });
  }
  function openInsight(id, expand) {
    const art = document.getElementById(id); if (!art) return;
    document.querySelectorAll('.ins-card.current').forEach((c) => c.classList.remove('current'));
    art.classList.add('current');
    if (expand) toggleEvidence(art, true);
    if (new URLSearchParams(location.search).get('shot') === '1') { // QA only: headless Chrome does not paint scrolled content, so show just this card and the next one at the top
      document.body.classList.add('shot'); document.querySelectorAll('.ins-card.next').forEach((c) => c.classList.remove('next')); if (art.nextElementSibling) art.nextElementSibling.classList.add('next');
    } else art.scrollIntoView({ block: 'start', behavior: 'auto' });
    art.focus({ preventScroll: true });
    state.insight = id; writeState(state);
  }

  // ---------------------------------------------------------------- closing note
  function renderFoot(el, data) {
    el.innerHTML = '';
    const box = h('aside', 'caveats ins-foot', el); h('h2', 'section-title', box, 'Reading these insights');
    const ul = h('ul', '', box);
    [['high', 'Robust is not proven. It means the finding survived the alternatives listed under Evidence; a check we did not think of could still move it.'], ['medium', 'Fragile is not wrong. It means a reasonable alternative changed the picture; the card names it so you can judge.'], ['low', `Ranking is editorial: how much a finding should change what a careful reader believes, given how sturdy it is. Rank ${data.insights.length} is still worth a look.`]].forEach(([sev, t]) => { const li = h('li', 'caveat sev-' + sev, ul); h('span', 'sev', li, sev === 'high' ? 'Could move the finding' : sev === 'medium' ? 'Worth knowing' : 'Minor'); li.appendChild(document.createTextNode(' ' + t)); });
    const fair = h('div', 'fair', el); fair.innerHTML = '<b>Unusual is not improper.</b> Every pattern on this page is a reason to ask a question, not a finding about anyone\'s conduct. Organizations and officials are named only in public roles; nobody below executive level is named.';
  }

  // ---------------------------------------------------------------- keyboard
  function currentCard() { return document.querySelector('.ins-card.current') || document.querySelector('.ins-card:focus-within') || null; }
  function moveCard(dir) {
    const cards = [...document.querySelectorAll('.ins-card')]; if (!cards.length) return;
    const cur = currentCard(); let idx = cur ? cards.indexOf(cur) + dir : (dir > 0 ? 0 : cards.length - 1);
    idx = Math.max(0, Math.min(cards.length - 1, idx)); openInsight(cards[idx].id, false);
  }
  function keys(e) {
    if (e.target.matches('input, textarea, select') || e.metaKey || e.ctrlKey || e.altKey) return;
    const cur = currentCard();
    switch (e.key) {
      case 'j': case 'ArrowDown': if (e.key === 'ArrowDown' && !cur) return; e.preventDefault(); moveCard(1); break;
      case 'k': case 'ArrowUp': if (e.key === 'ArrowUp' && !cur) return; e.preventDefault(); moveCard(-1); break;
      case 'e': case 'Enter': if (!cur || (e.key === 'Enter' && e.target !== cur)) return; e.preventDefault(); toggleEvidence(cur, $('.ins-evidence', cur).hidden); break;
      case 'o': if (!cur) return; e.preventDefault(); $('.explore-link', cur).click(); break;
      case 'c': if (!cur) return; e.preventDefault(); copyShare(cur.id, $('.share-btn', cur)); break;
      case 't': if (!cur) return; e.preventDefault(); $('.tbl-btn', cur).click(); break;
      case 'd': e.preventDefault(); toggleTheme(); break;
      case '?': e.preventDefault(); $('#help').hidden = !$('#help').hidden; break;
      case 'Escape': $('#help').hidden = true; if (cur) { cur.classList.remove('current'); state.insight = ''; writeState(state); } break;
      default: return;
    }
  }
  function toggleTheme() { const dark = document.documentElement.getAttribute('data-theme') !== 'dark'; document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light'); try { localStorage.setItem('sfcm-theme', dark ? 'dark' : 'light'); } catch (err) { /* ignore */ } $('#theme-toggle').setAttribute('aria-pressed', String(dark)); document.querySelectorAll('.explore-link').forEach((a) => { const i = byId[a.closest('.ins-card').id]; a.href = exploreUrl(i.explore); }); }

  // ---------------------------------------------------------------- boot
  let data, state, byId = {};
  function update() {
    writeState(state);
    const shown = applyFilters(data, state);
    renderFilters($('#filterbar'), data, state, update);
    renderData($('#ins-data'), data, shown, state, filtersText(state));
    renderGlance($('#ins-glance'), shown, data.insights.length);
    renderCards($('#ins-cards'), shown, state);
    renderCharts($('#ins-cards'));
    if (state.evidence === 'all') document.querySelectorAll('.ins-card').forEach((c) => toggleEvidence(c, true));
  }
  function boot(d) {
    data = d; state = readState(); d.insights.forEach((i) => { byId[i.id] = i; });
    const dash = renderShell(d);
    renderHeader($('#ins-header'), d, dash);
    update();
    renderFoot($('#ins-foot'), d);
    if (state.insight) requestAnimationFrame(() => openInsight(state.insight, true));
    document.addEventListener('keydown', keys);
    document.addEventListener('click', (e) => { const pick = document.getElementById('dept-pick'); if (pick && !pick.contains(e.target)) { const pop = pick.querySelector('.pick-pop'), pb = pick.querySelector('.pick-btn'); pop.hidden = true; state._pickOpen = false; pb.setAttribute('aria-expanded', 'false'); } });
    $('#theme-toggle').addEventListener('click', toggleTheme); $('#theme-toggle').setAttribute('aria-pressed', String(document.documentElement.getAttribute('data-theme') === 'dark'));
    $('#share-btn').addEventListener('click', () => { const b = $('#share-btn'); if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(location.href).then(() => { b.textContent = 'Copied'; setTimeout(() => { b.textContent = 'Copy link'; }, 1600); }, () => window.prompt('Copy this link', location.href)); else window.prompt('Copy this link', location.href); });
    $('#print-btn').addEventListener('click', () => { document.querySelectorAll('.ins-card').forEach((c) => toggleEvidence(c, true)); setTimeout(() => window.print(), 50); });
    $('#help-close').addEventListener('click', () => { $('#help').hidden = true; });
    let rt; window.addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => renderCharts($('#ins-cards')), 120); });
    window.addEventListener('beforeprint', () => document.querySelectorAll('.ins-card').forEach((c) => toggleEvidence(c, true)));
  }
  function load() {
    // Production: fetch(`${module}/data/site/insights/insights.json`). On file:// (and in this prototype) use the sample script.
    const q = new URLSearchParams(location.search), src = q.get('src');
    if (src && location.protocol !== 'file:') { fetch(src).then((r) => r.json()).then(boot).catch((e) => { $('#ins-header').innerHTML = `<div class="card empty"><b>Could not load data</b>${src}</div>`; console.error(e); }); return; }
    if (window.SFCM_INSIGHTS_SAMPLE) boot(window.SFCM_INSIGHTS_SAMPLE); else $('#ins-header').innerHTML = '<div class="card empty"><b>Could not load data</b>sample-data/insights.sample.js</div>';
  }
  M.insights = { boot, load, openInsight, DASHBOARDS, THEMES };
  document.addEventListener('DOMContentLoaded', load);
})();
