"""Read every CSA field follow-up memo (Claude Opus 5.5, cached) and record, per memo, what the department had
reported before the field check and what CSA auditors found.

Output: data/insights_work/field_followups.json  {doc_id: {...counts, verbatim quote + page, rationale, confidence}}
Every quote is re-checked word for word against the PDF text by verify_insights.py before any number is used.
Run: python3 pipeline/insights/field_followups.py
"""
import os, sys, json
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from llm import call_json, OPUS

ROOT = os.path.dirname(os.path.dirname(HERE))
DATA = os.path.join(ROOT, 'data')
OUT = os.path.join(DATA, 'insights_work', 'field_followups.json')
SYSTEM = """You read San Francisco Controller's Office (City Services Auditor, CSA) field follow-up memos. In a field
follow-up, CSA auditors check documentary evidence for recommendations from an earlier audit, usually the ones the
department had reported as implemented. Extract exactly what the memo states. Use null when the memo does not say.
Quotes must be copied character for character from one page of the text (no ellipses, no edits), 10-60 words."""
SCHEMA = {'type': 'object', 'properties': {
    'audited_department': {'type': 'string'},
    'n_recs_in_original_audit': {'type': ['integer', 'null']},
    'n_recs_followed_up': {'type': ['integer', 'null']},
    'scope': {'type': 'string', 'enum': ['only_recs_dept_reported_implemented', 'all_or_selected_recs', 'unclear']},
    'n_dept_reported_implemented': {'type': ['integer', 'null'], 'description': 'how many the department had reported (self-reported) as implemented before the field check'},
    'of_those_csa_confirmed_implemented': {'type': ['integer', 'null']},
    'of_those_csa_found_partial_or_not': {'type': ['integer', 'null']},
    'of_those_closed_no_longer_applicable': {'type': ['integer', 'null']},
    'csa_found_implemented_total': {'type': ['integer', 'null']},
    'csa_found_partial_or_not_total': {'type': ['integer', 'null']},
    'csa_found_not_applicable_total': {'type': ['integer', 'null']},
    'quote': {'type': 'string', 'description': 'verbatim sentence stating the result or the self-report comparison'},
    'quote_page': {'type': 'integer'},
    'rationale': {'type': 'string'}, 'confidence': {'type': 'number'}},
    'required': ['audited_department', 'n_recs_in_original_audit', 'n_recs_followed_up', 'scope', 'n_dept_reported_implemented',
                 'of_those_csa_confirmed_implemented', 'of_those_csa_found_partial_or_not', 'of_those_closed_no_longer_applicable',
                 'csa_found_implemented_total', 'csa_found_partial_or_not_total', 'csa_found_not_applicable_total',
                 'quote', 'quote_page', 'rationale', 'confidence'], 'additionalProperties': False}


def main():
    inv = [d for d in json.load(open(os.path.join(DATA, 'raw', 'inventory.json'))) if d['doc_type'] == 'csa_field_followup']
    out = {}

    def run(d):
        pages = json.load(open(os.path.join(DATA, 'text', d['doc_id'] + '.json')))['pages']
        txt = '\n'.join(f'[[PAGE {i + 1}]]\n{p}' for i, p in enumerate(pages))
        prompt = f"Memo {d['doc_id']}: {d['title']} ({d['date']})\n\n{txt}"
        r, _ = call_json('insights_field_followups', OPUS, SYSTEM, prompt, SCHEMA, effort='high', max_tokens=32000)
        return d['doc_id'], {**r, 'title': d['title'], 'date': d['date']}
    with ThreadPoolExecutor(6) as ex:
        for k, v in ex.map(run, inv):
            out[k] = v
    json.dump(out, open(OUT, 'w'), indent=1, ensure_ascii=False)
    print(len(out), 'memos')


if __name__ == '__main__':
    main()
