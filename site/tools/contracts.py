"""Machine-readable version of design/DATA_CONTRACT_<module>.md, used by bundle.py.

Each module lists its logical files (paths relative to <module>/data/site/). A file spec has:
  arrays   {array_key: {field: type}}   row arrays and the fields every row must carry
  keys     {key: type}                  required top-level keys (besides the arrays)
  split    glob for the production per-year (or size) split; the base file and every split part are
           merged into one logical file and rows are de-duplicated on `key` (a size-limited base file
           plus a complete split, as the nonprofits export ships, yields the complete set)
  enums    {"array.field": "dim:<dimension>" | "a|b|c" | "ref:<file>#<array>.<field>"}
  optional True when a missing file is not an error (the UI copes without it)
  bundle_drop {array_key: [fields]} long text fields the site never shows; left out of the bundle only
            (they stay in the export; over http the site reads the export itself when it is not larger)

Types: str, int, num, bool, list, dict, date, any; a trailing "?" allows null (the key must
still be present unless the type starts with "~", which means the key itself is optional).
Violations of types/required fields are errors (the file is not used); unknown enum values and
references are warnings (the UI shows the raw id), except where marked strict.
"""

COMMON_KEYS = {"as_of": "~date", "sources": "~list", "sample": "~bool"}

DIMS = {
    "nonprofits": ["dept", "area", "size_band", "result"],
    "performance": ["dept", "group", "char"],
    "audits": ["source", "dept", "topic", "status", "agreed"],
    "network": ["etype", "flow"],
}

VIEWS = {
    "nonprofits": ["np-overview", "np-flows", "np-dependency", "np-pay", "np-growth", "np-reviews", "np-orgs"],
    "performance": ["pf-overview", "pf-spending", "pf-staffing", "pf-outcomes", "pf-cost", "pf-integrity", "pf-gaps", "pf-depts"],
    "audits": ["au-overview", "au-status", "au-time", "au-agreement", "au-repeat", "au-open", "au-reports"],
    "network": ["nw-overview", "nw-graph", "nw-ban", "nw-behested", "nw-lobby", "nw-concentration", "nw-loop", "nw-entities"],
}
STORY = {"nonprofits": "story_np", "performance": "story_pf", "audits": "story_au", "network": "story_nw"}

# Template ids each view's code fills (DATA_CONTRACT §3 "Template ids and slots").
TEMPLATE_IDS = {
    "np-overview": ["total"], "np-flows": ["flows"], "np-dependency": ["dep"], "np-pay": ["pay"], "np-growth": ["growth"], "np-reviews": ["reviews"],
    "pf-overview": ["ov"], "pf-spending": ["sp"], "pf-staffing": ["st"], "pf-outcomes": ["oc"], "pf-cost": ["cost"], "pf-integrity": ["int"], "pf-gaps": ["gap"],
    "au-overview": ["ov"], "au-status": ["status"], "au-time": ["time"], "au-agreement": ["agree"], "au-repeat": ["repeat"], "au-open": ["open"],
    "nw-overview": ["ov"], "nw-graph": ["graph"], "nw-ban": ["ban"], "nw-behested": ["beh"], "nw-lobby": ["lob"], "nw-concentration": ["conc"], "nw-loop": ["loop"],
}

# Charts that draw commentary callouts (annotations[].chart), per view.
CHART_IDS = {"np-overview": ["np_trend"], "np-flows": ["np_trend"], "pf-overview": ["pf_trend"], "pf-spending": ["pf_trend"], "pf-staffing": ["pf_ot"],
             "au-overview": ["au_issued"], "au-status": ["au_impl"], "nw-overview": ["nw_dollars"], "nw-behested": ["nw_behested"]}

DIM_SHAPE = {"label": "~str", "values": "list"}

