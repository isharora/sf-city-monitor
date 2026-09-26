/* data.js - lazy data loader with an in-memory cache.
   Production: fetch(`${base}/${path}`) per view. Prototype on file:// (fetch blocked): fall
   back to sample-data/bundle.js (window.SFCM_SAMPLE_BUNDLE, written by generate.py). */
(function () {
  const M = (window.SFCM = window.SFCM || {});
  const BASE = 'sample-data';
  const cache = new Map(), inflight = new Map();
  const loaded = new Set(); // every path loaded so far (for the data panel)
  async function load(path) {
    if (cache.has(path)) return cache.get(path);
    if (inflight.has(path)) return inflight.get(path);
    const p = (async () => {
      let data = null;
      if (location.protocol !== 'file:') { try { const r = await fetch(`${BASE}/${path}`, { cache: 'no-cache' }); if (r.ok) data = await r.json(); } catch (e) { /* fall through */ } }
      if (!data) { if (!window.SFCM_SAMPLE_BUNDLE) await loadBundle(); data = window.SFCM_SAMPLE_BUNDLE && window.SFCM_SAMPLE_BUNDLE[path]; }
      if (!data) throw new Error(`Missing data file: ${path}`);
      cache.set(path, data); loaded.add(path); inflight.delete(path);
      return data;
    })();
    inflight.set(path, p);
    return p;
  }
  let bundlePromise;
  function loadBundle() { if (bundlePromise) return bundlePromise; bundlePromise = new Promise((res, rej) => { const s = document.createElement('script'); s.src = `${BASE}/bundle.js`; s.onload = res; s.onerror = () => rej(new Error('bundle.js failed to load')); document.head.appendChild(s); }); return bundlePromise; }
  async function loadAll(map) { const keys = Object.keys(map); const vals = await Promise.all(keys.map((k) => load(map[k]))); const out = {}; keys.forEach((k, i) => (out[k] = vals[i])); return out; }
  M.data = { load, loadAll, cache, loaded };
})();
