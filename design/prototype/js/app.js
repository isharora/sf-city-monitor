/* app.js - shell: dashboards, navigation, the filter bar (renders ONLY filters the view applies),
   card helper with table twin, data-transparency panel, story mode, search, theme, keyboard. */
(function () {
  const M = window.SFCM;
  const { h } = M.charts;
  const S = M.state;
  const fmt = M.stats.fmt;

  // ---------------------------------------------------------------- dashboards
  M.dashes = {
    np: { id: 'np', num: 1, title: 'Follow the nonprofit money', short: 'Nonprofit money', what: 'City payments and contracts to nonprofits, linked to their IRS 990 finances and the Controller’s monitoring results.', meta: 'nonprofits/meta.json', story: 'commentary/story_np.json', yearsKey: 'fiscal_years', yearsLabel: 'Fiscal years', filterKeys: ['years', 'dept', 'area', 'size', 'real'], views: ['np-overview', 'np-flows', 'np-dependency', 'np-pay', 'np-growth', 'np-reviews', 'np-orgs'] },
    pf: { id: 'pf', num: 2, title: 'Budget vs outcomes', short: 'Budget vs outcomes', what: 'What each department spends, in real dollars and per resident, and what it gets for it.', meta: 'performance/meta.json', story: 'commentary/story_pf.json', yearsKey: 'fiscal_years', yearsLabel: 'Fiscal years', filterKeys: ['years', 'group', 'dept', 'real'], views: ['pf-overview', 'pf-spending', 'pf-staffing', 'pf-outcomes', 'pf-cost', 'pf-integrity', 'pf-gaps', 'pf-depts'] },
    au: { id: 'au', num: 3, title: 'Audit recommendations tracker', short: 'Audit tracker', what: 'Every recommendation from the Controller’s auditors, the Budget and Legislative Analyst and the Civil Grand Jury, and what happened to it.', meta: 'audits/meta.json', story: 'commentary/story_au.json', yearsKey: 'years', yearsLabel: 'Years issued', filterKeys: ['years', 'source', 'dept', 'topic'], views: ['au-overview', 'au-status', 'au-time', 'au-agreement', 'au-repeat', 'au-open', 'au-reports'] },
    nw: { id: 'nw', num: 4, title: 'Money network', short: 'Money network', what: 'How money moves between donors, officials, lobbyists and the organizations that get city contracts and approvals.', meta: 'network/meta.json', story: 'commentary/story_nw.json', yearsKey: 'years', yearsLabel: 'Years', filterKeys: ['years', 'flow', 'etype', 'amt'], views: ['nw-overview', 'nw-graph', 'nw-ban', 'nw-behested', 'nw-lobby', 'nw-concentration', 'nw-loop', 'nw-entities'] },
  };
  const FILTER_LABELS = { years: 'Years', dept: 'Department', area: 'Service area', size: 'Size', group: 'Department group', real: 'Dollars', source: 'Recommended by', topic: 'Topic', flow: 'Flow type', etype: 'Entity type', amt: 'Minimum amount' };
  let METAS = {}, STORIES = {}, SITE = null;

  // ---------------------------------------------------------------- theme
  function applyTheme(pref) { const dark = pref === 'dark' || (pref === 'auto' && matchMedia('(prefers-color-scheme: dark)').matches); document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light'); document.getElementById('theme-toggle').setAttribute('aria-pressed', String(dark)); try { localStorage.setItem('sfcm-theme', pref); } catch (e) { /* ignore */ } }
  document.getElementById('theme-toggle').addEventListener('click', () => S.set({ theme: document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark' }));
  document.getElementById('share-btn').addEventListener('click', async (e) => { try { await navigator.clipboard.writeText(location.href); e.target.textContent = 'Link copied'; setTimeout(() => (e.target.textContent = 'Copy link'), 1500); } catch (err) { prompt('Copy this link', location.href); } });
  document.getElementById('story-btn').addEventListener('click', () => { const st = S.get(); if (st.mode === 'story') S.set({ mode: 'explore' }); else { const d = dashOf(st.view); if (d) enterStory(d.id, 0); } });

  function dashOf(viewId) { const v = M.views[viewId]; return v && M.dashes[v.dash] ? M.dashes[v.dash] : null; }

  // ---------------------------------------------------------------- nav
  function renderNav() {
    const st = S.get(), cur = dashOf(st.view);
    const sw = document.getElementById('dash-switch'); sw.innerHTML = '';
    const home = h('button', 'dash-btn', sw); home.type = 'button'; h('span', 'num', home, '⌂'); h('span', '', home, 'Home'); if (st.view === 'home') home.setAttribute('aria-current', 'true'); home.addEventListener('click', () => S.set({ view: 'home', id: null, mode: 'explore' }));
    Object.values(M.dashes).forEach((d) => { const b = h('button', 'dash-btn', sw); b.type = 'button'; h('span', 'num', b, String(d.num)); h('span', '', b, d.short); if (cur && cur.id === d.id) b.setAttribute('aria-current', 'true'); b.addEventListener('click', () => S.set({ view: d.views[0], id: null, mode: 'explore' })); });
    const nav = document.getElementById('nav'); nav.innerHTML = '';
    if (cur) {
      h('div', 'nav-group-title', nav, cur.title);
      cur.views.forEach((id, i) => { const v = M.views[id]; const b = h('button', 'nav-item', nav); b.type = 'button'; h('span', 'nav-num', b, String(i + 1)); h('span', '', b, v.nav || v.title); if (st.view === id) b.setAttribute('aria-current', 'page'); b.addEventListener('click', () => S.set({ view: id, id: null })); });
    } else {
      h('div', 'nav-group-title', nav, 'Site');
      [['home', 'Landing page'], ['search', 'Search'], ['methods', 'Methods and data']].forEach(([id, label]) => { const b = h('button', 'nav-item', nav); b.type = 'button'; h('span', 'nav-num', b, '·'); h('span', '', b, label); if (st.view === id) b.setAttribute('aria-current', 'page'); b.addEventListener('click', () => S.set({ view: id })); });
      if (['org', 'dept', 'report', 'official'].includes(st.view)) { const b = h('button', 'nav-item', nav); b.type = 'button'; b.setAttribute('aria-current', 'page'); h('span', 'nav-num', b, '·'); h('span', '', b, { org: 'Organization profile', dept: 'Department scorecard', report: 'Report page', official: 'Official profile' }[st.view]); }
    }
    const sb = document.getElementById('story-btn'); sb.hidden = !cur; sb.setAttribute('aria-pressed', String(st.mode === 'story'));
  }

  // ---------------------------------------------------------------- filter bar
  /** Multi-select popover. */
  function multiPick(parent, label, options, selected, onChange) {
    const wrap = h('div', 'pick', parent);
    const btn = h('button', 'pick-btn' + (selected.length ? ' active' : ''), wrap); btn.type = 'button'; btn.setAttribute('aria-haspopup', 'listbox'); btn.setAttribute('aria-expanded', 'false');
    btn.textContent = selected.length ? `${label} · ${selected.length === 1 ? (options.find((o) => o.id === selected[0]) || {}).label || selected[0] : selected.length + ' selected'}` : `${label} · All`;
    h('span', '', btn, ' ▾');
    const pop = h('div', 'pick-pop', wrap); pop.hidden = true; pop.setAttribute('role', 'listbox');
    const tools = h('div', 'tools', pop);
    const all = h('button', 'link', tools, 'All'); all.type = 'button'; all.addEventListener('click', () => onChange([]));
    const set = new Set(selected);
    options.forEach((o) => { const row = h('label', 'row', pop); const cb = h('input', '', row); cb.type = 'checkbox'; cb.checked = set.has(o.id); if (o.color) { const d = h('span', 'dot', row); d.style.background = o.color; } h('span', '', row, o.label); cb.addEventListener('change', () => { const s2 = new Set(set); cb.checked ? s2.add(o.id) : s2.delete(o.id); onChange([...s2]); }); });
    btn.addEventListener('click', () => { pop.hidden = !pop.hidden; btn.setAttribute('aria-expanded', String(!pop.hidden)); });
    document.addEventListener('click', (e) => { if (!wrap.contains(e.target)) { pop.hidden = true; btn.setAttribute('aria-expanded', 'false'); } });
    return wrap;
  }
  function renderFilters() {
    const st = S.get(), view = M.views[st.view], dash = dashOf(st.view);
    const bar = document.getElementById('filterbar'); bar.innerHTML = '';
    if (!dash || !view.filters || !view.filters.length) { bar.hidden = !(view && view.filterNote); if (view && view.filterNote) h('span', 'filter-na', bar, view.filterNote); return; }
    bar.hidden = false;
    const meta = METAS[dash.id];
    const dims = meta.dimensions || {};
    const bounds = meta[dash.yearsKey];
    for (const key of view.filters) {
      const f = h('div', 'filter', bar);
      if (key === 'years') {
        h('span', 'filter-label', f, dash.yearsLabel); const rng = h('div', 'range', f); const yrs = S.years(st, bounds);
        const mk = (val, onch) => { const s = h('select', '', rng); s.setAttribute('aria-label', dash.yearsLabel); for (let y = bounds.min; y <= bounds.max; y++) { const o = h('option', '', s, (dash.yearsKey === 'fiscal_years' ? 'FY' : '') + y); o.value = y; if (y === val) o.selected = true; } s.addEventListener('change', () => onch(+s.value)); };
        mk(yrs[0], (y) => S.set({ years: [y, Math.max(y, yrs[1])] })); h('span', '', rng, '–'); mk(yrs[1], (y) => S.set({ years: [Math.min(y, yrs[0]), y] }));
      } else if (key === 'real') {
        h('span', 'filter-label', f, 'Dollars'); const seg = h('div', 'seg', f); seg.setAttribute('role', 'group');
        const a = h('button', '', seg, `Real (FY${meta.deflator.base_fy})`); a.type = 'button'; a.setAttribute('aria-pressed', String(st.real)); a.addEventListener('click', () => S.set({ real: true }));
        const b = h('button', '', seg, 'Nominal'); b.type = 'button'; b.setAttribute('aria-pressed', String(!st.real)); b.addEventListener('click', () => S.set({ real: false }));
      } else if (key === 'amt') {
        h('span', 'filter-label', f, 'Min amount'); const s = h('select', 'ctl', f); s.setAttribute('aria-label', 'Minimum amount'); dims.amount_bands.forEach((b) => { const o = h('option', '', s, b.label); o.value = b.id; if (+st.amt === +b.id) o.selected = true; }); s.addEventListener('change', () => S.set({ amt: +s.value }));
      } else if (key === 'area' || key === 'size' || key === 'source' || key === 'flow') {
        const dim = dims[key === 'size' ? 'size_band' : key]; h('span', 'filter-label', f, dim.label.replace(/ \(.*\)/, '')); const cs = h('div', 'chips', f);
        dim.values.forEach((o) => { const c = h('button', 'chip', cs); c.type = 'button'; if (o.slot != null && key !== 'flow') { const d = h('span', 'dot', c); d.style.background = `var(--c-${o.id})`; } h('span', '', c, o.short || o.label); c.title = o.label; c.setAttribute('aria-pressed', String(st[key].includes(o.id))); c.addEventListener('click', () => { const set = new Set(st[key]); set.has(o.id) ? set.delete(o.id) : set.add(o.id); S.set({ [key]: [...set] }); }); });
      } else if (key === 'dept' || key === 'group' || key === 'topic' || key === 'etype') {
        const dim = dims[key]; multiPick(f, dim.label, dim.values.map((o) => ({ id: o.id, label: o.name || o.label, color: o.slot != null ? `var(--c-${o.id})` : null })), st[key], (vals) => S.set({ [key]: vals }));
      }
    }
    if (S.filtersActive(st, view.filters)) { const r = h('button', 'link-btn', bar, 'Reset filters'); r.type = 'button'; r.addEventListener('click', () => S.resetFilters(view.filters)); }
    const absent = dash.filterKeys.filter((k) => !view.filters.includes(k));
    if (absent.length) { const na = h('span', 'filter-na', bar); na.appendChild(document.createTextNode('Not on this view: ')); absent.forEach((k, i) => { h('b', '', na, FILTER_LABELS[k]); na.appendChild(document.createTextNode((view.absent && view.absent[k] ? ` (${view.absent[k]})` : '') + (i < absent.length - 1 ? '; ' : ''))); }); }
  }

  // ---------------------------------------------------------------- card helper
  function card(parent, opts) {
    const c = h('section', 'card col-' + (opts.span || 12), parent);
    const tid = 'c-' + Math.random().toString(36).slice(2, 8);
    c.setAttribute('aria-labelledby', tid);
    const head = h('div', 'card-head', c), titles = h('div', 'card-titles', head);
    const t = h('h2', 'card-title', titles, opts.title); t.id = tid;
    if (opts.sub) h('p', 'card-sub', titles, opts.sub);
    const ctl = h('div', 'card-controls', head);
    (opts.controls || []).forEach((k) => { const sel = h('select', '', ctl); sel.setAttribute('aria-label', k.label); sel.title = k.label; k.options.forEach(([v, l]) => { const o = h('option', '', sel, l); o.value = v; if (String(k.value) === String(v)) o.selected = true; }); sel.addEventListener('change', () => k.onChange(sel.value)); });
    const body = h('div', 'card-body', c);
    let tableMode = false, spec = null;
    const tb = h('button', 'tbl-btn', ctl, 'Table'); tb.type = 'button'; tb.setAttribute('aria-pressed', 'false'); tb.title = 'Show the same data as a table';
    const draw = () => { body.innerHTML = ''; try { if (tableMode && spec) renderTable(body, spec); else spec = opts.render(body) || spec; if (!spec || !spec.head) tb.hidden = true; } catch (err) { console.error('render failed:', opts.title, err); empty(body, 'Chart failed to render', String(err.message)); } };
    tb.addEventListener('click', () => { tableMode = !tableMode; tb.setAttribute('aria-pressed', String(tableMode)); tb.textContent = tableMode ? 'Chart' : 'Table'; draw(); });
    draw();
    if (opts.note) h('p', 'note', c, opts.note);
    if (opts.caveat) { const cv = h('p', 'caveat-inline', c); h('b', '', cv, 'Why this might be wrong: '); cv.appendChild(document.createTextNode(opts.caveat)); }
    if (opts.foot) { const f = h('div', 'card-foot', c); (Array.isArray(opts.foot) ? opts.foot : [opts.foot]).forEach((x) => h('span', 'tnum', f, x)); }
    return c;
  }
  function renderTable(el, spec) { const wrap = h('div', 'table-wrap', el); const t = h('table', 'data-table', wrap); const tr = h('tr', '', h('thead', '', t)); spec.head.forEach((x) => h('th', '', tr, x)); const tb = h('tbody', '', t); spec.rows.forEach((r) => { const row = h('tr', '', tb); r.forEach((x) => h('td', '', row, x == null ? '–' : String(x))); }); }
  function empty(el, title, txt) { const e = h('div', 'empty', el); h('b', '', e, title); if (txt) e.appendChild(document.createTextNode(txt)); return e; }

  // ---------------------------------------------------------------- render view
  let renderToken = 0;
  async function renderView() {
    const st = S.get();
    const view = M.views[st.view] || M.views.home;
    const dash = dashOf(view.id);
    const content = document.getElementById('content');
    document.title = `${view.title} · SF City Monitor (prototype)`;
    renderNav(); renderFilters();
    const token = ++renderToken;
    content.classList.add('loading');
    let data;
    const files = Object.assign({ commentary: `commentary/${view.id}.json` }, typeof view.files === 'function' ? view.files(st) : view.files || {});
    try { data = await M.data.loadAll(files); } catch (err) { content.classList.remove('loading'); content.innerHTML = ''; empty(content, 'Could not load data', err.message); return; }
    if (token !== renderToken) return;
    content.innerHTML = ''; content.classList.remove('loading');
    const meta = dash ? METAS[dash.id] : null;
    const feeds = [], slots = {};
    const ctx = {
      root: content, state: st, data, meta, metas: METAS, site: SITE, commentary: data.commentary, dash, view, h, empty, slots,
      card: (o) => card(ctx.grid || content, o),
      link(text, patch, cls) { const a = h('a', 'link' + (cls ? ' ' + cls : ''), null, text); a.href = S.serialise(Object.assign({}, S.DEFAULTS, { theme: st.theme }, patch)); a.addEventListener('click', (e) => { e.preventDefault(); S.set(Object.assign({ mode: 'explore' }, patch)); }); return a; },
      feed(label, matched, total) { feeds.push({ label, matched, total }); },
      years: dash ? S.years(st, meta[dash.yearsKey]) : null,
      yearList() { const [a, b] = ctx.years; const out = []; for (let y = a; y <= b; y++) out.push(y); return out; },
      v: (k, d) => (st.v[k] != null ? st.v[k] : d), setV: (k, val) => S.set({ v: { [k]: val } }),
      real(amount, fy) { return st.real && meta && meta.deflator ? M.stats.real(amount, fy, meta.deflator) : amount; },
      dollars: st.real && meta && meta.deflator ? `FY${meta.deflator.base_fy} dollars` : 'nominal dollars',
      deptName(id) { const d = (SITE.departments || []).find((x) => x.id === id); return d ? d.name : id; },
      deptShort(id) { const d = (SITE.departments || []).find((x) => x.id === id); return d ? d.short : id; },
      live(ids) { M.commentary.live(ctx.liveEl, data.commentary, ids, slots); },
      fair(text, label) { const b = h('div', 'fair', ctx.grid ? ctx.pre : content); h('b', '', b, label || 'Fairness note'); b.appendChild(document.createTextNode(' ' + text)); return b; },
      rule(id) { const nm = METAS.nw; const r = nm && (nm.rules || []).find((x) => x.id === id); if (!r) return null; const b = h('div', 'rule', ctx.pre); h('b', '', b, r.short + '. '); b.appendChild(document.createTextNode(r.text)); h('span', 'cite', b, 'Rule: ' + r.cite); if (r.verify) h('span', 'verify', b, 'To verify before publication: ' + r.verify); return b; },
      tag(kind, txt) { return h('span', 'tag tag-' + kind, null, txt); },
    };
    M.commentary.renderHeader(h('div', '', content), view, data.commentary, view.kicker || (dash ? `${dash.num} · ${dash.title}` : 'SF City Monitor'));
    ctx.liveEl = h('div', '', content); ctx.liveEl.hidden = true;
    ctx.dataEl = h('div', '', content);
    ctx.pre = h('div', '', content);
    ctx.grid = h('div', 'grid', content);
    try { await Promise.resolve(view.render(ctx)); } catch (err) { console.error(err); empty(ctx.grid, 'View failed to render', err.message); }
    if (token !== renderToken) return;
    // data-transparency panel (every view)
    const fileList = Object.values(files).map((p) => { const mod = p.split('/')[0]; const m = METAS[{ nonprofits: 'np', performance: 'pf', audits: 'au', network: 'nw' }[mod]]; const d = data[Object.keys(files).find((k) => files[k] === p)]; return { path: p, bytes: m && m.files && m.files[p] ? m.files[p].bytes : (window.SFCM_SAMPLE_BUNDLE && window.SFCM_SAMPLE_BUNDLE[p] ? JSON.stringify(window.SFCM_SAMPLE_BUNDLE[p]).length : null), sample: d && d.sample, as_of: d && d.as_of }; });
    const srcIds = new Set(); Object.values(data).forEach((d) => (d && d.sources || []).forEach((s) => srcIds.add(s)));
    const sources = []; Object.values(METAS).forEach((m) => (m.sources || []).forEach((s) => { if (srcIds.has(s.id) && !sources.some((x) => x.id === s.id)) sources.push(s); }));
    if (view.filters && view.filters.length && S.filtersActive(st, view.filters) && !feeds.length) console.warn(`[filters] view ${view.id} declares filters but registered no filtered record counts`);
    const filtersText = view.filters && view.filters.length ? describeFilters(st, view, dash, meta) : (dash ? 'This view has no filters; it shows all records.' : 'Profile pages show all years; filters live in the dashboards.');
    M.commentary.renderData(ctx.dataEl, { feeds, files: fileList, sources, asOf: meta ? meta.as_of : SITE.modules ? Object.values(SITE.modules).map((m) => m.as_of).sort().pop() : null, open: st.data, onToggle: (open) => S.set({ data: open }, { silent: true }), filtersText, sampleNote: 'Synthetic sample data for design review; production files must set "sample": false.' });
    M.commentary.renderAnalysis(h('div', '', content), data.commentary);
    M.commentary.renderCaveats(h('div', '', content), data.commentary);
    if (window.scrollY > 0 && st.mode !== 'story') window.scrollTo({ top: 0 });
    renderStoryBar();
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
    const story = STORIES[dashId]; if (!story) return;
    const s = story.steps[step] || story.steps[0];
    const d = M.dashes[dashId];
    const patch = { mode: 'story', step, view: s.view, id: null };
    for (const k of d.filterKeys) patch[k] = JSON.parse(JSON.stringify(S.DEFAULTS[k]));
    if (s.filters) Object.assign(patch, s.filters);
    S.set(patch);
  }
  function renderStoryBar() {
    const st = S.get(), bar = document.getElementById('storybar'), dash = dashOf(st.view);
    if (st.mode !== 'story' || !dash || !STORIES[dash.id]) { bar.hidden = true; return; }
    const story = STORIES[dash.id]; bar.hidden = false; bar.innerHTML = '';
    const s = story.steps[st.step] || story.steps[0];
    h('div', 'story-step', h('div', '', bar), `${story.title} · step ${st.step + 1} of ${story.steps.length}`);
    const mid = h('div', '', bar); h('p', 'story-title', mid, s.title); h('p', 'story-text', mid, s.text);
    const nav = h('div', 'story-nav', bar);
    const prev = h('button', 'btn', nav, 'Back'); prev.disabled = st.step === 0; prev.addEventListener('click', () => enterStory(dash.id, st.step - 1));
    const dots = h('div', 'story-dots', nav); story.steps.forEach((x, i) => { const d = h('button', 'story-dot', dots); d.title = x.title; d.setAttribute('aria-label', `Step ${i + 1}: ${x.title}`); if (i === st.step) d.setAttribute('aria-current', 'step'); d.addEventListener('click', () => enterStory(dash.id, i)); });
    const next = h('button', 'btn btn-primary', nav, st.step === story.steps.length - 1 ? 'Explore on your own' : 'Next'); next.addEventListener('click', () => (st.step === story.steps.length - 1 ? S.set({ mode: 'explore' }) : enterStory(dash.id, st.step + 1)));
    const exit = h('button', 'btn', nav, 'Exit'); exit.addEventListener('click', () => S.set({ mode: 'explore' }));
  }

  // ---------------------------------------------------------------- search (typeahead + results page)
  const input = document.getElementById('search-input'), pop = document.getElementById('search-pop');
  let searchT;
  input.addEventListener('input', () => { clearTimeout(searchT); searchT = setTimeout(async () => { const q = input.value.trim(); if (q.length < 2) { pop.hidden = true; return; } const hits = (await M.search.query(q)).slice(0, 8); pop.innerHTML = ''; pop.hidden = !hits.length; hits.forEach((x) => { const b = h('button', 'search-hit', pop); b.type = 'button'; const l = h('span', '', b); h('span', '', l, x.label); if (x.sub) h('span', 'kind', l, ' ' + x.sub); h('span', 'kind', b, x.kind); b.addEventListener('click', () => { pop.hidden = true; input.value = ''; S.set(Object.assign({ mode: 'explore' }, x.patch)); }); }); }, 120); });
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter') { pop.hidden = true; S.set({ view: 'search', q: input.value.trim(), id: null, mode: 'explore' }); } if (e.key === 'Escape') pop.hidden = true; });
  document.addEventListener('click', (e) => { if (!document.getElementById('search').contains(e.target)) pop.hidden = true; });

  // ---------------------------------------------------------------- keyboard
  document.addEventListener('keydown', (e) => {
    if (e.target.matches('input, select, textarea')) return;
    const st = S.get(), d = dashOf(st.view);
    if (e.key === '/') { e.preventDefault(); input.focus(); }
    else if (e.key === 'd') document.getElementById('theme-toggle').click();
    else if (e.key === 's' && d) (st.mode === 'story' ? S.set({ mode: 'explore' }) : enterStory(d.id, 0));
    else if (d && (e.key === ']' || e.key === '[')) { const i = d.views.indexOf(st.view); S.set({ view: d.views[(i + (e.key === ']' ? 1 : d.views.length - 1)) % d.views.length], id: null }); }
    else if (e.key === 'ArrowRight' && st.mode === 'story' && d) enterStory(d.id, Math.min(STORIES[d.id].steps.length - 1, st.step + 1));
    else if (e.key === 'ArrowLeft' && st.mode === 'story' && d) enterStory(d.id, Math.max(0, st.step - 1));
    else if (e.key === '?') alert('Keyboard: / search · [ and ] switch views within a dashboard · s story mode · arrows move through the story · d dark mode · Tab reaches every chart mark; focus shows the same tooltip as hover.');
  });

  // ---------------------------------------------------------------- boot
  S.subscribe((st, info) => { applyTheme(st.theme); if (info.silent) return; renderView(); });
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => applyTheme(S.get().theme));
  let resizeT; window.addEventListener('resize', () => { clearTimeout(resizeT); resizeT = setTimeout(renderView, 150); });
  (async () => {
    const st = S.get(); applyTheme(st.theme);
    const content = document.getElementById('content'); content.innerHTML = ''; h('div', 'skeleton', content);
    try {
      const d = await M.data.loadAll({ site: 'site.json', np: 'nonprofits/meta.json', pf: 'performance/meta.json', au: 'audits/meta.json', nw: 'network/meta.json', s_np: 'commentary/story_np.json', s_pf: 'commentary/story_pf.json', s_au: 'commentary/story_au.json', s_nw: 'commentary/story_nw.json' });
      SITE = d.site; METAS = { np: d.np, pf: d.pf, au: d.au, nw: d.nw }; STORIES = { np: d.s_np, pf: d.s_pf, au: d.s_au, nw: d.s_nw }; M.METAS = METAS; M.SITE = SITE;
    } catch (err) { content.innerHTML = ''; empty(content, 'Could not load data', err.message); return; }
    document.getElementById('asof').textContent = `Data as of ${Object.values(SITE.modules).map((m) => m.as_of).sort().pop()} · nonprofits ${METAS.np.counts.organizations} orgs · ${fmt.int(METAS.au.counts.recommendations)} recommendations · ${fmt.int(METAS.nw.counts.flows)} network flows`;
    renderView();
  })();
  M.app = { card, empty, enterStory, dashOf };
})();
