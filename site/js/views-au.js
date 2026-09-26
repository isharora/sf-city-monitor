/* views-au.js - dashboard 3: Audit recommendations tracker.
   Scope: one recommendation table filtered by year issued, source, department and topic. */
(function () {
  const M = window.SFCM;
  M.views = M.views || {};
  const C = M.charts, fmt = M.stats.fmt, st_ = M.stats, inList = M.state.inList;
  const FILES = { recs: 'audits/recs/recs.json', reports: 'audits/reports/reports.json' };
  const SRC_COLOR = (s) => `var(--c-${s})`;
  const STATUS_COLOR = { implemented: 'var(--ord-5)', in_progress: 'var(--ord-3)', open: 'var(--ord-1)', not_implementing: 'var(--div-neg-2)', closed_other: 'var(--neutral-2)', unknown: 'var(--neutral)' };
  // "No follow-up status" is the lightest neutral (recessive; DESIGN 6.2 "not reported"), closed-other the darker neutral; both ship with labels.
  const STATUS_SHORT = { implemented: 'Implemented', in_progress: 'In progress', open: 'Open', not_implementing: 'Won’t implement', closed_other: 'Closed, n/a', unknown: 'No status' };
  const UNKNOWN = 'unknown', hasStatus = (r) => r.status !== UNKNOWN;
  /** Rates on this dashboard use recommendations with a recorded follow-up status as the denominator (the BLA publishes no
      follow-up and older reports predate tracking); the no-status count is always shown next to them. */
  const knownShare = (rows, pred) => { const k = rows.filter(hasStatus); return k.length ? k.filter(pred).length / k.length : null; };
  /** Implemented with no month count = CSA inferred it from absence on its two-year open list (only an upper-bound date). */
  const untimed = (r) => r.status === 'implemented' && r.months_to_close == null;
  const AGREE_COLOR = { agree: 'var(--div-pos-2)', partial: 'var(--div-mid)', disagree: 'var(--div-neg-2)', none: 'var(--neutral)' };

  function scope(ctx) {
    const st = ctx.state, [y0, y1] = ctx.years;
    const recs = ctx.data.recs.rows.filter((r) => { const y = +r.date_issued.slice(0, 4); return y >= y0 && y <= y1 && inList(st.source, r.source) && inList(st.dept, r.dept) && inList(st.topic, r.topic); });
    const repIds = new Set(recs.map((r) => r.report)), reports = ctx.data.reports.reports.filter((r) => repIds.has(r.id)), repById = new Map(ctx.data.reports.reports.map((r) => [r.id, r]));
    ctx.feed('recommendations', recs.length, ctx.data.recs.rows.length); ctx.feed('reports', reports.length, ctx.data.reports.reports.length);
    const label = (dim, id) => ((ctx.meta.dimensions[dim].values.find((x) => x.id === id)) || {}).label || id;
    const impl = recs.filter((r) => r.status === 'implemented'), open = recs.filter((r) => r.status === 'open' || r.status === 'in_progress');
    const known = recs.filter(hasStatus), timed = impl.filter((r) => r.months_to_close != null);
    Object.assign(ctx.slots, { __small: recs.length < ctx.meta.small_n, years: fmt.range(y0, y1), recs: recs.length, recs_fmt: fmt.int(recs.length), reports_fmt: fmt.int(reports.length), known: known.length, known_fmt: fmt.int(known.length), nostatus: recs.length - known.length, nostatus_fmt: fmt.int(recs.length - known.length), impl: impl.length, impl_fmt: fmt.int(impl.length), impl_share: fmt.pct(known.length ? impl.length / known.length : null), timed_fmt: fmt.int(timed.length), open: open.length, open_fmt: fmt.int(open.length), median_months: fmt.months(st_.median(timed.map((r) => r.months_to_close))) });
    const short = (id) => { const v = ctx.meta.dimensions.source.values.find((x) => x.id === id); return v ? v.short || v.label : id; };
    const title = (id) => (repById.get(id) || { title: id }).title;
    return { st, y0, y1, recs, reports, repById, label, short, title, impl, open, known, timed, reportLink: (id) => ctx.link(title(id), { view: 'report', id }), deptLink: (id) => ctx.link(ctx.deptName(id), { view: 'dept', id }) };
  }
  const statusPill = (ctx, sc, s) => { const p = ctx.h('span', 'status-pill'); const i = ctx.h('i', '', p); i.style.background = STATUS_COLOR[s] || 'var(--neutral)'; ctx.h('span', '', p, String(sc.label('status', s) || s).replace(/ \(.*/, '')); return p; };

  M.views['au-overview'] = {
    id: 'au-overview', dash: 'au', nav: 'Overview', title: 'Audit recommendations tracker', what: 'What auditors recommended, whether departments agreed, and what happened next.',
    how: 'Three bodies recommend: the Controller’s City Services Auditor (CSA), the Budget and Legislative Analyst (BLA) and the Civil Grand Jury (CGJ). Status is on one shared five-step scale mapped from each body’s vocabulary. Every filter applies to every card.',
    filters: ['years', 'source', 'dept', 'topic'], files: FILES,
    render(ctx) {
      const sc = scope(ctx), { recs, impl, open, known, timed } = sc;
      if (known.length < ctx.meta.small_n) ctx.slots.__small = true;
      ctx.live('ov');
      const tiles = ctx.h('div', 'tiles', ctx.pre);
      const tile = (label, value, foot, patch) => { const t = ctx.h('button', 'tile', tiles); t.type = 'button'; ctx.h('div', 'tile-label', t, label); ctx.h('div', 'tile-value', t, value); ctx.h('div', 'tile-foot', t).appendChild(document.createTextNode(foot)); t.addEventListener('click', () => M.state.set(patch)); };
      tile('Recommendations', fmt.int(recs.length), `${fmt.int(sc.reports.length)} reports, ${fmt.range(sc.y0, sc.y1)}`, { view: 'au-reports' });
      tile('Implemented', fmt.pct(known.length ? impl.length / known.length : null), `${fmt.int(impl.length)} of ${fmt.int(known.length)} with a recorded status; ${fmt.int(recs.length - known.length)} have none`, { view: 'au-status' });
      tile('Median months to implement', fmt.months(st_.median(timed.map((r) => r.months_to_close))), `among ${fmt.int(timed.length)} implemented with a dated closure`, { view: 'au-time' });
      const asOf = new Date(ctx.meta.as_of), twoYearsAgo = new Date(asOf.getFullYear() - 2, asOf.getMonth(), asOf.getDate()).toISOString().slice(0, 10);
      tile('Open or in progress', fmt.int(open.length), `${fmt.int(open.filter((r) => r.date_issued < twoYearsAgo).length)} issued more than 2 years before ${fmt.date(ctx.meta.as_of)}`, { view: 'au-open' });
      const sources = ctx.meta.dimensions.source.values.filter((s) => inList(sc.st.source, s.id)), statuses = ctx.meta.dimensions.status.values;
      ctx.card({ title: 'Status by who recommended', sub: 'Share of recommendations at each status', span: 6, render(el) {
        if (!recs.length) return ctx.empty(el, 'No recommendations match', 'Widen the years or clear a filter.');
        return C.stackedBars(el, { horizontal: true, percent: true, categories: sources.map((s) => s.label), series: statuses.map((s) => ({ id: s.id, label: s.label.replace(/ \(.*/, ''), color: STATUS_COLOR[s.id], values: sources.map((src) => recs.filter((r) => r.source === src.id && r.status === s.id).length) })), n: sources.map((src) => recs.filter((r) => r.source === src.id).length), small: sources.map((src) => recs.filter((r) => r.source === src.id).length < ctx.meta.small_n), nHead: 'recommendations', rawFormat: (v) => `${fmt.int(v)} recs`, labelWidth: 210, aria: 'Status by source' });
      }, note: 'Grey “closed without implementation” is neither success nor failure (superseded or no longer applicable). Red is a department’s decision not to implement. The faintest grey, last, is no follow-up status (the BLA publishes none; older reports predate tracking): it is shown here but left out of every rate on this dashboard.' });
      ctx.card({ title: 'Recommendations issued by year', sub: 'By source; click a column to filter the years', span: 6, render(el) {
        const years = ctx.yearList(); if (!recs.length) return ctx.empty(el, 'No recommendations match');
        return C.stackedBars(el, { categories: years, series: sources.map((s) => ({ id: s.id, label: s.short, color: SRC_COLOR(s.id), values: years.map((y) => recs.filter((r) => r.source === s.id && +r.date_issued.slice(0, 4) === y).length) })), format: (v) => fmt.int(v), yTitle: 'Recommendations', onClick: (i) => M.state.set({ years: [years[i], years[i]] }), annotations: M.commentary.annotationsFor(ctx.commentary, 'au_issued'), aria: 'Issued by year' });
      } });
    },
  };

  M.views['au-status'] = {
    id: 'au-status', dash: 'au', nav: 'Implementation status', title: 'Implementation status', what: 'Where every recommendation stands, by recommender and by department.',
    how: 'One shared scale: implemented, in progress, open, will not implement, closed without implementation. The methods page shows how each body’s own terms (for example Penal Code 933 responses) map onto it.',
    filters: ['years', 'source', 'dept', 'topic'], files: FILES,
    render(ctx) {
      const sc = scope(ctx), { recs } = sc, statuses = ctx.meta.dimensions.status.values;
      const share = (id) => fmt.pct(knownShare(recs, (r) => r.status === id));
      Object.assign(ctx.slots, { prog_share: share('in_progress'), open_share: share('open'), notimpl_share: share('not_implementing') });
      if (sc.known.length < ctx.meta.small_n) ctx.slots.__small = true;
      ctx.live('status');
      const isOpen = (r) => r.status === 'open' || r.status === 'in_progress';
      ctx.card({ title: 'Status by department', sub: 'Sorted by share open or in progress among those with a recorded status; click to open the scorecard', span: 12, render(el) {
        const depts = [...new Set(recs.map((r) => r.dept))].map((d) => { const rows = recs.filter((r) => r.dept === d), o = knownShare(rows, isOpen); return { d, rows, o: o == null ? -1 : o }; }).sort((a, b) => b.o - a.o);
        if (!depts.length) return ctx.empty(el, 'No recommendations match');
        return C.stackedBars(el, { horizontal: true, percent: true, categories: depts.map((x) => ctx.deptName(x.d)), series: statuses.map((s) => ({ id: s.id, label: s.label.replace(/ \(.*/, ''), color: STATUS_COLOR[s.id], values: depts.map((x) => x.rows.filter((r) => r.status === s.id).length) })), n: depts.map((x) => x.rows.length), nHead: 'recommendations', rawFormat: (v) => `${fmt.int(v)} recs`, small: depts.map((x) => x.rows.length < ctx.meta.small_n), labelWidth: 220, rowH: 24, onClick: (i) => M.state.set({ view: 'dept', id: depts[i].d }), aria: 'Status by department' });
      }, note: `Departments with fewer than ${ctx.meta.small_n} recommendations are greyed. A department with many open items may simply have been audited more.` });
      ctx.card({ title: 'Status by topic', sub: 'What kinds of recommendations get done', span: 6, render(el) {
        const topics = ctx.meta.dimensions.topic.values.filter((t) => recs.some((r) => r.topic === t.id));
        if (!topics.length) return ctx.empty(el, 'No recommendations match');
        return C.stackedBars(el, { horizontal: true, percent: true, categories: topics.map((t) => t.label), series: statuses.map((s) => ({ id: s.id, label: s.label.replace(/ \(.*/, ''), color: STATUS_COLOR[s.id], values: topics.map((t) => recs.filter((r) => r.topic === t.id && r.status === s.id).length) })), n: topics.map((t) => recs.filter((r) => r.topic === t.id).length), small: topics.map((t) => recs.filter((r) => r.topic === t.id).length < ctx.meta.small_n), nHead: 'recommendations', rawFormat: (v) => `${fmt.int(v)} recs`, labelWidth: 200, rowH: 24, aria: 'Status by topic' });
      } });
      ctx.card({ title: 'Implemented share by year issued', sub: 'Among recommendations with a recorded status; recent years have had less time', span: 6, render(el) {
        const years = ctx.yearList(), sources = ctx.meta.dimensions.source.values.filter((s) => inList(sc.st.source, s.id));
        if (!recs.length) return ctx.empty(el, 'No recommendations match');
        return C.lines(el, { x: years, series: sources.map((s) => ({ id: s.id, label: s.short, color: SRC_COLOR(s.id), values: years.map((y) => { const rows = recs.filter((r) => r.source === s.id && +r.date_issued.slice(0, 4) === y && hasStatus(r)); return rows.length >= ctx.meta.small_n ? rows.filter((r) => r.status === 'implemented').length / rows.length : null; }) })), format: (v) => fmt.pct(v), maxY: 1, yTitle: 'Implemented', annotations: M.commentary.annotationsFor(ctx.commentary, 'au_impl'), aria: 'Implemented by year' });
      }, note: `Years with fewer than ${ctx.meta.small_n} recommendations with a recorded status from a source are left blank (the BLA publishes no follow-up, so it has no line).` });
    },
  };

  M.views['au-time'] = {
    id: 'au-time', dash: 'au', nav: 'How long it took', title: 'How long it took', what: 'Months from report to implementation, and the share implemented within one, two and three years.',
    how: 'Range bars show the middle half, median and 90th percentile among implemented recommendations. The step curves include recommendations that were never implemented (they never step up), so they correct the survivor bias in the medians; each curve stops where its cohort can no longer be observed. Recommendations known to be implemented only by inference (they dropped off CSA’s two-year open list, so only a latest possible date is known) are left out of the bars, the histogram and the curves.',
    filters: ['years', 'source', 'dept', 'topic'], files: FILES,
    render(ctx) {
      const sc = scope(ctx), { recs, impl } = sc, q = st_.quantiles(impl.map((r) => r.months_to_close));
      Object.assign(ctx.slots, { p75_months: fmt.months(q && q.p75), p90_months: fmt.months(q && q.p90) });
      ctx.live('time');
      const sources = ctx.meta.dimensions.source.values.filter((s) => inList(sc.st.source, s.id));
      ctx.card({ title: 'Months to implement, by recommender and priority', sub: 'Implemented recommendations with a dated closure only', span: 6, render(el) {
        const rows = [];
        sources.forEach((s) => { const v = sc.timed.filter((r) => r.source === s.id).map((r) => r.months_to_close); rows.push({ label: s.label, q: v.length >= ctx.meta.small_n ? st_.quantiles(v) : null, n: v.length, small: v.length < ctx.meta.small_n, color: SRC_COLOR(s.id) }); });
        ['high', 'medium', 'low'].forEach((p) => { const v = sc.timed.filter((r) => r.priority === p).map((r) => r.months_to_close); rows.push({ label: `${p[0].toUpperCase() + p.slice(1)} priority`, q: v.length >= ctx.meta.small_n ? st_.quantiles(v) : null, n: v.length, small: v.length < ctx.meta.small_n, color: 'var(--neutral-2)' }); });
        if (!impl.length) return ctx.empty(el, 'No implemented recommendations match');
        return C.rangeBars(el, { rows, labelWidth: 210, aria: 'Time to implement' });
      }, caveat: 'Time is rounded up to the follow-up cadence (about six months for CSA); recommendations still open are not in these bars.' });
      ctx.card({ title: 'Distribution of months to implement', sub: '6-month bins; last bin is 60+', span: 6, render(el) {
        if (!impl.length) return ctx.empty(el, 'No implemented recommendations match');
        const counts = st_.hist(impl.map((r) => r.months_to_close), 6, 11);
        return C.histogram(el, { counts, labels: counts.map((_, i) => (i === 10 ? '60+' : `${i * 6}`)), unit: 'recommendations', xTitle: 'Months', aria: 'Months histogram' });
      } });
      const curveRecs = recs.filter((r) => !untimed(r)), nUntimed = recs.length - curveRecs.length;
      const shownYears = new Set(ctx.yearList().filter((y) => curveRecs.filter((r) => +r.date_issued.slice(0, 4) === y).length >= ctx.meta.small_n).slice(-6));
      ctx.card({ title: 'Share implemented within N months, by year issued', sub: 'Step curves; never-implemented recommendations count as not yet', span: 12, render(el) {
        const years = ctx.yearList().filter((y) => curveRecs.filter((r) => +r.date_issued.slice(0, 4) === y).length >= ctx.meta.small_n).slice(-6);
        if (!years.length) return ctx.empty(el, 'Too few recommendations per year');
        const asOf = new Date(ctx.meta.as_of), steps = 12, X = Array.from({ length: steps + 1 }, (_, k) => k * 6);
        const series = years.map((y, i) => { const rows = curveRecs.filter((r) => +r.date_issued.slice(0, 4) === y); const ev = rows.map((r) => (r.status === 'implemented' ? r.months_to_close : null)), fu = rows.map((r) => (asOf - new Date(r.date_issued)) / (30.44 * 86400000)); const F = st_.incidence(ev, fu, 6, steps); const maxObs = Math.min(...fu); return { id: String(y), label: `Issued ${y} (n = ${rows.length})`, color: `var(--ord-${Math.min(5, i + 1)})`, values: [0, ...F].map((v, k) => (k * 6 <= maxObs + 6 ? v : null)) }; });
        return C.lines(el, { x: X, xFormat: (m) => `${m} mo`, series, step: true, format: (v) => fmt.pct(v), maxY: 1, yTitle: 'Share implemented', markers: false, endLabels: false, aria: 'Implementation curves' });
      }, note: `Cohorts stop where the youngest recommendation in the year cannot yet have been observed for that long. Left out: ${fmt.int(nUntimed)} recommendations in your selection (${fmt.int(recs.filter((r) => untimed(r) && shownYears.has(+r.date_issued.slice(0, 4))).length)} in the cohorts shown) recorded as implemented with no date (CSA inferred them from their absence on its list of items open more than two years, so only a latest possible date, 24 to 56 months after the report, is known). Counting them as never implemented would pull CSA curves down; an interval-censored estimate is not informative when the interval runs from the report date to two years or more, so they are excluded, which makes affected cohorts read somewhat low at long horizons.` });
    },
  };

  M.views['au-agreement'] = {
    id: 'au-agreement', dash: 'au', nav: 'Did departments agree?', title: 'Did departments agree?', what: 'Departments’ formal responses, and how response relates to what happened next.',
    how: 'Response is at publication (agree, partially agree, disagree, or none recorded). The grid crosses response with eventual status. Disagreeing is legitimate; each report page carries the department’s reasons.',
    filters: ['years', 'source', 'dept', 'topic'], files: FILES,
    render(ctx) {
      const sc = scope(ctx), { recs } = sc, agrees = ctx.meta.dimensions.agreed.values, statuses = ctx.meta.dimensions.status.values;
      // Response shares over recommendations with a recorded response; implemented shares over those with a recorded status.
      const responded = recs.filter((r) => r.agreed !== 'none'), sh = (id) => fmt.pct(responded.length ? responded.filter((r) => r.agreed === id).length / responded.length : null);
      const implOf = (id) => fmt.pct(knownShare(recs.filter((r) => r.agreed === id), (r) => r.status === 'implemented'));
      Object.assign(ctx.slots, { responded_fmt: fmt.int(responded.length), noresp_fmt: fmt.int(recs.length - responded.length), agree_share: sh('agree'), partial_share: sh('partial'), disagree_share: sh('disagree'), impl_agreed: implOf('agree'), impl_disagreed: implOf('disagree') });
      if (sc.known.length < ctx.meta.small_n) ctx.slots.__small = true;
      ctx.live('agree');
      const sources = ctx.meta.dimensions.source.values.filter((s) => inList(sc.st.source, s.id));
      ctx.card({ title: 'Response by recommender', sub: 'Blue agrees, red disagrees, grey is partial or none', span: 6, render(el) {
        if (!recs.length) return ctx.empty(el, 'No recommendations match');
        return C.stackedBars(el, { horizontal: true, percent: true, categories: sources.map((s) => s.label), series: agrees.map((a) => ({ id: a.id, label: a.label, color: AGREE_COLOR[a.id], values: sources.map((s) => recs.filter((r) => r.source === s.id && r.agreed === a.id).length) })), n: sources.map((s) => recs.filter((r) => r.source === s.id).length), small: sources.map((s) => recs.filter((r) => r.source === s.id).length < ctx.meta.small_n), nHead: 'recommendations', rawFormat: (v) => `${fmt.int(v)} recs`, labelWidth: 210, aria: 'Agreement by source' });
      } });
      const kStatuses = statuses.filter((s) => s.id !== UNKNOWN), known = sc.known;
      ctx.card({ title: 'Response × status', sub: 'Share of each response row at each status, among recommendations with a recorded status', span: 6, render(el) {
        if (!known.length) return ctx.empty(el, 'No recommendations with a recorded status match', 'The BLA publishes no follow-up; widen the years or clear a filter.');
        return C.heatmap(el, { rows: agrees.map((a) => a.label), cols: kStatuses.map((s) => STATUS_SHORT[s.id] || s.label.replace(/ \(.*/, '')), values: agrees.map((a) => { const rows = known.filter((r) => r.agreed === a.id); return kStatuses.map((s) => (rows.length ? rows.filter((r) => r.status === s.id).length / rows.length : null)); }), n: agrees.map((a) => kStatuses.map(() => known.filter((r) => r.agreed === a.id).length)), smallN: ctx.meta.small_n, nLabel: 'recommendations with this response', valueLabel: 'of row', labelWidth: 140, cellH: 40, aria: 'Response by status' });
      }, note: `Read across a row: of recommendations with this response, the share at each status. For the Grand Jury, a “will not be implemented” answer is usually also the final status, so the Disagreed row largely repeats the answer. ${fmt.int(recs.length - known.length)} recommendations in your selection have no follow-up status and are left out.` });
      ctx.card({ title: 'Disagreements', sub: 'Every recommendation a department formally disagreed with', span: 12, render(el) {
        const rows = recs.filter((r) => r.agreed === 'disagree'); if (!rows.length) return ctx.empty(el, 'No disagreements match');
        return C.dataTable(el, { rows, pageSize: 15, sort: 'date_issued', dir: 'desc', placeholder: 'Filter…', cols: [{ key: 'date_issued', label: 'Issued', format: (v) => fmt.date(v) }, { key: 'source', label: 'By', text: (r) => sc.label('source', r.source) }, { key: 'dept', label: 'Department', text: (r) => ctx.deptName(r.dept), render: (td, r) => td.appendChild(sc.deptLink(r.dept)) }, { key: 'text', label: 'Recommendation' }, { key: 'status', label: 'Status', text: (r) => sc.label('status', r.status), render: (td, r) => td.appendChild(statusPill(ctx, sc, r.status)) }, { key: 'report', label: 'Report', text: (r) => sc.title(r.report), render: (td, r) => td.appendChild(sc.reportLink(r.report)) }] });
      } });
    },
  };

  M.views['au-repeat'] = {
    id: 'au-repeat', dash: 'au', nav: 'Repeat findings', title: 'Repeat findings', what: 'Recommendations that repeat an earlier one on the same theme at the same department.',
    how: 'A repeat is coded when a later recommendation addresses the same problem at the same department as an earlier one. Clusters were drawn by a model (Claude Opus) within each department, kept only when they span at least two reports in different years, with a confidence stored per pair; they were validated on samples, not link by link: an independent model confirmed 87% of 150 sampled pairs and a hand check confirmed 37 of 40. The chains table links each repeat to its predecessor so the coding can be checked.',
    filters: ['years', 'source', 'dept', 'topic'], files: FILES,
    render(ctx) {
      const sc = scope(ctx), { recs } = sc, all = new Map(ctx.data.recs.rows.map((r) => [r.id, r]));
      const repeats = recs.filter((r) => r.repeat_of), byTopic = st_.group(repeats, (r) => r.topic), top = [...byTopic.entries()].sort((a, b) => b[1].length - a[1].length)[0];
      Object.assign(ctx.slots, { repeats_fmt: fmt.int(repeats.length), repeat_share: fmt.pct(recs.length ? repeats.length / recs.length : null), top_topic: top ? sc.label('topic', top[0]).toLowerCase() : '–', top_topic_fmt: top ? fmt.int(top[1].length) : '–' });
      ctx.live('repeat');
      ctx.card({ title: 'Repeats by department', sub: 'Count of repeat recommendations; n is all recommendations', span: 6, render(el) {
        const depts = [...new Set(repeats.map((r) => r.dept))].map((d) => ({ label: ctx.deptName(d), value: repeats.filter((r) => r.dept === d).length, n: recs.filter((r) => r.dept === d).length, onClick: () => M.state.set({ view: 'dept', id: d }) })).sort((a, b) => b.value - a.value).slice(0, 15);
        if (!depts.length) return ctx.empty(el, 'No repeats match');
        return C.bars(el, { rows: depts, rowH: 26, format: (v) => fmt.int(v), valueHead: 'Repeats', nHead: 'recommendations', labelWidth: 210, aria: 'Repeats by department' });
      } });
      ctx.card({ title: 'Repeats by topic', sub: 'Share of recommendations that repeat an earlier one', span: 6, render(el) {
        const topics = ctx.meta.dimensions.topic.values.map((t) => ({ label: t.label, value: recs.filter((r) => r.topic === t.id).length ? repeats.filter((r) => r.topic === t.id).length / recs.filter((r) => r.topic === t.id).length : null, n: recs.filter((r) => r.topic === t.id).length })).filter((r) => r.n).sort((a, b) => (b.value || 0) - (a.value || 0));
        if (!topics.length) return ctx.empty(el, 'No recommendations match');
        return C.bars(el, { rows: topics, rowH: 26, format: (v) => fmt.pct(v), valueHead: 'Repeat share', nHead: 'recommendations', labelWidth: 210, aria: 'Repeats by topic' });
      } });
      ctx.card({ title: 'Chains', sub: 'Each repeat with the recommendation it repeats', span: 12, render(el) {
        if (!repeats.length) return ctx.empty(el, 'No repeats match');
        return C.dataTable(el, { rows: repeats, pageSize: 15, sort: 'date_issued', dir: 'desc', placeholder: 'Filter…', cols: [{ key: 'dept', label: 'Department', text: (r) => ctx.deptName(r.dept), render: (td, r) => td.appendChild(sc.deptLink(r.dept)) }, { key: 'topic', label: 'Topic', text: (r) => sc.label('topic', r.topic) }, { key: 'date_issued', label: 'Repeat issued', format: (v) => fmt.date(v) }, { key: 'source', label: 'By', text: (r) => sc.short(r.source) }, { key: 'status', label: 'Repeat status', text: (r) => sc.label('status', r.status), render: (td, r) => td.appendChild(statusPill(ctx, sc, r.status)) }, { key: 'prev', label: 'Repeats', text: (r) => { const p = all.get(r.repeat_of); return p ? `${fmt.date(p.date_issued)} · ${sc.label('status', p.status).replace(/ \(.*/, '')}` : r.repeat_of; }, render: (td, r) => { const p = all.get(r.repeat_of); if (p) { td.appendChild(sc.reportLink(p.report)); ctx.h('span', 'sub', td, ` issued ${fmt.date(p.date_issued)}, ${sc.label('status', p.status).replace(/ \(.*/, '').toLowerCase()}`); } } }] });
      } });
    },
  };

  M.views['au-open'] = {
    id: 'au-open', dash: 'au', nav: 'Open and consequential', title: 'Open and consequential', what: 'The open recommendations that matter most, ranked by a published consequence score.',
    how: 'Consequence (1–10) adds points for auditor priority, dollars at stake stated in the report, age while a follow-up records it open, whether the department declined or disputed it, whether it repeats an earlier recommendation, and whether its topic is public safety, health or ethics; the full rule is on the methods page and each score carries its reason. Open includes “in progress”. Dollar figures overlap between recommendations and reports, so they are never added up.',
    filters: ['years', 'source', 'dept', 'topic'], files: FILES,
    render(ctx) {
      const sc = scope(ctx), { open } = sc, high = open.filter((r) => r.consequence && r.consequence.score >= 7);
      // Dollar figures overlap across recommendations and reports (the module's rule: never total them): count and largest single figure only.
      const withDollars = open.filter((r) => r.dollars_at_stake > 0), maxD = withDollars.reduce((m, r) => (!m || r.dollars_at_stake > m.dollars_at_stake ? r : m), null);
      Object.assign(ctx.slots, { high_fmt: fmt.int(high.length), dollars_n_fmt: fmt.int(withDollars.length), dollars_max: maxD ? fmt.money(maxD.dollars_at_stake) : '–' });
      ctx.live('open');
      ctx.fair('A consequence score is a reading aid built from published rules, not an audit judgment. “Open” often means work is in progress; each row links to the report so the department’s latest response can be checked. Dollar figures come from the reports and overlap between recommendations and reports, so they are never added up: ' + (withDollars.length ? `${fmt.int(withDollars.length)} of these ${fmt.int(open.length)} open recommendations state one, and the largest single figure is ${fmt.money(maxD.dollars_at_stake)} (${sc.title(maxD.report)}).` : 'none of these open recommendations states one.'), 'How to read the ranking');
      ctx.card({ title: 'Open recommendations by consequence score', sub: 'Count at each score; 7+ shaded', span: 5, render(el) {
        if (!open.length) return ctx.empty(el, 'No open recommendations match');
        const counts = Array.from({ length: 10 }, (_, i) => open.filter((r) => r.consequence.score === i + 1).length);
        return C.histogram(el, { counts, labels: counts.map((_, i) => String(i + 1)), highlight: [6, 7, 8, 9], unit: 'open recommendations', xTitle: 'Consequence score', aria: 'Score histogram' });
      } });
      ctx.card({ title: 'Age of open recommendations', sub: 'Months since the report, by recommender', span: 7, render(el) {
        const sources = ctx.meta.dimensions.source.values.filter((s) => inList(sc.st.source, s.id)), asOf = new Date(ctx.meta.as_of);
        const rows = sources.map((s) => { const v = open.filter((r) => r.source === s.id).map((r) => (asOf - new Date(r.date_issued)) / (30.44 * 86400000)); return { label: s.label, q: v.length >= ctx.meta.small_n ? st_.quantiles(v) : null, n: v.length, small: v.length < ctx.meta.small_n, color: SRC_COLOR(s.id) }; });
        if (!open.length) return ctx.empty(el, 'No open recommendations match');
        return C.rangeBars(el, { rows, labelWidth: 210, xTitle: 'Months open', aria: 'Age of open recommendations' });
      } });
      ctx.card({ title: 'The list', sub: 'Ranked by consequence, then age', span: 12, render(el) {
        const rows = open.slice().sort((a, b) => b.consequence.score - a.consequence.score || a.date_issued.localeCompare(b.date_issued));
        if (!rows.length) return ctx.empty(el, 'No open recommendations match');
        return C.dataTable(el, { rows, pageSize: 20, sort: 'score', placeholder: 'Filter…', cols: [{ key: 'score', label: 'Score', num: true, sortVal: (r) => r.consequence.score, render: (td, r) => { td.appendChild(ctx.tag(r.consequence.score >= 7 ? 'high' : 'pattern', String(r.consequence.score))); } }, { key: 'dept', label: 'Department', text: (r) => ctx.deptName(r.dept), render: (td, r) => td.appendChild(sc.deptLink(r.dept)) }, { key: 'text', label: 'Recommendation', text: (r) => r.text, render: (td, r) => { td.textContent = r.text; if (r.consequence.why) ctx.h('span', 'sub', td, ' ' + r.consequence.why).style.color = 'var(--text-muted)'; } }, { key: 'date_issued', label: 'Issued', format: (v) => fmt.date(v) }, { key: 'priority', label: 'Priority' }, { key: 'agreed', label: 'Response', text: (r) => sc.label('agreed', r.agreed) }, { key: 'status', label: 'Status', text: (r) => sc.label('status', r.status), render: (td, r) => td.appendChild(statusPill(ctx, sc, r.status)) }, { key: 'dollars_at_stake', label: 'Dollars at stake', num: true, format: (v) => (v == null ? '–' : fmt.money(v)) }, { key: 'report', label: 'Report', text: (r) => sc.title(r.report), render: (td, r) => td.appendChild(sc.reportLink(r.report)) }] });
      } });
    },
  };

  M.views['au-reports'] = {
    id: 'au-reports', dash: 'au', nav: 'Reports', title: 'Reports', what: 'Every report with its recommendations and their status.', headline: false,
    filters: ['years', 'source', 'dept', 'topic'], files: FILES,
    render(ctx) {
      const sc = scope(ctx);
      const rows = sc.reports.map((r) => { const recs = sc.recs.filter((k) => k.report === r.id); return Object.assign({}, r, { n_sel: recs.length, impl: knownShare(recs, (k) => k.status === 'implemented'), open: recs.filter((k) => k.status === 'open' || k.status === 'in_progress').length }); });
      ctx.card({ title: `${fmt.int(rows.length)} reports`, sub: 'Counts reflect the current filters; click to open', span: 12, render(el) {
        return C.dataTable(el, { rows, pageSize: 30, sort: 'date', dir: 'desc', placeholder: 'Search reports…', cols: [{ key: 'date', label: 'Date', format: (v) => fmt.date(v) }, { key: 'source', label: 'By', text: (r) => sc.label('source', r.source) }, { key: 'title', label: 'Report', render: (td, r) => td.appendChild(sc.reportLink(r.id)) }, { key: 'depts', label: 'Departments', text: (r) => r.depts.map(ctx.deptShort).join(', ') }, { key: 'topic', label: 'Topic', text: (r) => sc.label('topic', r.topic) }, { key: 'n_sel', label: 'Recs (selected)', num: true }, { key: 'impl', label: 'Implemented (of those with a status)', num: true, format: (v) => fmt.pct(v) }, { key: 'open', label: 'Open', num: true }] });
      } });
    },
  };
  M.au = { scope, SRC_COLOR, STATUS_COLOR, STATUS_SHORT, AGREE_COLOR, statusPill, hasStatus, knownShare, untimed };
})();
