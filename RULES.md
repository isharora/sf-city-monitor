# Working rules for every agent on SF City Monitor

- **Work only inside your module folder** (`nonprofits/`, `performance/`, `audits/` or `design/`). Other folders are read-only for you.
- **Keep `<module>/PROGRESS.md` updated after every step** (done, next, file paths), so a restarted agent can resume.
- **Put a timeout on every network and API call.** There's no `timeout` binary on this Mac, so wrap commands as `perl -e 'alarm N; exec @ARGV' cmd ...`. Never block on a background job with no timeout, and never wait indefinitely on your own background tasks.
- **Claude API:** the `anthropic` Python SDK is installed and credentials are configured. Log every call (timestamp, task, model, tokens, cost) to `<module>/data/llm_usage.jsonl`, cache results, and stop at your module's budget.
  - Models: `claude-sonnet-5` for bulk work ($2 / $10 per million input/output tokens); `claude-opus-5-5` for hard judgments ($4 / $20).
  - Use adaptive thinking, with `output_config` effort "high" for hard calls. Never use `budget_tokens` (it's rejected).
  - Store a rationale and a confidence score with each judgment.
- **Data sources:** DataSF lives on the new domain, data.sf.gov (e.g. `https://data.sf.gov/resource/<id>.json`, and CSV via `https://data.sf.gov/api/views/<id>/rows.csv?accessType=DOWNLOAD`). The Socrata catalog search is broken for this domain, so find datasets through `https://data.sf.gov/api/views/<id>.json`, sf.gov pages, and known IDs. Confirmed IDs:
  - Vendor Payments (Vouchers): `n9pm-xkyq`
  - Supplier Contracts: `cqi5-hm2d`
  - Budget: `xdgd-c79v`
  - Spending and Revenue: `bpnb-jwfb`
  - Employee Compensation: `88g8-5mnd`
  - 311 Cases: `vw6y-z8j6`
- **Rigor:**
  - Verify that every dataset exists and check its row counts.
  - Write down what each field actually means (read the data dictionaries).
  - Validate record matches on hand-checked samples.
  - Stress-test every finding (confounders, definition changes, inflation: state nominal vs real dollars and the deflator used), and write down the alternative explanations you considered.
  - Never invent values or URLs.
- **Fairness:** these are accountability dashboards about real organizations and people.
  - Report facts with context, and never imply wrongdoing the data doesn't show.
  - Distinguish "unusual" from "improper".
  - Name organizations; don't single out individual employees below the executive or elected level.
  - For any audit finding, cite the report.
- **Plain language:** American English, for smart non-experts.
- **Outputs:** follow `design/DATA_CONTRACT_<module>.md` once it exists; until then, export sensibly named JSON to `<module>/data/site/`. Write `<module>/ANALYSIS.md` (findings, numbers, caveats), `<module>/DATA_NOTES.md` (sources, fields, matching, validation), and code in `<module>/pipeline/` that reruns end to end.

## Budget (updated by the user)
The whole project's Claude API budget is **$2,500**:

| Module | Budget |
|---|---|
| nonprofits | $600 |
| performance | $400 |
| audits | $500 |
| network | $700 |
| reserve (red-team and commentary passes) | $300 |

## Extra fairness rules for the network module (donors, officials, contractors)
- **Who can be named:** organizations; elected and appointed officials acting in their public roles; registered lobbyists; city contractors and their disclosed principals.
- **Private individuals:** appear only in aggregates, unless they are one of the above. Never show home addresses, even though filings contain them.
- **Timing:** a donation near a contract or an approval is a pattern worth checking, never proof of improper influence. Say so wherever such links appear.
- **Legal status:** state the relevant legal rules, such as the contractor contribution ban and behested-payment disclosure, and whether a transaction appears to fall inside or outside them, with the exact rule cited. Never assert a violation; at most say "appears to warrant review", and explain why.
