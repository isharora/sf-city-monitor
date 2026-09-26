# SF City Monitor

Four accountability dashboards about San Francisco's government, built from public data. Each one leads with about 20 tested findings, and every number traces to a public dataset.

1. **Follow the nonprofit money:** city payments and contracts to nonprofits, linked to their IRS 990 finances, city dependency, contract growth and Controller monitoring findings.
2. **Budget vs outcomes:** what each department spends (real dollars, per resident, headcount, overtime) and what it gets for it (its own performance measures, cost per outcome, targets eased or dropped).
3. **Audit recommendations tracker:** about 9,900 recommendations from 881 Controller, Budget and Legislative Analyst, and Civil Grand Jury reports (1996–2026). What was recommended, whether departments agreed, and what happened.
4. **Money network:** campaign money, independent expenditures, lobbying, behested payments and city contracts, with verified legal rules and base rates.

**Open the site:** [`site/index.html`](site/index.html). It is static and works offline. On GitHub Pages it's at `/site/`.

## How it was made
- **Methods:** each module's pipeline is in `<module>/pipeline/` (`run_all.sh` reruns it end to end). Methods and caveats are in `<module>/DATA_NOTES.md` and on each dashboard's Methods view. Design specs and data contracts are in `design/`.
- **Checks:** every headline finding was independently re-derived by a separate red-team pass and stress-tested. Commentary and insight numbers are recomputed from the source tables by verifier scripts. A fairness review covered every page that names an organization or official.
- **Fairness rules** are in [`RULES.md`](RULES.md):
  - Private individuals appear only in aggregates.
  - A donation near a contract or approval is a pattern worth checking, not proof of anything.
  - "Unusual" is not "improper".
- **What's not in this repo:** raw downloads, PDFs, caches and the entity-matching working files. They are large, and some contain private donors' names. The site ships the bundled, privacy-checked dashboard data. The pipelines re-download everything from the public sources.
