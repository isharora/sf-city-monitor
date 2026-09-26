"""Prompts and JSON schemas for Claude extraction."""

CATEGORIES = [
    "financial_controls",        # accounting, cash handling, payments, reconciliations, budgeting controls
    "contracting_procurement",   # solicitation, contract management, vendor oversight, change orders
    "grants_nonprofit_oversight",  # grant agreements, nonprofit/CBO monitoring
    "revenue_billing",           # fees, collections, rates, revenue capture
    "performance_measurement",   # metrics, goals, data reporting, evaluation
    "it_data_systems",           # IT governance, security, systems, data quality
    "staffing_hr_payroll",       # staffing levels, hiring, training, overtime, payroll
    "safety_health",             # public/worker safety, health, emergency preparedness
    "service_delivery",          # program operations and outcomes for the public
    "governance_oversight",      # policies & procedures, commission oversight, roles, accountability
    "ethics_integrity",          # conflicts of interest, gifts, fraud risk, ethics rules
    "capital_assets_inventory",  # capital projects, facilities, fleet, inventory, property
    "compliance_legal",          # compliance with laws, codes, regulations
    "planning_policy",           # strategy, long-range planning, policy change
    "other",
]

RESPONSES = ["agree", "partially_agree", "disagree", "not_stated", "other"]

STATUSES = ["implemented", "partially_implemented", "in_progress", "open", "not_implementing",
            "closed_other", "contested", "unknown"]

CGJ_RESPONSES = ["has_been_implemented", "will_be_implemented", "requires_further_analysis",
                 "will_not_be_implemented", "other", "not_applicable"]

DOLLAR_KINDS = ["questioned_costs", "potential_savings", "overpayment_or_loss",
                "unrecovered_or_uncollected_revenue", "cost_overrun", "other"]


def _nullable(t):
    return {"type": [t, "null"]}


CONF = {"type": "number", "description": "0-1 confidence"}

REPORT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["report", "recommendations"],
    "properties": {
        "report": {
            "type": "object",
            "additionalProperties": False,
            "required": ["report_kind", "has_recommendations", "departments", "summary",
                         "report_date", "stated_recommendation_count", "overall_response",
                         "dollar_findings", "notes"],
            "properties": {
                "report_kind": {"type": "string", "enum": [
                    "performance_audit", "financial_or_compliance_audit", "assessment_or_review",
                    "public_integrity_review", "investigation", "civil_grand_jury_report",
                    "follow_up_report", "financial_statement_or_attestation", "analysis_or_study",
                    "other"]},
                "has_recommendations": {"type": "boolean"},
                "departments": {"type": "array", "items": {"type": "string"},
                                "description": "City departments/agencies audited or to whom recommendations are directed, full official names"},
                "summary": {"type": "string", "description": "Plain-language summary, max 60 words"},
                "report_date": _nullable("string"),
                "stated_recommendation_count": {"type": ["integer", "null"],
                                                "description": "Total number of recommendations the report itself says it makes, if stated"},
                "overall_response": _nullable("string"),
                "dollar_findings": {"type": "array", "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["amount_usd", "kind", "description", "page", "confidence"],
                    "properties": {
                        "amount_usd": {"type": "number"},
                        "kind": {"type": "string", "enum": DOLLAR_KINDS},
                        "description": {"type": "string"},
                        "page": {"type": ["integer", "null"]},
                        "confidence": CONF}}},
                "notes": _nullable("string"),
            },
        },
        "recommendations": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["rec_id", "text", "finding", "departments", "category",
                         "secondary_category", "priority", "response", "response_raw",
                         "target_date", "target_date_iso", "page", "response_page",
                         "conf_text", "conf_department", "conf_category", "conf_response",
                         "conf_target_date"],
            "properties": {
                "rec_id": {"type": "string", "description": "Number/label as printed, e.g. '3', '2.1', 'R4'"},
                "text": {"type": "string", "description": "Recommendation text, verbatim (up to ~120 words; trim with ... if longer)"},
                "finding": {"type": "string", "description": "The problem this addresses, plain language, max 35 words"},
                "departments": {"type": "array", "items": {"type": "string"}},
                "category": {"type": "string", "enum": CATEGORIES},
                "secondary_category": {"type": "string", "enum": CATEGORIES + ["none"]},
                "priority": {"type": ["string", "null"], "description": "Priority / risk rating only if the report states one"},
                "response": {"type": "string", "enum": RESPONSES},
                "response_raw": {"type": ["string", "null"], "description": "Department's response label/words as printed, e.g. 'Concur', 'Partially Agree'"},
                "target_date": {"type": ["string", "null"], "description": "Implementation target date/timeline as stated"},
                "target_date_iso": {"type": ["string", "null"], "description": "YYYY-MM-DD best reading of target date, else null"},
                "page": {"type": ["integer", "null"], "description": "PDF page where the recommendation text appears"},
                "response_page": {"type": ["integer", "null"]},
                "conf_text": CONF, "conf_department": CONF, "conf_category": CONF,
                "conf_response": CONF, "conf_target_date": CONF,
            }}},
    },
}

