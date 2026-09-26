"""Extract measure-level tables from the Controller's annual Performance Measures PDF reports
(FY2006-FY2019, FY2022) using Claude Sonnet reading one PDF page at a time (visual + text).

Output: data/interim/pdf_measures_raw.jsonl  (one line per page, raw extraction)
        data/interim/pdf_measures_long.csv    (report, page, department, goal, measure, column, value)
Usage: python3 13_extract_pdf_measures.py [--sample N] [--reports FY2010,FY2017]
"""
import os, sys, io, json, base64, argparse, re
import pypdf
import pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from common import RAW, INTERIM
from llm import run_many

REPORTS = {
    'FY2006': 'FY2006_PerfMeas_All2006.pdf', 'FY2007': 'FY2007_PerfMeas_Dept061307.pdf',
    'FY2008': 'FY2008_PM_0708Report.pdf', 'FY2009': 'FY2009_AnnualYearEndPM.pdf',
    'FY2010': 'FY2010_AnnualYearEndPM.pdf', 'FY2011': 'FY2011_AnnualYearEndPM.pdf',
    'FY2012': 'FY2012_PM_Annual_Report.pdf', 'FY2013': 'FY2013_City_Services_PM_Report.pdf',
    'FY2014': 'FY2014_Citywide_PM_Annual_Report.pdf', 'FY2015': 'FY2015_Performance_Annual_Report.pdf',
    'FY2016': 'FY2016_Scorecards_Update_and_Measures.pdf', 'FY2017': 'FY2017_Annual_Performance_Report.pdf',
    'FY2018': 'FY2018_Annual_Performance_Report.pdf', 'FY2019': 'FY2019_Annual_Performance_Report.pdf',
    'FY2022': 'FY2022_APR_with_Appendix.pdf',
}
PDIR = os.path.join(RAW, 'perf_measures', 'reports')
MODEL = 'claude-sonnet-5'

SYSTEM = """You transcribe performance-measure tables from San Francisco Controller's Office annual performance reports.
Transcribe exactly what is printed. Never compute, infer, round, or fill in values. If a cell is blank, omit it.
Keep numbers as printed (including %, $, commas, 'N/A', '-', 'n/a'). Column labels must combine the fiscal year and the
column type exactly as printed in the header (e.g. "2009-2010 Target", "2009-2010 Actual", "2010-2011 Target",
"2006-2007 6 Mos Actual", "Change from 2016 to 2017"). Include flag columns such as "New?", "Del?", "Mayor's Budget Book?"
as cells too. If the page has no measure table (cover, narrative, charts only, table of contents), set is_measure_table false
and return no rows. The measure text must be the full measure wording (join wrapped lines)."""

SCHEMA = {
    'type': 'object',
    'properties': {
        'is_measure_table': {'type': 'boolean'},
        'department': {'type': 'string', 'description': 'Department named in the page header, as printed; empty if none'},
        'rows': {'type': 'array', 'items': {
            'type': 'object',
            'properties': {
                'program_or_goal': {'type': 'string', 'description': 'Nearest program / goal / section heading above the measure'},
                'measure': {'type': 'string'},
                'cells': {'type': 'array', 'items': {
                    'type': 'object',
                    'properties': {'column': {'type': 'string'}, 'value': {'type': 'string'}},
                    'required': ['column', 'value'], 'additionalProperties': False}},
            },
            'required': ['program_or_goal', 'measure', 'cells'], 'additionalProperties': False}},
    },
    'required': ['is_measure_table', 'department', 'rows'], 'additionalProperties': False,
}


def page_pdf_b64(reader, i):
    w = pypdf.PdfWriter()
    w.add_page(reader.pages[i])
    buf = io.BytesIO()
    w.write(buf)
    return base64.standard_b64encode(buf.getvalue()).decode()


def jobs_for(rep, fname, pages=None):
    r = pypdf.PdfReader(os.path.join(PDIR, fname))
    idx = range(len(r.pages)) if pages is None else pages
    jobs = []
    for i in idx:
        content = [{'type': 'document', 'source': {'type': 'base64', 'media_type': 'application/pdf',
                                                    'data': page_pdf_b64(r, i)}},
                   {'type': 'text', 'text': f'Report {rep}, page {i+1}. Transcribe every performance measure row on this page.'}]
        jobs.append(((rep, i + 1), dict(task=f'pdf_extract_{rep}', model=MODEL, system=SYSTEM, prompt=content,
                                        schema=SCHEMA, effort='low', max_tokens=16000)))
    return jobs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sample', type=int, default=0)
    ap.add_argument('--reports', default='')
    ap.add_argument('--workers', type=int, default=8)
    a = ap.parse_args()
    reps = a.reports.split(',') if a.reports else list(REPORTS)
    jobs = []
    for rep in reps:
        fname = REPORTS[rep]
        n = len(pypdf.PdfReader(os.path.join(PDIR, fname)).pages)
        pages = None
        if a.sample:
            step = max(1, n // a.sample)
            pages = list(range(step // 2, n, step))[:a.sample]
        jobs += jobs_for(rep, fname, pages)
    print(f'{len(jobs)} page jobs')
    res = run_many(jobs, workers=a.workers)
    errs = {k: str(v) for k, v in res.items() if isinstance(v, Exception)}
    print('errors:', len(errs), list(errs.items())[:5])
    if a.sample:
        for k, v in sorted(res.items()):
            if not isinstance(v, Exception):
                print(k, v['department'], len(v['rows']), json.dumps(v['rows'][:2])[:600])
        return
    # full run: write outputs from cache (all reports)
    rows = []
    with open(os.path.join(INTERIM, 'pdf_measures_raw.jsonl'), 'w') as f:
        for (rep, pg), v in sorted(res.items()):
            if isinstance(v, Exception):
                continue
            f.write(json.dumps({'report': rep, 'page': pg, **v}) + '\n')
            for r_i, row in enumerate(v['rows']):
                for c in row['cells']:
                    rows.append({'report': rep, 'page': pg, 'row': r_i, 'department': v['department'],
                                 'goal': row['program_or_goal'], 'measure': row['measure'],
                                 'column': c['column'], 'value': c['value']})
    pd.DataFrame(rows).to_csv(os.path.join(INTERIM, 'pdf_measures_long.csv'), index=False)
    print('cells:', len(rows))


if __name__ == '__main__':
    main()
