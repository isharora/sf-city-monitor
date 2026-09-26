# Data contract — audits module ("Audit recommendations tracker")

The dashboard reads static JSON from `audits/data/site/`. `design/prototype/sample-data/audits/` follows this contract; `sample-data/generate.py` is the reference writer. Every rule is a *must* unless marked *may*.

## 1. Conventions
- Years are calendar years of the report date. Dates `YYYY-MM-DD`. Department ids are the Controller codes shared with the performance module (`meta.dimensions.dept` lists them with names); a recommendation has exactly one `dept` (the responding department); reports list all departments they cover.
- Sources: `csa` (Controller's City Services Auditor, incl. follow-up reports), `bla` (Budget and Legislative Analyst), `cgj` (Civil Grand Jury). Fixed colour slots 1–3.
- One shared five-step status scale and one four-step response scale (below); each body's own vocabulary is mapped and the mapping is exported so the UI can show it.
- Never `NaN`; use `null`. Keep small groups.

## 2. Client-side computation
Everything is derived from the one recommendation table: filters (year issued, source, dept, topic), status and response shares, months-to-implement quantiles, cumulative implementation curves by cohort (events = `months_to_close`, follow-up = months from `date_issued` to `meta.as_of`), repeats via `repeat_of`, consequence ranking via `consequence.score`. Reports are looked up by `report`.

## 3. Files

### `meta.json` — boot
```
sample, module: "audits", as_of, generated_at, version,
years: {min: 2014, max: 2025, note},
dimensions: {
  source: {label, kind: "categorical", values: [{id: "csa"|"bla"|"cgj", label, short, slot: 1..3}]},
  dept: {label, values: [{id, name, group, short}]},
  topic: {label, values: [{id, label}]},                      // contracts, it, hr, finance, safety, housing, facilities, service, governance (extend as coded)
  status: {label, kind: "ordinal", values: [{id, label}]},     // implemented | in_progress | open | not_implementing | closed_other
  agreed: {label, kind: "polarity", values: [{id, label}]},    // agree | partial | disagree | none
  priority: {label, values: [{id, label}]}                    // high | medium | low (null allowed in rows when the body does not rate)
},
status_mapping: {cgj: {<shared id>: "<Penal Code 933 term>", …}, bla: {…}, csa: {…}},
consequence_rule: str,                                       // the published formula (DESIGN.md §5.4 au-open); shown on the methods page
counts: {reports, recommendations}, small_n: 5, sources: [...], files: {...}
```

### `reports/reports.json`
```
reports: [{id, source, title, date, depts: [dept id], topic, url: str (required in production), pages: int|null, n_recs: int, summary: str,
           followups: [date], openbook_id?: str}]
```
Example: `{"id":"R-0123","source":"csa","title":"Audit of the Department of Public Health's Contract Monitoring","date":"2019-06-11","depts":["DPH"],"topic":"contracts","url":"https://openbook.sfgov.org/…/xxxx.pdf","pages":58,"n_recs":14,"summary":"…","followups":["2019-12-01","2020-06-01","2021-06-01"]}`.

### `recs/recs.json` (production: `recs/recs_<year>.json` by year issued)
```
rows: [{id, report, source, dept, date_issued, topic, priority: "high"|"medium"|"low"|null,
        text: str (the recommendation, verbatim or lightly shortened; ≤ 400 chars, full text in `text_full` if longer),
        agreed: agreed id, response_text: str|null,
        status: status id, status_date: date, months_to_close: num|null (implemented only; report date → first follow-up recording implemented),
        last_followup: date|null, repeat_of: id|null, repeat_confidence?: 0..1,
        dollars_at_stake: int|null, consequence: {score: 1..10, why: str|null}}]
```
Example: `{"id":"K-04122","report":"R-0123","source":"csa","dept":"DPH","date_issued":"2019-06-11","topic":"contracts","priority":"high","text":"DPH should require program managers to document monitoring visits within 30 days…","agreed":"agree","response_text":"DPH agrees and will…","status":"in_progress","status_date":"2025-12-01","months_to_close":null,"last_followup":"2025-12-01","repeat_of":"K-01877","repeat_confidence":0.86,"dollars_at_stake":null,"consequence":{"score":7,"why":"High priority; repeats an earlier recommendation; open more than three years."}}`

Rules: `months_to_close` is non-null iff `status = implemented`. `repeat_of` points to an earlier recommendation at the same department on the same theme, model-assisted and analyst-confirmed; store the confidence. `consequence.why` is required when `score ≥ 7` or `repeat_of` is set. Every recommendation cites its report through `report` (the UI links the report page, which links the PDF).

### `commentary/au-*.json`, `commentary/story_au.json`
Shared schema. Template ids and slots: `au-overview: ov` (`recs, recs_fmt, reports_fmt, years, impl_share, open_fmt, median_months`) · `au-status: status` (`recs, recs_fmt, years, impl_share, prog_share, open_share, notimpl_share`) · `au-time: time` (`impl, impl_fmt, years, median_months, p75_months, p90_months`) · `au-agreement: agree` (`recs, recs_fmt, years, agree_share, partial_share, disagree_share, impl_agreed, impl_disagreed`) · `au-repeat: repeat` (`repeats_fmt, recs_fmt, repeat_share, top_topic, top_topic_fmt`) · `au-open: open` (`open, open_fmt, years, high_fmt, dollars`). Story filters may set `years, source, dept, topic`.

## 4. Which view loads what
| View | Files |
|---|---|
| all au-* views | `recs/recs*.json`, `reports/reports.json` |
| report page | same |
| dept scorecard, org profile | `recs/recs*.json`, `reports/reports.json` |

## 5. QA checks
1. Every `report` id in recs exists in reports; `n_recs` equals the count of recs per report.
2. Every `source`, `dept`, `topic`, `status`, `agreed`, `priority` id exists in `meta.dimensions`.
3. `months_to_close` present iff `status = implemented`; `status_date ≥ date_issued`.
4. `repeat_of` targets exist, are earlier, and share `dept`; spot-check 40 pairs by hand and record the agreement rate in DATA_NOTES.
5. Every `reports[].url` resolves (HEAD 200) at export time.
6. `consequence.score` recomputes from the published rule for every row.
