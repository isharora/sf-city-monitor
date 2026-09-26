"""Red team 2: assemble data/redteam/redteam2.json from the parts.

Parts (all rerunnable, LLM calls cached):
  rederive.py    independent re-derivation of the headline findings from data/site/
  reasons.py     model-classified reasons for every 'disagree' response (Sonnet)
  spotcheck.py   25 random recommendations checked against the PDFs (Opus second reader + analyst)
  stories_check.json  the five headline stories checked word for word (analyst subagent, PDF pages)
  ../verify_commentary.py  every number/quote in the commentary recomputed/checked
Verdicts below are the analyst's judgments; every number they cite is read from the parts.
"""
import json
import os
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
RT = os.path.normpath(os.path.join(HERE, "..", "..", "data", "redteam"))
USAGE = os.path.normpath(os.path.join(HERE, "..", "..", "data", "llm_usage.jsonl"))


def load(name):
    p = os.path.join(RT, name)
    return json.load(open(p)) if os.path.exists(p) else None


def main():
    R = load("rederive.json")
    reasons = load("reasons.json")
    spot = load("spotcheck.json")
    stories = load("stories_check.json")
    ver = load("verify_commentary.json")
    f1, f2, f3, f4, f5, f6, f7 = (R[k] for k in ("F1_csa_implemented", "F2_cgj", "F3_agreement", "F4_bos", "F5_will_be_implemented", "F6_open", "F7_repeats"))
    spend = sum(json.loads(l)["cost_usd"] for l in open(USAGE) if '"redteam2_' in l)

    verdicts = [
        {"finding": "CSA 96% implemented", "reproduced": f"{f1['implemented']}/{f1['n_known']} = {f1['rate']}",
         "verdict": "holds as a record of CSA closures; overstated as proof of change",
         "why": f"{round(100*f1['share_of_implemented_from_report_level_closure_or_inference'])}% of CSA 'implemented' comes from whole-report closure or absence from CSA's 2-year list. "
                f"Recommendation-level evidence only: {f1['rate_rec_level_evidence_only']['rate']} (n={f1['rate_rec_level_evidence_only']['n']}); auditor-verified only: "
                f"{f1['rate_auditor_verified_only']['rate']} (n={f1['rate_auditor_verified_only']['n']}). All-rows denominator: {f1['rate_all_rows']}. CSA itself says 'departments report having implemented'. "
                "A closed-report table (CON-1454 p.2) shows closures can include items 'no longer applicable'.",
         "action": "commentary states the evidence mix and the 80%/86% alternatives; caveat on self-report"},
        {"finding": "Grand Jury 43%; 'will not' outnumbers 'implemented'", "reproduced": f"{f2['status']['implemented']}/{f2['n_known']} = {f2['rate']}; will-not {f2['status']['not_implementing']}",
         "verdict": "holds numerically; the 'outnumbers' framing is driven by two respondents",
         "why": f"Board of Supervisors + Mayor give {f2['status']['not_implementing'] - f2['excluding_BOS_and_MYR_rows']['not_implementing']} of {f2['status']['not_implementing']} refusals; excluding them, implemented leads "
                f"{f2['excluding_BOS_and_MYR_rows']['implemented']} to {f2['excluding_BOS_and_MYR_rows']['not_implementing']} (rate {f2['excluding_BOS_and_MYR_rows']['rate']}). Per distinct recommendation (any respondent implemented): {f2['distinct_rec_level']['rate']}. "
                f"Model-classified reasons for CGJ refusals: {reasons['summary']['cgj']['shares']}.",
         "action": "au-status headline rewritten to carry the concentration and the reasons"},
        {"finding": "Agreement predicts action (92% vs 6%)", "reproduced": f"agree {f3['pooled']['agree']['rate']} (n={f3['pooled']['agree']['n']}), disagree {f3['pooled']['disagree']['rate']} (n={f3['pooled']['disagree']['n']})",
         "verdict": "misleading as pooled: largely compositional and partly circular",
         "why": f"{round(100*f3['disagree_rows_by_source_share']['cgj'])}% of 'disagree' rows are Grand Jury 'will not be implemented' answers whose later status mostly repeats the answer; 'agree' includes "
                f"{f3['cgj_has_been_implemented_rows_in_agree']['n']} 'has been implemented' answers (implemented by construction). Within CSA: agree {f3['by_source']['csa']['agree']['rate']} vs disagree "
                f"{f3['by_source']['csa']['disagree']['rate']} (n={f3['by_source']['csa']['disagree']['n']}). Non-circular CGJ test: 'will be implemented' {f3['cgj_noncircular_by_response_with_tracker_followup']['will_be_implemented']['rate']}, "
                f"'further analysis' {f3['cgj_noncircular_by_response_with_tracker_followup']['requires_further_analysis']['rate']}.",
         "action": "au-agreement headline replaced; pooled figure kept only with the explanation; high caveat added"},
        {"finding": "Board of Supervisors disagrees 57%", "reproduced": f"{f4['agreed']['disagree']}/{f4['n_responses']} = {f4['disagree_share']} ({f4['by_source']['cgj']} of the responses are to CGJ)",
         "verdict": "holds numerically (ANALYSIS.md's '291 of 513' and Mayor '252 of 770' are stale; export gives 271/472 and 237/721); needs policy-choice framing",
         "why": f"Board refusal reasons (model-classified, n={reasons['summary']['BOS']['n']}): {reasons['summary']['BOS']['shares']}. Standard Board wording: supports the recommendation but lacks operational authority (CGJS-2004-05 p.4).",
         "action": "framed as a legislature's choice; reasons shown; never presented as ignoring auditors"},
        {"finding": "'Will be implemented' -> 67% implemented, 18% reversed", "reproduced": f"{f5['final_status']['implemented']}/{f5['n_with_tracker_entry']} = {f5['implemented_rate']}; reversed {f5['final_status']['not_implementing']} = {f5['reversed_rate']}",
         "verdict": "holds",
         "why": f"Board of Supervisors accounts for {f5['reversed_by_dept'].get('BOS')} of the reversals; excluding the Board: {f5['excluding_BOS']['implemented_rate']} implemented, {f5['excluding_BOS']['reversed_rate']} reversed. "
                "Some 'reversals' are a respondent later saying the item is not its role (e.g. City Administrator on HSH monitoring), not abandoning the fix.",
         "action": "used as the cleaner agreement test"},
        {"finding": "223 open > 2 years, 175 > 5 years", "reproduced": f"{f6['over_2y']} / {f6['over_5y']} of {f6['open_or_in_progress']}",
         "verdict": "holds as 'last recorded status'; not evidence the items are undone",
         "why": f"{f6['over_2y_last_followup_more_than_2y_ago']} of {f6['over_2y']} have had no follow-up in over 2 years; median last follow-up year {f6['over_2y_median_last_followup_year']}; CGJ {f6['over_2y_by_source'].get('cgj')}.",
         "action": "au-open headline leads with staleness"},
        {"finding": "1,137 repeats in 434 clusters", "reproduced": f"{f7['repeat_rows']} rows, {f7['distinct_clusters_among_repeat_rows']} clusters; {f7['n_bad']} invalid links",
         "verdict": "holds; cluster ids cited in ANALYSIS.md are stale (C-0236 -> C-0241 Police, C-0140 -> C-0137 contractor evaluation, C-0118/C-0088 -> C-0117/C-0087 Airport)",
         "why": f"{f7['predecessor_status'].get('implemented')} repeats follow a predecessor recorded implemented; {f7['cross_source_repeats']} cross-body; {f7['confidence_lt_0_8']} have confidence < 0.8; judge confirmed {round(100*f7['validation']['judge_confirms_pos'])}% of 150 pairs. "
                "Airport certified-report chain is 26 reports over 14 years, not '20 audits over 13 years'.",
         "action": "commentary cites report counts computed from the export, not cluster ids"},
        {"finding": "Only 11% auditor-verified", "reproduced": f"{R['evidence']['auditor_verified_share']}", "verdict": "holds", "why": str(R["evidence"]["by_basis"]), "action": "high caveat on overview"},
    ]
    corrections = [
        "Agreement headline (92% vs 6%) replaced: pooled contrast is compositional/circular; within CSA 76% of disagreed recs were still implemented (58/76).",
        "ANALYSIS.md 3.4: Board 57% is 271 of 472 (not 291 of 513); Mayor 33% is 237 of 721 (not 252 of 770).",
        "ANALYSIS.md 3.6 cluster ids are stale; Airport certified-report chain = 26 reports over 14 years.",
        "Story 4.1: 'no positions civilianized since FY2019-20' overstates the BLA; it says SFPD 'was unable to share details on any positions that have been civilianized since FY 2019-20'. CON-761/773 are consultant (PERF) reports commissioned by the Controller. 2018 overtime recs: SFPD 'partially implemented two'.",
        "Story 4.2: R2 is a plan for the parts of the City without high-pressure water, not citywide; R8 last status 'Will Be Implemented in the Future' (2022 column), not 'in progress (December 2022)'; hose-tender figure is on p.1.",
        "Story 4.3: the quoted phrase is the report title; body sentence used instead (CON-3045 p.3). The six open City Option items are not repeats.",
        "Story 4.4: 2014-15 R3 — only the Board said 'will not'; the Mayor reported it implemented in 2016 via an ordinance. Shovel Ready R3 passed through 'requires further analysis' (2023) before 'will not' (2024), citing Public Works budget constraints.",
        "Story 4.5 not supported as written: '10 open, 9 in progress, 1 partial' describes August 2024; the September 2026 update reports 86 of 91 closed; R9a-b/R10a are 'Partially Implemented and Closed', not in progress.",
        "au-open headline: previous '25 score 7+' counted unknown/not-implementing rows the page does not show; the page's open list has 14 at 7+.",
        "au-overview template claimed '(of those with a follow-up status)' but the site's impl_share divides by all rows; templates now describe the site's denominators.",
        "Extraction error found in spot-check: K-6986bb01bb (Mayor, CGJ 2004-05 Rec 7) carries the Juvenile Probation Department's response and a combined tracker label.",
    ]
    fairness = [
        "Every 'will not' is presented as a decision with its stated reasons (authority, existing process, alternative, legal, cost) and shares; Board/Mayor refusals framed as policy choices.",
        "CSA vs Grand Jury gap explicitly framed as leverage and scope, never as departments ignoring auditors (headline, paragraph, high caveat).",
        "Stories quote departments' own explanations (SFPD overtime impact; City capital planning process; DPH City Option policy changes; Public Works budget constraints).",
        "Only organizations and elected/appointed bodies are named; no staff below executive level. Fairness lint words avoided.",
        "Repeats framed as 'a signal to check, not proof a fix failed'; 508 repeats follow implemented predecessors.",
        "Open items framed as last recorded status; 163 of 223 untracked for over two years.",
    ]
    site_issues = [
        "au-overview 'Implemented' tile and au-status/au-reports shares divide by ALL rows incl. no-follow-up (unfiltered 40%), while the finding uses known-status rates (96%/43%). Suggest a known-status denominator (or a second tile/slot, e.g. impl_share_known) and label the denominator.",
        "au-agreement: agree/partial/disagree shares include 'none' in the denominator and impl_agreed/impl_disagreed count unknown status as not implemented. Consider known-status denominators.",
        "au-agreement heat-grid note is wrong/unsupported: rows are agree, partial, disagree, none, so 'bottom-left' is none x implemented, and 'disagreed, implemented anyway usually follows a Board hearing' has no support in the data. Suggest: 'Read across a row: of recommendations with this response, the share at each status. For the Grand Jury, a will-not answer usually is the final status.'",
        "au-open sums dollars_at_stake into a {dollars} slot; findings overlap across recommendations/reports and the module's rule is never to total them. Drop the sum or relabel as 'largest single figure'.",
        "au-repeat 'how to read' says 'an analyst confirmed the link'; in fact clusters are model-drawn and a sample was checked (judge 87%, hand 37/40).",
        "au-open 'how to read' omits two components of the consequence rule (declined; safety/health/ethics topic).",
        "au-time step curves treat the 651 inferred-implemented CSA rows (months_to_close null) as never implemented, biasing CSA curves down; could use months_to_close_upper or exclude them.",
        "Story filters use arrays (source:['cgj'], dept:['BOS'], dept:['POL'], source:['csa']); check that enterStory applies them.",
    ]
    out = {"generated_at": datetime.now(timezone.utc).isoformat(), "analyst": "red team 2 (independent of 10b_redteam.py)",
           "verdicts": verdicts, "rederive": R,
           "reasons_summary": reasons["summary"] if reasons else None,
           "spotcheck": {"n": spot["n"], "seed": spot["seed"], "second_reader_summary": spot["summary_second_reader"],
                         "analyst_review": {x["id"]: x["analyst"] for x in spot["items"] if x.get("analyst")},
                         "result": "23 of 25 correct or minor-only; 1 confirmed error (K-6986bb01bb: Mayor row carries another respondent's response/status); 1 second-reader 'error' overturned (absence inference verified across the whole CON-1772 list)",
                         "items": [{k: x[k] for k in ("id", "source", "year", "dept", "report", "page", "status", "status_basis")} | {"overall": x["check"]["overall"], "rationale": x["check"]["rationale"]} for x in spot["items"]]} if spot else None,
           "stories": stories, "commentary_verification": ver["summary"] if ver else None,
           "corrections": corrections, "fairness_changes": fairness, "site_issues_for_orchestrator": site_issues,
           "api_spend_usd": round(spend, 2)}
    json.dump(out, open(os.path.join(RT, "redteam2.json"), "w"), indent=1, ensure_ascii=False, default=str)
    print("redteam2.json written; spend", round(spend, 2), "; verification", out["commentary_verification"])


if __name__ == "__main__":
    main()
