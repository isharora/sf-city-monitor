# Audits module — DATA NOTES

Sources, fields, extraction, matching and validation for the Audit recommendations tracker.
Numbers marked TBD are filled in by the final run (see ANALYSIS.md for findings).

## 1. Sources (all fetched politely: 1 request/second/host, disk-cached, custom User-Agent)

| Source id | What | Where it was found | Coverage |
|---|---|---|---|
| `csa-reports` | Controller's Office reports: City Services Auditor audits, assessments, reviews, Public Integrity reviews, City Performance reports, Whistleblower program reports, and CSA follow-up reports | Legacy Controller report search `https://openbook.sfgov.org/webreports/search.aspx` (ASP.NET form; categories `AU` Audit Reports, `CP` City Performance, `Whistleblower`). Each hit links to `details3.aspx?id=N`, whose PDF URL is stored inside the base64 `__VIEWSTATE` (length-prefixed string; decoded in `01_inventory.py`). Old `sfcontroller.org` file URLs still serve PDFs. 7 PDFs from 2023 whose sf.gov paths 404 were re-located through the sf.gov Wagtail documents API (`api.sf.gov/api/v2/documents/?search=`), exact-title matches only. | 1986 (one ACFR) and 2002–2026; audit content is dense from 2005 |
| CSA follow-up | Semiannual/quarterly "City Services Auditor Follow-up on Recommendation Implementation Status" (2012–2026), annual "Recommendations Not Implemented After More Than Two Years" (2014–2025), "Field Follow-up of …" memos, Public Integrity status updates (2021, 2022, 2024, 2026) | Same OpenBook listing (category AU); classified by title | 2009–2026 |
| `cgj-status` | Controller's tracking documents "Status of the Civil Grand Jury Recommendations" by jury term (Admin. Code §2.10), each showing the original response and later follow-up responses by year | `https://www.sf.gov/information--status-civil-grand-jury-recommendations/` | Jury terms 2003-04 … 2024-25 (latest updated December 2025) |
| `cgj-reports` | Civil Grand Jury reports and department/official responses (Penal Code §933.05) | Archive `https://civilgrandjury.archive.sf.gov/{YYYY_YYYY}.html` (1995-96 … 2021-22) and sf.gov pages `https://www.sf.gov/resource--20XX--civil-grand-jury-reports-*` (2020-21 … 2025-26; found via `api.sf.gov/api/v2/pages/?search=`) | Reports 1995-96 onward; responses posted mainly from 2014-15 onward |
| `bla-reports` | Budget and Legislative Analyst reports for the Board of Supervisors | `https://sfbos.archive.sf.gov/budget-legislative-analyst-reports` (2010–2025) and `https://www.sf.gov/budget-and-legislative-analyst-bla` (2026) | 2010–2026; only titles containing "audit" (performance/management audits) are extracted |

There is no public machine-readable CSA recommendation dashboard that we could find; the follow-up PDFs are the public record. Web search was unavailable during this build, so discovery relied on the sites' own listings and APIs.

## 2. Pipeline (`audits/pipeline/`, rerun in order)
1. `01_inventory.py` → `data/raw/inventory.json` (doc_id, source, doc_type, title, date, url, listing_url).
   doc_ids: `CON-<openbook id>`, `CGJ-<term>-<sha1(url)[:8]>`, `BLA-<sha1(url)[:8]>`, `CGJS-<term>`.
2. `02_download.py` → `data/pdfs/`, `data/text/` (per-page text via PyMuPDF), `data/raw/downloads.json`. PDFs with <200 characters/page are flagged `ok_low_text` (scans) and are given to Claude as native PDFs.
3. `03_extract.py` (+ `extract_schemas.py`) → `data/extract/reports/`, `data/extract/status/` (Sonnet 5), `*_opus/` (QC).
4. `04_normalize.py` → `data/work/{reports,recommendations,status_items,report_level,dept_map}.json`.
5. `05_link.py` → `data/work/links_report.json`, `links_rec.json`.
6. `06_qc_compare.py` → `data/qc/` (Opus agreement).
7. `07_build_rows.py` → `data/work/rows.json` (one row per recommendation × responding department for CGJ; one per recommendation otherwise).
8. `08_dollars.py` → `data/work/dollars.json`.
9. `09_repeats.py` → `data/work/repeat_clusters.json`, `repeat_of.json`, `data/qc/repeat_validation.json`.
10. `10_analysis.py`, `11_export_site.py` → `ANALYSIS` numbers, `data/site/`.
LLM calls: `pipeline/llm.py` caches every request by hash (`data/cache/llm/`) and logs cost to `data/llm_usage.jsonl`.

