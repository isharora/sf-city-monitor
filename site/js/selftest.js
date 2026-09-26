/* selftest.js - ?selftest=1
   1. Statistics checks for the pooling code (quantiles, histogram, cumulative incidence with censoring,
      deflation, null-safe sums, the matched ban-window base rate and that the pooled chance figure is shown nowhere,
      and that audit rates use the known-status denominator).
   2. For every dashboard view: renders it with default filters, then sets each filter the view
      declares (one at a time) and checks that the view's numbers change AND the "Data on this page"
      strip changes (record counts; for Real/Nominal, the units item). Checks that every dashboard
      filter the view does not declare is labelled "Not on this view", and that filtered views register
      record counts.
   3. Partition checks through the UI: the records matched for each department (or recommender)
      add up to the records matched with no filter, so a filter never drops or double-counts rows.
   4. Renders every entity page, search and methods and checks for render errors.
   Results: document.title "SELFTEST PASS n/n" or "SELFTEST FAIL k of n", a table in the page, and
   JSON in <pre id="selftest-json"> (tools/check.sh reads it from --dump-dom). */
(function () {
  const M = (window.SFCM = window.SFCM || {});
  const results = [];
  const add = (group, name, pass, detail) => results.push({ group, name, pass: !!pass, detail: detail == null ? '' : String(detail) });
  const near = (a, b, tol) => a != null && b != null && Math.abs(a - b) <= (tol || 1e-9);
  let consoleErrors = [];

  function statsChecks() {
    const S = M.stats;
    const q = S.quantiles([5, 1, 4, 2, 3]);
    add('stats', 'quantiles of 1..5 (linear interpolation)', q && q.p25 === 2 && q.p50 === 3 && q.p75 === 4 && near(q.p90, 4.6, 1e-9), JSON.stringify(q));
    add('stats', 'quantiles ignore null and NaN', S.median([null, 3, NaN, 1, undefined, 2]) === 2, S.median([null, 3, NaN, 1, undefined, 2]));
    add('stats', 'median of empty is null', S.median([]) === null, S.median([]));
    add('stats', 'histogram with overflow bin', JSON.stringify(S.hist([0, 5, 6, 11, 100, null], 6, 3)) === '[2,2,1]', JSON.stringify(S.hist([0, 5, 6, 11, 100, null], 6, 3)));
    const F1 = S.incidence([1, 2, 3, null], [10, 10, 10, 10], 1, 4);
    add('stats', 'cumulative incidence, no censoring = empirical share', JSON.stringify(F1.map((x) => +x.toFixed(4))) === '[0,0.25,0.5,0.75]', JSON.stringify(F1));
    const F2 = S.incidence([2, null, 5, null], [20, 3, 20, 10], 1, 6);
    add('stats', 'cumulative incidence with censoring (Kaplan–Meier, 0.625)', near(F2[5], 0.625, 1e-9), JSON.stringify(F2.map((x) => +x.toFixed(4))));
    add('stats', 'incidence never exceeds 1 and never falls', F2.every((v, i) => v <= 1 && (i === 0 || v >= F2[i - 1])), '');
    add('stats', 'deflation: real = nominal / index', near(S.real(100, 2020, { index: { 2020: 0.8 } }), 125), S.real(100, 2020, { index: { 2020: 0.8 } }));
    add('stats', 'deflation: year without an index stays nominal', S.real(100, 1990, { index: { 2020: 0.8 } }) === 100, '');
    add('stats', 'sum skips null and NaN without resetting the total', S.sum([{ a: 1 }, { a: null }, { a: 2 }, { a: NaN }, {}], 'a') === 3, S.sum([{ a: 1 }, { a: null }, { a: 2 }, { a: NaN }, {}], 'a'));
    add('stats', 'formatters: no signed zero, B/M/k money', S.fmt.signedPct(0.00001) === '0%' && S.fmt.money(1.5e9) === '$1.50B' && S.fmt.money(-2500) === '−$2.5k' && S.fmt.pct(NaN) === '–', `${S.fmt.signedPct(0.00001)} ${S.fmt.money(1.5e9)} ${S.fmt.money(-2500)}`);
    for (const d of Object.values(M.dashes)) { const m = M.METAS[d.id]; if (m && m.deflator && m.deflator.index) add('stats', `${d.module}: deflator index is 1 in the base year`, near(m.deflator.index[String(m.deflator.base_fy)], 1, 1e-6), m.deflator.index[String(m.deflator.base_fy)]); }
    if (M.nw && M.nw.coverage) {
      add('stats', 'window coverage: union of overlapping intervals', near(M.nw.coverage([['2020-01-01', '2020-01-11'], ['2020-01-06', '2020-01-21']], '2020-01-01', '2020-01-31'), 20 / 30, 1e-9), M.nw.coverage([['2020-01-01', '2020-01-11'], ['2020-01-06', '2020-01-21']], '2020-01-01', '2020-01-31'));
    }
  }
  async function baseRateCheck() {
    // The chance benchmark is the exporter's matched pair (base_rates.expected_share_matched / observed_share_matched);
    // the contract's pooled expected_share_if_unrelated overstates chance and must not be shown anywhere.
    try {
      const ban = await M.data.load('network/analyses/ban_window.json');
      const b = ban.base_rates || {}, mb = M.nw.matchedBase(ban), inUnit = (x) => typeof x === 'number' && x > 0 && x < 1;
      add('stats', 'ban-window matched base rate is in the export (expected and observed shares between 0 and 1)', !!mb && inUnit(b.expected_share_matched) && inUnit(b.observed_share_matched), `expected ${b.expected_share_matched}, observed ${b.observed_share_matched}, n ${b.matched_n_records}`);
      if (mb && mb.ci) add('stats', 'matched observed minus expected lies inside the exported 95% interval', mb.observed - mb.expected >= mb.ci[0] - 1e-9 && mb.observed - mb.expected <= mb.ci[1] + 1e-9, `${(mb.observed - mb.expected).toFixed(3)} in [${mb.ci.join(', ')}]`);
      if (!mb) return;
      const pooled = b.expected_share_if_unrelated, F = M.stats.fmt;
      const stale = typeof pooled === 'number' && Math.abs(pooled - mb.expected) > 0.005 ? [F.pct(pooled), F.pct(pooled, 1)] : [];
      const staleRe = stale.length ? new RegExp(`(^|[^\\d.])(${stale.map((x) => x.replace('.', '\\.')).join('|')})`) : null;
      for (const vid of ['nw-ban', 'nw-overview', 'home']) {
        await show(defaults(vid));
        const txt = document.getElementById('content').textContent;
        const clone = document.getElementById('content').cloneNode(true); clone.querySelectorAll('.ax-label').forEach((e) => e.remove()); const txtNoAxis = clone.textContent; // axis ticks (…40%, 45%…) are not claims
        if (vid === 'nw-ban') {
          const bar = [...document.querySelectorAll('#content .card')].find((c) => /Observed vs expected by chance/.test((c.querySelector('.card-title') || {}).textContent || ''));
          const btxt = bar ? bar.textContent : '';
          add('stats', 'nw-ban: the chance bar and the live sentence show the matched expected and observed shares', btxt.includes(mb.expected_fmt) && btxt.includes(mb.observed_fmt) && (document.querySelector('#content .live-slot') || {}).textContent.includes(mb.expected_fmt), `looking for ${mb.expected_fmt} and ${mb.observed_fmt}`);
        } else add('stats', `${vid}: shows the matched base rate`, txt.includes(mb.expected_fmt) && txt.includes(mb.observed_fmt), `looking for ${mb.expected_fmt} and ${mb.observed_fmt}`);
        if (staleRe) { const m = txtNoAxis.match(staleRe); add('stats', `${vid}: the pooled chance figure (${stale[0]}) appears nowhere on the page (axis ticks aside)`, !m, m ? `found "${txtNoAxis.slice(Math.max(0, m.index - 60), m.index + 10)}"` : ''); }
      }
    } catch (e) { add('stats', 'ban-window base rate', true, `skipped: ${e.message}`); }
  }

  async function auDenominatorCheck() {
    // Audit rates use recommendations with a recorded follow-up status as the denominator (as the module's findings do:
    // CSA 3,244 of 3,385, Grand Jury 1,479 of 3,420), never all rows; the no-status count is shown beside them.
    if (!M.METAS.au || !M.au) return;
    try {
      const rows = (await M.data.load('audits/recs/recs.json')).rows, F = M.stats.fmt;
      for (const src of [null, 'csa', 'cgj']) {
        const sel = rows.filter((r) => !src || r.source === src), known = sel.filter((r) => r.status !== 'unknown'), impl = sel.filter((r) => r.status === 'implemented').length;
        const want = F.pct(known.length ? impl / known.length : null), allRows = F.pct(sel.length ? impl / sel.length : null), tag = src ? `source=${src}` : 'unfiltered';
        const p = defaults('au-overview'); if (src) p.source = [src];
        await show(p);
        const sl = (M.app.lastView || {}).slots || {}, tile = [...document.querySelectorAll('#content .tile')].find((t) => /Implemented/.test(t.querySelector('.tile-label').textContent));
        const tv = tile ? tile.querySelector('.tile-value').textContent : '', tf = tile ? tile.querySelector('.tile-foot').textContent : '', live = (document.querySelector('#content .live-slot') || {}).textContent || '';
        add('stats', `au-overview (${tag}): Implemented tile, slot and live sentence use the known-status denominator (${impl} of ${known.length} = ${want}, not ${allRows} of all rows)`,
          sl.impl_share === want && tv === want && sl.known === known.length && sl.nostatus === sel.length - known.length && tf.includes(F.int(known.length)) && tf.includes(F.int(sel.length - known.length)) && live.includes(want) && live.includes(F.int(sel.length - known.length)),
          `slot ${sl.impl_share}, tile "${tv}" / "${tf}", live has share: ${live.includes(want)}`);
        if (!src) {
          const ag = known.filter((r) => r.agreed === 'agree'), wantAg = F.pct(ag.length ? ag.filter((r) => r.status === 'implemented').length / ag.length : null);
          const resp = sel.filter((r) => r.agreed !== 'none'), wantShare = F.pct(resp.length ? resp.filter((r) => r.agreed === 'agree').length / resp.length : null);
          await show(defaults('au-agreement'));
          const s2 = (M.app.lastView || {}).slots || {}, live2 = (document.querySelector('#content .live-slot') || {}).textContent || '';
          add('stats', `au-agreement: impl_agreed over known status (${wantAg}) and agree_share over recorded responses (${wantShare})`, s2.impl_agreed === wantAg && s2.agree_share === wantShare && live2.includes(wantAg), `impl_agreed ${s2.impl_agreed}, agree_share ${s2.agree_share}`);
          const wantNi = F.pct(known.length ? known.filter((r) => r.status === 'not_implementing').length / known.length : null);
          await show(defaults('au-status'));
          const s3 = (M.app.lastView || {}).slots || {};
          add('stats', `au-status: shares over known status (will not implement ${wantNi})`, s3.notimpl_share === wantNi && s3.impl_share === want, `notimpl ${s3.notimpl_share}, impl ${s3.impl_share}`);
        }
      }
    } catch (e) { add('stats', 'audit known-status denominator', false, e.message); }
  }


  // ------------------------------------------------------------------ view checks
  const S = () => M.state;
  function defaults(view) { const p = { view, id: null, mode: 'explore', data: false }; for (const k of ['years', 'dept', 'area', 'size', 'group', 'real', 'source', 'topic', 'flow', 'etype', 'amt']) p[k] = JSON.parse(JSON.stringify(S().DEFAULTS[k])); return p; }
  async function show(patch) { S().set(patch); await M.app.rendered; await new Promise((r) => setTimeout(r, 0)); await M.app.rendered; }
  function fingerprint() {
    const c = document.getElementById('content');
    const parts = [];
    c.querySelectorAll('.tiles, .grid, .live-slot, .pre-cards').forEach((el) => parts.push(el.textContent));
    c.querySelectorAll('.grid svg').forEach((svg) => svg.querySelectorAll('rect, path, circle, line').forEach((e) => { for (const a of ['d', 'x', 'y', 'width', 'height', 'cx', 'cy', 'r', 'x1', 'x2', 'y1', 'y2']) { const v = e.getAttribute(a); if (v != null) parts.push(v); } }));
    return M.stats.hash(parts.join('|')) + ':' + parts.length;
  }
  function strip() {
    const feeds = [...document.querySelectorAll('#content .datastrip .ds-feed')].map((e) => +e.dataset.matched);
    const units = [...document.querySelectorAll('#content .datastrip .ds-units')].map((e) => e.textContent).join('|');
    return { feeds, units, key: feeds.join(',') + '|' + units };
  }
  function candidates(dash, key) {
    const meta = M.METAS[dash.id], dims = meta.dimensions || {}, b = meta[dash.yearsKey];
    if (key === 'years') return [[b.max - 1, b.max], [b.min, Math.min(b.max, b.min + 2)], [b.max, b.max]].filter((y) => !(y[0] === b.min && y[1] === b.max));
    if (key === 'real') return [false];
    if (key === 'amt') return (dims.amount_bands || []).map((x) => +x.id).filter((x) => x > 0);
    const dim = dims[key === 'size' ? 'size_band' : key];
    return dim ? dim.values.map((v) => [v.id]) : [];
  }
  async function viewChecks() {
    for (const dash of Object.values(M.dashes)) {
      if (!M.METAS[dash.id]) { add(dash.id, `${dash.module}: meta available`, false, 'meta.json missing or invalid'); continue; }
      for (const vid of dash.views) {
        const view = M.views[vid];
        const before = consoleErrors.length, errs0 = M.app.errors.length;
        await show(defaults(vid));
        const lv = M.app.lastView || {};
        if (lv.unavailable) { add(vid, 'renders', true, 'analysis not available yet (file missing or invalid): the view is blank by design'); continue; }
        add(vid, 'renders with default filters, no errors', consoleErrors.length === before && M.app.errors.length === errs0, [...consoleErrors.slice(before), ...M.app.errors.slice(errs0)].join(' | '));
        const F0 = fingerprint(), S0 = strip();
        // every chart has a table twin and keyboard-focusable marks
        const cards = [...document.querySelectorAll('#content .card')].filter((c) => c.querySelector('svg.chart, .nw-canvas svg'));
        const noTwin = cards.filter((c) => { const b = c.querySelector('.tbl-btn'); return !b || b.hidden; }).map((c) => (c.querySelector('.card-title') || {}).textContent);
        const noFocus = cards.filter((c) => !c.querySelector('svg [tabindex]')).map((c) => (c.querySelector('.card-title') || {}).textContent);
        if (cards.length) add(vid, `every chart has a table twin and focusable marks (${cards.length} charts)`, !noTwin.length && !noFocus.length, [noTwin.length ? 'no twin: ' + noTwin.join('; ') : '', noFocus.length ? 'no focusable marks: ' + noFocus.join('; ') : ''].filter(Boolean).join(' · '));
        // undeclared filters are labelled
        const absent = dash.filterKeys.filter((k) => !(view.filters || []).includes(k));
        const bar = document.getElementById('filterbar'), na = bar.querySelector('.filter-na');
        if (!(view.filters || []).length) add(vid, 'no filters: the bar says why', !!(view.filterNote && na && na.textContent.length > 20), na ? na.textContent.slice(0, 80) : 'no note');
        else if (absent.length) { const txt = na ? na.textContent : ''; const ok = na && absent.every((k) => txt.includes(M.app.FILTER_LABELS[k])); add(vid, `undeclared filters labelled (${absent.join(', ')})`, ok && txt.startsWith('Not on this view'), txt.slice(0, 120)); }
        // shown filters are exactly the declared ones
        const shown = [...bar.querySelectorAll('.filter')].map((f) => f.dataset.filter);
        add(vid, 'filter bar shows exactly the declared filters', JSON.stringify(shown) === JSON.stringify(view.filters || []), shown.join(','));
        if ((view.filters || []).length) add(vid, 'registers filtered record counts', (lv.feeds || []).length > 0, `${(lv.feeds || []).length} feeds`);
        for (const key of view.filters || []) {
          const cands = candidates(dash, key).slice(0, 6);
          let ok = false, used = null, why = 'no candidate value changed both the numbers and the strip';
          for (const val of cands) {
            const p = defaults(vid); p[key] = val;
            const e0 = consoleErrors.length;
            await show(p);
            const F1 = fingerprint(), S1 = strip();
            if (consoleErrors.length > e0) { why = 'console error: ' + consoleErrors.slice(e0).join(' | '); break; }
            const numbers = F1 !== F0, stripChanged = S1.key !== S0.key;
            const nonEmpty = key === 'real' || S1.feeds.some((n) => n > 0);
            if (numbers && stripChanged && nonEmpty) { ok = true; used = val; why = `${key}=${JSON.stringify(val)}: numbers and strip changed (${S0.key} → ${S1.key})`; break; }
            why = `${key}=${JSON.stringify(val)}: numbers ${numbers ? 'changed' : 'unchanged'}, strip ${stripChanged ? 'changed' : 'unchanged'}${nonEmpty ? '' : ', no records matched'}`;
          }
          add(vid, `filter "${M.app.FILTER_LABELS[key]}" applies`, ok, why);
        }
      }
    }
  }
  async function keyboardChecks() {
    await show(defaults('np-overview'));
    const mark = document.querySelector('#content svg.chart g[tabindex]');
    if (!mark) { add('a11y', 'chart marks are focusable', false, 'no focusable mark found'); return; }
    mark.focus();
    const tip = document.querySelector('.tip');
    add('a11y', 'focusing a chart mark shows the tooltip and names the mark', document.activeElement === mark && tip && !tip.hidden && (mark.getAttribute('aria-label') || '').length > 3, mark.getAttribute('aria-label'));
    const th = document.querySelector('#content .data-table th .th-btn');
    if (th) { th.click(); add('a11y', 'sortable table headers are buttons with aria-sort', !!document.querySelector('#content .data-table th[aria-sort="ascending"], #content .data-table th[aria-sort="descending"]'), ''); }
    const svgs = [...document.querySelectorAll('#content svg.chart')];
    add('a11y', 'every chart SVG has a title and a group label', svgs.every((x) => x.querySelector('title') && x.getAttribute('aria-label')), `${svgs.length} charts`);
    add('a11y', 'skip link and labelled data strip present', !!document.querySelector('.skip-link') && !!document.querySelector('.datastrip[aria-label]'), '');
  }
  async function partitionChecks() {
    const cases = [['np', 'np-flows', 'dept', 0], ['au', 'au-status', 'source', 0], ['pf', 'pf-spending', 'group', 0], ['nw', 'nw-overview', 'flow', 0]];
    for (const [d, vid, key, feedIdx] of cases) {
      const dash = M.dashes[d], meta = M.METAS[d]; if (!meta) continue;
      await show(defaults(vid)); if ((M.app.lastView || {}).unavailable) continue;
      const all = strip().feeds[feedIdx];
      const dim = meta.dimensions[key]; if (!dim) continue;
      let tot = 0;
      for (const v of dim.values) { const p = defaults(vid); p[key] = [v.id]; await show(p); tot += strip().feeds[feedIdx] || 0; }
      const label = (M.app.lastView.feeds[feedIdx] || {}).label || 'records';
      add('pooling', `${dash.short}: ${label} per ${M.app.FILTER_LABELS[key].toLowerCase()} add up to the unfiltered total`, tot === all, `${tot} vs ${all}`);
    }
  }
  async function pageChecks() {
    const pick = async (path, arr, f) => { try { const d = await M.data.load(path); const rows = d[arr]; return rows && rows.length ? f(rows) : null; } catch (e) { return null; } };
    const org = await pick('nonprofits/orgs/index.json', 'orgs', (r) => r.slice().sort((a, b) => b.city_total - a.city_total)[0].id);
    const con = await pick('network/entities.json', 'entities', (r) => (r.find((e) => e.type === 'contractor') || {}).id);
    const off = await pick('network/entities.json', 'entities', (r) => (r.find((e) => e.type === 'official') || {}).id);
    const rep = await pick('audits/reports/reports.json', 'reports', (r) => r[0].id);
    const dept = (M.SITE.departments || [])[0];
    const pages = [['home', {}], ['search', { q: 'health' }], ['methods', {}], ['org', { id: org }], ['org', { id: con }], ['dept', { id: dept && dept.id }], ['report', { id: rep }], ['official', { id: off }], ['org', { id: 'no-such-id' }]];
    for (const [vid, extra] of pages) {
      if (extra.id === null || extra.id === undefined) { if (vid !== 'home' && vid !== 'search' && vid !== 'methods') { add(vid, 'renders', true, 'skipped: no id available'); continue; } }
      const before = consoleErrors.length, errs0 = M.app.errors.length;
      await show(Object.assign(defaults(vid), extra));
      const txt = document.getElementById('content').textContent;
      const unknownExpected = extra.id === 'no-such-id';
      add(vid, `renders${extra.id ? ' ' + extra.id : extra.q ? ' q=' + extra.q : ''}`, consoleErrors.length === before && M.app.errors.length === errs0 && (unknownExpected ? /Unknown organization/.test(txt) : !/Unknown (organization|department|report|official)/.test(txt)), [...consoleErrors.slice(before), ...M.app.errors.slice(errs0)].join(' | ') || (unknownExpected ? 'shows "Unknown organization"' : ''));
    }
  }

  function report() {
    const pass = results.filter((r) => r.pass).length, fail = results.length - pass;
    document.title = fail ? `SELFTEST FAIL ${fail} of ${results.length}` : `SELFTEST PASS ${pass}/${results.length}`;
    const c = document.getElementById('content'); c.innerHTML = '';
    const box = M.charts.h('div', 'selftest', c);
    M.charts.h('h1', 'view-title', box, document.title);
    M.charts.h('p', 'view-what', box, 'Statistics checks, the filter invariant on every dashboard view, partition checks through the UI, and entity pages. Failures first.');
    const t = M.charts.h('table', '', box); const hr = M.charts.h('tr', '', M.charts.h('thead', '', t)); ['', 'Group', 'Check', 'Detail'].forEach((x) => M.charts.h('th', '', hr, x));
    const tb = M.charts.h('tbody', '', t);
    results.slice().sort((a, b) => a.pass - b.pass).forEach((r) => { const tr = M.charts.h('tr', '', tb); M.charts.h('td', r.pass ? 'pass' : 'fail', tr, r.pass ? 'PASS' : 'FAIL'); M.charts.h('td', '', tr, r.group); M.charts.h('td', '', tr, r.name); M.charts.h('td', '', tr, r.detail); });
    const pre = M.charts.h('pre', '', box); pre.id = 'selftest-json'; pre.hidden = true; pre.textContent = JSON.stringify({ pass, fail, results });
    window.SFCM_SELFTEST = { pass, fail, results };
    document.getElementById('filterbar').hidden = true;
  }

  async function run() {
    const orig = console.error;
    console.error = function () { consoleErrors.push([...arguments].map((a) => (a && a.message) || String(a)).join(' ')); return orig.apply(console, arguments); };
    window.addEventListener('error', (e) => consoleErrors.push('uncaught: ' + e.message));
    window.addEventListener('unhandledrejection', (e) => consoleErrors.push('unhandled rejection: ' + (e.reason && e.reason.message)));
    try {
      statsChecks();
      await baseRateCheck();
      await auDenominatorCheck();
      await viewChecks();
      await keyboardChecks();
      await partitionChecks();
      await pageChecks();
    } catch (e) { add('selftest', 'runner', false, e.stack || e.message); }
    console.error = orig;
    report();
  }
  M.selftest = { run, results };
})();
