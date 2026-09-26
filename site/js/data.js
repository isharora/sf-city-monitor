/* data.js - lazy, per-view data loader with an in-memory cache.
   Source of truth: window.SFCM_MANIFEST (data/manifest.js, written by tools/bundle.py). For every
   logical file ("nonprofits/payments/cells.json") the manifest says whether it is ok, missing or
   invalid, whether it is real or sample, its size, the raw export paths and the bundled chunks.
   - http(s) and a real module: fetch the raw export(s) from ../<module>/data/site/, normalize, and
     fall back to the chunks if the fetch fails (for example when only site/ is deployed).
   - file:// (Chrome blocks fetch) or sample modules: inject the chunk <script>s.
   A missing or invalid file rejects with a DataError; the app blanks only the views that need it. */
(function () {
  const M = (window.SFCM = window.SFCM || {});
  const MAN = window.SFCM_MANIFEST || null;
  const cache = new Map(), inflight = new Map();
  const info = new Map(); // logical -> {bytes, sample, via, parts}
  const parts = new Map(); // logical -> {n, got: [], resolve, reject}

  class DataError extends Error {
    constructor(logical, status, errors) { super(`${status === 'missing' ? 'Missing' : status === 'invalid' ? 'Invalid' : 'Could not load'} data file: ${logical}`); this.logical = logical; this.status = status; this.errors = errors || []; }
  }

  function moduleOf(logical) { const m = logical.split('/')[0]; return m; }
  function modEntry(module) { if (!MAN) return null; for (const k in MAN.modules) if (MAN.modules[k].module === module) return MAN.modules[k]; return null; }
  /** Manifest entry for a logical file, or null. */
  function entry(logical) {
    if (!MAN) return null;
    const mod = moduleOf(logical);
    if (mod === 'site') return MAN.site[logical] || null;
    const me = modEntry(mod); if (!me) return null;
    return me.files[logical] || me.commentary[logical] || null;
  }
  function status(logical) { const e = entry(logical); return e ? e.status : 'unknown'; }

  window.SFCM_DATA_PART = function (logical, i, n, obj) {
    let p = parts.get(logical);
    if (!p) { p = { n, got: new Array(n) }; parts.set(logical, p); }
    p.got[i] = obj;
    if (p.got.filter(Boolean).length === p.n && p.resolve) p.resolve(merge(p.got));
  };
  const isEnc = (v) => v && typeof v === 'object' && v.__enc === 'cols';
  /** Merge chunk parts (arrays concatenated) and decode columnar arrays written by bundle.py. */
  function merge(list) {
    const out = list[0];
    for (let i = 1; i < list.length; i++) for (const k in list[i]) {
      const v = list[i][k];
      if (Array.isArray(v) && Array.isArray(out[k])) { for (const r of v) out[k].push(r); }
      else if (isEnc(out[k]) && v && Array.isArray(v.rows)) { for (const r of v.rows) out[k].rows.push(r); }
      else if (!(k in out)) out[k] = v;
    }
    for (const k in out) if (isEnc(out[k])) out[k] = decode(out[k]);
    return out;
  }
  function decode(enc) {
    const cols = enc.cols, dicts = enc.dicts || {}, sparse = new Set(enc.sparse || []), n = cols.length, rows = new Array(enc.rows.length);
    const dcol = cols.map((c) => dicts[c] || null);
    for (let i = 0; i < enc.rows.length; i++) {
      const src = enc.rows[i], o = {};
      for (let j = 0; j < n; j++) { let v = src[j]; if (v == null) { if (sparse.has(cols[j])) continue; v = null; } else if (dcol[j]) v = dcol[j][v]; o[cols[j]] = v; }
      rows[i] = o;
    }
    return rows;
  }
  function viaChunks(logical, e) {
    return new Promise((resolve, reject) => {
      let p = parts.get(logical);
      if (!p) { p = { n: e.chunks.length, got: new Array(e.chunks.length) }; parts.set(logical, p); }
      p.resolve = resolve; p.reject = reject;
      e.chunks.forEach((src, i) => {
        if (p.got[i]) return;
        const s = document.createElement('script');
        s.src = src; s.async = true;
        s.onerror = () => reject(new DataError(logical, 'error', [`chunk failed to load: ${src}`]));
        document.head.appendChild(s);
      });
      if (p.got.filter(Boolean).length === p.n) resolve(merge(p.got));
    });
  }
  async function viaFetch(logical, e) {
    const mod = moduleOf(logical), rel = logical.slice(mod.length + 1);
    const objs = [];
    for (const path of e.raw) { const r = await fetch(path, { cache: 'no-cache' }); if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`); objs.push(await r.json()); }
    const obj = merge(objs);
    if (mod !== 'site' && !rel.startsWith('commentary/')) M.normalize(mod, rel, obj);
    // light shape check: every array the bundle saw must still be an array
    if (e.split_key && !Array.isArray(obj[e.split_key])) throw new Error(`${logical}: '${e.split_key}' is no longer an array`);
    return obj;
  }

  async function load(logical) {
    if (cache.has(logical)) return cache.get(logical);
    if (inflight.has(logical)) return inflight.get(logical);
    const p = (async () => {
      const e = entry(logical);
      if (!e) throw new DataError(logical, 'missing', ['not listed in data/manifest.js; rerun tools/bundle.py']);
      if (e.status !== 'ok') throw new DataError(logical, e.status, e.errors);
      let data = null, via = 'chunks';
      const me = modEntry(moduleOf(logical));
      if (/^https?:$/.test(location.protocol) && e.raw && e.raw.length && me && me.source === 'real' && !M.data.forceChunks && !e.repaired && !(e.chunk_bytes && e.chunk_bytes < 0.8 * e.bytes)) {
        try { data = await viaFetch(logical, e); via = 'fetch'; } catch (err) { console.info(`[data] ${logical}: using bundled chunks (${err.message})`); data = null; }
      }
      if (!data) data = await viaChunks(logical, e);
      cache.set(logical, data);
      info.set(logical, { bytes: e.bytes, sample: !!e.sample, via, parts: via === 'fetch' ? e.raw.length : e.chunks.length, warnings: (e.warnings || []).length });
      return data;
    })();
    inflight.set(logical, p);
    try { return await p; } finally { inflight.delete(logical); }
  }
  /** Load a {key: logical} map. opts.optional: missing files resolve to null (recorded in the result's __missing). */
  async function loadAll(map, opts) {
    const keys = Object.keys(map), out = { __missing: {} };
    const res = await Promise.allSettled(keys.map((k) => load(map[k])));
    res.forEach((r, i) => {
      if (r.status === 'fulfilled') out[keys[i]] = r.value;
      else { out[keys[i]] = null; out.__missing[keys[i]] = r.reason instanceof DataError ? r.reason : new DataError(map[keys[i]], 'error', [String(r.reason && r.reason.message)]); }
    });
    if (!(opts && opts.optional)) { const miss = Object.values(out.__missing); if (miss.length) { const e = miss[0]; e.all = miss; throw e; } }
    return out;
  }
  M.data = { load, loadAll, entry, status, info, modEntry, manifest: MAN, DataError, forceChunks: false };
})();