## 3. Extraction (Claude Sonnet 5, adaptive thinking, structured JSON output)
Recommendations (`reports` mode), per report: kind, departments, plain summary, report date, the report's own stated recommendation count, overall response, dollar-quantified findings (amount, kind, page); and for every recommendation: number, verbatim text (≤ ~120 words), the problem addressed, responsible departments, category (15-value enum), secondary category, priority if stated, response (agree/partially agree/disagree/not stated/other) with the printed label, target date (as printed + ISO), PDF page of the text and of the response, and a 0–1 confidence for text, department, category, response, target date.
- Text PDFs are sent as text with `[[PAGE n]]` markers (PDF page numbers). Scans and tabular status documents are sent as PDF (status docs in 4-page chunks); Claude reports page numbers within the chunk and the pipeline adds the offset.
- Triage: a text PDF with no occurrence of "recommend" is recorded as having no recommendations without an LLM call (financial statements, attestation reports, etc.).
- Status (`status` mode): per recommendation × department: cited original report title/date, number, text, respondent, original CGJ response (Penal Code 933.05 categories), latest status (8-value enum), status date, explanation, page; plus report-level rows (CSA "reports closed" tables with counts).
- Controller CGJ trackers: `**` in a response column means "response not required: fully implemented or abandoned" as of an earlier column; the latest substantive response is used.

## 4. Department ids
Canonical names are assigned by Claude (`04_normalize.py`, `dept_normalize` task) and mapped to the Controller department codes used by the performance module (`performance/pipeline/common.py` `DEPT_NAMES`), e.g. `POL`, `FIR`, `DPH`, `MTA`, `MYR` (Mayor incl. MOHCD), `HOM`. Commissions map to their department except independent ones (Ethics, Civil Service, Arts, Police Commission → `POL`). Extensions: `CITYWIDE`, `NONCITY` (contractors, school district), `TIDA`, `UNK`.

## 5. Status and response mapping
See `pipeline/maps.py` (`STATUS`, `AGREED`, `CGJ_AGREED`, `STATUS_MAPPING`). We use the contract's five statuses plus `unknown` (no follow-up found).

**Extraction statuses:**
- implemented
- partially_implemented → `in_progress`
- in_progress
- open (includes "requires further analysis")
- not_implementing ("will not be implemented", declined)
- closed_other (abandoned, no longer applicable, superseded)
- contested → `open`
- unknown

**Evidence rules** (`07_build_rows.py`): the latest dated event wins. A recommendation-level terminal status beats a report-level closure. Events with unknown status are ignored.

