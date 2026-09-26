"""Red team, finding E: classify WHY each contract ceiling at least doubled (Claude, cached, logged).

Input: data/redteam/parts/doubled_contracts.json (from rt_findings.py): for each contract whose current
awarded amount is >= 2x its earliest observed amount, the title and 'Scope of Work' text from Supplier
Contracts (both are short, <= 30 characters), department, type, purchasing authority, term start, the amount
and end date at every snapshot, the per-year-of-term ("annualized") ceiling ratio, and actual payments by
fiscal year from Vendor Payments.

Claude (claude-opus-5-5, adaptive thinking, effort high) assigns a primary driver and a confidence:
  extension          - ceiling raised mainly to cover added years at a similar annual level
  expansion          - the annual level rose substantially: more services, new programs, more beds/sites/units
  funding_increment  - term unchanged; later years of an already-approved term funded by amendment
  rate_or_volume     - same services, higher cost per unit or more clients, without evidence of new scope
  unclear            - the record cannot distinguish these
plus whether the title/scope text itself shows new scope or new sites (usually it cannot), and a rationale.
Output: data/redteam/parts/contracts_llm.json
"""
import json, os, sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import lib_llm  # noqa: E402

BASE = os.path.join(HERE, "..", "..", "data")
PARTS = os.path.join(BASE, "redteam", "parts")
MODEL = "claude-opus-5-5"
SYSTEM = ("You are a public-finance analyst who knows San Francisco's contracting practice: multi-year nonprofit "
          "grants and professional-services agreements are routinely amended to add years and money, departments "
          "often certify funding one fiscal year at a time, and emergency ordinances (COVID-19, 2023 homelessness and "
          "behavioral-health ordinance) allowed quick amendments. You judge only from the record given. You never "
          "imply wrongdoing: a larger contract is a budgeting and service decision, not evidence of impropriety.")
SCHEMA = {"type": "object", "additionalProperties": False,
          "properties": {"primary_driver": {"type": "string", "enum": ["extension", "expansion", "funding_increment", "rate_or_volume", "unclear"]},
                         "secondary_driver": {"type": "string", "enum": ["extension", "expansion", "funding_increment", "rate_or_volume", "none"]},
                         "text_shows_new_scope_or_sites": {"type": "string", "enum": ["yes", "no", "cannot_tell"]},
                         "rationale": {"type": "string"},
                         "confidence": {"type": "number"}},
          "required": ["primary_driver", "secondary_driver", "text_shows_new_scope_or_sites", "rationale", "confidence"]}


def prompt(c, name):
    hist = "; ".join(f"{h['snapshot']}: ${h['amt']:,.0f}, term ends {h['end']}" for h in c["history"])
    pays = ", ".join(f"FY{k}: ${v:,.0f}" for k, v in sorted(c["paid_by_fy"].items())) or "none found"
    return f"""Classify why this San Francisco contract's awarded ceiling at least doubled between snapshots.

Contractor: {name}
Department: {c['dept']}
Contract title: {c['title']}
Scope of work field: {c['scope']}
Contract type: {c['type']}
Purchasing authority: {c['authority']}
Term start: {c['start']}
Awarded amount and term end at each observation: {hist}
Ratio of current to earliest amount: {c['now'] / c['orig']:.2f}
Ratio of amount per year of term (current vs earliest; >1 means more money per year): {c['annualized_ratio'] if c['annualized_ratio'] is None else round(c['annualized_ratio'], 2)}
Actual payments on this contract by city fiscal year (FY2027 is partial, Jul-Sep 2026): {pays}

Definitions:
- extension: the increase mainly pays for added years at roughly the same annual level (amount per year of term up by less than about 1.5x, and yearly payments roughly steady apart from inflation).
- expansion: the annual level rose substantially (amount per year and yearly payments up well beyond inflation), consistent with more services, programs, beds, sites or units.
- funding_increment: the term end did not move; money for years already inside the approved term was added.
- rate_or_volume: same services at higher cost or volume, where nothing indicates new scope.
- unclear: the record cannot distinguish.
Use both the amount-per-year ratio and the payment history (payments are the best evidence of the real annual level). The title and scope fields are short; say "cannot_tell" unless they explicitly name a new program, site or phase. Confidence 0-1."""


def main():
    doubled = json.load(open(os.path.join(PARTS, "doubled_contracts.json")))
    names = {o["id"].replace("org-", ""): o["name"] for o in json.load(open(os.path.join(BASE, "site", "orgs", "index.json")))["orgs"]}
    def run(c):
        r = lib_llm.call_json("redteam_contract_growth", prompt(c, names.get(c["ein"], c["ein"])), SCHEMA, model=MODEL,
                              system=SYSTEM, effort="high", max_tokens=6000)
        return {"id": c["id"], "ein": c["ein"], "name": names.get(c["ein"]), "title": c["title"], "dept": c["dept"],
                "orig": c["orig"], "now": c["now"], "annualized_ratio": c["annualized_ratio"], "run_rate_ratio": c["run_rate_ratio"],
                "term_extended_days": c["term_extended_days"], **r}
    with ThreadPoolExecutor(8) as ex:
        out = list(ex.map(run, doubled))
    json.dump(out, open(os.path.join(PARTS, "contracts_llm.json"), "w"), indent=1)
    from collections import Counter
    print(Counter(o["primary_driver"] for o in out), Counter(o["text_shows_new_scope_or_sites"] for o in out))


if __name__ == "__main__":
    main()
