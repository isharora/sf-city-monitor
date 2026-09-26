# design PROGRESS

## Done
- Read RULES.md (incl. network fairness rules and budget), the reference design at ~/sf-time-to-build/design, dataset metadata in */data/raw, performance/DATA_NOTES.md.
- design/prototype/: working static prototype (no libraries; file://; `?view=<id>&theme=dark`; `&data=1` opens the data panel). Landing, 4 dashboards (30 views), entity pages (org/contractor, dept, report, official), search, story mode per dashboard, data-transparency strip and panel on every page. Synthetic sample data from `sample-data/generate.py` (rerun to regenerate; writes bundle.js).
- Headless Chrome QA: every view screenshotted in light and dark (design/shots/*.png; scripts shots/shoot.sh, shots/console.sh); console clean on 43 states incl. edge-case filters; filter-application warning never fires.
- design/DESIGN.md; design/DATA_CONTRACT_{nonprofits,performance,audits,network}.md.

## Next (for the engineer / data agents)
- Data agents: export to `<module>/data/site/` per the contracts; set `sample: false`; fill `meta.files`, `sources`, rule `verify` items (network).
- Engineer: replace `sample-data/` with the exports; per-year splitting for payments, recs, flows; precomputed `search/index.json` optional.

## Paths
- design/DESIGN.md, design/DATA_CONTRACT_*.md, design/prototype/index.html, design/prototype/js/*.js, design/prototype/css/app.css, design/prototype/sample-data/generate.py, design/shots/