**Evidence per source:**
- **CSA.** Recommendation-level items come from field follow-ups, Public Integrity updates, "not implemented after 2 years" lists, and older follow-up summaries. Report-level "reports closed" rows set every recommendation in the report to implemented as of the follow-up period's end.
- **CSA absence inference** (audits only; not City Performance, Whistleblower, or Public Integrity, which are outside CSA's follow-up program — no follow-up document cites them). A recommendation issued on or after 2010-07-01 and at least 2 years before a "not implemented after 2 years" list is closed by that list's date when the list does not mention its report. If the list details specific recommendations of the report, it counts as closed when it is not among them. This also overrides an older "open" status.
- **CGJ.** Rows are recommendation × responding department. The original response is the earliest response letter or the tracker's original column. Status is the latest tracker column. In the tracker, "**" means the item was resolved in an earlier column, so the latest substantive response is used. Response-letter dates are parsed from the listing title or file name; otherwise report date + 90 days (flagged).
- **Dates.** Year-only dates are set to Dec 31, clamped to the status document's date.
- **months_to_close** = report date → first implemented event.

## 6. Linking and validation
`05_link.py` links each status item to a report, then to a recommendation.

**Report linking.** Response letters use their listing parent (the same sf.gov/archive page). Otherwise we use fuzzy title matching (rapidfuzz token-set/sort, plus a date-proximity bonus) within:
- the jury term ±1, plus terms around the cited date, for CGJ;
- Controller and BLA reports, for CSA.

Accepted if the score is ≥92 with a margin of ≥8; below 45, no match; in between, Claude Sonnet adjudicates (up to 6 candidates).

**Recommendation linking:**
- normalized number match with text similarity ≥60;
- CSA summaries paraphrase, so number-first unless another recommendation's text matches ≥85 and ≥25 points better;
- a parent number (e.g., "1") links to all sub-parts (1a–1c);
- otherwise text similarity ≥85 with a margin of ≥10;
- otherwise Claude adjudication.

Items citing Grand Jury *findings* (F1, F.C.2) are dropped. Legacy 2006–2008 Controller CGJ status reports are excluded; the per-term trackers cover the same terms.

**Result:** 11,854 of 12,214 status items linked to a recommendation.

**Hand validation** (`data/validation/`):
- Round 1, 64 links: 57 of 60 linked were correct. The 3 errors came from paraphrased CSA summaries overriding numbers, plus 3 missed links (sub-parts, paraphrase). Both led to linker fixes.
- Round 2 (final method), 64 links: 62 of 63 correct, 1 uncertain, and 1 correct non-link (a finding).

**De-duplication** (`02b_dedupe.py`): identical bytes within a document type, CGJ report titles ≥95 similar within a term, and 1 manual pair. 50 duplicate documents were skipped, mostly 2020–22 Grand Jury reports and responses posted on both the archive and sf.gov.

**Departments:** Claude canonicalization, then mapping to Controller codes, with 7 analyst overrides (`pipeline/dept_overrides.json`).

**Dollar findings:**
- `08a_verify_dollars.py` re-checks each against the cited page text. It keeps only money lost, owed, questioned, savable, or overrun, and converts totals to the stated difference. 1,181 of 1,365 kept.
- `08_dollars.py` links findings to recommendations. The largest linked finding becomes `dollars_at_stake`.

**Repeat findings** (`09_repeats.py`):
- Opus clusters each department's recommendations (blocks by topic when >420). A cluster needs ≥2 reports and ≥2 years.
- `repeat_of` uses clusters with confidence ≥0.6.
- Validation: an independent Sonnet pair judge confirmed 87% of 150 random pairs. The analyst confirmed 37 of 40 final pairs (92.5%) and 34 of 40 in the pre-dedupe round, 88.7% combined. The judge called 43% of 100 near-miss non-pairs repeats; these are mostly recurring tenant-level concession findings, deliberately excluded by the definition.

## 7. Quality control

**Opus re-extraction** (`06_qc_compare.py`, `data/qc/qc_results.json`): 42 random reports (383 recommendations by Opus) and 15 status documents.

| Measure | Result |
|---|---|
| Recommendation recall | 98.2% |
| Precision | 99.2% |
| Response | 96.3% |
| Target date | 94.7% |
| Department | 90.7% |
| Category, exact | 76.3% |
| Category, lenient | 96.0% |
| Verified page | 83.2% |
| Status items | 94.8% |
| CGJ original response | 96.5% |

The Opus pass used the same input mode as Sonnet: 7 PDF-mode documents were re-run for Opus after the partial-scan fix.

**Page verification:** every recommendation's text is searched in the PDF text. 6,741 verified, 2,300 corrected (often Claude used printed page numbers), 549 unverified, 339 scans.

**Partial scans:** text PDFs where ≥15% of pages (≥2) are near-empty were re-extracted as native PDF. Recommendation counts barely changed (1,630 → 1,638), but recorded department responses rose from 622 to 906.

**Cross-checks against the Controller:**
- 3,095 CSA audit recommendations for FY2011–FY2025 vs CSA's own 2,887.
- 97% implemented vs CSA's 99%.
- Recommendations open more than 2 years (June 2025) match CSA's list.

**Report URL check:** 895 of 895 HEAD 200 (superset of the 881 exported).

**Known limitations:**
- Lettered sub-parts are split (7% more recommendations than CSA counts).
- CSA time-to-implement is an upper bound for most rows (report-level closure).
- Status is largely department self-report (only 11% of implemented statuses are auditor field-verified).
- BLA has no follow-up.

## 8. Money, dates, units
Dollars are nominal as stated in each report (no deflator applied, since amounts are never summed or compared across years). Dates are ISO. Ages are measured from the report date to the as-of date, 2026-09-26.

## 9. Red team 2 (independent check, fairness, commentary)
Code in `pipeline/redteam2/` (see `run_all.sh`); results in `data/redteam/redteam2.json`.
- **Re-derivation** (`rederive.py`) reads only the published export (`data/site/`). All seven headline numbers reproduce exactly. Robustness checks added: evidence mix behind CSA "implemented" (83% report closure or absence inference; 80% with recommendation-level evidence, n=708; 86% auditor-verified, n=608); Board/Mayor share of Grand Jury refusals (697 of 1,658; excluding them implemented leads 1,039 to 961); agreement vs status within each body (CSA disagreed: 58 of 76 implemented) and circularity for the Grand Jury; staleness of "open".
- **Disagreement reasons** (`reasons.py`): every `agreed = disagree` response (1,436; 1,435 classified) is classified by Claude Sonnet 5 from the extracted response summary into one primary reason (authority, existing process, alternative, legal, cost, merits, none), with a rationale and confidence. Analyst read 8 random items: all plausible. Shares are approximate.
- **PDF spot-check** (`spotcheck.py`): 25 random rows (seed 20260926; 10 CSA, 10 CGJ, 5 BLA), checked by an Opus second reader against the cited pages (scans as images) and reviewed by the analyst. Text 25/25 correct (3 lightly shortened), department 24/25, response and status consistent except one row: K-6986bb01bb (Mayor, CGJ 2004-05 Rec 7) carries the Juvenile Probation Department's response and a combined tracker label.
- **Commentary** is generated by `12_commentary.py` with every number, quote and dated fact inserted through a traced placeholder; `verify_commentary.py` recomputes each metric from `data/site/` with separate code and checks quotes word for word against the PDF text (172 tokens, 0 failures, 0 untraced numbers).
