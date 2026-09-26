/* commentary.js - the analyst layer and the data-transparency panel.
   Headline, live filter-aware sentences with small-sample fallbacks, analyst paragraphs,
   severity-tagged caveats, chart annotations; plus "how much data is feeding this page". */
(function () {
  const M = (window.SFCM = window.SFCM || {});
  const h = (tag, cls, parent, txt) => M.charts.h(tag, cls, parent, txt);
  const fmt = () => M.stats.fmt;

  /** Fill {slot}s; a slot with no value renders as an en dash, never as the raw placeholder. */
  function fill(template, slots) { return String(template).replace(/\{(\w+)\}/g, (m, k) => (slots[k] != null && slots[k] !== '' ? String(slots[k]) : '–')); }
  /** requires: {n_min: 20, x_max: 3, flag: true}; *_min / *_max compare against the slot without the suffix. */
  function passes(requires, slots) {
    if (!requires) return true;
    for (const k in requires) { const v = requires[k]; if (k.endsWith('_min')) { const s = slots[k.slice(0, -4)]; if (s == null || s < v) return false; } else if (k.endsWith('_max')) { const s = slots[k.slice(0, -4)]; if (s == null || s > v) return false; } else if (slots[k] !== v) return false; }
    return true;
  }
  const DEFAULT_FALLBACK = 'Too few records match to summarize; widen the years or clear a filter.';
  /** A template passes when its `requires` hold and the view has not flagged the scope as a small sample (slots.__small). */
  function sentence(tpl, slots) { if (!tpl || !tpl.template) return { text: '', small: false }; if (!slots.__small && passes(tpl.requires, slots)) return { text: fill(tpl.template, slots), small: false }; return { text: fill(tpl.fallback || DEFAULT_FALLBACK, slots), small: true }; }
  function template(commentary, id) { return ((commentary && commentary.templates) || []).find((t) => t.id === id); }
  /** Convenience: render the live block for template id(s) with slots. */
  function live(el, commentary, ids, slots, label) {
    const out = (Array.isArray(ids) ? ids : [ids]).map((id) => sentence(template(commentary, id), slots));
    renderLive(el, out.map((o) => o.text), { small: out.some((o) => o.small), label });
  }
  function renderLive(el, sentences, opts) {
    el.innerHTML = '';
    const txt = sentences.filter(Boolean);
    if (!txt.length) { el.hidden = true; return; }
    el.hidden = false;
    const box = h('div', 'live' + (opts && opts.small ? ' live-small' : ''), el);
    h('span', 'live-tag', box, opts && opts.small ? 'Too few records' : (opts && opts.label) || 'For your current filters');
    const body = h('div', 'live-body', box);
    txt.forEach((t) => h('p', 'live-text', body, t));
  }
  function renderHeader(el, view, commentary, kicker, opts) {
    opts = opts || {};
    el.innerHTML = '';
    const head = h('header', 'view-head', el);
    const k = h('div', 'kicker', head);
    h('span', '', k, kicker || view.section || '');
    if (commentary && commentary.sample) h('span', 'badge badge-sample', k, 'Sample commentary');
    h('h1', 'view-title', head, view.title);
    if (view.what) h('p', 'view-what', head, view.what);
    if (commentary && commentary.headline && view.headline !== false) { const hl = h('div', 'headline', head); h('span', 'headline-label', hl, 'Finding'); h('p', 'headline-text', hl, commentary.headline); }
    else if (opts.missingCommentary) { const hl = h('div', 'headline headline-missing', head); h('span', 'headline-label', hl, 'Finding'); h('p', 'headline-text', hl, 'The analyst’s commentary for this view has not been published yet. The charts below are computed from the data as filtered.'); }
    if (view.how) { const det = h('details', 'howto', head); h('summary', '', det, 'How to read this view'); h('p', '', det, view.how); }
    return head;
  }
  function renderAnalysis(el, commentary) {
    el.innerHTML = '';
    if (!commentary || !commentary.paragraphs || !commentary.paragraphs.length) return;
    const box = h('section', 'analysis', el);
    const top = h('div', 'analysis-top', box);
    h('h2', 'section-title', top, 'Analyst’s read');
    if (commentary.author) h('span', 'analysis-author', top, commentary.author);
    commentary.paragraphs.forEach((p) => h('p', 'analysis-p', box, p));
    if (commentary.sources && commentary.sources.length) { const src = h('p', 'analysis-sources', box, 'Numbers trace to: '); commentary.sources.forEach((s, i) => { h('code', '', src, s); if (i < commentary.sources.length - 1) src.appendChild(document.createTextNode(', ')); }); }
  }
  function renderCaveats(el, commentary, extra) {
    el.innerHTML = '';
    const list = [...((commentary && commentary.caveats) || []), ...(extra || [])];
    if (!list.length) return;
    const box = h('aside', 'caveats', el);
    h('h2', 'section-title', box, 'Why this might be wrong');
    const ul = h('ul', '', box);
    list.forEach((c) => { const li = h('li', 'caveat sev-' + (c.severity || 'medium'), ul); h('span', 'sev', li, c.severity === 'high' ? 'Could move the finding' : c.severity === 'low' ? 'Minor' : 'Worth knowing'); li.appendChild(document.createTextNode(' ' + c.text)); });
  }
  function annotationsFor(commentary, chartId) { return ((commentary && commentary.annotations) || []).filter((a) => a.chart === chartId); }

  /** Data transparency: strip (always visible) + panel (details). feeds: [{label, matched, total}]; units: ['real FY2025 dollars'];
      files: [{path, bytes, sample, status, via, parts}]; sources: [{id,name,rows,rows_used,as_of,publisher,note,url}]; filtersText. */
  function renderData(el, o) {
    el.innerHTML = '';
    const F = fmt();
    const strip = h('div', 'datastrip', el);
    strip.setAttribute('role', 'region'); strip.setAttribute('aria-label', 'How much data is feeding this page');
    h('span', 'ds-label', strip, 'Data on this page');
    if (!o.feeds.length) h('span', 'ds-item', strip, 'No record counts registered for this view');
    o.feeds.forEach((f) => { const it = h('span', 'ds-item ds-feed' + (f.matched === 0 ? ' zero' : ''), strip); it.dataset.matched = f.matched; if (f.total != null) it.dataset.total = f.total; h('b', '', it, F.int(f.matched)); it.appendChild(document.createTextNode(f.total != null && f.total !== f.matched ? ` of ${F.int(f.total)} ${f.label}` : ` ${f.label}`)); });
    (o.units || []).forEach((u) => { const it = h('span', 'ds-item ds-units', strip); it.appendChild(document.createTextNode('in ')); h('b', '', it, u); });
    if (o.sources.length) { const src = h('span', 'ds-item', strip); h('b', '', src, String(o.sources.length)); const dates = o.sources.map((s) => s.as_of).filter(Boolean).sort(); src.appendChild(document.createTextNode(` source dataset${o.sources.length === 1 ? '' : 's'}` + (dates.length ? `, as of ${dates[0] === dates[dates.length - 1] ? dates[0] : dates[0] + ' to ' + dates[dates.length - 1]}` : ''))); }
    const loaded = o.files.filter((f) => f.status === 'loaded'), notLoaded = o.files.filter((f) => f.status !== 'loaded' && !/commentary\//.test(f.path));
    const fl = h('span', 'ds-item', strip); h('b', '', fl, String(loaded.length)); fl.appendChild(document.createTextNode(` file${loaded.length === 1 ? '' : 's'} loaded (${F.bytes(loaded.reduce((a, f) => a + (f.bytes || 0), 0))})`));
    if (notLoaded.length) { const nl = h('span', 'ds-item zero', strip); h('b', '', nl, String(notLoaded.length)); nl.appendChild(document.createTextNode(` not available`)); }
    if (loaded.some((f) => f.sample)) h('span', 'badge badge-sample', strip, 'sample');
    if (o.asOf) { const ao = h('span', 'ds-item', strip); ao.appendChild(document.createTextNode('as of ')); h('b', '', ao, o.asOf); }
    const tog = h('button', 'link ds-toggle', strip, o.open ? 'Hide details' : 'Details'); tog.type = 'button'; tog.setAttribute('aria-expanded', String(!!o.open));
    const panel = h('div', 'datapanel', el); panel.hidden = !o.open; panel.id = 'datapanel'; tog.setAttribute('aria-controls', 'datapanel');
    tog.addEventListener('click', () => { panel.hidden = !panel.hidden; tog.textContent = panel.hidden ? 'Details' : 'Hide details'; tog.setAttribute('aria-expanded', String(!panel.hidden)); if (o.onToggle) o.onToggle(!panel.hidden); });
    // column 1: record counts for the current filters
    const c1 = h('div', '', panel); h('h3', '', c1, 'Records for your current filters');
    if (o.filtersText) h('p', 'muted', c1, o.filtersText).style.margin = '0 0 6px';
    const t1 = h('table', '', c1);
    o.feeds.forEach((f) => { const tr = h('tr', '', t1); const td = h('td', '', tr, f.label); const n = h('td', 'num', tr); n.textContent = f.total != null ? `${F.int(f.matched)} / ${F.int(f.total)}` : F.int(f.matched); if (f.total) { const bar = h('div', 'bar', td); const i = h('i', '', bar); i.style.width = `${Math.min(100, (100 * f.matched) / f.total)}%`; } });
    // column 2: sources
    const c2 = h('div', '', panel); h('h3', '', c2, 'Source datasets');
    const t2 = h('table', '', c2);
    const hr = h('tr', '', t2); ['Dataset', 'Rows used / total', 'As of'].forEach((x, i) => h('th', i ? 'num' : '', hr, x));
    if (!o.sources.length) { const tr = h('tr', '', t2); h('td', 'muted', tr, 'No source datasets are cited by the files on this page.').colSpan = 3; }
    o.sources.forEach((s) => { const tr = h('tr', '', t2); const td = h('td', '', tr); const nm = s.url ? h('a', '', td, s.name) : h('span', '', td, s.name); if (s.url) { nm.href = s.url; nm.target = '_blank'; nm.rel = 'noopener'; } h('div', 'muted', td, `${s.publisher || ''}${s.id ? ' · ' + s.id : ''}${s.note ? ' · ' + s.note : ''}`); h('td', 'num', tr, `${F.int(s.rows_used != null ? s.rows_used : s.rows)} / ${F.int(s.rows)}`); h('td', 'num', tr, s.as_of || '–'); });
    // column 3: files
    const c3 = h('div', '', panel); h('h3', '', c3, 'Files for this view');
    const t3 = h('table', '', c3);
    o.files.forEach((f) => { const tr = h('tr', '', t3); const td = h('td', '', tr); h('code', '', td, f.path); if (f.sample) { td.appendChild(document.createTextNode(' ')); h('span', 'badge badge-sample', td, 'sample'); } if (f.status !== 'loaded') h('div', 'muted', td, f.status === 'missing' ? 'not in the export' : f.status === 'invalid' ? 'fails the data contract' : 'not loaded'); else if (f.via) h('div', 'muted', td, f.via === 'fetch' ? `read from the export (${f.parts} file${f.parts === 1 ? '' : 's'})` : `bundled: ${f.parts} chunk${f.parts === 1 ? '' : 's'}${f.exportBytes && f.exportBytes !== f.bytes ? `, ${F.bytes(f.exportBytes)} as exported` : ''}`); h('td', 'num', tr, f.bytes ? F.bytes(f.bytes) : '–'); });
    if (o.sampleNote) h('p', 'muted', c3, o.sampleNote).style.margin = '8px 0 0';
    return panel;
  }
  M.commentary = { fill, passes, sentence, template, live, renderLive, renderHeader, renderAnalysis, renderCaveats, annotationsFor, renderData };
})();