REPORT_SYSTEM = """You are an expert government-audit analyst building a research database of recommendations that San Francisco oversight bodies (the Controller's City Services Auditor, the Board of Supervisors' Budget and Legislative Analyst, and the Civil Grand Jury) made to City departments.

You will receive one report, either as text with [[PAGE n]] markers (n = PDF page number, starting at 1) or as a PDF. Extract:

1. Report-level facts: kind of report, departments audited or addressed, a plain-language summary (max 60 words, neutral, factual, no speculation), the report date, the total number of recommendations the report itself says it makes (e.g. from the transmittal letter or executive summary, else null), the overall management response, and dollar-quantified findings the report explicitly states (questioned costs, potential savings, overpayments/losses, uncollected revenue, cost overruns). Only include dollar amounts the report states as findings; do not add or infer amounts; do not include budget totals or contract values that are merely context. Use the PDF page number for every page field.

2. EVERY recommendation the report makes to a City department, agency, commission, the Mayor or the Board of Supervisors. Rules:
- One entry per distinct numbered recommendation. If a recommendation has lettered sub-parts (1a, 1b), make one entry per sub-part.
- Do NOT duplicate a recommendation that is repeated in an executive summary, a summary table, and the body: record it once, using its full wording and its main page (prefer the body or the final recommendations list). Put the page where the full text appears.
- Do not include recommendations the report merely quotes from OTHER, earlier reports (e.g. in a background section or a status table of prior audits), unless this report re-issues them as its own recommendations.
- If the report is a follow-up/status report that only reports on earlier recommendations and makes no new ones, return an empty list and set report_kind to follow_up_report.
- If the report makes no recommendations (e.g. financial statements, clean compliance reviews, pure data reports), return an empty list and has_recommendations=false.
- text: copy the recommendation wording verbatim (up to about 120 words; trim with "..." if longer).
- departments: the department(s) responsible for acting, with full official names (e.g. "San Francisco Municipal Transportation Agency", "Department of Public Health", "Office of the Controller", "Mayor's Office", "Board of Supervisors").
- category: choose the single best fit from the enum; secondary_category optional.
  financial_controls = accounting, cash handling, payments, reconciliations, payroll processing controls; contracting_procurement = solicitations, contract terms, contract/vendor monitoring; grants_nonprofit_oversight = grant agreements and monitoring of nonprofits; revenue_billing = fees, rates, billing, collections; performance_measurement = goals, metrics, data reporting, evaluation; it_data_systems = IT governance/security/systems/data quality; staffing_hr_payroll = staffing, hiring, training, overtime, HR policy; safety_health = public/worker safety, health, emergency preparedness; service_delivery = how programs serve the public; governance_oversight = written policies and procedures, commission/management oversight, roles, accountability structures; ethics_integrity = conflicts of interest, gifts, fraud risk, ethics compliance; capital_assets_inventory = capital projects, facilities, fleet, inventory, property; compliance_legal = compliance with laws/regulations/codes; planning_policy = strategy, long-range plans, policy or legislative change.
- priority: only if the report assigns a priority or risk rating to the recommendation (e.g. "High risk"); else null.
- response: the responsible department's response as printed in the report (e.g. in a recommendation-and-response matrix or attached management letter): Concur/Agree/Will implement -> agree; Partially concur/partially agree -> partially_agree; Do not concur/Disagree/Will not implement -> disagree; response not included in this document -> not_stated (Civil Grand Jury reports normally do not contain responses: use not_stated); anything else (e.g. "will consider", "further analysis") -> other. Copy the printed label/wording into response_raw.
- target_date: the implementation date or timeline the department or report gives for this recommendation, as stated, and your best ISO reading (YYYY-MM-DD; use the last day of a stated month/quarter/fiscal year; null if none).
- Confidence fields: 0-1, your confidence that each field is correct (lower it for OCR problems, ambiguous responsibility, inferred categories, or responses you had to match across pages).

Be exhaustive: recommendations are the core of this database. Be precise: never invent text, numbers, dates or pages."""


