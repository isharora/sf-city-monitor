# SF City Monitor — site

One static site, four accountability dashboards (nonprofit money, budget vs outcomes, audit
recommendations, money network), entity pages, search, methods, story mode. No build step, no
external libraries, fonts or CDNs. Works from `file://` and from any static host.

## Run

Open `site/index.html` in a browser (double-click works). Every state is a URL, for example
`index.html?view=np-flows&dept=HSH&real=0&theme=dark&data=1`. Keyboard: `/` search, `[` `]` views,
`s` story, `d` dark, `?` help.

To serve it over http (the loader then reads real exports straight from `../<module>/data/site/`):

```sh
cd ~/sf-city-monitor && python3 -m http.server 8000   # then open http://localhost:8000/site/
```

## Data: rebundle

```sh
python3 site/tools/bundle.py          # rebuild site/data/ and print the readiness report
python3 site/tools/bundle.py --strict # exit 1 if a module that ships real data has an invalid file
```

For each module the bundler looks for `<module>/data/site/meta.json` (or `<module>/data/site/<module>/`).
A module uses its real export only when that meta **validates and says `"sample": false`**; otherwise
the whole dashboard falls back to `design/prototype/sample-data/` and every view shows a sample banner
(real and sample data are never mixed within a dashboard). Every file is validated against
`tools/contracts.py`, the machine-readable version of `design/DATA_CONTRACT_*.md`: required fields and
types are errors (the file is not used and only the views that need it show "Analysis not available
yet"); unknown ids, sizes over 400 KB, missing report URLs and similar are warnings. The report
lists every missing file and field. Documented shape variants are normalized in one place
(`normalize()` in `bundle.py`, mirrored in `js/normalize.js`): nested per-type entity/flow objects,
`multiplier_to_base` deflators, float years, numeric `met`, `*_better` directions, `city_paid_fy<y>`.

Output: `site/data/manifest.js` (what exists, its status, sizes, errors) and
`site/data/<module>/<file>.<n>.js` chunks (≤ ~380 KB each; large arrays are column-encoded, long text
fields the site never shows are dropped from the bundle only). On http the loader reads the raw
export for real modules unless the bundled chunk is much smaller; on `file://` it always uses chunks.
Per-year production files (`payments/cells_<fy>.json`, `recs/recs_<year>.json`, `flows/flows_<year>.json`,
`spending/cells_<fy>.json`, `measures/values_<fy>.json`) are merged automatically.

Commentary callouts (`annotations[]`) are drawn on these chart ids: `np_trend` (np-overview, np-flows),
`pf_trend` (pf-overview, pf-spending), `pf_ot` (pf-staffing), `au_issued` (au-overview), `au_impl`
(au-status), `nw_dollars` (nw-overview), `nw_behested` (nw-behested); `x` is the category (fiscal or
calendar year) and `series` optionally picks a line. The bundler warns about any other id.

Rerun the bundler whenever a module re-exports. Site-level commentary (home, search, methods, entity
pages) lives in `site/content/commentary/`.

## Check

```sh
site/tools/check.sh                 # bundle, render all states light+dark, console, self-test
site/tools/check.sh --no-shots      # console + self-test only
site/tools/check.sh --only pf-      # just the states whose name starts with pf-
site/tools/fixture_test.sh          # missing/invalid-file behaviour and the http fetch path
```

`check.sh` renders every `?view=` (all dashboard views, entity pages, search, methods, story mode,
the data panel, a focused graph, a filtered and an empty state, an unknown id) in light and dark with
headless Chrome, reports console errors, and writes screenshots to `/tmp/scm_site/`. It then runs the
in-page self-test (`index.html?selftest=1`, also usable by hand), which:

- checks the statistics code (quantiles, histogram, cumulative incidence with censoring, deflation,
  null-safe sums, window coverage) and recomputes the ban-window base rate from the contract windows
  against the exporter's figure;
- on every dashboard view sets each declared filter and checks that the view's numbers and its
  "Data on this page" strip both change, that the filter bar shows exactly the declared filters,
  that undeclared ones are labelled "Not on this view: … (reason)", and that counts are registered;
- checks that records matched per department / recommender / group / flow type add up to the
  unfiltered total (no filter drops or double-counts rows);
- renders every entity page and checks unknown ids.

Results: page title `SELFTEST PASS n/n`, a table in the page, and `/tmp/scm_site/selftest.json`.

## Deploy

Copy `site/` to any static host (it only needs `index.html`, `css/`, `js/`, `data/`). To let the
http loader read the raw exports too, deploy the repository root so that `../<module>/data/site/`
exists next to `site/`; without it the bundled chunks are used. Rebundle before deploying.

## Layout

```
index.html            shell (sidebar, top bar, filter bar, story bar, help)
css/app.css           tokens (light/dark), layout, charts, states
js/stats.js           pooling, quantiles, incidence, deflation, formatters
js/charts.js          SVG charts (bars, stacks, lines, heat grid, range bars, scatter, dot strip, slope,
                      dumbbell, tables) with keyboard focus, tooltips and table twins
js/network.js         deterministic network graph
js/normalize.js       shape variants → one shape (mirror of bundle.py)
js/data.js            manifest-driven lazy loader (chunks or fetch)
js/state.js           URL state
js/commentary.js      finding, live sentences with fallbacks, analyst's read, caveats, data strip/panel
js/views-*.js         one scope() per dashboard; every card consumes it
js/selftest.js        ?selftest=1
tools/                bundle.py, contracts.py, check.sh/check.py, fixture_test.sh
content/commentary/   site-level commentary
data/                 generated by bundle.py (do not edit)
```