SPEC = {
    "nonprofits": {
        "meta.json": {
            "keys": {"sample": "bool", "module": "str", "as_of": "date", "fiscal_years": "dict", "deflator": "dict", "dimensions": "dict",
                     "counts": "dict", "small_n": "int", "sources": "list", "files": "~dict"},
            "nested": {"fiscal_years": {"min": "int", "max": "int"}, "deflator": {"base_fy": "int", "source": "~str", "index": "dict"}},
            "dims": DIMS["nonprofits"],
        },
        "orgs/index.json": {
            "arrays": {"orgs": {"id": "str", "name": "str", "ein": "~str?", "area": "str", "size_band": "str", "depts": "list",
                                "city_total": "num", "city_fy_latest": "~num?", "first_fy": "int?", "last_fy": "int?", "match": "~dict?", "network_id": "~str?"}},
            "enums": {"orgs.area": "dim:area", "orgs.size_band": "dim:size_band"},
            "unique": "orgs.id",
        },
        "payments/cells.json": {
            "split": "payments/cells_*.json", "key": ["fy", "dept", "org"],
            "arrays": {"cells": {"fy": "int", "dept": "str", "org": "str", "amt": "num", "vouchers": "~int?", "contracts": "~int?"}},
            "enums": {"cells.dept": "dim:dept", "cells.org": "ref:orgs/index.json#orgs.id"},
        },
        "contracts/contracts.json": {
            # contracts/all_*.json (every contract >= $250k) is deliberately NOT merged: the module's commentary
            # describes contracts.json, and the text must never disagree with the charts.
            "arrays": {"contracts": {"id": "str", "org": "str", "dept": "str", "title": "~str?", "start": "date", "end": "~date?", "type": "str",
                                     "sole_source": "~bool?", "original_agreed": "num?", "agreed": "num?", "consumed": "~num?", "amendments": "list"}},
            "enums": {"contracts.type": "grant|professional_services|other", "contracts.org": "ref:orgs/index.json#orgs.id", "contracts.dept": "dim:dept"},
        },
        "finances/form990.json": {
            "split": "finances/form990_*.json", "key": ["org", "fy", "form"],
            "arrays": {"rows": {"org": "str", "fy": "int", "form": "~str?", "total_revenue": "num?", "total_expenses": "num?", "gov_grants": "~num?",
                                "program_share": "~num?", "net_assets": "~num?", "unrestricted_net_assets": "~num?", "months_reserves": "num?",
                                "employees": "~int?", "exec_comp": "num?", "exec_title": "~str?"}},
            "enums": {"rows.org": "ref:orgs/index.json#orgs.id"},
        },
        "reviews/findings.json": {
            "keys": {"results": "list", "categories": "~list"},
            "arrays": {"rows": {"id": "str", "org": "str", "fy": "int", "lead_dept": "~str?", "type": "~str?", "result": "str", "categories": "list",
                                "report": "dict", "note": "~str?"}},
            "enums": {"rows.result": "dim:result", "rows.org": "ref:orgs/index.json#orgs.id"},
            "row_rules": ["review_cites_report"],
        },
    },
    "performance": {
        "meta.json": {
            "keys": {"sample": "bool", "module": "str", "as_of": "date", "fiscal_years": "dict", "deflator": "dict", "population": "dict",
                     "dimensions": "dict", "counts": "dict", "small_n": "int", "sources": "list", "files": "~dict"},
            "nested": {"fiscal_years": {"min": "int", "max": "int"}, "deflator": {"base_fy": "int", "source": "~str", "index": "dict"}, "population": {"by_fy": "dict"}},
            "dims": DIMS["performance"],
        },
        "spending/cells.json": {
            "split": "spending/cells_*.json", "key": ["fy", "dept", "fund", "char"],
            "arrays": {"cells": {"fy": "int", "dept": "str", "fund": "~str?", "char": "str", "budget": "num?", "revised": "~num?", "actual": "num?"}},
            "enums": {"cells.dept": "dim:dept", "cells.char": "dim:char"},
        },
        "staffing/cells.json": {
            "arrays": {"cells": {"fy": "int", "dept": "str", "headcount": "int?", "salaries": "num?", "overtime": "num?", "ot_share": "num?",
                                 "employees_ot_over_100k": "~int?", "top_ot_job_families": "~list?"}},
            "enums": {"cells.dept": "dim:dept"},
        },
        "measures/measures.json": {
            "bundle_drop": {"measures": ["goal", "description", "kind_detail", "mapping", "report_years", "service_area"]},
            "arrays": {"measures": {"id": "str", "dept": "str", "name": "str", "unit": "~str?", "direction": "str", "type": "str",
                                    "first_fy": "~int?", "last_fy": "~int?", "dropped_fy": "~int?", "replaced_by": "~str?"}},
            "enums": {"measures.dept": "dim:dept", "measures.direction": "higher|lower|neutral", "measures.type": "outcome|output|efficiency"},
            "unique": "measures.id",
        },
        "measures/values.json": {
            "split": "measures/values_*.json", "key": ["measure", "fy"],
            "arrays": {"rows": {"measure": "str", "fy": "int", "target": "num?", "actual": "num?", "met": "bool?", "target_change": "~str?",
                                "source_doc": "~str?", "program_cost": "~num?", "cost_per_unit": "~num?"}},
            "enums": {"rows.measure": "ref:measures/measures.json#measures.id", "rows.target_change": "easier|harder|same|new"},
        },
        "measures/cost_links.json": {"optional": True, "arrays": {"links": {"measure": "str", "numerator": "~str?", "denominator": "~str?", "rationale": "~str?"}}},
    },
    "audits": {
        "meta.json": {
            "keys": {"sample": "bool", "module": "str", "as_of": "date", "years": "dict", "dimensions": "dict", "status_mapping": "~dict",
                     "consequence_rule": "~str", "counts": "dict", "small_n": "int", "sources": "list", "files": "~dict"},
            "nested": {"years": {"min": "int", "max": "int"}},
            "dims": DIMS["audits"],
        },
        "reports/reports.json": {
            "arrays": {"reports": {"id": "str", "source": "str", "title": "str", "date": "date", "depts": "list", "topic": "~str?", "url": "~str?",
                                   "pages": "~int?", "n_recs": "~int?", "summary": "~str?", "followups": "~list?"}},
            "enums": {"reports.source": "dim:source"},
            "unique": "reports.id",
        },
        "recs/recs.json": {
            "split": "recs/recs_*.json", "key": ["id"],
            "arrays": {"rows": {"id": "str", "report": "str", "source": "str", "dept": "str", "date_issued": "date", "topic": "str", "priority": "~str?",
                                "text": "str", "agreed": "str", "response_text": "~str?", "status": "str", "status_date": "~date?",
                                "months_to_close": "num?", "last_followup": "~date?", "repeat_of": "~str?", "dollars_at_stake": "~num?", "consequence": "dict"}},
            "enums": {"rows.source": "dim:source", "rows.dept": "dim:dept", "rows.topic": "dim:topic", "rows.status": "dim:status!", "rows.agreed": "dim:agreed",
                      "rows.report": "ref:reports/reports.json#reports.id"},
            "row_rules": ["months_iff_implemented", "consequence_score"],
        },
    },
    "network": {
        "meta.json": {
            "keys": {"sample": "bool", "module": "str", "as_of": "date", "years": "dict", "dimensions": "dict", "rules": "list", "fairness": "dict",
                     "counts": "dict", "small_n": "int", "sources": "list", "files": "~dict"},
            "nested": {"years": {"min": "int", "max": "int"}, "fairness": {"individuals": "str", "timing": "str", "review": "str"}},
            "dims": DIMS["network"],
            "row_rules": ["rules_cited"],
        },
        "entities.json": {
            "arrays": {"entities": {"id": "str", "type": "str", "name": "str", "cluster": "~str?"}},
            "enums": {"entities.type": "dim:etype"},
            "unique": "entities.id",
            "row_rules": ["no_addresses"],
        },
        "flows.json": {
            "bundle_drop": {"flows": ["ref", "sfec126_filing", "period"]},
            "split": "flows/flows_*.json", "key": ["id"],
            "arrays": {"flows": {"id": "str", "from": "str", "to": "str", "type": "str", "date": "date", "amount": "num?", "count": "~int?"}},
            "enums": {"flows.type": "dim:flow", "flows.from": "ref:entities.json#entities.id", "flows.to": "ref:entities.json#entities.id"},
            "row_rules": ["no_addresses"],
        },
        "analyses/ban_window.json": {
            "keys": {"base_rates": "dict"},
            "nested": {"base_rates": {"expected_share_if_unrelated": "num?"}},
            "arrays": {"contracts": {"contract": "str", "contractor": "str", "approval_date": "date", "window": "list"},
                       "records": {"flow": "str", "contractor": "str", "committee": "str", "date": "date", "amount": "num?", "days_from_approval": "num",
                                   "inside_window": "bool", "covered_official": "bool", "review": "str", "why": "~str?"}},
            "enums": {"records.review": "appears_to_warrant_review|inside_window_not_covered|outside_window"},
            "row_rules": ["review_has_reason"],
        },
        "analyses/behested.json": {
            "arrays": {"rows": {"flow": "str", "official": "str?", "payor": "str", "payee": "str", "date": "date", "amount": "num?", "purpose": "~str?",
                                "payor_interested_party": "bool", "filed_within_30_days": "~bool?"}},
        },
        "analyses/lobbying.json": {
            "arrays": {"rows": {"flow": "str", "lobbyist": "str", "client": "str", "target": "str", "month": "~str?", "topic": "~str?", "contacts": "int"}},
        },
        "analyses/concentration.json": {
            "arrays": {"rows": {"committee": "str", "official": "~str?", "cycle": "~str?", "total": "num", "n_contributions": "~int?", "by_source_type": "dict",
                                "top10_share_named": "~num?", "n_named_sources": "~int?"}},
        },
        "analyses/loop.json": {
            "keys": {"note": "str"},
            "arrays": {"rows": {"entity": "str", "org": "~str?", "city_paid": "num?", "depts_funding": "list", "depts_lobbied": "list"}},
        },
    },
}

COMMENTARY = {"headline": "~str?", "paragraphs": "~list", "annotations": "~list", "templates": "~list", "caveats": "~list", "sources": "~list", "sample": "~bool"}
STORY_SPEC = {"title": "str", "steps": "list"}

# Words that must not appear in commentary unless negated nearby (fairness lint; warnings only).
FAIRNESS_WORDS = ["violated", "violation", "illegal", "corrupt", "kickback", "bribe", "fraud", "pay-to-play", "quid pro quo"]