STATUS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["doc", "items", "report_level"],
    "properties": {
        "report_level": {"type": "array", "description": "Report-level status rows (e.g. tables of reports closed, or reports with open recommendations and counts)", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["source_report_title", "source_report_date", "department", "event",
                         "n_open", "n_implemented", "n_closed_not_implemented", "n_total",
                         "avg_age_months", "page"],
            "properties": {
                "source_report_title": {"type": "string"},
                "source_report_date": {"type": ["string", "null"]},
                "department": {"type": ["string", "null"]},
                "event": {"type": "string", "enum": ["report_closed", "report_has_open_recs",
                                                      "report_followed_up", "other"]},
                "n_open": {"type": ["integer", "null"]},
                "n_implemented": {"type": ["integer", "null"]},
                "n_closed_not_implemented": {"type": ["integer", "null"]},
                "n_total": {"type": ["integer", "null"]},
                "avg_age_months": {"type": ["number", "null"]},
                "page": {"type": ["integer", "null"]}}}},
        "doc": {
            "type": "object", "additionalProperties": False,
            "required": ["as_of_date", "kind", "summary_counts", "notes"],
            "properties": {
                "as_of_date": {"type": ["string", "null"], "description": "Date the statuses are as of (YYYY-MM-DD if possible)"},
                "kind": {"type": "string", "enum": ["csa_followup_summary", "csa_open_over_2yrs",
                                                     "csa_field_followup", "public_integrity_status",
                                                     "cgj_status_tracker", "cgj_response", "other"]},
                "summary_counts": {"type": ["string", "null"], "description": "Any overall counts the document states (e.g. '85 of 120 implemented'), verbatim-ish"},
                "notes": {"type": ["string", "null"]},
            }},
        "items": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["source_report_title", "source_report_date", "department", "rec_id",
                         "rec_text", "respondent", "original_response_raw", "original_response",
                         "status_raw", "status", "status_date", "target_date", "explanation",
                         "page", "confidence"],
            "properties": {
                "source_report_title": {"type": "string", "description": "Title of the ORIGINAL audit/report the recommendation came from, as printed"},
                "source_report_date": {"type": "string", "description": "Date of the original report as printed (or YYYY-MM-DD)"},
                "department": {"type": "string", "description": "Department the recommendation is directed to (full name)"},
                "rec_id": {"type": "string", "description": "Recommendation number as printed, e.g. '4', 'R2.3'"},
                "rec_text": {"type": "string", "description": "Recommendation text verbatim if printed (up to ~100 words), else null"},
                "respondent": {"type": "string", "description": "Official/entity giving the response (CGJ documents), else null"},
                "original_response_raw": {"type": "string", "description": "Original/initial response label if the document shows one (CGJ: e.g. 'Will be implemented in the future')"},
                "original_response": {"type": "string", "enum": CGJ_RESPONSES},
                "status_raw": {"type": "string", "description": "Most recent status/response label as printed"},
                "status": {"type": "string", "enum": STATUSES},
                "status_date": {"type": "string", "description": "Date or year the most recent status applies to"},
                "target_date": {"type": "string"},
                "explanation": {"type": "string", "description": "Department's or auditor's explanation of the status, max 50 words, close to verbatim"},
                "page": {"type": ["integer", "null"]},
                "confidence": CONF,
            }}},
    },
}

