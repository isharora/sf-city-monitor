/* normalize.js - accept the documented shape variants of the module exports so one shape reaches
   the views. Mirrors normalize() in tools/bundle.py (bundled chunks are already normalized; this
   runs again on JSON fetched directly from ../<module>/data/site/ over http, and is idempotent). */
(function () {
  const M = (window.SFCM = window.SFCM || {});
  const ENTITY_SUB = ['official', 'committee', 'department', 'contractor', 'nonprofit', 'lobbyist', 'individuals', 'donor_org'];

  function normalize(module, rel, obj) {
    if (!obj || typeof obj !== 'object') return obj;
    if (rel === 'meta.json') {
      if (obj.files && typeof obj.files === 'object') {
        const pre = module + '/', out = {};
        for (const k in obj.files) out[k.startsWith(pre) ? k.slice(pre.length) : k] = obj.files[k];
        obj.files = out;
      }
      const d = obj.deflator;
      if (d && !d.index && d.multiplier_to_base) { d.index = {}; for (const k in d.multiplier_to_base) if (d.multiplier_to_base[k]) d.index[k] = 1 / d.multiplier_to_base[k]; }
    }
    // (integral float years such as 2013.0 parse to integers in JavaScript; nothing to do for YEAR_FIELDS)
    if (module === 'performance' && rel === 'measures/values.json') for (const r of obj.rows || []) if (typeof r.met === 'number') r.met = !!r.met;
    if (module === 'performance' && rel === 'measures/measures.json') for (const m of obj.measures || []) if (typeof m.direction === 'string' && m.direction.endsWith('_better')) m.direction = m.direction.slice(0, -7);
    if (module === 'network' && rel === 'entities.json') for (const e of obj.entities || []) for (const t of ENTITY_SUB) { const sub = e[t]; if (sub && typeof sub === 'object' && !Array.isArray(sub)) for (const k in sub) if (!(k in e)) e[k] = sub[k]; }
    if (module === 'network' && rel === 'flows.json') for (const f of obj.flows || []) { const sub = f[f.type]; if (sub && typeof sub === 'object' && !Array.isArray(sub)) for (const k in sub) if (!(k in f)) f[k] = sub[k]; }
    if (module === 'network' && rel === 'analyses/loop.json') for (const r of obj.rows || []) if (!('city_paid' in r)) for (const k in r) { const m = k.match(/^city_paid_fy(\d{4})$/); if (m) { r.city_paid = r[k]; r.city_paid_fy = +m[1]; } }
    return obj;
  }
  M.normalize = normalize;
})();
