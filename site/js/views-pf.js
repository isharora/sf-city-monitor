/* views-pf.js - dashboard 2: Budget vs outcomes.
   Scope: departments (group + dept filters) × fiscal years × real/nominal. Every card draws from
   the same filtered spending, staffing and measure rows. */
(function () {
  const M = window.SFCM;
  M.views = M.views || {};
  const C = M.charts, fmt = M.stats.fmt, st_ = M.stats, inList = M.state.inList;
  const FILES = { spend: 'performance/spending/cells.json' };
  /** Spending categories: fixed slots from meta.dimensions.char; more than 7 fold into "Other" (last slot). */
  function charGroups(meta) {
    const vals = (meta.dimensions.char && meta.dimensions.char.values) || [];
    if (vals.length <= 7) return vals.map((v, i) => ({ id: v.id, label: v.label || v.id, ids: [v.id], color: `var(--series-${v.slot || i + 1})` }));
    const keep = vals.slice(0, 6).map((v, i) => ({ id: v.id, label: v.label || v.id, ids: [v.id], color: `var(--series-${i + 1})` }));
    return keep.concat([{ id: 'other', label: 'Other (' + vals.slice(6).map((v) => (v.label || v.id).toLowerCase()).join(', ') + ')', ids: vals.slice(6).map((v) => v.id), color: 'var(--series-7)' }]);
  }
  const CHAR_COLOR = (c) => { const g = charGroups(M.METAS.pf).find((x) => x.ids.includes(c)); return g ? g.color : 'var(--neutral)'; };
  const dirText = (d) => (d === 'higher' ? 'higher is better' : d === 'lower' ? 'lower is better' : 'no target direction');

  function scope(ctx) {
    const st = ctx.state, [y0, y1] = ctx.years;
    const depts = ctx.meta.dimensions.dept.values.filter((d) => inList(st.group, d.group) && inList(st.dept, d.id));
    const deptSet = new Set(depts.map((d) => d.id));
    const spend = ctx.data.spend ? ctx.data.spend.cells.filter((c) => c.fy >= y0 && c.fy <= y1 && deptSet.has(c.dept)) : [];
    if (ctx.data.spend) ctx.feed('spending records (dept × fund × category × year)', spend.length, ctx.data.spend.cells.length);
    ctx.feed('departments', depts.length, ctx.meta.dimensions.dept.values.length);
    const pop = (fy) => ctx.meta.population.by_fy[String(fy)];
    const actual = (rows, fy) => st_.sum(rows.filter((c) => c.fy === fy && c.actual != null), (c) => ctx.real(c.actual, c.fy));
    const budget = (rows, fy) => st_.sum(rows.filter((c) => c.fy === fy), (c) => ctx.real(c.budget, c.fy));
    Object.assign(ctx.slots, { years: fmt.range(y0, y1, 'FY'), fy: y1, fy0: y0, fy1: y1, depts: depts.length, depts_fmt: fmt.int(depts.length), dollars: ctx.dollars, total: fmt.money(actual(spend, y1)) });
    if (ctx.view.filters.includes('real')) ctx.units(ctx.dollars);
    return { st, y0, y1, depts, deptSet, spend, pop, actual, budget, deptLink: (id) => ctx.link(ctx.deptName(id), { view: 'dept', id }) };
  }
  function measureScope(ctx, sc) {
    const ms = ctx.data.measures.measures.filter((m) => sc.deptSet.has(m.dept)), mset = new Set(ms.map((m) => m.id));
    const vals = ctx.data.values.rows.filter((v) => mset.has(v.measure) && v.fy >= sc.y0 && v.fy <= sc.y1);
    ctx.feed('performance measures', ms.length, ctx.data.measures.measures.length); ctx.feed('measure-year values', vals.length, ctx.data.values.rows.length);
    // index of every value (all years) by measure and fiscal year, for "last reported" and "the year after a miss"
    const idx = new Map(); for (const v of ctx.data.values.rows) { if (!mset.has(v.measure)) continue; let m = idx.get(v.measure); if (!m) idx.set(v.measure, (m = new Map())); m.set(v.fy, v); }
    const at = (mid, fy) => (idx.get(mid) || new Map()).get(fy);
    // Latest selected year that has results (targets for the current year are published before its actuals).
    let fyR = sc.y1; while (fyR > sc.y0 && !vals.some((v) => v.fy === fyR && v.met != null)) fyR--;
    const fyNote = fyR < sc.y1 ? ` (FY${sc.y1} has no results yet; FY${fyR} is the latest year with results)` : '';
    return { ms, byId: new Map(ms.map((m) => [m.id, m])), vals, at, fyR, fyNote };
  }

  // ---------------------------------------------------------------- overview
  M.views['pf-overview'] = {
    id: 'pf-overview', dash: 'pf', nav: 'Overview', title: 'Budget vs outcomes', what: 'What departments spend, in real dollars and per resident, and whether they meet their own performance targets.',
    how: 'Real dollars deflate each year with the SF-area CPI to the base year shown on the Dollars switch. Per-resident figures use the population estimate for each fiscal year. “Met” compares actual with target in the measure’s direction (higher is better, or lower is better).',
    filters: ['years', 'group', 'dept', 'real'], files: Object.assign({ measures: 'performance/measures/measures.json', values: 'performance/measures/values.json', staff: 'performance/staffing/cells.json' }, FILES),
    render(ctx) {
      const sc = scope(ctx), { y0, y1, spend } = sc, ms = measureScope(ctx, sc);
      const staff = ctx.data.staff.cells.filter((s) => s.fy >= y0 && s.fy <= y1 && sc.deptSet.has(s.dept)); ctx.feed('staffing records', staff.length, ctx.data.staff.cells.length);
      const a1 = sc.actual(spend, y1), a0 = sc.actual(spend, y0), pr1 = a1 / sc.pop(y1), pr0 = a0 / sc.pop(y0);
      const v1 = ms.vals.filter((v) => v.fy === ms.fyR && v.met != null), met = v1.filter((v) => v.met).length;
      Object.assign(ctx.slots, { measures: v1.length, measures_fmt: fmt.int(v1.length), met_share: fmt.pct(v1.length ? met / v1.length : null), met_fy: `FY${ms.fyR}`, __small: !spend.length });
      ctx.live('ov');
      const tiles = ctx.h('div', 'tiles', ctx.pre);
      const tile = (label, value, foot, patch) => { const t = ctx.h('button', 'tile', tiles); t.type = 'button'; ctx.h('div', 'tile-label', t, label); ctx.h('div', 'tile-value', t, value); ctx.h('div', 'tile-foot', t).appendChild(document.createTextNode(foot)); t.addEventListener('click', () => M.state.set(patch)); };
      tile(`Actual spending FY${y1} (${ctx.dollars})`, fmt.money(a1), `${fmt.signedPct(a0 ? a1 / a0 - 1 : null)} vs FY${y0} · ${fmt.int(sc.depts.length)} departments`, { view: 'pf-spending' });
      tile(`Per resident FY${y1}`, fmt.moneyLong(pr1), `${fmt.signedPct(pr0 ? pr1 / pr0 - 1 : null)} vs FY${y0} · population ${fmt.int(sc.pop(y1))}`, { view: 'pf-spending' });
      tile(`Overtime FY${y1}`, fmt.money(st_.sum(staff.filter((s) => s.fy === y1), (s) => ctx.real(s.overtime, y1))), `${fmt.int(st_.sum(staff.filter((s) => s.fy === y1), 'headcount'))} employees`, { view: 'pf-staffing' });
      tile(`Measures meeting target FY${ms.fyR}`, fmt.pct(v1.length ? met / v1.length : null), `${fmt.int(met)} of ${fmt.int(v1.length)} reported${ms.fyR < y1 ? ` · FY${y1} results not yet published` : ''}`, { view: 'pf-outcomes' });
      const years = ctx.yearList();
      ctx.card({ title: 'Actual spending by fiscal year', sub: 'Real and nominal; the gap is inflation', span: 7, render(el) {
        if (!spend.length) return ctx.empty(el, 'No departments match');
        const rs = { id: 'real', label: `Real (FY${ctx.meta.deflator.base_fy} $)`, values: years.map((y) => st_.sum(spend.filter((c) => c.fy === y), (c) => M.stats.real(c.actual, c.fy, ctx.meta.deflator)) || null) }, ns = { id: 'nom', label: 'Nominal', values: years.map((y) => st_.sum(spend.filter((c) => c.fy === y), 'actual') || null) };
        const sel = ctx.state.real ? rs : ns, other = ctx.state.real ? ns : rs;
        return C.lines(el, { x: years, xFormat: (y) => `FY${String(y).slice(2)}`, series: [Object.assign(sel, { color: 'var(--c-real)' }), Object.assign(other, { color: 'var(--c-nominal)', dash: true })], yTitle: `Dollars (solid line: ${ctx.dollars})`, annotations: M.commentary.annotationsFor(ctx.commentary, 'pf_trend'), aria: 'Spending by year' });
      }, foot: `n = ${fmt.int(spend.length)} spending records` });
      ctx.card({ title: `Spending per resident, FY${y1}`, sub: 'Click a department to open its scorecard', span: 5, render(el) {
        const rows = sc.depts.map((d) => ({ label: d.name, value: sc.actual(spend.filter((c) => c.dept === d.id), y1) / sc.pop(y1), onClick: () => M.state.set({ view: 'dept', id: d.id }) })).sort((a, b) => b.value - a.value).slice(0, 12);
        if (!rows.length) return ctx.empty(el, 'No departments match');
        return C.bars(el, { rows, rowH: 26, format: (v) => fmt.moneyLong(v), valueHead: 'Per resident', labelWidth: 200, aria: 'Per-resident spending' });
      } });
    },
  };

  // ---------------------------------------------------------------- spending
  M.views['pf-spending'] = {
    id: 'pf-spending', dash: 'pf', nav: 'What departments spend', title: 'What departments spend', what: 'Real dollars, per resident, and by spending category.',
    how: 'The first chart indexes each department’s real spending to its first selected year (=100), so departments of very different size share one axis. Per-resident divides by the January population of each fiscal year.',
    filters: ['years', 'group', 'dept', 'real'], files: FILES,
    render(ctx) {
      const sc = scope(ctx), { y0, y1, spend } = sc, years = ctx.yearList();
      const a1 = sc.actual(spend, y1), a0 = sc.actual(spend, y0);
      const nom = (fy) => st_.sum(spend.filter((c) => c.fy === fy && c.actual != null), 'actual');
      const realAct = (fy) => st_.sum(spend.filter((c) => c.fy === fy && c.actual != null), (c) => M.stats.real(c.actual, c.fy, ctx.meta.deflator));
      Object.assign(ctx.slots, { change_real: fmt.signedPct(realAct(y0) ? realAct(y1) / realAct(y0) - 1 : null), change_nominal: fmt.signedPct(nom(y0) ? nom(y1) / nom(y0) - 1 : null), change_per_res: fmt.signedPct(a0 && sc.pop(y0) && sc.pop(y1) ? (a1 / sc.pop(y1)) / (a0 / sc.pop(y0)) - 1 : null), __small: !spend.length });
      ctx.live('sp');
      const unit = ctx.state.real ? 'real' : 'nominal';
      ctx.card({ title: `${ctx.state.real ? 'Real' : 'Nominal'} spending indexed to FY${y0} = 100`, sub: 'Up to 7 largest selected departments, plus the total', span: 12, render(el) {
        const top = sc.depts.map((d) => ({ d, v: sc.actual(spend.filter((c) => c.dept === d.id), y1) })).sort((a, b) => b.v - a.v).slice(0, 7);
        if (!top.length) return ctx.empty(el, 'No departments match');
        const idx = (rows) => { const base = st_.sum(rows.filter((c) => c.fy === y0), (c) => ctx.real(c.actual, c.fy)); return years.map((y) => { const v = st_.sum(rows.filter((c) => c.fy === y && c.actual != null), (c) => ctx.real(c.actual, c.fy)); return base && v ? (100 * v) / base : null; }); };
        const series = top.map((t, i) => ({ id: t.d.id, label: t.d.short, color: `var(--series-${i + 1})`, values: idx(spend.filter((c) => c.dept === t.d.id)) }));
        series.push({ id: 'all', label: 'All selected', color: 'var(--text-secondary)', dash: true, values: idx(spend) });
        return C.lines(el, { x: years, xFormat: (y) => `FY${String(y).slice(2)}`, series, format: (v) => fmt.num(v, 0), yTitle: `Index (FY${y0} = 100, ${unit})`, minY: 60, maxY: Math.max(140, ...series.flatMap((s) => s.values).filter(Boolean)) * 1.05, refY: 100, endLabels: false, annotations: M.commentary.annotationsFor(ctx.commentary, 'pf_trend'), aria: 'Indexed real spending' });
      }, note: 'Indexing puts departments of different size on one axis without a second y-axis. The legend identifies series; hover for values.' });
      ctx.card({ title: `Per resident, FY${y1} vs FY${y0}`, sub: `${ctx.state.real ? 'Real' : 'Nominal'} dollars per resident; the label is the change`, span: 6, render(el) {
        const rows = sc.depts.map((d) => ({ label: d.name, a: st_.sum(spend.filter((c) => c.dept === d.id && c.fy === y0), (c) => ctx.real(c.actual, c.fy)) / sc.pop(y0), b: st_.sum(spend.filter((c) => c.dept === d.id && c.fy === y1), (c) => ctx.real(c.actual, c.fy)) / sc.pop(y1), onClick: () => M.state.set({ view: 'dept', id: d.id }) })).filter((r) => r.a > 0 || r.b > 0).sort((a, b) => b.b - a.b);
        if (!rows.length) return ctx.empty(el, 'No departments match');
        return C.dumbbell(el, { rows, aLabel: `FY${y0}`, bLabel: `FY${y1}`, format: (v) => fmt.moneyLong(v), diffFormat: (d, r) => `${fmt.signedPct(r)}`, log: 5, labelWidth: 200, xTitle: `${ctx.state.real ? 'Real' : 'Nominal'} dollars per resident (log)`, aria: 'Per-resident change' });
      } });
      ctx.card({ title: `Spending by category, FY${y1}`, sub: 'Share of each department’s actual spending', span: 6, render(el) {
        const groups = charGroups(ctx.meta), rows = sc.depts.filter((d) => spend.some((c) => c.dept === d.id && c.fy === y1 && c.actual)).map((d) => ({ d, tot: sc.actual(spend.filter((c) => c.dept === d.id), y1) })).sort((a, b) => b.tot - a.tot).slice(0, 24).map((x) => x.d);
        if (!rows.length) return ctx.empty(el, 'No departments match');
        return C.stackedBars(el, { horizontal: true, percent: true, categories: rows.map((d) => d.name), series: groups.map((g) => ({ id: g.id, label: g.label, color: g.color, values: rows.map((d) => st_.sum(spend.filter((c) => c.dept === d.id && c.fy === y1 && g.ids.includes(c.char)), (c) => ctx.real(c.actual, c.fy))) })), rawFormat: (v) => fmt.money(v), labelWidth: 200, rowH: 24, aria: 'Spending by category' });
      }, note: 'Human-welfare departments are mostly “aid and grants”, the money that flows to the nonprofits in dashboard 1.' });
    },
  };

  // ---------------------------------------------------------------- staffing
  M.views['pf-staffing'] = {
    id: 'pf-staffing', dash: 'pf', nav: 'Headcount and overtime', title: 'Headcount and overtime', what: 'Employees paid, overtime dollars and overtime as a share of pay, by department.',
    how: 'Headcount is distinct employees paid in the fiscal year. Overtime share is overtime divided by base salaries plus overtime. Only executives and elected officials are ever named on this site; overtime is shown by department and job family.',
    filters: ['years', 'group', 'dept', 'real'], files: { staff: 'performance/staffing/cells.json' },
    render(ctx) {
      const sc = scope(ctx), { y0, y1 } = sc, years = ctx.yearList();
      const staff = ctx.data.staff.cells.filter((s) => s.fy >= y0 && s.fy <= y1 && sc.deptSet.has(s.dept)); ctx.feed('staffing records (dept × year)', staff.length, ctx.data.staff.cells.length);
      const s1 = staff.filter((s) => s.fy === y1), ot = st_.sum(s1, 'overtime'), sal = st_.sum(s1, 'salaries');
      Object.assign(ctx.slots, { headcount_fmt: fmt.int(st_.sum(s1, 'headcount')), ot_total: fmt.money(ctx.real(ot, y1)), ot_share: fmt.pct(sal + ot ? ot / (sal + ot) : null, 1), ot100k_fmt: fmt.int(st_.sum(s1, 'employees_ot_over_100k')), __small: !s1.length });
      const deptOf = new Map(sc.depts.map((d) => [d.id, d]));
      ctx.live('st');
      ctx.card({ title: `Overtime as a share of pay, FY${y1}`, sub: 'Overtime ÷ (salaries + overtime); departments with 50+ employees, top 20; click to open a scorecard', span: 6, render(el) {
        const rows = s1.filter((s) => s.ot_share != null && s.headcount >= 50).map((s) => ({ label: ctx.deptName(s.dept), value: s.ot_share, n: s.headcount, sub: `overtime ${fmt.money(ctx.real(s.overtime, y1))}`, onClick: () => M.state.set({ view: 'dept', id: s.dept }) })).sort((a, b) => b.value - a.value).slice(0, 20);
        if (!rows.length) return ctx.empty(el, 'No departments match');
        return C.bars(el, { rows, rowH: 26, format: (v) => fmt.pct(v, 1), valueHead: 'Overtime share', nHead: 'employees', labelWidth: 200, aria: 'Overtime share' });
      }, note: 'n is headcount. Public-safety overtime is driven by minimum staffing rules and vacancies as well as by management choices.' });
      ctx.card({ title: 'Overtime dollars by fiscal year', sub: `Selected departments (${ctx.dollars})`, span: 6, render(el) {
        if (!staff.length) return ctx.empty(el, 'No departments match');
        const groups = [...new Set(sc.depts.map((d) => d.group))];
        const glabel = (g) => (ctx.meta.dimensions.group.values.find((x) => x.id === g) || {}).label || g;
        return C.stackedBars(el, { categories: years, catFormat: (y) => `FY${String(y).slice(2)}`, series: groups.map((g, i) => ({ id: g, label: glabel(g), color: `var(--series-${i + 1})`, values: years.map((y) => st_.sum(staff.filter((s) => s.fy === y && (deptOf.get(s.dept) || {}).group === g), (s) => ctx.real(s.overtime, y))) })), yTitle: 'Overtime', annotations: M.commentary.annotationsFor(ctx.commentary, 'pf_ot'), aria: 'Overtime by year' });
      } });
      ctx.card({ title: 'Headcount by fiscal year', sub: 'Distinct employees paid; up to 7 largest departments', span: 6, render(el) {
        const top = sc.depts.map((d) => ({ d, v: (s1.find((s) => s.dept === d.id) || {}).headcount || 0 })).sort((a, b) => b.v - a.v).slice(0, 7);
        if (!top.length) return ctx.empty(el, 'No departments match');
        return C.lines(el, { x: years, xFormat: (y) => `FY${String(y).slice(2)}`, series: top.map((t, i) => ({ id: t.d.id, label: t.d.short, color: `var(--series-${i + 1})`, values: years.map((y) => (staff.find((s) => s.fy === y && s.dept === t.d.id) || {}).headcount || null) })), format: (v) => fmt.int(v), yTitle: 'Employees', endLabels: false, aria: 'Headcount' });
      } });
      ctx.card({ title: `Where overtime goes, FY${y1}`, sub: 'Top job families per department; employees earning over $100k in overtime', span: 6, render(el) {
        const rows = s1.slice().sort((a, b) => b.overtime - a.overtime);
        if (!rows.length) return ctx.empty(el, 'No departments match');
        return C.dataTable(el, { rows, search: false, pageSize: 12, sort: 'overtime', cols: [{ key: 'dept', label: 'Department', text: (s) => ctx.deptName(s.dept), render: (td, s) => td.appendChild(sc.deptLink(s.dept)) }, { key: 'overtime', label: 'Overtime', num: true, format: (v, s) => fmt.money(ctx.real(v, s.fy)) }, { key: 'fam', label: 'Largest job family', text: (s) => { const f = (s.top_ot_job_families || [])[0]; return f ? `${f.family} (${fmt.money(ctx.real(f.overtime, s.fy))})` : '–'; } }, { key: 'employees_ot_over_100k', label: '> $100k OT', num: true }] });
      } });
    },
  };

  // ---------------------------------------------------------------- outcomes
  M.views['pf-outcomes'] = {
    id: 'pf-outcomes', dash: 'pf', nav: 'Measures vs targets', title: 'Measures vs targets', what: 'Whether departments met the performance targets they set for themselves.',
    how: 'Each cell is the share of a department’s reported measures that met their target in a year; cells with fewer than three reported measures are greyed. A high share can mean strong performance or easy targets; the integrity view separates the two.',
    filters: ['years', 'group', 'dept'], absent: { real: 'no dollar amounts on this view' }, files: { measures: 'performance/measures/measures.json', values: 'performance/measures/values.json' },
    render(ctx) {
      const sc = scope(ctx), ms = measureScope(ctx, sc), years = ctx.yearList(), y1 = ms.fyR;
      const v1 = ms.vals.filter((v) => v.fy === y1 && v.met != null), met = v1.filter((v) => v.met);
      const share = (rows) => (rows.length ? rows.filter((v) => v.met).length / rows.length : null);
      Object.assign(ctx.slots, { __small: v1.length < ctx.meta.small_n, measures: v1.length, measures_fmt: fmt.int(v1.length), met_fmt: fmt.int(met.length), met_share: fmt.pct(share(v1)), met_share_outcome: fmt.pct(share(v1.filter((v) => ms.byId.get(v.measure).type === 'outcome'))), met_share_output: fmt.pct(share(v1.filter((v) => ms.byId.get(v.measure).type === 'output'))) });
      ctx.live('oc');
      ctx.card({ title: 'Share of measures meeting target', sub: 'Department × fiscal year; grey = fewer than 3 measures reported', span: 12, render(el) {
        const rows = sc.depts.filter((d) => ms.vals.some((v) => v.met != null && ms.byId.get(v.measure).dept === d.id));
        if (!rows.length) return ctx.empty(el, 'No measures match');
        const byDY = st_.group(ms.vals.filter((v) => v.met != null), (v) => `${ms.byId.get(v.measure).dept}|${v.fy}`);
        const cell = (d, y) => byDY.get(`${d.id}|${y}`) || [];
        const hy = years.filter((y) => y <= ms.fyR);
        return C.heatmap(el, { rows: rows.map((d) => d.name), cols: hy, colFormat: (y) => `FY${String(y).slice(2)}`, colFormatShort: (y) => `’${String(y).slice(2)}`, values: rows.map((d) => hy.map((y) => share(cell(d, y)))), n: rows.map((d) => hy.map((y) => cell(d, y).length)), smallN: ctx.meta.small_n, nLabel: 'measures reported', valueLabel: 'met', labelWidth: 210, cellH: 26, onClick: (i) => M.state.set({ view: 'dept', id: rows[i].id }), aria: 'Met share heat grid' });
      }, foot: `n = ${fmt.int(ms.vals.filter((v) => v.met != null).length)} measure-years with a target and an actual` });
      ctx.card({ title: `Met, missed and not reported, FY${y1}`, sub: 'By measure type' + ms.fyNote, span: 5, render(el) {
        const types = ['outcome', 'output', 'efficiency'], all = ms.vals.filter((v) => v.fy === y1);
        if (!all.length) return ctx.empty(el, 'No measures match');
        return C.stackedBars(el, { horizontal: true, percent: true, categories: types.map((t) => t[0].toUpperCase() + t.slice(1) + ' measures'), series: [{ id: 'met', label: 'Met', color: 'var(--c-met)', values: types.map((t) => all.filter((v) => ms.byId.get(v.measure).type === t && v.met === true).length) }, { id: 'missed', label: 'Missed', color: 'var(--c-missed)', values: types.map((t) => all.filter((v) => ms.byId.get(v.measure).type === t && v.met === false).length) }, { id: 'na', label: 'Not reported', color: 'var(--c-notarget)', values: types.map((t) => all.filter((v) => ms.byId.get(v.measure).type === t && v.met == null).length) }], n: types.map((t) => all.filter((v) => ms.byId.get(v.measure).type === t).length), small: types.map((t) => all.filter((v) => ms.byId.get(v.measure).type === t).length < ctx.meta.small_n), nHead: 'measures', rawFormat: (v) => `${fmt.int(v)} measures`, labelWidth: 150, aria: 'Met by type' });
      }, note: 'Outcome = results for residents; output = things done; efficiency = cost or time per unit.' });
      ctx.card({ title: `Every measure, FY${y1}`, sub: 'Target, actual and whether the target moved' + ms.fyNote, span: 7, render(el) {
        const rows = ms.vals.filter((v) => v.fy === y1).map((v) => Object.assign({}, v, { m: ms.byId.get(v.measure) }));
        if (!rows.length) return ctx.empty(el, 'No measures match');
        return C.dataTable(el, { rows, pageSize: 12, sort: 'dept', dir: 'asc', placeholder: 'Filter measures…', cols: [{ key: 'dept', label: 'Dept', text: (r) => ctx.deptShort(r.m.dept), sortVal: (r) => r.m.dept }, { key: 'name', label: 'Measure', text: (r) => `${r.m.name} (${r.m.unit || 'no unit'}, ${dirText(r.m.direction)})` }, { key: 'target', label: 'Target', num: true, format: (v) => fmt.num(v) }, { key: 'actual', label: 'Actual', num: true, format: (v) => fmt.num(v) }, { key: 'met', label: 'Met?', render: (td, r) => { td.appendChild(ctx.tag(r.met == null ? 'ok' : r.met ? 'met' : 'missed', r.met == null ? 'not reported' : r.met ? 'met' : 'missed')); }, sortVal: (r) => (r.met == null ? -1 : r.met ? 1 : 0) }, { key: 'target_change', label: 'Target vs prior year', text: (r) => ({ easier: 'made easier', harder: 'made harder', same: 'unchanged', new: 'new target' }[r.target_change] || '–') }] });
      } });
    },
  };

  // ---------------------------------------------------------------- cost per outcome
  M.views['pf-cost'] = {
    id: 'pf-cost', dash: 'pf', nav: 'Cost per outcome', title: 'Cost per outcome', what: 'Program cost divided by the units a measure counts, where the two can be tied together.',
    how: 'Only count measures with a linked program budget are included; percentages and rates cannot have a unit cost. Lines are indexed to the first selected year so measures with very different unit costs share one axis. The table gives the real unit cost itself.',
    filters: ['years', 'group', 'dept', 'real'], files: { measures: 'performance/measures/measures.json', values: 'performance/measures/values.json' },
    render(ctx) {
      const sc = scope(ctx), ms = measureScope(ctx, sc), years = ctx.yearList();
      const linked = ms.vals.filter((v) => v.cost_per_unit != null); const mids = [...new Set(linked.map((v) => v.measure))];
      ctx.feed('measure-years with a linked cost', linked.length, ctx.data.values.rows.filter((v) => v.cost_per_unit != null).length);
      const unit = (mid, y) => { const v = linked.find((x) => x.measure === mid && x.fy === y); return v ? ctx.real(v.cost_per_unit, y) : null; };
      // each measure is compared between its first and last years with a unit cost inside the selected range
      const span = (mid) => { const ys = linked.filter((x) => x.measure === mid).map((x) => x.fy).sort((a, b) => a - b); return ys.length ? [ys[0], ys[ys.length - 1]] : [null, null]; };
      const changes = mids.map((mid) => { const [f0, f1] = span(mid); const a = unit(mid, f0), b = unit(mid, f1); return a && b && f1 > f0 ? b / a - 1 : null; }).filter((x) => x != null);
      Object.assign(ctx.slots, { measures: mids.length, measures_fmt: fmt.int(mids.length), median_change: fmt.signedPct(st_.median(changes)), __small: !mids.length });
      ctx.live('cost');
      ctx.card({ title: `${ctx.state.real ? 'Real' : 'Nominal'} cost per unit, indexed to each measure’s first year = 100`, sub: `Up to 8 linked measures, FY${sc.y0}–FY${sc.y1}; each line starts at its first year with a unit cost; hover for values`, span: 12, render(el) {
        const show = mids.slice(0, 8); if (!show.length) return ctx.empty(el, 'No linked measures match', 'Choose departments with count measures (placements, visits, repairs).');
        return C.lines(el, { x: years, xFormat: (y) => `FY${String(y).slice(2)}`, series: show.map((mid, i) => { const base = unit(mid, span(mid)[0]); return { id: mid, label: `${ctx.deptShort(ms.byId.get(mid).dept)}: ${ms.byId.get(mid).name}`, color: `var(--series-${i + 1})`, values: years.map((y) => { const u = unit(mid, y); return base && u ? (100 * u) / base : null; }) }; }), format: (v) => fmt.num(v, 0), yTitle: `Index (${ctx.state.real ? 'real' : 'nominal'})`, minY: 40, refY: 100, endLabels: false, aria: 'Unit cost index' });
      } });
      ctx.card({ title: 'Unit cost by measure', sub: `${ctx.state.real ? `Real FY${ctx.meta.deflator.base_fy}` : 'Nominal'} dollars per unit, first and last year with a unit cost in FY${sc.y0}–FY${sc.y1}`, span: 12, render(el) {
        const rows = mids.map((mid) => { const [f0, f1] = span(mid); return { m: ms.byId.get(mid), f0, f1, a: unit(mid, f0), b: f1 > f0 ? unit(mid, f1) : null, prog: (linked.find((x) => x.measure === mid && x.fy === f1) || {}).program_cost }; });
        if (!rows.length) return ctx.empty(el, 'No linked measures match');
        return C.dataTable(el, { rows, search: false, pageSize: 20, sort: 'chg', cols: [{ key: 'dept', label: 'Department', text: (r) => ctx.deptName(r.m.dept), render: (td, r) => td.appendChild(sc.deptLink(r.m.dept)) }, { key: 'name', label: 'Measure', text: (r) => `${r.m.name} (per ${r.m.unit})` }, { key: 'a', label: 'First year', num: true, format: (v, r) => (v == null ? '–' : `${fmt.moneyLong(v)} (FY${r.f0})`) }, { key: 'b', label: 'Last year', num: true, format: (v, r) => (v == null ? '–' : `${fmt.moneyLong(v)} (FY${r.f1})`) }, { key: 'chg', label: 'Change (real)', num: true, sortVal: (r) => (r.a && r.b ? r.b / r.a - 1 : null), text: (r) => fmt.signedPct(r.a && r.b ? r.b / r.a - 1 : null) }, { key: 'prog', label: 'Program cost, last year', num: true, format: (v, r) => fmt.money(ctx.real(v, r.f1)) }] });
      }, caveat: 'Program-to-measure links are the analyst’s judgment (listed in DATA_NOTES); a different mapping gives different unit costs.' });
    },
  };

  // ---------------------------------------------------------------- integrity
  M.views['pf-integrity'] = {
    id: 'pf-integrity', dash: 'pf', nav: 'Dropped measures, lowered targets', title: 'Dropped measures and lowered targets', what: 'Measures that disappeared and targets that became easier, including right after a miss.',
    how: 'A measure is “dropped” when it stops being reported without a stated replacement. A target is “made easier” when it moves in the direction that makes it easier to meet. Neither is misconduct; both change what the met share means.',
    filters: ['years', 'group', 'dept'], absent: { real: 'no dollar amounts on this view' }, files: { measures: 'performance/measures/measures.json', values: 'performance/measures/values.json' },
    render(ctx) {
      const sc = scope(ctx), ms = measureScope(ctx, sc), years = ctx.yearList();
      const dropped = ms.ms.filter((m) => m.dropped_fy && m.dropped_fy >= sc.y0 && m.dropped_fy <= sc.y1);
      const lastVal = (m) => ms.at(m.id, m.last_fy);
      const droppedMissed = dropped.filter((m) => { const v = lastVal(m); return v && v.met === false; });
      const lowered = ms.vals.filter((v) => v.target_change === 'easier');
      const prevMissed = (v) => { const p = ms.at(v.measure, v.fy - 1); return !!p && p.met === false; };
      const loweredAfterMiss = lowered.filter(prevMissed);
      Object.assign(ctx.slots, { __small: !ms.ms.length, measures: ms.ms.length, dropped_fmt: fmt.int(dropped.length), dropped_missed_fmt: fmt.int(droppedMissed.length), lowered_fmt: fmt.int(lowered.length), lowered_after_miss_fmt: fmt.int(loweredAfterMiss.length) });
      ctx.live('int');
      ctx.card({ title: 'Dropped measures and easier targets by year', sub: 'Counts across selected departments', span: 7, render(el) {
        if (!ms.ms.length) return ctx.empty(el, 'No measures match');
        return C.stackedBars(el, { categories: years, catFormat: (y) => `FY${String(y).slice(2)}`, series: [{ id: 'dropped', label: 'Measures dropped', color: 'var(--series-2)', values: years.map((y) => dropped.filter((m) => m.dropped_fy === y).length) }, { id: 'lowered', label: 'Targets made easier, other years', color: 'var(--series-1)', values: years.map((y) => lowered.filter((v) => v.fy === y && !prevMissed(v)).length) }, { id: 'lam', label: 'Targets made easier the year after a miss', color: 'var(--ord-5)', values: years.map((y) => loweredAfterMiss.filter((v) => v.fy === y).length) }], format: (v) => fmt.int(v), yTitle: 'Count', aria: 'Integrity by year' });
      }, note: 'The two easier-target segments add up to all targets made easier. Easing after a miss is not by itself a sign of target-chasing: departments also raise targets after a hit about as often as they ease them after a miss (see the Finding), so the pattern mostly reflects targets that track results.' });
      ctx.card({ title: 'By department', sub: 'Easier targets as a share of target changes; click to open', span: 5, render(el) {
        const rows = sc.depts.map((d) => { const vs = ms.vals.filter((v) => ms.byId.get(v.measure).dept === d.id && v.fy > sc.y0); const ch = vs.filter((v) => v.target_change !== 'same'); return { label: d.name, value: ch.length ? ch.filter((v) => v.target_change === 'easier').length / ch.length : null, n: ch.length, small: ch.length < ctx.meta.small_n, sub: `${dropped.filter((m) => m.dept === d.id).length} dropped`, onClick: () => M.state.set({ view: 'dept', id: d.id }) }; }).filter((r) => r.n).sort((a, b) => (b.value || 0) - (a.value || 0));
        if (!rows.length) return ctx.empty(el, 'No measures match');
        return C.bars(el, { rows, rowH: 24, format: (v) => fmt.pct(v), valueHead: 'Easier share', nHead: 'target changes', labelWidth: 200, aria: 'Easier targets by department' });
      } });
      ctx.card({ title: 'The list', sub: 'Every dropped measure and every target made easier', span: 12, render(el) {
        const rows = [...dropped.map((m) => ({ kind: 'Dropped', dept: m.dept, name: m.name, fy: m.dropped_fy, detail: (() => { const v = lastVal(m); return v ? `last reported FY${m.last_fy}: actual ${fmt.num(v.actual)} vs target ${fmt.num(v.target)} (${v.met ? 'met' : 'missed'})` : 'no last value'; })(), flag: (() => { const v = lastVal(m); return v && v.met === false; })() })), ...lowered.map((v) => { const m = ms.byId.get(v.measure), p = ms.at(v.measure, v.fy - 1); return { kind: 'Target made easier', dept: m.dept, name: m.name, fy: v.fy, detail: `target ${p ? fmt.num(p.target) : '–'} → ${fmt.num(v.target)} (${m.unit}); prior year ${p ? (p.met ? 'met' : 'missed') : '–'}; this year ${v.met == null ? 'not reported' : v.met ? 'met' : 'missed'}`, flag: prevMissed(v) }; })];
        if (!rows.length) return ctx.empty(el, 'Nothing to list');
        return C.dataTable(el, { rows, pageSize: 20, sort: 'fy', dir: 'desc', placeholder: 'Filter…', cols: [{ key: 'kind', label: 'What' }, { key: 'dept', label: 'Dept', text: (r) => ctx.deptShort(r.dept) }, { key: 'name', label: 'Measure' }, { key: 'fy', label: 'FY', num: true }, { key: 'detail', label: 'Detail' }, { key: 'flag', label: '', render: (td, r) => { if (r.flag) td.appendChild(ctx.tag('pattern', r.kind === 'Dropped' ? 'was being missed' : 'after a miss')); }, sortVal: (r) => (r.flag ? 1 : 0) }] });
      } });
    },
  };

  // ---------------------------------------------------------------- gaps
  M.views['pf-gaps'] = {
    id: 'pf-gaps', dash: 'pf', nav: 'Budget vs actual', title: 'Budget vs actual', what: 'How far each department’s year-end spending landed from its original budget.',
    how: 'Gap is actual minus original adopted budget, as a share of budget. Positive is overspending (usually overtime), negative is underspending (usually hiring and projects lagging). The heat grid uses a diverging scale around zero.',
    filters: ['years', 'group', 'dept', 'real'], files: FILES,
    render(ctx) {
      const sc0 = scope(ctx), cats = ctx.v('cats', 'operating'), fund = ctx.v('fund', 'all');
      const nonOp = new Set(((ctx.meta.dimensions.char || {}).values || []).filter((c) => /^(capital|other)$/.test(c.id) || /capital|debt/i.test(c.label || '')).map((c) => c.id));
      const spend = sc0.spend.filter((c) => (cats === 'all' || !nonOp.has(c.char)) && (fund === 'all' || c.fund === fund));
      const sc = Object.assign({}, sc0, { spend }), { y1 } = sc, years = ctx.yearList().filter((y) => spend.some((c) => c.fy === y && c.actual != null));
      const tools = ctx.h('div', 'view-tools', ctx.pre); ctx.h('span', 'filter-label', tools, 'This view');
      const sel = (label, key, val, opts) => { const s2 = ctx.h('select', 'ctl', tools); s2.setAttribute('aria-label', label); opts.forEach(([v, l]) => { const o = ctx.h('option', '', s2, l); o.value = v; if (v === val) o.selected = true; }); s2.addEventListener('change', () => ctx.setV(key, s2.value)); };
      sel('Spending categories', 'cats', cats, [['operating', 'Operating categories (excludes capital and debt)'], ['all', 'All categories']]);
      sel('Fund', 'fund', fund, [['all', 'All funds'], ['gf', 'General Fund'], ['other', 'Other funds']]);
      ctx.h('span', 'muted', tools, 'applies to every card below');
      const gap = (rows) => { const b = st_.sum(rows, 'budget'), a = st_.sum(rows.filter((c) => c.actual != null), 'actual'); return b && rows.some((c) => c.actual != null) ? a / b - 1 : null; };
      const deptGap = (d, y) => gap(spend.filter((c) => c.dept === d && c.fy === y));
      const g1 = sc.depts.map((d) => ({ d, g: deptGap(d.id, y1) })).filter((x) => x.g != null);
      Object.assign(ctx.slots, { __small: !g1.length, gap_total: fmt.money(sc.actual(spend, y1) - sc.budget(spend, y1)), gap_pct: fmt.signedPct(gap(spend.filter((c) => c.fy === y1)), 1), over_fmt: fmt.int(g1.filter((x) => x.g > 0.05).length), under_fmt: fmt.int(g1.filter((x) => x.g < -0.05).length) });
      ctx.live('gap');
      ctx.card({ title: `Original budget vs actual, FY${y1}`, sub: 'Gap as a share of the original budget; hover for the dollar amounts', span: 6, render(el) {
        const rows = sc.depts.map((d) => { const a = sc.budget(spend.filter((c) => c.dept === d.id), y1), b = sc.actual(spend.filter((c) => c.dept === d.id), y1); return { label: d.name, value: a && b ? b / a - 1 : null, color: a && b && b / a - 1 < 0 ? 'var(--div-neg-2)' : 'var(--div-pos-2)', sub: `budget ${fmt.money(a)} · actual ${fmt.money(b)} · gap ${fmt.money(b - a)}`, onClick: () => M.state.set({ view: 'dept', id: d.id }) }; }).filter((r) => r.value != null).sort((a, b) => b.value - a.value);
        if (!rows.length) return ctx.empty(el, 'No actuals yet', 'The latest selected year has only a budget; pick an earlier year.');
        C.legend(el, [{ label: 'Spent more than budgeted', color: 'var(--div-pos-2)' }, { label: 'Spent less than budgeted', color: 'var(--div-neg-2)' }]);
        return C.bars(el, { rows, rowH: 26, format: (v) => fmt.signedPct(v, 1), valueHead: 'Actual vs original budget', labelWidth: 200, xTitle: 'Gap, share of original budget', aria: 'Budget vs actual gap' });
      } });
      ctx.card({ title: 'Gap over time', sub: 'Actual ÷ original budget − 1; blue over, red under', span: 6, render(el) {
        const rows = sc.depts.filter((d) => years.some((y) => deptGap(d.id, y) != null));
        if (!rows.length) return ctx.empty(el, 'No actuals yet');
        return C.heatmap(el, { rows: rows.map((d) => d.name), cols: years, colFormat: (y) => `FY${String(y).slice(2)}`, colFormatShort: (y) => `’${String(y).slice(2)}`, values: rows.map((d) => years.map((y) => deptGap(d.id, y))), diverging: true, mid: 0, min: -0.15, max: 0.15, format: (v) => fmt.signedPct(v, 0), labelWidth: 200, cellH: 24, valueLabel: 'gap', onClick: (i) => M.state.set({ view: 'dept', id: rows[i].id }), aria: 'Gap heat grid' });
      }, note: 'Scale clamps at ±15% so one outlier does not wash out the rest; hover for exact values.' });
      ctx.card({ title: `Gaps by category, FY${y1}`, sub: 'Which categories drive over- and underspending', span: 12, render(el) {
        const rows = charGroups(ctx.meta).filter((g) => cats === 'all' || !g.ids.every((id) => nonOp.has(id))).map((g) => { const r = spend.filter((c) => c.fy === y1 && g.ids.includes(c.char)); return { label: g.label, value: st_.sum(r.filter((c) => c.actual != null), (c) => ctx.real(c.actual, y1)) - st_.sum(r, (c) => ctx.real(c.budget, y1)), color: g.color, sub: `budget ${fmt.money(st_.sum(r, (c) => ctx.real(c.budget, y1)))} · actual ${fmt.money(st_.sum(r.filter((c) => c.actual != null), (c) => ctx.real(c.actual, y1)))}` }; });
        if (!spend.some((c) => c.fy === y1 && c.actual != null)) return ctx.empty(el, 'No actuals yet');
        return C.bars(el, { rows, format: (v) => fmt.money(v), valueHead: 'Actual − budget', labelWidth: 220, xTitle: ctx.dollars, aria: 'Gap by category' });
      } });
    },
  };

  // ---------------------------------------------------------------- directory
  M.views['pf-depts'] = {
    id: 'pf-depts', dash: 'pf', nav: 'Departments', title: 'Departments', what: 'Every department with its spending, staffing and measure counts.', headline: false,
    filters: ['years', 'group', 'dept', 'real'], files: Object.assign({ measures: 'performance/measures/measures.json', values: 'performance/measures/values.json', staff: 'performance/staffing/cells.json' }, FILES),
    render(ctx) {
      const sc = scope(ctx), ms = measureScope(ctx, sc), y1 = sc.y1;
      const rows = sc.depts.map((d) => { const v = ms.vals.filter((x) => x.fy === ms.fyR && x.met != null && ms.byId.get(x.measure).dept === d.id); const s = ctx.data.staff.cells.find((x) => x.dept === d.id && x.fy === y1) || {}; return { d, actual: sc.actual(sc.spend.filter((c) => c.dept === d.id), y1), perres: sc.actual(sc.spend.filter((c) => c.dept === d.id), y1) / sc.pop(y1), hc: s.headcount, ot: s.ot_share, n: v.length, met: v.length ? v.filter((x) => x.met).length / v.length : null }; });
      ctx.card({ title: `${rows.length} departments`, sub: `FY${y1} figures (${ctx.dollars}); click to open a scorecard`, span: 12, render(el) {
        return C.dataTable(el, { rows, pageSize: 30, sort: 'actual', placeholder: 'Search departments…', cols: [{ key: 'name', label: 'Department', text: (r) => r.d.name, render: (td, r) => td.appendChild(sc.deptLink(r.d.id)) }, { key: 'group', label: 'Group', text: (r) => (ctx.meta.dimensions.group.values.find((g) => g.id === r.d.group) || {}).label }, { key: 'actual', label: 'Actual spending', num: true, format: (v) => fmt.money(v) }, { key: 'perres', label: 'Per resident', num: true, format: (v) => fmt.moneyLong(v) }, { key: 'hc', label: 'Employees', num: true, format: (v) => fmt.int(v) }, { key: 'ot', label: 'OT share', num: true, format: (v) => fmt.pct(v, 1) }, { key: 'met', label: `Targets met FY${ms.fyR}`, num: true, format: (v, r) => (r.n ? `${fmt.pct(v)} of ${r.n}` : '–') }] });
      } });
    },
  };
  M.pf = { scope, measureScope, CHAR_COLOR, charGroups, dirText };
})();
