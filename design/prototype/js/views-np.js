/* views-np.js - dashboard 1: Follow the nonprofit money.
   One predicate drives every card: payment cells are filtered by fiscal year, department and
   organization attributes (service area, size); the organizations that survive define the org set
   used by the 990, contract and monitoring cards. So every filter in the bar applies to everything. */
(function () {
  const M = window.SFCM;
  const C = M.charts, fmt = M.stats.fmt, st_ = M.stats, inList = M.state.inList;
  M.views = M.views || {};
  const FILES = { orgs: 'nonprofits/orgs/index.json', pay: 'nonprofits/payments/cells.json' };
  const AREA_COLOR = (a) => `var(--c-${a})`;
  const SIZE_COLOR = { 'lt1m': 'var(--ord-2)', '1-5m': 'var(--ord-3)', '5-25m': 'var(--ord-4)', '25m+': 'var(--ord-5)' };

  /** Shared scope: filtered payment cells, org set, helpers. */
  function scope(ctx) {
    const st = ctx.state, [y0, y1] = ctx.years, orgs = ctx.data.orgs.orgs, byId = new Map(orgs.map((o) => [o.id, o]));
    const orgOk = (o) => inList(st.area, o.area) && inList(st.size, o.size_band);
    const cells = ctx.data.pay.cells.filter((c) => c.fy >= y0 && c.fy <= y1 && inList(st.dept, c.dept) && orgOk(byId.get(c.org)));
    const orgSet = new Set(cells.map((c) => c.org));
    ctx.feed('payment records (dept × org × year)', cells.length, ctx.data.pay.cells.length);
    ctx.feed('organizations', orgSet.size, orgs.length);
    const total = st_.sum(cells, (c) => ctx.real(c.amt, c.fy));
    const areaLabel = (a) => (ctx.meta.dimensions.area.values.find((x) => x.id === a) || {}).label || a;
    const sizeLabel = (s) => (ctx.meta.dimensions.size_band.values.find((x) => x.id === s) || {}).label || s;
    Object.assign(ctx.slots, { years: fmt.range(y0, y1, 'FY'), rows: cells.length, rows_fmt: fmt.int(cells.length), orgs: orgSet.size, orgs_fmt: fmt.int(orgSet.size), total: fmt.money(total), fy: y1, dollars: ctx.dollars });
    return { st, y0, y1, orgs, byId, cells, orgSet, total, areaLabel, sizeLabel, orgLink: (o) => ctx.link(o.name, { view: 'org', id: o.id }) };
  }
  const byOrgTotal = (sc, ctx) => { const m = new Map(); for (const c of sc.cells) m.set(c.org, (m.get(c.org) || 0) + ctx.real(c.amt, c.fy)); return [...m.entries()].sort((a, b) => b[1] - a[1]); };

  // ---------------------------------------------------------------- overview
  M.views['np-overview'] = {
    id: 'np-overview', dash: 'np', nav: 'Overview', title: 'Follow the nonprofit money', what: 'City payments to nonprofits, who receives them, and how dependent those organizations are on the city.',
    how: 'Tiles and charts use your filters. Real dollars deflate each fiscal year with the SF-area CPI to FY2025 dollars. Click an organization to open its profile, which links to its finances, monitoring results, the audits of the departments that fund it, and its network connections.',
    filters: ['years', 'dept', 'area', 'size', 'real'], files: Object.assign({ fin: 'nonprofits/finances/form990.json', rev: 'nonprofits/reviews/findings.json' }, FILES),
    render(ctx) {
      const sc = scope(ctx), { cells, orgSet, y0, y1 } = sc;
      const top = byOrgTotal(sc, ctx);
      const latest = cells.filter((c) => c.fy === y1), latestTot = st_.sum(latest, (c) => ctx.real(c.amt, c.fy));
      const top10 = byOrgTotal({ cells: latest }, ctx).slice(0, 10), top10Share = latestTot ? st_.sum(top10, (t) => t[1]) / latestTot : null;
      const rev = ctx.data.rev.rows.filter((r) => orgSet.has(r.org) && r.fy >= y0 && r.fy <= y1), elev = new Set(rev.filter((r) => r.result === 'elevated' || r.result === 'redflag').map((r) => r.org));
      ctx.feed('monitoring results', rev.length, ctx.data.rev.rows.length);
      ctx.live('total');
      const tiles = ctx.h('div', 'tiles', ctx.pre);
      const tile = (label, value, unit, foot, patch) => { const t = ctx.h('button', 'tile', tiles); t.type = 'button'; ctx.h('div', 'tile-label', t, label); const v = ctx.h('div', 'tile-value', t, value); if (unit) ctx.h('small', '', v, unit); ctx.h('div', 'tile-foot', t).appendChild(document.createTextNode(foot)); t.addEventListener('click', () => M.state.set(patch)); };
      tile(`Paid to nonprofits, ${fmt.range(y0, y1, 'FY')} (${ctx.dollars})`, fmt.money(sc.total), '', `${fmt.int(cells.length)} payment records`, { view: 'np-flows' });
      tile(`Organizations paid in FY${y1}`, fmt.int(new Set(latest.map((c) => c.org)).size), '', `${fmt.int(orgSet.size)} across the period`, { view: 'np-orgs' });
      tile(`Share of FY${y1} dollars to the 10 largest`, top10Share == null ? '–' : fmt.pct(top10Share), '', top10.length ? `largest: ${sc.byId.get(top10[0][0]).name}` : 'no records', { view: 'np-dependency' });
      tile('Organizations rated elevated concern or red flag', fmt.int(elev.size), '', `${fmt.int(rev.length)} monitoring results`, { view: 'np-reviews' });
      const years = ctx.yearList();
      ctx.card({ title: 'Payments to nonprofits by fiscal year', sub: 'Real and nominal dollars; the gap between the lines is inflation', span: 7, render(el) {
        const nom = years.map((y) => st_.sum(cells.filter((c) => c.fy === y), 'amt')), real = years.map((y, i) => st_.sum(cells.filter((c) => c.fy === y), (c) => M.stats.real(c.amt, c.fy, ctx.meta.deflator)));
        if (!cells.length) return ctx.empty(el, 'No payments match', 'Widen the fiscal years or clear a filter.');
        return C.lines(el, { x: years, xFormat: (y) => `FY${String(y).slice(2)}`, series: [{ id: 'real', label: `Real (FY${ctx.meta.deflator.base_fy} $)`, color: 'var(--c-real)', values: real }, { id: 'nom', label: 'Nominal', color: 'var(--c-nominal)', values: nom, dash: true }], yTitle: 'Dollars', aria: 'Payments by fiscal year' });
      }, foot: [`n = ${fmt.int(cells.length)} payment records`, `deflator: ${ctx.meta.deflator.source.split(',')[0]}`] });
      ctx.card({ title: `Largest recipients, ${fmt.range(y0, y1, 'FY')}`, sub: 'Total paid; click a bar to open the organization', span: 5, render(el) {
        if (!top.length) return ctx.empty(el, 'No organizations match');
        return C.bars(el, { rows: top.slice(0, 10).map(([id, v]) => { const o = sc.byId.get(id); return { label: o.name, value: v, color: AREA_COLOR(o.area), sub: sc.areaLabel(o.area), onClick: () => M.state.set({ view: 'org', id }) }; }), valueHead: `Paid (${ctx.dollars})`, labelWidth: 190, aria: 'Largest recipients' });
      }, note: 'Bar colour is the organization’s service area (see the flows view for the key). Being large is not a finding; the city contracts out large services by design.', foot: `n = ${fmt.int(orgSet.size)} organizations` });
    },
  };

  // ---------------------------------------------------------------- flows
  M.views['np-flows'] = {
    id: 'np-flows', dash: 'np', nav: 'Who gets paid, by whom', title: 'Who gets paid, by whom', what: 'Payments by department and service area, over time, and the organizations receiving the most.',
    how: 'The trend stacks each year’s payments by service area (or by department, using the control). The horizontal chart shows each department’s nonprofit spending split by service area. Both respond to every filter above.',
    filters: ['years', 'dept', 'area', 'size', 'real'], files: FILES,
    render(ctx) {
      const sc = scope(ctx), { cells, st } = sc, years = ctx.yearList();
      const depts = ctx.meta.dimensions.dept.values.filter((d) => inList(st.dept, d.id)), areas = ctx.meta.dimensions.area.values.filter((a) => inList(st.area, a.id));
      const byDept = new Map(); for (const c of cells) byDept.set(c.dept, (byDept.get(c.dept) || 0) + ctx.real(c.amt, c.fy));
      const topDept = [...byDept.entries()].sort((a, b) => b[1] - a[1])[0];
      Object.assign(ctx.slots, { depts_fmt: fmt.int(byDept.size), top_dept: topDept ? ctx.deptName(topDept[0]) : '–', top_dept_share: topDept ? fmt.pct(topDept[1] / sc.total) : '–' });
      ctx.live('flows');
      const stackBy = ctx.v('stack', 'area');
      ctx.card({ title: 'Payments by fiscal year', sub: `Stacked by ${stackBy === 'area' ? 'service area' : 'department'} (${ctx.dollars})`, span: 12, controls: [{ label: 'Stack by', key: 'stack', value: stackBy, options: [['area', 'Stack by service area'], ['dept', 'Stack by department']], onChange: (v) => ctx.setV('stack', v) }], render(el) {
        if (!cells.length) return ctx.empty(el, 'No payments match', 'Widen the fiscal years or clear a filter.');
        let series;
        if (stackBy === 'area') series = areas.map((a) => ({ id: a.id, label: a.label, color: AREA_COLOR(a.id), values: years.map((y) => st_.sum(cells.filter((c) => c.fy === y && sc.byId.get(c.org).area === a.id), (c) => ctx.real(c.amt, c.fy))) }));
        else { const top = [...byDept.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6).map((t) => t[0]); series = top.map((d, i) => ({ id: d, label: ctx.deptShort(d), color: `var(--series-${i + 1})`, values: years.map((y) => st_.sum(cells.filter((c) => c.fy === y && c.dept === d), (c) => ctx.real(c.amt, c.fy))) })); if (byDept.size > 6) series.push({ id: 'other', label: 'Other departments', color: 'var(--series-7)', values: years.map((y) => st_.sum(cells.filter((c) => c.fy === y && !top.includes(c.dept)), (c) => ctx.real(c.amt, c.fy))) }); }
        return C.stackedBars(el, { categories: years, catFormat: (y) => `FY${String(y).slice(2)}`, series, yTitle: 'Dollars', annotations: M.commentary.annotationsFor(ctx.commentary, 'np_trend'), aria: 'Payments by fiscal year' });
      }, foot: `n = ${fmt.int(cells.length)} payment records · ${fmt.int(sc.orgSet.size)} organizations` });
      ctx.card({ title: 'Departments and the service areas they fund', sub: `Total ${fmt.range(sc.y0, sc.y1, 'FY')}, sorted by total`, span: 7, render(el) {
        const rows = [...byDept.entries()].sort((a, b) => b[1] - a[1]);
        if (!rows.length) return ctx.empty(el, 'No payments match');
        return C.stackedBars(el, { horizontal: true, categories: rows.map((r) => ctx.deptName(r[0])), series: areas.map((a) => ({ id: a.id, label: a.label, color: AREA_COLOR(a.id), values: rows.map(([d]) => st_.sum(cells.filter((c) => c.dept === d && sc.byId.get(c.org).area === a.id), (c) => ctx.real(c.amt, c.fy))) })), n: rows.map(([d]) => new Set(cells.filter((c) => c.dept === d).map((c) => c.org)).size), nHead: 'organizations', labelWidth: 200, xTitle: ctx.dollars, onClick: (i) => M.state.set({ view: 'dept', id: rows[i][0] }), aria: 'Departments by service area' });
      }, note: 'n is the number of organizations each department paid. Click a row to open the department scorecard.' });
      ctx.card({ title: 'Top 20 organizations', sub: 'Click to open a profile', span: 5, render(el) {
        const top = byOrgTotal(sc, ctx).slice(0, 20); if (!top.length) return ctx.empty(el, 'No organizations match');
        return C.bars(el, { rows: top.map(([id, v]) => { const o = sc.byId.get(id); return { label: o.name, value: v, color: AREA_COLOR(o.area), sub: `${sc.areaLabel(o.area)} · ${o.depts.map(ctx.deptShort).join(', ')}`, onClick: () => M.state.set({ view: 'org', id }) }; }), rowH: 26, labelWidth: 190, valueHead: ctx.dollars, aria: 'Top organizations' });
      } });
    },
  };

  // ---------------------------------------------------------------- dependency
  M.views['np-dependency'] = {
    id: 'np-dependency', dash: 'np', nav: 'City dependency', title: 'City dependency', what: 'How much of each organization’s revenue comes from the city, from its IRS Form 990.',
    how: 'Each dot is an organization in the chosen year: city payments on a log axis against city payments divided by total revenue. Above 75% is shaded as high dependency. Dependency is a risk to understand, not a finding of wrongdoing.',
    filters: ['years', 'dept', 'area', 'size', 'real'], files: Object.assign({ fin: 'nonprofits/finances/form990.json' }, FILES),
    render(ctx) {
      const sc = scope(ctx), fy = +ctx.v('fy', sc.y1);
      const payFy = new Map(); for (const c of sc.cells) if (c.fy === fy) payFy.set(c.org, (payFy.get(c.org) || 0) + c.amt);
      const fin = ctx.data.fin.rows.filter((r) => r.fy === fy && sc.orgSet.has(r.org) && payFy.has(r.org)).map((r) => ({ r, o: sc.byId.get(r.org), city: payFy.get(r.org), share: payFy.get(r.org) / r.total_revenue }));
      ctx.feed(`Form 990 filings for FY${fy}`, fin.length, ctx.data.fin.rows.filter((r) => r.fy === fy).length);
      const hi = fin.filter((f) => f.share > 0.75);
      Object.assign(ctx.slots, { fy: `FY${fy}`, orgs: fin.length, orgs_fmt: fmt.int(fin.length), median_share: fmt.pct(st_.median(fin.map((f) => f.share))), hi_fmt: fmt.int(hi.length) });
      ctx.live('dep');
      const yearCtl = { label: 'Year', key: 'fy', value: fy, options: ctx.yearList().map((y) => [y, `FY${y}`]), onChange: (v) => ctx.setV('fy', v) };
      ctx.card({ title: 'City dollars vs city share of revenue', sub: `FY${fy} · one dot per organization with a Form 990`, span: 8, controls: [yearCtl], render(el) {
        if (fin.length < 3) return ctx.empty(el, 'Too few organizations', `${fin.length} organizations have a Form 990 for FY${fy} under these filters.`);
        return C.scatter(el, { points: fin.map((f) => ({ id: f.o.id, x: ctx.real(f.city, fy), y: Math.min(f.share, 1.2), label: f.o.name, color: AREA_COLOR(f.o.area), sub: `${sc.areaLabel(f.o.area)} · revenue ${fmt.money(f.r.total_revenue)} · city ${fmt.money(f.city)}`, onClick: () => M.state.set({ view: 'org', id: f.o.id }) })), logX: 50000, xTitle: `City payments (${ctx.dollars})`, yTitle: 'City share of total revenue', maxY: 1.25, refY: 0.75, refLabel: '75%: high dependency', legend: ctx.meta.dimensions.area.values.filter((a) => fin.some((f) => f.o.area === a.id)).map((a) => ({ label: a.label, color: AREA_COLOR(a.id) })), aria: 'Dependency scatter' });
      }, caveat: 'Form 990 tax years and city fiscal years do not align exactly, so shares near or above 100% usually mean timing, not fraud. Points above 120% are clamped to the top.', foot: `n = ${fmt.int(fin.length)} organizations with a Form 990 in FY${fy}` });
      ctx.card({ title: 'Distribution of city share', sub: 'Organizations by dependency band', span: 4, render(el) {
        if (!fin.length) return ctx.empty(el, 'No data');
        const bands = ['<25%', '25–50%', '50–75%', '75–100%', '>100%'], counts = [0, 0, 0, 0, 0];
        fin.forEach((f) => counts[f.share < 0.25 ? 0 : f.share < 0.5 ? 1 : f.share < 0.75 ? 2 : f.share <= 1 ? 3 : 4]++);
        return C.histogram(el, { counts, labels: bands, highlight: [3, 4], unit: 'organizations', xTitle: 'City share of revenue', aria: 'Dependency distribution' });
      }, note: 'Orange bands are high dependency (over 75%).' });
      ctx.card({ title: 'Large and dependent', sub: 'City share above 75% and at least $5M in city payments; click to open', span: 12, render(el) {
        const rows = fin.filter((f) => f.share > 0.75 && f.city >= 5e6).sort((a, b) => b.city - a.city);
        if (!rows.length) return ctx.empty(el, 'No organizations match', 'No organization above 75% with $5M or more under these filters.');
        return C.dataTable(el, { rows, search: false, pageSize: 15, sort: 'city', cols: [{ key: 'name', label: 'Organization', text: (f) => f.o.name, render: (td, f) => td.appendChild(sc.orgLink(f.o)) }, { key: 'area', label: 'Service area', text: (f) => sc.areaLabel(f.o.area) }, { key: 'depts', label: 'Departments', text: (f) => f.o.depts.map(ctx.deptShort).join(', ') }, { key: 'city', label: `City payments FY${fy}`, num: true, sortVal: (f) => f.city, text: (f) => fmt.money(f.city) }, { key: 'rev', label: 'Total revenue (990)', num: true, sortVal: (f) => f.r.total_revenue, text: (f) => fmt.money(f.r.total_revenue) }, { key: 'share', label: 'City share', num: true, sortVal: (f) => f.share, text: (f) => fmt.pct(f.share) }, { key: 'res', label: 'Months of reserves', num: true, sortVal: (f) => f.r.months_reserves, text: (f) => fmt.num(f.r.months_reserves, 1) }] });
      } });
    },
  };

  // ---------------------------------------------------------------- pay & reserves
  M.views['np-pay'] = {
    id: 'np-pay', dash: 'np', nav: 'Executive pay and reserves', title: 'Executive pay and reserves', what: 'Top-executive compensation against organization size, and how many months of reserves each organization holds.',
    how: 'Pay is the highest-paid officer’s total compensation on the Form 990. The range bars show the middle half (box), median (tick) and 90th percentile (dot) within each size band, so “high” means high for a peer. Reserves are unrestricted net assets divided by monthly expenses.',
    filters: ['years', 'dept', 'area', 'size', 'real'], files: Object.assign({ fin: 'nonprofits/finances/form990.json' }, FILES),
    render(ctx) {
      const sc = scope(ctx), fy = +ctx.v('fy', sc.y1);
      const fin = ctx.data.fin.rows.filter((r) => r.fy === fy && sc.orgSet.has(r.org)).map((r) => ({ r, o: sc.byId.get(r.org) }));
      ctx.feed(`Form 990 filings for FY${fy}`, fin.length, ctx.data.fin.rows.filter((r) => r.fy === fy).length);
      const low = fin.filter((f) => f.r.months_reserves < 1);
      Object.assign(ctx.slots, { fy: `FY${fy}`, orgs: fin.length, orgs_fmt: fmt.int(fin.length), median_pay: fmt.money(st_.median(fin.map((f) => ctx.real(f.r.exec_comp, fy)))), n_low_fmt: fmt.int(low.length) });
      ctx.live('pay');
      ctx.fair('High compensation is unusual, not improper. Boards set executive pay; the figures are shown because the city funds most of these budgets, and they are compared with peers of the same size, never with city salaries.');
      const yearCtl = { label: 'Year', key: 'fy', value: fy, options: ctx.yearList().map((y) => [y, `FY${y}`]), onChange: (v) => ctx.setV('fy', v) };
      const sizes = ctx.meta.dimensions.size_band.values;
      ctx.card({ title: 'Top-executive compensation vs organization expenses', sub: `FY${fy} · colour is size band`, span: 8, controls: [yearCtl], render(el) {
        if (fin.length < 3) return ctx.empty(el, 'Too few organizations', 'Widen the filters.');
        return C.scatter(el, { points: fin.map((f) => ({ id: f.o.id, x: ctx.real(f.r.total_expenses, fy), y: ctx.real(f.r.exec_comp, fy), label: f.o.name, color: SIZE_COLOR[f.o.size_band], sub: `${f.r.exec_title} · ${sc.sizeLabel(f.o.size_band)} · ${sc.areaLabel(f.o.area)}`, onClick: () => M.state.set({ view: 'org', id: f.o.id }) })), logX: 100000, xTitle: `Total expenses (${ctx.dollars})`, yTitle: `Top executive compensation (${ctx.dollars})`, yFormat: (v) => fmt.money(v), legend: sizes.map((s) => ({ label: s.label, color: SIZE_COLOR[s.id] })), aria: 'Executive pay scatter' });
      }, foot: `n = ${fmt.int(fin.length)} organizations` });
      ctx.card({ title: 'Compensation by size band', sub: 'Median, middle half and 90th percentile', span: 4, render(el) {
        const rows = sizes.map((s) => { const v = fin.filter((f) => f.o.size_band === s.id).map((f) => ctx.real(f.r.exec_comp, fy)); return { label: s.label, q: v.length >= ctx.meta.small_n ? st_.quantiles(v) : null, n: v.length, small: v.length < ctx.meta.small_n, color: SIZE_COLOR[s.id] }; });
        return C.rangeBars(el, { rows, format: (v) => fmt.money(v), xTitle: ctx.dollars, labelWidth: 110, aria: 'Pay by size band' });
      }, note: `Bands with fewer than ${ctx.meta.small_n} organizations are greyed.` });
      ctx.card({ title: 'Months of unrestricted reserves by service area', sub: 'Below one month is shaded as the risk threshold', span: 7, render(el) {
        const areas = ctx.meta.dimensions.area.values.filter((a) => inList(ctx.state.area, a.id));
        const rows = areas.map((a) => { const v = fin.filter((f) => f.o.area === a.id).map((f) => Math.max(0, f.r.months_reserves)); return { label: a.label, q: v.length >= ctx.meta.small_n ? st_.quantiles(v) : null, n: v.length, small: v.length < ctx.meta.small_n, color: AREA_COLOR(a.id) }; });
        if (!rows.length) return ctx.empty(el, 'No data');
        return C.rangeBars(el, { rows, format: (v) => fmt.num(v, 1), xTitle: 'Months of reserves', labelWidth: 200, aria: 'Reserves by area' });
      } });
      ctx.card({ title: 'Under one month of reserves', sub: 'Sorted by city payments; click to open', span: 5, render(el) {
        const payFy = new Map(); for (const c of sc.cells) if (c.fy === fy) payFy.set(c.org, (payFy.get(c.org) || 0) + c.amt);
        const rows = low.map((f) => Object.assign(f, { city: payFy.get(f.o.id) || 0 })).sort((a, b) => b.city - a.city);
        if (!rows.length) return ctx.empty(el, 'None', 'No organization under these filters reports less than one month of reserves.');
        return C.dataTable(el, { rows, search: false, pageSize: 10, sort: 'city', cols: [{ key: 'name', label: 'Organization', text: (f) => f.o.name, render: (td, f) => td.appendChild(sc.orgLink(f.o)) }, { key: 'res', label: 'Months', num: true, sortVal: (f) => f.r.months_reserves, text: (f) => fmt.num(f.r.months_reserves, 1) }, { key: 'city', label: `City FY${fy}`, num: true, sortVal: (f) => f.city, text: (f) => fmt.money(f.city) }] });
      } });
    },
  };

  // ---------------------------------------------------------------- contract growth
  M.views['np-growth'] = {
    id: 'np-growth', dash: 'np', nav: 'Contract growth', title: 'Contract growth', what: 'How much contracts grew from their original agreed amount through amendments.',
    how: 'Contracts are included when they started in the selected fiscal years, belong to a selected department and to an organization in the current filters. Growth ratio is the latest agreed amount over the original. Amendments are normal; large ratios are a reason to read the contract.',
    filters: ['years', 'dept', 'area', 'size', 'real'], files: Object.assign({ con: 'nonprofits/contracts/contracts.json' }, FILES),
    render(ctx) {
      const sc = scope(ctx), { st } = sc;
      const startFy = (c) => +c.start.slice(0, 4) + 1;
      const cons = ctx.data.con.contracts.filter((c) => sc.orgSet.has(c.org) && inList(st.dept, c.dept) && startFy(c) >= sc.y0 && startFy(c) <= sc.y1);
      ctx.feed('contracts', cons.length, ctx.data.con.contracts.length);
      const amended = cons.filter((c) => c.amendments.length), ratios = amended.map((c) => c.agreed / c.original_agreed), doubled = amended.filter((c) => c.agreed / c.original_agreed >= 2);
      Object.assign(ctx.slots, { years: fmt.range(sc.y0, sc.y1, 'FY'), contracts: cons.length, contracts_fmt: fmt.int(cons.length), amended_fmt: fmt.int(amended.length), median_ratio: fmt.num(st_.median(ratios), 2), doubled_fmt: fmt.int(doubled.length) });
      ctx.live('growth');
      ctx.card({ title: 'How much amended contracts grew', sub: 'Latest agreed amount ÷ original, amended contracts only', span: 5, render(el) {
        if (!amended.length) return ctx.empty(el, 'No amended contracts match');
        const labels = ['1–1.25×', '1.25–1.5×', '1.5–2×', '2–3×', '3–5×', '>5×'], counts = [0, 0, 0, 0, 0, 0];
        ratios.forEach((r) => counts[r < 1.25 ? 0 : r < 1.5 ? 1 : r < 2 ? 2 : r < 3 ? 3 : r < 5 ? 4 : 5]++);
        return C.histogram(el, { counts, labels, highlight: [3, 4, 5], unit: 'contracts', xTitle: 'Growth ratio', aria: 'Growth histogram' });
      }, note: 'Orange: at least doubled.', foot: `n = ${fmt.int(amended.length)} amended of ${fmt.int(cons.length)} contracts` });
      ctx.card({ title: 'Original vs latest agreed amount', sub: 'The 15 contracts that grew most in dollars; sole-source marked', span: 7, render(el) {
        const rows = amended.slice().sort((a, b) => (b.agreed - b.original_agreed) - (a.agreed - a.original_agreed)).slice(0, 12);
        if (!rows.length) return ctx.empty(el, 'No amended contracts match');
        return C.slope(el, { rows: rows.map((c) => ({ label: sc.byId.get(c.org).name, a: c.original_agreed, b: c.agreed, color: AREA_COLOR(sc.byId.get(c.org).area), sub: (c.sole_source ? '· sole source' : '') + ` · ${c.amendments.length} amend.`, onClick: () => M.state.set({ view: 'org', id: c.org }) })), aLabel: 'Original agreed', bLabel: 'Latest agreed', height: 440, log: 100000, aria: 'Contract growth slope chart' });
      }, note: 'Nominal dollars: both amounts are as written in the contract. Click a line to open the organization.' });
      ctx.card({ title: 'New contracts by start year', sub: `Count and total original agreed amount (${ctx.dollars})`, span: 12, render(el) {
        const years = ctx.yearList(); if (!cons.length) return ctx.empty(el, 'No contracts match');
        return C.stackedBars(el, { categories: years, catFormat: (y) => `FY${String(y).slice(2)}`, series: [{ id: 'grant', label: 'Grant agreements', color: 'var(--series-1)', values: years.map((y) => st_.sum(cons.filter((c) => startFy(c) === y && c.type === 'grant'), (c) => ctx.real(c.original_agreed, y))) }, { id: 'ps', label: 'Professional services', color: 'var(--series-2)', values: years.map((y) => st_.sum(cons.filter((c) => startFy(c) === y && c.type !== 'grant'), (c) => ctx.real(c.original_agreed, y))) }], n: years.map((y) => cons.filter((c) => startFy(c) === y).length), nHead: 'contracts', yTitle: 'Original agreed amount', aria: 'Contracts by start year' });
      } });
      ctx.card({ title: 'Contracts', sub: 'Every contract in the current filters', span: 12, render(el) {
        return C.dataTable(el, { rows: cons, pageSize: 20, sort: 'agreed', placeholder: 'Filter by organization, title or department…', cols: [{ key: 'org', label: 'Organization', text: (c) => sc.byId.get(c.org).name, render: (td, c) => td.appendChild(sc.orgLink(sc.byId.get(c.org))) }, { key: 'title', label: 'Contract' }, { key: 'dept', label: 'Dept', text: (c) => ctx.deptShort(c.dept) }, { key: 'start', label: 'Term', text: (c) => `${c.start.slice(0, 4)}–${c.end.slice(0, 4)}` }, { key: 'original_agreed', label: 'Original', num: true, format: (v) => fmt.money(v) }, { key: 'agreed', label: 'Latest', num: true, format: (v) => fmt.money(v) }, { key: 'ratio', label: 'Growth', num: true, sortVal: (c) => c.agreed / c.original_agreed, text: (c) => fmt.ratio(c.agreed / c.original_agreed) }, { key: 'amendments', label: 'Amend.', num: true, sortVal: (c) => c.amendments.length, text: (c) => String(c.amendments.length) }, { key: 'sole_source', label: 'Sole source', text: (c) => (c.sole_source ? 'yes' : '') }] });
      } });
    },
  };

  // ---------------------------------------------------------------- reviews
  M.views['np-reviews'] = {
    id: 'np-reviews', dash: 'np', nav: 'Controller review findings', title: 'Controller review findings', what: 'Results of the Controller’s joint fiscal and compliance monitoring of city-funded nonprofits.',
    how: 'Each result is one organization in one fiscal year, on a five-step scale. The findings chart counts the categories cited. Every organization rated elevated concern or red flag is listed with the report and page.',
    filters: ['years', 'dept', 'area', 'size'], absent: { real: 'no dollar amounts on this view' }, files: Object.assign({ rev: 'nonprofits/reviews/findings.json' }, FILES),
    render(ctx) {
      const sc = scope(ctx), { st } = sc;
      const rev = ctx.data.rev.rows.filter((r) => sc.orgSet.has(r.org) && r.fy >= sc.y0 && r.fy <= sc.y1 && inList(st.dept, r.lead_dept));
      ctx.feed('monitoring results', rev.length, ctx.data.rev.rows.length);
      const results = ctx.data.rev.results, elev = rev.filter((r) => r.result === 'elevated' || r.result === 'redflag');
      Object.assign(ctx.slots, { reviews: rev.length, reviews_fmt: fmt.int(rev.length), orgs_fmt: fmt.int(new Set(rev.map((r) => r.org)).size), none_share: fmt.pct(rev.filter((r) => r.result === 'none').length / (rev.length || 1)), elev_fmt: fmt.int(elev.length) });
      ctx.live('reviews');
      ctx.fair('A monitoring result is a review of fiscal and compliance practices, not a judgment of an organization’s mission or program quality. Every row cites the Controller’s report.', 'Reading the results');
      const years = ctx.yearList().filter((y) => y >= 2018);
      const COL = { none: 'var(--ord-1)', findings: 'var(--ord-2)', corrective: 'var(--ord-3)', elevated: 'var(--ord-4)', redflag: 'var(--ord-5)' };
      ctx.card({ title: 'Monitoring results by fiscal year', sub: 'Share of reviewed organizations at each level', span: 7, render(el) {
        if (!rev.length) return ctx.empty(el, 'No monitoring results match');
        return C.stackedBars(el, { categories: years, catFormat: (y) => `FY${String(y).slice(2)}`, percent: true, series: results.map((r) => ({ id: r.id, label: r.label, color: COL[r.id], values: years.map((y) => rev.filter((x) => x.fy === y && x.result === r.id).length) })), n: years.map((y) => rev.filter((x) => x.fy === y).length), nHead: 'reviews', rawFormat: (v) => `${fmt.int(v)} reviews`, aria: 'Results by year' });
      }, note: 'The ordinal ramp runs from no findings (light) to red flag (dark).' });
      ctx.card({ title: 'What the findings were about', sub: 'Categories cited, all results with findings', span: 5, render(el) {
        const counts = new Map(); rev.forEach((r) => r.categories.forEach((c) => counts.set(c, (counts.get(c) || 0) + 1)));
        const rows = [...counts.entries()].sort((a, b) => b[1] - a[1]).map(([label, value]) => ({ label, value }));
        if (!rows.length) return ctx.empty(el, 'No findings match');
        return C.bars(el, { rows, format: (v) => fmt.int(v), valueHead: 'Citations', labelWidth: 210, xTitle: 'Findings', aria: 'Finding categories' });
      } });
      ctx.card({ title: 'Elevated concern and red flag', sub: 'Each row cites the report; click an organization to open its profile', span: 12, render(el) {
        if (!elev.length) return ctx.empty(el, 'None under these filters');
        return C.dataTable(el, { rows: elev, pageSize: 20, sort: 'fy', dir: 'desc', cols: [{ key: 'org', label: 'Organization', text: (r) => sc.byId.get(r.org).name, render: (td, r) => td.appendChild(sc.orgLink(sc.byId.get(r.org))) }, { key: 'fy', label: 'FY', num: true }, { key: 'lead_dept', label: 'Lead dept', text: (r) => ctx.deptShort(r.lead_dept) }, { key: 'result', label: 'Result', text: (r) => results.find((x) => x.id === r.result).label }, { key: 'categories', label: 'Findings', text: (r) => r.categories.join('; ') }, { key: 'note', label: 'Note', text: (r) => r.note || '' }, { key: 'report', label: 'Source', text: (r) => `${r.report.title}${r.report.page ? ', p. ' + r.report.page : ''}` }] });
      } });
    },
  };

  // ---------------------------------------------------------------- directory
  M.views['np-orgs'] = {
    id: 'np-orgs', dash: 'np', nav: 'Organizations', title: 'Organizations', what: 'Every organization in the payments data.', headline: false,
    filters: ['years', 'dept', 'area', 'size', 'real'], files: FILES,
    render(ctx) {
      const sc = scope(ctx); const tot = new Map(byOrgTotal(sc, ctx));
      const rows = sc.orgs.filter((o) => sc.orgSet.has(o.id)).map((o) => Object.assign({}, o, { total_sel: tot.get(o.id) || 0 }));
      ctx.card({ title: `${fmt.int(rows.length)} organizations`, sub: `Paid in ${fmt.range(sc.y0, sc.y1, 'FY')} under the current filters (${ctx.dollars})`, span: 12, render(el) {
        return C.dataTable(el, { rows, pageSize: 40, sort: 'total_sel', placeholder: 'Search organizations…', cols: [{ key: 'name', label: 'Organization', render: (td, o) => td.appendChild(sc.orgLink(o)) }, { key: 'area', label: 'Service area', text: (o) => sc.areaLabel(o.area) }, { key: 'size_band', label: 'Size', text: (o) => sc.sizeLabel(o.size_band) }, { key: 'depts', label: 'Departments', text: (o) => o.depts.map(ctx.deptShort).join(', ') }, { key: 'total_sel', label: 'Paid (selection)', num: true, format: (v) => fmt.money(v) }, { key: 'city_fy_latest', label: 'Paid FY2025', num: true, format: (v) => fmt.money(v) }, { key: 'first_fy', label: 'First FY', num: true }, { key: 'match', label: '990 match', text: (o) => `${o.match.method} · ${fmt.pct(o.match.confidence)}` }] });
      } });
    },
  };
  M.np = { scope, AREA_COLOR, SIZE_COLOR };
})();
