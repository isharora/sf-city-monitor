"""Division-level budgets and funded positions from the Mayor's Proposed FY2026-27/FY2027-28 Budget Book
("Department Total Budget Historical Comparison" pages): FY2025-26 original budget, FY2026-27 and FY2027-28 proposed.
The open Budget dataset lost program detail at the FY2018 cutover; these division tables restore it for current years.
Pages are transcribed by Claude Sonnet reading each page visually (blank 'change' cells make text-layer parsing
ambiguous). Output: data/interim/budget_book_divisions.csv, budget_book_positions.csv
"""
import pypdf, os, sys, io, base64, json
import pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from common import RAW, INTERIM
from llm import run_many

PDF = os.path.join(RAW, 'perf_measures', 'reports', 'BudgetBook_FY27_FY28_Mayor_Proposed.pdf')
SYSTEM = ("Transcribe the San Francisco budget book page exactly as printed. Columns are: 2025-2026 Original Budget, "
          "2026-2027 Proposed Budget, Change from 2025-2026, 2027-2028 Proposed Budget, Change from 2026-2027. A blank cell "
          "means no amount (report null), and parentheses mean negative. Never compute values.")
ROW = {'type': 'object', 'properties': {'label': {'type': 'string'}, 'fy2026_original': {'type': ['number', 'null']},
       'fy2027_proposed': {'type': ['number', 'null']}, 'fy2028_proposed': {'type': ['number', 'null']}},
       'required': ['label', 'fy2026_original', 'fy2027_proposed', 'fy2028_proposed'], 'additionalProperties': False}
SCHEMA = {'type': 'object', 'properties': {
    'department_code': {'type': 'string'}, 'department_name': {'type': 'string'},
    'divisions': {'type': 'array', 'items': ROW, 'description': "rows under 'Uses - By Division Description' (not the total)"},
    'total_funded_positions': {'type': 'array', 'items': ROW, 'description': "the 'Total Funded' and 'Net Operating Positions' rows if on this page"}},
    'required': ['department_code', 'department_name', 'divisions', 'total_funded_positions'], 'additionalProperties': False}


def main():
    r = pypdf.PdfReader(PDF)
    jobs = []
    for i, p in enumerate(r.pages):
        t = p.extract_text() or ''
        if 'Department Total Budget Historical Comparison' in t:
            w = pypdf.PdfWriter(); w.add_page(p); b = io.BytesIO(); w.write(b)
            content = [{'type': 'document', 'source': {'type': 'base64', 'media_type': 'application/pdf',
                                                       'data': base64.standard_b64encode(b.getvalue()).decode()}},
                       {'type': 'text', 'text': 'Transcribe the division rows and funded-position totals on this page.'}]
            jobs.append((i + 1, dict(task='budget_book_divisions', model='claude-sonnet-5', system=SYSTEM, prompt=content,
                                     schema=SCHEMA, effort='low', max_tokens=8000)))
    print('pages:', len(jobs))
    res = run_many(jobs, workers=12)
    rows, pos = [], []
    for pg, v in sorted(res.items()):
        if isinstance(v, Exception):
            print('ERR', pg, v); continue
        for d in v['divisions']:
            rows.append({'dept': v['department_code'].strip()[:4].strip(), 'division': d['label'], 'fy2026_original': d['fy2026_original'],
                         'fy2027_proposed': d['fy2027_proposed'], 'fy2028_proposed': d['fy2028_proposed'], 'page': pg})
        for d in v['total_funded_positions']:
            pos.append({'dept': v['department_code'].strip()[:4].strip(), 'row': d['label'], 'fy2026': d['fy2026_original'],
                        'fy2027': d['fy2027_proposed'], 'fy2028': d['fy2028_proposed'], 'page': pg})
    d = pd.DataFrame(rows)
    # repair department codes the model read from the wrong place (page numbers, truncated names):
    # division labels carry the department prefix (e.g. 'ASR Recorder'); DPH divisions use H-prefixed codes
    import re as _re
    from common import DEPT_NAMES
    def fix(r):
        if r.dept in DEPT_NAMES:
            return r.dept
        tok = str(r.division).split()[0]
        if tok in DEPT_NAMES:
            return tok
        return 'DPH' if r.dept == 'PUBL' else r.dept
    d['dept'] = d.apply(fix, axis=1)
    d = d.drop_duplicates(['dept', 'division'])
    d.to_csv(os.path.join(INTERIM, 'budget_book_divisions.csv'), index=False)
    pd.DataFrame(pos).to_csv(os.path.join(INTERIM, 'budget_book_positions.csv'), index=False)
    print('divisions:', len(d), 'departments:', d.dept.nunique())
    return d


if __name__ == '__main__':
    d = main()
    pd.set_option('display.width', 200)
    print(d[d.dept.isin(['DPW', 'FIR', 'POL', 'DEM', 'ADM'])].to_string(index=False))
