/* views-entities.js - entity pages: organization profile, department scorecard, report page,
   official profile. No filter bar (profiles show all years); every section cross-links. */
(function () {
  const M = window.SFCM;
  const C = M.charts, fmt = M.stats.fmt, st_ = M.stats;
  const NOTE = 'Profile pages show all years; filters live in the dashboards.';
  function header(ctx, o) {
    const head = ctx.h('div', 'entity-head', ctx.pre);
    const left = ctx.h('div', '', head);
    const facts = ctx.h('div', 'facts', left); (o.facts || []).forEach(([k, v]) => { const s = ctx.h('span', '', facts); s.appendChild(document.createTextNode(k + ' ')); const b = ctx.h('b', '', s); if (v instanceof Node) b.appendChild(v); else b.textContent = v; });
    const links = ctx.h('div', 'entity-links', head); (o.links || []).forEach((l) => links.appendChild(l));
    return head;
  }
  const section = (ctx, title, small) => { const s = ctx.h('h2', 'section-h col-12', ctx.grid, title); if (small) ctx.h('small', '', s, small); return s; };

  // ---------------------------------------------------------------- organization
  M.views.org = {
    id: 'org', dash: 'site', title: 'Organization profile', kicker: 'Organization profile', filters: [], filterNote: NOTE, headline: false,
    files: { orgs: 'nonprofits/orgs/index.json', pay: 'nonprofits/payments/cells.json', fin: 'nonprofits/finances/form990.json', rev: 'nonprofits/reviews/findings.json', con: 'nonprofits/contracts/contracts.json', recs: 'audits/recs/recs.json', reports: 'audits/reports/reports.json', ents: 'network/entities.json', flows: 'network/flows.json', ban: 'network/analyses/ban_window.json' },
    render(ctx) {
      const id = ctx.state.id, ents = new Map(ctx.data.ents.entities.map((e) => [e.id, e]));
      const org = ctx.data.orgs.orgs.find((o) => o.id === id) || (ents.get(id) && ents.get(id).nonprofit_org ? ctx.data.orgs.orgs.find((o) => o.id === ents.get(id).nonprofit_org) : null);
      const ent = org ? (org.network_id ? ents.get(org.network_id) : null) : ents.get(id);
      if (!org && !ent) { ctx.empty(ctx.grid, 'Unknown organization', `No organization or entity with id ${id}.`); return; }
      const name = org ? org.name : ent.name;
      document.querySelector('.view-title').textContent = name;
      const npm = ctx.metas.np, aum = ctx.metas.au, nwm = ctx.metas.nw;
      const areaLabel = (a) => (npm.dimensions.area.values.find((x) => x.id === a) || {}).label || a;
      const facts = [];
      if (org) facts.push(['Service area', areaLabel(org.area)], ['Size', (npm.dimensions.size_band.values.find((x) => x.id === org.size_band) || {}).label], ['EIN', org.ein], ['Funded by', org.depts.map((d) => ctx.link(ctx.deptShort(d), { view: 'dept', id: d })).reduce((f, a, i) => { if (i) f.appendChild(document.createTextNode(', ')); f.appendChild(a); return f; }, document.createDocumentFragment())], ['990 match', `${org.match.method}, ${fmt.pct(org.match.confidence)} confidence`]);
      else facts.push(['Type', (nwm.dimensions.etype.values.find((x) => x.id === ent.type) || {}).label], ['Sector', ent.sector || '–'], ['Disclosed principals', ent.principals_disclosed != null ? `${ent.principals_disclosed} (counted, not named)` : '–']);
      header(ctx, { facts, links: [ctx.h('span', 'badge badge-sample', null, 'Synthetic sample entity'), ...(org ? [ctx.link('See in Follow the nonprofit money →', { view: 'np-orgs', area: [org.area] })] : []), ...(ent ? [ctx.link('See in the network graph →', { view: 'nw-graph', v: { focus: ent.id } })] : [])] });
      if (org) {
        const pay = ctx.data.pay.cells.filter((c) => c.org === org.id), years = [...new Set(pay.map((c) => c.fy))].sort(); ctx.feed('payment records', pay.length, ctx.data.pay.cells.length);
        section(ctx, 'City money', `${fmt.money(st_.sum(pay, 'amt'))} nominal, ${fmt.range(years[0], years[years.length - 1], 'FY')}`);
        ctx.card({ title: 'Payments by fiscal year and department', sub: 'Nominal dollars', span: 7, render(el) {
          return C.stackedBars(el, { categories: years, catFormat: (y) => `FY${String(y).slice(2)}`, series: org.depts.map((d, i) => ({ id: d, label: ctx.deptName(d), color: `var(--series-${i + 1})`, values: years.map((y) => st_.sum(pay.filter((c) => c.fy === y && c.dept === d), 'amt')) })), yTitle: 'Dollars', aria: 'Payments by year' });
        } });
        const fin = ctx.data.fin.rows.filter((f) => f.org === org.id).sort((a, b) => a.fy - b.fy); ctx.feed('Form 990 years', fin.length, null);
        ctx.card({ title: 'Finances (IRS Form 990)', sub: 'City share = city payments ÷ total revenue (approximate: tax year vs fiscal year)', span: 5, render(el) {
          if (!fin.length) return ctx.empty(el, 'No Form 990 matched', 'The organization may file a 990-N or be part of a larger filer.');
          return C.dataTable(el, { rows: fin, search: false, pageSize: 12, sort: 'fy', dir: 'desc', cols: [{ key: 'fy', label: 'FY', num: true }, { key: 'total_revenue', label: 'Revenue', num: true, format: (v) => fmt.money(v) }, { key: 'share', label: 'City share', num: true, sortVal: (f) => st_.sum(pay.filter((c) => c.fy === f.fy), 'amt') / f.total_revenue, text: (f) => fmt.pct(st_.sum(pay.filter((c) => c.fy === f.fy), 'amt') / f.total_revenue) }, { key: 'months_reserves', label: 'Reserves (mo)', num: true, format: (v) => fmt.num(v, 1) }, { key: 'exec_comp', label: 'Top exec pay', num: true, format: (v, f) => `${fmt.money(v)} (${f.exec_title})` }] });
        }, note: 'Executive pay is reported for the highest-paid officer, a public figure in the organization’s filing; no other employee is named.' });
        const con = ctx.data.con.contracts.filter((c) => c.org === org.id); ctx.feed('contracts', con.length, null);
        section(ctx, 'Contracts', `${con.length} contracts, ${con.filter((c) => c.amendments.length).length} amended`);
        ctx.card({ title: 'Contracts', sub: 'Original vs latest agreed amount', span: 12, render(el) {
          if (!con.length) return ctx.empty(el, 'No contracts in the data');
          return C.dataTable(el, { rows: con, search: false, pageSize: 10, sort: 'agreed', cols: [{ key: 'title', label: 'Contract' }, { key: 'dept', label: 'Department', text: (c) => ctx.deptName(c.dept), render: (td, c) => td.appendChild(ctx.link(ctx.deptName(c.dept), { view: 'dept', id: c.dept })) }, { key: 'start', label: 'Term', text: (c) => `${c.start.slice(0, 4)}–${c.end.slice(0, 4)}` }, { key: 'original_agreed', label: 'Original', num: true, format: (v) => fmt.money(v) }, { key: 'agreed', label: 'Latest', num: true, format: (v) => fmt.money(v) }, { key: 'consumed', label: 'Spent', num: true, format: (v) => fmt.money(v) }, { key: 'amendments', label: 'Amendments', num: true, sortVal: (c) => c.amendments.length, text: (c) => String(c.amendments.length) }, { key: 'sole_source', label: 'Sole source', text: (c) => (c.sole_source ? 'yes' : '') }] });
        } });
        const rev = ctx.data.rev.rows.filter((r) => r.org === org.id).sort((a, b) => b.fy - a.fy); ctx.feed('monitoring results', rev.length, null);
        section(ctx, 'Controller monitoring results', `${rev.length} reviews`);
        ctx.card({ title: 'Fiscal and compliance monitoring', sub: 'Each result cites the annual report', span: 6, render(el) {
          if (!rev.length) return ctx.empty(el, 'Not in the joint monitoring pool', 'Single-funder grantees are monitored by their department.');
          const ul = ctx.h('ul', 'list', el); rev.forEach((r) => { const li = ctx.h('li', '', ul); const l = ctx.h('span', '', li); l.textContent = `FY${r.fy}: ${(ctx.data.rev.results.find((x) => x.id === r.result) || {}).label}`; ctx.h('span', 'sub', l, (r.categories.join('; ') || 'no findings') + (r.note ? ' · ' + r.note : '')); ctx.h('span', 'sub', li, `${r.report.title}${r.report.page ? ', p. ' + r.report.page : ''}`); });
          return null;
        } });
        const recs = ctx.data.recs.rows.filter((r) => org.depts.includes(r.dept) && (r.topic === 'contracts' || r.status !== 'implemented')).sort((a, b) => b.date_issued.localeCompare(a.date_issued)).slice(0, 8); ctx.feed('related audit recommendations', recs.length, null);
        ctx.card({ title: 'Audit findings about the departments that fund this organization', sub: 'Contracting-related or still open; these are about the department, not the organization', span: 6, render(el) {
          if (!recs.length) return ctx.empty(el, 'No related recommendations');
          const ul = ctx.h('ul', 'list', el); recs.forEach((r) => { const li = ctx.h('li', '', ul); const l = ctx.h('span', '', li); l.appendChild(ctx.link(ctx.deptShort(r.dept), { view: 'dept', id: r.dept })); l.appendChild(document.createTextNode(`: ${r.text}`)); const s = ctx.h('span', 'sub', l); s.appendChild(document.createTextNode(`${fmt.date(r.date_issued)} · `)); s.appendChild(ctx.link((ctx.data.reports.reports.find((x) => x.id === r.report) || {}).title, { view: 'report', id: r.report })); li.appendChild(M.au.statusPill(ctx, { label: (dim, v) => (aum.dimensions[dim].values.find((x) => x.id === v) || {}).label }, r.status)); });
          return null;
        }, note: 'Shown so a reader can see the department context. An audit of a department is not a finding about its grantees.' });
      }
      // network connections (nonprofit with a network id, or a contractor)
      section(ctx, 'Network connections', ent ? 'from the Money network dashboard' : '');
      if (!ent) { ctx.card({ title: 'Not in the network data', sub: 'No contributions, behested payments, lobbying or SFEC-126(f)4 notices link to this organization', span: 12, render(el) { ctx.empty(el, 'No network connections', 'Absence here means no disclosed transaction was found, not that none exists.'); return null; } }); return; }
      const flows = ctx.data.flows.flows.filter((f) => f.from === ent.id || f.to === ent.id || f.client === ent.id || f.behest_of === ent.id); ctx.feed('network flows', flows.length, ctx.data.flows.flows.length);
      const nm = (x) => (ents.get(x) || { name: x }).name, flowLabel = (t) => (nwm.dimensions.flow.values.find((x) => x.id === t) || {}).label || t;
      ctx.fair(nwm.fairness.timing + ' ' + nwm.fairness.individuals);
      ctx.card({ title: 'Flows by type', sub: 'All years', span: 5, render(el) {
        const rows = nwm.dimensions.flow.values.map((t) => ({ label: t.label, value: st_.sum(flows.filter((f) => f.type === t.id), (f) => f.amount || 0), n: flows.filter((f) => f.type === t.id).length, color: M.nw.FLOW_COLOR[t.id] })).filter((r) => r.n);
        if (!rows.length) return ctx.empty(el, 'No flows');
        return C.bars(el, { rows, valueHead: 'Dollars', nHead: 'flows', labelWidth: 190, aria: 'Flows by type' });
      }, note: 'Lobbying contacts have no amount and show as $0 with a count.' });
      const affiliated = [...ents.values()].find((e) => e.affiliated_with === ent.id), banRecs = affiliated ? ctx.data.ban.records.filter((r) => r.contractor === ent.id) : [];
      ctx.card({ title: 'Connections', sub: 'Counterparties, most recent first', span: 7, render(el) {
        if (!flows.length) return ctx.empty(el, 'No flows');
        return C.dataTable(el, { rows: flows.slice().sort((a, b) => b.date.localeCompare(a.date)), search: false, pageSize: 12, sort: 'date', dir: 'desc', cols: [{ key: 'date', label: 'Date', format: (v) => fmt.date(v) }, { key: 'type', label: 'Flow', text: (f) => flowLabel(f.type) }, { key: 'cp', label: 'Counterparty', text: (f) => (f.from === ent.id ? '→ ' + nm(f.to) : '← ' + nm(f.from)), render: (td, f) => { const other = f.from === ent.id ? f.to : f.from, e = ents.get(other); td.appendChild(document.createTextNode(f.from === ent.id ? '→ ' : '← ')); if (e && e.type !== 'individuals') td.appendChild(ctx.link(e.name, e.type === 'official' ? { view: 'official', id: e.id } : e.type === 'department' ? { view: 'dept', id: e.code } : { view: 'org', id: e.nonprofit_org || e.id })); else td.appendChild(document.createTextNode(nm(other))); if (f.behest_of) { td.appendChild(document.createTextNode(' at the behest of ')); td.appendChild(ctx.link(nm(f.behest_of), { view: 'official', id: f.behest_of })); } if (f.flags && f.flags.in_ban_window) { td.appendChild(document.createTextNode(' ')); td.appendChild(ctx.tag('review', 'appears to warrant review · §1.126')); } } }, { key: 'amount', label: 'Amount', num: true, format: (v, f) => (v != null ? fmt.money(v) : `${f.count} contacts`) }] });
      } });
      if (affiliated) ctx.card({ title: 'Contributions by affiliated individuals and the ban window', sub: `${fmt.int(affiliated.count)} individuals, aggregated; ${banRecs.filter((r) => r.covered_official).length} records appear to warrant review`, span: 12, render(el) {
        if (!banRecs.length) return ctx.empty(el, 'No contribution records');
        return C.dotStrip(el, { points: banRecs.map((r) => ({ t: r.days_from_approval, amount: r.amount, label: `→ ${nm(r.committee)}`, color: r.covered_official ? 'var(--div-neg-2)' : r.inside_window ? 'var(--series-2)' : 'var(--neutral-2)', tag: r.covered_official ? 'Appears to warrant review (§1.126). Pattern worth checking, not proof.' : r.inside_window ? 'Inside a window; official not covered' : 'Outside every window', sub: fmt.date(r.date) })), window: [-183, 365], windowLabel: '§1.126 window (approx.)', min: -800, max: 1200, xTitle: 'Days from this contractor’s nearest contract approval', zeroLabel: 'approval', height: 200, aria: 'Ban window strip' });
      }, caveat: 'Attribution of donors to this contractor rests on self-reported employer fields; the Ethics Commission may already have reviewed these records.' });
    },
  };

  // ---------------------------------------------------------------- department scorecard
  M.views.dept = {
    id: 'dept', dash: 'site', title: 'Department scorecard', kicker: 'Department scorecard', filters: [], filterNote: NOTE, headline: false,
    files: { spend: 'performance/spending/cells.json', staff: 'performance/staffing/cells.json', measures: 'performance/measures/measures.json', values: 'performance/measures/values.json', pay: 'nonprofits/payments/cells.json', orgs: 'nonprofits/orgs/index.json', recs: 'audits/recs/recs.json', reports: 'audits/reports/reports.json', ents: 'network/entities.json', flows: 'network/flows.json' },
    render(ctx) {
      const id = ctx.state.id, d = (ctx.site.departments || []).find((x) => x.id === id);
      if (!d) { ctx.empty(ctx.grid, 'Unknown department', `No department with id ${id}.`); return; }
      document.querySelector('.view-title').textContent = d.name;
      const pfm = ctx.metas.pf, aum = ctx.metas.au, defl = pfm.deflator, real = (v, fy) => M.stats.real(v, fy, defl);
      const spend = ctx.data.spend.cells.filter((c) => c.dept === id), years = [...new Set(spend.filter((c) => c.actual != null).map((c) => c.fy))].sort(), y1 = years[years.length - 1];
      const staff = ctx.data.staff.cells.filter((s) => s.dept === id), s1 = staff.find((s) => s.fy === y1) || {};
      const a1 = st_.sum(spend.filter((c) => c.fy === y1), 'actual'), b1 = st_.sum(spend.filter((c) => c.fy === y1), 'budget');
      ctx.feed('spending records', spend.length, ctx.data.spend.cells.length); ctx.feed('staffing records', staff.length, null);
      header(ctx, { facts: [['Group', (pfm.dimensions.group.values.find((g) => g.id === d.group) || {}).label], [`Actual FY${y1}`, fmt.money(a1)], ['vs original budget', fmt.signedPct(b1 ? a1 / b1 - 1 : null, 1)], ['Employees', fmt.int(s1.headcount)], ['Overtime share', fmt.pct(s1.ot_share, 1)]], links: [ctx.h('span', 'badge badge-sample', null, 'Synthetic sample figures'), ctx.link('Budget vs outcomes, this department →', { view: 'pf-spending', dept: [id] }), ctx.link('Audit tracker, this department →', { view: 'au-status', dept: [id] }), ctx.link('Nonprofit money, this department →', { view: 'np-flows', dept: [id] })] });
      section(ctx, 'Spending and staffing');
      ctx.card({ title: 'Actual spending, real and nominal', sub: `Real = FY${defl.base_fy} dollars`, span: 6, render(el) {
        return C.lines(el, { x: years, xFormat: (y) => `FY${String(y).slice(2)}`, series: [{ id: 'real', label: 'Real', color: 'var(--c-real)', values: years.map((y) => st_.sum(spend.filter((c) => c.fy === y), (c) => real(c.actual, y))) }, { id: 'nom', label: 'Nominal', color: 'var(--c-nominal)', dash: true, values: years.map((y) => st_.sum(spend.filter((c) => c.fy === y), 'actual')) }, { id: 'bud', label: 'Original budget (nominal)', color: 'var(--text-muted)', values: years.map((y) => st_.sum(spend.filter((c) => c.fy === y), 'budget')) }], yTitle: 'Dollars', endLabels: false, aria: 'Spending' });
      } });
      ctx.card({ title: 'Headcount and overtime share', sub: 'Distinct employees paid; overtime ÷ (salaries + overtime)', span: 6, render(el) {
        const ys = staff.map((s) => s.fy).sort(); if (!ys.length) return ctx.empty(el, 'No staffing data');
        return C.lines(el, { x: ys, xFormat: (y) => `FY${String(y).slice(2)}`, series: [{ id: 'ot', label: 'Overtime share', color: 'var(--series-3)', values: ys.map((y) => (staff.find((s) => s.fy === y) || {}).ot_share * 100) }], format: (v) => `${fmt.num(v, 1)}%`, yTitle: 'Overtime share (%)', endLabels: false, aria: 'Overtime share' });
      }, note: `Headcount FY${y1}: ${fmt.int(s1.headcount)}; FY${ys0(staff)}: ${fmt.int((staff.find((s) => s.fy === ys0(staff)) || {}).headcount)}. Shown as text, not a second axis.` });
      const ms = ctx.data.measures.measures.filter((m) => m.dept === id), vals = ctx.data.values.rows.filter((v) => ms.some((m) => m.id === v.measure)); ctx.feed('performance measures', ms.length, null);
      section(ctx, 'Performance measures', `${ms.length} measures, ${ms.filter((m) => m.dropped_fy).length} dropped`);
      ctx.card({ title: 'Every measure, latest year', sub: 'Target, actual, met, and how the target moved', span: 12, render(el) {
        const rows = ms.map((m) => { const v = vals.filter((x) => x.measure === m.id).sort((a, b) => b.fy - a.fy)[0]; return { m, v }; }).filter((r) => r.v);
        if (!rows.length) return ctx.empty(el, 'No measures');
        return C.dataTable(el, { rows, search: false, pageSize: 12, sort: 'name', dir: 'asc', cols: [{ key: 'name', label: 'Measure', text: (r) => `${r.m.name} (${r.m.unit}, ${r.m.direction} is better)` }, { key: 'type', label: 'Type', text: (r) => r.m.type }, { key: 'fy', label: 'Latest FY', num: true, sortVal: (r) => r.v.fy, text: (r) => `FY${r.v.fy}` + (r.m.dropped_fy ? ` · dropped FY${r.m.dropped_fy}` : '') }, { key: 'target', label: 'Target', num: true, sortVal: (r) => r.v.target, text: (r) => fmt.num(r.v.target) }, { key: 'actual', label: 'Actual', num: true, sortVal: (r) => r.v.actual, text: (r) => fmt.num(r.v.actual) }, { key: 'met', label: 'Met?', sortVal: (r) => (r.v.met ? 1 : 0), render: (td, r) => td.appendChild(ctx.tag(r.v.met == null ? 'ok' : r.v.met ? 'unusual' : 'review', r.v.met == null ? 'not reported' : r.v.met ? 'met' : 'missed')) }, { key: 'tc', label: 'Target', text: (r) => ({ easier: 'made easier', harder: 'made harder', same: 'unchanged' }[r.v.target_change]) }, { key: 'met_hist', label: 'Met, all years', text: (r) => { const vs = vals.filter((x) => x.measure === r.m.id && x.met != null); return `${vs.filter((x) => x.met).length} of ${vs.length}`; } }] });
      } });
      const recs = ctx.data.recs.rows.filter((r) => r.dept === id), open = recs.filter((r) => r.status === 'open' || r.status === 'in_progress'); ctx.feed('audit recommendations', recs.length, ctx.data.recs.rows.length);
      section(ctx, 'Audits', `${recs.length} recommendations, ${open.length} open or in progress, ${recs.filter((r) => r.repeat_of).length} repeats`);
      ctx.card({ title: 'Status by recommender', sub: 'All years', span: 5, render(el) {
        if (!recs.length) return ctx.empty(el, 'No recommendations');
        const sources = aum.dimensions.source.values, statuses = aum.dimensions.status.values;
        return C.stackedBars(el, { horizontal: true, percent: true, categories: sources.map((s) => s.short), series: statuses.map((s) => ({ id: s.id, label: s.label.replace(/ \(.*/, ''), color: M.au.STATUS_COLOR[s.id], values: sources.map((src) => recs.filter((r) => r.source === src.id && r.status === s.id).length) })), n: sources.map((src) => recs.filter((r) => r.source === src.id).length), nHead: 'recommendations', rawFormat: (v) => `${fmt.int(v)} recs`, labelWidth: 60, aria: 'Status by source' });
      } });
      ctx.card({ title: 'Open recommendations, most consequential first', sub: 'Click a report title for the department’s response', span: 7, render(el) {
        if (!open.length) return ctx.empty(el, 'Nothing open');
        const ul = ctx.h('div', '', el); open.sort((a, b) => b.consequence.score - a.consequence.score).slice(0, 8).forEach((r) => { const row = ctx.h('div', 'rec', ul); const l = ctx.h('div', '', row); l.appendChild(ctx.tag(r.consequence.score >= 7 ? 'review' : 'pattern', `score ${r.consequence.score}`)); l.appendChild(document.createTextNode(' ' + r.text)); const meta = ctx.h('div', 'meta', l); meta.appendChild(document.createTextNode(`${fmt.date(r.date_issued)} · ${(aum.dimensions.source.values.find((s) => s.id === r.source) || {}).short} · response: ${(aum.dimensions.agreed.values.find((a) => a.id === r.agreed) || {}).label}`)); meta.appendChild(ctx.link((ctx.data.reports.reports.find((x) => x.id === r.report) || {}).title, { view: 'report', id: r.report })); row.appendChild(M.au.statusPill(ctx, { label: (dim, v) => (aum.dimensions[dim].values.find((x) => x.id === v) || {}).label }, r.status)); });
        return null;
      } });
      const pay = ctx.data.pay.cells.filter((c) => c.dept === id), orgs = new Map(ctx.data.orgs.orgs.map((o) => [o.id, o])); ctx.feed('nonprofit payment records', pay.length, ctx.data.pay.cells.length);
      section(ctx, 'Nonprofit spending', pay.length ? `${fmt.money(st_.sum(pay, 'amt'))} to ${new Set(pay.map((c) => c.org)).size} organizations, all years` : 'none in the data');
      if (pay.length) ctx.card({ title: 'Largest nonprofit recipients', sub: 'All years, nominal; click to open', span: 6, render(el) {
        const by = st_.group(pay, (c) => c.org), rows = [...by.entries()].map(([o, cs]) => ({ label: orgs.get(o).name, value: st_.sum(cs, 'amt'), color: M.np.AREA_COLOR(orgs.get(o).area), onClick: () => M.state.set({ view: 'org', id: o }) })).sort((a, b) => b.value - a.value).slice(0, 10);
        return C.bars(el, { rows, rowH: 26, labelWidth: 200, valueHead: 'Paid', aria: 'Top recipients' });
      } });
      const ents = new Map(ctx.data.ents.entities.map((e) => [e.id, e])), dnode = [...ents.values()].find((e) => e.type === 'department' && e.code === id);
      const contacts = dnode ? ctx.data.flows.flows.filter((f) => f.type === 'lobby_contact' && f.to === dnode.id) : []; ctx.feed('lobbying contact records targeting this department', contacts.length, null);
      section(ctx, 'Lobbying of this department', contacts.length ? `${fmt.int(st_.sum(contacts, 'count'))} contacts reported` : 'none reported');
      if (contacts.length) ctx.card({ title: 'Contacts by client', sub: 'Who paid lobbyists to talk to this department, all years', span: 6, render(el) {
        const by = st_.group(contacts, (f) => f.client), rows = [...by.entries()].map(([c, fs]) => { const e = ents.get(c) || { name: c, type: 'other' }; return { label: e.name, value: st_.sum(fs, 'count'), color: M.nw.TYPE_COLOR(e.type), sub: [...new Set(fs.map((f) => f.topic))].join(', '), onClick: () => M.state.set({ view: 'org', id: e.nonprofit_org || e.id }) }; }).sort((a, b) => b.value - a.value).slice(0, 10);
        return C.bars(el, { rows, rowH: 26, format: (v) => fmt.int(v), valueHead: 'Contacts', labelWidth: 200, aria: 'Lobbying by client' });
      }, note: 'Lobbying is lawful and disclosed; the bar colour is the client’s entity type.' });
    },
  };
  function ys0(staff) { return Math.min(...staff.map((s) => s.fy)); }

  // ---------------------------------------------------------------- report page
  M.views.report = {
    id: 'report', dash: 'site', title: 'Report', kicker: 'Audit report', filters: [], filterNote: NOTE, headline: false,
    files: { recs: 'audits/recs/recs.json', reports: 'audits/reports/reports.json' },
    render(ctx) {
      const rep = ctx.data.reports.reports.find((r) => r.id === ctx.state.id);
      if (!rep) { ctx.empty(ctx.grid, 'Unknown report'); return; }
      document.querySelector('.view-title').textContent = rep.title;
      const aum = ctx.metas.au, label = (dim, v) => (aum.dimensions[dim].values.find((x) => x.id === v) || {}).label || v;
      const recs = ctx.data.recs.rows.filter((r) => r.report === rep.id); ctx.feed('recommendations in this report', recs.length, ctx.data.recs.rows.length);
      header(ctx, { facts: [['Issued', fmt.date(rep.date)], ['By', label('source', rep.source)], ['Topic', label('topic', rep.topic)], ['Departments', rep.depts.map((d) => ctx.link(ctx.deptName(d), { view: 'dept', id: d })).reduce((f, a, i) => { if (i) f.appendChild(document.createTextNode(', ')); f.appendChild(a); return f; }, document.createDocumentFragment())], ['Pages', String(rep.pages)], ['Follow-ups', rep.followups.length ? rep.followups.map(fmt.date).join(', ') : 'none recorded']], links: [ctx.h('span', 'badge badge-sample', null, 'Synthetic sample report'), rep.url ? (() => { const a = ctx.h('a', 'link', null, 'Read the report (PDF) →'); a.href = rep.url; return a; })() : ctx.h('span', 'filter-na', null, 'Report URL to be supplied by the data agent'), ctx.link('All recommendations from this body →', { view: 'au-status', source: [rep.source] })] });
      const p = ctx.h('p', 'view-what col-12', ctx.grid, rep.summary);
      const impl = recs.filter((r) => r.status === 'implemented').length;
      section(ctx, 'Recommendations', `${recs.length} total · ${impl} implemented · ${recs.filter((r) => r.status === 'open' || r.status === 'in_progress').length} open`);
      ctx.card({ title: 'Status and response', sub: 'One row per recommendation, in report order', span: 12, render(el) {
        const wrap = ctx.h('div', '', el);
        recs.forEach((r, i) => { const row = ctx.h('div', 'rec', wrap); const l = ctx.h('div', '', row); l.appendChild(document.createTextNode(`${i + 1}. ${r.text}`)); const meta = ctx.h('div', 'meta', l); meta.appendChild(document.createTextNode(`Department: `)); meta.appendChild(ctx.link(ctx.deptName(r.dept), { view: 'dept', id: r.dept })); meta.appendChild(document.createTextNode(` · priority ${r.priority} · response: ${label('agreed', r.agreed)}${r.months_to_close ? ` · implemented after ${fmt.months(r.months_to_close)} months` : ''}${r.dollars_at_stake ? ` · ${fmt.money(r.dollars_at_stake)} at stake` : ''}${r.repeat_of ? ' · repeats an earlier recommendation' : ''}`)); if (r.consequence.why) ctx.h('div', 'meta', l, r.consequence.why); const right = ctx.h('div', '', row); right.appendChild(M.au.statusPill(ctx, { label }, r.status)); ctx.h('div', 'sub', right, `as of ${fmt.date(r.status_date)}`).style.cssText = 'font-size:12px;color:var(--text-muted);text-align:right'; });
        return { head: ['#', 'Recommendation', 'Department', 'Response', 'Status', 'Months to implement'], rows: recs.map((r, i) => [i + 1, r.text, ctx.deptName(r.dept), label('agreed', r.agreed), label('status', r.status), fmt.months(r.months_to_close)]) };
      }, note: rep.source === 'cgj' ? 'Civil Grand Jury responses are mapped from Penal Code 933 terms; see the methods page for the mapping.' : rep.source === 'bla' ? 'Implementation status for BLA recommendations is the department’s own report at follow-up hearings.' : 'Controller auditors verify implementation at semi-annual follow-up.' });
    },
  };

  // ---------------------------------------------------------------- official profile
  M.views.official = {
    id: 'official', dash: 'site', title: 'Official', kicker: 'Official profile (public role)', filters: [], filterNote: NOTE, headline: false,
    files: { ents: 'network/entities.json', flows: 'network/flows.json', beh: 'network/analyses/behested.json', conc: 'network/analyses/concentration.json', ban: 'network/analyses/ban_window.json' },
    render(ctx) {
      const ents = new Map(ctx.data.ents.entities.map((e) => [e.id, e])), off = ents.get(ctx.state.id);
      if (!off || off.type !== 'official') { ctx.empty(ctx.grid, 'Unknown official'); return; }
      document.querySelector('.view-title').textContent = `${off.name} · ${off.office}`;
      const nwm = ctx.metas.nw, nm = (x) => (ents.get(x) || { name: x }).name;
      const cmtes = [...ents.values()].filter((e) => e.type === 'committee' && e.official === off.id), cids = new Set(cmtes.map((c) => c.id));
      const contribs = ctx.data.flows.flows.filter((f) => f.type === 'contribution' && cids.has(f.to)), beh = ctx.data.beh.rows.filter((b) => b.official === off.id), contacts = ctx.data.flows.flows.filter((f) => f.type === 'lobby_contact' && f.to === off.id);
      ctx.feed('contribution records to this official’s committees', contribs.length, null); ctx.feed('behested payments', beh.length, null); ctx.feed('lobbying contact records', contacts.length, null);
      header(ctx, { facts: [['Office', off.office], ['Committees', cmtes.map((c) => c.name).join('; ') || 'none'], ['Contributions received', fmt.money(st_.sum(contribs, 'amount'))], ['Behested payments', fmt.money(st_.sum(beh, 'amount'))], ['Lobbying contacts', fmt.int(st_.sum(contacts, 'count'))]], links: [ctx.h('span', 'badge badge-sample', null, off.sample_note || 'Synthetic sample'), ctx.link('Focus in the network graph →', { view: 'nw-graph', v: { focus: cmtes[0] ? cmtes[0].id : off.id } })] });
      ctx.fair(`${nwm.fairness.individuals} ${nwm.fairness.timing} This page describes an elected or appointed official acting in a public role; it lists disclosed transactions, not conduct.`);
      section(ctx, 'Contributions to committees', 'individuals aggregated by affiliation');
      ctx.card({ title: 'By source type', sub: 'All years', span: 5, render(el) {
        const K = [['individuals', 'Individuals (aggregate)', 'var(--c-individuals)'], ['contractor_affiliated', 'Contractor-affiliated individuals (aggregate)', 'var(--c-contractor)'], ['donor_org', 'PACs and organizations', 'var(--c-donor_org)']];
        const typeOf = (f) => { const e = ents.get(f.from); return e.type === 'individuals' ? (e.affiliated_with ? 'contractor_affiliated' : 'individuals') : e.type; };
        const rows = K.map(([k, label, color]) => ({ label, value: st_.sum(contribs.filter((f) => typeOf(f) === k), 'amount'), n: contribs.filter((f) => typeOf(f) === k).reduce((a, f) => a + f.count, 0), color })).filter((r) => r.n);
        if (!rows.length) return ctx.empty(el, 'No contributions');
        return C.bars(el, { rows, valueHead: 'Dollars', nHead: 'contributions', labelWidth: 230, aria: 'Contributions by source type' });
      } });
      const banRecs = ctx.data.ban.records.filter((r) => cids.has(r.committee));
      ctx.card({ title: 'Contractor-affiliated contributions and the ban window', sub: `${banRecs.length} records; ${banRecs.filter((r) => r.covered_official).length} appear to warrant review`, span: 7, render(el) {
        if (!banRecs.length) return ctx.empty(el, 'No contractor-affiliated contributions');
        return C.dotStrip(el, { points: banRecs.map((r) => ({ t: r.days_from_approval, amount: r.amount, label: `${nm(r.contractor)} (affiliated individuals)`, color: r.covered_official ? 'var(--div-neg-2)' : r.inside_window ? 'var(--series-2)' : 'var(--neutral-2)', tag: r.covered_official ? 'Appears to warrant review (§1.126). Pattern worth checking, not proof.' : r.inside_window ? 'Inside a window; this official does not approve that contract' : 'Outside every window', sub: fmt.date(r.date) })), window: [-183, 365], windowLabel: '§1.126 window (approx.)', min: -800, max: 1200, xTitle: 'Days from the contractor’s nearest contract approval', zeroLabel: 'approval', height: 200, aria: 'Ban strip' });
      }, caveat: 'Expected-by-chance share for all contractors is on the ban-window view; this official’s records are too few for a base rate of their own.' });
      section(ctx, 'Behested payments', `${beh.length} payments, ${fmt.money(st_.sum(beh, 'amount'))}`);
      ctx.card({ title: 'Payments at this official’s behest', sub: 'Payor, payee and purpose', span: 12, render(el) {
        if (!beh.length) return ctx.empty(el, 'None disclosed');
        return C.dataTable(el, { rows: beh, search: false, pageSize: 10, sort: 'amount', cols: [{ key: 'date', label: 'Date', format: (v) => fmt.date(v) }, { key: 'payor', label: 'Payor', text: (b) => nm(b.payor), render: (td, b) => { const e = ents.get(b.payor); if (e && e.type !== 'individuals') td.appendChild(ctx.link(e.name, { view: 'org', id: e.nonprofit_org || e.id })); else td.textContent = nm(b.payor); if (b.payor_interested_party) { td.appendChild(document.createTextNode(' ')); td.appendChild(ctx.tag('pattern', 'interested party')); } } }, { key: 'payee', label: 'Payee', text: (b) => nm(b.payee), render: (td, b) => { const e = ents.get(b.payee); td.appendChild(e && e.type === 'department' ? ctx.link(e.name, { view: 'dept', id: e.code }) : ctx.link(nm(b.payee), { view: 'org', id: (e || {}).nonprofit_org || b.payee })); } }, { key: 'purpose', label: 'Purpose' }, { key: 'amount', label: 'Amount', num: true, format: (v) => fmt.money(v) }] });
      } });
      section(ctx, 'Lobbying contacts with this official', `${fmt.int(st_.sum(contacts, 'count'))} contacts`);
      ctx.card({ title: 'Contacts by client', sub: 'Who paid lobbyists to contact this official', span: 6, render(el) {
        const by = st_.group(contacts, (f) => f.client), rows = [...by.entries()].map(([c, fs]) => ({ label: nm(c), value: st_.sum(fs, 'count'), color: M.nw.TYPE_COLOR((ents.get(c) || {}).type), sub: [...new Set(fs.map((f) => f.topic))].join(', '), onClick: () => M.state.set({ view: 'org', id: (ents.get(c) || {}).nonprofit_org || c }) })).sort((a, b) => b.value - a.value).slice(0, 10);
        if (!rows.length) return ctx.empty(el, 'None reported');
        return C.bars(el, { rows, rowH: 26, format: (v) => fmt.int(v), valueHead: 'Contacts', labelWidth: 200, aria: 'Contacts by client' });
      } });
    },
  };
})();
