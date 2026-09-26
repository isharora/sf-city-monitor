/* views-site.js - landing page, search (index + results), methods. */
(function () {
  const M = window.SFCM;
  const C = M.charts, fmt = M.stats.fmt, st_ = M.stats;

  // ---------------------------------------------------------------- search index
  let INDEX = null;
  async function buildIndex() {
    if (INDEX) return INDEX;
    const d = await M.data.loadAll({ orgs: 'nonprofits/orgs/index.json', ents: 'network/entities.json', reports: 'audits/reports/reports.json', measures: 'performance/measures/measures.json' });
    const items = [];
    (M.SITE.departments || []).forEach((x) => items.push({ kind: 'Department', label: x.name, sub: x.short, patch: { view: 'dept', id: x.id }, key: `${x.name} ${x.short} ${x.id}`.toLowerCase() }));
    d.orgs.orgs.forEach((o) => items.push({ kind: 'Nonprofit', label: o.name, sub: o.ein, patch: { view: 'org', id: o.id }, key: `${o.name} ${o.ein}`.toLowerCase() }));
    d.ents.entities.filter((e) => e.type !== 'individuals' && e.type !== 'nonprofit' && e.type !== 'department').forEach((e) => items.push({ kind: e.type === 'official' ? 'Official' : e.type === 'committee' ? 'Committee' : e.type === 'lobbyist' ? 'Lobbyist firm' : e.type === 'contractor' ? 'Contractor' : 'Organization', label: e.name, sub: e.office || e.sector || '', patch: e.type === 'official' ? { view: 'official', id: e.id } : e.type === 'committee' ? { view: 'official', id: e.official } : { view: 'org', id: e.id }, key: `${e.name} ${e.office || ''}`.toLowerCase() }));
    d.reports.reports.forEach((r) => items.push({ kind: 'Audit report', label: r.title, sub: r.date.slice(0, 4), patch: { view: 'report', id: r.id }, key: `${r.title} ${r.date}`.toLowerCase() }));
    d.measures.measures.forEach((m) => items.push({ kind: 'Performance measure', label: m.name, sub: m.dept, patch: { view: 'dept', id: m.dept }, key: `${m.name} ${m.dept}`.toLowerCase() }));
    Object.values(M.views).filter((v) => v.dash !== 'site').forEach((v) => items.push({ kind: 'Dashboard view', label: v.title, sub: M.dashes[v.dash].short, patch: { view: v.id }, key: `${v.title} ${v.what || ''} ${M.dashes[v.dash].title}`.toLowerCase() }));
    INDEX = items; return items;
  }
  async function query(q) {
    const items = await buildIndex(), terms = q.toLowerCase().split(/\s+/).filter(Boolean);
    return items.map((it) => { let score = 0; for (const t of terms) { if (it.label.toLowerCase().startsWith(t)) score += 3; else if (it.label.toLowerCase().includes(t)) score += 2; else if (it.key.includes(t)) score += 1; else return null; } return { it, score }; }).filter(Boolean).sort((a, b) => b.score - a.score || a.it.label.localeCompare(b.it.label)).map((x) => x.it);
  }
  M.search = { query, buildIndex };

  // ---------------------------------------------------------------- landing page
  M.views.home = {
    id: 'home', dash: 'site', title: 'SF City Monitor', kicker: 'San Francisco government, in public data', filters: [], headline: false,
    what: 'Four dashboards that follow the money and the results: payments to nonprofits, budgets against outcomes, audit recommendations, and the network of donors, officials, lobbyists and contractors. Every number traces to a public dataset; every view says how much data is behind it.',
    files: {},
    render(ctx) {
      const m = ctx.metas;
      const cards = ctx.h('div', 'dash-cards col-12', ctx.grid);
      const kp = (label, value) => ({ label, value });
      const K = {
        np: [kp('organizations', fmt.int(m.np.counts.organizations)), kp('paid, all years', fmt.money(m.np.counts.total_paid_all_years)), kp('monitoring results', fmt.int(m.np.counts.monitoring_results))],
        pf: [kp('departments', fmt.int(m.pf.counts.departments)), kp('measures tracked', fmt.int(m.pf.counts.measures)), kp('fiscal years', `${m.pf.fiscal_years.min}–${m.pf.fiscal_years.max}`)],
        au: [kp('recommendations', fmt.int(m.au.counts.recommendations)), kp('reports', fmt.int(m.au.counts.reports)), kp('years', `${m.au.years.min}–${m.au.years.max}`)],
        nw: [kp('entities', fmt.int(m.nw.counts.entities)), kp('flows', fmt.int(m.nw.counts.flows)), kp('individuals aggregated', fmt.int(m.nw.counts.individuals_aggregated))],
      };
      Object.values(M.dashes).forEach((d) => {
        const c = ctx.h('button', 'card dash-card', cards); c.type = 'button';
        ctx.h('div', 'num', c, `Dashboard ${d.num}`); ctx.h('h2', '', c, d.title); ctx.h('p', '', c, d.what);
        const k = ctx.h('div', 'kpis', c); K[d.id].forEach((x) => { const s = ctx.h('div', 'kpi', k); ctx.h('b', '', s, x.value); ctx.h('span', '', s, x.label); });
        const vs = ctx.h('div', 'views', c); d.views.forEach((id) => ctx.h('span', '', vs, M.views[id].nav || M.views[id].title));
        c.addEventListener('click', () => M.state.set({ view: d.views[0] }));
      });
      const x = ctx.h('div', 'col-12', ctx.grid); ctx.h('h2', 'section-title', x, 'How the dashboards connect');
      const cross = ctx.h('div', 'cross', x);
      const item = (title, text, link) => { const it = ctx.h('div', 'cross-item', cross); ctx.h('b', '', it, title); it.appendChild(document.createTextNode(text + ' ')); it.appendChild(link); };
      item('An organization’s profile', 'shows its city money, 990 finances, monitoring results, the audit findings about the departments that fund it, and its network connections.', ctx.link('Example organization →', { view: 'org', id: 'org-001' }));
      item('A department scorecard', 'shows spending, staffing, measures, open audit recommendations, nonprofit spending and lobbying of that department.', ctx.link('Example: Public Health →', { view: 'dept', id: 'DPH' }));
      item('A report page', 'lists each recommendation with the department’s response and current status, and links to the department scorecards.', ctx.link('Example report →', { view: 'report', id: 'R-0001' }));
      const y = ctx.h('div', 'col-12', ctx.grid); ctx.h('h2', 'section-title', y, 'How to read this site');
      const rules = ctx.h('div', 'cross', y);
      [['Filters that apply', 'A filter appears on a view only if it applies to every chart and table on it. If a filter is missing, the bar says so and why.'], ['How much data', 'Every page carries a data strip: records matched by the current filters, the source datasets with row counts and as-of dates, and the files loaded.'], ['Unusual is not improper', 'The site names organizations and officials in their public roles, never private individuals. It distinguishes patterns worth checking from findings, cites the rule beside any “appears to warrant review”, and shows base rates so coincidences are not overread.']].forEach(([t, s]) => { const it = ctx.h('div', 'cross-item', rules); ctx.h('b', '', it, t); it.appendChild(document.createTextNode(s)); });
      const z = ctx.h('div', 'col-12', ctx.grid); ctx.h('h2', 'section-title', z, 'Search'); const p = ctx.h('p', 'view-what', z); p.appendChild(document.createTextNode('Type an organization, department, report, official, lobbyist or measure in the search box above (or press /). ')); p.appendChild(ctx.link('Methods and data →', { view: 'methods' }));
      Object.values(M.dashes).forEach((d) => { const mm = m[d.id]; ctx.feed(`${d.short}: source datasets`, mm.sources.length, null); });
    },
  };

  // ---------------------------------------------------------------- search results
  M.views.search = {
    id: 'search', dash: 'site', title: 'Search', kicker: 'Search', filters: [], headline: false, files: {},
    render(ctx) {
      const q = ctx.state.q || '';
      document.querySelector('.view-title').textContent = q ? `Results for “${q}”` : 'Search';
      const box = ctx.h('div', 'results col-12', ctx.grid);
      if (!q) { ctx.h('p', 'view-what', box, 'Type in the search box above and press Enter. Search covers organizations, departments, audit reports, officials and committees, lobbyist firms, contractors, performance measures and dashboard views.'); return; }
      return query(q).then((hits) => {
        ctx.feed('search hits', hits.length, INDEX ? INDEX.length : null);
        if (!hits.length) { ctx.empty(box, 'No results', 'Try a shorter word or a department abbreviation.'); return; }
        const groups = st_.group(hits, (x) => x.kind);
        for (const [kind, items] of groups) { const g = ctx.h('div', '', box); ctx.h('h2', '', g, `${kind} (${items.length})`); items.slice(0, 25).forEach((it) => { const r = ctx.h('div', 'result', g); const l = ctx.h('div', '', r); l.appendChild(ctx.link(it.label, it.patch)); if (it.sub) ctx.h('span', 'sub', l, it.sub); }); }
      });
    },
  };

  // ---------------------------------------------------------------- methods
  M.views.methods = {
    id: 'methods', dash: 'site', title: 'Methods and data', kicker: 'Methods', filters: [], headline: false,
    what: 'How the numbers were made, the rules behind every score and tag, ranked caveats, and every file the site loads.',
    files: {},
    render(ctx) {
      const m = ctx.metas, box = ctx.h('div', 'methods col-12', ctx.grid);
      const h2 = (t) => ctx.h('h2', '', box, t), p = (t) => ctx.h('p', '', box, t);
      h2('1. Sources'); p('Every dataset used, with the rows used against the rows published and the as-of date of the copy loaded. Where a dataset ID is shown it is a data.sf.gov resource; otherwise it is a document set the pipeline extracted.');
      const t = ctx.h('table', '', box); const tr = ctx.h('tr', '', ctx.h('thead', '', t)); ['Dashboard', 'Dataset', 'Publisher', 'Rows used / total', 'As of', 'Notes'].forEach((x) => ctx.h('th', '', tr, x));
      const tb = ctx.h('tbody', '', t); let n = 0;
      Object.values(M.dashes).forEach((d) => (m[d.id].sources || []).forEach((s) => { n++; const r = ctx.h('tr', '', tb); ctx.h('td', '', r, d.short); const td = ctx.h('td', '', r); const a = s.url ? ctx.h('a', '', td, s.name) : ctx.h('span', '', td, s.name); if (s.url) { a.href = s.url; a.target = '_blank'; a.rel = 'noopener'; } if (s.id) ctx.h('code', '', td, s.id).style.marginLeft = '6px'; ctx.h('td', '', r, s.publisher); ctx.h('td', '', r, `${fmt.int(s.rows_used)} / ${fmt.int(s.rows)}`); ctx.h('td', '', r, s.as_of); ctx.h('td', '', r, s.note || ''); }));
      ctx.feed('source datasets', n, null);
      h2('2. Dollars'); p(`Real dollars deflate each fiscal year with ${m.pf.deflator.source} to FY${m.pf.deflator.base_fy}. Nominal is what was paid. Every dollar view carries the Real/Nominal switch, and the live sentences say which is in use. Per-resident figures divide by ${m.pf.population.source}.`);
      h2('3. Filters that apply'); p('A view lists the filters it supports; the filter bar renders exactly those and names the missing ones with a reason. Each view registers the record counts it filtered so the data strip can prove the filters were applied; in development, a view that declares a filter but registers no filtered counts logs a warning.');
      h2('4. Small samples'); p(`Groups below each module’s small-n threshold (nonprofits ${m.np.small_n}, performance ${m.pf.small_n}, audits ${m.au.small_n}, network ${m.nw.small_n}) are greyed and italic in charts and replaced by a fallback in live sentences.`);
      h2('5. Audit status scale'); p('One five-step scale: implemented, in progress, open (not started), department will not implement, closed without implementation. Civil Grand Jury responses are mapped from Penal Code 933 terms as follows.');
      const t2 = ctx.h('table', '', box); const tr2 = ctx.h('tr', '', ctx.h('thead', '', t2)); ['Shared term', 'Civil Grand Jury term'].forEach((x) => ctx.h('th', '', tr2, x)); const tb2 = ctx.h('tbody', '', t2); Object.entries(m.au.status_mapping.cgj).forEach(([k, v]) => { const r = ctx.h('tr', '', tb2); ctx.h('td', '', r, k); ctx.h('td', '', r, v); });
      h2('6. Consequence score (audits)'); p('Score = priority (high 6, medium 4, low 2) + dollars at stake (2 if above $5M, 1 if any) + 1 if open more than three years + 1 if it repeats an earlier recommendation, capped at 10. Each score carries its reason. It is a reading aid, not an audit judgment.');
      h2('7. Network fairness rules'); p(m.nw.fairness.individuals); p(m.nw.fairness.timing + ' ' + m.nw.fairness.review);
      (m.nw.rules || []).forEach((r) => { const b = ctx.h('div', 'rule', box); ctx.h('b', '', b, r.short + '. '); b.appendChild(document.createTextNode(r.text)); ctx.h('span', 'cite', b, r.cite); if (r.verify) ctx.h('span', 'verify', b, 'To verify: ' + r.verify); });
      h2('8. Files'); p('Every JSON file the site can load, with its size. Production replaces the sample tree with the data agents’ exports following the DATA_CONTRACT files.');
      const t3 = ctx.h('table', '', box); const tr3 = ctx.h('tr', '', ctx.h('thead', '', t3)); ['File', 'Size'].forEach((x) => ctx.h('th', '', tr3, x)); const tb3 = ctx.h('tbody', '', t3); let tot = 0, cnt = 0;
      Object.values(M.dashes).forEach((d) => Object.entries(m[d.id].files || {}).forEach(([path, f]) => { cnt++; tot += f.bytes; const r = ctx.h('tr', '', tb3); ctx.h('code', '', ctx.h('td', '', r), path); ctx.h('td', '', r, fmt.bytes(f.bytes)); }));
      ctx.feed('data files', cnt, null); p(`Total ${fmt.bytes(tot)} uncompressed across ${cnt} files (sample).`);
    },
  };
})();
