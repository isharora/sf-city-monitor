/* views-site.js - landing page, search (index + results), methods. */
(function () {
  const M = window.SFCM;
  M.views = M.views || {};
  const C = M.charts, fmt = M.stats.fmt, st_ = M.stats;

  // ---------------------------------------------------------------- search index
  let INDEX = null;
  async function buildIndex() {
    if (INDEX) return INDEX;
    // Individuals are never indexed (they are aggregate nodes, not people). Missing files just leave their kind out.
    const d = await M.data.loadAll({ orgs: 'nonprofits/orgs/index.json', ents: 'network/entities.json', reports: 'audits/reports/reports.json', measures: 'performance/measures/measures.json' }, { optional: true });
    const items = [], smp = (dash) => M.app.modSource(dash) === 'sample';
    (M.SITE.departments || []).forEach((x) => items.push({ kind: 'Department', label: x.name, sub: x.short && x.short !== x.name ? x.short : x.id, sample: !!x.sample, patch: { view: 'dept', id: x.id }, key: `${x.name} ${x.short || ''} ${x.id}`.toLowerCase() }));
    if (d.orgs) d.orgs.orgs.forEach((o) => items.push({ kind: 'Nonprofit', label: o.name, sub: o.ein || '', sample: smp('np'), patch: { view: 'org', id: o.id }, key: `${o.name} ${o.ein || ''}`.toLowerCase() }));
    if (d.ents) d.ents.entities.filter((e) => e.type !== 'individuals' && e.type !== 'department' && !(e.type === 'nonprofit' && e.nonprofit_org && d.orgs)).forEach((e) => items.push({ kind: e.type === 'official' ? 'Official' : e.type === 'committee' ? 'Committee' : e.type === 'lobbyist' ? 'Lobbyist firm' : e.type === 'contractor' ? 'Contractor' : e.type === 'nonprofit' ? 'Nonprofit' : 'Organization', label: e.name, sub: e.office || e.sector || '', sample: smp('nw'), patch: e.type === 'official' ? { view: 'official', id: e.id } : e.type === 'committee' && e.official ? { view: 'official', id: e.official } : { view: 'org', id: e.nonprofit_org || e.id }, key: `${e.name} ${e.office || ''}`.toLowerCase() }));
    if (d.reports) d.reports.reports.forEach((r) => items.push({ kind: 'Audit report', label: r.title, sub: String(r.date || '').slice(0, 4), sample: smp('au'), patch: { view: 'report', id: r.id }, key: `${r.title} ${r.date} ${(r.depts || []).join(' ')}`.toLowerCase() }));
    if (d.measures) d.measures.measures.forEach((m) => items.push({ kind: 'Performance measure', label: m.name, sub: m.dept, sample: smp('pf'), patch: { view: 'dept', id: m.dept }, key: `${m.name} ${m.dept}`.toLowerCase() }));
    Object.values(M.views).filter((v) => v.dash !== 'site').forEach((v) => items.push({ kind: 'Dashboard view', label: v.title, sub: M.dashes[v.dash].short, patch: { view: v.id }, key: `${v.title} ${v.what || ''} ${M.dashes[v.dash].title}`.toLowerCase() }));
    INDEX = items; return items;
  }
  /** Scoring: prefix of the label (3) > substring of the label (2) > substring of the key (1); every term must match. */
  async function query(q) {
    const items = await buildIndex(), terms = q.toLowerCase().split(/\s+/).filter(Boolean);
    if (!terms.length) return [];
    return items.map((it) => { let score = 0; const lab = it.label.toLowerCase(); for (const t of terms) { if (lab.startsWith(t) || lab.includes(' ' + t)) score += 3; else if (lab.includes(t)) score += 2; else if (it.key.includes(t)) score += 1; else return null; } return { it, score }; }).filter(Boolean).sort((a, b) => b.score - a.score || a.it.label.length - b.it.label.length || a.it.label.localeCompare(b.it.label)).map((x) => x.it);
  }
  M.search = { query, buildIndex };

  // ---------------------------------------------------------------- landing page
  M.views.home = {
    id: 'home', dash: 'site', title: 'SF City Monitor', kicker: 'San Francisco government, in public data', filters: [], headline: false,
    what: 'Four dashboards that follow the money and the results: payments to nonprofits, budgets against outcomes, audit recommendations, and the network of donors, officials, lobbyists and contractors. Every number traces to a public dataset; every view says how much data is behind it.',
    files: { orgs: 'nonprofits/orgs/index.json', reports: 'audits/reports/reports.json' }, optional: true, allSources: true,
    render(ctx) {
      const m = ctx.metas;
      const cards = ctx.h('div', 'dash-cards col-12', ctx.grid);
      const kp = (label, value) => ({ label, value });
      const c_ = (mm, k) => (mm && mm.counts ? mm.counts[k] : null);
      const K = {
        np: m.np && [kp('organizations', fmt.int(c_(m.np, 'organizations'))), kp('paid, all years', fmt.money(c_(m.np, 'total_paid_all_years'))), kp('monitoring results', fmt.int(c_(m.np, 'monitoring_results')))],
        pf: m.pf && [kp('departments', fmt.int(c_(m.pf, 'departments') != null ? c_(m.pf, 'departments') : m.pf.dimensions.dept.values.length)), kp('measures tracked', fmt.int(c_(m.pf, 'measures') != null ? c_(m.pf, 'measures') : c_(m.pf, 'measures_current'))), kp('fiscal years', `${m.pf.fiscal_years.min}–${m.pf.fiscal_years.max}`)],
        au: m.au && [kp('recommendations', fmt.int(c_(m.au, 'recommendations'))), kp('reports', fmt.int(c_(m.au, 'reports'))), kp('years', `${m.au.years.min}–${m.au.years.max}`)],
        nw: m.nw && [kp('entities', fmt.int(c_(m.nw, 'entities'))), kp('flows', fmt.int(c_(m.nw, 'flows'))), kp('individuals aggregated', fmt.int(c_(m.nw, 'individuals_aggregated')))],
      };
      Object.values(M.dashes).forEach((d) => {
        const c = ctx.h('a', 'card dash-card', cards); c.href = M.state.serialise(Object.assign({}, M.state.DEFAULTS, { view: d.views[0] }));
        const top = ctx.h('div', 'num', c, `Dashboard ${d.num}`); if (ctx.isSample(d.id)) { top.appendChild(document.createTextNode(' ')); ctx.h('span', 'badge badge-sample', top, 'sample data'); }
        ctx.h('h2', '', c, d.title); ctx.h('p', '', c, d.what);
        const k = ctx.h('div', 'kpis', c); (K[d.id] || [kp('not available yet', '–')]).forEach((x) => { const s = ctx.h('div', 'kpi', k); ctx.h('b', '', s, x.value); ctx.h('span', '', s, x.label); });
        const vs = ctx.h('div', 'views', c); d.views.forEach((id) => ctx.h('span', '', vs, M.views[id].nav || M.views[id].title));
        c.addEventListener('click', (e) => { e.preventDefault(); M.state.set({ view: d.views[0], id: null }); });
      });
      // example cross-links use real ids from the loaded data (largest organization, latest report, largest department)
      const exOrg = ctx.data.orgs ? ctx.data.orgs.orgs.slice().sort((a, b) => (b.city_total || 0) - (a.city_total || 0))[0] : null;
      const exRep = ctx.data.reports ? ctx.data.reports.reports.slice().sort((a, b) => String(b.date).localeCompare(String(a.date)))[0] : null;
      const exDept = (ctx.site.departments || []).find((x) => x.id === 'DPH') || (ctx.site.departments || [])[0];
      const x = ctx.h('div', 'col-12', ctx.grid); ctx.h('h2', 'section-title', x, 'How the dashboards connect');
      const cross = ctx.h('div', 'cross', x);
      const item = (title, text, link) => { const it = ctx.h('div', 'cross-item', cross); ctx.h('b', '', it, title); it.appendChild(document.createTextNode(text + ' ')); it.appendChild(link); };
      item('An organization’s profile', 'shows its city money, 990 finances, monitoring results, the audit findings about the departments that fund it, and its network connections.', exOrg ? ctx.link(`Example: ${exOrg.name} →`, { view: 'org', id: exOrg.id }) : ctx.h('span', 'muted', null, 'Not available yet.'));
      item('A department scorecard', 'shows spending, staffing, measures, open audit recommendations, nonprofit spending and lobbying of that department.', exDept ? ctx.link(`Example: ${exDept.name} →`, { view: 'dept', id: exDept.id }) : ctx.h('span', 'muted', null, 'Not available yet.'));
      item('A report page', 'lists each recommendation with the department’s response and current status, and links to the department scorecards.', exRep ? ctx.link(`Example: ${exRep.title} →`, { view: 'report', id: exRep.id }) : ctx.h('span', 'muted', null, 'Not available yet.'));
      const y = ctx.h('div', 'col-12', ctx.grid); ctx.h('h2', 'section-title', y, 'How to read this site');
      const rules = ctx.h('div', 'cross', y);
      [['Filters that apply', 'A filter appears on a view only if it applies to every chart and table on it. If a filter is missing, the bar says so and why.'], ['How much data', 'Every page carries a data strip: records matched by the current filters, the source datasets with row counts and as-of dates, and the files loaded.'], ['Unusual is not improper', 'The site names organizations and officials in their public roles, never private individuals. It distinguishes patterns worth checking from findings, cites the rule beside any “appears to warrant review”, and shows base rates so coincidences are not overread.']].forEach(([t, s]) => { const it = ctx.h('div', 'cross-item', rules); ctx.h('b', '', it, t); it.appendChild(document.createTextNode(s)); });
      const z = ctx.h('div', 'col-12', ctx.grid); ctx.h('h2', 'section-title', z, 'Search'); const p = ctx.h('p', 'view-what', z); p.appendChild(document.createTextNode('Type an organization, department, report, official, lobbyist or measure in the search box above (or press /). ')); p.appendChild(ctx.link('Methods and data →', { view: 'methods' }));
      Object.values(M.dashes).forEach((d) => { const mm = m[d.id]; ctx.feed(`${d.short}: source datasets${ctx.isSample(d.id) ? ' (sample)' : ''}`, mm ? (mm.sources || []).length : 0, null); });
    },
  };

  // ---------------------------------------------------------------- search results
  M.views.search = {
    id: 'search', dash: 'site', title: 'Search', kicker: 'Search', filters: [], headline: false, optional: true, files: { orgs: 'nonprofits/orgs/index.json', ents: 'network/entities.json', reports: 'audits/reports/reports.json', measures: 'performance/measures/measures.json' },
    render(ctx) {
      const q = ctx.state.q || '';
      document.querySelector('.view-title').textContent = q ? `Results for “${q}”` : 'Search';
      const box = ctx.h('div', 'results col-12', ctx.grid);
      if (!q) { ctx.h('p', 'view-what', box, 'Type in the search box above and press Enter. Search covers organizations, departments, audit reports, officials and committees, lobbyist firms, contractors, performance measures and dashboard views.'); return; }
      return query(q).then((hits) => {
        ctx.feed('search hits', hits.length, INDEX ? INDEX.length : null);
        if (!hits.length) { ctx.empty(box, 'No results', 'Try a shorter word or a department abbreviation.'); return; }
        const ORDER = ['Department', 'Nonprofit', 'Contractor', 'Official', 'Committee', 'Lobbyist firm', 'Organization', 'Audit report', 'Performance measure', 'Dashboard view'];
        const groups = [...st_.group(hits, (x) => x.kind).entries()].sort((a, b) => ORDER.indexOf(a[0]) - ORDER.indexOf(b[0]));
        for (const [kind, items] of groups) { const g = ctx.h('div', '', box); ctx.h('h2', '', g, `${kind} (${items.length})`); items.slice(0, 25).forEach((it) => { const r = ctx.h('div', 'result', g); const l = ctx.h('div', '', r); l.appendChild(ctx.link(it.label, it.patch)); if (it.sample) { l.appendChild(document.createTextNode(' ')); ctx.h('span', 'badge badge-sample', l, 'sample'); } if (it.sub) ctx.h('span', 'sub', l, it.sub); }); if (items.length > 25) ctx.h('p', 'muted', g, `${items.length - 25} more; refine the search to narrow them.`); }
      });
    },
  };

  // ---------------------------------------------------------------- methods
  M.views.methods = {
    id: 'methods', dash: 'site', title: 'Methods and data', kicker: 'Methods', filters: [], headline: false,
    what: 'How the numbers were made, the rules behind every score and tag, and every file the site loads with its validation status.',
    files: { links: 'performance/measures/cost_links.json' }, optional: true, allSources: true,
    render(ctx) {
      const m = ctx.metas, box = ctx.h('div', 'methods col-12', ctx.grid);
      const h2 = (t) => ctx.h('h2', '', box, t), p = (t) => ctx.h('p', '', box, t);
      const table = (head, rows) => { const t = ctx.h('table', '', box); const tr = ctx.h('tr', '', ctx.h('thead', '', t)); head.forEach((x) => { const th = ctx.h('th', '', tr, x); th.scope = 'col'; }); const tb = ctx.h('tbody', '', t); rows.forEach((r) => { const row = ctx.h('tr', '', tb); r.forEach((x) => { const td = ctx.h('td', '', row); if (x instanceof Node) td.appendChild(x); else td.textContent = x == null ? '–' : String(x); }); }); return t; };
      h2('1. What is real and what is sample');
      p('Each dashboard reads its module’s export in <module>/data/site/. Until a module publishes a meta.json that passes the data contract and says "sample": false, that dashboard shows the design sample data instead, with a banner on every view. Real and sample data are never mixed within a dashboard.');
      table(['Dashboard', 'Data in use', 'Why', 'As of'], Object.values(M.dashes).map((d) => { const me = M.data.manifest.modules[d.id] || {}; return [d.title, me.source === 'real' ? 'published export' : 'synthetic sample', me.source === 'real' ? 'meta.json passes the contract with "sample": false' : me.reason, me.as_of]; }));
      h2('2. Sources'); p('Every dataset used, with the rows used against the rows published and the as-of date of the copy loaded. Where a dataset ID is shown it is a data.sf.gov resource; otherwise it is a document set the pipeline extracted.');
      let n = 0; const srows = [];
      Object.values(M.dashes).forEach((d) => ((m[d.id] || {}).sources || []).forEach((s) => { n++; const cell = document.createDocumentFragment(); const a = s.url ? ctx.h('a', '', cell, s.name) : ctx.h('span', '', cell, s.name); if (s.url) { a.href = s.url; a.target = '_blank'; a.rel = 'noopener'; } if (s.id) { cell.appendChild(document.createTextNode(' ')); ctx.h('code', '', cell, s.id); } srows.push([d.short + (ctx.isSample(d.id) ? ' (sample)' : ''), cell, s.publisher, `${fmt.int(s.rows_used)} / ${fmt.int(s.rows)}`, s.as_of ? String(s.as_of).replace(/-/g, '\u2011') : '–', s.note || '']); }));
      table(['Dashboard', 'Dataset', 'Publisher', 'Rows used / total', 'As of', 'Notes'], srows);
      h2('3. Dollars');
      Object.values(M.dashes).filter((d) => m[d.id] && m[d.id].deflator).forEach((d) => p(`${d.title}: real dollars deflate each fiscal year with ${m[d.id].deflator.source || 'the module’s deflator'} to FY${m[d.id].deflator.base_fy} (real = nominal ÷ index). Nominal is what was paid.`));
      if (m.pf && m.pf.population) p(`Per-resident figures divide by ${m.pf.population.source || 'the population series in performance/meta.json'}. Every dollar view carries the Real/Nominal switch, and the live sentences say which is in use.`);
      h2('4. Filters that apply'); p('A view lists the filters it supports; the filter bar renders exactly those and names the missing ones with a reason. Every card on a view is computed from the same filtered records, and each view registers the record counts it filtered so the data strip can prove the filters were applied. The self-test (?selftest=1) sets every declared filter on every view and checks that the numbers and the strip change; a view that declares a filter but registers no counts logs a [filters] warning.');
      h2('5. Small samples'); p(`Groups below each module’s small-n threshold (${Object.values(M.dashes).map((d) => `${d.short.toLowerCase()} ${m[d.id] ? m[d.id].small_n : '–'}`).join(', ')}) are greyed and italic in charts, parenthesised in heat grids, and replaced by a fallback sentence (“Too few records match…”) in the live commentary.`);
      h2('6. Audit status scale'); p('One five-step scale: implemented, in progress, open (not started), department will not implement, closed without implementation. Each body’s own vocabulary is mapped onto it as follows.');
      const sm = (m.au && m.au.status_mapping) || {}; const bodies = Object.keys(sm);
      if (bodies.length && m.au) table(['Shared term', ...bodies.map((b) => ((m.au.dimensions.source.values.find((x) => x.id === b) || {}).short || b.toUpperCase()) + ' term')], m.au.dimensions.status.values.map((s) => [s.label, ...bodies.map((b) => sm[b][s.id] || '–')]));
      h2('7. Consequence score (audits)'); p((m.au && m.au.consequence_rule) || 'Score = priority (high 6, medium 4, low 2) + dollars at stake (2 if above $5M, 1 if any) + 1 if open more than three years + 1 if it repeats an earlier recommendation, capped at 10. Each score carries its reason. It is a reading aid, not an audit judgment.');
      h2('8. Network fairness rules');
      if (m.nw) { p(m.nw.fairness.individuals); p(m.nw.fairness.timing + ' ' + m.nw.fairness.review); p('The site prints “appears to warrant review” only next to the rule it refers to and the recorded reason; a record without a reason is shown as a pattern. Base rates (the share expected by chance) sit beside observed rates on the ban-window view.'); (m.nw.rules || []).forEach((r) => { const b = ctx.h('div', 'rule', box); ctx.h('b', '', b, r.short + '. '); b.appendChild(document.createTextNode(r.text)); ctx.h('span', 'cite', b, r.cite); if (r.verify) ctx.h('span', 'verify', b, 'To verify: ' + r.verify); }); }
      if (ctx.data.links && ctx.data.links.links) { h2('9. Cost-per-unit links (performance)'); p('Program-to-measure links behind the cost-per-outcome view; each is the analyst’s judgment.'); table(['Measure', 'Numerator', 'Denominator', 'Rationale', 'Confidence'], ctx.data.links.links.map((l) => [l.measure, l.numerator, l.denominator, l.rationale, l.confidence != null ? fmt.pct(l.confidence) : '–'])); }
      h2(ctx.data.links ? '10. Files' : '9. Files'); p('Every file the site can load, its size, and whether it passed the data contract when the bundle was built (python3 site/tools/bundle.py).');
      let tot = 0, cnt = 0; const frows = [];
      Object.values(M.dashes).forEach((d) => { const me = M.data.manifest.modules[d.id]; if (!me) return; Object.entries(me.files).forEach(([path, f]) => { cnt++; tot += f.bytes || 0; const c = document.createDocumentFragment(); ctx.h('code', '', c, path); if (f.sample) { c.appendChild(document.createTextNode(' ')); ctx.h('span', 'badge badge-sample', c, 'sample'); } frows.push([c, f.status === 'ok' ? 'passes' : f.status === 'missing' ? (f.optional ? 'optional, absent' : 'missing') : 'fails: ' + (f.errors || []).slice(0, 2).join('; '), f.rows ? fmt.int(f.rows) : '–', f.bytes ? fmt.bytes(f.bytes) : '–', (f.warnings || []).length ? `${f.warnings.length} warning${f.warnings.length > 1 ? 's' : ''}` : '']); }); });
      table(['File', 'Contract check', 'Rows', 'Size', 'Notes'], frows);
      ctx.feed('data files', cnt, null); p(`Total ${fmt.bytes(tot)} across ${cnt} files. Bundle built ${M.data.manifest.generated_at}.`);
    },
  };
})();