STATUS_SYSTEM = """You are an expert government-audit analyst building a database that tracks whether recommendations made by San Francisco oversight bodies were implemented.

You will receive a document (or a page range of one) that reports the STATUS of previously issued recommendations, or a department's formal response to Civil Grand Jury recommendations. Text is given with [[PAGE n]] markers (n = PDF page number) or as a PDF.

Extract one item per recommendation per responding department that has a status or response in the pages given. Rules:
- source_report_title/source_report_date: the ORIGINAL report the recommendation came from, as printed (for Civil Grand Jury responses, the Grand Jury report being responded to).
- rec_id as printed (e.g. "3", "R1.2", "Recommendation 4"). rec_text verbatim if printed, else null.
- status (most recent status shown in the document), mapped as follows:
  implemented = fully implemented / closed as implemented / "has been implemented" / "recommendation implemented";
  partially_implemented = partially implemented (explicitly);
  in_progress = being implemented, in progress, "will be implemented in the future", work under way, target date set;
  open = open / not yet implemented / not started / pending / "requires further analysis" or "further study";
  not_implementing = the department will not implement it or declines ("will not be implemented", "not warranted or not reasonable", risk accepted);
  closed_other = closed without implementation for other reasons: abandoned, no longer applicable or relevant, superseded, overtaken by events, closed by the auditor as not feasible;
  contested = the department disputes the recommendation and the auditor keeps it open/unresolved;
  unknown = no status stated.
  Copy the printed label into status_raw.
- original_response (Civil Grand Jury documents only; "not_applicable" otherwise): the department's initial response category required by California Penal Code 933.05: has_been_implemented, will_be_implemented (in the future), requires_further_analysis, will_not_be_implemented (not warranted or not reasonable); other if the response does not fit. For a Civil Grand Jury response letter, the response in the letter is the original_response AND also map it to status (has been implemented -> implemented; will be implemented in the future -> in_progress; requires further analysis -> open; will not be implemented -> not_implementing).
- Controller Civil Grand Jury tracking documents show an original response and one or more later follow-up responses by year: put the original in original_response(_raw) and the LATEST follow-up in status/status_raw/status_date (the year of the latest response column that has content). If a row shows only an original response, map status from it.
- In Controller tracking documents, "**" in a response column means "Response not required: recommendation has been fully implemented or abandoned" as of an EARLIER column. In that case use the latest substantive (non-**) response as the status (e.g. an earlier "Recommendation Implemented" -> implemented; "Will not be implemented" -> not_implementing; "abandoned"/"no longer relevant" -> closed_other; if the earlier substantive response was still "will be implemented"/"further analysis", the ** means it was later resolved one way or the other: use status unknown and status_raw "** (implemented or abandoned)"). Put the substantive label followed by " [then **]" in status_raw, and use the year of the substantive response as status_date.
- Read table columns carefully: each row is one recommendation x one responding department; response columns are ordered by year left to right.
- status_date: date/year the most recent status applies to (for summary reports, the report's as-of date if no row date).
- explanation: short, close to verbatim (max 50 words).
- Include rows for all departments listed. Do not merge different departments' responses to the same recommendation.
- Tables that list whole REPORTS (e.g. "reports and memorandums closed" = all recommendations in that report are closed; or reports with N open recommendations) go into report_level, one row per report x department, with any counts shown. They should NOT become items. Overall totals go in doc.summary_counts.
- page: PDF page where the item appears. confidence 0-1.
Never invent information. When a text field is not shown, use an empty string "" (or null where allowed)."""
