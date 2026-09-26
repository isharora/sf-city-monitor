/* app.js - shell: dashboards, navigation, the filter bar (renders ONLY the filters a view applies
   and names the others), card helper with table twin, per-dashboard sample banner, "analysis not
   available yet" states, the data-transparency strip, story mode, search, theme and keyboard. */
(function () {
  const M = window.SFCM;
  const { h } = M.charts;
  const S = M.state;
  const fmt = M.stats.fmt;

  // ---------------------------------------------------------------- dashboards
  M.dashes = {
    np: { id: 'np', num: 1, module: 'nonprofits', title: 'Follow the nonprofit money', short: 'Nonprofit money', what: 'City payments and contracts to nonprofits, linked to their IRS 990 finances and the Controller’s monitoring results.', story: 'nonprofits/commentary/story_np.json', yearsKey: 'fiscal_years', yearsLabel: 'Fiscal years', filterKeys: ['years', 'dept', 'area', 'size', 'real'], views: ['np-overview', 'np-flows', 'np-dependency', 'np-pay', 'np-growth', 'np-reviews', 'np-orgs'] },
    pf: { id: 'pf', num: 2, module: 'performance', title: 'Budget vs outcomes', short: 'Budget vs outcomes', what: 'What each department spends, in real dollars and per resident, and what it gets for it.', story: 'performance/commentary/story_pf.json', yearsKey: 'fiscal_years', yearsLabel: 'Fiscal years', filterKeys: ['years', 'group', 'dept', 'real'], views: ['pf-overview', 'pf-spending', 'pf-staffing', 'pf-outcomes', 'pf-cost', 'pf-integrity', 'pf-gaps', 'pf-depts'] },
    au: { id: 'au', num: 3, module: 'audits', title: 'Audit recommendations tracker', short: 'Audit tracker', what: 'Every recommendation from the Controller’s auditors, the Budget and Legislative Analyst and the Civil Grand Jury, and what happened to it.', story: 'audits/commentary/story_au.json', yearsKey: 'years', yearsLabel: 'Years issued', filterKeys: ['years', 'source', 'dept', 'topic'], views: ['au-overview', 'au-status', 'au-time', 'au-agreement', 'au-repeat', 'au-open', 'au-reports'] },
    nw: { id: 'nw', num: 4, module: 'network', title: 'Money network', short: 'Money network', what: 'How money moves between donors, officials, lobbyists and the organizations that get city contracts and approvals.', story: 'network/commentary/story_nw.json', yearsKey: 'years', yearsLabel: 'Years', filterKeys: ['years', 'flow', 'etype', 'amt'], views: ['nw-overview', 'nw-graph', 'nw-ban', 'nw-behested', 'nw-lobby', 'nw-concentration', 'nw-loop', 'nw-entities'] },
  };
  const DASH_BY_MODULE = { nonprofits: 'np', performance: 'pf', audits: 'au', network: 'nw' };
  const FILTER_LABELS = { years: 'Years', dept: 'Department', area: 'Service area', size: 'Size', group: 'Department group', real: 'Dollars', source: 'Recommended by', topic: 'Topic', flow: 'Flow type', etype: 'Entity type', amt: 'Minimum amount' };
  let METAS = {}, STORIES = {}, SITE = { departments: [], groups: [], modules: {} };

  // ---------------------------------------------------------------- colours (slot-based: colour follows the entity)
  M.colors = {
    /** Colour for a categorical dimension value: its fixed slot (1..8), else its position. */
    slot(dim, id) { const vals = (dim && dim.values) || []; const i = vals.findIndex((v) => v.id === id); if (i < 0) return 'var(--neutral)'; const s = vals[i].slot != null ? vals[i].slot : i + 1; return s >= 1 && s <= 8 ? `var(--series-${s})` : 'var(--neutral)'; },
  };

  // ---------------------------------------------------------------- theme
  function applyTheme(pref) { const dark = pref === 'dark' || (pref === 'auto' && matchMedia('(prefers-color-scheme: dark)').matches); document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light'); document.getElementById('theme-toggle').setAttribute('aria-pressed', String(dark)); try { if (pref !== 'auto') localStorage.setItem('sfcm-theme', pref); } catch (e) { /* ignore */ } }
  document.getElementById('theme-toggle').addEventListener('click', () => S.set({ theme: document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark' }));
  document.getElementById('share-btn').addEventListener('click', async (e) => { const b = e.currentTarget; try { await navigator.clipboard.writeText(location.href); b.textContent = 'Link copied'; } catch (err) { b.textContent = 'Copy the address bar'; } setTimeout(() => (b.textContent = 'Copy link'), 1600); });
  document.getElementById('story-btn').addEventListener('click', () => { const st = S.get(); if (st.mode === 'story') S.set({ mode: 'explore' }); else { const d = dashOf(st.view); if (d) enterStory(d.id, 0); } });

  function dashOf(viewId) { const v = M.views[viewId]; return v && M.dashes[v.dash] ? M.dashes[v.dash] : null; }
  function modSource(dashId) { const me = M.data.manifest && M.data.manifest.modules[dashId]; return me ? me.source : 'sample'; }
  function modReason(dashId) { const me = M.data.manifest && M.data.manifest.modules[dashId]; return me ? me.reason : 'no data manifest (run tools/bundle.py)'; }

  // ---------------------------------------------------------------- nav
  function navBtn(parent, cls, num, label, current, onClick) { const b = h('button', cls, parent); b.type = 'button'; h('span', cls === 'dash-btn' ? 'num' : 'nav-num', b, num); h('span', '', b, label); if (current) b.setAttribute('aria-current', cls === 'dash-btn' ? 'true' : 'page'); b.addEventListener('click', onClick); return b; }
  function renderNav() {
    const st = S.get(), cur = dashOf(st.view);
    const sw = document.getElementById('dash-switch'); sw.innerHTML = '';
    navBtn(sw, 'dash-btn', '⌂', 'Home', st.view === 'home', () => S.set({ view: 'home', id: null, mode: 'explore' }));
    Object.values(M.dashes).forEach((d) => { const b = navBtn(sw, 'dash-btn', String(d.num), d.short, cur && cur.id === d.id, () => S.set({ view: d.views[0], id: null, mode: 'explore' })); if (modSource(d.id) === 'sample') { const t = h('span', 'nav-sample', b, 'sample'); t.title = 'This dashboard shows synthetic sample data'; } });
    const nav = document.getElementById('nav'); nav.innerHTML = '';
    if (cur) {
      h('div', 'nav-group-title', nav, cur.title);
      cur.views.forEach((id, i) => { const v = M.views[id]; navBtn(nav, 'nav-item', String(i + 1), v.nav || v.title, st.view === id, () => S.set({ view: id, id: null })); });
    } else {
      h('div', 'nav-group-title', nav, 'Site');
      [['home', 'Landing page'], ['search', 'Search'], ['methods', 'Methods and data']].forEach(([id, label]) => navBtn(nav, 'nav-item', '·', label, st.view === id, () => S.set({ view: id })));
      if (['org', 'dept', 'report', 'official'].includes(st.view)) navBtn(nav, 'nav-item', '·', { org: 'Organization profile', dept: 'Department scorecard', report: 'Report page', official: 'Official profile' }[st.view], true, () => {});
    }
    const sb = document.getElementById('story-btn'); sb.hidden = !cur || !STORIES[cur.id]; sb.setAttribute('aria-pressed', String(st.mode === 'story'));
  }
  function renderSampleNotice() {
    const sample = Object.values(M.dashes).filter((d) => modSource(d.id) === 'sample');
    const note = document.getElementById('sample-note'), badge = document.getElementById('brand-badge');
    note.innerHTML = ''; badge.innerHTML = '';
    if (!sample.length) { note.hidden = true; badge.hidden = true; return; }
    note.hidden = false; badge.hidden = false;
    if (sample.length === 4) { note.appendChild(document.createTextNode('All four dashboards show ')); h('b', '', note, 'synthetic sample data'); note.appendChild(document.createTextNode(' until the modules publish their exports; names are invented.')); h('span', 'badge badge-sample', badge, 'Synthetic sample data'); return; }
    h('b', '', note, 'Sample data'); note.appendChild(document.createTextNode(` in ${fmt.list(sample.map((d) => d.short))}; the other dashboards use the published exports.`));
    h('span', 'badge badge-sample', badge, `Sample data in ${sample.length} of 4 dashboards`);
  }

  // ---------------------------------------------------------------- filter bar
  let closePops = [];
  document.addEventListener('click', (e) => closePops.forEach((f) => f(e)));
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closePops.forEach((f) => f(null)); });
  /** Multi-select popover. */
  function multiPick(parent, label, options, selected, onChange) {
    const wrap = h('div', 'pick', parent);
    const btn = h('button', 'pick-btn' + (selected.length ? ' active' : ''), wrap); btn.type = 'button'; btn.setAttribute('aria-haspopup', 'listbox'); btn.setAttribute('aria-expanded', 'false');
    btn.textContent = selected.length ? `${label} · ${selected.length === 1 ? (options.find((o) => o.id === selected[0]) || {}).label || selected[0] : selected.length + ' selected'}` : `${label} · All`;
    h('span', '', btn, ' ▾');
    const pop = h('div', 'pick-pop', wrap); pop.hidden = true; pop.setAttribute('role', 'listbox'); pop.setAttribute('aria-label', label); pop.setAttribute('aria-multiselectable', 'true');
    const tools = h('div', 'tools', pop);
    const all = h('button', 'link', tools, 'All'); all.type = 'button'; all.addEventListener('click', () => onChange([]));
    const set = new Set(selected);
    options.forEach((o) => { const row = h('label', 'row', pop); const cb = h('input', '', row); cb.type = 'checkbox'; cb.checked = set.has(o.id); if (o.color) { const d = h('span', 'dot', row); d.style.background = o.color; } h('span', '', row, o.label); cb.addEventListener('change', () => { const s2 = new Set(set); cb.checked ? s2.add(o.id) : s2.delete(o.id); onChange([...s2]); }); });
    btn.addEventListener('click', () => { pop.hidden = !pop.hidden; btn.setAttribute('aria-expanded', String(!pop.hidden)); if (!pop.hidden) { const first = pop.querySelector('input'); if (first) first.focus(); } });
    closePops.push((e) => { if (!e || !wrap.contains(e.target)) { if (!pop.hidden && !e) btn.focus(); pop.hidden = true; btn.setAttribute('aria-expanded', 'false'); } });
    return wrap;
  }
  function renderFilters() {
    const st = S.get(), view = M.views[st.view], dash = dashOf(st.view);
    const bar = document.getElementById('filterbar'); bar.innerHTML = ''; closePops = [];
    const meta = dash ? METAS[dash.id] : null;
    if (!dash || !meta || !view.filters || !view.filters.length) {
      bar.hidden = !(view && view.filterNote);
      if (view && view.filterNote) h('span', 'filter-na', bar, view.filterNote);
      return;
    }
    bar.hidden = false;
    const dims = meta.dimensions || {};
    const bounds = meta[dash.yearsKey];
    for (const key of view.filters) {
      const f = h('div', 'filter', bar); f.dataset.filter = key;
      if (key === 'years') {
        h('span', 'filter-label', f, dash.yearsLabel); const rng = h('div', 'range', f); const yrs = S.years(st, bounds);
        const mk = (val, which, onch) => { const s = h('select', '', rng); s.setAttribute('aria-label', `${dash.yearsLabel}, ${which}`); for (let y = bounds.min; y <= bounds.max; y++) { const o = h('option', '', s, (dash.yearsKey === 'fiscal_years' ? 'FY' : '') + y); o.value = y; if (y === val) o.selected = true; } s.addEventListener('change', () => onch(+s.value)); };
        mk(yrs[0], 'from', (y) => S.set({ years: [y, Math.max(y, yrs[1])] })); h('span', '', rng, '–'); mk(yrs[1], 'to', (y) => S.set({ years: [Math.min(y, yrs[0]), y] }));
      } else if (key === 'real') {
        h('span', 'filter-label', f, 'Dollars'); const seg = h('div', 'seg', f); seg.setAttribute('role', 'group'); seg.setAttribute('aria-label', 'Dollars');
        const a = h('button', '', seg, `Real (FY${meta.deflator.base_fy})`); a.type = 'button'; a.setAttribute('aria-pressed', String(st.real)); a.addEventListener('click', () => S.set({ real: true }));
        const b = h('button', '', seg, 'Nominal'); b.type = 'button'; b.setAttribute('aria-pressed', String(!st.real)); b.addEventListener('click', () => S.set({ real: false }));
      } else if (key === 'amt') {
        h('span', 'filter-label', f, 'Min amount'); const s = h('select', 'ctl', f); s.setAttribute('aria-label', 'Minimum amount'); (dims.amount_bands || [{ id: 0, label: 'Any amount' }]).forEach((b) => { const o = h('option', '', s, b.label); o.value = b.id; if (+st.amt === +b.id) o.selected = true; }); s.addEventListener('change', () => S.set({ amt: +s.value }));
      } else if (key === 'area' || key === 'size' || key === 'source' || key === 'flow') {
        const dim = dims[key === 'size' ? 'size_band' : key] || { label: FILTER_LABELS[key], values: [] }; h('span', 'filter-label', f, (dim.label || FILTER_LABELS[key]).replace(/ \(.*\)/, '')); const cs = h('div', 'chips', f); cs.setAttribute('role', 'group'); cs.setAttribute('aria-label', dim.label || FILTER_LABELS[key]);
        dim.values.forEach((o) => { const c = h('button', 'chip', cs); c.type = 'button'; if (o.slot != null && key !== 'flow') { const d = h('span', 'dot', c); d.style.background = M.colors.slot(dim, o.id); } h('span', '', c, o.short || o.label); c.title = o.label; c.setAttribute('aria-pressed', String(st[key].includes(o.id))); c.addEventListener('click', () => { const set = new Set(st[key]); set.has(o.id) ? set.delete(o.id) : set.add(o.id); S.set({ [key]: [...set] }); }); });
      } else if (key === 'dept' || key === 'group' || key === 'topic' || key === 'etype') {
        const dim = dims[key] || { label: FILTER_LABELS[key], values: [] };
        multiPick(f, dim.label || FILTER_LABELS[key], dim.values.map((o) => ({ id: o.id, label: o.name || o.label || o.id, color: key === 'etype' ? `var(--c-${o.id}, var(--neutral))` : null })), st[key], (vals) => S.set({ [key]: vals }));
      }
    }
    if (S.filtersActive(st, view.filters)) { const r = h('button', 'link-btn', bar, 'Reset filters'); r.type = 'button'; r.addEventListener('click', () => S.resetFilters(view.filters)); }
    const absent = dash.filterKeys.filter((k) => !view.filters.includes(k));
    if (absent.length) { const na = h('span', 'filter-na', bar); na.dataset.absent = absent.join(','); na.appendChild(document.createTextNode('Not on this view: ')); absent.forEach((k, i) => { h('b', '', na, FILTER_LABELS[k]); na.appendChild(document.createTextNode((view.absent && view.absent[k] ? ` (${view.absent[k]})` : '') + (i < absent.length - 1 ? '; ' : ''))); }); }
  }

  // ---------------------------------------------------------------- card helper
  let cardSeq = 0;
  function card(parent, opts) {
    const c = h('section', 'card col-' + (opts.span || 12), parent);
    const tid = 'c-' + (++cardSeq);
    c.setAttribute('aria-labelledby', tid);
    const head = h('div', 'card-head', c), titles = h('div', 'card-titles', head);
    const t = h('h2', 'card-title', titles, opts.title); t.id = tid;
    if (opts.sub) h('p', 'card-sub', titles, opts.sub);
    const ctl = h('div', 'card-controls', head);
    (opts.controls || []).forEach((k) => { const sel = h('select', '', ctl); sel.setAttribute('aria-label', k.label); sel.title = k.label; k.options.forEach(([v, l]) => { const o = h('option', '', sel, l); o.value = v; if (String(k.value) === String(v)) o.selected = true; }); sel.addEventListener('change', () => k.onChange(sel.value)); });
    const body = h('div', 'card-body', c);
    let tableMode = false, spec = null;
    const tb = h('button', 'tbl-btn', ctl, 'Table'); tb.type = 'button'; tb.setAttribute('aria-pressed', 'false'); tb.title = 'Show the same data as a table';
    const draw = () => {
      body.innerHTML = '';
      try {
        if (tableMode && spec) renderTable(body, spec);
        else { const r = opts.render(body); spec = r && r.head ? r : r === null ? null : spec; }
        tb.hidden = !(spec && spec.head && spec.head.length && !opts.noTwin);
      } catch (err) { console.error('render failed:', opts.title, err); body.innerHTML = ''; empty(body, 'Chart failed to render', 'This card could not be drawn with the current data; the rest of the view is unaffected.'); tb.hidden = true; M.app.errors.push(`${opts.title}: ${err.message}`); }
    };
    tb.addEventListener('click', () => { tableMode = !tableMode; tb.setAttribute('aria-pressed', String(tableMode)); tb.textContent = tableMode ? 'Chart' : 'Table'; draw(); });
    draw();
    if (opts.note) h('p', 'note', c, opts.note);
    if (opts.caveat) { const cv = h('p', 'caveat-inline', c); h('b', '', cv, 'Why this might be wrong: '); cv.appendChild(document.createTextNode(opts.caveat)); }
    if (opts.foot) { const f = h('div', 'card-foot', c); (Array.isArray(opts.foot) ? opts.foot : [opts.foot]).forEach((x) => h('span', 'tnum', f, x)); }
    return c;
  }
  function renderTable(el, spec) { const wrap = h('div', 'table-wrap', el); const t = h('table', 'data-table', wrap); const cap = h('caption', 'sr-only', t, 'Table version of the chart'); cap.id = ''; const tr = h('tr', '', h('thead', '', t)); spec.head.forEach((x) => { const th = h('th', '', tr, x); th.scope = 'col'; }); const tb = h('tbody', '', t); spec.rows.forEach((r) => { const row = h('tr', '', tb); r.forEach((x) => h('td', '', row, x == null ? '–' : String(x))); }); }
  function empty(el, title, txt) { const e = h('div', 'empty', el); h('b', '', e, title); if (txt) e.appendChild(document.createTextNode(txt)); return e; }

  /** "Analysis not available yet" block for missing/invalid files. */
  function unavailable(el, errs, opts) {
    const box = h('div', 'unavailable' + (opts && opts.compact ? ' compact' : ''), el);
    h('b', '', box, (opts && opts.title) || 'Analysis not available yet');
    h('p', '', box, (opts && opts.text) || 'This view needs data that the module has not published in a usable form yet, so it is left blank rather than filled with partial or sample numbers.');
    const ul = h('ul', '', box);
    errs.forEach((e) => { const li = h('li', '', ul); h('code', '', li, e.logical); li.appendChild(document.createTextNode(` · ${e.status === 'missing' ? 'not in the export' : e.status === 'invalid' ? 'fails the data contract' : 'could not be loaded'}`)); (e.errors || []).slice(0, 3).forEach((x) => h('div', 'muted', li, x)); });
    h('p', 'muted', box, 'Rebuild with python3 site/tools/bundle.py once the export is fixed; its report lists every missing file and field.');
    return box;
  }

  function sampleBanner(el, dash) {
    const b = h('div', 'sample-banner', el); b.setAttribute('role', 'note');
    h('b', '', b, 'Sample data');
    b.appendChild(document.createTextNode(` The ${dash.short.toLowerCase()} module has not published its export yet (${modReason(dash.id)}). Every number, organization and official on this dashboard is synthetic, generated for design review; it describes no real entity.`));
    return b;
  }

  // ---------------------------------------------------------------- render view
  let renderToken = 0, lastWidth = 0;
  M.app = { errors: [], rendered: Promise.resolve() };
  function commentaryPath(view, dash) { return dash ? `${dash.module}/commentary/${view.id}.json` : `site/commentary/${view.id}.json`; }

  async function renderView() {
    const st = S.get();
    const view = M.views[st.view] || M.views.home;
    const dash = dashOf(view.id);
    const content = document.getElementById('content');
    document.title = `${view.title} · SF City Monitor`;
    renderNav(); renderFilters();
    const token = ++renderToken;
    content.classList.add('loading');
    content.setAttribute('aria-busy', 'true');
    const meta = dash ? METAS[dash.id] : null;
    const files = typeof view.files === 'function' ? view.files(st) : Object.assign({}, view.files || {});
    let data, missing = [];
    try {
      if (dash && !meta) throw Object.assign(new M.data.DataError(`${dash.module}/meta.json`, M.data.status(`${dash.module}/meta.json`), (M.data.entry(`${dash.module}/meta.json`) || {}).errors), {});
      const optKeys = view.optional ? Object.keys(files) : view.optionalFiles || [];
      const req = {}, opt = {}; for (const k in files) (optKeys.includes(k) ? opt : req)[k] = files[k];
      const [a, b] = await Promise.all([M.data.loadAll(req), M.data.loadAll(opt, { optional: true })]);
      data = Object.assign({}, a, b, { __missing: Object.assign({}, a.__missing, b.__missing) });
      missing = Object.values(data.__missing || {});
    } catch (err) {
      if (token !== renderToken) return;
      const errs = err.all || [err];
      content.innerHTML = ''; content.classList.remove('loading'); content.removeAttribute('aria-busy');
      M.commentary.renderHeader(h('div', '', content), view, null, view.kicker || (dash ? `${dash.num} · ${dash.title}` : 'SF City Monitor'));
      if (dash && modSource(dash.id) === 'sample') sampleBanner(content, dash);
      unavailable(content, errs.map((e) => ({ logical: e.logical || String(e), status: e.status || 'error', errors: e.errors || [String(e.message || e)] })));
      M.commentary.renderData(h('div', '', content), { feeds: [], files: fileList(files, data || {}, errs), sources: [], asOf: meta ? meta.as_of : null, open: st.data, filtersText: 'No records could be counted because a required file is unavailable.' });
      M.app.lastView = { id: view.id, unavailable: true };
      return;
    }
    let commentary = null;
    const cpath = commentaryPath(view, dash);
    try { commentary = await M.data.load(cpath); } catch (e) { commentary = null; }
    if (token !== renderToken) return;
    content.innerHTML = ''; content.classList.remove('loading'); content.removeAttribute('aria-busy');
    const feeds = [], slots = {}, units = [];
    const ctx = {
      root: content, state: st, data, meta, metas: METAS, site: SITE, commentary, dash, view, h, empty, slots, missing,
      card: (o) => card(ctx.grid || content, o),
      link(text, patch, cls) { const a = h('a', 'link' + (cls ? ' ' + cls : ''), null, text); a.href = S.serialise(Object.assign({}, S.DEFAULTS, { theme: st.theme }, patch)); a.addEventListener('click', (e) => { if (e.metaKey || e.ctrlKey || e.shiftKey) return; e.preventDefault(); S.set(Object.assign({ mode: 'explore', id: null }, patch)); }); return a; },
      feed(label, matched, total) { feeds.push({ label, matched, total }); },
      units(label) { units.push(label); },
      years: dash && meta ? S.years(st, meta[dash.yearsKey]) : null,
      yearList() { const [a, b] = ctx.years; const out = []; for (let y = a; y <= b; y++) out.push(y); return out; },
      v: (k, d) => (st.v[k] != null && st.v[k] !== '' ? st.v[k] : d), setV: (k, val) => S.set({ v: { [k]: val } }),
      real(amount, fy) { return st.real && meta && meta.deflator ? M.stats.real(amount, fy, meta.deflator) : amount; },
      dollars: st.real && meta && meta.deflator ? `FY${meta.deflator.base_fy} dollars` : 'nominal dollars',
      deptName(id) { const d = (SITE.departments || []).find((x) => x.id === id); return d ? d.name : id; },
      deptShort(id) { const d = (SITE.departments || []).find((x) => x.id === id); return d ? d.short || d.id : id; },
      live(ids) { M.commentary.live(ctx.liveEl, commentary, ids, slots, dash ? null : 'In brief'); },
      fair(text, label) { const b = h('div', 'fair', ctx.pre); h('b', '', b, label || 'Fairness note'); b.appendChild(document.createTextNode(' ' + text)); return b; },
      ruleOf(id) { const nm = METAS.nw; return nm && (nm.rules || []).find((x) => x.id === id && x.cite); },
      rule(id) { const r = ctx.ruleOf(id); if (!r) return null; const b = h('div', 'rule', ctx.pre); h('b', '', b, r.short + '. '); b.appendChild(document.createTextNode(r.text)); h('span', 'cite', b, 'Rule: ' + r.cite); if (r.verify) h('span', 'verify', b, 'To verify before publication: ' + r.verify); return b; },
      tag(kind, txt) { return h('span', 'tag tag-' + kind, null, txt); },
      /** The only way to print "appears to warrant review": needs a cited rule and a reason; otherwise a neutral pattern tag. */
      review(ruleId, reason, fallback) { const r = ctx.ruleOf(ruleId); const wrap = h('span', 'review-wrap'); if (r && reason) { wrap.appendChild(ctx.tag('review', 'appears to warrant review')); h('span', 'review-cite', wrap, ` ${r.cite.replace(/^S\.F\. Campaign and Governmental Conduct Code /, 'C&GC Code ')}`); h('span', 'review-why', wrap, reason); } else wrap.appendChild(ctx.tag('pattern', fallback || 'pattern worth checking')); return wrap; },
      need(keys, label) { const miss = keys.filter((k) => !data[k]); if (!miss.length) return true; unavailable(h('div', 'col-12', ctx.grid), miss.map((k) => { const e = data.__missing[k]; return { logical: e ? e.logical : files[k], status: e ? e.status : 'missing', errors: e ? e.errors : [] }; }), { compact: true, title: `${label}: not available yet` }); return false; },
      isSample(dashId) { return modSource(dashId) === 'sample'; },
      sampleTag(dashId) { return modSource(dashId) === 'sample' ? h('span', 'badge badge-sample', null, 'sample data') : null; },
    };
    M.commentary.renderHeader(h('div', '', content), view, commentary, view.kicker || (dash ? `${dash.num} · ${dash.title}` : 'SF City Monitor'), { missingCommentary: !commentary && dash && view.headline !== false, real: dash && modSource(dash.id) === 'real' });
    if (dash && modSource(dash.id) === 'sample') sampleBanner(content, dash);
    // Entity and site pages put their header of facts first; dashboards put the live sentences and the data strip first.
    if (!dash) ctx.pre = h('div', '', content);
    ctx.liveEl = h('div', 'live-slot', content); ctx.liveEl.hidden = true;
    ctx.dataEl = h('div', '', content);
    if (dash) ctx.pre = h('div', '', content);
    ctx.grid = h('div', 'grid', content);
    try { await Promise.resolve(view.render(ctx)); } catch (err) { console.error(err); empty(h('div', 'col-12 card', ctx.grid), 'View failed to render', 'Something in the data did not match what this view expects. The rest of the site is unaffected.'); M.app.errors.push(`${view.id}: ${err.message}`); }
    if (token !== renderToken) return;
    const srcIds = new Set(); Object.values(data).forEach((d) => (d && d.sources || []).forEach((s) => srcIds.add(typeof s === 'string' ? s : s && s.id)));
    if (view.allSources) Object.values(METAS).forEach((m) => (m && m.sources || []).forEach((s) => srcIds.add(s.id)));
    const sources = []; Object.values(METAS).forEach((m) => (m && m.sources || []).forEach((s) => { if (srcIds.has(s.id) && !sources.some((x) => x.id === s.id)) sources.push(s); }));
    if (dash && view.filters && view.filters.length && !feeds.length) console.warn(`[filters] view ${view.id} declares filters but registered no filtered record counts`);
    const filtersText = view.filters && view.filters.length ? describeFilters(st, view, dash, meta) : (dash ? (view.filterNote || 'This view has no filters; it shows all records.') : 'Profile pages show all years; filters live in the dashboards.');
    M.commentary.renderData(ctx.dataEl, { feeds, units, files: fileList(Object.assign({ commentary: cpath }, files), Object.assign({ commentary }, data), missing), sources, asOf: meta ? meta.as_of : latestAsOf(), open: st.data, onToggle: (open) => S.set({ data: open }, { silent: true }), filtersText, sampleNote: dash && modSource(dash.id) === 'sample' ? 'Sample files come from design/prototype/sample-data; the module’s own export replaces them when it sets "sample": false.' : null });
    M.commentary.renderAnalysis(h('div', '', content), commentary);
    M.commentary.renderCaveats(h('div', '', content), commentary);
    if (window.scrollY > 0 && st.mode !== 'story') window.scrollTo({ top: 0 });
    renderStoryBar();
    M.app.lastView = { id: view.id, feeds, units, slots };
  }
  function latestAsOf() { return Object.values(SITE.modules || {}).map((m) => m.as_of).filter(Boolean).sort().pop() || null; }
  function fileList(files, data, missing) {
    const out = [], seen = new Set();
    for (const k of Object.keys(files)) {
      const p = files[k]; if (seen.has(p)) continue; seen.add(p);
      const e = M.data.entry(p) || {}, inf = M.data.info.get(p);
      const viaChunks = inf && inf.via === 'chunks';
      out.push({ path: p, bytes: viaChunks && e.chunk_bytes ? e.chunk_bytes : e.bytes || null, exportBytes: e.bytes || null, sample: !!e.sample, status: inf ? 'loaded' : e.status || 'missing', via: inf ? inf.via : null, parts: inf ? inf.parts : null });
    }
    return out;
  }
  function describeFilters(st, view, dash, meta) {
    const parts = [];
    for (const k of view.filters) {
      if (k === 'years') { const y = S.years(st, meta[dash.yearsKey]); parts.push(`${dash.yearsLabel.toLowerCase()} ${y[0]}–${y[1]}`); }
      else if (k === 'real') parts.push(st.real ? `real FY${meta.deflator.base_fy} dollars` : 'nominal dollars');
      else if (k === 'amt') { if (st.amt) parts.push(`amount ≥ ${fmt.money(st.amt)}`); }
      else if (st[k] && st[k].length) parts.push(`${FILTER_LABELS[k].toLowerCase()}: ${st[k].join(', ')}`);
    }
    return 'Filters in effect: ' + parts.join(' · ') + '. Every card on this view uses exactly these filters.';
  }

  // ---------------------------------------------------------------- story mode
  function enterStory(dashId, step) {
    const story = STORIES[dashId]; if (!story || !story.steps || !story.steps.length) return;
    step = Math.max(0, Math.min(story.steps.length - 1, step));
    const s = story.steps[step];
    const d = M.dashes[dashId];
    const patch = { mode: 'story', step, view: M.views[s.view] ? s.view : d.views[0], id: null };
    for (const k of d.filterKeys) patch[k] = JSON.parse(JSON.stringify(S.DEFAULTS[k]));
    if (s.filters) for (const k in s.filters) if (d.filterKeys.includes(k)) patch[k] = s.filters[k];
    S.set(patch);
  }
  function renderStoryBar() {
    const st = S.get(), bar = document.getElementById('storybar'), dash = dashOf(st.view);
    document.body.classList.toggle('story-on', st.mode === 'story' && !!dash && !!STORIES[dash && dash.id]);
    if (st.mode !== 'story' || !dash || !STORIES[dash.id]) { bar.hidden = true; return; }
    const story = STORIES[dash.id]; bar.hidden = false; bar.innerHTML = '';
    const s = story.steps[st.step] || story.steps[0];
    h('div', 'story-step', h('div', '', bar), `${story.title} · step ${st.step + 1} of ${story.steps.length}`);
    const mid = h('div', '', bar); mid.setAttribute('aria-live', 'polite'); h('p', 'story-title', mid, s.title); h('p', 'story-text', mid, s.text);
    const nav = h('div', 'story-nav', bar);
    const prev = h('button', 'btn', nav, 'Back'); prev.disabled = st.step === 0; prev.addEventListener('click', () => enterStory(dash.id, st.step - 1));
    const dots = h('div', 'story-dots', nav); story.steps.forEach((x, i) => { const d = h('button', 'story-dot', dots); d.title = x.title; d.setAttribute('aria-label', `Step ${i + 1}: ${x.title}`); if (i === st.step) d.setAttribute('aria-current', 'step'); d.addEventListener('click', () => enterStory(dash.id, i)); });
    const next = h('button', 'btn btn-primary', nav, st.step === story.steps.length - 1 ? 'Explore on your own' : 'Next'); next.addEventListener('click', () => (st.step === story.steps.length - 1 ? S.set({ mode: 'explore' }) : enterStory(dash.id, st.step + 1)));
    const exit = h('button', 'btn', nav, 'Exit'); exit.addEventListener('click', () => S.set({ mode: 'explore' }));
  }

  // ---------------------------------------------------------------- search (typeahead + results page)
  const input = document.getElementById('search-input'), pop = document.getElementById('search-pop');
  let searchT, hitIdx = -1;
  function renderHits(hits) {
    pop.innerHTML = ''; pop.hidden = !hits.length; hitIdx = -1; input.setAttribute('aria-expanded', String(!!hits.length));
    hits.forEach((x, i) => { const b = h('button', 'search-hit', pop); b.type = 'button'; b.id = 'hit-' + i; b.setAttribute('role', 'option'); const l = h('span', '', b); h('span', '', l, x.label); if (x.sub) h('span', 'kind', l, ' ' + x.sub); h('span', 'kind', b, x.kind + (x.sample ? ' · sample' : '')); b.addEventListener('click', () => { pop.hidden = true; input.value = ''; S.set(Object.assign({ mode: 'explore', id: null }, x.patch)); }); });
  }
  input.addEventListener('input', () => { clearTimeout(searchT); searchT = setTimeout(async () => { const q = input.value.trim(); if (q.length < 2) { pop.hidden = true; return; } renderHits((await M.search.query(q)).slice(0, 8)); }, 120); });
  input.addEventListener('keydown', (e) => {
    const items = [...pop.querySelectorAll('.search-hit')];
    if ((e.key === 'ArrowDown' || e.key === 'ArrowUp') && items.length && !pop.hidden) { e.preventDefault(); hitIdx = (hitIdx + (e.key === 'ArrowDown' ? 1 : items.length - 1)) % items.length; items.forEach((b, i) => b.classList.toggle('active', i === hitIdx)); input.setAttribute('aria-activedescendant', items[hitIdx].id); return; }
    if (e.key === 'Enter') { e.preventDefault(); if (hitIdx >= 0 && items[hitIdx]) { items[hitIdx].click(); return; } pop.hidden = true; S.set({ view: 'search', q: input.value.trim(), id: null, mode: 'explore' }); }
    if (e.key === 'Escape') { pop.hidden = true; input.blur(); }
  });
  document.addEventListener('click', (e) => { if (!document.getElementById('search').contains(e.target)) pop.hidden = true; });

  // ---------------------------------------------------------------- keyboard + help
  const help = document.getElementById('help');
  function toggleHelp(show) { help.hidden = show == null ? !help.hidden : !show; if (!help.hidden) help.querySelector('button').focus(); }
  help.querySelector('button').addEventListener('click', () => toggleHelp(false));
  help.addEventListener('click', (e) => { if (e.target === help) toggleHelp(false); });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !help.hidden) { toggleHelp(false); return; }
    if (e.target.matches('input, select, textarea') || e.metaKey || e.ctrlKey || e.altKey) return;
    const st = S.get(), d = dashOf(st.view);
    if (e.key === '/') { e.preventDefault(); input.focus(); }
    else if (e.key === 'd') document.getElementById('theme-toggle').click();
    else if (e.key === 's' && d && STORIES[d.id]) (st.mode === 'story' ? S.set({ mode: 'explore' }) : enterStory(d.id, 0));
    else if (d && (e.key === ']' || e.key === '[')) { const i = d.views.indexOf(st.view); S.set({ view: d.views[(i + (e.key === ']' ? 1 : d.views.length - 1)) % d.views.length], id: null }); }
    else if (e.key === 'ArrowRight' && st.mode === 'story' && d && STORIES[d.id]) enterStory(d.id, st.step + 1);
    else if (e.key === 'ArrowLeft' && st.mode === 'story' && d && STORIES[d.id]) enterStory(d.id, st.step - 1);
    else if (e.key === '?') toggleHelp();
  });

  // ---------------------------------------------------------------- boot
  function schedule() { M.app.rendered = renderView().catch((err) => { console.error(err); M.app.errors.push(String(err && err.message)); }); return M.app.rendered; }
  S.subscribe((st, info) => { applyTheme(st.theme); if (info.silent) return; if (info.patch && Object.keys(info.patch).length === 1 && 'theme' in info.patch) return; schedule(); });
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => applyTheme(S.get().theme));
  let resizeT; window.addEventListener('resize', () => { clearTimeout(resizeT); resizeT = setTimeout(() => { const w = document.getElementById('content').getBoundingClientRect().width; if (Math.abs(w - lastWidth) > 40) { lastWidth = w; schedule(); } }, 200); });
  async function boot() {
    const st = S.get(); applyTheme(st.theme);
    const content = document.getElementById('content'); content.innerHTML = ''; h('div', 'skeleton', content);
    lastWidth = content.getBoundingClientRect().width;
    if (!M.data.manifest) { content.innerHTML = ''; unavailable(content, [{ logical: 'data/manifest.js', status: 'missing', errors: ['Run python3 site/tools/bundle.py to build the data bundles.'] }], { title: 'Data not bundled yet' }); return; }
    const want = { site: 'site/site.json' };
    Object.values(M.dashes).forEach((d) => { want['m_' + d.id] = `${d.module}/meta.json`; want['s_' + d.id] = d.story; });
    const got = await M.data.loadAll(want, { optional: true });
    SITE = got.site || SITE;
    Object.values(M.dashes).forEach((d) => { METAS[d.id] = got['m_' + d.id]; STORIES[d.id] = got['s_' + d.id] && got['s_' + d.id].steps && got['s_' + d.id].steps.length ? got['s_' + d.id] : null; });
    M.METAS = METAS; M.SITE = SITE; M.STORIES = STORIES;
    const asof = document.getElementById('asof'); asof.innerHTML = '';
    const la = latestAsOf(); asof.appendChild(document.createTextNode(`Data as of ${la || '–'}`));
    const bits = [];
    const smp = (d) => (modSource(d) === 'sample' ? ' (sample)' : '');
    if (METAS.np) bits.push(`${fmt.int(METAS.np.counts && METAS.np.counts.organizations)} organizations${smp('np')}`);
    if (METAS.pf) bits.push(`${fmt.int(METAS.pf.dimensions.dept.values.length)} departments${smp('pf')}`);
    if (METAS.au) bits.push(`${fmt.int(METAS.au.counts && METAS.au.counts.recommendations)} recommendations${smp('au')}`);
    if (METAS.nw) bits.push(`${fmt.int(METAS.nw.counts && METAS.nw.counts.flows)} network flows${smp('nw')}`);
    if (bits.length) asof.appendChild(document.createTextNode(' · ' + bits.join(' · ')));
    renderSampleNotice();
    if (new URLSearchParams(location.search).get('selftest') && M.selftest) { M.selftest.run(); return; }
    schedule();
  }
  document.getElementById('brand').addEventListener('click', (e) => { e.preventDefault(); S.set({ view: 'home', id: null, mode: 'explore' }); });
  Object.assign(M.app, { card, empty, unavailable, enterStory, dashOf, renderNow: schedule, modSource, DASH_BY_MODULE, FILTER_LABELS });
  boot();
})();
