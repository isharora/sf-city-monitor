# Money network module: progress log

## Status (update after every step)
- [x] 0: RULES.md read; module folders created.
- [x] 1: Dataset discovery via data.sf.gov/data.json + inventory y8fp-fbf5 (pipeline/00_probe.py -> data/raw/probe.json).
  Post-Mar-2018 FPPC 803 behested filings are PDF-only on NetFile (JS portal; Connect2 API returns nothing) -> documented gap.
- [x] 2: pipeline/01_download.py -> data/raw/*.csv + manifest.json (row counts).
- [x] 3: 02_normalize.py -> data/interim/*.parquet; 03_mentions.py (+03b_extra_pairs.py second pass after validation) -> data/er/org_*;
      06_officials.py -> officials, lobby_official_map.
- [x] 4: 04_adjudicate_orgs.py (Claude Sonnet, Opus for hard) -> org_pair_judgments.parquet (incremental; cached in data/cache/llm);
      05_people.py -> person_matches.parquet; 07_resolve.py -> org_entity_map/org_entities (lenient .7 / default .8 / strict .9);
      07b_entity_types.py -> entity_types.parquet (person-name detection for suppression).
- [x] 5: 10_validate.py sample -> data/validation/*_sample.csv; analyst labels in *_labels.csv; `score` -> validation_results.json.
- [x] 6: 08_network.py [variant] -> data/network/nodes*.parquet, edges*.parquet
- [x] 7: 09_analysis.py [--variant --person-t --tag] -> data/analysis/*.json|parquet; 12_redteam.py -> data/analysis/redteam.json
- [x] 8: 11_export.py -> data/site/ (contract design/DATA_CONTRACT_network.md; rules in pipeline/rules_network.json); 07c_type_exported.py (person-name suppression for low-activity names, then re-run 11); 13_extras.py (graph.json, summaries/, commentary_facts.json, commentary/, qa_report.json); data/site/CONTRACT_GAPS.md. QA: all contract checks pass (qa_report.json).
- [!] 9: ANALYSIS.md / DATA_NOTES.md: the harness blocked this subagent from writing .md report files; full text was handed back to the coordinator to save. Numbers are final as of 2026-09-26 08:40.

- [x] 10: Red-team pass 2 (2026-09-26): legal rules verified against enacted text (rules_network.json); roster.py (office holding);
      09 base_rates v2 (office-matched, calendar-weighted), lobbyist rule periods, IE dedup; 11 fairness fixes; 14_redteam2.py
      (re-derivations, fairness scans, Opus name re-check -> data/er/entity_type_overrides.parquet); 15_commentary.py; verify_commentary.py.
      Results: data/redteam/redteam2.json, data/redteam/verify_commentary.json.

- [x] 11: Office-history pass (2026-09-26): pipeline/offices_citywide.json (26 verified terms, 51 source quotes all found; complete
      2009-2026 succession of the 7 citywide offices incl. interim/acting terms). roster.py uses only this table for citywide holding
      (`python3 pipeline/roster.py verify` -> data/redteam/offices_citywide_verify.json); 09 Coverage.status uses exact term dates (2009+);
      11 labels interim/acting terms and pre-2009 holders (Susan Leal). 11: Form 803 filed_within_30_days = null. 15: nw-ban matched
      benchmark text generated directly; nw_behested callouts top/right. 14 adjudicate now merges with earlier overrides (a rerun had
      dropped 150 person-name decisions; restored from cache at $0). Reran 09 (+5 variants), 12, 11, 14 adjudicate, 11, 13, 15, 14 all,
      verify_commentary (131 traced, 0 untraced). Flags: 293 before and after, identical; 0 coverage changes. Site overrides for
      network removed; bundle 0 errors; check.sh 280/280. Spend this pass $1.83 (43 Opus calls).
      Open: site/content/commentary/official.json caveat still describes the old Form 700/contact method (site-owned).
      Arlo Smith (DA 1980-96) is not in the table: no official source found.

- [x] 12: Insights page (2026-09-26): pipeline/insights/ -> data/site/insights/insights.json (16 insights, contract design/insights/INSIGHTS_CONTRACT.json).
      classify_sectors.py (Sonnet sector labels for 1,731 org donors, overrides; data/insights/sector_labels*.{parquet,csv}); compute_build.py + spec.py +
      build_insights.py; verify_insights.py (independent recompute from interim/edges/raw; 263 values, 603 chart points, 0 failures -> data/redteam/verify_insights.json);
      check_private_names.py (291,602 private name pairs; 0 hits -> data/redteam/check_private_names.json); screen_candidates.py (18 dropped/folded ->
      data/redteam/insights_screening.json); fairness_review_insights.py (Opus, 2 passes; decisions in data/redteam/fairness_review_decisions.json).
      pipeline/run_all.sh created (--insights runs only this stage). Bundle: nw-insights 16 insights, 0 errors. Spend this pass $3.12.
      Known: 09_analysis.behested() dedup key collapses the 5 SFEC-3600 rows (behested.json says 221 used; insights use 225). Not fixed in 09.

## Rerun order
01 -> 02 -> 03 -> 03b -> 04 -> 05 -> 06 -> 07 -> 07b -> 08 (and `08 strict`, `08 lenient`) -> 09 (+ sensitivity tags) -> 10 score -> 12 -> 11 -> 14 adjudicate -> 11 -> 13 -> 15_commentary -> 14 all -> verify_commentary

## Notes
- LLM spend log: data/llm_usage.jsonl (budget $700; wrapper stops at $680).
- Designer contract arrived 2026-09-26 (design/DATA_CONTRACT_network.md); coordinator asked to verify rules[].cite/verify.
