/* state.js - single source of truth for view, filters, entity id, search, mode and theme,
   mirrored to the URL with history.replaceState so every state is shareable.
   URL grammar (all optional, order-free):
     ?view=np-flows            view id (default home)
     &years=2019-2025          inclusive year range (each dashboard has its own min/max)
     &dept=DPH,HSH             departments (empty = all)         nonprofits, performance, audits
     &area=homeless            nonprofit service areas            nonprofits
     &size=25m+                nonprofit size bands               nonprofits
     &group=protection         department groups                  performance
     &real=0                   nominal dollars (default real)     nonprofits, performance
     &source=csa,cgj           recommending body                  audits
     &topic=contracts          audit topics                       audits
     &flow=contribution        flow types                         network
     &etype=contractor         entity types                       network
     &amt=10000                minimum amount                     network
     &id=org-014               entity id for profile pages
     &q=housing                search query
     &theme=dark&mode=story&step=2&data=1&v.<key>=<value> */
(function () {
  const M = (window.SFCM = window.SFCM || {});
  const LIST_KEYS = ['dept', 'area', 'size', 'group', 'source', 'topic', 'flow', 'etype'];
  const DEFAULTS = { view: 'home', years: null, dept: [], area: [], size: [], group: [], real: true, source: [], topic: [], flow: [], etype: [], amt: 0, id: null, q: '', theme: 'auto', mode: 'explore', step: 0, data: false, v: {} };
  let state = parse(location.search);
  const subs = new Set();

  function parse(qs) {
    const q = new URLSearchParams(qs);
    const s = JSON.parse(JSON.stringify(DEFAULTS));
    if (q.get('view')) s.view = q.get('view');
    if (q.get('years')) { const m = q.get('years').match(/^(\d{4})(?:-(\d{4}))?$/); if (m) { const a = +m[1], b = m[2] ? +m[2] : +m[1]; s.years = [Math.min(a, b), Math.max(a, b)]; } }
    for (const k of LIST_KEYS) if (q.get(k)) s[k] = q.get(k).split(',').filter(Boolean);
    if (q.has('real')) s.real = q.get('real') !== '0';
    if (q.get('amt')) s.amt = Math.max(0, +q.get('amt') || 0);
    if (!['explore', 'story'].includes(s.mode)) s.mode = 'explore';
    if (!['auto', 'light', 'dark'].includes(s.theme)) s.theme = 'auto';
    if (q.get('id')) s.id = q.get('id');
    if (q.get('q')) s.q = q.get('q');
    if (q.get('theme')) s.theme = q.get('theme');
    if (q.get('mode')) s.mode = q.get('mode');
    if (q.get('step')) s.step = +q.get('step') || 0;
    if (q.has('data')) s.data = q.get('data') !== '0';
    for (const [k, v] of q.entries()) if (k.startsWith('v.')) s.v[k.slice(2)] = v;
    return s;
  }
  function serialise(s) {
    const q = new URLSearchParams();
    q.set('view', s.view);
    if (s.years) q.set('years', `${s.years[0]}-${s.years[1]}`);
    for (const k of LIST_KEYS) if (s[k].length) q.set(k, s[k].join(','));
    if (!s.real) q.set('real', '0');
    if (s.amt) q.set('amt', String(s.amt));
    if (s.id) q.set('id', s.id);
    if (s.q) q.set('q', s.q);
    if (s.theme !== 'auto') q.set('theme', s.theme);
    if (s.mode !== 'explore') { q.set('mode', s.mode); q.set('step', s.step); }
    if (s.data) q.set('data', '1');
    for (const k in s.v) if (s.v[k] != null && s.v[k] !== '') q.set('v.' + k, s.v[k]);
    return '?' + q.toString();
  }
  function get() { return state; }
  function set(patch, opts) {
    const next = Object.assign({}, state, patch);
    if (patch.v) next.v = Object.assign({}, state.v, patch.v);
    const changedView = next.view !== state.view;
    if (changedView && !patch.v) next.v = {}; // per-view controls do not leak across views
    state = next;
    try { history.replaceState(null, '', serialise(state) + location.hash); } catch (e) { /* some file:// contexts refuse; state still applies */ }
    for (const fn of subs) fn(state, { changedView, patch, silent: opts && opts.silent });
  }
  function subscribe(fn) { subs.add(fn); return () => subs.delete(fn); }
  /** Clear only the filters that the given dashboard owns. */
  function resetFilters(keys) { const p = {}; for (const k of keys) p[k] = JSON.parse(JSON.stringify(DEFAULTS[k])); set(p); }
  function filtersActive(s, keys) { return keys.some((k) => (k === 'years' ? !!s.years : k === 'real' ? !s.real : k === 'amt' ? !!s.amt : s[k] && s[k].length)); }
  /** Year range in effect for a dashboard with bounds [min,max]. */
  function years(s, bounds) { if (!bounds) return [0, 0]; if (!s.years) return [bounds.min, bounds.max]; const c = (y) => Math.max(bounds.min, Math.min(bounds.max, y)); const a = c(s.years[0]), b = c(s.years[1]); return [Math.min(a, b), Math.max(a, b)]; }
  const inList = (list, v) => !list.length || list.includes(v);
  M.state = { get, set, subscribe, resetFilters, filtersActive, years, inList, parse, serialise, DEFAULTS, LIST_KEYS };
})();
