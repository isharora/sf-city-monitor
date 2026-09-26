/* views-nw.js - dashboard 4: Money network.
   Scope: flows filtered by date, flow type, entity type (either end) and minimum amount.
   Fairness is designed in: individuals only as aggregates; timing labelled as a pattern, not
   proof; rules cited beside every "appears to warrant review"; base rates shown. */
(function () {
  const M = window.SFCM;
  M.views = M.views || {};
  const C = M.charts, fmt = M.stats.fmt, st_ = M.stats, inList = M.state.inList;
  const FILES = { ents: 'network/entities.json', flows: 'network/flows.json' };
  const TYPE_COLOR = (t) => `var(--c-${t}, var(--neutral))`;
  const FLOW_COLOR = { contribution: 'var(--series-7)', behested: 'var(--series-5)', lobby_contact: 'var(--series-3)', lobby_payment: 'var(--series-4)', contract: 'var(--series-2)', payment: 'var(--series-1)' };

  function scope(ctx, opts) {
    opts = opts || {};
    const st = ctx.state, [y0, y1] = ctx.years, ents = new Map(ctx.data.ents.entities.map((e) => [e.id, e]));
    const typeOf = (id) => (ents.get(id) || {}).type;
    const flows = ctx.data.flows.flows.filter((f) => { const y = +f.date.slice(0, 4); if (y < y0 || y > y1) return false; if (!opts.ignoreFlow && !inList(st.flow, f.type)) return false; if (!opts.ignoreEtype && st.etype.length && !(st.etype.includes(typeOf(f.from)) || st.etype.includes(typeOf(f.to)))) return false; if (!opts.ignoreAmt && st.amt && !(f.amount != null && f.amount >= st.amt)) return false; return true; });
    ctx.feed('flows (aggregated transactions)', flows.length, ctx.data.flows.flows.length);
    const entSet = new Set(flows.flatMap((f) => [f.from, f.to]));
    ctx.feed('entities connected', entSet.size, ents.size);
    const typeLabel = (t) => ((ctx.meta.dimensions.etype.values.find((x) => x.id === t)) || {}).label || t;
    const flowLabel = (t) => ((ctx.meta.dimensions.flow.values.find((x) => x.id === t)) || {}).label || t;
    const name = (id) => (ents.get(id) || { name: id }).name;
    const link = (id) => { const e = ents.get(id); if (!e) return document.createTextNode(id); const patch = e.type === 'official' ? { view: 'official', id } : e.type === 'department' && e.code ? { view: 'dept', id: e.code } : { view: 'org', id: e.nonprofit_org || id }; return ctx.link(e.name, patch); };
    Object.assign(ctx.slots, { years: fmt.range(y0, y1), flows: flows.length, flows_fmt: fmt.int(flows.length), entities_fmt: fmt.int(entSet.size), total: fmt.money(st_.sum(flows, (f) => f.amount || 0)) });
    return { st, y0, y1, ents, flows, entSet, typeOf, typeLabel, flowLabel, name, link, inYears: (d) => { const y = +d.slice(0, 4); return y >= y0 && y <= y1; } };
  }
  function fairnessBox(ctx) { ctx.fair(ctx.meta.fairness.individuals + ' ' + ctx.meta.fairness.timing, 'Fairness rules on this dashboard'); }
  /** A ban-window record may carry the review tag only when the data give the reason and both conditions hold. */
  const isReview = (r) => r.review === 'appears_to_warrant_review' && !!r.why && r.inside_window && r.covered_official;
  const DAY = 86400000, toDay = (s) => Math.floor(Date.parse(s + 'T00:00:00Z') / DAY);
  /** Share of days in [lo, hi] covered by the union of intervals [[a, b], ...] (ISO dates, end exclusive). */
  function coverage(intervals, lo, hi) {
    const L = toDay(lo), H = toDay(hi); if (!(H > L)) return 0;
    const iv = intervals.map(([a, b]) => [Math.max(L, toDay(a)), Math.min(H, toDay(b))]).filter(([a, b]) => b >= a).sort((x, y) => x[0] - y[0]);
    let days = 0, cur = null;
    for (const [a, b] of iv) { if (cur && a <= cur[1]) cur[1] = Math.max(cur[1], b); else { if (cur) days += cur[1] - cur[0]; cur = [a, b]; } }
    if (cur) days += cur[1] - cur[0];
    return days / (H - L);
  }
  const pts = (x) => fmt.signedPct(x, 1).replace('%', ' points');

  /** The matched ban-window base rate from analyses/ban_window.json › base_rates, or null when the export lacks it. */
  function matchedBase(ban) {
    const b = (ban && ban.base_rates) || {}, ok = (x) => typeof x === 'number' && x >= 0 && x <= 1;
    if (!ok(b.expected_share_matched) || !ok(b.observed_share_matched)) return null;
    const period = (String(b.matched_note || '').match(/\b(\d{4})-(\d{4})\b/) || []).slice(1);
    return { expected: b.expected_share_matched, observed: b.observed_share_matched, n: b.matched_n_records || null, ci: Array.isArray(b.matched_difference_95ci) && b.matched_difference_95ci.length === 2 ? b.matched_difference_95ci : null,
      note: b.matched_note || '', period: period.length ? `${period[0]} to ${period[1]}` : null, expected_fmt: fmt.pct(b.expected_share_matched, 1), observed_fmt: fmt.pct(b.observed_share_matched, 1) };
  }

  // ---------------------------------------------------------------- overview
  M.views['nw-overview'] = {
    id: 'nw-overview', dash: 'nw', nav: 'Overview', title: 'Money network', what: 'Campaign contributions, behested payments, lobbying and contracts, connected through the entities that appear in more than one of them.',
    how: 'Every flow is a disclosed transaction with a date and usually an amount, aggregated so that private individuals never appear by name. Filters apply to every card: years by transaction date, flow type, entity type (either end of a flow) and a minimum amount (flows without an amount, such as lobbying contacts, drop out when a minimum is set).',
    filters: ['years', 'flow', 'etype', 'amt'], files: Object.assign({ ban: 'network/analyses/ban_window.json' }, FILES),
    render(ctx) {
      const sc = scope(ctx), { flows } = sc, years = ctx.yearList(), types = ctx.meta.dimensions.flow.values.filter((t) => inList(sc.st.flow, t.id));
      ctx.live('ov'); fairnessBox(ctx);
      const flowIds = new Set(flows.map((f) => f.id)), banIn = ctx.data.ban.records.filter((r) => flowIds.has(r.flow)), review = banIn.filter(isReview);
      ctx.feed('contractor-affiliated contribution records', banIn.length, ctx.data.ban.records.length);
      const tiles = ctx.h('div', 'tiles', ctx.pre), mbO = matchedBase(ctx.data.ban);
      const tile = (label, value, foot, patch) => { const t = ctx.h('button', 'tile', tiles); t.type = 'button'; ctx.h('div', 'tile-label', t, label); ctx.h('div', 'tile-value', t, value); ctx.h('div', 'tile-foot', t).appendChild(document.createTextNode(foot)); t.addEventListener('click', () => M.state.set(patch)); };
      tile('Flows in your filters', fmt.int(flows.length), `${fmt.money(st_.sum(flows, (f) => f.amount || 0))} with a dollar amount`, { view: 'nw-graph' });
      tile('Entities connected', fmt.int(sc.entSet.size), `${fmt.int([...sc.entSet].filter((id) => sc.typeOf(id) === 'individuals').length)} aggregate individual nodes`, { view: 'nw-entities' });
      tile('Behested payments', fmt.money(st_.sum(flows.filter((f) => f.type === 'behested'), 'amount')), `${fmt.int(flows.filter((f) => f.type === 'behested').length)} payments`, { view: 'nw-behested' });
      tile(ctx.ruleOf('ban') ? `Contributions that appear to warrant review (${ctx.ruleOf('ban').cite.replace(/^.*(§[\d.]+).*$/, '$1')})` : 'Contributions inside a ban window to a covered official', fmt.int(review.length), `of ${fmt.int(banIn.length)} contractor-affiliated records · a pattern worth checking, not proof` + (mbO ? ` · all years: ${mbO.observed_fmt} of principals’ contributions fell inside a window vs ${mbO.expected_fmt} expected by chance (matched benchmark, not filtered)` : ''), { view: 'nw-ban' });
      ctx.card({ title: 'Dollars by year and flow type', sub: 'Lobbying contacts have no amount and are not in this chart', span: 7, render(el) {
        const dollar = flows.filter((f) => f.amount != null); if (!dollar.length) return ctx.empty(el, 'No flows with an amount match');
        return C.stackedBars(el, { categories: years, series: types.filter((t) => t.id !== 'lobby_contact').map((t) => ({ id: t.id, label: t.label, color: FLOW_COLOR[t.id], values: years.map((y) => st_.sum(dollar.filter((f) => f.type === t.id && +f.date.slice(0, 4) === y), 'amount')) })), yTitle: 'Dollars', annotations: M.commentary.annotationsFor(ctx.commentary, 'nw_dollars'), aria: 'Dollars by year' });
      }, note: 'City payments and contract values dwarf contributions by design; use the flow-type filter to look at one channel at a time.' });
      ctx.card({ title: 'Who is connected', sub: 'Entities in the current flows, by type', span: 5, render(el) {
        const rows = ctx.meta.dimensions.etype.values.map((t) => ({ label: t.label, value: [...sc.entSet].filter((id) => sc.typeOf(id) === t.id).length, color: TYPE_COLOR(t.id) })).filter((r) => r.value);
        if (!rows.length) return ctx.empty(el, 'No entities match');
        return C.bars(el, { rows, format: (v) => fmt.int(v), valueHead: 'Entities', labelWidth: 220, aria: 'Entities by type' });
      }, note: 'Individuals are counted as aggregate nodes (one per affiliated organization, plus one for everyone else), never as people.' });
    },
  };

  // ---------------------------------------------------------------- graph
  M.views['nw-graph'] = {
    id: 'nw-graph', dash: 'nw', nav: 'The network', title: 'The network', what: 'Entities as nodes, dated and amount-weighted flows as edges.',
    how: 'The graph shows only the strongest edges (choose how many), so it stays readable; searching for or clicking an entity adds its whole neighborhood and dims the rest. Node size is connected dollars, colour is entity type, edge thickness is amount (contacts weighted by count). Individuals appear only as dashed grey aggregate nodes. The table twin lists every drawn edge.',
    filters: ['years', 'flow', 'etype', 'amt'], files: Object.assign({ ban: 'network/analyses/ban_window.json' }, FILES), optionalFiles: ['ban'],
    render(ctx) {
      const sc = scope(ctx), sel = ctx.v('focus', null), maxEdges = Math.min(240, +ctx.v('edges', 80) || 80);
      const banWhy = new Map(((ctx.data.ban && ctx.data.ban.records) || []).filter(isReview).map((r) => [r.flow, r.why]));
      fairnessBox(ctx);
      const wrap = ctx.h('div', 'nw-wrap', ctx.grid); wrap.classList.add('col-12');
      const left = ctx.h('section', 'card', wrap), side = ctx.h('aside', 'card nw-side', wrap);
      const head = ctx.h('div', 'card-head', left); const titles = ctx.h('div', 'card-titles', head); ctx.h('h2', 'card-title', titles, 'Money flows between entities'); const sub = ctx.h('p', 'card-sub', titles);
      const tools = ctx.h('div', 'nw-tools', left);
      const search = ctx.h('input', '', tools); search.type = 'search'; search.placeholder = 'Find an entity to focus…'; search.setAttribute('aria-label', 'Find an entity'); search.setAttribute('list', 'nw-ents');
      const dl = ctx.h('datalist', '', tools); dl.id = 'nw-ents'; [...sc.entSet].map((id) => sc.ents.get(id)).filter(Boolean).sort((a, b) => a.name.localeCompare(b.name)).forEach((e) => { const o = ctx.h('option', '', dl); o.value = e.name; });
      search.addEventListener('change', () => { const e = [...sc.ents.values()].find((x) => x.name.toLowerCase() === search.value.trim().toLowerCase()); if (e) ctx.setV('focus', e.id); });
      const selE = ctx.h('select', 'ctl', tools); selE.setAttribute('aria-label', 'How many edges to show'); [[40, 'Top 40 edges'], [80, 'Top 80 edges'], [160, 'Top 160 edges'], [240, 'Top 240 edges (most drawn at once)']].forEach(([v, l]) => { const o = ctx.h('option', '', selE, l); o.value = v; if (v === maxEdges) o.selected = true; }); selE.addEventListener('change', () => ctx.setV('edges', selE.value));
      if (sel) { const clr = ctx.h('button', 'btn', tools, 'Clear focus'); clr.addEventListener('click', () => ctx.setV('focus', '')); }
      const tb = ctx.h('button', 'tbl-btn', tools, 'Table'); tb.setAttribute('aria-pressed', 'false');
      const canvas = ctx.h('div', 'nw-canvas', left);
      const lg = ctx.h('div', 'nw-legend', left); ctx.meta.dimensions.etype.values.filter((t) => t.id !== 'official').forEach((t) => { const s = ctx.h('span', '', lg); const d = ctx.h('i', 'dot', s); d.style.background = TYPE_COLOR(t.id); if (t.id === 'individuals') d.style.border = '1.5px dashed var(--surface-1)'; ctx.h('span', '', s, t.label); });
      if (!sc.flows.length) { ctx.empty(canvas, 'No flows match', 'Widen the years, lower the minimum amount or add a flow type.'); return; }
      const res = M.network.graph(canvas, { entities: sc.ents, edges: sc.flows, selected: sel || null, maxEdges, labelTop: 10, height: 620, clusterLabels: { officials: 'Officials and committees', city: 'City departments', lobbying: 'Lobbyists', nonprofits: 'Nonprofits', contractors_and_donors: 'Contractors, PACs and affiliated individuals' }, typeLabel: sc.typeLabel, flowLabel: sc.flowLabel, onSelect: (id) => ctx.setV('focus', id === sel ? '' : id), aria: 'Network graph' });
      sub.textContent = `${fmt.int(res.nodes)} entities · ${fmt.int(res.edges)} edges drawn · ${fmt.int(res.hidden)} weaker edges hidden`;
      Object.assign(ctx.slots, { nodes_fmt: fmt.int(res.nodes), edges: res.edges, edges_fmt: fmt.int(res.edges), hidden_fmt: fmt.int(res.hidden), total: fmt.money(res.total) }); ctx.live('graph');
      let table = false; tb.addEventListener('click', () => { table = !table; tb.setAttribute('aria-pressed', String(table)); tb.textContent = table ? 'Graph' : 'Table'; canvas.innerHTML = ''; if (table) { canvas.style.height = 'auto'; const w = ctx.h('div', 'table-wrap', canvas); const t = ctx.h('table', 'data-table', w); const tr = ctx.h('tr', '', ctx.h('thead', '', t)); res.table.head.forEach((x) => ctx.h('th', '', tr, x)); const tbd = ctx.h('tbody', '', t); res.table.rows.forEach((r) => { const row = ctx.h('tr', '', tbd); r.forEach((x) => ctx.h('td', '', row, x)); }); } else { canvas.style.height = ''; M.network.graph(canvas, { entities: sc.ents, edges: sc.flows, selected: sel || null, maxEdges, labelTop: 14, height: 620, clusterLabels: {}, typeLabel: sc.typeLabel, flowLabel: sc.flowLabel, onSelect: (id) => ctx.setV('focus', id === sel ? '' : id) }); } });
      // side panel
      if (!sel || !sc.ents.get(sel)) { ctx.h('h3', '', side, 'Select an entity'); ctx.h('p', '', side, 'Click a node or search above to see its flows, the rules that apply, and a link to its profile.').style.color = 'var(--text-secondary)'; ctx.h('h3', '', side, 'Largest flows shown').style.marginTop = '14px'; const ul = ctx.h('ul', 'list', side); res.table.rows.slice(0, 8).forEach((r) => { const li = ctx.h('li', '', ul); const l = ctx.h('span', '', li); l.textContent = `${r[0]} → ${r[1]}`; ctx.h('span', 'sub', l, r[2]); ctx.h('span', 'tnum', li, r[3]); }); return; }
      const e = sc.ents.get(sel); ctx.h('h3', '', side, e.name); const tp = ctx.h('div', 'type', side); const d = ctx.h('i', 'dot', tp); d.style.background = TYPE_COLOR(e.type); ctx.h('span', '', tp, sc.typeLabel(e.type) + (e.sample_note ? ' · ' + e.sample_note : ''));
      if (e.type === 'individuals') ctx.h('p', '', side, `${fmt.int(e.count)} individuals aggregated. ${e.basis || 'Individuals are never named.'}`).style.fontSize = '12.5px';
      else side.appendChild(sc.link(sel)).textContent = 'Open profile →';
      const mine = sc.flows.filter((f) => f.from === sel || f.to === sel);
      const dl2 = ctx.h('dl', 'kv', side); dl2.style.marginTop = '10px';
      const kv = (k, v) => { ctx.h('dt', '', dl2, k); ctx.h('dd', '', dl2, v); };
      kv('Flows', fmt.int(mine.length)); kv('Dollars in', fmt.money(st_.sum(mine.filter((f) => f.to === sel), (f) => f.amount || 0))); kv('Dollars out', fmt.money(st_.sum(mine.filter((f) => f.from === sel), (f) => f.amount || 0))); kv('Neighbors', fmt.int(res.neighbors.size - 1));
      ctx.h('h3', '', side, 'Largest flows').style.marginTop = '14px';
      const ul = ctx.h('ul', 'list', side);
      mine.slice().sort((a, b) => (b.amount || 0) - (a.amount || 0)).slice(0, 10).forEach((f) => { const li = ctx.h('li', '', ul); const l = ctx.h('span', '', li); l.textContent = f.from === sel ? `→ ${sc.name(f.to)}` : `← ${sc.name(f.from)}`; ctx.h('span', 'sub', l, `${sc.flowLabel(f.type)} · ${fmt.date(f.date)}`); if (f.flags && f.flags.in_ban_window && banWhy.get(f.id)) l.appendChild(ctx.review('ban', banWhy.get(f.id))); ctx.h('span', 'tnum', li, f.amount != null ? fmt.money(f.amount) : f.type === 'lobby_contact' ? `${fmt.int(f.count)} contacts` : 'no amount'); });
    },
  };

  // ---------------------------------------------------------------- ban window
  M.views['nw-ban'] = {
    id: 'nw-ban', dash: 'nw', nav: 'Contributions and the ban window', title: 'Contractor contributions and the ban window', what: 'Contributions by the disclosed principals of city contractors, placed in time against the contracts those contractors won.',
    how: 'Each dot is a contribution by a person name-matched to a principal (board member, officer or owner of more than 10%) listed on the contractor’s SFEC-126(f)4 filings, placed by days from the nearest contract approval; the shaded band is the §1.126 window (proposal to 12 months after approval). Compare the observed share inside a window with the matched share expected by chance, shown below.',
    filters: ['years', 'etype', 'amt'], absent: { flow: 'this view is contributions only' }, files: Object.assign({ ban: 'network/analyses/ban_window.json' }, FILES),
    render(ctx) {
      const sc = scope(ctx, { ignoreFlow: true }), ban = ctx.data.ban;
      const flowIds = new Set(sc.flows.map((f) => f.id));
      const recs = ban.records.filter((r) => flowIds.has(r.flow));
      ctx.feed('contractor-affiliated contribution records', recs.length, ban.records.length); const knownC = new Set(ban.contracts.map((c) => c.contract)); ctx.feed('contracts with an SFEC-126(f)4 notice', new Set(recs.map((r) => r.nearest_contract).filter((c) => knownC.has(c))).size, knownC.size);
      const inside = recs.filter((r) => r.inside_window), covered = recs.filter((r) => r.inside_window && r.covered_official), flagged = covered.filter(isReview);
      // Base rate for exactly the records in view, over the selected years (capped at the data's as-of date).
      // Base rate: the exporter's matched benchmark (approvals that list the donor and whose approving office covered the
      // recipient, days weighted by the election calendar). The contract's pooled expected_share_if_unrelated counts every
      // window a contractor has and overstates chance, so it is never shown.
      const mb = matchedBase(ban);
      Object.assign(ctx.slots, { __small: recs.length < ctx.meta.small_n, records: recs.length, records_fmt: fmt.int(recs.length), contracts_fmt: fmt.int(new Set(recs.map((r) => r.nearest_contract)).size), inside_fmt: fmt.int(inside.length), inside_share: fmt.pct(recs.length ? inside.length / recs.length : null), expected_share: mb ? mb.expected_fmt : null, observed_matched: mb ? mb.observed_fmt : null, matched_n_fmt: mb ? fmt.int(mb.n) : null, covered_fmt: fmt.int(flagged.length), covered_all_fmt: fmt.int(covered.length) });
      ctx.live('ban');
      ctx.rule('ban');
      ctx.fair(`${ctx.meta.fairness.timing} ${ctx.meta.fairness.review} The records here are contributions by people name-matched to the principals listed on the contractor’s SFEC-126(f)4 filings (board members, officers, owners of more than 10%), not by employer; they are never named here. Employees who name a contractor as their employer are not covered by §1.126 and are not in this view.`, 'Read this view with the base rate');
      const contractOf = new Map(ban.contracts.map((c) => [c.contract, c]));
      ctx.card({ title: 'Contributions by days from the nearest contract approval', sub: 'Shaded: the §1.126 window (about 6 months before to 12 months after approval); colour: outside, inside, inside and to a covered official', span: 12, render(el) {
        if (!recs.length) return ctx.empty(el, 'No records match');
        return C.dotStrip(el, { points: recs.map((r) => ({ t: r.days_from_approval, amount: r.amount, label: `${sc.name(r.contractor)} → ${sc.name(r.committee)}`, color: r.covered_official ? 'var(--div-neg-2)' : r.inside_window ? 'var(--series-2)' : 'var(--neutral-2)', tag: isReview(r) && ctx.ruleOf('ban') ? `Appears to warrant review (${ctx.ruleOf('ban').cite}): inside the window and to a covered official. Pattern worth checking, not proof.` : r.inside_window && r.covered_official ? 'Inside a window and to a covered official; no reason recorded, so shown as a pattern only' : r.inside_window ? 'Inside a window, but the committee’s official does not approve this contract' : 'Outside every window', sub: `${fmt.date(r.date)} · ${fmt.int(r.count)} individuals, aggregated · contract ${r.nearest_contract || '–'}${contractOf.get(r.nearest_contract) ? ' approved ' + fmt.date(contractOf.get(r.nearest_contract).approval_date) : ''}` })), window: [-183, 365], windowLabel: '§1.126 window (approx.)', min: -1830, max: 1830, xTitle: 'Days from contract approval', zeroLabel: 'approval', height: 260, aria: 'Ban window dot strip' });
      }, note: 'Dot size is amount. The window is drawn at its typical position; each record is judged against its own contract’s exact window and the rule in force on that date.' });
      ctx.card({ title: 'Observed vs expected by chance', sub: mb ? `Matched benchmark: ${fmt.int(mb.n)} contributions${mb.period ? ', ' + mb.period : ''}, to recipients covered for the approval` : 'Matched benchmark', span: 12, render(el) {
        if (!mb) return ctx.empty(el, 'Matched benchmark not in this export', 'The pooled chance figure in the data contract counts every window a contractor has and overstates chance, so the site does not show it.');
        return C.bars(el, { rows: [{ label: 'Expected by chance (matched)', value: mb.expected, color: 'var(--neutral-2)', sub: mb.note || '' }, { label: 'Observed (matched)', value: mb.observed, n: mb.n, color: 'var(--series-2)', sub: mb.ci ? `Observed minus expected: ${pts(mb.observed - mb.expected)} (95% interval ${pts(mb.ci[0])} to ${pts(mb.ci[1])})` : '' }], format: (v) => fmt.pct(v, 1), valueHead: 'Share inside a window', nHead: 'contributions', labelWidth: 220, maxX: 0.5, aria: 'Observed vs expected by chance' });
      }, note: `The benchmark is computed by the data team for the whole period and does not change with your filters. For the ${fmt.int(recs.length)} records in view, ${fmt.pct(recs.length ? inside.length / recs.length : null)} fall inside any post-approval window and ${fmt.pct(recs.length ? covered.length / recs.length : null)} inside a window and to a covered official; those shares include recipients the ban does not reach, so compare them with the dot strip, not with the benchmark.`, caveat: 'A simpler benchmark that pools every window a contractor has, including approvals by offices that do not cover the recipient, reads much higher and overstates chance; the site does not use it. Only the gap between the matched observed and expected shares, and the covered-official rows, carry information.' });
      ctx.card({ title: ctx.ruleOf('ban') ? 'Records that appear to warrant review' : 'Records inside a window to a covered official', sub: 'Each with the reason and the rule; committees belong to officials who approve the contract', span: 12, render(el) {
        if (!covered.length) return ctx.empty(el, 'None under these filters');
        return C.dataTable(el, { rows: covered, search: false, pageSize: 10, sort: 'date', dir: 'desc', cols: [{ key: 'date', label: 'Date', format: (v) => fmt.date(v) }, { key: 'contractor', label: 'Contractor (principals who gave)', text: (r) => sc.name(r.contractor), render: (td, r) => { td.appendChild(sc.link(r.contractor)); ctx.h('span', 'sub', td, ` ${fmt.int(r.count)} ${r.count === 1 ? 'person' : 'people'}, not named`).style.color = 'var(--text-muted)'; } }, { key: 'committee', label: 'Committee', text: (r) => sc.name(r.committee), render: (td, r) => td.appendChild(sc.link((sc.ents.get(r.committee) || {}).official || r.committee)) }, { key: 'amount', label: 'Amount', num: true, format: (v) => fmt.money(v) }, { key: 'days_from_approval', label: 'Days from approval', num: true, format: (v) => (v > 0 ? '+' : '') + v }, { key: 'review', label: 'Status, rule and reason', text: (r) => (isReview(r) ? 'appears to warrant review' : 'pattern'), render: (td, r) => td.appendChild(ctx.review('ban', isReview(r) ? r.why : null, 'inside window, covered official; no reason recorded')) }] });
      } });
    },
  };

  /** A behested row can be judged on timeliness only if it has a payment date: Form 803 rows carry a reporting period instead. */
  const hasPayDate = (b) => b.filed_within_30_days != null && !/803/.test(String(b.form || ''));

  // ---------------------------------------------------------------- behested
  M.views['nw-behested'] = {
    id: 'nw-behested', dash: 'nw', nav: 'Behested payments', title: 'Behested payments', what: 'Payments made to third parties at the request of a city official.',
    how: 'State law requires elected officers to report, on FPPC Form 803 within 30 days, payments made at their behest once one source gives $5,000 or more in a calendar year. San Francisco’s own report (Form SFEC-3610(b), for payments of $1,000 or more from interested parties) was repealed on January 24, 2022 (Ord. 232-21), when the §3.620 ban on soliciting behested payments from interested parties took its place. This view holds Form 803 filings from 2015 to March 2018 and SFEC-3610(b) filings from 2019 on. Payors are shown by type; a payor is flagged “interested party” when it had a contract, permit or lobbying matter before the official’s department within 12 months, which is a check, not a finding. “Late” counts only payments with a payment date that were reported more than 30 days after it; Form 803 rows give a reporting period, not a payment date, so they are left out of that count. Officials are named because they act in their public role.',
    filters: ['years', 'etype', 'amt'], absent: { flow: 'this view is behested payments only' }, files: Object.assign({ beh: 'network/analyses/behested.json' }, FILES),
    render(ctx) {
      const sc = scope(ctx, { ignoreFlow: true }), flowIds = new Set(sc.flows.map((f) => f.id));
      const rows = ctx.data.beh.rows.filter((b) => flowIds.has(b.flow)); ctx.feed('behested payments', rows.length, ctx.data.beh.rows.length);
      const total = st_.sum(rows, 'amount'), interested = st_.sum(rows.filter((b) => b.payor_interested_party), 'amount');
      // Timeliness needs a payment date. Form 803 data carry a reporting period, not a payment date (the exporter's
      // notes), and some rows have no comparison at all; neither kind is counted as late.
      const dated = rows.filter(hasPayDate), late = dated.filter((b) => b.filed_within_30_days === false), undated = rows.length - dated.length;
      Object.assign(ctx.slots, { __small: rows.length < ctx.meta.small_n, payments: rows.length, payments_fmt: fmt.int(rows.length), total: fmt.money(total), officials_fmt: fmt.int(new Set(rows.map((b) => b.official)).size), interested_share: fmt.pct(total ? interested / total : null), late_fmt: fmt.int(late.length), dated_fmt: fmt.int(dated.length), undated_fmt: fmt.int(undated) });
      ctx.live('beh'); ctx.rule('behested'); fairnessBox(ctx);
      const years = ctx.yearList(), ptypes = ['contractor', 'nonprofit', 'donor_org', 'individuals'];
      ctx.card({ title: 'Behested payments by year and payor type', sub: 'Dollars', span: 7, render(el) {
        if (!rows.length) return ctx.empty(el, 'No behested payments match');
        return C.stackedBars(el, { categories: years, series: ptypes.map((t) => ({ id: t, label: sc.typeLabel(t), color: TYPE_COLOR(t), values: years.map((y) => st_.sum(rows.filter((b) => +b.date.slice(0, 4) === y && sc.typeOf(b.payor) === t), 'amount')) })), yTitle: 'Dollars', annotations: M.commentary.annotationsFor(ctx.commentary, 'nw_behested'), aria: 'Behested by year' });
      } });
      ctx.card({ title: 'By official', sub: 'Total at each official’s behest; click to open the profile', span: 5, render(el) {
        const by = st_.group(rows, (b) => b.official), r = [...by.entries()].map(([id, bs]) => ({ label: `${sc.name(id)} (${(sc.ents.get(id) || {}).office || ''})`, value: st_.sum(bs, 'amount'), n: bs.length, color: TYPE_COLOR('official'), sub: `${fmt.pct(st_.sum(bs, 'amount') ? st_.sum(bs.filter((b) => b.payor_interested_party), 'amount') / st_.sum(bs, 'amount') : null)} from payors flagged as interested parties (a check, not a finding)`, onClick: () => M.state.set({ view: 'official', id }) })).sort((a, b) => b.value - a.value).slice(0, 12);
        if (!r.length) return ctx.empty(el, 'No behested payments match');
        return C.bars(el, { rows: r, rowH: 26, valueHead: 'Dollars', nHead: 'payments', labelWidth: 220, aria: 'Behested by official' });
      } });
      ctx.card({ title: 'Payments', sub: 'Payor, payee, official, purpose; interested-party flag is a check, not a finding', span: 12, render(el) {
        if (!rows.length) return ctx.empty(el, 'No behested payments match');
        return C.dataTable(el, { rows, pageSize: 15, sort: 'amount', placeholder: 'Filter…', cols: [{ key: 'date', label: 'Date', format: (v) => fmt.date(v) }, { key: 'official', label: 'At the behest of', text: (b) => sc.name(b.official), render: (td, b) => td.appendChild(sc.link(b.official)) }, { key: 'payor', label: 'Payor', text: (b) => sc.name(b.payor), render: (td, b) => { td.appendChild(sc.typeOf(b.payor) === 'individuals' ? document.createTextNode(sc.name(b.payor)) : sc.link(b.payor)); if (b.payor_interested_party) { td.appendChild(document.createTextNode(' ')); td.appendChild(ctx.tag('pattern', 'interested party')); } } }, { key: 'payee', label: 'Payee', text: (b) => sc.name(b.payee), render: (td, b) => td.appendChild(sc.link(b.payee)) }, { key: 'purpose', label: 'Purpose' }, { key: 'amount', label: 'Amount', num: true, format: (v) => fmt.money(v) }, { key: 'filed_within_30_days', label: 'Filed within 30 days', text: (b) => (!hasPayDate(b) ? 'no payment date' : b.filed_within_30_days ? 'yes' : 'late') }] });
      }, note: `“Late” means reported more than 30 days after the payment date: ${fmt.int(late.length)} of the ${fmt.int(dated.length)} payments with a payment date. ${fmt.int(undated)} payment${undated === 1 ? '' : 's'} (Form 803 rows, which give a reporting period rather than a payment date, and any row without a filing date) are not counted as late or on time. The 30-day comparison is a rough proxy for the legal deadline.` });
    },
  };

  // ---------------------------------------------------------------- lobbying
  M.views['nw-lobby'] = {
    id: 'nw-lobby', dash: 'nw', nav: 'Lobbying by client and topic', title: 'Lobbying by client and topic', what: 'Who lobbied which departments and officials, for whom, and about what.',
    how: 'Contact lobbyists report each contact with a city officer for a client on a matter. The grid crosses clients with the departments and officials they targeted; the topic chart shows what contacts were about. Lobbying is lawful and disclosed. The amount filter is not on this view because contacts have no dollar value.',
    filters: ['years', 'etype'], absent: { flow: 'this view is lobbying only', amt: 'contacts have no dollar amount' }, files: Object.assign({ lob: 'network/analyses/lobbying.json' }, FILES),
    render(ctx) {
      const sc = scope(ctx, { ignoreFlow: true, ignoreAmt: true }), flowIds = new Set(sc.flows.map((f) => f.id));
      const rows = ctx.data.lob.rows.filter((r) => flowIds.has(r.flow)); ctx.feed('lobbying contact records (lobbyist × client × target × month)', rows.length, ctx.data.lob.rows.length);
      const pay = sc.flows.filter((f) => f.type === 'lobby_payment'); ctx.feed('lobbyist payment records', pay.length, ctx.data.flows.flows.filter((f) => f.type === 'lobby_payment').length);
      const byTarget = st_.group(rows, (r) => r.target), topT = [...byTarget.entries()].sort((a, b) => st_.sum(b[1], 'contacts') - st_.sum(a[1], 'contacts'))[0];
      Object.assign(ctx.slots, { __small: rows.length < ctx.meta.small_n, contacts: st_.sum(rows, 'contacts'), contacts_fmt: fmt.int(st_.sum(rows, 'contacts')), lobbyists_fmt: fmt.int(new Set(rows.map((r) => r.lobbyist)).size), clients_fmt: fmt.int(new Set(rows.map((r) => r.client)).size), top_target: topT ? sc.name(topT[0]) : '–', top_target_fmt: topT ? fmt.int(st_.sum(topT[1], 'contacts')) : '–', payments_total: fmt.money(st_.sum(pay, 'amount')) });
      ctx.live('lob'); ctx.rule('lobby'); fairnessBox(ctx);
      ctx.card({ title: 'Contacts: clients × targets', sub: 'Top 12 clients by contacts against the top 8 targets', span: 12, render(el) {
        if (!rows.length) return ctx.empty(el, 'No lobbying contacts match');
        const clients = [...st_.group(rows, (r) => r.client).entries()].sort((a, b) => st_.sum(b[1], 'contacts') - st_.sum(a[1], 'contacts')).slice(0, 12).map((x) => x[0]);
        const targets = [...byTarget.entries()].sort((a, b) => st_.sum(b[1], 'contacts') - st_.sum(a[1], 'contacts')).slice(0, 8).map((x) => x[0]);
        return C.heatmap(el, { rows: clients.map(sc.name), cols: targets.map((t) => C.truncate(sc.name(t), 18)), values: clients.map((c) => targets.map((t) => st_.sum(rows.filter((r) => r.client === c && r.target === t), 'contacts') || null)), format: (v) => fmt.int(v), valueLabel: 'contacts', labelWidth: 220, cellH: 28, onClick: (i) => M.state.set({ view: 'org', id: (sc.ents.get(clients[i]) || {}).nonprofit_org || clients[i] }), aria: 'Client by target heat grid' });
      }, note: 'Click a row to open the client’s profile. Officials appear as targets when contacts were with them or their staff.' });
      ctx.card({ title: 'What contacts were about', sub: 'Reported topic of each contact', span: 5, render(el) {
        const t = st_.group(rows, (r) => r.topic), r = [...t.entries()].map(([label, rs]) => ({ label, value: st_.sum(rs, 'contacts'), color: 'var(--c-lobbyist)' })).sort((a, b) => b.value - a.value);
        if (!r.length) return ctx.empty(el, 'No lobbying contacts match');
        return C.bars(el, { rows: r, format: (v) => fmt.int(v), valueHead: 'Contacts', labelWidth: 180, aria: 'Contacts by topic' });
      } });
      ctx.card({ title: 'Payments from clients to lobbyists', sub: 'Top 12 clients; the dollars side of lobbying', span: 7, render(el) {
        const by = st_.group(pay, (f) => f.from), r = [...by.entries()].map(([id, fs]) => ({ label: sc.name(id), value: st_.sum(fs, 'amount'), n: fs.length, color: TYPE_COLOR(sc.typeOf(id)), onClick: () => M.state.set({ view: 'org', id: (sc.ents.get(id) || {}).nonprofit_org || id }) })).sort((a, b) => b.value - a.value).slice(0, 12);
        if (!r.length) return ctx.empty(el, 'No lobbyist payments match');
        return C.bars(el, { rows: r, rowH: 26, valueHead: 'Paid to lobbyists', nHead: 'payments', labelWidth: 220, aria: 'Lobbyist payments by client' });
      }, note: 'Bar colour is the client’s entity type.' });
    },
  };

  // ---------------------------------------------------------------- concentration
  M.views['nw-concentration'] = {
    id: 'nw-concentration', dash: 'nw', nav: 'Concentration', title: 'Concentration', what: 'How dependent each committee is on a few sources of money.',
    how: 'Per committee, the stacked bar splits contributions by source type; the top-10 share counts named sources (organizations and PACs) only, since individuals are aggregated. These are precomputed per election cycle, so the dashboard filters are not shown on this view.',
    filters: [], filterNote: 'This view uses precomputed per-committee totals for each election cycle. The dashboard filters (years, flow type, entity type, minimum amount) cannot slice those totals, so they are not shown here.', files: Object.assign({ conc: 'network/analyses/concentration.json' }, FILES),
    render(ctx) {
      const ents0 = new Map(ctx.data.ents.entities.map((e) => [e.id, e])), rows = ctx.data.conc.rows.filter((r) => r.total > 0);
      const ents = { get: (id) => ents0.get(id) || { id, name: id } };
      const cycles = [...new Set(rows.map((r) => r.cycle).filter(Boolean))].sort();
      ctx.feed('committees', rows.length, ctx.data.conc.rows.length);
      const tot = st_.sum(rows, 'total'), share = (k) => fmt.pct(st_.sum(rows, (r) => r.by_source_type[k] || 0) / tot);
      Object.assign(ctx.slots, { committees: rows.length, committees_fmt: fmt.int(rows.length), years: cycles.length ? `${fmt.list(cycles)} cycle${cycles.length > 1 ? 's' : ''}` : 'all cycles', ind_share: share('individuals'), org_share: fmt.pct(st_.sum(rows, (r) => (r.by_source_type.donor_org || 0)) / tot), contr_share: share('contractor_affiliated') });
      ctx.live('conc'); ctx.rule('limits'); fairnessBox(ctx);
      const K = [['individuals', 'Individuals (aggregate)', 'var(--c-individuals)'], ['contractor_affiliated', 'Contractor-affiliated individuals (aggregate)', 'var(--c-contractor)'], ['donor_org', 'PACs and other organizations', 'var(--c-donor_org)'], ['nonprofit', 'Nonprofits', 'var(--c-nonprofit)']];
      ctx.card({ title: 'Where each committee’s money came from', sub: 'Share of contribution dollars by source type; sorted by total', span: 12, render(el) {
        const r = rows.slice().sort((a, b) => b.total - a.total).slice(0, 20);
        return C.stackedBars(el, { horizontal: true, percent: true, categories: r.map((x) => ents.get(x.committee).name + (cycles.length > 1 && x.cycle ? ` (${x.cycle})` : '')), series: K.map(([k, label, color]) => ({ id: k, label, color, values: r.map((x) => x.by_source_type[k] || 0) })), rawFormat: (v) => fmt.money(v), n: r.map((x) => x.n_contributions), nHead: 'contributions', labelWidth: 240, rowH: 24, onClick: (i) => (r[i].official ? M.state.set({ view: 'official', id: r[i].official }) : null), aria: 'Concentration by committee' });
      }, note: 'Click a row to open the official’s profile. Individuals cannot be distinguished from each other here by design.' });
      ctx.card({ title: 'Top-10 named sources’ share', sub: 'Among organizations and PACs only', span: 6, render(el) {
        const r = rows.filter((x) => x.top10_share_named != null).sort((a, b) => b.top10_share_named - a.top10_share_named).slice(0, 15).map((x) => ({ label: ents.get(x.committee).name + (cycles.length > 1 && x.cycle ? ` (${x.cycle})` : ''), value: x.top10_share_named, n: x.n_named_sources, color: 'var(--c-committee)', onClick: () => M.state.set({ view: 'official', id: x.official }) }));
        if (!r.length) return ctx.empty(el, 'No committees');
        return C.bars(el, { rows: r, rowH: 26, format: (v) => fmt.pct(v), valueHead: 'Top-10 share', nHead: 'named sources', labelWidth: 240, maxX: 1, aria: 'Top-10 share' });
      }, note: 'With few named sources the top-10 share is trivially high; n tells you how many there were.' });
      ctx.card({ title: 'Committees', sub: 'Totals per committee', span: 6, render(el) {
        return C.dataTable(el, { rows, search: false, pageSize: 12, sort: 'total', cols: [{ key: 'committee', label: 'Committee', text: (r) => ents.get(r.committee).name, render: (td, r) => td.appendChild(ctx.link(ents.get(r.committee).name, { view: 'official', id: r.official })) }, { key: 'total', label: 'Total', num: true, format: (v) => fmt.money(v) }, { key: 'n_contributions', label: 'Contributions', num: true, format: (v) => fmt.int(v) }, { key: 'top10_share_named', label: 'Top-10 named', num: true, format: (v) => fmt.pct(v) }] });
      } });
    },
  };

  // ---------------------------------------------------------------- nonprofit loop
  M.views['nw-loop'] = {
    id: 'nw-loop', dash: 'nw', nav: 'The nonprofit loop', title: 'The nonprofit loop', what: 'City-funded nonprofits that also receive behested payments or hire lobbyists to work the departments that fund them.',
    how: 'Each row is a nonprofit with city payments that also appears as a behested payee or payor, or as a lobbying client, in the selected years. Every step is lawful and disclosed; the loop is shown so the pattern can be checked across four datasets, with the rules beside it.',
    filters: ['years', 'amt'], absent: { flow: 'fixed set: behested payments and lobbying', etype: 'all rows are nonprofits' }, files: Object.assign({ loop: 'network/analyses/loop.json', beh: 'network/analyses/behested.json' }, FILES),
    render(ctx) {
      const sc = scope(ctx, { ignoreFlow: true, ignoreEtype: true }), flows = sc.flows;
      const rows = ctx.data.loop.rows.map((r) => { const beh = flows.filter((f) => f.type === 'behested' && (f.to === r.entity || f.from === r.entity)), lob = flows.filter((f) => f.type === 'lobby_payment' && f.from === r.entity), contacts = flows.filter((f) => f.type === 'lobby_contact' && f.client === r.entity); return Object.assign({}, r, { beh_recv: st_.sum(beh.filter((f) => f.to === r.entity), 'amount'), beh_made: st_.sum(beh.filter((f) => f.from === r.entity), 'amount'), lob: st_.sum(lob, 'amount'), contacts: st_.sum(contacts, 'count'), steps: (beh.length ? 1 : 0) + (lob.length || contacts.length ? 1 : 0) + 1 }); }).filter((r) => r.steps >= 2);
      ctx.feed('nonprofits in the loop', rows.length, ctx.data.loop.rows.length);
      const cityFy = (ctx.data.loop.rows.find((r) => r.city_paid_fy) || {}).city_paid_fy;
      Object.assign(ctx.slots, { __small: rows.length < ctx.meta.small_n, orgs: rows.length, orgs_fmt: fmt.int(rows.length), city_total: fmt.money(st_.sum(rows, 'city_paid')), beh_total: fmt.money(st_.sum(rows, 'beh_recv')), lob_total: fmt.money(st_.sum(rows, 'lob')) });
      ctx.live('loop'); ctx.fair(ctx.data.loop.note, 'Appearing here is not improper'); ctx.rule('behested');
      ctx.card({ title: 'City money vs behested payments received', sub: 'Each dot is a nonprofit in the loop; hover for lobbying', span: 6, render(el) {
        if (!rows.length) return ctx.empty(el, 'No nonprofits match');
        return C.scatter(el, { points: rows.map((r) => ({ id: r.org, x: Math.max(r.city_paid, 1000), y: r.beh_recv, label: sc.name(r.entity), color: TYPE_COLOR('nonprofit'), sub: `paid lobbyists ${fmt.money(r.lob)} · ${fmt.int(r.contacts)} contacts · funders ${r.depts_funding.map(ctx.deptShort).join(', ')}`, onClick: () => M.state.set({ view: 'org', id: r.org }) })), logX: 10000, xTitle: `City payments${cityFy ? ' FY' + cityFy : ''} (log)`, yTitle: 'Behested payments received', yFormat: (v) => fmt.money(v), aria: 'Loop scatter' });
      } });
      ctx.card({ title: 'Funders lobbied', sub: 'Nonprofits whose lobbyists contacted a department that funds them', span: 6, render(el) {
        const r = rows.filter((x) => x.depts_lobbied.some((d) => x.depts_funding.includes(d))).map((x) => ({ label: sc.name(x.entity), value: x.contacts, n: x.depts_lobbied.filter((d) => x.depts_funding.includes(d)).length, color: TYPE_COLOR('nonprofit'), sub: `lobbied funders: ${x.depts_lobbied.filter((d) => x.depts_funding.includes(d)).map(ctx.deptShort).join(', ')}`, onClick: () => M.state.set({ view: 'org', id: x.org }) })).sort((a, b) => b.value - a.value).slice(0, 12);
        if (!r.length) return ctx.empty(el, 'None', 'No nonprofit in the loop lobbied one of its own funders under these filters.');
        return C.bars(el, { rows: r, rowH: 26, format: (v) => fmt.int(v), valueHead: 'Contacts', nHead: 'funders lobbied', labelWidth: 220, aria: 'Funders lobbied' });
      }, note: 'Lobbying a funder is lawful; it is shown because it closes the loop.' });
      ctx.card({ title: 'The loop, row by row', sub: 'Click a nonprofit for its full profile across all four dashboards', span: 12, render(el) {
        if (!rows.length) return ctx.empty(el, 'No nonprofits match');
        return C.dataTable(el, { rows, pageSize: 20, sort: 'city_paid', placeholder: 'Filter…', cols: [{ key: 'entity', label: 'Nonprofit', text: (r) => sc.name(r.entity), render: (td, r) => td.appendChild(ctx.link(sc.name(r.entity), { view: 'org', id: r.org })) }, { key: 'city_paid', label: `City${cityFy ? ' FY' + cityFy : ''}`, num: true, format: (v) => fmt.money(v) }, { key: 'depts_funding', label: 'Funders', text: (r) => r.depts_funding.map(ctx.deptShort).join(', ') }, { key: 'beh_recv', label: 'Behested received', num: true, format: (v) => fmt.money(v) }, { key: 'beh_made', label: 'Behested made', num: true, format: (v) => fmt.money(v) }, { key: 'lob', label: 'Paid lobbyists', num: true, format: (v) => fmt.money(v) }, { key: 'contacts', label: 'Contacts', num: true }, { key: 'depts_lobbied', label: 'Lobbied', text: (r) => r.depts_lobbied.map(ctx.deptShort).join(', ') }] });
      } });
    },
  };

  // ---------------------------------------------------------------- directory
  M.views['nw-entities'] = {
    id: 'nw-entities', dash: 'nw', nav: 'Entities', title: 'Entities', what: 'Every named entity in the network, with totals for the current filters.', headline: false,
    filters: ['years', 'flow', 'etype', 'amt'], files: FILES,
    render(ctx) {
      const sc = scope(ctx);
      // one pass over the filtered flows (entities × flows would be quadratic on real data)
      const agg = new Map(), get = (id) => agg.get(id) || (agg.set(id, { n: 0, in_: 0, out: 0 }), agg.get(id));
      for (const f of sc.flows) { const a = get(f.from), b = get(f.to); a.n++; a.out += f.amount || 0; if (f.to !== f.from) { b.n++; } b.in_ += f.amount || 0; }
      const rows = [...sc.ents.values()].filter((e) => inList(sc.st.etype, e.type) && agg.has(e.id)).map((e) => Object.assign({ e }, agg.get(e.id)));
      ctx.card({ title: `${fmt.int(rows.length)} entities`, sub: 'Totals reflect the current filters; click to open a profile', span: 12, render(el) {
        return C.dataTable(el, { rows, pageSize: 40, sort: 'in_', placeholder: 'Search entities…', cols: [{ key: 'name', label: 'Entity', text: (r) => r.e.name, render: (td, r) => { if (r.e.type === 'individuals') td.textContent = r.e.name; else td.appendChild(sc.link(r.e.id)); } }, { key: 'type', label: 'Type', text: (r) => sc.typeLabel(r.e.type), render: (td, r) => { const d = ctx.h('i', 'dot', td); d.style.background = TYPE_COLOR(r.e.type); d.style.marginRight = '6px'; td.appendChild(document.createTextNode(sc.typeLabel(r.e.type))); } }, { key: 'n', label: 'Flows', num: true }, { key: 'in_', label: 'Dollars in', num: true, format: (v) => fmt.money(v) }, { key: 'out', label: 'Dollars out', num: true, format: (v) => fmt.money(v) }, { key: 'extra', label: 'Note', text: (r) => r.e.office || (r.e.count ? `${fmt.int(r.e.count)} individuals aggregated` : r.e.sector || '') }] });
      } });
    },
  };
  M.nw = { scope, TYPE_COLOR, FLOW_COLOR, isReview, coverage, matchedBase };
})();
